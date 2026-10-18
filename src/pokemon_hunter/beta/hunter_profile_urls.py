"""Server-enforced route allowlist for the explicitly selected Hunter profile."""

from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.views import LoginView, LogoutView
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404
from django.shortcuts import redirect
from django.urls import path
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from . import collection_views, hunter_profile, hunter_views, store


class ExpectedAccountForm(AuthenticationForm):
    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        try:
            if store.principal(user.pk).user_id != hunter_profile.require_current().account_id:
                raise PermissionDenied
        except PermissionDenied:
            # AuthenticationForm validation happens before login() updates the
            # session or last_login. Keep the ordinary non-enumerating error.
            raise ValidationError(
                self.error_messages["invalid_login"],
                code="invalid_login",
                params={"username": self.username_field.verbose_name},
            ) from None


class HunterLoginView(LoginView):
    authentication_form = ExpectedAccountForm
    template_name = "beta/login.html"

    def get_success_url(self):
        return "/shopping/hunter/"


@login_required
@require_GET
def home(request):
    return redirect("/shopping/hunter/")


@require_GET
def asset(request, filename):
    if filename not in hunter_profile.ASSETS:
        raise Http404
    return collection_views.asset(request, filename)


@collection_views.endpoint
@require_http_methods(["GET", "POST"])
def hunts(request):
    return hunter_profile.start_once(request) if request.method == "POST" else hunter_views.hunts(request)


def acquisition(view):
    @collection_views.endpoint
    @require_POST
    def execute(request, *args, **kwargs):
        hunter_profile.require_acquisition()
        return view(request, *args, **kwargs)

    return execute


urlpatterns = [
    path("", home),
    path("login/", HunterLoginView.as_view()),
    path("logout/", LogoutView.as_view()),
    path("collection-assets/<str:filename>", asset),
    path("shopping/hunter/", hunter_views.home),
    path("api/shopping/hunter/", hunts),
    path("api/shopping/hunter/catalog/", hunter_views.catalog),
    path("api/shopping/hunter/<uuid:run>/stop/", hunter_views.stop),
    path("api/shopping/hunter/<uuid:run>/continue/", acquisition(hunter_views.continuation)),
    path("api/shopping/hunter/<uuid:run>/analyze-lots/", hunter_views.analyze_lots),
    path("api/shopping/hunter/<uuid:run>/lot-detail-intent/", hunter_views.lot_detail_intent),
    path(
        "api/shopping/hunter/<uuid:run>/analyze-lot-details/", acquisition(hunter_views.analyze_lot_details)
    ),
    path("api/shopping/hunter/lot-details/<uuid:action>/", hunter_views.lot_details_status),
    path("api/shopping/hunter/lot-details/<uuid:action>/stop/", hunter_views.lot_details_stop),
    path("api/shopping/hunter/lot-review/<uuid:review>/", hunter_views.lot_review),
]
