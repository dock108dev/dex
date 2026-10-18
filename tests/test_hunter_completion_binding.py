"""Completion execution binding: disposable roots and controlled transport only."""

import asyncio
import hashlib
import json
import sys
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_hunter import hunt as hunt
from test_hunter_h07_integration import integrated as integrated
from test_hunter_operator import boundary as boundary
from test_hunter_profile import b2 as b2
from test_hunter_profile import env as env
from test_hunter_profile import post
from test_hunter_profile import restricted as restricted
from test_hunter_profile import snapshot as snapshot
from test_hunter_profile_acquisition import _STORE_ROWS

from pokemon_hunter.beta import discovery, hunter, hunter_budget, hunter_profile, store
from pokemon_hunter.beta import hunter_operator as operator

COMPLETION = "hunt-07-completion-v1"
ORIGINAL = "hunt-04-qualification-v1"
LIMITS = dict(oauth=1, browse=12, detail=2, resolution=0, total=15, auction=8, buy_it_now=4, lots=8)
ORIGINAL_EXECUTION = "83eb166fdcac163017acc17e0998015b2bf9b36268de7f0b9cf75f61eab069d6"
ORIGINAL_WHEEL = "497f147b1d1e9f98fc6e1d33acf0007da9b1d090253dcba3948152b724a377e9"
CONSUMED = dict(oauth=1, browse=2, detail=0, resolution=0, total=3, auction=1, buy_it_now=1, lots=0)


def historical_consumed(root):
    """Make three fake old admissions; never copy the actual customer's ledger."""
    old = hunter_budget.TraversalAllowance(ORIGINAL, **LIMITS)
    for stage, lane in (("oauth", None), ("browse", "auction"), ("browse", "buy_it_now")):
        hunter_budget.consume_traversal(
            root,
            "closed-engineering-predecessor",
            stage,
            lane,
            dispatch_id=stage + "-" + str(lane),
            allowance=old,
        )
    return old, hunter_budget.traversal_path(root, old)


@pytest.fixture
def completion(boundary):
    root, value, save, _ = boundary
    _, old_ledger = historical_consumed(root)
    closure = root.parent / "closed-original-engineering.json"
    closure.write_text(
        json.dumps(
            dict(
                recorded_at="2026-10-17T13:29:09+00:00",
                temporary_execution_completed=True,
                latest_state_shop04_handback=True,
                runtime_selection_closed=True,
                provider_selection_closed=True,
                authorization_sha256=hashlib.sha256(b"closed-fake-authorization").hexdigest(),
                consumed_attempts_preserved=3,
                unused_numeric_slots_not_reused=12,
                allowance_reset=False,
                new_hunt_after_interruption=False,
            )
        )
    )
    predecessor = dict(
        id=ORIGINAL,
        ledger=str(old_ledger),
        ledger_sha256=operator.digest(old_ledger),
        consumed=CONSUMED,
        execution_sha256=ORIGINAL_EXECUTION,
        wheel_sha256=ORIGINAL_WHEEL,
        closed=True,
        closure_document=str(closure),
        closure_sha256=operator.digest(closure),
    )
    plan_document = root.parent / "completion-plan.json"
    plan_document.write_text(json.dumps(operator.completion_plan_document(predecessor)))
    new_ledger = hunter_budget.traversal_path(root, hunter_budget.TraversalAllowance(COMPLETION, **LIMITS))
    value["plan"] = dict(
        id=COMPLETION,
        limits=LIMITS,
        ledger=str(new_ledger),
        document=str(plan_document),
        sha256=operator.digest(plan_document),
        predecessor=predecessor,
    )
    return root, value, save, new_ledger


def test_completion_preflight_is_read_only_and_does_not_create_capacity(completion):
    root, value, save, new_ledger = completion
    identity, expected = save()
    before = {str(path): operator.digest(path) for path in root.parent.rglob("*") if path.is_file()}
    result, account = operator.preflight(identity, expected)
    assert result == value and account == "fixture-owner"
    assert {str(path): operator.digest(path) for path in root.parent.rglob("*") if path.is_file()} == before
    assert not new_ledger.exists()
    assert hunter_budget.TRAVERSAL_ALLOWANCE is None


