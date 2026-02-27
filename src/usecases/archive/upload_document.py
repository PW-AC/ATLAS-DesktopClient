"""
UseCase: Dokument hochladen.
"""

import os

from domain.archive.interfaces import IDocumentRepository
from domain.archive.entities import UploadResult


class UploadDocument:
    """Laedt ein einzelnes Dokument in die Eingangsbox hoch."""

    def __init__(self, repository: IDocumentRepository):
        self._repo = repository

    def execute(
        self, file_path: str, *,
        source_type: str = 'manual_upload',
        box_type: str = None,
    ) -> UploadResult:
        doc = self._repo.upload(file_path, source_type=source_type, box_type=box_type)
        if doc:
            return UploadResult(
                success=True,
                filename=doc.original_filename,
                document=doc,
                is_duplicate=doc.is_duplicate,
            )
        from i18n.de import WORKER_UPLOAD_FAILED
        return UploadResult(
            success=False,
            filename=os.path.basename(file_path),
            error=WORKER_UPLOAD_FAILED,
        )
