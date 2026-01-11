# Documentation

Project documentation and operational notes.

- `CONTAINERS.md`: container sizing, images, and disk usage notes.
- Timezone: Set `SYSTEM_TIMEZONE` in `compose/env/django.env` to control Django/Celery timezone. Scheduling inputs are interpreted in this timezone and converted to UTC.
- For getting started, see the root `README.md`.