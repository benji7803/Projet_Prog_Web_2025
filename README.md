# Projet_Prog_Web_2025
Projet Programmation Web, AMI2B

# Lancer le projet

Pour garantir d'avoir les mêmes packages entre nous, il faut lancer les commandes suivantes lors de la création de l'environnement virtuel.

```bash
python3 -m venv .venv

source .venv/bin/activate

pip install -r requirements.txt
```

# Liste des trucs à faire

- Tester le pipeline en ligne de commande
- Faire une page web qui demande une template (en excel) et une liste de séquences de plasmide et une liste de correspondance (bouton upload -> les fichiers apparaissent) (view submit dans l'app gestionTemplate)
- Faire une page pour créer une template (view create dans gestionTemplate et template create.html)

# Fait :

- Améliorer la template layout.html et le css pour faire une belle navbar et un site correct
- Ajouter des tests unitaires : Vérifier que les plasmides en .gb sont dans la template associée (à modifier)
