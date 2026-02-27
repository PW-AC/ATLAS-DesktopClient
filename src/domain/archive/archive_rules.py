"""
Archivierungsregeln fuer das Dokumentenarchiv.

Reine Business-Logik ohne externe Abhaengigkeiten.
Definiert welche Boxen archivierbar sind, welche Verschiebeziele
erlaubt sind und welche Verarbeitungsregeln gelten.
"""

from typing import FrozenSet, Set


ARCHIVABLE_BOXES: FrozenSet[str] = frozenset({
    'gdv', 'courtage', 'sach', 'leben', 'kranken', 'sonstige',
})

MOVE_TARGET_BOXES: tuple = (
    'gdv', 'courtage', 'sach', 'leben', 'kranken', 'sonstige',
)

ADMIN_ONLY_BOXES: FrozenSet[str] = frozenset({'falsch'})

PROCESSING_BOXES: FrozenSet[str] = frozenset({'eingang', 'verarbeitung'})


def is_archivable(box_type: str) -> bool:
    """Prueft ob Dokumente aus dieser Box archiviert werden koennen."""
    return box_type in ARCHIVABLE_BOXES


def get_move_targets(current_boxes: Set[str], is_admin: bool = False) -> list:
    """Gibt erlaubte Verschiebeziele zurueck (filtert aktuelle Box raus)."""
    targets = list(MOVE_TARGET_BOXES)
    if is_admin:
        targets.extend(sorted(ADMIN_ONLY_BOXES))
    if len(current_boxes) == 1:
        only_box = next(iter(current_boxes))
        targets = [t for t in targets if t != only_box]
    return targets


def should_auto_archive_on_download(box_type: str, is_archived: bool) -> bool:
    """Prueft ob ein Dokument nach Download automatisch archiviert werden soll."""
    return box_type in ARCHIVABLE_BOXES and not is_archived


def should_exclude_on_rename(box_type: str) -> bool:
    """Prueft ob ein manuell umbenanntes Dokument von der Verarbeitung ausgeschlossen werden soll."""
    return box_type == 'eingang'


def is_excludable_from_processing(box_type: str, processing_status: str) -> bool:
    """Prueft ob ein Dokument von der Verarbeitung ausgeschlossen werden kann."""
    return box_type == 'eingang' and processing_status != 'manual_excluded'


def is_reprocessable(box_type: str, processing_status: str) -> bool:
    """Prueft ob ein Dokument erneut verarbeitet werden kann."""
    if processing_status == 'manual_excluded':
        return True
    return box_type not in PROCESSING_BOXES and processing_status != 'pending'


def is_ai_renameable(box_type: str, is_pdf: bool, ai_renamed: bool) -> bool:
    """Prueft ob ein Dokument fuer KI-Benennung geeignet ist."""
    return is_pdf and not ai_renamed and box_type not in PROCESSING_BOXES
