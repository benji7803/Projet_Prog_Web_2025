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
    from gestionTemplate.models import PlasmidCollection, MappingTemplate, CampaignTemplate
    
    teams = request.user.equipes_membres.all()
    plasmid_collections = PlasmidCollection.objects.filter(user=request.user).order_by('-created_at')
    mapping_templates = MappingTemplate.objects.filter(user=request.user).order_by('-created_at')
    published_templates = CampaignTemplate.objects.filter(user=request.user, isPublic=True).order_by('-created_at')
    
    return render(request, 'users/profile.html', {
        'teams': teams,
        'plasmid_collections': plasmid_collections,
        'mapping_templates': mapping_templates,
        'published_templates': published_templates,
    })

#Gestion d'équipe --------------------------------------------------------------
def create_team(request):
    if request.method == 'POST':
        form = EquipeForm(request.POST)
        if form.is_valid():
            equipe = form.save(commit=False)
            equipe.leader = request.user
            equipe.save()
            equipe.membres.add(request.user)
            messages.success(request, f"L'équipe { equipe.name } a été créée avec succès")
            return redirect('users:profile')
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
        if team.leader == request.user:
            form = InviteMemberForm(request.POST)
            if form.is_valid():
                email = form.cleaned_data['email']
                try:
                    user_to_invite = UserModel.objects.get(email=email)
                    
                    if team.membres.filter(id=user_to_invite.id).exists():
                        messages.warning(request, "Cet utilisateur est déjà membre.")
                    else:
                        team.membres.add(user_to_invite)
                        messages.success(request, f"{user_to_invite.email} a été ajouté.")
                        
                except UserModel.DoesNotExist:
                    messages.error(request, "Aucun utilisateur trouvé avec cet email.")
        else:
            messages.error(request, "Seul le chef de l'équipe peut inviter des membres.")        
    return redirect('users:team_detail', team_id=team.id)

def remove_member(request, team_id, user_id):
    if team.leader == request.user:
        team = get_object_or_404(Equipe, id=team_id)
        membre_lien = get_object_or_404(MembreEquipe, equipe=team, user_id=user_id)
        messages.success(request, f"{membre_lien.user.get_full_name()} a été exclu de l'équipe")
        MembreEquipe.objects.filter(equipe=team, user_id=user_id).delete()
        return redirect('users:team_detail', team_id=team.id)
    else:
        messages.error(request, "Seul le chef de l'équipe peut exclure un membre.")
        return redirect('users:team_detail', team_id=team.id)

def promote_member(request, team_id, user_id):
    team = get_object_or_404(Equipe, id=team_id)
    membre_lien = get_object_or_404(MembreEquipe, equipe=team, user_id=user_id)
    if team.leader == request.user:
        if team.leader.id != int(user_id):
            team.leader_id = user_id
            team.save()
            messages.success(request, f"{membre_lien.user.get_full_name()} est le nouveau chef de l'équipe")
        else:
            messages.error(request, "Le chef de l'équipe ne peut pas se promouvoir lui-même.")
    else:
        messages.error(request, "Seul le chef de l'équipe peut promouvoir un membre.")
    return redirect('users:team_detail', team_id=team.id)

def delete_team(request, team_id):
    team = get_object_or_404(Equipe, id=team_id)
    if team.leader == request.user:
        messages.success(request, f"L'équipe {team.name} a été supprimée avec succès")
        team.delete()
    else:
        messages.error(request, "Seul le chef de l'équipe peut supprimer l'équipe.")
    return redirect('users:profile')

#Table de correspondances ----------------------------------------------------------------

def add_table(request, team_id):
    team = get_object_or_404(Equipe, id=team_id)
    if request.method == "POST":
        uploaded_table = request.FILES.get('uploaded_table')
        if uploaded_table:
            is_leader = (request.user == team.leader)
            Tablecor.objects.create(
                name = uploaded_table.name,
                equipe = team,
                fichier = uploaded_table,
                uploaded_by=request.user,
                is_validated=is_leader
            )
            if (is_leader) :
                messages.success(request, "Tableau ajouté pour l'équipe.")
            else :
                messages.success(request, "Tableau suggéré à la cheffe l'équipe.")
            return redirect('users:team_detail', team_id=team.id)
    return redirect('users:team_detail', team_id=team.id)

