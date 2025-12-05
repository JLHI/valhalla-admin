#!/bin/bash
set -e

echo "Applying migrations..."
python /app/manage.py migrate --noinput

echo "Creating superuser if not exists..."
python /app/manage.py shell <<EOF
from django.contrib.auth import get_user_model
User = get_user_model()

# Superuser
username = "$DJANGO_SUPERUSER_USERNAME"
email = "$DJANGO_SUPERUSER_EMAIL"
password = "$DJANGO_SUPERUSER_PASSWORD"

if not User.objects.filter(username=username).exists():
    User.objects.create_superuser(username, email, password)
    print("Superuser created.")
else:
    print("Superuser already exists.")

# Staff user (non superadmin)
staff_username = "$DJANGO_STAFF_USERNAME"
staff_email = "$DJANGO_STAFF_EMAIL"
staff_password = "$DJANGO_STAFF_PASSWORD"

if staff_username:
    if not User.objects.filter(username=staff_username).exists():
        user = User.objects.create_user(
            username=staff_username,
            email=staff_email,
            password=staff_password,
        )
        user.is_staff = True
        user.is_superuser = False
        user.save()
        print("Staff user created.")
    else:
        print("Staff user already exists.")
EOF

exec "$@"
