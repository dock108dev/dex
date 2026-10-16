"""Session-authorized collection routes; no client identity is used as authorization."""

import json
from functools import wraps
from pathlib import Path

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST
from pydantic import ValidationError

from . import collection as service
from . import image_bindings, store
from .diagnostics import failure
from .views import actor

BROWSING_ERROR = "Invalid browsing filters or return link. Go back or open My Cards at /cards/."


def endpoint(fn, *, browsing=False):
    @wraps(fn)
    def inner(request, *args, **kwargs):
        try:
            return fn(request, *args, **kwargs)
        except service.ReviewConflict as e:
            failure("request_review_conflict", e)
            return JsonResponse(
                {"error": service.REVIEW_CONFLICT_MESSAGES.get(e.code, service.REVIEW_CONFLICT_DEFAULT)},
                status=409,
            )
        except service.Conflict as e:
            failure("request_conflict", e)
            return JsonResponse(
                {
                    "error": "The operation conflicts with the current state. Reload and create a fresh preview."
                },
                status=409,
            )
        except ValidationError:
            # Pydantic messages include input values; do not echo private payloads.
            return JsonResponse({"error": "Invalid request fields; check the required format"}, status=400)
        except TypeError as e:
            failure("request_type_error", e)
            return JsonResponse({"error": "Invalid request field types"}, status=400)
        except ValueError as e:
            failure("request_value_error", e)
            if browsing:
                response = JsonResponse({"error": BROWSING_ERROR, "recovery_url": "/cards/"}, status=400)
                response["Cache-Control"] = "private, no-store"
                return response
            return JsonResponse({"error": "Invalid request. Check the fields and import format."}, status=400)

    return login_required(inner)


def browsing_endpoint(fn):
    """Opt-in read-only browsing guidance; mutation/import contracts stay unchanged."""
    return endpoint(fn, browsing=True)


def body(request):
    if request.content_type != "application/json":
        raise ValueError("Send an application/json request")
    try:
        data = json.loads(request.body)
    except (ValueError, UnicodeDecodeError):
        raise ValueError("Send a valid JSON object") from None
    if not isinstance(data, dict):
        raise ValueError("Send a JSON object")
    return data


@require_GET
def home(request, key=None):
    if request.path == "/":
        from .navigation import home as navigation_home

        return navigation_home(request)
    if not request.user.is_authenticated and request.path == "/hunt/":
        from . import public_views

        return public_views.hunt(request)
    return private_home(request)


@login_required
def private_home(request):
    actor(request)
    response = render(
        request,
        "beta/b2.html",
        {
            "parity": settings.PARITY_ENABLED,
            "scans": settings.B3_ENABLED,
            "expansion": settings.B4_ENABLED,
            "staging": getattr(settings, "STAGING", False),
        },
    )
    response._dex_owned_artwork = image_bindings.enabled()
    return response


@require_GET
def asset(request, filename):
    if filename not in {
        "collection.js",
        "bulk_entry.js",
        "bulk_entry.css",
        "photo_batches.js",
        "photo_batches.css",
        "navigation.js",
        "card-screens.js",
        "species-screens.js",
        "shopping.js",
        "listing_check.js",
        "listing_check.css",
        "discovery.js",
        "discovery.css",
        "lot_calculator.js",
        "lot_calculator.css",
        "shopping.css",
        "collection.css",
        "collection-base.css",
        "collection-browse.css",
        "parity.js",
        "scans.js",
        "catalog.js",
        "pokedex.js",
        "glass.css",
        "public.css",
        "public-species.js",
    }:
        raise Http404
    return HttpResponse(
        (Path(__file__).parent / "static" / filename).read_text(),
        content_type="text/javascript" if filename.endswith(".js") else "text/css",
    )


@browsing_endpoint
@require_GET
def context(request):
    """Small browsing authority; inventories and tool data load only on demand."""
    if request.GET:
        raise ValueError("Browsing context accepts no query fields")
    who = actor(request)
    generation = service.generation(who)
    result = {
        "context_only": True,
        "effective_collection": {"user_id": who.user_id, "generation": generation, "cards": []},
        "binders": service.binders(who),
        "copies": store.rows(
            "SELECT id,printing_id FROM owned_copies WHERE user_id=%s AND state='active' ORDER BY id",
            [who.user_id],
        ),
        "goals": store.rows(
            "SELECT id,name,version FROM collection_goals WHERE user_id=%s ORDER BY name,id", [who.user_id]
        ),
    }
    store.verified(who)
    if service.generation(who) != generation:
        raise service.Conflict("Collection changed while loading browsing context")
    response = JsonResponse(result)
    response["Cache-Control"] = "private, no-store"
    return response


