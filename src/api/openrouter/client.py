"""
OpenRouter API Client — HTTP-Basis und Backpressure-Kontrolle.

Enthaelt den OpenRouterClient mit HTTP-Request-Logik, Semaphore-Steuerung
und Credits-Abfrage. OCR- und Klassifikations-Methoden werden ueber
Mixins aus ocr.py und classification.py eingebracht.
"""

import logging
import time
import threading
from typing import List, Optional

import requests

from ..client import APIClient, APIError
from .ocr import OpenRouterOCRMixin
from .classification import OpenRouterClassificationMixin

logger = logging.getLogger(__name__)

# KI-Pipeline Backpressure-Kontrolle
# Begrenzt parallele KI-Aufrufe um Server-Ueberlastung zu vermeiden
DEFAULT_MAX_CONCURRENT_AI_CALLS = 5
_ai_semaphore: Optional[threading.Semaphore] = None
_ai_semaphore_lock = threading.Lock()
_ai_queue_depth = 0  # Monitoring: Anzahl wartender Aufrufe


def get_ai_semaphore(max_concurrent: int = DEFAULT_MAX_CONCURRENT_AI_CALLS) -> threading.Semaphore:
    """
    Gibt die globale KI-Semaphore zurueck (Singleton).
    
    Begrenzt die Anzahl gleichzeitiger KI-Aufrufe fuer Backpressure-Kontrolle.
    """
    global _ai_semaphore
    with _ai_semaphore_lock:
        if _ai_semaphore is None:
            _ai_semaphore = threading.Semaphore(max_concurrent)
            logger.info(f"KI-Semaphore initialisiert: max {max_concurrent} parallele Aufrufe")
    return _ai_semaphore


def get_ai_queue_depth() -> int:
    """Gibt die aktuelle Anzahl wartender KI-Aufrufe zurueck (Monitoring)."""
    return _ai_queue_depth


def _increment_queue_depth():
    """Erhoeht den Queue-Tiefe-Zaehler (Thread-safe)."""
    global _ai_queue_depth
    with _ai_semaphore_lock:
        _ai_queue_depth += 1


def _decrement_queue_depth():
    """Verringert den Queue-Tiefe-Zaehler (Thread-safe)."""
    global _ai_queue_depth
    with _ai_semaphore_lock:
        _ai_queue_depth = max(0, _ai_queue_depth - 1)

# OpenRouter API Konfiguration
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_VISION_MODEL = "openai/gpt-4o"
DEFAULT_EXTRACT_MODEL = "openai/gpt-4o-mini"  # Stufe 2: gpt-4o-mini statt gpt-4o (~17x guenstiger)
DEFAULT_TRIAGE_MODEL = "openai/gpt-4o-mini"  # Guenstiges Modell fuer schnelle Kategorisierung
DEFAULT_OCR_MODEL = "openai/gpt-4o-mini"  # OCR: gpt-4o-mini hat Vision-Support und ist ~17x guenstiger

# Retry-Konfiguration
MAX_RETRIES = 4
RETRY_STATUS_CODES = {429, 502, 503, 504}
RETRY_BACKOFF_FACTOR = 1.5


