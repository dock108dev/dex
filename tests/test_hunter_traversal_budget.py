"""Disposable-only durable consumption; no customer allowance or I/O."""

import threading
from dataclasses import replace
from types import SimpleNamespace

import pytest

from pokemon_hunter.beta import hunter_budget as budget
from pokemon_hunter.beta.discovery_transport import ProviderFailure


def allowance(**kw):
    return budget.TraversalAllowance(
        "hunt-04-offline-test",
        oauth=1,
        browse=2,
        detail=1,
        resolution=1,
        total=5,
        auction=1,
        buy_it_now=1,
        lots=2,
        **kw,
    )


def test_production_is_disabled_without_creating_or_touching_ledger(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    assert budget.TRAVERSAL_ALLOWANCE is None
    assert budget.remaining_traversal(root) == dict.fromkeys(budget.TRAVERSAL_LIMIT_KEYS, 0)
    with pytest.raises(ProviderFailure):
        budget.consume_traversal(root, "run", "browse", "auction", dispatch_id="cursor")
    assert not list(tmp_path.glob(".dex-shopping-discovery/**/*"))


def test_legacy_exhaustion_is_byte_preserved_and_independent_of_new_allowance(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    run = SimpleNamespace(owner=(str(root),), id="legacy", current_lane="auction")
    budget.consume(run, "oauth")
    budget.consume(run, "browse")
    run.current_lane = "buy_it_now"
    budget.consume(run, "browse")
    legacy = budget.path(root).read_bytes()
    selected = allowance()
    budget.consume_traversal(root, "new", "browse", "auction", dispatch_id="cursor0", allowance=selected)
    assert budget.path(root).read_bytes() == legacy
    assert budget.remaining(root) == dict.fromkeys(budget.LIMITS, 0)
    assert budget.remaining_traversal(root, selected)["browse"] == 1
    assert budget.path(root) != budget.traversal_path(root, selected)


def test_concurrent_duplicate_workers_consume_exactly_one_durable_attempt(tmp_path):
    selected = allowance()
    admitted = []
    barrier = threading.Barrier(12)

    def consume():
        barrier.wait()
        try:
            budget.consume_traversal(
                tmp_path, "run", "browse", "auction", dispatch_id="cursor0", allowance=selected
            )
            admitted.append(True)
        except ProviderFailure:
            pass

    threads = [threading.Thread(target=consume) for _ in range(12)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(admitted) == 1
    assert budget.remaining_traversal(tmp_path, selected)["total"] == 4
    assert len(budget.traversal_path(tmp_path, selected).read_text().splitlines()) == 1


def test_concurrent_independent_starts_share_limits_and_no_refund(tmp_path):
    selected = allowance()
    admitted = []

    def consume(index):
        try:
            budget.consume_traversal(
                tmp_path,
                f"run{index}",
                "browse",
                "auction" if index % 2 else "buy_it_now",
                dispatch_id="cursor0",
                allowance=selected,
            )
            admitted.append(True)
        except ProviderFailure:
            pass

    threads = [threading.Thread(target=consume, args=(index,)) for index in range(20)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(admitted) == 2
    remaining = budget.remaining_traversal(tmp_path, selected)
    assert remaining["browse"] == remaining["auction"] == remaining["buy_it_now"] == 0
    # New objects, actions and days do not reset the same durable identity.
    with pytest.raises(ProviderFailure):
        budget.consume_traversal(
            tmp_path, "later-run", "browse", "auction", dispatch_id="cursor1", allowance=replace(selected)
        )


def test_lot_details_and_resolution_share_total_and_exact_accounting(tmp_path):
    selected = allowance()
    for stage in ("oauth", "detail", "resolution"):
        budget.consume_traversal(tmp_path, "run", stage, dispatch_id=stage, allowance=selected, scope="lots")
    remaining = budget.remaining_traversal(tmp_path, selected)
    assert remaining["total"] == 2 and remaining["lots"] == 0
    with pytest.raises(ProviderFailure):
        budget.consume_traversal(
            tmp_path, "run", "browse", "auction", dispatch_id="lot-page", allowance=selected, scope="lots"
        )
    assert budget.remaining_traversal(tmp_path, selected) == remaining


def test_changed_numeric_authorization_cannot_reinterpret_existing_identity(tmp_path):
    selected = allowance()
    budget.consume_traversal(tmp_path, "run", "oauth", dispatch_id="token", allowance=selected)
    changed = replace(selected, oauth=2, total=6)
    with pytest.raises(ValueError, match="unavailable"):
        budget.remaining_traversal(tmp_path, changed)
    with pytest.raises(ProviderFailure):
        budget.consume_traversal(tmp_path, "run2", "oauth", dispatch_id="token", allowance=changed)


@pytest.mark.parametrize(
    "changes",
    [
        {"id": budget.ALLOWANCE},
        {"id": "../untrusted"},
        {"browse": True},
        {"oauth": -1},
        {"total": 1001},
    ],
)
def test_allowance_is_finite_trusted_configuration(changes):
    with pytest.raises(ValueError):
        replace(allowance(), **changes)


def test_malformed_or_symlinked_ledger_fails_closed(tmp_path):
    selected = allowance()
    target = budget.traversal_path(tmp_path, selected)
    target.parent.mkdir(parents=True)
    target.write_text('{"malformed":true}\n')
    before = target.read_bytes()
    with pytest.raises(ProviderFailure):
        budget.consume_traversal(tmp_path, "run", "oauth", dispatch_id="token", allowance=selected)
    assert target.read_bytes() == before
    target.unlink()
    other = tmp_path / "other"
    other.write_text("")
    target.symlink_to(other)
    with pytest.raises(ProviderFailure):
        budget.consume_traversal(tmp_path, "run", "oauth", dispatch_id="token", allowance=selected)
    assert other.read_text() == ""


def test_composite_requests_account_actual_scope_under_shared_numeric_caps(tmp_path):
    from datetime import UTC, datetime

    from pokemon_hunter.beta import hunter_traversal

    plan = hunter_traversal.build_plan(datetime(2026, 10, 16, tzinfo=UTC), scope="both")
    selected = budget.TraversalAllowance(
        "hunt-04-composite-offline", browse=12, total=12, auction=8, buy_it_now=4, lots=6
    )
    for request in plan.requests:
        budget.consume_traversal(
            tmp_path,
            "combined-run",
            "browse",
            request.lane,
            dispatch_id=plan.cursor(request.ordinal),
            allowance=selected,
            scope=request.scope,
        )
    assert budget.remaining_traversal(tmp_path, selected) == dict.fromkeys(budget.TRAVERSAL_LIMIT_KEYS, 0)
