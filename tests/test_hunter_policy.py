"""Everyday authority uses disposable roots, a controlled clock and no sockets."""

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from django.core.exceptions import PermissionDenied

from pokemon_hunter.beta import hunter as hunter
from pokemon_hunter.beta import hunter_budget as budget
from pokemon_hunter.beta import hunter_installed as installed
from pokemon_hunter.beta import hunter_policy as policy
from pokemon_hunter.beta.discovery_transport import ProviderFailure


@pytest.fixture
def everyday(tmp_path, monkeypatch):
    root = tmp_path / "actual-shaped-disposable"
    root.mkdir(mode=0o700)
    actor = SimpleNamespace(user_id="engineering-owner", role="owner", subject=1)
    clock = SimpleNamespace(now=datetime(2026, 10, 17, 14, 0, tzinfo=UTC))
    monkeypatch.setattr("django.conf.settings", SimpleNamespace(ROOT=root, STAGING=False))
    monkeypatch.setattr(hunter.discovery, "settings", SimpleNamespace(ROOT=root))
    monkeypatch.setattr(policy.store, "verified", lambda who: who)
    monkeypatch.setattr(installed, "package_digest", lambda: "a" * 64)
    monkeypatch.setattr(policy, "_now", lambda: clock.now)
    monkeypatch.setattr(hunter, "_runs", {})
    monkeypatch.setattr(installed, "_configured", None)
    monkeypatch.setattr(budget, "TRAVERSAL_ALLOWANCE", None)
    monkeypatch.setattr(hunter, "_launch", lambda *a: None)
    monkeypatch.setattr(
        hunter.ebay_hunts,
        "configuration",
        lambda: (
            SimpleNamespace(environment="production"),
            dict(EBAY_CLIENT_ID="fixture-client", EBAY_CLIENT_SECRET="fixture-secret"),
        ),
    )
    env = SimpleNamespace(root=root, actor=actor, clock=clock, monkeypatch=monkeypatch)

    def choose(**changes):
        status = policy.status(actor)
        selected = dict(
            enabled=True,
            per_hunt_limit=15,
            daily_limit=10,
            timezone="America/New_York",
            recurring=True,
            expires_at=None,
            revision=status["revision"],
        )
        selected.update(changes)
        return policy.select(actor, selected)

    def parent(key="parent"):
        run = hunter.Run(
            key,
            (str(root), actor.user_id, "session"),
            hunter.discovery.Choices(),
            None,
            [],
            allowance=installed.current_allowance(actor),
        )
        policy.bind(run, actor)
        hunter._runs[key] = run
        return run

    def consume(run, index, *, stage="browse", scope="singles", lane="auction"):
        budget.consume_traversal(
            root,
            run.id,
            stage,
            lane if stage == "browse" else None,
            dispatch_id=str(index),
            allowance=run.allowance,
            scope=scope,
        )

    env.choose, env.parent, env.consume = choose, parent, consume
    return env


def test_absence_is_disabled_and_reads_create_nothing(everyday):
    e = everyday
    before = list(e.root.parent.rglob("*"))
    state = policy.status(e.actor)
    assert state["configured"] is False and state["remaining"] == 0
    assert state["daily_limit"] is None and state["per_hunt_limit"] is None
    assert installed.current_allowance(e.actor) is None
    assert list(e.root.parent.rglob("*")) == before


@pytest.mark.parametrize(
    "changes",
    [
        {"per_hunt_limit": True},
        {"per_hunt_limit": 0},
        {"per_hunt_limit": 16},
        {"daily_limit": False},
        {"daily_limit": 0},
        {"daily_limit": 1001},
        {"enabled": 1},
        {"recurring": "yes"},
        {"timezone": "not/a-zone"},
        {"expires_at": "2026-10-16T00:00:00+00:00"},
        {"expires_at": "2028-01-01T00:00:00"},
        {"revision": True},
        {"root": "/arbitrary"},
        {"account_id": "another"},
        {"provider_url": "https://invalid.example"},
        {"budget": 100},
    ],
)
def test_explicit_strict_settings_cannot_override_service_boundaries(everyday, changes):
    with pytest.raises((ValueError, TypeError)):
        everyday.choose(**changes)
    assert not policy.present(everyday.root)


