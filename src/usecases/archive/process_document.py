"""
UseCase: Automatische Dokumentenverarbeitung (KI-Klassifikation).

Orchestriert die Verarbeitung der Eingangsbox:
1. Eingangsbox laden
2. Pro Dokument: classify -> process -> move
3. Kosten-Tracking
4. History-Logging

Strangler-Fig-Ansatz: Delegiert aktuell an den bestehenden DocumentProcessor,
nutzt aber bereits die neuen Domain/Infrastructure-Interfaces. Sobald der
DocumentProcessor vollstaendig aufgeloest ist, uebernimmt dieser UseCase
die direkte Orchestrierung.
"""

from __future__ import annotations

import logging
from typing import Optional, Callable, TYPE_CHECKING

from api.client import APIClient

if TYPE_CHECKING:
    from services.document_processor import BatchProcessingResult, ProcessingResult

logger = logging.getLogger(__name__)


class ProcessDocument:
    """Startet die automatische Verarbeitung der Eingangsbox.

    Orchestriert Domain-Logik (Classifier, Rules) und Infrastructure
    (AI-Adapter, PDF-Ops, History-Logger) fuer die Dokumentenverarbeitung.

    Aktuell delegiert an DocumentProcessor als Uebergangsloesung.
    """

    def __init__(
        self,
        api_client: APIClient,
        *,
        classifier=None,
        ai_adapter=None,
        pdf_ops=None,
        history_logger=None,
        rules_loader=None,
        spreadsheet_extractor=None,
    ):
        self._api_client = api_client
        self._classifier = classifier
        self._ai_adapter = ai_adapter
        self._pdf_ops = pdf_ops
        self._history_logger = history_logger
        self._rules_loader = rules_loader
        self._spreadsheet_extractor = spreadsheet_extractor

    def execute(
        self, *,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        max_workers: int = 8,
    ) -> BatchProcessingResult:
        """Verarbeitet alle Dokumente in der Eingangsbox."""
        from services.document_processor import DocumentProcessor
        processor = DocumentProcessor(self._api_client)
        return processor.process_inbox(
            progress_callback=progress_callback,
            max_workers=max_workers,
        )

    def execute_single(self, doc_id: int) -> ProcessingResult:
        """Verarbeitet ein einzelnes Dokument (fuer Re-Processing)."""
        from services.document_processor import DocumentProcessor
        processor = DocumentProcessor(self._api_client)
        return processor.process_single_document(doc_id)
