from django.conf import settings
from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path

from . import collection_views as collection_assets
from . import public_views, readiness, species_views, views
from .account_read_views import routes as account_read_routes
from .catalog_read_views import routes as catalog_read_routes

# Choose one authoritative handler per URL; retain account-only handlers for account-only roots.
collection_routes = views
hunt_routes = views
hunt_detail = views.hunt_detail
lookup_home = public_views.lookup
if settings.B2_ENABLED:
    from . import collection_views as collection_routes
    from . import lookup_views

    lookup_home = lookup_views.home
if settings.PARITY_ENABLED:
    from . import parity_views as hunt_routes

    hunt_detail = hunt_routes.saved

urlpatterns = [
    path("livez/", readiness.live),
    path("readyz/", readiness.ready),
    path("api/v2/readiness/", readiness.account),
    path("", collection_routes.home),
    path("pokedex/", species_views.home),
    path("pokedex/<int:dex>/", species_views.home),
    path("lookup/", lookup_home),
    path("api/public/catalog/", public_views.catalog),
    path("collection-assets/<str:filename>", collection_assets.asset),
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
    from . import (
        bulk_views,
        discovery_views,
        hunter_views,
        interpretation_views,
        listing_views,
        lookup_views,
        navigation,
        packs_views,
        product_views,
        refresh_views,
        shopping_views,
    )
    from . import card_group_views as groups
    from . import collection_views as b2

    urlpatterns = [
        path("api/listing-interpretation/readiness/", interpretation_views.readiness),
        path("api/listing-interpretation/", interpretation_views.start),
        path("api/listing-interpretation/<uuid:key>/", interpretation_views.status),
        path("api/listing-interpretation/<uuid:key>/stop/", interpretation_views.stop),
        path("collection-tools/", navigation.task_home),
        path("add-card/", navigation.task_home),
        path("add-many/", bulk_views.home),
        path("api/bulk/catalog/", bulk_views.catalog),
        path("api/bulk/template/", bulk_views.template),
        path("api/bulk/drafts/", bulk_views.drafts),
        path("api/bulk/save/", bulk_views.save),
        path("api/bulk/parse/", bulk_views.parse),
        path("api/bulk/drafts/<uuid:key>/", bulk_views.detail),
        path("api/bulk/drafts/<uuid:key>/<str:action>/", bulk_views.action),
        path("administration/", navigation.task_home),
        path("api/navigation/home/", navigation.validate_home),
        path("api/pokedex-species/", species_views.projection),
        path("api/card-groups/", groups.catalog),
        path("api/card-group-filters/", groups.filters),
        path("cards/", b2.home),
        path("card-library/", b2.home),
        path("cards/<str:key>/", groups.legacy),
        path("api/my-card-groups/", groups.owned),
        path("api/card-groups/<str:key>/", groups.detail),
        path("api/card-groups/<str:key>/preview/", groups.preview),
        path("api/species/<int:dex>/card-groups/", groups.species),
        path("api/public/card-groups/", groups.public_catalog),
        path("api/public/card-groups/<str:key>/", groups.public_detail),
        path("card-groups/<str:key>/", groups.home),
        path("shopping/", discovery_views.home),
        path("shopping/hunter/", hunter_views.home),
        path("shopping/calculator/", shopping_views.home),
        path("shopping/check/", listing_views.home),
        path("api/shopping/listing/", listing_views.loads),
        path("api/shopping/listing/candidate/", listing_views.candidate),
        path("api/shopping/listing/catalog/", listing_views.catalog),
        path("api/shopping/listing/<uuid:run>/stop/", listing_views.stop),
        path("api/shopping/listing/review/", listing_views.review),
        path("api/shopping/listing/compare/", listing_views.compare),
        path("api/shopping/discovery/", discovery_views.searches),
        path("api/shopping/hunter/", hunter_views.hunts),
        path("api/shopping/hunter/usage/", hunter_views.usage),
        path("api/shopping/hunter/catalog/", hunter_views.catalog),
        path("api/shopping/hunter/<uuid:run>/stop/", hunter_views.stop),
        path("api/shopping/hunter/<uuid:run>/continue/", hunter_views.continuation),
        path("api/shopping/hunter/<uuid:run>/analyze-lots/", hunter_views.analyze_lots),
        path("api/shopping/hunter/<uuid:run>/lot-detail-intent/", hunter_views.lot_detail_intent),
        path("api/shopping/hunter/<uuid:run>/analyze-lot-details/", hunter_views.analyze_lot_details),
        path("api/shopping/hunter/lot-details/<uuid:action>/", hunter_views.lot_details_status),
        path("api/shopping/hunter/lot-details/<uuid:action>/stop/", hunter_views.lot_details_stop),
        path("api/shopping/hunter/lot-review/<uuid:review>/", hunter_views.lot_review),
        path("api/shopping/discovery/catalog/", discovery_views.catalog),
        path("api/shopping/discovery/<uuid:run>/stop/", discovery_views.stop),
        path("api/shopping/discovery/<uuid:run>/reveal/<str:result>/", discovery_views.reveal),
        path("shopping/legacy/", shopping_views.legacy),
        path("api/shopping/lot-catalog/", shopping_views.lot_catalog),
        path("api/shopping/price-source-status/", shopping_views.source_status),
        path("api/shopping/wants/", shopping_views.wanted),
        path("api/shopping/lot-compare/", shopping_views.lot_compare),
        path("api/shopping/catalog/", shopping_views.catalog),
        path("api/shopping/compare/", shopping_views.compare),
        path("shopping/saved/<uuid:key>/", shopping_views.saved),
        path("shopping/saved/<uuid:key>/current/", shopping_views.current),
        path("product-review/", product_views.home),
        path("product-review/preview/", product_views.preview),
        path("product-review/<uuid:key>/", product_views.detail),
        path("product-review/<uuid:key>/<str:action>/", product_views.action),
        path("api/product-coverage/", product_views.coverage),
        path("collection/", b2.home),
        path("goals/", b2.home),
        path("lookup/save/", lookup_views.save),
        path("api/collection-sources/<str:key>/", lookup_views.source),
        path("packs/", packs_views.home),
        path("packs/refresh/", refresh_views.home),
        path("packs/refresh/start/", refresh_views.start),
        path("packs/refresh/<uuid:key>/stop/", refresh_views.stop),
        path("packs/refresh/<uuid:key>/<uuid:attempt>/<str:action>/", refresh_views.review),
        path("packs/save/", packs_views.save),
        path("packs/saved/", packs_views.saved_list),
        path("packs/saved/<uuid:key>/", packs_views.saved, name="saved-pack-research"),
        path("packs/saved/<uuid:key>/rename/", packs_views.rename),
        path("packs/saved/<uuid:key>/remove/", packs_views.remove),
        path("settings/", b2.home),
        path("api/collection/", b2.dashboard),
        path("api/collection-context/", b2.context),
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
        *[path(route + "/", b2.home) for route in ("overview", "hunt", "missing", "finds")],
        path("api/parity/", parity.projection),
        path("api/hunts/<uuid:batch>/<int:key>/reveal/<uuid:result>/", parity.reveal),
    ] + urlpatterns
else:
    urlpatterns = [path("hunt/", public_views.hunt)] + urlpatterns

if settings.B3_ENABLED:
    from . import photo_batch_views as photo_batches
    from . import scan_views as scans

    urlpatterns = [
        path("add-photos/", photo_batches.home),
        path("api/photo-batches/", photo_batches.listed),
        path("api/photo-batches/create/", photo_batches.create),
        path("api/photo-batches/<uuid:key>/", photo_batches.detail),
        path("api/photo-batches/<uuid:key>/upload/", photo_batches.upload),
        path("api/photo-batches/<uuid:key>/retake/", photo_batches.retake),
        path("api/photo-batches/<uuid:key>/photos/<uuid:pid>/", photo_batches.original),
        path("api/photo-batches/<uuid:key>/<str:action>/", photo_batches.action),
        path("scan/", scans.home),
        path("api/scans/", scans.jobs),
        path("api/scans/<uuid:key>/", scans.detail),
        path("api/scans/<uuid:key>/<str:action>/", scans.mutate),
        path("scan-photos/<uuid:key>/", scans.photo),
    ] + urlpatterns

if settings.B4_ENABLED:
    from . import catalog_pipeline_views as pipeline
    from . import catalog_views as catalogs

    urlpatterns = [
        path("catalog-coverage/", pipeline.coverage),
        path("api/catalog-coverage/", pipeline.report),
        path("catalog-pipeline/", pipeline.home),
        path("catalog-pipeline/preview/", pipeline.preview),
        path("catalog-pipeline/<uuid:key>/", pipeline.detail),
        path("catalog-pipeline/<uuid:key>/<str:action>/", pipeline.action),
        path("api/catalog-batches/", pipeline.api_preview),
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

# Additive public contracts remain available (503) before explicit preparation.

urlpatterns += catalog_read_routes()

urlpatterns += account_read_routes()
