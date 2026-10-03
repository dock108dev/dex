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


def test_no_unused_sample_entry_point():
    from pokemon_hunter.beta import parity

    assert not hasattr(parity, "sample")
    assert callable(parity.search)  # Explicit demo/live requests use the same service.


def test_provider_readers_share_settings_and_do_not_export_secrets(tmp_path, monkeypatch):
    import os

    from django.test import override_settings

    from pokemon_hunter import config
    from pokemon_hunter.beta import ebay_hunts

    (tmp_path / "config").mkdir()
    (tmp_path / "config/settings.yaml").write_text("environment: sandbox\nsearch:\n  max_pages: 5\n")
    (tmp_path / "config/sets.yaml").write_text("{}")
    (tmp_path / "config/searches.yaml").write_text("queries: [synthetic, synthetic]")
    (tmp_path / ".env").write_text(
        "EBAY_CLIENT_ID=file-key\nEBAY_CLIENT_ID=second-key\nEBAY_CLIENT_SECRET=file-secret\n"
        "EBAY_DELIVERY_POSTAL_CODE=07740\nUNRELATED_SECRET=excluded\n"
    )
    for key in ebay_hunts.ENV_KEYS | {"UNRELATED_SECRET"}:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("EBAY_CLIENT_ID", "process-key")
    monkeypatch.setattr(ebay_hunts, "configuration_root", lambda: tmp_path)
    before = dict(os.environ)
    with (
        override_settings(STAGING=False),
        patch.object(config, "load_settings", wraps=config.load_settings) as policy,
    ):
        provider, values = ebay_hunts.configuration()
        policy.assert_called_once_with(tmp_path, environ=values, required=False)
    assert values == {
        "EBAY_CLIENT_ID": "process-key",
        "EBAY_CLIENT_SECRET": "file-secret",
        "EBAY_DELIVERY_POSTAL_CODE": "07740",
    }
    assert os.environ == before
    assert provider.search.max_pages == 2 and provider.delivery_postal_code == "07740"
    with patch.object(config, "load_settings", wraps=config.load_settings) as policy:
        settings, _, queries = config.load_config(tmp_path)
        policy.assert_called_once_with(tmp_path)
    assert settings.environment == provider.environment and settings.search.max_pages == 5
    assert queries == ["synthetic"]


def test_env_policy_preserves_precedence_and_validates_before_export(tmp_path, monkeypatch):
    import os

    from pokemon_hunter import config

    path = tmp_path / ".env"
    path.write_text("SSOT_FIXTURE_KEY=first\nSSOT_FIXTURE_KEY=second\n")
    monkeypatch.setenv("SSOT_FIXTURE_KEY", "process")
    assert config.read_env(path) == {"SSOT_FIXTURE_KEY": "first"}
    config.load_env(path)
    assert os.environ["SSOT_FIXTURE_KEY"] == "process"
    monkeypatch.delenv("SSOT_FIXTURE_KEY")
    path.write_text("SSOT_FIXTURE_KEY=first\ninvalid entry\n")
    with pytest.raises(ValueError, match="Invalid .env entry"):
        config.load_env(path)
    assert "SSOT_FIXTURE_KEY" not in os.environ
    assert config.read_env(path, keys={"SSOT_FIXTURE_KEY"}) == {"SSOT_FIXTURE_KEY": "first"}


def test_provider_settings_optional_file_is_explicit_and_malformed_data_fails(tmp_path):
    from pokemon_hunter import config

    assert config.load_settings(tmp_path, environ={}, required=False).environment == "production"
    with pytest.raises(FileNotFoundError):
        config.load_settings(tmp_path, environ={})
    (tmp_path / "config").mkdir()
    path = tmp_path / "config/settings.yaml"
    for text in ("", "[]", "environment: unsupported"):
        path.write_text(text)
        with pytest.raises(ValueError):
            config.load_settings(tmp_path, environ={}, required=False)


def test_exact_ownership_policy_excludes_both_sources_of_uncertainty():
    from pokemon_hunter.beta import collection

    def copy(key, catalog="[]", identity="{}"):
        return dict(printing_id=key, unresolved_fields=catalog, provisional_identity=identity)

    active = [
        copy("resolved"),
        copy("catalog-uncertain", '["edition"]'),
        copy("copy-uncertain", identity='{"unresolved_fields":["finish"]}'),
        copy(None),
        copy("unpublished"),
    ]
    assert collection.exact_owned_printings(active) == {"resolved", "unpublished"}
    assert collection.exact_owned_printings(active, {"resolved"}) == {"resolved"}
    assert collection.exact_owned_printings(active, set()) == set()


def test_goal_and_hunt_exact_ownership_delegate_to_same_policy(env):
    from pokemon_hunter.beta import collection, goal_hunts

    active = [{"printing_id": "p", "unresolved_fields": "[]", "provisional_identity": "{}"}]
    catalog = [{"id": "p", "game_id": "g", "unresolved_fields": []}]
    actor = env["store"].principal(env["owner"].pk)
    with (
        patch.object(collection, "copies", return_value=active),
        patch.object(collection, "catalog", return_value=catalog),
        patch.object(collection.store, "verified"),
        patch.object(collection.store, "rows", return_value=[]),
        patch.object(collection, "exact_owned_printings", wraps=collection.exact_owned_printings) as policy,
    ):
        collection.goals(actor)
        assert policy.call_count == 1
        goal_hunts.project(
            actor,
            {"catalog": catalog, "cards": {}, "pokedex": {}},
            {"definition": {"policy": "exact", "items": []}},
        )
        assert policy.call_count == 2
        policy.assert_called_with(active)


def test_all_printing_checklists_delegate_to_same_shape(env):
    from pokemon_hunter.beta import collection, goal_filters

    entry = dict(
        id="p",
        game_id="g",
        set_id="s",
        name="Synthetic",
        set_name="Synthetic set",
        collector_number="1",
        edition=None,
        finish=None,
        variant=None,
        unresolved_fields=["edition"],
        catalog_version="v1",
        attributes={},
    )
    games = [dict(id="g", game_key="pokemon", name="Pokémon")]
    with (
        patch.object(collection, "catalog", return_value=[entry]),
        patch.object(collection.store, "rows", return_value=games),
        patch.object(goal_filters, "printing_items", wraps=goal_filters.printing_items) as policy,
    ):
        definitions = [
            collection.goal_definition(object(), request)
            for request in [
                dict(goal_kind="set", set_id="s"),
                dict(goal_kind="custom", printing_ids=["p"]),
                dict(goal_kind="filtered", filters=dict(game_id="g", completion="printings")),
            ]
        ]
        assert policy.call_count == 3
    assert definitions[0]["items"] == definitions[1]["items"] == definitions[2]["items"]
    assert definitions[0]["items"][0]["unresolved"] is True


def test_missing_game_does_not_silently_become_pokemon():
    from pokemon_hunter.beta import goal_hunts

    data = {
        "catalog": [{"id": "p", "game_id": "missing-game", "unresolved_fields": []}],
        "cards": {"card": {"printing_id": "p"}},
        "pokedex": {},
    }
    scope = {"definition": {"policy": "catalog", "items": [{"printing_ids": ["p"]}]}}
    with (
        patch.object(goal_hunts.service, "copies", return_value=[]),
        patch.object(goal_hunts.store, "rows", return_value=[]),
    ):
        with pytest.raises(ValueError, match="unavailable game"):
            goal_hunts.project(object(), data, scope)
