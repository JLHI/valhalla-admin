from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, Http404, HttpResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
import shutil

import os
import json
import csv

from .models import BuildTask
from .tasks import start_valhalla_build, ensure_valhalla_running, stop_valhalla_container
from valhalla_admin.gtfs.models import GtfsSource
from .utils import OSM_CATALOG_FR, get_gtfs_date_range
from valhalla_admin.timeutil import parse_datetime_local, to_utc, get_system_timezone
from .docker_manager import ValhallaDockerManager


# ─────────────────────────
# Dashboard & liste
# ─────────────────────────

def dashboard(request):
    """Dashboard de gestion des graphs avec statistiques containers"""
    docker_error = None
    stats = None
    
    try:
        manager = ValhallaDockerManager()
        stats = manager.get_system_stats()
        
        # Enrichir avec les infos DB
        graphs = BuildTask.objects.order_by("-created_at")
        
        # Synchroniser l'état is_serving avec les containers réels
        for graph in graphs:
            try:
                container_status = manager.get_container_status(graph.name)
                running = container_status.get("running", False)
                if graph.is_serving != running or (running and graph.status != "serving"):
                    graph.is_serving = running
                    if running:
                        # Si le container est effectivement actif, refléter l'état
                        graph.status = "serving"
                        if container_status.get("port"):
                            graph.serve_port = container_status["port"]
                        graph.save(update_fields=["is_serving", "status", "serve_port"])
                    else:
                        # Container arrêté: ne pas écraser un statut en cours (building),
                        # mais si prêt et marqué erreur, repasser à "built".
                        update_fields = ["is_serving"]
                        if graph.is_ready and graph.status == "error":
                            graph.status = "built"
                            update_fields.append("status")
                        graph.save(update_fields=update_fields)
            except Exception:
                pass  # Si un container pose problème, continuer avec les autres
            # Annoter plage de disponibilité GTFS
            try:
                s, e = get_gtfs_date_range(graph)
                graph.gtfs_start = s
                graph.gtfs_end = e
            except Exception:
                graph.gtfs_start = None
                graph.gtfs_end = None
                
    except Exception as e:
        docker_error = str(e)
        graphs = BuildTask.objects.order_by("-created_at")
        # Annoter plage de disponibilité GTFS même en cas d'erreur docker
        for graph in graphs:
            try:
                s, e = get_gtfs_date_range(graph)
                graph.gtfs_start = s
                graph.gtfs_end = e
            except Exception:
                graph.gtfs_start = None
                graph.gtfs_end = None
        stats = {
            "total_containers": 0,
            "running_containers": 0,
            "stopped_containers": 0,
            "containers": []
        }
    
    return render(request, "graph/dashboard.html", {
        "section": "dashboard",
        "stats": stats,
        "graphs": graphs,
        "docker_error": docker_error,
    })


def graph_list(request):
    graphs = BuildTask.objects.order_by("-created_at")
    # Annoter plage de disponibilité GTFS pour la liste
    for g in graphs:
        try:
            s, e = get_gtfs_date_range(g)
            g.gtfs_start = s
            g.gtfs_end = e
        except Exception:
            g.gtfs_start = None
            g.gtfs_end = None
    return render(request, "graph/list.html", {
        "section": "list",
        "graphs": graphs,
    })


# ─────────────────────────
# Création d’un graph
# ─────────────────────────

OSM_DIR = "/data/sources/osm"
GRAPH_ROOT = "/data/graphs"


