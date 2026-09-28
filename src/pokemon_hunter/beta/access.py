"""Bearer links stay in fragments and POST bodies, never provider request URLs."""

from pathlib import Path

from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from .accounts import invite_token, recovery_token
from .views import RedeemView


@require_GET
def landing(request):
    return render(request, "beta/access.html")


@require_GET
def script(request):
    return HttpResponse(
        (Path(__file__).parent / "static/access.js").read_text(), content_type="text/javascript"
    )


@require_POST
def start(request):
    kind, uid, token = (request.POST.get(k, "") for k in ("kind", "uid", "token"))
    if kind not in {"invite", "recovery"} or len(uid) > 100 or len(token) > 100:
        return HttpResponseBadRequest("Invalid or expired access link")
    view = RedeemView()
    view.kind = kind
    user = view.get_user(uid)
    generator = invite_token if kind == "invite" else recovery_token
    if not user or not generator.check_token(user, token):
        return HttpResponseBadRequest("Invalid or expired access link")
    request.session.cycle_key()
    request.session["access_kind"] = kind
    request.session["access_uid"] = uid
    request.session["_password_reset_token"] = token
    return redirect("/access/reset/")


class ResetView(RedeemView):
    def dispatch(self, request, *args, **kwargs):
        self.kind = request.session.get("access_kind", "recovery")
        self.token_generator = invite_token if self.kind == "invite" else recovery_token
        return super().dispatch(request, uidb64=request.session.get("access_uid", ""), token="set-password")
