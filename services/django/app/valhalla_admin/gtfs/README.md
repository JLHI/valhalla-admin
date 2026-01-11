# GTFS Module

GTFS ingestion and utilities.

- `utils.py`: `ensure_calendar_augmented(feed_dir)` — synthesize/extend `calendar.txt` using `calendar_dates`.
- Views: add GTFS feeds; list and health.

Notes:
- Calendar augmentation makes transit usable when `calendar.txt` is missing.
- Feed date window impacts routing availability; the UI displays start/end when available.