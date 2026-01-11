# Django Service

Django app with DRF and Celery.

- `Dockerfile` and `entrypoint.sh` configure the container.
- App code in `app/valhalla_admin`.
- Celery worker (`celery.py`) and beat scheduler manage tasks.

Environment:
- `SYSTEM_TIMEZONE` controls Django `TIME_ZONE` and Celery timezone.
- Database and Redis configured via compose.