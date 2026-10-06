"""Vintage views and explicit hunts projected from active session-owned copies."""

import json
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal

from django.conf import settings
from django.http import Http404
from pydantic import Field, field_validator

from pokemon_hunter import hunt
from pokemon_hunter.collection import derive, totals
from pokemon_hunter.hunt import SearchRequest, public_listing, query_plan
from pokemon_hunter.inventory import stable_id
from pokemon_hunter.migration import encode
from pokemon_hunter.valuation import valuation_records

from . import collection as service
from . import ebay_hunts, goal_hunts, hunt_values, store
from . import transactions as transaction
from .diagnostics import failure


def evidence(filename, default):
    if filename not in {"market_values.json", "raw_values.json", "hunt.json", "demo_hunts.json"}:
        raise ValueError("Unsupported parity evidence; species identity uses canonical_species")
    if getattr(settings, "STAGING", False):
        # Source review permits metadata only. No legacy pricing or hunt redistribution.
        return default
    path = settings.ROOT / "parity-evidence" / filename
    return json.loads(path.read_text()) if path.is_file() else default


def projection(actor):
    active = service.copies(actor)
    by_printing = {}
    for copy in active:
        by_printing.setdefault(copy["printing_id"], []).append(copy)
    sets = {
        r["internal_id"]: r["external_id"]
        for r in store.rows("SELECT * FROM external_mappings WHERE provider='legacy' AND entity_kind='set'")
    }
    from .canonical_species import registry

    species = registry()
    # No ownership is loaded from the historical species evidence.
    dex = {
        str(n): {
            "dex_number": n,
            "name": species[n]["name"],
            "generation": 1 if n <= 151 else 2,
        }
        for n in range(1, 252)
    }
    cards = {}
    catalog = service.catalog(actor)
    from .catalog_pipeline import indexed_eras

    eras = indexed_eras()
    for p in catalog:
        legacy = json.loads(p["provenance"]).get("legacy_id")
        if not legacy:
            legacy = "catalog-" + p["id"]
        copies = by_printing.get(p["id"], [])
        cards[legacy] = {
            **p["attributes"],
            # The classic overview has a fixed 251-species denominator. Catalog
            # support and exact printing display retain every canonical identity.
            "dex_eligible": bool(
                p["attributes"].get("dex_eligible") and str(p["attributes"].get("pokemon_dex")) in dex
            ),
            "card_id": legacy,
            "printing_id": p["id"],
            "set_id": sets.get(p["set_id"], p["set_id"]),
            "set": p["set_name"],
            "era": eras.get(p["set_id"]),
            "number": p["collector_number"],
            "variant": p["variant"],
            "owned": bool(copies),
            "rarity": p["attributes"].get("rarity", "Unknown"),
            "supertype": p["attributes"].get("supertype", "Unknown"),
            "first_edition": any(c["first_edition_selected"] for c in copies),
            "copy_ids": [c["id"] for c in copies],
        }
    data = derive({"cards": cards, "pokedex": dex})
    data["totals"] = {**totals(data), "physical_copies": len(active)}
    data["catalog"] = catalog
    data["valuation"] = estimates(active, catalog)
    from .ownership_declarations import summary

    declaration = summary(actor)
    from .collection_goals import latest

    declared_rows = declaration["rows"] + declaration["gen2"]["rows"]
    has_declaration = bool(latest(actor)) or bool(declared_rows)
    data["owner_collection"] = dict(
        kanto=declaration["species"],
        johto=declaration["gen2"]["species"],
        total=declaration["species"] + declaration["gen2"]["species"],
        active=has_declaration,
    )
    for key, item in data["pokedex"].items():
        item["declared_cards"] = [r for r in declared_rows if r["pokemon_dex"] == int(key)]
        item["collection_owned"] = bool(item["declared_cards"]) if has_declaration else item["dex_owned"]
    return data


