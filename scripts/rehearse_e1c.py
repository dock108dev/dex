"""Guarded, retained-byte full-set publication on fresh populated synthetic SQLite."""

import argparse
import copy
import hashlib
import json
import sqlite3
import uuid
from pathlib import Path
from unittest.mock import patch

from rehearse_e3a import snapshot as file_snapshot

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "evidence/e1c-20261005"
STATE = Path("/Users/michaelfuscoletti/dex-private/e1c-20261005/synthetic-r4")


def snapshot(root):
    value = file_snapshot(root)
    # Photos are normalized BLOBs in SQLite, not necessarily files on disk.
    with sqlite3.connect(root / "inventory.db") as db:
        for key, content in db.execute("SELECT id,content FROM scan_photos"):
            value["photos"]["scan_photos:" + key] = hashlib.sha256(content).hexdigest()
    return value


def write(name, value, private=False):
    dest = STATE if private else OUT
    (dest / (name + ".json")).write_text(json.dumps(value, indent=2, default=str) + "\n")


def compare(before, after, allowed):
    changed = {t for t in before["rows"] if before["rows"][t] != after["rows"].get(t)}
    assert changed <= allowed, changed - allowed
    assert before["photos"] == after["photos"]
    return dict(
        changed_tables=sorted(changed),
        identical_tables=sorted(set(before["rows"]) - changed),
        photo_bytes_identical=True,
        photos=before["photos"],
        table_comparisons={
            t: dict(
                before_rows=len(rows),
                after_rows=len(after["rows"].get(t, [])),
                before_sha256=hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest(),
                after_sha256=hashlib.sha256(
                    json.dumps(after["rows"].get(t, []), sort_keys=True).encode()
                ).hexdigest(),
                identical=t not in changed,
            )
            for t, rows in before["rows"].items()
        },
    )


