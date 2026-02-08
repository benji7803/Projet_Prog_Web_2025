from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.contrib.auth import get_user_model
from users.models import Equipe, MembreEquipe

User = get_user_model()

class Command(BaseCommand):
    help = "Initialise les utilisateurs et les équipes avec leaders"

    def handle(self, *args, **options):
        self.stdout.write("--- Début de l'initialisation ---")

        with transaction.atomic():
            # 1. Création des utilisateurs
            u1, created1 = User.objects.get_or_create(
                email="salah@dev.fr",
                defaults={
                    "username": "salah",
                    "first_name": "Salah",
                    "last_name": "Admin",
                    "isAdministrator": True
                }
            )
            if created1:
                u1.set_password("motdepasse123")
                u1.save()

            u2, created2 = User.objects.get_or_create(
                email="benjamin@dev.fr",
                defaults={
                    "username": "benjamin",
                    "first_name": "Benjamin",
                    "last_name": "Manager",
                    "isAdministrator": False
                }
            )
            if created2:
                u2.set_password("pass123")
                u2.save()

            # 2. Création de l'Équipe
            equipe, eq_created = Equipe.objects.get_or_create(
                name="Equipe Test",
                defaults={"leader": u1}
            )

            if eq_created:
                # 3. Création des liens dans la table intermédiaire
                MembreEquipe.objects.create(
                    user=u1, 
                    equipe=equipe, 
                    date_rejoint=timezone.now()
                )
                
                MembreEquipe.objects.create(
                    user=u2, 
                    equipe=equipe, 
                    date_rejoint=timezone.now() + timezone.timedelta(minutes=5)
                )

                self.stdout.write(self.style.SUCCESS(f"Équipe '{equipe.name}' créée."))
                self.stdout.write(f"Leader : {equipe.leader.email}")
            else:
                self.stdout.write(self.style.WARNING("L'équipe existe déjà."))

        self.stdout.write(self.style.SUCCESS("--- Initialisation terminée avec succès ---"))