from django.db import models
from django.conf import settings
import os
import uuid

class CampaignTemplate(models.Model):
    """
    Templates liés à un utilisateur connecté. 
    """
    name = models.CharField("Nom du template", max_length=100)
    description = models.TextField("Description", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    file = models.FileField(upload_to='campaign_templates/', verbose_name="Fichier Excel")
    mapping_file = models.FileField(upload_to='campaign_templates/', null=True, blank=True)
    plasmids_zip = models.FileField(upload_to='campaign_templates/', null=True, blank=True)
    primers_file = models.FileField(upload_to='campaign_templates/', null=True, blank=True)
    concentration_file = models.FileField(upload_to='campaign_templates/', null=True, blank=True)
    
    # Lien vers l'utilisateur propriétaire. Null = template anonyme
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True
    )

    def __str__(self):
        return self.name

    def filename(self):
        return os.path.basename(self.file.name)


