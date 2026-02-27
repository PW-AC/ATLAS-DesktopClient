"""
UseCase: Box-Statistiken laden.
"""

from domain.archive.interfaces import IDocumentRepository
from domain.archive.entities import BoxStats


class LoadBoxStats:
    """Laedt die aktuellen Statistiken fuer alle Boxen."""

    def __init__(self, repository: IDocumentRepository):
        self._repo = repository

    def execute(self) -> BoxStats:
        return self._repo.get_box_stats()
