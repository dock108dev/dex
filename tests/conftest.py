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


def synthetic_collection():
    """Public catalog with two explicitly synthetic owned cards; never read owner inventory."""
    import json

    from pokemon_hunter.collection import derive

    data = json.loads((ROOT / "config/pokedex_251.example.json").read_text())
    for key in ("base_set-2", "team_rocket-50"):
        data["cards"][key]["owned"] = True
    data["metadata"]["ownership_import_complete"] = True
    return derive(data)


def synthetic_project(destination):
    import json
    import shutil

    config = destination / "config"
    config.mkdir()
    for name in ("sets.yaml", "searches.yaml", "hunt.json", "demo_hunts.json", "raw_values.json"):
        shutil.copy2(ROOT / "config" / name, config / name)
    shutil.copy2(ROOT / "config/settings.example.yaml", config / "settings.yaml")
    (config / "pokedex_251.json").write_text(json.dumps(synthetic_collection()))
    (config / "market_values.json").write_text("[]")
    return destination
