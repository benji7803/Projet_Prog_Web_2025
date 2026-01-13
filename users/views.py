from django.shortcuts import render, redirect
from django.contrib.auth.forms import AuthenticationForm
from .forms import CustomUserCreationForm, EquipeForm
from django.contrib.auth import login, logout
from django.views.decorators.http import require_POST

# Create your views here.

def register_view(request):
    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            login(request, form.save())
            return redirect("templates:dashboard")
    else:
        form = CustomUserCreationForm()
    return render(request, 'users/register.html', {"form": form})

def login_view(request):
    if request.method == "POST":
        form = AuthenticationForm(data = request.POST)
        if form.is_valid():
            login(request, form.get_user())
            if "next" in request.POST:
                return redirect(request.POST.get("next"))
            else:
                return redirect("templates:dashboard")
    else:
        form = AuthenticationForm()
    return render(request, 'users/login.html', {"form": form})

@require_POST
def logout_view(request):
    logout(request)
    return redirect("templates:dashboard")

def user_profile(request):
    teams = request.user.equipes.all()
    return render(request, 'users/profile.html', {
        'teams': teams
    })

def create_team(request):
    if request.method == 'POST':
        form = EquipeForm(request.POST)
        if form.is_valid():
            equipe = form.save(commit=False)
            equipe.leader = request.user  # L'utilisateur est déclaré chef de l'équipe
            equipe.save()
            
            # On n'oublie pas d'ajouter le chef à la liste des membres
            request.user.equipes.add(equipe)
            
            return redirect('users:profile') # Redirection vers le profil
    else:
        form = EquipeForm()
    
    return render(request, 'users/create_team.html', {'form': form})


