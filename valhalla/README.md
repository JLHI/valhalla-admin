# Valhalla Build Context

Dockerfile and helper scripts for building Valhalla tiles.

- `build_graph.sh` — executes Valhalla `mjolnir` build inside container.
- `config/valhalla.json` and `config/valhalla_template.json` — base configs.
- GTFS optimization filters to clean feeds (optional helpers).

Notes:
- Serving config `valhalla_serve.json` is generated per-graph with CORS settings.
- After build, the Django tasks ensure the Valhalla container is running for the graph.
