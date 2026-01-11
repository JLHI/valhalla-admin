from django.utils import timezone


def get_system_timezone():
    """Return Django's configured system timezone as tzinfo."""
    try:
        return timezone.get_default_timezone()
    except Exception:
        return timezone.utc


def parse_datetime_local(value: str):
    """
    Parse an HTML input[type=datetime-local] string (YYYY-MM-DDTHH:MM)
    into an aware datetime in the configured system timezone.
    Returns None if invalid.
    """
    if not value:
        return None
    try:
        dt = timezone.datetime.fromisoformat(value)
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt, get_system_timezone())
        else:
            dt = dt.astimezone(get_system_timezone())
        return dt
    except Exception:
        return None


def to_utc(dt):
    """Convert an aware datetime to UTC for schedulers like Celery."""
    if dt is None:
        return None
    try:
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt, get_system_timezone())
        return dt.astimezone(timezone.utc)
    except Exception:
        return dt
