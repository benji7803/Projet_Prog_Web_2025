from django.shortcuts import render, redirect, get_object_or_404
from django.http import FileResponse
from django.conf import settings
from django.core.files import File
from django.core.files.storage import FileSystemStorage
from django.forms import inlineformset_factory
from django.core.files import File
from django.db import transaction

from .models import CampaignTemplate, Campaign, ColumnTemplate
from .forms import CampaignTemplateForm, AnonymousSimulationForm, ColumnForm
from .plasmid_mapping import generate_plasmid_maps

import pandas as pd
import uuid
import os
import pathlib
import zipfile
import tarfile
import shutil

# insillyclo
from insillyclo.template_generator import make_template
from insillyclo.data_source import DataSourceHardCodedImplementation
from insillyclo.observer import InSillyCloCliObserver
import insillyclo.data_source
import insillyclo.observer
import insillyclo.simulator


# Dashboard : Lister TOUS les templates (public)
def dashboard(request):
    if request.user.is_authenticated:
        liste_templates = CampaignTemplate.objects.filter(user=request.user).order_by('-created_at')
    else:
        liste_templates = CampaignTemplate.objects.filter(user=None).order_by('-created_at')

    context = {
        'liste_templates': liste_templates,
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
            return redirect('templates:dashboard')
        
    else:
        form = CampaignTemplateForm()
        formset = ColumnFormSet(instance=CampaignTemplate(), prefix='columns')

    return render(request, 'gestionTemplates/create.html', {"form": form, "formset": formset, "is_edit": False})


# Modification
def edit_template(request, template_id):
    
    campaign = get_object_or_404(CampaignTemplate, id=template_id)

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
        default_plasmid=["pID001"]  # Tu peux paramétrer ça aussi
    )
    
    # Envoyer le fichier au client
    response = FileResponse(open(output_path, 'rb'), as_attachment=True, filename=f"{template.name}.xlsx")
    
    # Nettoyage après envoi (optionnel)
    # Note: le fichier sera supprimé après, à gérer avec une tâche async si besoin
    return response


def submit(request):
    data_html = None
    message = None
    inputs_name = []
    file_names = []

    if request.method == "POST":
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
            except Exception as e:
                message = f"Erreur Excel : {e}"

        # 2 Gestion de l'archive
        if plasmid_archive:
            # AA partir des données stockées
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
        "file_names": file_names
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
                # CAS 1 : UTILISATEUR CONNECTÉ (Sauvegarde en BDD)
                # =========================================================
                if request.user.is_authenticated:
                    # A. Création de l'objet Campaign
                    campaign_instance = Campaign(
                        user=request.user,
                        name=f"Sim {unique_id[:8]}", 
                        status=Campaign.STATUS_RUNNING,
                        template_file=request.FILES['template_file'],
                        mapping_file=request.FILES['mapping_file'],
                        plasmid_archive=request.FILES['plasmids_zip'], # Attention au nom du champ form vs model
                        
                        # Options simples
                        enzyme=form.cleaned_data.get('enzyme'),
                        default_concentration=form.cleaned_data.get('default_concentration') or 200.0,
                    )

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
                    
                    # B. Gestion MANUELLE de l'archive ZIP sur le disque
                    uploaded_zip = request.FILES['plasmids_zip']
                    zip_path_on_disk = SANDBOX_DIR / "temp_plasmids.zip"
                    
                    with open(zip_path_on_disk, 'wb+') as destination:
                        for chunk in uploaded_zip.chunks():
                            destination.write(chunk)

                    # C. Extraction de l'archive
                    with zipfile.ZipFile(zip_path_on_disk, 'r') as zip_ref:
                        zip_ref.extractall(PLASMIDS_DIR)
                    
                    # D. Parsing et Création des objets Plasmide en BDD
                    # On parcourt tous les dossiers extraits pour trouver les .gb
                    for root, dirs, files in os.walk(PLASMIDS_DIR):
                        
                        # --- AJOUT : Calcul du nom du dossier ---
                        # On regarde le chemin relatif par rapport au dossier d'extraction
                        # Ex: si root est ".../plasmids/Niveau1/Promoteurs", rel_path sera "Niveau1/Promoteurs"
                        rel_path = os.path.relpath(root, PLASMIDS_DIR)
                        
                        # Si le fichier est à la racine, rel_path vaut "." -> on met None ou ""
                        current_dossier = rel_path if rel_path != "." else None
                        # ----------------------------------------

                        for file in files:
                            if file.lower().endswith('.gb') or file.lower().endswith('.gbk'):
                                full_file_path = os.path.join(root, file)
                                try:
                                    # --- MODIFICATION : On passe le dossier ---
                                    new_plasmid = Plasmide.create_from_genbank(
                                        full_file_path, 
                                        dossier_nom=current_dossier
                                    )
                                    
                                    new_plasmid.user = request.user
                                    new_plasmid.save()
                                    
                                    campaign_instance.plasmids.add(new_plasmid)
                                    
                                except Exception as e:
                                    print(f"Erreur import plasmide {file}: {e}")

                    # E. Définition des chemins pour le simulateur
                    full_template_path = pathlib.Path(campaign_instance.template_file.path)
                    full_mapping_path = pathlib.Path(campaign_instance.mapping_file.path)
                    
                    # Extraction de l'archive stockée
                    archive_path = pathlib.Path(campaign_instance.plasmid_archive.path)
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
                    # Ici, pour rester simple, on renvoie le fichier qui vient d'être sauvegardé
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
                    'previous_templates': Campaign.objects.filter(user=request.user).order_by('-created_at') if request.user.is_authenticated else None
                })
    else:
        form = AnonymousSimulationForm()
    
    context = {'form': form}
    if request.user.is_authenticated:
        context['previous_templates'] = Campaign.objects.filter(user=request.user).order_by('-created_at')

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
    campaign.delete()
    return redirect('templates:dashboard')

