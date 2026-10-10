"""Smoke a freshly installed wheel from disposable state, without checkout imports.

Install the wheel and locked runtime dependencies into a new environment first:
    python scripts/ci/smoke.py --wheel dist/example.whl --python /tmp/venv/bin/python \
        --report reports/build-smoke.json

The interpreter is supplied deliberately: dependency installation belongs to CI's
locked install step. All app commands use isolated mode and a fresh cwd/HOME. The
server uses its ordinary local CLI, with only its listener port changed to an
unused loopback port by the harness. The production Host/Origin contract remains
127.0.0.1:8011. No owner input or live provider request is used.
"""

import argparse
import hashlib
import http.cookiejar
import json
import os
import socket
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

# The harness may run directly or as a module; children remain isolated from checkout imports.
if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.ci.package_artifacts import REQUIRED_FILES as REQUIRED_FILES
from scripts.ci.package_artifacts import SmokeFailure as SmokeFailure
from scripts.ci.package_artifacts import inspect_sdist as inspect_sdist
from scripts.ci.package_artifacts import inspect_wheel as inspect_wheel

# Execute before importing app code. Isolated subprocesses have no provider keys;
# this also makes an accidental external socket/DNS request a visible failure.
NETWORK_GUARD = """
import os, socket
def local_host(host):
    if host not in (None, '', 'localhost', '127.0.0.1', '::1'):
        with open(os.environ['DEX_SMOKE_NETWORK_ATTEMPTS'], 'a') as output:
            output.write('blocked\\n')
        raise RuntimeError('CI smoke forbids external network access')
original_connect = socket.socket.connect
original_connect_ex = socket.socket.connect_ex
original_getaddrinfo = socket.getaddrinfo
def connect(self, address):
    if isinstance(address, tuple):
        local_host(address[0])
    return original_connect(self, address)
def connect_ex(self, address):
    if isinstance(address, tuple):
        local_host(address[0])
    return original_connect_ex(self, address)
def getaddrinfo(host, *args, **kwargs):
    local_host(host)
    return original_getaddrinfo(host, *args, **kwargs)
socket.socket.connect = connect
socket.socket.connect_ex = connect_ex
socket.getaddrinfo = getaddrinfo
"""

IMPORT_PROBE = """
import hashlib, importlib.metadata, json, sys
from pathlib import Path
import pokemon_hunter
from pokemon_hunter import runtime_data
from pokemon_hunter.beta import canonical_species, catalog_pipeline
expected = json.loads(sys.argv[1])
package = Path(pokemon_hunter.__file__).resolve().parent
prefix = Path(sys.prefix).resolve()
assert package.is_relative_to(prefix), 'Package is outside supplied installation'
assert package.parent.name != 'src', 'Checkout imports are forbidden'
assert runtime_data.root() == package / 'data', 'Packaged data was not selected'
for name, sha in expected.items():
    installed = package.parent / name
    assert hashlib.sha256(installed.read_bytes()).hexdigest() == sha, 'Installed wheel identity differs'
assert len(canonical_species.registry()) == 1025, 'Canonical registry is incomplete'
catalog_pipeline.verify_retained_inputs()
assert catalog_pipeline.retained_batch()['schema_version'] == 'dex-target-batch-v1'
current, aliases = catalog_pipeline.coverage_profile('current')
historical, _ = catalog_pipeline.coverage_profile('historical')
assert current['sets'] and historical['sets'] and aliases, 'Coverage inputs are missing'
entrypoints = importlib.metadata.distribution('pokemon-hunter').entry_points
assert any(ep.name == 'pokemon-hunter' and ep.value == 'pokemon_hunter.main:main' for ep in entrypoints)
print(json.dumps({'python_version': sys.version.split()[0], 'registry_species': 1025,
                  'installed_package_files': len(expected)}))
"""

