"""Shared private Shopping history and original per-card research; existing catalog/goal authority."""

import hashlib
import json
import uuid
from copy import deepcopy
from datetime import datetime
from zoneinfo import ZoneInfo

from django.db import connection
from django.http import Http404

from pokemon_hunter.migration import encode

from . import (
    broad_goals,
    canonical_species,
    collection,
    collection_goals,
    collection_imports,
    hunt_values,
    pack_research,
    parity,
    store,
    transactions,
)
from . import shopping_math as math

# Preserve the established service imports while keeping validation independent.
from .shopping_inputs import fields as fields
from .shopping_inputs import text as text
from .shopping_inputs import validate_component as validate_component
from .shopping_inputs import validate_request as validate_request

TZ = ZoneInfo("America/New_York")
SNAPSHOT_SCHEMAS = frozenset({"dex-shopping-v1", "dex-lot-v2"})


def digest(value):
    return hashlib.sha256(encode(value).encode()).hexdigest()


def initialize(db=None):
    ddl = """CREATE TABLE IF NOT EXISTS saved_shopping_comparisons(
    id TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id),name TEXT NOT NULL,
    created_at TEXT NOT NULL,parent_id TEXT,snapshot TEXT NOT NULL,snapshot_sha256 TEXT NOT NULL)"""
    if db is not None:
        db.execute(ddl)
    else:
        with transactions.atomic(), connection.cursor() as cursor:
            cursor.execute(ddl)


def available():
    return "saved_shopping_comparisons" in connection.introspection.table_names()


def identity(p):
    captured = {
        k: deepcopy(p.get(k))
        for k in (
            "id",
            "name",
            "set_id",
            "set_name",
            "collector_number",
            "language",
            "edition",
            "finish",
            "variant",
            "attributes",
            "unresolved_fields",
            "provenance",
            "catalog_version",
        )
    }
    number = p["attributes"].get("pokemon_dex")
    captured["species_id"] = canonical_species.require(number) if type(number) is int else None
    return captured


def observations(p, records, raw_values, edition, condition, grade, grader, today):
    """Retain raw amounts and candidates; legacy matcher decides basis, never money totals."""
    key = json.loads(p["provenance"]).get("legacy_id")
    if not key:
        return [], None
    candidates = []
    for index, row in enumerate(records):
        if not isinstance(row, dict) or row.get("card_id") != key:
            continue
        oid = "guide-" + digest(dict(index=index, record=row))
        g = (grader, grade) if grade else None
        match = hunt_values._guide(key, edition, g, [row], today)
        reason = "eligible" if match else "guide_basis_source_or_date_unavailable"
        if match and (
            row.get("language") not in (None, p["language"])
            or row.get("finish") not in (None, p["finish"])
            or row.get("variant") not in (None, p["variant"])
        ):
            reason = "conflicting_guide_identity"
        if match and p.get("edition") in {"standard", "first_edition"} and row.get("edition") != p["edition"]:
            reason = "conflicting_guide_edition"
        ref = dict(
            reference_id=oid,
            observation_id=oid,
            kind="guide",
            value_scope="per_card",
            amount=row.get("value"),
            currency=row.get("currency"),
            as_of=row.get("as_of"),
            source_url=row.get("source_url"),
            provenance="guide_reference",
            raw_record=deepcopy(row),
            source_key=key,
            record_sha256=digest(row),
            source_index=index,
            printing_id=p["id"],
            match_status="conditional" if reason == "eligible" else "unavailable",
            assumptions=[
                "Guide identity/condition fit is conditional; legacy language, finish, variant and raw condition may be absent."
            ],
            basis_eligibility=reason,
        )
        ref["eligibility"] = math.eligibility(ref, today.isoformat())
        candidates.append(ref)
    # Explicit condition buckets must carry every new-workspace field; no legacy defaults.
    bucket = {"LP": "LP", "NM": "NM"}.get(condition)
    raw = raw_values.get(key, {}).get(bucket) if isinstance(raw_values.get(key), dict) and bucket else None
    if not grade and isinstance(raw, dict):
        oid = "raw-" + digest(dict(key=key, bucket=bucket, record=raw))
        safe = (
            raw.get("currency") == "USD"
            and raw.get("edition") == edition == "standard"
            and hunt_values._source(raw.get("source_url") or raw.get("source"))
        )
        ref = dict(
            reference_id=oid,
            observation_id=oid,
            kind="guide",
            value_scope="per_card",
            amount=raw.get("value"),
            currency=raw.get("currency"),
            as_of=raw.get("as_of"),
            source_url=raw.get("source_url") or raw.get("source"),
            provenance="raw_condition_reference",
            raw_record=deepcopy(raw),
            source_key=key,
            record_sha256=digest(raw),
            printing_id=p["id"],
            match_status="conditional" if safe else "unavailable",
            assumptions=[f"Explicit {bucket} raw-condition scenario; physical identity remains unverified."],
            basis_eligibility="eligible" if safe else "missing_explicit_raw_fields",
        )
        ref["eligibility"] = math.eligibility(ref, today.isoformat())
        candidates.insert(0, ref)
    valid = [r for r in candidates if r["eligibility"] == "eligible"]
    raw = next((r for r in valid if r["provenance"] == "raw_condition_reference"), None)
    chosen = raw or (max(valid, key=lambda r: r["as_of"]) if valid else None)
    return candidates, chosen


