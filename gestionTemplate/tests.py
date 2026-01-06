from django.test import TestCase
from gestionTemplate.models import Template, Plasmid

#Test 1: Vérifier que les plasmides en .gb sont dans la template associée
class PlasmidTemplateTestCase(TestCase):
    def test_plasmids_in_template(self):
        # Récupérer toutes les templates
        templates = Template.objects.all()
        for template in templates:
            # Récupérer les plasmides associés à la template
            plasmids = template.plasmids.all()
            for plasmid in plasmids:
                # Vérifier que le fichier .gb existe pour chaque plasmide
                self.assertTrue(plasmid.gb_file.exists(), f"Le plasmide {plasmid.name} n'a pas de fichier .gb associé dans la template {template.name}")

