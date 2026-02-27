"""
Normalisierungsfunktionen für Provisionsdaten.

Reine String-Verarbeitung ohne externe Abhängigkeiten.
Migriert aus services/provision_import.py in den Domain Layer.
"""

import re


def normalize_vsnr(raw) -> str:
    """VSNR normalisieren: Nicht-Ziffern raus, ALLE Nullen raus.

    Identisch mit PHP normalizeVsnr() für konsistentes Matching.
    """
    s = str(raw).strip()
    if not s:
        return ''
    if 'e' in s.lower() and (',' in s or '.' in s):
        s = s.replace(',', '.')
        try:
            num = float(s)
            if num > 0 and not (num != num):
                s = f'{int(num)}'
        except (ValueError, OverflowError):
            pass
    digits = re.sub(r'\D', '', s)
    no_zeros = digits.replace('0', '')
    return no_zeros if no_zeros else '0'


def normalize_vermittler_name(name: str) -> str:
    """Vermittler-Namen normalisieren für Matching."""
    name = name.strip().lower()
    replacements = {'ä': 'ae', 'ö': 'oe', 'ü': 'ue', 'ß': 'ss'}
    for k, v in replacements.items():
        name = name.replace(k, v)
    name = re.sub(r'[^a-z0-9\s]', '', name)
    name = re.sub(r'\s+', ' ', name)
    return name.strip()


def normalize_for_db(name: str) -> str:
    """Person-Namen normalisieren für DB-Spalte.

    Identisch mit PHP normalizeForDb().
    """
    if not name:
        return ''
    name = name.strip().lower()
    for k, v in {'ä': 'ae', 'ö': 'oe', 'ü': 'ue', 'ß': 'ss'}.items():
        name = name.replace(k, v)
    name = re.sub(r'\(([^)]+)\)', r' \1', name)
    name = re.sub(r'[^a-z0-9\s]', ' ', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name


def normalize_vb_name(raw: str) -> str:
    """VB-Format 'NACHNAME (VORNAME)' in 'Nachname Vorname' normalisieren."""
    if not raw:
        return ''
    raw = raw.strip()
    m = re.match(r'^([^(]+)\(([^)]+)\)$', raw)
    if m:
        nachname = m.group(1).strip().title()
        vorname = m.group(2).strip().title()
        return f"{nachname} {vorname}"
    return raw.title()


def normalize_swisslife_vsnr(raw: str) -> str:
    """Swiss Life VSNR in XXXXX/XXXXX Format konvertieren."""
    digits = re.sub(r'\D', '', str(raw).strip())
    if len(digits) == 10:
        return f"{digits[:5]}/{digits[5:]}"
    return raw
