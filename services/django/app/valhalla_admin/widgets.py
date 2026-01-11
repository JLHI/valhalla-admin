import requests
from valhalla_admin.home_widgets import register_widget
from valhalla_admin.graph.models import BuildTask


# --- Widget 1 : Statut Valhalla + Graphs ---
@register_widget
def valhalla_status(request):
    """Widget affichant le statut Valhalla basé sur les graphs servis et un résumé des graphs."""
    # Dans notre setup, Valhalla est servi par graph via des containers dédiés avec ports dynamiques.
    # Considérer Valhalla "en ligne" si au moins un graph est en état serving.
    try:
        ok = BuildTask.objects.filter(is_serving=True).exists()
    except Exception:
        ok = False

    # Récupérer les graphs
    try:
        graphs = BuildTask.objects.order_by("-created_at")[:10]
        total = BuildTask.objects.count()
    except Exception:
        graphs = []
        total = 0

    def badge(status: str) -> str:
        if status == "serving":
            return "<span style='background:#4caf50;color:#fff;padding:2px 8px;border-radius:10px;font-size:11px;'>🟢 serving</span>"
        if status == "built":
            return "<span style='background:#2196f3;color:#fff;padding:2px 8px;border-radius:10px;font-size:11px;'>✓ built</span>"
        if status == "building":
            return "<span style='background:#ff9800;color:#fff;padding:2px 8px;border-radius:10px;font-size:11px;'>🔨 building</span>"
        if status == "error":
            return "<span style='background:#f44336;color:#fff;padding:2px 8px;border-radius:10px;font-size:11px;'>❌ error</span>"
        return f"<span style='background:#9e9e9e;color:#fff;padding:2px 8px;border-radius:10px;font-size:11px;'>{status}</span>"

    rows = []
    for g in graphs:
        port = f"<code style='margin-left:6px'>{g.serve_port}</code>" if getattr(g, "serve_port", None) else ""
        rows.append(f"<li><strong>{g.name}</strong> {badge(g.status)}{port}</li>")

    content = []
    content.append("<div style='margin-bottom:6px'>" + (
        "<span style='color:green;'>🟢 Valhalla</span>" if ok else "<span style='color:red;'>🔴 Valhalla</span>"
    ) + f" — Graphs: {total}</div>")
    if rows:
        content.append("<ul style='margin:0;padding-left:16px;font-size:12px'>" + "".join(rows) + "</ul>")
    else:
        content.append("<div style='color:#777;font-size:12px'>Aucun graph pour le moment.</div>")

    return {
        "title": "Valhalla & Graphs",
        "content": "".join(content)
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
