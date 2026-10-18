"""Separate retained-archive review. Reads literal data; never executes upstream code."""

import argparse
import ast
import base64
import hashlib
import json
import re
import tarfile
from collections import Counter, defaultdict
from pathlib import Path

PIN = "99c994747cf7519a3e51166cc932de79a88bd4b3"
ARCHIVE_SHA256 = "1431e3be180cc5c8e491e480fd78b2b721155622372591d9f82bfb8aa83a6cce"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


class LiteralReader:
    """Independent character scanner, deliberately separate from prepare_d6.parse."""

    def __init__(self, text):
        require(len(text.encode()) <= 2 * 1024 * 1024, "Oversized literal member")
        declaration = re.search(r"\bconst\s+(\w+)\s*:\s*\w+\s*=", text)
        require(declaration is not None, "Missing typed literal declaration")
        self.text, self.pos, self.name = text, declaration.end(), declaration[1]
        self.references = set(re.findall(r"import\s+(\w+)\s+from\s+", text[: declaration.start()]))

    def space(self):
        while self.pos < len(self.text):
            if self.text[self.pos].isspace():
                self.pos += 1
            elif self.text.startswith("//", self.pos):
                end = self.text.find("\n", self.pos)
                self.pos = len(self.text) if end < 0 else end + 1
            elif self.text.startswith("/*", self.pos):
                end = self.text.find("*/", self.pos + 2)
                require(end >= 0, "Unterminated comment")
                self.pos = end + 2
            else:
                break

    def take(self, value):
        self.space()
        if self.text.startswith(value, self.pos):
            self.pos += len(value)
            return True
        return False

    def word(self):
        self.space()
        match = re.match(r"[A-Za-z_$][\w$]*", self.text[self.pos :])
        require(match is not None, "Expected literal identifier")
        self.pos += len(match[0])
        return match[0]

    def string(self):
        self.space()
        start, quote = self.pos, self.text[self.pos]
        self.pos += 1
        while self.pos < len(self.text):
            char = self.text[self.pos]
            self.pos += 1
            if char == "\\":
                self.pos += 1
            elif char == quote:
                return ast.literal_eval(self.text[start : self.pos])
        raise ValueError("Unterminated literal string")

    def value(self, depth=0):
        require(depth < 80, "Literal nesting ceiling")
        self.space()
        require(self.pos < len(self.text), "Truncated literal")
        char = self.text[self.pos]
        if char in "\"'":
            value = self.string()
            while self.take("+"):
                self.space()
                require(self.text[self.pos] in "\"'", "Only literal string concatenation")
                value += self.string()
            return value
        if self.take("{"):
            result = {}
            while not self.take("}"):
                self.space()
                key = self.string() if self.text[self.pos] in "\"'" else self.word()
                require(key not in result, "Duplicate literal key")
                require(self.take(":"), "Explicit object values required")
                result[key] = self.value(depth + 1)
                if not self.take(","):
                    require(self.take("}"), "Unsupported object expression")
                    break
            return result
        if self.take("["):
            result = []
            while not self.take("]"):
                result.append(self.value(depth + 1))
                if not self.take(","):
                    require(self.take("]"), "Unsupported array expression")
                    break
            return result
        number = re.match(r"-?\d+(?:\.\d+)?", self.text[self.pos :])
        if number:
            self.pos += len(number[0])
            return float(number[0]) if "." in number[0] else int(number[0])
        word = self.word()
        if word in {"true", "false", "null", "undefined"}:
            return {"true": True, "false": False, "null": None, "undefined": None}[word]
        require(word in self.references, "Unbound literal reference")
        return {"reference": word}

    def read(self):
        result = self.value()
        self.take(";")
        self.space()
        tail = self.text[self.pos :].strip()
        require(
            re.fullmatch(r"export\s+default\s+" + re.escape(self.name) + r"\s*;?", tail),
            "Unsupported executable suffix",
        )
        require(isinstance(result, dict), "Object literal required")
        return result


