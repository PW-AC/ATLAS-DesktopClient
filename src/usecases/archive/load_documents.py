"""
UseCase: Dokumente laden (Cache-basiert).
"""

from typing import List, Optional

from domain.archive.interfaces import IDocumentRepository
from domain.archive.entities import Document


class LoadDocuments:
    """Laedt Dokumente aus dem Repository, optional gefiltert nach Box und Archiv-Status."""

    def __init__(self, repository: IDocumentRepository):
        self._repo = repository

    def execute(
        self, *,
        box_type: Optional[str] = None,
        is_archived: Optional[bool] = None,
    ) -> List[Document]:
        return self._repo.list_documents(box_type=box_type, is_archived=is_archived)
