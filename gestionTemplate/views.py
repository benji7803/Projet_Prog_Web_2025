from django.shortcuts import render, redirect, get_object_or_404
from django.http import FileResponse, HttpResponse, Http404
from django.urls import reverse
from urllib.parse import quote, unquote
from django.conf import settings
from django.core.files import File
from django.core.files.storage import FileSystemStorage
from django.forms import inlineformset_factory
from django.db import transaction
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q


from .models import CampaignTemplate, Campaign, ColumnTemplate, PlasmidCollection, MappingTemplate, Plasmide, PublicationRequest, CorrespondanceTable
from .forms import CampaignTemplateForm, AnonymousSimulationForm, ColumnForm, UploadFileForm
from .plasmid_mapping import generate_plasmid_maps
from users.models import Seqcollection

from Bio import SeqIO
from io import TextIOWrapper
import pandas as pd
import uuid
import os
import pathlib
import zipfile
import tarfile
import shutil
import json
import csv
import io

# insillyclo
from insillyclo.template_generator import make_template
from insillyclo.data_source import DataSourceHardCodedImplementation
from insillyclo.observer import InSillyCloCliObserver
import insillyclo.data_source
import insillyclo.observer
import insillyclo.simulator


# Dashboard : Lister TOUS les templates (public)
def dashboard(request):
    # Force la création de la session pour l'utilisateur anonyme
    _ = request.session.session_key
    
    if request.method == 'POST':
        form = UploadFileForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                file = request.FILES['fichier']
                template = process_template(file, request.user if request.user.is_authenticated else None)
                # Si utilisateur anonyme, ajouter le template à sa session
                if not request.user.is_authenticated and template:
                    if 'anonymous_templates' not in request.session:
                        request.session['anonymous_templates'] = []
                    if template.id not in request.session['anonymous_templates']:
                        request.session['anonymous_templates'].append(template.id)
                    request.session.modified = True
                    messages.success(request, f"Template '{template.name}' créé et sauvegardé dans votre session.")
                elif template and request.user.is_authenticated:
                    messages.success(request, f"Template '{template.name}' créé avec succès.")
            except Exception as e:
                messages.error(request, f"Erreur lors de l'upload : {str(e)}")
        else:
            messages.error(request, "Veuillez sélectionner un fichier valide.")
    else:
        form = UploadFileForm()

    if request.user.is_authenticated:
        # Récupérer les templates privés de l'utilisateur ET les templates publics
        liste_templates = CampaignTemplate.objects.filter(
            Q(user=request.user) | Q(isPublic=True)
        ).order_by('-created_at')
        previous_sim = Campaign.objects.filter(user=request.user).order_by('-created_at')
        anonymous_template_ids = []
    else:
        # Utilisateur non authentifié : montrer templates publics + ses propres templates en session
        anonymous_template_ids = request.session.get('anonymous_templates', [])
        liste_templates = CampaignTemplate.objects.filter(
            Q(isPublic=True) | Q(id__in=anonymous_template_ids)
        ).order_by('-created_at')
        previous_sim = None
    
    context = {
        'liste_templates': liste_templates,
        'previous_sim': previous_sim,
        'form': form,
        'anonymous_template_ids': anonymous_template_ids,
    }

    return render(request, 'gestionTemplates/dashboard.html', context)


ColumnFormSet = inlineformset_factory(
    CampaignTemplate,
    ColumnTemplate,
    form = ColumnForm,
    extra=2,
    can_delete=True
)


def create_template(request):
    if request.method == 'POST':
        form = CampaignTemplateForm(request.POST)
        parent = form.save(commit=False) if form.is_valid() else CampaignTemplate()
        formset = ColumnFormSet(request.POST, instance=parent, prefix='columns')

        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                parent.user = request.user if request.user.is_authenticated else None
                parent.save()
                formset.instance = parent
                formset.save()
                
                # Si utilisateur anonyme, tracker le template en session
                if not request.user.is_authenticated:
                    if 'anonymous_templates' not in request.session:
                        request.session['anonymous_templates'] = []
                    if parent.id not in request.session['anonymous_templates']:
                        request.session['anonymous_templates'].append(parent.id)
                    request.session.modified = True
                    messages.success(request, f"Template '{parent.name}' créé et sauvegardé dans votre session.")
                else:
                    messages.success(request, f"Template '{parent.name}' créé avec succès.")
            return redirect('templates:dashboard')
        
    else:
        form = CampaignTemplateForm()
        formset = ColumnFormSet(instance=CampaignTemplate(), prefix='columns')

    return render(request, 'gestionTemplates/create.html', {"form": form, "formset": formset, "is_edit": False})

# Upload
def process_template(file, user=None, is_public=False):
    df_raw = pd.read_excel(file, header=None)

    # Extraction des métadonnées
    enzyme = df_raw.iloc[1, 1]
    project_name = df_raw.iloc[2, 1]
    output_separator = df_raw.iloc[3, 1]

    # Trouver la ligne de départ
    start_row = 0
    for i, row in df_raw.iterrows():
        if "Output plasmid id" in str(row[0]):
            start_row = i
            break

    df_plasmids = df_raw.iloc[start_row:].copy()
    df_plasmids.columns = df_plasmids.iloc[0]
    df_plasmids = df_plasmids[1:]
    df_plasmids = df_plasmids.dropna(subset=[df_plasmids.columns[0]])

    # Créer le CampaignTemplate
    campaign_template = CampaignTemplate.objects.create(
        name=project_name,
        description=f"Template importé de {file.name}",
        restriction_enzyme=enzyme,
        separator_sortie=output_separator,
        user=user,
        isPublic=is_public
    )

    # Extraire et créer les colonnes (à partir de la colonne 2)
    part_columns = df_plasmids.columns[2:]
    for col_name in part_columns:
        if pd.notna(col_name):
            ColumnTemplate.objects.create(
                template=campaign_template,
                part_names=str(col_name),
                part_types='',
                is_optional=False,
                in_output_name=True,
                part_separators=output_separator
            )
    
    return campaign_template


def can_edit_template(request, template):
    """Vérifie si l'utilisateur peut modifier ce template"""
    if request.user.is_authenticated:
        return template.user == request.user or request.user.isAdministrator
    else:
        # Utilisateur anonyme : vérifie si le template est en session
        anonymous_template_ids = request.session.get('anonymous_templates', [])
        return template.id in anonymous_template_ids


# Modification
def edit_template(request, template_id):
    
    campaign = get_object_or_404(CampaignTemplate, id=template_id)
    
    # Vérifications de permission
    if campaign.isPublic and (not request.user.is_authenticated or not request.user.isAdministrator):
        messages.error(request, "Vous n'avez pas la permission de modifier ce template public.")
        return redirect('templates:dashboard')
    
    if not can_edit_template(request, campaign):
        messages.error(request, "Vous n'avez pas la permission de modifier ce template.")
        return redirect('templates:dashboard')

    if request.method == 'POST':
        form = CampaignTemplateForm(request.POST, instance=campaign)
        parent = form.save(commit=False) if form.is_valid() else CampaignTemplate()
        formset = ColumnFormSet(request.POST, instance=campaign, prefix='columns')

        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                parent.user = request.user if request.user.is_authenticated else None
                parent.save()
                formset.instance = parent
                formset.save()
                messages.success(request, f"Template '{parent.name}' mis à jour avec succès.")
            return redirect('templates:dashboard')
        
    else:
        form = CampaignTemplateForm(instance=campaign)
        formset = ColumnFormSet(instance=campaign, prefix='columns')

    return render(request, 'gestionTemplates/create.html', {"form": form, "formset": formset, "is_edit": True})


# Téléchargement
def download_template(request, template_id):
    template = get_object_or_404(CampaignTemplate, id=template_id)

    # Récupérer les colonnes du template
    columns = template.columns.all()
    
    # Construire la liste des InputPart pour insillyclo
    input_parts = []
    for col in columns:
        part_types = col.part_types.split(',') if col.part_types else ['1']
        input_part = insillyclo.models.InputPart(
            name=col.part_names,
            part_types=part_types,
            is_optional=col.is_optional,
            in_output_name=col.in_output_name,
            separator=col.part_separators or ""
        )
        input_parts.append(input_part)
    
    # Créer un fichier temporaire
    output_path = pathlib.Path(settings.MEDIA_ROOT) / 'temp_downloads' / f"{template.name}_{uuid.uuid4().hex[:8]}.xlsx"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Générer le template avec insillyclo
    observer = InSillyCloCliObserver(debug=False)
    data_source = DataSourceHardCodedImplementation()
    
    make_template(
        destination_file=output_path,
        input_parts=input_parts,
        observer=observer,
        data_source=data_source,
        default_separator=template.separator_sortie,
        enzyme=template.restriction_enzyme,
        name=template.name,
        default_plasmid=["pID001"]
    )
    
    # Envoyer le fichier au client
    response = FileResponse(open(output_path, 'rb'), as_attachment=True, filename=f"{template.name}.xlsx")

    return response


