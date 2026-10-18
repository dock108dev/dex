"""Ordinary installed authority, using disposable roots and no external work."""

import asyncio
import json
import time
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from test_hunter import hunt as hunt
from test_hunter_h07_integration import integrated as integrated

from pokemon_hunter.beta import discovery as d
from pokemon_hunter.beta import hunter as h
from pokemon_hunter.beta import hunter_budget as budget
from pokemon_hunter.beta import hunter_installed as installed


@pytest.fixture
def binding(tmp_path, monkeypatch):
    root = tmp_path / "disposable"
    root.mkdir(mode=0o700)
    actor = SimpleNamespace(user_id="engineering-owner")
    monkeypatch.setattr("django.conf.settings", SimpleNamespace(ROOT=root, STAGING=False))
    monkeypatch.setattr(d, "settings", SimpleNamespace(ROOT=root))
    monkeypatch.setattr(d.store, "verified", lambda who: who)
    monkeypatch.setattr(installed, "package_digest", lambda: "a" * 64)
    monkeypatch.setattr(installed, "_configured", None)
    monkeypatch.setattr(installed, "_parent_run_id", None)
    monkeypatch.setattr(budget, "TRAVERSAL_ALLOWANCE", None)
    monkeypatch.setattr(h, "_runs", {})
    document = installed.proposal(root, actor.user_id)
    path = root / installed.CONFIG_NAME

    def save(*, selected=True, **changes):
        value = {
            **document,
            "selected": selected,
            "expires_at": (datetime.now(UTC) + timedelta(minutes=10)).isoformat(),
            **changes,
        }
        path.write_text(json.dumps(value))
        path.chmod(0o600)
        return value

    def parent(key="engineering-parent", **changes):
        return h.Run(
            key,
            (str(root), actor.user_id, "navigation-binding"),
            d.Choices(),
            None,
            [],
            allowance=budget.TRAVERSAL_ALLOWANCE,
            **changes,
        )

    return SimpleNamespace(root=root, actor=actor, path=path, save=save, parent=parent)


def test_absence_and_unselected_template_create_no_authority_or_ledger(binding):
    assert installed.configure() is None
    assert budget.TRAVERSAL_ALLOWANCE is None
    assert list(binding.root.iterdir()) == []
    binding.save(selected=False)
    assert installed.configure() is None
    assert budget.TRAVERSAL_ALLOWANCE is None
    assert list(binding.root.iterdir()) == [binding.path]
    assert not (binding.root.parent / ".dex-shopping-discovery").exists()


def test_exact_binding_only_selects_future_fixed_capacity_without_dispatch(binding):
    binding.save()
    selected = installed.configure()
    assert selected.allowance.id == "hunt-04-installed-v1"
    assert selected.allowance.limits == installed.LIMITS
    assert installed.current_allowance(binding.actor) == selected.allowance
    assert installed.current_allowance(SimpleNamespace(user_id="other-account")) is None
    assert not budget.traversal_path(binding.root, selected.allowance).exists()
    with pytest.raises(ValueError, match="already selected"):
        installed.configure()


@pytest.mark.parametrize(
    "changes",
    [
        {"plan": "hunt-07-completion-v1"},
        {"plan": "hunt-04-installed-v2"},
        {"root": "/another-root"},
        {"package_sha256": "b" * 64},
        {"account_id": ""},
        {"selected": 1},
        {"version": True},
        {"limits": {**installed.LIMITS, "oauth": 2}},
        {"limits": {**installed.LIMITS, "oauth": True}},
        {"expires_at": (datetime.now(UTC) - timedelta(seconds=1)).isoformat()},
        {"expires_at": "2027-01-01T12:00:00"},
        {"expires_at": None},
    ],
)
def test_replaced_binding_refuses_before_worker_or_ledger(binding, changes):
    binding.save(**changes)
    assert installed.configure() is None
    assert budget.TRAVERSAL_ALLOWANCE is None
    assert not (binding.root.parent / ".dex-shopping-discovery").exists()


