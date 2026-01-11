# Graph Module

Manage Valhalla graphs: create, build, serve, and map.

- Views: create/recreate, status/logs, config operations (start/stop/restart).
- Tasks: `start_valhalla_build`, `run_valhalla_build`, `ensure_valhalla_running`.
- Utilities: OSM/GTFS handling, retries, log batching.
- Templates: `map.html` (playground) with maneuvers list and advanced costing options.

Endpoints:
- `/graphs/<name>/map` — map playground.
- `/graphs/<name>/config` — config view.
- `/graphs/<name>/status` — build/serve status.
