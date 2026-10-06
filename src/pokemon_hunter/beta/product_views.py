"""Owner review of retained/manual sealed packages through existing journals."""

import json
from datetime import datetime, timezone

from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from . import collection, product_lookup, store
from . import sealed_catalog as sealed
from .collection_views import endpoint
from .views import actor


@endpoint
@require_GET
def home(request):
    who = actor(request)
    sealed.cat.admin(who)
    return render(
        request,
        "beta/product_review.html",
        dict(
            imports=[
                dict(id=r["id"], state=r["state"], version=r["version"])
                for r in store.rows("SELECT id,state,version FROM sealed_imports ORDER BY id")
            ]
        ),
    )


@endpoint
@require_POST
def preview(request):
    text = request.POST.get("package", "")
    if len(text.encode()) > 5_000_000:
        raise ValueError("Package too large")
    op = sealed.preview(actor(request), json.loads(text))
    return redirect("/product-review/" + op["id"] + "/")


@endpoint
@require_GET
def detail(request, key):
    op = sealed.get(actor(request), str(key))
    return render(
        request,
        "beta/product_review.html",
        dict(op=op, review=sealed.review(op), package=json.dumps(op["package"], indent=2)),
    )


@endpoint
@require_POST
def action(request, key, action):
    try:
        sealed.transition(actor(request), str(key), action)
    except (collection.Conflict, ValueError) as exc:
        op = sealed.get(actor(request), str(key))
        return render(
            request,
            "beta/product_review.html",
            dict(
                op=op, review=sealed.review(op), package=json.dumps(op["package"], indent=2), refusal=str(exc)
            ),
        )
    return redirect("/product-review/" + str(key) + "/")


@endpoint
@require_GET
def coverage(request):
    who = actor(request)
    store.verified(who)
    return JsonResponse(
        dict(
            targets=product_lookup.coverage(
                sealed.records(), datetime.now(timezone.utc), collection.catalog(who)
            )
        )
    )
