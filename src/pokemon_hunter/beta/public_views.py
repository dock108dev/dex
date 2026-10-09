"""Read-only guest entry points; personal collection routes remain authenticated."""

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from . import lookup as lookup_service
from . import offer_filters, public_catalog


@require_GET
def pokedex(request, dex=None):
    template = "beta/public_species.html" if dex is not None else "beta/public_pokedex.html"
    try:
        context = public_catalog.pokedex(request.GET.dict(), dex)
    except ValueError as exc:
        context = public_catalog.pokedex({}, dex)
        context["page_error"] = str(exc)
        return render(request, template, context, status=400)
    return render(request, template, context)


@require_GET
def hunt(request):
    return render(request, "beta/public_hunt.html", dict(public=True))


@require_GET
def catalog(request):
    try:
        context = public_catalog.pokedex(request.GET.dict())
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    return JsonResponse({"printings": context["cards"], "counts": context["counts"]})


@require_GET
def lookup(request):
    try:
        allowed = (lookup_service.FIELDS - {"goal"}) | set(offer_filters.FIELDS) | {"expansion"}
        if set(request.GET) - allowed:
            raise ValueError(
                "Public lookup accepts Pokémon and offer filters. Sign in to use saved goals or collection tools."
            )
        context = public_catalog.pack_lookup(
            {key: request.GET.get(key, "") for key in lookup_service.FIELDS},
            filters={key: request.GET.get(key, "") for key in offer_filters.FIELDS},
            expansion=request.GET.get("expansion", ""),
        )
    except ValueError as exc:
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
            page_error=str(exc),
        )
        return render(request, "beta/packs.html", context, status=400)
    return render(request, "beta/packs.html", context)
