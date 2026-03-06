"""
Utility-Funktionen fuer das Workforce-Modul.

Quelle: app.py Zeilen 315-455, 2509-2555
"""

import json
import hashlib
from datetime import datetime


def get_from_path(obj: dict, *paths, default=None):
    """
    Greift sicher auf verschachtelte Schluessel in einem Dictionary zu.

    Args:
        obj: Das Dictionary, aus dem Werte extrahiert werden sollen
        *paths: Pfade als Strings ('a.b.c') oder Tupel ('a', 'b', 'c')
        default: Standardwert wenn kein Pfad gefunden wird

    Returns:
        Gefundener Wert oder default
    """
    for p in paths:
        if not p:
            continue
        keys = p if isinstance(p, (list, tuple)) else str(p).split(".")
        cur = obj
        ok = True
        for k in keys:
            if not isinstance(cur, dict):
                ok = False
                break
            cur = cur.get(k)
            if cur is None:
                ok = False
                break
        if ok and cur not in (None, ""):
            return cur
    return default


def get_value_from_details(details: dict, target_label: str, default=None):
    """
    Extrahiert einen Wert aus dem Details-Dictionary basierend auf dem Label.

    Args:
        details: Details-Dictionary mit strukturierten Gruppen
        target_label: Gesuchtes Label (case-insensitive)
        default: Standardwert

    Returns:
        Gefundener Wert oder default
    """
    target_label = target_label.lower()
    for group_items in details.values():
        for item in group_items:
            if item.get('label', '').lower() == target_label:
                return item.get('value', default)
    return default


def getv(e: dict, details: dict | None, label: str | None, *flat_paths, default: str = "") -> str:
    """
    Extrahiert einen Wert aus einem Mitarbeiter-Dictionary.
    Bevorzugt Suche in Details-Labels, dann Fallback auf flache Pfade.

    Args:
        e: Mitarbeiter-Dictionary
        details: Details-Dictionary mit strukturierten Labels
        label: Bevorzugtes Label fuer die Suche
        *flat_paths: Flache Pfade als Fallback
        default: Standardwert

    Returns:
        Gefundener Wert als String oder default
    """
    v = None
    if details and label:
        v = get_value_from_details(details, label, default=None)
    if v in (None, ""):
        v = get_from_path(e, *flat_paths, default=None)
    return "" if v is None else str(v).strip()


def get_safe_employer_name(name: str) -> str:
    """
    Bereinigt einen Arbeitgeber-Namen fuer die Verwendung in Dateinamen.

    Args:
        name: Urspruenglicher Arbeitgeber-Name

    Returns:
        Bereinigter Name, sicher fuer Dateinamen
    """
    return "".join(c for c in name if c.isalnum() or c in (' ', '_')).rstrip().replace(' ', '_')


def parse_date(date_str: str) -> datetime | None:
    """
    Parst einen Datumsstring aus gaengigen Formaten.

    Args:
        date_str: Zu parsender Datumsstring

    Returns:
        datetime-Objekt oder None
    """
    if not date_str or not isinstance(date_str, str):
        return None
    for fmt in ('%d.%m.%Y', '%Y-%m-%d'):
        try:
            return datetime.strptime(date_str.split('T')[0], fmt)
        except ValueError:
            pass
    return None


def format_date_for_display(date_str: str | None) -> str | None:
    """
    Formatiert einen Datumsstring in DD.MM.YYYY.

    Args:
        date_str: Zu formatierender Datumsstring

    Returns:
        Formatierter Datumsstring oder Original bei Fehlern
    """
    dt = parse_date(date_str)
    return dt.strftime('%d.%m.%Y') if dt else date_str


def json_hash(rec: dict) -> str:
    """
    Erstellt einen stabilen SHA256-Hash eines Dictionarys.

    Args:
        rec: Das zu hashende Dictionary

    Returns:
        SHA256-Hash als Hex-String
    """
    payload = json.dumps(rec, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8", errors="ignore")).hexdigest()


def flatten_record(obj, prefix="", out=None) -> dict:
    """
    Flacht ein verschachteltes Dictionary auf eine einzige Ebene ab.

    Args:
        obj: Zu flachendes Objekt
        prefix: Schluessel-Praefix
        out: Ausgabe-Dictionary (fuer Rekursion)

    Returns:
        Geflachtetes Dictionary
    """
    if out is None:
        out = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            flatten_record(v, f"{prefix}.{k}" if prefix else str(k), out)
    elif isinstance(obj, list):
        out[prefix or "value"] = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    else:
        out[prefix or "value"] = obj
    return out


def person_key(detail: dict) -> str | None:
    """
    Bestimmt die stabile eindeutige ID fuer einen Mitarbeiter.

    Args:
        detail: Mitarbeiterdetails

    Returns:
        Mitarbeiter-ID als String oder None
    """
    pid = detail.get("personId") or detail.get("uuid") or detail.get("personnelNumber") or detail.get("id")
    return str(pid) if pid is not None else None
