from django import forms
from .models import CampaignTemplate


class CampaignTemplateForm(forms.ModelForm):
    class Meta:
        model = CampaignTemplate
        # On ne demande que ces 3 champs à l'utilisateur
        fields = ['name', 'description', 'file']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'file': forms.FileInput(attrs={'class': 'form-control'}),
        }

    def clean_file(self):
        file = self.cleaned_data['file']
        if not file.name.endswith('.xlsx'):
            raise forms.ValidationError("Le fichier doit être au format Excel (.xlsx)")
        return file
