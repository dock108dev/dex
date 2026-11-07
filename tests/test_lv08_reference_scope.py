"""Final evidence checks reread contributing ranges and still detect mutation."""

import pytest

from pokemon_hunter.beta import lot_calculator as lot


@pytest.mark.parametrize("legacy", [False, True])
def test_contributing_ranges_reloaded_without_unrelated_source_rows(monkeypatch, legacy):
    contributing = dict(
        printing_id="selected",
        observation_id="one",
        _snapshot_version="release",
        _contract_sha256="contract",
        value="10",
    )
    unrelated = dict(contributing, printing_id="unrelated", observation_id="two")
    ref = (
        dict(raw_record=contributing)
        if legacy
        else dict(snapshot_version="release", source_contract="contract", evidence_id="one")
    )
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


def test_empty_reference_set_does_not_hash_or_reload_unrelated_prices(monkeypatch):
    from pokemon_hunter.beta import shopping_index

    monkeypatch.setattr(shopping_index, "current", lambda actor: None)

    def unrelated(*args):
        pytest.fail("An empty contributing set must not process unrelated prices")

    monkeypatch.setattr(lot.shopping, "digest", unrelated)
    monkeypatch.setattr(lot, "retained_records", unrelated)
    lot.reference_guard(None, [dict(value=str(n)) for n in range(2000)], [])()


def test_legacy_guard_filters_other_cards_but_rechecks_the_full_record(monkeypatch):
    from pokemon_hunter.beta import shopping_index

    monkeypatch.setattr(shopping_index, "current", lambda actor: None)
    wanted = dict(card_id="selected", value="10", grade="raw")
    rows = [wanted.copy(), *[dict(card_id=f"other-{n}", value="1") for n in range(2000)]]
    digest = lot.shopping.digest

    def checked(row):
        assert not row["card_id"].startswith("other-"), "Unrelated cards must not be hashed"
        return digest(row)

    monkeypatch.setattr(lot.shopping, "digest", checked)
    monkeypatch.setattr(lot, "retained_records", lambda: rows)
    check = lot.reference_guard(None, rows, [dict(raw_record=wanted)])
    check()
    rows[0]["value"] = "11"
    with pytest.raises(ValueError, match="Contributing reference changed"):
        check()
