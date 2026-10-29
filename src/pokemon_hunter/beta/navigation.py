"""Finite, read-only collection navigation; storage never conveys account authority."""

from urllib.parse import parse_qsl, urlsplit

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import render
from django.utils.crypto import salted_hmac
from django.views.decorators.http import require_GET

from . import collection_views, species_projection, store
from .card_group_views import check_generation, query, return_context
from .collection_views import browsing_endpoint
from .views import actor


def binding(request):
    """Opaque authority boundary changes with installation, account and auth session."""
    if not request.user.is_authenticated or not settings.B2_ENABLED:
        return {"navigation_account_id": "", "navigation_binding": ""}
    try:
        principal = store.verified(actor(request)).user_id
    except PermissionDenied:
        return {"navigation_account_id": "", "navigation_binding": ""}
    session = request.session.session_key
    if not session:
        return {"navigation_account_id": "", "navigation_binding": ""}
    token = salted_hmac(
        "dex.cx07.navigation", f"{settings.ROOT}\0{principal}\0{session}", algorithm="sha256"
    ).hexdigest()
    return {"navigation_account_id": principal, "navigation_binding": token}


def context(request):
    """Section-aware header semantics; query strings do not select extra menus."""
    path = request.path
    section = ""
    if path.startswith("/pokedex/"):
        section = "pokedex"
    elif path.startswith(("/shopping/", "/packs/", "/lookup/")) or path in {"/hunt/", "/missing/", "/finds/"}:
        section = "shopping"
    elif path in {"/cards/", "/card-library/"} or path.startswith("/card-groups/"):
        section = "cards"
        if path.startswith("/card-groups/"):
            try:
                back = return_context(request.GET.get("return", "/cards/"))
                if urlsplit(back).path.startswith("/pokedex/"):
                    section = "pokedex"
                elif urlsplit(back).path == "/card-library/":
                    section = "library"
            except ValueError:
                pass
    elif path in {"/collection-tools/", "/collection/", "/goals/", "/overview/"}:
        section = "cards"
    elif path != "/":
        section = "tools"
    if path == "/card-library/":
        section = "library"
    result = {**binding(request), "navigation_section": section}
    result.update(
        parity=settings.PARITY_ENABLED,
        scans=settings.B3_ENABLED,
        expansion=settings.B4_ENABLED,
        navigation_group=(
            "collection"
            if section == "cards"
            else "shopping"
            if section == "shopping"
            else "settings"
            if path in {"/settings/", "/requests/", "/catalog-coverage/"}
            else "administration"
            if path.startswith(
                ("/administration/", "/catalog-review/", "/catalog-pipeline/", "/product-review/")
            )
            else ""
        ),
    )
    if request.user.is_authenticated and settings.B2_ENABLED:
        try:
            result["admin"] = store.verified(actor(request)).role == "owner"
        except PermissionDenied:
            result["admin"] = False
    return result


@browsing_endpoint
@require_GET
def task_home(request):
    """Read-only entry points reuse existing workflows and their authorization."""
    who = store.verified(actor(request))
    if request.path == "/administration/" and who.role != "owner":
        raise PermissionDenied
    titles = {
        "/collection-tools/": "Collection tools",
        "/add-card/": "Add Card",
        "/administration/": "Administration",
    }
    from . import photo_batches

    response = render(
        request,
        "beta/task_home.html",
        {"task_title": titles[request.path], "photo_batches": photo_batches.available()},
    )
    response["Cache-Control"] = "private, no-store"
    return response


def authorize_destination(who, value):
    """Recheck every referenced private object in the bounded return chain."""
    value = return_context(value)
    parts = urlsplit(value)
    raw = dict(parse_qsl(parts.query, keep_blank_values=True, strict_parsing=True, max_num_fields=24))
    store.verified(who)
    if raw.get("goal"):
        species_projection.authorize_goal(who, raw["goal"], raw.get("version"))
    if parts.path.startswith("/card-groups/"):
        from . import account_read_queries

        result = account_read_queries.detail(
            who, {k: v for k, v in raw.items() if k in {"child", "generation"}}, key=parts.path.split("/")[2]
        )
        check_generation(raw, result)
        if result.get("public") is not False:
            raise ValueError("This collection destination is unavailable")
    if (
        parts.path == "/shopping/"
        or parts.path in {"/cards/", "/card-library/"}
        or (parts.path.startswith("/pokedex/") and parts.path != "/pokedex/")
    ):
        from . import shopping_context

        shopping_context.resolve(
            who,
            {key: value for key, value in raw.items() if key in shopping_context.FIELDS and key != "return"},
            legacy_goal=parts.path != "/shopping/",
        )
    if "return" in raw:
        authorize_destination(who, raw["return"])
    return value


@require_GET
def home(request):
    """Guests browse normally; authenticated root resolves optional browser memory."""
    if not request.user.is_authenticated:
        from . import species_views

        response = species_views.home(request)
    else:
        response = collection_views.private_home(request)
    response["Cache-Control"] = "private, no-store" if request.user.is_authenticated else "no-store"
    return response


@browsing_endpoint
@require_GET
def validate_home(request):
    """Read-only reauthorization before reopening optional remembered UI context."""
    raw = query(request, {"destination"})
    value = raw.get("destination", "/cards/")
    if urlsplit(value).path in {"/goals/", "/shopping/"}:
        raise ValueError("Choose a card or Pokémon home destination")
    destination = authorize_destination(actor(request), value)
    bound = binding(request)
    result = JsonResponse({"destination": destination, "account_id": bound["navigation_account_id"], **bound})
    result["Cache-Control"] = "private, no-store"
    return result
