"""Temporary single-listing comparisons over the admitted Shopping reference path.

Seller summaries propose identities. They never establish ownership, physical
condition, certification, or permission to retain a source or its derivatives.
This module has no acquisition or persistence entry point.
"""

import re
from datetime import datetime
from decimal import Decimal

from pokemon_hunter.parser import extract_count
from pokemon_hunter.pricing import money as provider_money
from pokemon_hunter.pricing import shipping as provider_shipping
from pokemon_hunter.security import ebay_url

from . import (
    collection,
    discovery_matching,
    image_bindings,
    lot_calculator,
    lot_guides,
    market_identity,
    shopping,
    store,
)
from . import shopping_math as math
from .discovery_search import product_kind

_GRADERS = r"PSA|BGS|CGC|SGC"
_LANGUAGES = {
    "en": r"english|eng",
    "ja": r"japanese|japan|jpn",
    "de": r"german|deutsch",
    "fr": r"french|francais|français",
    "it": r"italian|italiano",
    "es": r"spanish|español",
    "ko": r"korean",
    "zh": r"chinese",
    "pt": r"portuguese",
}
_NO_COMPARISON = dict(
    reference_minus_delivered_total=None,
    reference_minus_listing_price=None,
    difference_percent=None,
    below_reference=None,
    difference_percent_basis="listing_price_excluding_shipping",
)


def _condition(value):
    normalized = re.sub(r"[^a-z]", "", str(value or "").casefold())
    return {
        "nm": "NM",
        "nearmint": "NM",
        "nearmintorbetter": "NM",
        "lp": "LP",
        "lightlyplayed": "LP",
        "lightlyplayedexcellent": "LP",
        "mp": "MP",
        "moderatelyplayed": "MP",
        "moderatelyplayedverygood": "MP",
        "hp": "HP",
        "heavilyplayed": "HP",
        "heavilyplayedpoor": "HP",
        "dmg": "DMG",
        "damaged": "DMG",
    }.get(normalized)


def _clues(raw, *, claim_text=None):
    text = " ".join(str(raw.get(k) or "") for k in ("title", "shortDescription", "condition"))
    claim_text = text if claim_text is None else claim_text
    languages = {
        key for key, pattern in _LANGUAGES.items() if re.search(r"\b(?:" + pattern + r")\b", claim_text, re.I)
    }
    first = bool(re.search(r"\b(?:1st|first)[ -]*edition\b", claim_text, re.I))
    unlimited = bool(re.search(r"\b(?:unlimited|standard[ -]+edition)\b", claim_text, re.I))
    negated = bool(re.search(r"\b(?:no|not|non)[ -]+(?:1st|first)[ -]*edition\b", claim_text, re.I))
    editions = {v for v, yes in (("first_edition", first), ("unlimited", unlimited)) if yes}
    nonholo = bool(re.search(r"\b(?:non[ -]?(?:holo(?:foil)?|foil)|normal)\b", claim_text, re.I))
    # Remove the negated finish before checking its positive spelling.
    reverse = bool(re.search(r"\breverse[ -]*(?:holo(?:foil)?|foil)\b", claim_text, re.I))
    finish_text = re.sub(r"\b(?:non[ -]?|reverse[ -]*)(?:holo(?:foil)?|foil)\b", "", claim_text, flags=re.I)
    holo = bool(re.search(r"\b(?:holo(?:foil)?|foil)\b", finish_text, re.I))
    finishes = {v for v, yes in (("normal", nonholo), ("holo", holo), ("reverse-holo", reverse)) if yes}
    grades = {
        (grader.upper(), grade)
        for grader, grade in re.findall(
            r"\b(" + _GRADERS + r")\s*[-:]?\s*(10|[1-9](?:\.5)?)(?![\d.])", text, re.I
        )
    }
    graded = bool(grades or re.search(r"\b(?:graded|slab|gem[ -]*mint|grade\s*\d)\b", claim_text, re.I))
    condition = str(raw.get("condition") or "").strip() or None
    condition_text = re.sub(r"\b(?:[0-9]{1,4}\s*HP|HP\s*[:=-]?\s*[0-9]{1,4})\b", "", claim_text, flags=re.I)
    condition_claims = {
        value
        for value, pattern in (
            ("NM", r"nm|near[ -]+mint(?:[ -]+or[ -]+better)?"),
            ("LP", r"lp|lightly[ -]+played"),
            ("MP", r"mp|moderately[ -]+played"),
            ("HP", r"hp|heavily[ -]+played"),
            ("DMG", r"dmg|damaged"),
        )
        if re.search(r"\b(?:" + pattern + r")\b", condition_text, re.I)
    }
    special = bool(re.search(r"\b(?:shadowless|error|misprint|proxy|replica|custom)\b", claim_text, re.I))
    conflicts = []
    if len(languages) > 1:
        conflicts.append("Conflicting seller language claims")
    if len(editions) > 1 or negated:
        conflicts.append("Edition claims are conflicting or negated")
    if len(finishes) > 1:
        conflicts.append("Conflicting seller finish claims")
    if len(grades) > 1:
        conflicts.append("Conflicting literal grader or grade claims")
    if len(condition_claims) > 1:
        conflicts.append("Conflicting seller raw-condition claims")
    if special:
        conflicts.append("Special, altered, or unresolved printing claims need review")
    grade = next(iter(grades)) if len(grades) == 1 else (None, None)
    if graded and (grade[0] is None or grade[1] not in {"8", "9", "10"}):
        conflicts.append("No supported literal grader and grade combination")
    return dict(
        text=text,
        language=next(iter(languages)) if len(languages) == 1 else None,
        edition=next(iter(editions)) if len(editions) == 1 and not negated else None,
        finish=next(iter(finishes)) if len(finishes) == 1 else None,
        grader=grade[0],
        grade=grade[1] if graded else "raw",
        graded=graded,
        condition=condition,
        condition_claims=sorted(condition_claims),
        conflicts=conflicts,
    )


