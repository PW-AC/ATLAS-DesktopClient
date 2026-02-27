"""
UseCase: Dashboard-Daten laden.
"""

from typing import Optional, Dict, Tuple

from domain.provision.entities import DashboardSummary
from domain.provision.interfaces import IProvisionRepository


class LoadDashboard:
    """Lädt Dashboard-KPIs und Klärfall-Counts."""

    def __init__(self, repository: IProvisionRepository):
        self._repo = repository

    def execute(
        self, *,
        von: str = None,
        bis: str = None,
    ) -> Tuple[Optional[DashboardSummary], Dict]:
        summary = self._repo.get_dashboard_summary(von=von, bis=bis)
        clearance = self._repo.get_clearance_counts(von=von, bis=bis)
        return summary, clearance