@pytest.mark.parametrize(
    "change",
    [
        "plan",
        "plan_limits",
        "predecessor_id",
        "predecessor_ledger",
        "predecessor_digest",
        "predecessor_consumed",
        "predecessor_execution",
        "predecessor_wheel",
        "predecessor_open",
        "closure_digest",
        "closure_open",
        "root",
        "account",
        "wheel",
        "bootstrap",
        "profile",
        "plan_digest",
        "plan_document_rebound",
    ],
)
def test_mismatched_completion_binding_refuses_without_writes(completion, monkeypatch, change):
    root, original, save, new_ledger = completion
    value = deepcopy(original)
    predecessor = value["plan"]["predecessor"]
    if change == "plan":
        value["plan"]["id"] = "hunt-07-unselected-v1"
    elif change == "plan_limits":
        value["plan"]["limits"] = dict(LIMITS, browse=13)
    elif change == "predecessor_id":
        predecessor["id"] = "hunt-04-unselected-v1"
    elif change == "predecessor_ledger":
        predecessor["ledger"] += ".replacement"
    elif change == "predecessor_digest":
        predecessor["ledger_sha256"] = "0" * 64
    elif change == "predecessor_consumed":
        predecessor["consumed"]["total"] = 2
    elif change == "predecessor_execution":
        predecessor["execution_sha256"] = "0" * 64
    elif change == "predecessor_wheel":
        predecessor["wheel_sha256"] = "0" * 64
    elif change == "predecessor_open":
        predecessor["closed"] = False
    elif change == "closure_digest":
        predecessor["closure_sha256"] = "0" * 64
    elif change == "closure_open":
        path = Path(predecessor["closure_document"])
        closed = json.loads(path.read_text())
        closed["provider_selection_closed"] = False
        path.write_text(json.dumps(closed))
        predecessor["closure_sha256"] = operator.digest(path)
    elif change == "root":
        value["root"] = "/tmp"
    elif change == "account":
        value["account_sha256"] = "0" * 64
    elif change == "wheel":
        value["wheel_sha256"] = "0" * 64
    elif change == "bootstrap":
        value["launcher_sha256"] = "0" * 64
    elif change == "profile":
        value["profile_sha256"] = "0" * 64
    elif change == "plan_digest":
        value["plan"]["sha256"] = "0" * 64
    elif change == "plan_document_rebound":
        path = Path(value["plan"]["document"])
        document = json.loads(path.read_text())
        document["unselected_extra_capacity"] = 1
        path.write_text(json.dumps(document))
        value["plan"]["sha256"] = operator.digest(path)
    if change.startswith(("predecessor_", "closure_")):
        # Rebind the proposal's exact document too: refusal must exercise the
        # hard predecessor/receipt/accounting contract, not a stale plan digest.
        path = Path(value["plan"]["document"])
        path.write_text(json.dumps(operator.completion_plan_document(predecessor)))
        value["plan"]["sha256"] = operator.digest(path)
    identity, expected = save(value)
    before = {str(path): operator.digest(path) for path in root.parent.rglob("*") if path.is_file()}
    monkeypatch.setattr(hunter_profile, "configure", lambda *a, **kw: pytest.fail("Profile activated"))
    with pytest.raises((operator.Refusal, FileNotFoundError, ValueError)):
        operator.preflight(identity, expected)
    assert {str(path): operator.digest(path) for path in root.parent.rglob("*") if path.is_file()} == before
    assert not new_ledger.exists()


def test_completion_document_digest_refuses_before_state_reads(completion, monkeypatch):
    _, _, save, new_ledger = completion
    identity, _ = save()
    monkeypatch.setattr(operator, "schema_identity", lambda *a: pytest.fail("State read before digest"))
    with pytest.raises(operator.Refusal, match="identity changed"):
        operator.preflight(identity, "0" * 64)
    assert not new_ledger.exists()


