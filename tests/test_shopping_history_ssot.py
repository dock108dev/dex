"""Both persisted Shopping formats use one account/integrity and reevaluation service."""

import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from test_b1 import env as env
from test_b2 import b2 as b2
from test_lot_calculator import post, request
from test_lot_calculator import workspace as workspace
from test_migration import snapshot as snapshot
from test_shopping import NOW, inputs
from test_shopping import shop as shop

from pokemon_hunter.beta import collection, shopping
from pokemon_hunter.beta import lot_calculator as lot


def prepared(workspace, modern):
    return (
        lot.prepare(workspace["actor"], request(workspace), NOW)
        if modern
        else shopping.prepare(workspace["actor"], inputs(workspace), NOW)
    )


@pytest.mark.parametrize("modern", [False, True])
@pytest.mark.parametrize("mutation", ["future_schema", "missing_schema", "other_account"])
def test_save_rejects_unsupported_or_foreign_payload_before_write(workspace, modern, mutation):
    payload = prepared(workspace, modern)
    if mutation == "future_schema":
        payload["schema"] = "unsupported-future-format"
    elif mutation == "missing_schema":
        del payload["schema"]
    else:
        payload["context"]["account_id"] = workspace["member"].user_id
    before = shopping.listing(workspace["actor"])
    with pytest.raises(ValueError, match="schema|integrity"):
        shopping.store_payload(workspace["actor"], payload, "Rejected synthetic payload")
    assert shopping.listing(workspace["actor"]) == before


@pytest.mark.parametrize("modern", [False, True])
@pytest.mark.parametrize(
    "mutation", ["bytes", "malformed_json", "array", "future_schema", "missing_context", "other_account"]
)
def test_reopen_and_current_reject_corrupt_or_unsupported_history(workspace, modern, mutation):
    payload = prepared(workspace, modern)
    key = shopping.store_payload(workspace["actor"], payload, "Synthetic history")
    original = shopping.one(workspace["actor"], key)
    if mutation == "bytes":
        encoded, digest = original["snapshot"] + " ", original["snapshot_sha256"]
    else:
        changed = copy.deepcopy(payload)
        if mutation == "future_schema":
            changed["schema"] = "unsupported-future-format"
        elif mutation == "missing_context":
            del changed["context"]
        elif mutation == "other_account":
            changed["context"]["account_id"] = workspace["member"].user_id
        encoded = "{" if mutation == "malformed_json" else json.dumps([] if mutation == "array" else changed)
        digest = hashlib.sha256(encoded.encode()).hexdigest()
    collection.execute(
        "UPDATE saved_shopping_comparisons SET snapshot=%s,snapshot_sha256=%s WHERE id=%s",
        [encoded, digest, key],
    )
    before = shopping.listing(workspace["actor"])
    with (
        patch.object(lot, "prepare", side_effect=AssertionError("Invalid history cannot be reevaluated")),
        patch.object(
            shopping, "prepare", side_effect=AssertionError("Invalid history cannot be reevaluated")
        ),
    ):
        with pytest.raises(ValueError, match="schema|integrity"):
            shopping.reopen(workspace["actor"], key)
        assert workspace["a"].get(f"/shopping/saved/{key}/").status_code == 400
        assert post(workspace, f"/shopping/saved/{key}/current/", {}).status_code == 400
    assert shopping.listing(workspace["actor"]) == before
    assert shopping.one(workspace["actor"], key)["snapshot"] == encoded


@pytest.mark.parametrize("modern", [False, True])
def test_routes_delegate_to_shared_history_and_preserve_original(workspace, modern):
    payload = prepared(workspace, modern)
    key = shopping.store_payload(workspace["actor"], payload, "Synthetic history")
    original = shopping.one(workspace["actor"], key)
    before_inventory = collection.export_data(workspace["actor"])
    with patch.object(shopping, "reopen", wraps=shopping.reopen) as read:
        assert workspace["a"].get(f"/shopping/saved/{key}/").status_code == 200
        read.assert_called_once()
    with patch.object(shopping, "reevaluate", wraps=shopping.reevaluate) as evaluate:
        response = post(workspace, f"/shopping/saved/{key}/current/", {})
        assert response.status_code == 302
        evaluate.assert_called_once()
    new_key = response["Location"].strip("/").split("/")[-1]
    current = shopping.reopen(workspace["actor"], new_key)
    assert current["schema"] == payload["schema"]
    assert current["saved"]["parent_id"] == key
    assert current["request"] == payload["request"]
    result = current["scenarios"]["raw"]["result"] if modern else current["result"]
    assert result["full_selected_total"] == ("3.02" if modern else "28.00")
    assert shopping.one(workspace["actor"], key) == original
    assert collection.export_data(workspace["actor"]) == before_inventory
    assert workspace["b"].get(response["Location"]).status_code == 404


def test_duplicate_history_loader_stays_removed():
    assert not hasattr(lot, "reopen")
    assert shopping.SNAPSHOT_SCHEMAS == {"dex-shopping-v1", "dex-lot-v2"}


@pytest.mark.parametrize("script", ["qualify_shopping.py", "qualify_lot_calculator.py"])
def test_retired_browser_command_fails_before_creating_state(tmp_path, script):
    project = Path(__file__).resolve().parents[1]
    output = tmp_path / "must-not-exist"
    result = subprocess.run(
        [sys.executable, str(project / "scripts" / script), "--output", str(output)],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 2
    assert "browser journey removed; use current focused Shopping tests" in result.stderr
    assert not output.exists()
