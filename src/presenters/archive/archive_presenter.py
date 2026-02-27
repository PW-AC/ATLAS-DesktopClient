"""
Presenter: Dokumentenarchiv.

Vermittelt zwischen ArchiveBoxesView (View) und UseCases/Workers.
Alle Worker-Starts, API-Orchestrierung und Business-Logik-Aufrufe
laufen ueber diesen Presenter.
"""

from __future__ import annotations

import logging
from typing import Optional, List, TYPE_CHECKING

from PySide6.QtCore import QThread

if TYPE_CHECKING:
    from domain.archive.interfaces import IArchiveView
    from infrastructure.threading.archive_workers import AIRenameWorker

from api.client import APIClient
from api.documents import DocumentsAPI, Document

from infrastructure.archive.document_repository import DocumentRepository
from infrastructure.archive.smartscan_adapter import SmartScanAdapter

from infrastructure.threading.archive_workers import (
    DocumentHistoryWorker,
    CacheDocumentLoadWorker,
    MissingAiDataWorker,
    MultiUploadWorker,
    PreviewDownloadWorker,
    MultiDownloadWorker,
    BoxDownloadWorker,
    CreditsWorker,
    CostStatsWorker,
    DelayedCostWorker,
    BoxStatsWorker,
    DocumentMoveWorker,
    DocumentColorWorker,
    ProcessingWorker,
    SearchWorker,
    SmartScanWorker,
)

from usecases.archive.load_documents import LoadDocuments
from usecases.archive.load_box_stats import LoadBoxStats
from usecases.archive.upload_document import UploadDocument
from usecases.archive.download_document import DownloadDocument
from usecases.archive.search_documents import SearchDocuments
from usecases.archive.process_document import ProcessDocument
from usecases.archive.smartscan_send import SmartScanSend
from usecases.archive.move_document import MoveDocument
from usecases.archive.archive_document import ArchiveDocuments
from usecases.archive.rename_document import RenameDocument
from usecases.archive.delete_document import DeleteDocument
from usecases.archive.set_document_color import SetDocumentColor
from usecases.archive.exclude_from_processing import ExcludeFromProcessing
from usecases.archive.include_for_processing import IncludeForProcessing

from domain.archive import archive_rules
from domain.archive.entities import (
    ArchiveResult, RenameResult, DeleteResult, DownloadResult,
    ProcessingToggleResult,
)

logger = logging.getLogger(__name__)


