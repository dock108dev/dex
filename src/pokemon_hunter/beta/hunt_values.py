"""Dated guide comparisons, keeping seller clues and unknown lot contents conditional."""

import ipaddress
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit

MAX_VALUE = Decimal("1000000000000")


class GuideContext:
    """One search's immutable source index and reusable matching/benchmark cache."""

    def __init__(self, records):
        self.index = {}
        self.matches = {}
        self.benchmarks = {}
        for record in records if isinstance(records, list) else []:
            if isinstance(record, dict) and isinstance(record.get("card_id"), str):
                self.index.setdefault(record["card_id"], []).append(record)


def prepare_records(records):
    """Prepare once per saved-search projection; preserve source precedence on ties."""
    return records if isinstance(records, GuideContext) else GuideContext(records)


def _amount(value):
    try:
        result = Decimal(str(value))
        return result if result.is_finite() and 0 <= result <= MAX_VALUE else None
    except (InvalidOperation, TypeError, ValueError):
        return None


def _money(value):
    return str(value.quantize(Decimal(".01"))) if value is not None else None


def _source(value):
    if (
        not isinstance(value, str)
        or len(value) > 2000
        or any(ord(c) <= 32 or ord(c) == 127 or c == "\\" for c in value)
    ):
        return None
    try:
        parsed = urlsplit(value)
        host = parsed.hostname or ""
        if (
            parsed.scheme != "https"
            or parsed.username is not None
            or parsed.password is not None
            or parsed.port not in (None, 443)
            or not re.fullmatch(r"[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+", host)
            or host.endswith(".localhost")
        ):
            return None
        try:
            if not ipaddress.ip_address(host).is_global:
                return None
        except ValueError:
            pass
    except ValueError:
        return None
    return value


def _valid(record, today, *, guide):
    if not isinstance(record, dict) or record.get("currency", "USD" if not guide else None) != "USD":
        return None
    if guide and record.get("variant_verified") is not True:
        return None
    source = _source(record.get("source_url") or (None if guide else record.get("source")))
    try:
        observed = date.fromisoformat(record["as_of"])
        if not 0 <= (today - observed).days <= 30:
            return None
    except (KeyError, TypeError, ValueError):
        return None
    value = _amount(record.get("value"))
    if source is None or value is None:
        return None
    return {"guidevalue": _money(value), "source_url": source, "as_of": observed.isoformat()}


def _clues(row):
    text = " ".join(str(row.get(key) or "") for key in ("title", "shortDescription", "condition"))
    first = bool(re.search(r"\b(?:first|1st)\s*[- ]?edition\b", text, re.I))
    standard = bool(re.search(r"\b(?:unlimited|standard\s+edition)\b", text, re.I))
    negated = bool(re.search(r"\b(?:not|no|non)[ -]+(?:first|1st)\s*[- ]?edition\b", text, re.I))
    edition = "first_edition" if first and not standard and not negated else "standard"
    edition_known = standard and not first or first and not standard and not negated
    grades = re.findall(r"\b(PSA|BGS|CGC|SGC)\s*[-:]?\s*(10|[1-9](?:\.5)?)(?![\d.])\b", text, re.I)
    generic_grade = bool(
        re.search(r"\b(?:graded|grade\s*\d|gem\s*mint|slab|(?:PSA|BGS|CGC|SGC)\s*[-:]?\s*\d)", text, re.I)
    )
    grade = (grades[0][0].upper(), grades[0][1]) if len(set(grades)) == 1 else None
    return text, edition, bool(edition_known), grade, bool(grades or generic_grade)


