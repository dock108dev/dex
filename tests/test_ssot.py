"""Route ownership and shared configuration policy; synthetic roots only."""

import importlib
import json
from unittest.mock import patch

import pytest
from test_b1 import env as env
from test_migration import snapshot as snapshot

from pokemon_hunter.beta import deployment, scan_config, scans


@pytest.mark.parametrize("profile", ["b1", "b2", "parity", "b4", "staging"])
def test_each_route_has_one_selected_owner(env, profile):
    from django.test import override_settings
    from django.urls import clear_url_caches, resolve

    from pokemon_hunter.beta import collection_views, parity_views, urls, views

    b2 = profile != "b1"
    parity = profile in {"parity", "b4", "staging"}
    try:
        with override_settings(
            B2_ENABLED=b2,
            PARITY_ENABLED=parity,
            B3_ENABLED=profile in {"b4", "staging"},
            B4_ENABLED=profile in {"b4", "staging"},
            STAGING=profile == "staging",
            ROOT=env["root"],
        ):
            importlib.reload(urls)
            clear_url_caches()
            patterns = [str(p.pattern) for p in urls.urlpatterns]
            assert len(patterns) == len(set(patterns)), "A hidden alternate route has returned"
            selected = collection_views if b2 else views
            assert resolve("/").func is selected.home
            assert resolve("/api/export/").func is selected.export
            assert resolve("/api/inventory/synthetic/").func is selected.copy_detail
            assert resolve("/api/hunts/").func is (parity_views.hunts if parity else views.hunts)
            assert resolve("/api/hunts/00000000-0000-4000-8000-000000000001/1/").func is (
                parity_views.saved if parity else views.hunt_detail
            )
    finally:
        importlib.reload(urls)
        clear_url_caches()


@pytest.mark.parametrize("value", [True, None, "NaN", "Infinity", -1, 2, []])
def test_shared_policy_rejects_invalid_limits(value):
    config = dict(mode="openai", enabled=True, ceiling_usd=value, user_ceiling_usd=0.5)
    with pytest.raises(ValueError):
        scan_config.validate(config, require_complete=True)


def test_defaults_and_complete_configuration_have_distinct_contracts():
    assert scan_config.validate({}) == dict(
        mode="manual", enabled=True, ceiling_usd=1.0, user_ceiling_usd=0.5
    )
    with pytest.raises(ValueError):
        scan_config.validate({}, require_complete=True)
    for mode in ("manual", "fixture", "openai", "codex_cli"):
        original = dict(mode=mode, enabled=False, ceiling_usd="0.25", user_ceiling_usd="0.1")
        result = scan_config.validate(original, require_complete=True)
        assert result["ceiling_usd"] == 0.25 and result["mode"] == mode
        assert original["ceiling_usd"] == "0.25"


def test_local_and_persistent_readers_delegate_to_policy(env):
    from django.test import override_settings

    value = scan_config.validate({})
    (env["root"] / "scan-config.json").write_text(json.dumps(value))
    with patch.object(scan_config, "validate", wraps=scan_config.validate) as policy:
        with override_settings(STAGING=False, ROOT=env["root"]):
            assert scans.config() == value
            policy.assert_called_once_with(value, require_complete=False)
        policy.reset_mock()
        with (
            override_settings(STAGING=True),
            patch.object(scans.store, "rows", return_value=[{"value": json.dumps(value)}]),
        ):
            assert scans.config() == value
            policy.assert_called_once_with(value, require_complete=True)


def test_copy_import_uses_policy_before_opening_database(env):
    source = env["root"] / "synthetic.copied.sqlite3"
    value = scan_config.validate({})
    source.with_suffix(".scan-config.json").write_text(json.dumps(value))
    with (
        patch.object(deployment, "tables", return_value=[]),
        patch.object(scan_config, "validate", side_effect=ValueError("synthetic policy rejection")) as policy,
        patch.object(deployment.sqlite3, "connect") as connect,
    ):
        with pytest.raises(ValueError, match="synthetic policy rejection"):
            deployment.migrate_copy(source)
        policy.assert_called_once_with(value, require_complete=True)
        connect.assert_not_called()
    value["mode"] = "codex_cli"
    source.with_suffix(".scan-config.json").write_text(json.dumps(value))
    with (
        patch.object(deployment, "tables", return_value=[]),
        patch.object(deployment.sqlite3, "connect") as connect,
    ):
        with pytest.raises(ValueError, match="does not support codex_cli"):
            deployment.migrate_copy(source)
        connect.assert_not_called()
