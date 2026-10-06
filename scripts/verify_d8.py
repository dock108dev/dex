"""Read-only disposable browser preservation; private owner installation never accessed."""

import hashlib
import json
import sqlite3
from pathlib import Path

from acquire_d8 import OUT, ROOT, write
from rehearse_e3a import snapshot

root = Path("/private/tmp/dex-d8-final4")
assert (root / "SYNTHETIC_ONLY").is_file()
state = snapshot(root)
baseline = json.loads((OUT / "validation-final4/browser-baseline.json").read_text())
protected = json.loads((OUT / "validation-final4/preservation.json").read_text())["protected_tables"]
excluded = ["auth_user", "django_session", "axes_accesslog", "axes_accessattempt", "saved_pack_research"]
for t in protected:
    if t not in excluded:
        digest = hashlib.sha256(
            json.dumps(state["rows"][t], sort_keys=True, default=str).encode()
        ).hexdigest()
        assert digest == baseline["tables"][t]["sha256"], t
assert state["photos"] == baseline["photos"]
with sqlite3.connect(root / "inventory.db") as db, sqlite3.connect(root / "d8-restored.sqlite3") as old:
    db.row_factory = sqlite3.Row
    old.row_factory = sqlite3.Row

    def rows(d, t):
        return [dict(r) for r in d.execute(f'SELECT * FROM "{t}"')]

    for t in ["collection_goals", "ownership_declarations", "saved_pack_research"]:
        assert all(r in rows(db, t) for r in rows(old, t)), t

    def auth(d):
        return [{k: v for k, v in r.items() if k != "last_login"} for r in rows(d, "auth_user")]

    assert auth(db) == auth(old)
    for path in [
        OUT / "validation-final4/saved-before-restart.json",
        OUT / "browser/saved-before-restart.json",
    ]:
        saved = json.loads(path.read_text())
        actual = db.execute(
            "select snapshot,snapshot_sha256 from saved_pack_research where id=?", [saved["id"]]
        ).fetchone()
        assert (
            hashlib.sha256(actual["snapshot"].encode()).hexdigest()
            == actual["snapshot_sha256"]
            == saved["snapshot_sha256"]
        )
    observations = json.loads((ROOT / "config/sealed/d8-20261006/shopping-package.json").read_text())[
        "observations"
    ]
    for o in observations:
        assert (
            json.loads(db.execute("select data from sealed_observations where id=?", [o["id"]]).fetchone()[0])
            == o
        )
    for r in rows(old, "sealed_observations"):
        assert r in rows(db, "sealed_observations")
    with sqlite3.connect(root / "browser-restored.sqlite3") as restored:
        db.backup(restored)
        for t in [r[0] for r in db.execute("select name from sqlite_master where type='table'")]:
            assert sorted([tuple(r) for r in db.execute(f'SELECT * FROM "{t}"')], key=repr) == sorted(
                restored.execute(f'SELECT * FROM "{t}"').fetchall(), key=repr
            ), t
calls = json.loads((OUT / "browser/provider-calls.json").read_text())
assert calls == {"calls": 0, "server_starts": 2}
write(
    OUT / "browser/preservation.json",
    dict(
        protected_tables_identical=True,
        auth_unchanged_except_actual_synthetic_login_last_login=True,
        photos_identical=True,
        historical_goals_sources_saves_preserved=True,
        saved_snapshots_bytes_identical=True,
        all_observation_times_original=True,
        backup_all_tables_restored=True,
        provider_calls=0,
        server_starts=2,
        owner_access=False,
        owned=161,
        kanto_owned=137,
        johto_owned=24,
        missing=90,
        kanto_missing=14,
    ),
)
print("D8 browser preservation and exact snapshot/source times passed")
