# pip install biopython dna_features_viewer matplotlib

from Bio import SeqIO
from dna_features_viewer import BiopythonTranslator, GraphicFeature, GraphicRecord, CircularGraphicRecord
import matplotlib.pyplot as plt

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
    try:
        label = f.qualifiers.get("label", f.qualifiers.get("gene", [f.type]))[0]
    except Exception:
        label = f.type
    color = FEATURE_COLORS.get(f.type, FEATURE_COLORS["default"])
    return GraphicFeature(
        start=int(f.location.start),
        end=int(f.location.end),
        strand=f.location.strand,
        color=color,
        label=label
    )


features = [seqfeature_to_graphic(f) for f in record.features if seqfeature_to_graphic(f) is not None]

# Carte linéaire
linear_record = GraphicRecord(sequence_length=len(record.seq), features=features)
ax1, _ = linear_record.plot(figure_width=12)
ax1.set_title("Carte linéaire du plasmide {Y}", fontsize=14)
plt.tight_layout()
ax1.figure.savefig("{Y}_carte_lineaire.png", dpi=300)
plt.close(ax1.figure)

# Carte circulaire
circular_record = CircularGraphicRecord(sequence_length=len(record.seq), features=features)
ax2, _ = circular_record.plot(figure_width=8)
ax2.set_title("Carte circulaire du plasmide", fontsize=14)
plt.tight_layout()
ax2.figure.savefig("plasmide_carte_circulaire.png", dpi=300)
plt.close(ax2.figure)
