import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from .config import load_config, load_env
from .database import Database
from .ebay import EbayClient
from .notifier import Notifier, from_settings
from .pokedex import read_pokedex, summary
from .runner import run


def main(argv=None):
    parser = argparse.ArgumentParser(description="Daily vintage Pokémon bulk-lot watcher")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Project root containing config/")
    sub = parser.add_subparsers(dest="command", required=True)
    watch = sub.add_parser("run", help="Fetch eBay listings and deliver qualifying digests")
    watch.add_argument(
        "--fixture", type=Path, help="Offline eBay JSON; uses separate demo data/reports, no network"
    )
    watch.add_argument(
        "--db", type=Path, help="Override database path (fixture runs require a demo filename)"
    )
    watch.add_argument("--reports", type=Path, help="Override local report folder")
    sub.add_parser("doctor", help="Check local setup without making network requests")
    sub.add_parser("status", help="Show collection and latest live run")
    dex = sub.add_parser("pokedex", help="Inspect or update collection ownership")
    dex.add_argument("--owned", nargs="+", type=int)
    dex.add_argument("--missing", nargs="+", type=int)
    app_parser = sub.add_parser("app", help="Open the local Vintage 251 collection app")
    app_parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)
    root = args.root.expanduser().resolve()
    if args.command == "app":
        from .app import serve

        serve(root, args.port)
        return 0
    try:
        load_env(root / ".env")
        settings, catalog, queries = load_config(root)
        pokedex_path = root / "config/pokedex.json"
        rows = read_pokedex(pokedex_path)
        if args.command == "pokedex":
            owned, missing = set(args.owned or []), set(args.missing or [])
            if (owned | missing) - set(range(1, 252)) or owned & missing:
                raise ValueError("Use numbers 1–251; a number cannot be both owned and missing")
            if owned or missing:
                raise ValueError(
                    "Update exact card quantities in pokemon-hunter app; species ownership is derived"
                )
            print(summary(rows))
            return 0
        if args.command == "doctor":
            import os

            checks = {
                "delivery ZIP configured": bool(settings.delivery_postal_code),
                "eBay client ID present": bool(os.getenv("EBAY_CLIENT_ID")),
                "eBay client secret present": bool(os.getenv("EBAY_CLIENT_SECRET")),
            }
            print(summary(rows))
            print(
                f"{len(queries)} queries × 2 purchase types · {settings.environment} · ZIP {settings.delivery_postal_code}"
            )
            print(
                "Notifications: local reports"
                + (" + webhook" if os.getenv("POKEMON_HUNTER_WEBHOOK_URL") else "")
                + (" + macOS" if settings.alerts.macos_notification else "")
            )
            for label, ok in checks.items():
                print(f"{'OK' if ok else 'MISSING'}: {label}")
            print("Local setup check only; eBay access has not been tested.")
            return 0 if all(checks.values()) else 1
        if args.command == "status":
            print(summary(rows))
            path = root / "data/pokemon.db"
            if path.exists():
                db = Database(path)
                try:
                    row = db.conn.execute("SELECT * FROM runs ORDER BY id DESC LIMIT 1").fetchone()
                    print(json.dumps(dict(row), indent=2) if row else "No live runs yet.")
                finally:
                    db.close()
            else:
                print("No live runs yet.")
            return 0
        fixture = args.fixture is not None
        db_path = args.db or root / ("data/demo.db" if fixture else "data/pokemon.db")
        if fixture and "demo" not in db_path.stem:
            raise ValueError("Offline fixtures require a database filename containing demo")
        reports = args.reports or root / ("reports/demo" if fixture else "reports/live")
        raw = json.loads(args.fixture.read_text()) if fixture else None
        fixture_time = None
        if isinstance(raw, dict):
            if raw.get("observedAt"):
                fixture_time = datetime.fromisoformat(raw["observedAt"].replace("Z", "+00:00"))
                if fixture_time.tzinfo is None:
                    raise ValueError("Fixture observedAt requires a timezone")
            raw = raw["itemSummaries"]
        notifier = Notifier(reports) if fixture else from_settings(reports, settings)
        client = None if fixture else EbayClient(settings)
        try:
            result = run(
                db_path,
                settings,
                catalog,
                queries,
                rows,
                notifier,
                client=client,
                fixtures=raw,
                now=fixture_time,
            )
        finally:
            if client:
                client.close()
        # Silence on no hits. Run health and coverage remain inspectable in SQLite.
        if result["alerted"]:
            if fixture:
                print("OFFLINE DEMO — synthetic listings, not live eBay offers")
            print(json.dumps(result, indent=2))
        for note in result["notes"]:
            print("Coverage: " + note, file=sys.stderr)
        return 0
    except Exception as exc:
        # Do not print httpx URLs, tokens, response bodies, or arbitrary API data.
        safe = isinstance(exc, (ValueError, RuntimeError, FileNotFoundError))
        print(f"Watcher failed: {str(exc) if safe else type(exc).__name__}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
