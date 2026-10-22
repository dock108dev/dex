"""URL, image and aware timestamp admission; entirely offline engineering inputs."""

import pytest

from pokemon_hunter.beta.discovery_listing import end_timestamp, seller_image
from pokemon_hunter.security import ebay_url


@pytest.mark.parametrize(
    "value", [None, "", "bad", "2026-02-30T01:00:00Z", "2026-10-20T01:00:00", "2026-10-20T01:00:00+25:00"]
)
def test_invalid_missing_unzoned_times_remain_unknown(value):
    assert end_timestamp(value) is None


@pytest.mark.parametrize(
    "value", ["2026-10-20T01:00:00Z", "2026-10-20T01:00:00-04:00", "2000-01-01T00:00:00Z"]
)
def test_valid_aware_times_including_ended_remain_explicit(value):
    assert end_timestamp(value).endswith("+00:00")


@pytest.mark.parametrize(
    "value",
    [
        "javascript:alert(1)",
        "http://www.ebay.com/itm/1",
        "https://ebay.com.evil.invalid/itm/1",
        "https://www.ebay.com@evil.invalid/itm/1",
        "https://www.ebay.com:444/itm/1",
        "https://www.ebay.com/\\evil",
        "https://ebay.com/\n1",
    ],
)
def test_unsafe_seller_destinations_remain_blocked(value):
    assert ebay_url(value) is None


@pytest.mark.parametrize(
    "value",
    [
        "https://www.ebay.com/itm/123456789012",
        "https://www.ebay.com/itm/Jolteon/123456789012?var=123456789013",
        "https://ebay.com:443/itm/123456789012",
    ],
)
def test_supported_seller_urls_remain_actionable(value):
    assert ebay_url(value) == value


def test_only_checked_summary_cdn_images_are_admitted():
    valid = "https://i.ebayimg.com/images/g/AbC~123/s-l500.jpg"
    assert seller_image({"imageUrl": valid}) == valid
    for value in (
        "http://i.ebayimg.com/images/g/x/s-l500.jpg",
        "https://evil.invalid/images/g/x/s-l500.jpg",
        "https://i.ebayimg.com.evil.invalid/images/g/x/s-l500.jpg",
        "https://i.ebayimg.com@evil.invalid/images/g/x/s-l500.jpg",
        "https://i.ebayimg.com:444/images/g/x/s-l500.jpg",
        "https://i.ebayimg.com/images/g/x/s-l500.svg",
        valid + "?tracking=1",
        valid + "#fragment",
        "data:image/png;base64,AAAA",
    ):
        assert seller_image({"imageUrl": value}) is None
    assert seller_image(None) is None


def test_seller_image_csp_is_page_specific_and_single_directive():
    from django.http import HttpResponse

    from pokemon_hunter.beta.security import secure_response

    ordinary = secure_response(HttpResponse())
    assert "i.ebayimg.com" not in ordinary["Content-Security-Policy"]
    discovery = HttpResponse()
    discovery._dex_discovery_images = True
    discovery = secure_response(discovery)
    csp = discovery["Content-Security-Policy"]
    assert csp.count("img-src") == 1 and "https://i.ebayimg.com" in csp and "*" not in csp
