"""
UseCase: Auto-Match auslösen.
"""

from typing import Dict, Optional

from domain.provision.interfaces import IImportRepository


class AutoMatch:
    """Triggert automatisches Matching für einen Import-Batch."""

    def __init__(self, repository: IImportRepository):
        self._repo = repository

    def execute(self, batch_id: int = None) -> Dict:
        return self._repo.trigger_auto_match(batch_id=batch_id)
