"""Synthetic scenario independence, inclusion, history and retention authority."""

import copy
import json

import pytest
from test_b1 import env as env
from test_b2 import b2 as b2
from test_migration import snapshot as snapshot
from test_shopping import NOW, inputs
from test_shopping import shop as shop

from pokemon_hunter.beta import collection, shopping
from pokemon_hunter.beta import lot_calculator as lot


@pytest.fixture
def workspace(shop):
    collection.execute("UPDATE catalog_sets SET name='Base Set'")
    return shop


def request(workspace, quantities=(2, 1)):
    old = inputs(workspace)
    return dict(
        cards=[
            dict(
                printing_id=p["id"],
                quantity=q,
                values={
                    grade: dict(
                        mode="manual",
                        amount=value,
                        date="2026-10-09",
                        notes="Fabricated independent scenario",
                    )
                    for grade, value in zip(lot.COLUMNS, ("1.005", "7", "11", "19"), strict=True)
                },
            )
            for p, q in zip(workspace["catalog"][:2], quantities, strict=True)
        ],
        **{key: old[key] for key in (*shopping.math.BASES, "delivery_cost_inputs")},
    )


def post(workspace, url, payload, client=None):
    c = client or workspace["a"]
    c.get("/shopping/")
    return c.post(
        url,
        json.dumps(payload),
        content_type="application/json",
        HTTP_X_CSRFTOKEN=c.cookies["dex_b1_csrf"].value,
    )


@pytest.mark.parametrize("route", ["/api/shopping/lot-compare/", "/api/shopping/compare/"])
@pytest.mark.parametrize("save", ["false", "true", 0, 1, None, [], {}])
def test_save_intent_requires_boolean_before_evaluation(workspace, monkeypatch, route, save):
    def forbidden(*args):
        pytest.fail("Invalid save intent must not evaluate or persist a comparison")

    monkeypatch.setattr(lot, "prepare", forbidden)
    monkeypatch.setattr(shopping, "prepare", forbidden)
    before = shopping.listing(workspace["actor"])
    response = post(workspace, route, dict(inputs={}, save=save))
    assert response.status_code == 400
    assert shopping.listing(workspace["actor"]) == before


@pytest.mark.parametrize("modern", [True, False])
@pytest.mark.parametrize("save", [True, False, "omitted"])
def test_explicit_save_and_calculation_only_behavior(workspace, modern, save):
    route = "/api/shopping/lot-compare/" if modern else "/api/shopping/compare/"
    raw = request(workspace) if modern else inputs(workspace)
    payload = dict(inputs=raw, name="Synthetic save intent")
    if save != "omitted":
        payload["save"] = save
    response = post(workspace, route, payload)
    assert response.status_code == 200, response.content
    assert ("saved_url" in response.json()) == (save is True)
    assert len(shopping.listing(workspace["actor"])) == (1 if save is True else 0)


def test_independent_quantity_totals_rounding_unknown_delivery_and_zero(workspace):
    before = collection.export_data(workspace["actor"])
    raw = request(workspace)
    payload = lot.prepare(workspace["actor"], raw, NOW)
    assert [payload["scenarios"][g]["result"]["full_selected_total"] for g in lot.COLUMNS] == [
        "3.02",
        "21.00",
        "33.00",
        "57.00",
    ]
    assert (
        payload["scenarios"]["raw"]["result"]["comparisons"]["listing_observation"][
            "full_selected_reference_minus_base_price"
        ]
        == "-8.98"
    )
    assert all(
        s["result"]["comparisons"]["listing_observation"]["full_delivered_cost"] is None
        for s in payload["scenarios"].values()
    )
    for row in raw["cards"]:
        row["values"]["8"] = dict(mode="none")
        row["values"]["10"]["amount"] = "0"
    raw["cards"][0]["values"]["8"] = dict(mode="manual", amount="7", date="2026-10-09")
    partial = lot.prepare(workspace["actor"], raw, NOW)["scenarios"]
    assert partial["8"]["result"]["coverage"]["selected_unit_fraction"] == [2, 3]
    assert partial["8"]["result"]["full_selected_total"] is None
    assert partial["8"]["result"]["known_selected_subtotal"] == "14.00"
    assert partial["10"]["result"]["full_selected_total"] == "0.00"
    assert collection.export_data(workspace["actor"]) == before


def test_wants_absent_units_session_isolation_and_no_storage_requirement(workspace):
    p = workspace["catalog"][0]
    before = collection.export_data(workspace["actor"])
    response = post(workspace, "/api/shopping/wants/", dict(wants=[dict(printing_id=p["id"], quantity=3)]))
    assert response.status_code == 200
    assert p["id"].encode() in workspace["a"].get("/shopping/").content
    assert p["id"].encode() not in workspace["b"].get("/shopping/").content
    raw = request(workspace)
    raw["cards"] = []
    payload = lot.prepare(workspace["actor"], raw, NOW)
    assert all(
        s["result"]["coverage"]["selected_units"] == 0 and s["result"]["known_selected_subtotal"] is None
        for s in payload["scenarios"].values()
    )
    collection.execute("DROP TABLE saved_shopping_comparisons")
    assert workspace["a"].get("/shopping/").status_code == 200
    assert (
        post(
            workspace, "/api/shopping/wants/", dict(wants=[dict(printing_id=p["id"], quantity=3)])
        ).status_code
        == 200
    )
    assert collection.export_data(workspace["actor"]) == before


