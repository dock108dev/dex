"""Bounded text evidence for the existing lot parser; no I/O or model execution.

Spans are Unicode character offsets in sanitized plain-text source fields, not
HTML byte offsets. Scope evidence is kept separately from each literal item line.
"""

import re

from . import discovery_comparison as dc
from . import discovery_matching as matching

TRAIT_ASPECTS = {
    "set",
    "language",
    "edition",
    "finish",
    "card finish",
    "features",
    "graded",
    "professional grader",
    "grade",
}
CONTENT_ASPECTS = {"card name", "character", "card number", "collector number", "contents", "cards included"}
COUNT_ASPECTS = {"number of cards", "lot size"}
WORDS = {
    "zero": "0",
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
    "ten": "10",
    "eleven": "11",
    "twelve": "12",
    "thirteen": "13",
    "fourteen": "14",
    "fifteen": "15",
    "sixteen": "16",
    "seventeen": "17",
    "eighteen": "18",
    "nineteen": "19",
    "twenty": "20",
    "thirty": "30",
    "forty": "40",
    "fifty": "50",
    "sixty": "60",
    "seventy": "70",
    "eighty": "80",
    "ninety": "90",
}


def fields(raw, detail, plain):
    values = [("title", raw.get("title", "")), ("summary", raw.get("shortDescription", ""))]
    if detail is not None:
        values += [
            ("detail_title", detail.get("title", "")),
            ("official_description", detail.get("description", "")),
        ]
        if detail.get("shortDescription") and detail["shortDescription"] != raw.get("shortDescription"):
            values.append(("detail_summary", detail["shortDescription"]))
    aspects = (detail if detail is not None else raw).get("localizedAspects", [])
    if not isinstance(aspects, list) or len(aspects) > 100:
        raise ValueError("Official lot details exceed 100 structured aspects")
    aspect_names = {}
    for i, aspect in enumerate(aspects):
        if not isinstance(aspect, dict) or not all(isinstance(aspect.get(k), str) for k in ("name", "value")):
            raise ValueError("Unsupported official detail aspect")
        name, value = aspect["name"], aspect["value"]
        if len(name) > 100 or len(value) > 500:
            raise ValueError("Seller specifics exceed their limit")
        key = f"aspect_{i}"
        aspect_names[key] = name.casefold().strip()
        values.append((key, value))
    if any(not isinstance(value, str) for _, value in values):
        raise ValueError("Seller content must be bounded text")
    size = sum(len(value.encode()) for _, value in values)
    if size > 65536:
        raise ValueError("Seller text exceeds 65536 bytes; explicit manual review required")
    return [(key, plain(value)) for key, value in values], aspect_names, size


def mention(field, value, start=0, end=None):
    end = len(value) if end is None else end
    return dict(source_field=field, start=start, end=end, text=value[start:end], span_basis="sanitized_text")


def quantity_text(text):
    text = re.sub(r"\b(?:a\s+)?pair\s+of\b", "2 copies of", text, flags=re.I)
    text = re.sub(
        r"\b(twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety)[ -](one|two|three|four|five|six|seven|eight|nine)\b",
        lambda m: str(int(WORDS[m[1].casefold()]) + int(WORDS[m[2].casefold()])),
        text,
        flags=re.I,
    )
    text = re.sub(r"\b(" + "|".join(WORDS) + r")\b", lambda m: WORDS[m[0].casefold()], text, flags=re.I)
    return re.sub(r"^\s*(?:includes?|contains?|featuring|contents\s*:)\s*", "", text, flags=re.I)


