"""
Dateibenennungs-Regeln fuer das Dokumentenarchiv.

Reine Business-Logik fuer Dateinamen-Validierung und -Verarbeitung.
Kein Zugriff auf API, Dateisystem oder Qt.
"""

import os
from typing import Tuple, Optional


def split_filename(filename: str) -> Tuple[str, str]:
    """Trennt Dateiname und Endung. Gibt (name_ohne_ext, extension) zurueck."""
    return os.path.splitext(filename)


def build_renamed_filename(new_name_without_ext: str, original_filename: str) -> str:
    """Setzt neuen Dateinamen mit urspruenglicher Endung zusammen."""
    _, ext = split_filename(original_filename)
    return new_name_without_ext + ext


def validate_new_name(new_name_without_ext: str) -> Optional[str]:
    """Validiert einen neuen Dateinamen. Gibt Fehlermeldung oder None zurueck."""
    stripped = new_name_without_ext.strip()
    if not stripped:
        return 'empty_name'
    return None


def is_name_unchanged(new_name: str, current_name: str) -> bool:
    """Prueft ob der Name unveraendert ist."""
    return new_name == current_name