SERVER = """
import runpy, sys, uvicorn
port = int(sys.argv[1])
root = sys.argv[2]
original_run = uvicorn.run
def run(*args, **kwargs):
    assert kwargs['host'] == '127.0.0.1' and kwargs['port'] == 8011
    kwargs['port'] = port
    return original_run(*args, **kwargs)
uvicorn.run = run
sys.argv = ['pokemon_hunter.beta.cli', '--root', root, 'serve']
runpy.run_module('pokemon_hunter.beta.cli', run_name='__main__')
"""


def isolated_environment(python, home):
    env = {
        "PATH": str(python.parent) + os.pathsep + os.defpath,
        "HOME": str(home),
        "USERPROFILE": str(home),
        "DEX_PROFILE": "local",
        "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "DEX_SMOKE_NETWORK_ATTEMPTS": str(home.parent / "network-attempts"),
    }
    for key in ("SYSTEMROOT", "WINDIR", "COMSPEC", "TMP", "TEMP"):
        if key in os.environ:
            env[key] = os.environ[key]
    return env


def run_python(python, code, arguments, cwd, env, *, timeout=90):
    result = subprocess.run(
        [str(python), "-I", "-c", NETWORK_GUARD + code, *arguments],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if result.returncode:
        # Child commands read only this harness's fresh synthetic root. Reports
        # retain the failure class/exit status without private generated secrets.
        raise SmokeFailure(f"Installed app subprocess failed (exit {result.returncode})")
    return result.stdout


def required_output(output, expected, name):
    if expected not in output:
        raise SmokeFailure(name + " did not produce its expected success output")
    return {"output_verified": True}


def request(opener, port, route, data=None, extra_headers=None):
    headers = {"Host": "127.0.0.1:8011", **(extra_headers or {})}
    req = urllib.request.Request(f"http://127.0.0.1:{port}" + route, data=data, headers=headers)
    try:
        response = opener.open(req, timeout=5)
    except urllib.error.HTTPError as exc:
        response = exc
    with response:
        return response.status, response.headers, response.read()


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def browser_smoke(python, cwd, env, root, timeout):
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    server = subprocess.Popen(
        [str(python), "-I", "-c", NETWORK_GUARD + SERVER, str(port), str(root)],
        cwd=cwd,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    checks = 0
    try:
        guest = urllib.request.build_opener(NoRedirect(), urllib.request.ProxyHandler({}))
        deadline = time.monotonic() + timeout
        while True:
            if server.poll() is not None:
                raise SmokeFailure("Local server exited before becoming ready")
            try:
                status, _, body = request(guest, port, "/pokedex/")
                if status == 200:
                    break
                if status >= 500:
                    raise SmokeFailure("Local server returned an internal error during startup")
            except (urllib.error.URLError, TimeoutError):
                pass
            if time.monotonic() >= deadline:
                raise SmokeFailure("Local server startup exceeded bounded timeout")
            time.sleep(0.2)
        if b"Bulbasaur" not in body:
            raise SmokeFailure("Public Pokédex is missing canonical species")
        for route in ("/", "/pokedex/123/", "/hunt/", "/lookup/?targets=123", "/login/"):
            status, _, _ = request(guest, port, route)
            if status != 200:
                raise SmokeFailure("Public route failed: " + route)
            checks += 1
        status, _, body = request(guest, port, "/api/public/catalog/")
        catalog = json.loads(body)
        if status != 200 or not catalog["printings"] or "counts" not in catalog:
            raise SmokeFailure("Public catalog did not load packaged synthetic inputs")
        checks += 1
        for route in (
            "/api/collection/",
            "/api/inventory/",
            "/api/export/",
            "/collection/",
            "/shopping/",
            "/api/shopping/lot-catalog/",
        ):
            status, headers, _ = request(guest, port, route)
            if status != 302 or not headers.get("Location", "").startswith("/login/"):
                raise SmokeFailure("Guest access was not denied: " + route)
            checks += 1
        for asset in (
            "glass.css",
            "public.css",
            "collection.css",
            "parity.js",
            "pokedex.js",
            "lot_calculator.css",
            "lot_calculator.js",
            "shopping.css",
            "shopping.js",
        ):
            status, headers, body = request(guest, port, "/collection-assets/" + asset)
            expected_type = "text/javascript" if asset.endswith(".js") else "text/css"
            if status != 200 or not body or expected_type not in headers.get("Content-Type", ""):
                raise SmokeFailure("Packaged static asset failed: " + asset)
            checks += 1
        if request(guest, port, "/collection-assets/secret.key")[0] != 404:
            raise SmokeFailure("Asset allowlist did not reject a private filename")
        if request(guest, port, "/pokedex/252/")[0] != 404:
            raise SmokeFailure("Public catalog boundary above 251 was not enforced")
        if request(guest, port, "/pokedex/", extra_headers={"Host": "example.invalid"})[0] != 403:
            raise SmokeFailure("Loopback Host contract was not enforced")
        checks += 3

        jar = http.cookiejar.CookieJar()
        owner = urllib.request.build_opener(
            NoRedirect(), urllib.request.ProxyHandler({}), urllib.request.HTTPCookieProcessor(jar)
        )
        if request(owner, port, "/login/")[0] != 200:
            raise SmokeFailure("Login form failed")
        token = next((cookie.value for cookie in jar if cookie.name == "dex_b1_csrf"), None)
        if not token:
            raise SmokeFailure("Login form did not issue CSRF cookie")
        credentials = json.loads((root / "credentials.json").read_text())
        data = urllib.parse.urlencode(
            {"username": "admin", "password": credentials["admin"], "csrfmiddlewaretoken": token}
        ).encode()
        status, headers, _ = request(owner, port, "/login/", data, {"Origin": "http://127.0.0.1:8011"})
        if status != 302 or headers.get("Location") != "/":
            raise SmokeFailure("Synthetic account login failed")
        for route in ("/collection/", "/api/collection/", "/api/catalog-packages/gym-heroes/", "/shopping/"):
            if request(owner, port, route)[0] != 200:
                raise SmokeFailure("Authenticated route failed: " + route)
            checks += 1
        status, _, body = request(owner, port, "/api/shopping/lot-catalog/")
        shopping = json.loads(body)
        if status != 200 or not shopping.get("cards"):
            raise SmokeFailure("Installed Shopping catalog failed")
        checks += 1
        return {"http_assertions": checks + 2, "listener": "ephemeral loopback, ordinary CLI serve"}
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait(timeout=5)
        if server.poll() is None:
            raise SmokeFailure("Local server cleanup did not complete")


def smoke(wheel, python, timeout=30, *, comparison_wheel=None, sdist=None):
    started = time.monotonic()
    report = {
        "schema_version": "dex-build-smoke-v1",
        "status": "FAIL",
        "artifact": wheel.name,
        "duration_seconds": None,
        "python_version": None,
        "wheel_bytes": None,
        "wheel_uncompressed_bytes": None,
        "wheel_file_count": None,
        "wheel_sha256": None,
        "sdist_bytes": None,
        "sdist_uncompressed_bytes": None,
        "sdist_file_count": None,
        "sdist_sha256": None,
        "comparison_wheel_sha256": None,
        "reproducible_build": None,
        "checks": [],
    }

    def check(name, callback):
        before = time.monotonic()
        entry = {"name": name, "status": "FAIL", "duration_seconds": None, "details": None}
        report["checks"].append(entry)
        try:
            entry["details"] = callback()
            entry["status"] = "PASS"
            return entry["details"]
        finally:
            entry["duration_seconds"] = round(time.monotonic() - before, 3)

    try:
        wheel_check = check("wheel_contents", lambda: inspect_wheel(wheel))
        metrics, hashes = wheel_check
        report["checks"][-1]["details"] = {"packaged_files": len(hashes), "private_state_files": 0}
        report.update(metrics)
        if sdist is not None:
            report.update(check("source_distribution_and_wheel_inputs", lambda: inspect_sdist(sdist, hashes)))
        if comparison_wheel is not None:

            def reproducible():
                report["comparison_wheel_sha256"] = hashlib.sha256(comparison_wheel.read_bytes()).hexdigest()
                report["reproducible_build"] = report["wheel_sha256"] == report["comparison_wheel_sha256"]
                if not report["reproducible_build"]:
                    raise SmokeFailure("Repeated wheel build differs byte-for-byte")
                return {"byte_identical": True, "comparison_artifact": comparison_wheel.name}

            check("reproducible_wheel_build", reproducible)
        with tempfile.TemporaryDirectory(prefix="dex-wheel-smoke-") as work:
            work = Path(work)
            cwd = work / "empty-cwd"
            home = work / "empty-home"
            cwd.mkdir()
            home.mkdir()
            root = work / "synthetic-app"
            env = isolated_environment(python, home)
            imported = check(
                "isolated_installed_import_and_pinned_inputs",
                lambda: json.loads(run_python(python, IMPORT_PROBE, [json.dumps(hashes)], cwd, env)),
            )
            report["python_version"] = imported["python_version"]
            check(
                "synthetic_initializer",
                lambda: required_output(
                    run_python(
                        python,
                        "import runpy, sys; sys.argv=['synthetic','--output',sys.argv[1]]; "
                        "runpy.run_module('pokemon_hunter.beta.synthetic',run_name='__main__')",
                        [str(root)],
                        cwd,
                        env,
                    ),
                    "Synthetic seed prepared.",
                    "Synthetic initializer",
                ),
            )
            if not (root / "SYNTHETIC_ONLY").is_file():
                raise SmokeFailure("Initializer did not mark its synthetic output")
            check(
                "django_configuration",
                lambda: required_output(
                    run_python(
                        python,
                        "import runpy, sys; sys.argv=['cli','--root',sys.argv[1],'check']; "
                        "runpy.run_module('pokemon_hunter.beta.cli',run_name='__main__')",
                        [str(root)],
                        cwd,
                        env,
                    ),
                    "System check identified no issues",
                    "Django check",
                ),
            )
            check(
                "local_public_and_authenticated_journey",
                lambda: browser_smoke(python, cwd, env, root, timeout),
            )
            check(
                "legacy_console_entrypoint",
                lambda: required_output(
                    run_python(
                        python,
                        "import importlib.metadata, sys; sys.argv=['pokemon-hunter','--help']; "
                        "ep=next(ep for ep in importlib.metadata.distribution('pokemon-hunter').entry_points "
                        "if ep.name=='pokemon-hunter'); ep.load()()",
                        [],
                        cwd,
                        env,
                    ),
                    "Daily vintage Pokémon bulk-lot watcher",
                    "Legacy console entrypoint",
                ),
            )

            def no_external_network():
                if Path(env["DEX_SMOKE_NETWORK_ATTEMPTS"]).exists():
                    raise SmokeFailure("App attempted external network access during the smoke")
                return {"external_network_attempts": 0}

            check("acquisition_disabled", no_external_network)

        def cleanup_complete():
            if work.exists():
                raise SmokeFailure("Synthetic temporary state cleanup did not complete")
            return {"temporary_directory_removed": True}

        check("synthetic_state_and_process_cleanup", cleanup_complete)
        report["status"] = "PASS"
    except (
        OSError,
        ValueError,
        KeyError,
        SmokeFailure,
        subprocess.TimeoutExpired,
        zipfile.BadZipFile,
        tarfile.TarError,
    ) as exc:
        report["failure"] = str(exc) if isinstance(exc, SmokeFailure) else type(exc).__name__
    finally:
        report["duration_seconds"] = round(time.monotonic() - started, 3)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument(
        "--comparison-wheel", type=Path, help="Second fresh build; differing bytes fail the gate"
    )
    parser.add_argument("--sdist", type=Path, help="Source distribution used to build the installed wheel")
    parser.add_argument("--startup-timeout", type=int, default=30, choices=range(1, 121), metavar="1..120")
    args = parser.parse_args()
    # Do not resolve symlinks: a venv interpreter's path selects that environment.
    report = smoke(
        args.wheel.absolute(),
        args.python.absolute(),
        args.startup_timeout,
        comparison_wheel=args.comparison_wheel.absolute() if args.comparison_wheel else None,
        sdist=args.sdist.absolute() if args.sdist else None,
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))
    raise SystemExit(0 if report["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
