from django.shortcuts import render, redirect, get_object_or_404
from django.http import FileResponse
from .models import CampaignTemplate
from .forms import CampaignTemplateForm
import pandas as pd
import zipfile
import tarfile

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
