import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from pokemon_hunter.inventory import OWNER_ID, connect, stable_id
from pokemon_hunter.migration import compare, import_snapshot, restore, snapshot_files


@pytest.fixture
def snapshot(tmp_path):
    root = tmp_path / "snapshot"
    (root / "config/catalog").mkdir(parents=True)
    (root / "data").mkdir()
    cards = {
        "a": dict(
            number="001/A",
            source_id="a",
            set_id="test",
            name="Normal",
            owned=True,
            first_edition=True,
            dex_eligible=True,
            pokemon_dex=1,
            condition="LP",
            purchase_amount="12.30",
            purchase_currency="USD",
            notes="synthetic",
        ),
        "b": dict(
            number="X-02",
            source_id="b",
            set_id="test",
            name="Dark Example",
            owned=True,
            first_edition=False,
            dex_eligible=False,
            pokemon_dex=2,
        ),
        "c": dict(
            number="3/100",
            source_id="c",
            set_id="test",
            name="Missing",
            owned=False,
            first_edition=False,
            dex_eligible=True,
            pokemon_dex=152,
        ),
    }
    (root / "config/pokedex_251.json").write_text(json.dumps({"cards": cards}))
    (root / "config/catalog/sources.json").write_text(
        json.dumps({"commit": "synthetic", "sets": [{"id": "test", "name": "Test"}]})
    )
    (root / "config/settings.yaml").write_text("synthetic: true\n")
    with sqlite3.connect(root / "data/collection_hunts.db") as db:
        db.execute(
            "CREATE TABLE hunts(id INTEGER PRIMARY KEY,created TEXT,demo INTEGER,request TEXT,raw TEXT,coverage TEXT)"
        )
        db.executemany(
            "INSERT INTO hunts VALUES(?,?,?,?,?,?)",
            [
                (1, "date", 1, "{}", "[]", "{}"),
                (2, "date", 0, '{"budget":"15"}', '[{"synthetic":true}]', "{}"),
            ],
        )
    return root


def test_exact_repeat_restore_and_owner_scope(snapshot, tmp_path):
    target = tmp_path / "target.db"
    batch = import_snapshot(snapshot, target)
    report = compare(snapshot, target, batch)
    assert report["owned_copies"] == 2 and report["first_edition"] == 1
    assert report["vintage_251"] == {"kanto": 1, "johto": 0, "total": 1}
    with connect(target) as db:
        before = list(db.iterdump())
    assert import_snapshot(snapshot, target) == batch
    with connect(target) as db:
        assert list(db.iterdump()) == before
        db.execute("INSERT INTO users VALUES(?,NULL,NULL,?,?)", ("other", "member", "unprovisioned"))
        assert db.execute("SELECT count(*) FROM owned_copies WHERE user_id=?", ("other",)).fetchone()[0] == 0
        assert db.execute("SELECT auth_subject FROM users WHERE id=?", (OWNER_ID,)).fetchone()[0] is None
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("DELETE FROM printings")
    restored = tmp_path / "restored"
    restore(target, batch, restored)
    assert snapshot_files(restored) == snapshot_files(snapshot)
    with pytest.raises(FileExistsError):
        restore(target, batch, restored)


def test_changed_snapshot_and_corruption_are_not_silent(snapshot, tmp_path):
    target = tmp_path / "target.db"
    batch = import_snapshot(snapshot, target)
    with connect(target) as db:
        db.execute("UPDATE owned_copies SET notes='lost'")
    with pytest.raises(AssertionError):
        compare(snapshot, target, batch)
    (snapshot / "new-evidence.txt").write_text("changed")
    with pytest.raises(ValueError, match="reconciliation"):
        import_snapshot(snapshot, target)
    with pytest.raises(ValueError, match="outside"):
        import_snapshot(snapshot, snapshot / "bad.db")


def test_conflicting_source_mapping_visible(snapshot, tmp_path):
    p = snapshot / "config/pokedex_251.json"
    data = json.loads(p.read_text())
    data["cards"]["c"]["source_id"] = "b"
    p.write_text(json.dumps(data))
    target = tmp_path / "target.db"
    batch = import_snapshot(snapshot, target)
    assert compare(snapshot, target, batch)["identity_conflicts"] == 1


def test_generic_inventory_accepts_non_pokemon_number(tmp_path):
    with connect(tmp_path / "generic.db") as db:
        db.execute("INSERT INTO games VALUES('g','synthetic','Synthetic','1','[]','test')")
        db.execute("INSERT INTO catalog_sets VALUES('s','g','S',NULL,NULL,'[]','{}','1','partial')")
        db.execute("INSERT INTO printings VALUES('p','s','XY-001/PR',NULL,NULL,NULL,NULL,'[]','{}','{}')")
        db.execute("INSERT INTO users VALUES('u',NULL,NULL,'member','unprovisioned')")
        db.execute("INSERT INTO import_batches VALUES('b','u','hash','1','test')")
        for n in range(2):
            db.execute(
                "INSERT INTO owned_copies(id,user_id,printing_id,batch_id,first_edition_selected) VALUES(?,?,?,?,0)",
                (stable_id("copy", str(n)), "u", "p", "b"),
            )
        assert db.execute("SELECT count(*) FROM owned_copies").fetchone()[0] == 2


def test_snapshot_retains_wal(snapshot, tmp_path):
    path = snapshot / "data/wal.db"
    with sqlite3.connect(path) as db:
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("CREATE TABLE evidence(value TEXT)")
        db.execute("INSERT INTO evidence VALUES('pending-wal')")
        db.commit()
        out = tmp_path / "backup"
        subprocess.run(
            [
                sys.executable,
                str(Path(__file__).resolve().parents[1] / "scripts/snapshot_b0.py"),
                "--source",
                str(snapshot),
                "--output",
                str(out),
            ],
            check=True,
        )
        with sqlite3.connect(out / "snapshot/data/wal.db") as restored:
            assert restored.execute("SELECT value FROM evidence").fetchone()[0] == "pending-wal"
        assert not list((out / "snapshot").rglob("*-wal"))
