"""Trusted execution refusal tests: disposable roots, no startup or provider IO."""

import hashlib
import json
import sqlite3
import sys
import zipfile
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from pokemon_hunter.beta import hunter_operator as operator
from pokemon_hunter.beta import hunter_profile


@pytest.fixture
def boundary(tmp_path, monkeypatch):
    for key in (
        "DEX_PROFILE",
        "DJANGO_SETTINGS_MODULE",
        "DATABASE_URL",
        "EBAY_CLIENT_ID",
        "EBAY_CLIENT_SECRET",
        "EBAY_DELIVERY_POSTAL_CODE",
    ):
        monkeypatch.delenv(key, raising=False)
    root = tmp_path / "fixture"
    root.mkdir(mode=0o700)
    for name in ("SYNTHETIC_ONLY", "B1_ISOLATED", "B2_ISOLATED", "secret.key"):
        (root / name).write_text("engineering-only")
        (root / name).chmod(0o600)
    with sqlite3.connect(root / "inventory.db") as db:
        for table, columns in operator.REQUIRED.items():
            db.execute(
                'CREATE TABLE "'
                + table
                + '"('
                + ",".join('"' + column + '"' for column in sorted(columns))
                + ")"
            )
        db.execute(
            "INSERT INTO users(id,auth_subject,role,state) VALUES('fixture-owner','1','owner','active')"
        )
        db.execute("INSERT INTO auth_user(id,is_active) VALUES('1',1)")
    wheel = tmp_path / "candidate.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("pokemon_hunter/__init__.py", b"")
    helper = tmp_path / "helper.py"
    helper.write_text("# unchanged engineering startup pointer\n")
    plan = tmp_path / "plan.md"
    plan.write_text("unchanged engineering plan\n")
    launcher = Path(__file__).resolve().parents[1] / "scripts/hunter_boundary.py"
    ledger = (
        root.parent
        / ".dex-shopping-discovery"
        / hashlib.sha256(str(root).encode()).hexdigest()
        / (operator.PLAN_ID + ".jsonl")
    )
    value = dict(
        schema="dex-hunter-execution-v1",
        kind="engineering",
        profile=operator.PROFILE,
        root=str(root),
        host=operator.HOST,
        port=operator.PORT,
        account_sha256=hashlib.sha256(
            operator.canonical(("fixture-owner", "1", "owner", "active"))
        ).hexdigest(),
        schema_sha256=operator.schema_identity(root)[0],
        python=str(Path(sys.executable).absolute()),
        wheel=str(wheel),
        wheel_sha256=operator.digest(wheel),
        package_hashes={"pokemon_hunter/__init__.py": hashlib.sha256(b"").hexdigest()},
        dependencies={"engineering": "1"},
        dependency_tree_sha256="fixture-dependencies",
        runtime_trees={str(Path(sys.executable).absolute().parent.parent): "fixture-runtime"},
        bound_files={
            str(root / name): operator.digest(root / name)
            for name in ("B1_ISOLATED", "B2_ISOLATED", "secret.key")
        },
        launcher=str(launcher),
        launcher_sha256=operator.digest(launcher),
        profile_sha256=operator.digest(Path(hunter_profile.__file__)),
        plan=dict(
            id=operator.PLAN_ID,
            limits=operator.LIMITS,
            ledger=str(ledger),
            document=str(plan),
            sha256=operator.digest(plan),
        ),
        handback=dict(
            python=str(Path(sys.executable).absolute()),
            python_sha256=operator.digest(sys.executable),
            helper=str(helper),
            helper_sha256=operator.digest(helper),
        ),
        configuration_root=str(root),
        allowed_actions=list(hunter_profile.ALLOWED_ACTIONS),
        allowed_workers=list(hunter_profile.ALLOWED_WORKERS),
        expected_writes=list(hunter_profile.EXPECTED_WRITES),
    )
    identity = tmp_path / "identity.json"
    monkeypatch.setattr(operator, "installed_identity", lambda *args: None)
    monkeypatch.setattr(operator, "dependency_tree_identity", lambda: "fixture-dependencies")
    monkeypatch.setattr(operator, "runtime_tree_identity", lambda root: "fixture-runtime")

    def save(candidate=value):
        identity.write_text(json.dumps(candidate))
        return identity, operator.digest(identity)

    return root, value, save, ledger


def test_preflight_is_read_only_and_does_not_activate_capacity(boundary):
    from pokemon_hunter.beta import hunter_budget

    root, value, save, ledger = boundary
    before = {str(path): operator.digest(path) for path in root.rglob("*") if path.is_file()}
    result, account = operator.preflight(*save())
    assert result == value and account == "fixture-owner"
    assert before == {str(path): operator.digest(path) for path in root.rglob("*") if path.is_file()}
    assert hunter_budget.TRAVERSAL_ALLOWANCE is None
    assert not ledger.parent.exists()


