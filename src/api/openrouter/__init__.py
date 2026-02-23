"""
OpenRouter API Package — KI-basierte PDF-Analyse und -Klassifikation.

Re-exportiert alle oeffentlichen Symbole fuer Abwaertskompatibilitaet:
  from api.openrouter import OpenRouterClient
  from api.openrouter import DocumentClassification, ExtractedDocumentData
  from api.openrouter import slug_de, _safe_json_loads
"""

from .client import (
    OpenRouterClient,
    get_ai_semaphore,
    get_ai_queue_depth,
    DEFAULT_MAX_CONCURRENT_AI_CALLS,
    OPENROUTER_BASE_URL,
    DEFAULT_VISION_MODEL,
    DEFAULT_EXTRACT_MODEL,
    DEFAULT_TRIAGE_MODEL,
    DEFAULT_OCR_MODEL,
    MAX_RETRIES,
    RETRY_STATUS_CODES,
    RETRY_BACKOFF_FACTOR,
)
from .models import DocumentClassification, ExtractedDocumentData
from .utils import _safe_json_loads, slug_de, _build_keyword_hints
from .classification import TRIAGE_PROMPT, TRIAGE_SCHEMA

__all__ = [
    'OpenRouterClient',
    'DocumentClassification',
    'ExtractedDocumentData',
    'slug_de',
    '_safe_json_loads',
    '_build_keyword_hints',
    'get_ai_semaphore',
    'get_ai_queue_depth',
    'DEFAULT_MAX_CONCURRENT_AI_CALLS',
    'OPENROUTER_BASE_URL',
    'DEFAULT_VISION_MODEL',
    'DEFAULT_EXTRACT_MODEL',
    'DEFAULT_TRIAGE_MODEL',
    'DEFAULT_OCR_MODEL',
    'MAX_RETRIES',
    'RETRY_STATUS_CODES',
    'RETRY_BACKOFF_FACTOR',
    'TRIAGE_PROMPT',
    'TRIAGE_SCHEMA',
]
