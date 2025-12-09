from django.urls import path
from .views import gtfs_list, remove_gtfs

urlpatterns = [
    path("list/", gtfs_list, name="gtfs_list"),
    path("remove/", remove_gtfs, name="remove_gtfs"),

]