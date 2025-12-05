from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import redirect, render
from valhalla_admin.gtfs.models import GtfsSource
import requests
from datetime import datetime

@staff_member_required
def add_gtfs_from_eu(request):
    url = request.GET.get("url")
    name = request.GET.get("name", "Source GTFS")

    if url:
        GtfsSource.objects.get_or_create(
            name=name,
            defaults={"url": url},
        )

    return redirect("/admin/")

def normalize_title(title):
    """Normalise un titre pouvant être dict, liste ou string."""
    if isinstance(title, dict):
        return title.get("fr") or title.get("en") or next(iter(title.values()), None)
    if isinstance(title, list) and title:
        return title[0]
    return title or "(Sans titre)"


def normalize_publisher(pub):
    """Récupère le nom de l'éditeur, quelle que soit la structure."""
    if not pub:
        return None
    if "name" in pub:
        return pub["name"]
    if isinstance(pub, list) and pub:
        # structure parfois vue dans l'API
        name = pub[0].get("title")
        if isinstance(name, list):
            return name[0]
        if isinstance(name, dict):
            return name.get("fr") or name.get("en")
    return None


def extract_formats(item):
    """Extraction unique des formats disponibles."""
    formats = set()
    for d in item.get("distributions", []):
        fmt = d.get("format", {})
        if isinstance(fmt, dict):
            formats.add(fmt.get("label") or fmt.get("id"))
        else:
            formats.add(str(fmt))
    return sorted(f for f in formats if f)


def extract_gtfs_url(item):
    """Trouve la première distribution GTFS."""
    for dist in item.get("distributions", []):
        fmt = dist.get("format", {})
        fmt_id = fmt.get("id", "").upper()
        if fmt_id == "GTFS":
            urls = dist.get("download_url") or dist.get("access_url")
            if isinstance(urls, list):
                return urls[0]
            return urls
    return None


def gtfs_list(request):
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
        response = requests.get(url, timeout=25)
        data = response.json()
        results = data.get("result", {}).get("results", [])

        items = []

        for src in results:

            # === TITRE ===
            title = "Sans titre"
            if isinstance(src.get("title"), dict):
                title = src["title"].get("fr") or src["title"].get("en") or "Sans titre"

            # === PUBLISHER ===
            publisher = src.get("publisher", {}).get("name")

            # === DISTRIBUTIONS ===
            formats = []
            gtfs_url = None
            gtfs_modified = None

            for d in src.get("distributions", []):

                # formats disponibles
                fmt = d.get("format", {})
                fmt_label = fmt.get("label")
                if fmt_label:
                    formats.append(fmt_label)

                fmt_id = fmt.get("id", "").lower()

                # === Trouver la distribution GTFS ===
                if fmt_id == "gtfs":
                    urls = d.get("download_url") or d.get("access_url") or []
                    if isinstance(urls, list) and urls:
                        gtfs_url = urls[0]
                    elif isinstance(urls, str):
                        gtfs_url = urls

                    # conversion automatique de la date
                    raw_mod = d.get("modified")
                    if raw_mod:
                        try:
                            gtfs_modified = datetime.fromisoformat(raw_mod.replace("Z", "+00:00"))
                        except Exception:
                            pass

                    break  # on a trouvé GTFS → stop

            # === LANDING PAGE ===
            landing_page = None
            lp = src.get("landing_page")
            if isinstance(lp, list) and lp:
                landing_page = lp[0].get("resource")

            # === déjà importé ? ===
            exists = bool(gtfs_url and GtfsSource.objects.filter(url=gtfs_url).exists())

            items.append({
                "title": title,
                "publisher": publisher,
                "formats": formats,
                "landing_page": landing_page,
                "gtfs_url": gtfs_url,
                "gtfs_modified": gtfs_modified,  # maintenant un datetime
                "exists": exists,
            })

    except Exception as e:
        return render(request, "gtfs/list.html", {
            "error": str(e),
            "items": [],
            "count": 0,
        })

    return render(request, "gtfs/list.html", {
        "items": items,
        "count": len(items),
    })