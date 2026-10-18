"""Disposable SQLite roots and fake processes; no sockets or provider transport."""

import hashlib
import json
import signal
import sqlite3
import subprocess
from dataclasses import replace

import pytest

from pokemon_hunter.beta.hunter_transition import (
    HandbackRequired,
    LocalProcessAdapter,
    RuntimeTransitionAuthorization,
    TransitionPlan,
    TransitionRefused,
    file_digest,
    retry_handback,
    run_transition,
    schema_digest,
)


class FakeProcesses(LocalProcessAdapter):
    def __init__(self, plan, verify_identity=lambda: None):
        super().__init__(plan, verify_identity)
        self.active = "shop"
        self.events = []
        self.fail_candidate_start = False
        self.fail_shop_start = False
        self.fail_phase = None
        self.starts = {"shop": 0, "candidate": 0}

    def _compatible_shop_runtime(self):
        self.events.append("saved-runtime-read-only-check")

    def _processes(self, argv):
        kind = "shop" if tuple(argv) == self.plan.shop_argv else "candidate"
        return [101 if kind == "shop" else 102] if self.active == kind else []

    def _listener(self):
        return {"shop": 101, "candidate": 102, None: None, "other": 999}[self.active]

    def _stop(self, argv):
        kind = "shop" if tuple(argv) == self.plan.shop_argv else "candidate"
        self.events.append("stop-" + kind)
        if self.active == kind:
            self.active = None

    def _spawn(self, argv):
        assert self.active is None, "Two ordinary servers are forbidden"
        kind = "shop" if tuple(argv) == self.plan.shop_argv else "candidate"
        self.events.append("start-" + kind)
        self.starts[kind] += 1
        self.active = kind
        if (kind == "candidate" and self.fail_candidate_start) or (kind == "shop" and self.fail_shop_start):
            raise RuntimeError("Simulated process failure")

    def record(self, phase):
        super().record(phase)
        self.events.append(phase)
        if self.fail_phase == phase:
            self.fail_phase = None
            raise KeyboardInterrupt

    def backup(self):
        self.events.append("backup-root")
        return super().backup()


@pytest.fixture
def transition(tmp_path):
    root = tmp_path / "disposable-root"
    root.mkdir()
    with sqlite3.connect(root / "inventory.db") as db:
        db.executescript(
            "CREATE TABLE auth_sessions(id TEXT PRIMARY KEY,value TEXT);"
            "CREATE TABLE collection(id TEXT PRIMARY KEY,value TEXT);"
            "CREATE TABLE goals(id TEXT PRIMARY KEY,value TEXT);"
            "INSERT INTO collection VALUES('copy','retained');"
            "INSERT INTO goals VALUES('goal','retained');"
        )
    (root / "secret.key").write_text("disposable-private-secret")
    (root / "configuration.json").write_text('{"mode":"existing"}')
    (root / "photos").mkdir()
    (root / "photos" / "owned.jpg").write_bytes(b"controlled-image")
    for name in ("price-snapshots", "provider-cache", "hunter-results"):
        (root / name).mkdir()
        (root / name / "excluded.json").write_text('"temporary-provider-content"')
    sibling = tmp_path / ".dex-shopping-discovery"
    sibling.mkdir()
    (sibling / "attempts.jsonl").write_text('{"consumed":1}\n')
    revocations = tmp_path / ".dex-price-revocations"
    revocations.mkdir()
    (revocations / "source.json").write_text('{"revoked":true}')
    python = tmp_path / "shop-python"
    python.write_bytes(b"retained-shop-runtime")
    helper = tmp_path / "start-dex.py"
    helper.write_bytes(b"retained-startup-helper")
    candidate = tmp_path / "candidate-python"
    candidate.write_bytes(b"qualified-candidate-runtime")
    plan = TransitionPlan(
        root=root,
        candidate_argv=(str(candidate), "-I", "-m", "qualified.profile", "--root", str(root)),
        shop_python=python,
        startup_helper=helper,
        helper_sha256=file_digest(helper),
        shop_python_sha256=file_digest(python),
        identity_digest=hashlib.sha256(b"frozen-execution-identity").hexdigest(),
        schema_digest=schema_digest(root),
    )
    return plan, RuntimeTransitionAuthorization(plan.identity_digest, True), FakeProcesses(plan)


def _rows(root, table):
    with sqlite3.connect(root / "inventory.db") as db:
        return db.execute("SELECT * FROM " + table).fetchall()


