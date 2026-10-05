from django.shortcuts import render
from django.views.decorators.http import require_GET

from .collection_views import endpoint
from .packs import project
from .views import actor


@endpoint
@require_GET
def home(request):
    return render(
        request,
        "beta/packs.html",
        project(
            actor(request),
            request.GET.get("goal", ""),
            request.GET.get("species", ""),
            request.GET.get("expansion", ""),
        ),
    )
