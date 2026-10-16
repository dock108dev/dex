"""Private collection projections and spoiler-safe hunt reads."""

from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from . import ebay_hunts, parity
from .collection_views import body, endpoint
from .views import actor


@endpoint
@require_GET
def projection(request):
    return JsonResponse(parity.projection(actor(request)))


@endpoint
@require_http_methods(["GET", "POST"])
def hunts(request):
    who = actor(request)
    if request.method == "GET":
        return JsonResponse({"hunts": parity.history(who), "search_status": ebay_hunts.status()})
    # Historical reads remain available. Acquisition has one finite product route.
    response = JsonResponse(
        {"error": "Open Shopping to Find deals or Find missing cards.", "shopping_url": "/shopping/"},
        status=410,
    )
    response["Cache-Control"] = "private, no-store"
    return response


@endpoint
@require_GET
def saved(request, batch, key):
    return JsonResponse(parity.projected_hunt(actor(request), batch, key))


@endpoint
@require_POST
def reveal(request, batch, key, result):
    if body(request):
        raise ValueError("Reveal takes no replacement data")
    return JsonResponse(parity.projected_hunt(actor(request), batch, key, result))