@pytest.mark.parametrize("runtime,provider", [(False, False), (True, False), (False, True)])
def test_completion_requires_independent_exact_runtime_and_provider_selection(completion, runtime, provider):
    root, value, save, new_ledger = completion
    _, expected = save()
    path = root.parent / "simulated-completion-authorization.json"
    path.write_text(
        json.dumps(
            dict(
                schema="dex-hunter-authorization-v1",
                execution_sha256=expected,
                runtime_transition=runtime,
                provider_plan=dict(id=COMPLETION, sha256=value["plan"]["sha256"], selected=provider),
                expires_at=(datetime.now(UTC) + timedelta(minutes=30)).isoformat(),
            )
        )
    )
    path.chmod(0o600)
    with pytest.raises(operator.Refusal):
        operator.authorization(path, expected, value["plan"]["sha256"], plan_id=COMPLETION)
    assert not new_ledger.exists() and hunter_budget.TRAVERSAL_ALLOWANCE is None


@pytest.mark.parametrize("mismatch", ["old_execution", "old_plan", "wrong_plan_digest"])
def test_old_or_mismatched_authorization_cannot_select_completion(completion, mismatch):
    root, value, save, new_ledger = completion
    _, expected = save()
    selected = dict(
        schema="dex-hunter-authorization-v1",
        execution_sha256=ORIGINAL_EXECUTION if mismatch == "old_execution" else expected,
        runtime_transition=True,
        provider_plan=dict(
            id=ORIGINAL if mismatch == "old_plan" else COMPLETION,
            sha256="0" * 64 if mismatch == "wrong_plan_digest" else value["plan"]["sha256"],
            selected=True,
        ),
        expires_at=(datetime.now(UTC) + timedelta(minutes=30)).isoformat(),
    )
    path = root.parent / "simulated-mismatched-authorization.json"
    path.write_text(json.dumps(selected))
    path.chmod(0o600)
    with pytest.raises(operator.Refusal):
        operator.authorization(path, expected, value["plan"]["sha256"], plan_id=COMPLETION)
    assert not new_ledger.exists()


def test_matching_simulated_authorization_selects_only_exact_completion_without_activation(completion):
    root, value, save, new_ledger = completion
    _, expected = save()
    path = root.parent / "simulated-matching-authorization.json"
    path.write_text(
        json.dumps(
            dict(
                schema="dex-hunter-authorization-v1",
                execution_sha256=expected,
                runtime_transition=True,
                provider_plan=dict(id=COMPLETION, sha256=value["plan"]["sha256"], selected=True),
                expires_at=(datetime.now(UTC) + timedelta(minutes=30)).isoformat(),
            )
        )
    )
    path.chmod(0o600)
    assert operator.authorization(path, expected, value["plan"]["sha256"], plan_id=COMPLETION)
    assert not new_ledger.exists() and hunter_budget.TRAVERSAL_ALLOWANCE is None


def test_completion_linkage_is_rechecked_before_each_acquisition_authorization(completion, monkeypatch):
    root, value, save, new_ledger = completion
    _, expected = save()
    selections = []
    monkeypatch.setattr(
        operator,
        "authorization",
        lambda *args, **kwargs: selections.append(kwargs["plan_id"]) or True,
    )
    assert operator.acquisition_authorization(value, root.parent / "mock-selection.json", expected)
    assert selections == [COMPLETION]
    old_ledger = Path(value["plan"]["predecessor"]["ledger"])
    old_ledger.write_text(old_ledger.read_text() + "controlled-accounting-change\n")
    before = old_ledger.read_bytes()
    with pytest.raises((operator.Refusal, ValueError)):
        operator.acquisition_authorization(value, root.parent / "mock-selection.json", expected)
    assert selections == [COMPLETION]
    assert old_ledger.read_bytes() == before and not new_ledger.exists()


