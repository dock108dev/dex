"""Finite Pokédex criteria and one three-valued matching policy. No writes or acquisition."""

import calendar
import json
from datetime import date
from urllib.parse import urlencode

from . import catalog_coverage, store

MULTI = {"set", "era", "type", "rarity", "finish", "released", "year"}
DATES = {"date_from", "date_to"}
KEYS = MULTI | DATES | {"card"}
MAX_VALUES = 8
MAX_FIELD = 1400
MAX_ENCODED = 1500  # Reserve bounded room for scroll/focus in the 1,800-byte list context.


def values(value):
    """One value preserves old URLs; JSON arrays carry multivalues without delimiter collisions."""
    if not isinstance(value, str) or len(value) > MAX_FIELD:
        raise ValueError("Choose shorter scope values")
    parsed = json.loads(value) if value.startswith("[") else ([value] if value else [])
    if (
        not isinstance(parsed, list)
        or len(parsed) > MAX_VALUES
        or any(
            not isinstance(v, str) or not v or len(v) > 160 or any(ord(c) < 32 or ord(c) == 127 for c in v)
            for v in parsed
        )
    ):
        raise ValueError("Choose up to eight values per dimension")
    return sorted(set(parsed))


def encode(items):
    return (
        items[0]
        if len(items) == 1
        else json.dumps(items, ensure_ascii=False, separators=(",", ":"))
        if items
        else ""
    )


def validate(raw):
    result = {key: encode(values(raw.get(key, ""))) for key in MULTI}
    for key in DATES:
        value = raw.get(key, "")
        if (
            not isinstance(value, str)
            or value
            and (len(value) != 10 or date.fromisoformat(value).isoformat() != value)
        ):
            raise ValueError("Use an ISO calendar date")
        result[key] = value
    if result["date_from"] and result["date_to"] and result["date_from"] > result["date_to"]:
        raise ValueError("The inclusive start must precede the inclusive end")
    if set(values(result["released"])) - {"pre-2000", "2000-onward", "Unknown"}:
        raise ValueError("Choose a supported release period")
    if any(
        not v.isascii() or not v.isdecimal() or not 1996 <= int(v) <= 2100 or len(v) != 4
        for v in values(result["year"])
    ):
        raise ValueError("Choose a supported release year")
    if len(urlencode({k: v for k, v in result.items() if v})) > MAX_ENCODED:
        raise ValueError("Choose a smaller combined scope for navigation")
    return result


def interval(value):
    """Preserve source precision; a year/month is an interval, never January 1 proof."""
    try:
        if len(value) == 4:
            year = int(value)
            return date(year, 1, 1).isoformat(), date(year, 12, 31).isoformat()
        if len(value) == 7:
            y, m = map(int, value.split("-"))
            return date(y, m, 1).isoformat(), date(y, m, calendar.monthrange(y, m)[1]).isoformat()
        if len(value) == 10:
            return (date.fromisoformat(value).isoformat(),) * 2
    except (ValueError, TypeError):
        pass
    return None


def release_dates():
    """Hash-checked retained English evidence, joined by exact external identity only.

    Promo series start dates cannot date their individual releases. The source's
    English date is not a US/UK/Japanese or edition-specific release claim.
    """
    manifest, aliases = catalog_coverage.coverage_profile()
    by_id = {r["id"]: r for r in manifest["sets"]}
    external = {(r["provider"] + ":" + r["language"], r["provider_set_id"]): r for r in by_id.values()}
    for assessment, canonical in aliases.items():
        provider, language, key = assessment.split(":", 2)
        external[provider + ":" + language, key] = by_id[canonical]
    candidates = {}
    for mapping in store.rows("SELECT * FROM external_mappings WHERE entity_kind='set'"):
        source = external.get((mapping["provider"], mapping["external_id"]))
        if not source or source["language"] != "en" or source["medium"] != "physical":
            continue
        # Distributions within these rolling series require per-card evidence.
        if "promo" in source["name"].casefold():
            continue
        bounds = interval(source.get("release_date") or "")
        if bounds and source.get("source_status") == "retained-usable":
            candidates.setdefault(mapping["internal_id"], []).append(
                dict(
                    start=bounds[0],
                    end=bounds[1],
                    precision={4: "year", 7: "month", 10: "day"}[len(source["release_date"])],
                    language="en",
                    region="Unresolved",
                    source_url=source["source_url"],
                    source_sha256=source["source_sha256"],
                )
            )
    return {
        key: rows[0] for key, rows in candidates.items() if len({(r["start"], r["end"]) for r in rows}) == 1
    }