def _guide(key, edition, grade, records, today):
    cache_key = (key, edition, grade, today)
    if isinstance(records, GuideContext) and cache_key in records.matches:
        return records.matches[cache_key]
    entries = records.index.get(key, []) if isinstance(records, GuideContext) else records
    if isinstance(entries, dict):
        entries = entries.get(key, [])
    wanted = grade[1] if grade else "raw"
    matches = []
    for record in entries:
        if not isinstance(record, dict) or (
            record.get("card_id") != key
            or record.get("edition") != edition
            or str(record.get("grade")) != wanted
        ):
            continue
        valid = _valid(record, today, guide=True)
        if valid is None:
            continue
        grader = record.get("grader")
        if grade:
            # PriceCharting's stored grade-10 field is PSA 10. Its general grade
            # 7/8/9 scenarios do not establish matching PSA/BGS/CGC grades.
            pricecharting_psa10 = (
                grade == ("PSA", "10")
                and grader == "Guide"
                and urlsplit(valid["source_url"]).hostname in {"pricecharting.com", "www.pricecharting.com"}
                and not record.get("estimated")
            )
            if grader != grade[0] and not pricecharting_psa10:
                continue
            if record.get("estimated"):
                continue
        elif grader not in {"Guide", "PSA"}:
            continue
        matches.append({**valid, "card_id": key, "grade": wanted, "edition": edition})
    # A fresher observation wins; on the same date, the first source supplied
    # wins so an explicit refreshed snapshot can supersede retained evidence.
    match = max(matches, key=lambda r: r["as_of"]) if matches else None
    if isinstance(records, GuideContext):
        records.matches[cache_key] = match
    return match


def _raw(key, edition, condition, values, today):
    if edition != "standard" or not isinstance(values, dict):
        return None
    basis = {
        "lightly played": "LP",
        "lightly played (excellent)": "LP",
        "near mint": "NM",
        "near mint or better": "NM",
    }.get(str(condition).casefold())
    entries = values.get(key)
    record = entries.get(basis) if isinstance(entries, dict) and basis else None
    if not isinstance(record, dict):
        return None
    valid = _valid(record, today, guide=False)
    if valid is None or record.get("edition", "standard") != edition:
        return None
    return {**valid, "card_id": key, "grade": "raw", "edition": edition}


def _scope_cards(cards, scope):
    if not isinstance(scope, dict):
        return cards
    definition = scope.get("definition", scope)
    if not isinstance(definition, dict) or not isinstance(definition.get("items"), list):
        return cards
    allowed = {key for item in definition["items"] for key in item.get("printing_ids", [])}
    return {key: card for key, card in cards.items() if key in allowed or card.get("printing_id") in allowed}


