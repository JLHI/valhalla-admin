from django.contrib import admin
from django.urls import path, include, re_path
from .views import home, AdminLogin
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from valhalla_admin.gtfs.views import add_gtfs_from_eu


# URLs classiques (admin, home, etc.)
urlpatterns = [
    path("admin/add-gtfs-eu/", add_gtfs_from_eu, name="add_gtfs_from_eu"),
    path("admin/login/", AdminLogin.as_view(), name="admin_login"),
    path("admin/", admin.site.urls),
    path("", home, name="home"),
]


# URLs avec alias de graph en préfixe : /valhalla/<alias>/...
urlpatterns += [
    re_path(r"^valhalla/(?P<graph_alias>[^/]+)/api/", include(("valhalla_admin.api.urls", "api"), namespace="api_alias")),
    re_path(r"^valhalla/(?P<graph_alias>[^/]+)/gtfs/", include(("valhalla_admin.gtfs.urls", "gtfs"), namespace="gtfs_alias")),
    re_path(r"^valhalla/(?P<graph_alias>[^/]+)/graphs/", include(("valhalla_admin.graph.urls", "graph"), namespace="graph_alias")),
]

# URLs sans alias (compatibilité directe)
urlpatterns += [
    path("api/", include(("valhalla_admin.api.urls", "api"), namespace="api")),
    path("gtfs/", include(("valhalla_admin.gtfs.urls", "gtfs"), namespace="gtfs")),
    path("graphs/", include(("valhalla_admin.graph.urls", "graph"), namespace="graph")),
]

urlpatterns += staticfiles_urlpatterns()