# Troubleshooting

Common issues and quick fixes.

## Valhalla "No path could be found"
- Check GTFS service dates: selected `Date/Heure` might be outside the feed window.
- Try different times (e.g., 07:30, 12:00) or a weekday.
- Reduce pedestrian walking: lower `max_walk_distance`, increase `walk_factor`.

## Excessive Walking in Multimodal
- Tighten `transit.max_walk_distance` (600–800 m).
- Increase `pedestrian.walk_factor` to penalize walking; slow `walking_speed`.
- Snap destination to nearest transit stop and retry.

## CORS / Preflight
- Use GET `?json` for Valhalla calls; ensure `access_control` is injected into `valhalla_serve.json`.

## Timezone Misalignment
- Ensure `SYSTEM_TIMEZONE` is set and matches UI expectations.
- Scheduling uses this timezone and converts to UTC for Celery.

## Containers Unhealthy
- Check `docker compose ps` and health statuses.
- Inspect logs for django, worker, scheduler containers.

## Data Size / Disk
- Graph tiles and GTFS can be large. Monitor host disk space.

## Where to Look
- Django logs: UI errors, task scheduling.
- Celery worker logs: build pipeline and subprocess outputs.
- Valhalla server logs: routing endpoints and status.