def parse_literal(text):
    return LiteralReader(text).read()


def verify_records(package, assessment, source_set, series, records):
    """Compare directly to source members, without trusting inventory card facts."""
    code = source_set["id"]
    url = f"https://codeload.github.com/tcgdex/cards-database/tar.gz/{PIN}"
    require(package["set_key"] == code.replace(".", "-"), "Set key conflict")
    require(package["set_name"] == source_set["name"]["en"], "Set name conflict")
    require(package["provider"] == "tcgdex" and package["game"] == "pokemon", "Provider/game conflict")
    require(package["language"] == assessment["language"] == "en", "Language conflict")
    require(
        package["source_sha256"] == assessment["source_sha256"] == ARCHIVE_SHA256, "Archive binding conflict"
    )
    require(package["source_url"] == assessment["source_url"] == url, "Source URL conflict")
    require(package["image_permission"] == "not-included", "Artwork assertion")
    require(
        package["metadata_permission"]
        == "MIT; Copyright (c) 2021 TCGdex; retained evidence/d6-20261005/TCGDEX_LICENSE.txt",
        "Retained metadata license/notice conflict",
    )
    require(package["coverage"] == "catalog-entries", "Source enumeration assertion changed")
    require(assessment["set_id"] == f"tcgdex:en:{package['set_key']}", "Assessment identity conflict")
    require(assessment["catalog_policy"] == "english-physical-all", "Catalog policy conflict")
    require(assessment["medium"] == "physical" and series["id"] != "tcgp", "Out-of-scope medium")
    require(assessment["era"] == series["id"], "Series conflict")
    require(
        assessment["release_status"] == "released"
        and source_set["releaseDate"] <= assessment["source_time"][:10],
        "Set date/cutoff conflict",
    )
    require(assessment["evidence_class"] == "retained-real-source", "Source evidence class conflict")
    expected = {code + "-" + number: (number, source) for number, source in records.items()}
    cards = package["cards"]
    ids = [c["external_id"] for c in cards]
    require(len(ids) == len(set(ids)), "Duplicate package external identity")
    require(len({c["number"] for c in cards}) == len(cards), "Duplicate collector number")
    require(set(ids) == set(expected), "Missing or extra source identity")
    require(
        assessment["enumeration_complete"] is True
        and sorted(assessment["enumerated_ids"]) == sorted(expected),
        "Incomplete/duplicate enumeration",
    )
    require(
        package["expected_count"] == assessment["expected_target_count"] == len(expected),
        "Target count conflict",
    )
    for card in cards:
        number, source = expected[card["external_id"]]
        require(
            card["number"] == number and source.get("localId", number) == number,
            "Literal collector number conflict",
        )
        require(card["name"] == source["name"]["en"], "English name conflict")
        require(
            all(card.get(k) is None for k in ("edition", "finish", "variant", "legacy_id")),
            "Unproved physical or legacy identity",
        )
        category, dex = source["category"], source.get("dexId", [])
        require(category in {"Pokemon", "Trainer", "Energy"}, "Unknown category")
        if category == "Pokemon":
            require(
                isinstance(dex, list) and len(dex) == 1 and type(dex[0]) is int and 1 <= dex[0] <= 1025,
                "Unresolved canonical species",
            )
            species = dex[0]
        else:
            require(dex == [], "Non-Pokemon species conflict")
            species = None
        metadata = dict(
            pokemon_dex=species,
            dex_eligible=species is not None,
            supertype={"Pokemon": "Pokémon", "Trainer": "Trainer", "Energy": "Energy"}[category],
            rarity=source.get("rarity") or "Unknown",
        )
        require(card["metadata"] == metadata, "Category/species/rarity conflict")
        require(source.get("set") == {"reference": "Set"}, "Source set membership conflict")
    return dict(
        records=len(cards),
        categories=dict(Counter(c["metadata"]["supertype"] for c in cards)),
        above_251=sum((c["metadata"]["pokemon_dex"] or 0) > 251 for c in cards),
    )


