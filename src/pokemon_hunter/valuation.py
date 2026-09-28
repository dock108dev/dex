"""Edition-matched guide estimates; preserve missing prices."""

import json
from datetime import date
from decimal import Decimal, InvalidOperation


def valuation(data, path, today=None):
    today = today or date.today()
    records = json.loads(path.read_text()) if path.exists() else []
    owned = {k: c for k, c in data["cards"].items() if c["owned"]}
    matched = {k: {} for k in owned}
    for row in records:
        key = row.get("card_id")
        grade = str(row.get("grade"))
        if key not in owned or grade not in ("raw", "7", "8", "9", "10"):
            continue
        card = owned[key]
        edition = "first_edition" if card["first_edition"] else "standard"
        if (
            row.get("edition") != edition
            or row.get("grader") not in ("Guide", "PSA")
            or row.get("currency") != "USD"
        ):
            continue
        if not row.get("source_url", "").startswith("https://") or not row.get("variant_verified"):
            continue
        try:
            observed = date.fromisoformat(row["as_of"])
            value = Decimal(str(row["value"]))
            if not value.is_finite() or value < 0 or not 0 <= (today - observed).days <= 30:
                continue
        except (KeyError, TypeError, ValueError, InvalidOperation):
            continue
        previous = matched[key].get(grade)
        if previous and previous["as_of"] >= row["as_of"]:
            continue
        matched[key][grade] = {
            "value": str(value.quantize(Decimal(".01"))),
            "as_of": row["as_of"],
            "source_url": row["source_url"],
            "edition": edition,
            "estimated": bool(row.get("estimated")),
            "basis": row.get("basis", "Price-guide estimate"),
        }
    scenarios = {}
    for grade in ("raw", "7", "8", "9", "10"):
        priced = [r[grade] for r in matched.values() if grade in r]
        subtotal = sum((Decimal(r["value"]) for r in priced), Decimal(0))
        scenarios[grade] = {
            "priced": len(priced),
            "estimated": sum(r["estimated"] for r in priced),
            "owned": len(owned),
            "subtotal": str(subtotal),
            "total": str(subtotal) if len(priced) == len(owned) else None,
        }
    return {"cards": matched, "scenarios": scenarios, "max_age_days": 30}
