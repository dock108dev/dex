"""Ordinary independent lookup and frozen account-local saves, without acquisition."""

import json
from uuid import UUID

from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from . import collection_goals, lookup, offer_filters, pack_research
from .collection_views import endpoint
from .request_inputs import query, single_values
from .views import actor


@require_GET
def home(request):
    if not request.user.is_authenticated:
        from . import public_views

        return public_views.lookup(request)
    return private_home(request)


@endpoint
def private_home(request):
    who = actor(request)
    raw = query(request, lookup.FIELDS | set(offer_filters.FIELDS) | {"expansion"})
    context = lookup.project(
        who,
        {k: raw.get(k, "") for k in lookup.FIELDS},
        filters={k: raw.get(k, "") for k in offer_filters.FIELDS},
        expansion=raw.get("expansion", ""),
    )
    context["research_enabled"] = pack_research.available()
    from .collection import goals

    context["lookup_goals"] = goals(who)
    return render(request, "beta/packs.html", context)


@endpoint
@require_POST
def save(request):
    raw = single_values(
        request.POST,
        {
            "csrfmiddlewaretoken",
            *lookup.FIELDS,
            *offer_filters.FIELDS,
            "expansion",
            "scope_version",
            "name",
        },
    )
    context = lookup.project(
        actor(request),
        {k: raw.get(k, "") for k in lookup.FIELDS},
        filters={k: raw.get(k, "") for k in offer_filters.FIELDS},
        expansion=raw.get("expansion", ""),
    )
    if context["goal"]["version"] != raw.get("scope_version"):
        raise ValueError("Collection or catalog changed; review the lookup again")
    key = pack_research.store_context(actor(request), context, raw.get("name", ""))
    return redirect("saved-pack-research", key=UUID(str(key)))


@endpoint
@require_GET
def source(request, key):
    from django.http import JsonResponse

    row = collection_goals.source(actor(request), key)
    return JsonResponse(
        dict(collection_goals.reference(row), text=row["source_text"], rows=json.loads(row["reconciliation"]))
    )
