FROM python:3.12

# Dossier de travail de l'application
WORKDIR /app

# Installer les dépendances
#COPY requirements.txt /app/
RUN pip install django djangorestframework celery redis psycopg2-binary requests unzip docker
RUN apt-get update && apt-get install -y docker.io osmium-tool

# Copier l'entrypoint
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Copier l'application dans /app/src
COPY app/ /app/

# Lancer l'entrypoint avant toute commande
ENTRYPOINT ["/entrypoint.sh"]

# Commande finale
CMD ["python", "/app/manage.py", "runserver", "0.0.0.0:8000"]