def prepare():
    if STATE.exists() or (OUT / "publication.json").exists():
        raise ValueError("Fresh state required; never overwrite an earlier rehearsal")
    from pokemon_hunter.beta import synthetic

    synthetic.prepare(STATE)
    from django.contrib.auth import get_user_model
    from django.db import connection

    from pokemon_hunter.beta import catalog_imports as collection_catalog
    from pokemon_hunter.beta import collection as inv
    from pokemon_hunter.beta import pack_research, parity, store
    from pokemon_hunter.beta import sealed_catalog as cat

    cat.initialize()
    pack_research.initialize()
    actor = store.principal(get_user_model().objects.get(username="admin").pk)

    def apply(kind, data):
        op = inv.preview(actor, kind, data, str(uuid.uuid4()))
        assert not op["plan"]["errors"]
        inv.confirm(actor, op["id"])
        return op

    apply("binder", dict(name="E1c protected SYNTHETIC binder"))
    apply("goal", dict(name="E1c frozen Original 151", goal_kind="original151"))
    goal = next(g for g in inv.goals(actor) if g["kind"] == "original151")
    # Populate all preservation classes before the boundary, including saved research/hunts.
    evidence = STATE / "parity-evidence"
    for name in ("hunt.json", "demo_hunts.json", "raw_values.json"):
        (evidence / name).write_bytes((ROOT / "config" / name).read_bytes())
    parity.search(actor, dict(demo=True, goal_id=goal["id"], intent="missing"))
    pack_research.save(
        actor, goal["id"], research_name="E1c protected SYNTHETIC research", goal_version=goal["version"]
    )
    before = snapshot(STATE)
    for t in (
        "owned_copies",
        "saved_hunts",
        "saved_pack_research",
        "binders",
        "scan_jobs",
        "scan_photos",
        "collection_goals",
    ):
        assert before["rows"][t], "Unpopulated protection class: " + t
    assert any(r["reserved_usd"] for r in before["rows"]["scan_jobs"])
    assert before["photos"]
    write("before", before, private=True)
    with sqlite3.connect(STATE / "inventory.db") as src, sqlite3.connect(STATE / "before.sqlite3") as dest:
        src.backup(dest)
    # No schema change is necessary: nullable edition/finish already exist.
    with sqlite3.connect(STATE / "inventory.db") as db:
        collection_catalog.initialize(db)
        collection_catalog.initialize(db)
    cat.initialize()
    cat.initialize()
    assert snapshot(STATE) == before
    write(
        "migration",
        dict(
            schema_change_required=False,
            existing_null_storage=True,
            additive_initializers_repeatable=True,
            exact_rows_and_photos_preserved=True,
            backend="SQLite; PostgreSQL execution unqualified",
        ),
    )
    p = json.loads((ROOT / "config/sealed/2026-10-05-det1-e1c/package.json").read_text())
    op = cat.preview(actor, p)
    assert cat.preview(actor, p)["id"] == op["id"]
    assert op["baseline"]["bridges"][0]["impact"]["count"] == 18
    write("preview", cat.review(op))
    try:
        cat.transition(actor, op["id"], "publish")
    except ValueError:
        pass
    else:
        raise AssertionError("Publication without review accepted")
    cat.transition(actor, op["id"], "verify")
    cat.transition(actor, op["id"], "publish")
    assert cat.transition(actor, op["id"], "publish")["state"] == "published"
    published = snapshot(STATE)
    changed = copy.deepcopy(p)
    changed["version"] += "-conflict"
    changed["bridges"][0]["package"]["version"] += "-conflict"
    changed["bridges"][0]["package"]["cards"][0]["edition"] = "unlimited"
    try:
        cat.preview(actor, changed)
    except ValueError as exc:
        conflict = str(exc)
    else:
        raise AssertionError("Conflicting physical identity accepted")
    assert snapshot(STATE) == published
    cat.transition(actor, op["id"], "rollback")
    assert not any(r["expansion_id"] == "tcgdex:en:det1" for r in cat.records()["printings"].values())
    assert json.loads(inv.one(actor, "goal", goal["id"])["definition"]) == goal["definition"]
    write(
        "rollback",
        dict(
            state=cat.get(actor, op["id"])["state"],
            active_det1_printings=0,
            protected_goals_unchanged=True,
            archived_identity_retained=True,
        ),
    )
    # Restore exact identities through another reviewed sealed version.
    p["version"] += "-restore"
    p["bridges"][0]["package"]["version"] += "-restore"
    restored = cat.preview(actor, p)
    cat.transition(actor, restored["id"], "verify")
    cat.transition(actor, restored["id"], "publish")
    entries = [r for r in inv.catalog(actor) if r["set_name"] == "Detective Pikachu"]
    assert len(entries) == 18 and all(r["edition"] is None and r["finish"] is None for r in entries)
    assert all(r["unresolved_fields"] == ["edition", "finish"] for r in entries)
    frozen_after = inv.one(actor, "goal", goal["id"])
    assert json.loads(frozen_after["definition"]) == goal["definition"]
    successor = inv.preview(
        actor,
        "goal_edit",
        dict(id=goal["id"], revision=goal["revision"], name=goal["name"], goal_kind="original151"),
        str(uuid.uuid4()),
    )
    diff = successor["plan"]["goal_difference"]
    assert len(diff["added"]) == 13 and not diff["removed"]
    assert diff["progress_before"] == diff["progress_after"]
    assert len([g for g in inv.goals(actor) if g["kind"] == "original151"]) == 1
    write("successor-preview", successor)
    after = snapshot(STATE)
    allowed = {
        "catalog_sets",
        "printings",
        "catalog_heads",
        "catalog_aliases",
        "external_mappings",
        "catalog_imports",
        "catalog_audit",
        "catalog_requests",
        "collection_operations",
    }
    allowed |= {"sealed_" + k for k in cat.KINDS} | {"sealed_imports", "sealed_mappings", "sealed_bridges"}
    preservation = compare(before, after, allowed)
    assert before["rows"]["collection_goals"] == after["rows"]["collection_goals"]
    write("preservation", preservation)
    write("after-publication", after, private=True)
    write("browser-before", after, private=True)
    # Independently restore the copied pre-publication DB and compare every row/photo.
    connection.close()
    with (
        sqlite3.connect(STATE / "before.sqlite3") as src,
        sqlite3.connect(STATE / "restored.sqlite3") as dest,
    ):
        src.backup(dest)
        assert dest.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    current_name = connection.settings_dict["NAME"]
    connection.settings_dict["NAME"] = STATE / "restored.sqlite3"
    with connection.cursor() as cursor:
        restored_rows = {}
        for t in before["rows"]:
            cursor.execute(f'SELECT * FROM "{t}"')
            cols = [r[0] for r in cursor.description]
            restored_rows[t] = sorted(
                [dict(zip(cols, r)) for r in cursor.fetchall()],
                key=lambda r: json.dumps(r, sort_keys=True, default=str),
            )
    assert json.loads(json.dumps(restored_rows, default=str)) == before["rows"]
    connection.close()
    connection.settings_dict["NAME"] = current_name
    write(
        "publication",
        dict(
            evidence_class="fresh generated synthetic SQLite, retained real metadata",
            numbered_cards=18,
            canonical_species=18,
            higher_species_supported=[272, 755, 658, 289],
            edition=None,
            finish=None,
            unknown_memberships=18,
            explicit_verified_publication=True,
            idempotent=True,
            identity_conflict_rejected=conflict,
            publication_rollback=True,
            reviewed_restoration=True,
            copied_baseline_restoration_exact=True,
            frozen_goals_unchanged=True,
            successor_additions=13,
            other_five_excluded=True,
            catalog_only_completion_gain=0,
            successor_publication="pending ordinary browser review",
            root=str(STATE),
            goal_id=goal["id"],
        ),
    )
    print(
        "18 published / rollback / reviewed restoration; rows/photos preserved; 13-addition successor awaits browser review"
    )


