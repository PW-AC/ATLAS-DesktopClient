"""
UseCase: Dokumente loeschen.
"""

from typing import List, Union

from domain.archive.interfaces import IDocumentRepository
from domain.archive.entities import Document, DeleteResult


class DeleteDocument:
    """Loescht ein oder mehrere Dokumente."""

    def __init__(self, repository: IDocumentRepository):
        self._repo = repository

    def execute(self, documents: Union[Document, List[Document]]) -> DeleteResult:
        """Loescht ein einzelnes oder mehrere Dokumente."""
        if isinstance(documents, Document):
            documents = [documents]

        if len(documents) == 1:
            success = self._repo.delete(documents[0].id)
            return DeleteResult(deleted_count=1 if success else 0, total_requested=1)

        doc_ids = [d.id for d in documents]
        deleted = self._repo.delete_documents(doc_ids)
        return DeleteResult(deleted_count=deleted, total_requested=len(doc_ids))