def test_cli_passes_the_exact_completion_plan_to_authorization_before_transition(completion, monkeypatch):
    root, _, save, new_ledger = completion
    identity, expected = save()
    selected = []
    monkeypatch.setattr(
        operator,
        "authorization",
        lambda *args, **kwargs: selected.append(kwargs["plan_id"]) or True,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "operator",
            "execute",
            "--identity",
            str(identity),
            "--expected-identity",
            expected,
            "--authorization",
            str(root.parent / "mock-selection.json"),
        ],
    )
    with pytest.raises(SystemExit, match="Engineering transitions"):
        operator.main()
    assert selected == [COMPLETION] and not new_ledger.exists()


@pytest.mark.parametrize("tamper", ["suffix", "crlf"])
def test_completion_handback_preserves_changed_predecessor_ledger_without_reopening_it(completion, tamper):
    _, value, save, new_ledger = completion
    identity, expected = save()
    old_ledger = Path(value["plan"]["predecessor"]["ledger"])
    before = old_ledger.read_bytes()
    old_ledger.write_bytes(
        before + b"controlled-accounting-damage\n" if tamper == "suffix" else before.replace(b"\n", b"\r\n")
    )
    retained = old_ledger.read_bytes()
    with pytest.raises((operator.Refusal, ValueError)):
        operator.preflight(identity, expected)
    recovered, account = operator.preflight(identity, expected, handback=True)
    assert recovered == value and account == "fixture-owner"
    assert old_ledger.read_bytes() == retained and not new_ledger.exists()


def test_only_exact_reviewed_completion_allowance_is_added():
    allowance = hunter_budget.TraversalAllowance(COMPLETION, **LIMITS)
    assert allowance.id == COMPLETION and allowance.limits == LIMITS
    for unselected in ("hunt-07-other-v1", "hunt-07-completion-v2", "hunt-07-completion-v1-other"):
        with pytest.raises(ValueError):
            hunter_budget.TraversalAllowance(unselected, **LIMITS)
    for changed in (dict(detail=1, total=14), dict(browse=10, total=13), dict(oauth=0, total=14)):
        with pytest.raises(ValueError):
            hunter_budget.TraversalAllowance(COMPLETION, **(LIMITS | changed))


def test_original_three_consumed_operations_still_prevent_start(restricted, monkeypatch):
    root = restricted["root"]
    allowance, ledger = historical_consumed(root)
    before = ledger.read_bytes()
    monkeypatch.setattr(hunter_budget, "TRAVERSAL_ALLOWANCE", allowance)
    monkeypatch.setattr(hunter, "start", lambda *a, **kw: pytest.fail("Original attempt restarted"))
    assert post(restricted["a"], "/api/shopping/hunter/", {"scope": "both"}).status_code == 400
    assert not hunter_profile._started
    assert ledger.read_bytes() == before and len(before.splitlines()) == 3
    assert not hunter_budget.traversal_path(
        root, hunter_budget.TraversalAllowance(COMPLETION, **LIMITS)
    ).exists()


def test_completion_profile_requires_matching_trusted_allowance(restricted, monkeypatch):
    selected = hunter_profile.ExecutionProfile(
        restricted["actor"].user_id,
        restricted["root"],
        authorization_check=lambda: None,
        plan_id=COMPLETION,
    )
    monkeypatch.setattr(hunter_profile, "_configured", selected)
    monkeypatch.setattr(hunter, "start", lambda *a, **kw: pytest.fail("Mismatched allowance dispatched"))
    monkeypatch.setattr(
        hunter_budget, "TRAVERSAL_ALLOWANCE", hunter_budget.TraversalAllowance(ORIGINAL, **LIMITS)
    )
    assert post(restricted["a"], "/api/shopping/hunter/", {"scope": "both"}).status_code == 400
    assert not hunter_profile._started
    assert not (restricted["root"].parent / ".dex-shopping-discovery").exists()


