import json
from pathlib import Path

from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from . import catalog_imports as catalogs
from . import catalog_requests as service
from . import collection, store
from .collection_views import body, endpoint
from .views import actor


@endpoint
@require_GET
def home(request):
    who = actor(request)
    return render(request, "beta/catalog.html", {"admin": who.role == "owner", "review": False})


@endpoint
@require_GET
def review_home(request):
    catalogs.admin(actor(request))
    return render(request, "beta/catalog.html", {"admin": True, "review": True})


@endpoint
def requests(request):
    who = actor(request)
    if request.method == "POST":
        return JsonResponse(service.create(who, body(request)))
    if request.method != "GET":
        return HttpResponse(status=405)
    origins = [
        {"origin": "copy", "id": c["id"], "label": "Unidentified copy · " + (c["notes"] or c["id"])[:100]}
        for c in collection.copies(who)
        if not c["printing_id"]
    ]
    origins += [
        {"origin": "scan", "id": j["id"], "label": "Scan · " + j["state"] + " · " + j["id"]}
        for j in store.rows(
            "SELECT id,state FROM scan_jobs WHERE user_id=%s AND state NOT IN ('queued','processing','cancelled') ORDER BY created DESC LIMIT 40",
            [who.user_id],
        )
    ]
    return JsonResponse({"submissions": service.mine(who), "origins": origins})


@endpoint
@require_POST
def request_action(request, key, action):
    if action not in {"update", "resolve"}:
        raise ValueError("Unknown request action")
    return JsonResponse(getattr(service, action)(actor(request), str(key), body(request)))


@endpoint
@require_GET
def review(request):
    return JsonResponse({"requests": service.review_list(actor(request))})


@endpoint
@require_POST
def review_action(request, key):
    return JsonResponse({"requests": service.review(actor(request), str(key), body(request))})


@endpoint
@require_GET
def evidence(request, key, photo):
    content = service.shared_photo(actor(request), str(key), str(photo))
    return HttpResponse(
        content,
        content_type="image/jpeg",
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )


@endpoint
def imports(request):
    who = actor(request)
    catalogs.admin(who)
    if request.method == "POST":
        return JsonResponse(catalogs.preview(who, body(request)))
    if request.method != "GET":
        return HttpResponse(status=405)
    return JsonResponse(
        {
            "imports": [
                catalogs.get(who, r["id"])
                for r in store.rows("SELECT id FROM catalog_imports ORDER BY created DESC,id DESC")
            ]
        }
    )


@endpoint
@require_POST
def import_action(request, key, action):
    if body(request):
        raise ValueError("Publication uses the verified immutable preview")
    return JsonResponse(catalogs.transition(actor(request), str(key), action))


@endpoint
@require_GET
def package(request, name):
    catalogs.admin(actor(request))
    if name not in {"gym-heroes", "synthetic-orbits"}:
        raise Http404
    path = Path(__file__).resolve().parents[3] / "config" / "catalog-imports" / (name + ".json")
    return JsonResponse(json.loads(path.read_text()))
