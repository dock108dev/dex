"""Preservation evidence must detect data changes without changing its inputs."""

import importlib
import sqlite3
from pathlib import Path

import pytest


@pytest.fixture
def snapshot(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "scripts"))
    return importlib.import_module("qualification_state").persisted_snapshot


def test_snapshot_is_read_only_and_detects_database_and_protected_file_changes(snapshot, tmp_path):
    database = tmp_path / "inventory.db"
    with sqlite3.connect(database) as db:
        db.execute('CREATE TABLE "copy""evidence" (id INTEGER, photo BLOB)')
        db.execute('INSERT INTO "copy""evidence" VALUES (?,?)', (1, b"\x00\xff"))
    protected = tmp_path / "source.json"
    protected.write_text('{"known":false}\n')
    before_bytes = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    before = snapshot(tmp_path)
    assert snapshot(tmp_path) == before
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == before_bytes
    with sqlite3.connect(database) as db:
        db.execute('UPDATE "copy""evidence" SET photo=?', (b"changed",))
    after = snapshot(tmp_path)
    assert (
        after["databases"]["inventory.db"]["schema_sha256"]
        == before["databases"]["inventory.db"]["schema_sha256"]
    )
    assert after["databases"]["inventory.db"]["tables"] != before["databases"]["inventory.db"]["tables"]
    protected.write_text('{"known":true}\n')
    assert snapshot(tmp_path)["protected_files"] != before["protected_files"]


def test_snapshot_ignores_row_order_and_journal_files(snapshot, tmp_path):
    for name, values in [("first", [1, 2]), ("second", [2, 1])]:
        root = tmp_path / name
        root.mkdir()
        with sqlite3.connect(root / "inventory.db") as db:
            db.execute("CREATE TABLE copies (id INTEGER)")
            db.executemany("INSERT INTO copies VALUES (?)", [(value,) for value in values])
        (root / "unused.db-wal").write_bytes(b"transient")
        (root / "unused.db-shm").write_bytes(b"transient")
        (root / "unused.db-journal").write_bytes(b"transient")
    assert snapshot(tmp_path / "first") == snapshot(tmp_path / "second")
    assert snapshot(tmp_path / "first")["protected_files"] == {}


@pytest.mark.parametrize("name", ["verify_cx03", "verify_cx04", "verify_cx05", "verify_cx06", "verify_cx07"])
def test_existing_qualification_imports_keep_shared_snapshot(name, snapshot):
    assert importlib.import_module(name).persisted_snapshot is snapshot