def submit(request):
    data_html = None
    message = None
    inputs_name = []
    file_names = []

    # Récupérer les collections et fichiers de correspondance de l'utilisateur
    plasmid_collections = []
    mapping_templates = []
    if request.user.is_authenticated:
        plasmid_collections = PlasmidCollection.objects.filter(user=request.user).order_by('-created_at')
        mapping_templates = MappingTemplate.objects.filter(user=request.user).order_by('-created_at')

    if request.method == "POST":
        # ===== UPLOAD NOUVELLE COLLECTION DE PLASMIDES =====
        if 'save_collection' in request.POST and request.user.is_authenticated:
            collection_name = request.POST.get('collection_name', '').strip()
            collection_desc = request.POST.get('collection_description', '').strip()
            plasmid_archive = request.FILES.get('collection_plasmid_archive') or request.FILES.get('plasmid_archive') or request.FILES.get('plasmid-archive') or request.FILES.get('plasmid-archive-direct')
            
            if collection_name and plasmid_archive:
                try:
                    # Créer la collection
                    collection = PlasmidCollection.objects.create(
                        user=request.user,
                        name=collection_name,
                        description=collection_desc,
                        plasmid_archive=plasmid_archive
                    )
                    
                    # Parser et créer les Plasmide depuis l'archive ZIP
                    import tempfile
                    with tempfile.TemporaryDirectory() as temp_dir:
                        temp_path = pathlib.Path(temp_dir)
                        
                        # Extraire l'archive
                        with zipfile.ZipFile(plasmid_archive) as z:
                            z.extractall(temp_path)
                        
                        # Trouver tous les fichiers .gb
                        for gb_file in temp_path.glob('**/*.gb'):
                            try:
                                # Parser le fichier et créer le Plasmide
                                plasmide = Plasmide.create_from_genbank(
                                    str(gb_file),
                                    dossier_nom=collection_name
                                )
                                # Lier le plasmide à la collection
                                collection.plasmides.add(plasmide)
                                # Lier l'utilisateur au plasmide
                                if request.user.is_authenticated:
                                    plasmide.user = request.user
                                    plasmide.save()
                            except Exception as e:
                                print(f"Erreur parsing {gb_file.name}: {str(e)}")
                    
                    message = f"✅ Collection '{collection_name}' créée avec succès ! ({collection.plasmides.count()} plasmides détectés)"
                    # Rafraîchir la liste
                    plasmid_collections = PlasmidCollection.objects.filter(user=request.user).order_by('-created_at')
                except Exception as e:
                    message = f"Erreur lors de la création de la collection : {str(e)}"
            else:
                message = "Veuillez remplir le nom de la collection et uploader un fichier."

        # ===== UPLOAD NOUVEAU FICHIER DE CORRESPONDANCE =====
        elif 'save_mapping' in request.POST and request.user.is_authenticated:
            mapping_name = request.POST.get('mapping_name', '').strip()
            mapping_desc = request.POST.get('mapping_description', '').strip()
            mapping_file = request.FILES.get('mapping_file_upload')
            
            if mapping_name and mapping_file:
                try:
                    # Créer le fichier de correspondance
                    template = MappingTemplate.objects.create(
                        user=request.user,
                        name=mapping_name,
                        description=mapping_desc,
                        mapping_file=mapping_file
                    )
                    message = f"Fichier de correspondance '{mapping_name}' créé avec succès !"
                    # Rafraîchir la liste
                    mapping_templates = MappingTemplate.objects.filter(user=request.user).order_by('-created_at')
                except Exception as e:
                    message = f"Erreur lors de la création du fichier : {str(e)}"
            else:
                message = "Veuillez remplir le nom du fichier et uploader un fichier."

        # ===== UPLOAD ET TRAITEMENT FICHIER EXCEL =====
        uploaded_file = request.FILES.get('uploaded_file')
        plasmid_archive = request.FILES.get('plasmid_archive')

        # 1 Gestion du fichier Excel
        if uploaded_file:
            try:
                df = pd.read_excel(uploaded_file)
                data_html = df.to_html(classes='table table-striped', index=False)
                data_plasmides = pd.read_excel(uploaded_file, header=8)
                inputs_name = data_plasmides.columns[2:].tolist()

                # Stockage en session
                request.session['inputs_name'] = inputs_name
                request.session['data_html'] = data_html

                # Publication optionnelle depuis l'écran de vérification
                if request.POST.get('publish_template') == 'on' and request.user.is_authenticated:
                    publish_name = request.POST.get('publish_name') or os.path.splitext(uploaded_file.name)[0]
                    try:
                        pub = CampaignTemplate.objects.create(
                            name=publish_name,
                            description=f"Publié depuis la page Soumettre par {request.user.username}",
                            isPublic=True,
                            user=request.user
                        )
                        message = f"✅ Template '{publish_name}' publié avec succès !"
                    except Exception as e:
                        message = f"Erreur publication : {e}"

            except Exception as e:
                message = f"Erreur Excel : {e}"

        # 2 Gestion de l'archive
        if plasmid_archive:
            # A partir des données stockées
            inputs_name = request.session.get('inputs_name', [])
            data_html = request.session.get('data_html', None)

            try:
                ext = plasmid_archive.name.lower()
                if ext.endswith('.zip'):
                    with zipfile.ZipFile(plasmid_archive) as z:
                        file_names = [f for f in z.namelist() if not f.endswith('/')]
                elif ext.endswith(('.tar', '.tar.gz', '.tgz')):
                    with tarfile.open(fileobj=plasmid_archive) as t:
                        file_names = [m.name for m in t.getmembers() if m.isfile()]
            except Exception as e:
                message = f"Erreur Archive : {e}"

    return render(request, "gestionTemplates/submit.html", {
        "data_html": data_html,
        "message": message,
        "nb_plasmid": inputs_name,
        "file_names": file_names,
        "plasmid_collections": plasmid_collections,
        "mapping_templates": mapping_templates,
    })


