"""Canonical card contracts: explicit guest metadata and reauthorized private reads."""

from urllib.parse import parse_qsl, urlsplit

from django.http import HttpResponseRedirect, JsonResponse
from django.views.decorators.http import require_GET, require_POST

from . import card_groups, collection, collection_views, store
from .collection_views import body, browsing_endpoint, endpoint
from .views import actor


def query(request, allowed=None):
    if any(len(values) != 1 for _, values in request.GET.lists()):
        raise ValueError("Choose each filter once")
    raw = request.GET.dict()
    if allowed is not None and set(raw) - allowed:
        raise ValueError("Unsupported query fields")
    return raw


def private(response, who=None):
    if who is not None:
        response = {**response, "account_id": store.verified(who).user_id}
    result = JsonResponse(response)
    result["Cache-Control"] = "private, no-store"
    return result


@browsing_endpoint
@require_GET
def catalog(request):
    who = actor(request)
    return private(card_groups.list_groups(who, query(request)), who)


@browsing_endpoint
@require_GET
def owned(request):
    raw = query(request)
    if "scope" in raw:
        raise ValueError("My Cards has a fixed owned scope")
    who = actor(request)
    return private(card_groups.list_groups(who, {**raw, "scope": "owned"}), who)


@browsing_endpoint
@require_GET
def filters(request):
    who = actor(request)
    return private(card_groups.filter_options(who, query(request, {"scope", "generation"})), who)


@browsing_endpoint
@require_GET
def detail(request, key):
    raw = query(request, {"child", "generation"})
    who = actor(request)
    result = card_groups.detail(who, key, selected_child=raw.get("child"))
    check_generation(raw, result)
    return private(result, who)


def check_generation(raw, result):
    if "generation" in raw:
        value = raw["generation"]
        if len(value) > 160 or not value.isascii() or not value.isdecimal():
            raise ValueError("Choose an integer collection generation")
        if int(value) != result["generation"]:
            raise collection.Conflict("Collection changed; reload")


@browsing_endpoint
@require_GET
def species(request, dex):
    who = actor(request)
    return private(
        card_groups.species(who, dex, query(request, card_groups.FILTERS - {"scope", "species"})), who
    )


@browsing_endpoint
@require_GET
def legacy(request, key):
    query(request, set())
    resolved = card_groups.resolve_destination(actor(request), key)
    response = HttpResponseRedirect(resolved["url"])
    response["Cache-Control"] = "private, no-store"
    return response


@browsing_endpoint
@require_GET
def home(request, key):
    raw = query(request, {"child", "generation", "return"})
    if "return" in raw:
        return_context(raw["return"])
    result = card_groups.detail(actor(request), key, selected_child=raw.get("child"))
    check_generation(raw, result)
    response = collection_views.private_home(request)
    response["Cache-Control"] = "private, no-store"
    return response


def return_context(value, *, list_only=False, _depth=0):
    """Validate UI-only return context without adding it to identity/API filters."""
    if (
        not isinstance(value, str)
        or len(value) > 4096
        or _depth > 2
        or value != value.strip()
        or any(ord(char) < 32 or ord(char) == 127 for char in value)
    ):
        raise ValueError("Choose a local card list return destination")
    parts = urlsplit(value)
    if parts.scheme or parts.netloc or parts.fragment:
        raise ValueError("Choose a supported local return destination")
    pairs = parse_qsl(parts.query, keep_blank_values=True, strict_parsing=True, max_num_fields=24)
    raw = dict(pairs)
    if any(ord(char) < 32 or ord(char) == 127 for key, value in pairs for char in key + value):
        raise ValueError("Choose supported return fields without control characters")
    if len(raw) != len(pairs):
        raise ValueError("Choose each supported return field once")
    from . import species_projection

    if parts.path == "/pokedex/":
        species_projection.list_state(raw)
    elif not list_only and parts.path.startswith("/card-groups/"):
        import re

        if not re.fullmatch(r"/card-groups/dg1-[0-9a-f]{64}/", parts.path):
            raise ValueError("Choose a canonical card return destination")
        if set(raw) - {"child", "generation", "return"}:
            raise ValueError("Choose supported card return fields")
        if "child" in raw and (not raw["child"] or len(raw["child"]) > 160 or not raw["child"].isascii()):
            raise ValueError("Choose a supported printing reference")
        if "generation" in raw:
            card_groups._integer(raw["generation"], "collection generation", 0, 2**53 - 1)
        if "return" in raw:
            nested = urlsplit(raw["return"])
            if nested.path.startswith("/card-groups/"):
                raise ValueError("Choose a card list or Pokémon return destination")
            return_context(raw["return"], _depth=_depth + 1)
    elif not list_only and parts.path.startswith("/pokedex/"):
        import re

        match = re.fullmatch(r"/pokedex/([1-9][0-9]{0,2})/", parts.path)
        if not match:
            raise ValueError("Choose a canonical Pokémon return destination")
        if not 1 <= int(match[1]) <= 251:
            raise ValueError("Choose a canonical Pokémon return destination")
        if set(raw) - {"goal", "scroll", "return"}:
            raise ValueError("Choose supported species return fields")
        species_projection.filters({"goal": raw.get("goal", "")})
        if "scroll" in raw:
            card_groups._integer(raw["scroll"], "scroll position", 0, 10000000)
        if "return" in raw:
            return_context(raw["return"], list_only=True, _depth=_depth + 1)
    elif not list_only and parts.path in {"/cards/", "/card-library/"}:
        if set(raw) - (card_groups.FILTERS - {"scope", "generation"} | {"scroll"}):
            raise ValueError("Choose each supported return field once")
        scroll = raw.pop("scroll", "0")
        card_groups._integer(scroll, "scroll position", 0, 10000000)
        card_groups._filters(raw, {"public": False})
    elif not list_only and parts.path == "/goals/" and not raw:
        pass
    elif not list_only and parts.path == "/shopping/":
        from . import discovery_catalog

        discovery_catalog.validate_page(raw)
        if "return" in raw:
            return_context(raw["return"], _depth=_depth + 1)
    else:
        raise ValueError("Choose My Cards, Card Library or Pokédex as the return destination")
    return value


@endpoint
@require_POST
def preview(request, key):
    query(request, set())
    raw = body(request)
    if set(raw) - {"kind", "request", "operation_id", "child"} or not {
        "kind",
        "request",
        "operation_id",
    } <= set(raw):
        raise ValueError("Use kind, request and operation_id")
    who = actor(request)
    literal = card_groups.mutation_request(
        who, key, raw["kind"], raw["request"], selected_child=raw.get("child")
    )
    return private(collection.preview(who, raw["kind"], literal, raw["operation_id"]))


def public_endpoint(fn):
    def inner(request, *args, **kwargs):
        try:
            response = JsonResponse(fn(request, *args, **kwargs))
        except ValueError:
            response = JsonResponse({"error": "Choose valid catalog filters."}, status=400)
        response["Cache-Control"] = "no-store"
        return response

    return require_GET(inner)


@public_endpoint
def public_catalog(request):
    return card_groups.list_groups(None, query(request))


@public_endpoint
def public_detail(request, key):
    raw = query(request, {"child"})
    return card_groups.detail(None, key, selected_child=raw.get("child"))
