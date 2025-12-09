import requests
from celery import Celery
from valhalla_admin.home_widgets import register_widget
from valhalla_admin.gtfs.models import GtfsSource

# --- Celery Setup ---
celery_app = Celery("valhalla_admin")
celery_app.config_from_object("django.conf:settings", namespace="CELERY")


# --- Widget 1 : Statut Valhalla ---
@register_widget
def valhalla_status(request):
    """Widget affichant le statut du service Valhalla."""
    try:
        response = requests.get("http://valhalla:8002", timeout=1)
        ok = response.status_code == 200
    except Exception:
        ok = False

    return {
        "title": "Statut Valhalla",
        "content": (
            "<span style='color:green;'>🟢 En ligne</span>"
            if ok else
            "<span style='color:red;'>🔴 Hors ligne</span>"
        )
    }


# --- Widget 2 : Nombre de sources GTFS ---
@register_widget
def gtfs_count(request):
    """Widget affichant le nombre de sources GTFS."""
    count = GtfsSource.objects.count()

    return {
        "title": "Sources GTFS",
        "content": f"{count} source(s) disponible(s)"
    }


# --- Widget 3 : Statut Celery Worker ---
@register_widget
def celery_status(request):
    """Widget affichant si le worker Celery répond."""
    try:
        ping = celery_app.control.ping(timeout=1)
        ok = len(ping) > 0
    except Exception:
        ok = False

    return {
        "title": "Celery Worker",
        "content": (
            "<span style='color:green;'>🟢 Actif</span>"
            if ok else
            "<span style='color:red;'>🔴 Inactif</span>"
        )
    }

@register_widget
def eu_gtfs_france(request):
    url = (
        "https://data.europa.eu/api/hub/search/search"
        "?filters=catalogue,dataset,resource"
        "&resource=editorial-content"
        "&limit=200"
        "&page=0"
        "&sort=relevance+desc,+modified+desc,+title.en+asc"
        "&dataServices=false"
        "&countryData=true"
        "&facets=%7B%22dataScope%22%3A%5B%22countryData%22%5D%2C%22country%22%3A%5B%22fr%22%5D%2C%22format%22%3A%5B%22GTFS%22%5D%7D"
    )

    try:
        data = requests.get(url, timeout=25).json()

        # Le nombre correct est ici :
        count = data.get("result", {}).get("count", {}).get("dataset", 0)

        content = f"{count} GTFS disponibles en France"

    except Exception as e:
        content = f"Erreur API EU : {e}"

    return {
        "title": "GTFS France (EU Portal)",
        "content": content
    }

@register_widget
def manage_graphs(request):
    # 1. Récupérer les GTFS en base
    gtfs_sources = GtfsSource.objects.all().order_by("name")

    # 2. Récupérer les fichiers OSM disponibles
    import os
    OSM_DIR = "/data/osm"   # à ajuster
    osm_files = []
    try:
        if os.path.exists(OSM_DIR):
            for f in os.listdir(OSM_DIR):
                if f.endswith(".pbf"):
                    path = os.path.join(OSM_DIR, f)
                    size = os.path.getsize(path)
                    osm_files.append({
                        "name": f,
                        "size": round(size / 1024 / 1024, 1),  # MB
                        "path": path,
                    })
    except Exception as e:
        osm_files = [{"name": "Erreur lecture OSM", "size": 0}]

    # 3. Générer un HTML simple à afficher dans le widget
    html = "<div>"

    html += "<h4>GTFS disponibles</h4>"
    html += "<ul>"
    for g in gtfs_sources:
        html += f"""
            <li>
                <input type='checkbox' name='gtfs' value='{g.source_id}'>
                <strong>{g.name}</strong>
                <small>({g.source_id})</small>
            </li>
        """
    html += "</ul>"

    html += "<h4>OSM disponibles</h4>"
    html += "<ul>"
    for osm in osm_files:
        html += f"""
            <li>
                <input type='checkbox' name='osm' value='{osm["name"]}'>
                {osm["name"]} - {osm["size"]} MB
            </li>
        """
    html += "</ul>"

    # Bouton qui appelle une route Django pour créer une BuildTask
    html += """
        <button onclick="window.location='/build/graph/start/'">
             Construire un graphe Valhalla
        </button>
    """

    html += "</div>"

    return {
        "title": "Gérer les graphes Valhalla",
        "content": html
    }