def simulate(request):
    # Choix du template HTML selon le statut
    template_name = 'gestionTemplates/sim.html'
    
    if request.method == 'POST':
        form = AnonymousSimulationForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                unique_id = str(uuid.uuid4())
                BASE_MEDIA = pathlib.Path(settings.MEDIA_ROOT)
                SANDBOX_DIR = BASE_MEDIA / 'temp_uploads' / unique_id
                
                PLASMIDS_DIR = SANDBOX_DIR / 'plasmids'
                OUTPUT_DIR = SANDBOX_DIR / 'output'
                PLASMIDS_DIR.mkdir(parents=True, exist_ok=True)
                OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

                campaign_instance = None
                
                # =========================================================
                # Vérifier les sources de fichiers (upload vs existants)
                # =========================================================
                template_file_source = None  # 'upload' ou 'existing'
                plasmids_source = None      # 'upload' ou 'collection'
                mapping_source = None       # 'upload' ou 'template'
                
                # Déterminer la source du template
                template_existing_id = form.cleaned_data.get('template_existing')
                if template_existing_id:
                    template_file_source = 'existing'
                    template_obj = get_object_or_404(CampaignTemplate, id=template_existing_id, user=request.user)
                elif request.FILES.get('template_file'):
                    template_file_source = 'upload'
                else:
                    raise ValueError("Aucun fichier template fourni")
                
                # Déterminer la source des plasmides
                collection_id = form.cleaned_data.get('plasmid_collection_id')
                if collection_id:
                    plasmids_source = 'collection'
                    collection_obj = get_object_or_404(PlasmidCollection, id=collection_id, user=request.user)
                elif request.FILES.get('plasmids_zip'):
                    plasmids_source = 'upload'
                else:
                    raise ValueError("Aucune archive de plasmides fournie")
                
                # Déterminer la source du mapping
                mapping_id = form.cleaned_data.get('mapping_template_id')
                if mapping_id:
                    mapping_source = 'template'
                    mapping_obj = get_object_or_404(MappingTemplate, id=mapping_id, user=request.user)
                elif request.FILES.get('mapping_file'):
                    mapping_source = 'upload'
                else:
                    raise ValueError("Aucun fichier de correspondance fourni")
                
                # =========================================================
                # CAS 1 : UTILISATEUR CONNECTÉ (Sauvegarde en BDD)
                # =========================================================
                if request.user.is_authenticated:
                    # A. Création de l'objet Campaign
                    campaign_instance = Campaign(
                        user=request.user,
                        name=f"sim_{unique_id[:8]}", 
                        status=Campaign.STATUS_RUNNING,
                        
                        # Options simples
                        enzyme=form.cleaned_data.get('enzyme'),
                        default_concentration=form.cleaned_data.get('default_concentration') or 200.0,
                    )
                    
                    # Définir les fichiers selon la source
                    if template_file_source == 'upload':
                        campaign_instance.template_file = request.FILES['template_file']
                    else:
                        campaign_instance.template_file = template_obj.template_file
                    
                    if mapping_source == 'upload':
                        campaign_instance.mapping_file = request.FILES['mapping_file']
                    else:
                        campaign_instance.mapping_file = mapping_obj.mapping_file
                    
                    if plasmids_source == 'upload':
                        campaign_instance.plasmid_archive = request.FILES['plasmids_zip']
                    else:
                        campaign_instance.plasmid_collection = collection_obj

                    # Gestion des fichiers optionnels
                    if form.cleaned_data.get('primers_file'):
                        campaign_instance.primers_file = request.FILES['primers_file']
                    if form.cleaned_data.get('concentration_file'):
                        campaign_instance.concentration_file = request.FILES['concentration_file']
                    
                    # Options JSON
                    pairs_data = form.cleaned_data.get('primer_pairs')
                    options_dict = {}
                    if pairs_data:
                        options_dict['primer_pairs'] = pairs_data
                    campaign_instance.options = options_dict
                    
                    campaign_instance.save() # On sauvegarde pour obtenir un ID

                    # D. Publication optionnelle (via le formulaire submit)
                    try:
                        if request.POST.get('publish_template') == 'on' and request.user.is_authenticated:
                            publish_name = request.POST.get('publish_name') or f"Template_{uuid.uuid4().hex[:6]}"

                            # Cas : on a choisi un template existant -> cloner les colonnes
                            if template_file_source == 'existing':
                                old_columns = list(template_obj.columns.all())
                                public = CampaignTemplate(
                                    name=publish_name,
                                    description=template_obj.description,
                                    restriction_enzyme=template_obj.restriction_enzyme,
                                    separator_sortie=template_obj.separator_sortie,
                                    isPublic=True,
                                    user=request.user,
                                )
                                public.template_file = template_obj.template_file
                                public.save()

                                for col in old_columns:
                                    col.pk = None
                                    col.id = None
                                    col.template = public
                                    col.save()

                            else:
                                # Cas : upload direct -> créer un template public lié au même fichier
                                public = CampaignTemplate(
                                    name=publish_name,
                                    description='Publié via Submit',
                                    isPublic=True,
                                    user=None,
                                )
                                public.template_file = campaign_instance.template_file
                                # si l'enzyme a été fournie, on la copie
                                if campaign_instance.enzyme:
                                    public.restriction_enzyme = campaign_instance.enzyme
                                public.save()

                            messages.success(request, f"Template '{public.name}' publié avec succès.")
                    except Exception as e:
                        # Ne pas interrompre la simulation si la publication échoue
                        print(f"Erreur publication template: {e}")

                    # B. Gestion des plasmides
                    if plasmids_source == 'upload':
                        # Gestion MANUELLE de l'archive ZIP sur le disque
                        uploaded_zip = request.FILES['plasmids_zip']
                        zip_path_on_disk = SANDBOX_DIR / "temp_plasmids.zip"
                        
                        with open(zip_path_on_disk, 'wb+') as destination:
                            for chunk in uploaded_zip.chunks():
                                destination.write(chunk)

                        # Extraction de l'archive
                        with zipfile.ZipFile(zip_path_on_disk, 'r') as zip_ref:
                            zip_ref.extractall(PLASMIDS_DIR)
                        
                        # Parsing et Création des objets Plasmide en BDD
                        # On parcourt tous les dossiers extraits pour trouver les .gb
                        for root, dirs, files in os.walk(PLASMIDS_DIR):
                            
                            rel_path = os.path.relpath(root, PLASMIDS_DIR)
                            current_dossier = rel_path if rel_path != "." else None

                            for file in files:
                                if file.lower().endswith('.gb') or file.lower().endswith('.gbk'):
                                    full_file_path = os.path.join(root, file)
                                    try:
                                        new_plasmid = Plasmide.create_from_genbank(
                                            full_file_path, 
                                            dossier_nom=current_dossier
                                        )
                                        
                                        new_plasmid.user = request.user
                                        new_plasmid.save()
                                        
                                        campaign_instance.plasmids.add(new_plasmid)
                                        
                                    except Exception as e:
                                        print(f"Erreur import plasmide {file}: {e}")
                    else:
                        # Utiliser la collection existante
                        campaign_instance.plasmids.set(collection_obj.plasmides.all())

                    # E. Définition des chemins pour le simulateur
                    full_template_path = pathlib.Path(campaign_instance.template_file.path)
                    full_mapping_path = pathlib.Path(campaign_instance.mapping_file.path)
                    
                    # Extraction de l'archive stockée
                    if plasmids_source == 'upload':
                        archive_path = pathlib.Path(campaign_instance.plasmid_archive.path)
                    else:
                        # Utiliser l'archive de la collection
                        archive_path = pathlib.Path(collection_obj.plasmid_archive.path)
                    
                    with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                        zip_ref.extractall(PLASMIDS_DIR)
                        
                    # Chemins optionnels
                    final_primers_path = pathlib.Path(campaign_instance.primers_file.path) if campaign_instance.primers_file else None
                    final_conc_path = pathlib.Path(campaign_instance.concentration_file.path) if campaign_instance.concentration_file else None

                # =========================================================
                # CAS 2 : UTILISATEUR ANONYME (Fichiers temporaires uniquement)
                # =========================================================
                else:
                    fs = FileSystemStorage(location=SANDBOX_DIR)
                    
                    # Sauvegarde simple sur disque sans BDD
                    f_template = request.FILES['template_file']
                    full_template_path = SANDBOX_DIR / pathlib.Path(fs.save("campaign.xlsx", f_template))
                    
                    f_mapping = request.FILES['mapping_file']
                    full_mapping_path = SANDBOX_DIR / pathlib.Path(fs.save("mapping.csv", f_mapping))
                    
                    f_zip = request.FILES['plasmids_zip']
                    path_zip = pathlib.Path(fs.save("plasmids.zip", f_zip))
                    with zipfile.ZipFile(SANDBOX_DIR / path_zip, 'r') as zip_ref:
                        zip_ref.extractall(PLASMIDS_DIR)
                    
                    final_primers_path = None
                    if form.cleaned_data['primers_file']:
                        f_primers = request.FILES['primers_file']
                        final_primers_path = SANDBOX_DIR / pathlib.Path(fs.save("primers.csv", f_primers))
                        
                    final_conc_path = None
                    if form.cleaned_data['concentration_file']:
                        f_conc = request.FILES['concentration_file']
                        final_conc_path = SANDBOX_DIR / pathlib.Path(fs.save("concentrations.csv", f_conc))

                # === 3 PRÉPARATION PARAMÈTRES COMMUNS ===
                enzyme_data = form.cleaned_data['enzyme']
                final_enzyme_names = [enzyme_data] if enzyme_data else None
                final_default_conc = form.cleaned_data['default_concentration'] or 200.0
                
                pairs_data = form.cleaned_data['primer_pairs']
                final_primer_pairs = None
                if pairs_data and pairs_data.strip():
                    parts = [p.strip() for p in pairs_data.split(',')]
                    if len(parts) >= 2:
                        final_primer_pairs = [(parts[0], parts[1])]

                # === 4 LANCEMENT DE LA SIMULATION ===
                observer = insillyclo.observer.InSillyCloCliObserver(debug=False, fail_on_error=True)
                
                insillyclo.simulator.compute_all(
                    observer=observer,
                    settings=None,
                    input_template_filled=full_template_path,
                    input_parts_files=[full_mapping_path],
                    gb_plasmids=PLASMIDS_DIR.glob('**/*.gb'), # Cherche récursivement les .gb
                    output_dir=OUTPUT_DIR,
                    data_source=insillyclo.data_source.DataSourceHardCodedImplementation(),
                    primers_file=final_primers_path,
                    concentration_file=final_conc_path,
                    primer_id_pairs=final_primer_pairs,
                    enzyme_names=final_enzyme_names,
                    default_mass_concentration=final_default_conc,
                )

                # === 5 PACKAGING ET SAUVEGARDE RÉSULTAT ===
                if not os.listdir(OUTPUT_DIR):
                    raise Exception("La simulation n'a produit aucun fichier.")

                final_zip_name = f"resultats_{'user' if request.user.is_authenticated else 'anonymes'}_{unique_id}.zip"
                final_zip_path = SANDBOX_DIR / final_zip_name
                make_zipfile(str(OUTPUT_DIR), str(final_zip_path))

                # === RETOUR ===
                if campaign_instance:
                    # Sauvegarde du résultat final en BDD
                    with open(final_zip_path, 'rb') as f:
                        campaign_instance.result_file.save(final_zip_name, File(f))
                        campaign_instance.status = Campaign.STATUS_DONE
                        campaign_instance.save()
                    
                    # Nettoyage dossier temporaire
                    try:
                        shutil.rmtree(SANDBOX_DIR)
                    except OSError as e:
                        print(f"Erreur nettoyage : {e}")

                    # Pour l'utilisateur connecté, on redirige souvent vers le dashboard ou on renvoie le fichier stocké
                    response = FileResponse(campaign_instance.result_file.open('rb'), as_attachment=True, filename=final_zip_name)
                    response["X-Suggested-Filename"] = final_zip_name
                    return response
                else:
                    # Anonyme : On laisse le fichier temporaire pour le téléchargement
                    return FileResponse(open(final_zip_path, 'rb'), as_attachment=True, filename=final_zip_name)

            except Exception as e:
                # Gestion d'erreur (Statut Failed en BDD)
                if campaign_instance:
                    campaign_instance.status = Campaign.STATUS_FAILED
                    campaign_instance.error_message = str(e)
                    campaign_instance.save()
                    
                return render(request, template_name, {
                    'form': form,
                    'error': f"Erreur de simulation : {str(e)}",
                    'existing_templates': CampaignTemplate.objects.filter(user=request.user).order_by('-created_at') if request.user.is_authenticated else None,
                    'plasmid_collections': PlasmidCollection.objects.filter(user=request.user).order_by('-created_at') if request.user.is_authenticated else None,
                    'mapping_templates': MappingTemplate.objects.filter(user=request.user).order_by('-created_at') if request.user.is_authenticated else None,
                })
    else:
        form = AnonymousSimulationForm()

    context = {'form': form}

    if request.user.is_authenticated:
        context['existing_templates'] = CampaignTemplate.objects.filter(user=request.user).order_by('-created_at')
        context['plasmid_collections'] = PlasmidCollection.objects.filter(user=request.user).order_by('-created_at')
        context['mapping_templates'] = MappingTemplate.objects.filter(user=request.user).order_by('-created_at')

    return render(request, template_name, context)

