"""Shared preparation preserves full-scope identity, publication and evidence records."""

from copy import deepcopy
from unittest.mock import patch

import pytest
from test_b1 import env as env
from test_b2 import b2 as b2
from test_b3 import b3 as b3
from test_b4 import b4 as b4
from test_effective_collection import cx as cx
from test_migration import snapshot as snapshot
from test_sealed_catalog import e1 as e1

from pokemon_hunter.beta import card_groups, collection_catalog, public_catalog, store
from pokemon_hunter.beta import catalog_read_records as records


@pytest.mark.parametrize("case", ["mixed", "conflict", "duplicates", "all_public", "none_public"])
def test_partition_matches_complete_visibility_scopes(cx, case):
    base = collection_catalog.catalog_entries(include_archived=True)[0]
    rows = []
    for n in range(40):
        row = deepcopy(base)
        row.update(
            id=f"partition-{n}",
            collector_number=str(n // 2),
            name=f"Card {n // 2}",
            publication_state="published",
            set_publication_state="published",
            language="en",
        )
        row["provenance"] = {"legacy_id": "overlapping-alias" if n < 5 else f"alias-{n}"}
        rows.append(row)
    if case != "all_public":
        rows[0]["publication_state"] = "archived"
        rows[1]["name"] = "Different literal name"
        rows[2]["language"] = "ja"
        rows[4]["unresolved_fields"] = ["name"]
    if case == "conflict":
        rows[8]["name"] = "Conflicting public identity"
        rows[10]["parent_printing_id"] = rows[11]["id"]
    if case == "duplicates":
        rows.append(dict(rows[6], name="Contradictory duplicate ID"))
    if case == "none_public":
        for row in rows:
            row["publication_state"] = "archived"
    pokemon = {r["id"] for r in store.rows("SELECT id FROM games WHERE game_key='pokemon'")}
    metadata = {r["id"]: r for r in public_catalog.cards(rows)}
    aliases = [{"game": "pokemon", "language": "en", "alias": "reviewed", "identity_key": "literal-key"}]
    original = card_groups.build_groups
    sizes = []

    def measured(selected, **kwargs):
        sizes.append(len(selected))
        return original(selected, **kwargs)

    with patch.object(card_groups, "build_groups", side_effect=measured):
        actual = records.materialize(rows, pokemon, aliases, metadata)
    with patch.object(
        records,
        "scopes",
        side_effect=lambda all_rows, public: (
            (("shared", all_rows),)
            if len(public) == len(all_rows)
            else (("retained", all_rows), ("public", public))
        ),
    ):
        expected = records.materialize(rows, pokemon, aliases, metadata)
    assert actual == expected
    if case in {"mixed", "conflict"}:
        assert sum(sizes) < len(rows) + 5, "Shared identities must not be constructed twice"
    assert ("reviewed", '["pokemon","en","reviewed"]', "literal-key") in actual["cr_aliases"]
