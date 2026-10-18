"""Real Chromium Hunter qualification on disposable, explicitly fabricated state.

No customer installation or credentials are read. The test child replaces provider
transport with an in-process fake and deliberately selects ordinary usage through
the owner settings on its disposable root.
Controlled browser responses cover races and lifecycle changes that are awkward
to schedule through a real backend. Neither evidence class is genuine listings.
"""

import argparse
import asyncio
import hashlib
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import traceback
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.request import ProxyHandler, build_opener

# Keep the established harness imports usable by related qualification scripts.
if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.hunter_ui_journey import contrast_ratio as contrast_ratio
from scripts.hunter_ui_journey import exercise as exercise
from scripts.hunter_ui_journey import protected_state as protected_state

PROJECT = Path(__file__).resolve().parents[1]
SOURCE_FILES = (
    "src/pokemon_hunter/beta/static/hunter.js",
    "src/pokemon_hunter/beta/static/hunter-review.js",
    "src/pokemon_hunter/beta/static/hunter.css",
    "src/pokemon_hunter/beta/templates/beta/hunter.html",
    "src/pokemon_hunter/beta/hunter_views.py",
    "scripts/qualify_hunter_ui.py",
    "scripts/hunter_ui_journey.py",
)
INSTALLED = False


def package_binding():
    """Bind the actual imported package and shipped UI assets to this candidate."""
    import pokemon_hunter

    package = Path(pokemon_hunter.__file__).resolve().parent
    origins = {
        name: str(Path(module.__file__).resolve())
        for name, module in list(sys.modules.items())
        if name.startswith("pokemon_hunter") and getattr(module, "__file__", None)
    }
    if INSTALLED and any(
        not Path(path).is_relative_to(Path(sys.prefix).resolve()) for path in origins.values()
    ):
        raise AssertionError("Installed qualification imported application code outside its isolated runtime")
    assets = {}
    for source in SOURCE_FILES:
        prefix = "src/pokemon_hunter/"
        if not source.startswith(prefix):
            continue
        packaged = package / source.removeprefix(prefix)
        digest = hashlib.sha256(packaged.read_bytes()).hexdigest()
        assert digest == hashlib.sha256((PROJECT / source).read_bytes()).hexdigest(), source
        assets[source.removeprefix(prefix)] = digest
    return dict(
        installed=INSTALLED, package_root=str(package), module_origins=origins, matching_assets=assets
    )


def prepare(root, source):
    """Create the existing four-printing fixture; never accept an existing root."""
    if root.exists() or source.exists():
        raise ValueError("Fresh disposable paths required")
    from qualify_shopping import prepare as prepare_shopping

    prepare_shopping(root, source)
    from django.db import connection

    from pokemon_hunter.beta import collection

    collection.execute("UPDATE catalog_sets SET name='Engineering Set'")
    collection.execute(
        "UPDATE printings SET edition='unlimited',finish='normal',variant='normal',unresolved_fields='[]'"
    )
    guide_path = root / "parity-evidence/market_values.json"
    guides = json.loads(guide_path.read_text())
    for guide in guides:
        guide.update(
            as_of=(datetime.now(UTC) - timedelta(days=1)).date().isoformat(),
            edition="unlimited",
            finish="normal",
            language="en",
            condition="NM",
            value="12.00",
            basis="Fabricated engineering reference; not current market evidence",
        )
    guide_path.write_text(json.dumps(guides))
    (root / "engineering-package-origin.json").write_text(json.dumps(package_binding(), indent=2))
    connection.close()


def serve(root, output, port):
    """A fake provider runs only in this guarded disposable server process."""
    if not (root / "SYNTHETIC_ONLY").is_file() or port == 8011:
        raise ValueError("Disposable fixture root and non-customer port required")
    from pokemon_hunter.beta.cli import setup

    setup(root)
    from serve_e4a import run

    from pokemon_hunter.beta import hunter, hunter_budget, shopping

    # This assertion is before the test-only patch: source configuration stays off.
    assert hunter_budget.TRAVERSAL_ALLOWANCE is None
    calls = []

    class FakeTransport:
        async def request(self, stage, **kwargs):
            calls.append(dict(stage=stage))
            (output / "fake-transport.json").write_text(json.dumps(calls))
            await asyncio.sleep(0.03)
            if stage == "oauth":
                return dict(access_token="FABRICATED_LOCAL_TOKEN", expires_in=3600, token_type="Bearer")
            assert stage == "browse", "No detail capacity is granted"
            request = kwargs["search_options"]["hunter"]
            scope, lane = request.scope, request.lane
            ordinal = request.ordinal
            end = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
            rows = []
            for index in range(130):
                number = (1 if scope == "lots" else 0) * 100000 + (1 if lane == "auction" else 2) * 1000
                number += ordinal * 1000 + index
                row = dict(
                    itemId=f"v1|{123456000000 + number}|0",
                    title="Bulbasaur Engineering Set #44 English Unlimited Non Holo",
                    condition="Near Mint",
                    buyingOptions=["AUCTION"] if lane == "auction" else ["FIXED_PRICE"],
                    price=dict(value="2.00", currency="USD"),
                    currentBidPrice=dict(value="1.00", currency="USD"),
                    minimumPriceToBid=dict(value="1.50", currency="USD"),
                    shippingOptions=[dict(shippingCost=dict(value="0.50", currency="USD"))],
                    itemWebUrl=f"https://www.ebay.com/itm/{123456000000 + number}",
                    leafCategoryIds=["183455" if scope == "lots" else "183454"],
                )
                if lane == "auction":
                    row["itemEndDate"] = end
                if scope == "singles" and index == 1:
                    row["title"] = "Engineering mystery sealed booster"
                elif scope == "singles" and index == 2:
                    row["title"] = "Chansey Engineering Set #3 English Unlimited Non Holo"
                elif scope == "singles" and index == 3:
                    row["title"] = "Scyther English Pokémon card"
                if scope == "lots":
                    row.update(
                        title="Engineering Pokémon lot of 3 cards",
                        shortDescription=(
                            "2x Bulbasaur Engineering Set #44 English Unlimited Non Holo; "
                            "1x Chansey Engineering Set #3 English Unlimited Non Holo"
                        ),
                        lotSize="2",
                        estimatedAvailabilities=[dict(estimatedAvailableQuantity=8)],
                    )
                rows.append(row)
            return dict(itemSummaries=rows, total=5000, next="https://never-request.invalid/next")

        async def close(self):
            pass

    with (
        patch.object(hunter, "Transport", FakeTransport),
        patch.object(
            shopping,
            "sources",
            lambda: (json.loads((root / "parity-evidence/market_values.json").read_text()), {}),
        ),
        patch.object(
            hunter.ebay_hunts,
            "configuration",
            lambda: (
                SimpleNamespace(environment="production"),
                dict(EBAY_CLIENT_ID="FABRICATED_LOCAL_CLIENT", EBAY_CLIENT_SECRET="FABRICATED_LOCAL_SECRET"),
            ),
        ),
    ):
        run(root, output, port)


