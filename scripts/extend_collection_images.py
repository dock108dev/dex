"""Reproduce all-era private reference identities from retained TCGdex literals.

No network, image bytes, rules text or installation writes. The two spelling
aliases below are explicitly reviewed owner-set names, not fuzzy identity joins.
"""

import hashlib
import json
import tarfile
from pathlib import Path

from prepare_d6 import parse

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "evidence/d6-20261005/raw/tcgdex-archive.raw"
ARCHIVE_SHA256 = "1431e3be180cc5c8e491e480fd78b2b721155622372591d9f82bfb8aa83a6cce"
REVISION = "99c994747cf7519a3e51166cc932de79a88bd4b3"
ORIGINAL_SETS = {
    "Base Set",
    "Base Set 2",
    "Jungle",
    "Fossil",
    "Team Rocket",
    "Wizards Black Star Promos",
    "Gym Heroes",
    "Gym Challenge",
    "Neo Genesis",
    "Neo Discovery",
    "Neo Revelation",
    "Neo Destiny",
}
# Explicit application aliases preserve catalog identity; no input normalization.
SET_ALIASES = {"EX trainer Kit 2 (Minun)": "EX Trainer Kit 2 — Minun"}


def reviewed_cards():
    if hashlib.sha256(ARCHIVE.read_bytes()).hexdigest() != ARCHIVE_SHA256:
        raise ValueError("Retained TCGdex source drift")
    result, gaps = [], []
    with tarfile.open(ARCHIVE) as archive:
        members = {m.name.split("/", 1)[-1]: m for m in archive.getmembers() if m.isfile()}

        def read(path):
            return parse(archive.extractfile(members[path]).read().decode())

        for path in sorted(members):
            if not path.startswith("data/") or path.count("/") != 2 or not path.endswith(".ts"):
                continue
            if "/Pokémon TCG Pocket/" in path:
                continue
            try:
                source = read(path)
                name = source["name"]["en"]
                set_id = source["id"]
                series = read(str(Path(path).parent) + ".ts")["id"]
            except (ValueError, KeyError, IndexError, SyntaxError):
                gaps.append(dict(path=path, reason="unresolved-set-literal"))
                continue
            prefix = path[:-3] + "/"
            for card_path in sorted(members):
                if not card_path.startswith(prefix) or not card_path.endswith(".ts"):
                    continue
                try:
                    card = read(card_path)
                except (ValueError, KeyError, IndexError, SyntaxError):
                    gaps.append(dict(path=card_path, reason="unresolved-card-literal"))
                    continue
                if not isinstance(card.get("name"), dict) or not card["name"].get("en"):
                    continue
                # Retain only public asset identity, not effects/rules text.
                number = Path(card_path).stem
                dex = card.get("dexId", [])
                row = dict(
                    set_name=SET_ALIASES.get(name, name),
                    language="en",
                    collector_number=number,
                    name=card["name"]["en"],
                    pokemon_dex=dex[0] if card.get("category") == "Pokemon" and len(dex) == 1 else None,
                    external_id=f"{set_id}-{number}",
                    image_url=f"https://assets.tcgdex.net/en/{series}/{set_id}/{number}/low.webp",
                )
                # Trainer kit source explicitly provides no scan for this printing.
                if set_id == "tk-ex-m" and number == "7":
                    gaps.append(dict(path=card_path, reason="provider-image-unavailable"))
                    continue
                result.append(row)
                if set_id == "sv03.5":
                    result.append(
                        {**row, "set_name": "Scarlet & Violet—151", "collector_number": number + "/165"}
                    )
                if set_id == "det1":
                    result.append({**row, "collector_number": number + "/18"})
    return result, gaps


def main():
    path = ROOT / "src/pokemon_hunter/beta/data/cx04_image_mappings.json"
    data = json.loads(path.read_bytes())
    cards, gaps = reviewed_cards()
    # Preserve the original reviewed vintage mapping, including independently
    # retained metadata identity adjustments. Add all other exact source keys.
    original = [row for row in data["cards"] if row["set_name"] in ORIGINAL_SETS]
    keys = {
        (row["set_name"], row["language"], row["collector_number"], row["name"], row["pokemon_dex"])
        for row in original
    }
    data["cards"] = original + [
        row
        for row in cards
        if (row["set_name"], row["language"], row["collector_number"], row["name"], row["pokemon_dex"])
        not in keys
    ]
    names = {row["set_name"] for row in data["cards"]} - ORIGINAL_SETS
    report = ROOT / "reports/collection-images-20261014"
    report.mkdir(parents=True, exist_ok=True)
    (report / "source-gaps.json").write_text(json.dumps(gaps, indent=2) + "\n")
    data["card_source_revision"] = REVISION
    data["expanded_set_names"] = sorted(names)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    print(hashlib.sha256(path.read_bytes()).hexdigest())


if __name__ == "__main__":
    main()
