"""Vintage views and retained hunt reads projected from active session-owned copies."""

import json
from decimal import Decimal
from typing import Literal

from django.conf import settings
from django.http import Http404
from pydantic import Field, field_validator

from pokemon_hunter import hunt
from pokemon_hunter.collection import derive, totals
from pokemon_hunter.hunt import SearchRequest, public_listing
from pokemon_hunter.inventory import stable_id
from pokemon_hunter.valuation import valuation_records

from . import collection as service
from . import ebay_hunts, effective_collection, goal_hunts, hunt_values, store
from .diagnostics import failure


def evidence(filename, default):
    if filename not in {"market_values.json", "raw_values.json", "hunt.json"}:
        raise ValueError("Unsupported parity evidence; species identity uses canonical_species")
    if getattr(settings, "STAGING", False):
        # Source review permits metadata only. No legacy pricing or hunt redistribution.
        return default
    path = settings.ROOT / "parity-evidence" / filename
    return json.loads(path.read_text()) if path.is_file() else default


def projection(actor, *, include_presentation=True):
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
    printing_ids = {p["id"] for p in catalog}
    alias_ids = {}
    for p in catalog:
        alias_ids.setdefault(p["id"], set()).add(p["id"])
        alias_ids.setdefault("catalog-" + p["id"], set()).add(p["id"])
    for p in catalog:
        alias = json.loads(p["provenance"]).get("legacy_id")
        if alias:
            alias_ids.setdefault(alias, set()).add(p["id"])
    ambiguous_aliases = {key: sorted(ids) for key, ids in alias_ids.items() if len(ids) > 1}
    for p in catalog:
        legacy = json.loads(p["provenance"]).get("legacy_id")
        if legacy in ambiguous_aliases or (
            legacy and (legacy.startswith(("catalog-", "dg1-")) or legacy in printing_ids)
        ):
            legacy = None
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
    data["ambiguous_card_aliases"] = ambiguous_aliases
    if include_presentation:
        data["valuation"] = estimates(active, catalog)
    effective = effective_collection.project(actor, catalog=catalog, active=active)
    data["effective_collection"] = effective
    assertions = {row["id"]: row for row in effective["cards"]}
    for card in data["cards"].values():
        presence = effective["printings"][card["printing_id"]]
        card.update(
            effective_card_present=presence["present"],
            established_total_quantity=presence["established_total_quantity"],
            card_total_quantity=assertions[presence["card_ids"][0]]["established_total_quantity"],
            recorded_copy_count=presence["recorded_copy_count"],
            current_copy_owned=bool(presence["current_copy_ids"]),
            exact_printing_owned=presence["exact_printing_owned"],
            effective_identity_status=presence["identity_status"],
        )
    for key, item in data["pokedex"].items():
        item["qualified_copy_species_owned"] = item["dex_owned"]
        item["effective_species_present"] = effective["species"][key]["present"]
        item["collection_owned"] = item["effective_species_present"]
        item["dex_owned"] = item["effective_species_present"]
    # Acquisition/comparison needs current ownership and frozen-goal inputs, not
    # the overview's artwork, valuation or declaration presentation. Recompute
    # the same authorized ownership above; never cache private projections.
    if not include_presentation:
        return data
    from .ownership_declarations import summary

    declaration = summary(actor)
    declared_rows = [dict(row) for row in effective["declaration_rows"]]
    from . import image_bindings, image_mappings
    from .owned_artwork import reference_images

    images = reference_images(actor, catalog=catalog, active=active, effective=effective)
    card_images = image_bindings.catalog_images(actor, catalog)
    for card in data["cards"].values():
        card["reference_image"] = card_images.get(card["printing_id"])
    present_species = {int(n) for n, s in effective["species"].items() if s["present"]}
    data["owner_collection"] = dict(
        kanto=len(present_species.intersection(range(1, 152))),
        johto=len(present_species.intersection(range(152, 252))),
        total=len(present_species),
        active=effective["has_selected_source"],
        basis="effective-current-collection",
    )
    for key, item in data["pokedex"].items():
        item["artwork"] = image_mappings.species_artwork(int(key)) if image_bindings.enabled() else None
        item["declared_cards"] = [r for r in declared_rows if r["pokemon_dex"] == int(key)]
        item["reference_images"] = [r for r in images if r["pokemon_dex"] == int(key)]
        for row in item["declared_cards"]:
            row["reference_images"] = [
                r for r in item["reference_images"] if r["set_name"] == row["set_name"]
            ]
    data["ownership_declaration"] = declaration
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
