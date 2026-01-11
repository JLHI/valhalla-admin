#!/bin/bash
set -e

# S'assurer que le PYTHONPATH inclut /app pour uWSGI et Django
export PYTHONPATH=/app:$PYTHONPATH

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

# Remplacer ServerName dans la conf Apache par la variable d'environnement (si le fichier existe)
if [ -n "$SERVER_NAME" ] && [ -f /etc/apache2/sites-available/valhalla_admin.conf ]; then
    sed -i "s/__SERVER_NAME__/$SERVER_NAME/g" /etc/apache2/sites-available/valhalla_admin.conf
fi


echo "Contenu de /app :"
ls -l /app
echo "PYTHONPATH : $PYTHONPATH"
# Lancer uWSGI et Apache seulement si RUN_APACHE=1
if [ "$RUN_APACHE" = "1" ]; then
    if [ -f /app/uwsgi.ini ]; then
        uwsgi --ini /app/uwsgi.ini &
    else
        echo "[ERROR] /app/uwsgi.ini not found!"
        ls -l /app/
    fi
    apache2ctl -D FOREGROUND
fi

exec "$@"
