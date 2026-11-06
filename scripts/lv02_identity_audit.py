"""Offline pilot audit against pinned catalog publications and retained metadata.

Outputs proposals only. Never selects a physical child for an unspecified parent,
changes a catalog, admits a price mapping or contacts a provider.
"""

import argparse
import hashlib
import json
import sqlite3
import sys
import tarfile
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import prepare_d6 as retained
import reconcile_tcgcsv_identity as prior

from pokemon_hunter.beta import catalog_variants, reference_inventory
from pokemon_hunter.beta import price_snapshot_contract as rules
from pokemon_hunter.inventory import stable_id
from pokemon_hunter.migration import encode

REPO = Path(__file__).resolve().parents[1]


def disposition(identity, provenance, english):
    """A literal special finish is represented, not invented or labelled N/A."""
    evidence = provenance.get("variant_evidence")
    if evidence:
        physical = evidence["descriptor"]
        if evidence["source_descriptor"] not in english:
            raise ValueError("Published descriptor lacks retained corroboration")
        edition, finish, variant = catalog_variants.physical(physical)
        if (identity["edition"], identity["finish"], identity["variant"]) != (edition, finish, variant):
            raise ValueError("Published physical identity changed")
        if edition is None:
            return "external_edition_metadata", physical
        if finish is None and physical.get("foil"):
            return "locally_resolved_structured_finish", physical
        return "already_resolved", physical
    if len(english) > 1:
        return "ambiguous_numbered_parent", None
    return "external_physical_metadata", None


