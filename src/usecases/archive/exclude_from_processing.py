"""
UseCase: Dokumente von der automatischen Verarbeitung ausschliessen.

Eingangs-Dokumente werden nach 'sonstige' verschoben.
Dokumente in anderen Boxen behalten ihre Box, erhalten aber
processing_status='manual_excluded'.
"""

from typing import List

from domain.archive.interfaces import IDocumentRepository
from domain.archive.entities import Document, ProcessingToggleResult


class ExcludeFromProcessing:
    """Schliesst Dokumente von der automatischen Verarbeitung aus."""

    def __init__(self, repository: IDocumentRepository):
        self._repo = repository

    def execute(self, documents: List[Document]) -> ProcessingToggleResult:
        """Schliesst Dokumente von der Verarbeitung aus."""
        count = 0

        eingang_docs = [d for d in documents if d.box_type == 'eingang']
        if eingang_docs:
            eingang_ids = [d.id for d in eingang_docs]
            moved = self._repo.move_documents(
                eingang_ids, 'sonstige',
                processing_status='manual_excluded',
            )
            count += moved

        other_docs = [d for d in documents if d.box_type != 'eingang']
        for doc in other_docs:
            if self._repo.update(doc.id, processing_status='manual_excluded'):
                count += 1

        return ProcessingToggleResult(
            changed_count=count,
            total_requested=len(documents),
            action='exclude',
        )
