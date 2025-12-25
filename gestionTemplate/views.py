from django.shortcuts import render, redirect
from django.contrib import messages
import pandas as pd

# Create your views here.


def create(request):
    return render(request, 'gestionTemplates/create.html')


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