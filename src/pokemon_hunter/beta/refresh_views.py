"""Explicit local synthetic replay forms; ordinary mode exposes only unavailability."""

import threading

from django.db import close_old_connections
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from . import refresh, sealed_catalog, store
from .collection_views import endpoint
from .views import actor


def worker(principal, key):
    close_old_connections()
    try:
        refresh.execute(principal, key)
    finally:
        close_old_connections()


@endpoint
@require_GET
def home(request):
    principal = store.verified(actor(request))
    enabled = refresh.enabled() and principal.role == "owner" and refresh.available()
    context = dict(enabled=enabled, scenarios=refresh.SCENARIOS)
    if enabled:
        refresh.recover(principal)
        context["products"] = [
            p
            for p in sealed_catalog.records()["products"].values()
            if any(o["product_id"] == p["id"] for o in sealed_catalog.records()["offers"].values())
        ]
        context["runs"] = [
            refresh.get(principal, r["id"])
            for r in store.rows(
                "SELECT id FROM refresh_runs WHERE user_id=%s ORDER BY created_at DESC", [principal.user_id]
            )
        ]
    return render(request, "beta/refresh.html", context)


@endpoint
@require_POST
def start(request):
    if set(request.POST) - {"csrfmiddlewaretoken", "product", "sources", "timeout"}:
        raise ValueError("Only replay product, sources and timeout accepted")
    principal = actor(request)
    key = refresh.start(
        principal,
        request.POST.get("product", ""),
        request.POST.getlist("sources"),
        int(request.POST.get("timeout", "2")),
    )
    threading.Thread(target=worker, args=(principal, key), daemon=True).start()
    return redirect("/packs/refresh/")


@endpoint
@require_POST
def stop(request, key):
    refresh.stop(actor(request), str(key))
    return redirect("/packs/refresh/")


@endpoint
@require_POST
def review(request, key, attempt, action):
    refresh.review(actor(request), str(key), str(attempt), action)
    return redirect("/packs/refresh/")
