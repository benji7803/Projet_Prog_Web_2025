from django.test import TestCase

from django.test import TestCase
import tempfile
import shutil
from pathlib import Path
from gestionTemplate.models import Plasmide


class PlasmideGenbankTest(TestCase):
    def test_create_from_genbank_file(self):
        src = Path(r"c:\Users\ludov\Documents\Projet_Prog_Web_2025\data_web\pMISC\pCDE067.gb")
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