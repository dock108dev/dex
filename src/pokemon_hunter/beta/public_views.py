"""Read-only guest entry points; personal collection routes remain authenticated."""

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from . import lookup as lookup_service
from . import offer_filters, public_catalog
from .request_inputs import query


@require_GET
def hunt(request):
    return render(request, "beta/public_hunt.html", dict(public=True))


@require_GET
def catalog(request):
    try:
        context = public_catalog.pokedex(query(request, public_catalog.FILTERS))
    except ValueError:
        return JsonResponse({"error": "Choose valid, shorter catalog filters."}, status=400)
    return JsonResponse({"printings": context["cards"], "counts": context["counts"]})


@require_GET
def lookup(request):
    try:
        allowed = (lookup_service.FIELDS - {"goal"}) | set(offer_filters.FIELDS) | {"expansion"}
        raw = query(request, allowed)
        context = public_catalog.pack_lookup(
            {key: raw.get(key, "") for key in lookup_service.FIELDS},
            filters={key: raw.get(key, "") for key in offer_filters.FIELDS},
            expansion=raw.get("expansion", ""),
        )
    except ValueError:
        context = dict(
            public=True,
            lookup=True,
            supported=False,
            research_enabled=False,
            lookup_goals=[],
            lookup_request=dict(targets=request.GET.get("targets", ""), scope="all"),
            goal=dict(name="Selected Pokémon"),
            progress={},
            expansions=[],
            page_error="Choose valid Pokémon and offer filters. Sign in to use saved goals or collection tools.",
        )
        return render(request, "beta/packs.html", context, status=400)
    return render(request, "beta/packs.html", context)
