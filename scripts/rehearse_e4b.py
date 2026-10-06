"""Fresh E4b copied-state setup; original v1 snapshot bytes and every table protected."""

import argparse
import hashlib
import json
from pathlib import Path

from rehearse_e3a import snapshot
from rehearse_e5a import run, write
from rehearse_e5a import verify as verify_base


def boundary(root, output):
    from pokemon_hunter.beta.cli import setup

    setup(root)
    from django.contrib.auth import get_user_model

    from pokemon_hunter.beta import collection, pack_research, store

    actor = store.principal(get_user_model().objects.get(username="admin").pk)
    goals = [g for g in collection.goals(actor) if g["kind"] == "original151"]
    successor = max(goals, key=lambda g: g["definition"]["lineage"]["number"])
    key = pack_research.save(
        actor, successor["id"], goal_version=successor["version"], research_name="Legacy E5a snapshot"
    )
    row = pack_research.one(actor, key)
    payload = json.loads(row["snapshot"])
    context = payload["context"]
    context.pop("offer_filters")
    for group in context["expansions"]:
        for product in group["products"]:
            product.pop("offer_total", None)
            for offer in product["offers"]:
                for field in ("representative", "eligibility", "price_comparable"):
                    offer.pop(field, None)
                for obs in offer["observations"]:
                    obs.pop("age", None)
                    obs.pop("time_quality", None)
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    collection.execute(
        "UPDATE saved_pack_research SET snapshot=%s,snapshot_sha256=%s WHERE id=%s",
        [raw, hashlib.sha256(raw.encode()).hexdigest(), key],
    )
    write(output, "legacy", dict(id=key, sha256=hashlib.sha256(raw.encode()).hexdigest()))
    write(output, "before", snapshot(root))


def verify(root, output):
    verify_base(root, output)
    before = json.loads((output / "before.json").read_text())
    after = snapshot(root)
    old = before["rows"]["saved_pack_research"]
    rows = {r["id"]: r for r in after["rows"]["saved_pack_research"]}
    assert all(rows.get(r["id"]) == r for r in old)
    auth_before = {
        r["id"]: {k: v for k, v in r.items() if k != "last_login"} for r in before["rows"]["auth_user"]
    }
    auth_after = {
        r["id"]: {k: v for k, v in r.items() if k != "last_login"} for r in after["rows"]["auth_user"]
    }
    assert auth_before == auth_after
    write(
        output,
        "saved-preservation",
        dict(
            existing_snapshot_rows_byte_identical=True,
            auth_only_last_login=True,
            existing=len(old),
            new=len(rows) - len(old),
        ),
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("phase", choices=["prepare", "boundary", "verify"])
    p.add_argument("--seed", type=Path)
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    if a.phase == "prepare":
        run(a.seed, a.root, a.output)
        boundary(a.root, a.output)
    elif a.phase == "boundary":
        boundary(a.root, a.output)
    else:
        verify(a.root, a.output)
