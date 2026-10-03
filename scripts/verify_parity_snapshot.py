"""Compare restored projections on a fresh private copied root; never owner provisioning."""

import argparse
import json
import secrets
from pathlib import Path

from pokemon_hunter.beta.cli import setup
from pokemon_hunter.collection import read, totals
from pokemon_hunter.valuation import valuation

parser = argparse.ArgumentParser()
parser.add_argument("--root", type=Path, required=True)
parser.add_argument("--snapshot", type=Path, required=True)
args = parser.parse_args()
setup(args.root)
from django.contrib.auth import get_user_model  # noqa: E402

from pokemon_hunter.beta import accounts, parity, store  # noqa: E402

assert not get_user_model().objects.exists(), "Use a fresh copied verification root"
user = accounts.bootstrap(secrets.token_urlsafe(32))
actor = store.principal(user.pk)
original = read(args.snapshot / "config/pokedex_251.json")
restored = parity.projection(actor)
assert {k: restored["totals"][k] for k in totals(original)} == totals(original)
for key, card in original["cards"].items():
    assert all(
        restored["cards"][key][field] == card.get(field, "Unknown")
        for field in (
            "owned",
            "first_edition",
            "name",
            "number",
            "rarity",
            "supertype",
            "dex_eligible",
            "pokemon_dex",
            "set",
            "set_id",
        )
    )
for key, species in original["pokedex"].items():
    assert set(restored["pokedex"][key]["eligible_cards"]) == set(species["eligible_cards"])
    assert restored["pokedex"][key]["dex_owned"] == species["dex_owned"]
legacy_values = valuation(original, args.snapshot / "config/market_values.json")
for grade, value in legacy_values["scenarios"].items():
    assert restored["valuation"]["conditional"][grade] == value
from fastapi.testclient import TestClient  # noqa: E402

from pokemon_hunter.app import create_app  # noqa: E402

# Only GETs; use a restored disposable app directory, never the live app.
with TestClient(
    create_app(args.snapshot), base_url="http://127.0.0.1:8765", client=("127.0.0.1", 50000)
) as client:
    for saved in parity.history(actor):
        old = client.get(f"/api/hunts/{saved['id']}").json()
        new = parity.projected_hunt(actor, saved["batch"], saved["id"])
        drop = {"id", "condition"}
        assert [{k: v for k, v in r.items() if k not in drop} for r in old["results"]] == [
            {k: v for k, v in r.items() if k not in drop} for r in new["results"]
        ]
report = {
    "result": "PASS",
    "catalog_entries": len(original["cards"]),
    "species": len(original["pokedex"]),
    "totals": restored["totals"],
    "conditional_guide_scenarios": restored["valuation"]["conditional"],
    "confirmed_variant_estimates": restored["valuation"]["confirmed"],
    "saved_hunts": len(parity.history(actor)),
    "semantic_differences": [
        "Physical copies multiply estimates, never unique printing/species completion",
        "Unchecked edition remains unresolved; legacy-equivalent guide numbers are conditional, excluded from confirmed totals",
        "Hidden results use opaque IDs and omit free-form condition text; scoring agrees",
    ],
}
(args.root / "projection-report.json").write_text(json.dumps(report, indent=2) + "\n")
print("Copied snapshot projections, conditional values and saved-hunt scores agree")
