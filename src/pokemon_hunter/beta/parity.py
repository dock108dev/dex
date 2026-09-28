"""Vintage views projected from active session-owned copies; local evidence only."""

import json
import uuid
from datetime import UTC, datetime
from decimal import Decimal

from django.conf import settings
from django.http import Http404

from pokemon_hunter.app import SearchRequest
from pokemon_hunter.collection import derive, totals
from pokemon_hunter.hunt import project_results, public_listing, query_plan
from pokemon_hunter.inventory import stable_id
from pokemon_hunter.migration import encode
from pokemon_hunter.valuation import valuation_records

from . import collection as service
from . import store
from . import transactions as transaction


def evidence(filename, default):
    if getattr(settings, "STAGING", False):
        # Source review permits metadata only. No legacy pricing or hunt redistribution.
        if filename == "species.json":
            from .store import rows

            saved = rows("SELECT value FROM beta_operations WHERE key='species'")
            return json.loads(saved[0]["value"]) if saved else default
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
    species = evidence("species.json", {})
    # No ownership is loaded from the historical species evidence.
    dex = {
        str(n): {
            "dex_number": n,
            "name": species.get(str(n), {}).get("name", f"Species {n}"),
            "generation": 1 if n <= 151 else 2,
        }
        for n in range(1, 252)
    }
    cards = {}
    catalog = service.catalog(actor)
    for p in catalog:
        legacy = json.loads(p["provenance"]).get("legacy_id")
        if not legacy:
            legacy = "catalog-" + p["id"]
        copies = by_printing.get(p["id"], [])
        cards[legacy] = {
            **p["attributes"],
            "card_id": legacy,
            "printing_id": p["id"],
            "set_id": sets.get(p["set_id"], p["set_id"]),
            "set": p["set_name"],
            "number": p["collector_number"],
            "variant": p["variant"],
            "owned": bool(copies),
            "rarity": p["attributes"].get("rarity", "Unknown"),
            "supertype": p["attributes"].get("supertype", "Unknown"),
            "first_edition": any(c["first_edition_selected"] for c in copies),
            "copy_ids": [c["id"] for c in copies],
        }
        attrs = p["attributes"]
        n = attrs.get("pokemon_dex")
        if attrs.get("dex_eligible") and str(n) in dex and str(n) not in species:
            dex[str(n)]["name"] = attrs["name"]
    data = derive({"cards": cards, "pokedex": dex})
    data["totals"] = {**totals(data), "physical_copies": len(active)}
    data["catalog"] = catalog
    data["valuation"] = estimates(active, catalog)
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


def hunt_settings(raw):
    if set(raw) - {"pool", "focus", "budget", "demo", "offset"}:
        raise ValueError("Unsupported search settings")
    return SearchRequest.model_validate(raw)


def hunt_rows(actor):
    store.verified(actor)
    return store.rows(
        "SELECT * FROM saved_hunts WHERE user_id=%s ORDER BY created DESC,legacy_id DESC", [actor.user_id]
    )


def history(actor):
    return [
        {
            "batch": r["batch_id"],
            "id": r["legacy_id"],
            "created": r["created"],
            "demo": bool(r["demo"]),
            "settings": hunt_settings(json.loads(r["request"])).model_dump(mode="json"),
        }
        for r in hunt_rows(actor)
    ]


def projected_hunt(actor, batch, key, reveal=None):
    saved = store.resource(actor, "hunts", (str(batch), key))
    body = hunt_settings(json.loads(saved["request"]))
    data = projection(actor)
    config = evidence("hunt.json", None)
    if not config:
        raise ValueError("Local hunt evidence is unavailable in this environment")
    raws = json.loads(saved["raw"])
    # Opaque stable handles, never seller-controlled IDs or URLs in hidden responses.
    for index, raw in enumerate(raws):
        raw["itemId"] = stable_id("private-result", f"{actor.user_id}:{batch}:{key}:{index}")
    rows = project_results(raws, body, bool(saved["demo"]), data, config, evidence("raw_values.json", {}))

    def safe(row, revealed=False):
        public = public_listing(row, reveal=revealed)
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
    coverage = json.loads(saved["coverage"] or "{}")
    return {
        "batch": str(batch),
        "id": key,
        "demo": bool(saved["demo"]),
        "settings": body.model_dump(mode="json"),
        "created": saved["created"],
        "coverage": {
            k: v for k, v in coverage.items() if k in {"queries_run", "queries_total"} and type(v) is int
        },
        "note": "Synthetic examples; no live offers."
        if saved["demo"]
        else "Saved live snapshot; no new provider call. Availability may have changed.",
        "results": [safe(r) for r in rows],
        "rescored": True,
    }


@transaction.atomic
def sample(actor, raw):
    store.verified(actor)
    body = hunt_settings(raw)
    if not body.demo or body.offset:
        raise ValueError("Only local sample searches are enabled; live provider calls are not authorized")
    config = evidence("hunt.json", None)
    examples = evidence("demo_hunts.json", None)
    if config is None or examples is None:
        raise ValueError("Local sample evidence unavailable")
    plan = query_plan(projection(actor), config, body.pool, body.focus)
    batch = str(uuid.uuid4())
    service.execute(
        "INSERT INTO import_batches VALUES(%s,%s,%s,%s,%s)",
        [batch, actor.user_id, batch, "b2-parity-hunt", "saved"],
    )
    service.execute(
        "INSERT INTO saved_hunts VALUES(%s,%s,1,%s,1,%s,%s,%s)",
        [
            batch,
            actor.user_id,
            datetime.now(UTC).isoformat(),
            body.model_dump_json(),
            encode(examples),
            encode({"queries_run": 0, "queries_total": len(plan)}),
        ],
    )
    return projected_hunt(actor, batch, 1)
