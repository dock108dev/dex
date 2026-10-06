"""Qualify real D6 packages on a fresh disposable collection state only."""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from prepare_d6 import DEST, ROOT, write
from rehearse_e3a import snapshot
from rehearse_m1 import run as prepare_m1


def run(root, output):
    prepare_m1(root, output)
    for name, path in [
        ("catalog-batch-input", DEST / "batch.json"),
        ("sealed-input", ROOT / "config/sealed/d6-20261005/package.json"),
        ("gym-input", DEST / "gym1.json"),
    ]:
        (output / (name + ".json")).write_bytes(path.read_bytes())
    from django.contrib.auth import get_user_model

    from pokemon_hunter.beta import (
        catalog_imports as cat,
    )
    from pokemon_hunter.beta import (
        catalog_pipeline as pipe,
    )
    from pokemon_hunter.beta import (
        collection,
        lookup,
        product_lookup,
        store,
    )
    from pokemon_hunter.beta import (
        sealed_catalog as sealed,
    )

    actor = store.principal(get_user_model().objects.get(username="admin").pk)
    pipe.initialize()
    retained = pipe.retained_batch()
    retained["mode"] = "atomic"
    op = pipe.preview(actor, retained)
    pipe.transition(actor, op["id"], "verify")
    pipe.transition(actor, op["id"], "publish")
    before = snapshot(root)
    write(output / "before.json", before)
    # Standalone correction includes every original Gym Heroes ID, including non-target records.
    gym = json.loads((DEST / "gym1.json").read_text())
    op = cat.preview(actor, gym)
    write(output / "gym-preview.json", op)
    cat.transition(actor, op["id"], "verify")
    cat.transition(actor, op["id"], "publish")
    gymid = op["id"]
    assert cat.preview(actor, gym)["id"] == gymid
    p = json.loads((ROOT / "config/sealed/d6-20261005/package.json").read_text())
    sealed.validate(p, sealed.records())
    op = sealed.preview(actor, p)
    write(output / "sealed-preview.json", dict(id=op["id"], state=op["state"], review=sealed.review(op)))
    sealed.transition(actor, op["id"], "verify")
    sealed.transition(actor, op["id"], "publish")
    sealedid = op["id"]
    assert sealed.preview(actor, p)["id"] == sealedid
    observation = sealed.records()["observations"][p["observations"][0]["id"]]
    assert observation["checked_at"] == p["observations"][0]["checked_at"]
    write(
        output / "sealed-publication.json",
        dict(
            id=sealedid,
            state=sealed.get(actor, sealedid)["state"],
            review=sealed.review(sealed.get(actor, sealedid)),
        ),
    )
    batch = json.loads((DEST / "batch.json").read_text())
    pipe.Batch.model_validate(batch)
    for a in batch["sets"]:
        cat.validate(a["package"])
    op = pipe.preview(actor, batch)
    write(output / "catalog-preview.json", op)
    assert op["state"] == "preview", op
    pipe.transition(actor, op["id"], "verify")
    while pipe.get(actor, op["id"])["state"] != "published":
        pipe.transition(actor, op["id"], "publish")
    write(output / "catalog-publication.json", pipe.get(actor, op["id"]))
    batchid = op["id"]
    assert pipe.preview(actor, batch)["id"] == batchid
    write(output / "coverage.json", pipe.coverage(actor))
    write(
        output / "product-coverage.json",
        product_lookup.coverage(sealed.records(), datetime.now(UTC), collection.catalog(actor)),
    )
    for dex in [3, 123, 134, 135, 196, 197, 230, 251]:
        c = lookup.project(actor, dict(scope="all", targets=str(dex)))
        write(output / f"lookup-{dex}.json", c)
    ctx = lookup.project(actor, dict(scope="missing"))
    assert ctx["progress"]["satisfied"] == 161 and len(ctx["missing"]) == 90
    assert sum(r["pokemon_dex"] <= 151 for r in ctx["missing"]) == 14
    after = snapshot(root)
    changed = {
        "printings",
        "catalog_sets",
        "catalog_heads",
        "external_mappings",
        "catalog_aliases",
        "catalog_imports",
        "catalog_audit",
        "catalog_batches",
        "collection_generations",
        "sqlite_sequence",
    }
    protected = [t for t in before["rows"] if t not in changed and not t.startswith("sealed_")]
    for table in protected:
        assert before["rows"][table] == after["rows"][table], table
    assert before["photos"] == after["photos"]
    write(
        output / "preservation.json",
        dict(
            protected_tables=protected,
            photos_identical=True,
            owned=161,
            kanto_owned=137,
            missing=90,
            kanto_missing=14,
            owner_access=False,
            source="Fresh disposable synthetic collection with real D6 source packages",
            provider_calls=0,
        ),
    )
    # Roll back the delta, the nine-set checkpoint batch, and the canonical correction in reverse order.
    pipe.transition(actor, batchid, "rollback")
    sealed.transition(actor, sealedid, "rollback")
    cat.transition(actor, gymid, "rollback")
    restored = snapshot(root)
    for table in protected:
        assert before["rows"][table] == restored["rows"][table], table
    write(
        output / "rollback.json",
        dict(
            sealed=sealed.get(actor, sealedid)["state"],
            batch=pipe.get(actor, batchid)["state"],
            gym=cat.get(actor, gymid)["state"],
            protected_identical=True,
        ),
    )
    # Republish through fresh reviewed versions, leaving this disposable state ready for browser verification.
    gym["version"] += "-browser"
    op = cat.preview(actor, gym)
    cat.transition(actor, op["id"], "verify")
    cat.transition(actor, op["id"], "publish")
    p["version"] += "-browser"
    for b in p["bridges"]:
        b["package"]["version"] += "-browser"
    op = sealed.preview(actor, p)
    sealed.transition(actor, op["id"], "verify")
    sealed.transition(actor, op["id"], "publish")
    batch["version"] += "-browser"
    for a in batch["sets"]:
        a["package"]["version"] += "-browser"
    op = pipe.preview(actor, batch)
    pipe.transition(actor, op["id"], "verify")
    while pipe.get(actor, op["id"])["state"] != "published":
        pipe.transition(actor, op["id"], "publish")
    write(
        output / "result.json",
        dict(
            real_data=True,
            disposable_collection=True,
            idempotency=True,
            correction=True,
            rollback=True,
            source_refs=True,
            observation_time_preserved=True,
            owned=161,
            kanto_owned=137,
            provider_calls=0,
        ),
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--root", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    a = p.parse_args()
    with (
        patch("httpx.Client.send", side_effect=AssertionError("No acquisition")),
        patch("urllib.request.urlopen", side_effect=AssertionError("No acquisition")),
    ):
        run(a.root, a.output)
