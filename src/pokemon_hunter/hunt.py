"""Conservative listing evidence and spoiler-safe projections for the collection app."""

import json
import re
from datetime import UTC, datetime
from decimal import ROUND_DOWN, Decimal
from urllib.parse import urlparse

from .parser import extract_count
from .pricing import money, shipping


def query_plan(data, config, pool, focus):
    if pool == "singles":
        cards = [
            c
            for c in data["cards"].values()
            if c["dex_eligible"] and not data["pokedex"][str(c["pokemon_dex"])]["dex_owned"]
        ]
        if focus in ("kanto", "johto"):
            cards = [c for c in cards if (c["pokemon_dex"] <= 151) == (focus == "kanto")]
        if focus == "rares":
            cards = [c for c in cards if "Rare" in c["rarity"]]
        return [f"Pokemon {c['set']} {c['name']} {c['number']}" for c in cards]
    queries = config["pools"][pool]
    if focus == "johto":
        return (
            [
                "pokemon neo genesis lot",
                "pokemon neo discovery lot",
                "pokemon neo revelation lot",
                "pokemon neo destiny lot",
            ]
            if pool == "known_lots"
            else ["pokemon neo mystery pack"]
        )
    if focus == "kanto":
        return (
            ["pokemon base jungle fossil lot", "pokemon vintage kanto lot"]
            if pool == "known_lots"
            else ["pokemon vintage kanto mystery pack"]
        )
    if focus == "rares":
        return (
            ["pokemon WOTC non holo rare lot"] if pool == "known_lots" else ["pokemon WOTC rare mystery pack"]
        )
    if focus == "bulk":
        return (
            ["pokemon WOTC common uncommon bulk lot"]
            if pool == "known_lots"
            else ["pokemon vintage bulk mystery pack"]
        )
    return queries


def exact_text_matches(text, data):
    """Require an explicit set, exact normal card name and number in one short phrase.

    These remain seller-text candidates, never photo-verified inventory.
    """
    matches = set()
    for c in data["cards"].values():
        if not c["dex_eligible"]:
            continue
        set_pattern = re.escape(c["set"]).replace(r"\ ", r"\s+")
        if c["set_id"] == "base_set":
            set_pattern += r"(?!\s*2)"
        if not re.search(set_pattern, text, re.I):
            continue
        pattern = r"(?<![\w'’])" + re.escape(c["name"]) + r"\s*#?\s*" + re.escape(c["number"]) + r"(?!\d)"
        for match in re.finditer(pattern, text, re.I):
            prefix = text[max(0, match.start() - 30) : match.start()].strip()
            if re.search(r"(?:dark|light|\w+['’]s)\s*$", prefix, re.I):
                continue
            matches.add(c["card_id"])
    # Multi-set text can attach a number to the wrong printing; retain only unique name/number candidates.
    grouped = {}
    for key in matches:
        c = data["cards"][key]
        grouped.setdefault((c["name"], c["number"]), []).append(key)
    return sorted(keys[0] for keys in grouped.values() if len(keys) == 1)


