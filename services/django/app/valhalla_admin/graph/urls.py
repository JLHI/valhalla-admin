from django.urls import path
from . import views

urlpatterns = [
    path("", views.dashboard, name="graph_dashboard"),
    path("list/", views.graph_list, name="graph_list"),
    path("create/", views.graph_create, name="graph_create"),
]