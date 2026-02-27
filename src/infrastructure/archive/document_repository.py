"""
Infrastructure-Adapter: DocumentsAPI -> IDocumentRepository.

Wrappt die bestehende DocumentsAPI-Klasse und implementiert
das Domain-Interface. Konvertiert zwischen API-Datenformaten
und Domain-Entitaeten wo noetig.
"""

import logging
from typing import Optional, List, Dict, Tuple, Any

from api.client import APIClient
from api.documents import DocumentsAPI, Document, BoxStats, SearchResult

logger = logging.getLogger(__name__)


class DocumentRepository:
    """Implementiert IDocumentRepository.

    Fassade fuer den bestehenden DocumentsAPI-Client.
    """

    def __init__(self, client: APIClient):
        self._client = client
        self._api = DocumentsAPI(client)

    @property
    def api(self) -> DocumentsAPI:
        """Zugriff auf die zugrundeliegende API (fuer Worker die direkten Zugriff benoetigen)."""
        return self._api

    def list_documents(
        self, *,
        box_type: Optional[str] = None,
        is_archived: Optional[bool] = None,
    ) -> List[Document]:
        return self._api.list_documents(box_type=box_type, is_archived=is_archived)

    def get_document(self, doc_id: int) -> Optional[Document]:
        return self._api.get_document(doc_id)

    def search_documents(
        self, query: str, *,
        limit: int = 200,
        include_raw: bool = False,
        substring: bool = False,
    ) -> List[SearchResult]:
        return self._api.search_documents(
            query, limit=limit,
            include_raw=include_raw, substring=substring,
        )

    def get_box_stats(self) -> BoxStats:
        return self._api.get_box_stats()

    def upload(
        self, file_path: str, *,
        source_type: str = 'manual_upload',
        box_type: Optional[str] = None,
    ) -> Optional[Document]:
        if box_type:
            return self._api.upload(file_path, source_type, box_type=box_type)
        return self._api.upload(file_path, source_type)

    def download(
        self, doc_id: int, target_dir: str, *,
        filename_override: Optional[str] = None,
    ) -> Optional[str]:
        return self._api.download(doc_id, target_dir, filename_override=filename_override)

    def delete(self, doc_id: int) -> bool:
        return self._api.delete(doc_id)

    def delete_documents(self, doc_ids: List[int]) -> int:
        return self._api.delete_documents(doc_ids)

    def move_documents(
        self, doc_ids: List[int], target_box: str, *,
        reason: Optional[str] = None,
        processing_status: Optional[str] = None,
    ) -> int:
        return self._api.move_documents(
            doc_ids, target_box, processing_status=processing_status,
        )

    def rename_document(
        self, doc_id: int, new_filename: str, *,
        mark_ai_renamed: bool = False,
    ) -> bool:
        return self._api.rename_document(doc_id, new_filename, mark_ai_renamed=mark_ai_renamed)

    def update(self, doc_id: int, **fields: Any) -> bool:
        return self._api.update(doc_id, **fields)

    def archive_document(self, doc_id: int) -> bool:
        return self._api.archive_document(doc_id)

    def unarchive_document(self, doc_id: int) -> bool:
        return self._api.unarchive_document(doc_id)

    def archive_documents(self, doc_ids: List[int]) -> int:
        return self._api.archive_documents(doc_ids)

    def unarchive_documents(self, doc_ids: List[int]) -> int:
        return self._api.unarchive_documents(doc_ids)

    def set_document_color(self, doc_id: int, color: Optional[str]) -> bool:
        return self._api.set_document_color(doc_id, color)

    def set_documents_color(self, doc_ids: List[int], color: Optional[str]) -> int:
        return self._api.set_documents_color(doc_ids, color)

    def get_document_history(self, doc_id: int) -> Optional[List[Dict]]:
        return self._api.get_document_history(doc_id)

    def save_ai_data(self, doc_id: int, data: Dict[str, Any]) -> bool:
        return self._api.save_ai_data(doc_id, data)

    def get_ai_data(self, doc_id: int) -> Optional[Dict[str, Any]]:
        return self._api.get_ai_data(doc_id)

    def get_missing_ai_data_documents(self) -> List[Dict]:
        return self._api.get_missing_ai_data_documents()

    def replace_document_file(self, doc_id: int, file_path: str) -> bool:
        return self._api.replace_document_file(doc_id, file_path)

    def get_credits(self) -> Optional[Dict]:
        """Laedt OpenRouter-Credits."""
        try:
            from api.openrouter import OpenRouterClient
            client = OpenRouterClient(self._client)
            return client.get_credits()
        except Exception as e:
            logger.warning(f"Credits laden fehlgeschlagen: {e}")
            return None

    def get_cost_stats(self) -> Optional[float]:
        """Laedt durchschnittliche Verarbeitungskosten."""
        try:
            from api.processing_history import ProcessingHistoryAPI
            history_api = ProcessingHistoryAPI(self._client)
            stats = history_api.get_cost_stats()
            if stats and 'avg_cost_per_document_usd' in stats:
                return float(stats['avg_cost_per_document_usd'])
            return None
        except Exception as e:
            logger.warning(f"Kosten-Stats laden fehlgeschlagen: {e}")
            return None
