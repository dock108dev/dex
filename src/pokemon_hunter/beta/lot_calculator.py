"""Vintage lot scenarios and session-private wants; no inventory mutations or acquisition."""

import hashlib
import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path

from django.conf import settings

from pokemon_hunter.runtime_data import root as runtime_root

from . import collection, hunt_values, shopping, store
from . import shopping_math as math

SETS = (
    "Base Set",
    "Jungle",
    "Fossil",
    "Base Set 2",
    "Team Rocket",
    "Gym Heroes",
    "Gym Challenge",
    "Neo Genesis",
    "Neo Discovery",
    "Neo Revelation",
    "Neo Destiny",
)
COLUMNS = ("raw", "8", "9", "10")
# Admission is pinned to the existing approved guide bytes. New provider
# records, even unselected alternatives, cannot enter these immutable saves.
RETAINED_SHA256 = "2d3a0867906ac5f84464ee42b618583cd0cb88818f773522420aa230d899ee20"


def catalog(actor, query=""):
    store.verified(actor)
    games = {g["id"] for g in store.rows("SELECT id FROM games WHERE game_key='pokemon'")}
    return [p for p in collection.catalog(actor, query) if p["set_name"] in SETS and p["game_id"] in games]


def retained_records():
    """Freeze admission to existing guide bytes; synthetic sources require a disposable marker."""
    if (settings.ROOT / "SYNTHETIC_ONLY").is_file():
        rows, _ = shopping.sources()
        return rows
    path = runtime_root() / "config/market_values.json"
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != RETAINED_SHA256:
        return []
    return json.loads(path.read_text())


def cells(printing, records, today):
    key = json.loads(printing["provenance"]).get("legacy_id")
    result = {}
    for grade in COLUMNS:
        candidates = []
        for row in records:
            if not isinstance(row, dict) or row.get("card_id") != key or str(row.get("grade")) != grade:
                continue
            edition = printing.get("edition") or "standard"
            reason = "eligible"
            if row.get("edition") != edition or hunt_values._valid(row, today, guide=True) is None:
                reason = "edition_currency_source_date_or_amount_unavailable"
            elif grade != "raw" and (row.get("estimated") or not row.get("grader")):
                reason = "estimated_or_unknown_graded_basis"
            elif any(row.get(k) not in (None, printing.get(k)) for k in ("language", "finish", "variant")):
                reason = "conflicting_printing_identity"
            elif grade == "raw" and row.get("grader") not in {"Guide", "PSA"}:
                reason = "unsupported_raw_basis"
            # Generic grade fields retain the literal grader; no PSA8/9 mapping.
            ref = dict(
                reference_id="retained-" + shopping.digest(row),
                kind="guide",
                value_scope="per_card",
                amount=row.get("value"),
                currency=row.get("currency"),
                as_of=row.get("as_of"),
                source_url=row.get("source_url"),
                grade=grade,
                grader=row.get("grader"),
                estimated=row.get("estimated"),
                edition=row.get("edition"),
                raw_record=deepcopy(row),
                record_sha256=shopping.digest(row),
                printing_id=printing["id"],
                provenance="retained_guide_conditional",
                match_status="conditional" if reason == "eligible" else "unavailable",
                assumptions=[
                    "Catalog fit and physical condition are conditional; generic grader is not certification."
                ],
                admission="preexisting_retained_guide_boundary",
                basis_eligibility=reason,
            )
            ref["eligibility"] = math.eligibility(ref, today.isoformat())
            if ref["eligibility"] == "eligible":
                candidates.append(ref)
        result[grade] = max(candidates, key=lambda r: r["as_of"]) if candidates else None
    return result


def browse(actor, query=""):
    today = datetime.now(shopping.TZ).date()
    rows, copies = retained_records(), collection.copies(actor)
    return [
        dict(
            shopping.identity(p),
            copy_count=sum(c["printing_id"] == p["id"] for c in copies),
            cells=cells(p, rows, today),
        )
        for p in catalog(actor, query)
    ]


def locks(actor, session, supplied=None):
    """Reuse authenticated session storage; wants never enroll in frozen collection goals."""
    store.verified(actor)
    key = "shopping_wants_" + actor.user_id
    if supplied is not None:
        if not isinstance(supplied, list) or len(supplied) > 200:
            raise ValueError("At most 200 wanted identities")
        ids = {p["id"] for p in catalog(actor)} | {p["printing_id"] for p in session.get(key, [])}
        seen = set()
        for item in supplied:
            shopping.fields(item, {"printing_id", "quantity"}, {"printing_id", "quantity"})
            if item["printing_id"] not in ids or item["printing_id"] in seen:
                raise ValueError("Invalid or duplicate wanted printing")
            math.quantity(item["quantity"])
            seen.add(item["printing_id"])
        session[key] = deepcopy(supplied)
    # Preserve locks if metadata later disappears; expose gaps rather than remove wants.
    return session.get(key, [])


