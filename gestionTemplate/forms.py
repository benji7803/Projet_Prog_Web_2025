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


class AnonymousSimulationForm(forms.Form):
    # --- SECTION OBLIGATOIRE (Minima) ---
    template_file = forms.FileField(
        label="1. Fichier Template (.xlsx) *",
        help_text="Le fichier Excel définissant la campagne (requis).",
        required=True
    )
    plasmids_zip = forms.FileField(
        label="2. Archive des plasmides (.zip) *",
        help_text="Archive contenant tous les fichiers .gb (requis).",
        required=True
    )
    mapping_file = forms.FileField(
        label="3. Correspondance Noms <-> ID (.csv) *",
        help_text="Fichier CSV (iP_mapping) (requis).",
        required=True
    )

    # --- SECTION OPTIONNELLE ---

    primers_file = forms.FileField(
        label="4. Fichier des amorces (.csv)",
        help_text="Optionnel. Si vide, utilise la base de données du serveur.",
        required=False
    )

    concentration_file = forms.FileField(
        label="5. Concentrations des plasmides (.csv)",
        help_text="Optionnel. Si vide, utilise les valeurs par défaut.",
        required=False
    )

    default_concentration = forms.FloatField(
        label="Concentration par défaut (ng/µL)",
        initial=200.0,
        min_value=0.1,
        help_text="Valeur utilisée si un plasmide n'est pas dans le fichier de concentration.",
        required=False
    )

    enzyme = forms.ChoiceField(
        label="Enzyme de restriction",
        choices=[('BsaI', 'BsaI'), ('BsmBI', 'BsmBI'), ('BbsI', 'BbsI')],
        initial='BsaI',
        help_text="L'enzyme utilisée pour la digestion.",
        required=True
    )

    primer_pairs = forms.CharField(
        label="Paires d'amorces (IDs)",
        initial="P29,P30",
        help_text="IDs des amorces à tester, séparés par une virgule (ex: P29,P30).",
        required=False
    )
