"""Offline package and browser qualification for the guarded Hunter profile.

All interactive state is disposable and fabricated. The browser listener uses an
explicit test-only loopback port adapter; the supported operator's fixed origin is
qualified separately by its refusal tests. This helper never accepts an app root.
"""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import io
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from urllib.request import ProxyHandler, build_opener

PROJECT = Path(__file__).resolve().parents[1]
CUSTOMER_RUNTIME = Path("/Users/michaelfuscoletti/.local/share/dex/runtimes/shop-04-delivered-20261016")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def clean_environment():
    environment = os.environ.copy()
    for key in list(environment):
        if key.startswith(("DEX_", "EBAY_", "OPENAI_")) or key in {
            "DJANGO_SETTINGS_MODULE",
            "PYTHONPATH",
            "PYTHONHOME",
        }:
            environment.pop(key)
    environment["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    return environment


def verify_package(wheel, expected_digest):
    """Verify archive RECORD and every installed application/data member."""
    if Path(sys.prefix).absolute() == CUSTOMER_RUNTIME:
        raise ValueError("The customer runtime cannot be used for engineering qualification")
    if digest(wheel.read_bytes()) != expected_digest:
        raise ValueError("Wheel identity mismatch")
    import pokemon_hunter

    package = Path(pokemon_hunter.__file__).resolve().parent
    if not package.is_relative_to(Path(sys.prefix).resolve()):
        raise ValueError("Application import is outside the isolated interpreter")
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError("Duplicate wheel member")
        records = [name for name in names if name.endswith(".dist-info/RECORD")]
        if len(records) != 1:
            raise ValueError("Expected one wheel RECORD")
        rows = list(csv.reader(io.StringIO(archive.read(records[0]).decode())))
        for name, checksum, size in rows:
            if checksum:
                data = archive.read(name)
                actual = "sha256=" + base64.urlsafe_b64encode(hashlib.sha256(data).digest()).decode().rstrip(
                    "="
                )
                if actual != checksum or len(data) != int(size):
                    raise ValueError("Wheel RECORD identity mismatch")
        members = {
            name: digest(archive.read(name))
            for name in names
            if name.startswith("pokemon_hunter/") and not name.endswith("/")
        }
    for name, expected in members.items():
        if digest((package.parent / name).read_bytes()) != expected:
            raise ValueError("Installed application member mismatch")
    installed = {
        "pokemon_hunter/" + str(path.relative_to(package))
        for path in package.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    }
    if installed != set(members):
        raise ValueError("Installed application has extra or absent members")
    return dict(
        wheel_sha256=expected_digest,
        package_origin=str(package),
        installed_members_verified=len(members),
        record_entries_verified=len(rows),
        application_origin_isolated=True,
    )


def loaded_origins():
    origins = {
        name: str(Path(module.__file__).resolve())
        for name, module in list(sys.modules.items())
        if name.startswith("pokemon_hunter") and getattr(module, "__file__", None)
    }
    if any(not Path(path).is_relative_to(Path(sys.prefix).resolve()) for path in origins.values()):
        raise ValueError("An application module imported outside the isolated interpreter")
    return origins


def test_child(args):
    package = verify_package(args.wheel, args.expected_wheel_sha256)
    sys.path.insert(0, str(PROJECT / "tests"))
    import pytest

    code = pytest.main(
        [
            "-q",
            "-p",
            "pytest_socket",
            "--disable-socket",
            "--allow-unix-socket",
            "--junitxml=" + str(args.output / "installed-regressions.xml"),
            *(str(PROJECT / item) for item in args.test),
        ]
    )
    origins = loaded_origins()
    package.update(
        application_modules_verified=len(origins),
        exit_code=code,
        all_loaded_application_modules_isolated=True,
    )
    (args.output / "installed-imports.json").write_text(json.dumps(package, indent=2) + "\n")
    return code


def prepare_child(root, source):
    sys.path.insert(0, str(PROJECT / "scripts"))
    from qualify_hunter_ui import prepare

    prepare(root, source)


def serve_child(root, port, output):
    """Run only a fabricated root, without allowance or acquisition transport."""
    if not (root / "SYNTHETIC_ONLY").is_file() or port == 8011:
        raise ValueError("Disposable fixture and non-customer listener required")
    from pokemon_hunter.beta import hunter_profile
    from pokemon_hunter.beta.cli import setup
    from pokemon_hunter.inventory import OWNER_ID

    hunter_profile.configure(OWNER_ID, root, configuration_root=root)
    setup(root)
    from pokemon_hunter.beta import security

    def engineering_port(self, request):
        if (
            request.META.get("HTTP_HOST") != f"127.0.0.1:{port}"
            or request.META.get("REMOTE_ADDR") not in {"127.0.0.1", "::1"}
            or any(key == "HTTP_FORWARDED" or key.startswith("HTTP_X_FORWARDED_") for key in request.META)
            or request.headers.get("Origin") not in {None, f"http://127.0.0.1:{port}"}
        ):
            return security.forbidden("Engineering ingress refused")
        return security.secure_response(self.get_response(request))

    security.LocalOnlyMiddleware.__call__ = engineering_port
    import uvicorn

    from pokemon_hunter.beta.asgi import get_asgi_application

    calls = []
    call_report = output / "provider-attempt-count.json"
    call_report.write_text(json.dumps(dict(attempts=0)) + "\n")

    def prohibited(*args, **kwargs):
        calls.append(True)
        call_report.write_text(json.dumps(dict(attempts=len(calls))) + "\n")
        raise AssertionError("Boundary browser provider access is disabled")

    from unittest.mock import patch

    with (
        patch("httpx.Client.send", prohibited),
        patch("httpx.AsyncClient.send", prohibited),
        patch("pokemon_hunter.beta.discovery_transport.Transport.request", prohibited),
        patch("urllib.request.urlopen", prohibited),
    ):
        uvicorn.run(
            get_asgi_application(),
            host="127.0.0.1",
            port=port,
            access_log=False,
            proxy_headers=False,
            log_level="warning",
        )
    if calls:
        raise AssertionError("A provider path was attempted")


def browser_journey(base, output):
    from playwright.sync_api import expect, sync_playwright

    sys.path.insert(0, str(PROJECT / "scripts"))
    from qualify_shopping import PASSWORD

    checks, external = [], []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        version = browser.version
        context = browser.new_context(viewport=dict(width=1280, height=900))

        def intercept(route):
            if route.request.url.startswith(base + "/"):
                route.continue_()
            else:
                external.append(dict(resource=route.request.resource_type, sent=False))
                route.fulfill(status=404, body="Controlled absent engineering asset")

        context.route("**/*", intercept)
        page = context.new_page()
        page.goto(base + "/shopping/hunter/")
        expect(page).to_have_url(base + "/login/?next=/shopping/hunter/")
        checks.append("anonymous Hunter page requires ordinary sign in")
        page.get_by_label("Username").fill("admin")
        page.get_by_label("Password").fill(PASSWORD)
        page.get_by_role("button", name="Sign in", exact=True).click()
        expect(page.locator("#hunter-start")).to_be_visible()
        checks.append("ordinary password/session/CSRF form reaches Hunter")
        response = context.request.get(base + "/api/shopping/hunter/")
        assert response.status == 200
        assert {value.strip() for value in response.headers["cache-control"].split(",")} >= {
            "private",
            "no-store",
        }
        checks.append("authenticated local status is private and available")
        response = context.request.post(base + "/api/shopping/hunter/", data={"scope": "both"})
        assert response.status == 403
        checks.append("session cookie without CSRF token cannot start Hunter")
        csrf = next(cookie["value"] for cookie in context.cookies() if cookie["name"] == "dex_b1_csrf")
        response = context.request.post(
            base + "/api/shopping/hunter/", data={"scope": "both"}, headers={"X-CSRFToken": csrf}
        )
        assert response.status == 400
        checks.append("valid session and CSRF cannot dispatch without separate exact-plan capacity")
        for path in (
            "/api/inventory/",
            "/api/bulk/save/",
            "/api/scans/",
            "/api/shopping/discovery/",
            "/api/shopping/listing/",
            "/api/admin/catalog/",
            "/recovery/",
        ):
            response = context.request.get(base + path)
            assert response.status in {403, 404}, (path, response.status)
        checks.append("unselected collection/bulk/photo/discovery/admin/recovery routes are refused")
        response = context.request.get(base + "/collection-assets/hunter.js")
        assert response.status == 200
        response = context.request.get(base + "/collection-assets/bulk_entry.js")
        assert response.status in {403, 404}
        checks.append("selected Hunter assets work and unselected assets refuse")
        page.screenshot(path=str(output / "profile-hunter-1280.png"), full_page=True)
        page.set_viewport_size(dict(width=320, height=900))
        expect(page.locator("#hunter-start")).to_be_visible()
        page.screenshot(path=str(output / "profile-hunter-320.png"), full_page=True)
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        checks.append("selected profile renders at 1280 and 320 pixels without horizontal overflow")
        cookies = context.cookies()
        session = next(cookie for cookie in cookies if cookie["name"] == "dex_b1_session")
        assert session["httpOnly"] and session["sameSite"] == "Strict"
        checks.append("ordinary private session cookie policy remains effective")
        context.close()
        browser.close()
    return dict(browser_version=version, checks=checks, external_requests_blocked=len(external))


def browser_qualification(args):
    with tempfile.TemporaryDirectory(prefix="dex-hunter-boundary-") as temporary:
        temporary = Path(temporary)
        root, source = temporary / "application", temporary / "source"
        base_command = [str(args.python), "-I", str(Path(__file__).resolve())]
        subprocess.run(
            [*base_command, "--prepare-child", "--root", str(root), "--source", str(source)],
            env=clean_environment(),
            check=True,
            timeout=90,
        )
        sys.path.insert(0, str(PROJECT / "scripts"))
        from qualification_state import persisted_snapshot

        before = persisted_snapshot(root)
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        with (args.output / "browser-server.txt").open("x") as log:
            process = subprocess.Popen(
                [
                    *base_command,
                    "--serve-child",
                    "--root",
                    str(root),
                    "--port",
                    str(port),
                    "--output",
                    str(args.output),
                ],
                env=clean_environment(),
                stdout=log,
                stderr=subprocess.STDOUT,
            )
            try:
                opener = build_opener(ProxyHandler({}))
                for _ in range(100):
                    if process.poll() is not None:
                        raise ValueError("Disposable profile server failed before readiness")
                    try:
                        with opener.open(f"http://127.0.0.1:{port}/login/", timeout=0.2) as response:
                            if response.status == 200:
                                break
                    except OSError:
                        time.sleep(0.1)
                else:
                    raise TimeoutError("Disposable profile server did not become ready")
                result = browser_journey(f"http://127.0.0.1:{port}", args.output)
            finally:
                process.terminate()
                process.wait(timeout=20)
        assert json.loads((args.output / "provider-attempt-count.json").read_text()) == dict(attempts=0)
        after = persisted_snapshot(root)
        before_tables = before["databases"]["inventory.db"]["tables"]
        after_tables = after["databases"]["inventory.db"]["tables"]
        changed = sorted(name for name in before_tables if before_tables[name] != after_tables[name])
        assert set(changed) <= {
            "auth_user",
            "django_session",
            "axes_accesslog",
            "axes_accessattempt",
            "sqlite_sequence",
        }
        assert before["protected_files"] == after["protected_files"]
        assert not (root.parent / ".dex-shopping-discovery").exists()
        result.update(
            synthetic_only=True,
            disposable_root_removed=True,
            actual_customer_origin_used=False,
            test_only_ingress_port_adapter=True,
            provider_capacity_activated=False,
            no_ledger_created=True,
            changed_database_tables=changed,
            protected_collection_goals_photos_configuration_unchanged=True,
        )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", type=Path)
    parser.add_argument("--wheel", type=Path)
    parser.add_argument("--expected-wheel-sha256")
    parser.add_argument("--repeat-wheel", type=Path)
    parser.add_argument("--sdist", type=Path)
    parser.add_argument("--repeat-sdist", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--test", action="append", default=[])
    parser.add_argument("--browser", action="store_true")
    parser.add_argument("--verify-child", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--test-child", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--prepare-child", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--serve-child", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--root", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--source", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--port", type=int, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.verify_child:
        package = verify_package(args.wheel, args.expected_wheel_sha256)
        (args.output / "package-binding.json").write_text(json.dumps(package, indent=2) + "\n")
        return 0
    if args.prepare_child:
        prepare_child(args.root, args.source)
        return 0
    if args.serve_child:
        serve_child(args.root, args.port, args.output)
        return 0
    if args.test_child:
        return test_child(args)
    if not all((args.python, args.wheel, args.expected_wheel_sha256, args.output)):
        parser.error("--python, --wheel, --expected-wheel-sha256 and --output are required")
    if args.python.absolute().is_relative_to(CUSTOMER_RUNTIME):
        raise ValueError("The customer runtime cannot be used for engineering qualification")
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=False)
    if digest(args.wheel.read_bytes()) != args.expected_wheel_sha256:
        raise ValueError("Input wheel identity mismatch")
    result = dict(
        recorded_at=datetime.now(UTC).isoformat(),
        evidence_class="offline disposable engineering qualification",
        helper_sha256=digest(Path(__file__).read_bytes()),
        wheel_sha256=args.expected_wheel_sha256,
        actual_customer_http_requests=0,
        actual_customer_mutations=0,
        provider_operations=0,
    )
    for label, first, second in (
        ("wheel", args.wheel, args.repeat_wheel),
        ("sdist", args.sdist, args.repeat_sdist),
    ):
        if second:
            if not first or first.read_bytes() != second.read_bytes():
                raise ValueError("Repeat package build differs")
            result[label + "_repeat_identical"] = True
    subprocess.run(
        [
            str(args.python),
            "-I",
            str(Path(__file__).resolve()),
            "--verify-child",
            "--wheel",
            str(args.wheel.resolve()),
            "--expected-wheel-sha256",
            args.expected_wheel_sha256,
            "--output",
            str(args.output),
        ],
        env=clean_environment(),
        check=True,
        timeout=30,
    )
    if args.test:
        with (args.output / "installed-regressions.txt").open("x") as log:
            code = subprocess.call(
                [
                    str(args.python),
                    "-I",
                    str(Path(__file__).resolve()),
                    "--test-child",
                    "--wheel",
                    str(args.wheel.resolve()),
                    "--expected-wheel-sha256",
                    args.expected_wheel_sha256,
                    "--output",
                    str(args.output),
                    *[value for test in args.test for value in ("--test", test)],
                ],
                env=clean_environment(),
                stdout=log,
                stderr=subprocess.STDOUT,
            )
        result["installed_regressions_exit_code"] = code
        if code:
            (args.output / "qualification.json").write_text(json.dumps(result, indent=2) + "\n")
            return code
    if args.browser:
        result["browser"] = browser_qualification(args)
    result["status"] = "PASS"
    (args.output / "qualification.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