def analyze(raw, data, config, values, demo=False):
    title = raw.get("title", "")
    text = title + " " + (raw.get("shortDescription") or "")
    mystery = bool(re.search(r"\b(mystery|repack|random)\b", text, re.I))
    count = extract_count(text).denominator
    keys = raw.get("_demo_cards", []) if demo else exact_text_matches(text, data)
    keys = [k for k in keys if k in data["cards"]]
    if mystery:
        keys = []  # Random contents cannot establish exact-card or species hits.
    cards = [data["cards"][k] for k in keys]
    eligible = [c for c in cards if c["dex_eligible"]]
    dex_hits = {c["pokemon_dex"] for c in eligible if not data["pokedex"][str(c["pokemon_dex"])]["dex_owned"]}
    exact_hits = {c["card_id"] for c in cards if not c["owned"]}
    auction = "AUCTION" in raw.get("buyingOptions", [])
    price = money(raw.get("currentBidPrice") if auction else raw.get("price"), "USD")
    ship = shipping(raw, "USD")
    delivered = price + ship if price is not None and ship is not None else None
    condition = raw.get("condition", "")
    basis = (
        "LP"
        if condition.casefold() in ("lightly played", "lightly played (excellent)")
        else "NM"
        if condition.casefold() in ("near mint", "near mint or better")
        else None
    )
    # A complete enumerated inventory and raw condition are required for whole-lot economics.
    complete = bool(count and count == len(keys) and basis and not mystery)
    value_rows = [values.get(k, {}).get(basis) for k in keys] if basis else []
    priced = complete and all(
        v and v.get("value") is not None and v.get("source") and v.get("as_of") for v in value_rows
    )
    raw_value = sum((Decimal(str(v["value"])) for v in value_rows), Decimal(0)) if priced else None
    duplicates = sum(c["owned"] for c in cards) / len(cards) if cards else None
    components = {
        "dex_yield": min(1, len(dex_hits) / 5) if cards else None,
        "collection_yield": min(1, len(exact_hits) / 10) if cards else None,
        "value_ratio": min(1, float(raw_value / delivered) / 2)
        if raw_value is not None and delivered and delivered > 0
        else None,
        "set_fit": len(eligible) / len(cards) if cards else None,
        "mystery_quality": None,
    }
    coverage = sum(config["weights"][k] for k, v in components.items() if v is not None)
    score = (
        round(
            max(
                0,
                100 * sum(config["weights"][k] * v for k, v in components.items() if v is not None)
                - config["duplicate_penalty"] * (duplicates or 0)
                - config["junk_penalty"] * (1 - len(eligible) / len(cards) if cards else 0),
            )
        )
        if coverage
        else None
    )
    max_bid = None
    if auction and raw_value is not None and ship is not None:
        useful = sum(
            (Decimal(str(values[c["card_id"]][basis]["value"])) for c in cards if not c["owned"]), Decimal(0)
        )
        max_bid = max(
            Decimal(0),
            useful
            + Decimal(config["completion_premium"])
            + Decimal(config["mystery_premium"])
            - ship
            - Decimal(config["condition_risk"]),
        ).quantize(Decimal(".01"), rounding=ROUND_DOWN)
    end = raw.get("itemEndDate")
    active = True
    if end:
        try:
            dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
            active = dt.tzinfo is not None and dt > datetime.now(UTC)
        except ValueError:
            active = False
    if auction and not end:
        active = False
    if raw.get("estimatedAvailabilities") and all(
        x.get("estimatedAvailabilityStatus") == "OUT_OF_STOCK" for x in raw["estimatedAvailabilities"]
    ):
        active = False
    url = raw.get("itemWebUrl", "")
    host = urlparse(url).hostname or ""
    safe_url = (
        url
        if urlparse(url).scheme == "https" and (host == "ebay.com" or host.endswith(".ebay.com"))
        else None
    )
    return {
        "id": raw["itemId"],
        "title": title,
        "url": safe_url,
        "cards": keys,
        "pool": "mystery"
        if mystery
        else "singles"
        if count == 1 or (len(keys) == 1 and not re.search(r"\b(lot|binder|collection)\b", text, re.I))
        else "known_lots",
        "type": "auction" if auction else "fixed",
        "count": count,
        "price": str(price) if price is not None else None,
        "shipping": str(ship) if ship is not None else None,
        "delivered": str(delivered) if delivered is not None else None,
        "end_time": end,
        "active": active,
        "dex_hits": len(dex_hits),
        "exact_hits": len(exact_hits),
        "kanto_hits": sum(n <= 151 for n in dex_hits),
        "johto_hits": sum(n > 151 for n in dex_hits),
        "has_rare": any("Rare" in c["rarity"] for c in cards),
        "raw_value": str(raw_value) if raw_value is not None else None,
        "max_bid": str(max_bid) if max_bid is not None else None,
        "duplicate_ratio": duplicates,
        "score": score,
        "score_coverage": round(coverage, 2),
        "confidence": "Sample inventory"
        if demo and cards
        else "Seller text only"
        if cards
        else "Contents unknown",
        "components": components,
        "condition": condition,
        "value_basis": basis,
        "demo": demo,
    }


def public_listing(row, reveal=False):
    safe = {k: v for k, v in row.items() if k not in ("title", "url", "cards", "components", "has_rare")}
    safe["label"] = (
        "Mystery pack"
        if row["pool"] == "mystery"
        else "Dex opportunity"
        if row["pool"] == "singles"
        else "Vintage card lot"
    )
    if reveal:
        safe.update({k: row[k] for k in ("title", "url", "cards", "components")})
    return safe


def load_json(path):
    return json.loads(path.read_text())


def project_results(raws, body, demo, data, config, values):
    results = [analyze(r, data, config, values, demo=demo) for r in raws]
    results = [
        r
        for r in results
        if r["active"]
        and r["delivered"] is not None
        and Decimal(r["delivered"]) <= body.budget
        and r["pool"] == body.pool
    ]
    if body.pool == "singles":
        results = [r for r in results if r["dex_hits"]]
    if body.focus in ("kanto", "johto"):
        results = [r for r in results if r[f"{body.focus}_hits"] or not r["cards"]]
    if body.focus == "rares":
        results = [r for r in results if r["has_rare"] or not r["cards"]]
    if body.focus == "bulk":
        results = [r for r in results if r["count"] and r["count"] >= 25]
    for row in results:
        if row["max_bid"] is not None:
            row["max_bid"] = str(
                max(Decimal(0), min(Decimal(row["max_bid"]), body.budget - Decimal(row["shipping"])))
            )
    return sorted(results, key=lambda r: (r["score"] is not None, r["score"] or 0), reverse=True)
