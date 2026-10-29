from django.conf import settings
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from . import scan_config, scans, store
from .collection_views import body, endpoint
from .views import actor


@endpoint
@require_GET
def home(request):
    actor(request)
    return render(
        request,
        "beta/scans.html",
        {
            "mode": scan_config.effective_mode(scans.config()),
            "recognition_enabled": scan_config.recognition_enabled(),
            "expansion": settings.B4_ENABLED,
        },
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
    return JsonResponse(
        {"jobs": [scans.job(who, r["id"]) for r in keys], "mode": scan_config.effective_mode(scans.config())}
    )


@endpoint
@require_GET
def detail(request, key):
    return JsonResponse(scans.job(actor(request), str(key)))


@endpoint
@require_POST
def mutate(request, key, action):
    who = actor(request)
    if action == "retry" and not scan_config.recognition_enabled():
        return JsonResponse({"error": scan_config.UNAVAILABLE}, status=409)
    return JsonResponse(scans.action(who, str(key), action, body(request)))


@endpoint
@require_GET
def photo(request, key):
    who = actor(request)
    found = scans.authorized_photo_rows(who, key, content=True)
    if not found:
        raise Http404
    response = HttpResponse(bytes(found[0]["content"]), content_type="image/jpeg")
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response
