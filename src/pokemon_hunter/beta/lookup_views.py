"""Ordinary independent lookup and frozen account-local saves, without acquisition."""

import json

from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from . import collection_goals, lookup, offer_filters, pack_research
from .collection_views import endpoint
from .views import actor


@endpoint
@require_GET
def home(request):
    who = actor(request)
    raw = {k: request.GET.get(k, "") for k in lookup.FIELDS}
    context = lookup.project(
        who,
        raw,
        filters={k: request.GET.get(k, "") for k in offer_filters.FIELDS},
        expansion=request.GET.get("expansion", ""),
    )
    context["research_enabled"] = pack_research.available()
    from .collection import goals

    context["lookup_goals"] = goals(who)
    return render(request, "beta/packs.html", context)


@endpoint
@require_POST
def save(request):
    if set(request.POST) - {
        "csrfmiddlewaretoken",
        *lookup.FIELDS,
        *offer_filters.FIELDS,
        "expansion",
        "scope_version",
        "name",
    }:
        raise ValueError("Unsupported saved lookup fields")
    context = lookup.project(
        actor(request),
        {k: request.POST.get(k, "") for k in lookup.FIELDS},
        filters={k: request.POST.get(k, "") for k in offer_filters.FIELDS},
        expansion=request.POST.get("expansion", ""),
    )
    if context["goal"]["version"] != request.POST.get("scope_version"):
        raise ValueError("Collection or catalog changed; review the lookup again")
    key = pack_research.store_context(actor(request), context, request.POST.get("name", ""))
    return redirect(f"/packs/saved/{key}/")


@endpoint
@require_GET
def source(request, key):
    from django.http import JsonResponse

    row = collection_goals.source(actor(request), key)
    return JsonResponse(
        dict(collection_goals.reference(row), text=row["source_text"], rows=json.loads(row["reconciliation"]))
    )
