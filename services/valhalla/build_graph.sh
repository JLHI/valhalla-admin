#!/bin/bash
set -e

GRAPH_ROOT="$1"

if [ -z "$GRAPH_ROOT" ]; then
  echo "❌ Chemin du graph manquant"
  exit 1
fi

if [ ! -d "$GRAPH_ROOT" ]; then
  echo "❌ Dossier graph introuvable : $GRAPH_ROOT"
  exit 1
fi

GRAPH_NAME="$(basename "$GRAPH_ROOT")"

BUILD_DIR="$GRAPH_ROOT/build"

GTFS_ZIP_DIR="$GRAPH_ROOT/gtfs"
TRANSIT_FEEDS="$BUILD_DIR/transit-feeds"
TILES_DIR="$BUILD_DIR/tiles"

OSM_FILE=$(ls "$GRAPH_ROOT"/osm/*.pbf 2>/dev/null | head -n 1)

echo "🚀 Build Valhalla graph : $GRAPH_NAME"
echo "📁 Graph root : $GRAPH_ROOT"

# ==========================
# Vérifications
# ==========================
if [ ! -d "$GTFS_ZIP_DIR" ]; then
  echo "❌ Dossier GTFS introuvable : $GTFS_ZIP_DIR"
  exit 1
fi

if [ ! -f "$OSM_FILE" ]; then
  echo "❌ Fichier OSM manquant dans $GRAPH_ROOT/osm/"
  exit 1
fi

# ==========================
# Préparation dossiers
# ==========================
rm -rf "$BUILD_DIR"
mkdir -p "$TRANSIT_FEEDS"
mkdir -p "$TILES_DIR/transit_tiles"
mkdir -p "$TILES_DIR/valhalla"

# ==========================
# Copie GTFS + optimisation calendar
# ==========================
echo "📦 Copie des GTFS extraits…"

# Les GTFS sont déjà extraits dans gtfs/<source_id>/
# On les copie dans transit-feeds/
for GTFS_DIR in "$GTFS_ZIP_DIR"/*; do
  if [ -d "$GTFS_DIR" ]; then
    NAME=$(basename "$GTFS_DIR")
    OUT_DIR="$TRANSIT_FEEDS/$NAME"

    echo "  → $NAME"
    cp -r "$GTFS_DIR" "$OUT_DIR"

    if [ ! -f "$OUT_DIR/agency.txt" ]; then
      echo "⚠️ $NAME ne contient pas agency.txt"
    fi
  fi
done



# ==========================
# Timezones
# ==========================
echo "🕒 Construction timezones…"
valhalla_build_timezones > "$TILES_DIR/tz.sqlite"

# ==========================
# Config Valhalla
# ==========================
echo "⚙️ Génération config…"
valhalla_build_config \
  --mjolnir-tile-dir="$TILES_DIR/valhalla" \
  --mjolnir-transit-dir="$TILES_DIR/transit_tiles" \
  --mjolnir-transit-feeds-dir="$TRANSIT_FEEDS" \
  --mjolnir-timezone="$TILES_DIR/tz.sqlite" \
  --mjolnir-tile-extract="$TILES_DIR/valhalla_tiles.tar" \
  --mjolnir-concurrency=${MJOLNIR_CONCURRENCY:-8} \
  > "$GRAPH_ROOT/valhalla.json"
# ==========================
# Admins (admin.sqlite)
# ==========================
echo "🌍 Build admin.sqlite…"
valhalla_build_admins \
  -c "$GRAPH_ROOT/valhalla.json" \
  "$OSM_FILE"
# ==========================
# Transit
# ==========================
echo "🚍 Ingest transit…"
valhalla_ingest_transit -c "$GRAPH_ROOT/valhalla.json"

echo "🔄 Convert transit…"
valhalla_convert_transit -c "$GRAPH_ROOT/valhalla.json"

# ==========================
# OSM tiles
# ==========================
echo "🗺 Build OSM tiles…"
valhalla_build_tiles -c "$GRAPH_ROOT/valhalla.json" "$OSM_FILE"

# ==========================
# Extract final
# ==========================
echo "📦 Build extract…"
valhalla_build_extract -c "$GRAPH_ROOT/valhalla.json"

echo "🎉 Graph $GRAPH_NAME prêt !"
