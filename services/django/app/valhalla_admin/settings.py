from pathlib import Path
import os
BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY","devkey")
DEBUG = True
ALLOWED_HOSTS = ["*"]
INSTALLED_APPS = [
    "django.contrib.admin","django.contrib.auth","django.contrib.contenttypes","django.contrib.sessions","django.contrib.messages","django.contrib.staticfiles",
    "rest_framework","valhalla_admin.api","valhalla_admin.gtfs","valhalla_admin.tokens","valhalla_admin","valhalla_admin.graph"
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
DATABASES={
 "default": {
  "ENGINE":"django.db.backends.postgresql",
  "NAME":os.getenv("POSTGRES_DB"),
  "USER":os.getenv("POSTGRES_USER"),
  "PASSWORD":os.getenv("POSTGRES_PASSWORD"),
  "HOST":"postgres",
  "PORT":5432
 }
}
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [
                BASE_DIR / "valhalla_admin" / "templates"

        ],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "valhalla_admin.context_processors.global_settings",

            ],
        },
    },
]
CSRF_TRUSTED_ORIGINS = [
    "http://localhost",
    "http://localhost:8000",
    "http://127.0.0.1",
    "http://127.0.0.1:8000",
]
STATIC_URL="/static/"
MEDIA_ROOT="/app/media"
MEDIA_URL="/media/"
CELERY_BROKER_URL="redis://redis:6379/0"
DEFAULT_AUTO_FIELD='django.db.models.AutoField'
ROOT_URLCONF = "valhalla_admin.urls"
#LOGIN
LOGIN_URL = "/admin/login/"
LOGIN_REDIRECT_URL = "/"

#LOCALE
LANGUAGE_CODE = 'fr'
# Centralized system timezone (configurable via env)
# Priority: SYSTEM_TIMEZONE > DJANGO_TIMEZONE > default 'Europe/Paris'
TIME_ZONE = os.getenv("SYSTEM_TIMEZONE", os.getenv("DJANGO_TIMEZONE", "Europe/Paris"))

USE_I18N = True
USE_L10N = True
USE_TZ = True

#CELERY
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_RESULT_BACKEND = "redis://redis:6379/0"
CELERY_ENABLE_UTC = True
CELERY_TIMEZONE = TIME_ZONE

# External APIs
GTFS_SOURCE_API_URL = os.getenv("GTFS_SOURCE_API_URL", "https://transport.data.gouv.fr/api/datasets?format=gtfs")