def view_plasmid(request):
    if request.method == 'POST':
        plasmid_file = request.FILES.get('plasmid_file')

        # Vérification du fichier envoyé
        if not plasmid_file:
            return render(request, 'gestionTemplates/view_plasmid.html', {
                'error': "⚠️ Aucun fichier n’a été sélectionné."
            })

        if not plasmid_file.name.lower().endswith('.gb'):
            return render(request, 'gestionTemplates/view_plasmid.html', {
                'error': "❌ Le fichier doit être au format .gb (GenBank)."
            })

        # --- Sauvegarde temporaire du fichier GenBank ---
        upload_subdir = "temp_uploads/genbank_files"
        upload_dir = os.path.join(settings.MEDIA_ROOT, upload_subdir)
        os.makedirs(upload_dir, exist_ok=True)

        file_path = os.path.join(upload_dir, plasmid_file.name)
        with open(file_path, 'wb+') as destination:
            for chunk in plasmid_file.chunks():
                destination.write(chunk)

        # --- Génération des cartes linéaire et circulaire ---
        linear_url, circular_url = generate_plasmid_maps(file_path)

        # Log pour debug
        print("→ Fichiers générés :", linear_url, circular_url)

        # --- Affichage dans le template ---
        return render(request, 'gestionTemplates/view_plasmid.html', {
            'message': f"Fichier '{plasmid_file.name}' traité avec succès ✅",
            'linear_map': linear_url,
            'circular_map': circular_url
        })

    # Si GET : juste la page d’upload
    return render(request, 'gestionTemplates/view_plasmid.html')

def user_view_plasmid(request, campaign_id):
    campaign = get_object_or_404(Campaign, id=campaign_id)
    plasmid_maps = []  # liste des tuples (nom, linear_url, circular_url)

    if campaign.result_file:
        zip_path = campaign.result_file.path
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                # filtrer les .gb et enlever les dossiers
                gb_files = [
                    f for f in zip_ref.namelist()
                    if f.lower().endswith('.gb')
                ]

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
        'plasmid_maps': plasmid_maps
    })
