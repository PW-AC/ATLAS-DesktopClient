"""
Presenter: Auszahlungen & Reports.
"""

import logging
from typing import Optional

from domain.provision.interfaces import IPayoutsView
from infrastructure.api.provision_repository import ProvisionRepository
from infrastructure.threading.provision_workers import (
    AuszahlungenLoadWorker, AuszahlungenPositionenWorker,
)

logger = logging.getLogger(__name__)


class PayoutsPresenter:
    """Presenter für das Auszahlungen-Panel."""

    def __init__(self, repository: ProvisionRepository):
        self._repo = repository
        self._view: Optional[IPayoutsView] = None
        self._load_worker: Optional[AuszahlungenLoadWorker] = None
        self._pos_worker: Optional[AuszahlungenPositionenWorker] = None

    def set_view(self, view: IPayoutsView) -> None:
        self._view = view

    def load_abrechnungen(self, monat: str) -> None:
        if self._view:
            self._view.show_loading(True)

        if self._load_worker and self._load_worker.isRunning():
            return

        self._load_worker = AuszahlungenLoadWorker(self._repo, monat)
        self._load_worker.finished.connect(self._on_loaded)
        self._load_worker.error.connect(self._on_error)
        self._load_worker.start()

    def _on_loaded(self, abrechnungen) -> None:
        if self._view:
            self._view.show_loading(False)
            self._view.show_abrechnungen(abrechnungen)

    def _on_error(self, error: str) -> None:
        logger.error(f"Auszahlungen-Fehler: {error}")
        if self._view:
            self._view.show_loading(False)
            self._view.show_error(error)

    def load_berater_positionen(self, berater_id: int, von: str, bis: str) -> None:
        if self._pos_worker and self._pos_worker.isRunning():
            return
        self._pos_worker = AuszahlungenPositionenWorker(
            self._repo, berater_id, von, bis)
        self._pos_worker.finished.connect(self._on_positions_loaded)
        self._pos_worker.error.connect(self._on_error)
        self._pos_worker.start()

    def _on_positions_loaded(self, berater_id, commissions) -> None:
        if self._view and hasattr(self._view, 'show_berater_positionen'):
            self._view.show_berater_positionen(berater_id, commissions)

    def get_abrechnungen(self, monat: str):
        return self._repo.get_abrechnungen(monat)

    def get_commissions(self, **kwargs):
        return self._repo.get_commissions(**kwargs)

    def generate_abrechnung(self, monat: str):
        return self._repo.generate_abrechnung(monat)

    def update_abrechnung_status(self, abrechnung_id: int, status: str):
        return self._repo.update_abrechnung_status(abrechnung_id, status)

    def refresh(self) -> None:
        pass

    def has_running_workers(self) -> bool:
        for w in (self._load_worker, self._pos_worker):
            if w and w.isRunning():
                return True
        return False
