"""
Presenter: Verteilschlüssel / Rollen.
"""

import logging
from typing import Optional

from domain.provision.interfaces import IDistributionView
from infrastructure.api.provision_repository import ProvisionRepository
from infrastructure.threading.provision_workers import (
    VerteilschluesselLoadWorker, SaveEmployeeWorker, SaveModelWorker,
)

logger = logging.getLogger(__name__)


class DistributionPresenter:
    """Presenter für das Verteilschlüssel-Panel."""

    def __init__(self, repository: ProvisionRepository):
        self._repo = repository
        self._view: Optional[IDistributionView] = None
        self._load_worker: Optional[VerteilschluesselLoadWorker] = None
        self._save_emp_worker: Optional[SaveEmployeeWorker] = None
        self._save_model_worker: Optional[SaveModelWorker] = None

    def set_view(self, view: IDistributionView) -> None:
        self._view = view

    def load_data(self) -> None:
        if self._view:
            self._view.show_loading(True)

        if self._load_worker and self._load_worker.isRunning():
            return

        self._load_worker = VerteilschluesselLoadWorker(self._repo)
        self._load_worker.finished.connect(self._on_data_loaded)
        self._load_worker.error.connect(self._on_error)
        self._load_worker.start()

    def _on_data_loaded(self, models, employees) -> None:
        if self._view:
            self._view.show_loading(False)
            self._view.show_models(models)
            self._view.show_employees(employees)

    def _on_error(self, error: str) -> None:
        logger.error(f"Verteilschlüssel-Fehler: {error}")
        if self._view:
            self._view.show_loading(False)
            self._view.show_error(error)

    def save_employee(self, emp_id: int, data: dict) -> None:
        if self._save_emp_worker and self._save_emp_worker.isRunning():
            return
        self._save_emp_worker = SaveEmployeeWorker(self._repo, emp_id, data)
        self._save_emp_worker.finished.connect(self._on_employee_saved)
        self._save_emp_worker.error.connect(self._on_error)
        self._save_emp_worker.start()

    def _on_employee_saved(self, success, summary) -> None:
        if success:
            self.refresh()
        if self._view and hasattr(self._view, 'on_employee_saved'):
            self._view.on_employee_saved(success, summary)

    def save_model(self, model_id: int, data: dict) -> None:
        if self._save_model_worker and self._save_model_worker.isRunning():
            return
        self._save_model_worker = SaveModelWorker(self._repo, model_id, data)
        self._save_model_worker.finished.connect(self._on_model_saved)
        self._save_model_worker.error.connect(self._on_error)
        self._save_model_worker.start()

    def _on_model_saved(self, success, summary) -> None:
        if success:
            self.refresh()
        if self._view and hasattr(self._view, 'on_model_saved'):
            self._view.on_model_saved(success, summary)

    def create_model(self, data: dict):
        return self._repo.create_model(data)

    def delete_model(self, model_id: int) -> bool:
        return self._repo.delete_model(model_id)

    def create_employee(self, data: dict):
        return self._repo.create_employee(data)

    def update_employee(self, emp_id: int, data: dict):
        return self._repo.update_employee(emp_id, data)

    def delete_employee(self, emp_id: int, hard: bool = False):
        return self._repo.delete_employee(emp_id, hard=hard)

    def refresh(self) -> None:
        self.load_data()

    def has_running_workers(self) -> bool:
        for w in (self._load_worker, self._save_emp_worker, self._save_model_worker):
            if w and w.isRunning():
                return True
        return False
