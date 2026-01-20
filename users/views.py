from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.forms import AuthenticationForm
from .forms import CustomUserCreationForm, EquipeForm, InviteMemberForm
from django.contrib.auth import login, logout
from django.views.decorators.http import require_POST
from django.contrib import messages
from .models import Equipe, UserModel, MembreEquipe


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
    teams = request.user.equipes_membres.all()
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
            equipe.membres.add(request.user)
            
            return redirect('users:profile') # Redirection vers le profil
    else:
        form = EquipeForm()
    
    return render(request, 'users/create_team.html', {'form': form})

def team_detail(request, team_id):
    team = get_object_or_404(Equipe, id=team_id)  
    liens_membres = team.membreequipe_set.all().select_related('user')

    return render(request, 'users/team_detail.html', {
        'team': team,
        'lien_membres': liens_membres
    })

def invite_member(request, team_id):
    team = get_object_or_404(Equipe, id=team_id)

    if request.method == 'POST':
        form = InviteMemberForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            try:
                user_to_invite = UserModel.objects.get(email=email)
                
                # Vérifier si l'utilisateur est déjà dans l'équipe
                if team.membres.filter(id=user_to_invite.id).exists():
                    messages.warning(request, "Cet utilisateur est déjà membre.")
                else:
                    team.membres.add(user_to_invite)
                    messages.success(request, f"{user_to_invite.email} a été ajouté.")
                    
            except UserModel.DoesNotExist:
                messages.error(request, "Aucun utilisateur trouvé avec cet email.")
                
    return redirect('users:team_detail', team_id=team.id)

def remove_member(request, team_id, user_id):
    team = get_object_or_404(Equipe, id=team_id)
    MembreEquipe.objects.filter(equipe=team, user_id=user_id).delete()
    return redirect('users:team_detail', team_id=team.id)

def promote_member(request, team_id, user_id):
    team = get_object_or_404(Equipe, id=team_id)
    if team.leader.id != int(user_id):
            team.leader_id = user_id
            team.save()
    return redirect('users:team_detail', team_id=team.id)

def delete_team(request, team_id):
    team = get_object_or_404(Equipe, id=team_id)
    if team.leader == request.user:
        team.delete()
        
    return redirect('users:profile') # Retour au profil après suppression

def administration_view(request):

    liste_user = UserModel.objects.all()

    return render(request, 'users/administration.html', {"liste_utilisateur": liste_user})
