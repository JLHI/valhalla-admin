import json
import os
import subprocess
from .models import BuildTask
from valhalla_admin.gtfs.models import GtfsSource

BUILD_ROOT = "/data/builds"
OSM_DIR = "/data/osm"

def start_valhalla_build(task_id):
    task = BuildTask.objects.get(id=task_id)
    task.status = "running"
    task.save()

    # Préparation dossier
    task_dir = os.path.join(BUILD_ROOT, task.name)
    os.makedirs(task_dir, exist_ok=True)

    task.add_log("Création du dossier de build")

    # Copier OSM dans le build
    osm_path = os.path.join(OSM_DIR, task.osm_file)
    build_osm = os.path.join(task_dir, "osm.pbf")

    task.add_log(f"Copie du fichier OSM : {osm_path}")
    subprocess.run(["cp", osm_path, build_osm])

    # Télécharger les GTFS sélectionnés
    gtfs_dir = os.path.join(task_dir, "gtfs")
    os.makedirs(gtfs_dir, exist_ok=True)

    task.add_log("Téléchargement des GTFS…")

    for gtfs_id in task.gtfs_ids:
        g = GtfsSource.objects.get(id=gtfs_id)
        out = os.path.join(gtfs_dir, f"{g.source_id}.zip")

        subprocess.run(["wget", "-O", out, g.url])
        task.add_log(f"Téléchargé : {g.name}")

    # Générer valhalla.json
    valhalla_json = {
        "mjolnir": {
            "tile_dir": os.path.join(task_dir, "tiles"),
            "admin": os.path.join(task_dir, "admin.sqlite"),
            "timezone": os.path.join(task_dir, "timezones.sqlite"),
        },
        "additional_data": {
            "transit_dir": gtfs_dir
        }
    }

    with open(os.path.join(task_dir, "valhalla.json"), "w") as f:
        json.dump(valhalla_json, f, indent=2)

    task.add_log("valhalla.json généré")

    # Construction des tuiles via Docker
    cmd = [
        "docker", "run", "--rm",
        "-v", f"{task_dir}:/data",
        "ghcr.io/valhalla/valhalla:latest",
        "valhalla_build_tiles", "-c", "/data/valhalla.json",
        "/data/osm.pbf"
    ]

    task.add_log("Lancement de valhalla_build_tiles…")
    subprocess.run(cmd)
    task.add_log("Graphe construit.")

    task.status = "done"
    task.output_dir = task_dir
    task.save()