def test_snapshot_and_legacy_unchanged_reopening_account_scope(workspace):
    old_key = shopping.save(workspace["actor"], inputs(workspace), "Old per-card", now=NOW)
    old = shopping.one(workspace["actor"], old_key)
    raw = request(workspace)
    response = post(
        workspace, "/api/shopping/lot-compare/", dict(inputs=raw, save=True, name="Four scenarios")
    )
    assert response.status_code == 200, response.content
    url = response.json()["saved_url"]
    assert workspace["a"].get(url).status_code == 200
    assert workspace["b"].get(url).status_code == 404
    assert workspace["a"].get(f"/shopping/saved/{old_key}/").status_code == 200
    assert shopping.one(workspace["actor"], old_key) == old
    assert workspace["a"].get("/shopping/legacy/").status_code == 200
    assert workspace["client"]().post(
        "/api/shopping/lot-compare/", "{}", content_type="application/json"
    ).status_code in (302, 403)


def test_vintage_scope_guide_semantics_and_provider_admission(workspace, monkeypatch):
    assert len(lot.browse(workspace["actor"])) == 3
    assert any(p["copy_count"] for p in lot.browse(workspace["actor"]))
    p = collection.catalog(workspace["actor"])[0]
    row = copy.deepcopy(workspace["guides"][0])
    row["card_id"] = json.loads(p["provenance"])["legacy_id"]
    row["edition"] = p.get("edition") or "standard"
    rows = [dict(row, grade=g, value=v) for g, v in zip(lot.COLUMNS, ("1", "3", "5", "7"), strict=True)]
    assert lot.cells(p, rows, NOW.date())["8"]["grader"] == "Guide"
    rows[1]["estimated"] = True
    assert lot.cells(p, rows, NOW.date())["8"] is None
    rows[2]["finish"] = "contradicts-selected-printing"
    assert lot.cells(p, rows, NOW.date())["9"] is None
    ref = dict(kind="guide", raw_record=dict(row, value="999"))
    with pytest.raises(ValueError, match="surviving rights"):
        lot.admit_snapshot(dict(candidate_alternative=ref))
    collection.execute("UPDATE catalog_sets SET name='Prismatic Evolutions'")
    assert not lot.browse(workspace["actor"])
    assert len(collection.catalog(workspace["actor"])) == 3


@pytest.mark.parametrize(
    "mutation", ["duplicate", "zero_quantity", "negative", "stale", "overflow", "unsafe_url"]
)
def test_bad_ingress_rejected(workspace, mutation):
    raw = request(workspace)
    if mutation == "duplicate":
        raw["cards"].append(copy.deepcopy(raw["cards"][0]))
    elif mutation == "zero_quantity":
        raw["cards"][0]["quantity"] = 0
    elif mutation == "negative":
        raw["cards"][0]["values"]["raw"]["amount"] = "-1"
    elif mutation == "stale":
        raw["cards"][0]["values"]["raw"]["date"] = "2020-01-01"
    elif mutation == "overflow":
        raw["cards"][0]["quantity"] = 100000
    else:
        raw["listing_observation"]["source_url"] = "javascript:alert(1)"
    with pytest.raises(ValueError):
        lot.prepare(workspace["actor"], raw, NOW)


def test_guide_columns_quantity_and_saved_provenance(workspace, monkeypatch):
    p = next(
        p for p in collection.catalog(workspace["actor"]) if json.loads(p["provenance"])["legacy_id"] == "b"
    )
    original = workspace["guides"][0]
    records = [
        dict(original, grade=g, value=v, estimated=False)
        for g, v in zip(lot.COLUMNS, ("2.550001", "7", "11", "19"), strict=True)
    ]
    monkeypatch.setattr(lot, "retained_records", lambda: records)
    monkeypatch.setattr(lot, "admitted_hashes", lambda: {shopping.digest(r) for r in records})
    raw = request(workspace)
    raw["cards"] = [
        dict(printing_id=p["id"], quantity=2, values={g: dict(mode="guide") for g in lot.COLUMNS})
    ]
    payload = lot.prepare(workspace["actor"], raw, NOW)
    assert [payload["scenarios"][g]["result"]["full_selected_total"] for g in lot.COLUMNS] == [
        "5.10",
        "14.00",
        "22.00",
        "38.00",
    ]
    key = shopping.store_payload(workspace["actor"], payload, "Synthetic guides")
    saved = shopping.reopen(workspace["actor"], key)
    assert saved["scenarios"]["8"]["references"][0]["grader"] == "Guide"
    assert saved["scenarios"]["raw"]["references"][0]["raw_record"] == records[0]
    original_hash = shopping.one(workspace["actor"], key)["snapshot_sha256"]
    records.clear()
    assert (
        shopping.reopen(workspace["actor"], key)["scenarios"]["raw"]["result"]["full_selected_total"]
        == "5.10"
    )
    assert shopping.one(workspace["actor"], key)["snapshot_sha256"] == original_hash
