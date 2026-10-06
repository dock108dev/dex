"""Derive full unknown-physical-attribute bridge from locked D1d retained bytes."""

import argparse
import copy
import json
from pathlib import Path

from prepare_d1d import build

from pokemon_hunter.beta import sealed_catalog

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "config/sealed/2026-10-05-det1-e1c/package.json"


def run(check=False):
    build(check=True)
    p = copy.deepcopy(json.loads((ROOT / "evidence/d1d-20261005/rejected-bridge-input.json").read_text()))
    p["version"] = "2026-10-05-det1-e1c-v1"
    p["provider"] = "reviewed-e1c"
    bridge = p["bridges"][0]["package"]
    bridge["version"] = p["version"]
    for c in bridge["cards"]:
        c["edition"] = None
        assert c["finish"] is None
    sealed_catalog.validate(p)
    content = json.dumps(p, indent=2, ensure_ascii=False) + "\n"
    if check:
        assert DEST.read_text() == content
    else:
        DEST.parent.mkdir(parents=True, exist_ok=True)
        DEST.write_text(content)
    print("Locked bytes: 18 canonical identities, unknown edition/finish, 18 unknown relationships")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    run(parser.parse_args().check)
