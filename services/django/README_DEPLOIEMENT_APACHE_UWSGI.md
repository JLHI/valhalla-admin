# Déploiement Django + uWSGI + Apache (avec alias de graph)

1. Lancer uWSGI avec la config fournie :
   
   uwsgi --ini services/django/uwsgi.ini

2. Configurer Apache avec le fichier apache_valhalla_admin.conf (voir exemple fourni).
   - Adapter les chemins selon votre installation.
   - Activer les modules proxy, proxy_uwsgi, rewrite.

3. Les URLs de type /valhalla/<alias>/... sont supportées côté Django.

4. Pour chaque requête, l’alias du graph est accessible dans l’URL (paramètre graph_alias).

5. Adapter vos vues si besoin pour utiliser ce paramètre.

6. Redémarrer Apache et uWSGI après modification.

Voir la documentation Django et uWSGI pour plus de détails.
