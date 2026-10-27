"""Shared request and edition policy regressions; temporary synthetic roots only."""

import inspect
import json
from unittest.mock import patch

import pytest
from test_b1 import env as env
from test_b2 import b2 as b2
from test_migration import snapshot as snapshot

from pokemon_hunter.beta import copy_editions


@pytest.mark.parametrize(
    "module,handler,field",
    [
        ("discovery_views", "searches", "run_id"),
        ("listing_views", "loads", "run_id"),
        ("hunter_views", "hunts", "run_id"),
        ("bulk_views", "template", "set"),
        ("shopping_views", "catalog", "q"),
    ],
)
@pytest.mark.parametrize("suffix", ["=one&{field}=two", "=&{field}=", "=one&unsupported=two"])
def test_scalar_boundaries_reject_before_domain_read(env, module, handler, field, suffix):
    from importlib import import_module

    from django.test import RequestFactory

    from pokemon_hunter.beta import bulk_input, discovery_views, request_inputs, shopping

    view = import_module("pokemon_hunter.beta." + module)
    request = RequestFactory().get("/?" + field + suffix.format(field=field))
    with (
        patch.object(discovery_views, "principal", return_value=(object(), "session")),
        patch("pokemon_hunter.beta.hunter_views.principal", return_value=(object(), "session")),
        patch.object(shopping, "browse") as browse,
        patch.object(bulk_input, "catalog_state") as catalog,
        patch.object(request_inputs, "single_values", wraps=request_inputs.single_values) as policy,
    ):
        with pytest.raises(ValueError):
            args = (request, object()) if module == "bulk_views" else (request,)
            inspect.unwrap(getattr(view, handler))(*args)
        policy.assert_called_once()
        browse.assert_not_called()
        catalog.assert_not_called()


def test_shopping_catalog_preserves_filters_and_paging(env):
    from django.test import RequestFactory

    from pokemon_hunter.beta import shopping_views

    request = RequestFactory().get("/?q=&set=s&grade=8&offset=40")
    who = object()
    with (
        patch.object(shopping_views, "actor", return_value=who),
        patch.object(shopping_views.shopping, "browse", return_value={"cards": list(range(90))}) as browse,
        patch.object(shopping_views, "private_json", side_effect=lambda data, request: data),
    ):
        result = inspect.unwrap(shopping_views.catalog)(request)
    browse.assert_called_once_with(who, {"q": "", "set": "s", "grade": "8"})
    assert result == {"cards": list(range(40, 80)), "total": 90, "offset": 40}


@pytest.mark.parametrize("edition", ["first_edition", "1st-edition"])
def test_import_accepts_same_first_edition_spellings_as_creation(b2, edition):
    from pokemon_hunter.beta import collection

    printing = dict(b2["catalog"][0], edition=edition, provenance="{}")
    raw = dict(printing_id=printing["id"], first_edition_selected=1)
    with (
        patch.object(collection, "catalog", return_value=[printing]),
        patch.object(copy_editions, "is_first", wraps=copy_editions.is_first) as policy,
    ):
        plan = collection.plan(
            b2["actor"],
            "import",
            {
                "format": "json",
                "text": json.dumps([raw]),
                "duplicate_policy": "allow",
            },
            "synthetic-edition-import",
        )
    assert plan["errors"] == []
    assert plan["creates"][0]["row"]["first_edition_selected"] == 1
    assert policy.called


@pytest.mark.parametrize("legacy", ["base_set_2-1", "wizards_black_star_promos-1"])
def test_import_and_selection_share_unsupported_set_policy(b2, legacy):
    from pokemon_hunter.beta import collection

    printing = dict(b2["catalog"][0], edition="first_edition", provenance=json.dumps({"legacy_id": legacy}))
    with pytest.raises(ValueError, match="no standard first-edition"):
        copy_editions.select({"revision": 0}, printing, "first_edition")
    with patch.object(collection, "catalog", return_value=[printing]):
        plan = collection.plan(
            b2["actor"],
            "import",
            {
                "format": "json",
                "text": json.dumps([{"printing_id": printing["id"], "first_edition_selected": 1}]),
                "duplicate_policy": "allow",
            },
            "synthetic-rejected-edition",
        )
    assert not plan["creates"]
    assert any("no standard first-edition" in error for error in plan["errors"])
