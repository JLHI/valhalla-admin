from django.db import models
from django.utils import timezone

class BuildTask(models.Model):
    STATUS_CHOICES = [
        ("pending", "En attente"),
        ("running", "En cours"),
        ("done", "Terminé"),
        ("error", "Erreur"),
    ]

    name = models.CharField(max_length=200)
    osm_file = models.CharField(max_length=300)
    gtfs_ids = models.JSONField()  # liste des IDs des GTFS
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(default=timezone.now)
    logs = models.TextField(blank=True, default="")

    output_dir = models.CharField(max_length=500, blank=True, null=True)

    def add_log(self, text):
        self.logs += f"\n[{timezone.now()}] {text}"
        self.save()