def summarize(rows, owned):
    result = {}
    for grade in ("raw", "7", "8", "9", "10"):
        priced = [r[grade] for r in rows if grade in r]
        subtotal = str(sum((Decimal(r["value"]) for r in priced), Decimal(0))) if priced else None
        result[grade] = {
            "priced": len(priced),
            "owned": owned,
            "subtotal": subtotal,
            "total": subtotal if len(priced) == owned else None,
            "estimated": sum(r["estimated"] for r in priced),
        }
    return result


def estimates(active, catalog):
    records = evidence("market_values.json", [])
    by_id = {p["id"]: p for p in catalog}
    scenarios, confirmed, conditional = {}, [], []
    for copy in active:
        p = by_id.get(copy["printing_id"])
        if not p:
            scenarios[copy["id"]] = {"conditional": {}, "confirmed": {}, "reason": "Identity unresolved"}
            continue
        key = json.loads(p["provenance"]).get("legacy_id")
        identity = json.loads(copy["provisional_identity"] or "{}")
        selected = bool(copy["first_edition_selected"])
        # Legacy guide match remains unchanged, explicitly a hypothesis for uncertain copies.
        prices = valuation_records({"cards": {key: {"owned": True, "first_edition": selected}}}, records)[
            "cards"
        ].get(key, {})
        unresolved = set(p["unresolved_fields"]) | set(identity.get("unresolved_fields", []))
        if selected:
            unresolved.discard("edition")
        elif identity.get("edition_selection") == "unresolved":
            unresolved.add("edition")
        resolved = not unresolved and p["edition"] in ("standard", "first_edition")
        actual = prices if resolved else {}
        scenarios[copy["id"]] = {
            "conditional": prices,
            "confirmed": actual,
            "assumption": "First-edition guide variant"
            if selected
            else "Standard guide variant (not established by an unchecked flag)",
            "reason": ", ".join(sorted(unresolved)) or "Resolved guide identity",
        }
        conditional.append(prices)
        confirmed.append(actual)
    costs = {}
    for c in active:
        if c["purchase_amount"] is not None:
            currency = c["purchase_currency"]
            costs[currency] = str(Decimal(costs.get(currency, "0")) + Decimal(c["purchase_amount"]))
    return {
        "copies": scenarios,
        "confirmed": summarize(confirmed, len(active)),
        "conditional": summarize(conditional, len(active)),
        "max_age_days": 30,
        "purchase_subtotals": costs,
        "purchase_known": sum(c["purchase_amount"] is not None for c in active),
        "source_dates": sorted({r.get("as_of") for r in records if r.get("as_of")}),
        "evidence_available": bool(records),
    }


class AuthenticatedSearchRequest(SearchRequest):
    goal_id: str | None = Field(default=None, min_length=1, max_length=64)
    continuation_batch: str | None = Field(default=None, min_length=36, max_length=36)
    intent: Literal["value", "missing"] = "value"
    query: str = Field(default="", max_length=200)

    @field_validator("query")
    @classmethod
    def normalize_query(cls, value):
        return value.strip()


def hunt_settings(raw):
    return AuthenticatedSearchRequest.model_validate(raw)


def saved_settings(raw):
    return hunt_settings({"intent": "missing", **raw})


def hunt_projection(actor, scope, body):
    data = goal_hunts.project(actor, projection(actor), scope)
    return {**data, "value_intent": body.intent == "value"}


def hunt_guide_records():
    """Use explicit guide refreshes alongside preserved local evidence, never ownership."""
    retained = evidence("market_values.json", [])
    if getattr(settings, "STAGING", False):
        return retained
    path = ebay_hunts.configuration_root() / "config/market_values.json"
    latest = []
    if path.is_file():
        try:
            latest = json.loads(path.read_text())
        except (OSError, UnicodeError, ValueError) as exc:
            failure("hunt_guide_read_failed", exc)
    return (latest if isinstance(latest, list) else []) + (retained if isinstance(retained, list) else [])


