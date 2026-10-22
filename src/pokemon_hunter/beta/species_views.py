"""Finite canonical species boundary, independent of parity and private valuation."""

from urllib.parse import urlencode

from django.conf import settings
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET

from . import collection, collection_views, public_catalog, species_projection, species_scope
from .card_group_views import private, query, return_context
from .collection_views import endpoint
from .views import actor


def _redirect(target):
    if not target.startswith("/pokedex/") or not url_has_allowed_host_and_scheme(target, allowed_hosts=set()):
        raise ValueError("Choose a local Pokémon destination")
    response = HttpResponseRedirect(target)
    response["Cache-Control"] = "no-store"
    return response


@endpoint
@require_GET
def projection(request):
    try:
        who = actor(request)
        return private(
            species_projection.project(who, query(request, species_projection.FILTERS | {"generation"})), who
        )
    except collection.Conflict:
        return JsonResponse({"error": "Collection changed; reload the Pokémon view."}, status=409)
    except ValueError:
        return JsonResponse(
            {
                "error": "Choose valid Pokémon filters or context. A saved goal may be unavailable; review Goals."
            },
            status=400,
        )


def _species_context(raw):
    if set(raw) - {"goal", "version", "generation", "scroll", "return"}:
        raise ValueError("Choose supported species context")
    species_projection.filters({"goal": raw.get("goal", "")})
    from . import shopping_context

    shopping_context.validate_identity(
        {k: v for k, v in raw.items() if k in {"goal", "version", "generation"}}, legacy_goal=True
    )
    if "scroll" in raw:
        from . import card_groups

        card_groups._integer(raw["scroll"], "scroll position", 0, 10000000)
    if "return" in raw:
        return_context(raw["return"], list_only=True)
    return raw


@require_GET
def home(request, dex=None):
    """One canonical route: private collection view or allowlisted published metadata."""
    if dex is not None:
        species_projection.require_dex(dex)
    try:
        raw = query(request)
        legacy = raw.pop("species", None) if dex is None else None
        if legacy is not None:
            from . import card_groups

            number = card_groups._integer(legacy, "Pokémon number", 1, 251)
            species_projection.list_state(raw)
            if raw.get("region") in {"all", "1", "2"}:
                raw["region"] = {"all": "", "1": "kanto", "2": "johto"}[raw["region"]]
                if not raw["region"]:
                    raw.pop("region")
            context = {"return": "/pokedex/" + ("?" + urlencode(raw) if raw else "")}
            if raw.get("goal"):
                context["goal"] = raw["goal"]
            return _redirect(f"/pokedex/{number}/?" + urlencode(context))
        if dex is None:
            species_projection.list_state(raw)
        else:
            _species_context(raw)
        if dex is None and raw.get("region") in {"all", "1", "2"}:
            region = {"all": "", "1": "kanto", "2": "johto"}[raw["region"]]
            normalized = {**raw, "region": region}
            if not region:
                normalized.pop("region")
            return _redirect("/pokedex/" + ("?" + urlencode(normalized) if normalized else ""))
        if dex is not None and request.path != f"/pokedex/{dex}/":
            return _redirect(f"/pokedex/{dex}/" + ("?" + urlencode(raw) if raw else ""))
        if settings.B2_ENABLED and request.user.is_authenticated:
            who = actor(request)
            if raw.get("goal"):
                species_projection._scope(who, raw["goal"])
            if dex is not None:
                from . import navigation

                navigation.authorize_destination(who, request.get_full_path())
            return collection_views.private_home(request)
        # Public consumers never acquire private fields or ownership from missing fields.
        if raw.get("goal") or raw.get("owned") not in {None, "", "all"}:
            raise ValueError("Sign in to use saved goals and current collection status")
        guest_allowed = public_catalog.FILTERS | {"scroll", "focus"} if dex is None else {"scroll", "return"}
        if set(raw) - guest_allowed:
            raise ValueError("Choose supported published Pokémon filters. Sign in for collection tools.")
        if any(raw.get(key, "").startswith("[") for key in species_scope.MULTI):
            raise ValueError("Sign in to evaluate multiselect card scopes")
        public_raw = {key: value for key, value in raw.items() if key in public_catalog.FILTERS}
        context = public_catalog.pokedex(public_raw, dex)
        context["return_url"] = raw.get("return") or "/pokedex/"
        for row in context["species"]:
            list_fields = {**raw, "focus": str(row["dex"])}
            row["url"] = f"/pokedex/{row['dex']}/?" + urlencode(
                {"return": "/pokedex/?" + urlencode(list_fields)}
            )
        return render(
            request, "beta/public_species.html" if dex is not None else "beta/public_pokedex.html", context
        )
    except collection.Conflict:
        return JsonResponse(
            {"error": "Collection or saved goal changed; reopen the Pokémon view."}, status=409
        )
    except ValueError:
        return render(
            request,
            "beta/species_error.html",
            {
                "page_error": "Choose valid Pokémon filters or context. A saved goal may be unavailable; review Goals."
            },
            status=400,
        )
