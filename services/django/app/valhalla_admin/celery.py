from celery import Celery
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE","valhalla_admin.settings")
app = Celery("valhalla_admin")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
