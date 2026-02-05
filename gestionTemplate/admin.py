from django.contrib import admin, messages
from django.utils import timezone
from Bio import SeqIO
import zipfile
from io import TextIOWrapper

from .models import (
    Campaign, CampaignTemplate, Plasmide, MappingTemplate, PublicationRequest
)

# --- Enregistrements standards ---
admin.site.register(Campaign)
admin.site.register(CampaignTemplate)
admin.site.register(Plasmide)
admin.site.register(MappingTemplate)


# ----- PublicationRequest Admin -----
@admin.register(PublicationRequest)
class PublicationRequestAdmin(admin.ModelAdmin):
    list_display = ("plasmid_name", "table", "campaign", "requested_by", "status", "reviewed_at")
    list_filter = ("status",)
    actions = ["approve_requests", "reject_requests"]

    def approve_requests(self, request, queryset):
        """Valide les demandes et publie les plasmides ou tables correspondants."""
        approved = 0

        for req in queryset.filter(status="pending"):
            success = False
            campaign = getattr(req, "campaign", None)
            name = req.plasmid_name

            # ---- Cas : plasmide ----
            if hasattr(req, "plasmid_name") and Plasmide.objects.filter(name=name).exists():
                # Fonction utilitaire pour traiter un zip
                def process_zip(zip_path):
                    try:
                        with zipfile.ZipFile(zip_path, "r") as zf:
                            for f in zf.namelist():
                                if f.lower().endswith(('.gb', '.gbk')) and name.lower() in f.lower():
                                    with zf.open(f) as gb_file:
                                        text_stream = TextIOWrapper(gb_file, encoding='utf-8')
                                        record = SeqIO.read(text_stream, "genbank")
                                        Plasmide.objects.update_or_create(
                                            name=record.name,
                                            defaults={
                                                "dossier": "public",
                                                "organism": record.annotations.get("organism", ""),
                                                "length": len(record.seq),
                                                "sequence": str(record.seq),
                                                "features": {"raw": [feat.qualifiers for feat in record.features]}
                                            }
                                        )
                                        return True
                    except Exception:
                        return False
                    return False

                if campaign:
                    if campaign.plasmid_archive:
                        success = process_zip(campaign.plasmid_archive.path)
                    if not success and campaign.result_file:
                        success = process_zip(campaign.result_file.path)
                else:
                    try:
                        p = Plasmide.objects.get(name=name, user=req.requested_by)
                        p.dossier = "public"
                        p.save()
                        success = True
                    except Plasmide.DoesNotExist:
                        success = False

            # ---- Cas : table MappingTemplate ----
            elif MappingTemplate.objects.filter(name=name).exists():
                try:
                    table = MappingTemplate.objects.get(name=name)
                    table.is_public = True
                    table.save()
                    success = True
                except MappingTemplate.DoesNotExist:
                    success = False

            # ---- Mise à jour du statut de la demande ----
            if success:
                req.status = "approved"
                approved += 1
            else:
                req.status = "rejected"

            req.reviewed_at = timezone.now()
            req.reviewed_by = request.user

            # ---- Notification utilisateur ----
            if req.requested_by and not req.notified:
                if req.status == "approved":
                    messages.add_message(
                        request,
                        messages.INFO,
                        f"Votre demande de mise en public pour '{req.plasmid_name}' a été APPROUVÉE."
                    )
                elif req.status == "rejected":
                    messages.add_message(
                        request,
                        messages.WARNING,
                        f"Votre demande de mise en public pour '{req.plasmid_name}' a été REFUSÉE."
                    )
                req.notified = True

            req.save()

        self.message_user(request, f"{approved} demande(s) approuvée(s) et éléments publiés.")
    approve_requests.short_description = "Approuver et publier les demandes sélectionnées"

    def reject_requests(self, request, queryset):
        """Rejette les demandes sélectionnées."""
        updated = 0

        for req in queryset.filter(status="pending"):
            req.status = "rejected"
            req.reviewed_at = timezone.now()
            req.reviewed_by = request.user

            if req.requested_by and not req.notified:
                messages.add_message(
                    request,
                    messages.WARNING,
                    f"Votre demande de mise en public pour '{req.plasmid_name}' a été REFUSÉE."
                )
                req.notified = True

            req.save()
            updated += 1

        self.message_user(request, f"{updated} demande(s) rejetée(s).")
    reject_requests.short_description = "Rejeter les demandes sélectionnées"