class ArchivePresenter:
    """Presenter fuer das Dokumentenarchiv.

    Verwaltet alle Worker-Lifecycles, orchestriert UseCases
    und aktualisiert die View ueber das IArchiveView Interface.
    """

    def __init__(self, api_client: APIClient, auth_api=None):
        self._api_client = api_client
        self._auth_api = auth_api

        # Repository
        self._repo = DocumentRepository(api_client)
        self._smartscan = SmartScanAdapter(api_client)
        self._docs_api = self._repo.api

        # UseCases
        self._uc_load_docs = LoadDocuments(self._repo)
        self._uc_load_stats = LoadBoxStats(self._repo)
        self._uc_upload = UploadDocument(self._repo)
        self._uc_download = DownloadDocument(self._repo)
        self._uc_search = SearchDocuments(self._repo)
        self._uc_process = ProcessDocument(api_client)
        self._uc_smartscan = SmartScanSend(api_client)
        self._uc_move = MoveDocument(self._repo)
        self._uc_archive = ArchiveDocuments(self._repo)
        self._uc_rename = RenameDocument(self._repo)
        self._uc_delete = DeleteDocument(self._repo)
        self._uc_color = SetDocumentColor(self._repo)
        self._uc_exclude = ExcludeFromProcessing(self._repo)
        self._uc_include = IncludeForProcessing(self._repo)

        # View-Referenz (wird spaeter per set_view gesetzt)
        self._view: Optional[IArchiveView] = None

        # Worker-Referenzen
        self._load_worker: Optional[CacheDocumentLoadWorker] = None
        self._stats_worker: Optional[BoxStatsWorker] = None
        self._credits_worker: Optional[CreditsWorker] = None
        self._cost_stats_worker: Optional[CostStatsWorker] = None
        self._move_worker: Optional[DocumentMoveWorker] = None
        self._color_worker: Optional[DocumentColorWorker] = None
        self._history_worker: Optional[DocumentHistoryWorker] = None
        self._processing_worker: Optional[ProcessingWorker] = None
        self._upload_worker: Optional[MultiUploadWorker] = None
        self._download_worker: Optional[MultiDownloadWorker] = None
        self._preview_worker: Optional[PreviewDownloadWorker] = None
        self._ai_rename_worker: Optional[AIRenameWorker] = None
        self._smartscan_worker: Optional[SmartScanWorker] = None
        self._delayed_cost_worker: Optional[DelayedCostWorker] = None
        self._box_download_worker: Optional[BoxDownloadWorker] = None

        # Aktive Worker fuer Cleanup
        self._active_workers: List[QThread] = []

        # SmartScan-Status
        self._smartscan_enabled = False

    @property
    def repository(self) -> DocumentRepository:
        return self._repo

    def get_docs_api_for_dialog(self) -> DocumentsAPI:
        """Stellt DocumentsAPI fuer Dialoge bereit (DuplicateCompare, PDFViewer).

        NICHT fuer allgemeine Nutzung — Presenter-Methoden verwenden.
        """
        return self._docs_api

    @property
    def api_client(self) -> APIClient:
        return self._api_client

    @property
    def smartscan_enabled(self) -> bool:
        return self._smartscan_enabled

    @property
    def is_admin(self) -> bool:
        if self._auth_api and self._auth_api.current_user:
            return self._auth_api.current_user.is_admin
        return False

    def set_view(self, view: 'IArchiveView') -> None:
        self._view = view

    def get_smartscan_settings(self) -> dict:
        """Laedt SmartScan-Einstellungen ueber den Adapter."""
        return self._smartscan.get_settings()

    def log_batch_complete(self, batch_result) -> 'Optional[int]':
        """Loggt Batch-Verarbeitungsabschluss in der DB. Gibt History-Entry-ID zurueck."""
        from services.document_processor import DocumentProcessor
        processor = DocumentProcessor(self._api_client)
        return processor.log_batch_complete(batch_result)

    # ═══════════════════════════════════════════════════════════
    # Worker Management
    # ═══════════════════════════════════════════════════════════

    def register_worker(self, worker: QThread) -> None:
        """Registriert einen Worker fuer sauberes Cleanup."""
        self._active_workers.append(worker)
        worker.finished.connect(lambda: self._unregister_worker(worker))

    def _unregister_worker(self, worker: QThread) -> None:
        if worker in self._active_workers:
            self._active_workers.remove(worker)
        if getattr(self, '_preview_worker', None) is worker:
            self._preview_worker = None
        worker.deleteLater()

    def is_worker_running(self, attr_name: str) -> bool:
        worker = getattr(self, attr_name, None)
        if worker is None:
            return False
        try:
            return worker.isRunning()
        except RuntimeError:
            setattr(self, attr_name, None)
            return False

    def get_blocking_operations(self) -> list:
        from i18n import de as texts
        blocking = []
        if self.is_worker_running('_processing_worker'):
            blocking.append(texts.CLOSE_BLOCKED_PROCESSING)
        if self.is_worker_running('_delayed_cost_worker'):
            blocking.append(texts.CLOSE_BLOCKED_COST_CHECK)
        if self.is_worker_running('_smartscan_worker'):
            blocking.append(texts.CLOSE_BLOCKED_SMARTSCAN)
        return blocking

    def has_running_workers(self) -> bool:
        for w in self._active_workers:
            try:
                if w.isRunning():
                    return True
            except RuntimeError:
                pass
        return False

    def cleanup(self) -> None:
        """Beendet alle Worker sauber."""
        for w in list(self._active_workers):
            try:
                if w.isRunning():
                    w.quit()
                    w.wait(2000)
            except RuntimeError:
                pass
        self._active_workers.clear()

    # ═══════════════════════════════════════════════════════════
    # SmartScan
    # ═══════════════════════════════════════════════════════════

    def load_smartscan_status(self) -> bool:
        self._smartscan_enabled = self._smartscan.is_enabled()
        return self._smartscan_enabled

    # ═══════════════════════════════════════════════════════════
    # Load Operations (Stats, Documents, Credits, Costs)
    # ═══════════════════════════════════════════════════════════

    def load_stats(self, callback, error_callback=None) -> None:
        """Laedt Box-Statistiken asynchron."""
        self._stats_worker = BoxStatsWorker(self._repo)
        self._stats_worker.finished.connect(callback)
        if error_callback:
            self._stats_worker.error.connect(error_callback)
        self.register_worker(self._stats_worker)
        self._stats_worker.start()

    def load_credits(self, callback) -> None:
        """Laedt KI-Credits asynchron."""
        self._credits_worker = CreditsWorker(self._api_client)
        self._credits_worker.finished.connect(callback)
        self.register_worker(self._credits_worker)
        self._credits_worker.start()

    def load_avg_cost_stats(self, callback) -> None:
        """Laedt durchschnittliche Verarbeitungskosten."""
        if self._cost_stats_worker and self._cost_stats_worker.isRunning():
            return
        self._cost_stats_worker = CostStatsWorker(self._api_client)
        self._cost_stats_worker.finished.connect(callback)
        self.register_worker(self._cost_stats_worker)
        self._cost_stats_worker.start()

    def check_missing_ai_data(self, callback) -> None:
        """Startet Hintergrund-Worker fuer fehlende Text-Extraktion."""
        worker = MissingAiDataWorker(self._docs_api)
        worker.finished.connect(callback)
        self.register_worker(worker)
        worker.start()
        logger.debug("MissingAiDataWorker gestartet")

    # ═══════════════════════════════════════════════════════════
    # Document History
    # ═══════════════════════════════════════════════════════════

    def load_document_history(self, doc_id: int, finished_callback, error_callback) -> None:
        if self._history_worker:
            try:
                if self._history_worker.isRunning():
                    self._history_worker.quit()
                    self._history_worker.wait(1000)
            except RuntimeError:
                pass
            self._history_worker = None
        self._history_worker = DocumentHistoryWorker(self._api_client, doc_id)
        self._history_worker.finished.connect(finished_callback)
        self._history_worker.error.connect(error_callback)
        self.register_worker(self._history_worker)
        self._history_worker.start()

    # ═══════════════════════════════════════════════════════════
    # Move, Color, Archive, Delete, Rename
    # ═══════════════════════════════════════════════════════════

    def move_documents(
        self, doc_ids: List[int], target_box: str, *,
        processing_status: Optional[str] = None,
        finished_callback=None, error_callback=None,
    ) -> None:
        """Verschiebt Dokumente asynchron."""
        self._move_worker = DocumentMoveWorker(
            self._repo, doc_ids, target_box,
            processing_status=processing_status,
        )
        if finished_callback:
            self._move_worker.finished.connect(finished_callback)
        if error_callback:
            self._move_worker.error.connect(error_callback)
        self.register_worker(self._move_worker)
        self._move_worker.start()

    def set_document_color(
        self, doc_ids: List[int], color: Optional[str],
        finished_callback=None, error_callback=None,
    ) -> None:
        """Setzt Farbmarkierung asynchron."""
        self._color_worker = DocumentColorWorker(self._repo, doc_ids, color)
        if finished_callback:
            self._color_worker.finished.connect(finished_callback)
        if error_callback:
            self._color_worker.error.connect(error_callback)
        self.register_worker(self._color_worker)
        self._color_worker.start()

    def archive_documents(self, documents: List[Document]) -> ArchiveResult:
        """Archiviert Dokumente via UseCase (prueft Domain-Regeln)."""
        return self._uc_archive.execute(documents, action='archive')

    def archive_by_ids(self, doc_ids: List[int]) -> int:
        """Archiviert Dokumente nur per ID (fuer Worker-Callbacks ohne Document-Objekte).

        Keine Domain-Validierung — nur verwenden wenn der Aufrufer bereits
        geprueft hat, dass die Dokumente archivierbar sind.
        """
        return self._repo.archive_documents(doc_ids)

    def unarchive_documents(self, documents: List[Document]) -> ArchiveResult:
        """Entarchiviert Dokumente via UseCase."""
        return self._uc_archive.execute(documents, action='unarchive')

    def delete_document(self, doc: Document) -> DeleteResult:
        """Loescht ein einzelnes Dokument via UseCase."""
        return self._uc_delete.execute(doc)

    def delete_documents(self, documents: List[Document]) -> DeleteResult:
        """Loescht mehrere Dokumente via UseCase (Bulk)."""
        return self._uc_delete.execute(documents)

    def rename_document(self, doc: Document, new_name_without_ext: str) -> RenameResult:
        """Benennt ein Dokument um via UseCase."""
        return self._uc_rename.execute(doc, new_name_without_ext)

    def get_document(self, doc_id: int) -> Optional[Document]:
        """Laedt ein einzelnes Dokument (synchron)."""
        return self._repo.get_document(doc_id)

    def move_documents_sync(self, doc_ids: List[int], target_box: str) -> int:
        """Verschiebt Dokumente synchron (fuer Undo-Operationen).

        Nutzt Repository direkt, da Undo nur IDs hat (keine Document-Objekte).
        """
        return self._repo.move_documents(doc_ids, target_box)

    def download_and_archive(
        self, doc: Document, target_dir: str,
    ) -> DownloadResult:
        """Download mit automatischer Archivierung via UseCase."""
        return self._uc_download.execute(doc, target_dir)

    def exclude_from_processing(self, documents: List[Document]) -> ProcessingToggleResult:
        """Schliesst Dokumente von der Verarbeitung aus via UseCase."""
        return self._uc_exclude.execute(documents)

    def include_for_processing(self, documents: List[Document]) -> ProcessingToggleResult:
        """Gibt Dokumente fuer Verarbeitung frei via UseCase."""
        return self._uc_include.execute(documents)

    # ═══════════════════════════════════════════════════════════
    # Upload / Download
    # ═══════════════════════════════════════════════════════════

    def start_multi_upload(
        self, file_paths: list, source_type: str,
        progress_callback=None,
        file_finished_callback=None,
        file_error_callback=None,
        all_finished_callback=None,
    ) -> MultiUploadWorker:
        """Startet Multi-Upload Worker."""
        self._upload_worker = MultiUploadWorker(
            self._api_client, file_paths, source_type,
        )
        if progress_callback:
            self._upload_worker.progress.connect(progress_callback)
        if file_finished_callback:
            self._upload_worker.file_finished.connect(file_finished_callback)
        if file_error_callback:
            self._upload_worker.file_error.connect(file_error_callback)
        if all_finished_callback:
            self._upload_worker.all_finished.connect(all_finished_callback)
        self.register_worker(self._upload_worker)
        self._upload_worker.start()
        return self._upload_worker

    def start_multi_download(
        self, documents: List[Document], target_dir: str,
        progress_callback=None,
        file_finished_callback=None,
        file_error_callback=None,
        all_finished_callback=None,
    ) -> MultiDownloadWorker:
        """Startet Multi-Download Worker."""
        self._download_worker = MultiDownloadWorker(
            self._repo, documents, target_dir,
        )
        if progress_callback:
            self._download_worker.progress.connect(progress_callback)
        if file_finished_callback:
            self._download_worker.file_finished.connect(file_finished_callback)
        if file_error_callback:
            self._download_worker.file_error.connect(file_error_callback)
        if all_finished_callback:
            self._download_worker.all_finished.connect(all_finished_callback)
        self.register_worker(self._download_worker)
        self._download_worker.start()
        return self._download_worker

    def start_box_download(
        self, box_type: str, target_path: str, mode: str,
        progress_callback=None,
        finished_callback=None,
        status_callback=None,
        error_callback=None,
    ) -> BoxDownloadWorker:
        """Startet Box-Download Worker."""
        self._box_download_worker = BoxDownloadWorker(
            self._docs_api, box_type, target_path, mode,
        )
        if progress_callback:
            self._box_download_worker.progress.connect(progress_callback)
        if finished_callback:
            self._box_download_worker.finished.connect(finished_callback)
        if status_callback:
            self._box_download_worker.status.connect(status_callback)
        if error_callback:
            self._box_download_worker.error.connect(error_callback)
        self.register_worker(self._box_download_worker)
        self._box_download_worker.start()
        return self._box_download_worker

    def start_preview_download(
        self, doc_id: int, target_dir: str, *,
        filename: str = None,
        cache_dir: str = None,
        finished_callback=None,
        error_callback=None,
    ) -> PreviewDownloadWorker:
        """Startet Preview-Download Worker."""
        self._preview_worker = PreviewDownloadWorker(
            self._docs_api, doc_id, target_dir,
            filename=filename, cache_dir=cache_dir,
        )
        if finished_callback:
            self._preview_worker.download_finished.connect(finished_callback)
        if error_callback:
            self._preview_worker.download_error.connect(error_callback)
        self.register_worker(self._preview_worker)
        self._preview_worker.start()
        return self._preview_worker

    def download_single(self, doc: Document, target_dir: str):
        """Synchroner Einzel-Download mit Auto-Archivierung."""
        return self._uc_download.execute(doc, target_dir)

    # ═══════════════════════════════════════════════════════════
    # KI-Benennung
    # ═══════════════════════════════════════════════════════════

    def start_ai_rename(
        self, documents: List[Document],
        progress_callback=None,
        finished_callback=None,
        error_callback=None,
    ):
        """Startet KI-Benennung Worker."""
        from infrastructure.threading.archive_workers import AIRenameWorker
        self._ai_rename_worker = AIRenameWorker(
            self._api_client, self._repo, documents,
        )
        if progress_callback:
            self._ai_rename_worker.progress.connect(progress_callback)
        if finished_callback:
            self._ai_rename_worker.finished.connect(finished_callback)
        if error_callback:
            self._ai_rename_worker.error.connect(error_callback)
        self.register_worker(self._ai_rename_worker)
        self._ai_rename_worker.start()
        return self._ai_rename_worker

    def cancel_ai_rename(self) -> None:
        if self._ai_rename_worker:
            self._ai_rename_worker.cancel()

    # ═══════════════════════════════════════════════════════════
    # Automatische Verarbeitung
    # ═══════════════════════════════════════════════════════════

    def start_processing(
        self,
        progress_callback=None,
        finished_callback=None,
        error_callback=None,
    ) -> ProcessingWorker:
        """Startet den Verarbeitungs-Worker."""
        self._processing_worker = ProcessingWorker(self._api_client)
        if progress_callback:
            self._processing_worker.progress.connect(progress_callback)
        if finished_callback:
            self._processing_worker.finished.connect(finished_callback)
        if error_callback:
            self._processing_worker.error.connect(error_callback)
        self.register_worker(self._processing_worker)
        self._processing_worker.start()
        return self._processing_worker

    def cancel_processing(self) -> None:
        if self._processing_worker:
            self._processing_worker.cancel()

    def start_delayed_cost_check(
        self, batch_result, history_entry_id: int, *,
        delay_seconds: int = 90,
        countdown_callback=None,
        finished_callback=None,
    ) -> DelayedCostWorker:
        """Startet verzoegerten Kosten-Check."""
        self._delayed_cost_worker = DelayedCostWorker(
            self._api_client, batch_result, history_entry_id,
            delay_seconds=delay_seconds,
        )
        if countdown_callback:
            self._delayed_cost_worker.countdown.connect(countdown_callback)
        if finished_callback:
            self._delayed_cost_worker.finished.connect(finished_callback)
        self.register_worker(self._delayed_cost_worker)
        self._delayed_cost_worker.start()
        return self._delayed_cost_worker

    # ═══════════════════════════════════════════════════════════
    # SmartScan Worker
    # ═══════════════════════════════════════════════════════════

    def start_smartscan(
        self, mode: str, document_ids: list, *,
        box_type: str = None,
        archive_after: bool = False,
        recolor_after: bool = False,
        recolor_color: str = None,
        progress_callback=None,
        completed_callback=None,
        error_callback=None,
    ) -> SmartScanWorker:
        """Startet SmartScan Worker."""
        self._smartscan_worker = SmartScanWorker(
            self._api_client, self._repo, mode, document_ids=document_ids,
            box_type=box_type, archive_after=archive_after,
            recolor_after=recolor_after, recolor_color=recolor_color,
        )
        if progress_callback:
            self._smartscan_worker.progress.connect(progress_callback)
        if completed_callback:
            self._smartscan_worker.completed.connect(completed_callback)
        if error_callback:
            self._smartscan_worker.error.connect(error_callback)
        self.register_worker(self._smartscan_worker)
        self._smartscan_worker.start()
        return self._smartscan_worker

    def cancel_smartscan(self) -> None:
        if self._smartscan_worker:
            self._smartscan_worker.cancel()

    # ═══════════════════════════════════════════════════════════
    # Search
    # ═══════════════════════════════════════════════════════════

    def start_search(
        self, query: str, *,
        limit: int = 200,
        include_raw: bool = False,
        substring: bool = False,
        finished_callback=None,
        error_callback=None,
    ) -> SearchWorker:
        """Startet Such-Worker."""
        worker = SearchWorker(
            self._repo, query, limit=limit,
            include_raw=include_raw, substring=substring,
        )
        if finished_callback:
            worker.finished.connect(finished_callback)
        if error_callback:
            worker.error.connect(error_callback)
        self.register_worker(worker)
        worker.start()
        return worker

    # ═══════════════════════════════════════════════════════════
    # Domain-Regeln (Delegation)
    # ═══════════════════════════════════════════════════════════

    def get_move_targets(self, current_boxes: set) -> list:
        return archive_rules.get_move_targets(current_boxes, self.is_admin)

    def is_archivable(self, box_type: str) -> bool:
        return archive_rules.is_archivable(box_type)

    def should_auto_archive_on_download(self, box_type: str, is_archived: bool) -> bool:
        return archive_rules.should_auto_archive_on_download(box_type, is_archived)

    def is_excludable(self, box_type: str, processing_status: str) -> bool:
        return archive_rules.is_excludable_from_processing(box_type, processing_status)

    def is_reprocessable(self, box_type: str, processing_status: str) -> bool:
        return archive_rules.is_reprocessable(box_type, processing_status)

    def is_ai_renameable(self, box_type: str, is_pdf: bool, ai_renamed: bool) -> bool:
        return archive_rules.is_ai_renameable(box_type, is_pdf, ai_renamed)
