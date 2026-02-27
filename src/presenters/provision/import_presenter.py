"""
Presenter: Import / Abrechnungsläufe.

Vermittelt zwischen AbrechnungslaeufPanel (View) und UseCases.
"""

import logging
from typing import Optional, List, Dict

from domain.provision.interfaces import IImportView
from infrastructure.api.provision_repository import ProvisionRepository
from infrastructure.threading.provision_workers import (
    VuBatchesLoadWorker, VuParseFileWorker, VuImportWorker,
)

logger = logging.getLogger(__name__)


class ImportPresenter:
    """Presenter für das Import/Abrechnungsläufe-Panel."""

    def __init__(self, repository: ProvisionRepository):
        self._repo = repository
        self._view: Optional[IImportView] = None
        self._batches_worker: Optional[VuBatchesLoadWorker] = None
        self._parse_worker: Optional[VuParseFileWorker] = None
        self._import_worker: Optional[VuImportWorker] = None

    def set_view(self, view: IImportView) -> None:
        self._view = view

    def load_batches(self) -> None:
        if self._view:
            self._view.show_loading(True)

        if self._batches_worker and self._batches_worker.isRunning():
            return

        self._batches_worker = VuBatchesLoadWorker(self._repo)
        self._batches_worker.finished.connect(self._on_batches_loaded)
        self._batches_worker.error.connect(self._on_error)
        self._batches_worker.start()

    def _on_batches_loaded(self, batches) -> None:
        if self._view:
            self._view.show_loading(False)
            self._view.show_batches(batches)

    def _on_error(self, error: str) -> None:
        logger.error(f"Import-Fehler: {error}")
        if self._view:
            self._view.show_loading(False)
            self._view.show_error(error)

    def parse_file(self, filepath: str) -> None:
        if self._parse_worker and self._parse_worker.isRunning():
            return
        self._parse_worker = VuParseFileWorker(filepath)
        self._parse_worker.finished.connect(self._on_parse_done)
        self._parse_worker.error.connect(self._on_error)
        self._parse_worker.start()

    def _on_parse_done(self, rows, vu_name, sheet_name, log_text) -> None:
        if self._view:
            self._view.show_parse_progress(log_text)
            if hasattr(self._view, 'on_parse_complete'):
                self._view.on_parse_complete(rows, vu_name, sheet_name)

    def start_import(self, rows: List[Dict], filename: str,
                     sheet_name: str, vu_name: str, file_hash: str) -> None:
        if self._import_worker and self._import_worker.isRunning():
            return
        self._import_worker = VuImportWorker(
            self._repo, rows, filename, sheet_name, vu_name, file_hash)
        self._import_worker.progress.connect(self._on_import_progress)
        self._import_worker.finished.connect(self._on_import_done)
        self._import_worker.error.connect(self._on_error)
        self._import_worker.start()

    def _on_import_progress(self, message: str) -> None:
        if self._view:
            self._view.show_parse_progress(message)

    def _on_import_done(self, result) -> None:
        if self._view:
            self._view.show_import_result(result)

    def refresh(self) -> None:
        self.load_batches()

    def has_running_workers(self) -> bool:
        for w in (self._batches_worker, self._parse_worker, self._import_worker):
            if w and w.isRunning():
                return True
        return False
