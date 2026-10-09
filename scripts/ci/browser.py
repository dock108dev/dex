"""Run the existing public/member UI journey on a new synthetic root, then clean up."""

import argparse
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from unittest.mock import patch

PROJECT = Path(__file__).resolve().parents[2]


def browser_cache():
    """Preserve installed browser binaries when isolating the child's HOME."""
    if sys.platform == "darwin":
        return Path.home() / "Library/Caches/ms-playwright"
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / "ms-playwright"
    return Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "ms-playwright"


def prepare_journey(root):
    """Complete the fresh demo's documented UI prerequisites before snapshots.

    The general demo has legacy catalogs, two goals and three copies per user.
    The browser journey also needs sealed product metadata, an all-era goal and
    saved research. Publish reviewed inputs through their normal services; their
    original source dates/provenance and explicitly synthetic labels stay intact.
    """
    if not (root / "SYNTHETIC_ONLY").is_file():
        raise ValueError("Fresh generated synthetic browser root required")
    os.environ["DEX_PROFILE"] = "local"
    from pokemon_hunter.beta.cli import setup

    setup(root)
    from django.contrib.auth import get_user_model
    from django.db import connection

    from pokemon_hunter.beta import collection, pack_research, public_catalog, sealed_catalog, store

    owner = store.principal(get_user_model().objects.get(username="admin").pk)
    member = store.principal(get_user_model().objects.get(username="synthetic-member").pk)
    # Refuse an already enriched root instead of adding duplicate goals/saves.
    if any(len(collection.goals(who)) != 2 for who in (owner, member)):
        raise ValueError("Unmodified fresh demo goals required for browser preparation")
    sealed_catalog.initialize()
    pack_research.initialize()
    if sealed_catalog.records()["products"] or any(pack_research.listing(who) for who in (owner, member)):
        raise ValueError("Unmodified fresh demo research required for browser preparation")
    for package in ("2026-10-04", "2026-10-04-151", "m3-synthetic"):
        path = PROJECT / "config/sealed" / package / "package.json"
        op = sealed_catalog.preview(owner, json.loads(path.read_text()))
        sealed_catalog.transition(owner, op["id"], "verify")
        sealed_catalog.transition(owner, op["id"], "publish")
    for who in (owner, member):
        op = collection.preview(
            who,
            "goal",
            {"name": "Synthetic all-era Original 151", "goal_kind": "original151"},
            str(uuid.uuid4()),
        )
        collection.confirm(who, op["id"])
        goal = next(goal for goal in collection.goals(who) if goal["kind"] == "original151")
        pack_research.save(
            who, goal["id"], goal_version=goal["version"], research_name="Synthetic saved baseline"
        )
    public = public_catalog.pack_lookup({"targets": "123,134,230", "scope": "all"})
    if not any(expansion["products"] for expansion in public["expansions"]):
        raise ValueError("Prepared browser fixture has no selected product results")
    if len(collection.goals(member)) != 3 or len(collection.export_data(member)["copies"]) != 3:
        raise ValueError("Prepared browser fixture has unexpected collection state")
    connection.close()


def run(output):
    output.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="dex-ci-browser-") as temporary:
        temporary = Path(temporary)
        root = temporary / "synthetic"
        env = dict(os.environ)
        for key in list(env):
            if key.startswith(("DEX_", "OPENAI_", "EBAY_", "POKEMON_HUNTER_")) or key == "DATABASE_URL":
                del env[key]
        if not env.get("PLAYWRIGHT_BROWSERS_PATH"):
            env["PLAYWRIGHT_BROWSERS_PATH"] = str(browser_cache())
        env.update(DEX_PROFILE="local", HOME=str(temporary), PYTHONUNBUFFERED="1")
        subprocess.run(
            [sys.executable, "-m", "pokemon_hunter.beta.synthetic", "--output", str(root)],
            cwd=PROJECT,
            env=env,
            check=True,
            timeout=90,
            stdout=subprocess.DEVNULL,
        )
        subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--prepare-root", str(root)],
            cwd=PROJECT,
            env=env,
            check=True,
            timeout=90,
            stdout=subprocess.DEVNULL,
        )
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        if port == 8011:
            raise ValueError("Reserved personal app port selected")
        base = f"http://127.0.0.1:{port}"
        with (temporary / "server.log").open("w") as log:
            server = subprocess.Popen(
                [
                    sys.executable,
                    str(PROJECT / "scripts/serve_e4a.py"),
                    "--root",
                    str(root),
                    "--output",
                    str(temporary),
                    "--port",
                    str(port),
                ],
                cwd=PROJECT,
                env=env,
                stdout=log,
                stderr=log,
            )
            try:
                deadline = time.monotonic() + 30
                opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
                while time.monotonic() < deadline:
                    if server.poll() is not None:
                        raise RuntimeError("Synthetic browser server exited during startup")
                    try:
                        with opener.open(base + "/pokedex/", timeout=2) as response:
                            if response.status == 200:
                                break
                    except (urllib.error.URLError, TimeoutError):
                        time.sleep(0.2)
                else:
                    raise TimeoutError("Synthetic browser server did not become ready in 30 seconds")
                # The existing harness reads provider-calls.json beside its output directory.
                captures = temporary / "captures"
                subprocess.run(
                    [
                        sys.executable,
                        str(PROJECT / "scripts/verify_public_ui.py"),
                        "--root",
                        str(root),
                        "--base-url",
                        base,
                        "--output",
                        str(captures),
                    ],
                    cwd=PROJECT,
                    env=env,
                    check=True,
                    timeout=180,
                )
                report = json.loads((captures / "report.json").read_text())
                report["status"] = report["result"]
                report["duration_seconds"] = round(time.monotonic() - started, 3)
                report["state_count"] = len(report["states"])
                (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
            finally:
                server.terminate()
                try:
                    server.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait(timeout=5)
                # Retain only synthetic viewport captures, never credentials/database/server environment.
                if (temporary / "captures").exists():
                    for capture in (temporary / "captures").glob("*.png"):
                        (output / capture.name).write_bytes(capture.read_bytes())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--output", type=Path)
    mode.add_argument(
        "--prepare-root", type=Path, help="Complete an unmodified generated demo for this journey"
    )
    args = parser.parse_args()
    if args.prepare_root:
        with (
            patch("httpx.Client.send", side_effect=AssertionError("No CI fixture acquisition")),
            patch("httpx.AsyncClient.send", side_effect=AssertionError("No CI fixture acquisition")),
            patch(
                "pokemon_hunter.beta.ebay_hunts.search",
                side_effect=AssertionError("No CI fixture acquisition"),
            ),
            patch("urllib.request.urlopen", side_effect=AssertionError("No CI fixture acquisition")),
        ):
            prepare_journey(args.prepare_root.resolve())
    else:
        run(args.output.resolve())
