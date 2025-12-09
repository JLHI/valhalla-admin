from django.shortcuts import render
import os
from django.shortcuts import render, redirect
from .models import BuildTask
from valhalla_admin.gtfs.models import GtfsSource
from .utils import OSM_CATALOG_FR

def dashboard(request):
    return render(request, "graph/dashboard.html", {"section": "dashboard"})

def graph_list(request):
    return render(request, "graph/list.html", {"section": "list"})

def graph_create(request):
    return render(request, "graph/create.html", {"section": "create"})


OSM_DIR = "/data/osm"

def graph_create(request):
    # GET → afficher formulaire
    if request.method == "GET":
        # charger GTFS en base
        gtfs = GtfsSource.objects.all().order_by("name")

        # charger fichiers OSM
        osm_files = []
        if os.path.exists(OSM_DIR):
            for f in os.listdir(OSM_DIR):
                if f.endswith(".pbf"):
                    path = os.path.join(OSM_DIR, f)
                    size = round(os.path.getsize(path) / 1024 / 1024, 1)
                    osm_files.append({"name": f, "size": size})

        return render(request, "graph/create.html", {
            "section": "create",
            "gtfs": gtfs,
            "osm_files": osm_files,
            "osm_catalog": OSM_CATALOG_FR,

        })

    # POST → création de la tâche
    selected_gtfs = request.POST.getlist("gtfs")
    osm_name = request.POST.get("osm")
    graph_name = request.POST.get("graph_name")

    task = BuildTask.objects.create(
        name=graph_name,
        osm_file=osm_name,
        gtfs_ids=selected_gtfs,
        status="pending",
    )

    # Lancer la tâche de build
    from .tasks import start_valhalla_build
    start_valhalla_build(task.id)

    return redirect("/graphs/list/")