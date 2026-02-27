"""
Reine Business-Logik fuer die Dokumenten-Klassifikation.

Extrahiert aus DocumentProcessor — enthaelt KEINE API-Aufrufe,
kein File-I/O, kein Threading, kein PySide6.
"""

from __future__ import annotations

import os
import re
from typing import Optional, Tuple

from config.processing_rules import (
    PROCESSING_RULES,
    is_bipro_courtage_code,
    is_bipro_gdv_code,
)


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

def slugify(text: str) -> str:
    """
    Konvertiert Text in sicheren Dateinamen.
    Ersetzt Umlaute und entfernt Sonderzeichen.
    """
    if not text:
        return "unbekannt"

    replacements = {
        'ä': 'ae', 'ö': 'oe', 'ü': 'ue',
        'Ä': 'Ae', 'Ö': 'Oe', 'Ü': 'Ue',
        'ß': 'ss',
    }
    for old, new in replacements.items():
        text = text.replace(old, new)

    text = re.sub(r'[^a-zA-Z0-9_]', '_', text)
    text = re.sub(r'_+', '_', text)
    text = text.strip('_')

    return text or "unbekannt"


def rename_with_extension(filename: str, new_name: str) -> str:
    """
    Berechnet den neuen Dateinamen mit geaenderter Endung.

    Args:
        filename: Originaler Dateiname
        new_name: Neue Dateiendung (z.B. '.pdf', '.gdv')

    Returns:
        Neuer Dateiname mit ersetzter Endung
    """
    base_name, _ = os.path.splitext(filename)
    return base_name + new_name


def is_spreadsheet(extension: str) -> bool:
    """Prueft ob es sich um eine tabellarische Datei handelt (CSV, TSV, Excel)."""
    return extension.lower() in ['.csv', '.tsv', '.xlsx', '.xls']


# ---------------------------------------------------------------------------
# BiPRO-Klassifikation
# ---------------------------------------------------------------------------

def is_bipro_courtage(bipro_category: str) -> bool:
    """
    Prueft ob der BiPRO-Code eine Provisionsabrechnung markiert.

    Verwendet die Konfiguration aus config/processing_rules.py.
    """
    if not bipro_category:
        return False
    return is_bipro_courtage_code(bipro_category)


def is_bipro_gdv(bipro_category: str) -> bool:
    """
    Prueft ob der BiPRO-Code eine GDV-Datei markiert (999xxx).
    """
    if not bipro_category:
        return False
    return is_bipro_gdv_code(bipro_category)


# ---------------------------------------------------------------------------
# Datei-Typ-Erkennung (regelbasiert, kein Content-Check)
# ---------------------------------------------------------------------------

def is_xml_raw(filename: str, extension: str, bipro_category: str) -> bool:
    """Prueft ob es sich um eine XML-Rohdatei handelt."""
    for pattern in PROCESSING_RULES.get('raw_xml_patterns', []):
        if pattern.startswith('*'):
            if filename.endswith(pattern[1:]):
                return True
        elif pattern.endswith('*'):
            if filename.startswith(pattern[:-1]):
                return True
        elif '*' in pattern:
            prefix, suffix = pattern.split('*', 1)
            if filename.startswith(prefix) and filename.endswith(suffix):
                return True
        elif filename == pattern:
            return True

    is_xml = extension.lower() == '.xml'
    if is_xml and 'roh' in filename.lower():
        return True

    return False


def is_gdv_file(filename: str, extension: str, bipro_category: str) -> bool:
    """
    Prueft ob es sich um eine GDV-Datei handelt (BiPRO-Code + Endung).

    Content-basierte Erkennung (Magic-Bytes) liegt ausserhalb
    dieser reinen Logik und wird vom Aufrufer behandelt.
    """
    if bipro_category and is_bipro_gdv_code(bipro_category):
        return True

    ext = extension.lower()
    gdv_extensions = PROCESSING_RULES.get('gdv_extensions', ['.gdv'])
    if ext in gdv_extensions:
        return True

    return False


# ---------------------------------------------------------------------------
# Dokument-Klassifikation
# ---------------------------------------------------------------------------

def classify_document(
    filename: str,
    extension: str,
    bipro_category: str,
    is_pdf: bool,
    is_spreadsheet_flag: bool,
) -> Tuple[str, str]:
    """
    Klassifiziert ein Dokument basierend auf Typ und Dateiendung.

    Content-basierte Erkennung (Magic-Bytes) und Umbenennung
    liegen ausserhalb dieser reinen Logik und werden vom Aufrufer
    behandelt wenn ('sonstige', 'unknown_extension') zurueckgegeben wird.

    Returns:
        (target_box, category)
    """
    known_extensions = PROCESSING_RULES.get(
        'known_extensions', ['.pdf', '.xml', '.gdv', '.txt', ''],
    )

    if is_xml_raw(filename, extension, bipro_category):
        return ('roh', 'xml_raw')

    if is_gdv_file(filename, extension, bipro_category):
        return ('gdv', 'gdv')

    if is_pdf:
        return ('sonstige', 'pdf_pending')

    if is_spreadsheet_flag:
        return ('sonstige', 'spreadsheet_pending')

    if extension.lower() not in known_extensions:
        return ('sonstige', 'unknown_extension')

    return ('sonstige', 'unknown')


# ---------------------------------------------------------------------------
# Sparten-Erkennung
# ---------------------------------------------------------------------------

def is_leben_category(doc_type: str) -> bool:
    """Prueft ob der Dokumenttyp zur Leben-Kategorie gehoert."""
    leben_keywords = [
        'leben', 'life', 'rente', 'pension', 'altersvorsorge',
        'berufsunfähigkeit', 'bu', 'risiko', 'kapital', 'fond',
    ]
    return any(kw in doc_type for kw in leben_keywords)


def is_sach_category(doc_type: str) -> bool:
    """Prueft ob der Dokumenttyp zur Sach-Kategorie gehoert."""
    sach_keywords = [
        'sach', 'haftpflicht', 'hausrat', 'wohngebäude', 'kfz',
        'auto', 'unfall', 'rechtsschutz', 'glas', 'elektronik',
        'transport', 'gewerbe', 'betrieb',
    ]
    return any(kw in doc_type for kw in sach_keywords)


def is_courtage_document(versicherungstyp: Optional[str] = None) -> bool:
    """Prueft ob das Dokument eine Courtage/Provisionsabrechnung ist."""
    courtage_keywords = PROCESSING_RULES.get('courtage_keywords', [])
    doc_type = (versicherungstyp or '').lower()

    for keyword in courtage_keywords:
        if keyword.lower() in doc_type:
            return True

    return False


__all__ = [
    'slugify',
    'rename_with_extension',
    'is_spreadsheet',
    'is_bipro_courtage',
    'is_bipro_gdv',
    'is_xml_raw',
    'is_gdv_file',
    'classify_document',
    'is_leben_category',
    'is_sach_category',
    'is_courtage_document',
]
