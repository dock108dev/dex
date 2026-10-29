"""Explicit local account representation lifecycle; no mutation replay or acquisition."""

import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--username")
    parser.add_argument("action", choices=("migrate", "prepare", "status", "discard", "repair-schema"))
    args = parser.parse_args()
    if not (args.root / "inventory.db").is_file():
        parser.error("An existing installation is required")
    from .cli import setup

    setup(args.root)
    from . import account_read_build as builds
    from . import account_read_schema as schema
    from . import store

    if args.action in {"migrate", "repair-schema"}:
        getattr(schema, "migrate" if args.action == "migrate" else "repair")()
        print("Account read schema ready; preparation remains explicit.")
        return
    if not args.username:
        parser.error("--username is required for account actions")
    rows = store.rows("SELECT id FROM auth_user WHERE username=%s", [args.username])
    if not rows:
        parser.error("Active account unavailable")
    actor = store.principal(rows[0]["id"])
    if args.action == "prepare":
        print(json.dumps(builds.prepare(actor)))
    elif args.action == "discard":
        schema.discard(actor)
        print("Disposable account representation removed; authority unchanged.")
    else:
        from .readiness import inspect

        status = inspect(actor)
        print(json.dumps(status))
        if not status["ready"]:
            raise SystemExit(1)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        from .diagnostics import failure

        failure("read_maintenance_failed", exc)
        print("Read maintenance failed; preserve authority and inspect sanitized diagnostics.")
        raise SystemExit(1) from None
