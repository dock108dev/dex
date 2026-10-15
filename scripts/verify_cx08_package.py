"""Fresh repeat-build, archive, isolated installation and integrated collection checks.

Only disposable engineering roots/listeners are used. Runtime dependencies come
from the hash-locked export; browser tooling remains in the qualification host.
All installed package files, wheel RECORD entries and retained source inputs are
checked. Profile probes describe local configuration, never hosted deployment.
"""

import argparse
import base64
import csv
import hashlib
import io
import json
import subprocess
import sys
import tempfile
import time
import traceback
import zipfile
from pathlib import Path
from urllib.request import urlopen

from verify_cx02 import free_port
from verify_cx07 import exercise
from verify_cx07_package import PROBE, SERVER, b2_exercise

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
from scripts.ci.package_artifacts import inspect_sdist, inspect_wheel  # noqa: E402
from scripts.ci.smoke import NETWORK_GUARD, isolated_environment, smoke  # noqa: E402

ORIGINS = """
import importlib.util
origins={}
for name in expected:
    if not name.endswith('.py') or '/data/' in name:
        continue
    module=name[:-3].replace('/','.')
    if module.endswith('.__init__'): module=module[:-9]
    spec=importlib.util.find_spec(module)
    assert spec and spec.origin, module
    path=Path(spec.origin).resolve()
    assert path.is_relative_to(Path(sys.prefix).resolve()), module
    assert path==package.parent/name, module
    origins[module]=str(path)
assert not any(k.startswith('pokemon_hunter') and getattr(v,'__file__',None)
               and not Path(v.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
               for k,v in sys.modules.items()), 'Checkout application import'
print(json.dumps(dict(module_origins=origins,all_application_imports_installed=True)))
"""


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_inputs(hashes):
    inputs = {}
    for name, digest in hashes.items():
        source = name.removeprefix("pokemon_hunter/data/") if "/data/config/" in name else "src/" + name
        assert file_hash(PROJECT / source) == digest, source
        inputs[source] = digest
    for directory in ("scripts",):
        for path in sorted((PROJECT / directory).rglob("*.py")):
            inputs[str(path.relative_to(PROJECT))] = file_hash(path)
    for name in ("uv.lock", "pyproject.toml"):
        inputs[name] = file_hash(PROJECT / name)
    return inputs


def validate_record(wheel):
    with zipfile.ZipFile(wheel) as archive:
        records = [name for name in archive.namelist() if name.endswith(".dist-info/RECORD")]
        assert len(records) == 1, records
        rows = list(csv.reader(io.StringIO(archive.read(records[0]).decode())))
        assert {row[0] for row in rows} == set(archive.namelist()), "RECORD inventory differs"
        for name, digest, size in rows:
            if name == records[0]:
                assert digest == size == ""
                continue
            data = archive.read(name)
            encoded = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).decode().rstrip("=")
            assert digest == "sha256=" + encoded and int(size) == len(data), name
        return dict(record_entries=len(rows), hashes_and_sizes_verified=True)