def graph_create(request):
    # ─────────────────────────
    # POST → création de tâche
    # ─────────────────────────
    if request.method == "POST":
        graph_name = request.POST.get("graph_name")
        osm_names = request.POST.getlist("osm")  # plusieurs checkbox possibles
        custom_osm_urls = (request.POST.get("osm_url") or "").strip()
        selected_gtfs = request.POST.getlist("gtfs")

        # Parse custom URLs (séparées par virgule ou espace)
        custom_osm_list = []
        if custom_osm_urls:
            for part in custom_osm_urls.split(","):
                url = part.strip()
                if url:
                    custom_osm_list.append(url)

        # Fusionner les deux sources (checkbox + URLs)
        all_osm = osm_names + custom_osm_list

        # Sauvegarde des fichiers GTFS uploadés (optionnels)
        uploaded_files = request.FILES.getlist("gtfs_zips")
        schedule_at_raw = (request.POST.get("schedule_at") or "").strip()
        schedule_eta = None
        if schedule_at_raw:
            # Centralized parsing according to configured system timezone
            schedule_dt_local = parse_datetime_local(schedule_at_raw)
            if schedule_dt_local and schedule_dt_local > timezone.now():
                schedule_eta = to_utc(schedule_dt_local)

        # Stocker la liste sous forme de chaîne séparée par des virgules
        osm_value = ",".join(all_osm)

        if graph_name and osm_value:
            task = BuildTask.objects.create(
                name=graph_name,
                osm_file=osm_value,
                gtfs_ids=selected_gtfs,
                status="pending",
                serve_port=None,  # port réel attribué au démarrage du container
            )

            # Créer le dossier du graph et stocker les zips uploadés pour que le worker les traite
            try:
                graph_dir = os.path.join(GRAPH_ROOT, graph_name)
                uploads_dir = os.path.join(graph_dir, "gtfs_uploaded")
                os.makedirs(uploads_dir, exist_ok=True)
                saved_count = 0
                for f in uploaded_files:
                    # n'accepter que .zip
                    fname = os.path.basename(f.name or "")
                    if not fname.lower().endswith(".zip"):
                        continue
                    # chemin final
                    dest_path = os.path.join(uploads_dir, fname)
                    # écriture par chunks
                    with open(dest_path, "wb") as out:
                        for chunk in f.chunks():
                            out.write(chunk)
                    saved_count += 1
                if saved_count:
                    task.add_log(f"📥 {saved_count} fichier(s) GTFS .zip uploadé(s) en attente de traitement")
                    task.save(update_fields=["logs"])
            except Exception as e:
                try:
                    task.add_log(f"⚠️ Échec sauvegarde des zips uploadés: {e}")
                except Exception:
                    pass

            # Planifier ou lancer immédiatement
            if schedule_eta:
                try:
                    start_valhalla_build.apply_async(args=[task.id], eta=schedule_eta)
                    # Display planned time in system timezone
                    try:
                        disp = schedule_eta.astimezone(get_system_timezone())
                    except Exception:
                        disp = schedule_eta
                    task.add_log(f"🗓 Build planifié pour {disp}")
                    task.save(update_fields=["logs"])
                except Exception:
                    start_valhalla_build.delay(task.id)
            else:
                start_valhalla_build.delay(task.id)

            # 👉 retour sur la page avec la tâche sélectionnée et affichage des logs
            return redirect(f"/graphs/create/?task={task.id}&show=logs")

    # ─────────────────────────
    # GET → affichage
    # ─────────────────────────
    gtfs = GtfsSource.objects.all().order_by("name")
    tasks = BuildTask.objects.order_by("-created_at")

    task_id = request.GET.get("task")

    if task_id:
        graph = BuildTask.objects.filter(id=task_id).first()
    else:
        graph = tasks.first()  # dernière tâche par défaut

    return render(request, "graph/create.html", {
        "section": "create",
        "gtfs": gtfs,
        "osm_catalog": OSM_CATALOG_FR,
        "graph": graph,
        "tasks": tasks,
        "show_logs": (request.GET.get("show") == "logs"),
    })

# ─────────────────────────
# Page dédiée: logs d'une tâche
# ─────────────────────────
def graph_logs(request, task_id: int):
    task = get_object_or_404(BuildTask, id=task_id)
    # Annoter plage GTFS pour contexte, si dispo
    try:
        s, e = get_gtfs_date_range(task)
    except Exception:
        s, e = None, None
    return render(request, "graph/logs.html", {
        "section": "logs",
        "graph": task,
        "gtfs_start": s,
        "gtfs_end": e,
    })

