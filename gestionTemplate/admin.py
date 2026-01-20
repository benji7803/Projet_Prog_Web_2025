from django.contrib import admin
from . import models

# Register your models here.
admin.site.register(models.Campaign)
admin.site.register(models.CampaignTemplate)
admin.site.register(models.Plasmide)
admin.site.register(models.CorrespondanceTable)