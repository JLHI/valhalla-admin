# graph/tasks.py
import os
import json
import zipfile
import shutil
import subprocess
import requests
import time
import csv
from datetime import datetime

from celery import shared_task
from django.db import DatabaseError
from django.utils import timezone

from .models import BuildTask
from valhalla_admin.gtfs.models import GtfsSource
from valhalla_admin.gtfs.utils import ensure_calendar_augmented
from .utils import OSM_CATALOG_FR


# ─────────────────────────
# PATHS (montés dans le conteneur Valhalla)
# ─────────────────────────

GRAPH_ROOT = "/data/graphs"          # /data/graphs/<graph_name>
OSM_SOURCE_DIR = "/data/sources/osm"


# ─────────────────────────
# PHASE 1 — PRÉPARATION
# ─────────────────────────

@shared_task(bind=True)
def start_valhalla_build(self, task_id):
    try:
        task = BuildTask.objects.get(id=task_id)
        # Concurrency guard: prevent multiple builds for the same graph name
        try:
            conflict = (
                BuildTask.objects
                .filter(name=task.name)
                .exclude(id=task.id)
                .filter(status__in=["preparing","building"]) 
                .exists()
            )
        except Exception:
            conflict = False
        if conflict:
            task.status = "error"
            task.add_log("⛔ Build déjà en cours pour ce graph — annulation de cette tâche")
            _safe_save(task)
            return
        # ── statut
        task.status = "preparing"
        task.started_at = timezone.now()
        task.add_log("🧩 Préparation des données (OSM + GTFS)")
        _safe_save(task)

        # ── dossier du graph
        graph_dir = os.path.join(GRAPH_ROOT, task.name)
        os.makedirs(graph_dir, exist_ok=True)
        task.output_dir = graph_dir
        task.add_log(f"📁 Graph dir : {graph_dir}")

        # ─────────────────────────
        # OSM → COPIE dans <graph>/osm/
        # ─────────────────────────
        osm_source = get_osm_file(task)

        osm_dir = os.path.join(graph_dir, "osm")
        os.makedirs(osm_dir, exist_ok=True)

        osm_dest = os.path.join(osm_dir, os.path.basename(osm_source))
        if not os.path.exists(osm_dest):
            shutil.copy(osm_source, osm_dest)

        task.add_log(f"🗺 OSM prêt : {osm_dest}")

        # ─────────────────────────
        # GTFS → upload local + download + unzip
        # ─────────────────────────
        gtfs_dir = os.path.join(graph_dir, "gtfs")
        # Nettoyer pour forcer re-téléchargement à chaque build planifié/recréé
        try:
            if os.path.isdir(gtfs_dir):
                shutil.rmtree(gtfs_dir, ignore_errors=True)
        except Exception:
            pass
        os.makedirs(gtfs_dir, exist_ok=True)

        # 1) Traiter d'abord les zips uploadés côté Django (si présents)
        uploads_dir = os.path.join(graph_dir, "gtfs_uploaded")
        uploaded_zips = []
        try:
            if os.path.isdir(uploads_dir):
                uploaded_zips = [f for f in os.listdir(uploads_dir) if f.lower().endswith('.zip')]
        except Exception:
            uploaded_zips = []
        if uploaded_zips:
            task.add_log(f"📥 Zips GTFS uploadés détectés: {len(uploaded_zips)}")
        for fname in uploaded_zips:
            try:
                zip_path = os.path.join(uploads_dir, fname)
                base = os.path.splitext(fname)[0]
                extract_dir = os.path.join(gtfs_dir, base)
                os.makedirs(extract_dir, exist_ok=True)
                with zipfile.ZipFile(zip_path, "r") as z:
                    z.extractall(extract_dir)
                # supprimer l'archive après extraction pour économiser l'espace
                try:
                    os.remove(zip_path)
                except Exception:
                    pass
                task.add_log(f"📦 GTFS uploadé extrait : {base}")
                # Augmenter calendar.txt si nécessaire
                try:
                    summary = ensure_calendar_augmented(extract_dir)
                    task.add_log(summary)
                except Exception as e:
                    task.add_log(f"⚠️ Échec synthèse calendar.txt ({base}): {e}")
            except Exception as e:
                task.add_log(f"⚠️ Extraction zip uploadé échouée ({fname}): {e}")

        # 2) Télécharger et extraire les GTFS référencés en base
        for gtfs_id in task.gtfs_ids:
            g = GtfsSource.objects.get(id=gtfs_id)

            zip_path = os.path.join(gtfs_dir, f"{g.source_id}.zip")
            extract_dir = os.path.join(gtfs_dir, g.source_id)

            task.add_log(f"⬇️ Téléchargement GTFS : {g.name}")
            r = _fetch_with_retry(g.url, timeout=300)
            r.raise_for_status()

            with open(zip_path, "wb") as f:
                f.write(r.content)

            os.makedirs(extract_dir, exist_ok=True)
            with zipfile.ZipFile(zip_path, "r") as z:
                z.extractall(extract_dir)

            os.remove(zip_path)
            task.add_log(f"📦 GTFS extrait : {g.source_id}")

            # ─────────────────────────
            # Synthétiser calendar.txt si absent, depuis calendar_dates.txt
            # ─────────────────────────
            try:
                # Infos rapides sur la présence des fichiers GTFS clés
                cal_exists = os.path.exists(os.path.join(extract_dir, "calendar.txt"))
                cal_dates_exists = os.path.exists(os.path.join(extract_dir, "calendar_dates.txt"))
                try:
                    file_count = len(os.listdir(extract_dir))
                except Exception:
                    file_count = -1
                task.add_log(
                    f"📂 {g.source_id}: fichiers={file_count}, calendar.txt={'oui' if cal_exists else 'non'}, calendar_dates.txt={'oui' if cal_dates_exists else 'non'}"
                )

                summary = ensure_calendar_augmented(extract_dir)
                task.add_log(summary)
            except Exception as e:
                task.add_log(f"⚠️ Échec synthèse calendar.txt ({g.source_id}): {e}")

        # Compter uniquement les sous-dossiers (feeds extraits)
        try:
            feed_dirs = [
                d for d in os.listdir(gtfs_dir)
                if os.path.isdir(os.path.join(gtfs_dir, d))
            ]
        except Exception:
            feed_dirs = []

        task.add_log(f"📦 GTFS prêts : {len(feed_dirs)} dossier(s)")

        # Aucun feed → arrêter proprement avant le build
        if len(feed_dirs) == 0:
            task.status = "error"
            task.add_log("❌ Aucun GTFS détecté pour ce build (gtfs_ids vide ou téléchargements échoués). Annulation du build.")
            _safe_save(task)
            return

        # ─────────────────────────
        # Nettoyage GTFS (désactivé)
        # ─────────────────────────
        _safe_save(task)

        # ─────────────────────────
        # valhalla.json depuis template optimisé
        # ─────────────────────────
        template_path = os.path.join(os.path.dirname(__file__), "..", "config", "valhalla_template.json")
        
        with open(template_path, "r") as f:
            valhalla_json = json.load(f)
        
        # Ajuster les chemins dynamiques spécifiques au graph
        valhalla_json["mjolnir"]["tile_dir"] = os.path.join(graph_dir, "build/tiles/valhalla")
        valhalla_json["mjolnir"]["tile_extract"] = os.path.join(graph_dir, "build/tiles/valhalla_tiles.tar")
        valhalla_json["mjolnir"]["timezone"] = os.path.join(graph_dir, "build/tiles/tz.sqlite")
        valhalla_json["mjolnir"]["transit_dir"] = os.path.join(graph_dir, "build/tiles/transit_tiles")
        valhalla_json["mjolnir"]["transit_feeds_dir"] = os.path.join(graph_dir, "build/tiles/transit-feeds")

        with open(os.path.join(graph_dir, "valhalla.json"), "w") as f:
            json.dump(valhalla_json, f, indent=2)

        task.add_log("⚙️ valhalla.json généré")
        task.save()

        # ── phase 2
        run_valhalla_build.delay(task.id)

    except BuildTask.DoesNotExist:
        # The build record was deleted while queued; nothing to do.
        return
    except Exception as e:
        task.status = "error"
        try:
            task.add_log(f"❌ ERREUR PRÉPARATION : {e}")
            _safe_save(task)
        except Exception:
            pass