def test_completion_uses_latest_database_and_current_independent_journals(transition):
    plan, auth, adapter = transition
    helper = plan.startup_helper.read_bytes()
    runtime = plan.shop_python.read_bytes()
    config = (plan.root / "configuration.json").read_bytes()
    photo = (plan.root / "photos" / "owned.jpg").read_bytes()
    ledger = plan.root.parent / ".dex-shopping-discovery" / "attempts.jsonl"
    revocation = plan.root.parent / ".dex-price-revocations" / "source.json"

    def permitted_session(_):
        assert adapter.active == "candidate"
        with sqlite3.connect(plan.root / "inventory.db") as db:
            db.execute("INSERT INTO auth_sessions VALUES('new-session','latest')")
        ledger.write_text('{"consumed":2,"uncertain":true}\n')
        revocation.write_text('{"revoked":true,"new":true}')
        (plan.root / "price-snapshots" / "excluded.json").unlink()  # Required withdrawal/expiry.

    result = run_transition(plan, auth, adapter, permitted_session)
    assert result.handed_back and result.completed
    assert _rows(plan.root, "auth_sessions") == [("new-session", "latest")]
    assert _rows(plan.root, "collection") == [("copy", "retained")]
    assert _rows(plan.root, "goals") == [("goal", "retained")]
    assert ledger.read_text() == '{"consumed":2,"uncertain":true}\n'
    assert revocation.read_text() == '{"revoked":true,"new":true}'
    assert not (plan.root / "price-snapshots" / "excluded.json").exists()
    assert plan.startup_helper.read_bytes() == helper
    assert plan.shop_python.read_bytes() == runtime
    assert (plan.root / "configuration.json").read_bytes() == config
    assert (plan.root / "photos" / "owned.jpg").read_bytes() == photo
    assert adapter.active == "shop"
    assert adapter.starts == {"shop": 1, "candidate": 1}
    assert not adapter.marker.exists()
    backups = list(adapter.backup_parent.iterdir())
    assert len(backups) == 1
    assert _rows(backups[0], "auth_sessions") == []  # Old backup never overlaid.
    assert (backups[0] / "photos" / "owned.jpg").read_bytes() == photo
    assert (backups[0] / "secret.key").read_text() == "disposable-private-secret"
    assert (backups[0] / "saved-startup-helper.py").read_bytes() == helper
    assert not any(
        p.name in {"price-snapshots", "provider-cache", "hunter-results"} for p in backups[0].rglob("*")
    )
    assert not any(
        ".dex-shopping-discovery" in str(p) or ".dex-price-revocations" in str(p)
        for p in backups[0].rglob("*")
    )


@pytest.mark.parametrize("authorization", [None, False, RuntimeTransitionAuthorization("wrong", True)])
def test_runtime_authorization_precedes_all_mutation(transition, authorization):
    plan, _, adapter = transition
    with pytest.raises(TransitionRefused, match="runtime-transition"):
        run_transition(plan, authorization, adapter, lambda _: pytest.fail("session ran"))
    assert adapter.events == []
    assert not adapter.control.exists()
    assert not adapter.backup_parent.exists()


def test_provider_permission_is_not_runtime_selection(transition):
    plan, _, adapter = transition
    provider_only = RuntimeTransitionAuthorization(plan.identity_digest)
    with pytest.raises(TransitionRefused, match="runtime-transition"):
        run_transition(plan, provider_only, adapter, lambda _: None)
    assert adapter.events == []


@pytest.mark.parametrize("port", [0, 8012, 8000])
def test_wrong_port_refuses_before_side_effects(transition, port):
    plan, auth, adapter = transition
    with pytest.raises(TransitionRefused, match="origin"):
        run_transition(replace(plan, port=port), auth, adapter, lambda _: None)
    assert not adapter.control.exists()
    assert adapter.events == []


def test_noncanonical_root_refuses_before_side_effects(transition, tmp_path):
    plan, auth, adapter = transition
    alias = tmp_path / "root-alias"
    alias.symlink_to(plan.root)
    with pytest.raises(TransitionRefused, match="Canonical"):
        run_transition(replace(plan, root=alias), auth, adapter, lambda _: None)
    assert adapter.events == []