def segments(fields, aspects, index):
    """Split explicit lists, never a catalog name containing 'and'."""
    result, scopes, claims = [], [], []
    identity_aspects = []
    for field, value in fields:
        scope_continuation = False
        name = aspects.get(field)
        if name in TRAIT_ASPECTS:
            # 'Graded: No' is a negative assertion, not the word 'graded'.
            text = "graded" if name == "graded" and value.casefold() in {"yes", "true"} else value
            # eBay's literal single Finish: Regular means the normal/nonfoil
            # finish. Do not treat ordinary prose containing "regular" as a claim.
            if name in {"finish", "card finish"} and value.casefold().strip() == "regular":
                text = "normal"
            scopes.append((text, mention(field, value)))
            continue
        if name in CONTENT_ASPECTS:
            identity_aspects.append((field, value))
            continue
        if name is not None:
            continue  # Counts, stock and platform metadata never become card lines.
        for match in re.finditer(r"[^\n;,]+(?:,(?=[0-9]{3}\b)[^\n;,]+)*", value):
            start, end = match.span()
            while start < end and value[start].isspace():
                start += 1
            while end > start and value[end - 1].isspace():
                end -= 1
            if start == end:
                continue
            text = value[start:end]
            # Sentence delimiters exclude decimals and collector fractions.
            named = index.candidates(dict(text=text))
            name_spans = [
                m.span()
                for p in named
                for name in matching.names(p)
                for m in re.finditer(re.escape(name).replace(r"\ ", r"\s+"), text, re.I)
            ]
            boundaries = [
                m.start()
                for m in re.finditer(r"[.!?](?=\s|$)", text)
                if not any(lo <= m.start() < hi for lo, hi in name_spans)
            ]
            pieces, cursor = [], 0
            for boundary in boundaries:
                pieces.append((cursor, boundary))
                cursor = boundary + 1
            pieces.append((cursor, len(text)))
            for lo, hi in pieces:
                a, b = start + lo, start + hi
                while a < b and value[a].isspace():
                    a += 1
                if a == b:
                    continue
                line = value[a:b]
                traits = dc._clues(dict(title=line))
                continuation = (
                    scope_continuation
                    and not index.candidates(dict(text=line))
                    and any(traits[k] for k in ("language", "edition", "finish"))
                )
                if (
                    continuation
                    or re.match(r"set\s*/\s*edition\s*:\s*all\b", line, re.I)
                    or re.match(r"(?:all|both|each)\s+(?:of\s+the\s+)?(?:cards?|copies)\b", line, re.I)
                ):
                    scope_continuation = value[b : b + 1] not in {".", "!", "?", ";", "\n"}
                    scopes.append((line, mention(field, value, a, b)))
                    claims.append(mention(field, value, a, b))
                    continue
                scope_continuation = False
                # Conjunctions split only when both sides contain catalog names.
                cuts = [a]
                for conjunction in re.finditer(r"\s+and\s+", line, re.I):
                    left, right = line[: conjunction.start()], line[conjunction.end() :]
                    if index.candidates(dict(text=left)) and index.candidates(dict(text=right)):
                        cuts.extend([a + conjunction.start(), a + conjunction.end()])
                cuts.append(b)
                for lo, hi in zip(cuts[::2], cuts[1::2], strict=True):
                    result.append((field, value[lo:hi], mention(field, value, lo, hi)))
    # Structured identity attributes describe a single asserted identity only.
    # Lists in Contents remain separate; identity parts are jointly scoped.
    parts = [(f, v) for f, v in identity_aspects if aspects[f] not in {"contents", "cards included"}]
    if parts:
        text = " ".join(v for _, v in parts)
        result.append(("structured_identity", text, dict(mentions=[mention(f, v) for f, v in parts])))
    for field, value in identity_aspects:
        if aspects[field] in {"contents", "cards included"}:
            nested, nested_scopes, nested_claims = segments([(field, value)], {}, index)
            result.extend(nested)
            scopes.extend(nested_scopes)
            claims.extend(nested_claims)
    return _sections(result, fields, index), scopes, claims


def _sections(segments, fields, index):
    """Join indented numbered-card attributes only to their literal heading."""
    sections = []
    covered = []
    for field, value in fields:
        if field not in {"summary", "detail_summary", "official_description"}:
            continue
        lines = list(re.finditer(r"[^\n]+", value))
        for i, line in enumerate(lines):
            heading = line[0].strip()
            if not re.match(r"^[-*•]\s+.+:\s*$", heading) or not index.candidates(dict(text=heading)):
                continue
            indent = len(line[0]) - len(line[0].lstrip())
            parts = [mention(field, value, *line.span())]
            for following in lines[i + 1 :]:
                text = following[0]
                if not text.strip():
                    continue
                if len(text) - len(text.lstrip()) <= indent:
                    break
                if re.match(
                    r"\s*[-*•]\s*(?:Set|Card Number|Collector Number|Language|Edition|Finish)\s*:", text, re.I
                ):
                    parts.append(mention(field, value, *following.span()))
            if not any(re.search(r"(?:Card|Collector) Number\s*:", p["text"], re.I) for p in parts[1:]):
                continue
            sections.append((field, " ".join(p["text"] for p in parts), dict(mentions=parts, section=True)))
            covered.extend((field, p["start"], p["end"]) for p in parts)
    return sections + [
        row
        for row in segments
        if not any(row[0] == field and lo <= row[2].get("start", -1) < hi for field, lo, hi in covered)
    ]