# ─────────────────────────
# PHASE 2 — BUILD VALHALLA
# ─────────────────────────

@shared_task(bind=True)
def run_valhalla_build(self, task_id):
    try:
        task = BuildTask.objects.get(id=task_id)
        task.status = "building"
        task.add_log("🚧 Lancement build Valhalla")
        _safe_save(task)

        cmd = [
            "docker", "exec",
            "valhallaDjango",
            "build_graph.sh",
            task.output_dir   # CHEMIN COMPLET
        ]

        task.add_log("🐳 Commande : " + " ".join(cmd))

        # Streaming en temps réel avec capture stderr séparée
        build_log_path = os.path.join(task.output_dir, "build.log")
        os.makedirs(task.output_dir, exist_ok=True)

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

        # Buffer pour logs (sauvegarder toutes les 25 lignes)
        log_buffer = []
        flush_threshold = 25

        # Lire et logger ligne par ligne (stdout)
        # Écrire les logs complets dans un fichier, et ne pousser que des aperçus en DB
        with open(build_log_path, "a", encoding="utf-8", errors="ignore") as lf:
            for line in process.stdout:
                line = line.rstrip()
                if not line:
                    continue
                # Fichier complet
                try:
                    lf.write(line + "\n")
                except Exception:
                    pass
                # Aperçu DB
                log_buffer.append(f"[{timezone.now()}] 📟 {line}")
                if len(log_buffer) >= flush_threshold:
                    _flush_logs_buffer(task, log_buffer)
                    log_buffer = []

        # Sauvegarder les logs restants
        if log_buffer:
            _flush_logs_buffer(task, log_buffer)

        process.wait()
        # Pas de thread stderr: fusionné dans stdout

        if process.returncode != 0:
            raise RuntimeError(
                f"build_graph.sh exited with code {process.returncode}"
            )

        task.status = "built"
        task.is_ready = True
        task.finished_at = timezone.now()
        task.add_log("🎉 Tuiles Valhalla générées avec succès")
        _safe_save(task)

        ensure_valhalla_running.delay(task.id)

    except BuildTask.DoesNotExist:
        # Was deleted meanwhile; abort quietly
        return
    except Exception as e:
        task.status = "error"
        try:
            task.add_log(f"❌ BUILD ERROR : {e}")
            _safe_save(task)
        except Exception:
            pass


