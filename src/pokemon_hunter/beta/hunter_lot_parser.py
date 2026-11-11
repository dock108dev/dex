"""Bounded interpretation of supplied seller text and authorized printing identities.

No acquisition, review persistence or collection mutation belongs here. Caller
services retain account/lease checks and admission of reference values.
"""

import hashlib
import re
from html.parser import HTMLParser

from . import catalog_variants, discovery_matching, hunter_catalog, listing_details, shopping
from . import discovery_comparison as dc
from . import hunter_lot_evidence as evidence

MAX_TEXT_BYTES = 65536
MAX_TOKENS = 8192
MAX_SEGMENTS = 400
MAX_SEGMENT_CHARS = 2048
MAX_ITEMS = 200
MAX_QUANTITY = 100000
MAX_CANDIDATES = 40
MAX_CANDIDATE_BINDINGS = 200
_BLOCKS = {"br", "p", "div", "li", "ul", "ol", "tr", "td", "h1", "h2", "h3"}
_HIDDEN = {"script", "style", "iframe", "object", "svg", "template", "figcaption"}


class _PlainText(HTMLParser):
    """Discard markup, scripts and links without loading any external resource."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = []

    def handle_starttag(self, tag, attrs):
        if tag in _HIDDEN:
            self.hidden.append(tag)
        if tag in _BLOCKS and not self.hidden:
            self.parts.append("\n")

    def handle_startendtag(self, tag, attrs):
        if tag in _BLOCKS and not self.hidden:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if self.hidden and tag == self.hidden[-1]:
            self.hidden.pop()
        if tag in _BLOCKS and not self.hidden:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def _text(raw):
    if not isinstance(raw, str):
        raise ValueError("Seller content must be bounded text")
    parser = _PlainText()
    parser.feed(raw)
    parser.close()
    return "".join(parser.parts)


def _quantity(text, *, title=False):
    text = evidence.quantity_text(text)
    if re.search(r"\b[0-9]+\s*[x×]{2,}", text, re.I):
        return None, "Explicit per-card multiplicity is malformed"
    explicit_patterns = (
        r"^\s*([+-]?[0-9]+(?:\.[0-9]+)?)\s+(?:19|20)[0-9]{2}\s+[A-Za-z]",
        r"(?<![\w/#.])([+-]?[0-9]+(?:\.[0-9]+)?)\s*[x×](?!\w)",
        r"^\s*(?:[-*•]\s+)?([+-]?[0-9]+(?:\.[0-9]+)?)\s+(?!cards?\b|total\b|lots?\b)[A-Za-z]",
        r"\(\s*([+-]?[0-9]+(?:\.[0-9]+)?)\s*\)\s*$",
        r"^\s*(?:[-*•]\s+)?([+-]?[0-9]+(?:\.[0-9]+)?)\s*[x×]+\b",
        r"\b[x×]\s*([+-]?[0-9]+(?:\.[0-9]+)?)(?![\w.])",
        r"\b(?:qty|quantity)\s*[:=]?\s*([+-]?[0-9]+(?:\.[0-9]+)?)\b",
        r"\b([+-]?[0-9]+(?:\.[0-9]+)?)\s+copies?\b",
    )
    for pattern in explicit_patterns:
        for match in re.finditer(pattern, text, re.I):
            if not re.fullmatch(r"[1-9][0-9]{0,5}", match[1]) or int(match[1]) > MAX_QUANTITY:
                return None, "Explicit per-card multiplicity is invalid or exceeds the review limit"
    patterns = (
        r"^\s*([1-9][0-9]{0,5})\s+(?:19|20)[0-9]{2}\s+[A-Za-z]",
        r"(?<![\w/#.])([1-9][0-9]{0,5})\s*[x×](?!\w)",
        r"\(\s*([1-9][0-9]{0,5})\s*\)\s*$",
        r"^\s*(?:[-*•]\s+)?([1-9][0-9]{0,5})\s+(?!cards?\b|total\b|lots?\b|[x×]\b)[A-Za-z]",
        r"\b([1-9][0-9]{0,5})\s+copies?\b",
        r"^\s*(?:[-*•]\s+)?([1-9][0-9]{0,5})\s*[x×]\s+",
        r"^\s*(?:[-*•]\s+)?([1-9][0-9]{0,5})\s+(?:copies?\s+(?:of\s+)?|of\s+)",
        r"\s+[x×]\s*([1-9][0-9]{0,5})\s*$",
        r"\b[x×]\s*([1-9][0-9]{0,5})\b",
        r"\s*\(\s*([1-9][0-9]{0,5})\s+copies?\s*\)\s*$",
        r"\b(?:qty|quantity)\s*[:=]?\s*([1-9][0-9]{0,5})\b",
    )
    values = {int(m[1]) for pattern in patterns for m in re.finditer(pattern, text, re.I)}
    if len(values) > 1:
        return None, "Conflicting per-card quantities"
    if values:
        value = next(iter(values))
        if value > MAX_QUANTITY:
            return None, "Per-card quantity exceeds the review limit"
        return value, None
    if re.search(
        r"\b(?:hundred|thousand|dozen|pair|several|multiple|various|some|many|random|assorted|choose|pick)\b",
        text,
        re.I,
    ):
        return None, "Per-card quantity is ambiguous"
    return (None, "A title mention does not establish per-card multiplicity") if title else (1, None)


def _totals(text, names=()):
    text = evidence.quantity_text(text)
    text = re.sub(
        r"(?<!\d)[1-9][0-9]{0,2}(?:,[0-9]{3})+(?!\d)", lambda match: match[0].replace(",", ""), text
    )
    patterns = (
        r"\blot\s+of\s+([1-9][0-9]{0,5})\b(?!\s+lots?\b)",
        r"\b([1-9][0-9]{0,5})(?:\s+|[-‐‑–])(?:total\s+)?cards?\b",
        r"\btotal\s*(?:cards?\s*)?[:=]?\s*([1-9][0-9]{0,5})\b",
    )
    totals = {int(m[1]) for pattern in patterns for m in re.finditer(pattern, text, re.I)}
    # A complete named-family count sentence is a total, not an item subtotal
    # inside a longer conjunction/list. Only actual catalog names qualify.
    for name in names:
        pattern = (
            r"(?:^|[.\n])\s*(?:(?:this\s+(?:lot|bundle)\s+(?:includes|contains)|you\s+(?:will\s+)?receive)\s+)?([1-9][0-9]{0,5})\s+"
            + re.escape(name)
            + r"\s+cards?\s*(?:[.!]|$)"
        )
        totals.update(int(m[1]) for m in re.finditer(pattern, text, re.I))
    return totals


def _conflicting_fields(clues):
    fields = set()
    for issue in clues["conflicts"]:
        folded = issue.casefold()
        for token, field in (
            ("language", "language"),
            ("edition", "edition"),
            ("finish", "finish"),
            ("condition", "condition"),
        ):
            if token in folded:
                fields.add(field)
        if "grade" in folded:
            fields.update({"grade", "grader"})
    if len(clues.get("condition_claims", [])) > 1:
        fields.add("condition")
    return fields


def parse(raw, printings, *, detail=None, _index=None, complete_candidates=False):
    """Parse supplied authorized text only, with hard work and quantity limits.

    ``detail`` is an internal authorized adapter input, never a client-supplied body.
    Its exact variation must match the summary. It grants no acquisition right.
    Repeated identical mentions across fields are evidence, not extra copies.
    """
    if not isinstance(raw, dict):
        raise ValueError("Choose an authorized listing summary")
    if detail is not None:
        listing_details.validate_response(raw.get("itemId"), detail)
    fields, aspects, raw_bytes = evidence.fields(raw, detail, _text)
    if sum(len(re.findall(r"\S+", value)) for _, value in fields) > MAX_TOKENS:
        raise ValueError("Seller text exceeds 8192 tokens; explicit manual review required")
    index = _index or hunter_catalog.IdentityIndex(printings)
    segments, scopes, set_claims = evidence.segments(fields, aspects, index)
    sections_present = any(m.get("section") for _, _, m in segments)
    if any(len(text) > MAX_SEGMENT_CHARS for _, text, _ in segments):
        raise ValueError("Seller text segment exceeds 2048 characters; manual review required")
    if len(segments) > MAX_SEGMENTS:
        raise ValueError("Seller text exceeds 400 segments; manual review required")
    totals, total_mentions = set(), []
    for field, value in fields:
        claims = (
            {int(value)}
            if aspects.get(field) in evidence.COUNT_ASPECTS and re.fullmatch(r"[1-9][0-9]{0,5}", value)
            else set()
            if field in aspects
            else _totals(value, {p["name"] for p in index.candidates(dict(text=value))})
        )
        if claims:
            totals.update(claims)
            total_mentions.append(dict(evidence.mention(field, value), quantities=sorted(claims)))
    lookups = {}

    def candidates_for(clues):
        if not complete_candidates:
            return index.candidates(clues)
        text_key = clues["text"].strip()
        if text_key not in lookups:
            lookups[text_key] = index.candidates(clues)
        return lookups[text_key]

    multiple_catalog_names = complete_candidates and len({p["name"].casefold() for p in printings}) > 1
    proposals, seen, unresolved = [], {}, []
    product_excluded = any(
        evidence.unsupported(value, candidates_for(dc._clues(dict(title=value))))
        for field, value in fields
        if field.endswith("title")
    )
    candidate_bindings = 0
    excluded = []
    for field, text, literal_evidence in sorted(segments, key=lambda segment: segment[0].endswith("title")):
        # Multiplicity is parsed separately; it cannot become a conflicting
        # collector-number claim in the shared literal matcher.
        identity_text = re.sub(r"\b(?:qty|quantity)\s*[:=]?\s*[1-9][0-9]{0,5}\b", " ", text, flags=re.I)
        identity_text = re.sub(r"\b[x×]\s*[1-9][0-9]{0,5}\b", " ", identity_text, flags=re.I)
        identity_text = re.sub(r"(?<![\w/#.])[1-9][0-9]{0,5}\s*[x×](?!\w)", " ", identity_text, flags=re.I)
        scoped_text = " ".join([identity_text, *evidence.scoped_claims(identity_text, scopes, aspects)])
        clues = dc._clues(dict(title=scoped_text, condition=raw.get("condition", "")))
        # A missing grade claim is not a claim that this particular card is raw.
        # Only this card's scoped text may establish its status in a mixed lot.
        from . import listing_grading

        if listing_grading.status({}, scoped_text) == "unknown":
            clues["grade"] = ""
        # Retain a per-card condition category only when this scoped segment
        # states exactly one. The literal source spans remain available below.
        if len(clues["condition_claims"]) == 1:
            clues["condition"] = clues["condition_claims"][0]
        local_ids = {p["id"] for p in index.candidates(dict(text=identity_text))}
        candidates = [p for p in candidates_for(clues) if p["id"] in local_ids]
        plausible = dc._approx_matches(candidates, clues)
        if multiple_catalog_names:
            literal = discovery_matching.literal_candidates(printings, identity_text)
            if len({p["name"].casefold() for p in literal}) > 1:
                # A shared set/number cannot disambiguate different named cards.
                plausible = literal
        exclusion = evidence.noncontents(text, plausible)
        if product_excluded or evidence.unsupported(text, plausible):
            exclusion = "Unsupported sealed, mystery or random contents"
        if exclusion:
            repeated = next(
                (c for c in excluded if c["reason"] == exclusion and c["mentions"][0]["text"] == text), None
            )
            if repeated:
                repeated["mentions"].extend(literal_evidence.get("mentions", [literal_evidence]))
            else:
                excluded.append(
                    dict(
                        mentions=literal_evidence.get("mentions", [literal_evidence]),
                        reason=exclusion,
                        candidate_ids=[p["id"] for p in plausible],
                    )
                )
            continue
        if not plausible:
            if re.search(r"\b(?:complete|full)\s+(?:set|collection)|\bset\b", text, re.I) and not _totals(
                text
            ):
                set_claims.append(literal_evidence)
            # Headers/counts and innocuous listing prose are not invented cards.
            # Unrecognized explicit quantity lines are retained as unresolved.
            quantity, reason = _quantity(text, title=field.endswith("title"))
            quantity_line = evidence.quantity_text(text)
            metadata_only = bool(
                re.search(
                    r"\b(?:stock|available|lots?\s+offered|business\s+days?|handling|shipping|returns?|delivery)\b",
                    text,
                    re.I,
                )
            )
            subgroup = bool(
                re.match(
                    r"^\s*\d+\s+(?:of\s+(?:these|them|the\s+cards)|are\b|have\b|show\b)", quantity_line, re.I
                )
            )
            template_header = bool(
                re.fullmatch(
                    r"\s*(?:includes|contents|cards)\s*\(\s*(?:qty|quantity)\s*[x×]\s*name(?:\s+#[^)]*)?\s*\)\s*:?\s*",
                    text,
                    re.I,
                )
            )
            if (
                quantity is not None
                and not template_header
                and not metadata_only
                and not subgroup
                and not _totals(text)
                and re.search(r"(?:^\s*\d+\s*(?:[x×]|[A-Za-z])|\b(?:qty|quantity)\b)", quantity_line, re.I)
            ):
                repeated = next(
                    (r for r in unresolved if r["text"] == text and r["quantity"] == quantity), None
                )
                if repeated:
                    repeated["mentions"].extend(literal_evidence.get("mentions", [literal_evidence]))
                    continue
                unresolved.append(
                    dict(
                        text=text,
                        source_field=field,
                        quantity=quantity,
                        reason="No local card identity",
                        mentions=literal_evidence.get("mentions", [literal_evidence]),
                    )
                )
                if len(proposals) + len(unresolved) > MAX_ITEMS:
                    raise ValueError("Lot exceeds 200 content items; explicit manual review required")
            continue
        exact = dc._matches(candidates, clues)
        numbered = [p for p in plausible if discovery_matching.evidence(p, clues)["matched"]]
        # A literal name + set can identify a unique numbered catalog family.
        # Missing set, multiple numbers or conflicting explicit numbers never do.
        set_named = [p for p in plausible if discovery_matching.set_claimed(p, clues["text"])]
        if (
            not numbered
            and set_named
            and not any(discovery_matching.number_claims(p, clues["text"]) for p in set_named)
        ):
            families = {(p["set_id"], p["collector_number"], p["name"].casefold()) for p in set_named}
            if len(families) == 1:
                numbered = set_named
                fitting = [p for p in set_named if not dc._identity_conflicts(p, clues)]
                exact = catalog_variants.seller_candidates(fitting or set_named, clues)
        quantity_text = text
        if literal_evidence.get("section"):
            quantity_text = re.sub(r"^\s*[-*•]\s+(?:19|20)[0-9]{2}\s+", "", text)
        quantity, quantity_reason = _quantity(
            quantity_text,
            title=field.endswith("title")
            or field == "structured_identity"
            or (sections_present and not literal_evidence.get("section")),
        )
        if field == "structured_identity" and totals == {1}:
            quantity, quantity_reason = 1, None
        if (
            sections_present
            and not literal_evidence.get("section")
            and quantity is None
            and quantity_reason == "A title mention does not establish per-card multiplicity"
        ):
            context = evidence.section_context(proposals, plausible, identity_text, clues)
            if context:
                for row in context:
                    row["mentions"].extend(literal_evidence.get("mentions", [literal_evidence]))
                continue
        names = {p["name"].casefold() for p in plausible}
        reasons = list(clues["conflicts"])
        numbers = {number for p in plausible for number in discovery_matching.number_claims(p, identity_text)}
        if numbers and all(
            any(
                discovery_matching.number_key(number)[0]
                != discovery_matching.number_key(p["collector_number"])[0]
                or (
                    len(discovery_matching.number_key(number)) > 1
                    and len(discovery_matching.number_key(p["collector_number"])) > 1
                    and discovery_matching.number_key(number)[1:]
                    != discovery_matching.number_key(p["collector_number"])[1:]
                )
                for number in numbers
            )
            for p in plausible
        ):
            reasons.append("Seller collector-number claims conflict with catalog identity")
        reasons.extend(index.set_issues(plausible, clues))
        if clues["graded"]:
            reasons.append("Graded contents are excluded from automatic ungraded selection")
        if quantity_reason:
            reasons.append(quantity_reason)
        if len(names) > 1:
            reasons.append("Multiple card names share one text segment; split and correct quantities")
            quantity = None
        if len(exact) != 1:
            reasons.append(
                "Printing needs correction" if exact else "Set or collector-number evidence is incomplete"
            )
        chosen = exact[0] if len(exact) == 1 and not clues["conflicts"] else None
        if chosen and dc._identity_conflicts(chosen, clues):
            reasons.extend(dc._identity_conflicts(chosen, clues))
            chosen = None
        if chosen and discovery_matching.unavailable(chosen):
            reasons.append(discovery_matching.unavailable(chosen))
            chosen = None
        family_candidates = numbered
        family_selection = catalog_variants.selection_projection(
            family_candidates,
            chosen,
            clues,
            quantity=quantity,
            mentions=literal_evidence.get("mentions", [literal_evidence]) + [m for _, m in scopes],
        )
        if family_selection and not family_selection.get("selected_child_id"):
            chosen = None
            reasons.append("Physical variant requires scoped seller evidence")
        from .tcgcsv_vintage import numbered_finish

        catalog_finish = numbered_finish(chosen) if chosen and family_selection else None

        def established(k):
            return clues.get(k) or (k == "finish" and catalog_finish == chosen.get("finish"))

        if chosen and any(
            not chosen.get(k) or (not established(k) and chosen.get(k) != "not_applicable")
            for k in ("language", "edition", "finish")
        ):
            missing = [
                k
                for k in ("language", "edition", "finish")
                if not chosen.get(k) or (not established(k) and chosen.get(k) != "not_applicable")
            ]
            reasons.append("Physical identity is not established: confirm " + ", ".join(missing))
            chosen = None
        if family_selection and (chosen is None or reasons):
            family_selection.update(selected_child_id=None, allocations=[])
        candidate_rows = (
            family_candidates
            if family_selection
            else plausible
            if complete_candidates and len(names) > 1
            else exact or plausible
        )
        visible_candidates = (
            candidate_rows
            if complete_candidates
            else candidate_rows[: min(MAX_CANDIDATES, MAX_CANDIDATE_BINDINGS - candidate_bindings)]
        )
        candidate_bindings += len(visible_candidates)
        if len(visible_candidates) < len(candidate_rows):
            reasons.append("Plausible printing choices exceed the bounded response; refine locally")
        # Same identity+quantity repeated in title/description never adds units.
        # Conflicting repeated quantities stay as separate unresolved claims.
        identity_key = tuple(sorted(p["id"] for p in candidate_rows))
        key = (
            identity_key,
            quantity,
            chosen["id"] if chosen else None,
            clues.get("finish") if sections_present else None,
        )
        item_mentions = literal_evidence.get("mentions", [literal_evidence])
        if key in seen:
            previous = seen[key]
            previous["mentions"].extend(item_mentions)
            conflicting = []
            for trait in ("language", "edition", "finish", "grader", "grade"):
                before, after = previous["clues"].get(trait), clues.get(trait)
                if before and after and before != after:
                    conflicting.append(trait)
            conditions = set(previous["clues"].get("condition_claims", [])) | set(
                clues.get("condition_claims", [])
            )
            if len(conditions) > 1:
                conflicting.append("condition")
            has_conflict = bool(
                conflicting
                or clues["conflicts"]
                or any("conflict" in reason.casefold() for reason in reasons)
            )
            if reasons or conflicting:
                previous["included_quantity"] = 0
                previous["printing_id"] = None
                if previous.get("variant_selection"):
                    previous["variant_selection"].update(selected_child_id=None, allocations=[])
                previous["conflicting_fields"] = sorted(
                    set(previous.get("conflicting_fields", []))
                    | set(conflicting)
                    | _conflicting_fields(clues)
                )
                previous["reasons"] = list(
                    dict.fromkeys(
                        [
                            *previous["reasons"],
                            *reasons,
                            *(
                                [
                                    "Repeated seller mentions contain conflicting identity or applicability claims"
                                ]
                                if has_conflict
                                else []
                            ),
                        ]
                    )
                )
                previous["clues"]["conflicts"] = list(
                    dict.fromkeys(
                        [
                            *previous["clues"]["conflicts"],
                            *clues["conflicts"],
                            *(
                                ["Repeated seller mentions require explicit attribute correction"]
                                if has_conflict
                                else []
                            ),
                        ]
                    )
                )
            continue
        other = [
            p
            for (ids, _, selected, _), p in seen.items()
            if ids == identity_key
            and not (
                sections_present
                and p["clues"].get("finish")
                and clues.get("finish")
                and p["clues"]["finish"] != clues["finish"]
            )
            and (
                selected == (chosen["id"] if chosen else None)
                or selected is None
                or chosen is None
                or p["mentions"][0]["source_field"] != field
            )
        ]
        if (
            other
            and quantity is None
            and quantity_reason == "A title mention does not establish per-card multiplicity"
            and not any("conflict" in reason.casefold() for reason in reasons)
        ):
            previous = other[0]
            previous["mentions"].extend(item_mentions)
            if any(
                clues.get(k) and previous["clues"].get(k) and clues[k] != previous["clues"][k]
                for k in ("language", "edition", "finish")
            ):
                previous.update(included_quantity=0, printing_id=None)
                previous["reasons"].append("Conflicting seller identity claims")
                if previous.get("variant_selection"):
                    previous["variant_selection"].update(selected_child_id=None, allocations=[])
            continue
        if other:
            reasons.append("Repeated card mention has conflicting quantities; correct multiplicity")
            quantity = None
            for previous in other:
                previous["quantity"] = None
                previous["included_quantity"] = 0
                previous["printing_id"] = None
                if previous.get("variant_selection"):
                    previous["variant_selection"].update(selected_child_id=None, allocations=[])
                previous["reasons"].append(
                    "Repeated card mention has conflicting quantities; correct multiplicity"
                )
        if family_selection:
            family_selection["quantity"] = quantity
            if not chosen or not quantity or reasons:
                family_selection.update(selected_child_id=None, allocations=[])
            if "seller_evidence" in family_selection:
                family_selection["seller_evidence"].update(
                    observation_sha256=shopping.digest(dict(fields=fields, aspects=aspects)),
                    item_id=raw.get("itemId"),
                )
        row = dict(
            section=bool(literal_evidence.get("section")),
            parent_identity=(
                tuple(
                    next(
                        iter(
                            {
                                (p["set_id"], p["collector_number"], p["name"].casefold())
                                for p in family_candidates
                            }
                        )
                    )
                )
                if family_candidates
                and len(
                    {(p["set_id"], p["collector_number"], p["name"].casefold()) for p in family_candidates}
                )
                == 1
                else None
            ),
            variant_selection=family_selection,
            proposal_id=hashlib.sha256((str(len(proposals)) + "\0" + text).encode()).hexdigest()[:24],
            name=next(iter(names)) if len(names) == 1 else None,
            quantity=quantity,
            included_quantity=quantity if chosen and quantity and not reasons else 0,
            printing_id=chosen["id"] if chosen else None,
            candidates=[
                dict(shopping.identity(p), image_binding=dict(printing_id=p["id"], role="catalog_reference"))
                for p in visible_candidates
            ],
            candidates_total=len(candidate_rows),
            reasons=reasons,
            conflicting_fields=sorted(_conflicting_fields(clues)),
            clues={k: v for k, v in clues.items() if k != "text"},
            mentions=item_mentions,
            scope_mentions=[m for _, m in scopes],
        )
        seen[key] = row
        proposals.append(row)
        if len(proposals) + len(unresolved) > MAX_ITEMS:
            raise ValueError("Lot exceeds 200 content items; explicit manual review required")
    proposals = evidence.reconcile(proposals)
    for claim in excluded:
        if "excludes" not in claim["reason"]:
            continue
        for row in proposals:
            if set(claim["candidate_ids"]) & {p["id"] for p in row["candidates"]}:
                row.update(included_quantity=0, printing_id=None)
                row["reasons"].append("Seller inclusion and exclusion claims conflict")
                row["mentions"].extend(claim["mentions"])
                if row.get("variant_selection"):
                    row["variant_selection"].update(selected_child_id=None, allocations=[])
    if any(total > MAX_QUANTITY for total in totals):
        raise ValueError("Seller card total exceeds 100000 cards")
    total = next(iter(totals)) if len(totals) == 1 else None
    known = sum(p["included_quantity"] for p in proposals)
    if known > MAX_QUANTITY:
        raise ValueError("Proposed quantities exceed 100000 cards")
    unknown = total - known if total is not None and total >= known else None
    issues = []
    if any(
        re.search(r"\b(?:complete|full)\s+(?:set|collection)|\bcomplete\s+.+\bset\b", m["text"], re.I)
        for m in set_claims
    ):
        issues.append("Set-wide completeness claim is not a verified checklist")
    if len(totals) > 1:
        issues.append("Conflicting seller-stated total card counts")
    if total is not None and known > total:
        issues.append("Proposed quantities exceed the seller-stated card count")
    if not proposals:
        issues.append("Vague or photos-only contents remain unresolved")
    if any("Unsupported" in p["reason"] for p in excluded):
        issues.append("Unsupported products are outside the selected cards")
    if unresolved or any(not p["included_quantity"] for p in proposals):
        issues.append("Unresolved identity or quantity claims require correction")
    if any(
        "conflicting quantities" in reason.casefold()
        or ("quantity claims conflict" in reason.casefold() and p["quantity"] is None)
        for p in proposals
        for reason in p["reasons"]
    ):
        unknown = None
    if unknown is None or unknown:
        issues.append("The complete lot contents have not been reconciled")
    availability = raw.get("estimatedAvailabilities", [])
    stock = (
        {
            v.get("estimatedAvailableQuantity")
            for v in availability
            if isinstance(v, dict) and type(v.get("estimatedAvailableQuantity")) is int
        }
        if isinstance(availability, list)
        else set()
    )
    offered = {
        int(m[1])
        for _, value in fields
        for m in re.finditer(r"\b([1-9][0-9]{0,5})\s+lots?\s+(?:of|available|offered)\b", value, re.I)
    }
    units = raw.get("lotSize")
    lot_units = (
        int(units) if isinstance(units, (int, str)) and re.fullmatch(r"[1-9][0-9]{0,5}", str(units)) else None
    )
    return dict(
        schema="dex-seller-contents-v2",
        evidence_basis="seller_stated",
        source_fields=dict(fields),
        aspect_names=aspects,
        total_mentions=total_mentions,
        set_claims=set_claims,
        excluded_claims=excluded,
        physically_selected_quantity=known,
        unidentified_quantity=unknown,
        contents_state="resolved" if not issues else "unresolved",
        proposals=proposals,
        unresolved_contents=unresolved,
        seller_stated_total=total,
        seller_stated_totals=sorted(totals),
        included_quantity=known,
        parent_identified_quantity=sum(p["quantity"] or 0 for p in proposals if p.get("parent_identity")),
        unknown_remainder=unknown,
        stock_quantity=next(iter(stock)) if len(stock) == 1 else None,
        lot_units=lot_units,
        seller_lots_offered=next(iter(offered)) if len(offered) == 1 else None,
        quantity_issues=issues,
        text_bytes=raw_bytes,
        segment_count=len(segments),
        detail_used=detail is not None,
    )


def catalog_text(raw, detail=None):
    """Use every supplied text field for catalog narrowing, never the hunt target."""
    if detail is not None:
        listing_details.validate_response(raw.get("itemId"), detail)
    fields, _, _ = evidence.fields(raw, detail, _text)
    return " ".join(value for _, value in fields)


def interpretation_fields(raw):
    """Allowlisted seller text only; never include prices, URLs or account data."""
    fields = {}
    for source, key in (
        ("title", "title"),
        ("description", "shortDescription"),
        ("description_full", "description"),
    ):
        value = raw.get(key, "")
        if not isinstance(value, str):
            raise ValueError("Seller text is unavailable")
        if value:
            fields[source] = _text(value)
    aspects = raw.get("localizedAspects", [])
    if not isinstance(aspects, list) or len(aspects) > 100:
        raise ValueError("Seller specifics exceed their limit")
    for index, row in enumerate(aspects):
        if not isinstance(row, dict) or not all(isinstance(row.get(k), str) for k in ("name", "value")):
            raise ValueError("Invalid seller specifics")
        if len(row["name"]) > 100 or len(row["value"]) > 500:
            raise ValueError("Seller specifics exceed their limit")
        fields[f"specific_{index}"] = _text(row["name"] + ": " + row["value"])
    if not fields or sum(len(v.encode()) for v in fields.values()) > 16000:
        raise ValueError("Choose a listing with at most 16,000 bytes of seller text")
    return fields


def interpretation_result(fields, raw):
    """AI suggestions stay evidence-bound claims; no costs, ownership or mutations."""
    allowed = {
        "name",
        "set",
        "number",
        "language",
        "edition",
        "finish",
        "quantity",
        "structure",
        "condition",
        "grade",
        "exclusion",
    }
    if (
        not isinstance(raw, dict)
        or set(raw) != {"facts"}
        or not isinstance(raw["facts"], list)
        or len(raw["facts"]) > 12
    ):
        raise ValueError("Invalid interpretation")
    facts, warnings = [], []
    for fact in raw["facts"]:
        if not isinstance(fact, dict) or set(fact) != {"field", "value", "source", "quote"}:
            raise ValueError("Invalid fact")
        if any(not isinstance(value, str) or not value or len(value) > 500 for value in fact.values()):
            raise ValueError("Invalid fact value")
        field, value, source, quote = (fact[k] for k in ("field", "value", "source", "quote"))
        if field not in allowed or source not in fields or quote not in fields[source]:
            raise ValueError("Unsupported evidence")
        if field == "quantity":
            words = {"one": "1", "two": "2", "three": "3", "four": "4", "five": "5"}
            evidence = re.sub(r"\b(one|two|three|four|five)\b", lambda m: words[m[0]], quote.casefold())
            if (
                not re.fullmatch(r"[1-9][0-9]{0,5}", value)
                or int(value) > MAX_QUANTITY
                or not re.search(r"\b" + re.escape(value) + r"\s*(?:cards?|copies|copy|[x×])\b", evidence)
            ):
                raise ValueError("Quantity requires explicit card-count evidence")
        elif field == "structure":
            if value not in {"single", "mixed"}:
                raise ValueError("Invalid structure")
        elif value.casefold() not in quote.casefold():
            raise ValueError("Value lacks literal evidence")
        if field == "number" and not re.fullmatch(
            r"[A-Za-z]*[0-9]+[A-Za-z]*(?:/[A-Za-z]*[0-9]+[A-Za-z]*)?", value
        ):
            warnings.append("Unsupported collector-number suggestion omitted; review the original text.")
            continue
        facts.append(dict(fact, status="seller claim — review required"))
    for field in allowed:
        if len({f["value"].casefold() for f in facts if f["field"] == field}) > 1:
            warnings.append(f"Conflicting {field} claims; correct manually.")
    # Surface source-level hazards even when the model silently omits them.
    source_text = " ".join(fields.values())
    counts = set()
    words = {"one": "1", "two": "2", "three": "3", "four": "4", "five": "5"}
    normalized = re.sub(r"\b(one|two|three|four|five)\b", lambda m: words[m[0]], source_text.casefold())
    for count in re.findall(r"\b([0-9]+)\s*(?:cards?|copies|copy)\b", normalized):
        counts.add(int(count))
    if len(counts) > 1:
        warnings.append("Multiple card counts occur in the seller text; resolve quantities manually.")
    if re.search(r"\b(?:not included|excluded|excluding|except|without)\b", source_text, re.I) and not any(
        f["field"] == "exclusion" for f in facts
    ):
        warnings.append(
            "Seller exclusions were not extracted; review the original text before choosing cards."
        )
    patterns = {
        "condition": r"(?:near mint|mint|nm|lightly played|moderately played|heavily played|lp|mp|hp|damaged|excellent|good|poor|ungraded|used)",
        "edition": r"(?:1st edition|first edition|1st|unlimited|shadowless)",
        "finish": r"(?:non[ -]?holo|reverse holo|holo(?:graphic)?|normal|foil|reverse foil|non[ -]?foil)",
    }
    for fact in facts[:]:
        pattern = patterns.get(fact["field"])
        if pattern and not re.fullmatch(pattern, fact["value"].strip(" ."), re.I):
            facts.remove(fact)
            warnings.append(
                f"Unrecognized {fact['field']} suggestion omitted; review original seller wording."
            )
    explicit_one = any(re.search(r"\bone\s+card\b", v, re.I) for v in fields.values())
    if explicit_one and not any(f["field"] == "quantity" for f in facts):
        warnings.append("Seller explicitly says one card; quantity was not extracted. Review it manually.")
    return dict(
        facts=facts,
        source_fields=dict(fields),
        warnings=warnings,
        unknown_fields=sorted(allowed - {f["field"] for f in facts}),
        notice="Suggestions from seller text, not verified card identity. Prices, fees and ownership are unchanged.",
    )