def _identity_conflicts(printing, clues):
    issues = []
    for key, aliases in (
        ("language", {}),
        ("edition", market_identity.EDITION),
        ("finish", market_identity.FINISH),
    ):
        known, proposed = printing.get(key), clues[key]
        if known and proposed and aliases.get(known, known) != proposed:
            issues.append("Seller " + key + " conflicts with the catalog printing")
    return issues


def _reference_claim_issue(printing, clues, ref):
    """Seller claims narrow admitted observations, never establish admission."""
    if _identity_conflicts(printing, clues):
        return "Claimed attributes conflict with the selected printing"
    provider, evidence = ref.get("provider_identity") or {}, ref.get("raw_record") or {}
    for key in ("language", "edition", "finish"):
        known = provider.get(key) or evidence.get(key)
        if key == "edition" and known == "unspecified":
            continue
        known = {"edition": market_identity.EDITION, "finish": market_identity.FINISH}.get(key, {}).get(
            known, known
        )
        if clues.get(key) and known and clues[key] != known:
            return "Claimed attributes conflict with the admitted reference"
    reference_condition = _condition(evidence.get("condition"))
    condition_claims = set(clues.get("condition_claims", []))
    raw_condition = _condition(clues.get("condition"))
    if raw_condition:
        condition_claims.add(raw_condition)
    if (
        not clues["graded"]
        and reference_condition
        and any(claim != reference_condition for claim in condition_claims)
    ):
        return "Claimed condition conflicts with the admitted reference"
    if clues["graded"] and ref.get("grader") not in {
        clues.get("grader"),
        "Guide",
        "Generic guide population",
    }:
        return "Literal reference grader conflicts with the claimed grader"
    return None


def reference_issue(printing, clues, ref, today):
    """Shared seller/review applicability after admitted guide selection."""
    issue = _reference_claim_issue(printing, clues, ref)
    if issue:
        return issue
    if math.eligibility(ref, today.isoformat()) != "eligible":
        return "The retained reference is no longer eligible"
    return None


