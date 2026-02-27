"""
Adapter fuer KI-basierte Dokumenten-Klassifikation.

Kapselt OpenRouterClient-Aufrufe, Caching und Settings-Verwaltung
fuer die zweistufige KI-Klassifikation (Triage + Detail).
"""

import logging
import tempfile
import threading
from typing import Optional

from api.client import APIClient
from api.documents import DocumentsAPI
from api.openrouter import OpenRouterClient, DocumentClassification
from api.processing_settings import ProcessingSettingsAPI

__all__ = ['AiClassificationAdapter']

logger = logging.getLogger(__name__)


class AiClassificationAdapter:
    """
    Wrapper um OpenRouterClient fuer Dokumenten-Klassifikation.

    Thread-safe durch Lock auf dem Klassifikations-Cache.
    Settings werden einmal pro Instanz-Lebensdauer geladen und gecacht.
    """

    def __init__(self, api_client: APIClient) -> None:
        self._api_client = api_client
        self._docs_api = DocumentsAPI(api_client)
        self._settings_api = ProcessingSettingsAPI(api_client)
        self._openrouter: Optional[OpenRouterClient] = None

        self._classification_cache: dict = {}
        self._cache_lock = threading.Lock()

        self._ai_settings: Optional[dict] = None

    # ------------------------------------------------------------------
    # Lazy init
    # ------------------------------------------------------------------

    def _get_openrouter(self) -> OpenRouterClient:
        """Lazy-Init des OpenRouter-Clients."""
        if self._openrouter is None:
            self._openrouter = OpenRouterClient(self._api_client)
        return self._openrouter

    # ------------------------------------------------------------------
    # Cache (thread-safe)
    # ------------------------------------------------------------------

    def get_cached(self, content_hash: Optional[str]) -> Optional[dict]:
        """
        Prueft ob eine Klassifikation fuer diesen Content-Hash bereits im Cache liegt.

        Kostenoptimierung: Identische Dokumente werden nur 1x per KI klassifiziert.

        Args:
            content_hash: SHA256-Hash des Dokument-Inhalts

        Returns:
            Cached Klassifikations-dict oder None
        """
        if not content_hash:
            return None
        with self._cache_lock:
            return self._classification_cache.get(content_hash)

    def cache_result(self, content_hash: Optional[str], result: dict) -> None:
        """
        Speichert eine Klassifikation im Cache fuer Deduplizierung.

        Args:
            content_hash: SHA256-Hash des Dokument-Inhalts
            result: Klassifikations-Ergebnis als dict
        """
        if not content_hash:
            return
        with self._cache_lock:
            self._classification_cache[content_hash] = result
            logger.debug(f"Klassifikation gecached fuer Hash {content_hash[:12]}...")

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    def load_settings(self) -> dict:
        """
        Laedt KI-Einstellungen vom Server (einmal pro Verarbeitungslauf).

        Cached das Ergebnis in self._ai_settings, damit nicht pro Dokument
        ein API-Call gemacht wird.

        Returns:
            Dict mit stage1_*, stage2_* Feldern oder leeres Dict bei Fehler
        """
        if self._ai_settings is not None:
            return self._ai_settings

        try:
            self._ai_settings = self._settings_api.get_ai_settings()
            if self._ai_settings:
                logger.info(
                    f"KI-Settings geladen: S1={self._ai_settings.get('stage1_model')}, "
                    f"S2={'aktiv' if self._ai_settings.get('stage2_enabled') else 'deaktiviert'} "
                    f"({self._ai_settings.get('stage2_model')})"
                )
            else:
                logger.warning("KI-Settings leer, verwende Defaults")
                self._ai_settings = {}
        except Exception as e:
            logger.warning(f"KI-Settings konnten nicht geladen werden, verwende Defaults: {e}")
            self._ai_settings = {}

        return self._ai_settings

    def get_classify_kwargs(self, settings: Optional[dict] = None) -> dict:
        """
        Erstellt die kwargs fuer classify_sparte_with_date() aus den geladenen Settings.

        Args:
            settings: Optionale Settings; wenn None werden sie via load_settings() geladen.

        Returns:
            Dict mit stage1_*, stage2_* Parametern oder leeres Dict (Defaults)
        """
        if settings is None:
            settings = self.load_settings()
        if not settings:
            return {}

        kwargs: dict = {}

        # Stufe 1
        if settings.get('stage1_prompt'):
            kwargs['stage1_prompt'] = settings['stage1_prompt']
        if settings.get('stage1_model'):
            kwargs['stage1_model'] = settings['stage1_model']
        if settings.get('stage1_max_tokens'):
            kwargs['stage1_max_tokens'] = int(settings['stage1_max_tokens'])

        # Stufe 2
        kwargs['stage2_enabled'] = bool(settings.get('stage2_enabled', True))
        if settings.get('stage2_prompt'):
            kwargs['stage2_prompt'] = settings['stage2_prompt']
        if settings.get('stage2_model'):
            kwargs['stage2_model'] = settings['stage2_model']
        if settings.get('stage2_max_tokens'):
            kwargs['stage2_max_tokens'] = int(settings['stage2_max_tokens'])
        if settings.get('stage2_trigger'):
            kwargs['stage2_trigger'] = settings['stage2_trigger']

        return kwargs

    # ------------------------------------------------------------------
    # Klassifikation
    # ------------------------------------------------------------------

    def classify_pdf(self, doc_id: int, pdf_path: Optional[str] = None) -> Optional[DocumentClassification]:
        """
        Klassifiziert ein PDF mit dem zweistufigen KI-System.

        Stufe 1 (Triage): Schnelle Kategorisierung mit GPT-4o-mini
        Stufe 2 (Detail): Nur bei courtage/versicherung mit GPT-4o

        Bei 'sonstige' in Stufe 1 wird KEINE teure Detailanalyse gemacht.

        Args:
            doc_id: Dokument-ID fuer den Download (falls pdf_path nicht angegeben)
            pdf_path: Optionaler lokaler Pfad; wenn None wird das Dokument heruntergeladen.

        Returns:
            DocumentClassification oder None bei Fehler
        """
        try:
            openrouter = self._get_openrouter()

            if pdf_path:
                return openrouter.classify_pdf_smart(pdf_path)

            with tempfile.TemporaryDirectory() as tmpdir:
                local_path = self._docs_api.download(doc_id, tmpdir)

                if not local_path:
                    logger.warning(f"Download fehlgeschlagen fuer Dokument {doc_id}")
                    return None

                return openrouter.classify_pdf_smart(local_path)

        except Exception as e:
            logger.error(f"KI-Klassifikation fehlgeschlagen: {e}")
            return None