@endpoint
@require_GET
def dashboard(request):
    who = actor(request)
    data = service.export_data(who)
    from .ownership_declarations import summary

    data["ownership_declaration"] = summary(who)
    from . import collection_goals

    data["current_collection_source"] = (
        collection_goals.reference(collection_goals.latest(who)) if collection_goals.latest(who) else None
    )
    data["available_collection_sources"] = [
        dict(collection_goals.reference(r), owned=len(collection_goals.owned(r)))
        for r in collection_goals.sources(who)
    ]
    owned_ids = {c["printing_id"] for c in data["copies"]}
    from . import image_bindings

    entries = service.catalog(who, include_archived=True)
    from .effective_collection import project

    data["effective_collection"] = project(who, catalog=entries, active=data["copies"])
    data["current_collection_source"] = data["effective_collection"]["selected_source"]
    images = image_bindings.catalog_images(who, entries)
    photos = image_bindings.private_copy_photos(who, [c["id"] for c in data["copies"]])
    display_identities = {
        cid: {k: row[k] for k in ("set_name", "name", "number")}
        for row in data["effective_collection"]["cards"]
        if row["identity_status"] != "conflict"
        for cid in row["recorded_copy_ids"]
    }
    data["copies"] = [
        dict(
            c,
            photo_references=photos[c["id"]],
            **(
                {"display_identity": display_identities[c["id"]]}
                if not c["printing_id"] and c["id"] in display_identities
                else {}
            ),
        )
        for c in data["copies"]
    ]
    data["printing_details"] = {
        p["id"]: {
            **{k: p[k] for k in ("set_name", "edition", "finish", "variant")},
            "reference_image": images.get(p["id"]),
        }
        for p in entries
        if p["id"] in owned_ids
    }
    data["sets"] = store.rows(
        "SELECT id,game_id,name,coverage_status,catalog_version FROM catalog_sets "
        + ("WHERE publication_state='published' " if settings.B4_ENABLED else "")
        + "ORDER BY name"
    )
    data["operations"] = store.rows(
        "SELECT id,kind,state,created FROM collection_operations WHERE user_id=%s ORDER BY created DESC,id DESC LIMIT 40",
        [who.user_id],
    )
    entries = service.catalog(who)
    game_ids = {p["game_id"] for p in entries}
    data["goal_options"] = {
        "games": [
            g for g in store.rows("SELECT id,game_key,name FROM games ORDER BY name") if g["id"] in game_ids
        ],
        "card_types": sorted({p["attributes"].get("supertype") or "Unknown" for p in entries}),
        "rarities": sorted({p["attributes"].get("rarity") or "Unknown" for p in entries}),
        "pokemon_dex_max": 251,
    }
    return JsonResponse(data)


@endpoint
@require_GET
def catalog(request):
    return JsonResponse(
        {"printings": service.catalog(actor(request), request.GET.get("q", ""), request.GET.get("set", ""))}
    )


@endpoint
@require_GET
def binders(request):
    return JsonResponse({"binders": service.binders(actor(request))})


@endpoint
@require_GET
def binder(request, key):
    return JsonResponse(service.one(actor(request), "binder", key))


@endpoint
@require_GET
def goals(request):
    return JsonResponse({"goals": service.goals(actor(request))})


@endpoint
@require_GET
def goal(request, key):
    service.one(actor(request), "goal", key)
    return JsonResponse(next(g for g in service.goals(actor(request)) if g["id"] == key))


@endpoint
@require_GET
def copy_detail(request, key):
    return JsonResponse(service.one(actor(request), "copy", key))


@endpoint
@require_GET
def export(request):
    response = JsonResponse(service.export_data(actor(request)))
    response["Content-Disposition"] = 'attachment; filename="dex-collection-v2.json"'
    return response


@endpoint
@require_POST
def preview(request):
    data = body(request)
    if set(data) != {"kind", "request", "operation_id"}:
        raise ValueError("Expected kind, request and operation_id only")
    return JsonResponse(service.preview(actor(request), data["kind"], data["request"], data["operation_id"]))


@endpoint
@require_GET
def operation(request, key):
    return JsonResponse(service.operation(actor(request), key))


@endpoint
@require_POST
def confirm(request, key):
    if body(request):
        raise ValueError("Confirmation uses the stored preview; no replacement fields allowed")
    return JsonResponse(service.confirm(actor(request), key))


@endpoint
@require_POST
def undo(request, key):
    if body(request):
        raise ValueError("Undo uses the stored operation; no replacement fields allowed")
    return JsonResponse(service.undo(actor(request), key))