def test_only_authenticated_active_owner_can_select_or_read(everyday):
    e = everyday
    member = SimpleNamespace(user_id=e.actor.user_id, role="member", subject=1)
    with pytest.raises(PermissionDenied):
        policy.status(member)
    selected = dict(
        enabled=True,
        per_hunt_limit=3,
        daily_limit=5,
        timezone="UTC",
        recurring=False,
        expires_at=None,
        revision=0,
    )
    with pytest.raises(PermissionDenied):
        policy.select(member, selected)
    e.monkeypatch.setattr(policy.store, "verified", lambda who: (_ for _ in ()).throw(PermissionDenied()))
    with pytest.raises(PermissionDenied):
        policy.select(e.actor, selected)
    assert not policy.present(e.root)


def test_successive_independent_hunts_capture_limits_and_preserve_journal(everyday):
    e = everyday
    assert e.choose(per_hunt_limit=3, daily_limit=7)["remaining"] == 7
    first = e.parent("first")
    e.consume(first, "oauth", stage="oauth")
    e.consume(first, "page-one")
    e.consume(first, "page-two", lane="buy_it_now")
    prefix = (policy._storage(e.root) / policy.JOURNAL_NAME).read_bytes()
    with pytest.raises(ProviderFailure):
        e.consume(first, "overflow")
    second = e.parent("second")
    assert second.allowance.parent_id != first.allowance.parent_id
    e.consume(second, "page")
    assert policy.status(e.actor)["used"] == 4
    assert policy.status(e.actor)["remaining"] == 3
    assert (policy._storage(e.root) / policy.JOURNAL_NAME).read_bytes().startswith(prefix)
    assert budget.remaining_traversal(e.root, first.allowance)["total"] == 0
    assert budget.remaining_traversal(e.root, second.allowance)["total"] == 2


def test_actual_start_allows_two_concurrent_parents_and_rejects_raw_budgets(everyday):
    e = everyday
    e.choose(per_hunt_limit=3, daily_limit=6)
    first = hunter.start(e.actor, "session", dict(scope="singles"))
    second = hunter.start(e.actor, "session", dict(scope="both"))
    assert first["run_id"] != second["run_id"]
    assert hunter._runs[first["run_id"]].cancel.is_set() is False
    assert hunter._runs[first["run_id"]].window is not hunter._runs[second["run_id"]].window
    with pytest.raises(ValueError):
        hunter.start(e.actor, "session", dict(scope="both", daily_limit=100))


def test_concurrent_shared_hunt_continue_and_detail_admissions_are_atomic(everyday):
    e = everyday
    e.choose(per_hunt_limit=15, daily_limit=4)
    parents = [e.parent(str(i)) for i in range(12)]
    barrier = threading.Barrier(len(parents))

    def send(index):
        barrier.wait()
        try:
            e.consume(
                parents[index],
                index,
                stage="detail" if index % 3 == 0 else "browse",
                scope="lots" if index % 3 == 0 else "singles",
            )
            return True
        except ProviderFailure:
            return False

    with ThreadPoolExecutor(max_workers=len(parents)) as executor:
        result = list(executor.map(send, range(len(parents))))
    assert sum(result) == 4
    state = policy.status(e.actor)
    assert state["used"] == 4 and state["remaining"] == 0
    assert state["acquisition_available"] is False
    assert installed.current_allowance(e.actor) is None


def test_duplicate_transport_failed_uncertain_and_stopped_operations_never_refund(everyday):
    e = everyday
    e.choose(daily_limit=5)
    parent = e.parent()
    e.consume(parent, "uncertain")
    with pytest.raises(ProviderFailure):
        e.consume(parent, "uncertain")
    e.consume(parent, "failed", stage="detail", scope="lots")
    e.consume(parent, "stopped", lane="buy_it_now")
    parent.cancel.set()
    parent.state = "stopped"
    before = (policy._storage(e.root) / policy.JOURNAL_NAME).read_bytes()
    assert policy.status(e.actor)["used"] == 3
    assert (policy._storage(e.root) / policy.JOURNAL_NAME).read_bytes() == before
    for value in ("fixture-secret", "TOKEN", "title", "provider_url"):
        assert value.encode() not in before


def test_restart_has_same_capacity_and_historical_ledgers_stay_untouched(everyday):
    e = everyday
    legacy = budget.path(e.root)
    legacy.parent.mkdir(mode=0o700, parents=True)
    legacy.write_bytes(b"historical-consumed-prefix\n")
    historical = legacy.read_bytes()
    e.choose(daily_limit=3)
    first = e.parent("first")
    e.consume(first, 1)
    hunter._runs.clear()
    installed._configured = None
    second = e.parent("after-restart")
    e.consume(second, 2)
    assert policy.status(e.actor)["used"] == 2
    assert legacy.read_bytes() == historical


