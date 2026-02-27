# usecases/archive — Anwendungslogik fuer das Dokumentenarchiv (kein Qt)

from .load_documents import LoadDocuments
from .load_box_stats import LoadBoxStats
from .upload_document import UploadDocument
from .download_document import DownloadDocument
from .search_documents import SearchDocuments
from .process_document import ProcessDocument
from .smartscan_send import SmartScanSend
from .move_document import MoveDocument
from .archive_document import ArchiveDocuments
from .rename_document import RenameDocument
from .delete_document import DeleteDocument
from .set_document_color import SetDocumentColor
from .exclude_from_processing import ExcludeFromProcessing
from .include_for_processing import IncludeForProcessing

__all__ = [
    'LoadDocuments',
    'LoadBoxStats',
    'UploadDocument',
    'DownloadDocument',
    'SearchDocuments',
    'ProcessDocument',
    'SmartScanSend',
    'MoveDocument',
    'ArchiveDocuments',
    'RenameDocument',
    'DeleteDocument',
    'SetDocumentColor',
    'ExcludeFromProcessing',
    'IncludeForProcessing',
]
