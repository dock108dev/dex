"""Extract minimal MIT-licensed TCGdex metadata from a pinned, read-only source checkout.

No source code execution, prices, artwork, rules text or owner data. Explicit legacy
set/number/name reconciliation only; differences outside the reviewed list stop conversion.
"""

import argparse
import ast
import hashlib
import json
import re
import subprocess
import unicodedata
from pathlib import Path

# Individually reviewed spelling/qualifier differences at identical set + number.
REVIEWED_NAMES = {
    "base_set_2-102": ("Imposter Professor Oak", "Impostor Professor Oak"),
    "wizards_black_star_promos-24": ("_____'s Pikachu", "___________'s Pikachu"),
    "neo_destiny-96": ("Thought Wave Machine", "Thought Wave Machine (Rocket's Secret Machine)"),
}


def normalized(name):
    return (
        unicodedata.normalize("NFKC", name)
        .casefold()
        .replace("’", "'")
        .replace("[", "")
        .replace("]", "")
        .replace(" ♀", "♀")
        .replace(" ♂", "♂")
    )


def literal(text, field):
    found = re.search(r"^\t" + field + r':\s*("(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\')', text, re.M)
    if not found:
        raise ValueError("Missing literal field: " + field)
    return ast.literal_eval(found.group(1))


def prepare(source, output):
    project = Path(__file__).resolve().parents[1]
    reference = json.loads((project / "config/pokedex_251.example.json").read_text())["cards"]
    commit = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    if subprocess.check_output(["git", "-C", str(source), "status", "--porcelain"], text=True).strip():
        raise ValueError("Source checkout must be unmodified")
    license_bytes = (source / "LICENSE").read_bytes()
    if b"MIT License" not in license_bytes or b"Copyright (c) 2021 TCGdex" not in license_bytes:
        raise ValueError("Re-review changed source license")
    packages = {}
    sources = {}
    species = {}
    for legacy, old in reference.items():
        group = "Neo" if old["set"].startswith("Neo ") else "Base"
        folder = source / "data" / group / old["set"]
        cardpath = folder / (old["number"] + ".ts")
        raw = cardpath.read_bytes()
        text = raw.decode()
        block = re.search(r"^\tname: \{(.*?)^\t\}", text, re.M | re.S).group(1)
        found = re.search(r'\ben:\s*("(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\')', block)
        name = ast.literal_eval(found.group(1))
        if normalized(name) != normalized(old["name"]) and REVIEWED_NAMES.get(legacy) != (old["name"], name):
            raise ValueError("Unreviewed name mismatch: " + legacy)
        dex = re.search(r"^\tdexId:\s*\[([^]]*)\]", text, re.M)
        dexids = [int(x) for x in re.findall(r"\d+", dex.group(1))] if dex else []
        number = dexids[0] if len(dexids) == 1 else None
        if old.get("pokemon_dex") != number:
            raise ValueError("Species conflict: " + legacy)
        category = literal(text, "category")
        rarity = literal(text, "rarity")
        eligible = bool(
            category == "Pokemon"
            and number
            and 1 <= number <= 251
            and not name.startswith(("Dark ", "Light ", "Shining ", "Cool ", "Flying ", "Surfing "))
            and "'s " not in name
        )
        if eligible != old["dex_eligible"]:
            raise ValueError("Unreviewed goal eligibility difference: " + legacy)
        if eligible and number not in species:
            species[number] = re.sub(r"Unown(?: | \[)[A-Z](?:\])?$", "Unown", name)
        setkey = old["set_id"]
        if setkey not in packages:
            setraw = folder.with_suffix(".ts").read_bytes()
            setid = literal(setraw.decode(), "id")
            packages[setkey] = {
                "schema_version": "dex-catalog-v1",
                "game": "pokemon",
                "set_key": setid,
                "set_name": old["set"],
                "language": "en",
                "aliases": [old["set"]],
                "provider": "tcgdex",
                "version": commit,
                "source_url": "https://github.com/tcgdex/cards-database/tree/" + commit + "/data/" + group,
                "source_sha256": "",
                "metadata_permission": "TCGdex cards-database MIT; copyright (c) 2021 TCGdex. Attribution retained in TCGDEX_LICENSE.txt. Minimal hosted metadata; no artwork, prices or rules text.",
                "image_permission": "not-included",
                "coverage": "catalog-entries",
                "expected_count": 0,
                "reconcile_legacy_set": setkey,
                "cards": [],
            }
            sources[setkey] = {
                str(folder.with_suffix(".ts").relative_to(source)): hashlib.sha256(setraw).hexdigest()
            }
        p = packages[setkey]
        p["cards"].append(
            {
                "external_id": p["set_key"] + "-" + old["number"],
                "number": old["number"],
                "name": name,
                "legacy_id": legacy,
                "metadata": {
                    "pokemon_dex": number,
                    "dex_eligible": eligible,
                    "supertype": {"Pokemon": "Pokémon"}.get(category, category),
                    "rarity": rarity,
                },
            }
        )
        sources[setkey][str(cardpath.relative_to(source))] = hashlib.sha256(raw).hexdigest()
    output.mkdir(parents=True, exist_ok=True)
    for setkey, p in packages.items():
        p["expected_count"] = len(p["cards"])
        p["source_sha256"] = hashlib.sha256(json.dumps(sources[setkey], sort_keys=True).encode()).hexdigest()
        (output / (setkey + ".json")).write_text(json.dumps(p, ensure_ascii=False, indent=2) + "\n")
    (output / "source-manifest.json").write_text(
        json.dumps(
            {
                "commit": commit,
                "license_sha256": hashlib.sha256(license_bytes).hexdigest(),
                "sets": sources,
                "reviewed_name_differences": REVIEWED_NAMES,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )
    (output / "species.json").write_text(
        json.dumps(
            {
                k: {"name": v, "dex_number": k, "generation": 1 if k <= 151 else 2}
                for k, v in sorted(species.items())
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )
    print(
        json.dumps(
            {
                "sets": len(packages),
                "cards": sum(len(p["cards"]) for p in packages.values()),
                "named_species": len(species),
                "source_commit": commit,
            }
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    prepare(args.source, args.output)
