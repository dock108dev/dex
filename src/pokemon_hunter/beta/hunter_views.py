"""Authenticated Hunter screen and finite, private local/action adapters."""

import json

from django.core.exceptions import PermissionDenied
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from . import (
    collection,
    discovery_matching,
    hunter,
    hunter_query,
    image_bindings,
    navigation,
    shopping,
    shopping_views,
    store,
)
from .card_group_views import query
from .collection_views import body, endpoint
from .discovery_views import principal


def _images(value, request):
    """Resolve checked printing identifiers through the existing image authority.

    This presentation-only pass never changes matching, references or result
    cursor/rank semantics. Descriptors must fit the established response bound;
    omitted artwork remains an ordinary neutral image slot in the client.
    """
    identities, reviews = [], []
    for row in value.get("results", []):
        if row.get("proposed_identity"):
            identities.append(row["proposed_identity"])
        identities.extend(row.get("identity_candidates", []))
    if "review_id" in value:
        reviews.append(value)
    reviews.extend(value.get("reviews", []))
    for review in reviews:
        for proposal in review.get("proposal", {}).get("proposals", []):
            identities.extend(proposal.get("candidates", []))
    if not identities and not reviews:
        return
    who = shopping_views.request_authority(request)
    generation = collection.generation(who)
    entries = collection.catalog(who, include_archived=True)
    by_id = {entry["id"]: entry for entry in entries}
    # Extra identity labels and artwork are optional presentation data. Leave
    # enough space for normal authority/omission metadata before enriching.
    available = hunter_query.RESPONSE_BYTE_LIMIT - len(json.dumps(value, ensure_ascii=True).encode()) - 4096
    omitted = False
    for review in reviews:
        cards = review.get("review", {}).get("cards", [])
        rows = []
        available -= 24
        for card in cards:
            if card["printing_id"] not in by_id:
                continue
            identity = shopping.identity(by_id[card["printing_id"]])
            size = len(json.dumps(identity, ensure_ascii=True).encode()) + 2
            if size > available:
                omitted = True
                continue
            rows.append(identity)
            available -= size
        review.setdefault("review", {})["card_identities"] = rows
        identities.extend(rows)
    ids = {identity.get("printing_id", identity.get("id")) for identity in identities}
    selected = [by_id[key] for key in ids if key in by_id]
    artwork = image_bindings.catalog_images(who, selected) if selected else {}
    for identity in identities:
        descriptor = artwork.get(identity.get("printing_id", identity.get("id")))
        if descriptor is None:
            continue
        size = len(json.dumps(dict(artwork=descriptor), ensure_ascii=True).encode())
        if size > available:
            omitted = True
            continue
        identity["artwork"] = descriptor
        available -= size
    if omitted:
        value["image_binding_status"] = (
            "Some card labels or references omitted to retain the bounded response; neutral spaces remain"
        )
    if collection.generation(who) != generation:
        raise collection.Conflict("Catalog changed while resolving Hunter images; reload")


def _private_json(value, request):
    _images(value, request)
    response = shopping_views.private_json(value, request)
    if len(response.content) > hunter_query.RESPONSE_BYTE_LIMIT:
        raise ValueError("Hunter response exceeds 2 MiB; select a smaller lot batch or refine contents")
    return response


@endpoint
@require_GET
def home(request):
    who, binding = principal(request)
    raw = query(request, {"run", "review", "return"})
    if any(len(value) > 1024 for value in raw.values()):
        raise ValueError("Choose bounded Hunter navigation")
    back = navigation.authorize_destination(who, raw["return"]) if raw.get("return") else "/shopping/"
    initial = dict(
        metadata=hunter.metadata(who, binding),
        authority=dict(account_id=who.user_id, generation=collection.generation(who), binding=binding),
        navigation={key: raw[key] for key in ("run", "review") if key in raw},
    )
    from . import hunter_profile

    initial["usage_settings"] = {
        "owner": hunter_profile.current() is None and store.verified(who).role == "owner"
    }
    if initial["usage_settings"]["owner"]:
        from . import hunter_policy

        initial["usage_settings"]["policy"] = hunter_policy.status(who)
    response = render(request, "beta/hunter.html", dict(hunter_initial=initial, hunter_return=back))
    response["Cache-Control"] = "private, no-store"
    response._dex_owned_artwork = image_bindings.enabled()
    return response


@endpoint
@require_http_methods(["GET", "POST"])
def usage(request):
    """Owner-selected ordinary usage; this route never starts acquisition."""
    from . import hunter_policy

    who, _ = principal(request)
    if store.verified(who).role != "owner":
        raise PermissionDenied
    if request.GET:
        raise ValueError("Usage settings take no replacement query fields")
    try:
        value = (
            hunter_policy.select(who, body(request))
            if request.method == "POST"
            else hunter_policy.status(who)
        )
    except (OSError, ValueError):
        response = _private_json(
            {
                "error": "Usage settings were not confirmed. Check availability to load the current settings, "
                "then choose whole-number limits, a timezone and a future expiry if needed. "
                "No marketplace search was started.",
                "code": "hunter_usage_unavailable",
            },
            request,
        )
        response.status_code = 400
        return response
    return _private_json(value, request)


