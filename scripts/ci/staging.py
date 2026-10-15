"""Rehearse copied migration and account/mutation boundaries on an empty CI PostgreSQL DB."""

import argparse
import json
import os
import secrets
import sqlite3
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from urllib.parse import urlsplit

PROJECT = Path(__file__).resolve().parents[2]


def disposable_url(value):
    try:
        parsed = urlsplit(value)
        valid = (
            parsed.scheme == "postgresql"
            and parsed.hostname == "127.0.0.1"
            and parsed.path.startswith("/dex_ci_")
            and parsed.path[1:].replace("_", "").isalnum()
            and parsed.port is not None
            and not parsed.query
            and not parsed.fragment
        )
    except (ValueError, TypeError):
        valid = False
    if not valid:
        raise ValueError("Use an explicit loopback CI database named dex_ci_* with a port")
    return value


def environment():
    return {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("DEX_", "OPENAI_", "EBAY_", "POKEMON_HUNTER_", "PG"))
        and key not in {"DATABASE_URL", "DJANGO_SETTINGS_MODULE", "PGSERVICE", "PGSERVICEFILE"}
    }


def exercise(database_url, source, report):
    import psycopg

    database_url = disposable_url(database_url)
    with psycopg.connect(database_url, connect_timeout=10) as db:
        with db.cursor() as cursor:
            cursor.execute("SELECT current_setting('server_version'), current_schema()")
            version, schema = cursor.fetchone()
            cursor.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public'")
            if cursor.fetchone()[0] or schema != "public":
                raise ValueError("CI migration requires an empty public schema; existing state is refused")
    report["postgres_version"] = version
    if not (source / "SYNTHETIC_ONLY").is_file():
        raise ValueError("Generated synthetic migration input required")
    copied = source.parent / "fixture.copied.sqlite3"
    with sqlite3.connect(source / "inventory.db") as old, sqlite3.connect(copied) as target:
        old.backup(target)
        report["source_table_count"] = len(
            old.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
        )
    config = json.loads((source / "scan-config.json").read_text())
    copied.with_suffix(".scan-config.json").write_text(json.dumps(config))
    os.environ.update(
        DEX_PROFILE="staging",
        DEX_B1_ROOT=str(source),
        DATABASE_URL=database_url,
        DEX_SECRET_KEY=secrets.token_urlsafe(64),
        DEX_PUBLIC_ORIGIN="https://dex-ci.example.test",
        DEX_PROXY_NETWORKS="127.0.0.1/32",
        DEX_DATABASE_SSLMODE="disable",
    )
    from pokemon_hunter.beta import deployment

    deployment.setup()
    deployment.migrate_copy(copied)
    report["checks"].append(
        {"name": "copied migration validates every source table and stable row value", "status": "PASS"}
    )
    from django.contrib.auth import get_user_model
    from django.db import connection
    from django.test import Client

    from pokemon_hunter.beta import collection, scans, store

    if scans.config() != config:
        raise ValueError("Migration changed recognition/spending configuration")
    report["checks"].append(
        {"name": "recognition configuration and retained reservations preserved", "status": "PASS"}
    )
    owner = get_user_model().objects.get(username="admin")
    member = get_user_model().objects.get(username="synthetic-member")
    actor, other = store.principal(owner.pk), store.principal(member.pk)
    before = collection.export_data(actor)
    if {row["id"] for row in before["copies"]} & {
        row["id"] for row in collection.export_data(other)["copies"]
    }:
        raise ValueError("Copied accounts share private copies")
    client = Client(
        enforce_csrf_checks=True,
        REMOTE_ADDR="127.0.0.1",
        HTTP_HOST="dex-ci.example.test",
        HTTP_X_FORWARDED_PROTO="https",
    )
    if client.get("/api/collection-context/").status_code != 302:
        raise ValueError("Staging guest gained collection access")
    client.force_login(owner)
    for path in (
        "/cards/",
        "/pokedex/",
        "/api/collection-context/",
        "/api/my-card-groups/",
        "/api/pokedex-species/",
        "/shopping/",
    ):
        response = client.get(path)
        if response.status_code != 200:
            raise ValueError("Staging current collection route failed")
    if client.post("/api/operations/preview/", "{}", content_type="application/json").status_code != 403:
        raise ValueError("Staging CSRF boundary failed")
    report["checks"].append(
        {"name": "PostgreSQL-backed routes, guest denial and CSRF enforced", "status": "PASS"}
    )
    op = collection.preview(actor, "binder", {"name": "Synthetic CI binder"}, str(uuid.uuid4()))
    if op["plan"]["errors"]:
        raise ValueError("PostgreSQL mutation preview failed")
    first = collection.confirm(actor, op["id"])
    if collection.confirm(actor, op["id"]) != first:
        raise ValueError("Repeated PostgreSQL confirmation was not idempotent")
    collection.undo(actor, op["id"])
    if collection.export_data(actor)["copies"] != before["copies"]:
        raise ValueError("Binder operation changed copies")
    report["checks"].append({"name": "reviewed PostgreSQL confirmation, retry and undo", "status": "PASS"})
    try:
        deployment.migrate_copy(copied)
    except ValueError:
        pass
    else:
        raise ValueError("Repeated migration did not refuse an occupied database")
    report["checks"].append(
        {"name": "occupied destination refused without another migration", "status": "PASS"}
    )
    connection.close()


def run(database_url, output):
    disposable_url(database_url)
    started = time.monotonic()
    report = {
        "status": "FAIL",
        "checks": [],
        "evidence": "disposable synthetic PostgreSQL; no TLS/deployment qualification",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="dex-ci-staging-") as scratch:
        source = Path(scratch) / "synthetic"
        env = environment()
        env.update(DEX_PROFILE="local", HOME=scratch)
        try:
            subprocess.run(
                [sys.executable, "-m", "pokemon_hunter.beta.synthetic", "--output", str(source)],
                cwd=PROJECT,
                env=env,
                check=True,
                timeout=90,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            env["DEX_CI_DATABASE_URL"] = database_url
            result = subprocess.run(
                [
                    sys.executable,
                    str(Path(__file__).resolve()),
                    "--exercise",
                    str(source),
                    "--output",
                    str(output),
                ],
                cwd=PROJECT,
                env=env,
                check=False,
                timeout=120,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if result.returncode != 0:
                raise RuntimeError("PostgreSQL rehearsal failed; see sanitized report")
            report = json.loads(output.read_text())
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
            if output.exists():
                report = json.loads(output.read_text())
            report["status"] = "FAIL"
            report.setdefault("failure", type(error).__name__)
    report["duration_seconds"] = round(time.monotonic() - started, 3)
    output.write_text(json.dumps(report, indent=2) + "\n")
    return int(report["status"] != "PASS")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url")
    parser.add_argument("--exercise", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.exercise:
        report = {"status": "FAIL", "checks": []}
        try:
            exercise(os.environ["DEX_CI_DATABASE_URL"], args.exercise, report)
            report["status"] = "PASS"
        except Exception as error:
            report["failure"] = type(error).__name__
            # Safe fixed check errors aid debugging; framework errors can contain SQL/credentials.
            if isinstance(error, ValueError):
                report["reason"] = str(error)
        args.output.write_text(json.dumps(report, indent=2) + "\n")
        raise SystemExit(int(report["status"] != "PASS"))
    raise SystemExit(run(args.database_url, args.output))
