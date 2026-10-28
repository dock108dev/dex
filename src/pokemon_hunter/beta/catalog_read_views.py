"""Public V2 adapters; no account or provider data is consulted."""

from functools import wraps

from django.http import JsonResponse
from django.views.decorators.http import require_GET

from . import catalog_read_queries as reads
from .catalog_read_build import Unavailable
from .collection import Conflict
from .request_inputs import query


def endpoint(service):
    @wraps(service)
    @require_GET
    def view(request, **kwargs):
        try:
            response = JsonResponse(
                service(query(request), **kwargs), json_dumps_params={"ensure_ascii": False}
            )
        except Unavailable:
            response = JsonResponse(
                dict(
                    error="read_state_unavailable",
                    code="read_state_unavailable",
                    retry="Explicit catalog preparation required.",
                ),
                status=503,
            )
        except Conflict:
            response = JsonResponse(
                dict(error="catalog_revision_changed", code="catalog_revision_changed"), status=409
            )
        except ValueError:
            response = JsonResponse(dict(error="Choose valid catalog filters."), status=400)
        response["Cache-Control"] = "no-store"
        if service is reads.resource and response.status_code == 200:
            response["Content-Disposition"] = 'attachment; filename="catalog-record.json"'
        return response

    return view


def routes():
    from django.urls import path

    return [
        path("api/v2/public/" + route, endpoint(service))
        for route, service in (
            ("card-groups/", reads.groups),
            ("card-group-filters/", reads.options),
            ("card-groups/<str:key>/", reads.detail),
            ("card-groups/<str:key>/variants/", reads.variants),
            ("species/<int:dex>/card-groups/", reads.groups),
            ("pokedex-species/", reads.species),
            ("evidence/", reads.evidence),
            ("resources/<str:kind>/<str:key>/", reads.resource),
            ("aliases/<str:key>/", reads.resolve),
            ("catalog/", reads.printings),
            ("catalog-unresolved/", reads.unresolved_printings),
        )
    ]