class OpenRouterClient(OpenRouterOCRMixin, OpenRouterClassificationMixin):
    """
    Client fuer OpenRouter API zur PDF-Analyse.
    
    Workflow:
    1. PDF zu Bildern konvertieren
    2. Vision-Modell: OCR (Bilder -> Text)
    3. LLM mit Structured Output: Entity-Extraktion (Text -> JSON)
    """
    
    def __init__(self, api_client: APIClient):
        """
        Initialisiert den OpenRouter Client.
        
        Args:
            api_client: APIClient-Instanz fuer Server-Kommunikation
        """
        self.api_client = api_client
        self._api_key: Optional[str] = None
        self._session = requests.Session()
        
        self._cost_calculator = None
        try:
            from services.cost_calculator import CostCalculator
            self._cost_calculator = CostCalculator()
            self._cost_calculator.load_pricing_from_api(api_client)
        except Exception as e:
            logger.debug(f"CostCalculator nicht verfuegbar: {e}")
    
    def _ensure_api_key(self) -> str:
        """
        SV-004: API-Key wird nicht mehr vom Server geholt.
        Klassifikation laeuft jetzt ueber Server-Proxy POST /ai/classify.
        Diese Methode existiert nur noch fuer Abwaertskompatibilitaet.
        """
        # SV-004 Fix: Key wird nicht mehr benoetigt, Proxy uebernimmt
        return "proxy-mode"
    
    def get_credits(self) -> Optional[dict]:
        """
        Ruft Guthaben/Usage ueber Server-Proxy ab.
        Unterstuetzt OpenRouter (balance) und OpenAI (monthly usage).
        
        Returns:
            dict mit 'provider' und provider-spezifischen Feldern, oder None bei Fehler.
            OpenRouter: balance, total_credits, total_usage, currency
            OpenAI: total_usage (USD), period
        """
        try:
            response = self.api_client.get("/ai/credits")
            
            if response.get('success') and response.get('data'):
                data = response['data']
                provider = data.get('provider', 'openrouter')
                
                if provider == 'openai':
                    return {
                        'provider': 'openai',
                        'total_usage': data.get('total_usage'),
                        'period': data.get('period', ''),
                        'currency': 'USD'
                    }
                
                inner = data.get('data', data)
                total_credits = inner.get('total_credits', 0)
                total_usage = inner.get('total_usage', 0)
                balance = total_credits - total_usage
                
                return {
                    'provider': 'openrouter',
                    'total_credits': total_credits,
                    'total_usage': total_usage,
                    'balance': balance,
                    'currency': 'USD'
                }
            
            logger.warning("Credits-Abfrage ueber Proxy fehlgeschlagen")
            return None
            
        except Exception as e:
            logger.warning(f"Fehler beim Abrufen der Credits (Proxy): {e}")
            return None
    
    def _openrouter_request(self, messages: List[dict], model: str = DEFAULT_VISION_MODEL,
                            response_format: dict = None, max_tokens: int = 4096) -> dict:
        """
        SV-004 Fix: Sendet Anfragen ueber den Server-Proxy statt direkt an OpenRouter.
        
        Der Server-Proxy (POST /ai/classify) injiziert den API-Key serverseitig
        und reduziert PII aus dem Text (SV-013).
        
        BACKPRESSURE: Verwendet Semaphore um parallele KI-Aufrufe zu begrenzen.
        
        Args:
            messages: Chat-Nachrichten
            model: Modell-ID
            response_format: Optional - Structured Output Schema
            max_tokens: Maximale Ausgabelaenge
            
        Returns:
            API-Antwort als dict (OpenRouter-Format)
            
        Raises:
            APIError: Bei Proxy- oder OpenRouter-Fehlern
        """
        # BACKPRESSURE: Semaphore verwenden
        semaphore = get_ai_semaphore()
        _increment_queue_depth()
        queue_depth = get_ai_queue_depth()
        
        if queue_depth > 1:
            logger.debug(f"KI-Queue-Tiefe: {queue_depth} wartende Aufrufe")
        
        logger.debug(f"OpenRouter Proxy Request: model={model}, messages={len(messages)}, queue_depth={queue_depth}")
        
        # Proxy-Payload: Server fuegt API-Key hinzu
        proxy_payload = {
            "messages": messages,
            "model": model,
            "max_tokens": max_tokens
        }
        if response_format:
            proxy_payload["response_format"] = response_format
        
        last_error = None
        
        # Semaphore erwerben (blockiert wenn zu viele parallele Aufrufe)
        semaphore.acquire()
        try:
            for attempt in range(MAX_RETRIES):
                try:
                    # SV-004: Ueber unseren Server-Proxy statt direkt an OpenRouter
                    response = self.api_client.post(
                        "/ai/classify",
                        json_data=proxy_payload
                    )
                    
                    # Server-Proxy gibt KI-Antwort in 'data' zurueck
                    if response.get('success') and response.get('data'):
                        data = response['data']
                        cost_info = data.get('_cost', {})
                        if cost_info.get('provider'):
                            logger.info(f"KI-Request via Provider: {cost_info['provider']}")
                        return data
                    
                    # Fehler vom Proxy
                    error_msg = response.get('error', 'Unbekannter Proxy-Fehler')
                    logger.error(f"AI-Proxy Fehler: {error_msg}")
                    raise APIError(f"AI-Proxy Fehler: {error_msg}")
                    
                except APIError as e:
                    # Retryable Status Codes
                    if hasattr(e, 'status_code') and e.status_code in RETRY_STATUS_CODES:
                        wait_time = RETRY_BACKOFF_FACTOR * (attempt + 1)
                        logger.warning(
                            f"AI-Proxy HTTP {e.status_code}, "
                            f"Retry {attempt + 1}/{MAX_RETRIES} in {wait_time:.1f}s"
                        )
                        time.sleep(wait_time)
                        continue
                    raise
                    
                except requests.RequestException as e:
                    last_error = e
                    wait_time = RETRY_BACKOFF_FACTOR * (attempt + 1)
                    logger.warning(
                        f"AI-Proxy Netzwerkfehler: {e}, "
                        f"Retry {attempt + 1}/{MAX_RETRIES} in {wait_time:.1f}s"
                    )
                    time.sleep(wait_time)
            
            # Alle Retries fehlgeschlagen
            logger.error(f"AI-Proxy nach {MAX_RETRIES} Versuchen nicht erreichbar")
            raise APIError(f"AI-Proxy dauerhaft nicht erreichbar: {last_error}")
        finally:
            # BACKPRESSURE: Semaphore freigeben und Queue-Tiefe verringern
            semaphore.release()
            _decrement_queue_depth()
