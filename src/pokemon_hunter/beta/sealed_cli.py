"""Offline E1 package validation and explicit operator review on a selected root."""

import argparse
import json
from pathlib import Path

from . import sealed_catalog as catalog


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path)
    parser.add_argument("--owner", default="admin")
    sub = parser.add_subparsers(dest="action", required=True)
    for name in ("validate", "preview"):
        sub.add_parser(name).add_argument("package", type=Path)
    sub.add_parser("migrate")
    sub.add_parser("report").add_argument("--json", action="store_true")
    for name in ("verify", "publish", "rollback"):
        sub.add_parser(name).add_argument("import_id")
    args = parser.parse_args()
    if args.action == "validate":
        p = catalog.validate(json.loads(args.package.read_text()))
        print(
            json.dumps(
                {
                    "valid": True,
                    "version": p["version"],
                    "sha256": catalog.cat.fingerprint(p),
                    "counts": {k: len(p[k]) for k in catalog.KINDS},
                },
                indent=2,
            )
        )
        return
    if args.root is None:
        parser.error("Choose an explicit prepared disposable --root")
    from .cli import setup

    setup(args.root)
    from django.contrib.auth import get_user_model

    from . import store

    actor = store.principal(get_user_model().objects.get(username=args.owner).pk)
    catalog.cat.admin(actor)
    if args.action == "migrate":
        catalog.initialize()
        print("Additive E1 schema initialized; existing identities preserved.")
    elif args.action == "report":
        result = catalog.report(actor)
        print(json.dumps(result, indent=2) if args.json else catalog.summary(result))
    else:
        op = (
            catalog.preview(actor, json.loads(args.package.read_text()))
            if args.action == "preview"
            else catalog.transition(actor, args.import_id, args.action)
        )
        print(
            json.dumps(
                {
                    **{k: op[k] for k in ("id", "state", "package_hash", "version")},
                    "review": catalog.review(op),
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
