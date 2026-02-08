import io
import os
import zipfile
from django.core.management.base import BaseCommand
from django.core.files import File
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from gestionTemplate.models import CorrespondanceTable, PlasmidCollection, Plasmide, CampaignTemplate, MappingTemplate

User = get_user_model()

class Command(BaseCommand):
    help = "Importe des fichiers GB et XLSX dans la base de données"

    def handle(self, *args, **options):
        # 1. Configuration
        admin_user = User.objects.get(email="salah@dev.fr")
        data_path = os.path.join(os.getcwd(), 'data_init')
        
        zip_source_name = next((f for f in os.listdir(data_path) if f.endswith('.zip')), None)
        if not zip_source_name:
            self.stdout.write(self.style.ERROR("Aucun ZIP trouvé."))
            return

        zip_source_path = os.path.join(data_path, zip_source_name)
        liste_plasmides = []

        with zipfile.ZipFile(zip_source_path, 'r') as archive:
            gb_files = [f for f in archive.namelist() if f.endswith('.gb') and not f.startswith('__MACOSX')]
            
            for file_path_in_zip in gb_files:
                # On extrait le nom de fichier pur (sans le chemin du dossier)
                base_name = os.path.basename(file_path_in_zip)
                
                with archive.open(file_path_in_zip) as file_content:
                    # Création du fichier temporaire pour le parser
                    temp_path = os.path.join(data_path, "temp_parsing.gb")
                    with open(temp_path, "wb") as f:
                        f.write(file_content.read())
                    
                    plasmide = Plasmide.create_from_genbank(temp_path, dossier_nom="Import_ZIP")
                    plasmide.user = admin_user
                    # On force le nom si create_from_genbank utilise le nom du fichier temp
                    plasmide.name = os.path.splitext(base_name)[0]
                    plasmide.save()
                    
                    liste_plasmides.append(plasmide)
                    os.remove(temp_path)
                
                self.stdout.write(f"  - Importé : {base_name}")

        # Création de la collection
        if liste_plasmides:
            collection_name = f"Collection_{os.path.splitext(zip_source_name)[0]}"
            collection, _ = PlasmidCollection.objects.get_or_create(
                name=collection_name,
                user=admin_user
            )
            with open(zip_source_path, 'rb') as f:
                collection.plasmid_archive.save(zip_source_name, File(f), save=False)
            
            collection.plasmides.set(liste_plasmides)
            collection.save()
            self.stdout.write(self.style.SUCCESS(f"Collection '{collection_name}' créée !"))

        # --- 2. IMPORT DES TEMPLATES (.xlsx) ---
        self.stdout.write("Importation des templates Excel...")
        for file in os.listdir(data_path):
            if file.endswith('.xlsx') or file.endswith('.csv'):
                path = os.path.join(data_path, file)
                
                # Exemple pour un CampaignTemplate
                if "template" in file.lower():
                    with open(path, 'rb') as f:
                        ct = CampaignTemplate.objects.create(
                            name=f"Template {file}",
                            user=admin_user,
                            isPublic=True,
                            uploaded_by=admin_user
                        )
                        # On enregistre le fichier physique dans le champ FileField
                        ct.template_file.save(file, File(f))
                    self.stdout.write(self.style.SUCCESS(f"  - Template {file} chargé."))

                # Exemple pour un MappingTemplate
                elif "table" in file.lower():
                    with open(path, 'rb') as f:
                        mt = MappingTemplate.objects.create(
                            name=f"Mapping {file}",
                            user=admin_user
                        )
                        mt.mapping_file.save(file, File(f))
                    self.stdout.write(self.style.SUCCESS(f"  - Mapping {file} chargé."))

        self.stdout.write(self.style.SUCCESS("--- Fin de l'importation ---"))