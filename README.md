# Projet_Prog_Web_2025
Projet Programmation Web, AMI2B

de Benjamin Prehaud, Salah Bouchelagem, Jérémy Caron et Ludovic Senez

L'URL du git est : https://github.com/benji7803/Projet_Prog_Web_2025

# Lancer le projet

Pour garantir d'avoir les mêmes packages entre nous, il faut lancer les commandes suivantes lors de la création de l'environnement virtuel.

```bash
python3 -m venv .venv

source .venv/bin/activate

pip install -r requirements.txt

python manage.py import_users

python manage.py import_details

python3 manage.py migrate

python3 ./manage.py runserver
```
# Générer le schéma de la base de données

```bash
sudo apt-get update
sudo apt-get install graphviz libgraphviz-dev pkg-config

python manage.py graph_models -a -o schema_BD.png
```
Pour visualiser le site web, il suffit de rentrer 127.0.0.1:8000 dans le navigateur.

Suite à l'initialisation, vous disposez de deux comptes :
salah@dev.fr MdP:motdepasse123 (Admin)
benjamin@dev.fr MdP:motdepasse123

Ces deux comptes font partie d'une même équipe dont la cheffe est Salah

Sur le compte Salah, dans son profile, il dispose d'une collection de plasmide et d'une table de correspondance et à publier un template (qui est en réalité une campagne)
Pour lancer une simulation test, nous vous conseillons de télécharger le template pour pouvoir l'upload pour la simulation.
Vous pourriez alors sélectionner la collection de plasmides et la table de correspondance pour la simulation.

