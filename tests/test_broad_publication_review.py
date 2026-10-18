"""Independent source review rejects identity drift and executable source expressions."""

import copy
import importlib.util
import json
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "broad_review", Path(__file__).resolve().parents[1] / "scripts/review_broad_publication.py"
)
review = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(review)


@pytest.fixture
def case():
    source_set = dict(id="testp", name={"en": "Synthetic Promos"}, releaseDate="2011-04-26")
    records = {
        "BW01": dict(
            name={"en": "Snivy"}, category="Pokemon", dexId=[495], rarity="Common", set={"reference": "Set"}
        ),
        "BW02": dict(name={"en": "Synthetic Trainer"}, category="Trainer", set={"reference": "Set"}),
    }
    package = dict(
        set_key="testp",
        set_name="Synthetic Promos",
        language="en",
        provider="tcgdex",
        game="pokemon",
        source_sha256=review.ARCHIVE_SHA256,
        source_url=f"https://codeload.github.com/tcgdex/cards-database/tar.gz/{review.PIN}",
        image_permission="not-included",
        coverage="catalog-entries",
        expected_count=2,
        metadata_permission="MIT; Copyright (c) 2021 TCGdex; retained evidence/d6-20261005/TCGDEX_LICENSE.txt",
        cards=[
            dict(
                external_id="testp-BW01",
                number="BW01",
                name="Snivy",
                edition=None,
                finish=None,
                variant=None,
                metadata=dict(pokemon_dex=495, dex_eligible=True, supertype="Pokémon", rarity="Common"),
            ),
            dict(
                external_id="testp-BW02",
                number="BW02",
                name="Synthetic Trainer",
                edition=None,
                finish=None,
                variant=None,
                metadata=dict(pokemon_dex=None, dex_eligible=False, supertype="Trainer", rarity="Unknown"),
            ),
        ],
    )
    assessment = dict(
        set_id="tcgdex:en:testp",
        language="en",
        medium="physical",
        era="bw",
        release_status="released",
        evidence_class="retained-real-source",
        source_time="2026-10-06T03:14:11+00:00",
        source_url=package["source_url"],
        source_sha256=review.ARCHIVE_SHA256,
        catalog_policy="english-physical-all",
        enumeration_complete=True,
        enumerated_ids=[c["external_id"] for c in package["cards"]],
        expected_target_count=2,
    )
    return package, assessment, source_set, dict(id="bw"), records


def test_literal_prefix_padding_species_and_unknown_rarity(case):
    assert review.verify_records(*case) == dict(
        records=2, categories={"Pokémon": 1, "Trainer": 1}, above_251=1
    )


def test_changed_license_notice_rejected(case):
    case[0]["metadata_permission"] = "Unknown"
    with pytest.raises(ValueError):
        review.verify_records(*case)


@pytest.mark.parametrize(
    "field,value",
    [
        ("external_id", "testp-01"),
        ("number", "BW1"),
        ("name", "Different"),
        ("edition", "Unlimited"),
        ("finish", "holo"),
        ("variant", "promo"),
        ("legacy_id", "guessed"),
    ],
)
def test_record_drift_rejected(case, field, value):
    case[0]["cards"][0][field] = value
    with pytest.raises(ValueError):
        review.verify_records(*case)


@pytest.mark.parametrize(
    "field,value",
    [
        ("pokemon_dex", 1),
        ("dex_eligible", False),
        ("supertype", "Trainer"),
        ("rarity", "Rare"),
    ],
)
def test_metadata_drift_rejected(case, field, value):
    case[0]["cards"][0]["metadata"][field] = value
    with pytest.raises(ValueError):
        review.verify_records(*case)


@pytest.mark.parametrize(
    "change", ["missing", "extra", "duplicate", "duplicate-number", "duplicate-enumeration"]
)
def test_completeness_and_duplicates_rejected(case, change):
    package, assessment, *_ = case
    if change == "missing":
        package["cards"].pop()
    elif change == "extra":
        package["cards"].append(
            dict(copy.deepcopy(package["cards"][0]), external_id="testp-BW03", number="BW03")
        )
    elif change == "duplicate":
        package["cards"].append(copy.deepcopy(package["cards"][0]))
    elif change == "duplicate-number":
        package["cards"][1]["number"] = "BW01"
    else:
        assessment["enumerated_ids"].append(assessment["enumerated_ids"][0])
    with pytest.raises(ValueError):
        review.verify_records(*case)


@pytest.mark.parametrize("species", [[495, 496], [], [True], [1026], ["495"]])
def test_unresolved_or_conflicting_source_species_never_select_first(case, species):
    case[-1]["BW01"]["dexId"] = species
    with pytest.raises(ValueError):
        review.verify_records(*case)


@pytest.mark.parametrize(
    "field,value",
    [
        ("catalog_policy", "vintage-251"),
        ("expected_target_count", 1),
        ("enumeration_complete", False),
        ("medium", "digital"),
        ("source_sha256", "0" * 64),
        ("source_url", "https://example.test/other"),
        ("era", "base"),
        ("release_status", "uncertain"),
        ("evidence_class", "synthetic"),
    ],
)
def test_assessment_drift_rejected(case, field, value):
    case[1][field] = value
    with pytest.raises(ValueError):
        review.verify_records(*case)


def test_independent_scanner_literal_data_and_import_binding():
    source = """import Set from '../Synthetic'
    const card: Card = {set: Set, name: {en: 'A' + " B"}, dexId: [495,], enabled: true, unknown: null}
    export default card"""
    assert review.parse_literal(source) == dict(
        set={"reference": "Set"}, name={"en": "A B"}, dexId=[495], enabled=True, unknown=None
    )