# Fonction utilitaire création zipfile
def make_zipfile(source_dir, output_filename):
    with zipfile.ZipFile(output_filename, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(source_dir):
            for file in files:
                zipf.write(os.path.join(root, file),
                           os.path.relpath(os.path.join(root, file),
                           os.path.join(source_dir, '..')))


def delete_template(request, template_id):
    campaign = get_object_or_404(CampaignTemplate, id=template_id)
    
    if not can_edit_template(request, campaign):
        messages.error(request, "Vous n'avez pas la permission de supprimer ce template.")
        return redirect('templates:dashboard')
    
    campaign.delete()
    messages.success(request, f"Template '{campaign.name}' supprimé avec succès.")
    return redirect('templates:dashboard')


def delete_campaign(request, campaign_id):
    campaign = get_object_or_404(Campaign, id=campaign_id)
    campaign.delete()
    messages.success(request, f"Campagne '{campaign.name}' supprimée avec succès.")
    return redirect('templates:dashboard')


def view_plasmid(request):
    # ---- Notifications des décisions de l'admin ----
    if request.user.is_authenticated:
        pending_notifications = PublicationRequest.objects.filter(
            requested_by=request.user,
            notified=False
        ).exclude(status="pending")  # on ne prend que approved ou rejected

        for req in pending_notifications:
            if req.status == "approved":
                messages.info(request, f"Votre demande de mise en public pour '{req.plasmid_name}' a été APPROUVÉE par l’administrateur.")
            elif req.status == "rejected":
                messages.warning(request, f"Votre demande de mise en public pour '{req.plasmid_name}' a été REFUSÉE par l’administrateur.")
            req.notified = True
            req.save()

    # ---- Traitement de l'upload ----
    if request.method == 'POST':
        plasmid_file = request.FILES.get('plasmid_file')
        is_public = request.POST.get('is_public') == 'on'
        dossier_nom = "public" if is_public else (request.user.username if request.user.is_authenticated else "private")

        if not plasmid_file:
            messages.error(request, "Aucun fichier n’a été sélectionné.")
            return redirect('templates:view_plasmid')

        if not plasmid_file.name.lower().endswith('.gb'):
            messages.error(request, "Le fichier doit être au format .gb (GenBank).")
            return redirect('templates:view_plasmid')

        # Sauvegarde temporaire
        upload_subdir = "temp_uploads/genbank_files"
        upload_dir = os.path.join(settings.MEDIA_ROOT, upload_subdir)
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, plasmid_file.name)
        with open(file_path, 'wb+') as destination:
            for chunk in plasmid_file.chunks():
                destination.write(chunk)

        try:
            # Création ou récupération du plasmide
            plasmide = Plasmide.create_from_genbank(file_path, dossier_nom=dossier_nom)
            if request.user.is_authenticated:
                plasmide.user = request.user
                plasmide.save()

            # Génération des cartes
            linear_map, circular_map = generate_plasmid_maps(file_path)

            # Message de succès
            msg = f"Fichier '{plasmid_file.name}' traité avec succès."
            if plasmide.dossier == "public":
                # Créer une PublicationRequest si le plasmide doit être public
                if request.user.is_authenticated:
                    PublicationRequest.objects.create(
                        plasmid_name=plasmide.name,
                        requested_by=request.user,
                        campaign=None,  # upload individuel
                        status="pending"
                    )
                    msg += " Une demande de mise publique a été envoyée à l’administrateur."
            messages.success(request, msg)

            # Redirection vers la page de visualisation des cartes
            return redirect('templates:plasmid_detail', plasmid_id=plasmide.id)

        except Exception as e:
            messages.error(request, f"Erreur lors du traitement du plasmide : {e}")
            return redirect('templates:view_plasmid')

    # GET : page d’upload
    return render(request, 'gestionTemplates/view_plasmid.html')


def plasmid_detail(request, plasmid_id):
    plasmide = get_object_or_404(Plasmide, id=plasmid_id)
    file_path = os.path.join(settings.MEDIA_ROOT, "temp_uploads/genbank_files", f"{plasmide.name}.gb")

    # Génération des cartes
    linear_url, circular_url = generate_plasmid_maps(file_path)

    return render(request, 'gestionTemplates/plasmid_detail.html', {
        'plasmide': plasmide,
        'linear_map': linear_url,
        'circular_map': circular_url
    })


def user_view_plasmid(request, campaign_id):
    campaign = get_object_or_404(Campaign, id=campaign_id)
    plasmid_name = request.GET.get('plasmid', None)
    plasmid_maps = []  # liste des tuples (nom, linear_url, circular_url)
    files_in_zip = []  # liste des fichiers dans le zip (hors .gb)

    if campaign.result_file:
        zip_path = campaign.result_file.path
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                # filtrer les .gb et enlever les dossiers
                gb_files = [
                    f for f in zip_ref.namelist()
                    if f.lower().endswith('.gb')
                ]
                #Tous les fichiers dans le zip, sauf les .gb
                #Enlever le /output/ du début
                files_in_zip = [
                    f for f in zip_ref.namelist()
                    if not f.lower().endswith('.gb')
                ]
                for i in range(len(files_in_zip)):
                    if files_in_zip[i].startswith('output/'):
                        files_in_zip[i] = files_in_zip[i][7:]
                if plasmid_name:
                    # Filtrer pour ne garder que le plasmide demandé
                    gb_files = [f for f in gb_files if os.path.basename(f).replace('.gb', '') == plasmid_name]

                for f in gb_files:
                    # extraire le fichier dans un dossier temporaire
                    temp_dir = os.path.join("temp_uploads", "gb_temp")
                    os.makedirs(temp_dir, exist_ok=True)
                    extracted_path = zip_ref.extract(f, path=temp_dir)

                    # générer les cartes
                    linear_url, circular_url = generate_plasmid_maps(extracted_path)
                    # récupérer juste le nom du plasmide pour l'affichage
                    plasmid_name = os.path.basename(f).replace('.gb', '')
                    plasmid_maps.append((plasmid_name, linear_url, circular_url))

        except zipfile.BadZipFile:
            plasmid_maps = []

    return render(request, 'gestionTemplates/user_view_plasmid.html', {
        'campaign': campaign,
        'plasmid_maps': plasmid_maps,
        'files': files_in_zip
    })


