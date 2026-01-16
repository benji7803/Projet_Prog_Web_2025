# plasmid_mapping.py
from Bio import SeqIO
from dna_features_viewer import GraphicFeature, GraphicRecord, CircularGraphicRecord
import matplotlib.pyplot as plt
import os

# Couleurs par type de feature
FEATURE_COLORS = {
    "CDS": "#66c2a5",
    "gene": "#fc8d62",
    "promoter": "#8da0cb",
    "terminator": "#e78ac3",
    "rep_origin": "#a6d854",
    "misc_feature": "#ffd92f",
    "misc_binding": "#e5c494",
    "default": "#b3b3b3"
}

def seqfeature_to_graphic(f):
    """Convertit un feature Biopython en GraphicFeature avec couleur et label."""
    if f.type == "source":
        return None

    if "gene" in f.qualifiers:
        label = f.qualifiers["gene"][0]
    elif "label" in f.qualifiers:
        label = f.qualifiers["label"][0]
    else:
        label = f.type
    return GraphicFeature(
        start=int(f.location.start),
        end=int(f.location.end),
        strand=f.location.strand,
        color=FEATURE_COLORS.get(f.type, FEATURE_COLORS["default"]),
        label=label
    )

def generate_plasmid_maps(chemin, output_dir="temp_uploads/plasmid_maps"):
    """
    Génère les cartes linéaire et circulaire d'un plasmide GenBank.
    Renvoie les chemins relatifs vers les images pour Django.
    """
    os.makedirs(output_dir, exist_ok=True)

    # Lecture du fichier GenBank
    record = SeqIO.read(chemin, "genbank")

    # Nom de base pour le fichier PNG
    nom_fichier = os.path.basename(chemin)
    nom_sans_ext = os.path.splitext(nom_fichier)[0]
    nom_plasmide = nom_sans_ext
# Supprime le premier caractère si c'est un "p"
    if nom_plasmide.startswith("p"):
        nom_plasmide = nom_plasmide[1:]

    # Conversion des features
    features = [seqfeature_to_graphic(f) for f in record.features if seqfeature_to_graphic(f) is not None]

    # --- Carte linéaire ---
    linear_record = GraphicRecord(sequence_length=len(record.seq), features=features)
    ax1, _ = linear_record.plot(figure_width=12)
    ax1.set_title(f"Carte linéaire du plasmide {nom_plasmide}", fontsize=14)
    linear_path = os.path.join(output_dir, f"{nom_plasmide}_lineaire.png")
    plt.tight_layout()
    ax1.figure.savefig(linear_path, dpi=300)
    plt.close(ax1.figure)

    # --- Carte circulaire ---
    circular_record = CircularGraphicRecord(
        sequence_length=len(record.seq),
        features=features,
        annotation_labels_radius=1.35
    )
    fig, ax = plt.subplots(figsize=(8, 8))
    circular_record.initialize_ax(ax)
    for feature in features:
        circular_record.plot_feature(ax, feature, level=0)
    circular_record.add_labels(ax, features)
    ax.set_title(f"Carte circulaire du plasmide {nom_sans_ext}", fontsize=14)
    circular_path = os.path.join(output_dir, f"{nom_sans_ext}_circulaire.png")
    plt.tight_layout()
    ax.figure.savefig(circular_path, dpi=300)
    plt.close(ax.figure)

    # Retourne les chemins relatifs utilisables dans le template
    return linear_path, circular_path
