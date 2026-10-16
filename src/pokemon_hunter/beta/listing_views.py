"""Private assisted checks; all provider acquisition requires explicit POST."""

from django.shortcuts import render
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from . import discovery_views, navigation, shopping, shopping_views
from . import listing_check as checks
from .collection_views import body, endpoint


@endpoint
@require_GET
def home(request):
    who, _ = discovery_views.principal(request)
    response = render(
        request,
        "beta/listing_check.html",
        dict(shopping_binding=navigation.binding(request)["navigation_binding"], account_id=who.user_id),
    )
    response["Cache-Control"] = "private, no-store"
    return response


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
