"""Explicit CSRF-protected local text interpretation; GET only reads temporary state."""

from django.conf import settings
from django.views.decorators.http import require_GET, require_POST

from . import discovery_views, listing_interpretation, ollama_gateway, shopping, shopping_views
from .card_group_views import query
from .collection_views import body, endpoint


@endpoint
@require_GET
def readiness(request):
    discovery_views.principal(request)
    try:
        ollama_gateway.configuration(settings.ROOT)
        value = dict(
            configured=True,
            message="Local text analysis configured; model connectivity is checked only on explicit analysis.",
        )
    except ollama_gateway.Unavailable:
        value = dict(
            configured=False,
            message="Local listing analysis is not configured. Manual review remains available.",
        )
    return shopping_views.private_json(value, request)


@endpoint
@require_POST
def start(request):
    who, session = discovery_views.principal(request)
    raw = body(request)
    shopping.fields(raw, {"kind", "run_id", "result_id"}, {"kind", "run_id", "result_id"})
    return shopping_views.private_json(
        listing_interpretation.start(who, session, request.session.session_key, raw),
        request,
    )


@endpoint
@require_GET
def status(request, key):
    who, session = discovery_views.principal(request)
    query(request, set())
    return shopping_views.private_json(listing_interpretation.read(who, session, str(key)), request)


@endpoint
@require_POST
def stop(request, key):
    who, session = discovery_views.principal(request)
    if body(request):
        raise ValueError("Stop accepts no replacement content")
    return shopping_views.private_json(
        listing_interpretation.read(who, session, str(key), stop=True), request
    )
