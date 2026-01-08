from django.db import models
from django.contrib.auth.models import AbstractUser

# Create your models here.
class UserModel(AbstractUser):
    email = models.EmailField('email address', unique=True, max_length=254)
    first_name = models.CharField('first name', max_length=150)
    last_name = models.CharField('last name', max_length=150)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']  # ou ajuster selon besoin

    def __str__(self):
        return self.email

