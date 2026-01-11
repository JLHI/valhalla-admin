from django.db import models
from django.utils import timezone

class BuildTask(models.Model):

    STATUS_CHOICES = [
        ("pending", "En attente"),
        ("preparing", "Préparation des données"),
        ("building", "Construction des tuiles"),
        ("built", "Tuiles prêtes"),
        ("serving", "Serveur Valhalla actif"),
        ("error", "Erreur"),
    ]

    name = models.CharField(max_length=200)
    osm_file = models.CharField(max_length=300)
    gtfs_ids = models.JSONField()

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending"
    )

    created_at = models.DateTimeField(default=timezone.now)
    started_at = models.DateTimeField(blank=True, null=True)
    finished_at = models.DateTimeField(blank=True, null=True)
    logs = models.TextField(blank=True, default="")

    output_dir = models.CharField(max_length=500, blank=True, null=True)

    is_ready = models.BooleanField(default=False)
    is_serving = models.BooleanField(default=False)
    serve_port = models.IntegerField(null=True, blank=True)

    def add_log(self, text):
        line = f"\n[{timezone.now()}] {text}"
        # Append in-memory
        logs = (self.logs or "") + line
        # Cap logs to avoid OOM in worker/DB (keep last ~1MB)
        MAX_SIZE = 2_000_000  # 2 MB hard cap
        TRIM_TO = 1_000_000   # keep last 1 MB
        if len(logs) > MAX_SIZE:
            logs = logs[-TRIM_TO:]
        self.logs = logs
        # Try safe update to avoid race conditions / deleted rows
        try:
            self.save(update_fields=['logs'])
        except Exception:
            try:
                fresh = BuildTask.objects.filter(id=self.id).first()
                if fresh:
                    fresh.logs = logs
                    fresh.save(update_fields=['logs'])
                    # reflect back
                    self.logs = fresh.logs
            except Exception:
                # Swallow logging errors to avoid breaking the build pipeline
                pass