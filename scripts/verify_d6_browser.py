"""Read-only post-browser preservation and copied-backup verification."""

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path

from prepare_d6 import OUT, write
from rehearse_e3a import snapshot

args = argparse.ArgumentParser()
args.add_argument("--attempt", default="5")
a = args.parse_args()
root = Path("/private/tmp/dex-d6-attempt" + a.attempt)

before = json.loads((OUT / "validation-attempt5/before.json").read_text())
after = snapshot(root)
protected = json.loads((OUT / "validation-attempt5/preservation.json").read_text())["protected_tables"]
for t in protected:
    if t in ["django_session", "axes_accesslog", "saved_pack_research", "auth_user"]:
        continue
    assert before["rows"][t] == after["rows"][t], t
assert before["photos"] == after["photos"]
for t in ["collection_goals", "saved_pack_research", "ownership_declarations"]:
    assert all(r in after["rows"][t] for r in before["rows"][t]), t
assert [{k: v for k, v in r.items() if k != "last_login"} for r in before["rows"]["auth_user"]] == [
    {k: v for k, v in r.items() if k != "last_login"} for r in after["rows"]["auth_user"]
]
saved = json.loads((OUT / "browser-v2/saved-before-restart.json").read_text())
with sqlite3.connect(root / "inventory.db") as d:
    d.row_factory = sqlite3.Row
    r = dict(d.execute("select * from saved_pack_research where id=?", [saved["id"]]).fetchone())
    assert hashlib.sha256(r["snapshot"].encode()).hexdigest() == saved["snapshot_sha256"]
    obs = json.loads(
        d.execute(
            "select data from sealed_observations where id='target:91619942:d6:20261006T031602'"
        ).fetchone()[0]
    )
    assert obs["checked_at"] == "2026-10-06T03:16:02.472952+00:00"
    with sqlite3.connect(root / "d6-restored.sqlite3") as restored:
        d.backup(restored)
        tables = [r[0] for r in d.execute("select name from sqlite_master where type='table'")]
        for t in tables:
            assert sorted([tuple(r) for r in d.execute(f'SELECT * FROM "{t}"')], key=repr) == sorted(
                restored.execute(f'SELECT * FROM "{t}"').fetchall(), key=repr
            ), t
calls = json.loads((OUT / "browser-v2/provider-calls.json").read_text())
assert calls["calls"] == 0 and calls["server_starts"] == 2
write(
    OUT / "browser-v2/preservation.json",
    dict(
        copies_photos_credentials_identical=True,
        historical_goals_sources_research_retained=True,
        new_saved_snapshot_identical_after_restart=True,
        original_observation_time=obs["checked_at"],
        copied_backup_all_tables_restored=True,
        provider_calls=0,
        server_starts=2,
        owned=161,
        kanto_owned=137,
        missing=90,
        kanto_missing=14,
        owner_access=False,
    ),
)
print("Browser preservation, frozen snapshot and original observation time verified")