@pytest.mark.parametrize("changed", ["helper", "runtime", "schema"])
def test_pointer_schema_mismatch_refuses_without_backup_or_stop(transition, changed):
    plan, auth, adapter = transition
    if changed == "helper":
        plan.startup_helper.write_bytes(b"unexpected-helper")
    elif changed == "runtime":
        plan.shop_python.write_bytes(b"unexpected-runtime")
    else:
        with sqlite3.connect(plan.root / "inventory.db") as db:
            db.execute("CREATE TABLE unexpected(id TEXT)")
    with pytest.raises(TransitionRefused):
        run_transition(plan, auth, adapter, lambda _: None)
    assert adapter.events == []
    assert not adapter.marker.exists()


@pytest.mark.parametrize("mismatch", ["root", "account", "profile", "wheel", "launcher", "ledger"])
def test_trusted_verifier_refusal_precedes_runtime_effects(transition, mismatch):
    plan, auth, _ = transition

    def refuse():
        raise TransitionRefused("Frozen " + mismatch + " mismatch")

    adapter = FakeProcesses(plan, refuse)
    with pytest.raises(TransitionRefused, match=mismatch):
        run_transition(plan, auth, adapter, lambda _: None)
    assert adapter.events == []
    assert not adapter.control.exists()


def test_startup_failure_returns_to_latest_shop(transition):
    plan, auth, adapter = transition
    adapter.fail_candidate_start = True
    with pytest.raises(RuntimeError, match="Simulated"):
        run_transition(plan, auth, adapter, lambda _: pytest.fail("session ran"))
    assert adapter.active == "shop"
    assert not adapter.marker.exists()
    assert adapter.starts == {"shop": 1, "candidate": 1}


@pytest.mark.parametrize("error", [RuntimeError("acquisition failed"), KeyboardInterrupt()])
def test_acquisition_failure_or_stop_keeps_consumed_attempts_and_hands_back(transition, error):
    plan, auth, adapter = transition
    ledger = plan.root.parent / ".dex-shopping-discovery" / "attempts.jsonl"

    def interrupted(_):
        ledger.write_text('{"consumed":2,"uncertain":true}\n')
        with sqlite3.connect(plan.root / "inventory.db") as db:
            db.execute("INSERT INTO auth_sessions VALUES('latest','retained')")
        raise error

    with pytest.raises(type(error)):
        run_transition(plan, auth, adapter, interrupted)
    assert adapter.active == "shop"
    assert _rows(plan.root, "auth_sessions") == [("latest", "retained")]
    assert json.loads(ledger.read_text())["consumed"] == 2
    assert not adapter.marker.exists()


def test_interrupted_handback_is_resumable_without_reacquisition_or_repeat_backup(transition):
    plan, auth, adapter = transition
    adapter.fail_phase = "shop-starting"
    with pytest.raises(HandbackRequired):
        run_transition(plan, auth, adapter, lambda _: None)
    assert adapter.marker.exists()
    assert adapter.active is None
    assert adapter.starts["candidate"] == 1
    assert adapter.events.count("backup-root") == 1
    result = retry_handback(plan, auth, adapter)
    assert result.handed_back and not result.completed
    assert adapter.active == "shop"
    assert adapter.starts == {"candidate": 1, "shop": 1}
    assert adapter.events.count("backup-root") == 1
    assert not adapter.marker.exists()


def test_retry_does_not_duplicate_shop_started_before_interruption(transition):
    plan, auth, adapter = transition
    adapter.fail_shop_start = True
    with pytest.raises(HandbackRequired):
        run_transition(plan, auth, adapter, lambda _: None)
    assert adapter.active == "shop"
    assert adapter.marker.exists()
    adapter.fail_shop_start = False
    retry_handback(plan, auth, adapter)
    assert adapter.starts == {"candidate": 1, "shop": 1}
    assert not adapter.marker.exists()


def test_incompatible_latest_schema_requires_forward_repair_never_restore(transition):
    plan, auth, adapter = transition

    def changed_schema(_):
        with sqlite3.connect(plan.root / "inventory.db") as db:
            db.execute("CREATE TABLE new_state(id TEXT)")
            db.execute("INSERT INTO auth_sessions VALUES('latest','preserved')")

    with pytest.raises(HandbackRequired):
        run_transition(plan, auth, adapter, changed_schema)
    assert adapter.marker.exists()
    assert adapter.active is None
    assert _rows(plan.root, "auth_sessions") == [("latest", "preserved")]
    with pytest.raises(HandbackRequired):
        retry_handback(plan, auth, adapter)
    assert _rows(plan.root, "auth_sessions") == [("latest", "preserved")]
    assert adapter.starts["shop"] == 0


