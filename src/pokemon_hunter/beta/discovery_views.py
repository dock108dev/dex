"""Private explicit discovery actions; reads, reveal and Stop never acquire listings."""

import json
import uuid

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from . import discovery, image_bindings, navigation, shopping_views, store
from .collection_views import body, endpoint


def principal(request):
    who = shopping_views.request_authority(request)
    return who, navigation.binding(request)["navigation_binding"]


def goals(who):
    rows = store.rows(
        "SELECT id,name,kind,version,definition FROM collection_goals WHERE user_id=%s ORDER BY name",
        [store.verified(who).user_id],
    )
    return [
        {
            **{k: row[k] for k in ("id", "name", "kind", "version")},
            "policy": json.loads(row["definition"])["policy"],
        }
        for row in rows
    ]


@endpoint
@require_GET
def home(request):
    # Existing collection entry links retain their checked selector and return context.
    if request.GET and set(request.GET) != {"run_id"}:
        return shopping_views.home(request)
    if "run_id" in request.GET:
        if len(request.GET.getlist("run_id")) != 1:
            raise ValueError("Choose one discovery run")
        uuid.UUID(request.GET["run_id"])
    who, _ = principal(request)
    response = render(request, "beta/discovery.html", {"discovery_goals": goals(who)})
    response["Cache-Control"] = "private, no-store"
    response._dex_owned_artwork = image_bindings.enabled()
    return response


@endpoint
@require_http_methods(["GET", "POST"])
def searches(request):
    who, session = principal(request)
    try:
        if request.method == "POST":
            value = discovery.start(who, session, body(request))
        elif request.GET:
            if set(request.GET) != {"run_id"} or len(request.GET.getlist("run_id")) != 1:
                raise ValueError("Choose one discovery run")
            value = discovery.status(who, session, request.GET["run_id"])
        else:
            value = {**discovery.metadata(who), "goals": goals(who)}
        return shopping_views.private_json(value, request)
    except RuntimeError:
        response = JsonResponse(
            {"error": "This search cannot continue. Start a new search after checking the current status."},
            status=409,
        )
        response["Cache-Control"] = "private, no-store"
        return response


@endpoint
@require_POST
def stop(request, run):
    who, session = principal(request)
    if body(request):
        raise ValueError("Stop takes no replacement data")
    return shopping_views.private_json(discovery.stop(who, session, str(run)), request)


@endpoint
@require_POST
def reveal(request, run, result):
    who, session = principal(request)
    if body(request):
        raise ValueError("Reveal takes no replacement data")
    return shopping_views.private_json(discovery.reveal(who, session, str(run), result), request)
