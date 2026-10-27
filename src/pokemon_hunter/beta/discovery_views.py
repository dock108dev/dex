"""Private explicit discovery actions; reads, reveal and Stop never acquire listings."""

import json

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from . import (
    canonical_species,
    card_groups,
    discovery,
    discovery_catalog,
    image_bindings,
    navigation,
    shopping_context,
    shopping_views,
    store,
)
from .card_group_views import query
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
    who, _ = principal(request)
    raw = discovery_catalog.validate_page(query(request, discovery_catalog.PAGE_FIELDS))
    context = shopping_context.resolve(
        who, {key: value for key, value in raw.items() if key in shopping_context.FIELDS}
    )
    initial = dict(raw)
    if context.get("species") and "q" not in initial:
        initial["q"] = canonical_species.registry()[context["species"]]["name"]
    if context.get("group"):
        group = card_groups.detail(who, context["group"], selected_child=context.get("child"))["group"]
        initial.setdefault("q", group["name"] + " " + group["collector_number"])
        initial.setdefault("set_id", group["set_name"])
    if context["kind"] in {"goal", "missing"} or context.get("goal_version"):
        initial.setdefault("intent", "missing")
    initial, scope_note = discovery_catalog.entry_refinements(who, initial, context)
    response = render(
        request,
        "beta/discovery.html",
        {
            "discovery_goals": goals(who),
            "shopping_context": shopping_context.finish(who, context),
            "discovery_initial": initial,
            "discovery_scope_note": scope_note,
        },
    )
    response["Cache-Control"] = "private, no-store"
    response._dex_owned_artwork = image_bindings.enabled()
    response._dex_discovery_images = not getattr(settings, "STAGING", False)
    return response


@endpoint
@require_GET
def catalog(request):
    who, _ = principal(request)
    return shopping_views.private_json(
        discovery_catalog.search(who, query(request, discovery_catalog.CATALOG_FIELDS)), request
    )


@endpoint
@require_http_methods(["GET", "POST"])
def searches(request):
    who, session = principal(request)
    try:
        if request.method == "POST":
            value = discovery.start(who, session, body(request), auth_session=request.session.session_key)
        elif request.GET:
            raw = query(request, {"run_id"})
            if set(raw) != {"run_id"}:
                raise ValueError("Choose one discovery run")
            value = discovery.status(who, session, raw["run_id"])
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
