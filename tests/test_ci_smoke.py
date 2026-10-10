"""Build-gate regressions: private inputs, incomplete artifacts, false success."""

import importlib.util
import io
import json
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

from pokemon_hunter import runtime_data

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("dex_ci_smoke", ROOT / "scripts/ci/smoke.py")
ci_smoke = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ci_smoke)


def wheel(tmp_path, *, omit=None, extra=None):
    destination = tmp_path / "example.whl"
    with zipfile.ZipFile(destination, "w") as archive:
        for filename in ci_smoke.REQUIRED_FILES:
            if filename != omit:
                archive.writestr(filename, "synthetic package input")
        for filename in extra or []:
            archive.writestr(filename, "SYNTHETIC_PRIVATE_SENTINEL")
    return destination


@pytest.mark.parametrize(
    "missing",
    [
        "static/public.css",
        "asgi.py",
        "static/lot_calculator.js",
        "templates/beta/lot_calculator.html",
        "retained_guide_admission.json",
        "shopping_math.py",
    ],
)
def test_missing_runtime_asset_fails_with_required_check_in_report(tmp_path, missing):
    artifact = wheel(tmp_path, omit="pokemon_hunter/beta/" + missing)
    report = ci_smoke.smoke(artifact, Path(sys.executable))
    assert report["status"] == "FAIL"
    assert report["checks"][0]["status"] == "FAIL"
    assert missing in report["failure"]
    assert report["python_version"] is None


@pytest.mark.parametrize(
    "private_file",
    (
        "pokemon_hunter/data/.env",
        "pokemon_hunter/data/config/pokedex_251.json",
        "pokemon_hunter/inventory.db",
    ),
)
def test_packaging_private_state_cannot_produce_success(tmp_path, private_file):
    report = ci_smoke.smoke(wheel(tmp_path, extra=[private_file]), Path(sys.executable))
    assert report["status"] == "FAIL"
    assert report["checks"][0]["status"] == "FAIL"
    assert "SYNTHETIC_PRIVATE_SENTINEL" not in json.dumps(report)


def test_installed_layout_without_data_refuses_working_directory_fallback(tmp_path, monkeypatch):
    package = tmp_path / "site-packages/pokemon_hunter"
    package.mkdir(parents=True)
    checkout = tmp_path / "owner-checkout"
    (checkout / "config").mkdir(parents=True)
    (checkout / "pyproject.toml").write_text("SYNTHETIC checkout")
    monkeypatch.setattr(runtime_data, "__file__", str(package / "runtime_data.py"))
    monkeypatch.chdir(checkout)
    with pytest.raises(FileNotFoundError, match="missing from this installation"):
        runtime_data.root()


def test_empty_success_output_does_not_pass_required_command():
    with pytest.raises(ci_smoke.SmokeFailure, match="expected success output"):
        ci_smoke.required_output("", "System check identified no issues", "Django check")


def test_changed_repeated_wheel_is_a_required_failure_before_app_start(tmp_path):
    first = wheel(tmp_path)
    repeated = tmp_path / "repeated.whl"
    repeated.write_bytes(first.read_bytes() + b"SYNTHETIC_BUILD_DRIFT")
    report = ci_smoke.smoke(first, Path(sys.executable), comparison_wheel=repeated)
    assert report["status"] == "FAIL"
    assert report["reproducible_build"] is False
    assert report["checks"][-1]["name"] == "reproducible_wheel_build"
    assert report["checks"][-1]["status"] == "FAIL"
    assert report["python_version"] is None


@pytest.mark.parametrize("name", (".env", "../outside.py"))
def test_private_or_unsafe_sdist_is_a_required_failure(tmp_path, name):
    source = tmp_path / "example.tar.gz"
    with tarfile.open(source, "w:gz") as archive:
        entry = tarfile.TarInfo("example-0.1/" + name)
        entry.size = 1
        archive.addfile(entry, io.BytesIO(b"x"))
    report = ci_smoke.smoke(wheel(tmp_path), Path(sys.executable), sdist=source)
    assert report["status"] == "FAIL"
    assert report["checks"][-1]["name"] == "source_distribution_and_wheel_inputs"
    assert report["checks"][-1]["status"] == "FAIL"
    assert report["python_version"] is None


def test_child_environment_does_not_inherit_provider_keys_or_python_path(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "SYNTHETIC_API_SENTINEL")
    monkeypatch.setenv("EBAY_CLIENT_SECRET", "SYNTHETIC_EBAY_SENTINEL")
    monkeypatch.setenv("PYTHONPATH", str(ROOT / "src"))
    env = ci_smoke.isolated_environment(Path(sys.executable), tmp_path)
    assert "OPENAI_API_KEY" not in env
    assert "EBAY_CLIENT_SECRET" not in env
    assert "PYTHONPATH" not in env
    assert env["HOME"] == str(tmp_path)


def test_child_external_network_is_denied_and_recorded_even_when_caught(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    env = ci_smoke.isolated_environment(Path(sys.executable), home)
    code = """
try:
    socket.getaddrinfo('example.invalid', 443)
except RuntimeError:
    pass
print('completed')
"""
    assert ci_smoke.run_python(Path(sys.executable), code, [], tmp_path, env).strip() == "completed"
    assert (tmp_path / "network-attempts").read_text() == "blocked\n"
