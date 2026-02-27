"""
Duplikat-Erkennung fuer das Dokumentenarchiv.

Reine Business-Logik: Nimmt Daten entgegen, gibt Entscheidungen zurueck.
Kein Zugriff auf API, Dateisystem oder Qt.
"""

from typing import Optional, Tuple

from .entities import Document, DuplicateInfo


def detect_duplicate(document: Document) -> Optional[DuplicateInfo]:
    """Prueft ob ein Dokument ein Duplikat ist und gibt Details zurueck."""
    if is_file_duplicate(document):
        return DuplicateInfo(
            original_id=document.previous_version_id,
            original_filename=document.duplicate_of_filename or '',
            duplicate_type='file_hash',
            original_box_type=document.duplicate_of_box_type,
            original_is_archived=document.duplicate_of_is_archived,
        )
    if is_content_duplicate(document):
        return DuplicateInfo(
            original_id=document.content_duplicate_of_id,
            original_filename=document.content_duplicate_of_filename or '',
            duplicate_type='content_hash',
            original_box_type=document.content_duplicate_of_box_type,
            original_is_archived=document.content_duplicate_of_is_archived,
        )
    return None


def is_file_duplicate(document: Document) -> bool:
    """Prueft ob Datei-Duplikat (Version > 1)."""
    try:
        return int(document.version) > 1
    except (TypeError, ValueError):
        return False


def is_content_duplicate(document: Document) -> bool:
    """Prueft ob Inhaltsduplikat (gleicher Text, andere Datei)."""
    return document.content_duplicate_of_id is not None


def has_any_duplicate(document: Document) -> bool:
    """Prueft ob Datei- ODER Inhaltsduplikat."""
    return is_file_duplicate(document) or is_content_duplicate(document)


def get_counterpart_info(
    document: Document,
) -> Optional[Tuple[int, str, bool]]:
    """Gibt (counterpart_id, box_type, is_archived) des Gegenstuecks zurueck."""
    if is_file_duplicate(document) and document.previous_version_id:
        return (
            document.previous_version_id,
            document.duplicate_of_box_type or '',
            document.duplicate_of_is_archived,
        )
    if is_content_duplicate(document) and document.content_duplicate_of_id:
        return (
            document.content_duplicate_of_id,
            document.content_duplicate_of_box_type or '',
            document.content_duplicate_of_is_archived,
        )
    return None
