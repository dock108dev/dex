"""Catalog-backed release screening for received Shopping singles."""

import re
from datetime import UTC, datetime

from . import discovery_matching, species_scope
from .tcgcsv_vintage import numbered_finish

THROUGH_2000 = "2000-12-31"
# Collector fractions printed on the English original issues. The printed
# denominator can differ from the number of catalog entries (Team Rocket).
ORIGINAL_TOTALS = {
    "Base Set": "102",
    "Jungle": "64",
    "Fossil": "62",
    "Base Set 2": "130",
    "Team Rocket": "82",
    "Gym Heroes": "132",
    "Gym Challenge": "132",
    "Neo Genesis": "111",
}
SPECIAL = re.compile(
    r"\b(?:reprint(?:ed)?|celebrations?|jumbo|galaxy|cosmos|copyright|1999\s*[-–]\s*2000)\b", re.I
)


def classify(matched, clues, issues, dates):
    if issues:
        return {"status": "conflicting"}
    if not matched:
        return {"status": "unknown"}
    identities = {(p["set_id"], p["collector_number"], p["language"]) for p in matched}
    if len(identities) != 1:
        return {"status": "conflicting"}
    printing = matched[0]
    set_id, _, language = next(iter(identities))
    if clues["language"] and clues["language"] != language:
        return {"status": "conflicting"}
    if any(discovery_matching.unavailable(p) for p in matched):
        return {"status": "unknown"}
    claims = discovery_matching.number_claims(printing, clues["text"])
    total = ORIGINAL_TOTALS.get(printing["set_name"]) if language == "en" else None
    if total and any(
        "/" in claim
        and discovery_matching.number_key(claim.split("/")[-1]) != discovery_matching.number_key(total)
        for claim in claims
    ):
        return {"status": "conflicting"}
    finish = numbered_finish(printing)
    if finish and clues["finish"] and clues["finish"] != finish:
        return {"status": "conflicting"}
    # The dated set attests the original numbered issue. Special/reprint
    # wording needs separate dated evidence for that physical issue.
    if SPECIAL.search(discovery_matching.without_sets(matched, clues["text"])):
        return {"status": "unknown"}
    ordinary = [
        p
        for p in matched
        if not set(p["attributes"].get("physical_variant") or {}) - {"type", "edition", "stamp", "languages"}
    ]
    if not ordinary:
        return {"status": "unknown"}
    evidence = dates.get(set_id)
    if not evidence or language != evidence["language"]:
        return {"status": "unknown"}
    eligible = species_scope.date_match(evidence, {"date_to": THROUGH_2000})
    return {
        "status": "eligible" if eligible is True else "later" if eligible is False else "unknown",
        "start": evidence["start"],
        "end": evidence["end"],
        "language": language,
        "name": printing["name"],
        "set_name": printing["set_name"],
        "collector_number": printing["collector_number"],
        "finish": clues["finish"] or finish,
        "edition": clues["edition"],
    }


def scope_match(run, matched, options):
    allowed = {"buy_now": {"FIXED_PRICE"}, "auction": {"AUCTION"}, "both": {"FIXED_PRICE", "AUCTION"}}
    if not allowed[run.choices.single_buying].intersection(options):
        return False
    if run.single_set_name and not any(p["set_name"] == run.single_set_name for p in matched):
        return False
    if run.choices.printing_id:
        return len(matched) == 1 and matched[0]["id"] == run.choices.printing_id
    return not run.single_targets or all(p["id"] in run.single_targets for p in matched) and bool(matched)


def unavailable(raw, end):
    availability = raw.get("estimatedAvailabilities")
    return bool(
        end
        and datetime.fromisoformat(end) <= datetime.now(UTC)
        or isinstance(availability, list)
        and any(
            isinstance(item, dict)
            and item.get("estimatedAvailabilityStatus") in ("OUT_OF_STOCK", "UNAVAILABLE")
            for item in availability
        )
    )