def hunt_rows(actor):
    store.verified(actor)
    return store.rows(
        "SELECT * FROM saved_hunts WHERE user_id=%s ORDER BY created DESC,legacy_id DESC", [actor.user_id]
    )


def history(actor):
    result = []
    for r in hunt_rows(actor):
        coverage = json.loads(r["coverage"] or "{}")
        row = {
            "batch": r["batch_id"],
            "id": r["legacy_id"],
            "created": r["created"],
            "demo": bool(r["demo"]),
            "settings": saved_settings(json.loads(r["request"])).model_dump(mode="json"),
            "goal": goal_hunts.public(coverage.get("goal_scope")),
            "environment": coverage.get("environment")
            if coverage.get("environment") in {"production", "sandbox"}
            else None,
        }
        result.append(row)
    return result


def projected_hunt(actor, batch, key, reveal=None):
    saved = store.resource(actor, "hunts", (str(batch), key))
    return hunt_response(actor, saved, batch, key, reveal)


def hunt_response(actor, saved, batch, key, reveal=None):
    body = saved_settings(json.loads(saved["request"]))
    coverage = json.loads(saved["coverage"] or "{}")
    scope = coverage.get("goal_scope")
    data = hunt_projection(actor, scope, body)
    config = evidence("hunt.json", None)
    if not config:
        raise ValueError("Local hunt evidence is unavailable in this environment")
    raws = json.loads(saved["raw"])
    # Opaque stable handles, never seller-controlled IDs or URLs in hidden responses.
    for index, raw in enumerate(raws):
        raw["itemId"] = stable_id("private-result", f"{actor.user_id}:{batch}:{key}:{index}")
    rows = hunt.project_results(
        raws, body, bool(saved["demo"]), data, config, evidence("raw_values.json", {})
    )
    guides = hunt_values.prepare_records(hunt_guide_records())
    raw_values = evidence("raw_values.json", {})
    for row in rows:
        row["pricing"] = hunt_values.price_comparison(row, data, guides, raw_values, scope=scope)
    if body.intent == "value":
        rows.sort(
            key=lambda row: (
                row["pricing"]["discount_percent"] is not None,
                Decimal(row["pricing"]["discount_percent"] or "0"),
            ),
            reverse=True,
        )

    def safe(row, revealed=False):
        public = public_listing(row, reveal=revealed)
        public["pricing"] = {
            k: v
            for k, v in row["pricing"].items()
            if k
            in {
                "status",
                "basis",
                "reference_total",
                "delivered",
                "saving",
                "discount_percent",
                "average_per_card",
                "priced_cards",
                "identified_cards",
                "lot_count",
                "coverage",
                "source_dates",
                "note",
            }
            or (revealed and k == "evidence")
        }
        # Free-form condition text may itself contain identities. All other fields come
        # from the fixed shared scorer; never merge raw or arbitrary coverage text.
        public.pop("condition", None)
        if revealed and saved["demo"]:
            public["url"] = None
        return public

    if reveal is not None:
        row = next((r for r in rows if r["id"] == str(reveal)), None)
        if not row:
            raise Http404
        return safe(row, True)
    public_coverage = {
        k: v
        for k, v in coverage.items()
        if k in {"queries_run", "queries_total", "offset"} and type(v) is int and v >= 0
    }
    public_coverage["next_offset"] = (
        coverage.get("next_offset")
        if type(coverage.get("next_offset")) is int and coverage["next_offset"] >= 0
        else None
    )
    public_coverage["limited"] = coverage.get("limited") is True
    if coverage.get("environment") in {"production", "sandbox"}:
        public_coverage["environment"] = coverage["environment"]
    return {
        "batch": str(batch),
        "id": key,
        "demo": bool(saved["demo"]),
        "settings": body.model_dump(mode="json"),
        "created": saved["created"],
        "coverage": public_coverage,
        "goal": goal_hunts.public(scope),
        "note": "Synthetic examples; no live offers."
        if saved["demo"]
        else "eBay search snapshot; seller text only, photos not analyzed. Availability may have changed. Prices exclude tax.",
        "results": [safe(r) for r in rows],
        "rescored": True,
    }


