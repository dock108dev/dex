"""UX-05 wire, release and protected named-search regressions."""

import uuid
from types import SimpleNamespace

import pytest
from django.http import Http404
from test_hunter_lots import entries as entries
from test_hunter_policy import everyday as everyday
from test_lv03_hunt import env as env
from test_lv03_hunt import offer

from pokemon_hunter.beta import (
    discovery,
    discovery_catalog,
    discovery_paging,
    discovery_singles,
    hunter_policy,
    lot_hunt,
    species_scope,
)
from pokemon_hunter.beta import discovery_comparison as comparison


def card(name, number, expansion, **changes):
    return dict(
        {
            "id": f"{expansion}-{number}",
            "name": name,
            "collector_number": number,
            "set_name": expansion,
            "set_id": expansion,
            "language": "en",
            "attributes": {},
        },
        **changes,
    )


DATES = {
    key: dict(start=stamp, end=stamp, language="en")
    for key, stamp in {"Fossil": "1999-10-10", "Team Rocket": "2000-04-24", "Boundary": "2001-01-01"}.items()
}
CARDS = [
    card("Lapras", "10", "Fossil"),
    card("Lapras", "25", "Fossil"),
    card("Dratini", "53", "Team Rocket"),
    card("Lapras", "1/10", "Boundary"),
    card("Lapras", "1/10", "Unknown"),
]


@pytest.mark.parametrize(
    "title,status,finish",
    [
        ("Lapras Fossil 10/62 English", "eligible", "holo"),
        ("Fossil Lapras #25/62 English non-holo", "eligible", "normal"),
        ("Team Rocket Dratini 53/82 English", "eligible", None),
        ("Team Rocket Dratini 53/82 English LP/MP", "eligible", None),
        ("Lapras Boundary 1/10", "later", None),
        ("Lapras Unknown 1/10", "unknown", None),
        ("Fossil Lapras #10/62 #25/62", "conflicting", None),
        ("Fossil Lapras #10/63", "conflicting", None),
        ("Fossil Lapras #10/62 non-holo", "conflicting", None),
        ("Fossil Lapras #25/62 Japanese", "conflicting", None),
        ("Fossil Lapras #25/62 English Japanese", "conflicting", None),
        ("Fossil Lapras #25/62 1999-2000 copyright", "unknown", None),
        ("Fossil Lapras #25/62 reprint", "unknown", None),
        ("Lapras", "unknown", None),
    ],
)
def test_received_singles_use_catalog_evidence(monkeypatch, title, status, finish):
    monkeypatch.setattr(comparison.store, "verified", lambda actor: actor)
    run = SimpleNamespace(
        choices=discovery.Choices(product_type="singles", single_buying="both"),
        single_targets=set(),
        single_set_name=None,
    )
    rows = comparison._project(
        None, [offer(title=title)], CARDS, [], artwork={}, singles=run, release_dates=DATES
    )
    assert len(rows) == 1
    row = rows[0]
    assert row["single_scope_match"] and row["reference"] is None
    assert row["release"]["status"] == status
    assert row["release"].get("finish") == finish
    assert not row["release"].get("edition")


def test_cutoff_is_inclusive_and_legacy_period_unchanged():
    date = {"start": "2000-12-31", "end": "2000-12-31", "language": "en"}
    assert species_scope.date_match(date, {"date_to": discovery_singles.THROUGH_2000}) is True
    assert species_scope.date_match(date, {"released": "pre-2000"}) is False
    assert (
        discovery_catalog.validate_page(
            {"single_buying": "auction", "single_release": "through2000", "era_filter": "pre2000"}
        )["era_filter"]
        == "pre2000"
    )


