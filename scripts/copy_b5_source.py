"""Copy an isolated B4 database and scan settings for a disposable B5 migration."""

import argparse
import json
import os
import sqlite3
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--source-root", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
os.umask(0o077)
source = args.source_root.resolve(strict=True)
if not (source / "B4_ISOLATED").is_file():
    raise SystemExit("Only a prepared isolated B4 source is supported")
if args.output.resolve().is_relative_to(Path(__file__).resolve().parents[1]):
    raise SystemExit("Copied private evidence must stay outside the checkout")
args.output.mkdir(mode=0o700, parents=True, exist_ok=False)
with (
    sqlite3.connect(f"{(source / 'inventory.db').as_uri()}?mode=ro", uri=True) as old,
    sqlite3.connect(args.output / "review.copied.sqlite3") as new,
):
    old.backup(new)
config = source / "scan-config.json"
value = (
    config.read_text()
    if config.is_file()
    else json.dumps({"enabled": True, "mode": "manual", "ceiling_usd": 1.0, "user_ceiling_usd": 0.5})
)
(args.output / "review.copied.scan-config.json").write_text(value)
for file in args.output.iterdir():
    file.chmod(0o600)
print("Copied database and unchanged scan settings; source remains authoritative")