def campaign_digestion(request, campaign_id):
    """Page HTML affichant le Western Blot, la PCR et les dilutions si présentes dans le zip."""
    campaign = get_object_or_404(Campaign, id=campaign_id)

    # Vérifier qu'une enzyme a été sélectionnée lors de la simulation
    if not campaign.enzyme:
        return render(request, 'gestionTemplates/digestion.html', {
            'campaign': campaign,
            'error': "Aucune enzyme sélectionnée lors de la simulation."
        })

    if not campaign.result_file:
        return render(request, 'gestionTemplates/digestion.html', {
            'campaign': campaign,
            'error': "Aucun fichier de résultats disponible pour cette simulation."
        })

    try:
        images = []
        dilutions = {}
        # temporary buckets for ordering
        global_dig = []
        global_pcr = []
        per_dig = []
        per_pcr = []
        other_images = []

        with zipfile.ZipFile(campaign.result_file.path, 'r') as z:
            for f in z.namelist():
                name = os.path.basename(f)
                lower = name.lower()

                # Images categorization
                if lower.endswith(('.png', '.jpg', '.jpeg', '.gif')):
                    if 'digestion' in lower:
                        # Global digestion.png preferred first
                        if os.path.basename(f).lower() == 'digestion.png':
                            global_dig.append((f, name))
                        else:
                            per_dig.append((f, name))
                    elif 'pcr' in lower:
                        if os.path.basename(f).lower() == 'pcr.png':
                            global_pcr.append((f, name))
                        else:
                            per_pcr.append((f, name))
                    else:
                        other_images.append((f, name))

                # Dilution JSON files
                if lower.endswith('.json') and 'dilution' in lower:
                    # Determine type key
                    if '10x' in lower:
                        key = '10x'
                        pretty = 'Dilution 10x'
                    elif 'direct' in lower or 'direct' in name.lower():
                        key = 'direct'
                        pretty = 'Dilution Direct'
                    else:
                        key = 'other'
                        pretty = name

                    try:
                        raw = z.read(f)
                        data = json.loads(raw.decode('utf-8'))
                        # compute columns (ordered)
                        cols = set()
                        for r in data:
                            cols.update(r.keys())
                        # prefer an order: plasmid_id, h2o_volume, buffer, then others
                        ordered = []
                        for pref in ('plasmid_id', 'h2o_volume', 'buffer'):
                            if pref in cols:
                                ordered.append(pref)
                                cols.remove(pref)
                        ordered.extend(sorted(cols))

                        download_url = reverse('templates:campaign_dilution_download', args=[campaign.id]) + f'?type={key}'

                        dilutions[key] = {
                            'label': pretty,
                            'data': data,
                            'columns': ordered,
                            'download_url': download_url,
                        }
                    except Exception:
                        # ignore malformed JSON for now
                        continue

        # Build ordered images list: global digestion, global pcr, per-plasmid digestion, per-plasmid pcr, then others
        def mkitem(tup, kind_hint=None):
            f, name = tup
            lower = name.lower()
            if 'digestion' in lower:
                label = 'Western Blot' if kind_hint is None else kind_hint
            elif 'pcr' in lower:
                label = 'PCR'
            else:
                label = name
            url = reverse('templates:campaign_digestion_image', args=[campaign.id]) + '?file=' + quote(f)
            return {'label': label, 'url': url, 'filename': name}

        images.extend([mkitem(x) for x in global_dig])
        images.extend([mkitem(x) for x in global_pcr])
        images.extend([mkitem(x, kind_hint='Western Blot') for x in per_dig])
        images.extend([mkitem(x) for x in per_pcr])
        images.extend([mkitem(x) for x in other_images])

        if not images and not dilutions:
            return render(request, 'gestionTemplates/digestion.html', {
                'campaign': campaign,
                'error': "Aucune image ou dilution pertinente trouvée dans les résultats."
            })

        # Prepare a JSON dump for client-side charts
        dilutions_json = {k: v['data'] for k, v in dilutions.items()}

        return render(request, 'gestionTemplates/digestion.html', {
            'campaign': campaign,
            'images': images,
            'dilutions': dilutions,
            'dilutions_json': json.dumps(dilutions_json),
        })

    except zipfile.BadZipFile:
        return render(request, 'gestionTemplates/digestion.html', {
            'campaign': campaign,
            'error': "Fichier de résultats corrompu."
        })


def campaign_digestion_image(request, campaign_id):
    """Retourne l'image depuis l'archive de résultats. Reçoit un paramètre GET 'file' (encodé)."""
    campaign = get_object_or_404(Campaign, id=campaign_id)

    if not campaign.result_file:
        raise Http404

    file_param = request.GET.get('file')
    if not file_param:
        raise Http404

    file_in_zip = unquote(file_param)

    try:
        with zipfile.ZipFile(campaign.result_file.path, 'r') as z:
            namelist = z.namelist()

            # Accepter soit le chemin interne, soit seulement le basename
            if file_in_zip not in namelist:
                matches = [f for f in namelist if os.path.basename(f).lower() == os.path.basename(file_in_zip).lower()]
                if matches:
                    file_in_zip = matches[0]
                else:
                    raise Http404

            data = z.read(file_in_zip)
            ext = os.path.splitext(file_in_zip)[1].lower()
            if ext == '.png':
                ctype = 'image/png'
            elif ext in ('.jpg', '.jpeg'):
                ctype = 'image/jpeg'
            elif ext == '.gif':
                ctype = 'image/gif'
            else:
                ctype = 'application/octet-stream'

            response = HttpResponse(data, content_type=ctype)
            if request.GET.get('download') == '1':
                response['Content-Disposition'] = f'attachment; filename="{os.path.basename(file_in_zip)}"'
            return response
    except zipfile.BadZipFile:
        raise Http404


def campaign_dilution_download(request, campaign_id):
    """Retourne un CSV généré à partir du fichier dilution (type=10x|direct|other) présent dans le zip de résultats."""
    campaign = get_object_or_404(Campaign, id=campaign_id)

    if not campaign.result_file:
        raise Http404

    dtype = request.GET.get('type')
    if not dtype:
        raise Http404

    try:
        with zipfile.ZipFile(campaign.result_file.path, 'r') as z:
            matches = []
            for f in z.namelist():
                name = os.path.basename(f).lower()
                if 'dilution' in name:
                    if dtype == '10x' and '10x' in name:
                        matches.append(f)
                    elif dtype == 'direct' and 'direct' in name:
                        matches.append(f)
                    elif dtype == 'other' and '10x' not in name and 'direct' not in name:
                        matches.append(f)

            if not matches:
                raise Http404

            # Pick first match
            target = matches[0]
            raw = z.read(target)
            data = json.loads(raw.decode('utf-8'))

            # Build CSV
            fieldnames = set()
            for row in data:
                fieldnames.update(row.keys())
            # keep stable order
            ordered = []
            for pref in ('plasmid_id', 'h2o_volume', 'buffer'):
                if pref in fieldnames:
                    ordered.append(pref)
                    fieldnames.remove(pref)
            ordered.extend(sorted(fieldnames))

            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=ordered)
            writer.writeheader()
            for row in data:
                writer.writerow({k: row.get(k, '') for k in ordered})

            resp = HttpResponse(output.getvalue(), content_type='text/csv')
            resp['Content-Disposition'] = f'attachment; filename="{os.path.basename(target)}.csv"'
            return resp
    except zipfile.BadZipFile:
        raise Http404


