"""
BiPRO Kategorien-Mapping

Übersetzt BiPRO-Kategorie-Codes in lesbare Beschreibungen.
Basierend auf BiPRO-Norm und Degenia-spezifischen Werten.
"""

# BiPRO Hauptkategorien (1. Stelle = Bereich)
# 1xxxxxxx = Vertrag/Bestand
# 2xxxxxxx = Schaden
# 3xxxxxxx = Provision

CATEGORY_NAMES = {
    # Vertragsänderungen / Bestandsdaten
    "100001000": "Neugeschäft",
    "100002000": "Vertragsänderung",
    "100003000": "Kündigung",
    "100004000": "Storno",
    "100005000": "Beitragsänderung",
    "100006000": "Adressänderung",
    "100007000": "Geschäftsvorfall",
    "100008000": "Vertragsstatus",
    "100009000": "Mahnung",
    "100010000": "Inkasso",
    
    # Vertragsdokumente (11xxxxx)
    "110001000": "Police",
    "110002000": "Nachtrag",
    "110003000": "Beitragsrechnung",
    "110004000": "Mahnschreiben",
    "110005000": "Kündigungsbestätigung",
    "110006000": "Vertragsübersicht",
    "110007000": "Wertmitteilung",
    "110008000": "Dynamik-Mitteilung",
    "110009000": "Fondsreport",
    "110010000": "Steuerbescheinigung",
    "110011000": "Vertragsdokumente",
    
    # Schadenbereich (2xxxxxxx)
    "200001000": "Schadenmeldung",
    "200002000": "Schadenregulierung",
    "200003000": "Schadenzahlung",
    
    # Provision (3xxxxxxx)
    "300001000": "Provisionsabrechnung",
    "300002000": "Stornoreserve",
    
    # GDV-Daten
    "GDV": "GDV-Bestandsdaten",
    "GEVO": "Geschäftsvorfall",
}

# Kurznamen für Tabellenanzeige
CATEGORY_SHORT_NAMES = {
    "100001000": "Neugeschäft",
    "100002000": "Änderung",
    "100003000": "Kündigung",
    "100004000": "Storno",
    "100005000": "Beitrag",
    "100006000": "Adresse",
    "100007000": "GeVo",
    "100008000": "Status",
    "100009000": "Mahnung",
    "100010000": "Inkasso",
    "110001000": "Police",
    "110002000": "Nachtrag",
    "110003000": "Rechnung",
    "110004000": "Mahnung",
    "110005000": "Kündigung",
    "110006000": "Übersicht",
    "110007000": "Wert",
    "110008000": "Dynamik",
    "110009000": "Fonds",
    "110010000": "Steuer",
    "110011000": "Dokumente",
    "200001000": "Schaden",
    "200002000": "Regulierung",
    "200003000": "Zahlung",
    "300001000": "Provision",
    "300002000": "Reserve",
}


def get_category_name(code: str) -> str:
    """
    Gibt den lesbaren Namen für einen Kategorie-Code zurück.
    
    Args:
        code: BiPRO-Kategorie-Code (z.B. "100002000")
        
    Returns:
        Lesbarer Name (z.B. "Vertragsänderung") oder der Code selbst
    """
    if not code:
        return "Unbekannt"
    
    # Exakte Übereinstimmung
    if code in CATEGORY_NAMES:
        return CATEGORY_NAMES[code]
    
    # Versuche Präfix-Match (erste 3 Stellen)
    prefix = code[:3] if len(code) >= 3 else code
    
    if prefix == "100":
        return f"Vertrag ({code})"
    elif prefix == "110":
        return f"Dokument ({code})"
    elif prefix == "200":
        return f"Schaden ({code})"
    elif prefix == "300":
        return f"Provision ({code})"
    
    return code


def get_category_short_name(code: str) -> str:
    """
    Gibt einen Kurznamen für die Tabellenanzeige zurück.
    
    Args:
        code: BiPRO-Kategorie-Code
        
    Returns:
        Kurzname oder Code
    """
    if not code:
        return "-"
    
    return CATEGORY_SHORT_NAMES.get(code, code[:6] + "..." if len(code) > 6 else code)


def get_category_icon(code: str) -> str:
    """
    Gibt ein Icon/Emoji für die Kategorie zurück.
    
    Args:
        code: BiPRO-Kategorie-Code
        
    Returns:
        Passendes Icon
    """
    if not code:
        return "📄"
    
    prefix = code[:3] if len(code) >= 3 else ""
    
    icons = {
        "100": "📋",  # Vertrag
        "110": "📄",  # Dokument
        "200": "⚠️",  # Schaden
        "300": "💰",  # Provision
    }
    
    return icons.get(prefix, "📦")
