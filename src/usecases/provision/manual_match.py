"""
UseCase: Manuelles Matching / Zuordnung.
"""

from typing import Dict

from domain.provision.interfaces import IProvisionRepository


class ManualMatch:
    """Weist eine Provision manuell einem Vertrag zu."""

    def __init__(self, repository: IProvisionRepository):
        self._repo = repository

    def execute(self, commission_id: int, contract_id: int,
                force_override: bool = False) -> Dict:
        return self._repo.assign_contract(
            commission_id=commission_id,
            contract_id=contract_id,
            force_override=force_override,
        )
