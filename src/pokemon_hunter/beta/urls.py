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
