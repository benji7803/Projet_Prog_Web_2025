from django.shortcuts import render, redirect, get_object_or_404
from django.http import FileResponse
from .models import CampaignTemplate
from .forms import CampaignTemplateForm
import pandas as pd


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

    if request.method == "POST":
        uploaded_file = request.FILES.get('uploaded_file')

        if not uploaded_file:
            message = "Veuillez sélectionner un fichier."
        else:
            extension = uploaded_file.name.split('.')[-1].lower()
            if extension not in ['xlsx']:
                message = "Ce format n'est pas autorisé."
            else:
                try:
                    df = pd.read_excel(uploaded_file)
                    data_html = df.to_html(classes='table table-striped', index=False)
                    message = "Fichier soumis avec succès."
                except Exception as e:
                    message = f"Erreur lors de la lecture du fichier : {e}"
                    data_html = None

    return render(request, "gestionTemplates/submit.html", {
        "data_html": data_html,
        "message": message
    })
