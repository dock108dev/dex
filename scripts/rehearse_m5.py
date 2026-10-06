"""M5 exact copied-owner transition; never seeds accounts or inventory."""

import argparse
import hashlib
import json
import os
import uuid
from pathlib import Path
from unittest.mock import patch

PROJECT = Path(__file__).resolve().parents[1]
SOURCE_SHA = "511dec82f4434e1e90ae27ec634e85e546f7559d43cc61d4cabec310d4ccc1b2"


def write(path, value):
    path.write_text(json.dumps(value, indent=2, default=str) + "\n")


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def snapshot(root):
    from django.db import connection

    assert Path(connection.settings_dict["NAME"]).resolve() == (root / "inventory.db").resolve()
    with connection.cursor() as cursor:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cursor.fetchall()]
        result = {}
        for table in tables:
            cursor.execute(f'SELECT * FROM "{table}"')
            result[table] = sorted(cursor.fetchall(), key=repr)
        return result


def files(root):
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in root.rglob("*")
        if p.is_file()
        and p.name not in {"inventory.db", "inventory.db-wal", "inventory.db-shm", "inventory.db-journal"}
    }


def run(root, output, expected=None, reverse=False):
    from pokemon_hunter.beta.cli import setup

    setup(root)
    from pokemon_hunter.beta import catalog_imports as cat
    from pokemon_hunter.beta import catalog_pipeline as pipe
    from pokemon_hunter.beta import collection as inv
    from pokemon_hunter.beta import collection_goals as cg
    from pokemon_hunter.beta import lookup, pack_research, store
    from pokemon_hunter.beta import sealed_catalog as sealed

    output.mkdir(parents=True, exist_ok=False)
    before = snapshot(root)
    before_files = files(root)
    actor = store.principal(1)
    source = cg.latest(actor)
    assert source["source_sha256"] == SOURCE_SHA
    sealed.initialize()
    pipe.initialize()
    pack_research.initialize()

    def state():
        # Journal UUIDs differ across independent copies. Bind every active byte and
        # each journal's normalized package identity instead of substituting UUIDs.
        return digest(
            dict(
                records=sealed.records(False),
                states={
                    k: store.rows(f"SELECT id,publication_state FROM sealed_{k} ORDER BY id")
                    for k in sealed.KINDS
                },
                mappings=store.rows(
                    "SELECT * FROM sealed_mappings ORDER BY provider,language,kind,external_id"
                ),
                catalogs=store.rows("SELECT * FROM catalog_sets ORDER BY id"),
                printings=store.rows("SELECT * FROM printings ORDER BY id"),
                external=store.rows(
                    "SELECT * FROM external_mappings ORDER BY provider,entity_kind,external_id"
                ),
                heads=store.rows(
                    "SELECT h.set_id,i.package_hash FROM catalog_heads h JOIN catalog_imports i ON i.id=h.import_id ORDER BY h.set_id"
                ),
                sealed_journals=store.rows(
                    "SELECT package_hash,state FROM sealed_imports ORDER BY package_hash"
                ),
                batches=store.rows("SELECT package_hash,state FROM catalog_batches ORDER BY package_hash"),
            )
        )

    order = [
        dict(path=f"config/sealed/{n}/package.json", service="sealed")
        for n in ("2026-10-04", "2026-10-04-151")
    ]
    for step in json.loads((PROJECT / "evidence/d7-20261005/publication-order.json").read_text())["order"]:
        order.append(
            dict(
                step,
                service="catalog"
                if step["step"] == 2
                else "sealed"
                if step["step"] in (3, 5, 7)
                else "pipeline",
            )
        )
    order.append(dict(path="config/sealed/m4-20261006/inclusion-package.json", service="sealed"))
    operations = []
    services = {"sealed": sealed, "catalog": cat, "pipeline": pipe}
    for index, item in enumerate(order):
        raw = (PROJECT / item["path"]).read_bytes()
        sha = hashlib.sha256(raw).hexdigest()
        if "sha256" in item:
            assert sha == item["sha256"]
        pre = state()
        if expected:
            gate = expected["operations"][index]
            assert (item["path"], sha, pre) == (gate["path"], gate["source_sha256"], gate["before_hash"]), (
                "Stale exact rehearsal gate"
            )
        service = services[item["service"]]
        op = service.preview(actor, json.loads(raw))
        write(output / f"preview-{index:02}.json", op)
        assert op["state"] != "invalid", "Incompatible installed references"
        existing = op["state"] == "published"
        if op["state"] == "preview":
            service.transition(actor, op["id"], "verify")
        while service.get(actor, op["id"])["state"] in {"verified", "partial"}:
            service.transition(actor, op["id"], "publish")
        assert service.get(actor, op["id"])["state"] == "published"
        after = state()
        assert service.preview(actor, json.loads(raw))["id"] == op["id"]
        assert service.transition(actor, op["id"], "publish")["state"] == "published"
        assert state() == after
        if expected:
            assert after == gate["after_hash"], "Different rehearsed result"
        operations.append(
            dict(
                path=item["path"],
                service=item["service"],
                source_sha256=sha,
                before_hash=pre,
                after_hash=after,
                operation_id=op["id"],
                reused=existing,
            )
        )
        write(output / "operations.json", operations)
        print(item["path"], "reused" if existing else "published", flush=True)

    coverage = pipe.coverage(actor)
    assert coverage["totals"]["sets"] == 220
    historical = pipe.coverage(actor, profile="historical")
    unchanged = snapshot(root)
    assert pipe.coverage(actor) == coverage and snapshot(root) == unchanged
    write(output / "coverage.json", coverage)
    write(
        output / "projection-reversal.json",
        dict(current=220, historical=historical["totals"]["sets"], database_identical=True),
    )
    goal_operations = []
    for upper, kind in ((151, cg.KIND), (251, cg.TARGET_KIND)):
        matches = [
            g
            for g in inv.goals(actor)
            if g["kind"] == kind
            and g["definition"].get("collection_source") == cg.reference(source)
            and [i["pokemon_dex"] for i in g["definition"]["items"]] == list(range(1, upper + 1))
        ]
        if matches:
            goal = matches[0]
        else:
            req = dict(
                name=f"Original {upper} — owner collection", goal_kind=kind, collection_source_id=source["id"]
            )
            if upper == 251:
                req["targets"] = list(range(1, 252))
            op = inv.preview(actor, "goal", req, str(uuid.uuid4()))
            write(output / f"goal-{upper}-preview.json", op)
            assert not op["plan"]["errors"]
            inv.confirm(actor, op["id"])
            current = snapshot(root)
            inv.confirm(actor, op["id"])
            assert snapshot(root) == current
            goal = next(g for g in inv.goals(actor) if g["name"] == req["name"])
            goal_operations.append(op["id"])
        assert (goal["satisfied"], goal["total"]) == (137 if upper == 151 else 161, upper)
    context = lookup.project(actor, dict(targets="123,134,196,197"))
    assert context["progress"]["satisfied"] == 2
    crown = next(p for g in context["expansions"] for p in g["products"] if p.get("included_cards"))
    assert crown["included_cards"][0]["canonical_dex"] == 448 and crown["guaranteed_count"] == 0
    missing = lookup.project(actor, dict(scope="missing"))
    assert missing["progress"]["satisfied"] == 161 and len(missing["missing"]) == 90
    write(output / "lookup.json", context)
    write(output / "goals.json", inv.goals(actor))
    after = snapshot(root)
    allowed = {
        "catalog_sets",
        "printings",
        "external_mappings",
        "catalog_imports",
        "catalog_heads",
        "catalog_audit",
        "catalog_aliases",
        "catalog_batches",
        "collection_generations",
        "collection_operations",
        "collection_goals",
        "sqlite_sequence",
    }
    protected = [t for t in before if t not in allowed and not t.startswith("sealed_")]
    assert all(before[t] == after[t] for t in protected), "Changed protected owner rows"
    assert before_files == files(root), "Changed protected files"
    for t in ("catalog_sets", "printings"):
        assert {r[0] for r in before[t]} <= {r[0] for r in after[t]}, "Retired existing identity"
    assert all(r in after["external_mappings"] for r in before["external_mappings"])
    assert all(r in after["collection_goals"] for r in before["collection_goals"])
    receipt = dict(
        accepted=True,
        evidence_class="copied-owner" if not expected else "installed-owner",
        operations=operations,
        goal_operations=goal_operations,
        source_sha256=SOURCE_SHA,
        protected_tables=protected,
        protected_hashes={t: digest(before[t]) for t in protected},
        protected_files=before_files,
        before_counts={t: len(v) for t, v in before.items()},
        after_counts={t: len(v) for t, v in after.items()},
        goals=[dict(name=g["name"], satisfied=g["satisfied"], total=g["total"]) for g in inv.goals(actor)],
        original_catalog_printing_ids_preserved=True,
        original_external_mappings_preserved=True,
        acquisition_calls=0,
    )
    if reverse:
        for key in reversed(goal_operations):
            retained = snapshot(root)
            try:
                inv.undo(actor, key)
            except inv.Conflict:
                assert snapshot(root) == retained
            else:
                raise AssertionError("Frozen goal erasure unexpectedly allowed")
        active = sealed.records()
        sealed.transition(actor, operations[-1]["operation_id"], "rollback")
        assert sealed.records()["products"][crown["id"]] != active["products"][crown["id"]]
        for i in (8, 7, 6):
            services[operations[i]["service"]].transition(actor, operations[i]["operation_id"], "rollback")
        post = snapshot(root)
        assert all(before[t] == post[t] for t in protected) and before_files == files(root)
        receipt["supported_reversal"] = [
            "new goal erasure refused; restore qualified on fresh complete copy",
            "M4 inclusion",
            "D7 shopping",
            "D7 M2",
            "D7 sealed catalog",
        ]
    write(output / "receipt.json", receipt)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--expected", type=Path)
    ap.add_argument("--reverse", action="store_true")
    args = ap.parse_args()
    os.umask(0o077)
    with (
        patch("httpx.Client.send", side_effect=AssertionError("M5 acquisition forbidden")),
        patch("urllib.request.urlopen", side_effect=AssertionError("M5 acquisition forbidden")),
    ):
        run(
            args.root,
            args.output,
            json.loads(args.expected.read_text()) if args.expected else None,
            args.reverse,
        )
