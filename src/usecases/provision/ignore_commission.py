"""
UseCase: Provision ignorieren.
"""

from domain.provision.interfaces import IProvisionRepository


class IgnoreCommission:
    """Markiert eine Provision als 'ignoriert'."""

    def __init__(self, repository: IProvisionRepository):
        self._repo = repository

    def execute(self, commission_id: int) -> bool:
        return self._repo.ignore_commission(commission_id)
