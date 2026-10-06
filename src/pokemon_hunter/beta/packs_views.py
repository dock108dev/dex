from uuid import UUID

from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from . import offer_filters, pack_research
from .collection_views import endpoint
from .packs import project
from .views import actor


@endpoint
@require_GET
def home(request):
    context = project(
        actor(request),
        request.GET.get("goal", ""),
        request.GET.get("species", ""),
        request.GET.get("expansion", ""),
        filters={k: request.GET.get(k, "") for k in offer_filters.FIELDS},
    )
    context["research_enabled"] = pack_research.available()
    return render(request, "beta/packs.html", context)


@endpoint
@require_POST
def save(request):
    if set(request.POST) - {
        "csrfmiddlewaretoken",
        "goal",
        "goal_version",
        "species",
        "expansion",
        "name",
        *offer_filters.FIELDS,
    }:
        raise ValueError("Only selected scope and name are accepted")
    key = pack_research.save(
        actor(request),
        request.POST.get("goal", ""),
        request.POST.get("species", ""),
        request.POST.get("expansion", ""),
        request.POST.get("name", ""),
        request.POST.get("goal_version", ""),
        filters={k: request.POST.get(k, "") for k in offer_filters.FIELDS},
    )
    return redirect("saved-pack-research", key=UUID(str(key)))


@endpoint
@require_GET
def saved_list(request):
    return render(request, "beta/pack_research.html", {"items": pack_research.listing(actor(request))})


@endpoint
@require_GET
def saved(request, key):
    return render(request, "beta/packs.html", pack_research.reopen(actor(request), str(key)))


@endpoint
@require_POST
def rename(request, key):
    key = UUID(str(key))
    pack_research.rename(actor(request), str(key), request.POST.get("name", ""))
    return redirect("saved-pack-research", key=key)


@endpoint
@require_POST
def remove(request, key):
    pack_research.remove(actor(request), str(key))
    return redirect("/packs/saved/")
