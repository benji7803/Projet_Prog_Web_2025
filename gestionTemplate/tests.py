from django.test import TestCase

import tempfile
import shutil
from pathlib import Path
from gestionTemplate.models import Plasmide, CampaignTemplate

import io
import zipfile
import os
from django.test import Client
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from unittest.mock import patch

class PlasmideGenbankTest(TestCase):
    def test_create_from_genbank_file(self):
        src = Path(r"data_web\\pMISC\\pCDE067.gb")
        assert src.exists(), "Fichier GenBank introuvable pour le test"
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.gb') as tmp:
            shutil.copyfile(src, tmp.name)
            tmp_path = tmp.name

        p = Plasmide.create_from_genbank(tmp_path)
        self.assertIsNotNone(p.id)
        self.assertTrue(p.name)
        self.assertIsInstance(p.length, int)
        self.assertTrue(len(p.sequence) >= p.length or p.length > 0)
        self.assertIsNotNone(p.gc_content)

    def test_plasmids_in_template(self):
        # Récupérer toutes les templates
        templates = CampaignTemplate.objects.all()
        for template in templates:
            # Récupérer les plasmides associés à la template
            plasmids = CampaignTemplate.plasmids.all()
            for plasmid in plasmids:
                # Vérifier que le fichier .gb existe pour chaque plasmide
                self.assertTrue(plasmid.gb_file.exists(), f"Le plasmide {plasmid.name} n'a pas de fichier .gb associé dans la template {template.name}")


# Test 2: Vérifier que la simulation fonctionne correctement
class SimulationSimpleTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = reverse('templates:simulate')

    # On "patch" la fonction compute_all pour ne pas lancer le vrai calcul scientifique
    @patch('insillyclo.simulator.compute_all')
    def test_simulation_simple_success(self, mock_compute):
        """
        Teste une simulation simple avec uniquement les 3 fichiers requis.
        """

        # --- 1 PRÉPARATION DES DONNÉES DE TEST ---

        # A Création d'un faux fichier Excel
        template_content = b"Fake Excel Content"
        template_file = SimpleUploadedFile("template.xlsx", template_content, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        # B Création d'un faux fichier Mapping CSV
        mapping_content = b"pID;Name\np001;PromoterX"
        mapping_file = SimpleUploadedFile("mapping.csv", mapping_content, content_type="text/csv")

        # C Création d'un VRAI fichier ZIP valide (contenant un faux fichier .gb)
        # La vue essaie de dézipper le fichier, donc il doit être structurellement valide.
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr('plasmid_1.gb', 'LOCUS       plasmid_1...')

        zip_file = SimpleUploadedFile("plasmids.zip", zip_buffer.getvalue(), content_type="application/zip")


        # --- 2 CONFIGURATION DU MOCK ---

        # Quand la vue va appeler compute_all, on veut que cette fonction fake s'exécute
        # Elle doit créer un fichier dans le dossier de sortie pour que la vue ne lève pas d'erreur "Aucun fichier produit"
        def side_effect_compute(*args, **kwargs):
            output_dir = kwargs.get('output_dir')
            # On simule la création d'un résultat
            with open(os.path.join(output_dir, 'resultat_fake.gb'), 'w') as f:
                f.write('Simulation reussie')

        mock_compute.side_effect = side_effect_compute


        # --- 3 EXÉCUTION DE LA REQUÊTE ---

        # On envoie seulement les champs REQUIS (pas de primers_file, pas de concentration_file)
        data = {
            'template_file': template_file,
            'plasmids_zip': zip_file,
            'mapping_file': mapping_file,
            # Paramètres scalaires optionnels laissés vides (test des valeurs par défaut)
            'enzyme': '',
            'default_concentration': '',
            'primer_pairs': ''
        }

        response = self.client.post(self.url, data, format='multipart')


        # --- 4 VÉRIFICATIONS (ASSERTIONS) ---

        # Vérifier que la requête a réussi (200 OK)
        self.assertEqual(response.status_code, 200)

        # Vérifier que le simulateur a bien été appelé une fois
        mock_compute.assert_called_once()

        # Vérifier que la réponse est bien un téléchargement de fichier ZIP
        self.assertTrue(response.has_header('Content-Disposition'))
        self.assertIn('attachment; filename="resultats_anonymes_', response['Content-Disposition'])
        self.assertTrue(response['Content-Disposition'].endswith('.zip"'))

        # Vérifier le Content-Type
        self.assertEqual(response['Content-Type'], 'application/zip')

        # Vérifier que les paramètres par défaut ont bien été passés au simulateur
        call_kwargs = mock_compute.call_args.kwargs
        self.assertIsNone(call_kwargs['primers_file'])       # Doit être None car pas envoyé
        self.assertIsNone(call_kwargs['concentration_file']) # Doit être None car pas envoyé
        self.assertIsNone(call_kwargs['enzyme_names'])       # Doit être None car vide
        self.assertEqual(call_kwargs['default_mass_concentration'], 200.0) # Valeur par défaut
