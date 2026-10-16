"""Vintage lot scenarios and session-private wants; no inventory mutations or acquisition."""

import hashlib
import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path

from django.conf import settings

from pokemon_hunter.runtime_data import root as runtime_root

from . import canonical_species, collection, effective_collection, price_snapshots, shopping, store
from . import price_snapshot_contract as snapshot_rules
from . import shopping_math as math
from .lot_guides import cell_details as cell_details
from .lot_guides import cells as cells
from .lot_guides import legacy_cells as legacy_cells

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
COLUMNS = snapshot_rules.COLUMNS
# Historical admission remains pinned. Versioned observations have their own
# independently reviewed private contract and permanent-save policy.
RETAINED_SHA256 = "2d3a0867906ac5f84464ee42b618583cd0cb88818f773522420aa230d899ee20"
PRIVATE_RETAINED_SHA256 = "72d61c466c74b8a702cee9fd744a5485633c236c0dcbfaa07c26a3fafac27b03"


def current_species_printing(printing):
    attributes = printing["attributes"]
    number = attributes.get("pokemon_dex")
    return attributes.get("supertype") == "Pokémon" and type(number) is int and 1 <= number <= 151


def catalog(actor, query="", *, include_goals=False, goal_ids=None, include_current=False):
    store.verified(actor)
    games = {g["id"] for g in store.rows("SELECT id FROM games WHERE game_key='pokemon'")}
    goal_ids = (
        goal_ids
        if goal_ids is not None
        else (
            {
                pid
                for g in collection.goals(actor, include_updates=False)
                for item in g["definition"]["items"]
                for pid in item["printing_ids"]
            }
            if include_goals
            else set()
        )
    )
    return [
        p
        for p in collection.catalog(actor, query)
        if p["game_id"] in games
        and (p["set_name"] in SETS or p["id"] in goal_ids or include_current and current_species_printing(p))
    ]


def missing_choices(actor, goal_id, item_id="", *, pick_first=False):
    """Use the account's frozen goal and its existing ownership policy unchanged."""
    goal = next(iter(collection.goals(actor, goal_id=goal_id, include_updates=False)), None)
    if goal is None:
        raise ValueError("Choose one of your collection goals")
    available = {p["id"] for p in collection.catalog(actor)}
    items = [
        dict(id=i["label"], label=i["label"], printing_ids=[p for p in i["printing_ids"] if p in available])
        for i in goal["progress"]
        if i["status"] != "owned"
    ]
    if item_id and not any(i["id"] == item_id for i in items):
        raise ValueError("This card is no longer missing from your selected goal")
    selected = item_id or (items[0]["id"] if pick_first and items else "")
    ids = {p for i in items if not selected or i["id"] == selected for p in i["printing_ids"]}
    return ids, [dict(id=i["id"], label=i["label"], available=len(i["printing_ids"])) for i in items]


def current_missing_choices(actor, item_id="", *, pick_first=False):
    """Current Original 151 species presence, independent of saved goal snapshots."""
    actor = store.verified(actor)
    generation = collection.generation(actor)
    current = effective_collection.project(actor)
    if current["user_id"] != actor.user_id or current["generation"] != generation:
        raise collection.Conflict("Collection changed during Shopping read")
    by_species = {}
    for printing in catalog(actor, include_current=True):
        if current_species_printing(printing):
            by_species.setdefault(printing["attributes"]["pokemon_dex"], []).append(printing["id"])
    names = canonical_species.registry()
    items = [
        dict(
            id=f"#{number:03} {names[number]['name']}",
            label=f"#{number:03} {names[number]['name']}",
            printing_ids=by_species.get(number, []),
        )
        for number in range(1, 152)
        if not current["species"][str(number)]["present"]
    ]
    if item_id and not any(item["id"] == item_id for item in items):
        raise ValueError("This Pokémon is no longer missing from your current collection")
    selected = item_id or (items[0]["id"] if pick_first and items else "")
    ids = {pid for item in items if not selected or item["id"] == selected for pid in item["printing_ids"]}
    store.verified(actor)
    if collection.generation(actor) != generation:
        raise collection.Conflict("Collection changed during Shopping read")
    return ids, [dict(id=i["id"], label=i["label"], available=len(i["printing_ids"])) for i in items]


def legacy_records():
    """Freeze admission to existing guide bytes; synthetic sources require a disposable marker."""
    if (settings.ROOT / "SYNTHETIC_ONLY").is_file():
        rows, _ = shopping.sources()
        return rows
    for path, expected in (
        (settings.ROOT / "parity-evidence/market_values.json", PRIVATE_RETAINED_SHA256),
        (runtime_root() / "config/market_values.json", RETAINED_SHA256),
    ):
        if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == expected:
            return json.loads(path.read_text())
    return []


class SnapshotRecords(list):
    def __init__(self, rows, status):
        super().__init__(rows)
        self.status = status


def retained_records():
    """Active private prices and intact historical guides; no fetching or relabeling."""
    current, status = price_snapshots.display_current()
    return SnapshotRecords(current + legacy_records(), status)


