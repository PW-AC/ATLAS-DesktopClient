# domain/archive — Reine Business-Logik fuer das Dokumentenarchiv (kein Qt, kein HTTP)

from .entities import (
    Document, BoxStats, SearchResult,
    MoveResult, ColorResult, ArchiveResult,
    RenameResult, DeleteResult, UploadResult,
    DownloadResult, SmartScanResult, ProcessingToggleResult,
    DuplicateInfo,
)
from .interfaces import (
    IDocumentRepository, IHashService, IZipExtractor,
    ISmartScanAdapter, IPdfProcessor, IArchiveView,
)
from . import archive_rules
from . import document_classifier
from . import duplicate_detector
from . import naming_rules
from . import processing_rules

__all__ = [
    # Entities
    'Document', 'BoxStats', 'SearchResult',
    'MoveResult', 'ColorResult', 'ArchiveResult',
    'RenameResult', 'DeleteResult', 'UploadResult',
    'DownloadResult', 'SmartScanResult', 'ProcessingToggleResult',
    'DuplicateInfo',
    # Interfaces
    'IDocumentRepository', 'IHashService', 'IZipExtractor',
    'ISmartScanAdapter', 'IPdfProcessor', 'IArchiveView',
    # Submodule
    'archive_rules', 'document_classifier',
    'duplicate_detector', 'naming_rules', 'processing_rules',
]