def price_comparison(row, data, guide_records, raw_values, scope=None, *, today=None):
    """Return aggregate strings and reveal-only evidence; never predict unknown contents."""
    today = today or date.today()
    cards = _scope_cards(data.get("cards", {}), scope)
    records = guide_records if isinstance(guide_records, (list, dict, GuideContext)) else []
    keys = list(dict.fromkeys(key for key in row.get("cards", []) if key in cards))
    count = row.get("count")
    count = count if type(count) is int and 0 < count <= 100000 else None
    delivered = _amount(row.get("delivered"))
    text, edition, edition_known, grade, graded = _clues(row)
    lot_assumption = bool(keys) and (
        len(keys) > 1 or count is not None and count > 1 or row.get("pool") == "known_lots"
    )
    if lot_assumption:
        # A mention attached to one card cannot establish every card's edition
        # or grade. Lots get a transparent raw/standard scenario, not inflation
        # from a graded or first-edition clue elsewhere in the seller text.
        edition, edition_known, grade, graded = "standard", False, None, False
    result = {
        "status": "unavailable",
        "basis": "unavailable",
        "reference_total": None,
        "delivered": _money(delivered),
        "saving": None,
        "discount_percent": None,
        "priced_cards": 0,
        "identified_cards": len(keys),
        "lot_count": count,
        "coverage": 0,
        "average_per_card": None,
        "source_dates": [],
        "note": "No current matching guide evidence. Prices exclude tax; guide values are not appraisals.",
        "evidence": [],
    }
    if graded and grade is None:
        result["note"] = "Grade or grader is unclear; no matching graded comparison is established."
        return result
    if count == 1 and len(keys) > 1:
        result["note"] = "Multiple candidate identities; a single-card reference is unavailable."
        return result
    if count and len(keys) > count:
        result["note"] = (
            "Candidate identities exceed the stated lot count; a reliable subtotal is unavailable."
        )
        return result
    priced = []
    for key in keys:
        record = None if grade else _raw(key, edition, row.get("condition"), raw_values, today)
        record = record or _guide(key, edition, grade, records, today)
        if record:
            priced.append(record)
    if keys and priced:
        full = len(priced) == len(keys) and (
            count == len(keys) or row.get("pool") == "singles" and len(keys) == 1 and count is None
        )
        result["status"] = ("matched" if edition_known else "conditional") if full else "partial"
        result["basis"] = ("graded_guide" if grade else "ungraded_guide") if full else "identified_subtotal"
        result["coverage"] = len(priced) / (count or len(keys))
        result["note"] = (
            "Matching graded-guide comparison; seller identity and grade remain unverified."
            if grade and full
            else "Ungraded-guide comparison; seller identity and condition remain unverified."
            if full
            else "Identified priced-card subtotal only; unpriced or unknown contents are not valued."
        )
        if not edition_known:
            result["note"] += " Standard edition is a conditional assumption; seller edition is unverified."
        if lot_assumption:
            result["note"] += (
                " Individual lot grades and editions are not matched; this uses an ungraded baseline."
            )
    elif (
        not keys
        and count
        and row.get("pool") == "known_lots"
        and not graded
        and not re.search(r"\b(?:mystery|repack|random|sealed|booster|unopened)\b", text, re.I)
    ):
        benchmark_key = (tuple(sorted(cards)), today)
        if isinstance(records, GuideContext) and benchmark_key in records.benchmarks:
            priced = records.benchmarks[benchmark_key]["evidence"]
        else:
            priced = [record for key in cards if (record := _guide(key, "standard", None, records, today))]
            if isinstance(records, GuideContext):
                subtotal = sum((Decimal(r["guidevalue"]) for r in priced), Decimal(0))
                records.benchmarks[benchmark_key] = {
                    "evidence": priced,
                    "subtotal": subtotal,
                    "average": subtotal / len(priced) if priced else None,
                    "dates": sorted({r["as_of"] for r in priced}),
                }
        if priced:
            result["status"] = "benchmark"
            result["basis"] = "catalog_average_benchmark"
            result["coverage"] = len(priced) / len(cards)
            result["note"] = (
                "Scoped catalog average × stated lot count, assuming standard ungraded cards. "
                "A benchmark only: actual contents, condition and edition are unknown; this is not an appraisal."
            )
    if not priced:
        return result
    benchmark = (
        records.benchmarks.get(benchmark_key)
        if result["status"] == "benchmark" and isinstance(records, GuideContext)
        else None
    )
    subtotal = (
        benchmark["subtotal"] if benchmark else sum((Decimal(r["guidevalue"]) for r in priced), Decimal(0))
    )
    average = benchmark["average"] if benchmark else subtotal / len(priced)
    reference = average * count if result["status"] == "benchmark" else subtotal
    result.update(
        {
            "reference_total": _money(reference),
            "priced_cards": len(priced),
            "average_per_card": _money(average),
            "source_dates": benchmark["dates"] if benchmark else sorted({r["as_of"] for r in priced}),
            "evidence": priced,
        }
    )
    if delivered is not None:
        result["saving"] = _money(reference - delivered)
        result["discount_percent"] = _money((reference - delivered) / reference * 100) if reference else None
    result["note"] += " Prices exclude tax; guide values are not appraisals."
    if row.get("type") == "auction":
        result["note"] += " Auction comparison uses the current bid, not a settled purchase price."
    return result