@pytest.mark.parametrize(
    "field,wrong",
    [
        ("root", "/tmp"),
        ("account_sha256", "wrong"),
        ("port", 8012),
        ("port", True),
        ("host", "localhost"),
        ("profile", "ordinary"),
        ("wheel_sha256", "wrong"),
        ("launcher_sha256", "wrong"),
        ("profile_sha256", "wrong"),
        ("schema_sha256", "wrong"),
        ("python", "/unselected/python"),
        ("allowed_actions", ["bulk_save"]),
        ("allowed_workers", ["recognition"]),
        ("expected_writes", ["owned_copies"]),
        ("dependency_tree_sha256", "wrong"),
    ],
)
def test_mismatched_identity_refuses_without_capacity(boundary, field, wrong):
    root, value, save, ledger = boundary
    candidate = deepcopy(value)
    candidate[field] = wrong
    before = operator.digest(root / "inventory.db")
    with pytest.raises((operator.Refusal, FileNotFoundError)):
        operator.preflight(*save(candidate))
    assert operator.digest(root / "inventory.db") == before
    assert not ledger.parent.exists()


@pytest.mark.parametrize(
    "change",
    [
        "ledger",
        "id",
        "limits",
        "bool_limit",
        "plan_file",
        "helper",
        "config",
        "environment",
        "consumed_ledger",
    ],
)
def test_wrong_trusted_binding_refuses(boundary, change, monkeypatch):
    root, value, save, ledger = boundary
    if change == "ledger":
        value["plan"]["ledger"] += "-other"
    elif change == "id":
        value["plan"]["id"] = "hunt-04-replacement"
    elif change == "limits":
        value["plan"]["limits"] = dict(operator.LIMITS, browse=13)
    elif change == "bool_limit":
        value["plan"]["limits"] = dict(operator.LIMITS, oauth=True)
    elif change == "plan_file":
        Path(value["plan"]["document"]).write_text("changed")
    elif change == "helper":
        Path(value["handback"]["helper"]).write_text("changed")
    elif change == "config":
        (root / ".env").write_text("FIXTURE=unbound")
    elif change == "environment":
        monkeypatch.setenv("EBAY_CLIENT_ID", "unbound-fixture")
    else:
        ledger.parent.mkdir(parents=True)
        ledger.write_text('{"allowance":"wrong"}\n')
    with pytest.raises((operator.Refusal, ValueError)):
        operator.preflight(*save())


@pytest.mark.parametrize("change", ["table", "column"])
def test_incompatible_minimum_schema_refuses_even_with_rebound_digest(boundary, change):
    root, value, save, ledger = boundary
    with sqlite3.connect(root / "inventory.db") as db:
        if change == "table":
            db.execute("DROP TABLE owned_copies")
        else:
            db.execute("ALTER TABLE collection_generations RENAME COLUMN value TO unselected")
    with pytest.raises(operator.Refusal, match="minimum schema"):
        operator.preflight(*save())
    assert not ledger.parent.exists()


def test_wrong_document_digest_refuses_before_sqlite_or_package(boundary, monkeypatch):
    _, _, save, _ = boundary
    path, _ = save()
    monkeypatch.setattr(operator, "schema_identity", lambda *args: pytest.fail("unexpected schema access"))
    with pytest.raises(operator.Refusal, match="identity changed"):
        operator.preflight(path, "wrong")


def test_revoked_account_and_corrupt_ledger_do_not_prevent_handback_validation(boundary):
    root, _, save, ledger = boundary
    with sqlite3.connect(root / "inventory.db") as db:
        db.execute("UPDATE users SET state='revoked'")
    ledger.parent.mkdir(parents=True)
    ledger.write_text("uncertain-corrupt-fixture")
    value, account = operator.preflight(*save(), handback=True)
    assert account is None and value["root"] == str(root)
    assert ledger.read_text() == "uncertain-corrupt-fixture"


@pytest.mark.parametrize(
    "runtime,provider,accepted",
    [(False, False, False), (False, True, False), (True, False, False), (True, True, True)],
)
def test_runtime_and_finite_provider_authority_are_independent(tmp_path, runtime, provider, accepted):
    path = tmp_path / "simulated-only.json"
    value = dict(
        schema="dex-hunter-authorization-v1",
        execution_sha256="exact",
        runtime_transition=runtime,
        provider_plan=dict(id=operator.PLAN_ID, sha256="plan", selected=True) if provider else None,
        expires_at=(datetime.now(UTC) + timedelta(minutes=30)).isoformat(),
    )
    path.write_text(json.dumps(value))
    path.chmod(0o600)
    if accepted:
        assert operator.authorization(path, "exact", "plan")
    else:
        with pytest.raises(operator.Refusal):
            operator.authorization(path, "exact", "plan")


