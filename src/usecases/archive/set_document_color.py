"""
UseCase: Farbmarkierung fuer Dokumente setzen/entfernen.
"""

from typing import List, Optional

from domain.archive.interfaces import IDocumentRepository
from domain.archive.entities import Document, ColorResult


class SetDocumentColor:
    """Setzt oder entfernt die Farbmarkierung fuer Dokumente."""

    def __init__(self, repository: IDocumentRepository):
        self._repo = repository

    def execute(
        self, documents: List[Document], color: Optional[str],
    ) -> ColorResult:
        doc_ids = [d.id for d in documents]
        count = self._repo.set_documents_color(doc_ids, color)

        return ColorResult(
            changed_count=count,
            color=color,
            doc_ids=doc_ids,
        )
