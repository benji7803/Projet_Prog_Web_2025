import os
import re
from django.db import models
from django.conf import settings
from django.db.models import Q

class CampaignTemplate(models.Model):
    class EnzymeChoices(models.TextChoices):
        BSAI = 'BsaI', 'BsaI'
        BSMBI = 'BsmBI', 'BsmBI'
        BBSI = 'BbsI', 'BbsI'
        SAPI = 'SapI', 'SapI'

    name = models.CharField("Nom du template", max_length=100)
    description = models.TextField("Description", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    team = models.ForeignKey('users.Equipe', on_delete=models.CASCADE, null=True, blank=True)
    restriction_enzyme = models.CharField(
        max_length=10, 
        choices=EnzymeChoices.choices,
        default=EnzymeChoices.BSAI
    )
    separator_sortie = models.CharField(max_length=10, default='-')
    isPublic = models.BooleanField(default=False)
    # Fichier template associé (optionnel) — sera utilisé pour les templates publiés
    template_file = models.FileField(upload_to='simulations/templates/', null=True, blank=True)

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
    

class ColumnTemplate(models.Model):
    template = models.ForeignKey(CampaignTemplate, on_delete=models.CASCADE, related_name='columns')
    part_names = models.CharField(max_length=100)
    part_types = models.CharField(max_length=100, blank=True)
    is_optional = models.BooleanField(default=False)
    in_output_name = models.BooleanField(default=True)
    part_separators = models.CharField(max_length=10, blank=True)

class CorrespondanceTable(models.Model):
    name = models.CharField("Nom de la table de correspondance", max_length=100)
    description = models.TextField("Description", blank=True)
    mapping = models.JSONField("Mapping", default=dict)
    team = models.ForeignKey('users.Equipe', on_delete=models.CASCADE, null=True, blank=True)
    mapping_template = models.OneToOneField('MappingTemplate', on_delete=models.SET_NULL, null=True, blank=True, related_name='correspondance_table', help_text="Fichier original associé à cette table")


class PlasmidCollection(models.Model):
    """Stocke une collection réutilisable de plasmides pour un utilisateur"""
    name = models.CharField("Nom de la collection", max_length=200)
    description = models.TextField("Description", blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='plasmid_collections')
    plasmid_archive = models.FileField(upload_to='user_plasmid_collections/', help_text="Archive ZIP contenant les fichiers .gb originaux")
    plasmides = models.ManyToManyField('Plasmide', blank=True, related_name='collections', help_text="Plasmides parsés depuis cette collection")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.user.username})"


class MappingTemplate(models.Model):
    """Stocke un fichier de correspondance réutilisable pour un utilisateur"""
    name = models.CharField("Nom du fichier de correspondance", max_length=200)
    description = models.TextField("Description", blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='mapping_templates')
    mapping_file = models.FileField(upload_to='user_mapping_templates/', help_text="Fichier CSV/Excel original de correspondance")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.user.username})"

