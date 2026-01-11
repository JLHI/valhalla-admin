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

GTFS_DIR="$GRAPH_ROOT/gtfs"              # feeds extraits: gtfs/<source_id>/*
TRANSIT_FEEDS="$BUILD_DIR/transit-feeds"
TILES_DIR="$BUILD_DIR/tiles"

OSM_FILE=$(ls "$GRAPH_ROOT"/osm/*.pbf 2>/dev/null | head -n 1)

echo "🚀 Build Valhalla graph : $GRAPH_NAME"
echo "📁 Graph root : $GRAPH_ROOT"

# ==========================
# Vérifications minimales
# ==========================
if [ ! -f "$OSM_FILE" ]; then
  echo "❌ Fichier OSM manquant dans $GRAPH_ROOT/osm/"
  exit 1
fi

# ==========================buil
# Préparation dossiers
# ==========================
rm -rf "$BUILD_DIR"
mkdir -p "$TILES_DIR/valhalla"

# On ne crée transit_dirs que si on détecte du GTFS
HAS_GTFS=0

# ==========================
# Détection & copie GTFS (optionnel)
# ==========================
if [ -d "$GTFS_DIR" ]; then
  # Cherche au moins un dossier contenant un feed "probable"
  # (on teste agency.txt ou stops.txt pour éviter les dossiers vides)
  for D in "$GTFS_DIR"/*; do
    if [ -d "$D" ]; then
      if [ -f "$D/agency.txt" ] || [ -f "$D/stops.txt" ]; then
        HAS_GTFS=1
        break
      fi
    fi
  done
fi

if [ "$HAS_GTFS" -eq 1 ]; then
  echo "📦 GTFS détecté → activation du transit"
  mkdir -p "$TRANSIT_FEEDS"
  mkdir -p "$TILES_DIR/transit_tiles"

  echo "📦 Copie des GTFS extraits…"
  for FEED in "$GTFS_DIR"/*; do
    if [ -d "$FEED" ]; then
      NAME=$(basename "$FEED")

      # skip dossiers non-feeds (ex: vides)
      if [ ! -f "$FEED/agency.txt" ] && [ ! -f "$FEED/stops.txt" ]; then
        echo "  ↷ $NAME ignoré (pas un feed GTFS valide: agency.txt/stops.txt manquant)"
        continue
      fi

      OUT_DIR="$TRANSIT_FEEDS/$NAME"
      echo "  → $NAME"
      rm -rf "$OUT_DIR"
      cp -r "$FEED" "$OUT_DIR"

      if [ ! -f "$OUT_DIR/agency.txt" ]; then
        echo "⚠️ $NAME ne contient pas agency.txt (peut être OK selon feed)"
      fi
    fi
  done

  # Si finalement aucun feed copié (ex: tous invalides), on désactive transit
  if ! find "$TRANSIT_FEEDS" -mindepth 1 -maxdepth 1 -type d | grep -q .; then
    echo "⚠️ Aucun feed GTFS copié au final → désactivation transit"
    HAS_GTFS=0
    rm -rf "$TRANSIT_FEEDS" "$TILES_DIR/transit_tiles"
  fi
else
  echo "ℹ️ Aucun GTFS détecté → build OSM-only (sans transit)"
fi

# ==========================
# Timezones
# ==========================
echo "🕒 Construction timezones…"
valhalla_build_timezones > "$TILES_DIR/tz.sqlite"

# ==========================
# Config Valhalla
# ==========================
echo "⚙️ Génération config…"

if [ "$HAS_GTFS" -eq 1 ]; then
  valhalla_build_config \
    --mjolnir-tile-dir="$TILES_DIR/valhalla" \
    --mjolnir-transit-dir="$TILES_DIR/transit_tiles" \
    --mjolnir-transit-feeds-dir="$TRANSIT_FEEDS" \
    --mjolnir-timezone="$TILES_DIR/tz.sqlite" \
    --mjolnir-tile-extract="$TILES_DIR/valhalla_tiles.tar" \
    --mjolnir-concurrency=${MJOLNIR_CONCURRENCY:-8} \
    > "$GRAPH_ROOT/valhalla.json"
else
  # Pas de flags transit si pas de feeds
  valhalla_build_config \
    --mjolnir-tile-dir="$TILES_DIR/valhalla" \
    --mjolnir-timezone="$TILES_DIR/tz.sqlite" \
    --mjolnir-tile-extract="$TILES_DIR/valhalla_tiles.tar" \
    --mjolnir-concurrency=${MJOLNIR_CONCURRENCY:-8} \
    > "$GRAPH_ROOT/valhalla.json"
fi

# ==========================
# Admins (admin.sqlite)
# ==========================
echo "🌍 Build admin.sqlite…"
valhalla_build_admins -c "$GRAPH_ROOT/valhalla.json" "$OSM_FILE"

# ==========================
# Transit (optionnel)
# ==========================
if [ "$HAS_GTFS" -eq 1 ]; then
  echo "🚍 Ingest transit…"
  valhalla_ingest_transit -c "$GRAPH_ROOT/valhalla.json"

  echo "🔄 Convert transit…"
  valhalla_convert_transit -c "$GRAPH_ROOT/valhalla.json"
else
  echo "⏭ Transit désactivé (pas de GTFS)"
fi

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
