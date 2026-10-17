"""Offline qualification of the separate finite Hunter acquisition contract."""

import asyncio
import json
from copy import deepcopy
from datetime import UTC, datetime, timedelta, timezone

import httpx
import pytest

from pokemon_hunter.beta import hunter_query as hq
from pokemon_hunter.beta.discovery_transport import ProviderFailure, Transport

START = datetime(2026, 10, 16, 12, 34, 56, 123456, tzinfo=UTC)
END = START + timedelta(hours=24)


class Stream(httpx.AsyncByteStream):
    def __init__(self, body):
        self.body = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.closed = False

    async def __aiter__(self):
        for offset in range(0, len(self.body), 4096):
            yield self.body[offset : offset + 4096]

    async def aclose(self):
        self.closed = True


def run_transport(*, body=None, request=None, status=200, headers=None, query=None, options=None):
    sent = []
    stream = Stream(body if body is not None else {"itemSummaries": []})

    async def handler(wire):
        sent.append(wire)
        return httpx.Response(status, headers=headers or {}, stream=stream)

    async def execute():
        transport = Transport(transport=httpx.MockTransport(handler))
        try:
            return await transport.request(
                "browse",
                timeout=30,
                token="offline-fixture-token",
                query=query,
                search_options=options
                if options is not None
                else {"hunter": request or hq.plan(START)["requests"][0]},
            )
        finally:
            await transport.close()

    return execute, sent, stream


def test_all_year_listings_first_plan_is_exactly_two_pages():
    captured = hq.plan(START)
    assert captured["start"] == "2026-10-16T12:34:56.123456Z"
    assert captured["end"] == "2026-10-17T12:34:56.123456Z"
    assert len(captured["requests"]) == 2
    assert hq.SUMMARY_LIMIT == 400
    for request, lane in zip(captured["requests"], hq.LANES, strict=True):
        assert request == {"lane": lane, "start": captured["start"], "end": captured["end"], "limit": 200}
        params = hq.checked_params(request)
        assert params["category_ids"] == "183454"
        assert params["aspect_filter"] == "categoryId:183454,Game:{Pokémon TCG},Language:{English}"
        assert params["limit"] == 200 and params["offset"] == 0
        assert set(params) == {
            "category_ids",
            "aspect_filter",
            "filter",
            "limit",
            "offset",
            "fieldgroups",
        } | ({"sort"} if lane == "auction" else set())
        assert not any(word in str(params).casefold() for word in ("vintage", "wotc", "kanto", "johto"))
        assert not any(key in params for key in ("q", "epid", "gtin", "year", "card", "species", "owned"))


def test_auction_uses_real_end_range_bin_has_no_auction_window_filter():
    auction, buy_now = (hq.checked_params(r) for r in hq.plan(START)["requests"])
    assert auction["filter"] == (
        "buyingOptions:{AUCTION},deliveryCountry:US,itemLocationCountry:US,"
        "itemEndDate:[2026-10-16T12:34:56.123456Z..2026-10-17T12:34:56.123456Z]"
    )
    assert auction["sort"] == "endingSoonest"
    assert buy_now["filter"] == "buyingOptions:{FIXED_PRICE},deliveryCountry:US,itemLocationCountry:US"
    assert "sort" not in buy_now


def test_start_converts_one_aware_instant_to_utc():
    eastern = START.astimezone(timezone(timedelta(hours=-4)))
    assert hq.plan(eastern) == hq.plan(START)


@pytest.mark.parametrize("start", [datetime(2026, 10, 16), "2026-10-16T12:34:56", "bad", None, 0])
def test_naive_or_malformed_start_refused(start):
    with pytest.raises(ValueError):
        hq.plan(start)


@pytest.mark.parametrize("page_size", [0, 201, True, 1.0, "200", None])
def test_page_limit_requires_explicit_bounded_integer(page_size):
    with pytest.raises(ValueError):
        hq.plan(START, page_size=page_size)


@pytest.mark.parametrize(
    "change",
    [
        {"lane": "next"},
        {"limit": 201},
        {"limit": True},
        {"offset": 200},
        {"next": "https://api.ebay.com/continue"},
        {"category_ids": "183456"},
        {"q": "Pokemon Base Set Abra"},
        {"end": "2026-10-18T12:34:56.123456Z"},
        {"start": "2026-10-16T12:34:56"},
    ],
)
def test_transport_shape_rejects_expansion(change):
    request = hq.plan(START)["requests"][0] | change
    execute, sent, _ = run_transport(request=request)
    with pytest.raises(ValueError):
        asyncio.run(execute())
    assert not sent