def _reference_cells(printing, records, today, clues):
    """Narrow a local admitted bucket before the established dated selection.

    A newer observation for a different literal grader or raw condition cannot
    hide an older applicable observation. Null/stale/source/printing admission
    remains with the ordinary guide projection and source lifecycle.
    """
    import json

    legacy_id = json.loads(printing["provenance"]).get("legacy_id")
    accepted, rejected, applicable = [], set(), 0
    for record in records:
        same_printing = (
            record.get("printing_id") == printing["id"]
            if "_snapshot_version" in record
            else legacy_id is not None and record.get("card_id") == legacy_id
        )
        if not same_printing or str(record.get("grade")) != clues["grade"]:
            accepted.append(record)
            continue
        issue = _reference_claim_issue(
            printing,
            clues,
            dict(
                raw_record=record,
                provider_identity=record.get("provider_identity"),
                grader=record.get("grader"),
            ),
        )
        if issue:
            rejected.add(issue)
        else:
            accepted.append(record)
            applicable += 1
    subset = lot_calculator.SnapshotRecords(accepted, getattr(records, "status", "active_snapshot"))
    cells, reasons = lot_guides.cell_details(printing, subset, today)
    if cells.get(clues["grade"]) is None and rejected:
        explanation = "; ".join(sorted(rejected))
        reasons[clues["grade"]] = (
            reasons.get(clues["grade"], "Unavailable admitted observation") + "; " + explanation
            if applicable
            else explanation
        )
    return cells, reasons


def _matches(candidates, clues):
    # Name tokens only narrow. The shared literal set/name/whole-number check
    # establishes seller proposals; attributes may then resolve supported siblings.
    candidates = discovery_matching.literal_candidates(candidates, clues["text"])
    proposed = [p for p in candidates if discovery_matching.evidence(p, clues)["matched"]]
    fitting = [p for p in proposed if not _identity_conflicts(p, clues)]
    fitting = fitting or proposed
    # A family is one numbered card, but seller clues must establish a particular
    # child before its independent reference can be compared. Broad offers remain
    # ambiguous; no parent price or physical attribute is inherited.
    from .catalog_variants import seller_candidates

    return seller_candidates(fitting, clues)


def _approx_matches(candidates, clues):
    """Name-only seller clues are useful choices, never exact-price evidence."""
    return discovery_matching.literal_candidates(candidates, clues["text"])


def _identity(printing, clues, artwork=None):
    return dict(
        printing_id=printing["id"],
        name=printing["name"],
        set_name=printing["set_name"],
        collector_number=printing["collector_number"],
        seller_collector_numbers=discovery_matching.number_claims(printing, clues["text"]),
        artwork_url=(artwork or {}).get("image_url"),
        artwork_basis="Catalog card reference; edition and finish depiction unverified",
        language=clues["language"],
        edition=clues["edition"],
        finish=clues["finish"],
        condition=clues["condition"],
        grader=clues["grader"],
        grade=clues["grade"],
        verified=False,
        parent_printing_id=printing.get("parent_printing_id"),
        variant_label=printing.get("variant_label"),
    )


def _reference(ref):
    """Explicit display projection; raw_record and contract bytes never escape."""
    raw = ref.get("raw_record", {})
    provider = ref.get("provider_identity") or {}
    return dict(
        amount=ref["amount"],
        currency=ref["currency"],
        as_of=ref["as_of"],
        valuation_as_of=ref.get("valuation_as_of", None if not ref.get("snapshot_version") else ref["as_of"]),
        captured_at=ref.get("captured_at"),
        source_url=ref.get("source_url"),
        source_version=ref.get("source_version"),
        date_basis=ref.get("date_basis", "legacy"),
        publisher_built_at=ref.get("publisher_built_at"),
        expires_at=ref.get("expires_at"),
        # Noncontent lifecycle keys allow the open page to erase references when
        # their independently managed version or source is withdrawn locally.
        snapshot_version=ref.get("snapshot_version"),
        source_contract=ref.get("source_contract"),
        language=provider.get("language", raw.get("language")),
        edition=provider.get("edition", ref.get("edition", raw.get("edition"))),
        finish=provider.get("finish", raw.get("finish")),
        variant=provider.get("variant", raw.get("variant")),
        condition=raw.get("condition"),
        grade=ref["grade"],
        grader=ref.get("grader"),
        estimated=ref.get("estimated"),
        match_status=ref["match_status"],
        save_allowed=ref.get("save_allowed", True)
        and all(c.get("save_allowed") for c in ref.get("conflicts", [])),
        conflicts=[
            {
                k: c.get(k)
                for k in (
                    "source_url",
                    "source_version",
                    "source_contract",
                    "as_of",
                    "valuation_as_of",
                    "date_basis",
                    "publisher_built_at",
                    "captured_at",
                    "grade",
                    "grader",
                    "expires_at",
                    "save_allowed",
                    "explanation",
                )
            }
            for c in ref.get("conflicts", [])
        ],
    )


