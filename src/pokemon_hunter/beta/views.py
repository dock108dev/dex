import json

from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import PasswordResetConfirmView
from django.db import connection
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_http_methods

from . import store
from . import transactions as transaction
from .accounts import invite_token, recovery_token


def actor(request):
    return store.principal(request.user.pk)


class RedeemView(PasswordResetConfirmView):
    template_name = "beta/reset.html"
    success_url = "/login/"
    kind = "recovery"
    token_generator = recovery_token

    def get_user(self, uidb64):
        user = super().get_user(uidb64)
        if not user or not user.is_active:
            return None
        found = store.rows("SELECT state FROM users WHERE auth_subject=%s", [str(user.pk)])
        expected = "invited" if self.kind == "invite" else "active"
        return user if found and found[0]["state"] == expected else None

    @transaction.atomic
    def form_valid(self, form):
        # Serialize consumption, recheck the framework token under the write lock.
        self.user.refresh_from_db()
        if not self.user.is_active or not self.token_generator.check_token(
            self.user, self.request.session.get("_password_reset_token")
        ):
            raise Http404
        response = super().form_valid(form)
        with connection.cursor() as c:
            c.execute("UPDATE users SET state='active' WHERE auth_subject=%s", [str(self.user.pk)])
        return response


class InviteView(RedeemView):
    kind = "invite"
    token_generator = invite_token


@require_GET
def home(request):
    if not request.user.is_authenticated:
        from .public_views import pokedex

        return pokedex(request)
    return private_home(request)


@login_required
def private_home(request):
    who = actor(request)
    copies = store.collection(who)
    for c in copies:
        c["name"] = json.loads(c["attributes"] or "{}").get("name", "Unidentified card")
        c["unresolved_label"] = ", ".join(json.loads(c["unresolved_fields"] or "[]")) or "None"
    return render(
        request, "beta/collection.html", {"copies": copies, "progress": store.progress(copies), "who": who}
    )


@login_required
@require_GET
def inventory(request):
    return JsonResponse({"copies": store.collection(actor(request))})


@login_required
@require_http_methods(["GET", "POST"])
def copy_detail(request, key):
    who = actor(request)
    item = store.resource(who, "inventory", key)
    if request.method == "POST":
        if set(request.POST) - {"notes", "csrfmiddlewaretoken"} or len(request.POST.get("notes", "")) > 2000:
            return JsonResponse({"error": "Only notes (up to 2000 characters) may be edited"}, status=400)
        with connection.cursor() as c:
            c.execute(
                "UPDATE owned_copies SET notes=%s WHERE id=%s AND user_id=%s",
                [request.POST.get("notes", ""), key, who.user_id],
            )
        item = store.resource(who, "inventory", key)
    return JsonResponse(item)


@login_required
@require_GET
def hunts(request):
    who = store.verified(actor(request))
    return JsonResponse({"hunts": store.rows("SELECT * FROM saved_hunts WHERE user_id=%s", [who.user_id])})


@login_required
@require_GET
def hunt_detail(request, batch, key):
    return JsonResponse(store.resource(actor(request), "hunts", (str(batch), key)))


@login_required
@require_GET
def archives(request):
    who = store.verified(actor(request))
    return JsonResponse(
        {
            "archives": store.rows(
                "SELECT batch_id,path,sha256 FROM private_archives WHERE user_id=%s", [who.user_id]
            )
        }
    )


@login_required
@require_GET
def archive_file(request, batch, path):
    row = store.resource(actor(request), "archives", (str(batch), path))
    # Database bytes only; no filesystem path concatenation or static private directory.
    response = HttpResponse(bytes(row["content"]), content_type="application/octet-stream")
    response["Content-Disposition"] = 'attachment; filename="private-archive.bin"'
    return response


@login_required
@require_GET
def export(request):
    who = actor(request)
    copies = store.collection(who)
    response = JsonResponse(
        {"schema": "b1-inventory-v1", "copies": copies, "vintage_251": store.progress(copies)}
    )
    response["Content-Disposition"] = 'attachment; filename="b1-inventory.json"'
    return response


@login_required
@require_GET
def admin_catalog(request):
    return JsonResponse(
        {
            "catalog": store.catalog_admin(actor(request)),
            "publication": "Catalog publication is not enabled for this root",
        }
    )


def recovery_help(request):
    return render(request, "beta/recovery.html")
