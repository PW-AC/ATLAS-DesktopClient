"""
Presenter: Dashboard.

Vermittelt zwischen DashboardPanel (View) und UseCases.
"""

import logging
from typing import Optional

from domain.provision.entities import DashboardSummary
from domain.provision.interfaces import IDashboardView
from infrastructure.api.provision_repository import ProvisionRepository
from infrastructure.threading.provision_workers import (
    DashboardLoadWorker, BeraterDetailWorker,
)

logger = logging.getLogger(__name__)


class DashboardPresenter:
    """Presenter für das Dashboard-Panel."""

    def __init__(self, repository: ProvisionRepository):
        self._repo = repository
        self._view: Optional[IDashboardView] = None
        self._load_worker: Optional[DashboardLoadWorker] = None
        self._detail_worker: Optional[BeraterDetailWorker] = None

    def set_view(self, view: IDashboardView) -> None:
        self._view = view

    def load_dashboard(self, von: str = None, bis: str = None) -> None:
        if self._view:
            self._view.show_loading(True)

        if self._load_worker and self._load_worker.isRunning():
            self._load_worker.quit()
            self._load_worker.wait(2000)

        self._load_worker = DashboardLoadWorker(self._repo, von=von, bis=bis)
        self._load_worker.finished.connect(self._on_dashboard_loaded)
        self._load_worker.error.connect(self._on_load_error)
        self._load_worker.start()

    def _on_dashboard_loaded(self, summary, clearance) -> None:
        if self._view:
            self._view.show_loading(False)
            self._view.show_summary(summary)
            if summary:
                self._view.show_clearance_counts(clearance)

    def _on_load_error(self, error: str) -> None:
        logger.error(f"Dashboard-Fehler: {error}")
        if self._view:
            self._view.show_loading(False)
            self._view.show_error(error)

    def load_berater_detail(self, berater_id: int, berater_name: str,
                            row_data: dict, von: str = None, bis: str = None) -> None:
        if self._detail_worker and self._detail_worker.isRunning():
            return
        self._detail_worker = BeraterDetailWorker(
            self._repo, berater_id, berater_name, row_data, von=von, bis=bis)
        self._detail_worker.finished.connect(self._on_berater_detail)
        self._detail_worker.error.connect(self._on_load_error)
        self._detail_worker.start()

    def _on_berater_detail(self, berater_id, berater_name, row_data, detail) -> None:
        if self._view and hasattr(self._view, 'show_berater_detail'):
            self._view.show_berater_detail(berater_id, berater_name, row_data, detail)

    def refresh(self) -> None:
        self.load_dashboard()

    def has_running_workers(self) -> bool:
        for w in (self._load_worker, self._detail_worker):
            if w and w.isRunning():
                return True
        return False
