"""
UseCase: Dokument umbenennen (manuell).
"""

from domain.archive.interfaces import IDocumentRepository
from domain.archive.entities import Document, RenameResult
from domain.archive import archive_rules, naming_rules


class RenameDocument:
    """Benennt ein Dokument manuell um."""

    def __init__(self, repository: IDocumentRepository):
        self._repo = repository

    def execute(
        self, doc: Document, new_name_without_ext: str,
    ) -> RenameResult:
        validation_error = naming_rules.validate_new_name(new_name_without_ext)
        if validation_error:
            return RenameResult(
                success=False,
                doc_id=doc.id,
                new_filename=doc.original_filename,
            )

        new_name = naming_rules.build_renamed_filename(
            new_name_without_ext.strip(), doc.original_filename,
        )

        if naming_rules.is_name_unchanged(new_name, doc.original_filename):
            return RenameResult(
                success=True,
                doc_id=doc.id,
                new_filename=new_name,
            )

        success = self._repo.rename_document(doc.id, new_name, mark_ai_renamed=False)
        excluded = False

        if success and archive_rules.should_exclude_on_rename(doc.box_type):
            self._repo.update(doc.id, processing_status='manual_excluded')
            excluded = True

        return RenameResult(
            success=success,
            doc_id=doc.id,
            new_filename=new_name,
            excluded_from_processing=excluded,
        )
