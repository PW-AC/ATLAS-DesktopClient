"""
Domain-Entitaeten fuer das Dokumentenarchiv.

Re-exportiert die bestehenden Dataclasses aus api.documents,
damit UseCases und Domain-Logik nicht direkt von der API-Schicht abhaengen.
Eigene DTOs fuer rein domain-interne Zwecke werden hier definiert.
"""

from dataclasses import dataclass, field
from typing import Optional, List


# ═══════════════════════════════════════════════════════════
# Re-Export bestehender API-Entitaeten
# ═══════════════════════════════════════════════════════════

from api.documents import Document, BoxStats, SearchResult


# ═══════════════════════════════════════════════════════════
# Domain-spezifische DTOs
# ═══════════════════════════════════════════════════════════


@dataclass
class MoveResult:
    """Ergebnis einer Verschiebe-Operation."""
    moved_count: int
    target_box: str
    total_requested: int
    doc_ids: List[int] = field(default_factory=list)
    original_boxes: List[str] = field(default_factory=list)


@dataclass
class ColorResult:
    """Ergebnis einer Farbmarkierungs-Operation."""
    changed_count: int
    color: Optional[str]
    doc_ids: List[int] = field(default_factory=list)


@dataclass
class ArchiveResult:
    """Ergebnis einer Archivierungs-/Entarchivierungs-Operation."""
    changed_count: int
    action: str  # 'archive' | 'unarchive'
    doc_ids: List[int] = field(default_factory=list)
    affected_boxes: List[str] = field(default_factory=list)


@dataclass
class RenameResult:
    """Ergebnis einer Umbenennungs-Operation."""
    success: bool
    doc_id: int
    new_filename: str
    excluded_from_processing: bool = False


@dataclass
class DeleteResult:
    """Ergebnis einer Loesch-Operation."""
    deleted_count: int
    total_requested: int


@dataclass
class UploadResult:
    """Ergebnis eines Einzel-Uploads."""
    success: bool
    filename: str
    document: Optional[Document] = None
    error: Optional[str] = None
    is_duplicate: bool = False


@dataclass
class DownloadResult:
    """Ergebnis eines Einzel-Downloads."""
    success: bool
    doc_id: int
    filename: str
    saved_path: Optional[str] = None
    error: Optional[str] = None
    auto_archived: bool = False


@dataclass
class SmartScanResult:
    """Ergebnis eines SmartScan-Versands."""
    success: bool
    document_count: int
    job_id: Optional[str] = None
    raw_response: Optional[dict] = None


@dataclass
class ProcessingToggleResult:
    """Ergebnis einer Exclude-/Include-Operation."""
    changed_count: int
    total_requested: int
    action: str  # 'exclude' | 'include'


@dataclass
class DuplicateInfo:
    """Informationen ueber ein erkanntes Duplikat."""
    original_id: int
    original_filename: str
    duplicate_type: str  # 'file_hash' | 'content_hash'
    original_box_type: Optional[str] = None
    original_is_archived: bool = False
