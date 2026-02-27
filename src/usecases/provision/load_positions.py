"""
UseCase: Provisionspositionen laden.

Orchestriert Repository-Zugriff und Relevanz-Filterung.
"""

from typing import Optional, List, Tuple

from domain.provision.entities import Commission, PaginationInfo
from domain.provision.interfaces import IProvisionRepository


class LoadPositions:
    """Lädt Provisionspositionen mit optionaler Relevanz-Filterung."""

    def __init__(self, repository: IProvisionRepository):
        self._repo = repository

    def execute(
        self, *,
        berater_id: int = None,
        match_status: str = None,
        von: str = None,
        bis: str = None,
        versicherer: str = None,
        q: str = None,
        only_relevant: bool = True,
        page: int = None,
        per_page: int = None,
        limit: int = 500,
    ) -> Tuple[List[Commission], Optional[PaginationInfo]]:
        return self._repo.get_commissions(
            berater_id=berater_id,
            match_status=match_status,
            von=von,
            bis=bis,
            versicherer=versicherer,
            q=q,
            is_relevant=True if only_relevant else None,
            page=page,
            per_page=per_page,
            limit=limit,
        )
