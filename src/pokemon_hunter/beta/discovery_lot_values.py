"""Ephemeral ungraded lot projections from already received seller text.

No detail/photo acquisition, guessed quantities, persistent results or scope-based
contents substitution. The caller owns account, revision and original run leases.
"""

import json
from datetime import datetime, timezone
from decimal import Decimal

from . import (
    hunter_catalog,
    hunter_lot_parser,
    hunter_lots,
    listing_prices,
    lot_calculator,
    lot_guides,
    lot_hunt_contract,
    lot_recommendations,
    shopping_index,
    species_scope,
)
from .read_diagnostics import phase


def project(actor, raws, rows, *, details=None, summaries=None, _checks=None):
    checks = _checks if _checks is not None else []
    details, summaries = details or {}, summaries or {}
    indexed = shopping_index.current(actor)
    # Each seller keeps its own narrowed family inventory and catalog order.
    # Unioning inventories before parsing makes evidence depend on the other lot
    # in the batch, so an expanded single-offer read can have a different hash.
    catalogs = (
        {
            raw["itemId"]: indexed.proposals(
                hunter_lot_parser.catalog_text(summaries.get(raw["itemId"], raw), details.get(raw["itemId"]))
            )
            for raw in raws
        }
        if indexed
        else {}
    )
    fallback = None if indexed else hunter_lots._catalog(actor)
    entries = (
        list({p["id"]: p for group in catalogs.values() for p in group}.values()) if indexed else fallback
    )
    # The literal catalog match includes every candidate in each proposed family.
    # Unrelated source ranges cannot contribute to these seller contents.
    with lot_calculator.price_snapshots.selected(p["id"] for p in entries):
        records = lot_calculator.retained_records()
    sources = {raw.get("itemId"): raw for raw in raws}
    release_dates = indexed.release_dates() if indexed else species_scope.release_dates()
    for row in rows:
        raw = sources[row["item_id"]]
        entries = catalogs[raw["itemId"]] if indexed else fallback
        index = hunter_catalog.IdentityIndex(entries)
        unavailable = dict(
            native_guides=[],
            assessment_version="dex-lot-value-v3",
            basis=None,
            basis_label=None,
            gaps=["No exactly selected physical contents have compatible normalized references"],
            benchmark_costs=listing_prices.benchmark_costs(raw),
            normalized_priced_quantity=0,
            native_priced_quantity=0,
            alternatives=[],
            subtotal=None,
            total=None,
            priced_quantity=0,
            identified_quantity=0,
            parent_identified_quantity=0,
            stated_quantity=None,
            references=[],
            cards=[],
            identified_unpriced_quantity=0,
            unidentified_quantity=None,
            physically_selected_quantity=0,
            contents_state="unavailable",
            contents=[],
            quantity_issues=[],
            bid_difference=None,
            buy_now_difference=None,
            reason="Seller text does not identify enough card printings and quantities to value this lot.",
        )
        row["lot_value"] = unavailable
        try:
            with phase("composition_ms"):
                proposal = hunter_lot_parser.parse(
                    summaries.get(raw.get("itemId"), raw),
                    entries,
                    detail=details.get(raw.get("itemId")),
                    _index=index,
                )
            unavailable["identified_quantity"] = sum(p["included_quantity"] for p in proposal["proposals"])
            unavailable["parent_identified_quantity"] = proposal["parent_identified_quantity"]
            unavailable.update(
                stated_quantity=proposal.get("seller_stated_total"),
                physically_selected_quantity=proposal["physically_selected_quantity"],
                identified_unpriced_quantity=proposal["physically_selected_quantity"],
                unidentified_quantity=proposal["unidentified_quantity"],
                contents_state=proposal["contents_state"],
                contents=proposal["proposals"],
                quantity_issues=proposal["quantity_issues"],
                stock_quantity=proposal["stock_quantity"],
                lot_units=proposal["lot_units"],
                seller_lots_offered=proposal["seller_lots_offered"],
                excluded_claims=proposal["excluded_claims"],
                unresolved_contents=proposal["unresolved_contents"],
                evidence_basis=proposal["evidence_basis"],
                source_fields=proposal["source_fields"],
                aspect_names=proposal["aspect_names"],
            )
            with phase("composition_ms"):
                unavailable["alternatives"] = lot_guides.family_alternatives(
                    proposal, entries, records, datetime.now(timezone.utc).date()
                )
            if not unavailable["identified_quantity"]:
                if proposal["proposals"]:
                    unavailable["reason"] = (
                        "Seller mentions match catalog candidates. Printing or quantity remains unresolved."
                    )
                elif proposal["unresolved_contents"]:
                    unavailable["reason"] = (
                        "The parser could not match the supplied item lines to the local catalog."
                    )
                elif proposal["excluded_claims"]:
                    unavailable["reason"] = proposal["excluded_claims"][0]["reason"]
                else:
                    unavailable["reason"] = (
                        "No individually identifiable card lines were found in the supplied seller fields."
                    )
                continue
            with phase("composition_ms"):
                _, assessment = hunter_lots._compare(
                    actor, raw, proposal, None, entries, records, _checks=checks
                )
        except ValueError as error:
            unavailable["reason"] = str(error)
            continue
        result = assessment["result"]
        subtotal, total = result["known_selected_subtotal"], result["full_lot_total"]
        names = {p["id"]: p for p in entries}
        row["lot_value"] = dict(
            unavailable,
            native_guides=assessment["native_guides"],
            assessment_version=assessment["assessment_version"],
            basis=assessment["basis"],
            basis_label=assessment["basis_label"],
            benchmark_costs=assessment["benchmark_costs"],
            gaps=assessment["gaps"],
            normalized_priced_quantity=assessment["normalized_priced_quantity"],
            native_priced_quantity=assessment["native_priced_quantity"],
            subtotal=subtotal,
            total=total,
            priced_quantity=assessment["priced_card_quantity"],
            identified_unpriced_quantity=assessment["unpriced_card_quantity"],
            references=assessment["references"],
            cards=[
                dict(
                    dict({"reference_subtotal": None}, **card),
                    name=names[card["printing_id"]]["name"],
                    set_name=names[card["printing_id"]]["set_name"],
                    collector_number=names[card["printing_id"]]["collector_number"],
                )
                for card in [*assessment["priced_cards"], *assessment["unpriced_matches"]]
            ],
            reason=(
                "Conditional on seller contents and reference condition; dated ungraded references."
                if total is not None
                else "Publisher guide covers the selected contents; shipping/tax basis and condition remain unknown."
                if any(g["complete"] for g in assessment["native_guides"])
                else "Selected physical cards have no applicable admitted references."
                if subtotal is None and not assessment["native_guides"]
                else "Partial contents/pricing only; this is not the whole-lot value."
            ),
        )
        for lane, key in (("auction", "bid_difference"), ("buy_it_now", "buy_now_difference")):
            row["lot_value"][key] = assessment["benchmark_costs"][lane]["difference"]
        row["lot_value"]["all_pre_2000"] = lot_recommendations.pre_2000_contents(
            row["lot_value"], names, release_dates
        )
    rank(rows, raws)
    refs = [
        ref
        for row in rows
        for ref in (
            *row["lot_value"]["references"],
            *(r for g in row["lot_value"]["native_guides"] for r in g["references"]),
            *(
                c["reference"]
                for line in row["lot_value"]["alternatives"]
                for c in line["alternatives"]
                if c["reference"]
            ),
        )
    ]
    check = lot_calculator.reference_guard(actor, records, refs)
    check()
    if _checks is not None:
        _checks.append(check)


