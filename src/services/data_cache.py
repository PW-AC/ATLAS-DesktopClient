"""
Zentraler Daten-Cache Service

Cached Server-Daten persistent im Speicher:
- Dokumente (nach Box)
- Box-Statistiken
- VU-Verbindungen

Features:
- Lazy Loading: Daten werden erst bei Bedarf geladen
- Persistenter Cache: Daten bleiben beim View-Wechsel erhalten
- Auto-Refresh: Alle 90 Sekunden im Hintergrund
- Manuelle Aktualisierung: Bei explizitem Refresh-Button
"""

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any

from PySide6.QtCore import QObject, Signal, QTimer

from api.client import APIClient
from api.documents import DocumentsAPI, Document

logger = logging.getLogger(__name__)

# Cache-Konfiguration
DEFAULT_AUTO_REFRESH_INTERVAL = 90  # Sekunden
CACHE_TTL = 300  # 5 Minuten (als Fallback wenn Auto-Refresh nicht laeuft)


@dataclass
class CacheEntry:
    """Ein Eintrag im Cache mit Timestamp."""
    data: Any
    loaded_at: datetime = field(default_factory=datetime.now)
    
    def is_expired(self, ttl_seconds: int = CACHE_TTL) -> bool:
        """Prueft ob der Cache-Eintrag abgelaufen ist."""
        return datetime.now() - self.loaded_at > timedelta(seconds=ttl_seconds)