# ─────────────────────────
# Re-création d'un graph (même nom, mêmes GTFS/OSM) avec planification possible
# ─────────────────────────
@require_POST
def recreate_task(request, task_id: int):
    original = get_object_or_404(BuildTask, id=task_id)
    schedule_at_raw = (request.POST.get("schedule_at") or "").strip()
    schedule_eta = None
    if schedule_at_raw:
        dt_local = parse_datetime_local(schedule_at_raw)
        if dt_local and dt_local > timezone.now():
            schedule_eta = to_utc(dt_local)

    # Créer une nouvelle tâche avec les mêmes paramètres
    task = BuildTask.objects.create(
        name=original.name,
        osm_file=original.osm_file,
        gtfs_ids=original.gtfs_ids,
        status="pending",
        serve_port=None,
    )

    # Journal
    task.add_log("♻️ Re-création planifiée depuis une tâche existante")

    # Lancer ou planifier
    if schedule_eta:
        try:
            start_valhalla_build.apply_async(args=[task.id], eta=schedule_eta)
            try:
                disp = schedule_eta.astimezone(get_system_timezone())
            except Exception:
                disp = schedule_eta
            task.add_log(f"🗓 Build planifié pour {disp}")
            task.save(update_fields=["logs"])
        except Exception:
            start_valhalla_build.delay(task.id)
    else:
        start_valhalla_build.delay(task.id)

    return redirect(f"/graphs/create/?task={task.id}&show=logs")

# ─────────────────────────
# Endpoint STATUS (polling JS)
# ─────────────────────────

def graph_status(request, name):
    graph = (
        BuildTask.objects
        .filter(name=name)
        .order_by("-created_at")
        .first()
    )
    # Préparer un aperçu performant: 50 premières lignes + 50 dernières
    logs_text = graph.logs or ""
    lines = logs_text.splitlines()
    total = len(lines)
    head_count = 50
    tail_count = 50

    head = lines[:head_count]
    tail = lines[-tail_count:] if total > tail_count else lines

    # Insérer un séparateur si on tronque au milieu
    if total > head_count + tail_count:
        preview_lines = head + ["… (logs tronqués, utiliser le bouton pour tout afficher) …"] + tail
    else:
        preview_lines = lines

    preview_text = "\n".join(preview_lines)

    # Détecter un silence prolongé (possible SIGKILL/OOM) : si status=building et
    # aucun log récent depuis >10 minutes.
    warning = None
    if graph.status == "building" and lines:
        last_ts = None
        for l in reversed(lines):
            if l.startswith("[") and "]" in l:
                candidate = l.split("]", 1)[0].lstrip("[")
                try:
                    last_ts = timezone.datetime.fromisoformat(candidate)
                    if timezone.is_naive(last_ts):
                        last_ts = timezone.make_aware(last_ts, timezone.utc)
                    break
                except Exception:
                    continue
        if last_ts:
            delta = timezone.now() - last_ts
            if delta.total_seconds() > 600:
                warning = "Aucun log récent (>10 min). Le build peut avoir été tué (SIGKILL/OOM). Relancez après vérif mémoire."

    return JsonResponse({
        "name": graph.name,
        "status": graph.status,
        "ready": getattr(graph, "is_ready", False),
        "serving": getattr(graph, "is_serving", False),
        # Compat: certaines vues attendent "logs" → fournir le preview dans ce champ
        "logs": preview_text,
        # Et fournir aussi explicitement le champ preview pour les nouvelles vues
        "logs_preview": preview_text,
        "logs_total_lines": total,
        "logs_head_count": head_count,
        "logs_tail_count": tail_count,
        "warning": warning,
    })


# ─────────────────────────
# Détail / accès graph
# ─────────────────────────

