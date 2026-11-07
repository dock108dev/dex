"""Focused SHOP-08 checks; disposable accounts and controlled image fields only."""

import json
import shutil
import subprocess
from html.parser import HTMLParser
from pathlib import Path

import pytest
from test_b1 import env as env
from test_b2 import b2 as b2
from test_listing_check import REST, raw
from test_lot_calculator import workspace as workspace
from test_migration import snapshot as snapshot
from test_shopping import shop as shop

from pokemon_hunter.beta import listing_details


def test_inspection_styles_use_one_request_with_the_complete_existing_cascade(workspace):
    class Styles(HTMLParser):
        def __init__(self):
            super().__init__()
            self.hrefs = []

        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if tag == "link" and attrs.get("rel") == "stylesheet":
                self.hrefs.append(attrs["href"])

    shell = workspace["a"].get("/shopping/check/")
    styles = Styles()
    styles.feed(shell.content.decode())
    assert styles.hrefs == ["/collection-assets/listing-shell.css"]
    response = workspace["a"].get(styles.hrefs[0])
    assert response.status_code == 200 and response["Content-Type"].startswith("text/css")
    static = Path(__file__).resolve().parents[1] / "src/pokemon_hunter/beta/static"
    expected = "\n".join(
        (static / name).read_text()
        for name in (
            "glass.css",
            "collection-base.css",
            "collection-browse.css",
            "discovery.css",
            "listing_check.css",
        )
    )
    assert response.content.decode() == expected
    assert len(response.content) < 128 * 1024
    assert workspace["a"].get("/collection-assets/not-an-asset.css").status_code == 404


def test_selected_inspection_orders_offer_before_optional_identifier_and_editor(workspace):
    response = workspace["a"].get(
        "/shopping/check/",
        {
            "discovery_run": "11111111-1111-4111-8111-111111111111",
            "item_id": "a" * 24,
            "return": "/shopping/",
        },
    )
    assert response.status_code == 200
    text = response.content.decode()
    assert '<div class="check-heading">' in text
    assert text.index('id="offer-overview"') < text.index('id="listing-identifier"')
    assert '<details id="listing-tools" class="check-panel">' in text
    assert '<details id="review-editor" class="check-panel review-editor">' in text
    directives = [part.split() for part in response["Content-Security-Policy"].split(";")]
    assert [parts for parts in directives if parts and parts[0] == "img-src"] == [
        [
            "img-src",
            "'self'",
            "https://assets.tcgdex.net",
            "https://raw.githubusercontent.com",
            "https://i.ebayimg.com",
        ]
    ]
    assert "private, no-store" in response["Cache-Control"]
    manual = workspace["a"].get("/shopping/check/").content.decode()
    assert '<details id="listing-tools" class="check-panel" open>' in manual
    assert '<details id="review-editor" class="check-panel review-editor" open>' in manual


@pytest.mark.parametrize(
    "url",
    [
        "https://evil.invalid/photo.jpg",
        "http://i.ebayimg.com/images/g/A/s-l1600.jpg",
        "https://i.ebayimg.com/images/g/A/s-l1600.jpg?track=1",
        "data:image/png;base64,AAAA",
    ],
)
def test_inspection_image_reuses_strict_admission(url):
    assert listing_details.details(REST, raw(image={"imageUrl": url}))["seller_image"] is None


def test_official_photo_and_time_are_temporary_detail_fields_without_changing_costs():
    url = "https://i.ebayimg.com/images/g/Engineering/s-l1600.jpg"
    value = listing_details.details(REST, raw(image={"imageUrl": url}, itemEndDate="2099-01-01T00:00:00Z"))
    assert value["seller_image"] == url
    assert value["ends_at"] == "2099-01-01T00:00:00+00:00"
    assert value["shipping"]["amount"] is None
    assert value["price"] == {"amount": "3.50", "currency": "USD"}


def test_inspection_browser_adapter_cleanup_and_explicit_editor():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node needed for adapter checks")
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [
            node,
            str(root / "tests/shop08_inspection_ui_cases.cjs"),
            str(root / "src/pokemon_hunter/beta/static/listing_check.js"),
            str(root / "src/pokemon_hunter/beta/static/discovery-display.js"),
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    report = json.loads(result.stdout)
    assert report["passed"] >= 7 and report["provider_calls"] == 0 and report["customer_data"] is False
