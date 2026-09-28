from django.conf import settings
from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path

from . import views

urlpatterns = [
    path("", views.home),
    path("login/", LoginView.as_view(template_name="beta/login.html")),
    path("logout/", LogoutView.as_view()),
    path("recovery/", views.recovery_help),
    path("recovery/<uidb64>/<token>/", views.RedeemView.as_view()),
    path("invite/<uidb64>/<token>/", views.InviteView.as_view()),
    path("api/inventory/", views.inventory),
    path("api/inventory/<str:key>/", views.copy_detail),
    path("api/hunts/", views.hunts),
    path("api/hunts/<uuid:batch>/<int:key>/", views.hunt_detail),
    path("api/archives/", views.archives),
    path("files/<uuid:batch>/<path:path>", views.archive_file),
    path("api/export/", views.export),
    path("api/admin/catalog/", views.admin_catalog),
]

# B2 is enabled only by new-root initialization. Prepared B1 roots retain B1 routes.

if settings.B2_ENABLED:
    from . import collection_views as b2

    urlpatterns = [
        path("", b2.home),
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
        path("api/inventory/<str:key>/", b2.copy_detail),
        path("api/export/", b2.export),
    ] + urlpatterns

if settings.PARITY_ENABLED:
    from . import parity_views as parity

    urlpatterns = [
        *[
            path(route + "/", b2.home)
            for route in ("overview", "pokedex", "cards", "hunt", "missing", "finds")
        ],
        path("api/parity/", parity.projection),
        path("api/hunts/", parity.hunts),
        path("api/hunts/<uuid:batch>/<int:key>/", parity.saved),
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
