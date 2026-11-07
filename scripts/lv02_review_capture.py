"""Offline LV-02 evidence review; no transport, catalog mutation or admission.

Reuse the existing two identity reviewers and contract grammar. Report only
non-price decisions; temporary arithmetic stays in the one managed capture tree.
Unknown monetary semantics must keep the proposed v2 contract inadmissible.
"""

import argparse
import hashlib
import json
import os
import sys
import tarfile
import time
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from pokemon_hunter.beta import catalog_variants, market_identity, reference_inventory, tcgcsv_offline
from pokemon_hunter.beta import price_snapshot_contract as rules
from scripts import audit_tcgcsv_batch as independent
from scripts import prepare_d6 as retained
from scripts import prepare_tcgcsv_offline as managed
from scripts import reconcile_tcgcsv_identity as lineage
from scripts import review_tcgcsv_batch as reviewer

REPO = Path(__file__).resolve().parents[1]
SETS = {"Base Set": (604, 102, "base_set"), "Fossil": (630, 62, "fossil"), "Jungle": (635, 64, "jungle")}


def exact_candidate(entry, english):
    """Availability at one source never completes an unspecified parent."""
    if not all(entry.get(k) for k in rules.IDENTITY):
        return None, "unresolved_catalog_identity"
    provenance = json.loads(entry["provenance"])
    evidence = provenance.get("variant_evidence")
    if not evidence or evidence["source_descriptor"] not in english:
        return None, "missing_literal_physical_evidence"
    descriptor = evidence["descriptor"]
    if set(descriptor) - {"type", "stamp"}:
        return None, "unsupported_special_variant"
    ed, finish, variant = catalog_variants.physical(descriptor)
    if (ed, finish, variant) != (entry["edition"], entry["finish"], entry["variant"]):
        raise ValueError("Frozen physical identity conflict")
    product = evidence["source_descriptor"].get("thirdParty", {}).get("tcgplayer")
    subtypes = [s for s, pair in market_identity.SUBTYPES.items() if pair == (ed, finish)]
    if (product is not None and type(product) is not int) or len(subtypes) != 1:
        return None, "literal_source_product_or_subtype_unresolved"
    return (product, subtypes[0]), None


def basket_review(baskets, frozen_rows, values):
    """Compute native guide subtotals, never claim unknown-basis item values."""
    by_pilot = {r["pilot_id"]: r["printing_id"] for r in frozen_rows}
    public, temporary = [], []
    for basket in baskets:
        components = [
            (r["pilot_id"], r["quantity"], values.get(by_pilot[r["pilot_id"]])) for r in basket["contents"]
        ]
        available = [(pid, q, v) for pid, q, v in components if v is not None]
        quantity = sum(q for _, q, _ in available)
        subtotal = sum((q * v for _, q, v in available), Decimal(0)) if available else None
        # Check independent expanded-unit summation without changing the basket.
        if subtotal is not None:
            assert subtotal == sum((v for _, q, v in available for _ in range(q)), Decimal(0))
        public.append(
            dict(
                basket_id=basket["basket_id"],
                stated_quantity=basket["stated_quantity"],
                source_guide_supported_lines=len(available),
                source_guide_supported_quantity=quantity,
                eligible_item_value_quantity=0,
                eligible_item_total=None,
                source_native_arithmetic_evaluated=bool(available),
                source_native_scope=(
                    "complete_source_native_sum"
                    if quantity == basket["stated_quantity"]
                    else "partial_subtotal"
                    if available
                    else "unavailable"
                ),
                excluded_pilot_ids=[pid for pid, q, v in components if v is None],
                blocker="item_excluding_shipping_tax_not_established; no admission or activation",
            )
        )
        temporary.append(
            dict(
                basket_id=basket["basket_id"],
                source_native_subtotal=str(subtotal) if subtotal is not None else None,
                normalized_item_total=None,
                condition=None,
                amount_basis="unknown_shipping_and_tax",
                monetary_concentration=(
                    str(max(q * v for _, q, v in available) / subtotal) if subtotal else None
                ),
            )
        )
    return public, temporary


