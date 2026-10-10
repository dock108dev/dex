"""Authenticated, CSRF-protected shopping routes; listing URLs are never fetched."""

from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from . import lot_calculator as lot
from . import shopping
from .collection_views import body, endpoint
from .views import actor


def comparison_body(request):
    raw = body(request)
    shopping.fields(raw, {"inputs", "name", "save"}, {"inputs"})
    if "save" in raw and type(raw["save"]) is not bool:
        raise ValueError("Save must be a JSON boolean")
    return raw


@endpoint
@require_GET
def legacy(request):
    who = actor(request)
    return render(
        request,
        "beta/shopping.html",
        dict(research_enabled=shopping.available(), items=shopping.listing(who)),
    )


@endpoint
@require_GET
def home(request):
    who = actor(request)
    return render(
        request,
        "beta/lot_calculator.html",
        dict(
            research_enabled=shopping.available(),
            items=shopping.listing(who),
            wants=lot.locks(who, request.session),
        ),
    )


@endpoint
@require_GET
def lot_catalog(request):
    cards = lot.browse(actor(request), request.GET.get("q", ""))
    if request.GET.get("printing"):
        cards = [p for p in cards if p["id"] == request.GET["printing"]]
    offset = int(request.GET.get("offset", "0"))
    if not 0 <= offset <= 100000:
        raise ValueError("Invalid card page")
    return JsonResponse(dict(cards=cards[offset : offset + 40], total=len(cards), offset=offset))


@endpoint
@require_POST
def wanted(request):
    raw = body(request)
    shopping.fields(raw, {"wants"}, {"wants"})
    return JsonResponse(dict(wants=lot.locks(actor(request), request.session, raw["wants"])))


@endpoint
@require_POST
def lot_compare(request):
    raw = comparison_body(request)
    who = actor(request)
    payload = lot.prepare(who, raw["inputs"])
    if raw.get("save"):
        with shopping.transactions.atomic():
            key = shopping.store_payload(who, payload, raw.get("name", ""))
        payload["saved_url"] = f"/shopping/saved/{key}/"
    return JsonResponse(payload)


@endpoint
@require_GET
def catalog(request):
    data = shopping.browse(actor(request), dict(request.GET.items()))
    offset = int(request.GET.get("offset", "0"))
    if not 0 <= offset <= 100000:
        raise ValueError("Invalid card page")
    data["total"] = len(data["cards"])
    data["cards"] = data["cards"][offset : offset + 40]
    data["offset"] = offset
    return JsonResponse(data)


@endpoint
@require_POST
def compare(request):
    raw = comparison_body(request)
    payload = shopping.prepare(actor(request), raw["inputs"])
    if raw.get("save"):
        with shopping.transactions.atomic():
            key = shopping.store_payload(actor(request), payload, raw.get("name", ""))
        payload["saved_url"] = f"/shopping/saved/{key}/"
    return JsonResponse(payload)


@endpoint
@require_GET
def saved(request, key):
    who = actor(request)
    captured = shopping.reopen(who, str(key))
    modern = captured["schema"] == "dex-lot-v2"
    return render(
        request,
        "beta/lot_calculator.html" if modern else "beta/shopping.html",
        dict(
            captured=captured,
            research_enabled=shopping.available(),
            items=shopping.listing(who),
        ),
    )


@endpoint
@require_POST
def current(request, key):
    if set(request.POST) - {"csrfmiddlewaretoken"}:
        raise ValueError("Current evaluation uses the captured request")
    who = actor(request)
    return redirect(f"/shopping/saved/{shopping.reevaluate(who, str(key))}/")
