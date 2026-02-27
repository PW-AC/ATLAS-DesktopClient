"""
UseCase: Dokumente verschieben.
"""

from typing import List, Optional

from domain.archive.interfaces import IDocumentRepository
from domain.archive.entities import Document, MoveResult


class MoveDocument:
    """Verschiebt Dokumente in eine andere Box."""

    def __init__(self, repository: IDocumentRepository):
        self._repo = repository

    def execute(
        self, documents: List[Document], target_box: str, *,
        processing_status: Optional[str] = None,
    ) -> MoveResult:
        doc_ids = [d.id for d in documents]
        original_boxes = list({d.box_type for d in documents})

        moved = self._repo.move_documents(
            doc_ids, target_box,
            processing_status=processing_status,
        )

        return MoveResult(
            moved_count=moved,
            target_box=target_box,
            total_requested=len(doc_ids),
            doc_ids=doc_ids,
            original_boxes=original_boxes,
        )