@pytest.mark.parametrize("kind", ["public", "symlink", "oversize", "malformed"])
def test_untrusted_document_refused_without_retaining_contents(binding, kind):
    binding.save()
    if kind == "public":
        binding.path.chmod(0o644)
    elif kind == "symlink":
        target = binding.path.with_name("other.json")
        binding.path.rename(target)
        binding.path.symlink_to(target)
    elif kind == "oversize":
        binding.path.write_text("x" * (installed.MAX_CONFIG_BYTES + 1))
    else:
        binding.path.write_text("CANARY_PRIVATE_BROKEN_DOCUMENT")
    assert installed.configure() is None
    assert budget.TRAVERSAL_ALLOWANCE is None


def test_withdrawal_and_package_change_block_future_sends_and_publication(binding, monkeypatch):
    binding.save()
    selected = installed.configure()
    run = binding.parent()
    installed.check_dispatch(run)
    monkeypatch.setattr(installed, "package_digest", lambda: "b" * 64)
    assert installed.current_allowance(binding.actor, existing=selected.allowance) is None
    with pytest.raises(ValueError):
        d._check_acquisition(run)
    monkeypatch.setattr(installed, "package_digest", lambda: "a" * 64)
    binding.path.unlink()
    assert installed.current_allowance(binding.actor, existing=selected.allowance) is None
    with pytest.raises(ValueError):
        d._check_acquisition(run)
    assert not budget.traversal_path(binding.root, selected.allowance).exists()


def test_consumed_parent_survives_process_restart_and_blocks_replacement(binding, monkeypatch):
    binding.save()
    selected = installed.configure()
    first = binding.parent()
    installed.check_dispatch(first)
    budget.consume_traversal(
        binding.root, first.id, "oauth", dispatch_id="first-auth", allowance=selected.allowance
    )
    ledger = budget.traversal_path(binding.root, selected.allowance)
    consumed = ledger.read_bytes()
    assert installed.current_allowance(binding.actor) is None
    assert installed.current_allowance(binding.actor, existing=first.allowance) == first.allowance
    monkeypatch.setattr(installed, "_configured", None)
    monkeypatch.setattr(installed, "_parent_run_id", None)
    installed.configure()
    assert installed.current_allowance(binding.actor) is None
    with pytest.raises(ValueError, match="original Hunt"):
        installed.check_dispatch(binding.parent("replacement"))
    installed.check_dispatch(first)
    assert ledger.read_bytes() == consumed


def test_same_process_replacement_and_wrong_account_refuse_before_admission(binding):
    binding.save()
    selected = installed.configure()
    installed.check_dispatch(binding.parent())
    with pytest.raises(ValueError, match="replace"):
        installed.check_dispatch(binding.parent("replacement"))
    run = binding.parent()
    run.owner = (str(binding.root), "another-account", "navigation-binding")
    with pytest.raises(ValueError, match="root and account"):
        installed.check_dispatch(run)
    assert not budget.traversal_path(binding.root, selected.allowance).exists()


def test_detail_requires_original_parent_account_and_captured_allowance(binding):
    binding.save()
    installed.configure()
    parent = binding.parent()
    h._runs[parent.id] = parent
    detail = d.Run("detail-action", parent.owner, parent.choices, None, [], operation="detail")
    detail.parent_run_id = parent.id
    installed.check_dispatch(detail)
    parent.allowance = budget.TraversalAllowance("hunt-04-other", **installed.LIMITS)
    with pytest.raises(ValueError, match="retain"):
        installed.check_dispatch(detail)
    h._runs.clear()
    with pytest.raises(ValueError, match="parent"):
        installed.check_dispatch(detail)


def test_ordinary_discovery_unaffected_and_independent_stop_survives_withdrawal(binding):
    binding.save()
    installed.configure()
    run = binding.parent()
    h._runs[run.id] = run
    run.window = dict(start="engineering-start", end="engineering-end")
    binding.path.unlink()
    ordinary = d.Run("ordinary", run.owner, run.choices, None, [])
    installed.check_dispatch(ordinary)
    assert not run.cancel.is_set()
    h.stop(binding.actor, "navigation-binding", run.id)
    assert run.cancel.is_set() and run.state == "stopped" and not run.raws


