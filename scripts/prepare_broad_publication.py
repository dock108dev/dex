"""Prepare retained broad-policy numbered packages without customer writes."""

import argparse
import hashlib
import json
from pathlib import Path

from prepare_broad_catalog import ARCHIVE_SHA256, PIN, REPO, encode, read_retained


def load_inventory(directory):
    return {
        name: json.loads((directory / (name + ".json")).read_text()) for name in ("summary", "sets", "cards")
    }


def prepare(directory, set_code, *, inventory=None):
    inventory = load_inventory(directory) if inventory is None else inventory
    summary = inventory["summary"]
    if summary["commit"] != PIN or summary["archive_sha256"] != ARCHIVE_SHA256:
        raise ValueError("Frozen inventory identity mismatch")
    sets = inventory["sets"]
    source = next(s for s in sets if s["provider_set_id"] == set_code)
    cards = [c for c in inventory["cards"] if c["provider_set_id"] == set_code]
    if (
        not cards
        or len(cards) > 2000
        or source["medium"] != "physical"
        or source["gaps"]
        or any(c["current_matches"] or c["disposition"] != "resolved" for c in cards)
    ):
        raise ValueError("First package requires a complete, unresolved-free, unpublished physical set")
    package = dict(
        schema_version="dex-catalog-v1",
        game="pokemon",
        provider="tcgdex",
        version="c1a-" + PIN[:12] + "-numbered-v1",
        set_key=set_code.replace(".", "-"),
        set_name=source["name"],
        language="en",
        aliases=[],
        source_url=f"https://codeload.github.com/tcgdex/cards-database/tar.gz/{PIN}",
        source_sha256=ARCHIVE_SHA256,
        metadata_permission="MIT; Copyright (c) 2021 TCGdex; retained evidence/d6-20261005/TCGDEX_LICENSE.txt",
        image_permission="not-included",
        coverage="catalog-entries",
        expected_count=len(cards),
        cards=[],
    )
    for card in cards:
        if card["category"] == "Pokemon" and (
            len(card["species"]) != 1
            or type(card["species"][0]) is not int
            or not 1 <= card["species"][0] <= 1025
        ):
            raise ValueError("Unresolved canonical species: " + card["external_id"])
        if card["category"] != "Pokemon" and card["species"]:
            raise ValueError("Non-Pokemon species conflict: " + card["external_id"])
        species = card["species"][0] if card["category"] == "Pokemon" and len(card["species"]) == 1 else None
        package["cards"].append(
            dict(
                external_id=card["external_id"],
                number=card["number"],
                name=card["name"],
                edition=None,
                finish=None,
                variant=None,
                metadata=dict(
                    pokemon_dex=species,
                    dex_eligible=species is not None,
                    supertype={"Pokemon": "Pokémon", "Trainer": "Trainer", "Energy": "Energy"}[
                        card["category"]
                    ],
                    rarity=card.get("rarity") or "Unknown",
                ),
            )
        )
    assessment = dict(
        set_id="tcgdex:en:" + package["set_key"],
        language="en",
        era=source["era"],
        medium="physical",
        release_status="released"
        if isinstance(source["release_date"], str)
        and source["release_date"] <= summary["frozen_source_time"][:10]
        else "uncertain",
        source_url=package["source_url"],
        source_time=summary["frozen_source_time"],
        source_sha256=ARCHIVE_SHA256,
        evidence_class="retained-real-source",
        enumerated_ids=sorted(c["external_id"] for c in cards),
        enumeration_complete=True,
        expected_target_count=len(cards),
        catalog_policy="english-physical-all",
        package=package,
    )
    return assessment


def package_files(directory, assessment):
    return {
        "assessment.json": encode(assessment) + "\n",
        "package.json": encode(assessment["package"]) + "\n",
        "binding.json": encode(
            dict(
                inventory_summary_sha256=hashlib.sha256(
                    (directory / "summary.json").read_bytes()
                ).hexdigest(),
                source_cutoff=assessment["source_time"],
                package_sha256=hashlib.sha256(encode(assessment["package"]).encode()).hexdigest(),
                publication="not_performed",
                identity_policy="Numbered unspecified parent only; literal variants remain separate inventory evidence",
                frozen_goal_expansion=False,
                provider_operations=0,
            )
        )
        + "\n",
    }


