"""Authenticated, CSRF-protected shopping routes; listing URLs are never fetched."""

from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from . import lot_calculator as lot
from . import shopping, store
from .collection_views import body, endpoint
from .views import actor


def private_json(value):
    response = JsonResponse(value)
    response["Cache-Control"] = "no-store, private"
    return response


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
    goals = sorted(
        store.rows(
            "SELECT id,name,kind FROM collection_goals WHERE user_id=%s", [store.verified(who).user_id]
        ),
        key=lambda g: (g["kind"] != "original151_collection", bool(g.get("successor_ids")), g["name"]),
    )
    return render(
        request,
        "beta/lot_calculator.html",
        dict(
            research_enabled=shopping.available(),
            items=shopping.listing(who),
            wants=lot.locks(who, request.session),
            missing_goals=[dict(id=g["id"], name=g["name"]) for g in goals],
        ),
    )


@endpoint
@require_GET
def lot_catalog(request):
    who, goal = actor(request), request.GET.get("goal", "")
    if request.GET.get("wanted") == "1":
        ids = {w["printing_id"] for w in lot.locks(who, request.session)}
        printings = [p for p in lot.catalog(who, include_goals=True) if p["id"] in ids] if ids else []
        cards = lot.priced_cards(who, printings) if printings else []
        return private_json(dict(cards=cards, total=len(cards), offset=0, missing_items=[]))
    offset = int(request.GET.get("offset", "0"))
    if not 0 <= offset <= 100000:
        raise ValueError("Invalid card page")
    return private_json(
        lot.browse_page(
            who,
            request.GET.get("q", ""),
            goal_id=goal,
            item_id=request.GET.get("missing_item", ""),
            printing_id=request.GET.get("printing", ""),
            offset=offset,
            pick_first=request.GET.get("pick_first") == "1",
        )
    )


@endpoint
@require_GET
def source_status(request):
    """Non-price local status for removing revoked current-page derivatives."""
    from . import price_snapshots
    from .store import verified

    verified(actor(request))
    rows, status = price_snapshots.display_current()
    return private_json(
        dict(
            sources=sorted({row["_contract_sha256"] for row in rows}),
            versions=sorted({row["_snapshot_version"] for row in rows}),
            status=status,
        )
    )


@endpoint
@require_POST
def wanted(request):
    raw = body(request)
    shopping.fields(raw, {"wants"}, {"wants"})
    return private_json(dict(wants=lot.locks(actor(request), request.session, raw["wants"])))


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
    return private_json(payload)


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
    return private_json(data)


@endpoint
@require_POST
def compare(request):
    raw = comparison_body(request)
    payload = shopping.prepare(actor(request), raw["inputs"])
    if raw.get("save"):
        with shopping.transactions.atomic():
            key = shopping.store_payload(actor(request), payload, raw.get("name", ""))
        payload["saved_url"] = f"/shopping/saved/{key}/"
    return private_json(payload)


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