REVIEWER = "Independent implementation in same engineering session; not external review"
IMPLEMENTATION = "Independent character scanner and Git tree/blob reconstruction; no preparation parser"


def load_review_context(repo, inventory, codes):
    """Verify the complete retained archive/tree once; retain selected raw literals."""
    evidence = repo / "evidence/d6-20261005"
    summary_raw = (inventory / "summary.json").read_bytes()
    summary = json.loads(summary_raw)
    require(
        summary["commit"] == PIN and summary["archive_sha256"] == ARCHIVE_SHA256,
        "Inventory archive/commit conflict",
    )
    inventory_rows = json.loads((inventory / "sets.json").read_text())
    inventory_sets = {row["provider_set_id"]: row for row in inventory_rows}
    require(len(inventory_sets) == len(inventory_rows), "Duplicate inventory set identity")
    require(all(code in inventory_sets for code in codes), "Missing selected inventory set")
    ledger = json.loads((evidence / "source-ledger.json").read_text())
    sources = {r["key"]: r for r in ledger["attempts"] if r.get("key", "").startswith("tcgdex-")}
    for key in ("tcgdex-archive", "tcgdex-tree", "tcgdex-commit", "tcgdex-license"):
        require(
            sha((repo / sources[key]["response_path"]).read_bytes()) == sources[key]["sha256"],
            "Retained ledger bytes conflict: " + key,
        )
    license_metadata = json.loads((repo / sources["tcgdex-license"]["response_path"]).read_text())
    require(license_metadata["encoding"] == "base64", "Unknown retained license envelope")
    license_raw = (evidence / "TCGDEX_LICENSE.txt").read_bytes()
    require(license_raw == base64.b64decode(license_metadata["content"]), "Retained license content conflict")
    require(sources["tcgdex-archive"]["sha256"] == ARCHIVE_SHA256, "Pinned archive conflict")
    require(
        summary["frozen_source_time"] == sources["tcgdex-archive"]["retrieved_at"],
        "Inventory historical cutoff conflict",
    )
    tree = json.loads((evidence / "raw/tcgdex-tree.raw").read_text())
    commit = json.loads((evidence / "raw/tcgdex-commit.raw").read_text())
    require(commit["sha"] == PIN and tree["truncated"] is False, "Commit or incomplete tree conflict")
    entries = {r["path"]: r for r in tree["tree"]}
    require(len(entries) == len(tree["tree"]), "Duplicate Git tree member")
    license_blob = hashlib.sha1(b"blob " + str(len(license_raw)).encode() + b"\0" + license_raw).hexdigest()
    require(
        license_blob == entries["LICENSE"]["sha"] == license_metadata["sha"], "Pinned license blob conflict"
    )
    # Reconstruct every tree, including all intermediate links to the pinned commit root.
    directories = {
        "": commit["commit"]["tree"]["sha"],
        **{p: r["sha"] for p, r in entries.items() if r["type"] == "tree"},
    }
    by_parent = defaultdict(list)
    for path, row in entries.items():
        parent = "" if Path(path).parent == Path(".") else str(Path(path).parent)
        by_parent[parent].append(row)
    for parent, expected_sha in directories.items():
        children = by_parent[parent]
        children.sort(key=lambda r: Path(r["path"]).name + ("/" if r["type"] == "tree" else ""))
        raw = b"".join(
            r["mode"].lstrip("0").encode()
            + b" "
            + Path(r["path"]).name.encode()
            + b"\0"
            + bytes.fromhex(r["sha"])
            for r in children
        )
        actual = hashlib.sha1(b"tree " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
        require(actual == expected_sha, "Git tree linkage conflict")
    require(tree["sha"] in {PIN, directories[""]}, "Tree root response conflict")
    source_paths = {inventory_sets[code]["source_file"] for code in codes}
    prefixes = tuple(path[:-3] + "/" for path in source_paths)
    series_paths = {str(Path(path).parent) + ".ts" for path in source_paths}
    wanted = {
        p for p, r in entries.items() if r["type"] == "blob" and p.startswith("data/") and p.endswith(".ts")
    }
    seen, frozen, retained = set(), {}, {}
    archive_license_seen = False
    total = 0
    with tarfile.open(repo / sources["tcgdex-archive"]["response_path"]) as archive:
        for index, member in enumerate(archive):
            require(index < 100000, "Archive member ceiling")
            path = member.name.split("/", 1)[-1]
            if path == "LICENSE":
                require(not archive_license_seen, "Duplicate archive license")
                archive_license_seen = True
                require(member.isfile() and member.size == len(license_raw), "Invalid archive license")
                require(archive.extractfile(member).read() == license_raw, "Archive license conflict")
            if path not in wanted:
                require(not (path.startswith("data/") and path.endswith(".ts")), "Unexpected source member")
                continue
            require(
                path not in seen and member.isfile() and member.size <= 2 * 1024 * 1024,
                "Duplicate/invalid source member",
            )
            seen.add(path)
            raw = archive.extractfile(member).read()
            total += len(raw)
            require(total <= 256 * 1024 * 1024, "Archive total byte ceiling")
            blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
            require(blob == entries[path]["sha"] and len(raw) == entries[path]["size"], "Git blob conflict")
            if path in source_paths | series_paths or path.startswith(prefixes):
                retained[path] = raw
                frozen[path] = dict(sha256=sha(raw), git_blob_sha1=blob, bytes=len(raw))
    require(archive_license_seen, "Missing archive license")
    require(seen == wanted, "Missing archive/tree source members")
    return dict(
        inventory_sets=inventory_sets,
        inventory_summary_sha256=sha(summary_raw),
        source_cutoff=sources["tcgdex-archive"]["retrieved_at"],
        retained=retained,
        frozen=frozen,
        archive_tree_members_verified=len(seen),
        git_trees_verified=len(directories),
        retained_license_sha256=sha(license_raw),
    )


def review_prepared(context, directory, code):
    """Compare one package with independent literals; a failure affects this set."""
    selected = context["inventory_sets"][code]
    source_path = selected["source_file"]
    prefix, series_path = source_path[:-3] + "/", str(Path(source_path).parent) + ".ts"
    frozen = {
        p: row
        for p, row in context["frozen"].items()
        if p in {source_path, series_path} or p.startswith(prefix)
    }
    require(frozen[source_path]["sha256"] == selected["source_sha256"], "Set member binding conflict")
    retained = {p: parse_literal(context["retained"][p].decode()) for p in frozen}
    package_raw = (directory / "package.json").read_bytes()
    assessment_raw = (directory / "assessment.json").read_bytes()
    package = json.loads(package_raw)
    assessment = json.loads(assessment_raw)
    require(package == assessment["package"], "Assessment package differs")
    require(assessment["source_time"] == context["source_cutoff"], "Historical cutoff conflict")
    records = {Path(p).stem: r for p, r in retained.items() if p.startswith(prefix)}
    require(
        all(len(Path(p).parts) == 4 for p in retained if p.startswith(prefix)), "Nested source membership"
    )
    checked = package
    if package.get("schema_version") == "dex-catalog-additions-v1":
        checked = dict(package, cards=package["enumeration"])
        require(package["source_time"] == assessment["source_time"], "Extension cutoff conflict")
        for c in package["enumeration"]:
            member = prefix + c["number"] + ".ts"
            require(
                package["source_members"][c["external_id"]]
                == dict(path=member, sha256=frozen[member]["sha256"]),
                "Extension member provenance conflict",
            )
        require(
            set(package["represented"]) | {c["external_id"] for c in package["cards"]}
            == {c["external_id"] for c in package["enumeration"]},
            "Additive partition conflict",
        )
        require(
            not set(package["represented"]) & {c["external_id"] for c in package["cards"]},
            "Overlapping additive partition",
        )
        full = {c["external_id"]: c for c in package["enumeration"]}
        require(all(full[c["external_id"]] == c for c in package["cards"]), "Changed addition")
    counts = verify_records(checked, assessment, retained[source_path], retained[series_path], records)
    if checked is not package:
        counts.update(
            full_records=counts["records"],
            represented_records=len(package["represented"]),
            full_categories=counts["categories"],
            records=len(package["cards"]),
            categories=dict(Counter(c["metadata"]["supertype"] for c in package["cards"])),
        )
    return dict(
        status="PASS",
        reviewer=REVIEWER,
        implementation=IMPLEMENTATION,
        selected_set=code,
        selected_source_path=source_path,
        commit=PIN,
        archive_sha256=ARCHIVE_SHA256,
        set_member_sha256=frozen[source_path]["sha256"],
        source_cutoff=assessment["source_time"],
        source_set_release_date=retained[source_path]["releaseDate"],
        date_limitation="Set/series metadata only; individual promo issue date, US availability and distribution unknown",
        archive_tree_members_verified=context["archive_tree_members_verified"],
        git_trees_verified=context["git_trees_verified"],
        source_set_facts=retained[source_path],
        retained_license_sha256=context["retained_license_sha256"],
        package_file_sha256=sha(package_raw),
        assessment_file_sha256=sha(assessment_raw),
        members=frozen,
        **counts,
        accepted_english_physical_variant_combinations=sum(
            isinstance(v, dict)
            and ("languages" not in v or isinstance(v["languages"], list) and "en" in v["languages"])
            for r in records.values()
            for v in r.get("variants", [])
        ),
        all_physical_attributes_unknown=True,
        provider_operations=0,
        customer_writes=0,
    )


def review(repo, inventory, directory, code):
    """Backward-compatible single-set source review."""
    return review_prepared(load_review_context(repo, inventory, [code]), directory, code)


def verify_selection(selected, result, package):
    """A manifest is selection evidence, never a replacement for source literals."""
    require(selected["set"] == result["selected_set"], "Manifest set identity conflict")
    require(selected["source_file"] == result["selected_source_path"], "Manifest source path conflict")
    require(selected["source_sha256"] == result["set_member_sha256"], "Manifest source hash conflict")
    require(selected["name"] == package["set_name"], "Manifest set name conflict")
    require(selected["records"] == result["records"], "Manifest selected count conflict")
    expected_ids = selected["external_ids"]
    require(
        len(expected_ids) == len(set(expected_ids))
        and sorted(expected_ids) == sorted(card["external_id"] for card in package["cards"]),
        "Manifest selected identities conflict",
    )
    categories = {
        "Pokémon" if key == "Pokemon" else key: value for key, value in selected["categories"].items()
    }
    require(categories == result["categories"], "Manifest categories conflict")


def review_batch(repo, inventory, directory, manifest_path):
    """Review all selected sets with one shared verified archive/inventory pass."""
    manifest_raw = manifest_path.read_bytes()
    manifest = json.loads(manifest_raw)
    selected = manifest["selected_sets"]
    codes = [row["set"] for row in selected]
    repeated_codes = {code for code, count in Counter(codes).items() if count > 1}
    selection_issues = []
    if repeated_codes:
        selection_issues.append("Duplicate selected set identity")
    if manifest["selected_set_count"] != len(codes):
        selection_issues.append("Manifest total set count conflict")
    if manifest["selected_records"] != sum(row["records"] for row in selected):
        selection_issues.append("Manifest total record count conflict")
    context = load_review_context(repo, inventory, codes)
    source = manifest["source"]
    require(
        Path(source["inventory_directory"]).resolve() == inventory.resolve(),
        "Manifest inventory path conflict",
    )
    require(
        source["summary_sha256"] == context["inventory_summary_sha256"], "Manifest inventory hash conflict"
    )
    require(
        source["commit"] == PIN and source["archive_sha256"] == ARCHIVE_SHA256,
        "Manifest archive identity conflict",
    )
    require(source["cutoff"] == context["source_cutoff"], "Manifest source cutoff conflict")
    results = []
    for row in selected:
        code = row["set"]
        try:
            require(code not in repeated_codes, "Duplicate selected set identity")
            require(re.fullmatch(r"[A-Za-z0-9_.-]+", code) is not None, "Unsafe selected directory")
            package_directory = directory / code
            result = review_prepared(context, package_directory, code)
            package_raw = (package_directory / "package.json").read_bytes()
            assessment_raw = (package_directory / "assessment.json").read_bytes()
            require(
                result["package_file_sha256"] == sha(package_raw)
                and result["assessment_file_sha256"] == sha(assessment_raw),
                "Prepared files changed during source review",
            )
            package = json.loads(package_raw)
            verify_selection(row, result, package)
            binding_raw = (package_directory / "binding.json").read_bytes()
            binding = json.loads(binding_raw)
            canonical_package = json.dumps(
                package, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ).encode()
            require(binding["package_sha256"] == sha(canonical_package), "Prepared package hash conflict")
            require(
                binding["inventory_summary_sha256"] == context["inventory_summary_sha256"],
                "Prepared inventory hash conflict",
            )
            require(binding["source_cutoff"] == context["source_cutoff"], "Prepared source cutoff conflict")
            result.update(
                package_file_sha256=sha(package_raw),
                assessment_file_sha256=sha(assessment_raw),
                binding_file_sha256=sha(binding_raw),
                package_sha256=sha(canonical_package),
            )
        except (ValueError, KeyError, TypeError, IndexError, OSError, UnicodeError) as error:
            result = dict(
                status="HELD", selected_set=code, reason=str(error), provider_operations=0, customer_writes=0
            )
        results.append(result)
    passed = [row for row in results if row["status"] == "PASS"]
    return dict(
        schema="dex-retained-catalog-batch-source-review-v1",
        status="PASS" if len(passed) == len(results) and not selection_issues else "PARTIAL",
        reviewer=REVIEWER,
        implementation=IMPLEMENTATION,
        manifest_sha256=sha(manifest_raw),
        inventory_summary_sha256=context["inventory_summary_sha256"],
        commit=PIN,
        archive_sha256=ARCHIVE_SHA256,
        source_cutoff=context["source_cutoff"],
        archive_verification_passes=1,
        archive_tree_members_verified=context["archive_tree_members_verified"],
        git_trees_verified=context["git_trees_verified"],
        selected_sets=len(selected),
        selected_records=manifest["selected_records"],
        selection_issues=selection_issues,
        passed_sets=len(passed),
        passed_records=sum(row["records"] for row in passed),
        held_sets=len(results) - len(passed),
        sets=results,
        provider_operations=0,
        customer_writes=0,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--package-dir", type=Path)
    parser.add_argument("--set")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument(
        "--directory", type=Path, help="Prepared batch root containing one directory per selected set"
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.manifest:
        if not args.directory or args.package_dir or args.set:
            parser.error("--manifest requires --directory and cannot be combined with --package-dir/--set")
        result = review_batch(args.repo, args.inventory, args.directory, args.manifest)
    else:
        if not args.package_dir or not args.set or args.directory:
            parser.error("Single-set review requires --package-dir and --set")
        result = review(args.repo, args.inventory, args.package_dir, args.set)
    with args.output.open("x") as output:
        output.write(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k not in {"members", "sets"}}))


if __name__ == "__main__":
    main()
