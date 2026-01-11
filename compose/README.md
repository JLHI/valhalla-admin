# Compose

Docker Compose files and environment configuration.

- `docker-compose.yml`: services — django, worker, scheduler, valhalla, postgres, redis.
- `env/`: environment files. Set `SYSTEM_TIMEZONE` in `django.env`.
- Healthchecks ensure services are up before dependent tasks run.

Usage:
```bash
docker compose -f compose/docker-compose.yml up -d
```
