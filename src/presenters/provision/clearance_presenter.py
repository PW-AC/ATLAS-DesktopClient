"""
Presenter: Klärfälle / Zuordnung.

Vermittelt zwischen ZuordnungPanel (View) und UseCases.
"""

import logging
from typing import Optional

from domain.provision.interfaces import IClearanceView
from infrastructure.api.provision_repository import ProvisionRepository
from infrastructure.threading.provision_workers import (
    ClearanceLoadWorker, MappingSyncWorker, MatchSearchWorker,
)

logger = logging.getLogger(__name__)


class ClearancePresenter:
    """Presenter für das Zuordnung/Klärfälle-Panel."""

    def __init__(self, repository: ProvisionRepository):
        self._repo = repository
        self._view: Optional[IClearanceView] = None
        self._load_worker: Optional[ClearanceLoadWorker] = None
        self._mapping_worker: Optional[MappingSyncWorker] = None
        self._match_worker: Optional[MatchSearchWorker] = None

    def set_view(self, view: IClearanceView) -> None:
        self._view = view

    def load_clearance(self) -> None:
        if self._view:
            self._view.show_loading(True)

        if self._load_worker and self._load_worker.isRunning():
            self._load_worker.quit()
            self._load_worker.wait(2000)

        self._load_worker = ClearanceLoadWorker(self._repo)
        self._load_worker.finished.connect(self._on_clearance_loaded)
        self._load_worker.error.connect(self._on_error)
        self._load_worker.start()

    def _on_clearance_loaded(self, commissions, mappings_data) -> None:
        if self._view:
            self._view.show_loading(False)
            self._view.show_commissions(commissions)
            mappings = mappings_data.get('mappings', [])
            unmapped = mappings_data.get('unmapped', [])
            self._view.show_mappings(mappings, unmapped)

    def _on_error(self, error: str) -> None:
        logger.error(f"Klärfälle-Fehler: {error}")
        if self._view:
            self._view.show_loading(False)
            self._view.show_error(error)

    def create_mapping_and_rematch(self, primary_name: str, berater_id: int,
                                    also_vu_name: str = None) -> None:
        if self._mapping_worker and self._mapping_worker.isRunning():
            return
        self._mapping_worker = MappingSyncWorker(
            self._repo, primary_name, berater_id, also_vu_name)
        self._mapping_worker.finished.connect(self._on_mapping_done)
        self._mapping_worker.error.connect(self._on_error)
        self._mapping_worker.start()

    def _on_mapping_done(self, stats) -> None:
        self.refresh()

    def search_match_suggestions(self, commission_id: int, q: str = None) -> None:
        if self._match_worker and self._match_worker.isRunning():
            return
        self._match_worker = MatchSearchWorker(self._repo, commission_id, q)
        self._match_worker.finished.connect(self._on_suggestions)
        self._match_worker.error.connect(self._on_error)
        self._match_worker.start()

    def _on_suggestions(self, suggestions, commission) -> None:
        if self._view and hasattr(self._view, 'show_match_suggestions'):
            self._view.show_match_suggestions(suggestions, commission)

    def trigger_auto_match(self, batch_id: int = None):
        return self._repo.trigger_auto_match(batch_id)

    def get_commissions(self, **kwargs):
        return self._repo.get_commissions(**kwargs)

    def get_mappings(self, **kwargs):
        return self._repo.get_mappings(**kwargs)

    def get_employees(self):
        return self._repo.get_employees()

    def create_mapping(self, name: str, berater_id: int):
        return self._repo.create_mapping(name, berater_id)

    def delete_mapping(self, mapping_id: int) -> bool:
        return self._repo.delete_mapping(mapping_id)

    def match_commission(self, commission_id: int, contract_id: int,
                         berater_id: int = None) -> bool:
        return self._repo.match_commission(commission_id, contract_id, berater_id)

    def ignore_commission(self, commission_id: int) -> bool:
        return self._repo.ignore_commission(commission_id)

    def get_match_suggestions(self, commission_id: int, **kwargs):
        return self._repo.get_match_suggestions(commission_id, **kwargs)

    def assign_contract(self, commission_id: int, contract_id: int,
                        force_override: bool = False):
        return self._repo.assign_contract(commission_id, contract_id, force_override)

    def refresh(self) -> None:
        self.load_clearance()

    def has_running_workers(self) -> bool:
        for w in (self._load_worker, self._mapping_worker, self._match_worker):
            if w and w.isRunning():
                return True
        return False
