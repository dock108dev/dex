"""Operator entry point. Never accepts passwords or tokens in arguments or prints them."""

import argparse
import getpass
import os
import secrets
import sqlite3
import sys
from pathlib import Path


def initialize(root, source=None):
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
    for command in ("bootstrap", "serve", "check"):
        sub.add_parser(command)
    for command in ("invite", "recovery", "revoke"):
        p = sub.add_parser(command)
        p.add_argument("username")
        if command != "revoke":
            p.add_argument("--link-file", type=Path, required=True)
    args = parser.parse_args()
    os.umask(0o077)
    if args.action == "init":
        initialize(args.root, args.copied_inventory)
    setup(args.root)
    from django.contrib.auth import get_user_model
    from django.core.management import call_command

    from . import accounts

    if args.action == "init":
        call_command("migrate", verbosity=0)
        print("Isolated B1 database initialized. Provision owner before inviting anyone.")
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
            output.write("http://127.0.0.1:8011" + accounts.issue_link(user, args.action) + "\n")
        print("Private one-use link written. No message was sent. Expires in 30 minutes.")
    elif args.action == "revoke":
        accounts.revoke(get_user_model().objects.get(username=args.username))
        print("Account, sessions and outstanding links revoked.")
    elif args.action == "check":
        call_command("check")
    elif args.action == "serve":
        import uvicorn
        from django.core.asgi import get_asgi_application

        uvicorn.run(
            get_asgi_application(),
            host="127.0.0.1",
            port=8011,
            access_log=False,
            proxy_headers=False,
            log_level="warning",
        )


if __name__ == "__main__":
    main()
