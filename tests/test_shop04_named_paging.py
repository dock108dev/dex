"""SHOP-04 engineering only: disposable journals and controlled one-send providers."""

import asyncio
import hashlib
import json
from dataclasses import replace
from types import SimpleNamespace

import httpx
import pytest
from django.http import Http404
from test_discovery import discovery as discovery

from pokemon_hunter.beta import discovery as d
from pokemon_hunter.beta import discovery_paging as paging
from pokemon_hunter.beta.discovery_transport import ProviderFailure, Transport


class Inline:
    def __init__(self, target, args, **kwargs):
        self.target, self.args = target, args

    def start(self):
        self.target(*self.args)


@pytest.fixture
def named(discovery):
    env = discovery
    calls = []

    class Controlled:
        async def request(self, stage, **kwargs):
            calls.append((stage, kwargs))
            if stage == "oauth":
                return dict(access_token="CONTROLLED_TOKEN", expires_in=300, token_type="Bearer")
            page = kwargs["search_options"]["named"]
            offset = page.offset
            # One exact repeat across pages, while distinct variations remain distinct.
            return {
                "total": 10000,
                "itemSummaries": [
                    {
                        "itemId": f"v1|123456789012|{(offset - 1 if i == 0 and offset else offset + i)}",
                        "title": "Engineering only",
                    }
                    for i in range(20)
                ],
            }

        async def close(self):
            pass

    env.monkeypatch.setattr(d, "Transport", Controlled)
    env.monkeypatch.setattr(d, "threading", SimpleNamespace(Thread=Inline))
    env.calls = calls
    return env


@pytest.mark.parametrize(
    "query", ["Hypno Fossil", "Jolteon", "Gengar Fossil", "Pokemon Jungle", "Pokemon Cards"]
)
def test_names_and_broad_words_need_no_catalog_match_or_forms(named, query):
    named.monkeypatch.setattr(d, "_candidate_data", lambda *args, **kwargs: [])
    result = d.start(named.actor, "session", {"query": query})
    assert result["state"] == "complete" and result["has_next"]
    browse = [kw for stage, kw in named.calls if stage == "browse"]
    assert len(browse) == 1 and browse[0]["query"] is None
    assert browse[0]["search_options"]["named"] == paging.NamedPage(query, "183455", "ending_soonest")
    assert result["choices"]["budget"] is None and result["choices"]["goal_id"] is None
    assert result["counts"]["browse"] == 1


def test_authoritative_set_survives_empty_candidates(named):
    named.monkeypatch.setattr(d, "_candidate_data", lambda *args, **kwargs: [])
    result = d.start(named.actor, "session", {"query": "Jolteon base 2", "set_id": "base_set"})
    request = next(kw for stage, kw in named.calls if stage == "browse")["search_options"]["named"]
    assert request.query == "Jolteon" and result["state"] == "complete"
    assert request.set_name == "Base Set"
    assert paging.checked_params(request)["aspect_filter"] == "categoryId:183455,Set:{Base Set}"
    with pytest.raises(ValueError, match="available set"):
        d.start(named.actor, "session", {"query": "Jolteon", "set_id": "invented"})


def test_more_same_query_category_refinements_original_lease_and_finite_bound(named):
    result = d.start(named.actor, "session", {"query": "Jolteon", "sort": "best_match", "browse_requests": 4})
    run = d._runs[result["run_id"]]
    original_created = run.created
    for page in range(1, 4):
        result = d.start(named.actor, "session", {"continuation_run": run.id})
        assert result["run_id"] == run.id and run.created == original_created
        assert result["pages_completed"] == page + 1 and result["state"] == "complete"
    requests = [kw["search_options"]["named"] for stage, kw in named.calls if stage == "browse"]
    assert [r.offset for r in requests] == [0, 20, 40, 60]
    assert all(r.query == "Jolteon" and r.category == "183455" and r.sort == "best_match" for r in requests)
    assert len(run.raws) == len(run.seen) == 77
    assert result["counts"]["oauth"] == 1 and result["counts"]["browse"] == 4
    assert not result["has_next"]
    with pytest.raises(ValueError, match="No next results"):
        d.start(named.actor, "session", {"continuation_run": run.id})
    root_key = hashlib.sha256(str(named.root).encode()).hexdigest()
    text = (named.root.parent / ".dex-shopping-discovery" / root_key / "attempts.jsonl").read_text()
    assert all(secret not in text for secret in ("Jolteon", "CONTROLLED_TOKEN", "Engineering only"))
    assert (
        sum(
            json.loads(line)["stage"] == "browse" and json.loads(line)["state"] == "completed"
            for line in text.splitlines()
        )
        == 4
    )


def test_both_one_category_per_explicit_action_alternates_without_hidden_scan(named):
    result = d.start(named.actor, "session", {"query": "Pokemon Cards", "product_type": "both"})
    for _ in range(3):
        result = d.start(named.actor, "session", {"continuation_run": result["run_id"]})
    requests = [kw["search_options"]["named"] for stage, kw in named.calls if stage == "browse"]
    assert [(r.category, r.offset) for r in requests] == [
        ("183455", 0),
        ("183454", 0),
        ("183455", 20),
        ("183454", 20),
    ]
    assert not result["has_next"]