def remove_table(request, team_id, table_id):
    team = get_object_or_404(Equipe, id=team_id)
    table = get_object_or_404(Tablecor, id=table_id)
    if request.method == "POST":
        if request.user == team.leader:
            messages.success(request, f"La table { table.name } a été supprimée avec succès")
            table.fichier.delete(save=False)
            table.delete()
        else:
            messages.error(request, "Seul le chef de l'équipe peut supprimer un tableau.")
    return redirect('users:team_detail', team_id=team_id)

def download_table(request,team_id, table_id):
    table = get_object_or_404(Tablecor, id=table_id)
    try:
        file_handle = table.fichier.open()
        response = FileResponse(file_handle, as_attachment=True)
        filename = table.fichier.name.split('/')[-1]
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response
    except (FileNotFoundError, ValueError):
        raise Http404("Le fichier est introuvable sur le serveur.")

def validate_table(request, team_id, table_id):
    team = get_object_or_404(Equipe, id=team_id)
    if request.user == team.leader:
        table = get_object_or_404(Tablecor, id=table_id)
        table.is_validated = True
        table.save()
        messages.success(request, f"Le tableau {table.name} est désormais officiel.")
    else:
        messages.error(request, "Seul le chef de l'équipe peut valider un tableau.")
    return redirect('users:team_detail', team_id=team_id)

#Collection de plasmides-------------------------------------------------------------

def add_seqcol(request, team_id):
    team = get_object_or_404(Equipe, id=team_id)
    if request.method == "POST":
        uploaded_seqcol = request.FILES.get('uploaded_seqcol')
        if uploaded_seqcol:
            is_leader = (request.user == team.leader)
            Seqcollection.objects.create(
                name = uploaded_seqcol.name,
                equipe = team,
                fichier = uploaded_seqcol,
                uploaded_by=request.user,
                is_validated=is_leader
            )
            if (is_leader) :
                messages.success(request, "Collection de plasmides ajoutée pour l'équipe.")
            else :
                messages.success(request, "Collection de plasmides suggérée à la cheffe l'équipe.")
            return redirect('users:team_detail', team_id=team.id)
    return redirect('users:team_detail', team_id=team.id)

def remove_seqcol(request, team_id, seqcol_id):
    team = get_object_or_404(Equipe, id=team_id)
    seqcol = get_object_or_404(Seqcollection, id=seqcol_id)
    if request.method == "POST":
        if request.user == team.leader:
            messages.success(request, f"La collection { seqcol.name } a été supprimée avec succès")
            seqcol.fichier.delete(save=False)
            seqcol.delete()
        else:
            messages.error(request, "Seul le chef de l'équipe peut supprimer une collection de plasmides.")

    return redirect('users:team_detail', team_id=team_id)

def download_seqcol(request,team_id, seqcol_id):
    seqcol = get_object_or_404(Seqcollection, id=seqcol_id)
    try:
        file_handle = seqcol.fichier.open()
        response = FileResponse(file_handle, as_attachment=True)
        filename = seqcol.fichier.name.split('/')[-1]
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    except (FileNotFoundError, ValueError):
        raise Http404("Le fichier est introuvable sur le serveur.")
    
def validate_seqcol(request, team_id, seqcol_id):
    team = get_object_or_404(Equipe, id=team_id)
    if request.user == team.leader:
        seqcol = get_object_or_404(Seqcollection, id=seqcol_id)
        seqcol.is_validated = True
        seqcol.save()
        messages.success(request, f"La collection {seqcol.name} est désormais officiel.")
    else:
        messages.error(request, "Seul le chef de l'équipe peut valider une collection de plasmides.")
    return redirect('users:team_detail', team_id=team_id)

#-------------------------------------------------------------------------------------------------


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