def test_pause_withdrawal_and_reduced_limits_suppress_in_flight_publication(everyday):
    e = everyday
    e.choose(daily_limit=10)
    parent = e.parent()
    e.consume(parent, 1)
    e.consume(parent, 2)
    installed.check_dispatch(parent)
    e.choose(enabled=False)
    with pytest.raises(ValueError):
        installed.check_dispatch(parent)
    with pytest.raises(ProviderFailure):
        e.consume(parent, 3)
    e.choose(enabled=True, per_hunt_limit=1)
    with pytest.raises(ValueError, match="reduced"):
        installed.check_dispatch(parent)
    e.choose(enabled=True, per_hunt_limit=15, daily_limit=1)
    with pytest.raises(ValueError, match="reduced"):
        installed.check_dispatch(parent)
    assert policy.status(e.actor)["used"] == 2
    (e.root / policy.CONFIG_NAME).unlink()
    with pytest.raises(ValueError):
        installed.check_dispatch(parent)
    assert installed.current_allowance(e.actor, existing=parent.allowance) is None


def test_limit_increases_require_revision_and_never_raise_captured_parent_ceiling(everyday):
    e = everyday
    e.choose(per_hunt_limit=2, daily_limit=2)
    parent = e.parent()
    e.consume(parent, 1)
    e.consume(parent, 2, lane="buy_it_now")
    installed.check_dispatch(parent)  # Final admitted send may still publish.
    e.choose(per_hunt_limit=15, daily_limit=6)
    assert policy.status(e.actor)["used"] == 2
    assert budget.remaining_traversal(e.root, parent.allowance)["total"] == 0
    second = e.parent("larger-parent")
    assert budget.remaining_traversal(e.root, second.allowance)["total"] == 4
    with pytest.raises(ValueError, match="changed"):
        e.choose(revision=1, daily_limit=9)


def test_lowered_per_hunt_limit_is_effective_before_next_dispatch(everyday):
    e = everyday
    e.choose(per_hunt_limit=5)
    parent = e.parent()
    e.consume(parent, 1)
    e.choose(per_hunt_limit=1)
    with pytest.raises(ProviderFailure):
        e.consume(parent, 2)
    assert policy.status(e.actor)["used"] == 1


def test_expiry_is_immediate_and_expired_policy_can_be_paused(everyday):
    e = everyday
    e.choose(expires_at=(e.clock.now + timedelta(seconds=1)).isoformat())
    parent = e.parent()
    e.consume(parent, 1)
    e.clock.now += timedelta(seconds=2)
    assert policy.status(e.actor)["remaining"] == 0
    with pytest.raises(ValueError):
        installed.check_dispatch(parent)
    e.choose(enabled=False, expires_at=(e.clock.now - timedelta(seconds=1)).isoformat())
    assert policy.status(e.actor)["enabled"] is False


@pytest.mark.parametrize(
    "date,hours",
    [
        (datetime(2026, 3, 8, 6, 0, tzinfo=UTC), 23),
        (datetime(2026, 11, 1, 5, 0, tzinfo=UTC), 25),
    ],
)
def test_recurring_midnight_uses_iana_dst_calendar_days(everyday, date, hours):
    e = everyday
    e.clock.now = date
    state = e.choose(daily_limit=1)
    assert (
        datetime.fromisoformat(state["window_end"]) - datetime.fromisoformat(state["window_start"])
    ).total_seconds() == hours * 3600
    parent = e.parent()
    e.consume(parent, 1)
    prefix = (policy._storage(e.root) / policy.JOURNAL_NAME).read_bytes()
    e.clock.now = datetime.fromisoformat(state["next_window_at"]) - timedelta(microseconds=1)
    assert policy.status(e.actor)["remaining"] == 0
    e.clock.now += timedelta(microseconds=1)
    assert policy.status(e.actor)["remaining"] == 1
    assert (policy._storage(e.root) / policy.JOURNAL_NAME).read_bytes() == prefix
    assert policy.status(e.actor)["used"] == 0


def test_nonrecurring_has_no_automatic_new_day_capacity(everyday):
    e = everyday
    state = e.choose(recurring=False, daily_limit=2)
    e.clock.now = datetime.fromisoformat(state["window_end"])
    assert policy.status(e.actor)["remaining"] == 0
    assert installed.current_allowance(e.actor) is None
    assert policy.status(e.actor)["next_window_at"] is None
    assert e.choose(recurring=False)["remaining"] == 10  # Deliberate new selection.


