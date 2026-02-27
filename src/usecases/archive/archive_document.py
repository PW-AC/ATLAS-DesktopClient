"""
UseCase: Dokumente archivieren / entarchivieren.
"""

from typing import List

from domain.archive.interfaces import IDocumentRepository
from domain.archive.entities import Document, ArchiveResult
from domain.archive import archive_rules


class ArchiveDocuments:
    """Archiviert oder entarchiviert Dokumente (Bulk)."""

    def __init__(self, repository: IDocumentRepository):
        self._repo = repository

    def execute(self, documents: List[Document], *, action: str = 'archive') -> ArchiveResult:
        """Einheitlicher Einstiegspunkt: action='archive' oder 'unarchive'."""
        if action == 'unarchive':
            return self._unarchive(documents)
        return self._archive(documents)

    def _archive(self, documents: List[Document]) -> ArchiveResult:
        archivable = [d for d in documents if archive_rules.is_archivable(d.box_type)]
        if not archivable:
            return ArchiveResult(changed_count=0, action='archive')

        doc_ids = [d.id for d in archivable]
        count = self._repo.archive_documents(doc_ids)

        return ArchiveResult(
            changed_count=count,
            action='archive',
            doc_ids=doc_ids,
            affected_boxes=list({d.box_type for d in archivable}),
        )

    def _unarchive(self, documents: List[Document]) -> ArchiveResult:
        doc_ids = [d.id for d in documents]
        count = self._repo.unarchive_documents(doc_ids)

        return ArchiveResult(
            changed_count=count,
            action='unarchive',
            doc_ids=doc_ids,
            affected_boxes=list({d.box_type for d in documents}),
        )