def rank(rows, raws, *, now=None):
    """Ranks over this acquired batch, separately by offer lane and native cohort.

    Full, partial, unknown-cost and unpriced groups never compete. The combined
    view uses BIN when available, otherwise auction; it never takes the better of
    two prices. Native ranks compare only compatible publisher/date cohorts.
    """
    now = now or datetime.now(timezone.utc)
    sources = {r["itemId"]: r for r in raws}
    buckets = {}
    for row in rows:
        raw = sources[row["item_id"]]
        eligible = lot_hunt_contract.lanes(raw, now=now)
        value = row.get("lot_value", {})
        costs = value.get("benchmark_costs") or listing_prices.benchmark_costs(raw)
        row["value_order"] = dict(schema="dex-lot-order-v1", lanes={}, native=[], combined=None)
        for lane in eligible:
            cost = costs[lane]
            score = cost["difference"] if value.get("total") is not None else cost["subtotal_difference"]
            group = (
                "unpriced"
                if value.get("subtotal") is None
                else "unknown_cost"
                if cost["delivered_before_tax"] is None
                else "complete"
                if value.get("total") is not None
                else "partial"
            )
            dates = [r["as_of"] for r in value.get("references", [])]
            order = dict(
                group=group,
                score=score,
                priced_quantity=value.get("priced_quantity", 0),
                oldest_reference_date=min(dates, default=None),
                end_time=row.get("ends_at") if lane == "auction" else None,
                stable_identity=row["item_id"],
                rank=None,
                meaning="identified_subtotal_difference_not_whole_lot_score"
                if group == "partial"
                else "before_tax_reference_difference",
            )
            row["value_order"]["lanes"][lane] = order
            buckets.setdefault((lane, "normalized"), []).append(order)
            for native in value.get("native_guides", []):
                native_order = dict(
                    order,
                    group="complete" if native["complete"] else "partial",
                    score=native["total"] if native["complete"] else native["subtotal"],
                    priced_quantity=native["priced_quantity"],
                    oldest_reference_date=native["reference_date"],
                    cohort=native["cohort"],
                    lane=lane,
                    meaning="publisher_numbers_not_savings",
                )
                row["value_order"]["native"].append(native_order)
                buckets.setdefault((lane, native["cohort"]), []).append(native_order)
        row["value_order"]["combined"] = row["value_order"]["lanes"].get(
            "buy_it_now", row["value_order"]["lanes"].get("auction")
        )
    groups = {"complete": 0, "partial": 1, "unknown_cost": 2, "unpriced": 3}

    def key(order):
        # ISO calendar dates sort chronologically; negate their ordinal for newer first.
        from datetime import date

        return (
            groups[order["group"]],
            -Decimal(order["score"]) if order["score"] is not None else Decimal(0),
            -order["priced_quantity"],
            -date.fromisoformat(order["oldest_reference_date"]).toordinal()
            if order["oldest_reference_date"]
            else 0,
            order["end_time"] or "9999",
            order["stable_identity"],
        )

    for bucket in buckets.values():
        for position, order in enumerate(sorted(bucket, key=key), 1):
            order["rank"] = position
    # Deterministic combined order retains independent lane ranks as its audit trail.
    combined = [r["value_order"]["combined"] for r in rows if r["value_order"]["combined"]]
    for position, order in enumerate(sorted(combined, key=key), 1):
        order["combined_rank"] = position