def sources():
    return parity.hunt_guide_records(), parity.evidence("raw_values.json", {})


def goal_context(actor, key, version=""):
    if not key:
        if version:
            raise ValueError("Goal version requires a goal")
        return None
    # Account scope and progress policy are supplied by existing collection services.
    row = collection.one(actor, "goal", key)
    row["definition"] = json.loads(row["definition"])
    definition = collection_imports.goal_definition(row)
    if row["kind"] == "original151":
        broad_goals.validate(definition)
    elif row["kind"] not in collection_goals.OWNERSHIP_KINDS:
        collection_imports.validate_membership(
            row,
            definition,
            collection.catalog(actor, include_archived=True),
            games=store.rows("SELECT id,game_key,name FROM games"),
            vintage_template=collection.goal_definition(actor, {"goal_kind": "vintage"})
            if row["kind"] == "vintage"
            else None,
        )
    if version and row["version"] != version:
        raise ValueError("Frozen goal version changed")
    projection = next(g for g in collection.goals(actor) if g["id"] == key)
    if definition["policy"] == "species" and row["kind"] not in collection_goals.OWNERSHIP_KINDS:
        projection = broad_goals.progress(
            definition, collection.copies(actor), {p["id"] for p in collection.catalog(actor)}
        )
    for ref in definition.get("catalog_references", []):
        journals = store.rows("SELECT package_hash FROM catalog_imports WHERE id=%s", [ref["import_id"]])
        if not journals or journals[0]["package_hash"] != ref["package_sha256"]:
            raise ValueError("Frozen catalog reference missing or changed")
    # Item labels already participate in stored versions; do not rename or union policies.
    items = [
        dict(
            item_id=i["label"],
            printing_ids=i["printing_ids"],
            species_id=i.get("pokemon_dex"),
            unresolved=i.get("unresolved", False),
        )
        for i in definition["items"]
    ]
    if len({i["item_id"] for i in items}) != len(items):
        raise ValueError("Duplicate frozen item identity")
    policy = (
        "species_declaration"
        if row["kind"] in collection_goals.OWNERSHIP_KINDS
        else ("species_resolved_copy" if definition["policy"] == "species" else definition["policy"])
    )
    return dict(
        goal_id=key,
        name=row["name"],
        kind=row["kind"],
        version=row["version"],
        definition_sha256=digest(definition),
        definition=definition,
        policy=policy,
        items=items,
        owned_item_ids=sorted(i["label"] for i in projection["progress"] if i["status"] == "owned"),
    )


