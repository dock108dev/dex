"""Photo-only skip-existing policy and immutable reviewed addition report."""

from . import collection, copy_editions, effective_collection


def prepare(actor, rows, owned, catalog, result):
    current = effective_collection.project(actor)
    cards = {(r["set_name"], r["name"], r["number"]): r for r in current["cards"]}
    copies = {c["id"]: c for c in owned}
    seen = set()
    report = []
    # Prefer a reviewed first-edition observation when a new card repeats in one batch.
    ordered = sorted(rows, key=lambda r: not r.get("first_edition_selected", False))
    for row in ordered:
        entry = dict(
            row_id=row["row_id"],
            identity=row.get("identity"),
            url=row.get("url"),
            first_edition=False,
            status="excluded",
            detail="Not included",
        )
        report.append(entry)
        if row["errors"] or not row["included"] or row.get("skipped"):
            if row["errors"]:
                entry.update(status="needs_review", detail="Identity needs correction")
            continue
        identity = row["identity"]
        key = (identity["set_name"], identity["name"], identity["number"])
        card = cards[key]
        if key in seen:
            row["skipped"] = True
            entry.update(status="duplicate", detail="Repeated in this photo batch; no additional copy")
        elif card["present"]:
            row["skipped"] = True
            entry.update(status="already_owned", detail="Already in your collection; no additional copy")
            current_copies = [copies[cid] for cid in card["current_copy_ids"] if cid in copies]
            if any(c["first_edition_selected"] for c in current_copies):
                entry["first_edition"] = True
            elif row.get("first_edition_selected"):
                if len(current_copies) == 1 and current_copies[0]["printing_id"] in catalog:
                    before = collection.one(actor, "copy", current_copies[0]["id"])
                    after = copy_editions.select(before, catalog[before["printing_id"]], "first_edition")
                    result["updates"].append(dict(kind="copy", before=before, after=after))
                    entry.update(
                        status="edition_updated",
                        first_edition=True,
                        detail="First edition checked on the existing record; no copy added",
                    )
                else:
                    entry.update(
                        status="needs_review",
                        detail="Already owned; choose the existing physical record before checking first edition",
                    )
        else:
            entry.update(
                status="added", first_edition=bool(row.get("first_edition_selected")), detail="Add one card"
            )
        seen.add(key)
        row["photo_result"] = entry
    by_id = {r["row_id"]: r for r in report}
    result["photo_report"] = [by_id[r["row_id"]] for r in rows]
