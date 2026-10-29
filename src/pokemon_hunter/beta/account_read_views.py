"""Independently authorized private V2 resources; never select accounts from input."""

from functools import wraps

from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.views.decorators.http import require_GET

from . import account_read_queries as reads
from .catalog_read_build import Unavailable
from .collection import Conflict
from .read_diagnostics import category, phase
from .read_diagnostics import json_response as JsonResponse
from .request_inputs import query
from .views import actor


def endpoint(service, **fixed):
    @wraps(service)
    @require_GET
    def view(request, **kwargs):
        try:
            if not request.user.is_authenticated:
                raise PermissionDenied
            principal = actor(request)
            expected = request.headers.get("X-Dex-Read-Account")
            if expected is not None and expected != principal.user_id:
                raise PermissionDenied
            with phase("service_ms"):
                result = service(principal, query(request), **fixed, **kwargs)
            category("catalog", "ready")
            category("account", "ready")
            response = JsonResponse(result, json_dumps_params={"ensure_ascii": False})
        except PermissionDenied:
            response = JsonResponse(dict(error="permission_denied"), status=403)
        except Http404:
            response = JsonResponse(dict(error="not_found"), status=404)
        except Unavailable:
            response = JsonResponse(
                dict(
                    error="read_state_unavailable",
                    code="read_state_unavailable",
                    retry="Explicit account/catalog preparation required.",
                ),
                status=503,
            )
        except Conflict:
            response = JsonResponse(
                dict(error="read_revision_changed", code="read_revision_changed"), status=409
            )
        except ValueError:
            response = JsonResponse(dict(error="Choose valid collection selectors."), status=400)
        response["Cache-Control"] = "private, no-store"
        if service is reads.resource and response.status_code == 200:
            response["Content-Disposition"] = 'attachment; filename="collection-record.json"'
        return response

    return view


def routes():
    from django.urls import path

    return [
        path("api/v2/" + route, endpoint(service, **fixed))
        for route, service, fixed in (
            ("card-groups/", reads.groups, {}),
            ("my-card-groups/", reads.groups, {"owned": True}),
            ("card-group-filters/", reads.options, {}),
            ("card-groups/<str:key>/", reads.detail, {}),
            ("card-groups/<str:key>/variants/", reads.variants, {}),
            ("card-groups/<str:key>/artwork/", reads.artwork, {}),
            ("card-groups/<str:key>/copies/", reads.copies, {}),
            ("card-groups/<str:key>/history/", reads.copies, {"history": True}),
            ("card-groups/<str:key>/evidence/", reads.evidence, {}),
            ("species/<int:dex>/card-groups/", reads.groups, {}),
            ("pokedex-species/", reads.species, {}),
            ("species-filter-options/", reads.species_options, {}),
            ("collection-context/", reads.context, {}),
            ("goal-options/", reads.goal_options, {}),
            ("goals/", reads.goal_workspace, {}),
            ("goals/<str:key>/", reads.goal_workspace, {}),
            ("goals/<str:key>/items/", reads.goal_items, {}),
            ("goal-sources/", reads.goal_sources, {}),
            ("labels/", reads.labels, {}),
            ("selected-groups/", reads.selected_groups, {}),
            ("group-artwork/", reads.group_artwork, {}),
            ("species-artwork/", reads.species_artwork, {}),
            ("binders/", reads.binders, {}),
            ("selection-groups/", reads.selection_groups, {}),
            ("entry-options/", reads.entry_options, {}),
            ("species/<int:dex>/owned-groups/", reads.species_owned_groups, {}),
            ("copies/<str:key>/photos/", reads.photos, {}),
            ("duplicate-counts/", reads.duplicates, {}),
            ("catalog/", reads.printings, {}),
            ("aliases/<str:key>/", reads.resolve, {}),
            ("catalog-unresolved/", reads.printings, {"unresolved": True}),
            ("evidence/", reads.evidence, {}),
            ("resources/<str:kind>/<str:key>/", reads.resource, {}),
        )
    ]