def prepare_batch(directory, manifest_path, output, *, repo=REPO):
    """Verify retained inputs once, then prepare/reproduce every selected package."""
    manifest = json.loads(manifest_path.read_text())
    inventory = load_inventory(directory)
    parsed, members, failures, sources = read_retained(repo)
    if (
        hashlib.sha256((directory / "summary.json").read_bytes()).hexdigest()
        != manifest["source"]["summary_sha256"]
    ):
        raise ValueError("Selection inventory binding mismatch")
    if manifest["source"]["commit"] != PIN or manifest["source"]["archive_sha256"] != ARCHIVE_SHA256:
        raise ValueError("Selection archive binding mismatch")
    codes = [s["set"] for s in manifest["selected_sets"]]
    if len(codes) != len(set(codes)):
        raise ValueError("Duplicate selected set")
    output.mkdir(parents=True, exist_ok=False)
    results, excluded = [], []
    for selected in manifest["selected_sets"]:
        code = selected["set"]
        try:
            source = next(s for s in inventory["sets"] if s["provider_set_id"] == code)
            if (
                source["source_file"] != selected["source_file"]
                or members[source["source_file"]]["sha256"] != selected["source_sha256"]
            ):
                raise ValueError("Selected source member mismatch")
            assessment = prepare(directory, code, inventory=inventory)
            if len(assessment["package"]["cards"]) != selected["records"] or sorted(
                assessment["enumerated_ids"]
            ) != sorted(selected["external_ids"]):
                raise ValueError("Selected enumeration mismatch")
            if (
                assessment["source_time"] != manifest["source"]["cutoff"]
                or assessment["source_time"] != sources["tcgdex-archive"]["retrieved_at"]
            ):
                raise ValueError("Selected cutoff mismatch")
            first = package_files(directory, assessment)
            repeat = package_files(directory, prepare(directory, code, inventory=inventory))
            if first != repeat:
                raise ValueError("Package reproduction differs")
            target = output / code
            target.mkdir()
            for name, raw in first.items():
                (target / name).write_text(raw)
            results.append(
                dict(
                    set=code,
                    records=selected["records"],
                    files={
                        name: dict(
                            bytes=len(raw.encode()),
                            file_sha256=hashlib.sha256(raw.encode()).hexdigest(),
                            repeat_sha256=hashlib.sha256(repeat[name].encode()).hexdigest(),
                        )
                        for name, raw in first.items()
                    },
                )
            )
        except (ValueError, KeyError, StopIteration) as exc:
            excluded.append(dict(set=code, records=selected["records"], reason=str(exc)))
    result = dict(
        status="PASS" if not excluded else "PARTIAL",
        selected_sets=len(codes),
        prepared_sets=len(results),
        records=sum(r["records"] for r in results),
        packages=results,
        exclusions=excluded,
        archive_loads=1,
        archive_members_verified=len(members),
        literal_parse_gaps=len(failures),
        selection_file_sha256=hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        inventory_files={
            name: hashlib.sha256((directory / name).read_bytes()).hexdigest()
            for name in ("summary.json", "sets.json", "cards.json")
        },
        preparation_tool_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        provider_operations=0,
        customer_writes=0,
    )
    (output.parent / "preparation.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--set", default="bw1")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.manifest:
        result = prepare_batch(args.inventory, args.manifest, args.output)
        print(json.dumps({k: v for k, v in result.items() if k not in {"packages", "inventory_files"}}))
        return
    assessment = prepare(args.inventory, args.set)
    args.output.mkdir(exist_ok=False, parents=True)
    for key, value in (("assessment", assessment), ("package", assessment["package"])):
        (args.output / (key + ".json")).write_text(encode(value) + "\n")
    (args.output / "binding.json").write_text(
        encode(
            dict(
                inventory_summary_sha256=hashlib.sha256(
                    (args.inventory / "summary.json").read_bytes()
                ).hexdigest(),
                source_cutoff=assessment["source_time"],
                package_sha256=hashlib.sha256(encode(assessment["package"]).encode()).hexdigest(),
                publication="not_performed",
                identity_policy="Numbered unspecified parent only; literal variants remain separate inventory evidence",
                frozen_goal_expansion=False,
                provider_operations=0,
            )
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
