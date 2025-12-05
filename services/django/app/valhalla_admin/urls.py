from django.contrib import admin
from django.urls import path, include
from .views import home, AdminLogin   
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from valhalla_admin.gtfs.views import add_gtfs_from_eu

urlpatterns = [
    # Surcharger la vue de login admin
    path("admin/login/", AdminLogin.as_view(), name="admin_login"),

    # Admin normal (mais login remplacé)
    path("admin/", admin.site.urls),
    
    # API
    path("api/", include("valhalla_admin.api.urls")),

    # Page home
    path("", home, name="home"),

    #GTFS List
    path("gtfs/", include("valhalla_admin.gtfs.urls")),



]

urlpatterns += staticfiles_urlpatterns()


urlpatterns += [
    path("admin/add-gtfs-eu/", add_gtfs_from_eu, name="add_gtfs_from_eu"),
]