@pytest.mark.parametrize(
    "body",
    [
        "{name: 'a', name: 'b'}",
        "{name: dangerous()}",
        "{dexId: [1 + dangerous()]}",
        "{name: process.env.SECRET}",
        "{name: `execute ${dangerous()}`}",
        "{...other}",
        "{name: unknown}",
        "{name: 'ok'}; dangerous()",
    ],
)
def test_independent_scanner_rejects_code_and_duplicate_literals(body):
    with pytest.raises((ValueError, IndexError)):
        review.parse_literal("const card: Card = " + body + "\nexport default card")


@pytest.fixture
def batch_case(tmp_path, monkeypatch, case):
    """Synthetic engineering evidence for batch failure boundaries only."""
    inventory = tmp_path / "inventory"
    inventory.mkdir()
    directory = tmp_path / "prepared"
    directory.mkdir()
    context = dict(
        inventory_summary_sha256="summary-hash",
        source_cutoff="2026-10-06T03:14:11+00:00",
        archive_tree_members_verified=7,
        git_trees_verified=3,
    )
    selected, calls = [], []
    for code in ("testp", "otherp"):
        package = copy.deepcopy(case[0])
        package["set_key"] = code
        for card in package["cards"]:
            card["external_id"] = card["external_id"].replace("testp-", code + "-")
        row = dict(
            set=code,
            name=package["set_name"],
            source_file="data/Synthetic/" + code + ".ts",
            source_sha256="set-hash-" + code,
            records=2,
            categories={"Pokemon": 1, "Trainer": 1},
            external_ids=[card["external_id"] for card in package["cards"]],
        )
        selected.append(row)
        target = directory / code
        target.mkdir()
        canonical = json.dumps(package, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        (target / "package.json").write_bytes(canonical + b"\n")
        (target / "assessment.json").write_text(json.dumps({"package": package}))
        (target / "binding.json").write_text(
            json.dumps(
                dict(
                    package_sha256=review.sha(canonical),
                    inventory_summary_sha256=context["inventory_summary_sha256"],
                    source_cutoff=context["source_cutoff"],
                )
            )
        )
    manifest = dict(
        selected_sets=selected,
        selected_set_count=2,
        selected_records=4,
        source=dict(
            inventory_directory=str(inventory),
            summary_sha256=context["inventory_summary_sha256"],
            commit=review.PIN,
            archive_sha256=review.ARCHIVE_SHA256,
            cutoff=context["source_cutoff"],
        ),
    )
    manifest_path = tmp_path / "selection.json"
    manifest_path.write_text(json.dumps(manifest))

    def load(repo, selected_inventory, codes):
        calls.append((selected_inventory, codes))
        return context

    def prepared(shared, target, code):
        assert shared is context
        row = next(row for row in selected if row["set"] == code)
        return dict(
            status="PASS",
            selected_set=code,
            selected_source_path=row["source_file"],
            set_member_sha256=row["source_sha256"],
            records=2,
            categories={"Pokémon": 1, "Trainer": 1},
            package_file_sha256=review.sha((target / "package.json").read_bytes()),
            assessment_file_sha256=review.sha((target / "assessment.json").read_bytes()),
        )

    monkeypatch.setattr(review, "load_review_context", load)
    monkeypatch.setattr(review, "review_prepared", prepared)
    return tmp_path, inventory, directory, manifest_path, calls


def test_batch_uses_one_shared_verification_and_binds_file_bytes(batch_case):
    result = review.review_batch(*batch_case[:4])
    assert result["status"] == "PASS"
    assert result["passed_sets"] == 2 and result["passed_records"] == 4
    assert result["archive_verification_passes"] == 1 and len(batch_case[4]) == 1
    assert result["sets"][0]["package_file_sha256"] == review.sha(
        (batch_case[2] / "testp/package.json").read_bytes()
    )
    assert "not external review" in result["reviewer"]


@pytest.mark.parametrize(
    "change", ["missing-file", "package-hash", "manifest-ids", "manifest-source", "manifest-count"]
)
def test_batch_holds_only_package_with_failed_evidence(batch_case, change):
    root, inventory, directory, manifest_path, calls = batch_case
    if change == "missing-file":
        (directory / "testp/package.json").unlink()
    elif change == "package-hash":
        path = directory / "testp/binding.json"
        binding = json.loads(path.read_text())
        binding["package_sha256"] = "changed"
        path.write_text(json.dumps(binding))
    else:
        manifest = json.loads(manifest_path.read_text())
        selected = manifest["selected_sets"][0]
        if change == "manifest-ids":
            selected["external_ids"][0] = selected["external_ids"][1]
        elif change == "manifest-source":
            selected["source_sha256"] = "changed"
        else:
            selected["records"] = 3
        manifest_path.write_text(json.dumps(manifest))
    result = review.review_batch(root, inventory, directory, manifest_path)
    assert result["status"] == "PARTIAL"
    assert result["passed_sets"] == 1 and result["held_sets"] == 1
    assert [(row["selected_set"], row["status"]) for row in result["sets"]] == [
        ("testp", "HELD"),
        ("otherp", "PASS"),
    ]
    assert len(calls) == 1


def test_batch_stops_on_shared_inventory_binding_failure(batch_case):
    root, inventory, directory, manifest_path, _ = batch_case
    manifest = json.loads(manifest_path.read_text())
    manifest["source"]["summary_sha256"] = "changed"
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="inventory hash conflict"):
        review.review_batch(root, inventory, directory, manifest_path)