def test_pending_transition_refuses_new_session(transition):
    plan, auth, adapter = transition
    with adapter.lock():
        adapter.record("candidate-stopping")
    with pytest.raises(TransitionRefused, match="handback-only"):
        run_transition(plan, auth, adapter, lambda _: None)
    assert adapter.active == "shop"
    assert "stop-shop" not in adapter.events


def test_other_listener_refuses_without_stopping_any_process(transition):
    plan, auth, adapter = transition
    adapter.active = "other"
    with pytest.raises(TransitionRefused):
        run_transition(plan, auth, adapter, lambda _: None)
    assert adapter.events == []


def test_backup_refuses_symlink_and_handback_still_succeeds(transition, tmp_path):
    plan, auth, adapter = transition
    external = tmp_path / "external-private-file"
    external.write_bytes(b"must-not-copy")
    (plan.root / "linked-private-file").symlink_to(external)
    with pytest.raises(TransitionRefused, match="symlinks"):
        run_transition(plan, auth, adapter, lambda _: None)
    assert adapter.active == "shop"
    assert adapter.starts["candidate"] == 0
    assert not any(p.name == "linked-private-file" for p in adapter.backup_parent.rglob("*"))


def test_pending_marker_is_content_free(transition):
    plan, auth, adapter = transition
    adapter.fail_phase = "shop-starting"
    with pytest.raises(HandbackRequired):
        run_transition(plan, auth, adapter, lambda _: None)
    value = json.loads(adapter.marker.read_text())
    assert set(value) == {"identity_digest", "phase"}
    assert "disposable-private-secret" not in adapter.marker.read_text()
    assert str(plan.root) not in adapter.marker.read_text()


def test_sigterm_runs_normal_handback_and_restores_signal_handler(transition):
    plan, auth, adapter = transition
    original = signal.getsignal(signal.SIGTERM)

    def stopped(_):
        current = signal.getsignal(signal.SIGTERM)
        assert callable(current)
        current(signal.SIGTERM, None)

    with pytest.raises(KeyboardInterrupt):
        run_transition(plan, auth, adapter, stopped)
    assert adapter.active == "shop"
    assert not adapter.marker.exists()
    assert signal.getsignal(signal.SIGTERM) == original


def test_mismatched_adapter_plan_refuses_before_mutation(transition):
    plan, auth, adapter = transition
    changed = replace(plan, identity_digest="different-frozen-identity")
    changed_auth = RuntimeTransitionAuthorization(changed.identity_digest, True)
    with pytest.raises(TransitionRefused, match="Adapter"):
        run_transition(changed, changed_auth, adapter, lambda _: None)
    assert adapter.events == []
    assert not adapter.control.exists()


def test_concrete_saved_runtime_check_is_read_only_no_serve_or_migrate(transition, monkeypatch):
    plan, _, _ = transition
    adapter = LocalProcessAdapter(plan, lambda: None)
    calls = []

    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(subprocess, "run", run)
    adapter._compatible_shop_runtime()
    assert len(calls) == 1
    argv, options = calls[0]
    assert argv[:4] == [str(plan.shop_python), "-I", "-B", "-c"]
    assert argv[-1] == str(plan.root)
    script = argv[4]
    assert "?mode=ro" in script
    assert 'call_command("check"' in script
    assert "migration_plan" in script
    assert 'call_command("migrate"' not in script
    assert "serve" not in script
    assert options["stdout"] == subprocess.DEVNULL
    assert options["stderr"] == subprocess.DEVNULL
    assert options["timeout"] == adapter.timeout


@pytest.mark.parametrize("result", ["error", "timeout", "nonzero"])
def test_concrete_compatibility_failure_is_fixed_and_content_free(transition, monkeypatch, result):
    plan, _, _ = transition
    adapter = LocalProcessAdapter(plan, lambda: None)

    def run(argv, **kwargs):
        if result == "error":
            raise OSError("PRIVATE_INPUT_MUST_NOT_LEAK")
        if result == "timeout":
            raise subprocess.TimeoutExpired("PRIVATE_INPUT_MUST_NOT_LEAK", 1)
        return subprocess.CompletedProcess(argv, 1)

    monkeypatch.setattr(subprocess, "run", run)
    with pytest.raises(TransitionRefused) as caught:
        adapter._compatible_shop_runtime()
    assert str(caught.value) == "Saved runtime read-only compatibility check failed"


