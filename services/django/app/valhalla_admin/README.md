# Valhalla Admin (Django)

Modules:
- `graph/` — build/serve views, tasks, templates; Docker manager.
- `gtfs/` — GTFS management & utilities (calendar augmentation).
- `api/` — DRF endpoints exposing build tasks/status.
- `config/` — Valhalla templates and tooltips.

Key Concepts:
- Per-graph build lock to prevent duplicate builds.
- Robust downloads with exponential backoff.
- Access control (CORS) injected in `valhalla_serve.json`.

Templates:
- `graph/map.html` provides the Leaflet playground: route/isochrone, maneuvers panel, advanced options, draggable markers.