class Plasmide(models.Model):
    name = models.CharField("Nom du plasmide", max_length=100)
    description = models.TextField("Description", blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    dossier = models.CharField("Dossier", max_length=255, default="public")    
    team = models.ForeignKey('users.Equipe', on_delete=models.CASCADE, null=True, blank=True)

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

    class Meta:
        unique_together = ('name', 'dossier')  # empêche doublons dans le même dossier

    def __str__(self):
        return self.name

    @classmethod
    def create_from_genbank(cls, filepath, dossier_nom=None):
        """
        Parse un fichier GenBank et crée ou récupère un Plasmide.
        Retourne l'objet Plasmide.
        """
        import os
        name = os.path.splitext(os.path.basename(filepath))[0]

        # Vérifier si le plasmide existe déjà
        existing = cls.objects.filter(name=name, dossier=dossier_nom).first()
        if existing:
            return existing

        # Lecture du fichier GenBank
        with open(filepath, 'r', encoding='utf-8') as fh:
            lines = [l.rstrip('\n') for l in fh]

        fields = {}
        i = 0
        while i < len(lines):
            line = lines[i]
            if line.startswith('LOCUS'):
                m_len = re.search(r'(\d+)\s+bp', line)
                if m_len:
                    fields['length'] = int(m_len.group(1))
                m_mol = re.search(r'\d+\s+bp\s+([^\s]+)', line)
                if m_mol:
                    fields['mol_type'] = m_mol.group(1)
            elif line.startswith('DEFINITION'):
                val = line[len('DEFINITION'):].strip()
                j = i + 1
                while j < len(lines) and lines[j].startswith(' '):
                    cont = lines[j].strip()
                    if re.match(r'^[A-Z]+', cont) and cont.split()[0] in ('ACCESSION','VERSION','KEYWORDS','SOURCE','REFERENCE','FEATURES','ORIGIN','LOCUS','DEFINITION'):
                        break
                    val += ' ' + cont
                    j += 1
                fields['definition'] = val
                i = j - 1
            elif line.startswith('ACCESSION'):
                fields['accession'] = line[len('ACCESSION'):].strip()
            elif line.startswith('VERSION'):
                fields['version'] = line[len('VERSION'):].strip()
            elif line.startswith('KEYWORDS'):
                kw = line[len('KEYWORDS'):].strip()
                fields['keywords'] = kw.rstrip('.')
            elif line.lstrip().startswith('ORGANISM'):
                fields['organism'] = line.strip().split(None,1)[1] if len(line.strip().split(None,1))>1 else ''
            elif line.startswith('FEATURES'):
                feat_lines = []
                j = i + 1
                while j < len(lines) and not lines[j].startswith('ORIGIN'):
                    feat_lines.append(lines[j])
                    j += 1
                fields['features_raw'] = '\n'.join(feat_lines).strip()
                i = j - 1
            elif line.startswith('ORIGIN'):
                seq_parts = []
                j = i + 1
                while j < len(lines) and not lines[j].startswith('//'):
                    seq_line = re.sub(r'[^acgtACGT]', '', lines[j])
                    if seq_line:
                        seq_parts.append(seq_line)
                    j += 1
                seq = ''.join(seq_parts).upper()
                fields['sequence'] = seq
                fields['length'] = len(seq) if seq else fields.get('length')
                if seq:
                    gc = (seq.count('G') + seq.count('C')) / len(seq) * 100
                    fields['gc_content'] = round(gc, 2)
                i = j
            i += 1

        # Création du plasmide
        plasmide = cls.objects.create(
            name=name,
            description=fields.get('definition',''),
            dossier=dossier_nom,
            accession=fields.get('accession',''),
            version=fields.get('version',''),
            genbank_definition=fields.get('definition','')[:255],
            organism=fields.get('organism',''),
            mol_type=fields.get('mol_type',''),
            keywords=fields.get('keywords',''),
            length=fields.get('length'),
            sequence=fields.get('sequence',''),
            features={'raw': fields.get('features_raw','')},
            gc_content=fields.get('gc_content')
        )
        return plasmide

    def __str__(self):
        return self.name


class Campaign(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_RUNNING = 'running'
    STATUS_DONE = 'done'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_RUNNING, 'Running'),
        (STATUS_DONE, 'Done'),
        (STATUS_FAILED, 'Failed'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    team = models.ForeignKey('users.Equipe', on_delete=models.CASCADE, null=True, blank=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # fichiers requis pour la simulation
    template_file = models.FileField(upload_to='simulations/templates/', null=True)
    mapping_file = models.FileField(upload_to='simulations/mappings/', null=True)
    plasmid_archive = models.FileField(upload_to='simulations/plasmid_archive/', null=True)
    plasmids = models.ManyToManyField(Plasmide, blank=True)

    # Références aux collections réutilisables (optionnel - utilisé si l'utilisateur choisit une collection existante)
    plasmid_collection = models.ForeignKey(PlasmidCollection, on_delete=models.SET_NULL, null=True, blank=True, related_name='campaigns')
    mapping_template = models.ForeignKey(MappingTemplate, on_delete=models.SET_NULL, null=True, blank=True, related_name='campaigns')

    # optionnels
    primers_file = models.FileField(upload_to='simulations/primers/', null=True, blank=True)
    concentration_file = models.FileField(upload_to='simulations/concentrations/', null=True, blank=True)

    # options simples
    enzyme = models.CharField(max_length=100, blank=True, null=True)
    default_concentration = models.FloatField(default=200.0)
    # stocker paires / autres options en JSON
    options = models.JSONField(blank=True, default=dict)

    # résultat / statut
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING)
    result_file = models.FileField(upload_to='simulations/results/', null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"{self.name} ({self.pk})"

from django.db import models
from django.conf import settings  # ✅ pour AUTH_USER_MODEL

class PublicationRequest(models.Model):
    campaign = models.ForeignKey("Campaign", on_delete=models.CASCADE, null = True, blank = True)
    plasmid_name = models.CharField(max_length=255)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    status = models.CharField(
        max_length=20,
        choices=[
            ("pending", "En attente"),
            ("approved", "Approuvée"),
            ("rejected", "Rejetée"),
        ],
        default="pending",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_requests",
    )
    notified = models.BooleanField(default=False)
    def __str__(self):
        return f"Demande de publication : {self.plasmid_name} ({self.status})"
