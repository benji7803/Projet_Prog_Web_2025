from django.contrib import admin
from django.utils import timezone
from Bio import SeqIO
import zipfile
from io import TextIOWrapper
from django.contrib import messages
from .models import Campaign, CampaignTemplate, Plasmide, CorrespondanceTable, PublicationRequest

# Enregistrement standard des autres modèles
admin.site.register(Campaign)
admin.site.register(CampaignTemplate)
admin.site.register(Plasmide)
admin.site.register(CorrespondanceTable)

# ----- PublicationRequest Admin -----
@admin.register(PublicationRequest)
class PublicationRequestAdmin(admin.ModelAdmin):
    list_display = ("plasmid_name", "campaign", "requested_by", "status", "reviewed_at")
    list_filter = ("status",)
    actions = ["approve_requests", "reject_requests"]

    def approve_requests(self, request, queryset):
        """Valide les demandes et publie les plasmides correspondants."""
        approved = 0

        for req in queryset.filter(status="pending"):
            campaign = req.campaign
            plasmid_name = req.plasmid_name
            success = False

            # ---- fonction utilitaire pour traiter un zip ----
            def process_zip(zip_path):
                try:
                    with zipfile.ZipFile(zip_path, "r") as zf:
                        for f in zf.namelist():
                            if f.lower().endswith(('.gb', '.gbk')) and plasmid_name.lower() in f.lower():
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
                                            "features": {"raw": [f.qualifiers for f in record.features]}
                                        }
                                    )
                                    return True
                except Exception:
                    return False
                return False

            if campaign:
                # ---- Cas campagne ----
                if campaign.plasmid_archive:
                    success = process_zip(campaign.plasmid_archive.path)
                if not success and campaign.result_file:
                    success = process_zip(campaign.result_file.path)
            else:
                # ---- Cas upload individuel ----
                try:
                    p = Plasmide.objects.get(name=plasmid_name, user=req.requested_by)
                    p.dossier = "public"
                    p.save()
                    success = True
                except Plasmide.DoesNotExist:
                    success = False

            # ---- Mise à jour du statut ----
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
                        f"Votre demande de mise en public pour '{req.plasmid_name}' a été APPROUVÉE par l’administrateur."
                    )
                elif req.status == "rejected":
                    messages.add_message(
                        request,
                        messages.WARNING,
                        f"Votre demande de mise en public pour '{req.plasmid_name}' a été REFUSÉE par l’administrateur."
                    )
                req.notified = True

            req.save()

        self.message_user(request, f"{approved} demande(s) approuvée(s) et plasmide(s) publiés.")
    approve_requests.short_description = "Approuver et publier les plasmides sélectionnés"

    def reject_requests(self, request, queryset):
        """Rejette les demandes."""
        updated = 0

        for req in queryset.filter(status="pending"):
            req.status = "rejected"
            req.reviewed_at = timezone.now()
            req.reviewed_by = request.user

            # ---- Notification utilisateur ----
            if req.requested_by and not req.notified:
                messages.add_message(
                    request,
                    messages.WARNING,
                    f"Votre demande de mise en public pour '{req.plasmid_name}' a été REFUSÉE par l’administrateur."
                )
                req.notified = True

            req.save()
            updated += 1

        self.message_user(request, f"{updated} demande(s) rejetée(s).")
    reject_requests.short_description = "Rejeter les demandes sélectionnées"

