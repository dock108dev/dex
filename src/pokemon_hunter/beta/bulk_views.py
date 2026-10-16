"""Local manual entry only. No recognition, provider or price path is reachable here."""

import json
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from . import bulk_input, collection, collection_drafts, effective_collection, navigation, store
from .asgi import BULK_BODY_LIMIT
from .collection_views import body
from .views import actor


def draft_body(request):
    """Manual JSON has its own finite transport cap; ordinary/photo requests retain their limits."""
    if request.content_type != "application/json":
        raise ValueError("Send a JSON object")
    raw = request.read(BULK_BODY_LIMIT + 1)
    if len(raw) > BULK_BODY_LIMIT:
        raise ValueError("Manual draft transport limit exceeded")
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Send a JSON object")
    return data


def endpoint(fn):
    @login_required
    @wraps(fn)
    def wrapped(request, *args, **kwargs):
        try:
            who = actor(request)
            result = fn(request, who, *args, **kwargs)
            store.verified(who)
            response = (
                result
                if isinstance(result, HttpResponse)
                else JsonResponse(dict(result, binding=navigation.binding(request)["navigation_binding"]))
            )
        except collection.Conflict:
            response = JsonResponse(
                {"error": "This draft or collection changed. Reload and explicitly Review again."}, status=409
            )
        except (ValueError, TypeError):
            response = JsonResponse(
                {
                    "error": "Check the template, supported columns, row IDs and 2,000-row / 1.5 MB limits. Your input remains here."
                },
                status=400,
            )
        response["Cache-Control"] = "private, no-store"
        return response

    return wrapped


@endpoint
@require_GET
def home(request, who):
    return render(request, "beta/bulk_entry.html", {"bulk_available": collection_drafts.available()})


@endpoint
@require_GET
def catalog(request, who):
    entries, grouped = bulk_input.catalog_state(who)
    effective = effective_collection.project(who)
    status = {(r["set_name"], r["name"], r["number"]): r for r in effective["cards"]}
    groups = []
    for g in grouped["groups"]:
        current = status.get((g["set_name"], g["name"], g["collector_number"]), {})
        groups.append(
            {k: v for k, v in g.items() if k != "_children"}
            | dict(
                existing={
                    k: current.get(k)
                    for k in ("present", "established_total_quantity", "recorded_copy_count")
                },
                current_copy_count=len(current.get("current_copy_ids", [])),
                children=[
                    {
                        k: p[k]
                        for k in (
                            "id",
                            "edition",
                            "finish",
                            "variant",
                            "unresolved_fields",
                            "catalog_version",
                        )
                    }
                    for p in g["_children"]
                ],
            )
        )
    sets = {p["set_id"]: dict(id=p["set_id"], name=p["set_name"], game_id=p["game_id"]) for p in entries}
    return dict(
        groups=groups,
        sets=sorted(sets.values(), key=lambda s: s["name"]),
        games=store.rows("SELECT id,game_key,name FROM games ORDER BY name"),
        languages=sorted({p["language"] for p in entries}),
        binders=collection.binders(who),
        generation=effective["generation"],
    )


@endpoint
@require_GET
def template(request, who):
    content = bulk_input.template()
    if request.GET:
        if set(request.GET) != {"set"} or len(request.GET.getlist("set")) != 1:
            raise ValueError("Choose one supported set")
        _, grouped = bulk_input.catalog_state(who)
        groups = [g for g in grouped["groups"] if g["set_id"] == request.GET["set"]]
        if not groups:
            raise ValueError("Choose a supported set")
        content = bulk_input.export_rows(
            [
                dict(
                    row_id="card-" + g["id"],
                    action="add_copies",
                    set_id=g["set_id"],
                    language=g["language"],
                    number=g["collector_number"],
                    quantity="1",
                )
                for g in groups
            ]
        )
    response = HttpResponse(content, content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="dex-onboarding-v1.csv"'
    return response


@endpoint
@require_GET
def drafts(request, who):
    if not collection_drafts.available():
        return JsonResponse(
            {"error": "Manual bulk is unavailable until the additive enable-bulk migration."}, status=503
        )
    return dict(drafts=collection_drafts.listed(who))


@endpoint
@require_POST
def save(request, who):
    data = draft_body(request)
    if set(data) - {"input", "id", "revision", "new_batch", "batch_identity"} or "input" not in data:
        raise ValueError("Expected draft input and optional revision")
    if data.get("new_batch") and "batch_identity" not in data:
        raise ValueError("A stable batch identity is required for a new physical batch")
    return dict(
        draft=collection_drafts.save(
            who, data["input"], data.get("id"), data.get("revision"), data.get("new_batch", False)
        )
    )


@endpoint
@require_GET
def detail(request, who, key):
    draft = collection_drafts.get(who, str(key))
    opid = draft["confirmed_operation_id"] or draft["review_operation_id"]
    return dict(draft=draft, operation=collection.operation(who, opid) if opid else None)


@endpoint
@require_POST
def action(request, who, key, action):
    data = body(request)
    if set(data) != {"revision"}:
        raise ValueError("Expected exact draft revision")
    if action == "review":
        return collection_drafts.review(who, str(key), data["revision"])
    if action == "confirm":
        return dict(
            operation=collection_drafts.confirm(who, str(key), data["revision"]),
            draft=collection_drafts.get(who, str(key)),
        )
    if action == "cancel":
        return dict(draft=collection_drafts.cancel(who, str(key), data["revision"]))
    raise ValueError("Unsupported draft action")


@endpoint
@require_POST
def parse(request, who):
    data = draft_body(request)
    if set(data) != {"input"}:
        raise ValueError("Expected manual input only")
    parsed = bulk_input.envelope(data["input"])
    return dict(input=parsed, normalized=bulk_input.normalize(who, parsed))
