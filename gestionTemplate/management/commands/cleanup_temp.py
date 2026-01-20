import os
import shutil
import time
from pathlib import Path
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.conf import settings

class Command(BaseCommand):
    help = 'Supprime les dossiers temporaires vieux de plus de 24 heures.'

    def handle(self, *args, **options):
        # Configuration : Chemin et durée de vie
        temp_dir = Path(settings.MEDIA_ROOT) / 'temp_uploads'
        max_age_hours = 24
        
        # Calcul de la date limite (maintenant - 24h)
        limit_time = time.time() - (max_age_hours * 3600)

        if not temp_dir.exists():
            self.stdout.write(self.style.WARNING(f"Le dossier {temp_dir} n'existe pas encore. Rien à nettoyer."))
            return

        self.stdout.write(f"--- Nettoyage de {temp_dir} ---")
        deleted_count = 0

        # On parcourt tous les dossiers dans temp_uploads
        for item in os.listdir(temp_dir):
            item_path = temp_dir / item

            # On ne traite que les dossiers (les UUID générés)
            if item_path.is_dir():
                # Récupère la date de dernière modification
                mtime = os.path.getmtime(item_path)
                
                if mtime < limit_time:
                    try:
                        shutil.rmtree(item_path)
                        self.stdout.write(self.style.SUCCESS(f"Supprimé : {item}"))
                        deleted_count += 1
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"Erreur sur {item} : {e}"))
        
        if deleted_count == 0:
            self.stdout.write("Aucun vieux dossier à supprimer.")
        else:
            self.stdout.write(self.style.SUCCESS(f"Terminé. {deleted_count} dossiers supprimés."))