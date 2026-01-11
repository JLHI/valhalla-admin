# Contributing

Thanks for contributing! This guide covers local setup, style, and workflow.

## Local Setup

- Requirements: Docker Desktop; Python 3.12 (for scripts/tests).
- Clone and create a venv:
  ```powershell
  python -m venv .venv
  .venv\Scripts\Activate.ps1
  pip install -r requirements.txt  # if present
  ```
- Bring up services:
  ```bash
  docker compose -f compose/docker-compose.yml up -d
  ```

## Development Workflow

- Django app resides in `services/django/app/valhalla_admin`.
- Celery orchestrates builds; Valhalla containers serve graphs.
- Prefer small, focused changes; update docs where relevant.
- Run scripts:
  ```powershell
  & ".venv\Scripts\python.exe" scripts\analyze_transit.py --help
  ```

## Coding Style

- Python: PEP8; type hints where practical.
- JavaScript: keep functions small; avoid unnecessary global state.
- Templates: keep IDs stable; avoid heavy inline styles.

## Tests

- Minimal tests exist in `services/django/app/valhalla_admin/graph/tests/`.
- Add targeted tests for new utilities and endpoints when possible.

## Pull Requests

- Describe the change, rationale, and impact.
- Link to docs or screenshots for UI changes.
- Avoid unrelated refactors in the same PR.
