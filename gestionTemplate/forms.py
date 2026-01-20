from django import forms
from .models import CampaignTemplate, ColumnTemplate


# Création de templates
class ColumnForm(forms.ModelForm):
    class Meta:
        model = ColumnTemplate
        fields = ['part_names', 'part_types', 'is_optional', 'in_output_name', 'part_separators']
        widgets = {
            'part_names': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nom'}),
            'part_types': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Type'}),
            'part_separators': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '.'}),
            'is_optional': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'in_output_name': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class CampaignTemplateForm(forms.ModelForm):
    class Meta:
        model = CampaignTemplate
        fields = ['name', 'restriction_enzyme', 'separator_sortie', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'restriction_enzyme': forms.Select(attrs={'class': 'form-select'}),
            'separator_sortie': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }





# Formulaire pour la simulation anonyme
class AnonymousSimulationForm(forms.Form):
    # --- CHAMPS REQUIS ---
    template_file = forms.FileField(label="Fichier de Campagne (.xlsx) *", required=True)
    plasmids_zip = forms.FileField(label="Archive des plasmides (.zip) *", required=True)
    mapping_file = forms.FileField(label="Correspondance Noms <-> ID (.csv) *", required=True)

    # --- CHAMPS OPTIONNELS (FICHIERS) ---

    # Amorces
    primers_file = forms.FileField(
        label="Fichier des amorces (.csv)",
        required=False,
        help_text="Si vide, aucune PCR ne sera simulée."
    )

    # Concentrations
    concentration_file = forms.FileField(
        label="Concentrations spécifiques (.csv)",
        required=False,
        help_text="Optionnel. Permet de spécifier une concentration différente pour certains plasmides."
    )

    # --- PARAMÈTRES SCALAIRES ---
    enzyme = forms.ChoiceField(
        label="Enzyme de restriction",
        choices=[('', '--- Aucune (None) ---'), ('BsaI', 'BsaI'), ('BsmBI', 'BsmBI'), ('BbsI', 'BbsI')],
        required=False,
        help_text="Si non spécifiée, le paramètre sera None."
    )

    default_concentration = forms.FloatField(
        label="Concentration par défaut (ng/µL)",
        required=False,
        min_value=0.0,
        help_text="Si vide, la valeur sera forcée à 200."
    )

    primer_pairs = forms.CharField(
        label="Paires d'amorces (IDs)",
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'P29,P30'}),
        help_text="IDs séparés par une virgule. Si vide, paramètre à None."
    )
