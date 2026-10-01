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
from . import store
from .diagnostics import failure
from .views import actor


def endpoint(fn):
    @wraps(fn)
    def inner(request, *args, **kwargs):
        try:
            return fn(request, *args, **kwargs)
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
            return JsonResponse({"error": "Invalid request. Check the fields and import format."}, status=400)

    return login_required(inner)


def body(request):
    try:
        data = json.loads(request.body)
    except (ValueError, UnicodeDecodeError):
        raise ValueError("Send a valid JSON object") from None
    if not isinstance(data, dict):
        raise ValueError("Send a JSON object")
    return data


@login_required
@require_GET
def home(request):
    actor(request)
    return render(
        request,
        "beta/b2.html",
        {
            "parity": settings.PARITY_ENABLED,
            "scans": settings.B3_ENABLED,
            "expansion": settings.B4_ENABLED,
            "staging": getattr(settings, "STAGING", False),
        },
    )


@require_GET
def asset(request, filename):
    if filename not in {"collection.js", "collection.css", "parity.js", "scans.js", "catalog.js"}:
        raise Http404
    return HttpResponse(
        (Path(__file__).parent / "static" / filename).read_text(),
        content_type="text/javascript" if filename.endswith(".js") else "text/css",
    )


@endpoint
@require_GET
def dashboard(request):
    who = actor(request)
    data = service.export_data(who)
    owned_ids = {c["printing_id"] for c in data["copies"]}
    data["printing_details"] = {
        p["id"]: {k: p[k] for k in ("set_name", "edition", "finish", "variant")}
        for p in service.catalog(who, include_archived=True)
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