def integrated_server(python, inputs, work, output, expected_origin, report, env, *, b2=False):
    port = free_port()
    assert port != 8011
    url = f"http://127.0.0.1:{port}"
    with (output / "server.log").open("w") as log:
        server = subprocess.Popen(
            [str(python), "-I", "-c", NETWORK_GUARD + SERVER, *inputs, str(output), str(port)],
            cwd=work,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        try:
            for _ in range(100):
                if server.poll() is not None:
                    raise RuntimeError("Installed server exited before becoming ready")
                try:
                    with urlopen(url + "/login/", timeout=1) as response:
                        if response.status == 200:
                            break
                except OSError:
                    time.sleep(0.1)
            else:
                raise RuntimeError("Installed server readiness timeout")
            origin = json.loads((output / "installed-server-origin.json").read_text())
            assert origin["verified"] and origin["package_origin"] == expected_origin
            report.setdefault("installed_servers", []).append(dict(origin, parity=not b2))
            if b2:
                b2_exercise(url, work / "engineering-root", output, report)
                report["installed_b2_browser_execution_passed"] = True
            else:
                exercise(
                    url,
                    work / "engineering-root",
                    output,
                    json.loads((work / "fixture.json").read_text()),
                    report,
                )
                report["installed_browser_execution_passed"] = True
        finally:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=10)
            assert server.poll() is not None
            report.setdefault("process_cleanup", []).append(dict(pid=server.pid, exited=True, port=port))
    assert json.loads((output / "provider-calls.json").read_text())["calls"] == 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    report = dict(
        evidence_class="fresh hash-locked installed wheel; disposable integrated Chromium and profile probes",
        customer_installation_accessed=False,
        hosted_postgresql_tls_deployment_qualified=False,
        checks=[],
    )
    work = None
    started = time.monotonic()

    def run(command, cwd=PROJECT, env=None):
        result = subprocess.run(command, cwd=cwd, env=env, text=True, capture_output=True, timeout=600)
        report.setdefault("commands", []).append(
            dict(command=command, returncode=result.returncode, stdout=result.stdout, stderr=result.stderr)
        )
        assert result.returncode == 0, (command, result.stdout, result.stderr)
        return result

    try:
        for name in ("build-one", "build-two"):
            run(
                [
                    "uv",
                    "build",
                    "--offline",
                    "--no-build-isolation",
                    "--python",
                    sys.executable,
                    "--out-dir",
                    str(output / name),
                ]
            )
        wheels = list((output / "build-one").glob("*.whl"))
        repeats = list((output / "build-two").glob("*.whl"))
        sdists = list((output / "build-one").glob("*.tar.gz"))
        assert len(wheels) == len(repeats) == len(sdists) == 1
        wheel, repeat, sdist = wheels[0], repeats[0], sdists[0]
        metrics, expected = inspect_wheel(wheel)
        report.update(metrics)
        report.update(inspect_sdist(sdist, expected))
        report["wheel_record"] = validate_record(wheel)
        report["comparison_wheel_sha256"] = file_hash(repeat)
        assert report["wheel_sha256"] == report["comparison_wheel_sha256"], "Repeat wheel bytes differ"
        report["reproducible_build"] = True
        sources = source_inputs(expected)
        report.update(
            installed_input_hashes=expected, source_hashes=sources, uv_lock_sha256=sources["uv.lock"]
        )
        with tempfile.TemporaryDirectory(prefix="dex-cx08-installed-") as temporary:
            work = Path(temporary)
            environment = work / "venv"
            runtime = output / "runtime-requirements.txt"
            run(["uv", "venv", "--offline", "--python", sys.executable, str(environment)])
            run(
                [
                    "uv",
                    "export",
                    "--offline",
                    "--locked",
                    "--no-dev",
                    "--no-emit-project",
                    "--format",
                    "requirements-txt",
                    "--output-file",
                    str(runtime),
                ]
            )
            python = environment / "bin/python"
            run(["uv", "pip", "sync", "--offline", "--python", str(python), "--require-hashes", str(runtime)])
            run(["uv", "pip", "install", "--offline", "--python", str(python), "--no-deps", str(wheel)])
            report["runtime_requirements_sha256"] = file_hash(runtime)
            distribution = smoke(wheel, python, comparison_wheel=repeat, sdist=sdist)
            (output / "smoke.json").write_text(json.dumps(distribution, indent=2) + "\n")
            assert distribution["status"] == "PASS", distribution
            home = work / "home"
            home.mkdir()
            env = isolated_environment(python, home)
            inputs = [json.dumps(expected), str(work), str(PROJECT / "scripts")]
            result = run(
                [str(python), "-I", "-c", NETWORK_GUARD + PROBE + ORIGINS, *inputs], cwd=work, env=env
            )
            records = [json.loads(line) for line in result.stdout.splitlines()]
            report["installed_probe"], report["installed_module_origins"] = records[-2:]
            installed_origin = report["installed_probe"]["package_origin"]
            integrated_server(python, inputs, work, output, installed_origin, report, env)
            marker = work / "engineering-root/B2_PARITY_ISOLATED"
            assert marker.is_file()
            marker.rename(work / "retained-B2_PARITY_ISOLATED")
            b2_output = output / "installed-b2"
            b2_output.mkdir()
            integrated_server(python, inputs, work, b2_output, installed_origin, report, env, b2=True)
            assert not Path(env["DEX_SMOKE_NETWORK_ATTEMPTS"]).exists()
            report["provider_calls"] = 0
            assert sources == {name: file_hash(PROJECT / name) for name in sources}, (
                "Source changed during qualification"
            )
            report["source_stable_during_verification"] = True
        assert work is not None and not work.exists()
        report["disposable_root_and_runtime_cleanup"] = dict(path=str(work), removed=True)
        report["passed"] = True
    except Exception:
        report["passed"] = False
        report["failure"] = traceback.format_exc()
        raise
    finally:
        report["duration_seconds"] = round(time.monotonic() - started, 3)
        report["temporary_root_removed"] = work is None or not work.exists()
        (output / "verification.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
