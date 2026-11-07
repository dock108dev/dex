"""Private assisted checks; all provider acquisition requires explicit POST."""

from django.shortcuts import render
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from . import (
    discovery,
    discovery_views,
    image_bindings,
    navigation,
    price_snapshots,
    shopping,
    shopping_views,
    store,
)
from . import listing_check as checks
from .card_group_views import query
from .collection_views import body, endpoint


@endpoint
@require_GET
def home(request):
    who, _ = discovery_views.principal(request)
    raw = query(request, {"discovery_run", "item_id", "return", "request_id"})
    if raw.get("request_id"):
        import uuid

        uuid.UUID(raw["request_id"])
    if bool(raw.get("discovery_run")) != bool(raw.get("item_id")):
        raise ValueError("Choose one checked temporary offer.")
    back = navigation.authorize_destination(who, raw["return"]) if raw.get("return") else "/shopping/"
    response = render(
        request,
        "beta/listing_check.html",
        dict(
            shopping_binding=navigation.binding(request)["navigation_binding"],
            account_id=who.user_id,
            lot_usage_owner=store.verified(who).role == "owner",
            listing_entry={key: raw[key] for key in ("discovery_run", "item_id", "request_id") if key in raw},
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
        request_id = request.headers.get("X-Dex-Shopping-Action")
        result = (
            discovery.start_action(
                who, session, raw, request_id, auth_session=request.session.session_key, operation="detail"
            )
            if request_id
            else checks.start(who, session, raw["identifier"], auth_session=request.session.session_key)
        )
    else:
        raw = query(request, {"run_id", "request_id"})
        if set(raw) not in ({"run_id"}, {"request_id"}):
            raise ValueError("Choose one listing load.")
        result = (
            discovery.action_status(who, session, raw["request_id"], operation="detail")
            if "request_id" in raw
            else checks.status(who, session, raw["run_id"])
        )
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
    lease = request.headers.get("X-Dex-Review-Lease")
    if raw is None and lease is not None:
        with price_snapshots.read_only():
            return shopping_views.private_json(checks.review(who, session, lease=lease), request)
    return shopping_views.private_json(
        checks.review(who, session, raw["review"] if raw else None, raw["lease"] if raw else None), request
    )


@endpoint
@require_POST
def compare(request):
    raw = body(request)
    shopping.fields(raw, {"revision", "lease"}, {"revision", "lease"})
    return _assessment(request, raw["revision"], raw["lease"])


@endpoint
@require_GET
def return_assessment(request):
    with price_snapshots.read_only():
        return _assessment(
            request, request.headers.get("X-Dex-Review-Revision"), request.headers.get("X-Dex-Review-Lease")
        )


def _assessment(request, revision, lease):
    who, session = discovery_views.principal(request)
    result = checks.saved_comparison(who, session, revision, lease)
    return shopping_views.private_json(
        {key: result[key] for key in ("assessment", "benchmark") if key in result}, request
    )


@endpoint
@require_GET
def journal(request):
    who, session = discovery_views.principal(request)
    query(request, set())
    return shopping_views.private_json(checks.journal(who, session), request)