def test_cursor_rejects_replacement_choices_wrong_session_and_concurrent_more(named):
    result = d.start(named.actor, "session", {"query": "Jolteon"})
    with pytest.raises(ValueError, match="changing search choices"):
        d.start(named.actor, "session", {"continuation_run": result["run_id"], "query": "Gengar"})
    with pytest.raises(Http404):
        d.start(named.actor, "other-session", {"continuation_run": result["run_id"]})

    class Held(Inline):
        def start(self):
            pass

    named.monkeypatch.setattr(d, "threading", SimpleNamespace(Thread=Held))
    d.start(named.actor, "session", {"continuation_run": result["run_id"]})
    with pytest.raises(ValueError, match="No next results"):
        d.start(named.actor, "session", {"continuation_run": result["run_id"]})
    assert len([1 for stage, _ in named.calls if stage == "browse"]) == 1


@pytest.mark.parametrize("payload", [{}, {"total": "100"}, {"total": -1}, {"total": 20}, {"total": True}])
def test_exhaustion_is_conservative_and_never_follows_next_url(payload):
    page = paging.NamedPage("Jolteon", "183455", "best_match")
    assert paging.following(page, {**payload, "next": "https://bad.invalid"}, [{}] * 20) is None
    assert paging.following(page, {"total": 1000}, [{}] * 19) is None


def test_stop_during_more_discards_late_page_and_preserves_consumed_accounting(named):
    result = d.start(named.actor, "session", {"query": "Jolteon"})

    class Stops:
        async def request(self, stage, **kwargs):
            d.stop(named.actor, "session", result["run_id"])
            return {"total": 1000, "itemSummaries": [{"itemId": "LATE"}]}

        async def close(self):
            pass

    named.monkeypatch.setattr(d, "Transport", Stops)
    result = d.start(named.actor, "session", {"continuation_run": result["run_id"]})
    run = d._runs[result["run_id"]]
    assert run.state == "stopped" and not run.raws and not result["has_next"]
    assert run.counts["browse"] == 2
    with pytest.raises(ValueError):
        d.start(named.actor, "session", {"continuation_run": run.id})


def test_error_ends_continuation_without_retry(named):
    result = d.start(named.actor, "session", {"query": "Jolteon"})

    class Fails:
        async def request(self, stage, **kwargs):
            raise ProviderFailure(stage, 503, uncertain=True)

        async def close(self):
            pass

    named.monkeypatch.setattr(d, "Transport", Fails)
    result = d.start(named.actor, "session", {"continuation_run": result["run_id"]})
    assert result["state"] == "failed" and not result["has_next"]
    assert result["counts"]["browse"] == 2


def test_checked_named_transport_wire_and_no_auto_correct_or_provider_next():
    requests = []

    class Body(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b'{"itemSummaries":[],"next":"https://bad.invalid"}'

    async def reply(request):
        requests.append(request)
        return httpx.Response(200, stream=Body())

    async def execute():
        transport = Transport(transport=httpx.MockTransport(reply))
        try:
            await transport.request(
                "browse",
                timeout=30,
                token="ENGINEERING",
                search_options={"named": paging.NamedPage("Hypno Fossil", "183455", "ending_soonest", 20)},
            )
            for options in (
                {"named": {}},
                {"named": paging.NamedPage("x", "183455", "best_match"), "offset": 1},
            ):
                with pytest.raises(ValueError):
                    await transport.request("browse", timeout=30, token="ENGINEERING", search_options=options)
        finally:
            await transport.close()

    asyncio.run(execute())
    assert len(requests) == 1
    assert dict(requests[0].url.params) == dict(
        q="Hypno Fossil",
        category_ids="183455",
        filter="buyingOptions:{FIXED_PRICE|AUCTION},deliveryCountry:US,itemLocationCountry:US",
        limit="20",
        offset="20",
        fieldgroups="EXTENDED",
        sort="endingSoonest",
    )
    for change in ({"offset": 1}, {"offset": 80}, {"category": "1"}, {"offset": True}, {"query": ""}):
        with pytest.raises(ValueError):
            paging.checked_params(replace(paging.NamedPage("x", "183455", "best_match"), **change))


def test_original_named_lease_blocks_more_and_dispatch_even_without_watchdog(named):
    result = d.start(named.actor, "session", {"query": "Jolteon"})
    run = d._runs[result["run_id"]]
    run.created -= d.EPHEMERAL_SECONDS
    with pytest.raises(d._Stopped):
        d._check_acquisition(run)
    assert run.state == "expired" and not run.raws
    with pytest.raises(ValueError):
        d.start(named.actor, "session", {"continuation_run": run.id})
    assert len([1 for stage, _ in named.calls if stage == "browse"]) == 1


def test_previous_page_review_stays_local_during_more_and_stop_revokes_it(named):
    from pokemon_hunter.beta import discovery_comparison

    result = d.start(named.actor, "session", {"query": "Jolteon"})
    run = d._runs[result["run_id"]]
    named.monkeypatch.setattr(
        discovery_comparison,
        "compare",
        lambda actor, raws, candidates: [
            dict(item_id=r["itemId"], title=r["title"], discovery_kind="mixed_lot") for r in raws
        ],
    )
    handle = d.status(named.actor, "session", run.id)["results"][0]["id"]
    run.state = "running"
    assert d.review_candidate(named.actor, "session", run.id, handle)["created"] == run.created
    assert len([1 for stage, _ in named.calls if stage == "browse"]) == 1
    d.stop(named.actor, "session", run.id)
    with pytest.raises(Http404):
        d.review_candidate(named.actor, "session", run.id, handle)
