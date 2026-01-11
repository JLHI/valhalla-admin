# Compose Env

Environment files for services.

- `django.env`: includes `SYSTEM_TIMEZONE` and Django settings.
- `postgres.env`: database credentials for Postgres.

Notes:
- Set `SYSTEM_TIMEZONE` (e.g., `Europe/Paris`) to control Django/Celery timezone.
- Keep secrets out of version control when possible.