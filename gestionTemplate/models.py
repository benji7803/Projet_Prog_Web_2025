import os
import re
from django.db import models
from django.conf import settings
from django.db.models import Q

class CampaignTemplate(models.Model):
    name = models.CharField("Nom du template", max_length=100)
    description = models.TextField("Description", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    file = models.FileField(upload_to='campaign_templates/', verbose_name="Fichier Excel")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    display_name = models.CharField("Nom d'affichage", max_length=150, blank=True)

    def __str__(self):
        return self.name

    @staticmethod
    def generate_unique_filename(name):
        safe_name = re.sub(r'\W+', '_', name).strip('_')
        base_filename = f"Template_{safe_name}.xlsx"
        filename = base_filename
        counter = 0

        while CampaignTemplate.objects.filter(display_name=filename).exists():
            counter += 1
            filename = f"Template_{safe_name}_{counter}.xlsx"
        return filename
    
class Campaign(models.Model):
    name = models.CharField("Nom du template", max_length=100)
    description = models.TextField("Description", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    file = models.FileField(upload_to='campaign_templates/', verbose_name="Fichier Excel")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    display_name = models.CharField("Nom d'affichage", max_length=150, blank=True)
    plasmides = models.ManyToManyField('Plasmide', related_name='campaigns', blank=True)

    def __str__(self):
        return self.name

    @staticmethod
    def generate_unique_filename(name):
        safe_name = re.sub(r'\W+', '_', name).strip('_')
        base_filename = f"Template_{safe_name}.xlsx"
        filename = base_filename
        counter = 0

        while CampaignTemplate.objects.filter(display_name=filename).exists():
            counter += 1
            filename = f"Template_{safe_name}_{counter}.xlsx"
        return filename

class Plasmide(models.Model):
    name = models.CharField("Nom du plasmide", max_length=100)
    description = models.TextField("Description", blank=True)

    # GenBank fields
    accession = models.CharField("Accession", max_length=50, blank=True)
    version = models.CharField("Version", max_length=50, blank=True)
    genbank_definition = models.CharField("Definition GenBank", max_length=255, blank=True)
    organism = models.CharField("Organisme", max_length=150, blank=True)
    mol_type = models.CharField("Type molécule", max_length=50, blank=True)
    keywords = models.CharField("Mots-clés", max_length=255, blank=True)
    reference_authors = models.TextField("Auteurs / Référence", blank=True)
    reference_journal = models.TextField("Journal / Citation", blank=True)

    length = models.IntegerField("Longueur (bp)", null=True, blank=True)
    sequence = models.TextField("Séquence (nt)", blank=True)
    features = models.JSONField("Features (brut)", null=True, blank=True)
    gc_content = models.FloatField("GC (%)", null=True, blank=True)

    def __str__(self):
        return self.name
