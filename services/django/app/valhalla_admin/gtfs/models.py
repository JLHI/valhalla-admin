from django.db import models

class GtfsSource(models.Model):
    # Infos principales
    name = models.CharField(max_length=255)
    source_id = models.CharField(max_length=255, unique=True, help_text="Identifiant EU du dataset")
    url = models.URLField()
    publisher = models.CharField(max_length=255, null=True, blank=True)
    landing_page = models.URLField(null=True, blank=True)
    
    # Dates
    created_at = models.DateTimeField(auto_now_add=True)
    gtfs_modified = models.DateTimeField(null=True, blank=True)
    
    # Statut
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name