def graph_detail(request, name):
    graph = (
    BuildTask.objects
    .filter(name=name)
    .order_by("-created_at")
    .first()
    )

    if not graph.is_ready:
        return JsonResponse({
            "name": graph.name,
            "ready": False,
            "status": graph.status,
            "message": "Graph en cours de construction",
        }, status=202)

    if not graph.is_serving:
        ensure_valhalla_running.delay(graph.id)
        return JsonResponse({
            "name": graph.name,
            "ready": True,
            "serving": False,
            "message": "Graph prêt, démarrage de Valhalla…",
        }, status=202)

    return JsonResponse({
        "name": graph.name,
        "ready": True,
        "serving": True,
        "message": "Graph prêt et servi",
        "endpoint": f"/{graph.name}/route",
    })

# ─────────────────────────
# Carte (placeholder simple)
# ─────────────────────────
def graph_map(request, name):
    graph = (
        BuildTask.objects
        .filter(name=name)
        .order_by("-created_at")
        .first()
    )
    if not graph:
        raise Http404("Graph introuvable")

    # Tenter de récupérer l'état/port réel du container si non renseigné
    serve_url = None
    try:
        from .docker_manager import ValhallaDockerManager
        manager = ValhallaDockerManager()
        status = manager.get_container_status(graph.name)
        if status.get("running") and status.get("port"):
            serve_url = f"http://localhost:{status['port']}"
            # Garder la DB cohérente si besoin
            if (not graph.is_serving) or (graph.serve_port != status["port"]):
                graph.is_serving = True
                graph.serve_port = status["port"]
                try:
                    graph.save(update_fields=["is_serving", "serve_port"])
                except Exception:
                    pass
    except Exception:
        # Ignorer erreurs docker, on retombe sur le champ existant
        pass
    if not serve_url and graph.serve_port:
        serve_url = f"http://localhost:{graph.serve_port}"

    # Fournir infos minimales pour une page carte simple
    context = {
        "section": "list",
        "graph": graph,
        "serve_url": serve_url,
    }
    # Ajouter disponibilités GTFS
    try:
        s, e = get_gtfs_date_range(graph)
        context["gtfs_start"] = s
        context["gtfs_end"] = e
    except Exception:
        context["gtfs_start"] = None
        context["gtfs_end"] = None
    return render(request, "graph/map.html", context)


# Removed proxy helpers by request (no proxy)


def graph_stops_geojson(request, name):
    """Retourne les arrêts GTFS du graphe en GeoJSON FeatureCollection.
       Optionnel: filtrage par bbox via ?bbox=minLon,minLat,maxLon,maxLat
    """
    task = (
        BuildTask.objects
        .filter(name=name)
        .order_by("-created_at")
        .first()
    )
    if not task:
        raise Http404("Graph introuvable")

    gtfs_root = os.path.join(task.output_dir or "", "gtfs")
    if not os.path.isdir(gtfs_root):
        return JsonResponse({"type": "FeatureCollection", "features": []})

    # BBox facultative
    bbox_param = request.GET.get("bbox")
    bbox = None
    if bbox_param:
        try:
            parts = [float(p) for p in bbox_param.split(",")]
            if len(parts) == 4:
                minlon, minlat, maxlon, maxlat = parts
                bbox = (minlon, minlat, maxlon, maxlat)
        except Exception:
            bbox = None

    def in_bbox(lon, lat):
        if not bbox:
            return True
        return (bbox[0] <= lon <= bbox[2]) and (bbox[1] <= lat <= bbox[3])

    features = []

    # Si des IDs GTFS sont connus, cibler ces sous-dossiers, sinon parcourir tous
    subdirs = []
    if isinstance(task.gtfs_ids, list) and task.gtfs_ids:
        # Les dossiers sont nommés par source_id (champ GTFS) dans le pipeline
        # On liste pour trouver correspondance
        try:
            subdirs = [d for d in os.listdir(gtfs_root) if os.path.isdir(os.path.join(gtfs_root, d))]
        except Exception:
            subdirs = []
    else:
        try:
            subdirs = [d for d in os.listdir(gtfs_root) if os.path.isdir(os.path.join(gtfs_root, d))]
        except Exception:
            subdirs = []

    for sd in subdirs:
        stops_path = os.path.join(gtfs_root, sd, "stops.txt")
        if not os.path.exists(stops_path):
            continue
        try:
            with open(stops_path, "r", encoding="utf-8", errors="ignore") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        lat = float(row.get("stop_lat", ""))
                        lon = float(row.get("stop_lon", ""))
                    except Exception:
                        continue
                    if not in_bbox(lon, lat):
                        continue
                    props = {
                        "feed": sd,
                        "stop_id": row.get("stop_id", ""),
                        "stop_code": row.get("stop_code", ""),
                        "stop_name": row.get("stop_name", ""),
                        "zone_id": row.get("zone_id", ""),
                    }
                    features.append({
                        "type": "Feature",
                        "geometry": {"type": "Point", "coordinates": [lon, lat]},
                        "properties": props,
                    })
        except Exception:
            # Ignorer les erreurs de fichiers individuels
            continue

    return JsonResponse({
        "type": "FeatureCollection",
        "features": features
    })
