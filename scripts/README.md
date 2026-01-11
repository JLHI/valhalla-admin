# Scripts

Helper scripts for ops and analysis.

- `rebuild_tiles.py` — automate rebuilding graphs/tiles.
- `analyze_transit.py` — run multimodal routes, extract maneuvers, iterate snapping dest to first boarding; CLI flags for server/date/time/options.

Run example:
```powershell
& ".venv\Scripts\python.exe" scripts\analyze_transit.py --server http://localhost:8004 --origin <lat,lon> --dest <lat,lon> --date YYYY-MM-DD --time HH:MM --iterate 3
```