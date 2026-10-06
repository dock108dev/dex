"""Reproduce D1d metadata and bridge-gate diagnosis offline from locked retained bytes."""

import argparse
import copy
import hashlib
import json
from pathlib import Path

from pokemon_hunter.beta import sealed_catalog as sealed

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "evidence/d1d-20261005"
PACKAGE = ROOT / "config/sealed/2026-10-05-det1"


def read(path):
    return json.loads(Path(path).read_text())


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build(check=False):
    lock = read(OUT / "inputs.json")
    for path, sha in lock["files"].items():
        assert digest(path) == sha, "Input drift: " + path
    ledger = read(OUT / "attempt-ledger.json")
    assert ledger["budget_closed"] and ledger["state"] == "complete-acquisition-pending-normalization"
    assert ledger["attempts_consumed"] == 19 and ledger["retries"] == 0
    attempts = {r["key"]: r for r in ledger["attempts"]}
    for a in attempts.values():
        assert a["transport_exit"] == 0 and a["http_status"] == "200"
        assert digest(a["response_path"]) == a["response_sha256"]
        assert digest(a["headers_path"]) == a["headers_sha256"]
        assert digest(a["transport_evidence_path"]) == a["transport_sha256"]
    source = read(attempts["set"]["response_path"])
    assert source["id"] == "det1" and source["cardCount"]["total"] == 18
    assert source["serie"]["id"] == "sm" and len(source["cards"]) == 18
    assert len({b["id"] for b in source["cards"]}) == len({b["localId"] for b in source["cards"]}) == 18
    assert set(attempts) == {"set"} | {b["id"] for b in source["cards"]}
    baseline = read(ROOT / "config/sealed/2026-10-04/package.json")
    p = {k: [] for k in sealed.KINDS}
    p.update(schema_version="dex-sealed-v1", provider="reviewed-d1d", version="2026-10-05-det1-v1")
    p["species"] = baseline["species"]
    registry = {s["id"]: s for s in p["species"]}
    assert len(registry) == 1025
    sids = {s for r in p["species"] for s in r["sources"]}
    p["sources"] = [copy.deepcopy(s) for s in baseline["sources"] if s["id"] in sids]
    eid = "tcgdex:en:det1"

    def provenance(key, subjects, supports):
        a = attempts[key]
        sid = "d1d:" + key
        p["sources"].append(
            dict(
                id=sid,
                provider="tcgdex",
                url=a["url"],
                retrieved_at=a["finished_at"],
                sha256=a["response_sha256"],
                language="en",
                market=None,
                authority="provider",
                status="usable",
                subjects=subjects,
                supports=supports,
                rights="Retained TCGdex MIT metadata license; artwork, rules and prices excluded",
                note="English endpoint authority; physical distribution/edition/finish and booster/promo/deck relationships unverified.",
            )
        )
        return sid

    setsid = provenance("set", [eid], ["universe"])
    p["expansions"] = [
        dict(
            id=eid,
            sources=[setsid],
            name=source["name"],
            language="en",
            series="sm",
            medium="physical",
            expected_printings=18,
        )
    ]
    p["mappings"] = [
        dict(provider="tcgdex", language="en", kind="expansions", external_id="det1", internal_id=eid)
    ]
    cards, links, rows = [], [], []
    for brief in source["cards"]:
        d = read(attempts[brief["id"]]["response_path"])
        assert d["id"] == brief["id"] and d["localId"] == brief["localId"] and d["name"] == brief["name"]
        assert d["set"]["id"] == "det1" and d.get("language", "en") == "en"
        category = {"Pokemon": "pokemon", "Trainer": "trainer", "Energy": "energy"}[d["category"]]
        dex = d.get("dexId", [])
        if category == "pokemon":
            assert len(dex) == 1 and type(dex[0]) is int
            species = f"ndex:{dex[0]:04}"
            assert species in registry
        else:
            assert not dex
            species = None
        variants = d.get("variants_detailed")
        assert variants and len(variants) == len({json.dumps(v, sort_keys=True) for v in variants})
        # Only the exact returned standard generated description is supported by this tranche.
        assert variants == [dict(type="normal", size="standard", variantId="generated")]
        variant = "provider-normal-generated"
        pid = "tcgdex:en:" + d["id"] + ":" + variant
        sid = provenance(d["id"], [pid], ["printing-identity"])
        p["printings"].append(
            dict(
                id=pid,
                sources=[sid],
                expansion_id=eid,
                species_id=species,
                name=d["name"],
                number=d["localId"] + "/18",
                language="en",
                rarity=d.get("rarity"),
                finish=None,
                variant=variant,
                category=category,
            )
        )
        external = d["id"] + ":" + variant
        p["mappings"].append(
            dict(provider="tcgdex", language="en", kind="printings", external_id=external, internal_id=pid)
        )
        mid = "relationship:" + pid
        p["memberships"].append(
            dict(id=mid, sources=[sid], printing_id=pid, expansion_id=eid, status="unknown")
        )
        cards.append(
            dict(
                external_id=external,
                number=d["localId"] + "/18",
                name=d["name"],
                metadata=dict(
                    pokemon_dex=dex[0] if dex else None,
                    dex_eligible=category == "pokemon",
                    supertype={"pokemon": "Pokémon", "trainer": "Trainer", "energy": "Energy"}[category],
                    rarity=d.get("rarity") or "Unknown",
                ),
                edition="unlimited",
                finish=None,
                variant=variant,
            )
        )
        links.append(dict(printing_id=pid, external_id=external))
        rows.append(
            dict(
                provider_id=d["id"],
                number=d["localId"],
                printing_id=pid,
                category=category,
                species_id=species,
                canonical_name=registry[species]["name"] if species else None,
                original151=bool(dex and 1 <= dex[0] <= 151),
                provider_variant_description=variants,
                provider_variant_flags=d.get("variants"),
                verified_finish=None,
                verified_edition=None,
                verified_distribution=None,
                membership="unknown",
                source_sha256=attempts[d["id"]]["response_sha256"],
            )
        )
    assert len(p["printings"]) <= 72
    assert {r["provider_id"] for r in rows} == {b["id"] for b in source["cards"]}
    assert any(r["original151"] for r in rows)
    bridge = dict(
        schema_version="dex-catalog-v1",
        game="pokemon",
        set_key="det1",
        set_name=source["name"],
        language="en",
        aliases=["DET"],
        provider="tcgdex",
        version=p["version"],
        source_url=attempts["set"]["url"],
        source_sha256=attempts["set"]["response_sha256"],
        metadata_permission="TCGdex MIT metadata only; detail hashes in sealed metadata package",
        image_permission="not-included",
        coverage="catalog-entries",
        expected_count=18,
        cards=cards,
    )
    # Diagnostic compatibility input only: unlimited is the bridge-required sentinel, NOT verified edition.
    rejected = copy.deepcopy(p)
    rejected["bridges"] = [dict(expansion_id=eid, package=bridge, links=links)]
    # Historical D1d failure is immutable evidence, not the current acceptance gate.
    errors = read(OUT / "bridge-gate.json")["errors"]
    assert len(errors) == 4 and all(e["type"] == "less_than_equal" for e in errors)
    assert {e["input"] for e in errors} == {272, 755, 658, 289}
    sealed.validate(p)
    data = {
        PACKAGE / "package.json": p,
        PACKAGE / "normalization.json": dict(
            numbered_count=18,
            variant_records=18,
            expected_variant_count=None,
            canonical_species_count=len({r["species_id"] for r in rows}),
            original151_count=13,
            trainer_count=0,
            energy_count=0,
            rows=rows,
            bridge_status="blocked-by-canonical-251-limit",
            publication_status="not-published",
            edition_diagnostic_note="Rejected bridge input uses required unlimited compatibility sentinel; physical edition unknown.",
        ),
        OUT / "rejected-bridge-input.json": rejected,
        OUT / "bridge-gate.json": dict(
            state="stopped-at-acceptance-gate",
            errors=errors,
            unsupported_ids=[r["provider_id"] for r in rows if int(r["species_id"].split(":")[1]) > 251],
            no_partial_subset_import=True,
            reviewed_publication=False,
        ),
    }
    for path, value in data.items():
        text = json.dumps(value, indent=2, ensure_ascii=False) + "\n"
        if check:
            assert path.read_text() == text, "Output drift: " + str(path)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
    print(
        "Historical D1d: 18 numbered / 18 descriptions / 18 canonical species / 13 Original 151; retained four-species rejection unchanged"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    build(parser.parse_args().check)