def prepare(actor, raw, now=None):
    store.verified(actor)
    shopping.fields(
        raw,
        {"cards", "listing_observation", "planned_bid", "delivery_cost_inputs"},
        {"cards", "listing_observation", "planned_bid", "delivery_cost_inputs"},
    )
    if not isinstance(raw["cards"], list) or len(raw["cards"]) > 200:
        raise ValueError("At most 200 card identities")
    now = now or datetime.now(shopping.TZ)
    today = now.astimezone(shopping.TZ).date()
    entries = {p["id"]: p for p in catalog(actor)}
    records, identities, by_column, seen = retained_records(), [], {g: [] for g in COLUMNS}, set()
    selections = []
    for line in raw["cards"]:
        shopping.fields(line, {"printing_id", "quantity", "values"}, {"printing_id", "quantity", "values"})
        p = entries.get(line["printing_id"])
        if p is None or p["id"] in seen:
            raise ValueError("Missing, non-vintage or duplicate printing")
        seen.add(p["id"])
        math.quantity(line["quantity"])
        shopping.fields(line["values"], COLUMNS, COLUMNS)
        guides = cells(p, records, today)
        identities.append(
            dict(printing_id=p["id"], quantity=line["quantity"], captured_identity=shopping.identity(p))
        )
        selection = dict(
            selection_id=p["id"],
            printing_id=p["id"],
            quantity=line["quantity"],
            assumptions="Independent value scenario; physical grade unverified",
            completion_confirmed=False,
        )
        selections.append(selection)
        for grade, value in line["values"].items():
            shopping.fields(value, {"mode", "amount", "date", "notes"}, {"mode"})
            if value["mode"] == "guide":
                ref = guides[grade]
                if ref is None:
                    raise ValueError("Guide changed or unavailable; review this cell")
                ref = dict(ref, reference_id=p["id"] + ":" + grade)
            elif value["mode"] == "manual":
                math.amount(value.get("amount"))
                if math.fresh(value.get("date"), today.isoformat()) != "eligible":
                    raise ValueError("Manual date is missing, future or stale")
                notes = shopping.text(value.get("notes", ""))
                ref = dict(
                    reference_id=p["id"] + ":" + grade,
                    kind="manual",
                    amount=value["amount"],
                    currency="USD",
                    as_of=value["date"],
                    value_scope="per_card",
                    grade=grade,
                    grader=None,
                    match_status="conditional",
                    provenance="manual_user_estimate",
                    assumptions=[
                        notes or "Independent manual scenario; identity and physical grade unverified"
                    ],
                    admission="independent_manual_entry",
                )
            elif value["mode"] == "none":
                ref = None
            else:
                raise ValueError("Select unavailable, retained guide or manual estimate")
            if ref:
                by_column[grade].append(ref)
    # Reuse the existing ingress contract for money, price kinds and unknown costs.
    validation = dict(
        selected_cards=[dict(s, chosen_value_reference=None) for s in selections],
        value_references=[],
        unknown_contents=dict(quantity=0),
        **{k: raw[k] for k in math.BASES},
        delivery_cost_inputs=raw["delivery_cost_inputs"],
    )
    shopping.validate_request(validation)
    scenarios = {}
    for grade in COLUMNS:
        refs = by_column[grade]
        ids = {r["reference_id"] for r in refs}
        context = dict(
            validation,
            evaluation_date=today.isoformat(),
            frozen_goal=None,
            value_references=refs,
            selected_cards=[
                dict(
                    s,
                    chosen_value_reference=s["printing_id"] + ":" + grade
                    if s["printing_id"] + ":" + grade in ids
                    else None,
                )
                for s in selections
            ],
        )
        scenarios[grade] = dict(references=refs, result=math.evaluate(context))
    return dict(
        schema="dex-lot-v2",
        request=deepcopy(raw),
        context=dict(
            account_id=actor.user_id,
            evaluation_date=today.isoformat(),
            timezone="America/New_York",
            cards=identities,
        ),
        scenarios=scenarios,
    )


def admitted_hashes():
    if (settings.ROOT / "SYNTHETIC_ONLY").is_file():
        return {shopping.digest(r) for r in retained_records()}
    return set(
        json.loads(Path(__file__).with_name("retained_guide_admission.json").read_text())["record_hashes"]
    )


def admit_snapshot(payload):
    """Every guide derivative/alternative inherits admission; never mutate old saves."""
    admitted = admitted_hashes()

    def visit(value):
        if isinstance(value, dict):
            if value.get("kind") == "guide" and "raw_record" in value:
                if shopping.digest(value["raw_record"]) not in admitted:
                    raise ValueError("New provider embedding requires surviving rights and admission")
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(payload)