def plasmid_search(request):

    privacy = request.GET.get('privacy', '')
    query_name = request.GET.get('name', '').lower().strip()
    query_organism = request.GET.get('organism', '').lower().strip()
    query_seq = request.GET.get('sequence', '').upper().strip()
    query_site = request.GET.get('site', '').lower().strip()
    filter_type = request.GET.get('filter', 'public')  # 'public' ou 'mine'

    context = {}

    # -------------------------------
    # Cas 1 : recherche Entrez (NCBI)
    # -------------------------------
    if privacy == "search_enter":
        name = request.GET.get('name', '').strip()
        organism = request.GET.get('organism', '').strip()
        plasmid_type = request.GET.get('type', '').strip()
        binding_site = request.GET.get('site', '').strip()
        sequence = request.GET.get('sequence', '').strip()

        if any([name, organism, plasmid_type, binding_site, sequence]):
            terms = []
            if name:
                terms.append(f"{name}[Title]")
            if organism:
                terms.append(f"{organism}[Organism]")
            if plasmid_type:
                terms.append(f"{plasmid_type}[All Fields]")
            if binding_site:
                terms.append(f"{binding_site}[All Fields]")
            if sequence:
                terms.append(f"{sequence}[Sequence]")

            entrez_query = "+AND+".join(terms)
            url = f"https://www.ncbi.nlm.nih.gov/nuccore/?term={entrez_query}"
            return redirect(url)

        return render(request, 'gestionTemplates/plasmid_search.html', context)

    # -------------------------------
    # Cas 2 : recherche privée
    # -------------------------------
    elif privacy == "private" and request.user.is_authenticated:
        campaigns = Campaign.objects.filter(user=request.user).order_by('-created_at')
        campaigns_with_plasmids = []

        # Précharger tous les noms publics pour optimisation
        public_names = set(Plasmide.objects.filter(dossier="public").values_list('name', flat=True))

        for camp in campaigns:
            plasmids_in_archive = []
            plasmids_in_results = []

            # Fonction utilitaire pour filtrer par critères
            def match_criteria(p):
                if query_name and query_name not in p["name"].lower():
                    return False
                if query_organism and query_organism not in p["organism"].lower():
                    return False
                if query_seq and query_seq not in p.get("sequence", ""):
                    return False
                if query_site:
                    if not any(query_site in s.lower() for s in p.get("sites", [])):
                        return False
                return True

            # Fonction pour extraire plasmides depuis un zip
            def extract_plasmids_from_zip(zip_path):
                results = []
                try:
                    with zipfile.ZipFile(zip_path, 'r') as zf:
                        for f in zf.namelist():
                            if f.lower().endswith(('.gb', '.gbk')):
                                try:
                                    with zf.open(f) as gb_file:
                                        text_stream = TextIOWrapper(gb_file, encoding='utf-8')
                                        for record in SeqIO.parse(text_stream, "genbank"):
                                            p = {
                                                "name": record.name,
                                                "organism": record.annotations.get("organism", ""),
                                                "length": len(record.seq),
                                                "sequence": str(record.seq),
                                                "sites": [feat.qualifiers.get("gene",[None])[0] for feat in record.features if "gene" in feat.qualifiers]
                                            }
                                            if match_criteria(p):
                                                p["is_public"] = p["name"] in public_names
                                                results.append(p)
                                except Exception as e:
                                    results.append({"name": f"{f} (Erreur parsing: {e})"})
                except Exception as e:
                    results.append({"name": f"Erreur lecture archive : {e}"})
                return results

            if camp.plasmid_archive:
                plasmids_in_archive = extract_plasmids_from_zip(camp.plasmid_archive.path)
            if camp.result_file:
                plasmids_in_results = extract_plasmids_from_zip(camp.result_file.path)

            campaigns_with_plasmids.append({
                'campaign': camp,
                'plasmids_archive': plasmids_in_archive,
                'plasmids_results': plasmids_in_results
            })

        context['campaigns_with_plasmids'] = campaigns_with_plasmids

        # -------------------------------
        # Banque publique pour l'onglet privé
        # -------------------------------
        public_plasmids_qs = Plasmide.objects.all()
        if query_name:
            public_plasmids_qs = public_plasmids_qs.filter(name__icontains=query_name)
        if query_organism:
            public_plasmids_qs = public_plasmids_qs.filter(organism__icontains=query_organism)
        if query_seq:
            public_plasmids_qs = public_plasmids_qs.filter(sequence__icontains=query_seq)
        if query_site:
            public_plasmids_qs = public_plasmids_qs.filter(features__icontains=query_site)

        # Transformer features en labels affichables
        public_plasmids = []
        for p in public_plasmids_qs:
            display_features = []
            raw_features = getattr(p, 'features', None)

            # Cas dict ou liste ou autre
            lines = []
            if isinstance(raw_features, dict) and 'raw' in raw_features:
                lines = str(raw_features['raw']).splitlines()
            elif isinstance(raw_features, list):
                for f in raw_features:
                    if isinstance(f, dict) and 'raw' in f:
                        lines.extend(str(f['raw']).splitlines())
                    elif isinstance(f, str):
                        lines.extend(f.splitlines())
            # else on ignore None ou autre type

            for line in lines:
                line = line.strip()
                if line.startswith('/label='):
                    display_features.append(line.replace('/label=', '').strip())
                elif line.startswith('/allele='):
                    display_features.append(line.replace('/allele=', '').strip())

            p.display_features = ", ".join(display_features[:5])
            public_plasmids.append(p)

        context['public_plasmids'] = public_plasmids
        context['filter_type'] = filter_type

        # -------------------------------
        # Collections personnelles
        # -------------------------------
        my_collections_qs = PlasmidCollection.objects.filter(user=request.user).order_by('-created_at')
        collections_with_plasmids = []

        def extract_plasmids_from_zip(zip_path):
            results = []
            try:
                with zipfile.ZipFile(zip_path, 'r') as zf:
                    for f in zf.namelist():
                        if f.lower().endswith(('.gb', '.gbk')):
                            try:
                                with zf.open(f) as gb_file:
                                    text_stream = TextIOWrapper(gb_file, encoding='utf-8')
                                    for record in SeqIO.parse(text_stream, "genbank"):
                                        # On prend le nom du fichier pour éviter "exported"
                                        name = f.split('/')[-1].rsplit('.', 1)[0]  
                                        results.append({
                                            "name": name,
                                            "organism": record.annotations.get("organism", ""),
                                            "length": len(record.seq)
                                        })
                            except Exception as e:
                                results.append({"name": f"{f} (Erreur parsing: {e})"})
            except Exception as e:
                results.append({"name": f"Erreur lecture archive : {e}"})
            return results

        for c in my_collections_qs:
            plasmids = []
            if c.plasmid_archive:
                plasmids = extract_plasmids_from_zip(c.plasmid_archive.path)
            collections_with_plasmids.append({
                "collection": c,
                "plasmids": plasmids
            })

        context['my_collections'] = collections_with_plasmids


        # -------------------------------
        # Collections des équipes (groupées par équipe)
        # -------------------------------
        teams = request.user.equipes_membres.all()
        team_collections_qs = Seqcollection.objects.filter(equipe__in=teams).order_by('equipe__name', '-created_at')

        query_name = request.GET.get('name', '').strip()
        if query_name:
            team_collections_qs = team_collections_qs.filter(name__icontains=query_name)

        # Fonction pour extraire plasmides depuis un ZIP
        def extract_plasmids_from_zip(zip_path):
            results = []
            try:
                with zipfile.ZipFile(zip_path, 'r') as zf:
                    for f in zf.namelist():
                        if f.lower().endswith(('.gb', '.gbk')):
                            try:
                                with zf.open(f) as gb_file:
                                    text_stream = TextIOWrapper(gb_file, encoding='utf-8')
                                    for record in SeqIO.parse(text_stream, "genbank"):
                                        name = f.split('/')[-1].rsplit('.', 1)[0]  # vrai nom de fichier
                                        results.append({
                                            "name": name,
                                            "organism": record.annotations.get("organism", ""),
                                            "length": len(record.seq)
                                        })
                            except Exception as e:
                                results.append({"name": f"{f} (Erreur parsing: {e})"})
            except Exception as e:
                results.append({"name": f"Erreur lecture archive : {e}"})
            return results

        # Grouper par équipe
        from collections import defaultdict
        team_groups = defaultdict(list)

        for c in team_collections_qs:
            plasmids = []
            if c.fichier:
                plasmids = extract_plasmids_from_zip(c.fichier.path)
            team_groups[c.equipe].append({
                "collection": c,
                "plasmids": plasmids
            })

        context['team_collections_grouped'] = dict(team_groups)

    # -------------------------------
    # Cas 3 : recherche publique
    # -------------------------------
    elif privacy == "public" or (privacy == "private" and filter_type == "public"):
        plasmides_qs = Plasmide.objects.all()
        if query_name:
            plasmides_qs = plasmides_qs.filter(name__icontains=query_name)
        if query_organism:
            plasmides_qs = plasmides_qs.filter(organism__icontains=query_organism)
        if query_seq:
            plasmides_qs = plasmides_qs.filter(sequence__icontains=query_seq)
        if query_site:
            plasmides_qs = plasmides_qs.filter(features__icontains=query_site)

        public_plasmids = []
        for p in plasmides_qs:
            display_features = []
            raw_features = getattr(p, 'features', None)
            lines = []
            if isinstance(raw_features, dict) and 'raw' in raw_features:
                lines = str(raw_features['raw']).splitlines()
            elif isinstance(raw_features, list):
                for f in raw_features:
                    if isinstance(f, dict) and 'raw' in f:
                        lines.extend(str(f['raw']).splitlines())
                    elif isinstance(f, str):
                        lines.extend(f.splitlines())
            for line in lines:
                line = line.strip()
                if line.startswith('/label='):
                    display_features.append(line.replace('/label=', '').strip())
                elif line.startswith('/allele='):
                    display_features.append(line.replace('/allele=', '').strip())
            p.display_features = ", ".join(display_features[:5])
            public_plasmids.append(p)

        context['public_plasmids'] = public_plasmids

    else:
        context['campaigns_with_plasmids'] = []

    return render(request, 'gestionTemplates/plasmid_search.html', context)


