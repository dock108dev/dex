"""Private parity routes, including spoiler-safe replacements for B1 hunt reads."""

from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from . import parity
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
    return JsonResponse(
        {"hunts": parity.history(who)} if request.method == "GET" else parity.sample(who, body(request))
    )


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
