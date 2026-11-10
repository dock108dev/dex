"""Matched batch lookup experiment on a prepared engineering catalog."""

from time import perf_counter

import pytest
from perf04_helpers import prepare_reads
from test_account_read_performance import ownership
from test_b1 import env as env
from test_b2 import b2 as b2
from test_b3 import b3 as b3
from test_b4 import b4 as b4
from test_catalog_read_performance import seed
from test_effective_collection import cx as cx
from test_migration import snapshot as snapshot
from test_sealed_catalog import e1 as e1


@pytest.mark.no_cover
def test_matched_finished_hunt_catalog_queries(cx):
    from pokemon_hunter.beta import shopping_index, store

    seed(cx, 33083)
    ownership(cx, 5000)
    prepare_reads(cx)
    texts = [f"Pikachu {n} card lot" for n in range(32)]

    @shopping_index.indexed
    def measure(actor, batch):
        indexed = shopping_index.current(actor)
        original = store.rows
        counts = [0, 0]

        def counted(sql, *args, **kwargs):
            rows = original(sql, *args, **kwargs)
            if "ar_shopping_names" in sql:
                counts[0] += 1
                counts[1] += len(rows)
            return rows

        store.rows = counted
        try:
            start = perf_counter()
            rows = indexed.proposals_many(texts) if batch else [indexed.proposals(text) for text in texts]
            elapsed = (perf_counter() - start) * 1000
        finally:
            store.rows = original
        return {"ids": [[p["id"] for p in group] for group in rows], "ms": elapsed, "counts": counts}

    old = measure(cx["actor"], False)
    new = measure(cx["actor"], True)
    print(
        f"UX-06 lookup: sequential={old['ms']:.1f}ms {old['counts']}; batched={new['ms']:.1f}ms {new['counts']}"
    )
    assert new["ids"] == old["ids"]
    assert new["counts"][0] < old["counts"][0]

    from pokemon_hunter.beta import discovery_listing, discovery_lot_values

    raws = [
        dict(itemId=f"item-{n}", title=text, buyingOptions=["FIXED_PRICE"]) for n, text in enumerate(texts)
    ]

    @shopping_index.indexed
    def project(actor, batched):
        indexed = shopping_index.current(actor)
        if not batched:
            indexed.proposals_many = lambda inputs: [indexed.proposals(text) for text in inputs]
        rows = discovery_listing.received_rows(raws)
        start = perf_counter()
        discovery_lot_values.project(actor, raws, rows)
        return {"rows": rows, "ms": (perf_counter() - start) * 1000}

    individual = project(cx["actor"], False)
    combined = project(cx["actor"], True)
    print(
        f"UX-06 projection: sequential lookup={individual['ms']:.1f}ms; batch lookup={combined['ms']:.1f}ms"
    )
    assert combined["rows"] == individual["rows"]
