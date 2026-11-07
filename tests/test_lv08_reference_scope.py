"""Final evidence checks reread contributing ranges and still detect mutation."""

import pytest

from pokemon_hunter.beta import lot_calculator as lot


def test_contributing_ranges_reloaded_without_unrelated_source_rows(monkeypatch):
    contributing = dict(
        printing_id="selected",
        observation_id="one",
        _snapshot_version="release",
        _contract_sha256="contract",
        value="10",
    )
    unrelated = dict(contributing, printing_id="unrelated", observation_id="two")
    ref = dict(snapshot_version="release", source_contract="contract", evidence_id="one")
    seen = []
    rows = [contributing.copy()]

    def reload():
        seen.append(lot.price_snapshots._selection.get()[0])
        return rows

    monkeypatch.setattr(lot, "retained_records", reload)
    from pokemon_hunter.beta import shopping_index

    monkeypatch.setattr(shopping_index, "current", lambda actor: None)
    check = lot.reference_guard(None, [contributing, unrelated], [ref])
    check()
    assert seen == [frozenset({"selected"})]
    rows[0]["value"] = "11"
    with pytest.raises(ValueError, match="Contributing reference changed"):
        check()
    rows.clear()
    with pytest.raises(ValueError, match="Contributing reference changed"):
        check()
    assert lot.price_snapshots._selection.get() == (None, None)