def test_exact_broad_wire_request_has_no_keyword_or_automatic_continuation():
    for lane in hq.plan(START)["requests"]:
        execute, sent, stream = run_transport(
            request=lane, body={"itemSummaries": [], "next": "https://api.ebay.com/next", "total": 100000}
        )
        result = asyncio.run(execute())
        assert result["total"] == 100000
        assert len(sent) == 1 and stream.closed
        assert sent[0].url.path == "/buy/browse/v1/item_summary/search"
        assert sent[0].url.host == "api.ebay.com"
        assert dict(sent[0].url.params) == {key: str(value) for key, value in hq.checked_params(lane).items()}
        assert sent[0].headers["x-ebay-c-marketplace-id"] == "EBAY_US"
        assert sent[0].extensions["timeout"] == {key: 30 for key in ("connect", "read", "write", "pool")}


@pytest.mark.parametrize("options,query", [({"sort": "best_match", "hunter": {}}, None), (None, "Mew 151")])
def test_hunter_does_not_accept_shopping_choices_or_per_card_queries(options, query):
    execute, sent, _ = run_transport(options=options, query=query)
    with pytest.raises(ValueError):
        asyncio.run(execute())
    assert not sent


def test_ordinary_shopping_retains_exact_20_summary_query_contract():
    execute, sent, _ = run_transport(query="Pokemon Base Set Abra 43", options={"sort": "ending_soonest"})
    asyncio.run(execute())
    assert dict(sent[0].url.params) == {
        "q": "Pokemon Base Set Abra 43",
        "filter": "buyingOptions:{FIXED_PRICE|AUCTION},deliveryCountry:US,itemLocationCountry:US",
        "limit": "20",
        "offset": "0",
        "fieldgroups": "EXTENDED",
        "sort": "endingSoonest",
    }


def test_hunter_allows_200_summaries_in_one_received_page():
    execute, sent, _ = run_transport(body={"itemSummaries": [{"itemId": str(n)} for n in range(200)]})
    assert len(asyncio.run(execute())["itemSummaries"]) == 200
    assert len(sent) == 1


@pytest.mark.parametrize("rows", [[{}] * 201, {}, None, ["malformed"]])
def test_hunter_rejects_overcount_or_malformed_summary_collection(rows):
    execute, sent, stream = run_transport(body={"itemSummaries": rows})
    with pytest.raises(ProviderFailure):
        asyncio.run(execute())
    assert len(sent) == 1 and stream.closed


def test_hunter_validates_requested_smaller_page_count():
    request = hq.plan(START, page_size=1)["requests"][0]
    execute, sent, _ = run_transport(request=request, body={"itemSummaries": [{}, {}]})
    with pytest.raises(ProviderFailure):
        asyncio.run(execute())
    assert len(sent) == 1


@pytest.mark.parametrize("extra,valid", [(0, True), (1, False)])
def test_hunter_stream_response_byte_bound(extra, valid):
    prefix, suffix = b'{"itemSummaries":[],"padding":"', b'"}'
    body = prefix + b"x" * (hq.RESPONSE_BYTE_LIMIT - len(prefix) - len(suffix) + extra) + suffix
    execute, sent, stream = run_transport(body=body)
    if valid:
        assert asyncio.run(execute())["itemSummaries"] == []
    else:
        with pytest.raises(ProviderFailure):
            asyncio.run(execute())
    assert len(sent) == 1 and stream.closed


@pytest.mark.parametrize(
    "status,headers", [(302, {"Location": "https://example.invalid/"}), (401, {}), (500, {})]
)
def test_hunter_failure_is_one_send_without_redirect_retry_or_reauthentication(status, headers):
    execute, sent, stream = run_transport(status=status, headers=headers)
    with pytest.raises(ProviderFailure):
        asyncio.run(execute())
    assert len(sent) == 1 and stream.closed


def test_compressed_response_does_not_bypass_body_bound():
    execute, sent, stream = run_transport(headers={"Content-Encoding": "gzip"})
    with pytest.raises(ProviderFailure):
        asyncio.run(execute())
    assert len(sent) == 1 and stream.closed


