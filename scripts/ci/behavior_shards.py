"""Exhaustive module partitions for serial tests on independent CI runners."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHARDS = ("core", "shopping-discovery", "shopping-decisions", "shopping-journeys")


def shard_for(module: str) -> str:
    """Keep existing core order and distribute the new full-size Shopping suites."""
    match = re.fullmatch(r"test_shop(\d+)_.*", module)
    number = int(match[1]) if match else 0
    if number >= 16:
        return "shopping-journeys"
    if number >= 14:
        return "shopping-decisions"
    if number >= 12:
        return "shopping-discovery"
    return "core"


def modules(shard: str, root: Path = ROOT / "tests") -> list[Path]:
    if shard not in SHARDS:
        raise ValueError(f"Unknown behavior shard: {shard}")
    paths = [p for p in sorted(root.glob("test_*.py")) if p.is_file() and shard_for(p.stem) == shard]
    if not paths:
        raise ValueError(f"Behavior shard has no test modules: {shard}")
    return paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("shard", choices=SHARDS)
    parser.add_argument("pytest_args", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    paths = [str(p.relative_to(ROOT)) for p in modules(args.shard)]
    print(f"Behavior {args.shard}: {len(paths)} modules", flush=True)
    extra = args.pytest_args
    if extra[:1] == ["--"]:
        extra = extra[1:]
    return subprocess.call([sys.executable, "-m", "pytest", *paths, *extra], cwd=ROOT)


if __name__ == "__main__":
    sys.exit(main())
