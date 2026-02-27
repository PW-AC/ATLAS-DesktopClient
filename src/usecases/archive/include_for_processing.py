"""
UseCase: Dokumente fuer die automatische Verarbeitung freigeben.

Verschiebt Dokumente zurueck in die Eingangsbox mit
processing_status='pending'.
"""

from typing import List

from domain.archive.interfaces import IDocumentRepository
from domain.archive.entities import Document, ProcessingToggleResult


class IncludeForProcessing:
    """Gibt Dokumente fuer die automatische Verarbeitung frei."""

    def __init__(self, repository: IDocumentRepository):
        self._repo = repository

    def execute(self, documents: List[Document]) -> ProcessingToggleResult:
        """Gibt Dokumente fuer Verarbeitung frei."""
        doc_ids = [d.id for d in documents]
        count = self._repo.move_documents(
            doc_ids, 'eingang',
            processing_status='pending',
        )
        return ProcessingToggleResult(
            changed_count=count,
            total_requested=len(documents),
            action='include',
        )
