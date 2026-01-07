from django.shortcuts import render, redirect, get_object_or_404
from django.http import FileResponse
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.core.files.base import ContentFile
from .models import CampaignTemplate
from .forms import CampaignTemplateForm, AnonymousSimulationForm

import pandas as pd
import uuid
import os
import pathlib
import zipfile
import tarfile
import io

# insillyclo
import insillyclo.data_source
import insillyclo.observer
import insillyclo.simulator


# Dashboard : Lister TOUS les templates (public)
def dashboard(request):
    templates = CampaignTemplate.objects.all().order_by('-created_at')
    return render(request, 'gestionTemplates/dashboard.html', {'templates': templates})


def create_template(request):
    if request.method == 'POST':
        # 1 Récupérer les paramètres globaux
        name = request.POST.get('campaign_name')
        description = request.POST.get('description')
        enzyme = request.POST.get('enzyme')
        output_separator = request.POST.get('output_separator', '-')

        # 2 Récupérer les listes (Les colonnes définies par l'utilisateur)
        part_names = request.POST.getlist('part_names[]')
        part_types = request.POST.getlist('part_types[]')
        is_optional = request.POST.getlist('is_optional[]')
        in_output_name = request.POST.getlist('in_output_name[]')
        part_separators = request.POST.getlist('part_separators[]')

        try:
            # 3 Générer le fichier Excel en mémoire
            excel_content = generate_structural_template(
                enzyme, name, output_separator,
                part_names, part_types, is_optional, in_output_name, part_separators
            )

            # 4 Sauvegarder dans la BDD (Modèle CampaignTemplate)
            # création de l'objet
            new_campaign = CampaignTemplate(
                name=name,
                description=description
            )
            # On attache le fichier généré
            filename = f"Template_{name.replace(' ', '_')}.xlsx"
            new_campaign.file.save(filename, ContentFile(excel_content))
            new_campaign.save()

            return redirect('templates:dashboard')

        except Exception as e:
            return render(request, 'gestionTemplates/create_edit.html', {
                'error': f"Erreur lors de la création : {e}"
            })

    return render(request, 'gestionTemplates/create_edit.html')


def generate_structural_template(enzyme, name, out_sep, p_names, p_types, p_opt, p_in_name, p_seps):
    """
    Génère un fichier Excel VIDE de données mais avec la STRUCTURE complète.
    """
    output = io.BytesIO()

    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        worksheet = writer.book.add_worksheet('Sheet1')
        writer.sheets['Sheet1'] = worksheet

        # --- BLOC 1 : SETTINGS (Lignes 1 à 8) ---
        worksheet.write(0, 0, 'Assembly settings')

        # Structure clé/valeur simple
        settings = [
            ('Restriction enzyme', enzyme),
            ('Name', name),
            ('Output separator', out_sep),
            ('', ''),  # Lignes vides pour espacer
            ('', ''),
            ('', ''),
            ('', '')
        ]

        for i, (key, val) in enumerate(settings):
            worksheet.write(i+1, 0, key)
            worksheet.write(i+1, 1, val)

        # --- BLOC 2 : COMPOSITION HEADER (Lignes 9 à 13) ---
        start_row = 9

        # Colonne A : Les étiquettes des lignes de métadonnées
        metadata_labels = [
            'Assembly composition',           # Ligne 9
            '',                               # Ligne 10 (Vide en A, label en B)
            '',                               # Ligne 11
            '',                               # Ligne 12
            '',                               # Ligne 13
            'Output plasmid id ↓'             # Ligne 14 (Header data)
        ]
        for i, label in enumerate(metadata_labels):
            worksheet.write(start_row + i, 0, label)

        # Colonne B : Les types de métadonnées
        param_labels = [
            'Part name ->',                   # Ligne 9
            'Part types ->',                  # Ligne 10
            'Is optional part ->',            # Ligne 11
            'Part name should be in output name ->',  # Ligne 12
            'Part separator ->',              # Ligne 13
            'OutputType (optional) ↓'         # Ligne 14
        ]
        for i, label in enumerate(param_labels):
            worksheet.write(start_row + i, 1, label)

        # Colonnes C à fin: Les valeurs définies par l'utilisateur
        # On boucle sur chaque colonne définie dans le formulaire
        for col_idx, p_name in enumerate(p_names):
            # Commence à la colonne C
            excel_col = 2 + col_idx

            # Ligne 9 : Noms
            worksheet.write(start_row, excel_col, p_name)

            # Ligne 10 : Types (ex: 1, 2, 3...)
            val_type = p_types[col_idx] if col_idx < len(p_types) else ""
            worksheet.write(start_row + 1, excel_col, val_type)

            # Ligne 11 : Optional (True/False)
            val_opt = p_opt[col_idx] if col_idx < len(p_opt) else "False"
            worksheet.write(start_row + 2, excel_col, val_opt)

            # Ligne 12 : In Name (True/False)
            val_in_name = p_in_name[col_idx] if col_idx < len(p_in_name) else "True"
            worksheet.write(start_row + 3, excel_col, val_in_name)

            # Ligne 13 : Separator
            val_sep = p_seps[col_idx] if col_idx < len(p_seps) else ""
            worksheet.write(start_row + 4, excel_col, val_sep)

            # Ligne 14 : Le Header de la table de données
            worksheet.write(start_row + 5, excel_col, p_name)

    output.seek(0)
    return output.read()


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


def simulate_anonymous(request):
    # Chemins par défaut du serveur
    SERVER_DATA_DIR = pathlib.Path(settings.BASE_DIR) / 'data_science'
    DEFAULT_PRIMERS = SERVER_DATA_DIR / 'DB_primer.csv'
    DEFAULT_CONC_FILE = SERVER_DATA_DIR / 'input-plasmid-concentrations_updated.csv'

    if request.method == 'POST':
        form = AnonymousSimulationForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                # 1 SETUP SANDBOX (Dossier temporaire unique)
                unique_id = str(uuid.uuid4())
                BASE_MEDIA = pathlib.Path(settings.MEDIA_ROOT)
                SANDBOX_DIR = BASE_MEDIA / 'temp_uploads' / unique_id

                # Création des dossiers
                PLASMIDS_DIR = SANDBOX_DIR / 'plasmids'
                OUTPUT_DIR = SANDBOX_DIR / 'output'
                PLASMIDS_DIR.mkdir(parents=True, exist_ok=True)
                OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

                fs = FileSystemStorage(location=SANDBOX_DIR)

                # 2 GESTION DES FICHIERS REQUIS
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

                # 3 GESTION DES FICHIERS OPTIONNELS (Logique : User > Server)

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

                # 4 LANCEMENT DE LA SIMULATION
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

                # 5 PACKAGING ET RETOUR
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


# Fonction utilitaire création zipfile
def make_zipfile(source_dir, output_filename):
    with zipfile.ZipFile(output_filename, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(source_dir):
            for file in files:
                zipf.write(os.path.join(root, file), 
                           os.path.relpath(os.path.join(root, file),
                           os.path.join(source_dir, '..')))