def review(root, receipt_path, pilot_path):
    receipt = json.loads(receipt_path.read_bytes())
    if receipt["status"] != "captured" or receipt["provider_operations"] != 8:
        raise ValueError("Completed approved eight-attempt stage required")
    directory = root / receipt["capture_directory"]
    for f in receipt["files"]:
        p = managed._managed_input(root, directory / f["filename"])
        if p.stat().st_size != f["bytes"]:
            raise ValueError("Retained capture size changed")
    if (directory / "build-before.txt").read_bytes() != (directory / "build-after.txt").read_bytes():
        raise ValueError("Publication changed")
    with reference_inventory.bounded():
        entries = reference_inventory.catalog_metadata(root)
    selected = {pid: p for pid, p in entries.items() if p["set_name"] in SETS}
    if len(selected) != 307:
        raise ValueError("Frozen selected-set denominator changed")
    pilot = json.loads(pilot_path.read_bytes())
    old_audit = json.loads((REPO / "reports/lv-02-prerequisites-20261104/identity-audit.json").read_bytes())
    if old_audit["manifest_sha256"] != hashlib.sha256(pilot_path.read_bytes()).hexdigest():
        raise ValueError("Frozen pilot changed")
    for row in pilot["rows"]:
        if row["identity"] != {k: entries[row["printing_id"]].get(k) for k in rules.IDENTITY}:
            raise ValueError("Frozen identity changed")
    group_evidence = {}
    for name, (gid, count, key) in SETS.items():
        package = json.loads((REPO / f"config/catalog-imports/staging-ten/{key}.json").read_bytes())
        if package["language"] != "en" or package["expected_count"] != count:
            raise ValueError("English numbered-set evidence changed")
        group_evidence[str(gid)] = dict(
            category_id=3,
            literal_name=name,
            language="en",
            denominators={"": [str(count)]},
            language_evidence=[
                dict(source_url=package["source_url"], source_sha256=package["source_sha256"])
            ],
        )
    shards = [
        dict(group_id=gid, products=f"groups/{gid}/products.json", prices=f"groups/{gid}/prices.json")
        for gid, _, _ in SETS.values()
    ]
    products, prices, conflicts, totals = tcgcsv_offline._inputs(
        dict(shards=shards), directory, tcgcsv_offline.Limits(), time.monotonic()
    )
    other_products, other_prices = independent.load_sources(directory, [g for g, _, _ in SETS.values()])
    assignments = {pid: SETS[p["set_name"]][0] for pid, p in selected.items()}
    all_decisions, _ = reviewer.choose(entries, assignments, group_evidence, products, prices, conflicts)
    by_pid = {d["printing_id"]: d for d in all_decisions}
    archive = REPO / "evidence/d6-20261005/raw/tcgdex-archive.raw"
    with archive.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != lineage.ARCHIVE_SHA256:
            raise ValueError("Retained physical archive changed")
    exact, hold = {}, {}
    with tarfile.open(archive) as tar:
        members = {m.name.split("/", 1)[-1]: m for m in tar.getmembers() if m.isfile()}
        for pid, p in selected.items():
            member = f"data/Base/{p['set_name']}/{p['collector_number']}.ts"
            raw = tar.extractfile(members[member]).read()
            english, excluded = retained.english_variants(retained.parse(raw.decode()).get("variants", []))
            if excluded:
                raise ValueError("Unknown physical language inventory")
            ve = json.loads(p["provenance"]).get("variant_evidence")
            if ve and (
                ve["member"] != member
                or ve["member_sha256"] != hashlib.sha256(raw).hexdigest()
                or ve["archive_sha256"] != lineage.ARCHIVE_SHA256
            ):
                raise ValueError("Physical evidence changed")
            candidate, reason = exact_candidate(p, english)
            if candidate is None:
                hold[pid] = reason
                continue
            product_id, subtype = candidate
            gid = assignments[pid]
            # A missing vendor cross-reference is metadata, not an invented
            # physical distinction. Existing literal name/number/English-scope
            # review can establish it; the independent reviewer must agree.
            if product_id is None:
                proposed = by_pid[pid]["selected_binding"]
                if not proposed or proposed["sub_type_name"] != subtype:
                    hold[pid] = "literal_source_product_unresolved"
                    continue
                product_id = proposed["product_id"]
            rows = products.get((gid, product_id), [])
            if len(rows) != 1:
                hold[pid] = "retained_exact_product_not_returned"
                continue
            exact[pid] = dict(
                group_id=gid, product_id=product_id, sub_type_name=subtype, source_url=rows[0].get("url")
            )
    decisions, bindings = reviewer.choose(
        entries,
        {pid: assignments[pid] for pid in exact},
        group_evidence,
        products,
        prices,
        conflicts,
        exact_bindings=exact,
    )
    second, _ = independent.rederive(
        entries,
        {pid: assignments[pid] for pid in exact},
        group_evidence,
        other_products,
        other_prices,
        exact_bindings=exact,
    )
    if {b["printing_id"]: b for b in bindings} != second:
        raise ValueError("Independent identity reviewers disagree")
    matched = {b["printing_id"]: b for b in bindings}
    for d in decisions:
        if d["printing_id"] not in matched:
            hold[d["printing_id"]] = d["decision"]
    values = {}
    for pid, b in matched.items():
        row = prices[(b["group_id"], (b["product_id"], b["sub_type_name"]))][0]
        value = row.get("marketPrice")
        if (
            isinstance(value, (Decimal, int))
            and not isinstance(value, bool)
            and Decimal(value).is_finite()
            and Decimal(value) > 0
        ):
            rules.shopping_math.amount(str(value))
            values[pid] = Decimal(value)
        else:
            hold[pid] = "missing_or_invalid_market_price"
    source_counts = []
    for name, (gid, _, _) in SETS.items():
        rows = [r[0] for (g, _), r in prices.items() if g == gid]
        source_counts.append(
            dict(
                set_name=name,
                group_id=gid,
                product_rows=sum(g == gid for g, _ in products),
                price_rows=len(rows),
                positive_market_rows=sum(
                    isinstance(r.get("marketPrice"), (Decimal, int)) and r["marketPrice"] > 0 for r in rows
                ),
                null_market_rows=sum(r.get("marketPrice") is None for r in rows),
            )
        )
    reviewed = []
    for pid, p in sorted(selected.items()):
        candidates = by_pid[pid]["candidates"]
        # Source availability at numbered-card level is explicitly weaker than a physical match.
        numbered_rows = [
            r[0]
            for (g, (product_id, _)), r in prices.items()
            if g == assignments[pid] and product_id in {c["product_id"] for c in candidates}
        ]
        available = any(
            isinstance(r.get("marketPrice"), (Decimal, int)) and r["marketPrice"] > 0 for r in numbered_rows
        )
        number_products = []
        for (gid, product_id), source_rows in products.items():
            if gid != assignments[pid]:
                continue
            numbers = [f["value"] for f in source_rows[0]["extendedData"] if f["name"] == "Number"]
            if numbers and reviewer.collector_relation(
                p["collector_number"], numbers[0], group_evidence[str(gid)]
            ):
                number_products.append(product_id)
        number_available = any(
            isinstance(r[0].get("marketPrice"), (Decimal, int)) and r[0]["marketPrice"] > 0
            for (g, (product_id, _)), r in prices.items()
            if g == assignments[pid] and product_id in number_products
        )
        reviewed.append(
            dict(
                printing_id=pid,
                set_name=p["set_name"],
                name=p["name"],
                collector_number=p["collector_number"],
                number_only_counterpart_product_ids=number_products,
                number_only_counterpart_has_price=number_available,
                name_match_gap=bool(number_products) and not candidates,
                numbered_candidate_count=len(candidates),
                numbered_candidate_has_price=available,
                exact_physical_mapping=matched.get(pid),
                positive_exact_market_price=pid in values,
                identity_or_price_hold=hold.get(pid),
                valuation_hold="amount_basis_unverified",
                active_guide=False,
                active_sold=False,
                candidates=candidates,
            )
        )
    lookup = {r["printing_id"]: r for r in reviewed}
    pilot_rows = [dict(pilot_id=p["pilot_id"], **lookup[p["printing_id"]]) for p in pilot["rows"]]
    baskets, temporary = basket_review(pilot["authored_engineering_baskets"], pilot["rows"], values)
    summaries = []
    for name in SETS:
        rows = [r for r in reviewed if r["set_name"] == name]
        pr = [r for r in pilot_rows if r["set_name"] == name]
        summaries.append(
            dict(
                set_name=name,
                catalog_denominator=len(rows),
                pilot_denominator=len(pr),
                numbered_candidate_price_available=sum(r["numbered_candidate_has_price"] for r in rows),
                number_only_counterpart_price_available=sum(
                    r["number_only_counterpart_has_price"] for r in rows
                ),
                name_match_gaps=sum(r["name_match_gap"] for r in rows),
                exact_physical_matches=sum(r["exact_physical_mapping"] is not None for r in rows),
                exact_positive_guide_candidates=sum(r["positive_exact_market_price"] for r in rows),
                pilot_numbered_candidate_price_available=sum(r["numbered_candidate_has_price"] for r in pr),
                pilot_number_only_counterpart_price_available=sum(
                    r["number_only_counterpart_has_price"] for r in pr
                ),
                pilot_exact_positive_guide_candidates=sum(r["positive_exact_market_price"] for r in pr),
                eligible_guides=0,
                eligible_sold=0,
            )
        )
    scope = dict(
        capture_purpose="refresh",
        catalog_identity_sha256=rules.digest(entries),
        group_evidence=group_evidence,
        owner_scope="lv02-proof-only-no-activation",
    )
    policy = reviewer.contract_for(
        entries,
        decisions,
        bindings,
        rules.timestamp(receipt["publisher_built_at"]),
        "lv02-guide-proof-20261105-v1",
        scope,
    )
    policy.update(
        schema="dex-price-contract-v2",
        policy_version="public-documents-reviewed-2026-11-05; owner-lv02-bounded-proof",
        scope="Only the listed exact English raw physical mappings, condition-mixed guide; temporary private LV-02 review, no production admission or activation",
        deletion_policy="Completion or withdrawal or seven days after stage one, whichever is first; remove raw values and derivatives; keep only permitted noncontent evidence",
        acquisition_policy="The one approved 2+8 attempt capture is consumed; no retry, recurrence, renewal or fallback",
        valuation=dict(
            basis="guide",
            condition=None,
            amount_basis="unresolved_shipping_and_tax",
            ceiling_applicable=False,
            qualification="pending",
            qualification_review="Exact identity reviewed independently; monetary normalization unresolved in primary documentation",
            estimator=None,
            sale_origins=[],
        ),
    )
    try:
        rules.contract(policy)
    except ValueError as error:
        rejection = str(error)
    else:
        raise ValueError("An unresolved monetary contract must fail admission validation")
    report = dict(
        schema="dex-lv02-live-proof-review-v1",
        publisher_built_at=receipt["publisher_built_at"],
        reviewed_at=datetime.now(timezone.utc).isoformat(),
        captured_product_rows=receipt["product_rows"],
        captured_price_rows=receipt["price_rows"],
        source_counts=source_counts,
        selected_sets=summaries,
        pilot_denominator=60,
        selected_set_denominator=307,
        pilot=pilot_rows,
        selected_set_decisions=reviewed,
        baskets=baskets,
        independent_mapping_agreement=True,
        contract_draft_rejection=rejection,
        contract_mapping_count=len(bindings),
        source_semantics=dict(
            basis="provider_guide",
            individual_sales=False,
            currency="USD",
            condition=None,
            publisher_date=receipt["publisher_built_at"],
            valuation_date=None,
            sale_dates=None,
            shipping_basis="unverified",
            tax_basis="unverified",
        ),
        exact_mapping_count=len(bindings),
        positive_exact_guide_candidates=len(values),
        eligible_active_guides=0,
        eligible_active_sold=0,
        provider_operations=0,
        customer_catalog_or_admission_writes=0,
        production_route="not_qualified",
        monetary_values_in_report=False,
    )
    draft = dict(
        schema="dex-lv02-guide-contract-draft-v1",
        admissible=False,
        admitted=False,
        activated=False,
        validation_rejection=rejection,
        unresolved_fields=["valuation.amount_basis", "valuation.qualification"],
        contract=policy,
        limitations=[
            "Current source monetary basis must be established before a valid v2 body can be produced",
            "Owner approval covered evidence capture and temporary review only",
        ],
    )
    return report, draft, temporary, directory


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--pilot", type=Path, required=True)
    parser.add_argument("--report-directory", type=Path, required=True)
    args = parser.parse_args()
    report, draft, temporary, directory = review(args.root.absolute(), args.receipt, args.pilot)
    for name, value in [("proof-review.json", report), ("guide-contract-draft.json", draft)]:
        p = args.report_directory / name
        with p.open("x") as f:
            json.dump(value, f, indent=2, sort_keys=True)
            f.write("\n")
    # Sole temporary numeric result is beside its managed capture inputs; no exports/logs.
    path = directory / "lv02-private-basket-review.json"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(temporary, f, indent=2)
        f.write("\n")
    print(
        json.dumps(
            dict(
                source_counts=report["source_counts"],
                selected_sets=report["selected_sets"],
                baskets=report["baskets"],
                contract_mapping_count=report["contract_mapping_count"],
                contract_admissible=False,
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
