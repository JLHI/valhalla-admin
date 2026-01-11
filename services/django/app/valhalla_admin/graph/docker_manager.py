"""
Module de gestion des containers Valhalla via Docker API
"""
import docker
from docker.errors import NotFound, APIError
from typing import Optional, Dict, List


class ValhallaDockerManager:
    """Gestionnaire de containers Valhalla"""
    
    CONTAINER_PREFIX = "valhalla-graph-"
    NETWORK_NAME = "compose_default"
    VALHALLA_IMAGE = "compose-valhalla:latest"
    BASE_PORT = 8002
    
    def __init__(self):
        self.client = docker.from_env()
    
    def get_container_name(self, graph_name: str) -> str:
        """Retourne le nom du container pour un graph"""
        return f"{self.CONTAINER_PREFIX}{graph_name}"
    
    def get_next_available_port(self) -> int:
        """Trouve le prochain port disponible en collectant les HostPort des containers Valhalla (label ou préfixe de nom),
        y compris ceux qui sont arrêtés via HostConfig.PortBindings."""
        used_ports = set()

        def collect_ports(container) -> None:
            try:
                # 1) Ports mappés (containers RUNNING)
                ports = container.attrs.get("NetworkSettings", {}).get("Ports", {})
                mappings = ports.get("8002/tcp") or []
                for m in mappings:
                    hp = m.get("HostPort")
                    if hp:
                        used_ports.add(int(hp))
                # 2) PortBindings (containers STOPPED conservent la config ici)
                bindings = container.attrs.get("HostConfig", {}).get("PortBindings", {})
                bmaps = bindings.get("8002/tcp") or []
                for b in bmaps:
                    hp = b.get("HostPort")
                    if hp:
                        used_ports.add(int(hp))
            except Exception:
                pass

        try:
            # 1) Containers gérés (label)
            managed = self.client.containers.list(all=True, filters={"label": "valhalla.managed=true"})
            for c in managed:
                collect_ports(c)

            # 2) Fallback: tous les containers dont le nom commence par le préfixe
            all_containers = self.client.containers.list(all=True)
            for c in all_containers:
                try:
                    name = c.name or ""
                except Exception:
                    name = ""
                if name.startswith(self.CONTAINER_PREFIX):
                    collect_ports(c)
        except Exception:
            # Si l'inspection échoue, on tombera sur BASE_PORT
            pass

        port = self.BASE_PORT
        while port in used_ports:
            port += 1
        return port
    
    def _get_host_path_from_worker_mount(self, container_path: str) -> str:
        """
        Convertit un chemin container worker vers le chemin hôte réel
        En inspectant les volumes montés du worker
        """
        try:
            # Récupérer le container worker
            worker = self.client.containers.get("celery_worker")
            
            # Chercher le mount correspondant à /data/graphs
            for mount in worker.attrs["Mounts"]:
                if mount["Destination"] == "/data/graphs":
                    # Remplacer /data/graphs par le chemin source
                    source = mount["Source"]
                    # Convertir le chemin: /data/graphs/aura_2025 -> {source}/aura_2025
                    relative_path = container_path.replace("/data/graphs/", "")
                    host_path = f"{source}/{relative_path}".replace("\\", "/")
                    return host_path
            
            # Si pas trouvé, retourner tel quel
            return container_path
        except Exception as e:
            # En cas d'erreur, retourner tel quel
            return container_path
    
    def start_container(
        self,
        graph_name: str,
        graph_path: str,
        port: Optional[int] = None
    ) -> Dict:
        """
        Démarre un container Valhalla pour un graph
        
        Args:
            graph_name: Nom du graph
            graph_path: Chemin dans le worker (ex: /data/graphs/aura_2025)
            port: Port à utiliser (auto si None)
        
        Returns:
            Dict avec status, container_id, port
        """
        container_name = self.get_container_name(graph_name)
        
        # Convertir le chemin worker vers le chemin hôte
        host_graph_path = self._get_host_path_from_worker_mount(graph_path)
        
        # Vérifier si le container existe déjà
        try:
            existing = self.client.containers.get(container_name)
            if existing.status == "running":
                return {
                    "status": "already_running",
                    "container_id": existing.id,
                    "port": self._get_container_port(existing),
                    "message": "Container déjà actif"
                }
            else:
                # Redémarrer le container existant avec auto-heal réseau
                try:
                    existing.start()
                    return {
                        "status": "restarted",
                        "container_id": existing.id,
                        "port": self._get_container_port(existing),
                        "message": "Container redémarré"
                    }
                except APIError as e:
                    msg = str(e)
                    if "network" in msg and "not found" in msg:
                        try:
                            # Réparer l'attachement réseau puis redémarrer
                            self._heal_network(existing.name)
                            existing.start()
                            return {
                                "status": "restarted",
                                "container_id": existing.id,
                                "port": self._get_container_port(existing),
                                "message": "Container redémarré après réparation réseau"
                            }
                        except Exception as heal_err:
                            return {
                                "status": "error",
                                "message": f"Réparation réseau impossible: {heal_err}"
                            }
                    return {
                        "status": "error",
                        "message": f"Erreur Docker: {msg}"
                    }
        except NotFound:
            pass
        
        # Attribuer un port
        if port is None:
            port = self.get_next_available_port()
        
        # Vérifier que l'image existe, sinon la pull
        try:
            self.client.images.get(self.VALHALLA_IMAGE)
        except NotFound:
            try:
                self.client.images.pull(self.VALHALLA_IMAGE)
            except APIError as e:
                return {
                    "status": "error",
                    "message": f"Impossible de télécharger l'image Valhalla: {str(e)}"
                }
        
        # Créer et démarrer le container
        try:
            container = self.client.containers.run(
                image=self.VALHALLA_IMAGE,
                name=container_name,
                detach=True,
                command=[
                    "valhalla_service",
                    "/data/valhalla/valhalla_serve.json",  # Utiliser la version corrigée
                    "1"  # nombre de threads
                ],
                ports={"8002/tcp": port},
                volumes={
                    host_graph_path: {"bind": "/data/valhalla", "mode": "rw"}  # rw pour créer valhalla_serve.json
                },
                labels={
                    "valhalla.graph": graph_name,
                    "valhalla.managed": "true"
                },
                network=self.NETWORK_NAME,
                restart_policy={"Name": "unless-stopped"},
                healthcheck={
                    "test": ["CMD", "curl", "-f", "http://localhost:8002/status"],
                    "interval": 30000000000,  # 30s en nanosecondes
                    "timeout": 10000000000,    # 10s
                    "retries": 3
                }
            )
            
            return {
                "status": "started",
                "container_id": container.id,
                "port": port,
                "message": f"Container démarré sur le port {port}"
            }
            
        except APIError as e:
            return {
                "status": "error",
                "message": f"Erreur Docker: {str(e)}"
            }
    
    def stop_container(self, graph_name: str) -> Dict:
        """Arrête un container"""
        container_name = self.get_container_name(graph_name)
        
        try:
            container = self.client.containers.get(container_name)
            container.stop(timeout=10)
            return {
                "status": "stopped",
                "message": "Container arrêté"
            }
        except NotFound:
            return {
                "status": "not_found",
                "message": "Container introuvable"
            }
        except APIError as e:
            return {
                "status": "error",
                "message": f"Erreur: {str(e)}"
            }
    
    def restart_container(self, graph_name: str) -> Dict:
        """Redémarre un container"""
        container_name = self.get_container_name(graph_name)
        
        try:
            container = self.client.containers.get(container_name)
            try:
                container.restart(timeout=10)
                return {
                    "status": "restarted",
                    "port": self._get_container_port(container),
                    "message": "Container redémarré"
                }
            except APIError as e:
                msg = str(e)
                if "network" in msg and "not found" in msg:
                    # Auto-heal du réseau et démarrage
                    try:
                        self._heal_network(container.name)
                        container.start()
                        return {
                            "status": "restarted",
                            "port": self._get_container_port(container),
                            "message": "Container redémarré après réparation réseau"
                        }
                    except Exception as heal_err:
                        return {
                            "status": "error",
                            "message": f"Réparation réseau impossible: {heal_err}"
                        }
                return {
                    "status": "error",
                    "message": f"Erreur Docker: {msg}"
                }
        except NotFound:
            return {
                "status": "not_found",
                "message": "Container introuvable"
            }
        except APIError as e:
            return {
                "status": "error",
                "message": f"Erreur: {str(e)}"
            }
    
    def remove_container(self, graph_name: str, force: bool = False) -> Dict:
        """Supprime un container"""
        container_name = self.get_container_name(graph_name)
        
        try:
            container = self.client.containers.get(container_name)
            container.remove(force=force)
            return {
                "status": "removed",
                "message": "Container supprimé"
            }
        except NotFound:
            return {
                "status": "not_found",
                "message": "Container introuvable"
            }
        except APIError as e:
            return {
                "status": "error",
                "message": f"Erreur: {str(e)}"
            }
    
    def get_container_status(self, graph_name: str) -> Dict:
        """Récupère le statut d'un container"""
        container_name = self.get_container_name(graph_name)
        
        try:
            container = self.client.containers.get(container_name)
            stats = container.stats(stream=False)
            
            # Calculer l'utilisation CPU
            cpu_delta = stats["cpu_stats"]["cpu_usage"]["total_usage"] - \
                        stats["precpu_stats"]["cpu_usage"]["total_usage"]
            system_delta = stats["cpu_stats"]["system_cpu_usage"] - \
                          stats["precpu_stats"]["system_cpu_usage"]
            cpu_percent = 0.0
            if system_delta > 0:
                cpu_percent = (cpu_delta / system_delta) * len(stats["cpu_stats"]["cpu_usage"].get("percpu_usage", [1])) * 100
            
            # Utilisation mémoire
            mem_usage = stats["memory_stats"]["usage"]
            mem_limit = stats["memory_stats"]["limit"]
            mem_percent = (mem_usage / mem_limit) * 100
            
            return {
                "status": container.status,
                "running": container.status == "running",
                "port": self._get_container_port(container),
                "health": container.attrs.get("State", {}).get("Health", {}).get("Status", "unknown"),
                "cpu_percent": round(cpu_percent, 2),
                "memory_mb": round(mem_usage / (1024 * 1024), 2),
                "memory_percent": round(mem_percent, 2),
                "uptime": container.attrs["State"]["StartedAt"],
            }
        except NotFound:
            return {
                "status": "not_found",
                "running": False
            }
        except Exception as e:
            return {
                "status": "error",
                "running": False,
                "message": str(e)
            }
    
    def list_valhalla_containers(self) -> List[Dict]:
        """Liste tous les containers Valhalla gérés"""
        containers = self.client.containers.list(
            all=True,
            filters={"label": "valhalla.managed=true"}
        )
        
        result = []
        for container in containers:
            graph_name = container.labels.get("valhalla.graph", "unknown")
            result.append({
                "name": graph_name,
                "container_id": container.id,
                "container_name": container.name,
                "status": container.status,
                "running": container.status == "running",
                "port": self._get_container_port(container),
                "health": container.attrs.get("State", {}).get("Health", {}).get("Status", "unknown"),
            })
        
        return result
    
    def _get_container_port(self, container) -> Optional[int]:
        """Extrait le port mappé d'un container"""
        try:
            ports = container.attrs["NetworkSettings"]["Ports"]
            port_mapping = ports.get("8002/tcp", [])
            if port_mapping:
                return int(port_mapping[0]["HostPort"])
        except (KeyError, IndexError, TypeError):
            pass
        return None

    def _heal_network(self, container_name: str) -> None:
        """Reconnecte le container au réseau attendu pour corriger les IDs obsolètes"""
        try:
            # Déconnecter si déjà lié (au besoin, ignore les erreurs)
            try:
                self.client.api.disconnect_container_from_network(container_name, self.NETWORK_NAME)
            except Exception:
                pass
            # Reconnecter au réseau courant
            self.client.api.connect_container_to_network(container_name, self.NETWORK_NAME)
        except Exception as e:
            raise e
    
    def get_system_stats(self) -> Dict:
        """Statistiques système globales"""
        containers = self.list_valhalla_containers()
        
        total = len(containers)
        running = sum(1 for c in containers if c["running"])
        stopped = total - running
        
        return {
            "total_containers": total,
            "running_containers": running,
            "stopped_containers": stopped,
            "containers": containers
        }
