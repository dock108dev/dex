"""navigation rejects unbounded UI authority and preserves read-only identity."""

import shutil
import subprocess
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlencode

import pytest
from perf04_helpers import prepare_reads
from test_b1 import env as env
from test_b2 import b2 as b2
from test_b3 import b3 as b3
from test_b4 import b4 as b4
from test_card_groups import find
from test_cx03_review import dump
from test_effective_collection import cx as cx
from test_migration import snapshot as snapshot
from test_sealed_catalog import e1 as e1


def test_shopping_return_preserves_full_filter_state_with_frozen_goal(cx):
    from test_b2 import apply

    from pokemon_hunter.beta import collection, navigation
    from pokemon_hunter.beta.card_group_views import return_context

    goal = apply(cx, "goal", dict(name="Shopping return", goal_kind="original151"))["changes"][0]["after"]
    prepare_reads(cx)
    fields = dict(
        run_id="11111111-1111-4111-8111-111111111111",
        q="Venusaur",
        species="3",
        goal=goal["id"],
        version=goal["version"],
        generation=str(collection.generation(cx["actor"])),
        intent="missing",
        missing_basis="species",
        scope="all",
        budget="87.25",
        budget_mode="flexible",
        budget_rule="Higher cost only with supported value",
        budget_value_basis="collectible",
        prefer_vintage="1",
        product_type="mixed_lots",
        sort="ending_soonest",
        english_vintage="1",
        result_filter="all",
        time_window="72",
        value_sort="best",
        buying_mode="both",
        value_basis="all",
        estimate_filter="estimated",
        era_filter="pre2000",
        scroll="312",
        focus="offer-example",
    )
    destination = "/shopping/?" + urlencode(fields)
    assert len(fields) > 24
    assert return_context(destination) == destination
    assert navigation.authorize_destination(cx["actor"], destination) == destination
    for invalid in (
        destination + "&unsupported=1",
        destination + "&q=duplicate",
        "https://example.test" + destination,
    ):
        with pytest.raises(ValueError):
            return_context(invalid)


def test_bounded_shopping_return_chain_retains_null_and_explicit_child(cx):
    from pokemon_hunter.beta import navigation

    group = find(cx, "a")
    child = group["_children"][0]["id"]
    species = "/pokedex/2/?" + urlencode({"return": "/pokedex/?owned=missing&selecting=1&focus=2"})
    null = f"/card-groups/{group['id']}/?" + urlencode({"return": species})
    exact = f"/card-groups/{group['id']}/?" + urlencode({"child": child, "return": species})
    prepare_reads(cx)
    before = dump(cx)
    assert navigation.authorize_destination(cx["actor"], null) == null
    assert navigation.authorize_destination(cx["actor"], exact) == exact
    assert dump(cx) == before
    assert "child=" not in null
    assert child in exact


def test_home_storage_binding_changes_between_accounts_and_auth_sessions(cx):
    # Use real authenticated requests so the private shell binds the actual principal,
    # rather than trusting identifiers supplied in navigation query fields.
    first = cx["a"].get("/api/navigation/home/", {"destination": "/cards/"}).json()
    second = cx["b"].get("/api/navigation/home/", {"destination": "/cards/"}).json()
    assert first["account_id"] == cx["actor"].user_id
    assert second["account_id"] == cx["member"].user_id
    assert first["navigation_binding"] != second["navigation_binding"]
    assert cx["a"].session.session_key not in str(first)
    from django.utils import timezone

    with patch("django.utils.timezone.now", return_value=timezone.now() + timedelta(hours=2)):
        renewed = cx["a"].get("/api/navigation/home/", {"destination": "/cards/"}).json()
        assert renewed["navigation_binding"] == first["navigation_binding"]
    cx["a"].logout()
    assert cx["a"].get("/api/navigation/home/").status_code == 302


def test_remembered_card_generation_reauthorizes_or_rejects_without_writes(cx):
    from pokemon_hunter.beta import collection

    group = find(cx, "a")
    generation = collection.generation(cx["actor"])
    prepare_reads(cx)
    before = dump(cx)
    current = f"/card-groups/{group['id']}/?" + urlencode({"generation": generation})
    checked = cx["a"].get("/api/navigation/home/", {"destination": current})
    assert checked.status_code == 200
    assert checked.json()["destination"] == current
    stale = f"/card-groups/{group['id']}/?" + urlencode({"generation": generation + 1})
    assert cx["a"].get("/api/navigation/home/", {"destination": stale}).status_code == 409
    assert cx["a"].get(stale).status_code == 200
    assert (
        cx["a"].get(f"/api/v2/card-groups/{group['id']}/", {"generation": generation + 1}).status_code == 409
    )
    assert dump(cx) == before


@pytest.mark.parametrize(
    "destination",
    [
        "/",
        "/login/",
        "/settings/",
        "/shopping/",
        "/goals/",
        "//host/cards/",
        "https://host/cards/",
        "/cards/?q=one&q=two",
        "/cards/?account_id=owner",
        "/cards/?scroll=10000001",
        "/pokedex/252/",
        "/cards/?q=%0a",
    ],
)
def test_finite_home_validation_rejects_unrelated_or_malformed_context(cx, destination):
    response = cx["a"].get("/api/navigation/home/", {"destination": destination})
    assert response.status_code == 400


def test_return_chain_rejects_card_cycles_unknown_fields_and_controls(env):
    from pokemon_hunter.beta import card_group_views

    group = "/card-groups/dg1-" + "a" * 64 + "/"
    for value in (
        group + "?" + urlencode({"return": group}),
        group + "?quantity=9",
        group + "?child=",
        group + "?generation=-1",
        group + "?child=%00",
        "/goals/?goal=one",
        "/pokedex/2/?" + urlencode({"return": group}),
    ):
        with pytest.raises(ValueError):
            card_group_views.return_context(value)
    assert card_group_views.return_context("/goals/") == "/goals/"


def test_shipped_client_storage_account_and_explicit_navigation_boundaries():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node is required for the shipped browser adapter checks")
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [
            node,
            str(root / "tests/cx07_navigation_cases.cjs"),
            str(root / "src/pokemon_hunter/beta/static/navigation.js"),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert "boundaries" in result.stdout
