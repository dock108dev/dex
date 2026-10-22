"""Private assisted checks; all provider acquisition requires explicit POST."""

from django.shortcuts import render
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from . import discovery_views, image_bindings, navigation, shopping, shopping_views
from . import listing_check as checks
from .card_group_views import query
from .collection_views import body, endpoint


@endpoint
@require_GET
def home(request):
    who, _ = discovery_views.principal(request)
    raw = query(request, {"discovery_run", "item_id", "return"})
    if bool(raw.get("discovery_run")) != bool(raw.get("item_id")):
        raise ValueError("Choose one checked temporary offer.")
    back = navigation.authorize_destination(who, raw["return"]) if raw.get("return") else "/shopping/"
    response = render(
        request,
        "beta/listing_check.html",
        dict(
            shopping_binding=navigation.binding(request)["navigation_binding"],
            account_id=who.user_id,
            listing_entry={key: raw[key] for key in ("discovery_run", "item_id") if key in raw},
            listing_return=back,
        ),
    )
    response["Cache-Control"] = "private, no-store"
    response._dex_discovery_images = image_bindings.enabled()
    return response


@endpoint
@require_GET
def candidate(request):
    who, session = discovery_views.principal(request)
    raw = query(request, {"discovery_run", "item_id"})
    if set(raw) != {"discovery_run", "item_id"}:
        raise ValueError("Choose one checked temporary offer.")
    return shopping_views.private_json(
        checks.candidate(who, session, raw["discovery_run"], raw["item_id"]), request
    )


@endpoint
@require_GET
def catalog(request):
    who, _ = discovery_views.principal(request)
    if "restore" in request.GET:
        keys = request.GET.getlist("restore")
        if set(request.GET) != {"restore"} or len(keys) > 200 or len(keys) != len(set(keys)):
            raise ValueError("Choose a bounded card restore.")
        if any(not key or len(key) > 160 for key in keys):
            raise ValueError("Choose supported card identities.")
        value = checks.catalog(who, restore=keys)
    else:
        raw = query(request, {"q"})
        term = raw.get("q", "")
        if len(term) > 160 or any(ord(char) < 32 or ord(char) == 127 for char in term):
            raise ValueError("Use a bounded local card search.")
        value = checks.catalog(who, term)
    return shopping_views.private_json(value, request)


@endpoint
@require_http_methods(["GET", "POST"])
def loads(request):
    who, session = discovery_views.principal(request)
    if request.method == "POST":
        raw = body(request)
        shopping.fields(raw, {"identifier"}, {"identifier"})
        result = checks.start(who, session, raw["identifier"], auth_session=request.session.session_key)
    else:
        if set(request.GET) != {"run_id"} or len(request.GET.getlist("run_id")) != 1:
            raise ValueError("Choose one listing load.")
        result = checks.status(who, session, request.GET["run_id"])
    return shopping_views.private_json(result, request)


@endpoint
@require_POST
def stop(request, run):
    who, session = discovery_views.principal(request)
    if body(request):
        raise ValueError("Stop takes no replacement data.")
    return shopping_views.private_json(checks.stop(who, session, str(run)), request)


@endpoint
@require_http_methods(["GET", "POST"])
def review(request):
    who, session = discovery_views.principal(request)
    raw = body(request) if request.method == "POST" else None
    if raw is not None:
        shopping.fields(raw, {"review", "lease"}, {"review", "lease"})
    return shopping_views.private_json(
        checks.review(who, session, raw["review"] if raw else None, raw["lease"] if raw else None), request
    )


@endpoint
@require_POST
def compare(request):
    who, session = discovery_views.principal(request)
    raw = body(request)
    shopping.fields(raw, {"review", "lease"}, {"review", "lease"})
    checks.review(who, session, raw["review"], raw["lease"])
    return shopping_views.private_json(checks.compare(who, raw["review"]), request)
