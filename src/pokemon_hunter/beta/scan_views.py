import time

from django.conf import settings
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from . import scans, store
from .collection_views import body, endpoint
from .views import actor


@endpoint
@require_GET
def home(request):
    actor(request)
    return render(
        request, "beta/scans.html", {"mode": scans.config()["mode"], "expansion": settings.B4_ENABLED}
    )


@endpoint
def jobs(request):
    who = actor(request)
    if request.method == "POST":
        if int(request.META.get("CONTENT_LENGTH") or 0) > 16_100_000:
            raise ValueError("Upload exceeds the two-image size limit")
        if set(request.FILES) - {"front", "back"} or "front" not in request.FILES:
            raise ValueError("A front image is required; a back or close-up is optional")
        if any(len(request.FILES.getlist(k)) != 1 for k in request.FILES):
            raise ValueError("Select one image per field")
        return JsonResponse(
            scans.create(
                who,
                request.POST.get("job_id", ""),
                [request.FILES[k] for k in ("front", "back") if k in request.FILES],
                request.POST.get("fixture", "valid"),
            )
        )
    if request.method != "GET":
        return HttpResponse(status=405)
    keys = store.rows(
        "SELECT id FROM scan_jobs WHERE user_id=%s ORDER BY created DESC LIMIT 40", [who.user_id]
    )
    return JsonResponse({"jobs": [scans.job(who, r["id"]) for r in keys], "mode": scans.config()["mode"]})


@endpoint
@require_GET
def detail(request, key):
    return JsonResponse(scans.job(actor(request), str(key)))


@endpoint
@require_POST
def mutate(request, key, action):
    return JsonResponse(scans.action(actor(request), str(key), action, body(request)))


@endpoint
@require_GET
def photo(request, key):
    who = actor(request)
    found = store.rows(
        "SELECT p.content,j.copy_id,j.created,j.operation_id FROM scan_photos p JOIN scan_jobs j ON j.id=p.job_id WHERE p.id=%s AND p.user_id=%s",
        [str(key), who.user_id],
    )
    if not found or (not found[0]["operation_id"] and found[0]["created"] < time.time() - 7 * 86400):
        raise Http404
    if found[0]["copy_id"] and not store.rows(
        "SELECT id FROM owned_copies WHERE id=%s AND user_id=%s AND state='active'",
        [found[0]["copy_id"], who.user_id],
    ):
        raise Http404
    response = HttpResponse(bytes(found[0]["content"]), content_type="image/jpeg")
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response
