from django.db import models
import os


class CampaignTemplate(models.Model):
    name = models.CharField("Nom du template", max_length=100)
    description = models.TextField("Description", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    file = models.FileField(upload_to='campaign_templates/', verbose_name="Fichier Excel")

    def __str__(self):
        return self.name

    def filename(self):
        return os.path.basename(self.file.name)
