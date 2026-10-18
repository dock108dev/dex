"""Deterministic all-generation English physical inventory from a frozen local archive.

No upstream code execution, extraction, acquisition, customer write or publication.
External bindings establish existing matches; image metadata never supplies bytes
or variant proof. Unresolved multi-species records remain outside proposals.
"""

import argparse
import hashlib
import json
import re
import sqlite3
import tarfile
from collections import Counter, defaultdict
from pathlib import Path

from prepare_d6 import english_variants, parse

PIN = "99c994747cf7519a3e51166cc932de79a88bd4b3"
ARCHIVE_SHA256 = "1431e3be180cc5c8e491e480fd78b2b721155622372591d9f82bfb8aa83a6cce"
REPO = Path(__file__).resolve().parents[1]
MAX_MEMBERS = 100000
MAX_MEMBER_BYTES = 2 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def coverage_role(code, name):
    """An explicit project index over literal retained names/IDs, not release proof."""
    if (
        any(
            word in name
            for word in ("Gallery", "Shiny Vault", "Classic Collection", "Alternate", "Unown Collection")
        )
        or code == "rc"
    ):
        return "subset"
    if any(word in name for word in ("Promo", "POP Series", "McDonald's", "Futsal")) or code in {"bog", "sp"}:
        return "promo"
    if code.startswith("tk-") or code in {"xy0", "mfb", "sve", "mee", "jumbo", "ru1", "si1", "ex5.5"}:
        return "supplemental"
    if "." in code or code in {"dv1", "dc1", "g1", "det1", "sm115", "cel25", "30th"}:
        return "special"
    if re.fullmatch(r"(?:base|neo|gym|ecard|ex|dp|pl|hgss|bw|xy|sm|swsh|sv|me)\d+", code) or code in {
        "lc",
        "col1",
    }:
        return "main"
    return "unresolved"


def read_retained(repo):
    evidence = repo / "evidence/d6-20261005"
    ledger = json.loads((evidence / "source-ledger.json").read_text())
    sources = {r["key"]: r for r in ledger["attempts"] if r.get("key", "").startswith("tcgdex-")}
    for key in ("tcgdex-archive", "tcgdex-tree", "tcgdex-commit", "tcgdex-license"):
        assert digest((repo / sources[key]["response_path"]).read_bytes()) == sources[key]["sha256"], key
    archive = repo / sources["tcgdex-archive"]["response_path"]
    if digest(archive.read_bytes()) != ARCHIVE_SHA256:
        raise ValueError("Pinned archive mismatch")
    commit = json.loads((evidence / "raw/tcgdex-commit.raw").read_text())
    tree = json.loads((evidence / "raw/tcgdex-tree.raw").read_text())
    root_entries = sorted(
        (r for r in tree["tree"] if "/" not in r["path"]),
        key=lambda r: r["path"] + ("/" if r["type"] == "tree" else ""),
    )
    root_bytes = b"".join(
        r["mode"].lstrip("0").encode() + b" " + r["path"].encode() + b"\0" + bytes.fromhex(r["sha"])
        for r in root_entries
    )
    root_sha = hashlib.sha1(b"tree " + str(len(root_bytes)).encode() + b"\0" + root_bytes).hexdigest()
    if (
        commit["sha"] != PIN
        or tree.get("truncated") is not False
        or root_sha != commit["commit"]["tree"]["sha"]
        or tree["sha"] not in {PIN, root_sha}
    ):
        raise ValueError("Frozen commit/tree mismatch or truncated tree")
    blobs = {
        r["path"]: r
        for r in tree["tree"]
        if r["type"] == "blob" and r["path"].startswith("data/") and r["path"].endswith(".ts")
    }
    parsed, members, failures, total = {}, {}, [], 0
    with tarfile.open(archive) as tar:
        for index, member in enumerate(tar):
            if index >= MAX_MEMBERS:
                raise ValueError("Archive member ceiling exceeded")
            path = member.name.split("/", 1)[-1]
            if not path.startswith("data/") or not path.endswith(".ts"):
                continue
            if not member.isfile() or member.size > MAX_MEMBER_BYTES or path in members:
                raise ValueError("Invalid retained archive member")
            raw = tar.extractfile(member).read(MAX_MEMBER_BYTES + 1)
            total += len(raw)
            if total > MAX_TOTAL_BYTES or len(raw) != member.size:
                raise ValueError("Retained member byte ceiling exceeded")
            blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
            if path not in blobs or blobs[path]["sha"] != blob or blobs[path]["size"] != len(raw):
                raise ValueError("Archive member and independent Git blob conflict")
            members[path] = dict(sha256=digest(raw), git_blob=blob, bytes=len(raw))
            try:
                parsed[path] = parse(raw.decode("utf-8"))
            except (ValueError, IndexError, SyntaxError, UnicodeError, RecursionError):
                failures.append(dict(path=path, reason="literal-parser-unresolved"))
    if set(members) != set(blobs):
        raise ValueError("Archive and complete retained tree member sets differ")
    return parsed, members, failures, sources


