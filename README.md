# Valhalla Admin

A Dockerized admin and dashboard around Valhalla routing, with GTFS transit support, a Leaflet map playground, and Django + Celery orchestration to build and serve graphs.

## Features

- Manage per-graph builds and serving state (auto, bicycle, pedestrian, multimodal).
- Robust data pipeline: OSM + GTFS downloads with retry/backoff, GTFS calendar augmentation.
- Health-checked services: Django app, Celery worker/scheduler, Valhalla server.
- Interactive map playground: routes, isochrones, maneuvers panel, draggable origin/destination, advanced costing options.
- DRF endpoints for build tasks and status.

## Quick Start

Prerequisites: Docker Desktop.

1. Configure environment:
   - `compose/env/django.env` includes `SYSTEM_TIMEZONE` (e.g. `Europe/Paris`).
   - Add other secrets (DB/Redis) as needed.
2. Bring up the stack:
   ```bash
   docker compose -f compose/docker-compose.yml up -d
   ```
3. Access the app:
   - Django UI: http://localhost:8000
   - Valhalla (per graph): see graph page for serve URL (e.g. http://localhost:8002).

## Timezone

- Set `SYSTEM_TIMEZONE` in `compose/env/django.env`. Django and Celery use this timezone; scheduling converts to UTC internally.

## Data Layout

- `data/graphs/<name>/` holds OSM, GTFS, and built tiles for Valhalla.
- `services/django/app/valhalla_admin/graph/config/` provides Valhalla templates and tooltips.

## Build Graphs

- Use the UI to schedule a build for a graph name. The pipeline cleans GTFS dir, processes uploads, downloads feeds with retry, augments calendars, and builds tiles.
- Serving is configured via `valhalla_serve.json` with CORS access_control.

## Map Playground

- Click map to set origin/destination; drag to adjust; double-click a marker to delete.
- Choose `Mode` and advanced options (`costing_options`) to tune walking/transit behavior.
- Segment list highlights maneuvers; per-mode colors are shown.

## API

- Build tasks list: `/api/build-tasks/`
- Build task status: `/api/build-tasks/<id>/status`

## Scripts

- `scripts/rebuild_tiles.py` — helper to rebuild tiles.
- `scripts/analyze_transit.py` — transit routing analyzer with iterative snapping to first boarding.

## Development

- Django app in `services/django/app/valhalla_admin`.
- Celery tasks coordinate build/serve.
- Healthchecks added in compose for reliability.

## License

Internal project. Add a license if distributing.