def test_completion_dispatch_requires_exact_captured_allowance_and_live_authority(tmp_path, monkeypatch):
    checked = []
    active = True

    def authorize():
        checked.append("checked")
        if not active:
            raise ValueError("Controlled withdrawn completion selection")

    selected = hunter_profile.ExecutionProfile(
        "fixture-owner", tmp_path, authorization_check=authorize, plan_id=COMPLETION
    )
    monkeypatch.setattr(hunter_profile, "_configured", selected)
    monkeypatch.setattr(hunter_profile, "require_current", lambda: selected)
    run = SimpleNamespace(operation="hunter", owner=(str(tmp_path), "fixture-owner", "binding"))
    for captured in (
        None,
        hunter_budget.TraversalAllowance(ORIGINAL, **LIMITS),
        SimpleNamespace(id=COMPLETION, limits=LIMITS),
    ):
        run.allowance = captured
        with pytest.raises(ValueError, match="completion"):
            hunter_profile.check_dispatch(run)
    assert not checked
    run.allowance = hunter_budget.TraversalAllowance(COMPLETION, **LIMITS)
    hunter_profile.check_dispatch(run)
    assert checked == ["checked"]
    active = False
    with pytest.raises(ValueError, match="withdrawn completion"):
        hunter_profile.check_dispatch(run)
    assert checked == ["checked", "checked"]
    assert list(tmp_path.iterdir()) == []


def test_completion_detail_dispatch_uses_same_owner_live_parent_allowance(tmp_path, monkeypatch):
    checked = []
    selected = hunter_profile.ExecutionProfile(
        "fixture-owner", tmp_path, authorization_check=lambda: checked.append(True), plan_id=COMPLETION
    )
    monkeypatch.setattr(hunter_profile, "_configured", selected)
    monkeypatch.setattr(hunter_profile, "require_current", lambda: selected)
    parents = {}
    monkeypatch.setattr(hunter, "_runs", parents)
    allowance = hunter_budget.TraversalAllowance(COMPLETION, **LIMITS)
    run = SimpleNamespace(
        operation="detail",
        owner=(str(tmp_path), "fixture-owner", "binding"),
        parent_run_id="captured-parent",
        allowance=allowance,
    )
    for parent in (
        None,
        SimpleNamespace(owner=(*run.owner[:2], "foreign-binding"), allowance=allowance),
        SimpleNamespace(owner=run.owner, allowance=hunter_budget.TraversalAllowance(ORIGINAL, **LIMITS)),
    ):
        parents.clear()
        if parent is not None:
            parents[run.parent_run_id] = parent
        with pytest.raises(ValueError, match="completion"):
            hunter_profile.check_dispatch(run)
    assert not checked
    parents[run.parent_run_id] = SimpleNamespace(owner=run.owner, allowance=allowance)
    hunter_profile.check_dispatch(run)
    assert checked == [True]
    parents.clear()
    with pytest.raises(ValueError, match="completion"):
        hunter_profile.check_dispatch(run)
    assert checked == [True] and list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "stage,lane,scope",
    [("oauth", None, "singles"), ("browse", "auction", "singles"), ("detail", None, "lots")],
)
def test_any_consumed_completion_capacity_prevents_replacement_start(
    restricted, monkeypatch, stage, lane, scope
):
    selected = hunter_profile.ExecutionProfile(
        restricted["actor"].user_id,
        restricted["root"],
        authorization_check=lambda: None,
        plan_id=COMPLETION,
    )
    monkeypatch.setattr(hunter_profile, "_configured", selected)
    allowance = hunter_budget.TraversalAllowance(COMPLETION, **LIMITS)
    monkeypatch.setattr(hunter_budget, "TRAVERSAL_ALLOWANCE", allowance)
    hunter_budget.consume_traversal(
        restricted["root"],
        "uncertain-previous-run",
        stage,
        lane,
        dispatch_id="uncertain-consumed-operation",
        allowance=allowance,
        scope=scope,
    )
    ledger = hunter_budget.traversal_path(restricted["root"], allowance)
    before = ledger.read_bytes()
    monkeypatch.setattr(hunter, "start", lambda *a, **kw: pytest.fail("Consumed completion restarted"))
    assert post(restricted["a"], "/api/shopping/hunter/", {"scope": "both"}).status_code == 400
    assert not hunter_profile._started and ledger.read_bytes() == before


