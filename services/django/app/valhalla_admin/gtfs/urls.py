from django.urls import path
from .views import gtfs_list

urlpatterns = [
    path("list/", gtfs_list, name="gtfs_list"),
]