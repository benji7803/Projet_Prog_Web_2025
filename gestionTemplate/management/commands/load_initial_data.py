import os
import csv
import shutil
from pathlib import Path
from django.core.management.base import BaseCommand
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from gestionTemplate.models import Plasmide, CampaignTemplate, MappingTemplate, PlasmidCollection
from users.models import Equipe

User = get_user_model()


class Command(BaseCommand):
    help = 'Charge les plasmides, templates et mappings depuis data_web'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Supprime tous les plasmides/templates existants avant de charger',
        )
        parser.add_argument(
            '--data-dir',
            type=str,
            default=os.path.join(settings.BASE_DIR, 'data_web'),
            help='Chemin du dossier contenant les données',
        )
        parser.add_argument(
            '--admin-email',
            type=str,
            default='admin@example.com',
            help='Email pour l\'utilisateur admin (défaut: admin@example.com)',
        )
        parser.add_argument(
            '--admin-password',
            type=str,
            default='admin123',
            help='Mot de passe pour l\'utilisateur admin (défaut: admin123)',
        )

    def handle(self, *args, **options):
        data_dir = options['data_dir']
        admin_email = options['admin_email']
        admin_password = options['admin_password']

        # Vérifier que le dossier existe
        if not os.path.exists(data_dir):
            self.stdout.write(
                self.style.ERROR(f"❌ Le dossier {data_dir} n'existe pas")
            )
            return

        # Créer ou récupérer l'utilisateur admin via email
        # Chercher d'abord s'il existe un utilisateur avec cet email
        try:
            admin_user = User.objects.get(email=admin_email)
            created = False
        except User.DoesNotExist:
            # Générer un username unique
            base_username = admin_email.split('@')[0]
            username = base_username
            counter = 1
            
            while User.objects.filter(username=username).exists():
                username = f"{base_username}{counter}"
                counter += 1
            
            # Créer nouvel utilisateur
            admin_user = User.objects.create_user(
                username=username,
                email=admin_email,
                password=admin_password,
                is_staff=True,
                is_superuser=True,
            )
            created = True
        
        # Si utilisateur existait, mettre à jour le mot de passe
        if not created:
            admin_user.set_password(admin_password)
            admin_user.is_staff = True
            admin_user.is_superuser = True
            admin_user.save()

        self.stdout.write("\n" + "="*70)
        self.stdout.write("CHARGEMENT DES DONNÉES")
        self.stdout.write("="*70)
        
        if created:
            self.stdout.write(
                self.style.SUCCESS(f"\n Utilisateur admin créé avec succès")
            )
        else:
            self.stdout.write(
                self.style.WARNING(f"\n Utilisateur admin mise à jour")
            )
        
        self.stdout.write(
            self.style.SUCCESS(f"\n Identifiants de connexion:")
        )
        self.stdout.write(f"   Email: {admin_email}")
        self.stdout.write(f"   Mot de passe: {admin_password}")
        self.stdout.write("")

        # Suppression des données si demandé
        if options['clear']:
            count_p = Plasmide.objects.count()
            count_t = CampaignTemplate.objects.count()
            count_m = MappingTemplate.objects.count()
            Plasmide.objects.all().delete()
            CampaignTemplate.objects.all().delete()
            MappingTemplate.objects.all().delete()
            self.stdout.write(
                self.style.WARNING(
                    f" Données supprimées: {count_p} plasmides, {count_t} templates, {count_m} mappings"
                )
            )
            self.stdout.write("")
        self.stdout.write("1️ Chargement des plasmides GenBank...")
        self._load_plasmids(data_dir, admin_user)

        # 2. Charger les mappings
        self.stdout.write("\n2️ Chargement des fichiers de mapping...")
        self._load_mappings(data_dir, admin_user)

        # 3. Charger les simulations (campagnes)
        self.stdout.write("\n3️ Chargement des template...")
        self._load_simulations(data_dir, admin_user)

        # 4. Charger les collections de plasmides
        self.stdout.write("\n4️ Chargement des collections de plasmides...")
        self._load_plasmid_collections(data_dir, admin_user)

        self.stdout.write("\n" + "="*70)
        self.stdout.write(self.style.SUCCESS(" Chargement terminé"))
        self.stdout.write("="*70)
        self.stdout.write(
            self.style.SUCCESS(f"\n Vous pouvez maintenant vous connecter avec:")
        )
        self.stdout.write(f"   Email: {admin_email}")
        self.stdout.write(f"   Mot de passe: {admin_password}\n")

    def _load_plasmids(self, data_dir, admin_user):
        """Charge tous les plasmides GenBank depuis data_web"""
        total_loaded = 0
        total_skipped = 0
        failed_files = []

        for root, dirs, files in os.walk(data_dir):
            # Ignorer les dossiers Simple_assembly et Typed_assembly pour les plasmides top-level
            rel_path = os.path.relpath(root, data_dir)
            
            for file in sorted(files):
                if file.endswith('.gb'):
                    if rel_path == '.':
                        dossier_nom = 'public'
                    else:
                        dossier_nom = rel_path.split(os.sep)[0]

                    filepath = os.path.join(root, file)

                    try:
                        plasmide = Plasmide.create_from_genbank(
                            filepath=filepath,
                            dossier_nom=dossier_nom
                        )

                        if plasmide.pk:
                            # Associer le plasmide à l'utilisateur admin
                            plasmide.user = admin_user
                            plasmide.save()
                            
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f"  ✓ {file:30} ({dossier_nom:15}) - "
                                    f"{plasmide.length:6} bp"
                                )
                            )
                            total_loaded += 1
                        else:
                            total_skipped += 1

                    except Exception as e:
                        self.stdout.write(
                            self.style.ERROR(
                                f"  ✗ {file:30} - {str(e)[:60]}"
                            )
                        )
                        failed_files.append((file, str(e)))

        self.stdout.write(
            f"  ✓ {total_loaded} plasmides chargés"
        )
        if total_skipped > 0:
            self.stdout.write(
                self.style.WARNING(f"  ⊘ {total_skipped} plasmides déjà existants")
            )
        if failed_files:
            self.stdout.write(
                self.style.ERROR(f"  ✗ {len(failed_files)} fichiers en erreur")
            )

    def _load_mappings(self, data_dir, admin_user):
        """Charge les fichiers de mapping CSV"""
        total_loaded = 0

        for root, dirs, files in os.walk(data_dir):
            for file in sorted(files):
                if file.startswith('iP_mapping_') and file.endswith('.csv'):
                    filepath = os.path.join(root, file)
                    mapping_name = file.replace('iP_mapping_', '').replace('.csv', '')

                    try:
                        # Lire le CSV et créer le mapping
                        mapping_data = {}
                        with open(filepath, 'r', encoding='utf-8') as f:
                            reader = csv.DictReader(f, delimiter=';')
                            for row in reader:
                                if row.get('pID') and row.get('Name'):
                                    mapping_data[row['pID']] = row['Name']

                        # Créer MappingTemplate
                        template, created = MappingTemplate.objects.get_or_create(
                            name=f"Mapping_{mapping_name}",
                            user=admin_user,
                            defaults={
                                'description': f"Mapping généré depuis {file}",
                                'is_public': True,
                            }
                        )

                        # Associer le fichier au mapping s'il n'existe pas
                        if created or not template.mapping_file:
                            with open(filepath, 'rb') as f:
                                template.mapping_file.save(
                                    file,
                                    ContentFile(f.read()),
                                    save=True
                                )

                        if created:
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f"  ✓ {file:35} ({len(mapping_data)} entrées)"
                                )
                            )
                            total_loaded += 1
                        else:
                            self.stdout.write(
                                self.style.WARNING(f"  ⊘ {file:35} déjà présent")
                            )

                    except Exception as e:
                        self.stdout.write(
                            self.style.ERROR(
                                f"  ✗ {file:35} - {str(e)[:50]}"
                            )
                        )

        self.stdout.write(f"  ✓ {total_loaded} fichiers de mapping chargés")

    def _load_simulations(self, data_dir, admin_user):
        """Charge les configurations de simulation depuis Simple_assembly et Typed_assembly"""
        total_loaded = 0

        # Traiter chaque répertoire de simulation
        simulation_dirs = ['Simple_assembly', 'Typed_assembly']

        for sim_type in simulation_dirs:
            sim_path = os.path.join(data_dir, sim_type)
            if not os.path.exists(sim_path):
                continue

            # Lire Campaign_*.csv
            campaign_files = [f for f in os.listdir(sim_path) 
                            if f.startswith('Campaign_') and f.endswith('.csv')]

            for campaign_file in campaign_files:
                campaign_path = os.path.join(sim_path, campaign_file)
                campaign_name = campaign_file.replace('Campaign_', '').replace('.csv', '')

                try:
                    # Parser le fichier Campaign
                    with open(campaign_path, 'r', encoding='utf-8') as f:
                        lines = [line.strip() for line in f.readlines()[:10]]

                    # Extraire les infos de base
                    enzyme = 'BsaI'  # défaut
                    separator = '-'

                    for line in lines:
                        if 'Restriction enzyme' in line:
                            parts = line.split(';')
                            if len(parts) > 1:
                                enzyme = parts[1].strip()
                        elif 'Output separator' in line:
                            parts = line.split(';')
                            if len(parts) > 1:
                                separator = parts[1].strip()

                    # Créer CampaignTemplate
                    template, created = CampaignTemplate.objects.get_or_create(
                        name=f"{campaign_name}_{sim_type}",
                        user=admin_user,
                        defaults={
                            'description': f"Simulation {campaign_name} ({sim_type})",
                            'restriction_enzyme': enzyme,
                            'separator_sortie': separator,
                            'isPublic': True,
                            'user': admin_user,  # Associer à l'admin user
                        }
                    )

                    if created:
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"  ✓ {sim_type:20} > {campaign_name:20} "
                                f"({enzyme})"
                            )
                        )
                        total_loaded += 1
                    else:
                        self.stdout.write(
                            self.style.WARNING(
                                f"  ⊘ {sim_type:20} > {campaign_name:20} "
                                f"déjà présent"
                            )
                        )

                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(
                            f"  ✗ {sim_type} > {campaign_file} - "
                            f"{str(e)[:45]}"
                        )
                    )

        self.stdout.write(f"  ✓ {total_loaded} simulations chargées")

    def _load_plasmid_collections(self, data_dir, admin_user):
        """Charge les collections de plasmides (fichiers zip)"""
        total_loaded = 0

        for root, dirs, files in os.walk(data_dir):
            for file in sorted(files):
                if file.endswith('.zip'):
                    filepath = os.path.join(root, file)
                    collection_name = file.replace('.zip', '')

                    try:
                        # Créer ou récupérer la collection
                        collection, created = PlasmidCollection.objects.get_or_create(
                            name=collection_name,
                            user=admin_user,
                            defaults={
                                'description': f"Collection de plasmides depuis {file}",
                            }
                        )

                        # Associer le fichier zip à la collection s'il n'existe pas
                        if created or not collection.plasmid_archive:
                            with open(filepath, 'rb') as f:
                                collection.plasmid_archive.save(
                                    file,
                                    ContentFile(f.read()),
                                    save=True
                                )

                        if created:
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f"  ✓ {file:35}"
                                )
                            )
                            total_loaded += 1
                        else:
                            self.stdout.write(
                                self.style.WARNING(f"  ⊘ {file:35} déjà présente")
                            )

                    except Exception as e:
                        self.stdout.write(
                            self.style.ERROR(
                                f"  ✗ {file:35} - {str(e)[:50]}"
                            )
                        )

        self.stdout.write(f"  ✓ {total_loaded} collections de plasmides chargées")