def test_timezone_revision_extends_current_window_without_double_capacity(everyday):
    e = everyday
    e.clock.now = datetime(2026, 10, 17, 22, 0, tzinfo=UTC)
    original = e.choose(timezone="America/Los_Angeles", daily_limit=2)
    parent = e.parent()
    e.consume(parent, 1)
    changed = e.choose(timezone="Pacific/Kiritimati", daily_limit=2)
    assert changed["used"] == 1 and changed["remaining"] == 1
    assert datetime.fromisoformat(changed["window_start"]) <= datetime.fromisoformat(original["window_start"])
    assert datetime.fromisoformat(changed["window_end"]) >= datetime.fromisoformat(original["window_end"])
    e.clock.now = datetime.fromisoformat(original["window_end"])
    assert policy.status(e.actor)["used"] == 1


def test_clock_rollback_fails_closed_until_last_durable_time(everyday):
    e = everyday
    e.choose()
    parent = e.parent()
    e.clock.now += timedelta(seconds=10)
    e.consume(parent, 1)
    latest = e.clock.now
    e.clock.now -= timedelta(seconds=1)
    assert "clock" in policy.status(e.actor)["reason"]
    with pytest.raises(ProviderFailure):
        e.consume(parent, 2)
    with pytest.raises(ValueError):
        e.choose()
    e.clock.now = latest
    e.consume(parent, 2, lane="buy_it_now")
    assert policy.status(e.actor)["used"] == 2


@pytest.mark.parametrize(
    "kind",
    [
        "missing-journal",
        "missing-marker",
        "both-missing",
        "partial",
        "symlink",
        "public",
        "mismatch",
        "reordered",
        "valid-prefix",
    ],
)
def test_missing_damaged_or_replaced_policy_accounting_never_renews(everyday, kind):
    e = everyday
    e.choose()
    parent = e.parent()
    e.consume(parent, 1)
    journal = policy._storage(e.root) / policy.JOURNAL_NAME
    marker = e.root / policy.CONFIG_NAME
    if kind in {"missing-journal", "both-missing"}:
        journal.unlink()
    if kind in {"missing-marker", "both-missing"}:
        marker.unlink()
    if kind == "partial":
        with journal.open("ab") as out:
            out.write(b'{"partial":')
    if kind == "symlink":
        alternate = journal.with_suffix(".old")
        journal.rename(alternate)
        journal.symlink_to(alternate)
    if kind == "public":
        journal.chmod(0o644)
    if kind == "mismatch":
        value = json.loads(marker.read_text())
        value["id"] = "f" * 32
        marker.write_text(json.dumps(value))
    if kind == "valid-prefix":
        journal.write_bytes(b"".join(journal.read_bytes().splitlines(keepends=True)[:-1]))
    if kind == "reordered":
        lines = journal.read_bytes().splitlines(keepends=True)
        journal.write_bytes(b"".join(reversed(lines)))
    assert policy.status(e.actor)["acquisition_available"] is False
    assert installed.current_allowance(e.actor) is None
    with pytest.raises((OSError, ValueError)):
        e.choose()
    with pytest.raises(ProviderFailure):
        e.consume(parent, 2)


def test_root_marker_restore_keeps_latest_independent_accounting(everyday):
    e = everyday
    e.choose(daily_limit=2)
    marker = (e.root / policy.CONFIG_NAME).read_bytes()
    parent = e.parent()
    e.consume(parent, 1)
    e.choose(daily_limit=1)
    (e.root / policy.CONFIG_NAME).write_bytes(marker)
    assert policy.status(e.actor)["used"] == 1
    assert policy.status(e.actor)["daily_limit"] == 1
    assert policy.status(e.actor)["remaining"] == 0


def test_cross_account_root_parent_and_detail_isolation(everyday, tmp_path):
    e = everyday
    e.choose()
    parent = e.parent()
    other = SimpleNamespace(user_id="other-owner", role="owner", subject=2)
    assert policy.status(other)["acquisition_available"] is False
    assert policy.current(other, root=e.root) is None
    other_root = tmp_path / "another-root"
    other_root.mkdir()
    assert budget.remaining_traversal(other_root, parent.allowance)["total"] == 0
    with pytest.raises(ProviderFailure):
        budget.consume_traversal(
            other_root, parent.id, "browse", "auction", dispatch_id="wrong-root", allowance=parent.allowance
        )
    detail = SimpleNamespace(operation="detail", parent_run_id=parent.id, owner=parent.owner)
    installed.check_dispatch(detail)
    detail.owner = (str(e.root), "other-owner", "session")
    with pytest.raises(ValueError):
        installed.check_dispatch(detail)


