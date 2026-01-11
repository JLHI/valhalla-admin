# Architecture

High-level overview of the Valhalla Admin platform.

## Components

- Django + DRF: Web UI and API.
- Celery (worker, beat): Task orchestration for builds and serving.
- Valhalla: Routing engine container, per-graph serve.
- Postgres: Application database.
- Redis: Broker/result backend for Celery.
- Docker Compose: Service orchestration & healthchecks.

## Data Flow

1. Inputs: OSM PBF + GTFS zip(s) → stored under `data/graphs/<name>/`.
2. Build:
   - Celery task cleans GTFS dir; processes uploads; downloads feeds with retry/backoff; augments `calendar.txt` when missing.
   - `valhalla.json` written; `build_graph.sh` runs in the Valhalla build context.
   - Tiles output to `build/tiles/valhalla` and `build/tiles/transit_tiles`.
3. Serve:
   - Generate `valhalla_serve.json` (inject CORS access_control).
   - Start Valhalla container for the graph; expose port (e.g., 8002).
4. UI:
   - Map playground (Leaflet) calls Valhalla endpoints via GET `?json`.
   - Advanced `costing_options` adjust walking/transit behavior.

## Sequence (Build → Serve)

- User schedules build in UI → Celery task `start_valhalla_build`.
- Task prepares data and enqueues `run_valhalla_build`.
- On success, `ensure_valhalla_running` writes serve config and starts the container.
- Django reflects serving status in widgets and API.

## Concurrency & Reliability

- Per-graph build lock to prevent duplicate builds.
- HTTP downloads use exponential backoff.
- Subprocess logging batched to reduce DB writes.
- Compose healthchecks for django/worker/scheduler.

## Timezone

- `SYSTEM_TIMEZONE` drives Django/Celery; scheduling converts to UTC.

## Network Endpoints

- App: http://localhost:8000
- Valhalla (per graph): see graph page for URL (e.g., http://localhost:8002).
- API: `/api/build-tasks/`, `/api/build-tasks/<id>/status`.