def test_withdrawn_dispatch_cannot_send_or_consume(binding):
    binding.save()
    selected = installed.configure()
    run = binding.parent()
    run.deadline = time.monotonic() + 10
    binding.path.unlink()

    class ForbiddenTransport:
        async def request(self, *args, **kwargs):
            pytest.fail("No provider operation is authorized")

    with pytest.raises(ValueError):
        asyncio.run(d._dispatch(run, ForbiddenTransport(), "oauth", run.deadline))
    assert run.counts["total"] == 0
    assert not budget.traversal_path(binding.root, selected.allowance).exists()


def test_metadata_and_start_refuse_wrong_account_without_action_or_configuration_probe(binding, monkeypatch):
    binding.save()
    installed.configure()
    other = SimpleNamespace(user_id="another-account")
    assert h.metadata(other, "navigation-binding")["acquisition_available"] is False
    monkeypatch.setattr(h.ebay_hunts, "configuration", lambda: pytest.fail("No credential probe"))
    monkeypatch.setattr(h, "_launch", lambda *args: pytest.fail("No action journal or worker"))
    with pytest.raises(ValueError, match="allowance"):
        h.start(other, "navigation-binding", {"scope": "both"})
    assert not h._runs


def test_expiry_without_document_change_blocks_sends_but_preserves_local_stop(binding, monkeypatch):
    binding.save()
    selected = installed.configure()
    run = binding.parent()
    run.window = dict(start="engineering-start", end="engineering-end")
    h._runs[run.id] = run
    installed.check_dispatch(run)

    class Later(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime.now(tz) + timedelta(days=1)

    monkeypatch.setattr(installed, "datetime", Later)
    assert installed.current_allowance(binding.actor, existing=selected.allowance) is None
    with pytest.raises(ValueError, match="expired"):
        d._check_acquisition(run)
    h.stop(binding.actor, "navigation-binding", run.id)
    assert run.cancel.is_set() and run.state == "stopped"


def test_document_extension_cannot_renew_selected_authority(binding):
    binding.save()
    selected = installed.configure()
    run = binding.parent()
    installed.check_dispatch(run)
    binding.save(expires_at=(datetime.now(UTC) + timedelta(days=1)).isoformat())
    assert installed.current_allowance(binding.actor, existing=selected.allowance) is None
    with pytest.raises(ValueError, match="changed"):
        installed.check_dispatch(run)


def test_full_installed_binding_both_five_continues_two_details_and_consumed_restart(integrated, monkeypatch):
    from copy import deepcopy

    from pokemon_hunter.beta import hunter_lot_details as details
    from pokemon_hunter.beta import hunter_lots as lots

    root, actor = integrated.env.root, integrated.env.actor
    monkeypatch.setattr("django.conf.settings", SimpleNamespace(ROOT=root, STAGING=False))
    monkeypatch.setattr(installed, "_configured", None)
    monkeypatch.setattr(installed, "_parent_run_id", None)
    # This uses the actual private-document parser and package member identity,
    # replacing the fixture's direct allowance with ordinary startup selection.
    proposal = installed.proposal(root, actor.user_id)
    proposal.update(
        selected=True,
        expires_at=(datetime.now(UTC) + timedelta(minutes=10)).isoformat(),
    )
    path = root / installed.CONFIG_NAME
    path.write_text(json.dumps(proposal))
    path.chmod(0o600)
    selected = installed.configure()
    assert selected.allowance.id == installed.PLAN_ID
    authority_bytes = path.read_bytes()
    integrated.pages[0] = deepcopy(integrated.pages[1])
    started = h.start(actor, "binding", {"scope": "both"})
    parent = h._runs[started["run_id"]]
    captured_created, captured_window = parent.created, dict(parent.window)
    continues = 0
    while True:
        asyncio.run(h._acquire_traversal(parent, ("fixture-client", "CANARY_SECRET"), actor))
        current = h.status(actor, "binding", parent.id)
        if parent.next_index == len(parent.traversal.requests):
            break
        h.continue_run(actor, "binding", parent.id, {"cursor": current["continuation_cursor"]})
        continues += 1
    assert continues == 5 and parent.next_index == 12
    assert parent.created == captured_created and parent.window == captured_window
    chosen = [row["id"] for row in current["results"]]
    assert len(chosen) == 2
    before_details = len(integrated.calls)
    local = [lots.analyze(actor, "binding", parent.id, result_id) for result_id in chosen]
    assert lots.detail_intent(actor, "binding", parent.id, chosen)["dispatch_allowed"]
    assert len(integrated.calls) == before_details == 13
    started_details = details.start(actor, "binding", parent.id, chosen)
    detail = details._runs[started_details["detail_action_id"]]
    asyncio.run(details._acquire(detail, actor, "binding", ("fixture-client", "CANARY_SECRET")))
    loaded = details.status(actor, "binding", detail.id)
    assert len(loaded["reviews"]) == 2
    assert [stage for stage, _ in integrated.calls] == ["oauth"] + ["browse"] * 12 + ["detail"] * 2
    ledger = budget.traversal_path(root, selected.allowance)
    consumed = ledger.read_bytes()
    assert len(consumed.splitlines()) == 15
    assert budget.remaining_traversal(root, selected.allowance) == dict.fromkeys(
        budget.TRAVERSAL_LIMIT_KEYS, 0
    )
    for private in (b"CANARY", b"Charizard", b"Blastoise", b"access_token", b"description"):
        assert private not in consumed
    assert h.metadata(actor, "binding")["acquisition_available"] is False
    with pytest.raises(ValueError):
        h.start(actor, "binding", {"scope": "both"})
    # Withdrawal leaves received content locally readable under its original
    # account/source lease and preserves independent detail and parent Stops.
    path.unlink()
    assert h.status(actor, "binding", parent.id)["results"]
    assert len(details.status(actor, "binding", detail.id)["reviews"]) == 2
    assert lots.read(actor, "binding", local[0]["review_id"])
    details.stop(actor, "binding", detail.id)
    assert not parent.cancel.is_set() and h.status(actor, "binding", parent.id)["results"]
    h.stop(actor, "binding", parent.id)
    assert parent.cancel.is_set() and not parent.raws and not detail.raws
    assert len(integrated.calls) == 15 and ledger.read_bytes() == consumed
    # A fresh ordinary process with the exact original authority has no renewed
    # allocation and cannot replace the completed parent after restart.
    path.write_bytes(authority_bytes)
    path.chmod(0o600)
    monkeypatch.setattr(installed, "_configured", None)
    monkeypatch.setattr(installed, "_parent_run_id", None)
    installed.configure()
    assert h.metadata(actor, "binding")["acquisition_available"] is False
    with pytest.raises(ValueError):
        h.start(actor, "binding", {"scope": "both"})
    assert len(integrated.calls) == 15 and ledger.read_bytes() == consumed


def test_package_identity_changes_for_members_but_ignores_bytecode(tmp_path, monkeypatch):
    package = tmp_path / "package"
    beta = package / "beta"
    beta.mkdir(parents=True)
    module = beta / "hunter_installed.py"
    module.write_text("engineering-module")
    monkeypatch.setattr(installed, "__file__", str(module))
    before = installed.package_digest()
    cache = beta / "__pycache__"
    cache.mkdir()
    (cache / "compiled.pyc").write_bytes(b"interpreter-cache")
    assert installed.package_digest() == before
    (beta / "hunter.js").write_text("changed-application-member")
    assert installed.package_digest() != before
    (beta / "alias.py").symlink_to(module)
    with pytest.raises(ValueError, match="identity"):
        installed.package_digest()