def _dependencies(refs):
    """Deduplicate lifecycle checks. Full reference provenance is available on expansion."""
    dependencies = set()
    pending = list(refs)
    while pending:
        ref = pending.pop()
        dependency = tuple(ref.get(k) for k in ("snapshot_version", "source_contract", "expires_at"))
        if any(dependency):
            dependencies.add(dependency)
        pending.extend(ref.get("conflicts", ()))
    return [
        {k: v for k, v in zip(("snapshot_version", "source_contract", "expires_at"), dep, strict=True) if v}
        for dep in sorted(dependencies, key=lambda d: tuple(v or "" for v in d))
    ]


def compact(value):
    """Glance quantities, costs and values retain their original server semantics."""
    fields = (
        "assessment_version",
        "basis",
        "basis_label",
        "subtotal",
        "total",
        "priced_quantity",
        "identified_quantity",
        "physically_selected_quantity",
        "parent_identified_quantity",
        "normalized_priced_quantity",
        "native_priced_quantity",
        "identified_unpriced_quantity",
        "unidentified_quantity",
        "stated_quantity",
        "contents_state",
        "reason",
        "bid_difference",
        "buy_now_difference",
        "benchmark_costs",
    )
    dependencies = _dependencies(value["references"])
    dependency_ids = {tuple(sorted(ref.items())): i for i, ref in enumerate(dependencies)}
    quantities = {}
    for card in value["cards"]:
        if ref := card.get("reference"):
            group = tuple(dependency_ids[tuple(sorted(dep.items()))] for dep in _dependencies([ref]))
            quantities[group] = quantities.get(group, 0) + card["quantity"]
    return {
        **{key: value[key] for key in fields},
        "references": dependencies,
        "priced_coverage": [[quantity, ids] for ids, quantity in quantities.items()],
        "native_guides": [
            {
                **{
                    key: group[key]
                    for key in (
                        "cohort",
                        "provider",
                        "reference_date",
                        "date_basis",
                        "complete",
                        "total",
                        "subtotal",
                        "priced_quantity",
                    )
                },
                "references": _dependencies(group["references"]),
            }
            for group in value["native_guides"]
        ],
    }


def bound_list(result):
    """Fit the authenticated envelope, including worst-case quoted titles and repeated native cohorts."""
    limit = 120 * 1024
    if len(json.dumps(result, separators=(",", ":")).encode()) <= limit:
        return
    # Keep all offers and all financial fields. Factor repeated cohort and source
    # metadata out of unusually dense lists. The full labels stay in local evidence.
    dependencies, labels = {}, {}
    for row in result["results"]:
        # These legacy discovery placeholders carry no evidence on automatic Hunt rows.
        for key in (
            "save_reason",
            "identity_candidates",
            "proposed_identity",
            "comparison",
            "reference",
            "discovery_eligibility",
            "discovery_kind",
            "save_allowed",
            "revealed",
        ):
            row.pop(key, None)
        value = row.get("lot_value")
        if not value:
            continue
        ranks = {(r["cohort"], r["lane"]): r["rank"] for r in row["value_order"]["native"]}
        groups = []
        for g in value["native_guides"]:
            deps = []
            for ref in g["references"]:
                key = tuple(sorted(ref.items()))
                deps.append(dependencies.setdefault(key, len(dependencies)))
            label = g["provider"][:60]
            groups.append(
                [
                    g["cohort"],
                    labels.setdefault(label, len(labels)),
                    g["reference_date"],
                    g["date_basis"],
                    g["priced_quantity"],
                    g["subtotal"],
                    g["complete"],
                    deps,
                    ranks.get((g["cohort"], "auction")),
                    ranks.get((g["cohort"], "buy_it_now")),
                ]
            )
        value["native_guides"] = []
        row["value_order"]["native"] = []
        value["cohort_rows"] = groups
    result["cohort_sources"] = [dict(ref) for ref in dependencies]
    result["cohort_labels"] = list(labels)
    # Preserve seller thumbnails. Only unusually long titles are shortened if
    # metadata factoring still exceeds the actual compact JSON envelope.
    for maximum in (160, 60):
        if len(json.dumps(result, separators=(",", ":")).encode()) <= limit:
            return
        for row in result["results"]:
            row["title"] = row["title"][:maximum]
    if len(json.dumps(result, separators=(",", ":")).encode()) > limit:
        raise ValueError("Hunt summary exceeded the supported response limit")
