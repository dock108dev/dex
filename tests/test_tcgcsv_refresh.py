"""Refresh integration with disposable fabricated inputs; sockets forbidden by the runner."""

import copy
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import audit_tcgcsv_batch as independent  # noqa: E402
import capture_tcgcsv_snapshot as collector  # noqa: E402
import review_tcgcsv_batch as builder  # noqa: E402


@pytest.fixture
def refresh(tmp_path, monkeypatch):
    root = tmp_path / "customer"
    root.mkdir(mode=0o700)
    directory = root / "price-snapshots/staging/refresh"
    collector._private_directory(directory / "groups/11")
    target = dict(
        id="printing",
        set_id="set",
        set_name="Synthetic Set",
        name="Pikachu",
        collector_number="1",
        language="en",
        edition="first_edition",
        finish="normal",
        variant='{"stamp":["1st-edition"],"type":"normal"}',
        catalog_version="v1",
        attributes={},
    )
    entries = {"printing": target}
    monkeypatch.setattr(builder.audit, "catalog_metadata", lambda _: entries)
    exact = dict(
        group_id=11,
        product_id=10,
        sub_type_name="1st Edition",
        source_url="https://www.tcgplayer.com/product/10/pokemon-synthetic-pikachu",
    )
    evidence = dict(
        category_id=3,
        literal_name="Synthetic Set",
        language="en",
        language_evidence=[{"source": "fabricated engineering evidence"}],
        denominators={},
        denominator_evidence=[],
    )
    scope = dict(
        schema=builder.SCOPE_SCHEMA,
        catalog_identity_sha256=builder.rules.digest(entries),
        capture_purpose="refresh",
        printings=[dict(printing_id="printing", source_group_id=11)],
        exact_bindings={"printing": exact},
        group_evidence={"11": evidence},
    )
    plan = collector.make_batch_plan(
        root,
        [dict(group_id=11, name="Synthetic Set")],
        "2026-01-01T00:00:00Z",
        "a" * 64,
        purpose="refresh",
        refresh_cadence="selected_groups",
    )
    now = datetime.now(UTC) - timedelta(seconds=5)
    built = now.replace(microsecond=0)
    product = dict(
        productId=10,
        categoryId=3,
        groupId=11,
        name="Pikachu",
        url=exact["source_url"],
        extendedData=[dict(name="Number", value="1")],
    )
    prices = [
        dict(productId=10, subTypeName="1st Edition", marketPrice=None),
        dict(productId=10, subTypeName="Unlimited", marketPrice=1),
    ]
    paths = {
        "build-before.txt": built.isoformat().encode(),
        "build-after.txt": built.isoformat().encode(),
        "groups/11/products.json": collector._json_bytes(
            dict(success=True, errors=[], totalItems=1, results=[product])
        ),
        "groups/11/prices.json": collector._json_bytes(dict(success=True, errors=[], results=prices)),
    }
    for name, body in paths.items():
        collector._write_new(directory / name, body)
    metadata = dict(
        status="captured",
        plan_sha256=collector.validate_batch_plan(plan, root),
        group_ids=[11],
        provider_operations=4,
        capture_directory=str(directory.relative_to(root)),
        publisher_built_at=built.isoformat(),
        provider_valuation_at=None,
        http_statuses=[200] * 4,
        files=[
            dict(
                attempt=i,
                filename=s["filename"],
                group_id=s["group_id"],
                bytes=len(paths[s["filename"]]),
                captured_at=now.isoformat(),
            )
            for i, s in enumerate(plan["steps"], 1)
        ],
    )
    collector._write_new(directory / "capture-metadata.json", collector._json_bytes(metadata))
    plan_path, scope_path = tmp_path / "plan.json", tmp_path / "scope.json"
    plan_path.write_text(json.dumps(plan))
    scope_path.write_text(json.dumps(scope))
    return root, directory, plan, scope, plan_path, scope_path


def inspect(refresh):
    root, directory, plan, _, plan_path, scope_path = refresh
    return builder.inspect(
        root, plan_path, collector.validate_batch_plan(plan, root), directory, "synthetic-refresh", scope_path
    )


def test_exact_refresh_builder_and_independent_audit_agree_with_null_price(refresh):
    root, directory, plan, scope, *_ = refresh
    review, manifest = inspect(refresh)
    assert manifest["contract"]["acquisition_policy"].startswith("One finite selected ordinary refresh;")
    assert len(manifest["bindings"]) == 1
    # A null observed amount is retained as a mapping, never silently priced.
    result = independent.inspect(root, scope, plan, directory, review, manifest)
    assert result["all_passed"] and result["selected_bindings"] == 1


