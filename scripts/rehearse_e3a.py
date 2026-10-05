"""Fresh synthetic copied-state E3a setup and read-only before/after verification."""

import argparse
import hashlib
import json
import shutil
import sqlite3
import uuid
from pathlib import Path


def snapshot(root):
    with sqlite3.connect(root / "inventory.db") as db:
        db.row_factory = sqlite3.Row
        tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        rows = {
            t: sorted(
                [dict(r) for r in db.execute(f'SELECT * FROM "{t}"')],
                key=lambda r: json.dumps(r, sort_keys=True, default=str),
            )
            for t in tables
        }
    files = {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in root.rglob("*")
        if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
    }
    return json.loads(json.dumps(dict(rows=rows, photos=files), default=str))


def prepare(seed, root, output):
    if not (seed / "SYNTHETIC_ONLY").is_file() or root.exists() or output.exists():
        raise ValueError("Fresh synthetic seed/copy/evidence paths required")
    shutil.copytree(seed, root)
    output.mkdir(parents=True, mode=0o700)
    from pokemon_hunter.beta.cli import setup

    setup(root)
    from django.contrib.auth import get_user_model

    from pokemon_hunter.beta import collection as inv
    from pokemon_hunter.beta import packs, store
    from pokemon_hunter.beta import sealed_catalog as cat

    actor = store.principal(get_user_model().objects.get(username="admin").pk)

    def apply(kind, request):
        op = inv.preview(actor, kind, request, str(uuid.uuid4()))
        inv.confirm(actor, op["id"])
        return op

    apply("goal", dict(name="Packs browser Original 151", goal_kind="original151"))
    first = next(g for g in inv.goals(actor) if g["kind"] == "original151")
    cat.initialize()
    project = Path(__file__).resolve().parents[1]
    for name in ("2026-10-04", "2026-10-04-151"):
        raw = json.loads((project / "config/sealed" / name / "package.json").read_text())
        op = cat.preview(actor, raw)
        cat.transition(actor, op["id"], "verify")
        cat.transition(actor, op["id"], "publish")
    apply(
        "goal_edit",
        dict(name=first["name"], goal_kind="original151", id=first["id"], revision=first["revision"]),
    )
    versions = [g for g in inv.goals(actor) if g["kind"] == "original151"]
    for g in versions:
        p = packs.project(actor, g["id"])
        (output / f"version-{g['definition']['lineage']['number']}.json").write_text(
            json.dumps(p, indent=2, default=str)
        )
    (output / "setup.json").write_text(
        json.dumps(
            dict(
                root=str(root),
                versions=[
                    dict(id=g["id"], version=g["version"], number=g["definition"]["lineage"]["number"])
                    for g in versions
                ],
            ),
            indent=2,
        )
    )
    (output / "before.json").write_text(json.dumps(snapshot(root), indent=2, default=str))


def verify(root, output):
    before = json.loads((output / "before.json").read_text())
    after = snapshot(root)
    protected = [
        "owned_copies",
        "collection_goals",
        "saved_hunts",
        "scan_jobs",
        "scan_photos",
        "binders",
        "sealed_observations",
    ]
    unchanged = {t: before["rows"].get(t) == after["rows"].get(t) for t in protected}
    assert all(unchanged.values()) and before["photos"] == after["photos"]
    report = dict(
        protected_tables=unchanged,
        photos_unchanged=True,
        provider_calls=json.loads((output / "provider-calls.json").read_text()),
        evidence_class="copied-state comparison; browser execution status reported separately",
    )
    assert report["provider_calls"]["calls"] == 0
    (output / "after.json").write_text(json.dumps(after, indent=2, default=str))
    (output / "preservation.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--seed", type=Path)
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--verify", action="store_true")
    a = p.parse_args()
    if a.verify:
        verify(a.root, a.output)
    else:
        prepare(a.seed, a.root, a.output)