def verify_browser():
    from pokemon_hunter.beta.cli import setup

    setup(STATE)
    from django.contrib.auth import get_user_model

    from pokemon_hunter.beta import broad_goals, packs, store
    from pokemon_hunter.beta import collection as inv

    actor = store.principal(get_user_model().objects.get(username="admin").pk)
    baseline = json.loads((STATE / "browser-before.json").read_text())
    after = snapshot(STATE)
    allowed = {
        "collection_goals",
        "collection_operations",
        "collection_generations",
        "auth_user",
        "django_session",
        "axes_accesslog",
        "axes_accessattempt",
        "axes_accessfailurelog",
        "sqlite_sequence",
    }
    result = compare(baseline, after, allowed)
    for t in ("collection_goals", "collection_operations"):
        assert all(r in after["rows"][t] for r in baseline["rows"][t])

    def without_login(rows):
        return [{k: v for k, v in r.items() if k != "last_login"} for r in rows]

    assert without_login(baseline["rows"]["auth_user"]) == without_login(after["rows"]["auth_user"])
    generations = [
        dict(r, value=r["value"] + (1 if r["user_id"] == actor.user_id else 0))
        for r in baseline["rows"]["collection_generations"]
    ]
    assert after["rows"]["collection_generations"] == generations
    oldseq = {r["name"]: r["seq"] for r in baseline["rows"].get("sqlite_sequence", [])}
    newseq = {r["name"]: r["seq"] for r in after["rows"].get("sqlite_sequence", [])}
    assert {k for k in oldseq.keys() | newseq.keys() if oldseq.get(k) != newseq.get(k)} <= {
        "axes_accesslog",
        "axes_accessattempt",
        "axes_accessfailurelog",
    }
    result["change_classes"] = dict(
        successor="one new goal, predecessor rows exact; one collection generation increment",
        journals="new reviewed successor operation; preexisting operations exact",
        browser="generated-account last login, session and access-log bookkeeping only",
    )
    versions = [g for g in inv.goals(actor) if g["kind"] == "original151"]
    assert len(versions) == 2
    old, new = sorted(versions, key=lambda g: g["definition"]["lineage"]["number"])
    assert (
        len(broad_goals.difference(old["definition"], new["definition"], inv.copies(actor), set())["added"])
        == 13
    )
    assert old["satisfied"] == new["satisfied"]
    context = packs.project(actor, new["id"])
    det = next(e for e in context["expansions"] if e["expansion"]["id"] == "tcgdex:en:det1")
    assert det["count"] == 0 and len(det["uncertain"]) == 13
    assert not det["products"]
    broad_goals.validate(new["definition"])
    calls = json.loads((OUT / "browser/provider-calls.json").read_text())
    assert calls["calls"] == 0
    write("browser-preservation", result)
    write("browser-after", after, private=True)
    write(
        "successor-publication",
        dict(
            reviewed=True,
            reopened=True,
            goal_id=new["id"],
            version=new["version"],
            original151_total=151,
            vintage_total=251,
            additions=13,
            other_five_excluded=True,
            catalog_only_completion_gain=0,
            confirmed_pack_species=0,
            uncertain_printings=13,
            unknown_full_set_relationships=18,
            acquisition_calls=0,
        ),
    )
    publication = json.loads((OUT / "publication.json").read_text())
    publication["successor_publication"] = "confirmed through ordinary browser review and reopened"
    publication["successor_evidence"] = "evidence/e1c-20261005/successor-publication.json"
    write("publication", publication)
    print("Reviewed successor reopened: 13 additions, 151 denominator; 0 confirmed Packs coverage")


def main(verify=False):
    OUT.mkdir(parents=True, exist_ok=True)
    calls = dict(calls=0)

    def denied(*args, **kwargs):
        calls["calls"] += 1
        write("acquisition-calls", calls)
        raise AssertionError("E1c acquisition prohibited")

    with (
        patch("httpx.Client.send", denied),
        patch("httpx.AsyncClient.send", denied),
        patch("urllib.request.urlopen", denied),
    ):
        (verify_browser if verify else prepare)()
    write("acquisition-calls", calls)
    assert calls["calls"] == 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-browser", action="store_true")
    parser.add_argument("--root", type=Path, default=STATE)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()
    STATE, OUT = args.root, args.output
    main(args.verify_browser)