@pytest.mark.parametrize("change", ["identity", "plan", "expired", "mode", "symlink", "missing"])
def test_invalid_authorization_refuses(tmp_path, change):
    path = tmp_path / "simulated-only.json"
    value = dict(
        schema="dex-hunter-authorization-v1",
        execution_sha256="exact",
        runtime_transition=True,
        provider_plan=dict(id=operator.PLAN_ID, sha256="plan", selected=True),
        expires_at=(datetime.now(UTC) + timedelta(minutes=30)).isoformat(),
    )
    if change == "identity":
        value["execution_sha256"] = "wrong"
    elif change == "plan":
        value["provider_plan"]["sha256"] = "wrong"
    elif change == "expired":
        value["expires_at"] = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()
    path.write_text(json.dumps(value))
    path.chmod(0o644 if change == "mode" else 0o600)
    if change == "symlink":
        link = tmp_path / "link"
        link.symlink_to(path)
        path = link
    elif change == "missing":
        path.unlink()
    with pytest.raises(operator.Refusal):
        operator.authorization(path, "exact", "plan")
    if change == "expired":
        assert operator.authorization(path, "exact", "plan", handback=True)


def test_dependency_bytes_are_hashed_not_only_version(tmp_path, monkeypatch):
    from types import SimpleNamespace

    member = tmp_path / "dependency.py"
    member.write_text("first")
    dist = SimpleNamespace(
        metadata={"Name": "fixture"}, files=[Path("dependency.py")], locate_file=lambda path: tmp_path / path
    )
    monkeypatch.setattr(operator.importlib.metadata, "distributions", lambda: [dist])
    before = operator.dependency_tree_identity()
    member.write_text("changed")
    assert operator.dependency_tree_identity() != before


def test_engineering_cli_never_activates_real_transport(boundary, monkeypatch):
    _, _, save, _ = boundary
    path, expected = save()
    monkeypatch.setattr(hunter_profile, "configure", lambda *args, **kwargs: pytest.fail("startup reached"))
    with pytest.raises(operator.Refusal, match="fake-transport tests"):
        operator.serve(path, expected, Path("no-authorization"))


def test_direct_candidate_start_requires_transition_marker_before_workers(tmp_path, monkeypatch):
    identity = {"kind": "proposed-production", "root": str(tmp_path), "plan": {"sha256": "plan"}}
    monkeypatch.setattr(operator, "preflight", lambda *args: (identity, "fixture-owner"))
    monkeypatch.setattr(operator, "authorization", lambda *args, **kwargs: True)
    monkeypatch.setattr(hunter_profile, "configure", lambda *args, **kwargs: pytest.fail("startup reached"))
    with pytest.raises(operator.Refusal, match="document is unavailable"):
        operator.serve(Path("fixture"), "exact", Path("simulated-only"))


def test_execute_without_authorization_stops_before_transition(boundary, monkeypatch):
    _, _, save, ledger = boundary
    path, expected = save()
    monkeypatch.setattr(
        sys, "argv", ["operator", "execute", "--identity", str(path), "--expected-identity", expected]
    )
    with pytest.raises(SystemExit, match="authorization is required"):
        operator.main()
    assert not ledger.parent.exists()


@pytest.mark.parametrize("tamper", [None, "init", "operator", "extra", "wheel"])
def test_bootstrap_checks_installed_code_before_import(tmp_path, monkeypatch, tamper):
    import importlib.util

    launcher = Path(__file__).resolve().parents[1] / "scripts/hunter_boundary.py"
    spec = importlib.util.spec_from_file_location("engineering_bootstrap", launcher)
    bootstrap = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bootstrap)
    package = tmp_path / "pokemon_hunter"
    package.mkdir()
    members = {
        "pokemon_hunter/__init__.py": b"# controlled init",
        "pokemon_hunter/operator.py": b"# controlled operator",
    }
    wheel = tmp_path / "candidate.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        for name, content in members.items():
            (tmp_path / name).write_bytes(content)
            archive.writestr(name, content)
    value = dict(
        wheel=str(wheel),
        wheel_sha256=operator.digest(wheel),
        package_hashes={name: hashlib.sha256(content).hexdigest() for name, content in members.items()},
    )
    monkeypatch.setattr(bootstrap.sysconfig, "get_path", lambda name: str(tmp_path))
    if tamper == "init":
        (package / "__init__.py").write_text("raise RuntimeError('must never import')")
    elif tamper == "operator":
        (package / "operator.py").write_text("raise RuntimeError('must never import')")
    elif tamper == "extra":
        (package / "unselected.py").write_text("# unselected code")
    elif tamper == "wheel":
        wheel.write_bytes(b"unqualified")
    if tamper:
        with pytest.raises(ValueError):
            bootstrap.verify_package(value)
    else:
        bootstrap.verify_package(value)
