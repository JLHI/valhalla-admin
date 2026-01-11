# API Module

DRF endpoints to decouple UI from backend.

- `build-tasks/` — list recent build tasks.
- `build-tasks/<id>/status` — status + logs preview.

Use cases:
- External tools can monitor builds/concurrency without scraping HTML.