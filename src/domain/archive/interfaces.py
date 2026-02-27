"""
Interfaces (Protocols) fuer das Dokumentenarchiv.

Definiert die Vertraege zwischen Schichten.
Domain und UseCases haengen nur von diesen Interfaces ab,
nie von konkreten Implementierungen.
"""

from __future__ import annotations

from typing import Protocol, Optional, List, Dict, Tuple, Any, runtime_checkable, TYPE_CHECKING

if TYPE_CHECKING:
    from services.zip_handler import ZipExtractResult

from .entities import Document, BoxStats, SearchResult, DuplicateInfo


# ═══════════════════════════════════════════════════════════
# Repository Interfaces (implementiert in Infrastructure)
# ═══════════════════════════════════════════════════════════


@runtime_checkable
class IDocumentRepository(Protocol):
    """Zugriff auf Dokumente (API/Storage)."""

    def list_documents(
        self, *,
        box_type: Optional[str] = None,
        is_archived: Optional[bool] = None,
    ) -> List[Document]: ...

    def get_document(self, doc_id: int) -> Optional[Document]: ...

    def search_documents(
        self, query: str, *,
        limit: int = 200,
        include_raw: bool = False,
        substring: bool = False,
    ) -> List[SearchResult]: ...

    def get_box_stats(self) -> BoxStats: ...

    def upload(
        self, file_path: str, *,
        source_type: str = 'manual_upload',
        box_type: Optional[str] = None,
    ) -> Optional[Document]: ...

    def download(
        self, doc_id: int, target_dir: str, *,
        filename_override: Optional[str] = None,
    ) -> Optional[str]: ...

    def delete(self, doc_id: int) -> bool: ...

    def delete_documents(self, doc_ids: List[int]) -> int: ...

    def move_documents(
        self, doc_ids: List[int], target_box: str, *,
        processing_status: Optional[str] = None,
    ) -> int: ...

    def rename_document(
        self, doc_id: int, new_filename: str, *,
        mark_ai_renamed: bool = False,
    ) -> bool: ...

    def update(self, doc_id: int, **fields: Any) -> bool: ...

    def archive_document(self, doc_id: int) -> bool: ...

    def unarchive_document(self, doc_id: int) -> bool: ...

    def archive_documents(self, doc_ids: List[int]) -> int: ...

    def unarchive_documents(self, doc_ids: List[int]) -> int: ...

    def set_document_color(self, doc_id: int, color: Optional[str]) -> bool: ...

    def set_documents_color(self, doc_ids: List[int], color: Optional[str]) -> int: ...

    def get_document_history(self, doc_id: int) -> Optional[List[Dict]]: ...

    def save_ai_data(self, doc_id: int, data: Dict[str, Any]) -> bool: ...

    def get_ai_data(self, doc_id: int) -> Optional[Dict[str, Any]]: ...

    def get_missing_ai_data_documents(self) -> List[Dict]: ...

    def get_credits(self) -> Optional[Dict]: ...

    def get_cost_stats(self) -> Optional[float]: ...

    def replace_document_file(self, doc_id: int, file_path: str) -> bool: ...


@runtime_checkable
class IHashService(Protocol):
    """Berechnung von Datei-Hashes."""

    def calculate_file_hash(
        self, filepath: str, algorithm: str = 'sha256',
    ) -> str: ...

    def verify_file_integrity(
        self, filepath: str, *,
        expected_size: Optional[int] = None,
        expected_hash: Optional[str] = None,
    ) -> Tuple[bool, str]: ...


@runtime_checkable
class IZipExtractor(Protocol):
    """Extraktion von ZIP-Archiven."""

    def is_zip_file(self, file_path: str) -> bool: ...

    def extract_zip_contents(
        self, zip_path: str, *,
        temp_dir: Optional[str] = None,
    ) -> ZipExtractResult: ...


@runtime_checkable
class ISmartScanAdapter(Protocol):
    """SmartScan-Integration."""

    def is_enabled(self) -> bool: ...

    def send_documents(
        self, doc_ids: List[int], *,
        mode: str = 'selected',
        archive_after: bool = False,
        recolor: bool = False,
        recolor_color: Optional[str] = None,
    ) -> Tuple[Optional[int], Optional[Dict]]: ...


@runtime_checkable
class IPdfProcessor(Protocol):
    """PDF-Verarbeitung (Thumbnails, Text-Extraktion)."""

    def extract_text(self, file_path: str) -> Optional[str]: ...

    def get_page_count(self, file_path: str) -> int: ...


# ═══════════════════════════════════════════════════════════
# View Interface (implementiert in UI)
# ═══════════════════════════════════════════════════════════


@runtime_checkable
class IArchiveView(Protocol):
    """Interface fuer die Archiv-View (implementiert von ArchiveBoxesView)."""

    def show_documents(self, documents: List[Document]) -> None: ...

    def show_stats(self, stats: BoxStats) -> None: ...

    def show_loading(self, visible: bool, status: str = "") -> None: ...

    def show_error(self, message: str) -> None: ...

    def show_success(self, message: str) -> None: ...

    def show_warning(self, message: str) -> None: ...

    def show_info(self, message: str) -> None: ...

    def show_credits(self, credits: Optional[Dict]) -> None: ...

    def refresh_all(self) -> None: ...
