"""Authenticated readable coverage and owner-only retained batch review."""

import json

from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from . import catalog_imports as cat
from . import catalog_pipeline as pipeline
from . import store
from .collection_views import body, endpoint
from .views import actor


@endpoint
@require_GET
def coverage(request):
    who = actor(request)
    return render(
        request, "beta/catalog_coverage.html", dict(report=pipeline.coverage(who), admin=who.role == "owner")
    )


@endpoint
@require_GET
def report(request):
    return JsonResponse(pipeline.coverage(actor(request)))


@endpoint
@require_GET
def home(request):
    who = actor(request)
    cat.admin(who)
    pipeline.initialize()
    batches = [
        pipeline.get(who, r["id"])
        for r in store.rows("SELECT id FROM catalog_batches ORDER BY created DESC,id DESC LIMIT 30")
    ]
    return render(request, "beta/catalog_pipeline.html", dict(batches=batches))


@endpoint
@require_POST
def preview(request):
    who = actor(request)
    cat.admin(who)
    if request.POST.get("retained") == "yes":
        p = pipeline.retained_batch()
        p["mode"] = request.POST.get("mode", "atomic")
    else:
        text = request.POST.get("package", "")
        if len(text.encode()) > 5_000_000:
            raise ValueError("Retained batch too large")
        p = json.loads(text)
    op = pipeline.preview(who, p)
    if op["state"] == "invalid":
        return render(request, "beta/catalog_pipeline.html", dict(invalid=op), status=400)
    return redirect("/catalog-pipeline/" + op["id"] + "/")


@endpoint
@require_GET
def detail(request, key):
    return render(request, "beta/catalog_pipeline.html", dict(op=pipeline.get(actor(request), str(key))))


@endpoint
@require_POST
def action(request, key, action):
    pipeline.transition(
        actor(request),
        str(key),
        action,
        limit=int(request.POST.get("limit", "1")),
        expected_completed=int(request.POST["expected_completed"])
        if "expected_completed" in request.POST
        else None,
    )
    return redirect("/catalog-pipeline/" + str(key) + "/")


@endpoint
@require_POST
def api_preview(request):
    return JsonResponse(pipeline.preview(actor(request), body(request)))