# ─────────────────────────
# PHASE 3 — SERVING
# ─────────────────────────

@shared_task
def ensure_valhalla_running(task_id):
    """Démarre un container Valhalla pour le graph"""
    from .docker_manager import ValhallaDockerManager
    import json
    
    task = BuildTask.objects.filter(id=task_id).first()
    if not task:
        return

    if task.is_serving:
        task.add_log("ℹ️ Container déjà actif")
        return

    task.add_log("🐳 Lancement du container Valhalla...")
    _safe_save(task)
    
    try:
        # Préparer les chemins de config
        valhalla_json_path = os.path.join(task.output_dir, "valhalla.json")
        valhalla_serve_json_path = os.path.join(task.output_dir, "valhalla_serve.json")

        def replace_paths(obj):
            if isinstance(obj, dict):
                return {k: replace_paths(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [replace_paths(item) for item in obj]
            elif isinstance(obj, str) and task.output_dir in obj:
                return obj.replace(task.output_dir, "/data/valhalla")
            return obj

        # Charger config de base (valhalla.json) si dispo, sinon patcher l'existante (valhalla_serve.json)
        valhalla_config = None
        if os.path.exists(valhalla_json_path):
            try:
                with open(valhalla_json_path, "r") as f:
                    valhalla_config = json.load(f)
                valhalla_config = replace_paths(valhalla_config)
                task.add_log("🔧 Base config chargée depuis valhalla.json")
            except Exception as e:
                task.add_log(f"⚠️ Lecture valhalla.json impossible: {e}")
        if valhalla_config is None and os.path.exists(valhalla_serve_json_path):
            try:
                with open(valhalla_serve_json_path, "r") as f:
                    valhalla_config = json.load(f)
                task.add_log("🔧 Patch de valhalla_serve.json existant")
            except Exception as e:
                task.add_log(f"⚠️ Lecture valhalla_serve.json impossible: {e}")
        if valhalla_config is None:
            valhalla_config = {}

        # Injecter CORS par défaut
        try:
            httpd = valhalla_config.setdefault("httpd", {})
            service = httpd.setdefault("service", {})
            ac = service.setdefault("access_control", {})
            ac.setdefault("allow_origin", "*")
            ac.setdefault("allow_methods", "GET, POST, OPTIONS")
            ac.setdefault("allow_headers", "Content-Type")
            task.add_log("🌐 CORS (access_control) injecté dans valhalla_serve.json")
        except Exception as e:
            task.add_log(f"⚠️ Injection CORS échouée: {e}")

        try:
            with open(valhalla_serve_json_path, "w") as f:
                json.dump(valhalla_config, f, indent=2)
        except Exception as e:
            task.add_log(f"⚠️ Écriture valhalla_serve.json impossible: {e}")
        
        task.add_log("⚙️ Configuration serving générée")
        
        manager = ValhallaDockerManager()
        
        # Utiliser le chemin du worker (sera converti en chemin hôte par le manager)
        # Démarrer le container
        result = manager.start_container(
            graph_name=task.name,
            graph_path=task.output_dir  # Ex: /data/graphs/aura_2025
        )
        
        if result["status"] in ["started", "restarted", "already_running"]:
            task.status = "serving"
            task.is_serving = True
            task.serve_port = result["port"]
            task.add_log(f"✅ {result['message']}")
            task.add_log(f"🌐 Endpoint: http://localhost:{result['port']}/route")
            _safe_save(task)
        else:
            task.status = "error"
            task.add_log(f"❌ Erreur démarrage container: {result.get('message')}")
            _safe_save(task)
            
    except Exception as e:
        task.status = "error"
        try:
            task.add_log(f"❌ Erreur Docker: {str(e)}")
            _safe_save(task)
        except Exception:
            pass

# ─────────────────────────
# Helpers
# ─────────────────────────
def _safe_save(task: BuildTask, update_fields=None):
    """Persist a task safely, re-fetching if the row was replaced/deleted.
    Swallow errors to avoid breaking long-running builds.
    """
    try:
        if update_fields:
            task.save(update_fields=update_fields)
        else:
            task.save()
    except Exception:
        try:
            fresh = BuildTask.objects.filter(id=task.id).first()
            if fresh:
                # copy requested fields
                if update_fields:
                    for f in update_fields:
                        setattr(fresh, f, getattr(task, f, getattr(fresh, f)))
                    fresh.save(update_fields=update_fields)
                else:
                    # attempt best-effort full save
                    for f in [
                        'status','logs','output_dir','is_ready','is_serving','serve_port'
                    ]:
                        try:
                            setattr(fresh, f, getattr(task, f))
                        except Exception:
                            pass
                    fresh.save()
                # reflect back
                task.status = fresh.status
                task.logs = fresh.logs
                task.output_dir = fresh.output_dir
                task.is_ready = fresh.is_ready
                task.is_serving = fresh.is_serving
                task.serve_port = fresh.serve_port
        except Exception:
            pass




@shared_task
def stop_valhalla_container(task_id):
    """Arrête le container Valhalla d'un graph"""
    from .docker_manager import ValhallaDockerManager
    
    task = BuildTask.objects.filter(id=task_id).first()
    if not task:
        return
    
    try:
        manager = ValhallaDockerManager()
        result = manager.stop_container(task.name)
        
        if result["status"] == "stopped":
            task.is_serving = False
            task.add_log("🛑 Container arrêté")
            task.save()
        else:
            task.add_log(f"⚠️ {result.get('message')}")
            task.save()
            
    except Exception as e:
        task.add_log(f"❌ Erreur arrêt container: {str(e)}")
        task.save()


# ─────────────────────────
# OSM HELPER
# ─────────────────────────

def get_osm_file(task):
    """
    Garantit la présence du fichier OSM dans /data/sources/osm
    """
    from urllib.parse import urlparse

    os.makedirs(OSM_SOURCE_DIR, exist_ok=True)

    osm_value = task.osm_file

    if osm_value.startswith("http"):
        osm_url = osm_value
        osm_filename = os.path.basename(urlparse(osm_value).path) or "osm.pbf"
    else:
        osm_url = None
        osm_filename = osm_value

    local_path = os.path.join(OSM_SOURCE_DIR, osm_filename)

    if os.path.exists(local_path):
        task.add_log("📦 OSM trouvé localement")
        return local_path

    entry = next((e for e in OSM_CATALOG_FR if e["file"] == osm_filename), None)

    download_url = None
    if entry:
        download_url = entry["url"]
        task.add_log(f"⬇️ Téléchargement OSM (catalogue) : {download_url}")
    elif osm_url:
        download_url = osm_url
        task.add_log(f"⬇️ Téléchargement OSM (URL fournie) : {download_url}")
    else:
        raise FileNotFoundError(f"OSM inconnu : {osm_filename}")

    r = _fetch_with_retry(download_url, stream=True, timeout=900)
    r.raise_for_status()

    with open(local_path, "wb") as f:
        for chunk in r.iter_content(1024 * 1024):
            f.write(chunk)

    task.add_log("✅ OSM téléchargé")
    return local_path

# ─────────────────────────
# Internal helpers (retry + log flush)
# ─────────────────────────

def _flush_logs_buffer(task: BuildTask, buffer: list[str]):
    """Append buffered lines to task logs with safe save."""
    try:
        task.logs = (task.logs or "") + "\n" + "\n".join(buffer)
        task.save(update_fields=['logs'])
    except Exception:
        try:
            fresh = BuildTask.objects.filter(id=task.id).first()
            if fresh:
                fresh.logs = (fresh.logs or "") + "\n" + "\n".join(buffer)
                fresh.save(update_fields=['logs'])
                task.logs = fresh.logs
        except Exception:
            pass


def _fetch_with_retry(url: str, timeout: int = 300, stream: bool = False, max_retries: int = 3, backoff_seconds: int = 2):
    """Simple HTTP GET with retry/backoff for transient network errors."""
    last_exc = None
    for attempt in range(1, max_retries + 1):
        try:
            r = requests.get(url, timeout=timeout, stream=stream)
            r.raise_for_status()
            return r
        except Exception as e:
            last_exc = e
            if attempt < max_retries:
                time.sleep(backoff_seconds * attempt)
            else:
                raise
