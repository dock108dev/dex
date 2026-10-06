"""D1d real metadata acceptance and the current full-set bridge blocker."""

import copy
import json
from pathlib import Path

import pytest

from pokemon_hunter.beta import sealed_catalog as cat

ROOT = Path(__file__).resolve().parents[1]


def package():
    return json.loads((ROOT / "config/sealed/2026-10-05-det1/package.json").read_text())


def test_full_set_canonical_identity_and_unknown_distribution():
    p = cat.validate(package())
    assert len(p["species"]) == 1025
    assert len(p["printings"]) == 18
    assert {r["species_id"] for r in p["printings"]} == {
        "ndex:0001",
        "ndex:0272",
        "ndex:0755",
        "ndex:0004",
        "ndex:0006",
        "ndex:0059",
        "ndex:0054",
        "ndex:0129",
        "ndex:0658",
        "ndex:0025",
        "ndex:0122",
        "ndex:0150",
        "ndex:0068",
        "ndex:0039",
        "ndex:0209",
        "ndex:0108",
        "ndex:0132",
        "ndex:0289",
    }
    assert sum(int(r["species_id"].split(":")[1]) <= 151 for r in p["printings"]) == 13
    assert all(r["finish"] is None for r in p["printings"])
    assert all(m["status"] == "unknown" for m in p["memberships"])
    assert all(not p[k] for k in ["products", "packs", "offers", "observations", "guaranteed"])


def test_full_set_bridge_supports_canonical_species_above_251():
    # The public reviewed bridge exercises the former out-of-range blocker.
    # Historical rejection receipts remain private operational evidence.
    p = json.loads((ROOT / "config/sealed/2026-10-05-det1-e1c/package.json").read_text())
    assert len(p["bridges"][0]["package"]["cards"]) == 18
    validated = cat.validate(p)
    numbers = {c["metadata"]["pokemon_dex"] for c in validated["bridges"][0]["package"]["cards"]}
    assert {272, 755, 658, 289} <= numbers


@pytest.mark.parametrize("fault", ["cameo", "language", "booster", "remap"])
def test_unsupported_source_or_identity_cannot_be_accepted(fault):
    p = copy.deepcopy(package())
    if fault == "cameo":
        p["printings"][0]["category"] = "trainer"
    elif fault == "language":
        p["printings"][0]["language"] = "fr"
    elif fault == "booster":
        p["memberships"][0]["status"] = "booster"
    else:
        p["mappings"][-1]["internal_id"] = "unretained-identity"
    with pytest.raises(ValueError):
        cat.validate(p)
