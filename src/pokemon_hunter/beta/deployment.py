"""Small staging operator: copied migration, consistent backup, empty-target restore."""

import argparse
import hashlib
import json
import os
import re
import sqlite3
from pathlib import Path


def setup():
    os.environ["DEX_PROFILE"] = "staging"
    os.environ["DJANGO_SETTINGS_MODULE"] = "pokemon_hunter.beta.settings"
    import django

    django.setup()


def tables():
    from django.db import connection

    return connection.introspection.table_names()


def migrate_copy(source):
    """Only a caller-created SQLite backup is accepted; never reads a live collection."""
    from django.core.management import call_command
    from django.db import connection, transaction

    if tables():
        raise ValueError("Migration requires an empty disposable PostgreSQL database")
    if not source.name.endswith(".copied.sqlite3"):
        raise ValueError("Supply an explicit .copied.sqlite3 backup, not a live database")
    scan_config_path = source.with_suffix(".scan-config.json")
    if not scan_config_path.is_file():
        raise ValueError(
            "Copied database requires its .scan-config.json sidecar; never reset spending configuration"
        )
    scan_config = json.loads(scan_config_path.read_text())
    if scan_config.get("mode") not in {"manual", "fixture", "openai"} or not isinstance(
        scan_config.get("enabled"), bool
    ):
        raise ValueError("Invalid copied scan configuration")
    for key, limit in (("ceiling_usd", 1.0), ("user_ceiling_usd", 0.5)):
        if not 0 <= float(scan_config[key]) <= limit:
            raise ValueError("Copied configuration exceeds current spending ceilings")
    with sqlite3.connect(f"{source.resolve().as_uri()}?mode=ro", uri=True) as old:
        schema = old.execute(
            "SELECT name,sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY rowid"
        ).fetchall()
        if not {"scan_jobs", "catalog_imports", "auth_user"} <= {t[0] for t in schema}:
            raise ValueError("A complete B4 copied database is required")
        call_command("migrate", verbosity=0)
        existing = set(tables())
        with transaction.atomic(), connection.cursor() as c:
            c.execute("SET CONSTRAINTS ALL DEFERRED")
            for name, ddl in schema:
                if name in existing:
                    continue
                ddl = re.sub(r"\bBLOB\b", "BYTEA", ddl, flags=re.I)
                ddl = re.sub(r"\bREAL\b", "DOUBLE PRECISION", ddl, flags=re.I)
                ddl = re.sub(r"\bINTEGER PRIMARY KEY\b", "BIGSERIAL PRIMARY KEY", ddl, flags=re.I)
                ddl = re.sub(
                    r"REFERENCES (\w+\([^)]*\))",
                    r"REFERENCES \1 DEFERRABLE INITIALLY DEFERRED",
                    ddl,
                    flags=re.I,
                )
                c.execute(ddl)
            # Django migrations seed permissions/content types. Copy their original stable IDs.
            for name in reversed([n for n, _ in schema if n in existing]):
                c.execute(f'DELETE FROM "{name}"')
            for name, _ in schema:
                info = old.execute(f'PRAGMA table_info("{name}")').fetchall()
                columns = [r[1] for r in info]
                c.execute(
                    "SELECT column_name,data_type FROM information_schema.columns WHERE table_schema='public' AND table_name=%s",
                    [name],
                )
                types = dict(c.fetchall())
                data = old.execute(f'SELECT * FROM "{name}"').fetchall()
                values = [
                    tuple(
                        bool(v) if types[k] == "boolean" and v is not None else v
                        for k, v in zip(columns, row, strict=True)
                    )
                    for row in data
                ]
                if values:
                    names = ",".join('"' + k + '"' for k in columns)
                    c.executemany(
                        f'INSERT INTO "{name}" ({names}) VALUES ({",".join(["%s"] * len(columns))})', values
                    )
                for col in columns:
                    c.execute("SELECT pg_get_serial_sequence(%s,%s)", [name, col])
                    seq = c.fetchone()[0]
                    if seq:
                        c.execute(
                            f'SELECT setval(%s,COALESCE(MAX("{col}"),1),MAX("{col}") IS NOT NULL) FROM "{name}"',
                            [seq],
                        )
                c.execute(
                    f'SELECT {names if values else ",".join(chr(34) + k + chr(34) for k in columns)} FROM "{name}"'
                )
                restored = c.fetchall()

                def canonical(row):
                    from datetime import datetime, timezone

                    encoded = []
                    for col, value in zip(columns, row, strict=True):
                        if value is not None and types[col].startswith("timestamp"):
                            dt = datetime.fromisoformat(value) if isinstance(value, str) else value
                            value = (
                                dt.replace(tzinfo=timezone.utc).isoformat()
                                if dt.tzinfo is None
                                else dt.astimezone(timezone.utc).isoformat()
                            )
                        if isinstance(value, (bytes, memoryview)):
                            value = bytes(value).hex()
                        encoded.append(value)
                    return json.dumps(encoded, default=str)

                if sorted(map(canonical, values)) != sorted(map(canonical, restored)):
                    raise ValueError("Copied migration value mismatch in " + name)
    initialize()
    with connection.cursor() as c:
        c.execute("UPDATE beta_operations SET value=%s WHERE key='scan_config'", [json.dumps(scan_config)])