def scoped_claims(text, scopes, aspects):
    """A literal list of finishes is a choice set, not a global single finish."""
    finish = dc._clues(dict(title=text))["finish"]
    result = []
    for claim, source in scopes:
        if aspects.get(source["source_field"]) in {"finish", "card finish"}:
            parts = re.split(r"\s*[,/]\s*", claim)
            finishes = {
                dc._clues(dict(title="normal" if p.casefold() == "regular" else p))["finish"] for p in parts
            }
            if len(parts) > 1 and None not in finishes and (finish is None or finish in finishes):
                continue
        result.append(claim)
    return result


def section_context(rows, candidates, text, clues):
    """Attach unquantified descriptive/list-wide claims to compatible sections.

    A mixed-finish title or numbered list describes the enumerated union, not a
    contradictory claim about every individual card. Unknown numbers, conflicting
    scalar traits and explicit quantities remain ordinary reconciliation inputs.
    """
    sections = [r for r in rows if r.get("section") and r["printing_id"]]
    ids = {p["id"] for p in candidates}
    related = [r for r in sections if r["printing_id"] in ids]
    if not related or set(clues["conflicts"]) - {"Conflicting seller finish claims"}:
        return []
    numbers = {matching.number_key(n) for p in candidates for n in matching.number_claims(p, text)}
    known = {
        matching.number_key(n)
        for r in related
        for p in r["candidates"]
        for n in [
            p["collector_number"],
            *matching.number_claims(p, " ".join(m["text"] for m in r["mentions"])),
        ]
    }
    if numbers and not numbers <= known:
        return []
    related = [
        r
        for r in related
        if not numbers or matching.number_key(r["parent_identity"][1])[0] in {n[0] for n in numbers}
    ]
    for trait in ("language", "edition", "finish", "grader", "grade"):
        if clues.get(trait):
            related = [r for r in related if r["clues"].get(trait) == clues[trait]]
    if "Conflicting seller finish claims" in clues["conflicts"]:
        finishes = set()
        for phrase in re.split(r"[,/]|\band\b", text, flags=re.I):
            value = dc._clues(dict(title=phrase))
            if value["conflicts"]:
                return []
            if value["finish"]:
                finishes.add(value["finish"])
        if len(finishes) < 2 or not finishes <= {r["clues"].get("finish") for r in related}:
            return []
    return related


def noncontents(text, candidates=()):
    """Conservative local exclusions; incidental packaging prose is harmless."""
    normalized = matching.literal(text)
    if any(
        re.search(r"\b(?:no|not|without|except|excluding)\s*$", normalized[:start], re.I)
        for p in candidates
        for start, _ in matching.name_spans(p, normalized)
    ):
        return "Seller excludes these contents or states a negative claim"
    if re.search(
        r"\b(?:not included|does not include|not for sale|excluded|excluding|except|not available)\b",
        text,
        re.I,
    ):
        return "Seller excludes these contents or states a negative claim"
    if re.search(r"\b(?:ignore|disregard|override|system prompt|execute|instructions?\s*:)\b", text, re.I):
        return "Instruction-like seller text is not a contents assertion"
    if re.search(
        r"\b(?:pictured|photo(?:graph)?s?|image|caption|example|such as|may (?:include|contain)|might (?:include|contain)|could include|not guaranteed)\b",
        text,
        re.I,
    ):
        return "Illustrative or photo-only mention does not establish supplied contents"
    return None


