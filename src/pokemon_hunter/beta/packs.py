"""Read-only frozen-goal projection over reviewed public metadata; no acquisition."""

import json
from datetime import datetime, timedelta, timezone

from django.db import connection

from . import broad_goals, catalog_imports, collection, sealed_catalog, store


def money(value, currency):
    return "Unknown" if value is None else f"{currency} {value / 100:.2f}"


def project(actor, key, species="", expansion="", now=None):
    row = collection.one(actor, "goal", key)
    d = json.loads(row["definition"])
    result = dict(
        goal=dict(row, definition=d),
        supported=row["kind"] == "original151" and d.get("eligibility_policy") == broad_goals.POLICY,
        expansions=[],
        limitations=[],
    )
    if not result["supported"]:
        result["limitations"].append("Packs to open supports retained Original 151 broad goal versions only.")
        return result
    result["versions"] = []
    for version in store.rows(
        "SELECT id,name,definition FROM collection_goals WHERE user_id=%s", [actor.user_id]
    ):
        definition = json.loads(version["definition"])
        if definition.get("lineage", {}).get("root_id") == d["lineage"]["root_id"]:
            result["versions"].append(
                dict(id=version["id"], name=version["name"], number=definition["lineage"]["number"])
            )
    result["versions"].sort(key=lambda v: v["number"])
    available = {p["id"] for p in collection.catalog(actor)}
    progress = broad_goals.progress(d, collection.copies(actor), available)
    missing = [i for i in progress["progress"] if i["status"] != "owned"]
    selected = [i for i in missing if not species or str(i["pokemon_dex"]) == species]
    result.update(progress=progress, missing=missing, species=species, expansion=expansion)
    if species and not selected:
        result["limitations"].append("This species is not missing in the selected goal version.")
    if "sealed_bridges" not in connection.introspection.table_names():
        result["limitations"].append("Reviewed sealed publication coverage is unavailable.")
        return result
    records = sealed_catalog.records()
    # Resolve exact metadata from the selected review journals, never catalog heads.
    approved = {}
    for ref in d["catalog_references"]:
        journal = store.rows("SELECT * FROM catalog_imports WHERE id=%s", [ref["import_id"]])
        if not journal or journal[0]["package_hash"] != ref["package_sha256"]:
            result["limitations"].append("Selected catalog review unavailable: " + ref["name"])
            continue
        package = json.loads(journal[0]["package"])
        if (
            package["version"] != ref["version"]
            or journal[0]["set_id"] != ref["set_id"]
            or journal[0]["state"] not in {"published", "rolled-back"}
            or catalog_imports.fingerprint(package) != ref["package_sha256"]
        ):
            result["limitations"].append("Selected catalog reference no longer matches: " + ref["name"])
            continue
        _, rows = catalog_imports.rows_for(package)
        approved.update({p["id"]: (p, package["language"]) for p in rows})
    bridges = {b["catalog_id"]: b for b in store.rows("SELECT * FROM sealed_bridges")}
    members = {m["printing_id"]: m for m in records["memberships"].values()}
    groups = {}
    unmapped = 0
    for item in selected:
        for cid in item["printing_ids"]:
            bridge = bridges.get(cid)
            p = records["printings"].get(bridge["printing_id"]) if bridge else None
            original = approved.get(cid)
            if not p or not original:
                unmapped += 1
                continue
            frozen, language = original
            attrs = json.loads(frozen["attributes"])
            if (p["number"], p["language"], p["finish"], p["variant"], p["species_id"], p["category"]) != (
                frozen["collector_number"],
                language,
                frozen["finish"],
                frozen["variant"],
                f"ndex:{item['pokemon_dex']:04}",
                "pokemon",
            ):
                unmapped += 1
                continue
            ex = records["expansions"].get(p["expansion_id"])
            if not ex:
                unmapped += 1
                continue
            g = groups.setdefault(ex["id"], dict(expansion=ex, confirmed={}, uncertain=[], products=[]))
            m = members.get(p["id"])
            status = m["status"] if m else "unknown"
            detail = dict(
                p,
                catalog_id=cid,
                membership=status,
                frozen_name=attrs.get("name"),
                frozen_rarity=attrs.get("rarity"),
                currently_selectable=cid in available,
                descriptive_correction=p["name"] != attrs.get("name") or p["rarity"] != attrs.get("rarity"),
                sources=p["sources"] + (m["sources"] if m else []),
            )
            if status == "booster" and ex["medium"] == "physical":
                target = g["confirmed"].setdefault(
                    item["pokemon_dex"], dict(label=item["label"], dex=item["pokemon_dex"], printings=[])
                )
                target["printings"].append(detail)
            else:
                g["uncertain"].append(detail)
    result["unmapped_printings"] = unmapped
    now = now or datetime.now(timezone.utc)
    for eid, g in groups.items():
        g["species"] = list(g.pop("confirmed").values())
        g["count"] = len(g["species"])
        for product in records["products"].values():
            packs = [p for p in records["packs"].values() if p["product_id"] == product["id"]]
            relevant = [p for p in packs if p["expansion_id"] == eid]
            if not relevant:
                continue
            verified = product["contents"] != "unknown" and all(
                p["quantity"] is not None and p["expansion_id"] for p in packs
            )
            quantity = sum(p["quantity"] for p in relevant) if verified else None
            pr = dict(
                product,
                packs=packs,
                verified=verified,
                coverage=g["count"] if verified else None,
                quantity=quantity,
                offers=[],
                guaranteed=[],
            )
            pr["guaranteed"] = [
                dict(r, printing=records["printings"].get(r["printing_id"]))
                for r in records["guaranteed"].values()
                if r["product_id"] == product["id"]
            ]
            for offer in records["offers"].values():
                if offer["product_id"] != product["id"]:
                    continue
                observations = []
                for o in sorted(
                    records["observations"].values(), key=lambda x: x["checked_at"], reverse=True
                ):
                    if o["offer_id"] != offer["id"]:
                        continue
                    age = now - sealed_catalog.instant(o["checked_at"])
                    observations.append(
                        dict(
                            o,
                            fresh=timedelta(0) <= age <= timedelta(hours=24),
                            price=money(o["price_minor"], offer["currency"]),
                            shipping=money(o["shipping_minor"], offer["currency"]),
                            per_pack=money(o["price_minor"] / quantity, offer["currency"])
                            if quantity
                            and all(p["expansion_id"] == eid for p in packs)
                            and o["price_minor"] is not None
                            else None,
                        )
                    )
                pr["offers"].append(dict(offer, observations=observations))
            g["products"].append(pr)
    result["options"] = sorted(groups.values(), key=lambda g: (-g["count"], g["expansion"]["name"]))
    result["expansions"] = [
        g for g in result["options"] if not expansion or g["expansion"]["id"] == expansion
    ]
    result["coverage"] = list(records["coverage"].values())
    used = {s for g in groups.values() for i in g["species"] for p in i["printings"] for s in p["sources"]}
    used.update(s for g in groups.values() for p in g["products"] for s in p["sources"])
    result["sources"] = [records["sources"][s] for s in sorted(used) if s in records["sources"]]
    return result
