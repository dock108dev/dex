"""Explicit broad catalog policy; legacy targets and frozen goals keep their scope."""

import copy

from pokemon_hunter.beta import catalog_imports, catalog_pipeline


def assessment():
    package = dict(
        schema_version="dex-catalog-v1",
        game="pokemon",
        provider="tcgdex",
        version="synthetic-broad",
        set_key="synthetic-broad",
        set_name="Synthetic broad",
        language="en",
        aliases=[],
        source_url="https://example.test/retained",
        source_sha256="a" * 64,
        metadata_permission="Synthetic metadata",
        image_permission="not-included",
        coverage="catalog-entries",
        expected_count=4,
        cards=[],
    )
    for key, category, dex in [
        ("old", "Pokémon", 25),
        ("new", "Pokémon", 1025),
        ("trainer", "Trainer", None),
        ("energy", "Energy", None),
    ]:
        package["cards"].append(
            dict(
                external_id=key,
                number=key,
                name="Synthetic " + key,
                metadata=dict(
                    pokemon_dex=dex, dex_eligible=dex is not None, supertype=category, rarity="Unknown"
                ),
            )
        )
    return dict(
        set_id="tcgdex:en:synthetic-broad",
        language="en",
        era="synthetic",
        medium="physical",
        release_status="released",
        source_url=package["source_url"],
        source_time="2026-10-06T00:00:00+00:00",
        source_sha256=package["source_sha256"],
        evidence_class="synthetic",
        enumerated_ids=["old", "new", "trainer", "energy"],
        enumeration_complete=True,
        package=package,
    )


def test_legacy_default_preserves_vintage_scope():
    raw = assessment()
    result = catalog_pipeline.assess(raw)
    assert [c["external_id"] for c in result["target_records"]] == ["old"]
    assert result["excluded_above251"] == ["new"]


def test_broad_policy_includes_all_species_trainers_and_energy():
    raw = dict(assessment(), catalog_policy="english-physical-all", expected_target_count=4)
    result = catalog_pipeline.assess(raw)
    assert result["enumeration_complete"] and not result["fatal"]
    assert len(result["target_records"]) == 4
    assert result["species"] == [25, 1025]
    assert result["excluded_above251"] == []
    prepared = catalog_pipeline.prepared(raw, result)
    catalog_imports.Package.model_validate(prepared)
    assert len(prepared["cards"]) == 4


def test_broad_policy_still_excludes_digital_and_ambiguous_species():
    raw = dict(assessment(), catalog_policy="english-physical-all", medium="digital")
    result = catalog_pipeline.assess(raw)
    assert result["status"] == "out-of-scope" and result["target_records"] == []
    raw = dict(assessment(), catalog_policy="english-physical-all")
    raw["package"] = copy.deepcopy(raw["package"])
    raw["package"]["cards"][0]["metadata"]["pokemon_dex"] = None
    result = catalog_pipeline.assess(raw)
    assert len(result["target_records"]) == 3
    assert any(e["reason"] == "unresolved-canonical-mapping" for e in result["exceptions"])
