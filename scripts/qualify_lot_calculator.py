"""Four-printing synthetic fixture/server helpers; obsolete browser journey is retired."""

import argparse
import json
from pathlib import Path

from qualify_shopping import prepare, serve


def fixtures(root, source):
    prepare(root, source)
    from django.conf import settings
    from django.db import connection

    from pokemon_hunter.beta import collection, shopping, store

    collection.execute("UPDATE catalog_sets SET name='Base Set'")
    actor = store.principal(1)
    cards = {p["name"]: p for p in collection.catalog(actor)}
    refs = []
    for grade, value in zip(("raw", "8", "9", "10"), ("2.550001", "9.10", "17.20", "31.30"), strict=True):
        refs.append(
            dict(
                card_id="synthetic-bulbasaur",
                value=value,
                currency="USD",
                as_of="2026-10-09",
                edition="standard",
                grade=grade,
                grader="Guide",
                variant_verified=True,
                source_url="https://example.test/synthetic-guide",
                basis="Fabricated guide fixture",
                estimated=False,
            )
        )
    (root / "parity-evidence/market_values.json").write_text(json.dumps(refs))
    (root / "protected.json").write_text(json.dumps(collection.export_data(actor), sort_keys=True))

    def basis(amount, kind):
        return dict(amount=amount, status="known", currency="USD", date="2026-10-09", price_kind=kind)

    raw = dict(
        selected_cards=[
            dict(
                selection_id=name,
                printing_id=cards[name]["id"],
                quantity=1,
                assumptions="Fabricated manual raw comparison",
                completion_confirmed=False,
                chosen_value_reference="group",
            )
            for name in ("Chansey", "Scyther")
        ],
        value_references=[
            dict(
                reference_id="group",
                kind="manual",
                amount="14",
                currency="USD",
                as_of="2026-10-09",
                assumptions="Fabricated group value, counted once",
                value_scope="selection_group_total",
                applies_to_quantities={"Chansey": 1, "Scyther": 1},
            )
        ],
        unknown_contents=dict(quantity=0),
        listing_observation=basis("12", "current_bid"),
        planned_bid=basis("20", "personal_planned_bid"),
        delivery_cost_inputs={
            b: {
                c: dict(amount=None, currency="USD", status="unknown", date="2026-10-09")
                for c in shopping.math.COSTS
            }
            for b in shopping.math.BASES
        },
    )
    old = shopping.save(actor, raw, "Synthetic old group")
    (root / "old-save.json").write_text(
        json.dumps(dict(id=old, sha256=shopping.one(actor, old)["snapshot_sha256"]))
    )
    connection.close()
    assert settings.ROOT == root.resolve()


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--serve", action="store_true")
    p.add_argument("--root", type=Path)
    p.add_argument("--port", type=int)
    a = p.parse_args()
    if a.serve:
        serve(a.root, a.output, a.port)
    else:
        p.error("Superseded lot-calculator browser journey removed; use current focused Shopping tests")
