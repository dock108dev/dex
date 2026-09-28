import copy
from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml

from pokemon_hunter.models import Settings

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def settings():
    return Settings(delivery_postal_code="08803")


@pytest.fixture
def catalog():
    return yaml.safe_load((ROOT / "config/sets.yaml").read_text())


@pytest.fixture
def now():
    return datetime(2026, 9, 24, 12, tzinfo=UTC)


@pytest.fixture
def raw():
    return copy.deepcopy(
        {
            "itemId": "v1|123|0",
            "title": "100 Pokemon cards Neo Genesis lot no trainers or energy",
            "itemWebUrl": "https://www.ebay.com/itm/123",
            "buyingOptions": ["FIXED_PRICE"],
            "price": {"value": "30.00", "currency": "USD"},
            "shippingOptions": [
                {"shippingCost": {"value": "5.00", "currency": "USD"}, "shippingCostType": "FIXED"}
            ],
            "seller": {"username": "synthetic-fixture"},
        }
    )