def browse(actor, filters=None, today=None):
    store.verified(actor)
    f = filters or {}
    today = today or datetime.now(TZ).date()
    entries = collection.catalog(actor, f.get("q", ""), f.get("set", ""))
    active = collection.copies(actor)
    exact = collection.exact_owned_printings(active)
    goal = goal_context(actor, f.get("goal", ""))
    if f.get("missing") == "species" and (not goal or not goal["policy"].startswith("species")):
        raise ValueError("Missing species requires a selected species goal policy")
    records, raw = sources()
    result = []
    for p in entries:
        if f.get("edition") and f["edition"] != p.get("edition"):
            continue
        if f.get("variant") and f["variant"].casefold() not in str(p.get("variant") or "").casefold():
            continue
        matches = [i for i in (goal["items"] if goal else []) if p["id"] in i["printing_ids"]]
        if goal and not matches:
            continue
        if f.get("missing") == "species" and any(i["item_id"] in goal["owned_item_ids"] for i in matches):
            continue
        if f.get("missing") == "printing" and p["id"] in exact:
            continue
        candidates, chosen = observations(
            p,
            records,
            raw,
            f.get("value_edition", "standard"),
            f.get("condition", ""),
            f.get("grade", ""),
            f.get("grader", ""),
            today,
        )
        if f.get("value") == "available" and not chosen or f.get("value") == "unavailable" and chosen:
            continue
        result.append(
            dict(
                identity(p),
                copy_count=sum(c["printing_id"] == p["id"] for c in active),
                exact_owned=p["id"] in exact,
                candidates=candidates,
                guide=chosen,
                value=chosen["amount"] if chosen else None,
            )
        )
    sort = f.get("sort", "name")
    if sort in {"value_asc", "value_desc"}:
        valued = [r for r in result if r["value"] is not None]
        unpriced = [r for r in result if r["value"] is None]
        result = (
            sorted(valued, key=lambda r: (math.amount(r["value"]), r["id"]), reverse=sort == "value_desc")
            + unpriced
        )
    else:
        result.sort(
            key=lambda r: (
                str(r.get("set_name") if sort == "set" else r["name"]).casefold(),
                r["collector_number"],
                r["id"],
            )
        )
    return dict(
        cards=result,
        goal=goal,
        goals=[{k: g[k] for k in ("id", "name", "version")} for g in collection.goals(actor)],
    )