def metadata(card, dates):
    return dict(
        set=card["set_id"],
        set_name=card["set_name"],
        era=card["era"],
        type=card["supertype"],
        rarity=card["rarity"],
        finish=card["finish"] or "Unknown",
        card=f"{card['name']} {card['collector_number']}",
        release=dates.get(card["set_id"]) if card.get("language") == "en" else None,
    )


def date_match(evidence, selected):
    periods, years = values(selected.get("released", "")), values(selected.get("year", ""))
    lower, upper = selected.get("date_from", ""), selected.get("date_to", "")
    if not (periods or years or lower or upper):
        return True
    if evidence is None:
        return True if "Unknown" in periods and not (years or lower or upper) else None
    start, end = evidence["start"], evidence["end"]
    ranges = [("0001-01-01", "9999-12-31")]
    for options in (
        [("0001-01-01", "1999-12-31") for p in periods if p == "pre-2000"]
        + [("2000-01-01", "9999-12-31") for p in periods if p == "2000-onward"]
        if periods
        else ranges,
        [(y + "-01-01", y + "-12-31") for y in years] if years else ranges,
        [(lower or "0001-01-01", upper or "9999-12-31")],
    ):
        ranges = [(max(a, c), min(b, d)) for a, b in ranges for c, d in options if max(a, c) <= min(b, d)]
    spans = sorted((max(start, a), min(end, b)) for a, b in ranges if max(start, a) <= min(end, b))
    if not spans:
        return False
    # Adjacent selected years/periods may jointly cover an imprecise interval.
    covered = start
    for a, b in spans:
        if a > covered:
            return None
        if b >= end:
            return True
        covered = date.fromordinal(date.fromisoformat(b).toordinal() + 1).isoformat()
    return None


def match(evidence, selected):
    """True = supported, False = excluded, None = insufficient evidence. AND on one card."""
    checks = [date_match(evidence.get("release"), selected)]
    for key in ("set", "era", "type", "rarity", "finish"):
        wanted = values(selected.get(key, ""))
        if not wanted:
            continue
        value = evidence.get(key)
        if value in {None, "Unknown"}:
            # A metadata gap is not an attestation of a physical attribute.
            # Only the explicit Unknown *date* scope has unknown-bucket semantics.
            checks.append(None)
        else:
            checks.append(value in wanted or key == "set" and evidence.get("set_name") in wanted)
    if selected.get("card"):
        value = evidence.get("card")
        checks.append(selected["card"].casefold() in value.casefold() if value else None)
    return False if False in checks else None if None in checks else True


def owned_evidence(row, indexed, set_facts=None):
    """Broad possession supports common identity facts, never an inferred finish."""
    candidates = [indexed[key] for key in row["printing_ids"] if key in indexed]
    broad = dict(card=f"{row['name']} {row['number']}", set_name=row["set_name"], finish=None)
    for key in ("set", "era", "type", "rarity", "release"):
        items = [r.get(key) for r in candidates]
        broad[key] = items[0] if items and all(v == items[0] for v in items) else None
    if not candidates and set_facts and row["set_name"] in set_facts:
        # A fully literal owned card can establish a unique expansion even when
        # that individual card has no indexed printing. Species-only marks never
        # enter this boundary. Set facts confer no rarity or physical finish.
        broad.update(set_facts[row["set_name"]])
        broad["type"] = "Pokémon" if row.get("pokemon_dex") else None
    # Even a single catalog candidate does not establish the owned physical finish.
    result = [broad]
    for key in set(row["exact_printing_owned_ids"]) | set(row.get("owned_variant_printing_ids", [])):
        if key in indexed:
            result.append(indexed[key])
    if row.get("owned_variant") == "normal":
        result[0] = {**broad, "finish": "normal"}
    return result


def classify(evidence, selected):
    checks = [match(row, selected) for row in evidence]
    return "collected" if True in checks else "unresolved" if None in checks else "outside"
