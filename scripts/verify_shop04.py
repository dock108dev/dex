"""Listing browser checks with a disposable root and mocked provider."""

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.request import urlopen

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
from scripts.ci.browser import browser_cache  # noqa: E402
from scripts.ci.shop04_journey import exercise  # noqa: E402


def main(output):
    from playwright.sync_api import sync_playwright

    output.mkdir(parents=True, exist_ok=True)
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("DEX_", "EBAY_", "OPENAI_", "POKEMON_HUNTER_")) and k != "DATABASE_URL"
    }
    env.update(DEX_PROFILE="local", PLAYWRIGHT_BROWSERS_PATH=str(browser_cache()))
    report = dict(
        status="FAIL",
        evidence_class="disposable engineering state and controlled Browse responses; not customer state or marketplace qualification",
        provider_operations=0,
    )
    with tempfile.TemporaryDirectory(prefix="dex-shop04-ui-") as tmp:
        tmp = Path(tmp)
        root = tmp / "synthetic"
        subprocess.run(
            [sys.executable, "-m", "pokemon_hunter.beta.synthetic", "--output", str(root)],
            env=env,
            check=True,
            stdout=subprocess.DEVNULL,
        )
        subprocess.run(
            [sys.executable, str(PROJECT / "scripts/ci/browser.py"), "--prepare-root", str(root)],
            env=env,
            check=True,
            stdout=subprocess.DEVNULL,
        )
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        assert port != 8011
        base = f"http://127.0.0.1:{port}"
        with (output / "server.log").open("w") as log:
            server = subprocess.Popen(
                [
                    sys.executable,
                    str(PROJECT / "scripts/serve_e4a.py"),
                    "--root",
                    str(root),
                    "--output",
                    str(tmp),
                    "--port",
                    str(port),
                ],
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
            )
            try:
                for _ in range(100):
                    try:
                        if urlopen(base + "/login/", timeout=1).status == 200:
                            break
                    except OSError:
                        time.sleep(0.1)
                with sync_playwright() as pw:
                    browser = pw.chromium.launch()
                    context = browser.new_context(viewport=dict(width=1280, height=900))
                    page = context.new_page()
                    context.route(
                        "**/*",
                        lambda r: (
                            r.continue_()
                            if r.request.url.startswith(base + "/")
                            else r.fulfill(status=404, body="Engineering remote asset blocked")
                        ),
                    )
                    page.goto(base + "/login/")
                    page.get_by_label("Username:", exact=True).fill("admin")
                    page.get_by_label("Password:", exact=True).fill(
                        json.loads((root / "credentials.json").read_text())["admin"]
                    )
                    page.get_by_role("button", name="Sign in", exact=True).click()
                    report["checks"] = exercise(page, base, output)
                    report["status"] = "PASS"
                    context.close()
                    browser.close()
            finally:
                server.terminate()
                server.wait(timeout=10)
                report["provider_operations"] = json.loads((tmp / "provider-calls.json").read_text())["calls"]
                (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main(Path(sys.argv[1]).resolve())