def initialize():
    from django.db import connection

    with connection.cursor() as c:
        c.execute(
            "CREATE TABLE IF NOT EXISTS beta_feedback(id TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id),message TEXT NOT NULL,created DOUBLE PRECISION NOT NULL)"
        )
        c.execute("CREATE TABLE IF NOT EXISTS beta_operations(key TEXT PRIMARY KEY,value TEXT NOT NULL)")
        c.execute(
            "INSERT INTO beta_operations VALUES('scan_config',%s) ON CONFLICT DO NOTHING",
            [json.dumps({"enabled": True, "mode": "manual", "ceiling_usd": 1.0, "user_ceiling_usd": 0.5})],
        )
        c.execute("INSERT INTO beta_operations VALUES('schema','5') ON CONFLICT DO NOTHING")


def manifest():
    """Exact value hashes, including bytes, with no private values in diagnostics."""
    from django.db import connection

    result = {}
    with connection.cursor() as c:
        for table in tables():
            c.execute(f'SELECT * FROM "{table}"')
            rows = []
            for row in c.fetchall():
                encoded = [
                    bytes(v).hex()
                    if isinstance(v, (bytes, memoryview))
                    else str(v)
                    if v is not None
                    else None
                    for v in row
                ]
                rows.append(json.dumps(encoded, separators=(",", ":")))
            result[table] = {
                "count": len(rows),
                "sha256": hashlib.sha256("\n".join(sorted(rows)).encode()).hexdigest(),
            }
    return result


def postgres_environment():
    from psycopg.conninfo import conninfo_to_dict

    values = conninfo_to_dict(os.environ["DATABASE_URL"])
    env = dict(os.environ)
    for key, variable in (
        ("host", "PGHOST"),
        ("port", "PGPORT"),
        ("user", "PGUSER"),
        ("password", "PGPASSWORD"),
        ("dbname", "PGDATABASE"),
    ):
        if key in values:
            env[variable] = values[key]
    env["PGSSLMODE"] = os.environ.get("DEX_DATABASE_SSLMODE", "require")
    return env


