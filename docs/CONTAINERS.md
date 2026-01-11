# 🚀 Gestion des Containers Valhalla

## Architecture mise en place

### Option choisie : **1 container par graph**

Chaque graph dispose de son propre container Valhalla isolé avec :
- Port dédié (8002, 8003, 8004...)
- Volume monté en lecture seule sur les tuiles du graph
- Health check automatique
- Restart policy `unless-stopped`

## 📦 Composants ajoutés

### 1. `docker_manager.py` - Gestionnaire Docker
Module centralisant toutes les opérations Docker :
- `start_container()` : Créer et démarrer un container
- `stop_container()` : Arrêter un container
- `restart_container()` : Redémarrer un container
- `get_container_status()` : Récupérer métriques (CPU, RAM, health)
- `list_valhalla_containers()` : Lister tous les containers Valhalla
- `get_next_available_port()` : Attribution automatique de ports

### 2. Vues ajoutées dans `views.py`
- `dashboard()` : Vue enrichie avec statistiques containers
- `start_container()` : POST endpoint pour démarrer
- `stop_container()` : POST endpoint pour arrêter  
- `restart_container()` : POST endpoint pour redémarrer
- `container_status_api()` : API JSON pour polling status

### 3. URLs ajoutées
```python
/graphs/task/<id>/start/          # Démarrer container
/graphs/task/<id>/stop/           # Arrêter container
/graphs/task/<id>/restart/        # Redémarrer container
/graphs/task/<id>/container-status/  # Status API
```

### 4. Templates mis à jour

#### `dashboard.html`
- 📊 Stats globales (total, actifs, arrêtés)
- Tableau avec état containers en temps réel
- Boutons Start/Stop/Restart
- Polling auto toutes les 5 secondes
- Indicateurs health check

#### `list.html`
- Liste complète des graphs
- Actions inline par graph
- Status containers synchronisé
- Liens vers endpoints Valhalla

### 5. Tasks Celery
Mise à jour de `ensure_valhalla_running()` :
- Appelle maintenant `DockerManager.start_container()`
- Gère les ports dynamiquement
- Met à jour le statut DB

Ajout de `stop_valhalla_container()` :
- Arrête proprement un container
- Met à jour is_serving = False

## 🔄 Cycle de vie d'un graph

```
1. BUILD    → Construction des tuiles (container builder)
2. BUILT    → Tuiles prêtes, pas de container actif
3. START    → Lancement container Valhalla dédié
4. SERVING  → Container actif, API accessible
5. STOP     → Arrêt container, tuiles conservées
```

## 🌐 Accès aux graphs

Chaque container est accessible sur son port :
```
http://localhost:8002/route    # Graph 1
http://localhost:8003/route    # Graph 2
http://localhost:8004/route    # Graph 3
```

## 📝 Configuration requise

### docker-compose.yml
Le container worker doit avoir accès au socket Docker :
```yaml
worker:
  volumes:
    - /var/run/docker.sock:/var/run/docker.sock
```

### Réseau Docker
Les containers Valhalla rejoignent automatiquement le réseau `valhalla-admin_default`

## 🔍 Monitoring

### Dashboard
- Nombre total de containers
- Containers actifs vs arrêtés
- État en temps réel avec polling
- Métriques CPU/RAM par container

### Logs
Tous les événements containers sont loggés dans `BuildTask.logs`

## 🚨 Gestion des erreurs

- **Container déjà existant** : Redémarre le container existant
- **Port déjà utilisé** : Attribution auto du prochain port libre
- **Container zombie** : Force removal avec `force=True`
- **Health check failed** : Visible dans le dashboard

## 🔐 Sécurité

- Volumes montés en **read-only** (`:ro`)
- Pas d'accès réseau externe nécessaire
- Labels Docker pour identification (`valhalla.managed=true`)

## 📈 Scaling

Pour ajouter de la capacité :
1. Créer de nouveaux graphs → containers auto-créés
2. Chaque container = isolé et indépendant
3. Load balancer externe (Nginx/Traefik) pour routing par nom

Exemple Nginx :
```nginx
location /aura_2025/ {
    proxy_pass http://localhost:8002/;
}

location /bretagne_2025/ {
    proxy_pass http://localhost:8003/;
}
```

## 🛠 Commandes utiles

```bash
# Lister les containers Valhalla
docker ps --filter "label=valhalla.managed=true"

# Logs d'un container
docker logs valhalla-graph-aura_2025

# Statistiques
docker stats valhalla-graph-aura_2025

# Arrêter tous les graphs
docker ps -q --filter "label=valhalla.managed=true" | xargs docker stop
```