# ─────────────────────────
# Détail / supprimer task
# ─────────────────────────

@require_POST
def delete_task(request, task_id):
    task = BuildTask.objects.filter(id=task_id).first()

    if not task:
        return redirect("/graphs/create/")

    # Essayer d'annuler les tâches Celery actives/réservées liées à ce build
    try:
        from valhalla_admin.celery import app as celery_app
        i = celery_app.control.inspect()
        to_revoke = []
        names = {
            "valhalla_admin.graph.tasks.start_valhalla_build",
            "valhalla_admin.graph.tasks.run_valhalla_build",
            "valhalla_admin.graph.tasks.ensure_valhalla_running",
            "valhalla_admin.graph.tasks.stop_valhalla_container",
        }
        def collect(tasks_dict):
            if not isinstance(tasks_dict, dict):
                return
            for worker, tasks in tasks_dict.items():
                for t in tasks or []:
                    try:
                        tn = t.get("name")
                        tid = t.get("id")
                        args = t.get("argsrepr") or ""
                        kwargs = t.get("kwargs") or {}
                        if tn in names and (str(task.id) in str(args) or str(task.id) in str(kwargs)):
                            to_revoke.append(tid)
                    except Exception:
                        continue
        collect(getattr(i, "active")() or {})
        collect(getattr(i, "reserved")() or {})
        collect(getattr(i, "scheduled")() or {})
        for tid in set(to_revoke):
            try:
                celery_app.control.revoke(tid, terminate=True)
            except Exception:
                pass
    except Exception:
        pass

    # Arrêter et supprimer le container si actif
    try:
        manager = ValhallaDockerManager()
        manager.remove_container(task.name, force=True)
    except Exception:
        pass

    if task.output_dir and os.path.exists(task.output_dir):
        shutil.rmtree(task.output_dir, ignore_errors=True)

    task.delete()

    return redirect("/graphs/create/")


# ─────────────────────────
# Gestion des containers
# ─────────────────────────

@require_POST
def start_container(request, task_id):
    """Démarre le container d'un graph"""
    task = get_object_or_404(BuildTask, id=task_id)
    
    if not task.is_ready:
        return JsonResponse({
            "success": False,
            "message": "Le graph n'est pas encore prêt"
        }, status=400)
    
    ensure_valhalla_running.delay(task.id)
    
    return JsonResponse({
        "success": True,
        "message": "Démarrage du container en cours..."
    })


@require_POST
def stop_container(request, task_id):
    """Arrête le container d'un graph"""
    task = get_object_or_404(BuildTask, id=task_id)
    
    stop_valhalla_container.delay(task.id)
    
    return JsonResponse({
        "success": True,
        "message": "Arrêt du container en cours..."
    })


@require_POST
def restart_container(request, task_id):
    """Redémarre le container d'un graph"""
    task = get_object_or_404(BuildTask, id=task_id)
    
    try:
        manager = ValhallaDockerManager()
        result = manager.restart_container(task.name)
        
        if result["status"] == "restarted":
            task.is_serving = True
            task.serve_port = result.get("port")
            task.add_log("🔄 Container redémarré")
            task.save()
            
            return JsonResponse({
                "success": True,
                "message": result["message"],
                "port": result.get("port")
            })
        else:
            return JsonResponse({
                "success": False,
                "message": result.get("message", "Erreur inconnue")
            }, status=400)
            
    except Exception as e:
        return JsonResponse({
            "success": False,
            "message": str(e)
        }, status=500)


