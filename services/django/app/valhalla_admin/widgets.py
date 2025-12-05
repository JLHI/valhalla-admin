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