@pytest.mark.parametrize("change", ["missing_product", "missing_subtype", "url_conflict", "wrong_finish"])
def test_exact_refresh_never_substitutes_product_subtype_or_physical_identity(refresh, change):
    root, directory, plan, scope, *_ = refresh
    name = "products" if change in {"missing_product", "url_conflict"} else "prices"
    path = directory / f"groups/11/{name}.json"
    data = json.loads(path.read_bytes())
    if change == "missing_product":
        data["results"][0]["productId"] = 99
        data["results"][0]["url"] = "https://www.tcgplayer.com/product/99/pokemon-synthetic-pikachu"
    elif change == "url_conflict":
        data["results"][0]["url"] += "-different"
    elif change == "missing_subtype":
        data["results"] = data["results"][1:]
    else:
        data["results"][0]["subTypeName"] = "1st Edition Holofoil"
    path.write_bytes(collector._json_bytes(data))
    meta = json.loads((directory / "capture-metadata.json").read_bytes())
    for row in meta["files"]:
        row["bytes"] = (directory / row["filename"]).stat().st_size
    (directory / "capture-metadata.json").write_bytes(collector._json_bytes(meta))
    review, manifest = inspect(refresh)
    assert not manifest["bindings"]
    result = independent.inspect(root, scope, plan, directory, review)
    assert result["all_passed"] and result["selected_bindings"] == 0


def test_refresh_refuses_scope_without_exact_bindings(refresh):
    root, directory, plan, scope, _, scope_path = refresh
    scope = copy.deepcopy(scope)
    del scope["exact_bindings"]
    scope_path.write_text(json.dumps(scope))
    with pytest.raises(ValueError, match="frozen exact child bindings"):
        inspect(refresh)
    with pytest.raises(ValueError, match="refresh_exact_scope_required"):
        independent.inspect(
            root, scope, plan, directory, dict(catalog_identity_sha256=scope["catalog_identity_sha256"])
        )


def _received_refresh(refresh):
    root, directory, plan, scope, plan_path, scope_path = refresh
    plan.update(refresh_cadence="selected_groups_new_build", timing_override="selected-refresh-once")
    scope.pop("exact_bindings")
    scope["refresh_binding_mode"] = "received_identity"
    plan_path.write_text(json.dumps(plan))
    scope_path.write_text(json.dumps(scope))
    meta = json.loads((directory / "capture-metadata.json").read_text())
    meta["plan_sha256"] = collector.validate_batch_plan(plan, root)
    (directory / "capture-metadata.json").write_bytes(collector._json_bytes(meta))


def test_received_refresh_independently_rederives_received_binding(refresh):
    _received_refresh(refresh)
    root, directory, plan, scope, *_ = refresh
    result, manifest = inspect(refresh)
    assert len(manifest["bindings"]) == 1
    assert independent.inspect(root, scope, plan, directory, result, manifest)["all_passed"]


def test_received_refresh_holds_conflicting_received_name(refresh):
    _received_refresh(refresh)
    root, directory, plan, scope, *_ = refresh
    path = directory / "groups/11/products.json"
    body = json.loads(path.read_text())
    body["results"][0]["name"] = "Bulbasaur"
    path.write_bytes(collector._json_bytes(body))
    meta = json.loads((directory / "capture-metadata.json").read_text())
    for row in meta["files"]:
        row["bytes"] = (directory / row["filename"]).stat().st_size
    (directory / "capture-metadata.json").write_bytes(collector._json_bytes(meta))
    result, manifest = inspect(refresh)
    assert not manifest["bindings"]
    assert independent.inspect(root, scope, plan, directory, result, manifest)["all_passed"]


def test_r3_received_identity_independent_review_and_pins(refresh, monkeypatch):
    _received_refresh(refresh)
    root, directory, plan, scope, plan_path, _ = refresh
    from scripts import tcgcsv_capture_contract

    monkeypatch.setattr(tcgcsv_capture_contract, "R3_ACQUIRE1_GROUPS", ((11,),))
    plan.update(
        refresh_cadence="owner_r3_acquire1_same_build_once",
        timing_override=f"r3-acquire1-{collector.R3_ACQUIRE1_PROPOSAL[:16]}-batch-1",
    )
    plan_path.write_text(json.dumps(plan))
    meta = json.loads((directory / "capture-metadata.json").read_text())
    meta["plan_sha256"] = collector.validate_batch_plan(plan, root)
    (directory / "capture-metadata.json").write_bytes(collector._json_bytes(meta))
    result, manifest = inspect(refresh)
    assert len(manifest["bindings"]) == 1
    assert independent.inspect(root, scope, plan, directory, result, manifest)["all_passed"]