def published(root):
    path = root / "inventory.db"
    with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as db:
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA query_only=ON")
        db.execute("BEGIN")
        rows = [
            dict(r)
            for r in db.execute(
                "SELECT p.*,s.name AS set_name FROM printings p JOIN catalog_sets s ON p.set_id=s.id WHERE p.publication_state='published' AND s.publication_state='published' ORDER BY p.id"
            )
        ]
        mappings = [
            dict(r)
            for r in db.execute(
                "SELECT * FROM external_mappings WHERE entity_kind='printing' ORDER BY provider,external_id"
            )
        ]
    if len(rows) > 100000:
        raise ValueError("Published lookup exceeds finite inventory ceiling")
    by_id = {r["id"]: r for r in rows}
    by_numbered = defaultdict(set)
    for mapping in mappings:
        if mapping["provider"] == "tcgdex:en" and mapping["internal_id"] in by_id:
            by_numbered[mapping["external_id"].split(":", 1)[0]].add(mapping["internal_id"])
    children = defaultdict(set)
    for row in rows:
        attrs = json.loads(row["attributes"])
        parent = attrs.get("parent_printing_id")
        if parent:
            children[parent].add(row["id"])
    return rows, by_id, by_numbered, children


def inventory(repo, root):
    parsed, members, failures, sources = read_retained(repo)
    current, by_id, by_numbered, children = published(root)
    old = json.loads((repo / "evidence/d7-20261005/universe.json").read_text())
    old_sets = {s["provider_set_id"]: s for s in old["sets"]}
    images = json.loads((repo / "src/pokemon_hunter/beta/data/cx04_image_mappings.json").read_text())["cards"]
    image_counts = Counter(
        (r["set_name"], r["name"], r["language"], r["collector_number"], r["pokemon_dex"]) for r in images
    )
    sets, cards, exclusions = [], [], []
    for path, source in sorted(parsed.items()):
        if len(Path(path).parts) != 3 or not source.get("id") or not source.get("name", {}).get("en"):
            continue
        code = source["id"]
        era = parsed.get(str(Path(path).parent) + ".ts", {}).get("id", "unknown")
        medium = "digital" if era == "tcgp" or "Pocket" in path else "physical"
        role = coverage_role(code, source["name"]["en"])
        release_date = source.get("releaseDate")
        release_status = (
            "released-by-frozen-cutoff"
            if isinstance(release_date, str)
            and release_date <= sources["tcgdex-archive"]["retrieved_at"][:10]
            else "unreleased-at-cutoff"
            if isinstance(release_date, str)
            else "unknown-release-date"
        )
        prefix = path[:-3] + "/"
        paths = sorted(p for p in members if p.startswith(prefix) and len(Path(p).parts) == 4)
        set_cards, gaps = [], []
        for card_path in paths:
            data = parsed.get(card_path)
            if data is None or not isinstance(data.get("name", {}).get("en"), str):
                gaps.append(
                    dict(path=card_path, reason="parser-failure" if data is None else "no-english-name")
                )
                continue
            name, number = data["name"]["en"], Path(card_path).stem
            external = code + "-" + number
            category, species = data.get("category"), data.get("dexId", [])
            resolved = category in {"Trainer", "Energy"} and not species
            if category == "Pokemon":
                resolved = (
                    isinstance(species, list)
                    and len(species) == 1
                    and type(species[0]) is int
                    and 1 <= species[0] <= 1025
                )
            disposition = (
                "resolved"
                if resolved
                else "unresolved-multi-species"
                if isinstance(species, list) and len(species) > 1
                else "unresolved-category-or-species"
            )
            if disposition != "resolved":
                gaps.append(dict(path=card_path, reason=disposition, species=species))
            variants, rejected = english_variants(data.get("variants", []))
            combinations = []
            seen_variants = set()
            for variant in variants:
                descriptor = {k: v for k, v in variant.items() if k != "thirdParty"}
                key = encode(descriptor)
                if key in seen_variants:
                    continue
                seen_variants.add(key)
                combinations.append(
                    dict(
                        descriptor=descriptor,
                        external_id=external + ":" + digest(key.encode())[:16],
                        source_variant=variant,
                    )
                )
            matched = sorted(by_numbered.get(external, ()))
            child_ids = sorted({child for pid in matched for child in children.get(pid, ())})
            single_species = species[0] if resolved and category == "Pokemon" else None
            image_key = source["name"]["en"], name, "en", number, single_species
            official = source.get("cardCount", {}).get("official")
            number_kind = (
                "secret-number"
                if number.isdecimal() and type(official) is int and int(number) > official
                else "numeric"
                if number.isdecimal()
                else "literal-subset-or-promo-number"
            )
            row = dict(
                external_id=external,
                provider_set_id=code,
                set_name=source["name"]["en"],
                number=number,
                name=name,
                category=category,
                rarity=data.get("rarity"),
                species=species,
                language="en",
                medium=medium,
                era=era,
                release_status=release_status,
                number_evidence=dict(member_stem=number, source_local_id=data.get("localId")),
                disposition=disposition,
                source_file=card_path,
                source_sha256=members[card_path]["sha256"],
                forms={
                    k: data[k]
                    for k in ("stage", "suffix", "prefix", "regulationMark", "trainerType", "energyType")
                    if k in data
                },
                number_kind=number_kind,
                coverage_role=role,
                literal_number_prefix=re.match(r"^[A-Za-z]+", number).group()
                if re.match(r"^[A-Za-z]+", number)
                else None,
                variants=variants,
                supported_combinations=combinations,
                variant_exclusions=rejected,
                variant_completeness="unknown",
                distribution="unresolved",
                current_matches=matched,
                existing_children=child_ids,
                proposed_addition=medium == "physical"
                and release_status == "released-by-frozen-cutoff"
                and resolved
                and not matched,
                image_binding="reviewed-numbered-reference-not-variant-proof"
                if image_counts[image_key] == 1
                else "unavailable",
                missing_image=image_counts[image_key] != 1,
            )
            if medium == "physical":
                cards.append(row)
            else:
                exclusions.append(dict(external_id=external, reason="digital-pocket", source_file=card_path))
            set_cards.append(row)
        previous = old_sets.get(code)
        if (
            previous is None
            or previous["english_source_records"] != len(set_cards)
            or previous["medium"] != medium
        ):
            raise ValueError("Recomputed set denominator conflicts with retained universe")
        sets.append(
            dict(
                provider_set_id=code,
                name=source["name"]["en"],
                era=era,
                medium=medium,
                release_date=source.get("releaseDate"),
                release_status=release_status,
                source_file=path,
                source_sha256=members[path]["sha256"],
                archive_card_members=len(paths),
                english_records=len(set_cards),
                official_numbered_count=source.get("cardCount", {}).get("official"),
                scope_evidence={
                    k: source[k]
                    for k in ("serie", "cardCount", "abbreviations", "releaseDate")
                    if k in source
                },
                coverage_role=role,
                scope_classification="Project inventory partition inferred by explicit retained name/ID rules; not independent release/distribution proof",
                gaps=gaps,
                prior_enumeration_complete=previous["enumeration_complete"],
                reconciled_enumeration="empty-source-set"
                if not paths
                else "retained-member-enumeration-with-gaps"
                if gaps
                else "retained-member-enumeration-complete",
                source_completeness="unknown",
            )
        )
    if len(sets) != len(old_sets):
        raise ValueError("Set inventory differs from retained universe")
    physical = [s for s in sets if s["medium"] == "physical"]
    summary = dict(
        schema="dex-broad-catalog-inventory-v1",
        commit=PIN,
        archive_sha256=ARCHIVE_SHA256,
        frozen_source_time=sources["tcgdex-archive"]["retrieved_at"],
        current_coverage_claim=False,
        provider_operations=0,
        archive_tree_members_verified=len(members),
        literal_parser_failures=failures,
        physical_sets=len(physical),
        digital_sets=sum(s["medium"] == "digital" for s in sets),
        english_physical_records=len(cards),
        categories=dict(Counter(c["category"] for c in cards)),
        set_coverage_roles=dict(Counter(s["coverage_role"] for s in physical)),
        card_coverage_roles=dict(Counter(c["coverage_role"] for c in cards)),
        number_kinds=dict(Counter(c["number_kind"] for c in cards)),
        dispositions=dict(Counter(c["disposition"] for c in cards)),
        supported_variant_combinations=sum(len(c["supported_combinations"]) for c in cards),
        records_without_variant_evidence=sum(not c["supported_combinations"] for c in cards),
        variant_language_exclusions=sum(len(c["variant_exclusions"]) for c in cards),
        matched_source_records=sum(bool(c["current_matches"]) for c in cards),
        proposed_numbered_additions=sum(c["proposed_addition"] for c in cards),
        release_statuses=dict(Counter(c["release_status"] for c in cards)),
        published_identities=len(current),
        existing_children=sum(bool(json.loads(c["attributes"]).get("parent_printing_id")) for c in current),
        published_metadata_sha256=digest(encode(current).encode()),
        missing_image_records=sum(c["missing_image"] for c in cards),
        prior_incomplete_sets=[s for s in physical if not s["prior_enumeration_complete"]],
        newly_identified_gap_sets=[s for s in physical if s["prior_enumeration_complete"] and s["gaps"]],
        incomplete_source_evidence_sets=sum(
            bool(s["gaps"]) or not s["archive_card_members"] for s in physical
        ),
        us_applicability="unresolved; English source evidence alone is insufficient",
        publication="not_performed",
    )
    return dict(summary=summary, sets=sets, cards=cards, exclusions=exclusions, published=current)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    result = inventory(args.repo.resolve(), args.root.resolve(strict=True))
    for key, value in result.items():
        (args.output / (key + ".json")).write_text(encode(value) + "\n")
    print(json.dumps(result["summary"], indent=2))


if __name__ == "__main__":
    main()
