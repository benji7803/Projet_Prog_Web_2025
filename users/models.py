from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.db import transaction

class Equipe(models.Model):
    name = models.CharField(max_length=100)
    leader = models.ForeignKey(
        'UserModel',
        on_delete=models.CASCADE, 
        related_name='equipes_dirigees'
    )
    membres = models.ManyToManyField(
        'UserModel',
        through='MembreEquipe',
        related_name='equipes_membres'
    )

    def __str__(self):
        return f"{self.name} (Chef: {self.leader.email})"
    
    def quitter_equipe(self, utilisateur): #Methode abandon d'équipe
        with transaction.atomic():
            # Verification de si l'utilisateur dans l'équipe 

            if not self.membres.filter(id=utilisateur.id).exists():
                return "L'utilisateur n'est pas dans cette équipe."

            if self.leader == utilisateur:
                autres_membres = self.membreequipe_set.exclude(user=utilisateur) #Les autres membres de l'équipe ordonnés par date de join

                if not autres_membres.exists(): #Equipe sans membres -> Suppression de l'Equipe
                    self.delete()
                
                #Autres membres -> Plus ancien = nouveau chef
                nouveau_leader = autres_membres.first().user
                self.leader = nouveau_leader
                self.save()

            # Suppression du membre
            self.membres.remove(utilisateur)
            return f"{utilisateur} a quitté l'équipe."
    
class MembreEquipe(models.Model):
    user = models.ForeignKey('UserModel', on_delete=models.CASCADE)
    equipe = models.ForeignKey(Equipe, on_delete=models.CASCADE)
    date_rejoint = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['date_rejoint']

class UserModel(AbstractUser):
    email = models.EmailField('email address', unique=True, max_length=254)
    first_name = models.CharField('first name', max_length=150)
    last_name = models.CharField('last name', max_length=150)
    equipes = models.ManyToManyField(Equipe, related_name='equipe', blank=True)
    isAdministrator = models.BooleanField(default=False)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']  # ou ajuster selon besoin

    def __str__(self):
        return self.email