def audit(root, manifest_path):
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    if len(manifest["rows"]) != 60 or len({r["printing_id"] for r in manifest["rows"]}) != 60:
        raise ValueError("Frozen 60-entry denominator required")
    archive = REPO / "evidence/d6-20261005/raw/tcgdex-archive.raw"
    with archive.open("rb") as f:
        if hashlib.file_digest(f, "sha256").hexdigest() != prior.ARCHIVE_SHA256:
            raise ValueError("Retained archive changed")
    old_manifest = json.loads((REPO / "config/catalog-imports/staging-ten/source-manifest.json").read_text())
    with reference_inventory.bounded():
        entries = reference_inventory.catalog_metadata(root)
    rows = []
    with (
        sqlite3.connect((root / "inventory.db").as_uri() + "?mode=ro", uri=True) as db,
        tarfile.open(archive) as tar,
    ):
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA query_only=ON")
        db.execute("BEGIN")
        publications = [
            dict(r) for r in db.execute("SELECT id,package,package_hash,set_id,state FROM catalog_imports")
        ]
        for publication in publications:
            publication["package"] = json.loads(publication["package"])
        members = {m.name.split("/", 1)[-1]: m for m in tar.getmembers() if m.isfile()}
        for frozen in manifest["rows"]:
            entry = entries[frozen["printing_id"]]
            identity = {k: entry.get(k) for k in rules.IDENTITY}
            if identity != frozen["identity"] or entry["name"] != frozen["name"]:
                raise ValueError("Frozen pilot changed")
            provenance = json.loads(entry["provenance"])
            matches = [
                p
                for p in publications
                if p["set_id"] == identity["set_id"]
                and p["state"] == "published"
                and p["package"]["version"] == provenance["source_version"]
                and p["package"]["source_sha256"] == provenance["source_sha256"]
            ]
            if len(matches) != 1:
                raise ValueError("Unique surviving catalog publication required")
            publication = matches[0]
            prior.verify_publication(publication, old_manifest)
            member = f"data/Base/{frozen['set_name']}/{identity['collector_number']}.ts"
            raw = tar.extractfile(members[member]).read()
            member_sha = hashlib.sha256(raw).hexdigest()
            source = retained.parse(raw.decode())
            if source["name"]["en"] != entry["name"]:
                raise ValueError("Source name mismatch")
            english, excluded = retained.english_variants(source.get("variants", []))
            if excluded or not english:
                raise ValueError("Unreviewed source language/variant inventory")
            ve = provenance.get("variant_evidence")
            if ve and (
                ve["member"] != member or ve["member_sha256"] != member_sha or ve["revision"] != prior.PIN
            ):
                raise ValueError("Physical member evidence mismatch")
            status, physical = disposition(identity, provenance, english)
            candidates = []
            parent_id = ve["parent_id"] if ve else frozen["printing_id"]
            parent = dict(db.execute("SELECT * FROM printings WHERE id=?", (parent_id,)).fetchone())
            parent_sha = hashlib.sha256(encode(parent).encode()).hexdigest()
            for literal in english:
                descriptor = {k: v for k, v in literal.items() if k != "thirdParty"}
                candidate = dict(
                    descriptor=descriptor, source_product_id=literal.get("thirdParty", {}).get("tcgplayer")
                )
                try:
                    ed, finish, variant = catalog_variants.physical(descriptor)
                except ValueError:
                    candidate.update(
                        authority="existing_closed_catalog_grammar_requires_review", proposed_printing_id=None
                    )
                else:
                    same = db.execute(
                        "SELECT id FROM printings WHERE set_id=? AND collector_number=? AND language=? AND edition IS ? AND finish IS ? AND variant IS ?",
                        (identity["set_id"], identity["collector_number"], "en", ed, finish, variant),
                    ).fetchall()
                    if len(same) > 1:
                        raise ValueError("Duplicate physical identity")
                    external = parent_id + ":" + hashlib.sha256(encode(descriptor).encode()).hexdigest()
                    candidate.update(
                        authority="existing_physical_child" if same else "catalog_variants_additive_review",
                        proposed_printing_id=same[0][0]
                        if same
                        else stable_id("catalog-printing", catalog_variants.PROVIDER + ":en:" + external),
                    )
                candidates.append(candidate)
            common = {v["type"] for v in english if not v.get("foil")}
            proposed_fields = {}
            if (
                not physical
                and not identity["finish"]
                and len(common) == 1
                and all(not v.get("foil") for v in english)
            ):
                proposed_fields["finish"] = next(iter(common))
            product = ve["source_descriptor"].get("thirdParty", {}).get("tcgplayer") if ve else None
            ordinary = status == "already_resolved" and set(physical) <= {"type", "stamp", "languages"}
            mapping = (
                dict(
                    group_id={"Base Set": 604, "Fossil": 630, "Jungle": 635}[frozen["set_name"]],
                    product_id=product,
                    subtype=("1st Edition Holofoil" if identity["finish"] == "holo" else "1st Edition")
                    if ordinary
                    else None,
                    admission="candidate_only_requires_current_product_subtype_review",
                )
                if ordinary
                else None
            )
            rows.append(
                dict(
                    **frozen,
                    audit_status=status,
                    structured_identity=physical,
                    common_field_proposal=proposed_fields,
                    exact_mapping_proposal=mapping,
                    alternatives=candidates,
                    parent_id=parent_id,
                    parent_sha256=parent_sha,
                    publication_id=publication["id"],
                    publication_sha256=publication["package_hash"],
                    source_evidence=dict(
                        revision=prior.PIN,
                        archive_sha256=prior.ARCHIVE_SHA256,
                        member=member,
                        member_sha256=member_sha,
                        source_url="https://github.com/tcgdex/cards-database/blob/"
                        + prior.PIN
                        + "/"
                        + member,
                    ),
                    edition_not_applicable=False,
                    language_status="explicit_English",
                    notes="Parent is preserved; alternatives are not replacements or ownership assignments. No absent stamp implies unlimited.",
                )
            )
    counts = Counter(r["audit_status"] for r in rows)
    return dict(
        schema="dex-lv02-identity-audit-v1",
        manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
        counts=dict(counts),
        denominator=60,
        selected_sets=manifest["denominators"],
        rows=rows,
        common_finish_proposals=sum(bool(r["common_field_proposal"]) for r in rows),
        newly_resolved_descriptor_count=counts["locally_resolved_structured_finish"],
        source_eligible_new_mappings=0,
        provider_operations=0,
        customer_writes=0,
        authority="catalog publication and retained metadata, never price admission",
    )


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--manifest", type=Path, required=True)
    args = p.parse_args()
    print(json.dumps(audit(args.root.absolute(), args.manifest), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
