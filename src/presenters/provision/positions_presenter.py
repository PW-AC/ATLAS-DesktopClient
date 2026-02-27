"""
Presenter: Provisionspositionen.

Vermittelt zwischen ProvisionspositionenPanel (View) und UseCases.
Formatiert Daten für die Anzeige, hält Filter-State.
"""

import logging
from typing import Optional, List

from domain.provision.entities import Commission, PaginationInfo
from domain.provision.interfaces import IPositionsView
from infrastructure.api.provision_repository import ProvisionRepository
from infrastructure.threading.provision_workers import (
    PositionsLoadWorker, AuditLoadWorker, IgnoreWorker,
)

logger = logging.getLogger(__name__)


class PositionsPresenter:
    """Presenter für das Provisionspositionen-Panel."""

    def __init__(self, repository: ProvisionRepository):
        self._repo = repository
        self._view: Optional[IPositionsView] = None
        self._load_worker: Optional[PositionsLoadWorker] = None
        self._audit_worker: Optional[AuditLoadWorker] = None
        self._ignore_worker: Optional[IgnoreWorker] = None

        self._only_relevant: bool = True
        self._current_filters: dict = {}

    def set_view(self, view: IPositionsView) -> None:
        self._view = view

    @property
    def only_relevant(self) -> bool:
        return self._only_relevant

    @only_relevant.setter
    def only_relevant(self, value: bool) -> None:
        self._only_relevant = value

    def load_positions(self, **filters) -> None:
        """Startet das asynchrone Laden der Positionen."""
        self._current_filters = filters
        if self._view:
            self._view.show_loading(True)

        if self._load_worker and self._load_worker.isRunning():
            self._load_worker.quit()
            self._load_worker.wait(2000)

        self._load_worker = PositionsLoadWorker(
            self._repo,
            is_relevant=True if self._only_relevant else None,
            **filters,
        )
        self._load_worker.finished.connect(self._on_positions_loaded)
        self._load_worker.error.connect(self._on_load_error)
        self._load_worker.start()

    def _on_positions_loaded(self, commissions: List[Commission],
                              pagination: Optional[PaginationInfo]) -> None:
        if self._view:
            self._view.show_loading(False)
            self._view.show_commissions(commissions, pagination)

    def _on_load_error(self, error: str) -> None:
        logger.error(f"Fehler beim Laden der Positionen: {error}")
        if self._view:
            self._view.show_loading(False)
            self._view.show_error(error)

    def load_audit(self, commission_id: int) -> None:
        """Lädt Audit-Log für eine Commission."""
        if self._audit_worker and self._audit_worker.isRunning():
            return
        self._audit_worker = AuditLoadWorker(self._repo, commission_id)
        self._audit_worker.finished.connect(self._on_audit_loaded)
        self._audit_worker.start()

    def _on_audit_loaded(self, comm_id: int, entries: list) -> None:
        if self._view and hasattr(self._view, 'show_audit'):
            self._view.show_audit(comm_id, entries)

    def ignore_commission(self, commission_id: int) -> None:
        """Markiert eine Commission als ignoriert."""
        if self._ignore_worker and self._ignore_worker.isRunning():
            return
        self._ignore_worker = IgnoreWorker(self._repo, commission_id)
        self._ignore_worker.finished.connect(self._on_ignore_finished)
        self._ignore_worker.error.connect(self._on_load_error)
        self._ignore_worker.start()

    def _on_ignore_finished(self, success: bool) -> None:
        if success:
            self.refresh()

    def get_commissions(self, **kwargs):
        return self._repo.get_commissions(**kwargs)

    def get_employees(self):
        return self._repo.get_employees()

    def create_mapping(self, name: str, berater_id: int):
        return self._repo.create_mapping(name, berater_id)

    def trigger_auto_match(self, batch_id: int = None):
        return self._repo.trigger_auto_match(batch_id)

    def get_audit_log(self, **kwargs):
        return self._repo.get_audit_log(**kwargs)

    def get_match_suggestions(self, commission_id: int, **kwargs):
        return self._repo.get_match_suggestions(commission_id, **kwargs)

    def assign_contract(self, commission_id: int, contract_id: int,
                        force_override: bool = False):
        return self._repo.assign_contract(commission_id, contract_id, force_override)

    def refresh(self) -> None:
        """Aktuelle Ansicht neu laden."""
        self.load_positions(**self._current_filters)

    def toggle_relevance(self) -> None:
        """Relevanz-Filter umschalten und neu laden."""
        self._only_relevant = not self._only_relevant
        self.refresh()

    def has_running_workers(self) -> bool:
        for w in (self._load_worker, self._audit_worker, self._ignore_worker):
            if w and w.isRunning():
                return True
        return False
