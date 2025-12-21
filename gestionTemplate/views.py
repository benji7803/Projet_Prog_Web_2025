from django.shortcuts import render

# Create your views here.


def create(request):
    return render(request, 'gestionTemplates/create.html')


def submit(request):
    return render(request, "gestionTemplates/submit.html")