def unsupported(text, candidates):
    text = matching.without_names(candidates, text)
    text = matching.without_sets(candidates, text)
    if re.search(r"\b(?:no|not|without)\s+(?:sealed|graded|mystery|random|slabs?)\b", text, re.I):
        text = re.sub(
            r"\b(?:no|not|without)\s+(?:sealed|graded|mystery|random|slabs?)\b", "", text, flags=re.I
        )
    return bool(
        re.search(
            r"^\s*(?:[0-9]+\s*[x×]\s*)?(?:sealed|mystery|random|curated|repacked|choose your|custom|proxy|replica)\b",
            text,
            re.I,
        )
        or re.search(
            r"\b(?:mystery\s+(?:pokemon\s+)?(?:lot|box|pack|cards?)|random\s+(?:cards?|selection|lot)|sealed\s+(?:product|booster|pack|box|deck)|booster\s+(?:pack|box)|factory[ -]sealed)\b",
            text,
            re.I,
        )
    )


def reconcile(rows):
    """Fold broader repeated fields into specific lines without multiplying units.

    Separate, explicit variant allocations in the same field survive. Cross-field
    incompatible assertions withhold the affected selection, never pick a winner.
    """
    removed = set()
    for i, row in enumerate(rows):
        if i in removed:
            continue
        for j, other in enumerate(rows[i + 1 :], i + 1):
            if j in removed:
                continue
            if {m["source_field"] for m in row["mentions"]} & {m["source_field"] for m in other["mentions"]}:
                if not row.get("section") or other.get("section") or other.get("parent_identity"):
                    continue
                targets = [
                    candidate
                    for candidate in rows
                    if candidate.get("section")
                    and candidate["printing_id"]
                    and candidate["printing_id"] in {p["id"] for p in other["candidates"]}
                    and all(
                        not other["clues"].get(k) or other["clues"][k] == candidate["clues"].get(k)
                        for k in ("language", "edition", "finish", "grader", "grade")
                    )
                ]
                if targets != [row] and not any(
                    "conflict" in reason.casefold() for reason in other["reasons"]
                ):
                    continue
            shared = {p["id"] for p in row["candidates"]} & {p["id"] for p in other["candidates"]}
            parent = row.get("parent_identity") and row.get("parent_identity") == other.get("parent_identity")
            if not shared and not parent:
                continue
            # A broader mention of the other explicitly enumerated finish is
            # not a contradiction of this numbered section. Its own matching
            # section still checks quantity and identity below.
            if (
                row.get("section")
                and not other.get("parent_identity")
                and other["clues"].get("finish")
                and other["clues"]["finish"] != row["clues"].get("finish")
                and any(
                    candidate.get("section")
                    and candidate["clues"].get("finish") == other["clues"]["finish"]
                    and candidate["printing_id"] in {p["id"] for p in other["candidates"]}
                    for candidate in rows
                )
            ):
                continue
            conflicts = [
                k
                for k in ("language", "edition", "finish", "grader", "grade")
                if row["clues"].get(k) and other["clues"].get(k) and row["clues"][k] != other["clues"][k]
            ]
            q1, q2 = row["quantity"], other["quantity"]
            quantity_conflict = q1 is not None and q2 is not None and q1 != q2
            unsafe = any(
                "conflict" in r.casefold()
                or "graded contents" in r.casefold()
                or "special, altered" in r.casefold()
                for entry in (row, other)
                for r in entry["reasons"]
            )
            if conflicts or quantity_conflict or unsafe:
                row["included_quantity"] = other["included_quantity"] = 0
                row["printing_id"] = other["printing_id"] = None
                for entry in (row, other):
                    entry["conflicting_fields"] = sorted(set(entry["conflicting_fields"]) | set(conflicts))
                    entry["reasons"].append("Repeated seller identity or quantity claims conflict")
                    if entry.get("variant_selection"):
                        entry["variant_selection"].update(selected_child_id=None, allocations=[])
                if quantity_conflict:
                    row["quantity"] = None
            elif other["included_quantity"] and not row["included_quantity"]:
                # Keep the more specific evidence-backed selection.
                row, other = other, row
                rows[i], rows[j] = row, other
            elif not row["included_quantity"] and not other["included_quantity"] and q1 is None:
                row["quantity"] = q2
            if conflicts or quantity_conflict or unsafe:
                row["reasons"] = list(dict.fromkeys(row["reasons"] + other["reasons"]))
            row["mentions"].extend(other["mentions"])
            row["scope_mentions"].extend(other["scope_mentions"])
            removed.add(j)
    return [row for i, row in enumerate(rows) if i not in removed]
