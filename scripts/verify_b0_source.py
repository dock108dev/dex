"""Verify private live source against backup; smoke-test only a restored copy."""

import argparse
import json
import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from pokemon_hunter.app import create_app
from pokemon_hunter.collection import read, totals
from pokemon_hunter.migration import digest

parser = argparse.ArgumentParser()
for name in ("source", "snapshot", "manifest", "restored", "report"):
    parser.add_argument("--" + name, type=Path, required=True)
args = parser.parse_args()
if args.source.resolve() == args.restored.resolve():
    raise ValueError("Smoke tests require a restored copy")
verified, databases = [], []
for row in json.loads(args.manifest.read_text()):
    p = args.source / row["path"]
    if row["kind"] == "sqlite-backup":
        with (
            sqlite3.connect(f"{p.resolve().as_uri()}?mode=ro", uri=True) as a,
            sqlite3.connect(f"{(args.snapshot / row['path']).resolve().as_uri()}?mode=ro", uri=True) as b,
        ):
            assert list(a.iterdump()) == list(b.iterdump()), row["path"]
        databases.append(row["path"])
    elif row["path"].startswith(("config/", "sources/", "data/", "web/")) or p.name.startswith(".env"):
        assert digest(p.read_bytes()) == row["sha256"], row["path"]
        verified.append(row["path"])
with TestClient(
    create_app(args.restored), base_url="http://127.0.0.1:8765", client=("127.0.0.1", 50000)
) as client:
    assert client.get("/").status_code == 200
    assert client.get("/api/collection").json()["totals"] == totals(
        read(args.source / "config/pokedex_251.json")
    )
    assert client.get("/api/export").json() == json.loads(
        (args.source / "config/pokedex_251.json").read_text()
    )
    hunts = client.get("/api/hunts").json()
    for hunt in hunts:
        response = client.get("/api/hunts/" + str(hunt["id"]))
        assert response.status_code == 200
        assert all("title" not in r and "cards" not in r for r in response.json()["results"])
args.report.write_text(
    json.dumps(
        {
            "hash_verified": verified,
            "databases_logically_equal": databases,
            "restored_app": "pass",
            "hunts_read": len(hunts),
        },
        indent=2,
    )
    + "\n"
)
print("Source preservation and restored-app checks passed")