@transactions.atomic
def prepare(actor, raw, now=None, retained=None):
    actor = store.verified(actor)
    validate_request(raw)
    now = now or datetime.now(TZ)
    today = now.astimezone(TZ).date()
    goal = goal_context(actor, raw.get("goal_id", ""), raw.get("goal_version", ""))
    if goal and not raw.get("goal_version"):
        raise ValueError("Select exact frozen goal version")
    entries = {p["id"]: p for p in collection.catalog(actor)}
    records, raw_values = sources()
    candidates, selected = {}, []
    for supplied in raw["selected_cards"]:
        p = entries.get(supplied["printing_id"])
        if p is None:
            raise ValueError("Selected printing missing or archived")
        observations_, _ = observations(
            p,
            records,
            raw_values,
            supplied.get("edition", "standard"),
            supplied.get("condition", ""),
            supplied.get("grade", ""),
            supplied.get("grader", ""),
            today,
        )
        candidates[supplied["selection_id"]] = observations_
        exact = supplied["completion_confirmed"] and not p["unresolved_fields"]
        catalog = (
            supplied["completion_confirmed"] and goal and goal["policy"] in {"catalog", "species_declaration"}
        )
        # Even exact policy admits only resolved frozen checklist members.
        if (
            goal
            and any(i["unresolved"] for i in goal["items"] if p["id"] in i["printing_ids"])
            and goal["policy"] == "exact"
        ):
            exact = False
        selected.append(
            dict(
                supplied,
                captured_identity=identity(p),
                completion_identity_status="eligible" if exact or catalog else "unknown",
                completion_identity_basis="Owner-supplied physical identification under selected policy"
                if exact or catalog
                else "Physical identity unresolved; catalog selection is a candidate",
            )
        )
    ref_by_observation = {r["observation_id"]: r for rows in candidates.values() for r in rows}
    # Alternatives may survive removal of a line; validate their printing independently.
    for r in raw["value_references"]:
        if r["kind"] != "guide" or r.get("observation_id") in ref_by_observation:
            continue
        p = entries.get(r.get("printing_id"))
        if p:
            # Candidate matching below still restricts active lines to their chosen basis.
            for edition in ("standard", "first_edition"):
                for condition in ("", "LP", "NM"):
                    extra, _ = observations(p, records, raw_values, edition, condition, "", "", today)
                    ref_by_observation.update({v["observation_id"]: v for v in extra})
    refs = []
    for r in raw["value_references"]:
        if r["kind"] == "guide":
            ref = ref_by_observation.get(r.get("observation_id"))
            lines = [s for s in selected if s["chosen_value_reference"] == r["reference_id"]]
            if ref is None and retained:
                ref = next(
                    (
                        v
                        for v in retained["value_references"]
                        if v.get("observation_id") == r.get("observation_id")
                    ),
                    None,
                )
                if ref:
                    ref = dict(
                        ref,
                        match_status="unavailable",
                        basis_eligibility="current_guide_reference_missing_or_changed",
                    )
            if (
                ref is None
                or r.get("printing_id") != ref["printing_id"]
                or any(s["printing_id"] != ref["printing_id"] for s in lines)
            ):
                raise ValueError("Missing, tampered or mismatched guide reference")
            for line in lines:
                matched = next(
                    (
                        v
                        for v in candidates[line["selection_id"]]
                        if v["observation_id"] == ref["observation_id"]
                    ),
                    None,
                )
                if matched is None:
                    if not retained:
                        raise ValueError("Guide reference does not apply to selected basis")
                    ref = dict(
                        ref,
                        match_status="unavailable",
                        basis_eligibility="current_guide_reference_missing_or_changed",
                    )
                elif matched["match_status"] == "unavailable":
                    ref = dict(
                        ref, match_status="unavailable", basis_eligibility=matched["basis_eligibility"]
                    )
            refs.append(dict(ref, reference_id=r["reference_id"]))
        else:
            scope = r.get("value_scope")
            if scope not in {"per_card", "selection_group_total"}:
                raise ValueError("Specify per-card or group-total estimate")
            member_ids = r.get("applies_to_quantities", {})
            if not isinstance(member_ids, dict):
                raise ValueError("Group membership requires captured quantities")
            for sid, q in member_ids.items():
                text(sid, 200)
                math.quantity(q)
            refs.append(
                dict(
                    r,
                    provenance="manual_user_estimate",
                    match_status="conditional",
                    assumptions=[r["assumptions"]],
                    entered_date=r["as_of"],
                )
            )
    active = collection.copies(actor)
    context = dict(
        deepcopy(raw),
        account_id=actor.user_id,
        context_id=str(uuid.uuid4()),
        evaluation_date=today.isoformat(),
        evaluation_at=now.isoformat(),
        timezone="America/New_York",
        selected_cards=selected,
        value_references=refs,
        candidate_references=candidates,
        frozen_goal=goal,
        ownership_context=dict(
            availability="complete",
            generation=collection.generation(actor),
            captured_at=now.isoformat(),
            copies=deepcopy(active),
            declaration_sources=[collection_goals.reference(r) for r in collection_goals.sources(actor)],
            declaration_source=goal["definition"].get("collection_source") if goal else None,
        ),
    )
    context["listing_observation"]["observation_id"] = (
        retained["listing_observation"]["observation_id"] if retained else str(uuid.uuid4())
    )
    # Shared costs require an explicit matching decision on both independent bases.
    for key in math.COSTS:
        a, b = (context["delivery_cost_inputs"][basis][key] for basis in math.BASES)
        if a.get("applies_to_both") or b.get("applies_to_both"):
            if (
                not a.get("applies_to_both")
                or not b.get("applies_to_both")
                or any(a.get(k) != b.get(k) for k in ("amount", "currency", "status"))
            ):
                raise ValueError("Shared cost confirmation differs between bases")
    return dict(
        schema="dex-shopping-v1", request=deepcopy(raw), context=context, result=math.evaluate(context)
    )


def listing(actor):
    store.verified(actor)
    return (
        store.rows(
            "SELECT id,name,created_at,parent_id FROM saved_shopping_comparisons WHERE user_id=%s ORDER BY created_at DESC,id",
            [actor.user_id],
        )
        if available()
        else []
    )


