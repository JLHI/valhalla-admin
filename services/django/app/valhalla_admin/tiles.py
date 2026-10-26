import os
import time
from pathlib import Path

import requests
from django.conf import settings
from django.http import HttpResponse, HttpResponseBadRequest
from django.views.decorators.http import require_GET

# Politique OSM : https://operations.osmfoundation.org/policies/tiles/
# - Referer et User-Agent identifiant l'application obligatoires
# - cache local d'au moins 7 jours
OSM_TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"


@require_GET
def osm_tile(request, z, x, y):
    """Proxy des tuiles OSM avec cache disque (le navigateur peut supprimer le Referer)."""
    if z > 19 or x >= 2 ** z or y >= 2 ** z:
        return HttpResponseBadRequest("Tuile hors limites")

    cache_dir = Path(settings.OSM_TILE_CACHE_DIR)
    tile_path = cache_dir / str(z) / str(x) / f"{y}.png"

    if tile_path.exists() and time.time() - tile_path.stat().st_mtime < settings.OSM_TILE_CACHE_TTL:
        return _tile_response(tile_path.read_bytes())

    try:
        resp = requests.get(
            OSM_TILE_URL.format(z=z, x=x, y=y),
            headers={
                "User-Agent": settings.OSM_TILE_USER_AGENT,
                "Referer": settings.OSM_TILE_REFERER or request.build_absolute_uri("/"),
            },
            timeout=15,
        )
    except requests.RequestException:
        resp = None

    # Réponse invalide ou tuile de blocage OSM (200 + en-tête x-blocked) : ne jamais la mettre en cache
    if resp is None or resp.status_code != 200 or "x-blocked" in resp.headers:
        if tile_path.exists():
            # Tuile périmée plutôt que rien
            return _tile_response(tile_path.read_bytes())
        status = 502 if resp is None or resp.status_code == 200 else resp.status_code
        return HttpResponse(status=status)

    tile_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = tile_path.with_suffix(f".{os.getpid()}.tmp")
    tmp_path.write_bytes(resp.content)
    os.replace(tmp_path, tile_path)
    return _tile_response(resp.content)


def _tile_response(content):
    response = HttpResponse(content, content_type="image/png")
    response["Cache-Control"] = "public, max-age=86400"
    return response