def test_singles_use_named_pages_and_shared_durable_allowance(env, monkeypatch):
    monkeypatch.setattr(discovery, "Transport", lot_hunt.Transport)
    monkeypatch.setattr(
        discovery, "threading", SimpleNamespace(Thread=lambda **kw: SimpleNamespace(start=lambda: None))
    )
    monkeypatch.setattr(discovery, "close_old_connections", lambda: None)
    monkeypatch.setattr(discovery, "_actions", {})
    monkeypatch.setattr(discovery, "_candidate_data", lambda *a, **kw: CARDS)
    monkeypatch.setattr(comparison.collection, "catalog", lambda *a, **kw: CARDS)
    monkeypatch.setattr(species_scope, "release_dates", lambda: DATES)
    env.bin = [offer(title="Fossil Lapras #25/62 English")]
    env.auction = [offer(1, lane="auction", title="Fossil Lapras #10/62 English")]
    request_id = str(uuid.uuid4())
    raw = dict(product_type="singles", single_buying="both", query="Lapras", listing_years="pre2000")
    receipt = discovery.start_action(env.actor, "session", raw, request_id)
    run = discovery._runs[receipt["run_id"]]
    original = run.created
    discovery._worker(run, env.actor, ("fixture-client", "fixture-secret"))
    first = discovery.status(env.actor, "session", run.id, received=True)
    assert first["next_buying_lane"] == "auction"
    assert first["counts"]["summary_count"] == 1
    assert first["results"][0]["release"]["finish"] == "normal"
    assert discovery.action_status(env.actor, "session", request_id, received=True) == first
    with pytest.raises(Http404):
        discovery.status(env.actor, "another-session", run.id)
    assert len(env.calls) == 2
    next_receipt = discovery.start(env.actor, "session", {"continuation_run": run.id})
    assert next_receipt["run_id"] == run.id and run.created == original
    discovery._worker(run, env.actor, ("fixture-client", "fixture-secret"))
    final = discovery.status(env.actor, "session", run.id, received=True)
    assert final["counts"]["summary_count"] == 2 and not final["has_next"]
    assert {r["release"]["finish"] for r in final["results"]} == {"holo", "normal"}
    params = [r.url.params for r in env.calls[1:]]
    assert all(p["q"] == "Lapras" and p["category_ids"] == "183454" for p in params)
    assert [p["aspect_filter"] for p in params] == [
        "categoryId:183454,Year Manufactured:{1996|1997|1998|1999}"
    ] * 2
    assert [p["filter"].split(",")[0] for p in params] == [
        "buyingOptions:{FIXED_PRICE}",
        "buyingOptions:{AUCTION}",
    ]
    assert hunter_policy.remaining(run.owner[0], run.allowance)["total"] == 2
    discovery.stop(env.actor, "session", run.id)
    assert not discovery.status(env.actor, "session", run.id, received=True)["results"]
    assert len(env.calls) == 3


def test_broad_wire_is_finite_and_singles_optional_set_is_a_keyword():
    (page,) = discovery_paging.singles_pages("Pokemon", "buy_now", vintage_sample=True)
    params = discovery_paging.checked_params(page)
    assert params["q"] == "Pokemon" and params["limit"] == 20
    assert params["category_ids"] == "183454"
    assert params["aspect_filter"] == "categoryId:183454,Game:{Pokémon TCG},Set:{Base Set|Fossil|Neo Genesis}"
    assert discovery_paging.following(page, {"total": 80}, [None] * 20).vintage_sample
    assert discovery.submitted_query("Lapras", set_name="Fossil") == "Lapras Fossil"
    (named,) = discovery_paging.singles_pages("Lapras Fossil", "buy_now")
    assert "aspect_filter" not in discovery_paging.checked_params(named)


def test_pack_in_singles_category_is_excluded(monkeypatch):
    monkeypatch.setattr(comparison.store, "verified", lambda actor: actor)
    run = SimpleNamespace(
        choices=discovery.Choices(product_type="singles", single_buying="both"),
        single_targets=set(),
        single_set_name=None,
    )
    assert not comparison._project(
        None,
        [offer(title="Vintage Pokemon Cards Pack! 1999 WOTC")],
        CARDS,
        [],
        artwork={},
        singles=run,
        release_dates=DATES,
    )
