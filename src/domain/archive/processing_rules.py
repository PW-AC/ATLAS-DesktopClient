"""
Verarbeitungsregeln fuer das Dokumentenarchiv.

Reine Business-Logik fuer Dokumenttyp-Erkennung und Metadaten-Extraktion.
Kein Zugriff auf API, Dateisystem oder Qt.
"""

__all__ = [
    'SPREADSHEET_EXTENSIONS',
    'GDV_EXTENSIONS',
    'XML_EXTENSIONS',
    'DEFAULT_MAX_WORKERS',
    'GDV_FALLBACK_VU',
    'GDV_FALLBACK_DATE',
    'check_gdv_content',
    'extract_gdv_metadata',
]

# ---------------------------------------------------------------------------
# Extension-Sets fuer Dokumenttyp-Erkennung
# ---------------------------------------------------------------------------
SPREADSHEET_EXTENSIONS: frozenset = frozenset({'.csv', '.tsv', '.xlsx', '.xls'})
GDV_EXTENSIONS: frozenset = frozenset({'.gdv', '.dat', '.vwb'})
XML_EXTENSIONS: frozenset = frozenset({'.xml'})

# ---------------------------------------------------------------------------
# Verarbeitungslimits
# ---------------------------------------------------------------------------
DEFAULT_MAX_WORKERS: int = 8

# ---------------------------------------------------------------------------
# GDV-Fallback-Werte (identisch zu config/processing_rules.py)
# ---------------------------------------------------------------------------
GDV_FALLBACK_VU: str = "Xvu"
GDV_FALLBACK_DATE: str = "kDatum"


def check_gdv_content(text_content: str) -> bool:
    """
    Prueft ob der Textinhalt eine GDV-Datei ist.

    GDV-Dateien beginnen IMMER mit Satzart '0001' (Vorsatz).
    Prueft ZUERST auf PDF-Signatur, um False-Positives zu vermeiden.

    Args:
        text_content: Bereits dekodierter Dateiinhalt (oder erste 256 Zeichen)

    Returns:
        True wenn erste Zeile mit '0001' beginnt UND KEINE PDF-Signatur
    """
    if not text_content:
        return False

    if text_content.startswith('%PDF'):
        return False

    first_line = text_content.strip()
    return first_line.startswith('0001')


def extract_gdv_metadata(text_content: str) -> dict:
    """
    Extrahiert VU-Nummer, Absender und Datum aus GDV-Datensatz.

    Liest direkt aus dem Vorsatz (Satzart 0001):
    - VU-Nummer: Position 5-9 (5 Zeichen)
    - Absender: Position 10-39 (30 Zeichen) — Versicherer-Name
    - Datum: Position 70-77 (Erstellungsdatum, 8 Zeichen, TTMMJJJJ)

    Bei Fehlern werden definierte Fallback-Werte verwendet:
    - Xvu: Unbekannter Versicherer
    - kDatum: Kein Datum gefunden

    Args:
        text_content: Dekodierter GDV-Dateiinhalt

    Returns:
        Dict mit Schluesseln 'vu_nummer', 'absender', 'datum_iso'.
        Fallback-Werte bei fehlenden Daten.
    """
    fallback = {
        'vu_nummer': GDV_FALLBACK_VU,
        'absender': None,
        'datum_iso': GDV_FALLBACK_DATE,
    }

    if not text_content:
        return fallback

    for line in text_content.splitlines():
        if len(line) >= 77 and line[0:4] == '0001':
            vu_nummer = line[4:9].strip()
            absender = line[9:39].strip() if len(line) >= 39 else None

            datum_raw = line[69:77].strip()

            # TTMMJJJJ -> YYYY-MM-DD
            datum_iso = None
            if len(datum_raw) == 8 and datum_raw.isdigit():
                tag = datum_raw[0:2]
                monat = datum_raw[2:4]
                jahr = datum_raw[4:8]
                datum_iso = f"{jahr}-{monat}-{tag}"

            if not vu_nummer and not absender:
                vu_nummer = GDV_FALLBACK_VU

            if not datum_iso:
                datum_iso = GDV_FALLBACK_DATE

            return {
                'vu_nummer': vu_nummer,
                'absender': absender,
                'datum_iso': datum_iso,
            }

    return fallback
