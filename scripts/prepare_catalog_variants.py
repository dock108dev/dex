"""Prepare the exact S4 variant cohort offline; never acquire or publish data."""

import argparse
import hashlib
import json
import socket
import sqlite3
import sys
import tarfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import prepare_d6 as retained  # noqa: E402
import reconcile_tcgcsv_identity as prior  # noqa: E402

from pokemon_hunter.beta import catalog_variants as variants  # noqa: E402
from pokemon_hunter.inventory import stable_id  # noqa: E402
from pokemon_hunter.migration import digest, encode  # noqa: E402

REPO = Path(__file__).resolve().parents[1]


def fingerprint(value):
    return digest(encode(value).encode())


def prepare(root):
    ledger_path = REPO / "reports/hunt-11-s4-20261017/decision-ledger.json"
    handoff_path = ledger_path.with_name("representation-handoff.json")
    ledger = json.loads(ledger_path.read_text())["decisions"]
    handoff = json.loads(handoff_path.read_text())
    if len(ledger) != 660 or len({r["printing_id"] for r in ledger}) != 660:
        raise ValueError("Exact frozen parent cohort required")
    archive = REPO / "evidence/d6-20261005/raw/tcgdex-archive.raw"
    with archive.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != prior.ARCHIVE_SHA256:
            raise ValueError("Retained archive changed")
    packages, parents, dispositions, targets = {}, [], [], []
    with (
        sqlite3.connect((root / "inventory.db").as_uri() + "?mode=ro", uri=True) as db,
        tarfile.open(archive) as tar,
    ):
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA query_only=ON")
        db.execute("BEGIN")
        members = {m.name.split("/", 1)[-1]: m for m in tar.getmembers() if m.isfile()}
        for decision in ledger:
            pid = decision["printing_id"]
            parent = dict(db.execute("SELECT * FROM printings WHERE id=?", (pid,)).fetchone())
            identity = decision["canonical_identity"]
            if (
                any(
                    parent[k] != identity[k]
                    for k in ("set_id", "collector_number", "language", "edition", "finish", "variant")
                )
                or json.loads(parent["attributes"])["name"] != identity["name"]
            ):
                raise ValueError("Frozen parent identity changed")
            evidence = decision["evidence"][-1]
            raw = tar.extractfile(members[evidence["member"]]).read()
            source = retained.parse(raw.decode())
            if digest(raw) != evidence["sha256"] or evidence["revision"] != prior.PIN:
                raise ValueError("Frozen member changed")
            english, excluded = retained.english_variants(source.get("variants", []))
            if english != evidence["english_variants"] or excluded:
                raise ValueError("Literal variant inventory changed")
            old = json.loads(
                db.execute(
                    "SELECT package FROM catalog_imports WHERE id=?",
                    (decision["evidence"][1]["publication_id"],),
                ).fetchone()[0]
            )
            sid = parent["set_id"]
            package = packages.setdefault(
                sid,
                dict(
                    schema_version=variants.SCHEMA,
                    game="pokemon",
                    set_id=sid,
                    set_key=old["set_key"],
                    set_name=identity["set_name"],
                    language="en",
                    provider=variants.PROVIDER,
                    version="hunt11-s5-99c994747cf7-v1",
                    source_url="https://github.com/tcgdex/cards-database/tree/" + prior.PIN,
                    source_sha256=prior.ARCHIVE_SHA256,
                    metadata_permission=old["metadata_permission"],
                    image_permission="not-included",
                    coverage="partial",
                    expected_count=0,
                    cards=[],
                ),
            )
            parents.append(
                dict(
                    printing_id=pid,
                    parent_sha256=fingerprint(parent),
                    set_id=sid,
                    identity=identity,
                    evidence=evidence,
                    descriptors=len(english),
                    status="preserved_unspecified_parent",
                    additional_evidence_requirement=(
                        "Literal per-card English physical variant evidence with relevant language, finish, stamp, foil, copyright, size and distribution; source product subtypes alone do not establish a combination"
                        if not english
                        else "A particular owned copy requires explicit owner identification; no automatic reassignment"
                    ),
                )
            )
            for offset, literal in enumerate(english):
                physical = {k: v for k, v in literal.items() if k != "thirdParty"}
                variants.descriptor(physical)
                card = dict(
                    parent_id=pid,
                    parent_sha256=fingerprint(parent),
                    descriptor=physical,
                    evidence=dict(
                        source_url=evidence["source_url"],
                        revision=prior.PIN,
                        archive_sha256=prior.ARCHIVE_SHA256,
                        member=evidence["member"],
                        member_sha256=evidence["sha256"],
                        lineage=evidence["lineage"],
                        source_identity=evidence["source_identity"],
                        source_descriptor=literal,
                        original_member_sha256=evidence["original_member_sha256"],
                    ),
                )
                package["cards"].append(card)
                edition, finish, variant = variants.physical(physical)
                external = pid + ":" + fingerprint(physical)
                child = stable_id("catalog-printing", variants.PROVIDER + ":en:" + external)
                # Reuse an existing exact identity, while leaving its original mappings intact.
                matches = db.execute(
                    "SELECT id FROM printings WHERE set_id=? AND collector_number=? AND language=? "
                    "AND edition IS ? AND finish IS ? AND variant IS ?",
                    (sid, parent["collector_number"], "en", edition, finish, variant),
                ).fetchall()
                if len(matches) > 1:
                    raise ValueError("Duplicate existing variant requires reconciliation")
                child = matches[0][0] if matches else child
                subtype = (
                    ("1st Edition Holofoil" if finish == "holo" else "1st Edition")
                    if edition == "first_edition" and set(physical) <= {"type", "stamp", "languages"}
                    else None
                )
                candidate = decision["source_candidate"]
                product = literal.get("thirdParty", {}).get("tcgplayer")
                ready = bool(
                    subtype
                    and subtype in candidate["supported_subtypes"]
                    and product == candidate["product_id"]
                )
                row = dict(
                    parent_id=pid,
                    descriptor_index=offset,
                    literal_descriptor=literal,
                    physical_descriptor=physical,
                    printing_id=child,
                    disposition="existing_identity" if matches else "new_identity",
                    variant_label=variants.label(physical),
                    price_ready=ready,
                    reason="Exact first-edition stamp and ordinary finish"
                    if ready
                    else "Unknown edition or special physical attributes lack a unique compatible source subtype",
                )
                dispositions.append(row)
                if ready:
                    targets.append(
                        dict(
                            printing_id=child,
                            parent_id=pid,
                            group_id=decision["source_group_id"],
                            product_id=product,
                            subtype=subtype,
                            source_url=candidate["source_url"],
                            source_identity=evidence["source_identity"],
                            descriptor=physical,
                            identity=dict(
                                set_id=sid,
                                collector_number=parent["collector_number"],
                                language="en",
                                edition=edition,
                                finish=finish,
                                variant=variant,
                                catalog_version=decision["canonical_catalog_version"],
                            ),
                        )
                    )
    packages = {
        sid: dict(
            p,
            cards=sorted(p["cards"], key=lambda c: (c["parent_id"], encode(c["descriptor"]))),
            expected_count=len(p["cards"]),
        )
        for sid, p in packages.items()
        if p["cards"]
    }
    for p in packages.values():
        variants.validate(p)
    if (len(parents), len(dispositions), len(targets)) != (660, 617, 300):
        raise ValueError("Frozen descriptor or mapping counts changed")
    # Enforce pinned identity lists independently; counts alone cannot prove scope.
    for key, count in (
        ("numbered_identity_spans_multiple_variants", 305),
        ("source_variant_detail_absent", 355),
    ):
        expected = {r["printing_id"] for r in handoff["cohorts"][key]}
        actual = {r["printing_id"] for r in ledger if r["root_cause"] == key}
        if len(expected) != count or actual != expected:
            raise ValueError("Exact representation handoff cohort changed")
    groups = sorted({t["group_id"] for t in targets})
    refresh = dict(
        schema="dex-hunt11-s5-ready-refresh-v1",
        execution_selected=False,
        provider_operations=0,
        mode="refresh",
        target_count=len(targets),
        targets=sorted(targets, key=lambda t: t["printing_id"]),
        groups=groups,
        request_ceiling=2 * len(groups) + 2,
        request_breakdown=dict(
            products=len(groups), prices=len(groups), publisher_build_checks=2, metadata=0
        ),
        requirements=[
            "Explicit later finite capture selection; this handoff executes zero operations",
            "All 63 consumed scopes and history survive; ordinary refresh, never initial_fill replay",
            "Per-group not_before and daily pacing; strictly newer equal before/after publisher build",
            "Finite body/row/storage bounds, independent Stop, no retries, exact mapping review and source admission",
            "No parent prices, sibling values or reconstructed deleted raw data",
        ],
    )
    return packages, dict(schema="dex-hunt11-s5-parents-v1", parents=parents), dispositions, refresh


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    socket.socket.connect = prior.no_network
    socket.create_connection = prior.no_network
    packages, parents, dispositions, refresh = prepare(args.root.resolve())
    args.output.mkdir(parents=True, exist_ok=False)
    outputs = dict(
        **{"parent-inventory": parents, "descriptor-dispositions": dispositions, "refresh-handoff": refresh},
        **{"package-" + sid: p for sid, p in packages.items()},
    )
    for name, value in outputs.items():
        (args.output / (name + ".json")).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            dict(
                parents=len(parents["parents"]),
                descriptors=len(dispositions),
                packages=len(packages),
                ready_targets=refresh["target_count"],
                provider_operations=0,
            )
        )
    )


if __name__ == "__main__":
    main()
