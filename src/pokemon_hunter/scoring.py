import re

from .models import Listing, Settings
from .parser import clean

PRIORITIES = {"low": 0, "medium": 1, "high": 2}


def score(listing: Listing, settings: Settings, missing: tuple[float, float], text: str):
    text = clean(text)
    neo = any(s.startswith("neo_") for s in listing.detected_sets) or bool(re.search(r"\bneo\b", text))
    ereader = bool(listing.detected_sets & {"expedition", "aquapolis", "skyridge"})
    rocket_gym = bool(listing.detected_sets) and listing.detected_sets <= {
        "team_rocket",
        "gym_heroes",
        "gym_challenge",
    }
    # Generation-level opportunity only. This is not a probability of new species.
    relevance = (0.2 + missing[1]) if neo else (0.2 + sum(missing) / 2) if ereader else (0.2 + missing[0])
    if rocket_gym:
        relevance *= 0.65
    multiplier = {"pure": 1.0, "probably_pure": 0.85, "mixed": 0.5, "unknown": 0.4}[listing.purity]
    threshold = (
        settings.thresholds.auction_per_card
        if listing.listing_type == "auction"
        else settings.thresholds.fixed_price_per_card
    )
    ratio = float(listing.cost_per_card / threshold) if listing.cost_per_card is not None else 1.0
    bonus = 1.0
    for pattern in [
        r"\bno duplicates\b",
        r"\bmostly pokemon\b",
        r"\bno trainers\b",
        r"\bno energy\b",
        r"\bplayed\b",
        r"\bdamaged\b",
        r"\bchildhood collection\b",
        r"\bunsorted\b",
    ]:
        if re.search(pattern, text):
            bonus += 0.03
    listing.confidence = listing.count.confidence * multiplier
    listing.pokedex_score = round(
        relevance * multiplier * listing.count.confidence * max(0, 1 - ratio) * bonus, 5
    )
    if neo:
        listing.reasons.append("Neo/Johto emphasis; more of your Johto Pokédex is missing")
    elif ereader:
        listing.reasons.append("e-Reader sets span Kanto and Johto")
    else:
        listing.reasons.append("Kanto-era opportunity; most Kanto species already owned")
    if rocket_gym:
        listing.reasons.append("Dark/owner-named cards may not qualify for your Pokédex")
    listing.reasons.append(
        {
            "pure": "Only eligible set names detected; seller composition is unverified",
            "probably_pure": "Vintage keywords only; exact sets unverified",
            "mixed": "Mixed era/language: cost is per stated card, not per eligible species card",
            "unknown": "No identifiable eligible sets",
        }[listing.purity]
    )
    listing.reasons.append(listing.count.explanation)
    if listing.purity == "pure" and neo and ratio < 0.75 and listing.count.confidence >= 0.7:
        listing.priority = "high"
    elif (
        listing.purity == "pure"
        or (listing.purity == "probably_pure" and ratio <= 0.65)
        or (listing.purity == "mixed" and neo and ratio <= 0.4)
    ):
        listing.priority = "medium"
    else:
        listing.priority = "low"
    if PRIORITIES[listing.priority] < PRIORITIES[settings.alerts.minimum_priority]:
        listing.rejection_reasons.append("Below minimum alert priority")
    listing.qualifying = not listing.rejection_reasons