def run(output):
    output.mkdir(parents=True, exist_ok=True)
    report = dict(
        status="FAIL",
        evidence_class="disposable engineering roots; fabricated provider transport; labeled controlled browser responses",
        customer_installation_accessed=False,
        external_provider_operations=0,
        checks=[],
    )
    report["source_hashes"] = {
        name: hashlib.sha256((PROJECT / name).read_bytes()).hexdigest() for name in SOURCE_FILES
    }
    try:
        with tempfile.TemporaryDirectory(prefix="dex-hunter-ui-engineering-") as temporary:
            temporary = Path(temporary)
            root = temporary / "engineering-root"
            env = {
                key: value
                for key, value in os.environ.items()
                if not key.startswith(("DEX_", "EBAY_", "OPENAI_", "POKEMON_HUNTER_"))
                and key != "DATABASE_URL"
            }
            env.update(DEX_PROFILE="local", PYTHONUNBUFFERED="1")
            env.pop("PYTHONPATH", None)
            env.pop("PYTHONHOME", None)
            installed_option = ["--installed"] if INSTALLED else []
            subprocess.run(
                [
                    sys.executable,
                    __file__,
                    "--prepare",
                    "--root",
                    str(root),
                    "--source",
                    str(temporary / "source"),
                    *installed_option,
                ],
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
                raise ValueError("Reserved customer port selected")
            base = f"http://127.0.0.1:{port}"
            with (output / "engineering-server.log").open("w") as log:
                server = subprocess.Popen(
                    [
                        sys.executable,
                        __file__,
                        "--serve",
                        "--root",
                        str(root),
                        "--port",
                        str(port),
                        "--output",
                        str(output),
                        *installed_option,
                    ],
                    cwd=PROJECT,
                    env=env,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                )
                try:
                    opener = build_opener(ProxyHandler({}))
                    deadline = time.monotonic() + 30
                    while time.monotonic() < deadline:
                        if server.poll() is not None:
                            raise RuntimeError("Disposable server exited before readiness")
                        try:
                            with opener.open(base + "/login/", timeout=1) as response:
                                if response.status == 200:
                                    break
                        except OSError:
                            time.sleep(0.1)
                    else:
                        raise TimeoutError("Disposable server failed to become ready")
                    exercise(base, root, output, report)
                    report["application_binding"] = json.loads(
                        (root / "engineering-package-origin.json").read_text()
                    )
                finally:
                    server.terminate()
                    try:
                        server.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        server.kill()
                        server.wait(timeout=5)
            assert json.loads((output / "provider-calls.json").read_text())["calls"] == 0
            report["blocked_provider_transport_attempts"] = 0
            report["fake_transport_operations"] = json.loads((output / "fake-transport.json").read_text())
            after_source_hashes = {
                name: hashlib.sha256((PROJECT / name).read_bytes()).hexdigest() for name in SOURCE_FILES
            }
            assert report["source_hashes"] == after_source_hashes, (
                "Source changed during browser qualification"
            )
            report["source_stable_during_verification"] = True
        report["status"] = "PASS"
    except Exception:
        report["failure"] = traceback.format_exc()
        raise
    finally:
        (output / "verification.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


def main():
    global INSTALLED
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--prepare", action="store_true")
    mode.add_argument("--serve", action="store_true")
    parser.add_argument("--root", type=Path)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--port", type=int)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--installed",
        action="store_true",
        help="Require application imports inside this isolated interpreter",
    )
    args = parser.parse_args()
    INSTALLED = args.installed
    os.environ["DEX_PROFILE"] = "local"
    if args.prepare:
        prepare(args.root.resolve(), args.source.resolve())
    elif args.serve:
        serve(args.root.resolve(), args.output.resolve(), args.port)
    elif args.output:
        run(args.output.resolve())
    else:
        parser.error("Choose --output, --prepare or --serve")


if __name__ == "__main__":
    main()