@endpoint
@require_GET
def catalog(request):
    """Bounded all-era correction choices, including Trainer and Energy cards."""
    from . import hunter_lots

    who, _ = principal(request)
    raw = query(request, {"q"})
    term = raw.get("q", "")
    if len(term) > 160 or any(ord(char) < 32 or ord(char) == 127 for char in term):
        raise ValueError("Choose bounded local Hunter card filters")
    tokens = discovery_matching.literal(term).casefold().split()
    generation = collection.generation(who)
    entries = [
        p
        for p in hunter_lots._catalog(who)
        if not discovery_matching.unavailable(p)
        and all(
            token
            in " ".join(
                [p["name"], p["set_name"], p["collector_number"], p.get("variant_label", "")]
            ).casefold()
            for token in tokens
        )
    ]
    total, selected = len(entries), entries[:40]
    artwork = image_bindings.catalog_images(who, selected) if selected else {}
    value = dict(
        cards=[dict(shopping.identity(p), artwork=artwork.get(p["id"])) for p in selected], total=total
    )
    if collection.generation(who) != generation:
        raise collection.Conflict("Catalog changed while selecting Hunter corrections; reload")
    return _private_json(value, request)


@endpoint
@require_http_methods(["GET", "POST"])
def hunts(request):
    who, binding = principal(request)
    if request.method == "POST":
        value = hunter.start(who, binding, body(request), auth_session=request.session.session_key)
    elif request.GET:
        if set(request.GET) not in ({"run_id"}, {"run_id", "cursor"}) or any(
            len(request.GET.getlist(key)) != 1 for key in request.GET
        ):
            raise ValueError("Choose one Hunter run")
        try:
            value = hunter.status(
                who,
                binding,
                request.GET["run_id"],
                **({"cursor": request.GET["cursor"]} if "cursor" in request.GET else {}),
            )
        except hunter.InvalidResultCursor:
            response = _private_json(
                dict(
                    error="This local result cursor is no longer valid. Reload the first local page with current ranks.",
                    code="invalid_result_cursor",
                ),
                request,
            )
            response.status_code = 400
            return response
    else:
        value = hunter.metadata(who, binding)
    return _private_json(value, request)


@endpoint
@require_POST
def stop(request, run):
    who, binding = principal(request)
    if body(request):
        raise ValueError("Stop takes no replacement data")
    return _private_json(hunter.stop(who, binding, str(run)), request)


@endpoint
@require_POST
def continuation(request, run):
    who, binding = principal(request)
    return _private_json(hunter.continue_run(who, binding, str(run), body(request)), request)


@endpoint
@require_POST
def analyze_lots(request, run):
    from . import hunter_lots

    who, binding = principal(request)
    raw = body(request)
    if not isinstance(raw, dict) or set(raw) != {"result_ids"}:
        raise ValueError("Choose only the explicit selected lot result IDs")
    return _private_json(hunter_lots.selected_batch(who, binding, str(run), raw["result_ids"]), request)


@endpoint
@require_http_methods(["GET", "POST"])
def lot_review(request, review):
    from . import hunter_lots

    who, binding = principal(request)
    if request.GET:
        raise ValueError("Lot review takes no replacement query data")
    value = (
        hunter_lots.correct(who, binding, str(review), body(request))
        if request.method == "POST"
        else hunter_lots.read(who, binding, str(review))
    )
    return _private_json(value, request)


@endpoint
@require_POST
def lot_detail_intent(request, run):
    from . import hunter_lots

    who, binding = principal(request)
    raw = body(request)
    if not isinstance(raw, dict) or set(raw) != {"result_ids"}:
        raise ValueError("Choose only explicit lot result IDs for a future official detail plan")
    return _private_json(hunter_lots.detail_intent(who, binding, str(run), raw["result_ids"]), request)


@endpoint
@require_POST
def analyze_lot_details(request, run):
    from . import hunter_lot_details

    who, binding = principal(request)
    raw = body(request)
    if not isinstance(raw, dict) or set(raw) != {"result_ids"}:
        raise ValueError("Choose explicit lot result IDs for official details")
    return _private_json(hunter_lot_details.start(who, binding, str(run), raw["result_ids"]), request)


@endpoint
@require_http_methods(["GET"])
def lot_details_status(request, action):
    from . import hunter_lot_details

    who, binding = principal(request)
    if request.GET:
        raise ValueError("Detail status takes no replacement data")
    return _private_json(hunter_lot_details.status(who, binding, str(action)), request)


@endpoint
@require_POST
def lot_details_stop(request, action):
    from . import hunter_lot_details

    who, binding = principal(request)
    if body(request):
        raise ValueError("Stop takes no replacement data")
    return _private_json(hunter_lot_details.stop(who, binding, str(action)), request)
