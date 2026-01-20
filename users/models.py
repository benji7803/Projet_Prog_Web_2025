from django.db import models
from django.contrib.auth.models import AbstractUser

class Equipe(models.Model):
    name = models.CharField(max_length=100)
    leader = models.ForeignKey(
        'UserModel',
        on_delete=models.CASCADE, 
        related_name='equipes_dirigees'
    )

    def __str__(self):
        return f"{self.nom} (Chef: {self.leader.email})"

# Create your models here.
class UserModel(AbstractUser):
    email = models.EmailField('email address', unique=True, max_length=254)
    first_name = models.CharField('first name', max_length=150)
    last_name = models.CharField('last name', max_length=150)
    equipes = models.ManyToManyField(Equipe, related_name='membres', blank=True)
    isAdministrator = models.BooleanField(default=False)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']  # ou ajuster selon besoin

    def __str__(self):
        return self.email



