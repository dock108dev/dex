"""E6a labeled fixtures and exact integrated preservation, disposable state only."""

import argparse
import json
import uuid
from pathlib import Path
from unittest.mock import patch

from rehearse_e3a import snapshot
from rehearse_e5a import write


def prepare(root, output):
    from pokemon_hunter.beta.cli import setup

    setup(root)
    from django.contrib.auth import get_user_model

    from pokemon_hunter.beta import collection, parity, refresh, store

    actor = store.principal(get_user_model().objects.get(username="admin").pk)
    goal = max(
        (g for g in collection.goals(actor) if g["kind"] == "original151"),
        key=lambda g: g["definition"]["lineage"]["number"],
    )
    printing = next(p for p in collection.catalog(actor) if p["id"] == "a4e2324d-e556-5dd8-b794-a34a82d36886")
    op = collection.preview(
        actor,
        "add",
        dict(
            printing_id=printing["id"],
            duplicate_policy="allow",
            attributes=dict(notes="E6a SYNTHETIC Bulbasaur ownership transition fixture"),
        ),
        str(uuid.uuid4()),
    )
    assert not op["plan"]["errors"]
    collection.confirm(actor, op["id"])
    copy = next(c for c in collection.copies(actor) if c["batch_id"] == op["id"])
    evidence = root / "parity-evidence"
    for name in ("hunt.json", "demo_hunts.json", "raw_values.json"):
        (evidence / name).write_bytes((Path("config") / name).read_bytes())
    with patch("pokemon_hunter.beta.ebay_hunts.search", side_effect=AssertionError("No acquisition")):
        hunt = parity.search(actor, dict(demo=True, goal_id=goal["id"], intent="missing"))
    refresh.initialize()
    from pokemon_hunter.beta import sealed_catalog

    product = next(iter(sealed_catalog.records()["products"]))
    queued = refresh.start(actor, product, ["unknown"])
    write(
        output,
        "fixtures",
        dict(
            evidence_class="synthetic ownership and sample eBay; retained Target unchanged",
            copy_id=copy["id"],
            printing_id=printing["id"],
            goal_id=goal["id"],
            hunt_batch=hunt["batch"],
            queued_run=queued,
            transition="ordinary UI remove synthetic Bulbasaur copy, active to removed",
        ),
    )
    write(output, "before", snapshot(root))


def verify(root, output):
    before = json.loads((output / "before.json").read_text())
    after = snapshot(root)
    fixtures = json.loads((output / "fixtures.json").read_text())
    allowed = {
        "owned_copies",
        "collection_operations",
        "collection_generations",
        "saved_pack_research",
        "auth_user",
        "django_session",
        "axes_accesslog",
        "axes_accessattempt",
        "axes_accessfailurelog",
        "sqlite_sequence",
    }
    changed = {t for t in before["rows"] if before["rows"][t] != after["rows"].get(t)}
    assert changed <= allowed, changed
    old = {r["id"]: r for r in before["rows"]["owned_copies"]}
    transition_owner = old[fixtures["copy_id"]]["user_id"]
    generations = [
        dict(r, value=r["value"] + (1 if r["user_id"] == transition_owner else 0))
        for r in before["rows"]["collection_generations"]
    ]
    assert after["rows"]["collection_generations"] == generations
    new = {r["id"]: r for r in after["rows"]["owned_copies"]}
    expected = dict(old[fixtures["copy_id"]], state="removed", revision=1)
    assert new == {**old, fixtures["copy_id"]: expected}
    for t in ("collection_operations", "saved_pack_research"):
        assert all(r in after["rows"][t] for r in before["rows"][t]), t
    for t in ("auth_user",):

        def strip(rows):
            return [{k: v for k, v in r.items() if k != "last_login"} for r in rows]

        assert strip(before["rows"][t]) == strip(after["rows"][t])
    oldseq = {r["name"]: r["seq"] for r in before["rows"].get("sqlite_sequence", [])}
    newseq = {r["name"]: r["seq"] for r in after["rows"].get("sqlite_sequence", [])}
    assert {k for k in oldseq.keys() | newseq.keys() if oldseq.get(k) != newseq.get(k)} <= {
        "axes_accesslog",
        "axes_accessattempt",
        "axes_accessfailurelog",
    }
    assert before["photos"] == after["photos"]
    calls = json.loads((output / "provider-calls.json").read_text())
    assert calls["calls"] == 0
    write(output, "after", after)
    write(
        output,
        "preservation",
        dict(
            protected_tables_unchanged=sorted(set(before["rows"]) - changed),
            changes_classified=sorted(changed),
            exact_ownership_transition=True,
            existing_saved_rows_identical=True,
            photo_bytes_identical=True,
            acquisition=calls,
        ),
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("phase", choices=["prepare", "verify"])
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    (prepare if a.phase == "prepare" else verify)(a.root, a.output)
