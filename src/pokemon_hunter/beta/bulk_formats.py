"""Finite CSV/paste formats and draft fingerprints, without account reads or persistence."""

import csv
import io
import json

from pokemon_hunter.migration import digest, encode

from .collection_imports import FIELDS

SCHEMA = "dex-onboarding-v1"
LIMIT = 2000
MAX_BYTES = 1_500_000
# Retain Python's ordinary endpoint limit even when its process setting is disabled.
_MAX_RANGE_DIGITS = 4300
ACTIONS = {"add_copies", "set_total", "mark_owned"}
COLUMNS = (
    "schema",
    "row_id",
    "action",
    "game",
    "set_id",
    "set",
    "language",
    "number",
    "name",
    "printing_id",
    "quantity",
    "total",
    "edition",
    "finish",
    "variant",
    *FIELDS,
    "location",
    "purchase_basis",
    "text_encoding",
)
ROW_FIELDS = set(COLUMNS) | {
    "group_id",
    "keep_unknown",
    "included",
    "duplicate_decision",
    "literal_text",
    "first_edition_selected",
}
DEFAULT_FIELDS = {
    "action",
    "game",
    "set_id",
    "set",
    "language",
    "quantity",
    "edition",
    "finish",
    "variant",
    *FIELDS,
    "location",
    "purchase_basis",
}


def positive(value):
    if type(value) is int:
        value = str(value)
    if not isinstance(value, str) or not _ascii_integer(value):
        raise ValueError("Use a whole number from 1 to 2,000")
    significant = value.lstrip("0") or "0"
    # Bound conversion before int(): an untrusted quantity can contain many digits.
    if len(significant) > len(str(LIMIT)) or not 1 <= int(significant) <= LIMIT:
        raise ValueError("Use a whole number from 1 to 2,000")
    return int(significant)


def parse_csv(text):
    if not isinstance(text, str) or len(text.encode("utf-8")) > MAX_BYTES:
        raise ValueError("CSV must be UTF-8 and at most 1.5 MB")
    try:
        reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff"), newline=""), strict=True)
        headers = reader.fieldnames
        if not headers or len(headers) != len(set(headers)) or set(headers) - set(COLUMNS):
            raise ValueError("Use unique supported template columns")
        if not {"schema", "row_id", "action"} <= set(headers):
            raise ValueError("CSV requires schema, row_id and action columns")
        rows = []
        for row in reader:
            if len(rows) == LIMIT:
                raise ValueError("At most 2,000 source rows; create a separate explicit batch")
            if None in row or any(v is None for v in row.values()):
                raise ValueError("CSV row has a different number of cells from its header")
            if row["schema"] != SCHEMA:
                raise ValueError("Use schema dex-onboarding-v1")
            encoding = row.pop("text_encoding", "")
            if encoding not in ("", "json-text-v1"):
                raise ValueError("Unsupported text encoding")
            if encoding:
                row["literal_text"] = []
                for k in ("notes", "location", "name", "certificate", "grading_company", "grade"):
                    if row.get(k):
                        decoded = json.loads(row[k])
                        if not isinstance(decoded, str):
                            raise ValueError("Encoded text must be a JSON string")
                        row[k] = decoded
                        row["literal_text"].append(k)
            elif any(v.lstrip().startswith(("=", "+", "-", "@")) for v in row.values()):
                raise ValueError("Formula-leading text requires the safe template encoding")
            rows.append(row)
        return rows
    except (csv.Error, json.JSONDecodeError):
        raise ValueError("Malformed CSV or encoded text; check quoting and template format") from None


def template():
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=COLUMNS)
    writer.writeheader()
    return stream.getvalue()


def export_rows(rows):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=COLUMNS)
    writer.writeheader()
    for raw in rows:
        row = {k: raw.get(k, "") for k in COLUMNS}
        row.update(schema=SCHEMA, text_encoding="json-text-v1")
        for key in ("notes", "location", "name", "certificate", "grading_company", "grade"):
            if row[key]:
                row[key] = json.dumps(row[key], ensure_ascii=False)
        writer.writerow(row)
    return stream.getvalue()


def _ascii_integer(value):
    return bool(value) and value.isascii() and value.isdecimal()


def _paste_token(token):
    """Read one token in a single pass, without backtracking on pasted text."""
    if token.startswith('"'):
        end = token.find('"', 1)
        if end <= 1 or "\r" in token[1:end]:
            raise ValueError("Use literal numbers or ascending integer ranges: 1-3 x2, 8")
        number, quoted = token[1:end], True
        offset = end + 1
    else:
        offset = 0
        while offset < len(token) and not token[offset].isspace() and token[offset] not in '"x':
            offset += 1
        if not offset:
            raise ValueError("Use literal numbers or ascending integer ranges: 1-3 x2, 8")
        number, quoted = token[:offset], False
    while offset < len(token) and token[offset].isspace():
        offset += 1
    if offset == len(token):
        return number, None, quoted
    if token[offset] != "x":
        raise ValueError("Use literal numbers or ascending integer ranges: 1-3 x2, 8")
    offset += 1
    while offset < len(token) and token[offset].isspace():
        offset += 1
    quantity = token[offset:]
    if quantity != "unknown" and not _ascii_integer(quantity):
        raise ValueError("Use literal numbers or ascending integer ranges: 1-3 x2, 8")
    return number, quantity, quoted


