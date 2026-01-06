from django.shortcuts import render, redirect, get_object_or_404
from django.http import FileResponse
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from .models import CampaignTemplate
from .forms import CampaignTemplateForm, AnonymousSimulationForm

import pandas as pd
import uuid
import os
import pathlib
import zipfile
import tarfile

# insillyclo
import insillyclo.data_source
import insillyclo.observer
import insillyclo.simulator


# Dashboard : Lister TOUS les templates (public)
def dashboard(request):
    templates = CampaignTemplate.objects.all().order_by('-created_at')
    return render(request, 'gestionTemplates/dashboard.html', {'templates': templates})


# Création simple
def create_template(request):
    if request.method == 'POST':
        form = CampaignTemplateForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('/template/dashboard')
    else:
        form = CampaignTemplateForm()

    return render(request, 'gestionTemplates/create_edit.html', {'form': form})


# Modification
def edit_template(request, template_id):
    campaign = get_object_or_404(CampaignTemplate, id=template_id)

    if request.method == 'POST':
        form = CampaignTemplateForm(request.POST, request.FILES, instance=campaign)
        if form.is_valid():
            form.save()
            return redirect('dashboard')
    else:
        form = CampaignTemplateForm(instance=campaign)

    return render(request, 'gestionTemplates/create_edit.html', {'form': form, 'action': 'Modifier'})


# Téléchargement
def download_template(request, template_id):
    campaign = get_object_or_404(CampaignTemplate, id=template_id)
    return FileResponse(campaign.file.open(), as_attachment=True, filename=campaign.filename())


def submit(request):
    data_html = None
    message = None
    inputs_name = []
    file_names = []

    if request.method == "POST":
        uploaded_file = request.FILES.get('uploaded_file')
        plasmid_archive = request.FILES.get('plasmid_archive')

        # 1. Gestion du fichier Excel
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

        # 2. Gestion de l'archive 
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


def simulate_anonymous(request):
    # Chemins par défaut du serveur
    SERVER_DATA_DIR = pathlib.Path(settings.BASE_DIR) / 'data_science'
    DEFAULT_PRIMERS = SERVER_DATA_DIR / 'DB_primer.csv'
    DEFAULT_CONC_FILE = SERVER_DATA_DIR / 'input-plasmid-concentrations_updated.csv'

    if request.method == 'POST':
        form = AnonymousSimulationForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                # 1. SETUP SANDBOX (Dossier temporaire unique)
                unique_id = str(uuid.uuid4())
                BASE_MEDIA = pathlib.Path(settings.MEDIA_ROOT)
                SANDBOX_DIR = BASE_MEDIA / 'temp_uploads' / unique_id

                # Création des dossiers
                PLASMIDS_DIR = SANDBOX_DIR / 'plasmids'
                OUTPUT_DIR = SANDBOX_DIR / 'output'
                PLASMIDS_DIR.mkdir(parents=True, exist_ok=True)
                OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

                fs = FileSystemStorage(location=SANDBOX_DIR)

                # 2  GESTION DES FICHIERS REQUIS
                # Template
                f_template = request.FILES['template_file']
                path_template = pathlib.Path(fs.save("campaign.xlsx", f_template))
                full_template_path = SANDBOX_DIR / path_template

                # Mapping
                f_mapping = request.FILES['mapping_file']
                path_mapping = pathlib.Path(fs.save("mapping.csv", f_mapping))
                full_mapping_path = SANDBOX_DIR / path_mapping

                # Zip Plasmides (Extraction immédiate)
                f_zip = request.FILES['plasmids_zip']
                path_zip = pathlib.Path(fs.save("plasmids.zip", f_zip))
                with zipfile.ZipFile(SANDBOX_DIR / path_zip, 'r') as zip_ref:
                    zip_ref.extractall(PLASMIDS_DIR)

                # 3  GESTION DES FICHIERS OPTIONNELS (Logique : User > Server)

                # A Primers
                if form.cleaned_data['primers_file']:
                    f_primers = form.cleaned_data['primers_file']
                    path_primers = pathlib.Path(fs.save("primers.csv", f_primers))
                    final_primers_path = SANDBOX_DIR / path_primers
                else:
                    final_primers_path = DEFAULT_PRIMERS

                # B Concentrations
                if form.cleaned_data['concentration_file']:
                    f_conc = form.cleaned_data['concentration_file']
                    path_conc = pathlib.Path(fs.save("concentrations.csv", f_conc))
                    final_conc_path = SANDBOX_DIR / path_conc
                else:
                    final_conc_path = DEFAULT_CONC_FILE

                # C Paramètres scalaires
                enzyme_choice = form.cleaned_data['enzyme']
                default_conc_val = form.cleaned_data['default_concentration'] or 200.0

                # D Paires d'amorces (Parsing du texte "P29,P30")
                raw_pairs = form.cleaned_data['primer_pairs']
                primer_pairs_list = []
                if raw_pairs:
                    # On transforme "P29,P30" en [('P29', 'P30')]
                    # Note: pour faire simple on suppose une seule paire pour l'instant
                    # ou on splitte simplement si insillyclo attend une liste de tuples
                    parts = [p.strip() for p in raw_pairs.split(',')]
                    if len(parts) >= 2:
                        primer_pairs_list = [(parts[0], parts[1])]
                    else:
                        primer_pairs_list = [] # Pas de paire valide

                # 4. LANCEMENT DE LA SIMULATION
                observer = insillyclo.observer.InSillyCloCliObserver(debug=False, fail_on_error=True)

                insillyclo.simulator.compute_all(
                    observer=observer,
                    settings=None,

                    # Entrées obligatoires
                    input_template_filled=full_template_path,
                    input_parts_files=[full_mapping_path],
                    gb_plasmids=PLASMIDS_DIR.glob('**/*.gb'), # Récursif dans le zip extrait

                    output_dir=OUTPUT_DIR,
                    data_source=insillyclo.data_source.DataSourceHardCodedImplementation(),

                    # Entrées dynamiques (User ou Default)
                    primers_file=final_primers_path,
                    concentration_file=final_conc_path,

                    # Paramètres
                    enzyme_names=[enzyme_choice],
                    primer_id_pairs=primer_pairs_list,
                    default_mass_concentration=default_conc_val,
                )

                # 5. PACKAGING ET RETOUR
                if not os.listdir(OUTPUT_DIR):
                    raise Exception("La simulation n'a produit aucun fichier. Vérifiez vos fichiers d'entrée.")

                final_zip_name = f"resultats_anonymes_{unique_id}.zip"
                final_zip_path = SANDBOX_DIR / final_zip_name

                make_zipfile(str(OUTPUT_DIR), str(final_zip_path))

                return FileResponse(open(final_zip_path, 'rb'), as_attachment=True, filename=final_zip_name)

            except Exception as e:
                # En cas d'erreur, on renvoie le formulaire rempli avec l'erreur
                return render(request, 'gestionTemplates/anonymous_sim.html', {
                    'form': form, 
                    'error': f"Erreur de simulation : {str(e)}"
                })
    else:
        form = AnonymousSimulationForm()

    return render(request, 'gestionTemplates/anonymous_sim.html', {'form': form})


# Fonction utilitaire
def make_zipfile(source_dir, output_filename):
    with zipfile.ZipFile(output_filename, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(source_dir):
            for file in files:
                zipf.write(os.path.join(root, file), 
                           os.path.relpath(os.path.join(root, file),
                           os.path.join(source_dir, '..')))
