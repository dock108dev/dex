"""Evidence-strength regressions; fabricated metadata only, never customer state."""

import copy
import importlib.util
import json
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "reconcile_tcgcsv_identity", Path(__file__).parents[1] / "scripts/reconcile_tcgcsv_identity.py"
)
reconcile = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(reconcile)


@pytest.mark.parametrize("subtypes", list(reconcile.PAIR_COUNTS))
def test_source_alternatives_never_assign_the_existing_identity(subtypes):
    finish = "holo" if "Holofoil" in subtypes and "Normal" not in subtypes else "normal"
    variants = [
        {"type": finish},
        {"type": "reverse"} if "Reverse" in subtypes else {"type": finish, "stamp": ["1st-edition"]},
    ]
    original = copy.deepcopy(variants)
    cause, accepted, excluded = reconcile.classify({"variants": variants})
    assert cause == "numbered_identity_spans_multiple_variants"
    assert accepted == original
    assert not excluded
    assert variants == original


@pytest.mark.parametrize(
    "source",
    [{}, {"variants": []}, {"variants": None}, {"rarity": "Holo Rare"}, {"thirdParty": {"tcgplayer": 10}}],
)
def test_missing_variant_evidence_does_not_default_to_a_finish(source):
    assert reconcile.classify(source) == ("source_variant_detail_absent", [], [])


def test_availability_flags_do_not_expand_into_a_cartesian_product():
    source = {"variants": {"normal": True, "reverse": True, "firstEdition": True}}
    cause, accepted, excluded = reconcile.classify(source)
    assert cause == "source_variant_shape_or_language_unresolved"
    assert not accepted
    assert excluded[0]["value"] == source["variants"]


def test_non_english_variant_cannot_silently_establish_an_english_finish():
    cause, accepted, excluded = reconcile.classify({"variants": [{"type": "holo", "languages": ["de"]}]})
    assert cause == "source_variant_shape_or_language_unresolved"
    assert not accepted and len(excluded) == 1


def test_conflicting_literal_finishes_remain_alternatives():
    variants = [{"type": "normal"}, {"type": "holo"}]
    cause, accepted, _ = reconcile.classify({"variants": variants})
    assert cause == "numbered_identity_spans_multiple_variants"
    assert accepted == variants


def test_single_variant_does_not_establish_assignment_to_the_preserved_id():
    assert reconcile.classify({"variants": [{"type": "holo"}]})[0] == (
        "single_source_variant_without_identity_assignment"
    )


def test_special_variants_and_shared_product_ids_stay_literal():
    variants = [
        {"type": "normal", "foil": "galaxy", "thirdParty": {"tcgplayer": 10}},
        {"type": "normal", "foil": "galaxy", "stamp": ["1st-edition"], "thirdParty": {"tcgplayer": 10}},
        {"type": "normal", "subtype": "1999-2000-copyright"},
        {"type": "normal", "size": "jumbo", "stamp": ["25th-celebration"]},
    ]
    assert reconcile.classify({"variants": variants})[1] == variants


@pytest.fixture
def batches():
    pairs = [p.split(" / ") for p, count in reconcile.PAIR_COUNTS.items() for _ in range(count)]
    rows = [
        dict(
            printing_id=f"synthetic-{i}",
            catalog_identity=dict(
                name="Unown (A)",
                collector_number="RC01/RC25",
                language="en",
                edition=None,
                finish=None,
                variant=None,
            ),
            candidates=[dict(supported_subtypes=pair)],
            decision="ambiguous_supported_subtypes",
        )
        for i, pair in enumerate(pairs)
    ]
    result, start = {}, 0
    for batch, count in reconcile.BATCH_COUNTS.items():
        result[batch] = dict(decisions=rows[start : start + count])
        start += count
    return result


def test_complete_distinct_frozen_cohort_preserves_names_forms_and_numbers(batches):
    original = copy.deepcopy(batches)
    rows = reconcile.freeze(batches)
    assert len(rows) == len({r["printing_id"] for r in rows}) == 660
    assert {r["catalog_identity"]["name"] for r in rows} == {"Unown (A)"}
    assert {r["catalog_identity"]["collector_number"] for r in rows} == {"RC01/RC25"}
    assert batches == original


@pytest.mark.parametrize("field,value", [("edition", "unlimited"), ("finish", "normal"), ("variant", "holo")])
def test_frozen_identity_cannot_be_repurposed_to_fit_a_subtype(batches, field, value):
    batches[1]["decisions"][0]["catalog_identity"][field] = value
    with pytest.raises(ValueError, match="unspecified"):
        reconcile.freeze(batches)


def test_missing_disposition_rejected(batches):
    batches[1]["decisions"].pop()
    with pytest.raises(ValueError, match="count"):
        reconcile.freeze(batches)


def test_duplicate_printing_rejected(batches):
    batches[2]["decisions"][0]["printing_id"] = batches[1]["decisions"][0]["printing_id"]
    with pytest.raises(ValueError, match="Duplicate"):
        reconcile.freeze(batches)


@pytest.mark.parametrize(
    "candidates",
    [[], [{"supported_subtypes": ["Normal"]}], [{"supported_subtypes": ["Normal", "Unsupported"]}]],
)
def test_candidate_substitution_is_refused(batches, candidates):
    batches[1]["decisions"][0]["candidates"] = candidates
    with pytest.raises(ValueError):
        reconcile.freeze(batches)


def test_no_network_guard():
    with pytest.raises(ValueError, match="forbids network"):
        reconcile.no_network("https://example.invalid")


def test_cli_rejects_any_acquisition_attempt(monkeypatch, tmp_path):
    def forbidden_collect(*_args):
        import socket

        socket.create_connection(("example.invalid", 443))

    monkeypatch.setattr(reconcile, "collect", forbidden_collect)
    monkeypatch.setattr("sys.argv", ["reconcile", "--root", str(tmp_path), "--output", str(tmp_path)])
    # main installs guards; restore socket attributes when this test finishes.
    import socket

    with monkeypatch.context() as context:
        for name in ("socket", "create_connection", "getaddrinfo"):
            context.setattr(socket, name, getattr(socket, name))
        with pytest.raises(ValueError, match="forbids network"):
            reconcile.main()
    assert not list(tmp_path.iterdir())


@pytest.fixture
def publication():
    original = {"data/Synthetic/Set/1.ts": "synthetic-member-hash"}
    package = dict(
        version="synthetic-revision",
        reconcile_legacy_set="synthetic",
        source_sha256=reconcile.sha(json.dumps(original, sort_keys=True).encode()),
    )
    encoded = json.dumps(package, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    return dict(package=package, package_hash=reconcile.sha(encoded)), dict(
        commit="synthetic-revision", sets={"synthetic": original}
    )


def test_original_lineage_and_package_hash_are_verified(publication):
    published, original = publication
    reconcile.verify_publication(published, original)


@pytest.mark.parametrize("tamper", ["package", "commit", "member"])
def test_conflicting_publication_lineage_is_refused(publication, tamper):
    published, original = publication
    if tamper == "package":
        published["package"]["name"] = "changed"
    elif tamper == "commit":
        original["commit"] = "other-revision"
    else:
        original["sets"]["synthetic"]["data/Synthetic/Set/1.ts"] = "changed"
    with pytest.raises(ValueError, match="conflict"):
        reconcile.verify_publication(published, original)
