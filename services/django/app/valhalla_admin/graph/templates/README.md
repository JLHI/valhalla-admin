# Graph Templates

Templates for graph management views.

- `map.html`: Leaflet playground with routes/isochrones, maneuvers panel, draggable markers, advanced costing options.
- Use server-side context to pass `serve_url`, GTFS date windows, and graph name.

Front-end:
- Avoid CORS preflight by GET `?json` calls to Valhalla.
- Maneuvers list highlights segments; click to zoom.