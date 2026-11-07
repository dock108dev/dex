"""Read-only LV readiness: JSON metadata to stdout; no app setup or output writes."""

import argparse
import json
from pathlib import Path

from pokemon_hunter.beta.lot_value_readiness import project


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--version", type=int, choices=(1, 2, 3), default=3)
    args = parser.parse_args(argv)
    report = project(args.root, version=args.version)
    print(json.dumps(report, sort_keys=True, indent=2))
    return 0 if report["state"] != "unavailable" else 1


if __name__ == "__main__":
    raise SystemExit(main())