def eligibility(raw, lane="auction", *, now=START - timedelta(seconds=1)):
    return hq.lane_eligibility(raw, lane, START, END, now=now)


@pytest.mark.parametrize("end", [START, END])
def test_utc_auction_window_endpoints_are_inclusive(end):
    assert eligibility({"buyingOptions": ["AUCTION"], "itemEndDate": end.isoformat()}) is None


@pytest.mark.parametrize("end", [START - timedelta(microseconds=1), END + timedelta(microseconds=1)])
def test_auction_outside_captured_window_is_explicit(end):
    assert (
        eligibility({"buyingOptions": ["AUCTION"], "itemEndDate": end.isoformat()})
        == "outside_auction_window"
    )


@pytest.mark.parametrize("end", [None, "bad", "2026-10-16T15:00:00", "", 0, True])
def test_auction_requires_parseable_aware_end(end):
    assert eligibility({"buyingOptions": ["AUCTION"], "itemEndDate": end}) == "invalid_end_time"


def test_auction_equivalent_timezone_is_validated_as_utc_and_ended_rechecked():
    raw = {"buyingOptions": ["AUCTION"], "itemEndDate": "2026-10-16T09:00:00-04:00"}
    assert eligibility(raw) is None
    assert eligibility(raw, now=datetime(2026, 10, 16, 13, tzinfo=UTC)) == "ended_offer"
    assert eligibility(raw, now=datetime(2026, 10, 16, 14, tzinfo=UTC)) == "ended_offer"


def test_bin_does_not_need_auction_end_timestamp_or_pokemon_word_in_title():
    raw = {"title": "Gardevoir ex 245/198 Scarlet & Violet", "buyingOptions": ["FIXED_PRICE"]}
    assert eligibility(raw, "buy_it_now") is None
    assert eligibility(raw) == "buying_option_unavailable"


def test_mixed_options_survive_local_checks_and_bin_can_outlive_window():
    raw = {
        "title": "Modern Trainer 001/100",
        "buyingOptions": ["FIXED_PRICE", "AUCTION", "BEST_OFFER"],
        "itemEndDate": (END + timedelta(days=1)).isoformat(),
    }
    original = deepcopy(raw)
    assert eligibility(raw) == "outside_auction_window"
    assert eligibility(raw, "buy_it_now") is None
    assert raw == original


@pytest.mark.parametrize("end", ["bad", "2026-10-16T00:00:00Z"])
def test_bin_supplied_malformed_or_ended_time_is_not_assumed_available(end):
    raw = {"buyingOptions": ["FIXED_PRICE"], "itemEndDate": end}
    assert eligibility(raw, "buy_it_now", now=START) in {"invalid_end_time", "ended_offer"}


@pytest.mark.parametrize(
    "metadata",
    [
        {"listingMarketplaceId": "EBAY_GB"},
        {"leafCategoryIds": ["183456"]},
        {"localizedAspects": [{"name": "Game", "value": "Magic: The Gathering"}]},
        {"localizedAspects": [{"name": "Language", "value": "Japanese"}]},
    ],
)
def test_supplied_contradictory_scope_metadata_is_rejected(metadata):
    assert eligibility({"buyingOptions": ["FIXED_PRICE"]} | metadata, "buy_it_now") == "scope_conflict"


def test_missing_scope_metadata_uses_verified_search_scope_and_correct_claims_are_accepted():
    raw = {
        "buyingOptions": ["FIXED_PRICE"],
        "listingMarketplaceId": "EBAY_US",
        "leafCategoryIds": ["183454", "183456"],
        "localizedAspects": [
            {"name": "Game", "value": "Pokémon TCG"},
            {"name": "Language", "value": "English"},
            {"name": "Card Type", "value": "Energy"},
        ],
    }
    assert eligibility(raw, "buy_it_now") is None


def test_unavailable_stock_and_wrong_lane_remain_explicit():
    raw = {
        "buyingOptions": ["FIXED_PRICE"],
        "estimatedAvailabilities": [{"estimatedAvailabilityStatus": "OUT_OF_STOCK"}],
    }
    assert eligibility(raw, "buy_it_now") == "unavailable"
    assert eligibility({"buyingOptions": "AUCTION"}) == "unsupported_buying_options"
    assert eligibility([]) == "malformed_summary"