class DataCacheService(QObject):
    """
    Zentraler Cache fuer Server-Daten.
    
    Singleton-Pattern: Eine Instanz pro App.
    
    Signals:
        documents_updated: Dokumente wurden aktualisiert (box_type)
        stats_updated: Statistiken wurden aktualisiert
        connections_updated: VU-Verbindungen wurden aktualisiert
        refresh_started: Hintergrund-Refresh gestartet
        refresh_finished: Hintergrund-Refresh beendet
    """
    
    # Signals fuer UI-Updates
    documents_updated = Signal(str)  # box_type oder 'all'
    stats_updated = Signal()
    connections_updated = Signal()
    refresh_started = Signal()
    refresh_finished = Signal()
    
    _instance: Optional['DataCacheService'] = None
    _lock = threading.Lock()
    
    def __new__(cls, *args, **kwargs):
        """Singleton-Pattern."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self, api_client: APIClient = None):
        """
        Initialisiert den Cache-Service.
        
        Args:
            api_client: API-Client (nur beim ersten Aufruf noetig)
        """
        if self._initialized:
            return
            
        super().__init__()
        
        if api_client is None:
            raise ValueError("api_client muss beim ersten Aufruf gesetzt werden")
        
        self.api_client = api_client
        self.docs_api = DocumentsAPI(api_client)
        
        # Cache-Storage
        self._documents_cache: Dict[str, CacheEntry] = {}  # box_type -> CacheEntry
        self._stats_cache: Optional[CacheEntry] = None
        self._connections_cache: Optional[CacheEntry] = None
        
        # Lock fuer Thread-Safety
        self._cache_lock = threading.Lock()
        
        # Auto-Refresh Timer
        self._auto_refresh_timer = QTimer(self)
        self._auto_refresh_timer.timeout.connect(self._on_auto_refresh)
        self._auto_refresh_interval = DEFAULT_AUTO_REFRESH_INTERVAL
        
        # Background-Worker laeuft?
        self._refresh_in_progress = False
        
        # Pause-Zaehler fuer verschachtelte Pause-Aufrufe
        # (z.B. wenn BiPRO-Download UND Verarbeitung gleichzeitig laufen)
        self._pause_count = 0
        self._was_running_before_pause = False
        
        self._initialized = True
        logger.info("DataCacheService initialisiert")
    
    # =========================================================================
    # DOKUMENTE
    # =========================================================================
    
    def get_documents(self, box_type: str = None, force_refresh: bool = False) -> List[Document]:
        """
        Holt Dokumente aus dem Cache oder laedt sie vom Server.
        
        Args:
            box_type: Box-Typ oder None fuer alle
            force_refresh: True = Cache ignorieren, neu laden
            
        Returns:
            Liste von Document-Objekten
        """
        cache_key = box_type or 'all'
        
        with self._cache_lock:
            # Cache vorhanden und nicht abgelaufen?
            if not force_refresh and cache_key in self._documents_cache:
                entry = self._documents_cache[cache_key]
                if not entry.is_expired():
                    logger.debug(f"Dokumente aus Cache: {cache_key} ({len(entry.data)} Stk)")
                    return entry.data
        
        # Neu laden
        return self._load_documents(box_type)
    
    def _load_documents(self, box_type: str = None) -> List[Document]:
        """Laedt Dokumente vom Server und cached sie."""
        cache_key = box_type or 'all'
        
        try:
            logger.info(f"Lade Dokumente vom Server: {cache_key}")
            
            if box_type:
                documents = self.docs_api.list_by_box(box_type)
            else:
                documents = self.docs_api.list_documents()
            
            with self._cache_lock:
                self._documents_cache[cache_key] = CacheEntry(data=documents)
            
            logger.info(f"Dokumente geladen und gecached: {len(documents)} Stk")
            return documents
            
        except Exception as e:
            logger.error(f"Fehler beim Laden der Dokumente: {e}")
            # Bei Fehler: Alten Cache zurueckgeben falls vorhanden
            with self._cache_lock:
                if cache_key in self._documents_cache:
                    return self._documents_cache[cache_key].data
            return []
    
    def invalidate_documents(self, box_type: str = None):
        """
        Invalidiert den Dokumente-Cache.
        
        Args:
            box_type: Bestimmte Box oder None fuer alle
        """
        with self._cache_lock:
            if box_type:
                self._documents_cache.pop(box_type, None)
                logger.debug(f"Dokumente-Cache invalidiert: {box_type}")
            else:
                self._documents_cache.clear()
                logger.debug("Dokumente-Cache komplett invalidiert")
    
    # =========================================================================
    # STATISTIKEN
    # =========================================================================
    
    def get_stats(self, force_refresh: bool = False) -> Dict[str, int]:
        """
        Holt Box-Statistiken aus dem Cache oder laedt sie vom Server.
        
        Args:
            force_refresh: True = Cache ignorieren, neu laden
            
        Returns:
            Dict mit Box-Typ -> Anzahl
        """
        with self._cache_lock:
            if not force_refresh and self._stats_cache:
                if not self._stats_cache.is_expired():
                    logger.debug("Statistiken aus Cache")
                    return self._stats_cache.data
        
        return self._load_stats()
    
    def _load_stats(self) -> Dict[str, int]:
        """Laedt Statistiken vom Server und cached sie."""
        try:
            logger.info("Lade Statistiken vom Server")
            stats = self.docs_api.get_box_stats()
            
            with self._cache_lock:
                self._stats_cache = CacheEntry(data=stats)
            
            logger.info(f"Statistiken geladen: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"Fehler beim Laden der Statistiken: {e}")
            with self._cache_lock:
                if self._stats_cache:
                    return self._stats_cache.data
            return {}
    
    def invalidate_stats(self):
        """Invalidiert den Statistiken-Cache."""
        with self._cache_lock:
            self._stats_cache = None
            logger.debug("Statistiken-Cache invalidiert")
    
    # =========================================================================
    # VU-VERBINDUNGEN
    # =========================================================================
    
    def get_connections(self, force_refresh: bool = False) -> List[Any]:
        """
        Holt VU-Verbindungen aus dem Cache oder laedt sie vom Server.
        
        Args:
            force_refresh: True = Cache ignorieren, neu laden
            
        Returns:
            Liste von VU-Verbindungen
        """
        with self._cache_lock:
            if not force_refresh and self._connections_cache:
                if not self._connections_cache.is_expired():
                    logger.debug("VU-Verbindungen aus Cache")
                    return self._connections_cache.data
        
        return self._load_connections()
    
    def _load_connections(self) -> List[Any]:
        """Laedt VU-Verbindungen vom Server und cached sie."""
        try:
            from api.vu_connections import VUConnectionsAPI
            
            logger.info("Lade VU-Verbindungen vom Server")
            vu_api = VUConnectionsAPI(self.api_client)
            connections = vu_api.list_connections()
            
            with self._cache_lock:
                self._connections_cache = CacheEntry(data=connections)
            
            logger.info(f"VU-Verbindungen geladen: {len(connections)} Stk")
            return connections
            
        except Exception as e:
            logger.error(f"Fehler beim Laden der VU-Verbindungen: {e}")
            with self._cache_lock:
                if self._connections_cache:
                    return self._connections_cache.data
            return []
    
    def invalidate_connections(self):
        """Invalidiert den VU-Verbindungen-Cache."""
        with self._cache_lock:
            self._connections_cache = None
            logger.debug("VU-Verbindungen-Cache invalidiert")
    
    # =========================================================================
    # AUTO-REFRESH
    # =========================================================================
    
    def start_auto_refresh(self, interval_seconds: int = DEFAULT_AUTO_REFRESH_INTERVAL):
        """
        Startet den Auto-Refresh Timer.
        
        Args:
            interval_seconds: Intervall in Sekunden (default: 90)
        """
        self._auto_refresh_interval = interval_seconds
        self._auto_refresh_timer.start(interval_seconds * 1000)
        logger.info(f"Auto-Refresh gestartet: alle {interval_seconds} Sekunden")
    
    def stop_auto_refresh(self):
        """Stoppt den Auto-Refresh Timer."""
        self._auto_refresh_timer.stop()
        logger.info("Auto-Refresh gestoppt")
    
    def pause_auto_refresh(self):
        """
        Pausiert den Auto-Refresh temporaer.
        
        Kann mehrfach aufgerufen werden (verschachtelt).
        Erst bei gleichvielen resume_auto_refresh() Aufrufen
        wird der Refresh wieder gestartet.
        
        Nutzung:
            cache.pause_auto_refresh()
            try:
                # Lange Operation (BiPRO-Download, Verarbeitung...)
                pass
            finally:
                cache.resume_auto_refresh()
        """
        with self._cache_lock:
            self._pause_count += 1
            should_stop = (self._pause_count == 1)
            if should_stop:
                # Erster Pause-Aufruf: Timer-Zustand merken
                self._was_running_before_pause = self._auto_refresh_timer.isActive()
        # Timer-Stop ausserhalb Lock (Main-Thread QTimer Operation)
        if should_stop and self._was_running_before_pause:
            self._auto_refresh_timer.stop()
            logger.info("Auto-Refresh pausiert")
    
    def resume_auto_refresh(self):
        """
        Setzt den Auto-Refresh nach pause_auto_refresh() fort.
        
        Der Timer wird nur gestartet wenn:
        - Alle pause_auto_refresh() Aufrufe mit resume_auto_refresh() beendet wurden
        - Der Timer vor dem Pausieren aktiv war
        """
        should_resume = False
        with self._cache_lock:
            if self._pause_count > 0:
                self._pause_count -= 1
                should_resume = (self._pause_count == 0 and self._was_running_before_pause)
        # Timer-Start ausserhalb Lock (Main-Thread QTimer Operation)
        if should_resume:
            self._auto_refresh_timer.start(self._auto_refresh_interval * 1000)
            logger.info("Auto-Refresh fortgesetzt")
    
    def is_auto_refresh_paused(self) -> bool:
        """Prueft ob Auto-Refresh aktuell pausiert ist."""
        with self._cache_lock:
            return self._pause_count > 0
    
    def _on_auto_refresh(self):
        """Callback fuer Auto-Refresh Timer."""
        with self._cache_lock:
            if self._refresh_in_progress:
                logger.debug("Auto-Refresh uebersprungen (laeuft bereits)")
                return
        logger.info("Auto-Refresh gestartet")
        self.refresh_all_async()
    
    def refresh_all_async(self):
        """
        Aktualisiert alle Caches asynchron im Hintergrund.
        
        Sendet Signals wenn fertig.
        """
        with self._cache_lock:
            if self._refresh_in_progress:
                return
            self._refresh_in_progress = True
        # Signal-Emit und Thread-Start ausserhalb Lock
        self.refresh_started.emit()
        
        # In Thread ausfuehren
        thread = threading.Thread(target=self._refresh_all_background, daemon=True)
        thread.start()
    
    def _refresh_all_background(self):
        """Background-Worker fuer Refresh."""
        try:
            # Statistiken laden
            self._load_stats()
            # Signal ueber QTimer.singleShot im Main-Thread emittieren
            # (threading.Thread hat keine Qt Event-Loop, daher direktes emit() -> Deadlock!)
            QTimer.singleShot(0, self.stats_updated.emit)
            
            # Dokumente fuer alle gecachten Boxen neu laden
            with self._cache_lock:
                cached_boxes = list(self._documents_cache.keys())
            
            for box_type in cached_boxes:
                if box_type == 'all':
                    self._load_documents(None)
                else:
                    self._load_documents(box_type)
                # Signal im Main-Thread emittieren (Closure fuer box_type)
                QTimer.singleShot(0, lambda bt=box_type: self.documents_updated.emit(bt))
            
            # VU-Verbindungen
            if self._connections_cache:
                self._load_connections()
                QTimer.singleShot(0, self.connections_updated.emit)
            
            logger.info("Auto-Refresh abgeschlossen")
            
        except Exception as e:
            logger.error(f"Fehler beim Auto-Refresh: {e}")
        finally:
            with self._cache_lock:
                self._refresh_in_progress = False
            QTimer.singleShot(0, self.refresh_finished.emit)
    
    def refresh_all_sync(self):
        """
        Aktualisiert alle Caches synchron (blockierend).
        
        Fuer manuellen Refresh-Button.
        """
        logger.info("Manueller Refresh gestartet")
        
        # Alles invalidieren
        self.invalidate_documents()
        self.invalidate_stats()
        self.invalidate_connections()
        
        # Neu laden (wird beim naechsten Abruf gemacht)
        self._load_stats()
        self.stats_updated.emit()
    
    # =========================================================================
    # HILFSMETHODEN
    # =========================================================================
    
    def get_cache_info(self) -> Dict[str, Any]:
        """Gibt Cache-Status-Informationen zurueck (fuer Debug)."""
        with self._cache_lock:
            return {
                'documents_cached': list(self._documents_cache.keys()),
                'stats_cached': self._stats_cache is not None,
                'connections_cached': self._connections_cache is not None,
                'auto_refresh_active': self._auto_refresh_timer.isActive(),
                'auto_refresh_interval': self._auto_refresh_interval,
            }
    
    @classmethod
    def reset_instance(cls):
        """Setzt die Singleton-Instanz zurueck (fuer Tests)."""
        with cls._lock:
            if cls._instance:
                cls._instance.stop_auto_refresh()
            cls._instance = None


def get_cache_service(api_client: APIClient = None) -> DataCacheService:
    """
    Factory-Funktion fuer den Cache-Service.
    
    Args:
        api_client: API-Client (nur beim ersten Aufruf noetig)
        
    Returns:
        DataCacheService Singleton-Instanz
    """
    return DataCacheService(api_client)