def search_public_templates(request):
    query = request.GET.get('q', '')
    templates = CampaignTemplate.objects.filter(name__icontains=query, isPublic=True)

    if "HX-Request" in request.headers:
        return render(request, 'gestionTemplates/partials/results_list.html', {'templates': templates})
    
    return render(request, 'gestionTemplates/search_main_page.html', {'templates': templates})


def import_public_templates(request, template_id):

    original = get_object_or_404(CampaignTemplate, id=template_id)

    old_columns = list(original.columns.all())

    original.id = None
    original.pk = None
    original.isPublic = False

    original.user = request.user
    original.name = "Copie de " + original.name

    original.save()

    for col in old_columns:
        col.pk = None
        col.id = None
        col.template = original  # On lie la copie de la colonne au nouveau template
        col.save()

    liste_templates = CampaignTemplate.objects.filter(user=request.user).order_by('-created_at')

    context = {
        'liste_templates': liste_templates,
    }
    messages.success(request, f"Template '{original.name}' importé avec succès dans vos templates privés.")

    return render(request, 'gestionTemplates/dashboard.html', context)


def publier_template(request, template_id):
    # Only accept POST to mutate data
    if request.method != 'POST':
        return redirect('templates:dashboard')

    # Ensure the user owns the template
    original = get_object_or_404(CampaignTemplate, id=template_id, user=request.user)

    # Create a public copy so the user's private template remains unchanged
    old_columns = list(original.columns.all())

    public = CampaignTemplate()
    public.id = None
    public.pk = None
    public.name = original.name
    public.description = original.description
    public.restriction_enzyme = original.restriction_enzyme
    public.separator_sortie = original.separator_sortie
    public.isPublic = True
    public.user = None
    public.uploaded_by = request.user
    public.team = None
    public.save()

    for col in old_columns:
        col.pk = None
        col.id = None
        col.template = public
        col.save()

    messages.success(request, f"Template '{original.name}' publié avec succès.")
    return redirect('templates:dashboard')


def user_view_plasmid_archive(request, campaign_id):
    campaign = get_object_or_404(Campaign, id=campaign_id)
    plasmid_name = request.GET.get('plasmid', None)
    plasmid_maps = []  # liste des tuples (nom, linear_url, circular_url)
    files_in_zip = []  # liste des fichiers dans le zip (hors .gb)

    if campaign.plasmid_archive:
        zip_path = campaign.plasmid_archive.path
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                # filtrer les .gb et enlever les dossiers
                gb_files = [
                    f for f in zip_ref.namelist()
                    if f.lower().endswith('.gb')
                ]
                if plasmid_name:
                    # Filtrer pour ne garder que le plasmide demandé
                    gb_files = [f for f in gb_files if os.path.basename(f).replace('.gb', '') == plasmid_name]

                for f in gb_files:
                    # extraire le fichier dans un dossier temporaire
                    temp_dir = os.path.join("temp_uploads", "gb_temp")
                    os.makedirs(temp_dir, exist_ok=True)
                    extracted_path = zip_ref.extract(f, path=temp_dir)

                    # générer les cartes
                    linear_url, circular_url = generate_plasmid_maps(extracted_path)
                    # récupérer juste le nom du plasmide pour l'affichage
                    plasmid_name = os.path.basename(f).replace('.gb', '')
                    plasmid_maps.append((plasmid_name, linear_url, circular_url))

        except zipfile.BadZipFile:
            plasmid_maps = []

    return render(request, 'gestionTemplates/user_view_plasmid_archive.html', {
        'campaign': campaign,
        'plasmid_maps': plasmid_maps,
        'files': files_in_zip
    })


def make_public(request):
    if request.method == "POST" and request.user.is_authenticated:
        campaign_id = request.POST.get("campaign_id")
        plasmid_name = request.POST.get("plasmid_name")

        campaign = get_object_or_404(Campaign, id=campaign_id)

        # Fonction pour traiter un zip et créer le plasmide
        def process_zip(zip_path):
            try:
                with zipfile.ZipFile(zip_path, "r") as zf:
                    gb_file_name = None
                    for f in zf.namelist():
                        if f.lower().endswith(('.gb', '.gbk')) and plasmid_name.lower() in f.lower():
                            gb_file_name = f
                            break

                    if not gb_file_name:
                        return None, "Fichier GenBank non trouvé."

                    with zf.open(gb_file_name) as gb_file:
                        text_stream = TextIOWrapper(gb_file, encoding='utf-8')
                        record = SeqIO.read(text_stream, "genbank")
                        return record, None
            except Exception as e:
                return None, f"Erreur lors de l'import : {e}"

        record, error_msg = None, None
        if campaign.plasmid_archive:
            record, error_msg = process_zip(campaign.plasmid_archive.path)
        if not record and campaign.result_file:
            record, error_msg = process_zip(campaign.result_file.path)

        if not record:
            messages.error(request, error_msg or "Plasmide non trouvé.")
            return redirect(request.META.get("HTTP_REFERER"))

        # ---- Créer ou mettre à jour le plasmide public ----
        plasmide, created = Plasmide.objects.update_or_create(
            name=record.name,
            defaults={
                "dossier": "public",
                "organism": record.annotations.get("organism", ""),
                "length": len(record.seq),
                "sequence": str(record.seq),
                "features": {"raw": [f.qualifiers for f in record.features]}
            }
        )

        # ---- Créer une PublicationRequest si nécessaire ----
        PublicationRequest.objects.create(
            plasmid_name=plasmide.name,
            requested_by=campaign.user if campaign.user else None,
            campaign=campaign,
            status="approved",   # puisque c’est l’admin qui valide directement
            reviewed_by=request.user,
            reviewed_at=timezone.now(),
            notified=False       # l’utilisateur sera notifié sur view_plasmid
        )

        messages.success(request, f"Plasmide '{plasmide.name}' rendu public et PublicationRequest créée.")
        return redirect(request.META.get("HTTP_REFERER"))

    messages.error(request, "Action non autorisée.")
    return redirect("plasmid_search")


def make_public_bulk(request):
    if request.method != "POST" or not request.user.is_authenticated:
        messages.error(request, "Action non autorisée.")
        return redirect("plasmid_search")

    campaign_id = request.POST.get("campaign_id")
    campaign = get_object_or_404(Campaign, id=campaign_id)

    def process_zip(zip_path):
        created_count = 0
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                for f in zf.namelist():
                    if f.lower().endswith(('.gb', '.gbk')):
                        with zf.open(f) as gb_file:
                            text_stream = TextIOWrapper(gb_file, encoding='utf-8')
                            record = SeqIO.read(text_stream, "genbank")

                            if Plasmide.objects.filter(name=record.name, dossier="public").exists():
                                continue

                            plasmide = Plasmide.objects.create(
                                name=record.name,
                                dossier="public",
                                organism=record.annotations.get("organism", ""),
                                length=len(record.seq),
                                sequence=str(record.seq),
                                features={"raw": [f.qualifiers for f in record.features]}
                            )

                            # ---- Création PublicationRequest ----
                            PublicationRequest.objects.create(
                                plasmid_name=plasmide.name,
                                requested_by=campaign.user if campaign.user else None,
                                campaign=campaign,
                                status="approved",
                                reviewed_by=request.user,
                                reviewed_at=timezone.now(),
                                notified=False
                            )

                            created_count += 1
        except Exception as e:
            messages.error(request, f"Erreur lors de l'import depuis {zip_path} : {e}")
        return created_count

    total_created = 0
    if campaign.plasmid_archive:
        total_created += process_zip(campaign.plasmid_archive.path)
    if campaign.result_file:
        total_created += process_zip(campaign.result_file.path)

    if total_created > 0:
        messages.success(request, f"{total_created} plasmide(s) rendus publics et PublicationRequests créées.")
    else:
        messages.info(request, "Aucun plasmide nouveau à rendre public.")

    return redirect(request.META.get("HTTP_REFERER"))


