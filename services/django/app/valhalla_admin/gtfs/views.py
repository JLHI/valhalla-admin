from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import redirect, render
from django.contrib import messages
from valhalla_admin.gtfs.models import GtfsSource
from django.core.cache import cache
import requests
from datetime import datetime
import json
from django.http import JsonResponse
from django.core.cache import cache

@staff_member_required
def add_gtfs_from_eu(request):
    print("\n" + "="*60)
    print("🔍 [DEBUG] add_gtfs_from_eu CALLED")
    print("="*60)

    url = request.GET.get("url")
    name = request.GET.get("name", "Source GTFS")
    publisher = request.GET.get("publisher")
    landing_page = request.GET.get("landing_page")
    gtfs_modified_str = request.GET.get("gtfs_modified")
    source_id = request.GET.get("source_id")

    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"

    # —— DEBUG INPUT ——
    print("📥 Paramètres reçus :")
    print("  source_id      =", source_id)
    print("  url            =", url)
    print("  name           =", name)
    print("  publisher      =", publisher)
    print("  landing_page   =", landing_page)
    print("  gtfs_modified  =", gtfs_modified_str)
    print("  is_ajax        =", is_ajax)

    if not url or not source_id:
        msg = "Données manquantes — impossible d'ajouter la source."
        print("❌ [DEBUG] ERREUR : paramètres manquants")

        if is_ajax:
            return JsonResponse({"status": "error", "message": msg}, status=400)

        messages.error(request, msg)
        return redirect("/gtfs/list/")

    try:
        # —— Parsing de la date ——
        gtfs_modified = None
        if gtfs_modified_str:
            try:
                print("🔧 [DEBUG] Parsing date…")
                gtfs_modified = datetime.fromisoformat(gtfs_modified_str.replace("Z", "+00:00"))
                print("    ➜ Date parsée :", gtfs_modified)
            except Exception as e:
                print("⚠️ [DEBUG] Erreur parsing date :", e)

        # —— Debug AVANT insertion ——
        print("\n🛠 [DEBUG] Tentative get_or_create() avec :")
        print({
            "source_id": source_id,
            "name": name,
            "url": url,
            "publisher": publisher,
            "landing_page": landing_page,
            "gtfs_modified": gtfs_modified,
        })

        obj, created = GtfsSource.objects.get_or_create(
            source_id=source_id,
            defaults={
                "name": name,
                "url": url,
                "publisher": publisher,
                "landing_page": landing_page,
                "gtfs_modified": gtfs_modified,
            },
        )

        # —— Debug résultat ——
        print("\n📦 [DEBUG] get_or_create RESULT :")
        print("  created ?", created)
        print("  object  :", obj)
        print("  PK      :", getattr(obj, "id", None))

        if created:
            cache.delete('gtfs_eu_france_list')
            msg = f"Source ajoutée : {obj.name}"
            status = "created"
            print("✅ [DEBUG] Création OK")
        else:
            msg = "Cette source est déjà importée."
            status = "exists"
            print("ℹ️ [DEBUG] Objet existant — Aucune création")

        # —— Réponse AJAX ——
        if is_ajax:
            print("📤 [DEBUG] Réponse JSON AJAX :", status, msg)
            return JsonResponse({
                "status": status,
                "message": msg,
                "created": created,
                "source_id": obj.source_id,
                "pk": getattr(obj, "id", None),
            })

        # —— Réponse non AJAX ——
        if created:
            messages.success(request, f"✅ {msg}")
        else:
            messages.info(request, f"ℹ️ {msg}")

    except Exception as e:
        msg = f"Erreur lors de l'ajout : {e}"
        print("🔥 [DEBUG] EXCEPTION :", e)

        if is_ajax:
            return JsonResponse({"status": "error", "message": msg}, status=500)

        messages.error(request, f"❌ {msg}")

    print("🏁 [DEBUG] Fin de add_gtfs_from_eu")
    return redirect("/gtfs/list/")


    return redirect("/gtfs/list/")

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
    cache_key = "gtfs_eu_france_list"

    cached_data = cache.get(cache_key)
    if cached_data:
        items = cached_data
    else:
        url = "https://transport.data.gouv.fr/api/datasets?format=gtfs"

        try:
            response = requests.get(url, timeout=25)
            response.raise_for_status()
            datasets = response.json()

            items = []

            for ds in datasets:

                # === ID unique ===
                source_id = str(ds.get("id") or ds.get("slug"))
                if not source_id:
                    continue

                # === TITRE ===
                title = ds.get("title") or "Sans titre"

                # === PUBLISHER (nouvelle source) ===
                publisher = None
                if isinstance(ds.get("publisher"), dict):
                    publisher = ds["publisher"].get("name")
                if not publisher:
                    publisher = "Inconnu"

                # === DATE MISE A JOUR DU DATASET (nouvelle source) ===
                updated_raw = ds.get("updated")
                gtfs_modified = None
                if updated_raw:
                    try:
                        gtfs_modified = datetime.fromisoformat(
                            updated_raw.replace("Z", "+00:00")
                        )
                    except:
                        pass

                # === RESSOURCES → filtrer strictement GTFS + URL ===
                gtfs_url = None
                for r in ds.get("resources", []):
                    if r.get("format", "").upper() == "GTFS" and r.get("url"):
                        gtfs_url = r["url"]
                        break

                # On ignore le dataset si pas de vrai fichier GTFS
                if not gtfs_url:
                    continue

                # === PAGE HTML ===
                landing_page = ds.get("page")

                # === Déjà importé ? ===
                exists = GtfsSource.objects.filter(source_id=source_id).exists()

                # === FORMAT supprimé comme demandé ===
                items.append({
                    "title": title,
                    "publisher": publisher,      # Zenbus / SNCF / etc.
                    "formats": ["GTFS"],         # fixe pour compatibilité Django
                    "landing_page": landing_page,
                    "gtfs_url": gtfs_url,
                    "gtfs_modified": gtfs_modified,
                    "source_id": source_id,
                    "exists": exists,
                })

            cache.set(cache_key, items, 3600)

        except Exception as e:
            return render(request, "gtfs/list.html", {
                "error": str(e),
                "items": [],
                "count": 0,
            })

    imported_ids = set(GtfsSource.objects.values_list("source_id", flat=True))
    for item in items:
        item["exists"] = item["source_id"] in imported_ids

    return render(request, "gtfs/list.html", {
        "items": items,
        "count": len(items),
    })



@staff_member_required
def remove_gtfs(request):
    """Supprime une source GTFS par source_id (support AJAX)."""
    
    source_id = request.GET.get("source_id")
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"

    if not source_id:
        msg = "ID de la source manquant."
        
        if is_ajax:
            return JsonResponse({"status": "error", "message": msg}, status=400)
        
        messages.error(request, msg)
        return redirect("/gtfs/list/")

    try:
        deleted, _ = GtfsSource.objects.filter(source_id=source_id).delete()

        if deleted:
            cache.delete('gtfs_eu_france_list')
            msg = "Source supprimée."
            status = "deleted"
        else:
            msg = "Aucune source trouvée."
            status = "not_found"

        # --- Réponse AJAX ---
        if is_ajax:
            return JsonResponse({
                "status": status,
                "message": msg,
                "source_id": source_id
            })

        # --- Réponse normale ---
        if deleted:
            messages.success(request, f"✅ {msg}")
        else:
            messages.warning(request, f"ℹ️ {msg}")

    except Exception as e:
        msg = f"Erreur lors de la suppression : {e}"

        if is_ajax:
            return JsonResponse({"status": "error", "message": msg}, status=500)

        messages.error(request, f"❌ {msg}")

    return redirect("/gtfs/list/")