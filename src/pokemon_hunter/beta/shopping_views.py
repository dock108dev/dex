"""Authenticated, CSRF-protected shopping routes; listing URLs are never fetched."""

from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from . import collection, shopping, shopping_context, store
from . import lot_calculator as lot
from .card_group_views import query
from .collection_views import body, endpoint
from .views import actor


def request_authority(request):
    """Optional page boundary checked before every explicit write or local read."""
    who = store.verified(actor(request))
    from .navigation import binding

    expected = request.headers.get("X-Dex-Shopping-Binding")
    if expected is not None and expected != binding(request)["navigation_binding"]:
        from django.core.exceptions import PermissionDenied

        raise PermissionDenied
    generation = request.headers.get("X-Dex-Shopping-Generation")
    if generation is not None:
        shopping_context.resolve(who, {"generation": generation})
    goal = request.headers.get("X-Dex-Shopping-Goal")
    version = request.headers.get("X-Dex-Shopping-Version")
    if goal is not None or version is not None:
        shopping_context.resolve(who, {"goal": goal or "", "version": version or ""})
    return who


def private_json(value, request):
    from .navigation import binding

    who = request_authority(request)
    value["authority"] = dict(
        account_id=who.user_id,
        generation=collection.generation(who),
        binding=binding(request)["navigation_binding"],
    )
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
    context = shopping_context.resolve(who, query(request, shopping_context.FIELDS))
    from .navigation import binding

    goals = sorted(
        store.rows(
            "SELECT id,name,kind,version FROM collection_goals WHERE user_id=%s",
            [store.verified(who).user_id],
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
            missing_goals=[dict(id=g["id"], name=g["name"], version=g["version"]) for g in goals],
            shopping_context=shopping_context.finish(who, context),
            shopping_binding=binding(request)["navigation_binding"],
        ),
    )


@endpoint
@require_GET
def lot_catalog(request):
    who = request_authority(request)
    # Draft resolution is a bounded GET with repeated printing IDs, never a write.
    if "restore" in request.GET:
        if set(request.GET) - {"restore", "generation"} or len(request.GET.getlist("generation")) > 1:
            raise ValueError("Choose a bounded draft restore")
        ids = request.GET.getlist("restore")
        if len(ids) > 200 or len(ids) != len(set(ids)) or any(not key or len(key) > 160 for key in ids):
            raise ValueError("Choose at most 200 distinct printing identities")
        context = shopping_context.resolve(
            who, {"generation": request.GET["generation"]} if "generation" in request.GET else {}
        )
        entries = [p for p in lot.catalog(who, include_goals=True, include_current=True) if p["id"] in ids]
        cards = lot.priced_cards(who, entries)
        return private_json(
            dict(
                cards=cards,
                context=shopping_context.finish(who, context),
                missing_ids=sorted(set(ids) - {p["id"] for p in entries}),
            ),
            request,
        )
    raw = query(
        request, shopping_context.FIELDS | {"q", "offset", "wanted", "missing_item", "printing", "pick_first"}
    )
    for field in ("q", "missing_item", "printing"):
        value = raw.get(field, "")
        if len(value) > 160 or any(ord(char) < 32 or ord(char) == 127 for char in value):
            raise ValueError("Choose bounded local card filters")
    for field in ("wanted", "pick_first"):
        if field in raw and raw[field] not in {"0", "1"}:
            raise ValueError("Choose a supported card selector mode")
    if "offset" in raw and (
        not raw["offset"]
        or not raw["offset"].isascii()
        or not raw["offset"].isdecimal()
        or len(raw["offset"]) > 6
    ):
        raise ValueError("Choose a bounded card page")
    context = shopping_context.resolve(
        who,
        {key: value for key, value in raw.items() if key in shopping_context.FIELDS},
        legacy_goal=not (raw.get("species") or raw.get("group")),
    )
    if raw.get("wanted") == "1":
        ids = {w["printing_id"] for w in lot.locks(who, request.session)}
        printings = (
            [p for p in lot.catalog(who, include_goals=True, include_current=True) if p["id"] in ids]
            if ids
            else []
        )
        cards = lot.priced_cards(who, printings) if printings else []
        data = dict(cards=cards, total=len(cards), offset=0, missing_items=[])
    else:
        offset = int(raw.get("offset", "0"))
        if not 0 <= offset <= 100000:
            raise ValueError("Invalid card page")
        if context["kind"] in {"species", "group", "printing"}:
            data = shopping_context.catalog(
                who, context, raw.get("q", ""), printing=raw.get("printing", ""), offset=offset
            )
        else:
            data = lot.browse_page(
                who,
                raw.get("q", ""),
                goal_id=raw.get("goal", ""),
                item_id=raw.get("missing_item", ""),
                printing_id=raw.get("printing", ""),
                offset=offset,
                pick_first=raw.get("pick_first") == "1",
                current_missing=context["kind"] == "missing",
            )
    data["context"] = shopping_context.finish(who, context)
    return private_json(data, request)


@endpoint
@require_GET
def source_status(request):
    """Non-price local status for removing revoked current-page derivatives."""
    from . import price_snapshots
    from .store import verified

    verified(request_authority(request))
    rows, status = price_snapshots.display_current()
    return private_json(
        dict(
            sources=sorted({row["_contract_sha256"] for row in rows}),
            versions=sorted({row["_snapshot_version"] for row in rows}),
            status=status,
            account_id=actor(request).user_id,
        ),
        request,
    )


@endpoint
@require_POST
def wanted(request):
    request_authority(request)
    raw = body(request)
    shopping.fields(raw, {"wants"}, {"wants"})
    return private_json(
        dict(
            wants=lot.locks(actor(request), request.session, raw["wants"]), account_id=actor(request).user_id
        ),
        request,
    )


@endpoint
@require_POST
def lot_compare(request):
    request_authority(request)
    raw = comparison_body(request)
    who = actor(request)
    payload = lot.prepare(who, raw["inputs"])
    if raw.get("save"):
        with shopping.transactions.atomic():
            key = shopping.store_payload(who, payload, raw.get("name", ""))
        payload["saved_url"] = f"/shopping/saved/{key}/"
    return private_json(payload, request)


@endpoint
@require_GET
def catalog(request):
    raw = query(
        request,
        {
            "q",
            "set",
            "goal",
            "missing",
            "edition",
            "variant",
            "value_edition",
            "condition",
            "grade",
            "grader",
            "value",
            "sort",
            "offset",
        },
    )
    offset = int(raw.pop("offset", "0"))
    if not 0 <= offset <= 100000:
        raise ValueError("Invalid card page")
    data = shopping.browse(actor(request), raw)
    data["total"] = len(data["cards"])
    data["cards"] = data["cards"][offset : offset + 40]
    data["offset"] = offset
    return private_json(data, request)


@endpoint
@require_POST
def compare(request):
    raw = comparison_body(request)
    payload = shopping.prepare(actor(request), raw["inputs"])
    if raw.get("save"):
        with shopping.transactions.atomic():
            key = shopping.store_payload(actor(request), payload, raw.get("name", ""))
        payload["saved_url"] = f"/shopping/saved/{key}/"
    return private_json(payload, request)


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