def test_concrete_listener_rejects_another_origin_and_multiple_servers(transition, monkeypatch):
    plan, _, _ = transition
    adapter = LocalProcessAdapter(plan, lambda: None)
    responses = iter(
        [
            "p101\nfcwd\nn127.0.0.1:8011\n",
            "p101\nn*:8011\n",
            "p101\nn127.0.0.1:8011\np102\nn127.0.0.1:8011\n",
        ]
    )
    monkeypatch.setattr(
        subprocess, "run", lambda argv, **kwargs: subprocess.CompletedProcess(argv, 0, stdout=next(responses))
    )
    assert adapter._listener() == 101
    with pytest.raises(TransitionRefused, match="unexpected listener"):
        adapter._listener()
    with pytest.raises(TransitionRefused, match="unexpected listener"):
        adapter._listener()


def test_concrete_process_match_requires_exact_runtime_root_and_argv(transition, monkeypatch):
    plan, _, _ = transition
    adapter = LocalProcessAdapter(plan, lambda: None)
    wrong_root = list(plan.shop_argv)
    wrong_root[-2] = "/another-root"
    output = "\n".join(
        [
            "101 " + " ".join(plan.shop_argv),
            "102 " + " ".join(wrong_root),
            "103 /another-python " + " ".join(plan.shop_argv[1:]),
        ]
    )
    monkeypatch.setattr(
        subprocess, "run", lambda argv, **kwargs: subprocess.CompletedProcess(argv, 0, stdout=output)
    )
    assert adapter._processes(plan.shop_argv) == [101]
    assert adapter._processes(plan.candidate_argv) == []


@pytest.mark.parametrize("location", ["control-parent", "control", "lock", "marker", "backup-parent"])
def test_transition_symlink_refuses_without_touching_unrelated_target(transition, tmp_path, location):
    plan, auth, adapter = transition
    target = tmp_path / "unrelated-target"
    target.mkdir(mode=0o700)
    protected = target / "protected.txt"
    protected.write_bytes(b"retained-unrelated-private-state")
    protected.chmod(0o600)
    if location == "control-parent":
        adapter.control.parent.symlink_to(target, target_is_directory=True)
    elif location == "control":
        adapter.control.parent.mkdir(mode=0o700)
        adapter.control.symlink_to(target, target_is_directory=True)
    elif location in {"lock", "marker"}:
        adapter.control.mkdir(parents=True, mode=0o700)
        adapter.control.parent.chmod(0o700)
        (adapter.control / ("operator.lock" if location == "lock" else "pending.json")).symlink_to(protected)
    else:
        adapter.backup_parent.parent.mkdir(mode=0o700)
        adapter.backup_parent.symlink_to(target, target_is_directory=True)
    with pytest.raises((TransitionRefused, HandbackRequired)):
        run_transition(plan, auth, adapter, lambda _: None)
    assert protected.read_bytes() == b"retained-unrelated-private-state"
    assert list(target.iterdir()) == [protected]
    assert adapter.starts["candidate"] == 0


def test_old_pending_tmp_symlink_cannot_be_followed(transition, tmp_path):
    plan, auth, adapter = transition
    target = tmp_path / "private-unrelated-file"
    target.write_bytes(b"retained")
    with adapter.lock():
        (adapter.control / "pending.tmp").symlink_to(target)
    result = run_transition(plan, auth, adapter, lambda _: None)
    assert result.handed_back
    assert target.read_bytes() == b"retained"
    assert (adapter.control / "pending.tmp").is_symlink()


def test_handback_uses_independent_identity_verifier(transition):
    plan, auth, adapter = transition
    calls = []
    adapter.verify_identity = lambda: calls.append("normal")
    adapter.verify_handback_identity = lambda: calls.append("handback")
    run_transition(plan, auth, adapter, lambda _: None)
    assert "normal" in calls and "handback" in calls
    assert calls[-1] == "handback"


@pytest.mark.parametrize("contents", ["[]", "null", "{}", "not-json", '"' + "x" * 5000 + '"'])
def test_corrupt_pending_marker_refuses_without_server_mutation(transition, contents):
    plan, auth, adapter = transition
    with adapter.lock():
        adapter.marker.write_text(contents)
        adapter.marker.chmod(0o600)
    adapter.events.clear()
    with pytest.raises(TransitionRefused):
        run_transition(plan, auth, adapter, lambda _: None)
    assert adapter.active == "shop"
    assert "stop-shop" not in adapter.events
    assert "backup-root" not in adapter.events