def parse_paste(text, defaults):
    if not isinstance(text, str) or len(text.encode()) > MAX_BYTES:
        raise ValueError("Paste is too large")
    rows = []
    # Quotes force literal numbers; delimiters within quotes are not number syntax.
    tokens = text.replace(";", ",").replace("\n", ",").split(",")
    if len(tokens) > LIMIT:
        raise ValueError("At most 2,000 source tokens")
    occurrences = {}
    for token in tokens:
        token = token.strip()
        if not token:
            if len(tokens) == 1:
                return []
            raise ValueError("Empty number token; use 1-3 x2, 8, 10 x3")
        number, quantity, quoted = _paste_token(token)
        action = defaults.get("action", "add_copies")
        if action == "mark_owned" and quantity is not None:
            raise ValueError("Mark owned does not accept quantities")
        if action == "set_total" and quantity is None:
            raise ValueError("Record totals requires xN or xunknown on every token")
        if quantity == "unknown" and action != "set_total":
            raise ValueError("Unknown is only valid for a total")
        if quantity and quantity != "unknown":
            positive(quantity)
        numbers = [number]
        if not quoted and "-" in number:
            start_text, _, end_text = number.partition("-")
            if not _ascii_integer(start_text) or not _ascii_integer(end_text):
                raise ValueError("Only ascending ASCII integer ranges; quote hyphenated literal numbers")
            if max(len(start_text), len(end_text)) > _MAX_RANGE_DIGITS:
                raise ValueError("Integer range endpoints are too long")
            try:
                start, end = int(start_text), int(end_text)
            except ValueError:
                raise ValueError("Integer range endpoints are too long") from None
            if start > end:
                raise ValueError("Only ascending ASCII integer ranges; quote hyphenated literal numbers")
            if end - start + len(rows) + 1 > LIMIT:
                raise ValueError("Range exceeds 2,000 normalized rows")
            width = len(start_text) if start_text.startswith("0") else 0
            numbers = [str(n).zfill(width) for n in range(start, end + 1)]
        for n in numbers:
            occurrences[n] = occurrences.get(n, 0) + 1
            row = dict(row_id=f"paste-{digest(n.encode())[:24]}-{occurrences[n]}", number=n)
            if quantity is not None:
                row["total" if action == "set_total" else "quantity"] = quantity
            rows.append(row)
        if len(rows) > LIMIT:
            raise ValueError("At most 2,000 normalized rows")
    return rows


def envelope(raw):
    if not isinstance(raw, dict) or set(raw) - {"schema", "rows", "defaults", "lot", "source", "text"}:
        raise ValueError("Unsupported draft fields")
    if raw.get("schema", SCHEMA) != SCHEMA:
        raise ValueError("Unsupported onboarding schema")
    defaults = raw.get("defaults", {})
    if not isinstance(defaults, dict) or set(defaults) - DEFAULT_FIELDS:
        raise ValueError("Unsupported batch defaults")
    if any(v is not None and not isinstance(v, (str, int)) for v in defaults.values()):
        raise ValueError("Defaults must be text or null")
    source = raw.get("source", "checklist")
    if source not in {"checklist", "paste", "csv"}:
        raise ValueError("Choose checklist, paste or CSV")
    rows = (
        parse_csv(raw.get("text"))
        if source == "csv"
        else parse_paste(raw.get("text"), defaults)
        if source == "paste"
        else raw.get("rows", [])
    )
    if not isinstance(rows, list) or len(rows) > LIMIT:
        raise ValueError("At most 2,000 normalized rows")
    ids = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) - ROW_FIELDS:
            raise ValueError("Unsupported row fields")
        key = row.get("row_id")
        if not isinstance(key, str) or not 1 <= len(key) <= 200 or key in ids:
            raise ValueError("Use unique stable row IDs of 1–200 characters")
        ids.add(key)
        literals = row.get("literal_text", [])
        if not isinstance(literals, list) or any(
            k not in {"notes", "location", "name", "certificate", "grading_company", "grade"}
            for k in literals
        ):
            raise ValueError("Unsupported literal text fields")
        for field, value in list(row.items()):
            if isinstance(value, str) and field not in {"notes", "location", "certificate", "name", "row_id"}:
                row[field] = value.strip()
    lot = raw.get("lot", {})
    if not isinstance(lot, dict) or set(lot) - {"lot_amount", "lot_currency", "lot_date"}:
        raise ValueError("Unsupported whole-lot context")
    return dict(schema=SCHEMA, rows=rows, defaults=defaults, lot=lot)


def fingerprint(data):
    # Source order, whitespace and input adapter do not create another physical batch.
    normalized = json.loads(encode(data))
    normalized["rows"] = sorted(normalized["rows"], key=lambda r: r["row_id"])
    for row in normalized["rows"]:
        for key, value in list(row.items()):
            if isinstance(value, str) and key not in {"notes", "location", "certificate", "name"}:
                row[key] = value.strip()
        for key in ("schema", "text_encoding"):
            row.pop(key, None)
        for key in list(row):
            if row[key] == "" or (key == "literal_text" and row[key] == []):
                row.pop(key)
    return digest(encode(normalized).encode())
