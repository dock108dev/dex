"""Local photo staging and explicit stage consent; no collection mutation here."""

from functools import wraps

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST
from pydantic import ValidationError

from . import collection, navigation, store
from . import photo_batches as batches
from .collection_views import body
from .views import actor


def endpoint(fn):
    @login_required
    @wraps(fn)
    def wrapped(request, *args, **kwargs):
        try:
            who = store.verified(actor(request))
            if settings.STAGING:
                raise Http404
            binding = navigation.binding(request)["navigation_binding"]
            if request.method == "POST" and request.headers.get("X-Dex-Binding") != binding:
                raise PermissionDenied
            value = fn(request, who, *args, **kwargs)
            store.verified(who)
            response = (
                value if isinstance(value, HttpResponse) else JsonResponse(dict(value, binding=binding))
            )
        except collection.Conflict:
            response = JsonResponse(
                dict(error="Photo batch changed or is unavailable. Reload before editing."), status=409
            )
        except ValidationError:
            response = JsonResponse(
                dict(error="Use finite in-bounds crop geometry and supported fields"), status=400
            )
        except (ValueError, TypeError):
            # Exception text can include private inputs or downstream implementation details.
            response = JsonResponse(dict(error="Check the photo review fields"), status=400)
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response

    return wrapped


@endpoint
@require_GET
def home(request, who):
    return render(request, "beta/photo_batches.html", dict(available=batches.available()))


@endpoint
@require_GET
def listed(request, who):
    if not batches.available():
        return dict(batches=[], available=False)
    rows = store.rows(
        "SELECT id,revision,state,created,draft_id FROM scan_batches WHERE user_id=%s ORDER BY created DESC LIMIT 100",
        [who.user_id],
    )
    return dict(batches=rows, available=True)


@endpoint
@require_POST
def create(request, who):
    data = body(request)
    if set(data) != {"id"}:
        raise ValueError("Use one stable batch UUID")
    return dict(batch=batches.create(who, data["id"]))


@endpoint
@require_GET
def detail(request, who, key):
    return dict(batch=batches.detail(who, str(key)))


@endpoint
@require_POST
def upload(request, who, key):
    if (
        set(request.FILES) != {"photo"}
        or len(request.FILES.getlist("photo")) != 1
        or set(request.POST) != {"revision"}
    ):
        raise ValueError("Choose exactly one source photo and the current revision")
    return dict(batch=batches.admit(who, str(key), int(request.POST["revision"]), request.FILES["photo"]))


@endpoint
@require_GET
def original(request, who, key, pid):
    p = batches.photo(who, str(key), str(pid))
    return HttpResponse(bytes(p["content"]), content_type="image/jpeg")


@endpoint
@require_POST
def action(request, who, key, action):
    data = body(request)
    key = str(key)
    fields = {
        "layout": {"revision", "photo_id", "boxes"},
        "select": {"revision", "crop_id", "row", "included", "retain", "decision"},
        "analyze": {"revision", "photo_id", "stage", "consent"},
        "reorder": {"revision", "photo_ids"},
        "delete-images": set(),
        "stop": set(),
        "cancel": set(),
        "remove": {"revision", "photo_id"},
        "handoff": {"revision", "duplicates_reviewed", "manual_rows"},
    }
    if action not in fields or set(data) != fields[action]:
        raise ValueError("Use the exact current photo action fields")
    if action == "layout":
        b = batches.layout(who, key, data["revision"], data["photo_id"], data["boxes"])
    elif action == "select":
        b = batches.select_crop(
            who,
            key,
            data["revision"],
            data["crop_id"],
            data["row"],
            data["included"],
            data["retain"],
            data["decision"],
        )
    elif action == "analyze":
        b = batches.analyze(
            who,
            key,
            data["revision"],
            data["photo_id"],
            data["stage"],
            request.session.session_key,
            data["consent"],
        )
    elif action == "reorder":
        b = batches.reorder(who, key, data["revision"], data["photo_ids"])
    elif action == "delete-images":
        b = batches.delete_images(who, key)
    elif action == "stop":
        b = batches.stop_analysis(who, key)
    elif action == "cancel":
        b = batches.cancel(who, key)
    elif action == "remove":
        b = batches.remove_photo(who, key, data["revision"], data["photo_id"])
    else:
        return batches.handoff(who, key, data["revision"], data["duplicates_reviewed"], data["manual_rows"])
    return dict(batch=b)


@endpoint
@require_POST
def retake(request, who, key):
    if (
        set(request.FILES) != {"photo"}
        or len(request.FILES.getlist("photo")) != 1
        or set(request.POST) != {"revision", "photo_id", "same_objects"}
    ):
        raise ValueError("Select one retake and explicitly identify the same physical objects")
    return dict(
        batch=batches.retake(
            who,
            str(key),
            int(request.POST["revision"]),
            request.POST["photo_id"],
            request.FILES["photo"],
            request.POST["same_objects"] == "true",
        )
    )
