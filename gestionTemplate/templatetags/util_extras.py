from django import template
import os
import re

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Retourne dictionary[key] ou chaîne vide si absent."""
    try:
        return dictionary.get(key, '')
    except Exception:
        return ''

@register.simple_tag
def image_title(label, filename):
    """Formate le titre affiché pour une image (p.ex. "Western Blot (pSA001)" ou "Western Blot (global)").

    Nettoie les suffixes courants ajoutés aux noms de fichiers ("-digestion", "_pcr", "__10x__", etc.)
    pour ne garder que l'identifiant du plasmide lorsqu'il est présent.
    """
    try:
        name = os.path.basename(filename or '')
        base = os.path.splitext(name)[0]
        lower = name.lower()

        base_stripped = base.rstrip('_-')
        base_clean = re.sub(r'(?i)(?:[_-]+(?:digestion|pcr|10x|direct|dilution|dig|blot))+$', '', base_stripped)

        
        if 'western' in label.lower() or 'blot' in label.lower() or 'digestion' in lower:
            if lower in ('digestion.png', 'digestion.jpg', 'digestion.jpeg'):
                return 'Western Blot (global)'
            return f'Western Blot ({base_clean})' if base_clean else 'Western Blot (global)'

        if 'pcr' in label.lower() or 'pcr' in lower:
            if lower in ('pcr.png', 'pcr.jpg', 'pcr.jpeg'):
                return 'PCR (global)'
            return f'PCR ({base_clean})' if base_clean else 'PCR'

        return label
    except Exception:
        return label

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)