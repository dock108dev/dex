from django.conf import settings
from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path

from . import views

# Choose one authoritative handler per URL; retain account-only handlers for account-only roots.
collection_routes = views
hunt_routes = views
hunt_detail = views.hunt_detail
if settings.B2_ENABLED:
    from . import collection_views as collection_routes
if settings.PARITY_ENABLED:
    from . import parity_views as hunt_routes

    hunt_detail = hunt_routes.saved

urlpatterns = [
    path("", collection_routes.home),
    path("login/", LoginView.as_view(template_name="beta/login.html")),
    path("logout/", LogoutView.as_view()),
    path("recovery/", views.recovery_help),
    path("api/inventory/", views.inventory),
    path("api/inventory/<str:key>/", collection_routes.copy_detail),
    path("api/hunts/", hunt_routes.hunts),
    path("api/hunts/<uuid:batch>/<int:key>/", hunt_detail),
    path("api/archives/", views.archives),
    path("files/<uuid:batch>/<path:path>", views.archive_file),
    path("api/export/", collection_routes.export),
    path("api/admin/catalog/", views.admin_catalog),
]

if settings.B2_ENABLED:
    from . import collection_views as b2

    urlpatterns = [
        path("goals/", b2.home),
        path("settings/", b2.home),
        path("collection-assets/<str:filename>", b2.asset),
        path("api/collection/", b2.dashboard),
        path("api/catalog/", b2.catalog),
        path("api/binders/", b2.binders),
        path("api/binders/<str:key>/", b2.binder),
        path("api/goals/", b2.goals),
        path("api/goals/<str:key>/", b2.goal),
        path("api/operations/preview/", b2.preview),
        path("api/operations/<str:key>/", b2.operation),
        path("api/operations/<str:key>/confirm/", b2.confirm),
        path("api/operations/<str:key>/undo/", b2.undo),
    ] + urlpatterns

if settings.PARITY_ENABLED:
    from . import parity_views as parity

    urlpatterns = [
        *[
            path(route + "/", b2.home)
            for route in ("overview", "pokedex", "cards", "hunt", "missing", "finds")
        ],
        path("api/parity/", parity.projection),
        path("api/hunts/<uuid:batch>/<int:key>/reveal/<uuid:result>/", parity.reveal),
    ] + urlpatterns

if settings.B3_ENABLED:
    from . import scan_views as scans

    urlpatterns = [
        path("scan/", scans.home),
        path("api/scans/", scans.jobs),
        path("api/scans/<uuid:key>/", scans.detail),
        path("api/scans/<uuid:key>/<str:action>/", scans.mutate),
        path("scan-photos/<uuid:key>/", scans.photo),
    ] + urlpatterns

if settings.B4_ENABLED:
    from . import catalog_views as catalogs

    urlpatterns = [
        path("requests/", catalogs.home),
        path("catalog-review/", catalogs.review_home),
        path("api/catalog-requests/", catalogs.requests),
        path("api/catalog-requests/<uuid:key>/<str:action>/", catalogs.request_action),
        path("api/catalog-review/", catalogs.review),
        path("api/catalog-review/<uuid:key>/", catalogs.review_action),
        path("api/catalog-evidence/<uuid:key>/<uuid:photo>/", catalogs.evidence),
        path("api/catalog-imports/", catalogs.imports),
        path("api/catalog-imports/<uuid:key>/<str:action>/", catalogs.import_action),
        path("api/catalog-packages/<str:name>/", catalogs.package),
    ] + urlpatterns

if getattr(settings, "STAGING", False) or (settings.ROOT / "B5_ISOLATED").is_file():
    from . import support

    urlpatterns += [
        path("support/", support.page),
        path("support/feedback/", support.feedback),
        path("support/delete/", support.erase),
        path("healthz/", support.health),
    ]

if getattr(settings, "STAGING", False):
    from . import access

    urlpatterns += [
        path("access/", access.landing),
        path("access/script.js", access.script),
        path("access/start/", access.start),
        path("access/reset/", access.ResetView.as_view()),
    ]
else:
    urlpatterns += [
        path("recovery/<uidb64>/<token>/", views.RedeemView.as_view()),
        path("invite/<uidb64>/<token>/", views.InviteView.as_view()),
    ]