def _arithmetic(price, shipping, ref, today, *, auction=False):
    def cost(value):
        return dict(amount=value, currency="USD", status="known" if value is not None else "unknown")

    basis = dict(
        cost(price), price_kind="current_bid" if auction else "current_asking_price", date=today.isoformat()
    )
    data = dict(
        evaluation_date=today.isoformat(),
        listing_observation=basis,
        planned_bid=dict(cost(None), price_kind="personal_planned_bid", date=today.isoformat()),
        delivery_cost_inputs={
            key: dict(shipping=cost(shipping), tax=cost("0"), other_costs=cost("0")) for key in math.BASES
        },
    )
    value = math.amount(ref["amount"]) if ref is not None else None
    result = math.comparisons(data, value, value, None, None)["listing_observation"]
    delta = result["full_selected_reference_minus_delivered_cost"]
    return result["full_delivered_cost"], dict(
        reference_minus_delivered_total=delta,
        reference_minus_listing_price=result["full_selected_reference_minus_base_price"],
        difference_percent=result["full_reference_difference_percent"],
        below_reference=Decimal(delta) > 0 if delta is not None else None,
        difference_percent_basis="listing_price_excluding_shipping",
    )


def compare(actor, raw_rows, candidates, *, now=None):
    """Project supplied single/loose-lot summaries without calls or saves.

    Candidates must be internally scoped, authorized catalog rows. Additional
    ownership annotations are ignored; discovery does not require missing cards.
    Every projection re-enters reference lifecycle admission, including reopening.
    """
    store.verified(actor)
    now = now or datetime.now(shopping.TZ)
    authoritative = {p["id"]: p for p in collection.catalog(actor, include_archived=True)}
    printings = []
    for candidate in candidates:
        p = authoritative.get(candidate.get("id"))
        if p is None or any(candidate.get(k) != p.get(k) for k in p):
            raise ValueError("Discovery catalog differs from authorized metadata")
        printings.append(p)
    records = lot_calculator.retained_records()
    return _project(actor, raw_rows, printings, records, now=now)