def search(actor, raw):
    store.verified(actor)
    body = hunt_settings(raw)
    config = evidence("hunt.json", None)
    if config is None:
        raise ValueError("Local hunt evidence unavailable")
    if body.continuation_batch:
        uuid.UUID(body.continuation_batch)
        prior = store.resource(actor, "hunts", (body.continuation_batch, 1))
        previous_body = saved_settings(json.loads(prior["request"]))
        previous = json.loads(prior["coverage"] or "{}")
        unchanged = all(
            getattr(body, key) == getattr(previous_body, key)
            for key in ("pool", "focus", "budget", "demo", "goal_id", "intent", "query")
        )
        if body.demo or not body.offset or body.offset != previous.get("next_offset") or not unchanged:
            raise ValueError("Start a new search after changing search settings")
        scope = previous.get("goal_scope")
        plan = previous.get("query_plan")
        if not isinstance(plan, list) or any(not isinstance(query, str) for query in plan):
            raise ValueError("Start a new search to continue this historical snapshot")
    else:
        if body.offset:
            raise ValueError("Continue from a saved search batch")
        scope = goal_hunts.snapshot(actor, body.goal_id)
        data = hunt_projection(actor, scope, body)
        plan = [body.query] if body.query else query_plan(data, config, body.pool, body.focus)
    if body.demo:
        if body.offset:
            raise ValueError("Samples have one batch")
        raws = evidence("demo_hunts.json", None)
        if raws is None:
            raise ValueError("Local sample evidence unavailable")
        coverage = {"queries_run": 0, "queries_total": len(plan), "offset": 0, "next_offset": None}
    else:
        if body.offset and body.offset >= len(plan):
            raise ValueError("No more queries in this search")
        queries = plan[
            body.offset : body.offset + min(ebay_hunts.MAX_QUERIES, max(1, int(config["query_limit"])))
        ]
        raws, provider = ebay_hunts.search(queries)
        coverage = {
            **provider,
            "queries_run": len(queries),
            "queries_total": len(plan),
            "offset": body.offset,
            "next_offset": body.offset + len(queries) if body.offset + len(queries) < len(plan) else None,
        }
    coverage["goal_scope"] = scope
    coverage["query_plan"] = plan
    batch = str(uuid.uuid4())
    saved = {
        "created": datetime.now(UTC).isoformat(),
        "demo": int(body.demo),
        "request": body.model_dump_json(),
        "raw": encode(raws),
        "coverage": encode(coverage),
    }
    try:
        # Validate and compare provider results before taking the short write lock.
        result = hunt_response(actor, saved, batch, 1)
    except (ValueError, TypeError, KeyError, AttributeError, IndexError, OverflowError) as exc:
        if body.demo:
            raise
        failure("ebay_response_failed", exc)
        raise ebay_hunts.LiveHuntError(
            "eBay returned listing data that could not be reviewed. Retry explicitly.", status=502
        ) from None
    save_hunt(actor, batch, saved)
    return result


@transaction.atomic
def save_hunt(actor, batch, saved):
    store.verified(actor)
    service.execute(
        "INSERT INTO import_batches VALUES(%s,%s,%s,%s,%s)",
        [batch, actor.user_id, batch, "b2-parity-hunt", "saved"],
    )
    service.execute(
        "INSERT INTO saved_hunts VALUES(%s,%s,1,%s,%s,%s,%s,%s)",
        [
            batch,
            actor.user_id,
            saved["created"],
            saved["demo"],
            saved["request"],
            saved["raw"],
            saved["coverage"],
        ],
    )
