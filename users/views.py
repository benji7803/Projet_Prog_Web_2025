from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.forms import AuthenticationForm
from .forms import CustomUserCreationForm, EquipeForm, InviteMemberForm
from django.contrib.auth import login, logout
from django.views.decorators.http import require_POST
from django.contrib import messages
from .models import Equipe, UserModel, MembreEquipe, Tablecor, Seqcollection
from django.http import FileResponse, Http404


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
    from gestionTemplate.models import PlasmidCollection, MappingTemplate
    
    teams = request.user.equipes_membres.all()
    plasmid_collections = PlasmidCollection.objects.filter(user=request.user).order_by('-created_at')
    mapping_templates = MappingTemplate.objects.filter(user=request.user).order_by('-created_at')
    
    return render(request, 'users/profile.html', {
        'teams': teams,
        'plasmid_collections': plasmid_collections,
        'mapping_templates': mapping_templates,
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
    liste_table = team.tablecor.all()
    liste_seqcol = team.seqcol.all()

    return render(request, 'users/team_detail.html', {
        'team': team,
        'lien_membres': liens_membres,
        'list_table' : liste_table,
        'list_seqcol' : liste_seqcol
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
    return redirect('users:profile')

def add_table(request, team_id):
    team = get_object_or_404(Equipe, id=team_id)
    if request.method == "POST":
        uploaded_table = request.FILES.get('uploaded_table')
        
        if uploaded_table:
            Tablecor.objects.create(
                name = uploaded_table.name,
                equipe = team,
                fichier = uploaded_table
            )
            return redirect('users:team_detail', team_id=team.id)
    return redirect('users:team_detail', team_id=team.id)

def remove_table(request, team_id, table_id):
    team = get_object_or_404(Equipe, id=team_id)
    table = get_object_or_404(Tablecor, id=table_id)
    if request.method == "POST":
        table.fichier.delete(save=False)
        table.delete()

    return redirect('users:team_detail', team_id=team_id)

def download_table(request,team_id, table_id):
    table = get_object_or_404(Tablecor, id=table_id)
    team = get_object_or_404(Equipe, id=team_id)
    try:
        file_handle = table.fichier.open()
        response = FileResponse(file_handle, as_attachment=True)
        filename = table.fichier.name.split('/')[-1]
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response
    except (FileNotFoundError, ValueError):
        raise Http404("Le fichier est introuvable sur le serveur.")

def add_seqcol(request, team_id):
    team = get_object_or_404(Equipe, id=team_id)
    if request.method == "POST":
        uploaded_seqcol = request.FILES.get('uploaded_seqcol')
        if uploaded_seqcol:
            Seqcollection.objects.create(
                name = uploaded_seqcol.name,
                equipe = team,
                fichier = uploaded_seqcol
            )
            return redirect('users:team_detail', team_id=team.id)
    return redirect('users:team_detail', team_id=team.id)

def remove_seqcol(request, team_id, seqcol_id):
    team = get_object_or_404(Equipe, id=team_id)
    seqcol = get_object_or_404(Seqcollection, id=seqcol_id)
    if request.method == "POST":
        seqcol.fichier.delete(save=False)
        seqcol.delete()

    return redirect('users:team_detail', team_id=team_id)

def download_seqcol(request,team_id, seqcol_id):
    seqcol = get_object_or_404(Seqcollection, id=seqcol_id)
    team = get_object_or_404(Equipe, id=team_id)
    try:
        file_handle = seqcol.fichier.open()
        response = FileResponse(file_handle, as_attachment=True)
        filename = seqcol.fichier.name.split('/')[-1]
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response
    except (FileNotFoundError, ValueError):
        raise Http404("Le fichier est introuvable sur le serveur.")


def delete_plasmid_collection(request, collection_id):
    """Supprime une collection de plasmides"""
    from gestionTemplate.models import PlasmidCollection
    
    collection = get_object_or_404(PlasmidCollection, id=collection_id, user=request.user)
    collection.delete()
    messages.success(request, f"Collection '{collection.name}' supprimée avec succès.")
    return redirect('users:profile')


def delete_mapping_template(request, template_id):
    """Supprime un fichier de correspondance"""
    from gestionTemplate.models import MappingTemplate
    
    template = get_object_or_404(MappingTemplate, id=template_id, user=request.user)
    template.delete()
    messages.success(request, f"Fichier '{template.name}' supprimé avec succès.")
    return redirect('users:profile')



def administration_view(request):

    liste_user = UserModel.objects.all()

    return render(request, 'users/administration.html', {"liste_utilisateur": liste_user})
