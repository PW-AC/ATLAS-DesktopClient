"""
Adaptiver Rate Limiter für BiPRO-Downloads.

Erkennt Rate Limiting (HTTP 429, 503) und passt die Download-Geschwindigkeit
dynamisch an, um Server-Überlastung zu vermeiden und keine Dokumente zu verlieren.
"""

import threading
import time
import logging
from typing import Dict, Set, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@dataclass
class RetryInfo:
    """Informationen über Retry-Versuche für eine Lieferung."""
    shipment_id: str
    retry_count: int = 0
    last_error: str = ""
    last_attempt: Optional[datetime] = None


class RateLimitError(Exception):
    """Wird ausgelöst wenn Rate Limiting erkannt wird."""
    def __init__(self, status_code: int, retry_after: Optional[int] = None):
        self.status_code = status_code
        self.retry_after = retry_after
        super().__init__(f"Rate Limit erreicht (HTTP {status_code})")


class AdaptiveRateLimiter:
    """
    Adaptiver Rate Limiter für parallele Downloads.
    
    Features:
    - Erkennt HTTP 429 (Too Many Requests) und 503 (Service Unavailable)
    - Reduziert Worker-Anzahl dynamisch bei Rate Limiting
    - Exponential Backoff zwischen Retries
    - Erhöht Worker-Anzahl nach erfolgreichen Downloads
    - Tracking von Retry-Versuchen pro Lieferung
    
    Usage:
        limiter = AdaptiveRateLimiter(max_workers=10)
        
        # Bei Erfolg:
        limiter.on_success()
        
        # Bei Rate Limit:
        if limiter.on_rate_limit(status_code):
            # Retry später
            time.sleep(limiter.get_current_backoff())
        
        # Worker-Anzahl prüfen:
        active = limiter.get_active_workers()
    """
    
    # HTTP Status Codes die als Rate Limit gelten
    RATE_LIMIT_CODES = {429, 503}
    
    # Auch bei diesen Codes retry versuchen (temporäre Fehler)
    RETRYABLE_CODES = {429, 500, 502, 503, 504}
    
    def __init__(
        self,
        max_workers: int = 10,
        min_workers: int = 1,
        initial_backoff: float = 1.0,
        max_backoff: float = 30.0,
        max_retries: int = 3,
        recovery_threshold: int = 10
    ):
        """
        Initialisiert den Rate Limiter.
        
        Args:
            max_workers: Maximale Anzahl paralleler Worker (Start-Wert)
            min_workers: Minimale Anzahl Worker (bei Rate Limit)
            initial_backoff: Start-Wartezeit bei Rate Limit (Sekunden)
            max_backoff: Maximale Wartezeit (Sekunden)
            max_retries: Maximale Retry-Versuche pro Lieferung
            recovery_threshold: Nach X erfolgreichen Downloads Worker erhöhen
        """
        self._lock = threading.Lock()
        
        self.max_workers = max_workers
        self.min_workers = min_workers
        self._active_workers = max_workers
        
        self.initial_backoff = initial_backoff
        self.max_backoff = max_backoff
        self._current_backoff = 0.0
        
        self.max_retries = max_retries
        self.recovery_threshold = recovery_threshold
        
        # Statistiken
        self._success_count = 0
        self._rate_limit_count = 0
        self._consecutive_successes = 0
        
        # Retry-Tracking pro Shipment
        self._retry_info: Dict[str, RetryInfo] = {}
        self._failed_shipments: Set[str] = set()
        
        logger.info(
            f"AdaptiveRateLimiter initialisiert: max_workers={max_workers}, "
            f"max_retries={max_retries}, recovery_threshold={recovery_threshold}"
        )
    
    def on_success(self, shipment_id: Optional[str] = None):
        """
        Wird nach erfolgreichem Download aufgerufen.
        
        Erhöht Worker-Anzahl langsam nach mehreren Erfolgen.
        
        Args:
            shipment_id: Optional - ID der erfolgreich geladenen Lieferung
        """
        with self._lock:
            self._success_count += 1
            self._consecutive_successes += 1
            
            # Backoff zurücksetzen
            if self._current_backoff > 0:
                self._current_backoff = max(0, self._current_backoff - self.initial_backoff)
            
            # Worker erhöhen nach recovery_threshold Erfolgen
            if (self._consecutive_successes >= self.recovery_threshold and 
                self._active_workers < self.max_workers):
                self._active_workers = min(self._active_workers + 1, self.max_workers)
                self._consecutive_successes = 0
                logger.info(
                    f"Rate Limiter: Worker erhöht auf {self._active_workers}/{self.max_workers} "
                    f"nach {self.recovery_threshold} erfolgreichen Downloads"
                )
            
            # Retry-Info entfernen wenn erfolgreich
            if shipment_id and shipment_id in self._retry_info:
                del self._retry_info[shipment_id]
    
    def on_rate_limit(self, status_code: int, shipment_id: Optional[str] = None, 
                      retry_after: Optional[int] = None) -> bool:
        """
        Wird bei Rate Limiting aufgerufen.
        
        Reduziert Worker und erhöht Backoff.
        
        Args:
            status_code: HTTP Status Code (429, 503, etc.)
            shipment_id: Optional - ID der betroffenen Lieferung
            retry_after: Optional - Vom Server vorgeschlagene Wartezeit
            
        Returns:
            True wenn Retry empfohlen, False wenn aufgegeben werden soll
        """
        with self._lock:
            self._rate_limit_count += 1
            self._consecutive_successes = 0
            
            # Backoff erhöhen (exponential)
            if retry_after:
                self._current_backoff = min(retry_after, self.max_backoff)
            else:
                if self._current_backoff == 0:
                    self._current_backoff = self.initial_backoff
                else:
                    self._current_backoff = min(
                        self._current_backoff * 2, 
                        self.max_backoff
                    )
            
            # Worker reduzieren
            if self._active_workers > self.min_workers:
                old_workers = self._active_workers
                # Bei schwerem Rate Limit halbieren, sonst -1
                if status_code == 429:
                    self._active_workers = max(
                        self.min_workers,
                        self._active_workers // 2
                    )
                else:
                    self._active_workers = max(
                        self.min_workers,
                        self._active_workers - 1
                    )
                
                if old_workers != self._active_workers:
                    logger.warning(
                        f"Rate Limit erkannt (HTTP {status_code})! "
                        f"Worker reduziert: {old_workers} -> {self._active_workers}, "
                        f"Backoff: {self._current_backoff:.1f}s"
                    )
            
            # Retry-Tracking
            if shipment_id:
                return self._track_retry(shipment_id, f"HTTP {status_code}")
            
            return True
    
    def on_error(self, shipment_id: str, error: str, status_code: Optional[int] = None) -> bool:
        """
        Wird bei allgemeinem Fehler aufgerufen.
        
        Args:
            shipment_id: ID der betroffenen Lieferung
            error: Fehlermeldung
            status_code: Optional - HTTP Status Code
            
        Returns:
            True wenn Retry empfohlen, False wenn aufgegeben werden soll
        """
        with self._lock:
            # Bei retryable Status Codes auch Rate Limit behandeln
            if status_code and status_code in self.RETRYABLE_CODES:
                # Leichten Backoff erhöhen
                if self._current_backoff < self.initial_backoff:
                    self._current_backoff = self.initial_backoff
            
            return self._track_retry(shipment_id, error)
    
    def _track_retry(self, shipment_id: str, error: str) -> bool:
        """
        Trackt Retry-Versuche für eine Lieferung.
        
        Args:
            shipment_id: Lieferungs-ID
            error: Fehlermeldung
            
        Returns:
            True wenn Retry erlaubt, False wenn max. Retries erreicht
        """
        # Lock wird vom Aufrufer gehalten
        
        if shipment_id not in self._retry_info:
            self._retry_info[shipment_id] = RetryInfo(shipment_id=shipment_id)
        
        info = self._retry_info[shipment_id]
        info.retry_count += 1
        info.last_error = error
        info.last_attempt = datetime.now()
        
        if info.retry_count > self.max_retries:
            self._failed_shipments.add(shipment_id)
            logger.error(
                f"Lieferung {shipment_id} nach {self.max_retries} Versuchen aufgegeben: {error}"
            )
            return False
        
        logger.warning(
            f"Lieferung {shipment_id}: Retry {info.retry_count}/{self.max_retries} - {error}"
        )
        return True
    
    def should_retry(self, shipment_id: str) -> bool:
        """
        Prüft ob eine Lieferung erneut versucht werden sollte.
        
        Args:
            shipment_id: Lieferungs-ID
            
        Returns:
            True wenn Retry erlaubt
        """
        with self._lock:
            if shipment_id in self._failed_shipments:
                return False
            
            info = self._retry_info.get(shipment_id)
            if info and info.retry_count >= self.max_retries:
                return False
            
            return True
    
    def get_retry_count(self, shipment_id: str) -> int:
        """Gibt die Anzahl bisheriger Retries für eine Lieferung zurück."""
        with self._lock:
            info = self._retry_info.get(shipment_id)
            return info.retry_count if info else 0
    
    def get_current_backoff(self) -> float:
        """Gibt die aktuelle Backoff-Wartezeit in Sekunden zurück."""
        with self._lock:
            return self._current_backoff
    
    def get_active_workers(self) -> int:
        """Gibt die aktuelle Anzahl aktiver Worker zurück."""
        with self._lock:
            return self._active_workers
    
    def wait_if_needed(self):
        """
        Wartet falls Backoff aktiv ist.
        
        Sollte von Workern vor jedem Request aufgerufen werden.
        """
        backoff = self.get_current_backoff()
        if backoff > 0:
            logger.debug(f"Rate Limiter: Warte {backoff:.1f}s vor nächstem Request")
            time.sleep(backoff)
    
    def is_rate_limit_status(self, status_code: int) -> bool:
        """Prüft ob ein Status Code als Rate Limit gilt."""
        return status_code in self.RATE_LIMIT_CODES
    
    def is_retryable_status(self, status_code: int) -> bool:
        """Prüft ob ein Status Code einen Retry rechtfertigt."""
        return status_code in self.RETRYABLE_CODES
    
    def get_stats(self) -> Dict:
        """Gibt Statistiken zurück."""
        with self._lock:
            return {
                'success_count': self._success_count,
                'rate_limit_count': self._rate_limit_count,
                'active_workers': self._active_workers,
                'max_workers': self.max_workers,
                'current_backoff': self._current_backoff,
                'pending_retries': len(self._retry_info),
                'failed_shipments': len(self._failed_shipments),
                'failed_ids': list(self._failed_shipments)
            }
    
    def get_failed_shipments(self) -> Set[str]:
        """Gibt die IDs der endgültig fehlgeschlagenen Lieferungen zurück."""
        with self._lock:
            return self._failed_shipments.copy()
    
    def reset(self):
        """Setzt den Rate Limiter zurück."""
        with self._lock:
            self._active_workers = self.max_workers
            self._current_backoff = 0.0
            self._success_count = 0
            self._rate_limit_count = 0
            self._consecutive_successes = 0
            self._retry_info.clear()
            self._failed_shipments.clear()
            logger.info("Rate Limiter zurückgesetzt")