def _project(
    actor,
    raw_rows,
    printings,
    records,
    *,
    now=None,
    candidates_for=None,
    records_for=None,
    artwork=None,
    include_unsupported=False,
    identity_issues_for=None,
):
    """Shared arithmetic over internally authorized catalog/reference batches.

    This is an internal adapter boundary, not an alternate admission path. Callers
    must load the catalog through collection.catalog and references through
    retained_records before entering it. Hunter supplies indexed candidate and
    reference subsets and leaves artwork for its later screen integration.
    """
    store.verified(actor)
    now = now or datetime.now(shopping.TZ)
    today = now.astimezone(shopping.TZ).date()
    if artwork is None:
        artwork = image_bindings.catalog_images(actor, printings)
    result, seen, guide_cache = [], set(), {}
    for raw in raw_rows:
        item_id = raw.get("itemId")
        if not isinstance(item_id, str) or not item_id or item_id in seen:
            continue
        seen.add(item_id)
        clues = _clues(raw)
        candidates = candidates_for(clues) if candidates_for else printings
        literal = [
            candidate for candidate in candidates if discovery_matching.evidence(candidate, clues)["matched"]
        ]
        claim_text = (
            discovery_matching.without_sets(literal, discovery_matching.without_names(literal, clues["text"]))
            if literal
            else clues["text"]
        )
        if literal:
            clues = _clues(raw, claim_text=claim_text)
        kind = product_kind(claim_text)
        if kind == "unsupported" and not include_unsupported:
            continue
        matched = _matches(candidates, clues)
        approximate = matched or _approx_matches(candidates, clues)
        p = matched[0] if len(matched) == 1 and kind == "single" else None
        evidence = discovery_matching.evidence(p, clues) if p else None
        identity_issues = list(clues["conflicts"])
        if identity_issues_for:
            identity_issues.extend(identity_issues_for(candidates, clues))
        if p:
            identity_issues.extend(_identity_conflicts(p, clues))
        elif not matched:
            for candidate in approximate:
                identity_issues.extend(discovery_matching.evidence(candidate, clues)["conflicts"])
        unavailable = discovery_matching.unavailable(p) if p else None
        if unavailable:
            identity_issues.append(unavailable)
        identity_issues = list(dict.fromkeys(identity_issues))
        identity_status = (
            "unavailable"
            if unavailable
            else "conflicting"
            if identity_issues
            else "matched"
            if p
            else "ambiguous"
            if approximate
            else "unmatched"
        )
        options = raw.get("buyingOptions", [])
        options = options if isinstance(options, list) and all(isinstance(o, str) for o in options) else []
        auction = "AUCTION" in options
        price = provider_money(raw.get("currentBidPrice") if auction else raw.get("price"), "USD")
        shipping = provider_shipping(raw, "USD")
        # Shopping owns decimal admission and rounding, including upper bounds.
        try:
            price = math.money(math.amount(format(price, "f"))) if price is not None else None
            shipping = math.money(math.amount(format(shipping, "f"))) if shipping is not None else None
        except ValueError:
            price, shipping = None, None
        buy_now = provider_money(raw.get("price"), "USD") if "FIXED_PRICE" in options else None
        try:
            buy_now = math.money(math.amount(format(buy_now, "f"))) if buy_now is not None else None
        except ValueError:
            buy_now = None
        delivered, _ = _arithmetic(price, shipping, None, today, auction=auction)
        row = dict(
            item_id=item_id,
            title=str(raw.get("title") or ""),
            item_url=ebay_url(raw.get("itemWebUrl")),
            label="Loose mixed-lot candidate" if kind == "mixed_lot" else "Single-card candidate",
            discovery_kind=kind,
            proposed_identity=_identity(p, clues, artwork.get(p["id"])) if p else None,
            identity_candidates=[_identity(c, clues, artwork.get(c["id"])) for c in approximate[:40]],
            identity_candidates_total=len(approximate),
            identity_status=identity_status,
            identity_diagnostics=identity_issues,
            identity_uncertainties=evidence["uncertainties"] if evidence else [],
            seller_collector_numbers=discovery_matching.number_claims(p, clues["text"]) if p else [],
            discovery_eligibility="candidate",
            reference_eligibility="unpriced",
            listing_price=price,
            current_bid=price if auction else None,
            buy_now_price=buy_now,
            buying_options=[o for o in ("AUCTION", "FIXED_PRICE", "BEST_OFFER") if o in options],
            ends_at=raw.get("itemEndDate") if isinstance(raw.get("itemEndDate"), str) else None,
            shipping=shipping,
            delivered_total=delivered,
            currency="USD",
            price_kind="current_bid" if auction else "fixed_price",
            classification="unpriced",
            reason="No unique seller-text set, card name and number match",
            basis="Seller text proposes identity; verify the physical card. Totals exclude tax and other costs.",
            reference=None,
            comparison=dict(_NO_COMPARISON),
            save_allowed=False,
            save_reason="Discovery results are temporary; saved research is available in Check a listing/lot.",
        )
        issues = list(identity_issues)
        if len(matched) > 1:
            issues.append("Multiple catalog printings match; edition or finish needs review")
        if not {"FIXED_PRICE", "AUCTION"}.intersection(options):
            issues.append("No supported fixed-price or auction buying option was supplied")
        if kind == "mixed_lot":
            issues.append(
                "Loose mixed-lot contents need review; one card reference cannot value the whole lot"
            )
        elif kind == "unsupported":
            issues.append("Unsupported product cannot use a single-card reference")
        count = extract_count(clues["text"]).denominator
        if (
            count is not None
            and count != 1
            or re.search(
                r"\b(?:choose|pick\s+(?:your|from)|complete\s+set|master\s+set)\b", clues["text"], re.I
            )
            or re.search(r"(?:\bx\s*[2-9]\d*\b|\b[2-9]\d*\s*[x×]\b)", clues["text"], re.I)
        ):
            issues.append("A multiple-card or selectable offer cannot use a single-card reference")
        if issues:
            row["reason"] = "; ".join(issues)
        elif p:
            guide_key = (
                (p["id"],)
                + tuple(
                    clues.get(key)
                    for key in ("language", "edition", "finish", "grade", "grader", "graded", "condition")
                )
                + (tuple(clues.get("condition_claims", [])),)
            )
            if guide_key not in guide_cache:
                guide_cache[guide_key] = _reference_cells(
                    p, records_for(p) if records_for else records, today, clues
                )
            cells, reasons = guide_cache[guide_key]
            ref = cells.get(clues["grade"])
            if ref is None:
                row["reason"] = reasons.get(
                    clues["grade"], "No applicable admitted reference for this printing and grade"
                )
            else:
                evidence = ref.get("raw_record") or {}
                issue = reference_issue(p, clues, ref, today)
                if issue:
                    row["reason"] = issue
                else:
                    generic_grade = clues["graded"] and ref.get("grader") != clues["grader"]
                    raw_condition = not clues["graded"] and (
                        _condition(evidence.get("condition")) is None
                        or _condition(clues["condition"]) is None
                    )
                    conditional = (
                        ref.get("match_status") != "exact"
                        or generic_grade
                        or raw_condition
                        or any(clues[k] is None for k in ("language", "edition", "finish"))
                        or shipping is None
                        or price is None
                        or bool(ref.get("conflicts"))
                        or bool(row.get("identity_uncertainties"))
                    )
                    row["reference"] = _reference(ref)
                    row["reference_eligibility"] = "conditional" if conditional else "eligible"
                    row["delivered_total"], comparison = _arithmetic(
                        price, shipping, ref, today, auction=auction
                    )
                    # A current bid is neither a final cost nor an owner bid. An
                    # admitted dated reference may be shown without a bargain rank.
                    row["comparison"] = dict(_NO_COMPARISON) if auction else comparison
                    row["classification"] = "conditional" if conditional or auction else "comparable"
                    row["reason"] = (
                        "Generic grade scenario; this reference does not establish a matching "
                        + clues["grader"]
                        + " slab"
                        if generic_grade
                        else "Conditional identity or condition comparison; verify edition, finish and condition"
                        if conditional
                        else "Applicable literal reference; seller identity and physical condition remain unverified"
                    )
                    if shipping is None:
                        row["reason"] += "; shipping is unknown, so a delivered comparison is unavailable"
                    if price is None:
                        row["reason"] += "; a supported listing price is unavailable"
                    if ref.get("conflicts"):
                        row["reason"] += "; competing source observations remain separate"
                    if not row["reference"]["save_allowed"]:
                        row["save_reason"] = (
                            "This source permits temporary comparison only; saving is unavailable."
                        )
                    if generic_grade:
                        row["basis"] += " Generic grade scenario, not an exact slab match."
                    elif clues["graded"]:
                        row["basis"] += " Literal grader and grade match; certification remains unverified."
        if auction:
            row["reason"] += "; current bid is not the final purchase price or your planned bid"
            row["basis"] += " Auction bid may change; any buy-now amount is a separate offer."
        if approximate and not matched:
            row["reason"] += "; approximate name match only, choose and confirm contents in review"
        if row["identity_uncertainties"]:
            row["reason"] += "; " + "; ".join(row["identity_uncertainties"])
        result.append(row)

    def rank(row):
        comparison = row["comparison"]
        classification = row["classification"]
        below = comparison["below_reference"] is True
        band = (
            0
            if classification == "comparable" and below
            else 1
            if classification == "conditional" and below
            else 2
            if classification == "comparable"
            else 3
            if classification == "conditional"
            else 4
        )
        delta = comparison["reference_minus_delivered_total"]
        return band, -Decimal(delta) if delta is not None else Decimal(0), row["item_id"]

    store.verified(actor)
    return sorted(result, key=rank)