def one(actor, key):
    store.verified(actor)
    rows = (
        store.rows(
            "SELECT * FROM saved_shopping_comparisons WHERE user_id=%s AND id=%s", [actor.user_id, key]
        )
        if available()
        else []
    )
    if not rows:
        raise Http404
    return rows[0]


@transactions.atomic
def save(actor, raw, name, parent=None, now=None):
    retained = reopen(actor, parent)["context"] if parent else None
    payload = prepare(actor, raw, now=now, retained=retained)
    return store_payload(actor, payload, name, parent)


def store_payload(actor, payload, name, parent=None):
    store.verified(actor)
    if not available():
        raise ValueError("Enable additive shopping storage before saving")
    validate_snapshot(actor, payload)
    if parent:
        one(actor, parent)
    from .lot_calculator import admit_snapshot

    admit_snapshot(payload)
    key = str(uuid.uuid4())
    collection.execute(
        "INSERT INTO saved_shopping_comparisons VALUES(%s,%s,%s,%s,%s,%s,%s)",
        [
            key,
            actor.user_id,
            pack_research.name(name),
            datetime.now(TZ).isoformat(),
            parent,
            encode(payload),
            digest(payload),
        ],
    )
    return key


def validate_snapshot(actor, payload):
    """Both history formats share schema and account authority; unknown formats never fall back."""
    if not isinstance(payload, dict) or not isinstance(payload.get("schema"), str):
        raise ValueError("Unsupported shopping snapshot schema")
    if payload["schema"] not in SNAPSHOT_SCHEMAS:
        raise ValueError("Unsupported shopping snapshot schema")
    context = payload.get("context")
    if not isinstance(context, dict) or context.get("account_id") != actor.user_id:
        raise ValueError("Retained comparison integrity mismatch")


def reopen(actor, key):
    """Load authenticated immutable history once, then project format-specific reference status."""
    row = one(actor, key)
    if hashlib.sha256(row["snapshot"].encode()).hexdigest() != row["snapshot_sha256"]:
        raise ValueError("Retained comparison integrity mismatch")
    try:
        payload = json.loads(row["snapshot"])
    except ValueError:
        raise ValueError("Retained comparison integrity mismatch") from None
    validate_snapshot(actor, payload)
    payload["saved"] = {k: row[k] for k in ("id", "name", "created_at", "parent_id", "snapshot_sha256")}
    if payload["schema"] == "dex-lot-v2":
        return payload
    gaps = []
    entries = {p["id"]: p for p in collection.catalog(actor)}
    for s in payload["context"]["selected_cards"]:
        if s["printing_id"] not in entries or identity(entries[s["printing_id"]]) != s["captured_identity"]:
            gaps.append(
                f"{s['selection_id']}: catalog identity missing, archived or changed; captured history retained."
            )
    goal = payload["context"]["frozen_goal"]
    if goal:
        try:
            goal_context(actor, goal["goal_id"], goal["version"])
        except (ValueError, Http404):
            gaps.append("Frozen goal/reference is missing or changed; captured history retained.")
    records, raw_values = sources()
    current_hashes = {digest(r) for r in records if isinstance(r, dict)}
    for buckets in raw_values.values() if isinstance(raw_values, dict) else []:
        if isinstance(buckets, dict):
            current_hashes.update(digest(r) for r in buckets.values() if isinstance(r, dict))
    for ref in payload["context"]["value_references"]:
        if ref.get("kind") == "guide" and ref.get("record_sha256") not in current_hashes:
            gaps.append(
                f"{ref['reference_id']}: current retained guide missing or changed; captured observation retained."
            )
    ages = {
        r["reference_id"]: math.fresh(r.get("as_of"), datetime.now(TZ).date().isoformat())
        for r in payload["context"]["value_references"]
    }
    return dict(
        payload,
        reference_gaps=gaps,
        present_reference_age=ages,
    )


@transactions.atomic
def reevaluate(actor, key):
    old = reopen(actor, key)
    if old["schema"] == "dex-lot-v2":
        from .lot_calculator import prepare as prepare_lot

        payload = prepare_lot(actor, old["request"])
    else:
        payload = prepare(actor, old["request"], retained=old["context"])
    return store_payload(actor, payload, old["saved"]["name"] + " · current", parent=key)