def container_status_api(request, task_id):
    """API pour récupérer le statut d'un container"""
    task = get_object_or_404(BuildTask, id=task_id)
    
    try:
        manager = ValhallaDockerManager()
        status = manager.get_container_status(task.name)
        
        # Synchroniser l'état DB
        if status.get("running") != task.is_serving:
            task.is_serving = status.get("running", False)
            if status.get("port"):
                task.serve_port = status["port"]
            task.save(update_fields=["is_serving", "serve_port"])
        
        return JsonResponse({
            "success": True,
            "graph_name": task.name,
            "status": status
        })
        
    except Exception as e:
        return JsonResponse({
            "success": False,
            "message": str(e)
        }, status=500)


# ─────────────────────────
# Configuration valhalla_serve.json (GET/POST)
# ─────────────────────────
def _get_task_by_name_or_404(name: str) -> BuildTask:
    task = (
        BuildTask.objects
        .filter(name=name)
        .order_by("-created_at")
        .first()
    )
    if not task:
        raise Http404("Graph introuvable")
    return task


def graph_config(request, name):
    """GET → retourne le contenu JSON de valhalla_serve.json
       POST → met à jour le valhalla_serve.json (backup + écriture),
               optionnellement redémarre le container si ?restart=true
    """
    task = _get_task_by_name_or_404(name)
    serve_path = os.path.join(task.output_dir or "", "valhalla_serve.json")
    base_path = os.path.join(task.output_dir or "", "valhalla.json")

    if request.method == "GET":
        # Si valhalla_serve.json n'existe pas encore, tenter de le dériver
        if not os.path.exists(serve_path):
            if os.path.exists(base_path):
                try:
                    with open(base_path, "r") as f:
                        cfg = json.load(f)

                    def replace_paths(obj):
                        if isinstance(obj, dict):
                            return {k: replace_paths(v) for k, v in obj.items()}
                        elif isinstance(obj, list):
                            return [replace_paths(item) for item in obj]
                        elif isinstance(obj, str) and task.output_dir in obj:
                            return obj.replace(task.output_dir, "/data/valhalla")
                        return obj

                    cfg = replace_paths(cfg)
                    # Inject default CORS
                    try:
                        httpd = cfg.setdefault("httpd", {})
                        service = httpd.setdefault("service", {})
                        ac = service.setdefault("access_control", {})
                        ac.setdefault("allow_origin", "*")
                        ac.setdefault("allow_methods", "GET, POST, OPTIONS")
                        ac.setdefault("allow_headers", "Content-Type")
                    except Exception:
                        pass

                    return JsonResponse(cfg)
                except Exception as e:
                    return JsonResponse({"error": f"Lecture/derivation impossible: {str(e)}"}, status=500)
            else:
                return JsonResponse({"error": "Aucun fichier de configuration disponible"}, status=404)

        try:
            with open(serve_path, "r") as f:
                data = f.read()
            # Retourner tel quel pour préserver formatation (indentation)
            return HttpResponse(data, content_type="application/json")
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    # POST → enregistrer
    try:
        body = request.body.decode("utf-8")
        payload = json.loads(body)
    except Exception as e:
        return JsonResponse({"success": False, "message": f"JSON invalide: {str(e)}"}, status=400)

    # Validation via schema (basique: types + enums)
    def _load_schema() -> dict:
        schema_path = os.path.join(os.path.dirname(__file__), "..", "config", "valhalla_schema.json")
        try:
            with open(schema_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _validate_against_schema(cfg: dict, schema: dict) -> str:
        # Très légère validation: uniquement quelques propriétés typées / enums
        try:
            httpd = cfg.get("httpd", {})
            service = httpd.get("service", {})
            if "listen" in service and not isinstance(service["listen"], str):
                return "httpd.service.listen doit être une chaîne"
            for num_key in ("timeout_seconds", "shutdown_seconds"):
                if num_key in service and not isinstance(service[num_key], (int, float)):
                    return f"httpd.service.{num_key} doit être numérique"

            loki = cfg.get("loki", {})
            actions = loki.get("actions")
            if actions is not None:
                if not isinstance(actions, list):
                    return "loki.actions doit être une liste"
                allowed = [
                    "locate","route","height","sources_to_targets","optimized_route",
                    "isochrone","trace_route","trace_attributes","transit_available",
                    "expansion","centroid","status"
                ]
                for a in actions:
                    if a not in allowed:
                        return f"loki.actions contient une action inconnue: {a}"

            mj = cfg.get("mjolnir", {})
            for key in ["tile_dir", "tile_extract", "timezone", "transit_dir", "transit_feeds_dir"]:
                if key in mj and not isinstance(mj[key], str):
                    return f"mjolnir.{key} doit être une chaîne"
        except Exception:
            return "Erreur de validation"
        return ""

    schema = _load_schema()
    err = _validate_against_schema(payload, schema)
    if err:
        return JsonResponse({"success": False, "message": err}, status=400)

    # Backup puis écriture (sauf dry-run)
    try:
        dry_run = request.GET.get("dry_run") in ["1", "true", "True"]
        if not dry_run:
            os.makedirs(os.path.dirname(serve_path), exist_ok=True)
            if os.path.exists(serve_path):
                ts = timezone.now().strftime("%Y%m%d-%H%M%S")
                bak = serve_path + f".{ts}.bak"
                shutil.copyfile(serve_path, bak)

            # Normaliser automatiquement les chemins mjolnir dans /data/valhalla
            mj = payload.get("mjolnir", {})
            for key in ["tile_dir", "tile_extract", "timezone", "transit_dir", "transit_feeds_dir"]:
                if key in mj and isinstance(mj[key], str):
                    if not mj[key].startswith("/data/valhalla") and "/data/" in mj[key]:
                        # Re-map naïf vers /data/valhalla pour éviter des chemins hors mount
                        tail = mj[key].split("/data/")[1]
                        mj[key] = "/data/valhalla/" + tail.split("/", 1)[1] if "/" in tail else "/data/valhalla/" + tail
            payload["mjolnir"] = mj

            with open(serve_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)

    except Exception as e:
        return JsonResponse({"success": False, "message": f"Écriture impossible: {str(e)}"}, status=500)

    # Optionnellement redémarrer
    restart = (request.GET.get("restart") in ["1", "true", "True"]) and not dry_run
    restart_result = None
    if restart:
        try:
            manager = ValhallaDockerManager()
            restart_result = manager.restart_container(task.name)
            if restart_result.get("status") == "restarted":
                task.is_serving = True
                task.serve_port = restart_result.get("port")
                task.add_log("🔄 Config mise à jour, container redémarré")
                task.save(update_fields=["is_serving", "serve_port", "logs"])
            else:
                return JsonResponse({
                    "success": False,
                    "message": restart_result.get("message", "Redémarrage échoué")
                }, status=400)
        except Exception as e:
            return JsonResponse({"success": False, "message": str(e)}, status=500)

    return JsonResponse({
        "success": True,
        "message": "Validation OK" if dry_run else "Configuration sauvegardée",
        "dry_run": dry_run,
        "restarted": bool(restart),
        "restart": restart_result or {}
    })


def config_schema(request):
    schema_path = os.path.join(os.path.dirname(__file__), "..", "config", "valhalla_schema.json")
    try:
        with open(schema_path, "r", encoding="utf-8") as f:
            return HttpResponse(f.read(), content_type="application/json")
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


def config_tooltips(request):
    tips_path = os.path.join(os.path.dirname(__file__), "..", "config", "valhalla_tooltips.json")
    try:
        with open(tips_path, "r", encoding="utf-8") as f:
            return HttpResponse(f.read(), content_type="application/json")
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)