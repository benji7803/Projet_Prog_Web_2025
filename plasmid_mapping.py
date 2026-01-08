# pip install biopython dna_features_viewer matplotlib

from Bio import SeqIO
from dna_features_viewer import GraphicFeature, GraphicRecord, CircularGraphicRecord
import matplotlib.pyplot as plt
import os

chemin = "data_web/pMISC/pCDE068.gb"

# Récupère juste le nom du fichier
nom_fichier = os.path.basename(chemin)

# Supprime l'extension
nom_sans_ext = os.path.splitext(nom_fichier)[0]

nom_plasmide = nom_sans_ext[1:]

record = SeqIO.read("data_web/pMISC/pCDE067.gb", "genbank")

# Couleurs selon le type de feature
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
    if f.type == "source":
        return None
    # utiliser seulement gene ou label, pas translation
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


features = [seqfeature_to_graphic(f) for f in record.features if seqfeature_to_graphic(f) is not None]

# Carte linéaire
linear_record = GraphicRecord(sequence_length=len(record.seq), features=features)
ax1, _ = linear_record.plot(figure_width=12)
ax1.set_title(f"Carte linéaire du plasmide {nom_plasmide}", fontsize=14)
plt.tight_layout()
ax1.figure.savefig(f"{nom_plasmide}_carte_lineaire.png", dpi=300)
plt.close(ax1.figure)

# Carte circulaire
circular_record = CircularGraphicRecord(
    sequence_length=len(record.seq),
    features=features,
    annotation_labels_radius=1.35
)

fig, ax = plt.subplots(figsize=(8,8))
circular_record.initialize_ax(ax)

# tracer les features
for feature in features:
    circular_record.plot_feature(ax, feature, level=0)

# supprimer les features contenant "Translation" dans le label
features = [f for f in features if "Translation" not in f.label]

# placer les labels autour du cercle
circular_record.add_labels(ax, features)

plt.tight_layout()
plt.show()
ax.set_title(f"Carte circulaire du plasmide {nom_plasmide}", fontsize=14)
ax.figure.savefig(f"{nom_plasmide}_carte_circulaire.png", dpi=300)
plt.close(ax.figure)

