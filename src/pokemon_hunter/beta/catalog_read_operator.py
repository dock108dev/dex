"""Explicit local maintenance. Never installs authority, reseeds, or contacts providers."""

import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument(
        "action",
        choices=("migrate", "prepare", "status", "activate", "discard", "repair-index", "repair-schema"),
    )
    parser.add_argument("--build")
    args = parser.parse_args()
    if not (args.root / "inventory.db").is_file():
        parser.error("An existing installation is required")
    from .cli import setup

    setup(args.root)
    from . import catalog_read_build as builds
    from .catalog_read_schema import migrate

    if args.action == "migrate":
        migrate()
        print("Catalog read schema installed; preparation remains explicit.")
    elif args.action == "repair-schema":
        from .catalog_read_schema import repair

        repair()
        print("Derived schema repaired; prepare and activate a current candidate next.")
    elif args.action == "repair-index":
        builds.repair_index()
        print("Search index repaired; prepare and activate a current candidate next.")
    elif args.action == "prepare":
        print(json.dumps(dict(build=builds.prepare(), activated=False)))
    elif args.action in {"activate", "discard"}:
        if not args.build:
            parser.error("--build is required")
        getattr(builds, args.action)(args.build)
        print("Catalog build action completed.")
    else:
        manifest, revision = builds.active()
        print(json.dumps(dict(build=manifest["id"], catalog_revision=revision, status=manifest["status"])))


if __name__ == "__main__":
    main()
