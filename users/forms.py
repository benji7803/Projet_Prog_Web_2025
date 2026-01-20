from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model
from django import forms
from .models import Equipe

User = get_user_model()

class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ("username", "email", "first_name", "last_name")

class EquipeForm(forms.ModelForm):
    class Meta:
        model = Equipe
        fields = ['name']

class InviteMemberForm(forms.Form):
    email = forms.EmailField(label="Email de l'utilisateur")