def test_matching_completion_selection_one_both_and_first_continue_reaches_lots(
    restricted, integrated, monkeypatch
):
    from django.conf import settings

    from pokemon_hunter.beta import hunter_views

    selected = hunter_profile.ExecutionProfile(
        restricted["actor"].user_id,
        restricted["root"],
        authorization_check=lambda: None,
        plan_id=COMPLETION,
    )
    monkeypatch.setattr(hunter_profile, "_configured", selected)
    monkeypatch.setattr(
        store,
        "rows",
        lambda sql, params=(): (
            [{"id": "pokemon"}]
            if sql == "SELECT id FROM games WHERE game_key='pokemon'"
            else _STORE_ROWS(sql, params)
        ),
    )
    monkeypatch.setattr(discovery, "settings", settings)
    monkeypatch.setattr(hunter_views, "_images", lambda *args: None)
    allowance = hunter_budget.TraversalAllowance(COMPLETION, **LIMITS)
    monkeypatch.setattr(hunter_budget, "TRAVERSAL_ALLOWANCE", allowance)
    integrated.pages[0] = deepcopy(integrated.pages[1])
    dispatched = []
    original_transport = hunter.Transport

    class RecordingTransport(original_transport):
        async def request(self, stage, **kwargs):
            if stage == "browse":
                captured = kwargs["search_options"]["hunter"]
                dispatched.append((captured.scope, captured.lane))
            return await super().request(stage, **kwargs)

    monkeypatch.setattr(hunter, "Transport", RecordingTransport)
    client, actor = restricted["a"], restricted["actor"]
    api = "/api/shopping/hunter/"
    for unselected in ({"plan": COMPLETION}, {"limits": LIMITS}, {"root": str(restricted["root"])}):
        assert post(client, api, {"scope": "both", **unselected}).status_code == 400
    assert not integrated.calls and not hunter_profile._started
    started = post(client, api, {"scope": "both"})
    assert started.status_code == 200
    parent = hunter._runs[started.json()["run_id"]]
    captured_created = parent.created
    captured_plan = parent.traversal
    assert parent.auth_session == client.session.session_key
    asyncio.run(hunter._acquire_traversal(parent, ("fixture-client", "FIXTURE_ONLY"), actor))
    first = client.get(api, {"run_id": parent.id}).json()
    assert dispatched == [("singles", "auction"), ("singles", "buy_it_now")]
    assert [stage for stage, _ in integrated.calls] == ["oauth", "browse", "browse"]
    assert post(client, api, {"scope": "both"}).status_code == 400
    assert len(integrated.calls) == 3
    continued = post(client, f"{api}{parent.id}/continue/", {"cursor": first["continuation_cursor"]})
    assert continued.status_code == 200 and continued.json()["run_id"] == parent.id
    asyncio.run(hunter._acquire_traversal(parent, ("fixture-client", "FIXTURE_ONLY"), actor))
    current = client.get(api, {"run_id": parent.id}).json()
    assert dispatched == [
        ("singles", "auction"),
        ("singles", "buy_it_now"),
        ("lots", "auction"),
        ("lots", "buy_it_now"),
    ]
    assert [stage for stage, _ in integrated.calls] == ["oauth"] + ["browse"] * 4
    assert current["run_id"] == first["run_id"] and current["window"] == first["window"]
    assert parent.created == captured_created and parent.traversal is captured_plan
    assert current["expires_in_seconds"] <= first["expires_in_seconds"]
    for _ in range(2):
        assert client.get(api, {"run_id": parent.id}).status_code == 200
    assert len(integrated.calls) == 5
    assert post(client, f"{api}{parent.id}/stop/", {}).status_code == 200
    assert parent.cancel.is_set() and not parent.raws
    assert len(integrated.calls) == 5
    remaining = hunter_budget.remaining_traversal(restricted["root"], allowance)
    assert remaining["oauth"] == 0 and remaining["browse"] == 8 and remaining["total"] == 10
    assert not hunter_budget.traversal_path(
        restricted["root"], hunter_budget.TraversalAllowance(ORIGINAL, **LIMITS)
    ).exists()
