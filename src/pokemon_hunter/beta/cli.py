"""Operator entry point. Never accepts passwords or tokens in arguments or prints them."""

import argparse
import getpass
import os
import secrets
import sqlite3
import sys
from pathlib import Path


def initialize(root, source=None, b2=False, parity=False):
    root = root.expanduser().absolute()
    project = Path(__file__).resolve().parents[3]
    if root.resolve().is_relative_to(project):
        raise ValueError("Choose a new private directory outside the checkout")
    root.mkdir(mode=0o700, parents=True, exist_ok=False)
    os.chmod(root, 0o700)
    (root / "B1_ISOLATED").write_text("Disposable B1 environment; not live authority\n")
    if source:
        source = source.resolve(strict=True)
        with (
            sqlite3.connect(f"{source.as_uri()}?mode=ro", uri=True) as old,
            sqlite3.connect(root / "inventory.db") as new,
        ):
            old.backup(new)
    from pokemon_hunter.inventory import connect

    with connect(root / "inventory.db") as db:
        db.execute("""CREATE TABLE b1_private_resources(
            id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
            kind TEXT NOT NULL CHECK(kind IN ('photos','scan_jobs','goals','request_evidence')),
            payload TEXT NOT NULL)""")
    if parity:
        b2 = True
    if b2:
        from .collection import initialize as initialize_collection

        with connect(root / "inventory.db") as db:
            initialize_collection(db)
        (root / "B2_ISOLATED").write_text("Disposable B2 environment; never owner-local\n")
    if parity:
        import json

        evidence = root / "parity-evidence"
        evidence.mkdir(mode=0o700)
        with sqlite3.connect(root / "inventory.db") as db:
            for filename in (
                "market_values.json",
                "raw_values.json",
                "hunt.json",
                "demo_hunts.json",
                "pokedex_251.json",
            ):
                row = db.execute(
                    "SELECT content FROM private_archives WHERE path=? ORDER BY rowid LIMIT 1",
                    ("config/" + filename,),
                ).fetchone()
                if not row:
                    continue
                value = json.loads(bytes(row[0]))
                if filename == "pokedex_251.json":
                    value = {
                        key: {k: v for k, v in species.items() if k in ("name", "dex_number", "generation")}
                        for key, species in value.get("pokedex", {}).items()
                    }
                    filename = "species.json"
                (evidence / filename).write_text(json.dumps(value))
        (root / "B2_PARITY_ISOLATED").write_text("Fresh B2 parity rehearsal; no live providers\n")
    (root / "secret.key").write_text(secrets.token_urlsafe(64))
    for name in ("secret.key", "inventory.db", "B1_ISOLATED"):
        os.chmod(root / name, 0o600)


def setup(root):
    os.umask(0o077)
    os.environ["DEX_B1_ROOT"] = str(root.resolve())
    os.environ["DJANGO_SETTINGS_MODULE"] = "pokemon_hunter.beta.settings"
    import django

    django.setup()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    sub = parser.add_subparsers(dest="action", required=True)
    init = sub.add_parser("init")
    init.add_argument("--copied-inventory", type=Path)
    init.add_argument("--b2", action="store_true", help="Enable B2 only in this new isolated root")
    init.add_argument("--parity", action="store_true", help="Fresh B2 parity root with copied local evidence")
    for command in ("bootstrap", "serve", "check", "enable-scans", "scan-worker", "enable-catalog"):
        sub.add_parser(command)
    for command in ("invite", "recovery", "revoke"):
        p = sub.add_parser(command)
        p.add_argument("username")
        if command != "revoke":
            p.add_argument("--link-file", type=Path, required=True)
    args = parser.parse_args()
    os.umask(0o077)
    if args.action == "init":
        initialize(args.root, args.copied_inventory, b2=args.b2, parity=args.parity)
    if os.environ.get("DEX_PROFILE") == "staging" and args.action not in {
        "bootstrap",
        "invite",
        "recovery",
        "revoke",
        "check",
    }:
        raise ValueError("Use the staging deployment operator for this action")
    setup(args.root)
    from django.conf import settings
    from django.contrib.auth import get_user_model
    from django.core.management import call_command

    from . import accounts

    if args.action == "init":
        call_command("migrate", verbosity=0)
        stage = "B2 parity" if args.parity else "B2" if args.b2 else "B1"
        print(f"Isolated {stage} database initialized. Provision an isolated account before inviting anyone.")
    elif args.action == "bootstrap":
        from pokemon_hunter.inventory import OWNER_ID

        from .store import rows

        existing = rows("SELECT auth_subject FROM users WHERE id=%s", [OWNER_ID])
        if existing and existing[0]["auth_subject"]:
            accounts.bootstrap(None)
            print("Owner already bound; identity and password unchanged.")
        else:
            if not sys.stdin.isatty():
                raise ValueError("Owner provisioning requires a private interactive terminal")
            password = getpass.getpass("Owner password (not echoed): ")
            if password != getpass.getpass("Repeat password: "):
                raise ValueError("Passwords differ")
            accounts.bootstrap(password)
            print("Owner bound to stable B0 identity in this isolated environment.")
    elif args.action in {"invite", "recovery"}:
        # Create output before mutation, refusing overwrite and keeping links out of logs.
        dest = args.link_file.expanduser().absolute()
        if not dest.parent.resolve().is_relative_to(args.root.resolve()):
            raise ValueError("Link file must be inside the private B1 directory")
        with dest.open("x", encoding="utf-8") as output:
            user = (
                accounts.invite(args.username)
                if args.action == "invite"
                else get_user_model().objects.get(username=args.username)
            )
            output.write(
                getattr(settings, "PUBLIC_ORIGIN", "http://127.0.0.1:8011")
                + accounts.issue_link(user, args.action)
                + "\n"
            )
        print("Private one-use link written. No message was sent. Expires in 30 minutes.")
    elif args.action == "revoke":
        accounts.revoke(get_user_model().objects.get(username=args.username))
        print("Account, sessions and outstanding links revoked.")
    elif args.action == "check":
        call_command("check")
    elif args.action == "enable-catalog":
        if not (args.root / "B3_ISOLATED").is_file():
            raise ValueError("Catalog expansion requires B3")
        from .catalog_imports import initialize as initialize_catalog

        with sqlite3.connect(args.root / "inventory.db") as db:
            initialize_catalog(db)
        (args.root / "B4_ISOLATED").write_text("B4 catalog expansion enabled; identities preserved\n")
        print("B4 enabled. Restart the server.")
    elif args.action == "enable-scans":
        if not (args.root / "B2_ISOLATED").is_file():
            raise ValueError("Scans require the B2 inventory")
        from .scans import initialize as initialize_scans

        with sqlite3.connect(args.root / "inventory.db") as db:
            initialize_scans(db)
        (args.root / "B3_ISOLATED").write_text("B3 photo entry enabled; original accounts preserved\n")
        print("B3 enabled. Restart serve; default is manual photo entry.")
    elif args.action == "scan-worker":
        from .scan_worker import run

        run()
    elif args.action == "serve":
        import uvicorn
        from django.core.asgi import get_asgi_application

        worker = None
        if (args.root / "B3_ISOLATED").is_file():
            import threading

            from .scan_worker import run

            stop = threading.Event()
            worker = threading.Thread(target=run, args=(stop,), daemon=True)
            worker.start()

        try:
            uvicorn.run(
                get_asgi_application(),
                host="127.0.0.1",
                port=8011,
                access_log=False,
                proxy_headers=False,
                log_level="warning",
            )
        finally:
            if worker is not None:
                stop.set()
                worker.join(timeout=5)


if __name__ == "__main__":
    main()