def test_parent_lease_expiry_never_renews_after_policy_revision(everyday):
    e = everyday
    e.choose()
    parent = e.parent()
    e.clock.now += timedelta(minutes=30)
    e.choose(daily_limit=50)
    with pytest.raises(ValueError, match="expired"):
        installed.check_dispatch(parent)
    with pytest.raises(ProviderFailure):
        e.consume(parent, 1)


def test_qualified_routine_package_rebinding_keeps_all_accounting(everyday):
    e = everyday
    e.choose()
    parent = e.parent()
    e.consume(parent, 1)
    journal = policy._storage(e.root) / policy.JOURNAL_NAME
    prefix = journal.read_bytes()
    e.monkeypatch.setattr(installed, "package_digest", lambda: "b" * 64)
    assert installed.current_allowance(e.actor) is None
    with pytest.raises(ValueError):
        e.choose()
    with pytest.raises(ValueError):
        policy.rebind_package(
            e.root, expected_previous="a" * 64, package_sha256="b" * 64, contract="changed-semantics"
        )
    assert policy.rebind_package(e.root, expected_previous="a" * 64, package_sha256="b" * 64)
    assert journal.read_bytes().startswith(prefix)
    assert policy.status(e.actor)["used"] == 1
    assert installed.current_allowance(e.actor, existing=parent.allowance) == parent.allowance
    assert e.choose(daily_limit=12)["used"] == 1


def test_independent_processes_share_one_durable_daily_admission(everyday):
    import subprocess
    import sys

    e = everyday
    e.choose(daily_limit=2)
    parents = [e.parent(str(index)) for index in range(5)]
    script = """
import sys
from datetime import datetime
from pokemon_hunter.beta import hunter_policy as p, hunter_installed as i
from pokemon_hunter.beta.discovery_transport import ProviderFailure
root, owner, policy_id, parent_id, at = sys.argv[1:]
i.package_digest = lambda: 'a' * 64
p._now = lambda: datetime.fromisoformat(at)
a = p.OrdinaryAllowance(root, owner, policy_id, parent_id)
try:
    p.consume(root, parent_id, 'browse', 'auction', dispatch_id='process-page', allowance=a, scope='singles')
except ProviderFailure:
    print('blocked')
else:
    print('admitted')
"""
    processes = [
        subprocess.Popen(
            [
                sys.executable,
                "-c",
                script,
                str(e.root),
                e.actor.user_id,
                parent.allowance.policy_id,
                parent.id,
                e.clock.now.isoformat(),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for parent in parents
    ]
    outputs = [process.communicate(timeout=10) for process in processes]
    assert all(process.returncode == 0 for process in processes), outputs
    assert [out.strip() for out, err in outputs].count("admitted") == 2
    assert policy.status(e.actor)["used"] == 2


def test_expiry_is_revalidated_after_waiting_for_selection_lock(everyday):
    from contextlib import contextmanager

    e = everyday
    original = policy._locked

    @contextmanager
    def delayed(root, **kwargs):
        with original(root, **kwargs) as stream:
            e.clock.now += timedelta(seconds=2)
            yield stream

    e.monkeypatch.setattr(policy, "_locked", delayed)
    raw = dict(
        enabled=True,
        per_hunt_limit=3,
        daily_limit=5,
        timezone="UTC",
        recurring=True,
        expires_at=(e.clock.now + timedelta(seconds=1)).isoformat(),
        revision=0,
    )
    with pytest.raises(ValueError, match="future"):
        policy.select(e.actor, raw)
    assert not (e.root / policy.CONFIG_NAME).exists()
    assert not (policy._storage(e.root) / policy.JOURNAL_NAME).exists()


def test_inaccessible_accounting_never_falls_back_to_historical_authority(everyday):
    from pathlib import Path

    e = everyday
    selected = budget.TraversalAllowance("hunt-04-disposable-fallback", browse=1, total=1, auction=1)
    e.monkeypatch.setattr(budget, "TRAVERSAL_ALLOWANCE", selected)
    original = Path.lstat

    def inaccessible(path):
        if path.name == policy.LOCK_NAME:
            raise PermissionError("engineering inaccessible storage")
        return original(path)

    e.monkeypatch.setattr(Path, "lstat", inaccessible)
    assert policy.present(e.root) is True
    assert installed.current_allowance(e.actor) is None
    assert policy.status(e.actor)["acquisition_available"] is False