def download_plasmid(request):
    plasmid_name = request.GET.get("plasmid_name")
    campaign_id = request.GET.get("campaign_id")
    plasmid_id = request.GET.get("plasmid_id")  # pour plasmides publics

    if plasmid_id:  # téléchargement d'un plasmide public
        plasmid = get_object_or_404(Plasmide, id=plasmid_id)
        response = HttpResponse(plasmid.sequence, content_type='text/plain')
        response['Content-Disposition'] = f'attachment; filename={plasmid.name}.gb'
        return response

    elif campaign_id and plasmid_name:  # téléchargement d'un plasmide privé
        campaign = get_object_or_404(Campaign, id=campaign_id, user=request.user)
        if not campaign.plasmid_archive:
            raise Http404("Aucune archive trouvée pour cette campagne.")

        # Chercher le plasmide dans le zip
        with zipfile.ZipFile(campaign.plasmid_archive.path, 'r') as zf:
            gb_file_name = None
            for f in zf.namelist():
                if f.lower().endswith(('.gb', '.gbk')) and plasmid_name.lower() in f.lower():
                    gb_file_name = f
                    break
            if not gb_file_name:
                raise Http404("Plasmide non trouvé dans l'archive.")

            with zf.open(gb_file_name) as gb_file:
                text_stream = TextIOWrapper(gb_file, encoding='utf-8')
                content = text_stream.read()

        response = HttpResponse(content, content_type='text/plain')
        response['Content-Disposition'] = f'attachment; filename={plasmid_name}.gb'
        return response

    else:
        raise Http404("Paramètres manquants pour le téléchargement.")


def download_my_collection(request, collection_id):
    collection = get_object_or_404(Seqcollection, id=collection_id, uploaded_by=request.user)
    try:
        file_handle = collection.fichier.open()
        response = FileResponse(file_handle, as_attachment=True)
        filename = collection.fichier.name.split('/')[-1]
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    except (FileNotFoundError, ValueError):
        raise Http404("Le fichier est introuvable sur le serveur.")


def download_single_plasmid(request, collection_id, plasmid_name):
    try:
        collection = Seqcollection.objects.get(id=collection_id)
    except Seqcollection.DoesNotExist:
        raise Http404("Collection non trouvée")

    if not collection.fichier:
        raise Http404("Pas de fichier ZIP associé à cette collection")

    # Ouvrir le ZIP et chercher le plasmide demandé
    zip_path = collection.fichier.path
    with zipfile.ZipFile(zip_path, 'r') as zf:
        matched_file = None
        for f in zf.namelist():
            if f.lower().endswith(('.gb', '.gbk')) and plasmid_name.lower() in f.lower():
                matched_file = f
                break

        if not matched_file:
            raise Http404("Plasmide non trouvé dans le ZIP")

        # Lire le fichier et le renvoyer
        with zf.open(matched_file) as file_data:
            data = file_data.read()
            response = HttpResponse(data, content_type='application/octet-stream')
            response['Content-Disposition'] = f'attachment; filename="{os.path.basename(matched_file)}"'
            return response


def ct_search(request):
    # Récupérer le filtre depuis les paramètres GET
    filter_type = request.GET.get('filter', 'public')  # public par défaut

    # Tables publiques
    public_tables = MappingTemplate.objects.filter(is_public=True)

    # Mes tables
    if request.user.is_authenticated:
        my_tables = MappingTemplate.objects.filter(user=request.user)
    else:
        my_tables = MappingTemplate.objects.none()

    return render(request, 'gestionTemplates/ct_search.html', {
        'public_tables': public_tables,
        'my_tables': my_tables,
        'filter_type': filter_type  # <- important !
    })


def ct_search(request):
    filter_type = request.GET.get('filter', 'public')  # public par défaut

    # Tables publiques
    public_tables = MappingTemplate.objects.filter(is_public=True)

    # Mes tables
    if request.user.is_authenticated:
        my_tables = MappingTemplate.objects.filter(user=request.user)
    else:
        my_tables = MappingTemplate.objects.none()

    # Préparer le contenu de toutes les tables pour affichage
    def get_table_data(tables):
        all_tables = []
        for table in tables:
            try:
                file_path = table.mapping_file.path
                if file_path.lower().endswith('.csv'):
                    df = pd.read_csv(file_path, sep = ';')
                else:
                    df = pd.read_excel(file_path)
                table_content = df.values.tolist()   # liste de listes
                table_columns = df.columns.tolist()  # liste de colonnes
            except Exception:
                table_content = []
                table_columns = []
            all_tables.append({
                "id": table.id,
                "name": table.name,
                "description": table.description,
                "columns": table_columns,
                "content": table_content,
            })
        return all_tables

    public_tables_data = get_table_data(public_tables)
    my_tables_data = get_table_data(my_tables)

    return render(request, 'gestionTemplates/ct_search.html', {
        'public_tables': public_tables_data,
        'my_tables': my_tables_data,
        'filter_type': filter_type,
    })


def download_ct(request, table_id):
    table = get_object_or_404(MappingTemplate, pk=table_id)
    response = FileResponse(open(table.mapping_file.path, 'rb'))
    response['Content-Disposition'] = f'attachment; filename="{table.name}{table.mapping_file.name[-5:]}"'
    return response


def search(request):
    # Placeholder : tu peux ajouter la logique de recherche plus tard
    return render(request, 'gestionTemplates/search.html')


def request_table_public(request):
    if request.method == "POST" and request.user.is_authenticated:
        table_id = request.POST.get("table_id")
        table = get_object_or_404(MappingTemplate, id=table_id)

        # Vérifier que l'utilisateur est le propriétaire
        if table.user != request.user:
            messages.error(request, "Action non autorisée.")
            return redirect(request.META.get("HTTP_REFERER"))

        # Vérifier qu'il n'existe pas déjà une demande en attente pour cette table
        existing_request = PublicationRequest.objects.filter(
            table=table, status='pending'
        ).first()
        if existing_request:
            messages.info(request, "Une demande de mise publique est déjà en attente pour cette table.")
            return redirect(request.META.get("HTTP_REFERER"))

        # Créer la demande
        PublicationRequest.objects.create(
            table=table,
            requested_by=request.user,
            status="pending"
        )

        messages.success(request, f"Demande de mise publique envoyée pour la table '{table.name}'.")
        return redirect(request.META.get("HTTP_REFERER"))

    messages.error(request, "Action non autorisée.")
    return redirect("ct_search")


def template_search(request):
    filter_type = request.GET.get('filter', 'public')  # public par défaut

    # Templates publics
    public_templates = CampaignTemplate.objects.filter(isPublic=True)

    # Mes templates
    if request.user.is_authenticated:
        my_templates = CampaignTemplate.objects.filter(user=request.user)
    else:
        my_templates = CampaignTemplate.objects.none()

    # Préparer le contenu des fichiers pour affichage
    def get_template_data(templates):
        all_templates = []
        for template in templates:
            try:
                if template.template_file:
                    file_path = template.template_file.path
                    if file_path.lower().endswith('.csv'):
                        df = pd.read_csv(file_path, sep=';')
                    else:
                        df = pd.read_excel(file_path)
                    content = df.values.tolist()   # liste de listes
                    columns = df.columns.tolist()  # liste de colonnes
                else:
                    content, columns = [], []
            except Exception:
                content, columns = [], []
            all_templates.append({
                "id": template.id,
                "name": template.name,
                "description": template.description,
                "user": template.user,
                "created_at": template.created_at,
                "template_file": template.template_file,
                "columns": columns,
                "content": content
            })
        return all_templates

    public_templates_data = get_template_data(public_templates)
    my_templates_data = get_template_data(my_templates)

    return render(request, 'gestionTemplates/template_search.html', {
        'public_templates': public_templates_data,
        'my_templates': my_templates_data,
        'filter_type': filter_type,
    })

def request_table_public(request):
    if request.method == "POST" and request.user.is_authenticated:
        table_id = request.POST.get("table_id")
        table = get_object_or_404(MappingTemplate, id=table_id)

        # Vérifier que l'utilisateur est le propriétaire
        if table.user != request.user:
            messages.error(request, "Action non autorisée.")
            return redirect(request.META.get("HTTP_REFERER"))

        # Vérifier qu'il n'existe pas déjà une demande en attente pour cette table
        existing_request = PublicationRequest.objects.filter(
            table=table,
            status="pending"
        ).first()
        if existing_request:
            messages.info(request, "Une demande de mise publique est déjà en attente pour cette table.")
            return redirect(request.META.get("HTTP_REFERER"))

        # Créer la demande
        PublicationRequest.objects.create(
            table=table,
            requested_by=request.user,
            status="pending"
        )

        messages.success(request, f"Demande de mise publique envoyée pour la table '{table.name}'.")
        return redirect(request.META.get("HTTP_REFERER"))

    messages.error(request, "Action non autorisée.")
    return redirect("template_search")