def backup(path):
    """One transaction-consistent native dump includes private photo BYTEA and journals."""
    import subprocess

    from django.db import connection

    path.mkdir(mode=0o700, parents=True, exist_ok=False)
    env = postgres_environment()
    with connection.cursor() as c:
        c.execute("BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY")
        try:
            c.execute("SELECT pg_export_snapshot()")
            snapshot = c.fetchone()[0]
            subprocess.run(
                [
                    "pg_dump",
                    "--format=custom",
                    "--no-owner",
                    "--no-acl",
                    "--snapshot=" + snapshot,
                    "--file=" + str(path / "database.dump"),
                ],
                env=env,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            (path / "manifest.json").write_text(json.dumps(manifest(), indent=2))
        finally:
            c.execute("ROLLBACK")
    (path / "sha256").write_text(hashlib.sha256((path / "database.dump").read_bytes()).hexdigest())
    (path / "expires.json").write_text(json.dumps({"expires": __import__("time").time() + 7 * 86400}))
    for p in path.iterdir():
        p.chmod(0o600)


def restore(path):
    import subprocess

    if tables():
        raise ValueError("Restore refuses a nonempty database; retain post-release writes")
    if hashlib.sha256((path / "database.dump").read_bytes()).hexdigest() != (path / "sha256").read_text():
        raise ValueError("Backup checksum mismatch")
    subprocess.run(
        [
            "pg_restore",
            "--exit-on-error",
            "--single-transaction",
            "--no-owner",
            "--no-acl",
            "--dbname="
            + __import__("urllib.parse", fromlist=["urlsplit"]).urlsplit(os.environ["DATABASE_URL"]).path[1:],
            str(path / "database.dump"),
        ],
        env=postgres_environment(),
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    if manifest() != json.loads((path / "manifest.json").read_text()):
        raise ValueError("Restored identities or content differ")


def expire_backups(path, now=None):
    import time

    now = time.time() if now is None else now
    for folder in path.iterdir():
        marker = folder / "expires.json"
        if folder.is_symlink() or not folder.is_dir() or not marker.is_file():
            continue
        if json.loads(marker.read_text())["expires"] > now:
            continue
        expected = {"database.dump", "manifest.json", "sha256", "expires.json"}
        if {p.name for p in folder.iterdir()} != expected or any(p.is_symlink() for p in folder.iterdir()):
            raise ValueError("Unexpected backup contents; refusing cleanup")
        for p in folder.iterdir():
            p.unlink()
        folder.rmdir()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=[
            "migrate-copy",
            "publish-staging-catalog",
            "migrate",
            "web",
            "worker",
            "backup",
            "restore",
            "diagnostics",
            "disable-scanning",
            "cleanup",
            "check",
            "expire-backups",
        ],
    )
    parser.add_argument("--path", type=Path)
    args = parser.parse_args()
    os.umask(0o077)
    setup()
    if args.action == "publish-staging-catalog":
        from pokemon_hunter.inventory import OWNER_ID

        from . import store
        from .catalog_reconcile import publish_all

        owner = store.rows("SELECT auth_subject FROM users WHERE id=%s", [OWNER_ID])[0]
        publish_all(store.principal(owner["auth_subject"]))
    elif args.action == "migrate-copy":
        migrate_copy(args.path)
    elif args.action == "migrate":
        initialize()
    elif args.action == "backup":
        backup(args.path)
    elif args.action == "expire-backups":
        expire_backups(args.path)
    elif args.action == "restore":
        restore(args.path)
    elif args.action == "disable-scanning":
        from .collection import execute
        from .scans import config

        cfg = config()
        cfg["enabled"] = False
        execute("UPDATE beta_operations SET value=%s WHERE key='scan_config'", [json.dumps(cfg)])
    elif args.action == "cleanup":
        from .support import cleanup

        cleanup()
    elif args.action == "diagnostics":
        from .support import diagnostics

        print(json.dumps(diagnostics()))
    elif args.action == "check":
        from django.core.management import call_command

        call_command("check", deploy=True)
    elif args.action == "worker":
        from .scans import config

        if not {"scan_jobs", "scan_photos", "beta_operations", "beta_feedback"} <= set(tables()):
            raise ValueError("Staging migration required")
        config()
        from .scan_worker import run

        run()
    elif args.action == "web":
        from .scans import config

        if not {"scan_jobs", "scan_photos", "beta_operations", "beta_feedback"} <= set(tables()):
            raise ValueError("Staging migration required")
        config()
        import uvicorn
        from django.core.asgi import get_asgi_application

        uvicorn.run(
            get_asgi_application(),
            host="0.0.0.0",
            port=int(os.environ.get("PORT", "8000")),
            access_log=False,
            proxy_headers=False,
            log_level="critical",
            timeout_graceful_shutdown=50,
        )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # No DSNs, SQL, bearer links or provider response bodies in ordinary logs.
        raise SystemExit(
            "Staging operation failed: " + type(exc).__name__ + "; inspect private operator context"
        ) from None
