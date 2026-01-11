from django.urls import path
from . import views

urlpatterns = [
    path("", views.dashboard, name="graph_dashboard"),
    path("list/", views.graph_list, name="graph_list"),
    path("create/", views.graph_create, name="graph_create"),
    path("<str:name>/status/", views.graph_status, name="graph_status"),
    path("<str:name>/map/", views.graph_map, name="graph_map"),
    path("<str:name>/stops.geojson", views.graph_stops_geojson, name="graph_stops_geojson"),
    # Config endpoints (GET/POST JSON)
    path("<str:name>/config/", views.graph_config, name="graph_config"),
    path("config/schema/", views.config_schema, name="config_schema"),
    path("config/tooltips/", views.config_tooltips, name="config_tooltips"),
    path("<str:name>/", views.graph_detail, name="graph_detail"),
    path("task/<int:task_id>/delete/", views.delete_task, name="graph_task_delete"),
    path("task/<int:task_id>/logs/", views.graph_logs, name="graph_logs"),
    path("task/<int:task_id>/recreate/", views.recreate_task, name="graph_task_recreate"),
    
    # Gestion containers
    path("task/<int:task_id>/start/", views.start_container, name="container_start"),
    path("task/<int:task_id>/stop/", views.stop_container, name="container_stop"),
    path("task/<int:task_id>/restart/", views.restart_container, name="container_restart"),
    path("task/<int:task_id>/container-status/", views.container_status_api, name="container_status"),
]