def selector(
    actor, query="", *, goal_id="", item_id="", printing_id="", pick_first=False, current_missing=False
):
    if current_missing and goal_id:
        raise ValueError("Choose current collection or a saved goal")
    missing_ids, items = (
        current_missing_choices(actor, item_id, pick_first=pick_first)
        if current_missing
        else missing_choices(actor, goal_id, item_id, pick_first=pick_first)
        if goal_id
        else (None, [])
    )
    printings = [
        p
        for p in catalog(
            actor,
            query,
            include_goals=bool(printing_id),
            goal_ids=missing_ids,
            include_current=current_missing,
        )
        if (missing_ids is None or p["id"] in missing_ids) and (not printing_id or p["id"] == printing_id)
    ]
    if goal_id or current_missing:
        printings.sort(
            key=lambda p: (
                p["set_name"] not in SETS,
                SETS.index(p["set_name"]) if p["set_name"] in SETS else len(SETS),
                p["name"].casefold(),
                p["collector_number"],
                p["id"],
            )
        )
    return printings, items


def priced_cards(actor, printings):
    today = datetime.now(shopping.TZ).date()
    rows, copies = retained_records(), collection.copies(actor)
    result = []
    for p in printings:
        values, reasons = cell_details(p, rows, today)
        result.append(
            dict(
                shopping.identity(p),
                copy_count=sum(c["printing_id"] == p["id"] for c in copies),
                cells=values,
                price_reasons=reasons,
            )
        )
    return result


def browse(actor, query="", *, goal_id="", item_id="", printing_id="", current_missing=False):
    printings, _ = selector(
        actor,
        query,
        goal_id=goal_id,
        item_id=item_id,
        printing_id=printing_id,
        current_missing=current_missing,
    )
    return priced_cards(actor, printings)


def browse_page(
    actor,
    query="",
    *,
    goal_id="",
    item_id="",
    printing_id="",
    offset=0,
    pick_first=False,
    current_missing=False,
):
    printings, items = selector(
        actor,
        query,
        goal_id=goal_id,
        item_id=item_id,
        printing_id=printing_id,
        pick_first=pick_first,
        current_missing=current_missing,
    )
    return dict(
        cards=priced_cards(actor, printings[offset : offset + 40]),
        total=len(printings),
        offset=offset,
        missing_items=items,
        selected_missing_item=item_id or (items[0]["id"] if pick_first and items else ""),
    )


def locks(actor, session, supplied=None):
    """Reuse authenticated session storage; wants never enroll in frozen collection goals."""
    store.verified(actor)
    key = "shopping_wants_" + actor.user_id
    if supplied is not None:
        if not isinstance(supplied, list) or len(supplied) > 200:
            raise ValueError("At most 200 wanted identities")
        ids = {p["id"] for p in catalog(actor, include_goals=True, include_current=True)} | {
            p["printing_id"] for p in session.get(key, [])
        }
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


def prepare(actor, raw, now=None, *, review_traits=None, unknown_quantity=0):
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
    entries = {p["id"]: p for p in catalog(actor, include_goals=True, include_current=True)}
    records, identities, by_column, seen = retained_records(), [], {g: [] for g in COLUMNS}, set()
    selections = []
    for line in raw["cards"]:
        shopping.fields(line, {"printing_id", "quantity", "values"}, {"printing_id", "quantity", "values"})
        p = entries.get(line["printing_id"])
        if p is None or p["id"] in seen:
            raise ValueError("Missing, unsupported or duplicate printing")
        seen.add(p["id"])
        math.quantity(line["quantity"])
        shopping.fields(line["values"], COLUMNS, COLUMNS)
        guides = cells(p, records, today)
        if review_traits is not None:
            from .discovery_comparison import reference_issue

            traits = review_traits[p["id"]]
            grade = traits.get("grade") or "unknown"
            clues = {
                key: traits.get(key) or None
                for key in ("language", "edition", "finish", "condition", "grader")
            }
            clues["graded"] = grade not in {"raw", "unknown"}
            for column, ref in list(guides.items()):
                if (
                    ref is None
                    or column != grade
                    or (clues["graded"] and not clues["grader"])
                    or reference_issue(p, clues, ref, today)
                ):
                    guides[column] = None
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
                    if review_traits is not None:
                        continue
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
        unknown_contents=dict(quantity=unknown_quantity),
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
    versioned_rows = None

    def visit(value):
        nonlocal versioned_rows
        if isinstance(value, dict):
            if value.get("source_contract") and value.get("save_allowed") is False:
                raise ValueError(
                    "This source permits current display only; permanent comparison saving is unavailable"
                )
            if value.get("kind") == "guide" and "raw_record" in value:
                if "_snapshot_version" in value["raw_record"]:
                    if versioned_rows is None:
                        versioned_rows, _ = price_snapshots.current()
                    price_snapshots.admit(value, versioned_rows)
                elif shopping.digest(value["raw_record"]) not in admitted:
                    raise ValueError("New provider embedding requires surviving rights and admission")
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(payload)
