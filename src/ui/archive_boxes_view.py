"""
ACENCIA ATLAS - Dokumentenarchiv mit Box-System

Neue Ansicht mit:
- Sidebar fuer Box-Navigation
- Eingeklappter Verarbeitungsbereich
- Box-Spalte mit Farbkodierung
- Verschieben zwischen Boxen
- Automatische Verarbeitung

Design: ACENCIA Corporate Identity
"""

from typing import Optional, List, Dict
from datetime import datetime
from pathlib import Path
import tempfile
import os
import logging

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableView,
    QHeaderView, QPushButton, QLabel, QComboBox, QLineEdit,
    QFileDialog, QMessageBox, QMenu, QProgressDialog, QFrame,
    QSplitter, QGroupBox, QTreeWidget, QTreeWidgetItem, QToolBar,
    QApplication, QProgressBar, QInputDialog, QStyledItemDelegate,
    QDialog, QFormLayout, QCheckBox, QScrollArea, QAbstractItemView,
    QStackedWidget
)
from PySide6.QtCore import (
    Qt, Signal, QThread, QMimeData, QTimer, QSize,
    QAbstractTableModel, QModelIndex, QSortFilterProxyModel
)
from shiboken6 import isValid
from PySide6.QtGui import QAction, QFont, QColor, QDrag, QBrush, QPainter, QShortcut, QKeySequence

logger = logging.getLogger(__name__)

# ACENCIA Design Tokens
from ui.styles.tokens import (
    PRIMARY_900, PRIMARY_500, PRIMARY_100, PRIMARY_0,
    ACCENT_500, ACCENT_100,
    TEXT_PRIMARY, TEXT_SECONDARY,
    BG_PRIMARY, BG_SECONDARY, BORDER_DEFAULT,
    SUCCESS, WARNING, ERROR, INFO,
    FONT_HEADLINE, FONT_BODY, FONT_MONO,
    FONT_SIZE_H2, FONT_SIZE_BODY, FONT_SIZE_CAPTION,
    RADIUS_MD, SPACING_SM, SPACING_MD,
    get_button_primary_style, get_button_secondary_style, get_button_ghost_style,
    DOCUMENT_DISPLAY_COLORS
)

from api.client import APIClient
from api.documents import (
    DocumentsAPI, Document, BoxStats, SearchResult,
    BOX_TYPES, BOX_TYPES_ADMIN, BOX_DISPLAY_NAMES, BOX_COLORS
)

# Boxen aus denen nach Download automatisch archiviert wird
ARCHIVABLE_BOXES = {'gdv', 'courtage', 'sach', 'leben', 'kranken', 'sonstige'}

# Import der bestehenden Hilfsklassen aus archive_view
from ui.archive_view import (
    format_date_german, DocumentLoadWorker, UploadWorker, 
    AIRenameWorker, PDFViewerDialog, HAS_PDF_VIEW,
    SpreadsheetViewerDialog
)


class DocumentHistoryWorker(QThread):
    """
    Worker zum asynchronen Laden der Dokument-Historie.
    
    Laedt die Aenderungshistorie eines Dokuments aus dem activity_log
    via GET /documents/{id}/history.
    """
    finished = Signal(int, list)    # doc_id, history_entries
    error = Signal(int, str)        # doc_id, error_message
    
    def __init__(self, api_client: APIClient, doc_id: int, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.doc_id = doc_id
    
    def run(self):
        try:
            docs_api = DocumentsAPI(self.api_client)
            history = docs_api.get_document_history(self.doc_id)
            if history is not None:
                self.finished.emit(self.doc_id, history)
            else:
                self.error.emit(self.doc_id, "Historie konnte nicht geladen werden")
        except Exception as e:
            logger.error(f"Fehler beim Laden der Dokument-Historie: {e}")
            self.error.emit(self.doc_id, str(e))


class DocumentHistoryPanel(QWidget):
    """
    Seitenpanel fuer die Aenderungshistorie eines Dokuments.
    
    Zeigt alle Aktionen (Verschiebungen, Downloads, Uploads, etc.)
    farbcodiert mit Zeitstempel und Benutzername.
    
    Wird rechts neben der Dokumenten-Tabelle angezeigt.
    """
    
    close_requested = Signal()
    
    # Aktions-Farben
    ACTION_COLORS = {
        'move': '#3b82f6',              # Blau
        'download': '#059669',          # Gruen
        'upload': '#6b7280',            # Grau
        'delete': '#dc2626',            # Rot
        'bulk_archive': '#f59e0b',      # Orange
        'bulk_unarchive': '#f59e0b',    # Orange
        'archive': '#f59e0b',           # Orange
        'unarchive': '#f59e0b',         # Orange
        'bulk_set_color': '#8b5cf6',    # Lila
        'update': '#6366f1',            # Indigo
        'classify': '#06b6d4',          # Cyan
        'list': '#9ca3af',              # Hellgrau (unwichtig)
    }
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_doc_id = None
        self._history_cache: Dict[int, tuple] = {}  # doc_id -> (timestamp, entries)
        self._cache_ttl = 60  # Sekunden
        self._setup_ui()
    
    def _setup_ui(self):
        """Baut das Panel-UI auf."""
        from i18n.de import (
            HISTORY_PANEL_TITLE, HISTORY_PANEL_CLOSE,
            HISTORY_EMPTY, HISTORY_LOADING
        )
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        
        # Header mit Titel und Schliessen-Button
        header = QHBoxLayout()
        self._title_label = QLabel(HISTORY_PANEL_TITLE)
        self._title_label.setStyleSheet(f"""
            font-size: 14px;
            font-weight: bold;
            color: {TEXT_PRIMARY};
        """)
        header.addWidget(self._title_label)
        
        header.addStretch()
        
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(24, 24)
        close_btn.setToolTip(HISTORY_PANEL_CLOSE)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                color: {TEXT_SECONDARY};
                font-size: 14px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                color: {TEXT_PRIMARY};
                background: {BG_SECONDARY};
                border-radius: 4px;
            }}
        """)
        close_btn.clicked.connect(self.close_requested.emit)
        header.addWidget(close_btn)
        
        layout.addLayout(header)
        
        # Trennlinie
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet(f"color: {BORDER_DEFAULT};")
        layout.addWidget(separator)
        
        # Dokument-Name
        self._doc_name_label = QLabel("")
        self._doc_name_label.setWordWrap(True)
        self._doc_name_label.setStyleSheet(f"""
            font-size: 11px;
            color: {TEXT_SECONDARY};
            padding: 2px 0;
        """)
        layout.addWidget(self._doc_name_label)
        
        # Scrollbereich fuer Historie-Eintraege
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"""
            QScrollArea {{
                border: none;
                background: transparent;
            }}
            QScrollArea > QWidget > QWidget {{
                background: transparent;
            }}
        """)
        
        self._entries_widget = QWidget()
        self._entries_layout = QVBoxLayout(self._entries_widget)
        self._entries_layout.setContentsMargins(0, 0, 0, 0)
        self._entries_layout.setSpacing(4)
        self._entries_layout.addStretch()
        
        scroll.setWidget(self._entries_widget)
        layout.addWidget(scroll, 1)
        
        # Status-Label (Loading / Empty / Error)
        self._status_label = QLabel(HISTORY_EMPTY)
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_label.setStyleSheet(f"""
            color: {TEXT_SECONDARY};
            font-size: 12px;
            padding: 20px;
        """)
        layout.addWidget(self._status_label)
        
        # Panel-Breite
        self.setMinimumWidth(220)
        self.setMaximumWidth(400)
        
        # Styling
        self.setStyleSheet(f"""
            DocumentHistoryPanel {{
                background-color: {BG_PRIMARY};
                border-left: 1px solid {BORDER_DEFAULT};
            }}
        """)
    
    def show_history(self, doc_id: int, doc_name: str, entries: list):
        """Zeigt die Historie-Eintraege an."""
        from i18n.de import (
            HISTORY_EMPTY, HISTORY_ACTION_MOVE, HISTORY_ACTION_MOVE_FROM,
            HISTORY_ACTION_DOWNLOAD, HISTORY_ACTION_UPLOAD, HISTORY_ACTION_DELETE,
            HISTORY_ACTION_ARCHIVE, HISTORY_ACTION_UNARCHIVE, HISTORY_ACTION_RENAME,
            HISTORY_ACTION_COLOR, HISTORY_ACTION_CLASSIFY, HISTORY_ACTION_UPDATE,
            HISTORY_ACTION_UNKNOWN, HISTORY_BY_USER, HISTORY_BY_SYSTEM
        )
        
        self._current_doc_id = doc_id
        self._doc_name_label.setText(doc_name)
        
        # Alte Eintraege entfernen
        self._clear_entries()
        
        if not entries:
            self._status_label.setText(HISTORY_EMPTY)
            self._status_label.setVisible(True)
            return
        
        self._status_label.setVisible(False)
        
        # Eintraege aufbauen
        for entry in entries:
            widget = self._create_entry_widget(entry)
            # Vor dem Stretch einfuegen
            self._entries_layout.insertWidget(
                self._entries_layout.count() - 1, widget
            )
        
        # Cache aktualisieren
        import time
        self._history_cache[doc_id] = (time.time(), entries)
    
    def show_loading(self, doc_name: str = ""):
        """Zeigt den Lade-Indikator."""
        from i18n.de import HISTORY_LOADING
        self._doc_name_label.setText(doc_name)
        self._clear_entries()
        self._status_label.setText(HISTORY_LOADING)
        self._status_label.setVisible(True)
    
    def show_error(self, message: str):
        """Zeigt eine Fehlermeldung."""
        from i18n.de import HISTORY_ERROR
        self._clear_entries()
        self._status_label.setText(HISTORY_ERROR)
        self._status_label.setVisible(True)
    
    def get_cached_history(self, doc_id: int) -> Optional[list]:
        """Gibt gecachte Historie zurueck wenn noch gueltig (< cache_ttl Sekunden)."""
        import time
        if doc_id in self._history_cache:
            ts, entries = self._history_cache[doc_id]
            if time.time() - ts < self._cache_ttl:
                return entries
            else:
                del self._history_cache[doc_id]
        return None
    
    def invalidate_cache(self, doc_id: Optional[int] = None):
        """Invalidiert den Cache fuer ein bestimmtes Dokument oder alle."""
        if doc_id is not None:
            self._history_cache.pop(doc_id, None)
        else:
            self._history_cache.clear()
    
    def _clear_entries(self):
        """Entfernt alle Historie-Eintraege aus dem Layout."""
        while self._entries_layout.count() > 1:  # Stretch behalten
            item = self._entries_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
    
    def _create_entry_widget(self, entry: dict) -> QWidget:
        """Erstellt ein Widget fuer einen einzelnen Historie-Eintrag."""
        from i18n.de import (
            HISTORY_ACTION_MOVE, HISTORY_ACTION_MOVE_FROM,
            HISTORY_ACTION_DOWNLOAD, HISTORY_ACTION_UPLOAD, HISTORY_ACTION_DELETE,
            HISTORY_ACTION_ARCHIVE, HISTORY_ACTION_UNARCHIVE, HISTORY_ACTION_RENAME,
            HISTORY_ACTION_COLOR, HISTORY_ACTION_CLASSIFY, HISTORY_ACTION_UPDATE,
            HISTORY_ACTION_UNKNOWN, HISTORY_BY_USER, HISTORY_BY_SYSTEM
        )
        
        action = entry.get('action', '')
        details = entry.get('details', {}) or {}
        username = entry.get('username', '')
        created_at = entry.get('created_at', '')
        
        # Farbe fuer diese Aktion
        color = self.ACTION_COLORS.get(action, '#6b7280')
        
        # Aktion menschenlesbar aufbereiten
        action_text = self._format_action(action, details)
        
        # Zeitstempel formatieren (DD.MM. HH:MM)
        time_text = self._format_timestamp(created_at)
        
        # User-Text
        if username:
            user_text = HISTORY_BY_USER.format(user=username)
        else:
            user_text = HISTORY_BY_SYSTEM
        
        # Widget aufbauen
        widget = QFrame()
        widget.setStyleSheet(f"""
            QFrame {{
                background-color: {BG_SECONDARY};
                border-radius: 4px;
                padding: 6px 8px;
                border-left: 3px solid {color};
            }}
        """)
        
        entry_layout = QVBoxLayout(widget)
        entry_layout.setContentsMargins(4, 4, 4, 4)
        entry_layout.setSpacing(2)
        
        # Zeile 1: Zeitstempel + User
        header_layout = QHBoxLayout()
        header_layout.setSpacing(4)
        
        time_label = QLabel(time_text)
        time_label.setStyleSheet(f"font-size: 10px; color: {TEXT_SECONDARY}; font-weight: 500;")
        header_layout.addWidget(time_label)
        
        header_layout.addStretch()
        
        user_label = QLabel(user_text)
        user_label.setStyleSheet(f"font-size: 10px; color: {TEXT_SECONDARY};")
        header_layout.addWidget(user_label)
        
        entry_layout.addLayout(header_layout)
        
        # Zeile 2: Aktion
        action_label = QLabel(action_text)
        action_label.setWordWrap(True)
        action_label.setStyleSheet(f"font-size: 11px; color: {TEXT_PRIMARY}; font-weight: 500;")
        entry_layout.addWidget(action_label)
        
        return widget
    
    def _format_action(self, action: str, details: dict) -> str:
        """Formatiert eine Aktion in lesbaren Text."""
        from i18n.de import (
            HISTORY_ACTION_MOVE, HISTORY_ACTION_MOVE_FROM,
            HISTORY_ACTION_DOWNLOAD, HISTORY_ACTION_UPLOAD, HISTORY_ACTION_DELETE,
            HISTORY_ACTION_ARCHIVE, HISTORY_ACTION_UNARCHIVE, HISTORY_ACTION_RENAME,
            HISTORY_ACTION_COLOR, HISTORY_ACTION_CLASSIFY, HISTORY_ACTION_UPDATE,
            HISTORY_ACTION_UNKNOWN
        )
        
        if action == 'move':
            target = details.get('target_box', '')
            source = details.get('source_box', '')
            target_display = BOX_DISPLAY_NAMES.get(target, target)
            if source:
                source_display = BOX_DISPLAY_NAMES.get(source, source)
                return HISTORY_ACTION_MOVE_FROM.format(source=source_display, target=target_display)
            return HISTORY_ACTION_MOVE.format(target=target_display)
        
        elif action == 'download':
            return HISTORY_ACTION_DOWNLOAD
        
        elif action == 'upload':
            return HISTORY_ACTION_UPLOAD
        
        elif action == 'delete':
            return HISTORY_ACTION_DELETE
        
        elif action in ('bulk_archive', 'archive'):
            return HISTORY_ACTION_ARCHIVE
        
        elif action in ('bulk_unarchive', 'unarchive'):
            return HISTORY_ACTION_UNARCHIVE
        
        elif action == 'update':
            changes = details.get('changes', {})
            if 'original_filename' in changes:
                return HISTORY_ACTION_RENAME
            if 'box_type' in changes:
                old_box = details.get('old_box_type', '')
                new_box = changes.get('box_type', '')
                old_display = BOX_DISPLAY_NAMES.get(old_box, old_box)
                new_display = BOX_DISPLAY_NAMES.get(new_box, new_box)
                if old_box:
                    return HISTORY_ACTION_MOVE_FROM.format(source=old_display, target=new_display)
                return HISTORY_ACTION_MOVE.format(target=new_display)
            if 'display_color' in changes:
                return HISTORY_ACTION_COLOR
            if 'processing_status' in changes and changes.get('processing_status') in ('classified', 'completed'):
                return HISTORY_ACTION_CLASSIFY
            return HISTORY_ACTION_UPDATE
        
        elif action == 'bulk_set_color':
            return HISTORY_ACTION_COLOR
        
        elif action == 'classify':
            return HISTORY_ACTION_CLASSIFY
        
        return HISTORY_ACTION_UNKNOWN.format(action=action)
    
    def _format_timestamp(self, iso_str: str) -> str:
        """Formatiert einen ISO-Zeitstempel in DD.MM. HH:MM Format."""
        if not iso_str:
            return ""
        try:
            # Versuche ISO-Format zu parsen
            dt = datetime.fromisoformat(iso_str.replace('Z', '+00:00'))
            return dt.strftime('%d.%m. %H:%M')
        except (ValueError, TypeError):
            # Fallback: Einfach die ersten 16 Zeichen
            return iso_str[:16] if len(iso_str) >= 16 else iso_str


class CacheDocumentLoadWorker(QThread):
    """
    Worker zum Laden von Dokumenten ueber den zentralen Cache-Service.
    
    Laedt ALLE Dokumente in einem API-Call in den Cache,
    filtert dann client-seitig nach box_type und is_archived.
    
    Vorteil gegenueber DocumentLoadWorker:
    - 1 API-Call statt N (pro Box)
    - Cache wird fuer alle Boxen befuellt
    - Nachfolgende Box-Wechsel sind instant (aus Cache)
    """
    finished = Signal(list)
    error = Signal(str)
    
    def __init__(self, cache_service, box_type: str = None, 
                 is_archived: bool = None, force_refresh: bool = True):
        super().__init__()
        self._cache = cache_service
        self.box_type = box_type
        self.is_archived = is_archived
        self.force_refresh = force_refresh
    
    def run(self):
        try:
            # Laedt ALLE Dokumente in Cache (1 API-Call), filtert lokal
            docs = self._cache.get_documents(
                box_type=self.box_type, 
                force_refresh=self.force_refresh
            )
            
            # is_archived Filter client-seitig anwenden
            if self.is_archived is True:
                docs = [d for d in docs if d.is_archived]
            elif self.is_archived is False:
                docs = [d for d in docs if not d.is_archived]
            
            self.finished.emit(docs)
        except Exception as e:
            self.error.emit(str(e))


class MissingAiDataWorker(QThread):
    """
    Hintergrund-Worker der Dokumente ohne AI-Data (Text-Extraktion) prueft.
    
    Wird einmal beim Archiv-Start ausgefuehrt. Findet Dokumente die
    serverseitig hochgeladen wurden (z.B. Scans via Power Automate)
    und fuer die noch kein Volltext extrahiert wurde.
    
    Fuer jedes solche Dokument: Download -> Text extrahieren -> save_ai_data.
    Dadurch werden auch Scan-Duplikate erkannt.
    """
    finished = Signal(int)  # Anzahl verarbeiteter Dokumente
    
    def __init__(self, docs_api):
        super().__init__()
        self._docs_api = docs_api
    
    def run(self):
        import tempfile
        import time
        from services.early_text_extract import extract_and_save_text
        
        try:
            missing = self._docs_api.get_missing_ai_data_documents()
            if not missing:
                self.finished.emit(0)
                return
            
            processed = 0
            for doc_info in missing:
                doc_id = doc_info.get('id')
                filename = doc_info.get('original_filename', '')
                if not doc_id:
                    continue
                
                try:
                    with tempfile.TemporaryDirectory() as tmp_dir:
                        file_path = self._docs_api.download(
                            doc_id, tmp_dir, filename_override=filename
                        )
                        if file_path:
                            extract_and_save_text(
                                self._docs_api, doc_id, file_path, filename
                            )
                            processed += 1
                except Exception:
                    pass  # Einzelne Fehler ueberspringen
                
                time.sleep(0.2)  # Server nicht ueberlasten
            
            self.finished.emit(processed)
        except Exception:
            self.finished.emit(0)


class LoadingOverlay(QWidget):
    """
    Semi-transparentes Overlay mit Lade-Animation.
    
    Zeigt dem Benutzer, dass Daten geladen werden.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        
        # Animation Timer ZUERST erstellen (vor setVisible!)
        self._dot_count = 0
        self._animation_timer = QTimer(self)
        self._animation_timer.timeout.connect(self._animate_dots)
        
        # Jetzt erst verstecken (loest hideEvent aus)
        self.setVisible(False)
        
        # Layout zentriert
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Container fuer Inhalt
        container = QFrame()
        container.setObjectName("loadingContainer")
        container.setStyleSheet(f"""
            QFrame#loadingContainer {{
                background-color: rgba(255, 255, 255, 0.95);
                border-radius: {RADIUS_MD};
                border: 1px solid {BORDER_DEFAULT};
                padding: 20px 40px;
            }}
        """)
        container_layout = QVBoxLayout(container)
        container_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        container_layout.setSpacing(10)
        
        # Animierte Punkte
        self._dots_label = QLabel("Laden")
        self._dots_label.setStyleSheet(f"""
            font-family: {FONT_HEADLINE};
            font-size: 16px;
            color: {PRIMARY_500};
            font-weight: 500;
        """)
        self._dots_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        container_layout.addWidget(self._dots_label)
        
        # Status-Text
        self._status_label = QLabel("")
        self._status_label.setStyleSheet(f"""
            font-family: {FONT_BODY};
            font-size: {FONT_SIZE_CAPTION};
            color: {TEXT_SECONDARY};
        """)
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        container_layout.addWidget(self._status_label)
        
        layout.addWidget(container)
        
    def showEvent(self, event):
        """Startet Animation wenn sichtbar."""
        super().showEvent(event)
        self._dot_count = 0
        self._animation_timer.start(400)  # Alle 400ms
        
    def hideEvent(self, event):
        """Stoppt Animation wenn versteckt."""
        super().hideEvent(event)
        self._animation_timer.stop()
    
    def _animate_dots(self):
        """Animiert die Lade-Punkte."""
        self._dot_count = (self._dot_count + 1) % 4
        dots = "." * self._dot_count
        self._dots_label.setText(f"Laden{dots}")
    
    def set_status(self, text: str):
        """Setzt den Status-Text unter dem Laden-Text."""
        self._status_label.setText(text)
    
    def paintEvent(self, event):
        """Zeichnet halbtransparenten Hintergrund."""
        from PySide6.QtGui import QPainter, QColor as QC
        painter = QPainter(self)
        painter.fillRect(self.rect(), QC(0, 0, 0, 80))  # Leicht dunkler Hintergrund
        super().paintEvent(event)



class ProcessingProgressOverlay(QWidget):
    """
    Einheitliche Fortschrittsfläche für Dokumentenverarbeitung.
    
    Zeigt:
    - Titel (statusabhängig)
    - Fortschrittsbalken (0-100%)
    - Status-Text mit Zahlen
    - Fazit nach Abschluss (kein Popup!)
    """
    
    close_requested = Signal()
    
    PHASE_PROCESSING = "processing"
    PHASE_COMPLETE = "complete"
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setVisible(False)
        
        self._phase = self.PHASE_PROCESSING
        self._total = 0
        self._current = 0
        self._results = []
        
        self._setup_ui()
        
        self._auto_close_timer = QTimer(self)
        self._auto_close_timer.setSingleShot(True)
        self._auto_close_timer.timeout.connect(self._on_auto_close)
    
    def _setup_ui(self):
        """UI aufbauen."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Zentrierter Container
        container = QFrame()
        container.setObjectName("processingContainer")
        container.setStyleSheet(f"""
            QFrame#processingContainer {{
                background-color: rgba(255, 255, 255, 0.98);
                border-radius: {RADIUS_MD};
                border: 2px solid {PRIMARY_500};
            }}
        """)
        container.setMinimumWidth(450)
        container.setMaximumWidth(550)
        
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(32, 28, 32, 28)
        container_layout.setSpacing(16)
        
        # Titel
        self._title_label = QLabel("Dokumente werden verarbeitet")
        self._title_label.setStyleSheet(f"""
            font-family: {FONT_HEADLINE};
            font-size: 18px;
            font-weight: 600;
            color: {PRIMARY_900};
        """)
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        container_layout.addWidget(self._title_label)
        
        # Untertitel
        self._subtitle_label = QLabel("")
        self._subtitle_label.setStyleSheet(f"""
            font-family: {FONT_BODY};
            font-size: {FONT_SIZE_BODY};
            color: {TEXT_SECONDARY};
        """)
        self._subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        container_layout.addWidget(self._subtitle_label)
        
        container_layout.addSpacing(8)
        
        # Fortschrittsbalken
        self._progress_bar = QProgressBar()
        self._progress_bar.setMinimum(0)
        self._progress_bar.setMaximum(100)
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(True)
        self._progress_bar.setFormat("%p%")
        self._progress_bar.setStyleSheet(f"""
            QProgressBar {{
                border: 1px solid {BORDER_DEFAULT};
                border-radius: 6px;
                background-color: {BG_SECONDARY};
                height: 24px;
                text-align: center;
                font-family: {FONT_BODY};
                font-size: 13px;
                font-weight: 500;
            }}
            QProgressBar::chunk {{
                background-color: {PRIMARY_500};
                border-radius: 5px;
            }}
        """)
        container_layout.addWidget(self._progress_bar)
        
        # Status-Text
        self._status_label = QLabel("")
        self._status_label.setStyleSheet(f"""
            font-family: {FONT_BODY};
            font-size: {FONT_SIZE_BODY};
            color: {TEXT_PRIMARY};
            font-weight: 500;
        """)
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        container_layout.addWidget(self._status_label)
        
        container_layout.addSpacing(8)
        
        # Fazit-Bereich (initial versteckt)
        self._summary_frame = QFrame()
        self._summary_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {BG_SECONDARY};
                border-radius: 8px;
                padding: 12px;
            }}
        """)
        summary_layout = QVBoxLayout(self._summary_frame)
        summary_layout.setSpacing(6)
        
        self._summary_label = QLabel("")
        self._summary_label.setStyleSheet(f"""
            font-family: {FONT_BODY};
            font-size: {FONT_SIZE_BODY};
            color: {TEXT_PRIMARY};
            line-height: 1.5;
        """)
        self._summary_label.setWordWrap(True)
        summary_layout.addWidget(self._summary_label)
        
        self._summary_frame.setVisible(False)
        container_layout.addWidget(self._summary_frame)
        
        # Fertig-Indikator
        self._done_label = QLabel("✓ Fertig")
        self._done_label.setStyleSheet(f"""
            font-family: {FONT_HEADLINE};
            font-size: 14px;
            font-weight: 600;
            color: {SUCCESS};
        """)
        self._done_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._done_label.setVisible(False)
        container_layout.addWidget(self._done_label)
        
        # Container zentrieren
        layout.addStretch()
        h_layout = QHBoxLayout()
        h_layout.addStretch()
        h_layout.addWidget(container)
        h_layout.addStretch()
        layout.addLayout(h_layout)
        layout.addStretch()
    
    def paintEvent(self, event):
        """Zeichnet halbtransparenten Hintergrund."""
        from PySide6.QtGui import QPainter, QColor as QC
        painter = QPainter(self)
        painter.fillRect(self.rect(), QC(0, 0, 0, 100))
        super().paintEvent(event)
    
    def start_processing(self, total_docs: int):
        """Startet die Verarbeitungsanzeige."""
        self._phase = self.PHASE_PROCESSING
        self._total = total_docs
        self._current = 0
        self._results = []
        
        self._title_label.setText("Dokumente werden verarbeitet")
        self._subtitle_label.setText(f"{total_docs} Dokument(e) zur Verarbeitung")
        self._status_label.setText("Starte Verarbeitung...")
        self._progress_bar.setValue(0)
        
        self._summary_frame.setVisible(False)
        self._done_label.setVisible(False)
        
        self.setGeometry(self.parent().rect() if self.parent() else self.rect())
        self.raise_()
        self.setVisible(True)
        QApplication.processEvents()
    
    def update_progress(self, current: int, total: int, message: str):
        """Aktualisiert den Fortschritt."""
        self._current = current
        self._total = total
        
        percent = int((current / total) * 100) if total > 0 else 0
        self._progress_bar.setValue(percent)
        
        # Message kürzen wenn zu lang
        if len(message) > 50:
            message = message[:47] + "..."
        
        self._status_label.setText(f"{message}\n({current} / {total})")
        QApplication.processEvents()
    
    def show_completion(self, batch_result, auto_close_seconds: int = 6):
        """
        Zeigt das Fazit an.
        
        Args:
            batch_result: BatchProcessingResult oder Liste von ProcessingResult (Legacy)
            auto_close_seconds: Sekunden bis Auto-Close
        """
        self._phase = self.PHASE_COMPLETE
        
        # Kompatibilitaet: Unterstuetzt sowohl BatchProcessingResult als auch Liste
        from services.document_processor import BatchProcessingResult
        
        if isinstance(batch_result, BatchProcessingResult):
            results = batch_result.results
            success_count = batch_result.successful_documents
            failed_count = batch_result.failed_documents
            total_cost = batch_result.total_cost_usd
            cost_per_doc = batch_result.cost_per_document_usd
            duration = batch_result.duration_seconds
        else:
            # Legacy: Liste von ProcessingResult
            results = batch_result
            success_count = sum(1 for r in results if r.success)
            failed_count = len(results) - success_count
            total_cost = None
            cost_per_doc = None
            duration = None
        
        self._results = results
        
        self._title_label.setText("Verarbeitung abgeschlossen")
        self._subtitle_label.setText("")
        self._progress_bar.setValue(100)
        self._status_label.setText("")
        
        # Verteilung nach Ziel-Box
        box_counts = {}
        for r in results:
            if r.success and r.target_box:
                box_name = BOX_DISPLAY_NAMES.get(r.target_box, r.target_box)
                box_counts[box_name] = box_counts.get(box_name, 0) + 1
        
        # Fazit zusammenstellen
        lines = []
        
        if success_count > 0:
            lines.append(f"✅ {success_count} Dokument(e) zugeordnet")
        
        if failed_count > 0:
            lines.append(f"⚠️ {failed_count} Dokument(e) nicht zugeordnet/fehlgeschlagen")
        
        # Dauer anzeigen
        if duration is not None:
            lines.append(f"⏱️ Dauer: {duration:.1f} Sekunden")
        
        if box_counts:
            lines.append("")
            lines.append("Verteilung:")
            for box_name, count in sorted(box_counts.items()):
                lines.append(f"  • {box_name}: {count}")
        
        # KOSTEN-ANZEIGE
        if total_cost is not None and total_cost > 0:
            lines.append("")
            lines.append("💰 Kosten:")
            lines.append(f"  • Gesamt: ${total_cost:.4f} USD")
            if cost_per_doc is not None and len(results) > 0:
                lines.append(f"  • Pro Dokument: ${cost_per_doc:.6f} USD")
        elif isinstance(batch_result, BatchProcessingResult):
            lines.append("")
            lines.append("💰 Kosten werden ermittelt...")
        
        self._summary_label.setText("\n".join(lines))
        self._summary_frame.setVisible(True)
        self._done_label.setVisible(True)
        
        if auto_close_seconds > 0:
            self._auto_close_timer.start(auto_close_seconds * 1000)
        
        QApplication.processEvents()
    
    def _on_auto_close(self):
        """Wird nach Auto-Close Timeout aufgerufen."""
        self.hide()
        self.close_requested.emit()
    
    def hide(self):
        """Versteckt das Overlay."""
        self._auto_close_timer.stop()
        super().hide()
    
    def mousePressEvent(self, event):
        """Klick schließt das Overlay (nur wenn fertig)."""
        if self._phase == self.PHASE_COMPLETE:
            self.hide()
            self.close_requested.emit()
        event.accept()


class MultiUploadWorker(QThread):
    """Worker zum Hochladen mehrerer Dateien.
    
    Phase 1: Alle ZIPs/MSGs rekursiv entpacken -> flache Job-Liste
    Phase 2: Parallele Uploads via ThreadPoolExecutor (max. 5 gleichzeitig)
    
    Jeder Upload-Thread bekommt eine eigene requests.Session (thread-safe).
    """
    MAX_UPLOAD_WORKERS = 5
    
    file_finished = Signal(str, object)  # filename, Document or None
    file_error = Signal(str, str)  # filename, error message
    all_finished = Signal(int, int)  # erfolge, fehler
    progress = Signal(int, int, str)  # current, total, filename
    
    def __init__(self, docs_api: DocumentsAPI, file_paths: list, source_type: str):
        super().__init__()
        self.docs_api = docs_api
        self.file_paths = file_paths
        self.source_type = source_type
    
    def _expand_all_files(self, file_paths):
        """Phase 1: Entpackt alle ZIPs/MSGs rekursiv und liefert flache Upload-Job-Liste.
        
        Returns:
            Liste von (path, box_type_or_None) Tupeln.
            box_type=None bedeutet Eingangsbox, 'roh' = Roh-Archiv.
        """
        import tempfile
        from services.msg_handler import is_msg_file, extract_msg_attachments
        from services.zip_handler import is_zip_file, extract_zip_contents
        from services.pdf_unlock import unlock_pdf_if_needed

        jobs = []

        for fp in file_paths:
            if is_zip_file(fp):
                td = tempfile.mkdtemp(prefix="atlas_zip_")
                self._temp_dirs.append(td)
                zr = extract_zip_contents(fp, td, api_client=self.docs_api.client)
                if zr.error:
                    self._errors.append((Path(fp).name, zr.error))
                    jobs.append((fp, 'roh'))
                    continue
                for ext in zr.extracted_paths:
                    if is_msg_file(ext):
                        md = tempfile.mkdtemp(prefix="atlas_msg_", dir=td)
                        mr = extract_msg_attachments(ext, md, api_client=self.docs_api.client)
                        if mr.error:
                            self._errors.append((Path(ext).name, mr.error))
                        else:
                            for att in mr.attachment_paths:
                                try:
                                    unlock_pdf_if_needed(att, api_client=self.docs_api.client)
                                except ValueError as e:
                                    logger.warning(str(e))
                                jobs.append((att, None))
                        jobs.append((ext, 'roh'))
                    else:
                        try:
                            unlock_pdf_if_needed(ext, api_client=self.docs_api.client)
                        except ValueError as e:
                            logger.warning(str(e))
                        jobs.append((ext, None))
                jobs.append((fp, 'roh'))

            elif is_msg_file(fp):
                td = tempfile.mkdtemp(prefix="atlas_msg_")
                self._temp_dirs.append(td)
                mr = extract_msg_attachments(fp, td, api_client=self.docs_api.client)
                if mr.error:
                    self._errors.append((Path(fp).name, mr.error))
                    continue
                for att in mr.attachment_paths:
                    if is_zip_file(att):
                        zd = tempfile.mkdtemp(prefix="atlas_zip_", dir=td)
                        zr = extract_zip_contents(att, zd, api_client=self.docs_api.client)
                        if zr.error:
                            self._errors.append((Path(att).name, zr.error))
                        else:
                            for ext in zr.extracted_paths:
                                try:
                                    unlock_pdf_if_needed(ext, api_client=self.docs_api.client)
                                except ValueError as e:
                                    logger.warning(str(e))
                                jobs.append((ext, None))
                        jobs.append((att, 'roh'))
                    else:
                        try:
                            unlock_pdf_if_needed(att, api_client=self.docs_api.client)
                        except ValueError as e:
                            logger.warning(str(e))
                        jobs.append((att, None))
                jobs.append((fp, 'roh'))

            else:
                try:
                    unlock_pdf_if_needed(fp, api_client=self.docs_api.client)
                except ValueError as e:
                    logger.warning(str(e))
                jobs.append((fp, None))

        return jobs
    
    def _upload_single(self, path: str, source_type: str, box_type: str = None):
        """Thread-safe Upload einer einzelnen Datei mit per-Thread API-Client.
        
        Returns:
            (filename, success, doc_or_error_str)
        """
        import threading
        name = Path(path).name
        try:
            # Per-Thread API-Client (eigene requests.Session)
            tid = threading.get_ident()
            if tid not in self._thread_apis:
                from api.client import APIClient
                client = APIClient(self.docs_api.client.config)
                client.set_token(self.docs_api.client._token)
                self._thread_apis[tid] = DocumentsAPI(client)
            docs_api = self._thread_apis[tid]

            if box_type:
                doc = docs_api.upload(path, source_type, box_type=box_type)
            else:
                doc = docs_api.upload(path, source_type)
            if doc:
                # Fruehe Text-Extraktion fuer Inhaltsduplikat-Erkennung
                if box_type != 'roh':
                    try:
                        from services.early_text_extract import extract_and_save_text
                        extract_and_save_text(docs_api, doc.id, path, name)
                    except Exception:
                        pass  # Darf Upload nicht abbrechen
                return (name, True, doc)
            else:
                return (name, False, "Upload fehlgeschlagen")
        except Exception as e:
            return (name, False, str(e))
    
    def run(self):
        from concurrent.futures import ThreadPoolExecutor, as_completed

        self._temp_dirs = []
        self._errors = []
        self._thread_apis = {}

        # Phase 1: Alle Dateien entpacken (sequentiell, lokal)
        jobs = self._expand_all_files(self.file_paths)
        total = len(jobs)
        self.progress.emit(0, total, "")

        # Fehler aus Phase 1 emittieren
        for name, error in self._errors:
            self.file_error.emit(name, error)

        # Phase 2: Parallele Uploads
        erfolge = 0
        fehler = len(self._errors)
        uploaded = 0

        workers = min(self.MAX_UPLOAD_WORKERS, max(1, total))
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(self._upload_single, path, self.source_type, box_type): path
                for path, box_type in jobs
            }
            for future in as_completed(futures):
                name, success, result = future.result()
                uploaded += 1
                self.progress.emit(uploaded, total, name)
                if success:
                    erfolge += 1
                    self.file_finished.emit(name, result)
                else:
                    fehler += 1
                    self.file_error.emit(name, result)

        # Temporaere Verzeichnisse aufraeumen
        import shutil
        for td in self._temp_dirs:
            try:
                shutil.rmtree(td, ignore_errors=True)
            except Exception:
                pass
        
        self.all_finished.emit(erfolge, fehler)


class PreviewDownloadWorker(QThread):
    """
    Worker zum Herunterladen einer Datei fuer die Vorschau.
    
    Optimierungen:
    - filename_override: Spart get_document() API-Call (Filename bereits bekannt)
    - cache_dir: Persistenter Cache fuer Vorschauen (gleiche Datei nur 1x downloaden)
    """
    download_finished = Signal(object)  # saved_path oder None
    download_error = Signal(str)
    
    def __init__(self, docs_api: DocumentsAPI, doc_id: int, target_dir: str,
                 filename: str = None, cache_dir: str = None):
        super().__init__()
        self.docs_api = docs_api
        self.doc_id = doc_id
        self.target_dir = target_dir
        self.filename = filename
        self.cache_dir = cache_dir
        self._cancelled = False
    
    def cancel(self):
        """Markiert den Download als abgebrochen."""
        self._cancelled = True
    
    def run(self):
        try:
            from api.documents import safe_cache_filename
            
            if self._cancelled:
                self.download_finished.emit(None)
                return
            
            # Cache-Check: Datei bereits lokal vorhanden?
            if self.cache_dir and self.filename:
                cache_name = safe_cache_filename(self.doc_id, self.filename)
                cached_path = os.path.join(self.cache_dir, cache_name)
                if os.path.exists(cached_path) and os.path.getsize(cached_path) > 0:
                    logger.info(f"Vorschau aus Cache: {cached_path}")
                    self.download_finished.emit(cached_path)
                    return
            
            # Download mit filename_override (spart get_document API-Call)
            download_dir = self.cache_dir or self.target_dir
            cache_name = safe_cache_filename(self.doc_id, self.filename) if self.cache_dir and self.filename else self.filename
            result = self.docs_api.download(
                self.doc_id, download_dir, 
                filename_override=cache_name
            )
            
            if self._cancelled:
                self.download_finished.emit(None)
                return
            self.download_finished.emit(result)
        except Exception as e:
            self.download_error.emit(str(e))


class MultiDownloadWorker(QThread):
    """Worker zum Herunterladen mehrerer Dateien im Hintergrund."""
    file_finished = Signal(int, str, str)  # doc_id, filename, saved_path
    file_error = Signal(int, str, str)  # doc_id, filename, error message
    all_finished = Signal(int, int, list, list)  # erfolge, fehler, fehler_liste, erfolgreiche_doc_ids
    progress = Signal(int, int, str)  # current, total, filename
    
    def __init__(self, docs_api: DocumentsAPI, documents: list, target_dir: str):
        super().__init__()
        self.docs_api = docs_api
        self.documents = documents  # List[Document]
        self.target_dir = target_dir
        self._cancelled = False
    
    def cancel(self):
        """Bricht den Download ab."""
        self._cancelled = True
    
    def run(self):
        erfolge = 0
        fehler = 0
        fehler_liste = []
        erfolgreiche_doc_ids = []  # IDs der erfolgreich heruntergeladenen Dokumente
        total = len(self.documents)
        
        for i, doc in enumerate(self.documents):
            if self._cancelled:
                break
            
            self.progress.emit(i + 1, total, doc.original_filename)
            
            try:
                result = self.docs_api.download(
                    doc.id, self.target_dir,
                    filename_override=doc.original_filename
                )
                if result:
                    self.file_finished.emit(doc.id, doc.original_filename, result)
                    erfolgreiche_doc_ids.append(doc.id)
                    erfolge += 1
                else:
                    error_msg = "Download fehlgeschlagen"
                    self.file_error.emit(doc.id, doc.original_filename, error_msg)
                    fehler_liste.append(f"{doc.original_filename}: {error_msg}")
                    fehler += 1
            except Exception as e:
                error_msg = str(e)
                self.file_error.emit(doc.id, doc.original_filename, error_msg)
                fehler_liste.append(f"{doc.original_filename}: {error_msg}")
                fehler += 1
        
        self.all_finished.emit(erfolge, fehler, fehler_liste, erfolgreiche_doc_ids)


class BoxDownloadWorker(QThread):
    """
    Worker zum Herunterladen aller Dokumente einer Box.
    
    Laedt alle nicht-archivierten Dokumente aus einer Box herunter.
    Optional: ZIP-Erstellung nach Download.
    """
    progress = Signal(int, int, str)  # current, total, filename
    finished = Signal(int, int, list, list)  # erfolge, fehler, fehler_liste, erfolgreiche_doc_ids
    status = Signal(str)  # Status-Meldung (z.B. "Erstelle ZIP...")
    error = Signal(str)
    
    def __init__(self, docs_api: DocumentsAPI, box_type: str, 
                 target_path: str, mode: str = 'folder'):
        """
        Args:
            docs_api: DocumentsAPI-Instanz
            box_type: Box-Typ ('gdv', 'courtage', etc.)
            target_path: Ziel-Pfad (Ordner fuer 'folder', .zip Datei fuer 'zip')
            mode: 'zip' oder 'folder'
        """
        super().__init__()
        self.docs_api = docs_api
        self.box_type = box_type
        self.target_path = target_path
        self.mode = mode
        self._cancelled = False
    
    def cancel(self):
        """Bricht den Download ab."""
        self._cancelled = True
    
    def run(self):
        import zipfile
        
        try:
            # 1. Alle nicht-archivierten Dokumente der Box laden
            documents = self.docs_api.list_documents(
                box_type=self.box_type, 
                is_archived=False
            )
            
            if not documents:
                self.finished.emit(0, 0, [], [])
                return
            
            total = len(documents)
            erfolge = 0
            fehler = 0
            fehler_liste = []
            erfolgreiche_doc_ids = []
            
            # 2. Zielverzeichnis bestimmen
            if self.mode == 'zip':
                # Temp-Verzeichnis fuer ZIP-Modus
                temp_dir = tempfile.mkdtemp(prefix='bipro_box_download_')
                download_dir = temp_dir
            else:
                download_dir = self.target_path
                os.makedirs(download_dir, exist_ok=True)
            
            # 3. Dokumente herunterladen
            for i, doc in enumerate(documents):
                if self._cancelled:
                    break
                
                self.progress.emit(i + 1, total, doc.original_filename)
                
                try:
                    result = self.docs_api.download(
                        doc.id, download_dir,
                        filename_override=doc.original_filename
                    )
                    if result:
                        erfolgreiche_doc_ids.append(doc.id)
                        erfolge += 1
                    else:
                        fehler_liste.append(f"{doc.original_filename}: Download fehlgeschlagen")
                        fehler += 1
                except Exception as e:
                    fehler_liste.append(f"{doc.original_filename}: {str(e)}")
                    fehler += 1
            
            # 4. ZIP erstellen wenn gewuenscht
            if self.mode == 'zip' and erfolge > 0 and not self._cancelled:
                from i18n.de import BOX_DOWNLOAD_CREATING_ZIP
                self.status.emit(BOX_DOWNLOAD_CREATING_ZIP)
                
                try:
                    with zipfile.ZipFile(self.target_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                        for filename in os.listdir(download_dir):
                            file_path = os.path.join(download_dir, filename)
                            if os.path.isfile(file_path):
                                zf.write(file_path, filename)
                except Exception as e:
                    self.error.emit(f"ZIP-Erstellung fehlgeschlagen: {e}")
                    return
                finally:
                    # Temp-Verzeichnis aufraeumen
                    import shutil
                    try:
                        shutil.rmtree(temp_dir, ignore_errors=True)
                    except Exception:
                        pass
            
            self.finished.emit(erfolge, fehler, fehler_liste, erfolgreiche_doc_ids)
            
        except Exception as e:
            self.error.emit(str(e))


class CreditsWorker(QThread):
    """Worker zum Abrufen der KI-Provider Credits/Usage."""
    finished = Signal(object)  # dict oder None
    
    def __init__(self, api_client):
        super().__init__()
        self.api_client = api_client
    
    def run(self):
        try:
            from api.openrouter import OpenRouterClient
            openrouter = OpenRouterClient(self.api_client)
            credits = openrouter.get_credits()
            self.finished.emit(credits)
        except Exception as e:
            logger.debug(f"Credits-Abfrage fehlgeschlagen: {e}")
            self.finished.emit(None)


class CostStatsWorker(QThread):
    """Worker zum Laden der durchschnittlichen Verarbeitungskosten pro Dokument."""
    finished = Signal(float)  # avg_cost_per_document_usd
    
    def __init__(self, api_client):
        super().__init__()
        self._api_client = api_client
    
    def run(self):
        try:
            from api.processing_history import ProcessingHistoryAPI
            history_api = ProcessingHistoryAPI(self._api_client)
            stats = history_api.get_cost_stats()
            if stats:
                avg_cost = float(stats.get('avg_cost_per_document_usd', 0))
                self.finished.emit(avg_cost)
            else:
                self.finished.emit(0.0)
        except Exception as e:
            logger.debug(f"Kosten-Statistik Abfrage fehlgeschlagen: {e}")
            self.finished.emit(0.0)


class DelayedCostWorker(QThread):
    """
    Worker fuer verzoegerten Kosten-Check.
    
    Wartet die angegebene Verzoegerung ab, ruft dann das aktuelle
    OpenRouter-Guthaben ab und berechnet die Kosten.
    """
    finished = Signal(object)  # dict mit Kosten oder None
    countdown = Signal(int)    # Verbleibende Sekunden
    
    def __init__(self, api_client, batch_result, history_entry_id: int, delay_seconds: int = 90):
        super().__init__()
        self.api_client = api_client
        self.batch_result = batch_result
        self.history_entry_id = history_entry_id
        self.delay_seconds = delay_seconds
        self._cancelled = False
    
    def cancel(self):
        self._cancelled = True
    
    def run(self):
        import time
        
        # Countdown abwarten
        for remaining in range(self.delay_seconds, 0, -1):
            if self._cancelled:
                self.finished.emit(None)
                return
            self.countdown.emit(remaining)
            time.sleep(1)
        
        if self._cancelled:
            self.finished.emit(None)
            return
        
        # Jetzt Credits abrufen
        try:
            from api.openrouter import OpenRouterClient
            from services.document_processor import DocumentProcessor
            
            openrouter = OpenRouterClient(self.api_client)
            credits_info = openrouter.get_credits()
            
            if not credits_info:
                logger.warning("Verzoegerter Kosten-Check: Credits-Abfrage fehlgeschlagen")
                self.finished.emit(None)
                return
            
            provider = credits_info.get('provider', 'openrouter')
            if provider == 'openai':
                credits_after = credits_info.get('total_usage', 0.0) or 0.0
            else:
                credits_after = credits_info.get('balance', 0.0)
            
            # Kosten berechnen und in DB loggen
            processor = DocumentProcessor(self.api_client)
            cost_result = processor.log_delayed_costs(
                history_entry_id=self.history_entry_id,
                batch_result=self.batch_result,
                credits_after=credits_after,
                provider=provider
            )
            
            self.finished.emit(cost_result)
            
        except Exception as e:
            logger.error(f"Verzoegerter Kosten-Check fehlgeschlagen: {e}")
            self.finished.emit(None)


class BoxStatsWorker(QThread):
    """Worker zum Laden der Box-Statistiken."""
    finished = Signal(object)  # BoxStats
    error = Signal(str)
    
    def __init__(self, docs_api: DocumentsAPI):
        super().__init__()
        self.docs_api = docs_api
    
    def run(self):
        try:
            stats = self.docs_api.get_box_stats()
            self.finished.emit(stats)
        except Exception as e:
            self.error.emit(str(e))


class DocumentMoveWorker(QThread):
    """Worker zum Verschieben von Dokumenten."""
    finished = Signal(int)  # Anzahl verschoben
    error = Signal(str)
    
    def __init__(self, docs_api: DocumentsAPI, doc_ids: List[int], target_box: str,
                 processing_status: str = None):
        super().__init__()
        self.docs_api = docs_api
        self.doc_ids = doc_ids
        self.target_box = target_box
        self.processing_status = processing_status
    
    def run(self):
        try:
            moved = self.docs_api.move_documents(
                self.doc_ids, self.target_box,
                processing_status=self.processing_status
            )
            self.finished.emit(moved)
        except Exception as e:
            self.error.emit(str(e))


class DocumentColorWorker(QThread):
    """Worker zum Setzen/Entfernen von Farbmarkierungen im Hintergrund."""
    finished = Signal(int, object)  # count, color (str or None)
    error = Signal(str)

    def __init__(self, docs_api: DocumentsAPI, doc_ids: List[int], color: Optional[str]):
        super().__init__()
        self.docs_api = docs_api
        self.doc_ids = doc_ids
        self.color = color

    def run(self):
        try:
            count = self.docs_api.set_documents_color(self.doc_ids, self.color)
            self.finished.emit(count, self.color)
        except Exception as e:
            self.error.emit(str(e))


class ProcessingWorker(QThread):
    """Worker fuer automatische Dokumentenverarbeitung."""
    finished = Signal(object)  # BatchProcessingResult
    progress = Signal(int, int, str)  # current, total, message
    error = Signal(str)
    
    def __init__(self, api_client: APIClient):
        super().__init__()
        self.api_client = api_client
        self._cancelled = False
    
    def cancel(self):
        self._cancelled = True
    
    def run(self):
        try:
            from services.document_processor import DocumentProcessor
            
            processor = DocumentProcessor(self.api_client)
            
            def on_progress(current, total, msg):
                if not self._cancelled:
                    self.progress.emit(current, total, msg)
            
            # process_inbox gibt jetzt BatchProcessingResult zurueck
            batch_result = processor.process_inbox(progress_callback=on_progress)
            self.finished.emit(batch_result)
            
        except Exception as e:
            logger.exception("ProcessingWorker Fehler")
            self.error.emit(str(e))


class DocumentTableModel(QAbstractTableModel):
    """
    Virtualisiertes Table-Model fuer Dokumente.
    
    Ersetzt QTableWidget + QTableWidgetItem komplett.
    Qt ruft data() NUR fuer sichtbare Zeilen auf (~30 statt 500+).
    Kein Item-Spam, kein Rebuild, kein UI-Freeze.
    """
    
    # Spalten-Konstanten
    COL_DUPLICATE = 0
    COL_EMPTY_PAGES = 1
    COL_FILENAME = 2
    COL_BOX = 3
    COL_SOURCE = 4
    COL_TYPE = 5
    COL_AI = 6
    COL_DATE = 7
    COL_BY = 8
    COLUMN_COUNT = 9
    
    # Dateiendung -> Anzeigename Mapping (statisch)
    _TYPE_MAP = {
        '.pdf': 'PDF', '.xml': 'XML', '.txt': 'TXT', '.gdv': 'GDV',
        '.dat': 'DAT', '.vwb': 'VWB', '.csv': 'CSV', '.xlsx': 'Excel',
        '.xls': 'Excel', '.doc': 'Word', '.docx': 'Word', '.jpg': 'Bild',
        '.jpeg': 'Bild', '.png': 'Bild', '.gif': 'Bild', '.zip': 'ZIP',
    }
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._documents: List[Document] = []
        self._box_font = QFont("Open Sans", 9, QFont.Weight.Medium)
        # Header-Labels (werden in headerData verwendet)
        from i18n.de import DUPLICATE_COLUMN_HEADER, EMPTY_PAGES_COLUMN_HEADER
        self._headers = [
            DUPLICATE_COLUMN_HEADER, EMPTY_PAGES_COLUMN_HEADER, "Dateiname", "Box", "Quelle",
            "Art", "KI", "Datum", "Von"
        ]
    
    def rowCount(self, parent=QModelIndex()):
        if parent.isValid():
            return 0
        return len(self._documents)
    
    def columnCount(self, parent=QModelIndex()):
        if parent.isValid():
            return 0
        return self.COLUMN_COUNT
    
    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        """Liefert Daten fuer eine Zelle - wird NUR fuer sichtbare Zeilen aufgerufen."""
        if not index.isValid():
            return None
        
        row = index.row()
        col = index.column()
        
        if row < 0 or row >= len(self._documents):
            return None
        
        doc = self._documents[row]
        
        # ---- DisplayRole: Anzeige-Text ----
        if role == Qt.ItemDataRole.DisplayRole:
            if col == self.COL_DUPLICATE:
                if doc.is_duplicate:
                    from i18n.de import DUPLICATE_ICON
                    return DUPLICATE_ICON
                elif doc.is_content_duplicate:
                    from i18n.de import CONTENT_DUPLICATE_ICON
                    return CONTENT_DUPLICATE_ICON
                return ""
            elif col == self.COL_EMPTY_PAGES:
                if doc.is_completely_empty:
                    from i18n.de import EMPTY_PAGES_ICON_FULL
                    return EMPTY_PAGES_ICON_FULL
                elif doc.has_empty_pages:
                    from i18n.de import EMPTY_PAGES_ICON_PARTIAL
                    return EMPTY_PAGES_ICON_PARTIAL
                return ""
            elif col == self.COL_FILENAME:
                return doc.original_filename
            elif col == self.COL_BOX:
                return doc.box_type_display
            elif col == self.COL_SOURCE:
                return doc.source_type_display
            elif col == self.COL_TYPE:
                return self._get_file_type(doc)
            elif col == self.COL_AI:
                if doc.ai_renamed:
                    return "✓"
                elif doc.ai_processing_error:
                    return "✗"
                elif doc.is_pdf:
                    return "-"
                return ""
            elif col == self.COL_DATE:
                return format_date_german(doc.created_at)
            elif col == self.COL_BY:
                return doc.uploaded_by_name or ""
        
        # ---- UserRole: Document-Objekt (fuer alle Spalten verfuegbar) ----
        elif role == Qt.ItemDataRole.UserRole:
            return doc
        
        # ---- ForegroundRole: Text-Farben ----
        elif role == Qt.ItemDataRole.ForegroundRole:
            if col == self.COL_DUPLICATE:
                if doc.is_duplicate:
                    return QColor("#f59e0b")  # Amber: Datei-Duplikat
                elif doc.is_content_duplicate:
                    return QColor("#6366f1")  # Indigo: Inhaltsduplikat
            elif col == self.COL_EMPTY_PAGES:
                if doc.is_completely_empty:
                    return QColor("#dc2626")  # Rot: komplett leer
                elif doc.has_empty_pages:
                    return QColor("#f59e0b")  # Orange: teilweise leer
            elif col == self.COL_BOX:
                return QColor(doc.box_color)
            elif col == self.COL_SOURCE:
                if doc.source_type == 'bipro_auto':
                    return QColor(INFO)
                elif doc.source_type == 'scan':
                    return QColor("#9C27B0")
            elif col == self.COL_TYPE:
                ft = self._get_file_type(doc)
                if ft == "GDV":
                    return QColor(SUCCESS)
                elif ft == "PDF":
                    return QColor(ERROR)
                elif ft == "XML":
                    return QColor(INFO)
            elif col == self.COL_AI:
                if doc.ai_renamed:
                    return QColor(SUCCESS)
                elif doc.ai_processing_error:
                    return QColor(ERROR)
        
        # ---- BackgroundRole: Farbmarkierung (display_color) ----
        elif role == Qt.ItemDataRole.BackgroundRole:
            if doc.display_color and doc.display_color in DOCUMENT_DISPLAY_COLORS:
                return QBrush(QColor(DOCUMENT_DISPLAY_COLORS[doc.display_color]))
        
        # ---- FontRole: Spezial-Fonts ----
        elif role == Qt.ItemDataRole.FontRole:
            if col == self.COL_BOX:
                return self._box_font
        
        # ---- TextAlignmentRole ----
        elif role == Qt.ItemDataRole.TextAlignmentRole:
            if col in (self.COL_DUPLICATE, self.COL_EMPTY_PAGES, self.COL_AI):
                return int(Qt.AlignmentFlag.AlignCenter)
        
        # ---- ToolTipRole ----
        elif role == Qt.ItemDataRole.ToolTipRole:
            if col == self.COL_DUPLICATE:
                if doc.is_duplicate:
                    from i18n.de import (DUPLICATE_TOOLTIP_LABEL, DUPLICATE_TOOLTIP_NO_ORIGINAL)
                    if doc.duplicate_of_filename:
                        return self._build_duplicate_tooltip(
                            label=DUPLICATE_TOOLTIP_LABEL,
                            filename=doc.duplicate_of_filename,
                            doc_id=doc.previous_version_id,
                            box_type=doc.duplicate_of_box_type or '',
                            created_at=doc.duplicate_of_created_at or '',
                            is_archived=doc.duplicate_of_is_archived,
                        )
                    else:
                        return DUPLICATE_TOOLTIP_NO_ORIGINAL.format(version=doc.version)
                elif doc.is_content_duplicate:
                    from i18n.de import (CONTENT_DUPLICATE_TOOLTIP_LABEL,
                                         CONTENT_DUPLICATE_TOOLTIP_NO_ORIGINAL)
                    if doc.content_duplicate_of_filename:
                        return self._build_duplicate_tooltip(
                            label=CONTENT_DUPLICATE_TOOLTIP_LABEL,
                            filename=doc.content_duplicate_of_filename,
                            doc_id=doc.content_duplicate_of_id,
                            box_type=doc.content_duplicate_of_box_type or '',
                            created_at=doc.content_duplicate_of_created_at or '',
                            is_archived=doc.content_duplicate_of_is_archived,
                        )
                    else:
                        return CONTENT_DUPLICATE_TOOLTIP_NO_ORIGINAL
            elif col == self.COL_EMPTY_PAGES:
                if doc.is_completely_empty:
                    from i18n.de import EMPTY_PAGES_TOOLTIP_FULL
                    return EMPTY_PAGES_TOOLTIP_FULL.format(total=doc.total_page_count)
                elif doc.has_empty_pages:
                    from i18n.de import EMPTY_PAGES_TOOLTIP_PARTIAL
                    return EMPTY_PAGES_TOOLTIP_PARTIAL.format(
                        count=doc.empty_page_count, total=doc.total_page_count
                    )
            elif col == self.COL_AI:
                if doc.ai_renamed:
                    return "KI-verarbeitet"
                elif doc.ai_processing_error:
                    return doc.ai_processing_error
        
        return None
    
    def headerData(self, section: int, orientation, role: int = Qt.ItemDataRole.DisplayRole):
        """Spalten-Header."""
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            if 0 <= section < len(self._headers):
                return self._headers[section]
        return None
    
    def flags(self, index: QModelIndex):
        """Alle Zellen sind selektierbar und aktiviert, aber nicht editierbar."""
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        return Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled
    
    def set_documents(self, documents: List[Document]):
        """Setzt die gesamte Dokumentliste (ersetzt _populate_table)."""
        self.beginResetModel()
        self._documents = documents
        self.endResetModel()
    
    def get_document(self, row: int) -> Optional[Document]:
        """Zugriff auf ein Dokument per Zeilen-Index."""
        if 0 <= row < len(self._documents):
            return self._documents[row]
        return None
    
    def get_documents(self) -> List[Document]:
        """Gibt die komplette Dokumentliste zurueck."""
        return self._documents
    
    def update_colors(self, doc_ids: set, color: Optional[str]):
        """Aktualisiert display_color fuer betroffene Dokumente und emittiert dataChanged."""
        for row, doc in enumerate(self._documents):
            if doc.id in doc_ids:
                doc.display_color = color
                # Nur BackgroundRole hat sich geaendert - emittiere fuer die ganze Zeile
                top_left = self.index(row, 0)
                bottom_right = self.index(row, self.COLUMN_COUNT - 1)
                self.dataChanged.emit(top_left, bottom_right, [Qt.ItemDataRole.BackgroundRole])
    
    @staticmethod
    def _get_file_type(doc) -> str:
        """Ermittelt den Dateityp fuer die Anzeige."""
        if doc.is_gdv:
            return "GDV"
        ext = doc.file_extension.lower() if hasattr(doc, 'file_extension') else ""
        if not ext and '.' in doc.original_filename:
            ext = '.' + doc.original_filename.rsplit('.', 1)[-1].lower()
        return DocumentTableModel._TYPE_MAP.get(ext, ext.upper().lstrip('.') if ext else '?')

    @staticmethod
    def _build_duplicate_tooltip(label: str, filename: str, doc_id, box_type: str,
                                  created_at: str, is_archived: bool) -> str:
        """Baut einen Rich-HTML-Tooltip fuer Duplikat-Anzeige (analog ATLAS Index Kachel)."""
        from html import escape
        from i18n.de import DUPLICATE_TOOLTIP_ARCHIVED

        # Box-Emojis (gleiche Mapping wie SearchResultCard)
        box_emojis = {
            'gdv': '📊', 'courtage': '💰', 'sach': '🏠', 'leben': '❤️',
            'kranken': '🏥', 'sonstige': '📁', 'roh': '📦', 'eingang': '📬',
            'verarbeitung': '📥', 'falsch': '⚠️'
        }
        box_emoji = box_emojis.get(box_type, '📁') if box_type else '📁'
        box_display = BOX_DISPLAY_NAMES.get(box_type, box_type) if box_type else ''

        # Datum formatieren (YYYY-MM-DD HH:MM:SS -> DD.MM.YYYY)
        date_display = ''
        if created_at:
            try:
                date_part = created_at[:10]  # YYYY-MM-DD
                parts = date_part.split('-')
                if len(parts) == 3:
                    date_display = f"{parts[2]}.{parts[1]}.{parts[0]}"
            except (IndexError, ValueError):
                date_display = created_at[:10] if created_at else ''

        # Meta-Zeile zusammenbauen
        meta_parts = []
        if box_display:
            meta_parts.append(f"{box_emoji} {escape(box_display)}")
        if date_display:
            meta_parts.append(date_display)
        if is_archived:
            meta_parts.append(f"📦 {DUPLICATE_TOOLTIP_ARCHIVED}")
        meta_line = " &nbsp;|&nbsp; ".join(meta_parts) if meta_parts else ''

        # HTML zusammenbauen
        html = f"""<div style="padding: 4px;">
<div style="color: #9E9E9E; font-size: 11px; margin-bottom: 2px;">{escape(label)}</div>
<div style="font-weight: bold; font-size: 12px; margin-bottom: 3px;">{escape(filename)}</div>"""
        if meta_line:
            html += f'\n<div style="color: #757575; font-size: 11px;">{meta_line}</div>'
        if doc_id:
            html += f'\n<div style="color: #BDBDBD; font-size: 10px; margin-top: 2px;">ID: {doc_id}</div>'
        html += '\n</div>'
        return html


class DocumentSortFilterProxy(QSortFilterProxyModel):
    """
    Proxy-Model fuer Sortierung und Suche.
    
    - filterAcceptsRow(): Textsuche nach Dateiname
    - lessThan(): Custom-Sortierung fuer Datum-Spalte (ISO statt DD.MM.YYYY)
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._search_text = ""
        self.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
    
    def set_search_text(self, text: str):
        """Setzt den Suchtext und filtert die Tabelle."""
        self._search_text = text.lower()
        self.invalidateFilter()
    
    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        """Filtert Zeilen nach Suchtext im Dateinamen."""
        if not self._search_text:
            return True
        model = self.sourceModel()
        if model is None:
            return True
        index = model.index(source_row, DocumentTableModel.COL_FILENAME, source_parent)
        filename = model.data(index, Qt.ItemDataRole.DisplayRole)
        if filename is None:
            return False
        return self._search_text in filename.lower()
    
    def lessThan(self, left: QModelIndex, right: QModelIndex) -> bool:
        """Custom-Sortierung: Datum-Spalte nach ISO-String, Rest nach Display-Text."""
        col = left.column()
        model = self.sourceModel()
        if model is None:
            return False
        
        if col == DocumentTableModel.COL_DATE:
            # Nach ISO-Datum sortieren (created_at), nicht nach DD.MM.YYYY
            left_doc = model.data(left, Qt.ItemDataRole.UserRole)
            right_doc = model.data(right, Qt.ItemDataRole.UserRole)
            left_val = left_doc.created_at or "" if left_doc else ""
            right_val = right_doc.created_at or "" if right_doc else ""
            return left_val < right_val
        
        # Standard: Display-Text vergleichen
        left_data = model.data(left, Qt.ItemDataRole.DisplayRole) or ""
        right_data = model.data(right, Qt.ItemDataRole.DisplayRole) or ""
        return left_data < right_data


class ColorBackgroundDelegate(QStyledItemDelegate):
    """
    Custom Delegate der Item-Hintergrundfarben respektiert,
    auch wenn ein globales Qt-Stylesheet gesetzt ist.
    
    Qt-Stylesheets ueberschreiben normalerweise BackgroundRole auf Items.
    Dieser Delegate malt die Hintergrundfarbe manuell vor dem Standard-Rendering.
    """
    
    def paint(self, painter: QPainter, option, index):
        """Malt zuerst die Hintergrundfarbe, dann den normalen Inhalt."""
        bg = index.data(Qt.ItemDataRole.BackgroundRole)
        if isinstance(bg, QBrush) and bg.color().alpha() > 0 and bg.style() != Qt.BrushStyle.NoBrush:
            painter.save()
            painter.fillRect(option.rect, bg)
            painter.restore()
        super().paint(painter, option, index)


class DraggableDocumentView(QTableView):
    """
    QTableView mit Drag-Unterstuetzung fuer Dokumente.
    
    Beim Ziehen werden die IDs der ausgewaehlten Dokumente als Text uebertragen.
    Mehrfachauswahl bleibt beim Drag erhalten.
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._drag_start_pos = None
        self._drag_started = False
        self._clicked_on_selected = False
    
    def mousePressEvent(self, event):
        """Speichert Startposition fuer Drag und prueft ob auf Auswahl geklickt."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_pos = event.position().toPoint()
            self._drag_started = False
            
            # Pruefen ob auf eine bereits ausgewaehlte Zeile geklickt wurde
            index = self.indexAt(event.position().toPoint())
            if index.isValid() and self.selectionModel().isSelected(index):
                self._clicked_on_selected = True
                # Nicht an Parent weitergeben - verhindert Auswahl-Reset
                return
            else:
                self._clicked_on_selected = False
        
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        """Startet Drag wenn Maus weit genug bewegt wurde."""
        if not (event.buttons() & Qt.MouseButton.LeftButton):
            super().mouseMoveEvent(event)
            return
        
        if self._drag_start_pos is None:
            super().mouseMoveEvent(event)
            return
        
        # Pruefen ob Mindestdistanz ueberschritten
        distance = (event.position().toPoint() - self._drag_start_pos).manhattanLength()
        if distance < QApplication.startDragDistance():
            super().mouseMoveEvent(event)
            return
        
        # Drag starten (nur einmal)
        if not self._drag_started:
            self._drag_started = True
            self._start_drag()
    
    def mouseReleaseEvent(self, event):
        """Setzt Drag-Startposition zurueck und handhabt Klick auf Auswahl."""
        if self._clicked_on_selected and not self._drag_started:
            index = self.indexAt(event.position().toPoint())
            if index.isValid():
                self.clearSelection()
                self.setCurrentIndex(index)
                self.selectRow(index.row())
        
        self._drag_start_pos = None
        self._drag_started = False
        self._clicked_on_selected = False
        super().mouseReleaseEvent(event)
    
    def _start_drag(self):
        """Startet Drag mit Dokument-IDs als MIME-Daten."""
        # Sammle eindeutige Zeilen aus der Auswahl
        selected_rows = set()
        for index in self.selectedIndexes():
            selected_rows.add(index.row())
        
        if not selected_rows:
            return
        
        # Dokument-IDs ueber das Model holen
        doc_ids = []
        model = self.model()
        for row in selected_rows:
            index = model.index(row, DocumentTableModel.COL_FILENAME)
            doc = index.data(Qt.ItemDataRole.UserRole)
            if doc:
                doc_ids.append(str(doc.id))
        
        if not doc_ids:
            return
        
        # MIME-Daten erstellen
        mime_data = QMimeData()
        mime_data.setText(','.join(doc_ids))
        
        # Drag starten
        drag = QDrag(self)
        drag.setMimeData(mime_data)
        
        # Drag-Vorschau (Anzahl der Dokumente)
        count = len(doc_ids)
        from PySide6.QtGui import QPixmap
        
        pixmap = QPixmap(140, 32)
        pixmap.fill(QColor("#1a1a2e"))
        painter = QPainter(pixmap)
        painter.setPen(QColor("#ffffff"))
        painter.setFont(QFont("Segoe UI", 10))
        text = f"{count} Dokument{'e' if count > 1 else ''}"
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, text)
        painter.end()
        
        drag.setPixmap(pixmap)
        drag.setHotSpot(pixmap.rect().center())
        
        self._drag_start_pos = None
        drag.exec(Qt.DropAction.MoveAction)


# =============================================
# ATLAS Index - Volltextsuche
# =============================================

class SearchWorker(QThread):
    """
    Worker fuer nicht-blockierende ATLAS Index Volltextsuche.
    
    Fuehrt GET /documents/search?q=... im Hintergrund aus.
    """
    finished = Signal(list)   # List[SearchResult]
    error = Signal(str)       # Fehlermeldung
    
    def __init__(self, api_client: APIClient, query: str, limit: int = 200,
                 include_raw: bool = False, substring: bool = False, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.query = query
        self.limit = limit
        self.include_raw = include_raw
        self.substring = substring
    
    def run(self):
        try:
            docs_api = DocumentsAPI(self.api_client)
            results = docs_api.search_documents(
                self.query, self.limit,
                include_raw=self.include_raw,
                substring=self.substring
            )
            self.finished.emit(results)
        except Exception as e:
            logger.error(f"ATLAS Index Suche fehlgeschlagen: {e}")
            self.error.emit(str(e))


class SearchResultCard(QFrame):
    """
    Einzelne Ergebnis-Karte im ATLAS Index (Google-Stil).
    
    Zeigt: Dateiname (fett), Meta-Zeile (Box|VU|Datum), Text-Snippet mit Highlighting.
    """
    clicked = Signal(object)         # SearchResult
    double_clicked = Signal(object)  # SearchResult
    context_menu_requested = Signal(object, object)  # SearchResult, QPoint
    
    # Box-Emojis fuer Meta-Zeile
    _BOX_EMOJIS = {
        'gdv': '📊', 'courtage': '💰', 'sach': '🏠', 'leben': '❤️',
        'kranken': '🏥', 'sonstige': '📁', 'roh': '📦', 'eingang': '📬',
        'verarbeitung': '📥', 'falsch': '⚠️'
    }
    
    def __init__(self, result: SearchResult, query: str, parent=None):
        super().__init__(parent)
        self.result = result
        self.query = query
        self._setup_ui()
    
    def _setup_ui(self):
        from html import escape
        from i18n.de import ATLAS_INDEX_RESULT_ARCHIVED, ATLAS_INDEX_NO_TEXT
        
        doc = self.result.document
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Plain)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        # Hover-Effekt + Basis-Style
        border_color = BORDER_DEFAULT
        bg = BG_PRIMARY
        color_strip = ""
        if doc.display_color and doc.display_color in DOCUMENT_DISPLAY_COLORS:
            color_strip = f"border-left: 4px solid {doc.display_color};"
        
        self.setStyleSheet(f"""
            SearchResultCard {{
                background: {bg};
                border: 1px solid {border_color};
                border-radius: 6px;
                padding: 10px 12px;
                {color_strip}
            }}
            SearchResultCard:hover {{
                background: {BG_SECONDARY};
                border-color: {PRIMARY_500};
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        
        # Zeile 1: Dateiname (fett)
        filename_label = QLabel(f"📄 {escape(doc.original_filename)}")
        filename_label.setFont(QFont(FONT_BODY, int(FONT_SIZE_BODY.replace('pt', '').replace('px', '')), QFont.Weight.Bold))
        filename_label.setStyleSheet(f"color: {TEXT_PRIMARY}; border: none; background: transparent; padding: 0;")
        filename_label.setWordWrap(True)
        layout.addWidget(filename_label)
        
        # Zeile 2: Meta (Box | VU | Datum | Archiviert)
        box_emoji = self._BOX_EMOJIS.get(doc.box_type, '📁')
        box_name = BOX_DISPLAY_NAMES.get(doc.box_type, doc.box_type)
        box_color = BOX_COLORS.get(doc.box_type, TEXT_SECONDARY)
        
        meta_parts = [f'<span style="color:{box_color}; font-weight:600;">{box_emoji} {escape(box_name)}</span>']
        if doc.vu_name:
            meta_parts.append(escape(doc.vu_name))
        if doc.created_at:
            meta_parts.append(format_date_german(doc.created_at))
        if doc.is_archived:
            meta_parts.append(f'<span style="color:{WARNING};">{escape(ATLAS_INDEX_RESULT_ARCHIVED)}</span>')
        
        meta_label = QLabel(" &nbsp;|&nbsp; ".join(meta_parts))
        meta_label.setTextFormat(Qt.TextFormat.RichText)
        meta_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px; border: none; background: transparent; padding: 0;")
        layout.addWidget(meta_label)
        
        # Zeile 3: Text-Snippet mit Highlighting
        snippet_html = self._build_snippet(self.result.text_preview, self.query)
        if snippet_html:
            snippet_label = QLabel(snippet_html)
            snippet_label.setTextFormat(Qt.TextFormat.RichText)
            snippet_label.setWordWrap(True)
            snippet_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px; border: none; background: transparent; padding: 2px 0 0 0;")
            layout.addWidget(snippet_label)
        else:
            no_text_label = QLabel(f"<i>{escape(ATLAS_INDEX_NO_TEXT)}</i>")
            no_text_label.setTextFormat(Qt.TextFormat.RichText)
            no_text_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px; border: none; background: transparent; padding: 2px 0 0 0;")
            layout.addWidget(no_text_label)
    
    @staticmethod
    def _build_snippet(text_preview: Optional[str], query: str) -> Optional[str]:
        """
        Baut ein kontextuelles Snippet mit dem ersten Treffer fett hervorgehoben.
        
        - Sucht case-insensitive nach dem vollen Suchbegriff, dann nach Einzelwoertern
        - Zeigt ~100 Zeichen davor + Treffer + ~200 Zeichen danach
        - Schneidet an Wortgrenzen ab
        - HTML-escaped, Treffer-Wort in <b>
        """
        from html import escape
        
        if not text_preview or not text_preview.strip():
            return None
        
        # Einzeiliger Text (Newlines -> Spaces)
        clean_text = ' '.join(text_preview.split())
        text_lower = clean_text.lower()
        
        # Treffer finden: Erst voller Suchbegriff, dann Einzelwoerter
        match_term = None
        pos = -1
        
        # 1. Versuch: Voller Suchbegriff
        query_lower = query.lower().strip()
        pos = text_lower.find(query_lower)
        if pos >= 0:
            match_term = query.strip()
        
        # 2. Versuch: Einzelne Woerter (laengstes zuerst, da aussagekraeftiger)
        if pos < 0:
            words = [w for w in query.split() if len(w) >= 3]
            words.sort(key=len, reverse=True)
            for word in words:
                word_pos = text_lower.find(word.lower())
                if word_pos >= 0:
                    pos = word_pos
                    match_term = word
                    break
        
        if pos >= 0 and match_term:
            match_len = len(match_term)
            # Kontext um den Treffer: ~100 vor, ~200 nach
            start = max(0, pos - 100)
            end = min(len(clean_text), pos + match_len + 200)
            
            # An Wortgrenzen ausrichten (nicht mitten im Wort abschneiden)
            if start > 0:
                space_pos = clean_text.find(' ', start)
                if space_pos != -1 and space_pos < pos:
                    start = space_pos + 1
            if end < len(clean_text):
                space_pos = clean_text.rfind(' ', pos + match_len, end + 30)
                if space_pos != -1:
                    end = space_pos
            
            snippet = clean_text[start:end]
            
            # Prefix/Suffix Ellipsis
            prefix = "..." if start > 0 else ""
            suffix = "..." if end < len(clean_text) else ""
            
            # Treffer-Wort im Snippet hervorheben (nur erstes Vorkommen)
            snippet_lower = snippet.lower()
            match_pos = snippet_lower.find(match_term.lower())
            if match_pos >= 0:
                before = escape(snippet[:match_pos])
                matched = escape(snippet[match_pos:match_pos + match_len])
                after = escape(snippet[match_pos + match_len:])
                return f'{prefix}{before}<b style="color:{TEXT_PRIMARY};">{matched}</b>{after}{suffix}'
            
            return f'{prefix}{escape(snippet)}{suffix}'
        else:
            # Kein Treffer im Preview (nur Dateiname-Match) -> erste ~200 Zeichen
            snippet = clean_text[:200]
            if len(clean_text) > 200:
                # An Wortgrenze abschneiden
                space_pos = snippet.rfind(' ', 150)
                if space_pos != -1:
                    snippet = snippet[:space_pos]
                snippet += "..."
            return escape(snippet)
    
    def mouseDoubleClickEvent(self, event):
        """Doppelklick -> Vorschau oeffnen."""
        self.double_clicked.emit(self.result)
        event.accept()
    
    def mousePressEvent(self, event):
        """Einfacher Klick."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.result)
        event.accept()
    
    def contextMenuEvent(self, event):
        """Rechtsklick -> Kontextmenue."""
        self.context_menu_requested.emit(self.result, event.globalPos())
        event.accept()


class AtlasIndexWidget(QWidget):
    """
    ATLAS Index - Globale Volltextsuche ueber alle Dokumente.
    
    Virtuelle "Box" im Archiv, die server-seitige Suche mit FULLTEXT-Index
    auf document_ai_data.extracted_text nutzt. Snippet-basierte Ergebnisdarstellung.
    """
    # Signale fuer Interaktion mit dem ArchiveBoxesView
    preview_requested = Signal(object)       # Document -> Vorschau oeffnen
    show_in_box_requested = Signal(object)   # Document -> Zur Box wechseln
    download_requested = Signal(object)      # Document -> Download
    
    def __init__(self, api_client: APIClient, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self._search_worker: Optional[SearchWorker] = None
        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(400)
        self._debounce_timer.timeout.connect(self._execute_search)
        self._current_query = ""
        self._result_cards: List[SearchResultCard] = []
        self._setup_ui()
    
    def _setup_ui(self):
        from i18n.de import (
            ATLAS_INDEX_TITLE, ATLAS_INDEX_SEARCH_PLACEHOLDER,
            ATLAS_INDEX_LIVE_SEARCH, ATLAS_INDEX_ENTER_QUERY
        )
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # Header: Titel
        title = QLabel(f"🔎 {ATLAS_INDEX_TITLE}")
        title.setFont(QFont(FONT_HEADLINE, 18, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {TEXT_PRIMARY};")
        layout.addWidget(title)
        
        # Suchfeld
        search_row = QHBoxLayout()
        search_row.setSpacing(8)
        
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText(ATLAS_INDEX_SEARCH_PLACEHOLDER)
        self._search_input.setFont(QFont(FONT_BODY, 13))
        self._search_input.setMinimumHeight(38)
        self._search_input.setStyleSheet(f"""
            QLineEdit {{
                border: 2px solid {BORDER_DEFAULT};
                border-radius: {RADIUS_MD};
                padding: 6px 12px;
                font-size: 13px;
                background: {BG_PRIMARY};
                color: {TEXT_PRIMARY};
            }}
            QLineEdit:focus {{
                border-color: {PRIMARY_500};
            }}
        """)
        self._search_input.textChanged.connect(self._on_text_changed)
        self._search_input.returnPressed.connect(self._on_enter_pressed)
        search_row.addWidget(self._search_input)
        
        # Such-Button (sichtbar wenn Live-Suche deaktiviert)
        from i18n.de import ATLAS_INDEX_SEARCH_BUTTON
        self._search_btn = QPushButton(ATLAS_INDEX_SEARCH_BUTTON)
        self._search_btn.setMinimumHeight(38)
        self._search_btn.setFont(QFont(FONT_BODY, 13))
        self._search_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._search_btn.setStyleSheet(f"""
            QPushButton {{
                background: {ACCENT_500};
                color: white;
                border: none;
                border-radius: {RADIUS_MD};
                padding: 6px 20px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: {PRIMARY_900};
            }}
            QPushButton:pressed {{
                background: {PRIMARY_900};
            }}
        """)
        self._search_btn.clicked.connect(self._on_enter_pressed)
        self._search_btn.setVisible(False)  # Anfangs versteckt (Live-Suche ist an)
        search_row.addWidget(self._search_btn)
        
        layout.addLayout(search_row)
        
        # Checkboxen: Suchoptionen
        from i18n.de import ATLAS_INDEX_INCLUDE_RAW, ATLAS_INDEX_SUBSTRING_SEARCH
        
        options_row = QHBoxLayout()
        options_row.setSpacing(16)
        
        self._live_search_cb = QCheckBox(ATLAS_INDEX_LIVE_SEARCH)
        self._live_search_cb.setChecked(True)
        self._live_search_cb.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")
        self._live_search_cb.toggled.connect(self._on_live_search_toggled)
        options_row.addWidget(self._live_search_cb)
        
        self._include_raw_cb = QCheckBox(ATLAS_INDEX_INCLUDE_RAW)
        self._include_raw_cb.setChecked(False)
        self._include_raw_cb.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")
        self._include_raw_cb.toggled.connect(self._on_option_changed)
        options_row.addWidget(self._include_raw_cb)
        
        self._substring_cb = QCheckBox(ATLAS_INDEX_SUBSTRING_SEARCH)
        self._substring_cb.setChecked(False)
        self._substring_cb.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")
        self._substring_cb.toggled.connect(self._on_option_changed)
        options_row.addWidget(self._substring_cb)
        
        options_row.addStretch()
        layout.addLayout(options_row)
        
        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {BORDER_DEFAULT};")
        layout.addWidget(sep)
        
        # Ergebnis-Zaehler / Status
        self._status_label = QLabel(ATLAS_INDEX_ENTER_QUERY)
        self._status_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 13px; font-weight: 500;")
        layout.addWidget(self._status_label)
        
        # Ergebnis-Liste (scrollbar)
        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll_area.setStyleSheet(f"""
            QScrollArea {{
                border: none;
                background: transparent;
            }}
        """)
        
        self._results_container = QWidget()
        self._results_layout = QVBoxLayout(self._results_container)
        self._results_layout.setContentsMargins(0, 0, 8, 0)
        self._results_layout.setSpacing(8)
        self._results_layout.addStretch()
        
        self._scroll_area.setWidget(self._results_container)
        layout.addWidget(self._scroll_area, 1)  # stretch=1 -> nimmt restlichen Platz
    
    def _on_text_changed(self, text: str):
        """Reagiert auf Texteingabe im Suchfeld."""
        from i18n.de import ATLAS_INDEX_MIN_CHARS, ATLAS_INDEX_ENTER_QUERY
        
        text = text.strip()
        if len(text) < 3:
            self._debounce_timer.stop()
            if len(text) == 0:
                self._status_label.setText(ATLAS_INDEX_ENTER_QUERY)
            else:
                self._status_label.setText(ATLAS_INDEX_MIN_CHARS)
            self._clear_results()
            return
        
        self._current_query = text
        
        if self._live_search_cb.isChecked():
            # Live-Suche: Debounce 400ms
            self._debounce_timer.start()
        # Wenn Live-Suche deaktiviert: nichts tun (warten auf Enter)
    
    def _on_live_search_toggled(self, checked: bool):
        """Live-Suche Checkbox geaendert -> Such-Button ein-/ausblenden."""
        self._search_btn.setVisible(not checked)
        if not checked:
            self._debounce_timer.stop()
    
    def _on_enter_pressed(self):
        """Enter oder Such-Button gedrueckt -> sofort suchen."""
        text = self._search_input.text().strip()
        if len(text) >= 3:
            self._current_query = text
            self._debounce_timer.stop()
            self._execute_search()
    
    def _on_option_changed(self, checked: bool):
        """Checkbox geaendert -> erneut suchen wenn Ergebnisse vorhanden."""
        if self._current_query and len(self._current_query) >= 3:
            self._execute_search()
    
    def _execute_search(self):
        """Fuehrt die Suche per SearchWorker aus."""
        from i18n.de import ATLAS_INDEX_SEARCHING
        
        query = self._current_query
        if len(query) < 3:
            return
        
        # Laufenden Worker abbrechen
        if self._search_worker is not None and self._search_worker.isRunning():
            self._search_worker.disconnect()
            # Worker im Hintergrund auslaufen lassen
            self._search_worker = None
        
        self._status_label.setText(ATLAS_INDEX_SEARCHING)
        
        self._search_worker = SearchWorker(
            self.api_client, query,
            include_raw=self._include_raw_cb.isChecked(),
            substring=self._substring_cb.isChecked()
        )
        self._search_worker.finished.connect(self._on_search_finished)
        self._search_worker.error.connect(self._on_search_error)
        self._search_worker.start()
    
    def _on_search_finished(self, results: List[SearchResult]):
        """Callback wenn Suchergebnisse vorliegen."""
        from i18n.de import ATLAS_INDEX_RESULTS_COUNT, ATLAS_INDEX_NO_RESULTS
        
        self._clear_results()
        
        if not results:
            self._status_label.setText(ATLAS_INDEX_NO_RESULTS)
            return
        
        self._status_label.setText(ATLAS_INDEX_RESULTS_COUNT.format(count=len(results)))
        
        for result in results:
            card = SearchResultCard(result, self._current_query)
            card.double_clicked.connect(self._on_card_double_clicked)
            card.context_menu_requested.connect(self._on_card_context_menu)
            self._result_cards.append(card)
            # Vor dem Stretch einfuegen
            self._results_layout.insertWidget(self._results_layout.count() - 1, card)
    
    def _on_search_error(self, error_msg: str):
        """Callback bei Suchfehler."""
        self._clear_results()
        self._status_label.setText(f"Fehler: {error_msg}")
    
    def _clear_results(self):
        """Entfernt alle Ergebnis-Karten."""
        for card in self._result_cards:
            card.setParent(None)
            card.deleteLater()
        self._result_cards.clear()
    
    def _on_card_double_clicked(self, result: SearchResult):
        """Doppelklick auf Ergebnis-Karte -> Vorschau."""
        self.preview_requested.emit(result.document)
    
    def _on_card_context_menu(self, result: SearchResult, pos):
        """Rechtsklick auf Ergebnis-Karte -> Kontextmenue."""
        from i18n.de import (
            ATLAS_INDEX_PREVIEW, ATLAS_INDEX_DOWNLOAD, ATLAS_INDEX_SHOW_IN_BOX
        )
        
        menu = QMenu(self)
        
        preview_action = menu.addAction(f"👁 {ATLAS_INDEX_PREVIEW}")
        download_action = menu.addAction(f"💾 {ATLAS_INDEX_DOWNLOAD}")
        menu.addSeparator()
        box_name = BOX_DISPLAY_NAMES.get(result.document.box_type, result.document.box_type)
        show_in_box_action = menu.addAction(f"📂 {ATLAS_INDEX_SHOW_IN_BOX} ({box_name})")
        
        action = menu.exec(pos)
        if action == preview_action:
            self.preview_requested.emit(result.document)
        elif action == download_action:
            self.download_requested.emit(result.document)
        elif action == show_in_box_action:
            self.show_in_box_requested.emit(result.document)
    
    def focus_search(self):
        """Setzt Fokus auf das Suchfeld."""
        self._search_input.setFocus()
        self._search_input.selectAll()
    
    def cleanup(self):
        """Bereinigt laufende Worker."""
        self._debounce_timer.stop()
        if self._search_worker is not None and self._search_worker.isRunning():
            self._search_worker.disconnect()
            self._search_worker = None


class BoxSidebar(QWidget):
    """
    Sidebar mit Box-Navigation und Drag & Drop Unterstützung.
    
    Zeigt alle Boxen mit Anzahl und ermoeglicht Navigation.
    Dokumente koennen per Drag & Drop in Boxen verschoben werden.
    """
    box_selected = Signal(str)  # box_type oder '' fuer alle
    documents_dropped = Signal(list, str)  # doc_ids, target_box
    box_download_requested = Signal(str, str)  # box_type, mode ('zip' oder 'folder')
    smartscan_box_requested = Signal(str)  # box_type
    
    # Boxen die als Drop-Ziel erlaubt sind
    DROPPABLE_BOXES = {'gdv', 'courtage', 'sach', 'leben', 'kranken', 'sonstige'}
    
    # Admin-only Drop-Ziele (werden bei set_admin_mode hinzugefuegt)
    DROPPABLE_BOXES_ADMIN = {'falsch'}
    
    # Boxen die heruntergeladen werden koennen
    DOWNLOADABLE_BOXES = {'gdv', 'courtage', 'sach', 'leben', 'kranken', 'sonstige', 'eingang', 'roh'}
    
    # Admin-only Downloads
    DOWNLOADABLE_BOXES_ADMIN = {'falsch'}
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(220)
        self.setMaximumWidth(300)
        
        self._stats = BoxStats()
        self._current_box = ''
        self._is_admin = False
        self._smartscan_enabled = False
        
        # Instanz-Kopien der Drop/Download-Sets (damit set_admin_mode sicher ist)
        self.DROPPABLE_BOXES = set(BoxSidebar.DROPPABLE_BOXES)
        self.DOWNLOADABLE_BOXES = set(BoxSidebar.DOWNLOADABLE_BOXES)
        
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 8, 4, 8)
        layout.setSpacing(4)
        
        # Tree Widget fuer hierarchische Darstellung mit Drop-Unterstützung
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(12)
        self.tree.setRootIsDecorated(True)
        self.tree.itemClicked.connect(self._on_item_clicked)
        
        # Kontextmenue fuer Box-Download
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_box_context_menu)
        
        # Modernes Styling für die Sidebar
        self.tree.setStyleSheet(f"""
            QTreeWidget {{
                background-color: {BG_PRIMARY};
                border: none;
                outline: none;
                font-family: {FONT_BODY};
                font-size: 15px;
            }}
            QTreeWidget::item {{
                padding: 8px 6px;
                margin: 2px 2px;
                border-radius: 6px;
                border: 1px solid transparent;
            }}
            QTreeWidget::item:hover {{
                background-color: {PRIMARY_100};
                border: 1px solid {BORDER_DEFAULT};
            }}
            QTreeWidget::item:selected {{
                background-color: {PRIMARY_100};
                border: 1px solid {PRIMARY_500};
                color: {TEXT_PRIMARY};
            }}
            QTreeWidget::branch {{
                background: transparent;
            }}
            QTreeWidget::branch:has-children:!has-siblings:closed,
            QTreeWidget::branch:closed:has-children:has-siblings {{
                image: url(none);
                border-image: none;
            }}
            QTreeWidget::branch:open:has-children:!has-siblings,
            QTreeWidget::branch:open:has-children:has-siblings {{
                image: url(none);
                border-image: none;
            }}
        """)
        
        # Drag & Drop aktivieren
        self.tree.setAcceptDrops(True)
        self.tree.setDragDropMode(QTreeWidget.DragDropMode.DropOnly)
        
        # Drop-Events abfangen
        self.tree.dragEnterEvent = self._tree_drag_enter
        self.tree.dragMoveEvent = self._tree_drag_move
        self.tree.dropEvent = self._tree_drop
        
        # ATLAS Index (ganz oben, virtuelle Box fuer Volltextsuche)
        from i18n.de import ATLAS_INDEX_TITLE
        self.atlas_index_item = QTreeWidgetItem(self.tree)
        self.atlas_index_item.setText(0, f"🔎 {ATLAS_INDEX_TITLE}")
        self.atlas_index_item.setData(0, Qt.ItemDataRole.UserRole, "atlas_index")
        self.atlas_index_item.setFont(0, QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.atlas_index_item.setForeground(0, QBrush(QColor(PRIMARY_500)))
        
        # Separator nach ATLAS Index
        atlas_separator = QTreeWidgetItem(self.tree)
        atlas_separator.setText(0, "")
        atlas_separator.setFlags(Qt.ItemFlag.NoItemFlags)
        atlas_separator.setSizeHint(0, QSize(0, 8))
        
        # Verarbeitung (eingeklappt) - mit Pfeil-Indikator
        self.processing_item = QTreeWidgetItem(self.tree)
        self.processing_item.setText(0, "▶  📥 Verarbeitung (0)")
        self.processing_item.setData(0, Qt.ItemDataRole.UserRole, "processing_group")
        self.processing_item.setFont(0, QFont("Segoe UI", 11, QFont.Weight.DemiBold))
        self.processing_item.setExpanded(False)
        
        # Expand/Collapse Signal verbinden
        self.tree.itemExpanded.connect(self._on_item_expanded)
        self.tree.itemCollapsed.connect(self._on_item_collapsed)
        
        # Eingangsbox
        self.eingang_item = QTreeWidgetItem(self.processing_item)
        self.eingang_item.setText(0, "📬 Eingang (0)")
        self.eingang_item.setData(0, Qt.ItemDataRole.UserRole, "eingang")
        self.eingang_item.setFont(0, QFont("Segoe UI", 11))
        
        # Roh Archiv (unter Verarbeitung)
        self.roh_item = QTreeWidgetItem(self.processing_item)
        self.roh_item.setText(0, "📦 Rohdaten (0)")
        self.roh_item.setData(0, Qt.ItemDataRole.UserRole, "roh")
        self.roh_item.setFont(0, QFont("Segoe UI", 11))
        
        # Gesamt Archiv (unter Verarbeitung)
        self.gesamt_item = QTreeWidgetItem(self.processing_item)
        self.gesamt_item.setText(0, "🗂️ Gesamt (0)")
        self.gesamt_item.setData(0, Qt.ItemDataRole.UserRole, "")
        self.gesamt_item.setFont(0, QFont("Segoe UI", 11))
        
        # Separator
        separator = QTreeWidgetItem(self.tree)
        separator.setText(0, "")
        separator.setFlags(Qt.ItemFlag.NoItemFlags)
        separator.setSizeHint(0, QSize(0, 8))
        
        # Boxen mit Emojis und Archiviert-Sub-Boxen
        self.box_items: Dict[str, QTreeWidgetItem] = {}
        self.archived_items: Dict[str, QTreeWidgetItem] = {}
        
        # Box-Definitionen: (key, emoji, name)
        box_definitions = [
            ("gdv", "📊", "GDV"),
            ("courtage", "💰", "Courtage"),
            ("sach", "🏠", "Sach"),
            ("leben", "❤️", "Leben"),
            ("kranken", "🏥", "Kranken"),
            ("sonstige", "📁", "Sonstige"),
        ]
        
        for box_key, emoji, name in box_definitions:
            # Haupt-Box
            item = QTreeWidgetItem(self.tree)
            item.setText(0, f"{emoji} {name} (0)")
            item.setData(0, Qt.ItemDataRole.UserRole, box_key)
            item.setFont(0, QFont("Segoe UI", 11))
            self.box_items[box_key] = item
            
            # Archiviert-Sub-Box (als Kind)
            archived_item = QTreeWidgetItem(item)
            archived_item.setText(0, "📦 Archiviert (0)")
            archived_item.setData(0, Qt.ItemDataRole.UserRole, f"{box_key}_archived")
            archived_item.setFont(0, QFont("Segoe UI", 10))
            self.archived_items[box_key] = archived_item
            
            # Standardmaessig eingeklappt
            item.setExpanded(False)
        
        # Admin-only Boxen (initial versteckt)
        self.admin_box_items: Dict[str, QTreeWidgetItem] = {}
        self.admin_archived_items: Dict[str, QTreeWidgetItem] = {}
        
        admin_box_definitions = [
            ("falsch", "⚠️", "Falsch"),
        ]
        
        for box_key, emoji, name in admin_box_definitions:
            item = QTreeWidgetItem(self.tree)
            item.setText(0, f"{emoji} {name} (0)")
            item.setData(0, Qt.ItemDataRole.UserRole, box_key)
            item.setFont(0, QFont("Segoe UI", 11))
            self.admin_box_items[box_key] = item
            self.box_items[box_key] = item  # Auch in box_items fuer update_stats
            
            # Archiviert-Sub-Box
            archived_item = QTreeWidgetItem(item)
            archived_item.setText(0, "📦 Archiviert (0)")
            archived_item.setData(0, Qt.ItemDataRole.UserRole, f"{box_key}_archived")
            archived_item.setFont(0, QFont("Segoe UI", 10))
            self.admin_archived_items[box_key] = archived_item
            self.archived_items[box_key] = archived_item
            
            item.setExpanded(False)
            # Initial versteckt (wird per set_admin_mode sichtbar)
            item.setHidden(True)
        
        layout.addWidget(self.tree)
        
        # Kosten-Voranschlag Card (unter dem Tree, initial versteckt)
        self._cost_estimate_frame = QFrame()
        self._cost_estimate_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {ACCENT_100};
                border: 2px solid {ACCENT_500};
                border-radius: {RADIUS_MD};
                margin: 6px 2px;
            }}
        """)
        cost_layout = QVBoxLayout(self._cost_estimate_frame)
        cost_layout.setContentsMargins(10, 8, 10, 8)
        cost_layout.setSpacing(4)
        
        # Titel-Zeile mit Icon
        self._cost_title_label = QLabel("💰 Kostenvoranschlag")
        self._cost_title_label.setStyleSheet(f"""
            QLabel {{
                color: {PRIMARY_900};
                font-size: {FONT_SIZE_BODY};
                font-family: {FONT_BODY};
                font-weight: bold;
                background: transparent;
                border: none;
            }}
        """)
        cost_layout.addWidget(self._cost_title_label)
        
        # Betrag (gross und prominent)
        self._cost_amount_label = QLabel()
        self._cost_amount_label.setStyleSheet(f"""
            QLabel {{
                color: {ACCENT_500};
                font-size: 20px;
                font-family: {FONT_MONO};
                font-weight: bold;
                background: transparent;
                border: none;
            }}
        """)
        cost_layout.addWidget(self._cost_amount_label)
        
        # Beschreibungstext
        self._cost_desc_label = QLabel()
        self._cost_desc_label.setWordWrap(True)
        self._cost_desc_label.setStyleSheet(f"""
            QLabel {{
                color: {TEXT_SECONDARY};
                font-size: {FONT_SIZE_CAPTION};
                font-family: {FONT_BODY};
                background: transparent;
                border: none;
            }}
        """)
        cost_layout.addWidget(self._cost_desc_label)
        
        self._cost_estimate_frame.setVisible(False)
        self._avg_cost_per_doc: float = 0.0
        layout.addWidget(self._cost_estimate_frame)
        
        # Gesamt Archiv als Standard auswaehlen
        self.gesamt_item.setSelected(True)
    
    def _set_item_color(self, item: QTreeWidgetItem, box_type: str):
        """Setzt die Farbe eines Items basierend auf dem Box-Typ."""
        color = BOX_COLORS.get(box_type, "#9E9E9E")
        item.setForeground(0, QBrush(QColor(color)))
    
    def _on_item_expanded(self, item: QTreeWidgetItem):
        """Handler fuer das Aufklappen eines Items - aktualisiert den Pfeil."""
        if item == self.processing_item:
            # Pfeil von ▶ zu ▼ ändern
            current_text = item.text(0)
            if current_text.startswith("▶"):
                new_text = "▼" + current_text[1:]
                item.setText(0, new_text)
    
    def _on_item_collapsed(self, item: QTreeWidgetItem):
        """Handler fuer das Zuklappen eines Items - aktualisiert den Pfeil."""
        if item == self.processing_item:
            # Pfeil von ▼ zu ▶ ändern
            current_text = item.text(0)
            if current_text.startswith("▼"):
                new_text = "▶" + current_text[1:]
                item.setText(0, new_text)
    
    def _on_item_clicked(self, item: QTreeWidgetItem, column: int):
        """Handler fuer Klick auf ein Item."""
        box_type = item.data(0, Qt.ItemDataRole.UserRole)
        
        # Separator und Gruppen-Header ignorieren
        if box_type is None or box_type == "processing_group":
            return
        
        self._current_box = box_type
        self.box_selected.emit(box_type)
    
    def select_box(self, box_type: str):
        """Programmatisch eine Box auswaehlen (fuer 'In Box anzeigen' aus ATLAS Index).
        
        Args:
            box_type: Box-Key (z.B. 'sach', 'courtage_archived', '')
        """
        # Item im Baum finden
        target_item = self._find_tree_item(box_type)
        if target_item:
            self.tree.setCurrentItem(target_item)
            # Eltern-Item aufklappen falls noetig
            parent = target_item.parent()
            if parent:
                parent.setExpanded(True)
        
        self._current_box = box_type
        self.box_selected.emit(box_type)
    
    def _find_tree_item(self, box_type: str) -> Optional[QTreeWidgetItem]:
        """Findet ein QTreeWidgetItem anhand des box_type UserRole-Wertes."""
        def _search(item: QTreeWidgetItem) -> Optional[QTreeWidgetItem]:
            if item.data(0, Qt.ItemDataRole.UserRole) == box_type:
                return item
            for i in range(item.childCount()):
                result = _search(item.child(i))
                if result:
                    return result
            return None
        
        for i in range(self.tree.topLevelItemCount()):
            result = _search(self.tree.topLevelItem(i))
            if result:
                return result
        return None
    
    def _show_box_context_menu(self, position):
        """Zeigt Kontextmenue fuer Rechtsklick auf eine Box."""
        from i18n.de import BOX_DOWNLOAD_MENU, BOX_DOWNLOAD_AS_ZIP, BOX_DOWNLOAD_AS_FOLDER
        
        item = self.tree.itemAt(position)
        if not item:
            return
        
        box_type = item.data(0, Qt.ItemDataRole.UserRole)
        
        # Nur fuer herunterladbare Boxen anzeigen (keine Archiviert-Sub-Boxen, kein Separator)
        if not box_type or box_type == "processing_group":
            return
        
        # Archiviert-Boxen haben den Suffix "_archived"
        if box_type.endswith("_archived"):
            return
        
        # Leere Box "" (Gesamt) nicht anbieten - zu viele Dateien
        if box_type not in self.DOWNLOADABLE_BOXES:
            return
        
        # Pruefen ob Box Dokumente hat
        count = self._stats.get_count(box_type)
        if count == 0:
            return
        
        menu = QMenu(self)
        
        # Download-Untermenue
        download_menu = QMenu(BOX_DOWNLOAD_MENU, menu)
        
        zip_action = QAction(BOX_DOWNLOAD_AS_ZIP, self)
        zip_action.triggered.connect(
            lambda: self.box_download_requested.emit(box_type, 'zip')
        )
        download_menu.addAction(zip_action)
        
        folder_action = QAction(BOX_DOWNLOAD_AS_FOLDER, self)
        folder_action.triggered.connect(
            lambda: self.box_download_requested.emit(box_type, 'folder')
        )
        download_menu.addAction(folder_action)
        
        menu.addMenu(download_menu)
        
        # Smart!Scan Option (nur wenn in Admin-Einstellungen aktiviert)
        if self._smartscan_enabled:
            from i18n.de import SMARTSCAN_CONTEXT_BOX
            smartscan_action = QAction(SMARTSCAN_CONTEXT_BOX, self)
            smartscan_action.triggered.connect(
                lambda: self.smartscan_box_requested.emit(box_type)
            )
            menu.addAction(smartscan_action)
        
        menu.exec(self.tree.viewport().mapToGlobal(position))
    
    def set_avg_cost_per_doc(self, avg_cost: float):
        """Setzt die durchschnittlichen Kosten pro Dokument fuer die Kostenvoranschlag-Anzeige."""
        self._avg_cost_per_doc = avg_cost
        self._update_cost_estimate()
    
    def _update_cost_estimate(self):
        """Aktualisiert die Kosten-Voranschlag Anzeige basierend auf Eingangs-Dokumenten."""
        from i18n import de as texts
        eingang_count = self._stats.eingang if self._stats else 0
        
        if eingang_count > 1 and self._avg_cost_per_doc > 0:
            estimated_cost = eingang_count * self._avg_cost_per_doc
            self._cost_amount_label.setText(f"~${estimated_cost:.4f}")
            self._cost_desc_label.setText(
                texts.PROCESSING_ESTIMATED_COST.format(
                    count=eingang_count,
                    cost=f"{estimated_cost:.4f}"
                )
            )
            self._cost_estimate_frame.setVisible(True)
        else:
            self._cost_estimate_frame.setVisible(False)
    
    def update_stats(self, stats: BoxStats):
        """Aktualisiert die Anzahlen in der Sidebar."""
        self._stats = stats
        
        # Verarbeitung - nur Anzahl der zu verarbeitenden Dokumente (Eingang)
        pending_count = stats.eingang
        arrow = "▼" if self.processing_item.isExpanded() else "▶"
        self.processing_item.setText(0, f"{arrow}  📥 Verarbeitung ({pending_count})")
        self.eingang_item.setText(0, f"📬 Eingang ({stats.eingang})")
        self.roh_item.setText(0, f"📦 Rohdaten ({stats.roh})")
        
        # Kosten-Voranschlag aktualisieren
        self._update_cost_estimate()
        
        # Gesamt
        self.gesamt_item.setText(0, f"🗂️ Gesamt ({stats.total})")
        
        # Box-Definitionen: (key, emoji, name)
        box_definitions = [
            ("gdv", "📊", "GDV"),
            ("courtage", "💰", "Courtage"),
            ("sach", "🏠", "Sach"),
            ("leben", "❤️", "Leben"),
            ("kranken", "🏥", "Kranken"),
            ("sonstige", "📁", "Sonstige"),
        ]
        
        # Einzelne Boxen mit Emojis und Archiviert-Sub-Boxen
        for box_key, emoji, name in box_definitions:
            count = stats.get_count(box_key)
            archived_count = stats.get_count(f"{box_key}_archived")
            
            # Haupt-Box (ohne archivierte)
            self.box_items[box_key].setText(0, f"{emoji} {name} ({count})")
            
            # Archiviert-Sub-Box
            if box_key in self.archived_items:
                self.archived_items[box_key].setText(0, f"📦 Archiviert ({archived_count})")
        
        # Admin-only Boxen aktualisieren
        admin_box_definitions = [
            ("falsch", "⚠️", "Falsch"),
        ]
        for box_key, emoji, name in admin_box_definitions:
            if box_key in self.box_items:
                count = stats.get_count(box_key)
                archived_count = stats.get_count(f"{box_key}_archived")
                self.box_items[box_key].setText(0, f"{emoji} {name} ({count})")
                if box_key in self.archived_items:
                    self.archived_items[box_key].setText(0, f"📦 Archiviert ({archived_count})")
        
        # Verarbeitung ausklappen nur wenn Dokumente in Eingangsbox (nicht Roh)
        if stats.eingang > 0:
            self.processing_item.setExpanded(True)
    
    def set_admin_mode(self, is_admin: bool):
        """Aktiviert/Deaktiviert Admin-only Boxen in der Sidebar."""
        self._is_admin = is_admin
        
        # Admin-Boxen ein-/ausblenden
        for box_key, item in self.admin_box_items.items():
            item.setHidden(not is_admin)
        
        # Drop-Ziele erweitern/einschraenken
        if is_admin:
            self.DROPPABLE_BOXES = self.DROPPABLE_BOXES | self.DROPPABLE_BOXES_ADMIN
            self.DOWNLOADABLE_BOXES = self.DOWNLOADABLE_BOXES | self.DOWNLOADABLE_BOXES_ADMIN
        else:
            self.DROPPABLE_BOXES = self.DROPPABLE_BOXES - self.DROPPABLE_BOXES_ADMIN
            self.DOWNLOADABLE_BOXES = self.DOWNLOADABLE_BOXES - self.DOWNLOADABLE_BOXES_ADMIN
    
    def _tree_drag_enter(self, event):
        """Akzeptiert Drag-Events wenn gültige Dokument-IDs enthalten sind."""
        if event.mimeData().hasText():
            event.acceptProposedAction()
        else:
            event.ignore()
    
    def _tree_drag_move(self, event):
        """Hebt die Box unter dem Cursor hervor wenn sie ein gültiges Drop-Ziel ist."""
        item = self.tree.itemAt(event.position().toPoint())
        if item:
            box_type = item.data(0, Qt.ItemDataRole.UserRole)
            if box_type in self.DROPPABLE_BOXES:
                event.acceptProposedAction()
                # Visuelles Feedback - Item hervorheben
                self.tree.setCurrentItem(item)
                return
        event.ignore()
    
    def _tree_drop(self, event):
        """Verarbeitet den Drop und emittiert Signal zum Verschieben."""
        item = self.tree.itemAt(event.position().toPoint())
        if not item:
            event.ignore()
            return
        
        box_type = item.data(0, Qt.ItemDataRole.UserRole)
        if box_type not in self.DROPPABLE_BOXES:
            event.ignore()
            return
        
        # Dokument-IDs aus MIME-Daten extrahieren
        try:
            text = event.mimeData().text()
            doc_ids = [int(id_str) for id_str in text.split(',') if id_str.strip()]
            if doc_ids:
                self.documents_dropped.emit(doc_ids, box_type)
                event.acceptProposedAction()
            else:
                event.ignore()
        except (ValueError, AttributeError):
            event.ignore()


class SmartScanWorker(QThread):
    """Worker fuer SmartScan Versand mit Client-seitigem Chunking."""
    progress = Signal(int, int, str)  # current, total, status
    completed = Signal(int, dict)  # job_id, result  (NICHT 'finished' - wuerde QThread.finished ueberschreiben!)
    error = Signal(str)
    
    def __init__(self, api_client, mode: str, document_ids: list = None,
                 box_type: str = None, archive_after: bool = False,
                 recolor_after: bool = False, recolor_color: str = None):
        super().__init__()
        self._api_client = api_client
        self._mode = mode
        self._document_ids = document_ids
        self._box_type = box_type
        self._archive_after = archive_after
        self._recolor_after = recolor_after
        self._recolor_color = recolor_color
        self._cancelled = False
    
    def cancel(self):
        self._cancelled = True
    
    def run(self):
        import uuid
        try:
            from api.smartscan import SmartScanAPI
            api = SmartScanAPI(self._api_client)
            
            client_request_id = str(uuid.uuid4())[:16]
            
            # Job starten
            result = api.send(
                mode=self._mode,
                document_ids=self._document_ids,
                box_type=self._box_type,
                client_request_id=client_request_id
            )
            
            if not result or not result.get('job_id'):
                self.error.emit("Versand konnte nicht gestartet werden.")
                return
            
            job_id = result['job_id']
            total = result.get('total', 0)
            processed = result.get('processed', 0)
            remaining = result.get('remaining', total)
            
            self.progress.emit(processed, total, "Versendet...")
            
            # Chunks verarbeiten
            max_iterations = (total // 10) + 5  # Sicherheitslimit
            iteration = 0
            
            while remaining > 0 and not self._cancelled and iteration < max_iterations:
                iteration += 1
                chunk_result = api.process_chunk(job_id)
                
                if not chunk_result:
                    self.error.emit("Chunk-Verarbeitung fehlgeschlagen.")
                    return
                
                processed += chunk_result.get('processed', 0)
                remaining = chunk_result.get('remaining', 0)
                status = chunk_result.get('status', '')
                
                self.progress.emit(processed, total, f"Versendet: {processed}/{total}")
                
                if status in ('sent', 'partial', 'failed'):
                    break
            
            if self._cancelled:
                self.error.emit("Versand abgebrochen.")
                return
            
            # Ergebnis holen
            final = api.get_job_details(job_id)
            
            # Post-Send-Aktionen: Faerben und/oder Archivieren
            if self._document_ids and (self._recolor_after or self._archive_after):
                try:
                    from api.documents import DocumentsAPI
                    docs_api = DocumentsAPI(self._api_client)
                    
                    if self._recolor_after and self._recolor_color:
                        self.progress.emit(processed, total, "Dokumente werden gefaerbt...")
                        docs_api.set_documents_color(self._document_ids, self._recolor_color)
                    
                    if self._archive_after:
                        self.progress.emit(processed, total, "Dokumente werden archiviert...")
                        docs_api.archive_documents(self._document_ids)
                        
                except Exception as e:
                    logger.warning(f"Post-Send-Aktion fehlgeschlagen: {e}")
            
            self.completed.emit(job_id, final or result)
            
        except Exception as e:
            logger.error(f"SmartScan Worker Fehler: {e}")
            self.error.emit(str(e))


class ArchiveBoxesView(QWidget):
    """
    Dokumentenarchiv mit Box-System.
    
    Ersetzt die alte ArchiveView mit neuem Layout:
    - Sidebar links mit Box-Navigation
    - Hauptbereich rechts mit Dokumententabelle
    
    Features:
    - Zentraler Cache fuer Server-Daten
    - Auto-Refresh alle 30 Sekunden
    - Daten bleiben beim View-Wechsel erhalten
    """
    
    # Signal wenn ein GDV-Dokument geoeffnet werden soll
    open_gdv_requested = Signal(int, str)  # doc_id, original_filename
    
    def __init__(self, api_client: APIClient, auth_api=None, parent=None):
        super().__init__(parent)
        
        self.api_client = api_client
        self.auth_api = auth_api
        self.docs_api = DocumentsAPI(api_client)
        
        # Cache-Service initialisieren
        from services.data_cache import get_cache_service
        self._cache = get_cache_service(api_client)
        # WICHTIG: QueuedConnection verwenden, da Signals aus Background-Thread kommen!
        # Ohne QueuedConnection kann die App einfrieren (Deadlock/Race Condition)
        self._cache.documents_updated.connect(
            self._on_cache_documents_updated, 
            Qt.ConnectionType.QueuedConnection
        )
        self._cache.stats_updated.connect(
            self._on_cache_stats_updated,
            Qt.ConnectionType.QueuedConnection
        )
        self._cache.refresh_started.connect(
            self._on_cache_refresh_started,
            Qt.ConnectionType.QueuedConnection
        )
        self._cache.refresh_finished.connect(
            self._on_cache_refresh_finished,
            Qt.ConnectionType.QueuedConnection
        )
        
        self._documents: List[Document] = []
        self._current_box = ''  # '' = Alle
        self._stats = BoxStats()
        
        # Worker-Referenzen (wichtig fuer Thread-Sicherheit!)
        self._load_worker = None
        self._stats_worker = None
        self._upload_worker = None
        self._move_worker = None
        self._ai_rename_worker = None
        self._processing_worker = None
        self._download_worker = None
        self._multi_upload_worker = None
        self._credits_worker = None
        self._preview_worker = None
        self._cost_stats_worker = None
        self._history_worker = None
        
        # Debounce-Timer fuer Historie-Laden (300ms)
        self._history_debounce_timer = None
        self._pending_history_doc_id = None
        
        # Aufgeschobene Dokumente (wenn View nicht sichtbar bei Callback)
        self._pending_documents = None
        self._pending_force_rebuild = False
        
        # Persistenter Vorschau-Cache (Dateien werden nur 1x heruntergeladen)
        self._preview_cache_dir = os.path.join(tempfile.gettempdir(), 'bipro_preview_cache')
        os.makedirs(self._preview_cache_dir, exist_ok=True)
        self._preview_progress = None
        self._preview_cancelled = False
        
        # Liste aller aktiven Worker fuer Cleanup
        self._active_workers: List[QThread] = []
        
        # Flag ob erste Ladung erfolgt ist
        self._initial_load_done = False
        self._missing_ai_data_checked = False
        
        # Fingerprint der aktuellen Dokumente (verhindert unnoetige Tabellen-Rebuilds)
        self._documents_fingerprint: str = ""
        
        # Tracking: Wann wurde welche Box zuletzt manuell aktualisiert?
        # Key: box_type (oder '' fuer alle), Value: datetime
        self._last_manual_refresh: Dict[str, datetime] = {}
        
        # Tracking: Welche Boxen wurden seit dem letzten manuellen Refresh bereits geladen?
        # Key: box_type (oder '' fuer alle), Value: datetime
        self._last_box_load: Dict[str, datetime] = {}
        
        # SmartScan-Enabled Status (wird nach _setup_ui via _load_smartscan_status aktualisiert)
        self._smartscan_enabled = False
        
        self._setup_ui()
        self._setup_shortcuts()
        
        # Loading-Overlay erstellen (ueber der Tabelle)
        self._loading_overlay = LoadingOverlay(self)
        self._loading_overlay.setVisible(False)
        
        # Processing-Overlay erstellen (fuer Dokumentenverarbeitung)
        self._processing_overlay = ProcessingProgressOverlay(self)
        self._processing_overlay.close_requested.connect(self._on_processing_overlay_closed)
        
        # Speicher fuer Undo-Funktion beim Verschieben
        self._last_move_data = None  # (doc_ids, original_boxes, target_box)
        
        # Admin-Mode fuer Sidebar setzen (Falsch-Box nur fuer Admins)
        self._is_admin = False
        if self.auth_api and self.auth_api.current_user:
            self._is_admin = self.auth_api.current_user.is_admin
        self.sidebar.set_admin_mode(self._is_admin)
        
        # SmartScan-Enabled Status cachen (fuer Kontextmenue- und Button-Sichtbarkeit)
        self._smartscan_enabled = False
        self._load_smartscan_status()
        self.sidebar._smartscan_enabled = self._smartscan_enabled
        if hasattr(self, '_smartscan_btn'):
            self._smartscan_btn.setVisible(self._smartscan_enabled)
        
        # Historie-Toggle-Button: Nur sichtbar wenn Berechtigung vorhanden
        self._history_enabled = self._has_history_permission()
        if hasattr(self, '_history_toggle_btn'):
            self._history_toggle_btn.setVisible(self._history_enabled)
        
        # Initiales Laden VERZÖGERT - erst nachdem Qt die View gerendert hat.
        # Verhindert Freeze beim ersten Wechsel ins Archiv, da _populate_table()
        # mit 500+ Dokumenten synchron laeuft und Qt sonst alle Zeilen in einem
        # einzigen Layout-/Paint-Zyklus verarbeiten muss bevor die View sichtbar wird.
        QTimer.singleShot(0, lambda: self._refresh_all(force_refresh=False))
        
        # Durchschnittliche Verarbeitungskosten laden (fuer Kostenvoranschlag)
        self._load_avg_cost_stats()
        
        # Auto-Refresh starten (alle 30 Sekunden)
        self._cache.start_auto_refresh(20)
    
    def _load_smartscan_status(self):
        """Laedt den SmartScan-Enabled-Status vom Server (fuer Kontextmenue-Sichtbarkeit)."""
        try:
            from api.smartscan import SmartScanAPI
            smartscan_api = SmartScanAPI(self.api_client)
            settings = smartscan_api.get_settings()
            # enabled kann String "0"/"1" oder int 0/1 sein - immer ueber int() konvertieren
            self._smartscan_enabled = bool(settings and int(settings.get('enabled', 0) or 0))
        except Exception as e:
            logger.warning(f"SmartScan-Status konnte nicht geladen werden: {e}")
            self._smartscan_enabled = False
    
    def _register_worker(self, worker: QThread):
        """Registriert einen Worker fuer sauberes Cleanup."""
        self._active_workers.append(worker)
        # Wenn Worker fertig, aus Liste entfernen und aufräumen
        worker.finished.connect(lambda: self._unregister_worker(worker))
    
    def _unregister_worker(self, worker: QThread):
        """Entfernt einen Worker aus der aktiven Liste."""
        if worker in self._active_workers:
            self._active_workers.remove(worker)
        if getattr(self, '_preview_worker', None) is worker:
            self._preview_worker = None
        # Sicher löschen
        worker.deleteLater()
    
    def _is_worker_running(self, attr_name: str) -> bool:
        """Prueft sicher ob ein Worker noch laeuft (C++-Objekt kann bereits geloescht sein)."""
        worker = getattr(self, attr_name, None)
        if worker is None:
            return False
        try:
            return worker.isRunning()
        except RuntimeError:
            # C++-Objekt bereits geloescht (deleteLater), Referenz aufraeumen
            setattr(self, attr_name, None)
            return False

    def get_blocking_operations(self) -> list:
        """Gibt Liste von laufenden Operationen zurueck, die das Schliessen verhindern."""
        from i18n import de as texts
        blocking = []

        # KI-Verarbeitung laeuft
        if self._is_worker_running('_processing_worker'):
            blocking.append(texts.CLOSE_BLOCKED_PROCESSING)

        # Verzoegerter Kosten-Check laeuft
        if self._is_worker_running('_delayed_cost_worker'):
            blocking.append(texts.CLOSE_BLOCKED_COST_CHECK)

        # SmartScan-Versand laeuft
        if self._is_worker_running('_smartscan_worker'):
            blocking.append(texts.CLOSE_BLOCKED_SMARTSCAN)

        return blocking

    def closeEvent(self, event):
        """Wird aufgerufen wenn das Widget geschlossen wird."""
        # Historie-Timer stoppen
        if self._history_debounce_timer is not None:
            self._history_debounce_timer.stop()
        
        # Alle laufenden Worker stoppen
        for worker in self._active_workers[:]:  # Kopie der Liste
            if worker.isRunning():
                logger.info(f"Warte auf Worker: {worker.__class__.__name__}")
                # Versuche abzubrechen falls möglich
                if hasattr(worker, 'cancel'):
                    worker.cancel()
                # Kurz warten
                if not worker.wait(2000):  # 2 Sekunden Timeout
                    logger.warning(f"Worker {worker.__class__.__name__} antwortet nicht, terminiere...")
                    worker.terminate()
                    worker.wait(1000)
        
        self._active_workers.clear()
        
        # ATLAS Index Widget bereinigen
        if hasattr(self, '_atlas_index_widget'):
            self._atlas_index_widget.cleanup()
        
        super().closeEvent(event)
    
    def resizeEvent(self, event):
        """Positioniert die Overlays bei Groessenaenderung."""
        super().resizeEvent(event)
        if hasattr(self, '_loading_overlay'):
            self._loading_overlay.setGeometry(self.rect())
        if hasattr(self, '_processing_overlay'):
            self._processing_overlay.setGeometry(self.rect())
    
    def _on_processing_overlay_closed(self):
        """Callback wenn das Processing-Overlay geschlossen wird."""
        # Daten neu laden
        self._refresh_all()
    
    def _show_loading(self, status: str = ""):
        """Zeigt das Loading-Overlay."""
        if hasattr(self, '_loading_overlay'):
            self._loading_overlay.set_status(status)
            self._loading_overlay.setGeometry(self.rect())
            self._loading_overlay.raise_()
            self._loading_overlay.setVisible(True)
            # Event-Loop kurz verarbeiten damit Overlay sofort sichtbar ist
            QApplication.processEvents()
    
    def _hide_loading(self):
        """Versteckt das Loading-Overlay."""
        if hasattr(self, '_loading_overlay'):
            self._loading_overlay.setVisible(False)
    
    def showEvent(self, event):
        """Wird aufgerufen wenn der View sichtbar wird (z.B. Rueckkehr aus BiPRO/Admin)."""
        super().showEvent(event)
        # Aufgeschobene Dokumente anzeigen (wurden geladen waehrend View unsichtbar war)
        if self._pending_documents is not None:
            logger.debug("Archiv sichtbar - fuehre aufgeschobenen Tabellen-Rebuild aus")
            self._apply_filters_and_display(
                self._pending_documents,
                force_rebuild=self._pending_force_rebuild
            )
            self._pending_documents = None
            self._pending_force_rebuild = False
    
    def _setup_ui(self):
        """UI aufbauen."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Splitter fuer Sidebar und Hauptbereich
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # ========== SIDEBAR ==========
        self.sidebar = BoxSidebar()
        self.sidebar.box_selected.connect(self._on_box_selected)
        self.sidebar.documents_dropped.connect(self._on_documents_dropped)
        self.sidebar.box_download_requested.connect(self._download_box)
        self.sidebar.smartscan_box_requested.connect(self._smartscan_box)
        splitter.addWidget(self.sidebar)
        
        # ========== HAUPTBEREICH ==========
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # Header mit Titel und Buttons
        header = self._create_header()
        main_layout.addLayout(header)
        
        # Filter-Bereich
        filter_group = self._create_filter_group()
        main_layout.addWidget(filter_group)
        
        # Dokumenten-Tabelle
        self._create_table()
        main_layout.addWidget(self.table)
        
        # Status-Zeile
        self.status_label = QLabel("Lade Dokumente...")
        self.status_label.setStyleSheet("color: gray;")
        main_layout.addWidget(self.status_label)
        
        # Inner-Splitter: Tabelle + Historie-Panel
        self._inner_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._inner_splitter.addWidget(main_widget)
        
        # Historie-Panel (rechts neben Tabelle, standardmaessig ausgeblendet)
        self._history_panel = DocumentHistoryPanel()
        self._history_panel.close_requested.connect(self._hide_history_panel)
        self._history_panel.setVisible(False)
        self._inner_splitter.addWidget(self._history_panel)
        
        # Inner-Splitter-Proportionen (Tabelle : Historie = 3:1)
        self._inner_splitter.setSizes([800, 0])
        
        # ========== CONTENT STACK (Tabelle vs. ATLAS Index) ==========
        self._content_stack = QStackedWidget()
        self._content_stack.addWidget(self._inner_splitter)  # Page 0: Normale Archiv-Tabelle
        
        # ATLAS Index Widget (Page 1: Volltextsuche)
        self._atlas_index_widget = AtlasIndexWidget(self.api_client)
        self._atlas_index_widget.preview_requested.connect(self._on_atlas_preview)
        self._atlas_index_widget.download_requested.connect(self._on_atlas_download)
        self._atlas_index_widget.show_in_box_requested.connect(self._on_atlas_show_in_box)
        self._content_stack.addWidget(self._atlas_index_widget)  # Page 1: ATLAS Index
        
        splitter.addWidget(self._content_stack)
        
        # Splitter-Proportionen (Sidebar : Hauptbereich = 1:4)
        splitter.setSizes([200, 800])
        
        layout.addWidget(splitter)
    
    # ========================================
    # Tastenkuerzel / Shortcuts
    # ========================================
    
    def _setup_shortcuts(self):
        """
        Richtet Tastenkuerzel fuer das Dokumentenarchiv ein.
        
        Alle Shortcuts sind auf WidgetWithChildrenShortcut beschraenkt,
        d.h. sie wirken nur wenn das Archiv oder ein Kind-Widget den Fokus hat.
        """
        shortcuts = [
            # F2 - Umbenennen
            (QKeySequence(Qt.Key.Key_F2), self._shortcut_rename),
            # Entf - Loeschen
            (QKeySequence(Qt.Key.Key_Delete), self._shortcut_delete),
            # Strg+A - Alle auswaehlen
            (QKeySequence.StandardKey.SelectAll, self._shortcut_select_all),
            # Strg+D - Download
            (QKeySequence("Ctrl+D"), self._download_selected),
            # Strg+F - Suchen/Filtern (Fokus auf Suchfeld)
            (QKeySequence.StandardKey.Find, self._shortcut_focus_search),
            # Strg+U - Upload
            (QKeySequence("Ctrl+U"), self._upload_document),
            # Enter - Vorschau oeffnen
            (QKeySequence(Qt.Key.Key_Return), self._shortcut_preview),
            # Esc - Auswahl aufheben / Suche leeren
            (QKeySequence(Qt.Key.Key_Escape), self._shortcut_escape),
            # Strg+Shift+A - Archivieren
            (QKeySequence("Ctrl+Shift+A"), self._shortcut_archive),
            # F5 - Aktualisieren
            (QKeySequence(Qt.Key.Key_F5), lambda: self._refresh_all(force_refresh=True)),
        ]
        
        for key_seq, handler in shortcuts:
            shortcut = QShortcut(key_seq, self)
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            shortcut.activated.connect(handler)
    
    def _shortcut_rename(self):
        """Shortcut-Handler fuer F2 - Umbenennen eines einzelnen Dokuments."""
        from i18n.de import SHORTCUT_SELECT_ONE_RENAME
        
        selected = self._get_selected_documents()
        if len(selected) == 1:
            self._rename_document(selected[0])
        elif len(selected) > 1:
            self._toast_manager.show_info(SHORTCUT_SELECT_ONE_RENAME)
    
    def _shortcut_delete(self):
        """Shortcut-Handler fuer Entf - Loeschen."""
        # Del im Suchfeld soll Text loeschen, nicht Dokumente
        if self.search_input.hasFocus():
            return
        self._delete_selected()
    
    def _shortcut_select_all(self):
        """Shortcut-Handler fuer Strg+A - Alle auswaehlen."""
        # Im Suchfeld: Text auswaehlen (Standard-Verhalten)
        if self.search_input.hasFocus():
            self.search_input.selectAll()
        else:
            self.table.selectAll()
            self.table.setFocus()
    
    def _shortcut_focus_search(self):
        """Shortcut-Handler fuer Strg+F - Fokus auf Suchfeld."""
        self.search_input.setFocus()
        self.search_input.selectAll()
    
    def _shortcut_preview(self):
        """Shortcut-Handler fuer Enter - Vorschau oeffnen."""
        # Enter im Suchfeld oder Filter soll nicht Vorschau oeffnen
        if self.search_input.hasFocus():
            return
        # Auch nicht bei aktiven ComboBoxen
        for combo in (self.source_filter, self.type_filter, self.ki_filter):
            if combo.hasFocus():
                return
        self._preview_selected()
    
    def _shortcut_escape(self):
        """Shortcut-Handler fuer Esc - Auswahl aufheben / Suche leeren."""
        if self.search_input.hasFocus():
            # Erst Suchtext leeren, dann Fokus auf Tabelle
            if self.search_input.text():
                self.search_input.clear()
            self.table.setFocus()
        else:
            self.table.clearSelection()
            self.table.setFocus()
    
    def _shortcut_archive(self):
        """Shortcut-Handler fuer Strg+Shift+A - Ausgewaehlte archivieren."""
        selected = self._get_selected_documents()
        if selected:
            self._archive_documents(selected)
    
    def _create_header(self) -> QHBoxLayout:
        """Erstellt den Header mit Titel und Buttons (ACENCIA Design)."""
        header_layout = QHBoxLayout()
        
        # Titel (wird dynamisch aktualisiert)
        self.title_label = QLabel("Gesamt Archiv")
        self.title_label.setStyleSheet(f"""
            font-family: {FONT_HEADLINE};
            font-size: {FONT_SIZE_H2};
            color: {TEXT_PRIMARY};
            font-weight: 400;
        """)
        header_layout.addWidget(self.title_label)
        
        header_layout.addStretch()
        
        # OpenRouter Credits (subtil)
        self.credits_label = QLabel("")
        self.credits_label.setStyleSheet(f"""
            color: {TEXT_SECONDARY};
            font-size: {FONT_SIZE_CAPTION};
            font-family: {FONT_BODY};
        """)
        self.credits_label.setToolTip("KI-Provider Guthaben / Kosten")
        header_layout.addWidget(self.credits_label)
        
        header_layout.addSpacing(20)
        
        from i18n.de import (
            SHORTCUT_PROCESS_TOOLTIP, SHORTCUT_REFRESH_TOOLTIP,
            SHORTCUT_PREVIEW_TOOLTIP, SHORTCUT_DOWNLOAD_TOOLTIP,
            SHORTCUT_UPLOAD_TOOLTIP
        )
        
        # Verarbeiten-Button (PRIMÄR - Orange)
        self.process_btn = QPushButton("Verarbeiten")
        self.process_btn.setToolTip(SHORTCUT_PROCESS_TOOLTIP)
        self.process_btn.setStyleSheet(get_button_primary_style())
        self.process_btn.clicked.connect(self._start_processing)
        header_layout.addWidget(self.process_btn)
        
        # Aktualisieren (Sekundär) - Erzwingt Server-Reload
        refresh_btn = QPushButton("Aktualisieren")
        refresh_btn.setStyleSheet(get_button_secondary_style())
        refresh_btn.setToolTip(SHORTCUT_REFRESH_TOOLTIP)
        refresh_btn.clicked.connect(lambda: self._refresh_all(force_refresh=True))
        header_layout.addWidget(refresh_btn)
        
        # Vorschau (Ghost)
        self.preview_btn = QPushButton("Vorschau")
        self.preview_btn.setStyleSheet(get_button_ghost_style())
        self.preview_btn.setToolTip(SHORTCUT_PREVIEW_TOOLTIP)
        self.preview_btn.clicked.connect(self._preview_selected)
        header_layout.addWidget(self.preview_btn)
        
        # Download (Ghost)
        self.download_btn = QPushButton("Herunterladen")
        self.download_btn.setStyleSheet(get_button_ghost_style())
        self.download_btn.setToolTip(SHORTCUT_DOWNLOAD_TOOLTIP)
        self.download_btn.clicked.connect(self._download_selected)
        header_layout.addWidget(self.download_btn)
        
        # Upload (Sekundär)
        self.upload_btn = QPushButton("Hochladen")
        self.upload_btn.setStyleSheet(get_button_secondary_style())
        self.upload_btn.setToolTip(SHORTCUT_UPLOAD_TOOLTIP)
        self.upload_btn.clicked.connect(self._upload_document)
        header_layout.addWidget(self.upload_btn)
        
        # Historie-Toggle (Ghost, nur sichtbar mit Berechtigung)
        from i18n.de import HISTORY_TOGGLE_TOOLTIP, HISTORY_PANEL_TITLE
        self._history_toggle_btn = QPushButton("⏱ " + HISTORY_PANEL_TITLE)
        self._history_toggle_btn.setCheckable(True)
        self._history_toggle_btn.setChecked(False)
        self._history_toggle_btn.setToolTip(HISTORY_TOGGLE_TOOLTIP)
        self._history_toggle_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {TEXT_SECONDARY};
                border: 1px solid {BORDER_DEFAULT};
                border-radius: {RADIUS_MD};
                padding: 6px 12px;
                font-size: {FONT_SIZE_BODY};
            }}
            QPushButton:hover {{
                background-color: {BG_SECONDARY};
                color: {TEXT_PRIMARY};
            }}
            QPushButton:checked {{
                background-color: {PRIMARY_100};
                color: {PRIMARY_900};
                border-color: {PRIMARY_500};
            }}
        """)
        self._history_toggle_btn.toggled.connect(self._on_history_toggle)
        self._history_toggle_btn.setVisible(False)  # Sichtbarkeit wird in __init__ gesetzt
        header_layout.addWidget(self._history_toggle_btn)
        
        return header_layout
    
    def _create_filter_group(self) -> QGroupBox:
        """Erstellt den Filter-Bereich."""
        filter_group = QGroupBox("Filter")
        filter_layout = QHBoxLayout(filter_group)
        
        # Quelle-Filter
        filter_layout.addWidget(QLabel("Quelle:"))
        self.source_filter = QComboBox()
        self.source_filter.addItem("Alle", "")
        self.source_filter.addItem("BiPRO", "bipro_auto")
        self.source_filter.addItem("Manuell", "manual_upload")
        self.source_filter.addItem("Scan", "scan")
        self.source_filter.currentIndexChanged.connect(self._apply_filter)
        filter_layout.addWidget(self.source_filter)
        
        # Art-Filter (Dateityp)
        filter_layout.addWidget(QLabel("Art:"))
        self.type_filter = QComboBox()
        self.type_filter.addItem("Alle", "")
        self.type_filter.addItem("PDF", "PDF")
        self.type_filter.addItem("GDV", "GDV")
        self.type_filter.addItem("XML", "XML")
        self.type_filter.addItem("Excel", "Excel")
        self.type_filter.currentIndexChanged.connect(self._apply_filter)
        filter_layout.addWidget(self.type_filter)
        
        # KI-Filter
        filter_layout.addWidget(QLabel("KI:"))
        self.ki_filter = QComboBox()
        self.ki_filter.addItem("Alle", "")
        self.ki_filter.addItem("Verarbeitet", "yes")
        self.ki_filter.addItem("Nicht verarbeitet", "no")
        self.ki_filter.currentIndexChanged.connect(self._apply_filter)
        filter_layout.addWidget(self.ki_filter)
        
        # Suche
        from i18n.de import SHORTCUT_SEARCH_PLACEHOLDER
        filter_layout.addWidget(QLabel("Suche:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(SHORTCUT_SEARCH_PLACEHOLDER)
        self.search_input.textChanged.connect(self._filter_table)
        filter_layout.addWidget(self.search_input)
        
        # Zurücksetzen-Button
        reset_btn = QPushButton("Zurücksetzen")
        reset_btn.setToolTip("Filter und Sortierung zurücksetzen")
        reset_btn.clicked.connect(self._reset_filters)
        filter_layout.addWidget(reset_btn)
        
        # Smart!Scan Button (gruen, nur sichtbar wenn SmartScan aktiviert)
        from i18n.de import SMARTSCAN_TOOLBAR_BUTTON
        self._smartscan_btn = QPushButton(f"  {SMARTSCAN_TOOLBAR_BUTTON}")
        self._smartscan_btn.setFixedHeight(30)
        self._smartscan_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 4px 14px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: #43A047;
            }}
            QPushButton:pressed {{
                background-color: #388E3C;
            }}
            QPushButton:disabled {{
                background-color: #A5D6A7;
                color: #E8F5E9;
            }}
        """)
        self._smartscan_btn.clicked.connect(self._on_smartscan_btn_clicked)
        self._smartscan_btn.setVisible(self._smartscan_enabled)
        filter_layout.addWidget(self._smartscan_btn)
        
        filter_layout.addStretch()
        
        return filter_group
    
    def _create_table(self):
        """Erstellt die Dokumenten-Tabelle mit Model/View-Architektur."""
        # Model + Proxy erstellen
        self._doc_model = DocumentTableModel(self)
        self._proxy_model = DocumentSortFilterProxy(self)
        self._proxy_model.setSourceModel(self._doc_model)
        
        # View erstellen und Model setzen
        self.table = DraggableDocumentView()
        self.table.setModel(self._proxy_model)
        
        # Header konfigurieren
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)   # Duplikat-Icon (schmal)
        header.resizeSection(0, 30)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)   # Leere-Seiten-Icon (schmal)
        header.resizeSection(1, 30)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)  # Dateiname
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # Box
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)  # Quelle
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)  # Art
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)  # KI (schmal)
        header.resizeSection(6, 35)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)  # Datum
        header.setSectionResizeMode(8, QHeaderView.ResizeMode.ResizeToContents)  # Von
        
        # Sortieren aktivieren (Klick auf Header zum Sortieren)
        self.table.setSortingEnabled(True)
        # Standard: Nach Datum absteigend (neueste zuerst)
        self._proxy_model.sort(DocumentTableModel.COL_DATE, Qt.SortOrder.DescendingOrder)
        
        # Zeilenhoehe fest anpassen (nicht vom Nutzer aenderbar)
        self.table.verticalHeader().setDefaultSectionSize(36)
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self.table.verticalHeader().setVisible(False)
        
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        self.table.clicked.connect(self._on_table_clicked)
        self.table.doubleClicked.connect(self._on_double_click)
        self.table.selectionModel().selectionChanged.connect(self._on_table_selection_changed)
        
        # Fokus-Umrandung entfernen
        self.table.setStyleSheet("""
            QTableView::item:focus {
                outline: none;
                border: none;
            }
            QTableView:focus {
                outline: none;
            }
        """)
        
        # Custom Delegate fuer Hintergrundfarben (trotz Stylesheet)
        self.table.setItemDelegate(ColorBackgroundDelegate(self.table))
        
        # Drag aktivieren (Drop wird von Sidebar gehandhabt)
        self.table.setDragEnabled(True)
        self.table.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)
    
    def _refresh_all(self, force_refresh: bool = True):
        """
        Aktualisiert Statistiken, Dokumente und Credits.
        
        Args:
            force_refresh: True = Vom Server neu laden, False = Cache nutzen
        """
        # Bei manuellem Refresh: Timestamp speichern
        if force_refresh:
            now = datetime.now()
            # Alle Boxen als "manuell aktualisiert" markieren
            self._last_manual_refresh[''] = now  # Gesamt
            for box in BOX_TYPES:
                self._last_manual_refresh[box] = now
            logger.info("Manueller Refresh: Alle Boxen markiert")
        
        self._refresh_stats(force_refresh)
        self._refresh_documents(force_refresh)
        self._refresh_credits()
    
    def _refresh_after_move(self):
        """
        Leichtgewichtiger Refresh nach Verschieben von Dokumenten.
        
        Aktualisiert nur Statistiken und die aktuelle Ansicht,
        ohne alle Boxen zu invalidieren.
        Verwendet async Worker um den Main Thread nicht zu blockieren.
        """
        # Nur Statistiken vom Server holen (async via BoxStatsWorker)
        self._refresh_stats(force_refresh=True)
        
        # Dokumente async vom Server laden (via CacheDocumentLoadWorker)
        # _refresh_documents() handhabt is_archived Filter korrekt
        self._refresh_documents(force_refresh=True)
    
    # =========================================================================
    # CACHE-CALLBACKS (fuer Auto-Refresh)
    # =========================================================================
    
    def _on_cache_documents_updated(self, box_type: str):
        """Callback wenn Cache-Service Dokumente aktualisiert hat."""
        # Nur aktualisieren wenn die aktuelle Box betroffen ist
        if box_type == 'all' or box_type == self._current_box or self._current_box == '':
            logger.debug(f"Cache-Update: Dokumente ({box_type})")
            # Daten aus Cache holen und UI aktualisieren
            self._load_documents_from_cache()
    
    def _on_cache_stats_updated(self):
        """Callback wenn Cache-Service Statistiken aktualisiert hat."""
        logger.debug("Cache-Update: Statistiken")
        stats = self._cache.get_stats(force_refresh=False)
        self._stats = BoxStats(**stats) if isinstance(stats, dict) else stats
        self.sidebar.update_stats(self._stats)
    
    def _on_cache_refresh_started(self):
        """Callback wenn Auto-Refresh gestartet wurde."""
        # Optional: Status anzeigen
        logger.debug("Auto-Refresh gestartet...")
    
    def _on_cache_refresh_finished(self):
        """Callback wenn Auto-Refresh beendet wurde."""
        logger.debug("Auto-Refresh beendet")
        self._initial_load_done = True
        # SmartScan-Status aktualisieren (falls Admin ihn zwischenzeitlich geaendert hat)
        self._load_smartscan_status()
        self.sidebar._smartscan_enabled = self._smartscan_enabled
        if hasattr(self, '_smartscan_btn'):
            self._smartscan_btn.setVisible(self._smartscan_enabled)
        
        # Einmalig: Dokumente ohne Text-Extraktion pruefen (Scan-Uploads etc.)
        if not self._missing_ai_data_checked:
            self._missing_ai_data_checked = True
            self._check_missing_ai_data()
    
    def _check_missing_ai_data(self):
        """Startet Hintergrund-Worker fuer Dokumente ohne Text-Extraktion.
        
        Wird einmal beim App-Start ausgefuehrt. Prueft ob Scan-Dokumente
        oder andere serverseitig hochgeladene Dateien noch keinen
        document_ai_data-Eintrag haben und holt die Text-Extraktion nach.
        """
        worker = MissingAiDataWorker(self.docs_api)
        worker.finished.connect(self._on_missing_ai_data_finished)
        self._active_workers.append(worker)
        worker.start()
        logger.debug("MissingAiDataWorker gestartet")
    
    def _on_missing_ai_data_finished(self, count: int):
        """Callback wenn Hintergrund-Text-Extraktion fertig ist."""
        if count > 0:
            logger.info(f"Nachtraegliche Text-Extraktion: {count} Dokument(e) verarbeitet")
            # Archiv aktualisieren, damit Duplikat-Markierungen erscheinen
            self._refresh_all(force_refresh=True)
        else:
            logger.debug("Keine Dokumente ohne Text-Extraktion gefunden")
    
    def _load_avg_cost_stats(self):
        """Laedt die durchschnittlichen Verarbeitungskosten pro Dokument im Hintergrund."""
        if self._cost_stats_worker and self._cost_stats_worker.isRunning():
            return
        
        self._cost_stats_worker = CostStatsWorker(self.api_client)
        self._cost_stats_worker.finished.connect(self._on_avg_cost_loaded)
        self._register_worker(self._cost_stats_worker)
        self._cost_stats_worker.start()
    
    def _on_avg_cost_loaded(self, avg_cost: float):
        """Callback wenn durchschnittliche Kosten geladen wurden."""
        logger.debug(f"Durchschnittliche Verarbeitungskosten/Dokument: ${avg_cost:.6f}")
        self.sidebar.set_avg_cost_per_doc(avg_cost)
    
    def _load_documents_from_cache(self):
        """
        Laedt Dokumente aus dem Cache und aktualisiert die UI.
        
        Wird von Auto-Refresh Callbacks aufgerufen, nachdem Daten
        bereits im Hintergrund geladen wurden.
        
        WICHTIG: Muss dieselbe Filter-Logik wie _refresh_documents() verwenden,
        damit Sidebar-Zaehler und Tabelleninhalt konsistent bleiben.
        """
        # Archived-Box erkennen (z.B. 'courtage_archived' -> box='courtage', is_archived=True)
        is_archived_box = self._current_box and self._current_box.endswith("_archived")
        actual_box = self._current_box.replace("_archived", "") if is_archived_box else self._current_box
        
        # Thread-safe Zugriff ueber oeffentliche API (kein direkter Lock-Zugriff!)
        cache_key = actual_box if actual_box else None
        documents = self._cache.get_documents(box_type=cache_key, force_refresh=False)
        
        # is_archived Filter client-seitig (wie CacheDocumentLoadWorker)
        if is_archived_box:
            documents = [d for d in documents if d.is_archived]
        elif actual_box:
            documents = [d for d in documents if not d.is_archived]
        
        # Wenn View nicht sichtbar: Rebuild aufschieben (verhindert UI-Freeze)
        if not self.isVisible():
            self._pending_documents = documents
            self._pending_force_rebuild = False
            return
        
        # Alle Filter anwenden und anzeigen (Quelle, Typ, KI, Suche)
        self._apply_filters_and_display(documents)
    
    def _refresh_credits(self):
        """Laedt das OpenRouter-Guthaben im Hintergrund."""
        self._credits_worker = CreditsWorker(self.api_client)
        self._credits_worker.finished.connect(self._on_credits_loaded)
        self._register_worker(self._credits_worker)
        self._credits_worker.start()
    
    def _on_credits_loaded(self, credits: Optional[dict]):
        """Callback wenn Credits geladen wurden (ACENCIA Design)."""
        if not credits:
            self.credits_label.setText("")
            self.credits_label.setToolTip("")
            return
        
        provider = credits.get('provider', 'openrouter')
        
        if provider == 'openai':
            usage = credits.get('total_usage')
            if usage is not None:
                self.credits_label.setStyleSheet(f"""
                    color: {SUCCESS};
                    font-size: {FONT_SIZE_CAPTION};
                    font-family: {FONT_BODY};
                """)
                self.credits_label.setText(f"OpenAI: ${float(usage):.2f}")
                period = credits.get('period', '')
                self.credits_label.setToolTip(f"OpenAI Kosten: ${float(usage):.4f}\n{period}")
            else:
                self.credits_label.setText("OpenAI")
                self.credits_label.setToolTip("")
        else:
            balance = credits.get('balance', 0)
            total_credits = credits.get('total_credits', 0)
            total_usage = credits.get('total_usage', 0)
            
            if balance < 1.0:
                color = ERROR
            elif balance < 5.0:
                color = WARNING
            else:
                color = SUCCESS
            
            self.credits_label.setStyleSheet(f"""
                color: {color};
                font-size: {FONT_SIZE_CAPTION};
                font-family: {FONT_BODY};
            """)
            
            self.credits_label.setText(f"KI: ${balance:.2f}")
            self.credits_label.setToolTip(
                f"Guthaben: ${total_credits:.2f}\n"
                f"Verbraucht: ${total_usage:.4f}\n"
                f"Verbleibend: ${balance:.4f}"
            )
    
    def _refresh_stats(self, force_refresh: bool = True):
        """
        Laedt die Box-Statistiken.
        
        Args:
            force_refresh: True = Vom Server, False = Aus Cache
        """
        if force_refresh:
            # Vom Server laden (via Worker fuer UI-Responsivitaet)
            self._stats_worker = BoxStatsWorker(self.docs_api)
            self._stats_worker.finished.connect(self._on_stats_loaded)
            self._stats_worker.error.connect(self._on_stats_error)
            self._register_worker(self._stats_worker)
            self._stats_worker.start()
        else:
            # Aus Cache
            stats = self._cache.get_stats(force_refresh=False)
            if stats:
                self._stats = BoxStats(**stats) if isinstance(stats, dict) else stats
                self.sidebar.update_stats(self._stats)
            else:
                # Cache leer -> doch vom Server laden
                self._refresh_stats(force_refresh=True)
    
    def _on_stats_loaded(self, stats: BoxStats):
        """Callback wenn Statistiken geladen wurden."""
        self._stats = stats
        self.sidebar.update_stats(stats)
        # Cache aktualisieren ueber oeffentliche API (thread-safe!)
        self._cache.invalidate_stats()
        self._cache.get_stats(force_refresh=True)  # Neu laden in Cache
    
    def _on_stats_error(self, error: str):
        """Callback bei Statistik-Fehler."""
        logger.error(f"Statistiken laden fehlgeschlagen: {error}")
    
    def _refresh_documents(self, force_refresh: bool = True):
        """
        Laedt die Dokumente fuer die aktuelle Box.
        
        Strategie (optimiert):
        1. Cache-Check: Wenn frische Daten im RAM -> direkt anzeigen (instant)
        2. Cache-Load: Worker laedt ALLE Dokumente in Cache (1 API-Call)
           -> Nachfolgende Box-Wechsel sind instant aus Cache
        
        Args:
            force_refresh: True = Vom Server, False = Aus Cache (falls vorhanden)
        """
        self.status_label.setText("Lade Dokumente...")
        
        # Pruefen ob archivierte Box
        is_archived_box = self._current_box and self._current_box.endswith("_archived")
        actual_box = self._current_box.replace("_archived", "") if is_archived_box else self._current_box
        
        # Cache-Check: Frische Daten im RAM?
        if not force_refresh:
            cache_key = actual_box if actual_box else None
            # Schneller Check ob Daten im RAM-Cache sind (ohne API-Call!)
            # WICHTIG: Oeffentliche API verwenden, NICHT direkten Lock-Zugriff!
            documents = self._cache.get_documents_cached_only(box_type=cache_key)
            if documents is not None:
                # Daten sind im RAM -> direkt anzeigen (instant!)
                # is_archived Filter client-seitig
                if is_archived_box:
                    documents = [d for d in documents if d.is_archived]
                elif actual_box:
                    documents = [d for d in documents if not d.is_archived]
                self._apply_filters_and_display(documents, force_rebuild=True)
                return
        
        # Daten nicht im Cache oder force_refresh -> Worker starten
        # Loading-Overlay anzeigen
        if is_archived_box:
            box_name = f"{BOX_DISPLAY_NAMES.get(actual_box, 'Box')} Archiviert"
        else:
            box_name = BOX_DISPLAY_NAMES.get(self._current_box, "Archiv")
        self._show_loading(f"{box_name} wird geladen...")
        self.table.setEnabled(False)
        
        # is_archived Filter bestimmen
        is_archived_filter = None  # Gesamt Archiv: alle
        if is_archived_box:
            is_archived_filter = True
        elif actual_box:
            is_archived_filter = False
        
        # CacheDocumentLoadWorker: Laedt ALLE Dokumente in Cache (1 API-Call),
        # filtert lokal nach box_type und is_archived.
        # Nachfolgende Box-Wechsel sind instant (aus Cache).
        self._load_worker = CacheDocumentLoadWorker(
            self._cache,
            box_type=actual_box or None,
            is_archived=is_archived_filter,
            force_refresh=force_refresh
        )
        self._load_worker.finished.connect(self._on_documents_loaded)
        self._load_worker.error.connect(self._on_load_error)
        self._register_worker(self._load_worker)
        self._load_worker.start()
    
    def _on_documents_loaded(self, documents: List[Document]):
        """Callback wenn Dokumente geladen wurden."""
        # Loading-Overlay verstecken
        self._hide_loading()
        
        # Wenn View nicht sichtbar: Daten zwischenspeichern, Tabelle erst bei
        # Rueckkehr zum Archiv-View neu aufbauen (verhindert UI-Freeze in anderen Views)
        if not self.isVisible():
            self._pending_documents = documents
            self._pending_force_rebuild = True
            logger.debug("Archiv nicht sichtbar - Tabellen-Rebuild aufgeschoben")
            return
        
        self._apply_filters_and_display(documents, force_rebuild=True)
        
        # Cache wird automatisch durch get_documents() bei Bedarf befuellt
        # Kein manuelles Befuellen noetig (und kein direkter Lock-Zugriff!)
    
    @staticmethod
    def _compute_documents_fingerprint(documents: List[Document]) -> str:
        """
        Berechnet einen Fingerprint fuer die Dokumentliste.
        
        Aendert sich nur wenn Dokumente hinzukommen, entfernt werden,
        umbenannt, verschoben oder anderweitig aktualisiert werden.
        """
        parts = []
        for doc in documents:
            parts.append(
                f"{doc.id}:{doc.original_filename}:{doc.box_type}:"
                f"{doc.display_color or ''}:{doc.ai_renamed}:{doc.is_archived}:"
                f"{doc.processing_status or ''}:{doc.created_at or ''}:"
                f"{doc.version}"
            )
        return "|".join(parts)
    
    def _apply_filters_and_display(self, documents: List[Document], force_rebuild: bool = False):
        """Wendet Filter an und zeigt Dokumente in der Tabelle."""
        # Admin-Filter: Falsch-Box Dokumente fuer Nicht-Admins ausblenden
        if not self._is_admin:
            documents = [d for d in documents if d.box_type != 'falsch']
        
        # Quelle-Filter anwenden
        source = self.source_filter.currentData() if hasattr(self, 'source_filter') else None
        if source:
            documents = [d for d in documents if d.source_type == source]
        
        # Art-Filter anwenden (Dateityp)
        file_type = self.type_filter.currentData() if hasattr(self, 'type_filter') else None
        if file_type:
            documents = [d for d in documents if DocumentTableModel._get_file_type(d) == file_type]
        
        # KI-Filter anwenden
        ki_status = self.ki_filter.currentData() if hasattr(self, 'ki_filter') else None
        if ki_status == "yes":
            documents = [d for d in documents if d.ai_renamed]
        elif ki_status == "no":
            documents = [d for d in documents if not d.ai_renamed and d.is_pdf]
        
        # Fingerprint pruefen: Model nur aktualisieren wenn sich Daten geaendert haben
        new_fingerprint = self._compute_documents_fingerprint(documents)
        if not force_rebuild and new_fingerprint == self._documents_fingerprint:
            logger.debug("Auto-Refresh: Keine Aenderungen - Tabelle uebersprungen")
            return
        
        self._documents_fingerprint = new_fingerprint
        self._documents = documents
        # Model aktualisieren - virtualisiert, kein Item-Spam
        self._doc_model.set_documents(documents)
        self.table.setEnabled(True)
        
        # Box-Name ermitteln (inkl. archivierte Boxen)
        if self._current_box and self._current_box.endswith("_archived"):
            actual_box = self._current_box.replace("_archived", "")
            box_name = f"{BOX_DISPLAY_NAMES.get(actual_box, 'Box')} Archiviert"
        else:
            box_name = BOX_DISPLAY_NAMES.get(self._current_box, "Gesamt Archiv")
        self.status_label.setText(f"{len(documents)} Dokument(e) in {box_name}")
    
    def _on_load_error(self, error: str):
        """Callback bei Ladefehler."""
        # Loading-Overlay verstecken
        self._hide_loading()
        
        self.table.setEnabled(True)
        self.status_label.setText(f"Fehler: {error}")
        self._toast_manager.show_error(f"Dokumente konnten nicht geladen werden:\n{error}")
    
    def _get_file_type(self, doc) -> str:
        """Ermittelt den Dateityp fuer die Anzeige (delegiert an Model)."""
        return DocumentTableModel._get_file_type(doc)
    
    def _filter_table(self):
        """Filtert die Tabelle nach Suchbegriff (via Proxy-Model)."""
        search_text = self.search_input.text()
        self._proxy_model.set_search_text(search_text)
    
    def _apply_filter(self):
        """Wendet Filter an (aus Cache, kein Server-Request)."""
        self._refresh_documents(force_refresh=False)
    
    def _on_smartscan_btn_clicked(self):
        """Smart!Scan Button in der Toolbar geklickt - versendet ausgewaehlte Dokumente."""
        from i18n.de import SMARTSCAN_NO_SELECTION
        
        # BUG-0005 Fix: _get_selected_documents() liest korrekt per UserRole
        # statt ueber sortierte Zeilen-Indices in unsortierter Liste
        selected_docs = self._get_selected_documents()
        
        if not selected_docs:
            self._toast_manager.show_info(SMARTSCAN_NO_SELECTION)
            return
        
        self._start_smartscan(selected_docs)
    
    def _reset_filters(self):
        """Setzt alle Filter und Sortierung auf Standard zurück."""
        # Filter-Signale temporär blockieren um mehrfaches Neuladen zu vermeiden
        self.source_filter.blockSignals(True)
        self.type_filter.blockSignals(True)
        self.ki_filter.blockSignals(True)
        
        # Filter zurücksetzen
        self.source_filter.setCurrentIndex(0)  # "Alle"
        self.type_filter.setCurrentIndex(0)    # "Alle"
        self.ki_filter.setCurrentIndex(0)      # "Alle"
        self.search_input.clear()
        
        # Signale wieder aktivieren
        self.source_filter.blockSignals(False)
        self.type_filter.blockSignals(False)
        self.ki_filter.blockSignals(False)
        
        # Sortierung auf Standard zuruecksetzen (Datum absteigend, Spalte 6)
        self._proxy_model.sort(DocumentTableModel.COL_DATE, Qt.SortOrder.DescendingOrder)
        
        # Tabelle neu laden
        self._refresh_documents(force_refresh=False)
    
    def _on_box_selected(self, box_type: str):
        """Handler wenn eine Box in der Sidebar ausgewaehlt wird."""
        # ATLAS Index: Zur Such-View wechseln
        if box_type == "atlas_index":
            self._content_stack.setCurrentIndex(1)  # AtlasIndexWidget
            self._atlas_index_widget.focus_search()
            return
        
        # Normale Box: Zur Archiv-Tabelle wechseln
        self._content_stack.setCurrentIndex(0)
        
        self._current_box = box_type
        
        # Titel aktualisieren
        if box_type:
            self.title_label.setText(BOX_DISPLAY_NAMES.get(box_type, box_type))
        else:
            self.title_label.setText("Gesamt Archiv")
        
        # Upload-Button nur in Eingangsbox aktiv
        self.upload_btn.setEnabled(box_type in ['', 'eingang'])
        if box_type and box_type != 'eingang':
            self.upload_btn.setToolTip("Hochladen nur in die Eingangsbox moeglich")
        else:
            self.upload_btn.setToolTip("")
        
        # Pruefen ob diese Box seit dem letzten manuellen Refresh bereits geladen wurde
        needs_refresh = self._should_refresh_box(box_type)
        
        if needs_refresh:
            logger.info(f"Box '{box_type}' seit manuellem Refresh noch nicht geladen - lade alle Dokumente in Cache (1 API-Call)")
            self._refresh_documents(force_refresh=True)
            # Als geladen markieren (fuer Fallback-Logik)
            self._last_box_load[box_type] = datetime.now()
        else:
            # Dokumente aus Cache laden (kein Server-Request!)
            logger.debug(f"Box '{box_type}' aus Cache (instant)")
            self._refresh_documents(force_refresh=False)
    
    # ========================================
    # ATLAS Index Handler
    # ========================================
    
    def _on_atlas_preview(self, document: Document):
        """ATLAS Index: Vorschau fuer ein Dokument oeffnen."""
        self._preview_document(document)
    
    def _on_atlas_download(self, document: Document):
        """ATLAS Index: Dokument herunterladen."""
        self._download_document(document)
    
    def _on_atlas_show_in_box(self, document: Document):
        """ATLAS Index: Zur echten Box des Dokuments wechseln und selektieren."""
        target_box = document.box_type or ''
        # Wenn archiviert, zur archivierten Sub-Box wechseln
        if document.is_archived and target_box:
            target_box = f"{target_box}_archived"
        
        # Zur Box wechseln (triggert _on_box_selected -> laedt Dokumente)
        self.sidebar.select_box(target_box)
        
        # Nach kurzer Verzoegerung Dokument selektieren (Tabelle muss erst geladen sein)
        self._pending_select_doc_id = document.id
        QTimer.singleShot(500, self._select_pending_document)
    
    def _select_pending_document(self):
        """Selektiert ein Dokument in der Tabelle nach Box-Wechsel (fuer 'In Box anzeigen')."""
        doc_id = getattr(self, '_pending_select_doc_id', None)
        if doc_id is None:
            return
        self._pending_select_doc_id = None
        
        # Dokument in der Tabelle finden und selektieren
        for row in range(self._proxy_model.rowCount()):
            proxy_index = self._proxy_model.index(row, 0)
            source_index = self._proxy_model.mapToSource(proxy_index)
            doc = self._doc_model.get_document(source_index.row())
            if doc and doc.id == doc_id:
                self.table.selectRow(row)
                self.table.scrollTo(proxy_index)
                break
    
    def _should_refresh_box(self, box_type: str) -> bool:
        """
        Prueft ob eine Box seit dem letzten manuellen Refresh neu geladen werden muss.
        
        Optimierung: Da der zentrale Cache ALLE Dokumente auf einmal laedt,
        reicht es zu pruefen ob der Cache NACH dem manuellen Refresh geladen wurde.
        Wenn ja, haben ALLE Boxen frische Daten (kein erneuter Server-Call noetig).
        
        Returns:
            True wenn die Box seit dem letzten "Aktualisieren"-Klick noch nicht geladen wurde
        """
        # Wenn noch nie manuell aktualisiert wurde, nicht noetig
        if box_type not in self._last_manual_refresh and '' not in self._last_manual_refresh:
            return False
        
        # Zeitpunkt des letzten manuellen Refresh (box-spezifisch oder global)
        last_manual = self._last_manual_refresh.get(box_type) or self._last_manual_refresh.get('')
        if not last_manual:
            return False
        
        # OPTIMIERUNG: Prüfe zentralen Cache-Zeitstempel
        # Wenn der Cache NACH dem manuellen Refresh geladen wurde, haben ALLE Boxen frische Daten
        cache_time = self._cache.get_documents_cache_time()
        if cache_time and cache_time >= last_manual:
            return False  # Cache ist frisch genug - kein Server-Call noetig
        
        # Fallback: Box-spezifisches Tracking (fuer Sonderfaelle)
        last_load = self._last_box_load.get(box_type)
        if not last_load or last_load < last_manual:
            return True
        
        return False
    
    def _show_context_menu(self, position):
        """Zeigt das Kontextmenue."""
        index = self.table.indexAt(position)
        if not index.isValid():
            return
        
        selected_docs = self._get_selected_documents()
        if not selected_docs:
            return
        
        menu = QMenu(self)
        
        # ===== Vorschau / Oeffnen =====
        if len(selected_docs) == 1:
            doc = selected_docs[0]
            
            if self._is_pdf(doc):
                preview_action = QAction("Vorschau", self)
                preview_action.triggered.connect(lambda: self._preview_document(doc))
                menu.addAction(preview_action)
            
            if self._is_spreadsheet(doc):
                from i18n.de import SPREADSHEET_CONTEXT_MENU
                spreadsheet_preview_action = QAction(SPREADSHEET_CONTEXT_MENU, self)
                spreadsheet_preview_action.triggered.connect(lambda: self._preview_spreadsheet(doc))
                menu.addAction(spreadsheet_preview_action)
            
            if doc.is_gdv:
                open_gdv_action = QAction("Im GDV-Editor oeffnen", self)
                open_gdv_action.triggered.connect(lambda: self._open_in_gdv_editor(doc))
                menu.addAction(open_gdv_action)
        
        # ===== Download =====
        if len(selected_docs) == 1:
            download_action = QAction("Herunterladen", self)
            download_action.triggered.connect(lambda: self._download_document(selected_docs[0]))
            menu.addAction(download_action)
        else:
            download_action = QAction(f"{len(selected_docs)} Dokumente herunterladen", self)
            download_action.triggered.connect(self._download_selected)
            menu.addAction(download_action)
        
        # ===== Umbenennen (nur bei Einzelauswahl) =====
        if len(selected_docs) == 1:
            from i18n.de import RENAME
            rename_action = QAction(RENAME, self)
            rename_action.triggered.connect(lambda: self._rename_document(selected_docs[0]))
            menu.addAction(rename_action)
        
        # ===== Duplikat-Navigation (nur bei Einzelauswahl + Duplikat) =====
        if len(selected_docs) == 1:
            doc = selected_docs[0]
            if doc.is_duplicate or doc.is_content_duplicate:
                from i18n.de import DUPLICATE_JUMP_TO, DUPLICATE_COMPARE
                menu.addSeparator()
                
                # Gegenstueck-ID und Metadaten ermitteln
                if doc.is_duplicate and doc.previous_version_id:
                    _cpart_id = doc.previous_version_id
                    _cpart_box = doc.duplicate_of_box_type or ''
                    _cpart_archived = doc.duplicate_of_is_archived
                elif doc.is_content_duplicate and doc.content_duplicate_of_id:
                    _cpart_id = doc.content_duplicate_of_id
                    _cpart_box = doc.content_duplicate_of_box_type or ''
                    _cpart_archived = doc.content_duplicate_of_is_archived
                else:
                    _cpart_id = None
                
                if _cpart_id:
                    jump_action = QAction(DUPLICATE_JUMP_TO, self)
                    jump_action.triggered.connect(
                        lambda checked, cid=_cpart_id, cb=_cpart_box, ca=_cpart_archived:
                            self._jump_to_counterpart(cid, cb, ca))
                    menu.addAction(jump_action)
                
                compare_action = QAction(DUPLICATE_COMPARE, self)
                compare_action.triggered.connect(lambda: self._open_duplicate_compare(doc))
                menu.addAction(compare_action)
        
        menu.addSeparator()
        
        # ===== Verschieben =====
        move_menu = QMenu("Verschieben nach...", menu)
        
        # Boxen der ausgewaehlten Dokumente ermitteln (diese nicht anbieten)
        current_boxes = set(d.box_type for d in selected_docs if d.box_type)
        
        # Basis-Boxen fuer alle Benutzer
        move_targets = ['gdv', 'courtage', 'sach', 'leben', 'kranken', 'sonstige']
        
        # Admin-only Boxen hinzufuegen
        if self._is_admin:
            move_targets.extend(BOX_TYPES_ADMIN)
        
        for box_type in move_targets:
            # Box ueberspringen wenn alle Dokumente bereits dort sind
            if box_type in current_boxes and len(current_boxes) == 1:
                continue
            box_name = BOX_DISPLAY_NAMES.get(box_type, box_type)
            action = QAction(box_name, self)
            action.triggered.connect(lambda checked, bt=box_type: self._move_documents(selected_docs, bt))
            move_menu.addAction(action)
        
        menu.addMenu(move_menu)
        
        # ===== Farbmarkierung =====
        from i18n.de import (
            DOC_COLOR_MENU, DOC_COLOR_REMOVE,
            DOC_COLOR_GREEN, DOC_COLOR_RED, DOC_COLOR_BLUE, DOC_COLOR_ORANGE,
            DOC_COLOR_PURPLE, DOC_COLOR_PINK, DOC_COLOR_CYAN, DOC_COLOR_YELLOW
        )
        color_menu = QMenu(DOC_COLOR_MENU, menu)
        
        color_labels = {
            'green': DOC_COLOR_GREEN,
            'red': DOC_COLOR_RED,
            'blue': DOC_COLOR_BLUE,
            'orange': DOC_COLOR_ORANGE,
            'purple': DOC_COLOR_PURPLE,
            'pink': DOC_COLOR_PINK,
            'cyan': DOC_COLOR_CYAN,
            'yellow': DOC_COLOR_YELLOW,
        }
        
        for color_key, color_label in color_labels.items():
            hex_color = DOCUMENT_DISPLAY_COLORS.get(color_key, '#ffffff')
            color_action = QAction(f"\u25cf  {color_label}", self)
            color_action.setData(color_key)
            # Farbigen Punkt als Icon-Ersatz via Stylesheet nicht moeglich,
            # daher Unicode-Kreis mit Farbkodierung im Text
            icon_pixmap = self._create_color_icon(hex_color)
            if icon_pixmap:
                color_action.setIcon(icon_pixmap)
            color_action.triggered.connect(
                lambda checked, ck=color_key: self._set_document_color(selected_docs, ck)
            )
            color_menu.addAction(color_action)
        
        # Farbe entfernen - nur anbieten wenn mindestens ein Dokument eine Farbe hat
        colored_docs = [d for d in selected_docs if d.display_color]
        if colored_docs:
            color_menu.addSeparator()
            remove_color_action = QAction(DOC_COLOR_REMOVE, self)
            remove_color_action.triggered.connect(
                lambda: self._set_document_color(selected_docs, None)
            )
            color_menu.addAction(remove_color_action)
        
        menu.addMenu(color_menu)
        
        # ===== Smart!Scan (nur wenn in Admin-Einstellungen aktiviert) =====
        if self._smartscan_enabled:
            from i18n.de import SMARTSCAN_CONTEXT_MENU, SMARTSCAN_CONTEXT_SELECTED
            menu.addSeparator()
            if len(selected_docs) == 1:
                smartscan_action = QAction(SMARTSCAN_CONTEXT_MENU, self)
            else:
                smartscan_action = QAction(f"{SMARTSCAN_CONTEXT_MENU} ({len(selected_docs)})", self)
            smartscan_action.triggered.connect(lambda: self._start_smartscan(selected_docs))
            menu.addAction(smartscan_action)
        
        # ===== KI-Benennung =====
        # Nur fuer PDFs die NICHT in Eingangsbox/Verarbeitung sind
        # (dort soll die volle Verarbeitungs-Pipeline genutzt werden)
        pdf_docs = [
            d for d in selected_docs 
            if d.is_pdf and not d.ai_renamed 
            and d.box_type not in ('eingang', 'verarbeitung')
        ]
        if pdf_docs:
            menu.addSeparator()
            ai_action = QAction(f"KI-Benennung ({len(pdf_docs)} PDF{'s' if len(pdf_docs) > 1 else ''})", self)
            ai_action.triggered.connect(lambda: self._ai_rename_documents(pdf_docs))
            menu.addAction(ai_action)
        
        # ===== Verarbeitungs-Steuerung =====
        from i18n.de import PROCESSING_EXCLUDE, PROCESSING_INCLUDE
        
        # "Von Verarbeitung ausschliessen" - NUR fuer Dokumente in der Eingangsbox
        # die noch nicht ausgeschlossen sind (nur dort wartet Verarbeitung)
        excludable_docs = [
            d for d in selected_docs 
            if d.box_type == 'eingang' and d.processing_status != 'manual_excluded'
        ]
        if excludable_docs:
            if len(excludable_docs) == 1:
                exclude_action = QAction(PROCESSING_EXCLUDE, self)
            else:
                exclude_action = QAction(
                    f"{PROCESSING_EXCLUDE} ({len(excludable_docs)})", self
                )
            exclude_action.triggered.connect(
                lambda: self._exclude_from_processing(excludable_docs)
            )
            menu.addAction(exclude_action)
        
        # "Erneut fuer Verarbeitung freigeben" - fuer:
        # 1. Manuell ausgeschlossene Dokumente (egal in welcher Box)
        # 2. Bereits verarbeitete Dokumente in Ziel-Boxen (erneut verarbeiten)
        # NICHT fuer Dokumente die bereits in der Eingangsbox mit status 'pending' sind
        reprocessable_docs = [
            d for d in selected_docs 
            if d.processing_status == 'manual_excluded'
            or (d.box_type not in ('eingang', 'verarbeitung')
                and d.processing_status != 'pending')
        ]
        if reprocessable_docs:
            if len(reprocessable_docs) == 1:
                include_action = QAction(PROCESSING_INCLUDE, self)
            else:
                include_action = QAction(
                    f"{PROCESSING_INCLUDE} ({len(reprocessable_docs)})", self
                )
            include_action.triggered.connect(
                lambda: self._include_for_processing(reprocessable_docs)
            )
            menu.addAction(include_action)
        
        # ===== Archivieren/Entarchivieren =====
        # Dokumente aus archivierungsfaehigen Boxen filtern
        archivable_docs = [d for d in selected_docs if d.box_type in ARCHIVABLE_BOXES]
        
        if archivable_docs:
            from i18n.de import ARCHIVE, ARCHIVE_DOCUMENTS, UNARCHIVE, UNARCHIVE_DOCUMENTS
            menu.addSeparator()
            
            # Pruefen ob alle archiviert oder alle nicht archiviert sind
            all_archived = all(d.is_archived for d in archivable_docs)
            all_not_archived = all(not d.is_archived for d in archivable_docs)
            
            if all_not_archived:
                # Alle nicht archiviert -> Archivieren anbieten
                if len(archivable_docs) == 1:
                    archive_action = QAction(ARCHIVE, self)
                    archive_action.triggered.connect(lambda: self._archive_documents(archivable_docs))
                else:
                    archive_action = QAction(ARCHIVE_DOCUMENTS.format(count=len(archivable_docs)), self)
                    archive_action.triggered.connect(lambda: self._archive_documents(archivable_docs))
                menu.addAction(archive_action)
            elif all_archived:
                # Alle archiviert -> Entarchivieren anbieten
                if len(archivable_docs) == 1:
                    unarchive_action = QAction(UNARCHIVE, self)
                    unarchive_action.triggered.connect(lambda: self._unarchive_documents(archivable_docs))
                else:
                    unarchive_action = QAction(UNARCHIVE_DOCUMENTS.format(count=len(archivable_docs)), self)
                    unarchive_action.triggered.connect(lambda: self._unarchive_documents(archivable_docs))
                menu.addAction(unarchive_action)
            else:
                # Gemischte Auswahl -> beide Optionen anbieten
                not_archived = [d for d in archivable_docs if not d.is_archived]
                archived = [d for d in archivable_docs if d.is_archived]
                
                archive_action = QAction(ARCHIVE_DOCUMENTS.format(count=len(not_archived)), self)
                archive_action.triggered.connect(lambda: self._archive_documents(not_archived))
                menu.addAction(archive_action)
                
                unarchive_action = QAction(UNARCHIVE_DOCUMENTS.format(count=len(archived)), self)
                unarchive_action.triggered.connect(lambda: self._unarchive_documents(archived))
                menu.addAction(unarchive_action)
        
        menu.addSeparator()
        
        # ===== Loeschen =====
        if len(selected_docs) == 1:
            delete_action = QAction("Loeschen", self)
            delete_action.triggered.connect(lambda: self._delete_document(selected_docs[0]))
            menu.addAction(delete_action)
        else:
            delete_action = QAction(f"{len(selected_docs)} Dokumente loeschen", self)
            delete_action.triggered.connect(self._delete_selected)
            menu.addAction(delete_action)
        
        menu.exec(self.table.viewport().mapToGlobal(position))
    
    def _on_table_clicked(self, proxy_index):
        """Handler fuer Einfach-Klick: Bei COL_DUPLICATE zum Gegenstueck springen."""
        if not proxy_index.isValid():
            return
        col = proxy_index.column()
        if col != DocumentTableModel.COL_DUPLICATE:
            return
        source_index = self._proxy_model.mapToSource(proxy_index)
        doc = self._doc_model.get_document(source_index.row())
        if not doc:
            return
        if doc.is_duplicate and doc.previous_version_id:
            self._jump_to_counterpart(
                doc.previous_version_id,
                doc.duplicate_of_box_type or '',
                doc.duplicate_of_is_archived)
        elif doc.is_content_duplicate and doc.content_duplicate_of_id:
            self._jump_to_counterpart(
                doc.content_duplicate_of_id,
                doc.content_duplicate_of_box_type or '',
                doc.content_duplicate_of_is_archived)
    
    def _jump_to_counterpart(self, doc_id: int, box_type: str, is_archived: bool):
        """Springt zum Gegenstueck-Dokument in seiner Box."""
        target_box = box_type or ''
        if is_archived and target_box:
            target_box = f"{target_box}_archived"
        self.sidebar.select_box(target_box)
        self._pending_select_doc_id = doc_id
        QTimer.singleShot(500, self._select_pending_document)
    
    def _open_duplicate_compare(self, doc: Document):
        """Oeffnet den Duplikat-Vergleichsdialog."""
        counterpart_id = doc.previous_version_id if doc.is_duplicate else doc.content_duplicate_of_id
        if not counterpart_id:
            return
        # Gegenstueck-Dokument laden
        counterpart = self.docs_api.get_document(counterpart_id)
        if not counterpart:
            from ui.toast import ToastManager
            from i18n.de import DUPLICATE_COMPARE_NOT_FOUND
            toast = ToastManager.instance()
            if toast:
                toast.show_warning(DUPLICATE_COMPARE_NOT_FOUND)
            return
        from ui.archive_view import DuplicateCompareDialog
        dialog = DuplicateCompareDialog(
            doc, counterpart, self.docs_api,
            preview_cache_dir=getattr(self, '_preview_cache_dir', None),
            parent=self)
        dialog.documents_changed.connect(self._refresh_all)
        dialog.exec()
    
    def _on_double_click(self, proxy_index):
        """Handler fuer Doppelklick."""
        if not proxy_index.isValid():
            return
        # Proxy-Index auf Source-Model mappen
        source_index = self._proxy_model.mapToSource(proxy_index)
        doc = self._doc_model.get_document(source_index.row())
        if doc:
            if doc.is_gdv:
                self._open_in_gdv_editor(doc)
            elif self._is_pdf(doc):
                self._preview_document(doc)
            elif self._is_spreadsheet(doc):
                self._preview_spreadsheet(doc)
            else:
                self._download_document(doc)
    
    def _get_selected_documents(self) -> List[Document]:
        """Gibt alle ausgewaehlten Dokumente zurueck."""
        selected_docs = []
        selected_rows = set()
        
        for proxy_index in self.table.selectedIndexes():
            selected_rows.add(proxy_index.row())
        
        for proxy_row in selected_rows:
            proxy_index = self._proxy_model.index(proxy_row, DocumentTableModel.COL_FILENAME)
            source_index = self._proxy_model.mapToSource(proxy_index)
            doc = self._doc_model.get_document(source_index.row())
            if doc:
                selected_docs.append(doc)
        
        return selected_docs
    
    def _is_pdf(self, doc: Document) -> bool:
        """Prueft ob das Dokument ein PDF ist."""
        return doc.is_pdf
    
    def _is_spreadsheet(self, doc: Document) -> bool:
        """Prueft ob das Dokument eine Tabellen-Datei ist (CSV, XLSX, XLS, TSV)."""
        ext = doc.file_extension.lower() if hasattr(doc, 'file_extension') else ""
        if not ext and '.' in doc.original_filename:
            ext = '.' + doc.original_filename.rsplit('.', 1)[-1].lower()
        return ext in ('.csv', '.xlsx', '.xls', '.tsv')
    
    # ========================================
    # Dokument-Historie (Seitenpanel)
    # ========================================
    
    def _on_history_toggle(self, checked: bool):
        """Wird aufgerufen wenn der Historie-Toggle-Button geklickt wird."""
        if not checked:
            # Toggle aus: Panel verstecken
            self._hide_history_panel()
        else:
            # Toggle an: Wenn ein Dokument ausgewaehlt ist, Historie laden
            selected = self._get_selected_documents()
            if len(selected) == 1:
                self._load_document_history(selected[0])
    
    def _on_table_selection_changed(self, *args):
        """
        Wird aufgerufen wenn sich die Tabellenauswahl aendert.
        Laedt die Historie fuer das ausgewaehlte Dokument (mit Debounce).
        Akzeptiert optionale args von selectionModel().selectionChanged(selected, deselected).
        """
        # Toggle muss aktiv sein UND Berechtigung vorhanden
        if not self._history_enabled or not self._history_toggle_btn.isChecked():
            return
        
        selected = self._get_selected_documents()
        
        if len(selected) != 1:
            # Kein oder mehrere Dokumente ausgewaehlt: Panel ausblenden
            if self._history_panel.isVisible():
                self._hide_history_panel_content()
            return
        
        doc = selected[0]
        
        # Debounce: 300ms warten bevor wir laden
        if self._history_debounce_timer is not None:
            self._history_debounce_timer.stop()
        
        self._pending_history_doc_id = doc.id
        self._history_debounce_timer = QTimer()
        self._history_debounce_timer.setSingleShot(True)
        self._history_debounce_timer.timeout.connect(
            lambda: self._load_document_history(doc)
        )
        self._history_debounce_timer.start(300)
    
    def _has_history_permission(self) -> bool:
        """Prueft ob der aktuelle Benutzer die documents_history Berechtigung hat."""
        if self.auth_api and self.auth_api.current_user:
            return self.auth_api.current_user.has_permission('documents_history')
        return False
    
    def _load_document_history(self, doc: Document):
        """Laedt die Historie fuer ein Dokument (aus Cache oder Server)."""
        # Pruefen ob das Dokument noch ausgewaehlt ist
        if self._pending_history_doc_id != doc.id:
            return
        
        # Panel sichtbar machen
        if not self._history_panel.isVisible():
            self._show_history_panel()
        
        # Cache pruefen
        cached = self._history_panel.get_cached_history(doc.id)
        if cached is not None:
            self._history_panel.show_history(doc.id, doc.original_filename, cached)
            return
        
        # Loading-Indikator anzeigen
        self._history_panel.show_loading(doc.original_filename)
        
        # Worker starten - alten Worker sauber stoppen
        if self._history_worker is not None:
            try:
                self._history_worker.finished.disconnect()
                self._history_worker.error.disconnect()
                if self._history_worker.isRunning():
                    self._history_worker.quit()
                    self._history_worker.wait(2000)  # Max 2 Sekunden warten
            except (RuntimeError, TypeError):
                pass
            self._history_worker = None
        
        self._history_worker = DocumentHistoryWorker(self.api_client, doc.id)
        self._history_worker.finished.connect(self._on_history_loaded)
        self._history_worker.error.connect(self._on_history_error)
        self._register_worker(self._history_worker)
        self._history_worker.start()
    
    def _on_history_loaded(self, doc_id: int, entries: list):
        """Callback wenn die Historie geladen wurde."""
        # Pruefen ob das Dokument noch ausgewaehlt ist
        selected = self._get_selected_documents()
        if len(selected) != 1 or selected[0].id != doc_id:
            return
        
        self._history_panel.show_history(doc_id, selected[0].original_filename, entries)
    
    def _on_history_error(self, doc_id: int, error_msg: str):
        """Callback bei Fehler beim Laden der Historie."""
        logger.warning(f"Dokument-Historie Fehler (ID {doc_id}): {error_msg}")
        self._history_panel.show_error(error_msg)
    
    def _show_history_panel(self):
        """Zeigt das Historie-Panel und passt den Splitter an."""
        self._history_panel.setVisible(True)
        # Splitter-Proportionen anpassen (Tabelle : Historie = 3:1)
        total_width = self._inner_splitter.width()
        history_width = min(300, total_width // 4)
        self._inner_splitter.setSizes([total_width - history_width, history_width])
    
    def _hide_history_panel(self):
        """Versteckt das Historie-Panel komplett und setzt den Toggle zurueck."""
        self._history_panel.setVisible(False)
        self._inner_splitter.setSizes([self._inner_splitter.width(), 0])
        # Toggle-Button zuruecksetzen (ohne Signal auszuloesen)
        if hasattr(self, '_history_toggle_btn'):
            self._history_toggle_btn.blockSignals(True)
            self._history_toggle_btn.setChecked(False)
            self._history_toggle_btn.blockSignals(False)
        # Debounce-Timer stoppen
        if self._history_debounce_timer is not None:
            self._history_debounce_timer.stop()
        self._pending_history_doc_id = None
    
    def _hide_history_panel_content(self):
        """Leert den Inhalt des Historie-Panels (Panel bleibt offen)."""
        from i18n.de import HISTORY_EMPTY
        self._history_panel._clear_entries()
        self._history_panel._doc_name_label.setText("")
        self._history_panel._status_label.setText(HISTORY_EMPTY)
        self._history_panel._status_label.setVisible(True)
        # Debounce-Timer stoppen
        if self._history_debounce_timer is not None:
            self._history_debounce_timer.stop()
        self._pending_history_doc_id = None
    
    # ========================================
    # Farbmarkierung
    # ========================================
    
    def _create_color_icon(self, hex_color: str):
        """Erstellt ein kleines farbiges Icon (QIcon) fuer das Kontextmenue."""
        from PySide6.QtGui import QPixmap, QPainter, QIcon
        pixmap = QPixmap(16, 16)
        pixmap.fill(QColor(0, 0, 0, 0))  # Transparent
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QBrush(QColor(hex_color)))
        painter.setPen(QColor("#999999"))
        painter.drawEllipse(2, 2, 12, 12)
        painter.end()
        return QIcon(pixmap)
    
    def _set_document_color(self, documents: List[Document], color: Optional[str]):
        """Setzt oder entfernt die Farbmarkierung fuer Dokumente (async via Worker)."""
        if not documents:
            return
        
        doc_ids = [d.id for d in documents]
        
        # Dokument-Referenzen speichern fuer Callback
        self._color_change_documents = documents
        
        self._color_worker = DocumentColorWorker(self.docs_api, doc_ids, color)
        self._color_worker.finished.connect(self._on_color_finished)
        self._color_worker.error.connect(self._on_color_error)
        self._register_worker(self._color_worker)
        self._color_worker.start()
    
    def _on_color_finished(self, count: int, color: Optional[str]):
        """Callback nach Farbmarkierung - aktualisiert lokale Daten und Tabelle."""
        if count > 0:
            # Lokale Dokumente aktualisieren (ohne Server-Refresh)
            documents = getattr(self, '_color_change_documents', [])
            affected_ids = set()
            for doc in documents:
                doc.display_color = color
                affected_ids.add(doc.id)
            
            # Nur betroffene Zeilen updaten statt gesamte Tabelle neu aufbauen
            self._update_row_colors(affected_ids, color)
            
            from i18n.de import DOC_COLOR_SET_SUCCESS, DOC_COLOR_REMOVE_SUCCESS
            if color:
                logger.info(DOC_COLOR_SET_SUCCESS.format(count=count))
            else:
                logger.info(DOC_COLOR_REMOVE_SUCCESS.format(count=count))
        
        self._color_change_documents = None
    
    def _update_row_colors(self, doc_ids: set, color: Optional[str]):
        """Aktualisiert nur die Hintergrundfarbe der betroffenen Zeilen (kein Full-Rebuild)."""
        # Model aktualisiert intern die Document-Objekte und emittiert dataChanged
        self._doc_model.update_colors(doc_ids, color)
    
    def _on_color_error(self, error_msg: str):
        """Callback bei Fehler der Farbmarkierung."""
        from i18n.de import DOC_COLOR_ERROR
        logger.error(DOC_COLOR_ERROR.format(error=error_msg))
        self._toast_manager.show_error(DOC_COLOR_ERROR.format(error=error_msg))
        self._color_change_documents = None
    
    # ========================================
    # Aktionen
    # ========================================
    
    def _move_documents(self, documents: List[Document], target_box: str):
        """
        Verschiebt Dokumente sofort in eine andere Box (ohne Bestätigung).
        
        Wenn Dokumente aus der Eingangsbox manuell verschoben werden,
        werden sie automatisch von der Verarbeitung ausgeschlossen
        (processing_status='manual_excluded').
        
        Zeigt eine Toast-Benachrichtigung mit Rückgängig-Option.
        """
        if not documents:
            return
        
        # Urspruengliche Boxen speichern fuer Undo
        doc_ids = [d.id for d in documents]
        original_boxes = {d.id: d.box_type for d in documents}
        target_name = BOX_DISPLAY_NAMES.get(target_box, target_box)
        
        # Daten fuer Undo speichern
        self._last_move_data = (doc_ids, original_boxes, target_box)
        
        # Wenn aus Eingangsbox manuell verschoben: Von Verarbeitung ausschliessen
        from_eingang = any(d.box_type == 'eingang' for d in documents)
        processing_status = 'manual_excluded' if from_eingang else None
        
        # Sofort verschieben (kein Bestätigungsdialog)
        self._move_worker = DocumentMoveWorker(
            self.docs_api, doc_ids, target_box,
            processing_status=processing_status
        )
        self._move_worker.finished.connect(lambda count: self._on_move_finished(count, target_name, len(documents)))
        self._move_worker.error.connect(self._on_move_error)
        self._register_worker(self._move_worker)
        self._move_worker.start()
    
    def _on_move_finished(self, count: int, target_name: str, total: int):
        """Callback nach Verschieben - zeigt Toast statt MessageBox."""
        from i18n.de import MOVE_SUCCESS_SINGLE, MOVE_SUCCESS_MULTI, MOVE_UNDO
        
        # Historie-Cache invalidieren (betroffene Dokumente wurden verschoben)
        self._history_panel.invalidate_cache()
        
        # Toast-Nachricht erstellen
        if total == 1:
            message = MOVE_SUCCESS_SINGLE.format(box=target_name)
        else:
            message = MOVE_SUCCESS_MULTI.format(count=count, box=target_name)
        
        # Toast anzeigen mit Undo-Button (5 Sekunden)
        self._toast_manager.show_success(message, action_text=MOVE_UNDO, action_callback=self._on_toast_undo_clicked, duration_ms=5000)
        
        # Leichtgewichtiger Refresh - nur Stats und aktuelle Ansicht
        self._refresh_after_move()
    
    def _on_move_error(self, error: str):
        """Callback bei Verschiebe-Fehler."""
        self._toast_manager.show_error(f"Verschieben fehlgeschlagen:\n{error}")
        # Undo-Daten loeschen bei Fehler
        self._last_move_data = None
    
    def _on_documents_dropped(self, doc_ids: List[int], target_box: str):
        """
        Handler fuer Drag & Drop von Dokumenten auf eine Box.
        
        Args:
            doc_ids: Liste der Dokument-IDs die gedroppt wurden
            target_box: Ziel-Box
        """
        # Dokumente anhand der IDs finden
        documents = [doc for doc in self._documents if doc.id in doc_ids]
        
        if documents:
            # Bestehende Move-Logik verwenden (mit Toast und Undo)
            self._move_documents(documents, target_box)
    
    def _on_toast_undo_clicked(self):
        """Handler fuer Klick auf Rückgängig-Button im Toast."""
        from i18n.de import MOVE_UNDONE
        
        # Archivierungs-Undo pruefen
        if hasattr(self, '_last_archive_data') and self._last_archive_data:
            data = self._last_archive_data
            self._last_archive_data = None  # Nur einmal Undo moeglich
            
            doc_ids = data['doc_ids']
            affected_boxes = data['boxes']
            action = data['action']
            
            # Umkehren: archive -> unarchive, unarchive -> archive
            if action == 'archive':
                self.docs_api.unarchive_documents(doc_ids)
            else:
                self.docs_api.archive_documents(doc_ids)
            
            # Cache invalidieren
            self._cache.invalidate_documents()
            
            # Refresh
            self._refresh_stats()
            self._refresh_documents(force_refresh=True)
            self._toast_manager.show_success(MOVE_UNDONE)
            return
        
        # Move-Undo pruefen
        if not self._last_move_data:
            return
        
        doc_ids, original_boxes, _ = self._last_move_data
        self._last_move_data = None  # Nur einmal Undo moeglich
        
        # Dokumente zurueck in ihre urspruenglichen Boxen verschieben
        # Gruppieren nach Ziel-Box
        boxes_to_docs: Dict[str, List[int]] = {}
        for doc_id in doc_ids:
            original_box = original_boxes.get(doc_id)
            if original_box:
                if original_box not in boxes_to_docs:
                    boxes_to_docs[original_box] = []
                boxes_to_docs[original_box].append(doc_id)
        
        # Jede Gruppe zurueck verschieben
        for box_type, ids in boxes_to_docs.items():
            try:
                self.docs_api.move_documents(ids, box_type)
            except Exception as e:
                logger.error(f"Undo fehlgeschlagen: {e}")
        
        # Leichtgewichtiger Refresh
        self._refresh_after_move()
        self._toast_manager.show_success(MOVE_UNDONE)
    
    def _preview_selected(self):
        """Zeigt Vorschau fuer ausgewaehltes Dokument."""
        selected_docs = self._get_selected_documents()
        
        if not selected_docs:
            self._toast_manager.show_info("Bitte ein Dokument auswaehlen.")
            return
        
        if len(selected_docs) > 1:
            self._toast_manager.show_info("Bitte nur ein Dokument fuer die Vorschau auswaehlen.")
            return
        
        doc = selected_docs[0]
        
        if self._is_pdf(doc):
            self._preview_document(doc)
        elif doc.is_gdv:
            self._open_in_gdv_editor(doc)
        elif self._is_spreadsheet(doc):
            self._preview_spreadsheet(doc)
        else:
            from i18n.de import SPREADSHEET_PREVIEW_NOT_AVAILABLE
            self._toast_manager.show_info(SPREADSHEET_PREVIEW_NOT_AVAILABLE.format(filename=doc.original_filename))
    
    def _preview_document(self, doc: Document):
        """Zeigt PDF-Vorschau."""
        self._start_preview_download(doc, preview_kind="pdf")
    
    def _preview_spreadsheet(self, doc: Document):
        """Zeigt Tabellen-Vorschau fuer CSV/Excel-Dateien."""
        self._start_preview_download(doc, preview_kind="spreadsheet")

    def _start_preview_download(self, doc: Document, preview_kind: str):
        """
        Startet den Vorschau-Download im Hintergrund.
        
        Optimierungen:
        - Filename wird direkt uebergeben (spart get_document() API-Call)
        - Persistenter Cache: Gleiche Datei wird nur 1x heruntergeladen
        - Cache-Hit: Kein Progress-Dialog, instant Anzeige
        """
        if hasattr(self, '_preview_worker') and self._preview_worker:
            if not isValid(self._preview_worker):
                self._preview_worker = None
            elif self._preview_worker.isRunning():
                return
        
        self._preview_cancelled = False
        self._preview_doc = doc
        self._preview_kind = preview_kind
        
        # Schnell-Check: Datei bereits im Cache?
        from api.documents import safe_cache_filename
        cached_path = os.path.join(self._preview_cache_dir, safe_cache_filename(doc.id, doc.original_filename))
        if os.path.exists(cached_path) and os.path.getsize(cached_path) > 0:
            logger.info(f"Vorschau instant aus Cache: {doc.original_filename}")
            self._on_preview_download_finished(cached_path)
            return
        
        # Nicht im Cache -> Download mit Progress-Dialog
        progress = QProgressDialog("Lade Vorschau...", "Abbrechen", 0, 0, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.canceled.connect(self._on_preview_download_cancelled)
        progress.show()
        self._preview_progress = progress
        
        self._preview_worker = PreviewDownloadWorker(
            self.docs_api, doc.id, self._preview_cache_dir,
            filename=doc.original_filename,
            cache_dir=self._preview_cache_dir
        )
        self._preview_worker.download_finished.connect(self._on_preview_download_finished)
        self._preview_worker.download_error.connect(self._on_preview_download_error)
        self._register_worker(self._preview_worker)
        self._preview_worker.start()

    def _on_preview_download_cancelled(self):
        """Callback wenn Vorschau-Download abgebrochen wurde."""
        self._preview_cancelled = True
        if hasattr(self, '_preview_worker') and self._preview_worker:
            if isValid(self._preview_worker) and self._preview_worker.isRunning():
                if hasattr(self._preview_worker, 'cancel'):
                    self._preview_worker.cancel()
        if hasattr(self, '_preview_progress') and self._preview_progress:
            self._preview_progress.close()

    def _on_preview_download_finished(self, result):
        """Callback wenn Vorschau-Download fertig ist."""
        # WICHTIG: Cancelled-Flag VOR close() pruefen, weil close() 
        # das canceled-Signal emittiert und den Flag setzen wuerde
        was_cancelled = getattr(self, '_preview_cancelled', False)
        if hasattr(self, '_preview_progress') and self._preview_progress:
            self._preview_progress.blockSignals(True)
            self._preview_progress.close()
            self._preview_progress = None
        
        if was_cancelled:
            return
        
        if result and os.path.exists(result):
            if getattr(self, '_preview_kind', '') == "pdf":
                doc = getattr(self, '_preview_doc', None)
                viewer = PDFViewerDialog(
                    result,
                    f"Vorschau: {self._preview_doc.original_filename}",
                    self,
                    doc_id=doc.id if doc else None,
                    docs_api=self.docs_api,
                    editable=True
                )
                # PDF-Save-Flag: Refresh erst NACH viewer.exec() ausfuehren
                # (verhindert Freeze durch Tabellen-Rebuild waehrend modaler Dialog)
                self._pdf_saved_doc_id = None
                viewer.pdf_saved.connect(self._on_pdf_saved)
                viewer.exec()
                # Nach Dialog-Schliessen: Leichtgewichtigen Refresh ausfuehren
                # Cache invalidieren und Refresh VERZÖGERT starten (100ms),
                # damit Qt die UI erst aktualisieren kann (Dialog-Cleanup).
                if self._pdf_saved_doc_id is not None:
                    self._cache.invalidate_documents()
                    self._cache.invalidate_stats()
                    QTimer.singleShot(100, lambda: self._refresh_documents(force_refresh=True))
            elif getattr(self, '_preview_kind', '') == "spreadsheet":
                from i18n.de import SPREADSHEET_PREVIEW_TITLE
                title = SPREADSHEET_PREVIEW_TITLE.format(filename=self._preview_doc.original_filename)
                viewer = SpreadsheetViewerDialog(result, title, self)
                viewer.exec()
        else:
            if getattr(self, '_preview_kind', '') == "spreadsheet":
                self._toast_manager.show_error("Datei konnte nicht geladen werden.")
            else:
                self._toast_manager.show_error("PDF konnte nicht geladen werden.")

    def _on_preview_download_error(self, error: str):
        """Callback bei Vorschau-Downloadfehler."""
        if hasattr(self, '_preview_progress') and self._preview_progress:
            self._preview_progress.close()
        if self._preview_cancelled:
            return
        self._toast_manager.show_error(f"Vorschau fehlgeschlagen:\n{error}")
    
    def _on_pdf_saved(self, doc_id: int):
        """Callback wenn ein PDF im Editor gespeichert wurde.
        
        WICHTIG: Wird aufgerufen waehrend der modale PDFViewerDialog noch offen ist.
        Schwere Operationen (Tabellen-Rebuild, Server-Refresh) werden aufgeschoben
        bis der Dialog geschlossen ist, um UI-Freeze zu vermeiden.
        """
        from i18n.de import PDF_EDIT_SAVE_SUCCESS
        
        # Vorschau-Cache fuer dieses Dokument invalidieren (leichtgewichtig)
        if self._preview_cache_dir:
            import glob
            cache_pattern = os.path.join(self._preview_cache_dir, f"{doc_id}_*")
            for cached_file in glob.glob(cache_pattern):
                try:
                    os.unlink(cached_file)
                    logger.info(f"Vorschau-Cache invalidiert: {cached_file}")
                except Exception:
                    pass
        
        # Historie-Cache invalidieren (leichtgewichtig)
        if hasattr(self, '_history_panel'):
            self._history_panel.invalidate_cache(doc_id)
        
        # Toast
        self._toast_manager.show_success(PDF_EDIT_SAVE_SUCCESS)
        
        # Refresh AUFGESCHOBEN: Flag setzen, _refresh_all() laeuft nach viewer.exec()
        # (verhindert Tabellen-Rebuild + Server-Calls waehrend modaler Dialog offen ist)
        self._pdf_saved_doc_id = doc_id
    
    def _open_in_gdv_editor(self, doc: Document):
        """Oeffnet GDV-Dokument im Editor."""
        self.open_gdv_requested.emit(doc.id, doc.original_filename)
    
    def _upload_document(self):
        """Ladet ein oder mehrere Dokumente hoch."""
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Dokumente hochladen (in Eingangsbox)",
            "",
            "Alle Dateien (*);;GDV-Dateien (*.gdv *.txt *.dat);;PDF (*.pdf);;XML (*.xml)"
        )
        
        if not file_paths:
            return
        
        # Auto-Refresh pausieren
        self._cache.pause_auto_refresh()
        
        # Progress-Dialog mit Fortschrittsanzeige
        self._upload_progress = QProgressDialog(
            "Lade hoch...", 
            "Abbrechen", 
            0, 
            len(file_paths), 
            self
        )
        self._upload_progress.setWindowModality(Qt.WindowModality.WindowModal)
        self._upload_progress.setWindowTitle("Upload")
        self._upload_progress.setMinimumDuration(0)
        self._upload_progress.show()
        
        self._upload_results = {'erfolge': [], 'fehler': [], 'duplikate': 0}
        
        self._multi_upload_worker = MultiUploadWorker(
            self.docs_api, 
            file_paths, 
            'manual_upload'
        )
        self._multi_upload_worker.progress.connect(self._on_multi_upload_progress)
        self._multi_upload_worker.file_finished.connect(self._on_file_uploaded)
        self._multi_upload_worker.file_error.connect(self._on_file_upload_error)
        self._multi_upload_worker.all_finished.connect(self._on_multi_upload_finished)
        self._register_worker(self._multi_upload_worker)
        self._multi_upload_worker.start()
    
    def _on_multi_upload_progress(self, current: int, total: int, filename: str):
        """Aktualisiert Progress-Dialog."""
        if hasattr(self, '_upload_progress') and self._upload_progress:
            # Maximum dynamisch anpassen (ZIP/MSG koennen mehr Dateien liefern)
            if total != self._upload_progress.maximum():
                self._upload_progress.setMaximum(total)
            self._upload_progress.setValue(current)
            self._upload_progress.setLabelText(f"Lade hoch ({current}/{total}):\n{filename}")
    
    def _on_file_uploaded(self, filename: str, doc: Document):
        """Callback wenn eine Datei erfolgreich hochgeladen wurde."""
        self._upload_results['erfolge'].append(filename)
        if doc and hasattr(doc, 'is_duplicate') and doc.is_duplicate:
            self._upload_results['duplikate'] += 1
    
    def _on_file_upload_error(self, filename: str, error: str):
        """Callback bei Upload-Fehler einer Datei."""
        self._upload_results['fehler'].append(f"{filename}: {error}")
    
    def _on_multi_upload_finished(self, erfolge: int, fehler: int):
        """Callback wenn alle Uploads abgeschlossen sind."""
        if hasattr(self, '_upload_progress') and self._upload_progress:
            self._upload_progress.close()
        
        self._refresh_all()
        
        # Duplikat-Toast anzeigen wenn Duplikate erkannt wurden
        dup_count = self._upload_results.get('duplikate', 0)
        if dup_count > 0:
            from i18n.de import DUPLICATE_DETECTED_TOAST
            self._toast_manager.show_warning(
                DUPLICATE_DETECTED_TOAST.format(count=dup_count)
            )
        
        # Auto-Refresh wieder aktivieren
        self._cache.resume_auto_refresh()
    
    def _download_document(self, doc: Document):
        """Ladet ein Dokument herunter und archiviert es bei Erfolg (nur Target-Boxen)."""
        from i18n.de import ARCHIVE_DOWNLOAD_NOTE, MOVE_UNDO
        
        target_dir = QFileDialog.getExistingDirectory(self, "Speicherort waehlen", "")
        
        if not target_dir:
            return
        
        result = self.docs_api.download(doc.id, target_dir, filename_override=doc.original_filename)
        
        if result:
            # Auto-Archivierung: Nur wenn aus archivierungsfaehiger Box und nicht bereits archiviert
            if doc.box_type in ARCHIVABLE_BOXES and not doc.is_archived:
                if self.docs_api.archive_document(doc.id):
                    # Daten fuer Rueckgaengig speichern
                    self._last_archive_data = {
                        'doc_ids': [doc.id],
                        'boxes': {doc.box_type},
                        'action': 'archive'
                    }
                    # Cache und Stats aktualisieren
                    self._cache.invalidate_documents()
                    self._refresh_stats()
                    self._refresh_documents(force_refresh=True)
                    # Toast mit Rueckgaengig
                    self._toast_manager.show_success(ARCHIVE_DOWNLOAD_NOTE, action_text=MOVE_UNDO, action_callback=self._on_toast_undo_clicked)
            else:
                # Nur Download-Erfolg ohne Archivierung
                self._toast_manager.show_success("Download erfolgreich")
        else:
            self._toast_manager.show_error("Download fehlgeschlagen")
    
    def _download_selected(self):
        """Ladet ausgewaehlte Dokumente im Hintergrund herunter."""
        selected_docs = self._get_selected_documents()
        
        if not selected_docs:
            self._toast_manager.show_info("Bitte mindestens ein Dokument auswaehlen.")
            return
        
        target_dir = QFileDialog.getExistingDirectory(
            self,
            f"Speicherort fuer {len(selected_docs)} Dokument(e) waehlen",
            ""
        )
        
        if not target_dir:
            return
        
        # Auto-Refresh pausieren
        self._cache.pause_auto_refresh()
        
        # Progress-Dialog
        self._download_progress = QProgressDialog(
            f"Lade {len(selected_docs)} Dokument(e) herunter...",
            "Abbrechen",
            0, len(selected_docs),
            self
        )
        self._download_progress.setWindowModality(Qt.WindowModality.WindowModal)
        self._download_progress.setWindowTitle("Download")
        self._download_progress.setMinimumDuration(0)
        self._download_progress.canceled.connect(self._on_download_cancelled)
        self._download_progress.show()
        
        self._download_target_dir = target_dir
        # Dokumente speichern fuer spaetere Archivierung
        self._download_documents_map = {doc.id: doc for doc in selected_docs}
        
        # Worker starten
        self._download_worker = MultiDownloadWorker(
            self.docs_api,
            selected_docs,
            target_dir
        )
        self._download_worker.progress.connect(self._on_download_progress)
        self._download_worker.file_finished.connect(self._on_file_downloaded)
        self._download_worker.file_error.connect(self._on_file_download_error)
        self._download_worker.all_finished.connect(self._on_multi_download_finished)
        self._register_worker(self._download_worker)
        self._download_worker.start()
    
    def _on_download_cancelled(self):
        """Wird aufgerufen wenn der Download abgebrochen wird."""
        if hasattr(self, '_download_worker') and self._download_worker:
            self._download_worker.cancel()
    
    def _on_download_progress(self, current: int, total: int, filename: str):
        """Aktualisiert den Download-Progress-Dialog."""
        if hasattr(self, '_download_progress') and self._download_progress:
            self._download_progress.setValue(current)
            self._download_progress.setLabelText(f"Lade ({current}/{total}):\n{filename}")
    
    def _on_file_downloaded(self, doc_id: int, filename: str, saved_path: str):
        """Callback wenn eine Datei erfolgreich heruntergeladen wurde."""
        logger.debug(f"Download erfolgreich: {filename} (ID: {doc_id}) -> {saved_path}")
    
    def _on_file_download_error(self, doc_id: int, filename: str, error: str):
        """Callback bei Download-Fehler einer Datei."""
        logger.warning(f"Download fehlgeschlagen: {filename} (ID: {doc_id}) - {error}")
    
    def _on_multi_download_finished(self, erfolge: int, fehler: int, fehler_liste: list, erfolgreiche_doc_ids: list):
        """Callback wenn alle Downloads abgeschlossen sind."""
        from i18n.de import ARCHIVE_DOWNLOAD_NOTE_MULTI, MOVE_UNDO
        
        if hasattr(self, '_download_progress') and self._download_progress:
            self._download_progress.close()
        
        # Auto-Archivierung: Archivierbare Dokumente markieren
        archived_count = 0
        archived_doc_ids = []
        docs_map = getattr(self, '_download_documents_map', {})
        affected_boxes = set()
        
        for doc_id in erfolgreiche_doc_ids:
            doc = docs_map.get(doc_id)
            if doc and doc.box_type in ARCHIVABLE_BOXES and not doc.is_archived:
                archived_doc_ids.append(doc_id)
                affected_boxes.add(doc.box_type)
        
        # Bulk-Archivierung (1 API-Call statt N)
        if archived_doc_ids:
            archived_count = self.docs_api.archive_documents(archived_doc_ids)
        
        # Cache invalidieren
        if archived_count > 0:
            self._cache.invalidate_documents()
        
        # Stats und Anzeige aktualisieren wenn archiviert wurde
        if archived_count > 0:
            # Daten fuer Rueckgaengig speichern
            self._last_archive_data = {
                'doc_ids': archived_doc_ids,
                'boxes': affected_boxes,
                'action': 'archive'
            }
            self._refresh_stats()
            self._refresh_documents(force_refresh=True)
        
        # Auto-Refresh wieder aktivieren
        self._cache.resume_auto_refresh()
        
        # Toast anzeigen (still, kein Dialog)
        if fehler == 0:
            if archived_count > 0:
                self._toast_manager.show_success(
                    ARCHIVE_DOWNLOAD_NOTE_MULTI.format(count=archived_count),
                    action_text=MOVE_UNDO, action_callback=self._on_toast_undo_clicked
                )
            else:
                self._toast_manager.show_success(f"{erfolge} Dokument(e) heruntergeladen")
        else:
            # Bei Fehlern nur Toast mit Zusammenfassung
            self._toast_manager.show_warning(f"{erfolge} heruntergeladen, {fehler} fehlgeschlagen")
        
        # Aufraeumen
        self._download_documents_map = {}
    
    # ========================================
    # Box-Download (ganze Box als ZIP/Ordner)
    # ========================================
    
    def _download_box(self, box_type: str, mode: str):
        """
        Laedt alle nicht-archivierten Dokumente einer Box herunter.
        
        Args:
            box_type: Box-Typ ('gdv', 'courtage', etc.)
            mode: 'zip' oder 'folder'
        """
        from i18n.de import (
            BOX_DOWNLOAD_EMPTY, BOX_DOWNLOAD_CHOOSE_ZIP,
            BOX_DOWNLOAD_CHOOSE_FOLDER, BOX_DOWNLOAD_PROGRESS_TITLE
        )
        
        box_name = BOX_DISPLAY_NAMES.get(box_type, box_type)
        
        # Pruefen ob Box leer ist
        count = self.sidebar._stats.get_count(box_type)
        if count == 0:
            self._toast_manager.show_info(BOX_DOWNLOAD_EMPTY.format(box=box_name))
            return
        
        # Zielpfad waehlen
        if mode == 'zip':
            # ZIP-Datei Speicherort waehlen
            default_name = f"{box_name}.zip"
            target_path, _ = QFileDialog.getSaveFileName(
                self,
                BOX_DOWNLOAD_CHOOSE_ZIP,
                default_name,
                "ZIP-Archiv (*.zip)"
            )
        else:
            # Speicherort waehlen - Ordner mit Box-Name wird dort erstellt
            parent_dir = QFileDialog.getExistingDirectory(
                self,
                BOX_DOWNLOAD_CHOOSE_FOLDER.format(box=box_name),
                ""
            )
            if parent_dir:
                target_path = os.path.join(parent_dir, box_name)
            else:
                target_path = ""
        
        if not target_path:
            return
        
        # Auto-Refresh pausieren
        self._cache.pause_auto_refresh()
        
        # Progress-Dialog
        self._box_download_progress = QProgressDialog(
            f"Lade {box_name} herunter...",
            "Abbrechen",
            0, count,
            self
        )
        self._box_download_progress.setWindowModality(Qt.WindowModality.WindowModal)
        self._box_download_progress.setWindowTitle(BOX_DOWNLOAD_PROGRESS_TITLE)
        self._box_download_progress.setMinimumDuration(0)
        self._box_download_progress.canceled.connect(self._on_box_download_cancelled)
        self._box_download_progress.show()
        
        # Box-Typ speichern fuer Archivierung
        self._box_download_box_type = box_type
        
        # Worker starten
        self._box_download_worker = BoxDownloadWorker(
            self.docs_api,
            box_type,
            target_path,
            mode
        )
        self._box_download_worker.progress.connect(self._on_box_download_progress)
        self._box_download_worker.status.connect(self._on_box_download_status)
        self._box_download_worker.finished.connect(self._on_box_download_finished)
        self._box_download_worker.error.connect(self._on_box_download_error)
        self._register_worker(self._box_download_worker)
        self._box_download_worker.start()
    
    def _on_box_download_cancelled(self):
        """Wird aufgerufen wenn der Box-Download abgebrochen wird."""
        if hasattr(self, '_box_download_worker') and self._box_download_worker:
            self._box_download_worker.cancel()
    
    def _on_box_download_progress(self, current: int, total: int, filename: str):
        """Aktualisiert den Box-Download-Progress-Dialog."""
        if hasattr(self, '_box_download_progress') and self._box_download_progress:
            self._box_download_progress.setMaximum(total)
            self._box_download_progress.setValue(current)
            self._box_download_progress.setLabelText(
                f"Lade ({current}/{total}):\n{filename}"
            )
    
    def _on_box_download_status(self, status_msg: str):
        """Aktualisiert die Status-Meldung im Progress-Dialog."""
        if hasattr(self, '_box_download_progress') and self._box_download_progress:
            self._box_download_progress.setLabelText(status_msg)
    
    def _on_box_download_finished(self, erfolge: int, fehler: int, 
                                   fehler_liste: list, erfolgreiche_doc_ids: list):
        """Callback wenn der Box-Download abgeschlossen ist."""
        from i18n.de import (
            BOX_DOWNLOAD_SUCCESS_ZIP, BOX_DOWNLOAD_SUCCESS_FOLDER,
            BOX_DOWNLOAD_PARTIAL, BOX_DOWNLOAD_ARCHIVED, MOVE_UNDO
        )
        
        if hasattr(self, '_box_download_progress') and self._box_download_progress:
            self._box_download_progress.close()
        
        box_type = getattr(self, '_box_download_box_type', '')
        mode = 'zip'
        if hasattr(self, '_box_download_worker') and self._box_download_worker:
            mode = self._box_download_worker.mode
        
        # Auto-Archivierung: Alle erfolgreich heruntergeladenen Dokumente archivieren
        archived_count = 0
        archived_doc_ids = []
        
        if box_type in ARCHIVABLE_BOXES and erfolgreiche_doc_ids:
            # Bulk-Archivierung (1 API-Call statt N)
            archived_count = self.docs_api.archive_documents(erfolgreiche_doc_ids)
            if archived_count > 0:
                archived_doc_ids = erfolgreiche_doc_ids[:archived_count]
        
        # Cache invalidieren und Stats aktualisieren
        if archived_count > 0:
            self._cache.invalidate_documents()
            
            # Daten fuer Rueckgaengig speichern
            self._last_archive_data = {
                'doc_ids': archived_doc_ids,
                'boxes': {box_type},
                'action': 'archive'
            }
            
            self._refresh_stats()
            self._refresh_documents(force_refresh=True)
        
        # Auto-Refresh wieder aktivieren
        self._cache.resume_auto_refresh()
        
        # Toast-Nachricht zusammenbauen
        if fehler == 0:
            if mode == 'zip':
                msg = BOX_DOWNLOAD_SUCCESS_ZIP.format(count=erfolge)
            else:
                msg = BOX_DOWNLOAD_SUCCESS_FOLDER.format(count=erfolge)
            
            if archived_count > 0:
                msg += " " + BOX_DOWNLOAD_ARCHIVED.format(count=archived_count)
            
            self._toast_manager.show_success(msg, action_text=MOVE_UNDO if archived_count > 0 else None, action_callback=self._on_toast_undo_clicked if archived_count > 0 else None)
        else:
            msg = BOX_DOWNLOAD_PARTIAL.format(success=erfolge, failed=fehler)
            if archived_count > 0:
                msg += " " + BOX_DOWNLOAD_ARCHIVED.format(count=archived_count)
            self._toast_manager.show_warning(msg, action_text=MOVE_UNDO if archived_count > 0 else None, action_callback=self._on_toast_undo_clicked if archived_count > 0 else None)
    
    def _on_box_download_error(self, error: str):
        """Callback bei Box-Download-Fehler."""
        from i18n.de import BOX_DOWNLOAD_ERROR
        
        if hasattr(self, '_box_download_progress') and self._box_download_progress:
            self._box_download_progress.close()
        
        # Auto-Refresh wieder aktivieren
        self._cache.resume_auto_refresh()
        
        self._toast_manager.show_error(BOX_DOWNLOAD_ERROR.format(error=error))
    
    # ========================================
    # Verarbeitungs-Ausschluss
    # ========================================
    
    def _exclude_from_processing(self, documents: List[Document]):
        """
        Schliesst Dokumente von der automatischen Verarbeitung aus.
        
        Dokumente in der Eingangsbox werden nach 'sonstige' verschoben,
        damit der Processor sie nicht mehr sieht (robust gegen Server-Caching).
        """
        from i18n.de import PROCESSING_EXCLUDED_TOAST, PROCESSING_EXCLUDED_MULTI
        
        if not documents:
            return
        
        count = 0
        affected_boxes = set()
        
        # Eingangsbox-Dokumente: Verschieben + Status setzen (atomar ueber move)
        eingang_docs = [d for d in documents if d.box_type == 'eingang']
        if eingang_docs:
            eingang_ids = [d.id for d in eingang_docs]
            moved = self.docs_api.move_documents(
                eingang_ids, 'sonstige', 
                processing_status='manual_excluded'
            )
            count += moved
            affected_boxes.add('eingang')
            affected_boxes.add('sonstige')
        
        # Andere Boxen: Nur Status setzen (sind ohnehin nicht in Eingangsbox)
        other_docs = [d for d in documents if d.box_type != 'eingang']
        for doc in other_docs:
            if self.docs_api.update(doc.id, processing_status='manual_excluded'):
                count += 1
                affected_boxes.add(doc.box_type)
        
        if count > 0:
            # Cache invalidieren und Anzeige aktualisieren
            for box_type in affected_boxes:
                self._cache.invalidate_documents(box_type)
            self._refresh_stats()
            self._refresh_documents(force_refresh=True)
            
            if count == 1:
                self._toast_manager.show_info(PROCESSING_EXCLUDED_TOAST)
            else:
                self._toast_manager.show_info(PROCESSING_EXCLUDED_MULTI.format(count=count))
    
    def _include_for_processing(self, documents: List[Document]):
        """Gibt Dokumente erneut fuer die Verarbeitung frei (zurueck in Eingangsbox)."""
        from i18n.de import PROCESSING_INCLUDED_TOAST, PROCESSING_INCLUDED_MULTI
        
        if not documents:
            return
        
        doc_ids = [d.id for d in documents]
        affected_boxes = set(d.box_type for d in documents)
        
        # Zurueck in Eingangsbox verschieben mit Status 'pending'
        moved = self.docs_api.move_documents(doc_ids, 'eingang', processing_status='pending')
        
        if moved > 0:
            # Cache invalidieren
            affected_boxes.add('eingang')
            for box_type in affected_boxes:
                self._cache.invalidate_documents(box_type)
            
            self._refresh_stats()
            self._refresh_documents(force_refresh=True)
            
            if moved == 1:
                self._toast_manager.show_success(PROCESSING_INCLUDED_TOAST)
            else:
                self._toast_manager.show_success(PROCESSING_INCLUDED_MULTI.format(count=moved))
    
    def _archive_documents(self, documents: List[Document]):
        """Archiviert die ausgewaehlten Dokumente (Bulk-API)."""
        from i18n.de import ARCHIVE_SUCCESS_SINGLE, ARCHIVE_SUCCESS_MULTI, MOVE_UNDO
        
        if not documents:
            return
        
        doc_ids = [d.id for d in documents]
        affected_boxes = set(d.box_type for d in documents)
        
        # Archivieren (Bulk: 1 API-Call statt N)
        archived_count = self.docs_api.archive_documents(doc_ids)
        
        if archived_count > 0:
            # Daten fuer Rueckgaengig speichern
            self._last_archive_data = {
                'doc_ids': doc_ids,
                'boxes': affected_boxes,
                'action': 'archive'
            }
            
            # Cache invalidieren
            self._cache.invalidate_documents()
            
            # Stats und Anzeige aktualisieren
            self._refresh_stats()
            self._refresh_documents(force_refresh=True)
            
            # Toast mit Rueckgaengig-Option
            if archived_count == 1:
                self._toast_manager.show_success(ARCHIVE_SUCCESS_SINGLE, action_text=MOVE_UNDO, action_callback=self._on_toast_undo_clicked)
            else:
                self._toast_manager.show_success(
                    ARCHIVE_SUCCESS_MULTI.format(count=archived_count),
                    action_text=MOVE_UNDO, action_callback=self._on_toast_undo_clicked
                )
    
    def _unarchive_documents(self, documents: List[Document]):
        """Entarchiviert die ausgewaehlten Dokumente (Bulk-API)."""
        from i18n.de import UNARCHIVE_SUCCESS_SINGLE, UNARCHIVE_SUCCESS_MULTI, MOVE_UNDO
        
        if not documents:
            return
        
        doc_ids = [d.id for d in documents]
        affected_boxes = set(d.box_type for d in documents)
        
        # Entarchivieren (Bulk: 1 API-Call statt N)
        unarchived_count = self.docs_api.unarchive_documents(doc_ids)
        
        if unarchived_count > 0:
            # Daten fuer Rueckgaengig speichern
            self._last_archive_data = {
                'doc_ids': doc_ids,
                'boxes': affected_boxes,
                'action': 'unarchive'
            }
            
            # Cache invalidieren
            self._cache.invalidate_documents()
            
            # Stats und Anzeige aktualisieren
            self._refresh_stats()
            self._refresh_documents(force_refresh=True)
            
            # Toast mit Rueckgaengig-Option
            if unarchived_count == 1:
                self._toast_manager.show_success(UNARCHIVE_SUCCESS_SINGLE, action_text=MOVE_UNDO, action_callback=self._on_toast_undo_clicked)
            else:
                self._toast_manager.show_success(
                    UNARCHIVE_SUCCESS_MULTI.format(count=unarchived_count),
                    action_text=MOVE_UNDO, action_callback=self._on_toast_undo_clicked
                )
    
    def _delete_document(self, doc: Document):
        """Loescht ein Dokument."""
        reply = QMessageBox.question(
            self,
            "Loeschen bestaetigen",
            f"Dokument '{doc.original_filename}' wirklich loeschen?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            if self.docs_api.delete(doc.id):
                # Erfolgreich geloescht - keine Meldung, nur Refresh
                self._refresh_all()
            else:
                # Nur bei Fehler eine Meldung anzeigen
                self._toast_manager.show_error("Loeschen fehlgeschlagen.")
    
    def _delete_selected(self):
        """Loescht ausgewaehlte Dokumente (Bulk-API: 1 Request statt N)."""
        from i18n import de as texts
        selected_docs = self._get_selected_documents()
        
        if not selected_docs:
            return
        
        reply = QMessageBox.question(
            self,
            texts.CONFIRM_DELETE_TITLE,
            texts.CONFIRM_DELETE_MESSAGE.format(count=len(selected_docs)),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        # Auto-Refresh pausieren
        self._cache.pause_auto_refresh()
        
        try:
            doc_ids = [doc.id for doc in selected_docs]
            deleted = self.docs_api.delete_documents(doc_ids)
            logger.info(f"Bulk-Delete: {deleted}/{len(doc_ids)} Dokument(e) geloescht")
            
            # Daten neu laden
            self._refresh_all()
        
        finally:
            # Auto-Refresh wieder aktivieren
            self._cache.resume_auto_refresh()
    
    # ========================================
    # Umbenennen
    # ========================================
    
    def _rename_document(self, doc: Document):
        """
        Oeffnet einen Dialog zum manuellen Umbenennen eines Dokuments.
        
        Die Dateiendung wird nicht angezeigt und kann nicht geaendert werden.
        
        Args:
            doc: Das Dokument das umbenannt werden soll
        """
        from i18n.de import (
            RENAME_DOCUMENT, RENAME_NEW_NAME, RENAME_SUCCESS, 
            RENAME_ERROR, RENAME_EMPTY_NAME
        )
        import os
        
        # Dateiname und Endung trennen
        current_name = doc.original_filename
        name_without_ext, file_extension = os.path.splitext(current_name)
        
        # InputDialog erstellen und konfigurieren (nur Name ohne Endung)
        dialog = QInputDialog(self)
        dialog.setWindowTitle(RENAME_DOCUMENT)
        # Label mit Hinweis auf Dateiendung
        label_text = f"{RENAME_NEW_NAME}\n(Dateiendung: {file_extension})" if file_extension else RENAME_NEW_NAME
        dialog.setLabelText(label_text)
        dialog.setTextValue(name_without_ext)
        dialog.setMinimumWidth(500)  # Breiterer Dialog
        dialog.resize(550, dialog.sizeHint().height())
        
        # Dialog anzeigen
        ok = dialog.exec()
        new_name_without_ext = dialog.textValue()
        
        if not ok:
            # Benutzer hat abgebrochen
            return
        
        # Leeren Namen pruefen
        new_name_without_ext = new_name_without_ext.strip()
        if not new_name_without_ext:
            self._toast_manager.show_warning(RENAME_EMPTY_NAME)
            return
        
        # Vollstaendigen Namen mit urspruenglicher Endung zusammensetzen
        new_name = new_name_without_ext + file_extension
        
        # Wenn Name unveraendert, nichts tun
        if new_name == current_name:
            return
        
        # Umbenennen (NICHT als KI-umbenannt markieren)
        success = self.docs_api.rename_document(doc.id, new_name, mark_ai_renamed=False)
        
        if success:
            # Wenn in Eingangsbox umbenannt: Von Verarbeitung ausschliessen
            if doc.box_type == 'eingang':
                self.docs_api.update(doc.id, processing_status='manual_excluded')
                logger.info(
                    f"Dokument {doc.id} manuell umbenannt in Eingangsbox "
                    f"-> processing_status='manual_excluded'"
                )
            
            # Tabelle aktualisieren
            self._refresh_all(force_refresh=True)
        else:
            self._toast_manager.show_error(RENAME_ERROR)
    
    # ========================================
    # KI-Benennung
    # ========================================
    
    def _ai_rename_selected(self):
        """KI-Benennung fuer ausgewaehlte Dokumente."""
        selected_docs = self._get_selected_documents()
        pdf_docs = [d for d in selected_docs if d.is_pdf and not d.ai_renamed]
        
        if not pdf_docs:
            all_unrenamed = [d for d in self._documents if d.is_pdf and not d.ai_renamed]
            
            if not all_unrenamed:
                self._toast_manager.show_info("Keine PDFs ohne KI-Benennung gefunden.")
                return
            
            reply = QMessageBox.question(
                self,
                "KI-Benennung",
                f"Keine PDFs ausgewaehlt.\n\n"
                f"Sollen alle {len(all_unrenamed)} unbenannten PDFs verarbeitet werden?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                pdf_docs = all_unrenamed
            else:
                return
        
        self._ai_rename_documents(pdf_docs)
    
    def _ai_rename_documents(self, documents: List[Document]):
        """Startet die KI-Benennung."""
        if not documents:
            return
        
        reply = QMessageBox.question(
            self,
            "KI-Benennung starten",
            f"{len(documents)} PDF(s) werden durch KI analysiert.\n\n"
            "Fortfahren?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        # Auto-Refresh pausieren
        self._cache.pause_auto_refresh()
        
        self._ai_progress = QProgressDialog(
            "Initialisiere KI-Benennung...",
            "Abbrechen",
            0, len(documents),
            self
        )
        self._ai_progress.setWindowTitle("KI-Benennung")
        self._ai_progress.setWindowModality(Qt.WindowModality.WindowModal)
        self._ai_progress.setMinimumDuration(0)
        self._ai_progress.canceled.connect(self._cancel_ai_rename)
        self._ai_progress.show()
        
        self._ai_rename_worker = AIRenameWorker(
            self.api_client,
            self.docs_api,
            documents
        )
        self._ai_rename_worker.progress.connect(self._on_ai_progress)
        self._ai_rename_worker.finished.connect(self._on_ai_finished)
        self._ai_rename_worker.error.connect(self._on_ai_error)
        self._register_worker(self._ai_rename_worker)
        self._ai_rename_worker.start()
    
    def _cancel_ai_rename(self):
        """Bricht KI-Benennung ab."""
        if self._ai_rename_worker:
            self._ai_rename_worker.cancel()
    
    def _on_ai_progress(self, current: int, total: int, filename: str):
        """Callback fuer KI-Fortschritt."""
        if hasattr(self, '_ai_progress') and self._ai_progress:
            self._ai_progress.setValue(current)
            self._ai_progress.setLabelText(f"Verarbeite: {filename}\n({current}/{total})")
    
    def _on_ai_finished(self, results: List):
        """Callback wenn KI-Benennung fertig."""
        if hasattr(self, '_ai_progress') and self._ai_progress:
            self._ai_progress.close()
        
        # Auto-Refresh wieder aktivieren
        self._cache.resume_auto_refresh()
        
        success_count = sum(1 for _, success, _ in results if success)
        failed_count = len(results) - success_count
        
        if failed_count == 0:
            self._toast_manager.show_success(f"Alle {success_count} Dokument(e) erfolgreich umbenannt.")
        else:
            self._toast_manager.show_warning(f"Erfolgreich: {success_count}\nFehlgeschlagen: {failed_count}")
        
        self._refresh_all()
    
    def _on_ai_error(self, error: str):
        """Callback bei KI-Fehler."""
        if hasattr(self, '_ai_progress') and self._ai_progress:
            self._ai_progress.close()
        
        # Auto-Refresh wieder aktivieren
        self._cache.resume_auto_refresh()
        
        self._toast_manager.show_error(f"Ein Fehler ist aufgetreten:\n\n{error}")
    
    # ========================================
    # Automatische Verarbeitung
    # ========================================
    
    def _start_processing(self):
        """Startet die automatische Verarbeitung."""
        # Pruefen ob Dokumente in der Eingangsbox sind
        if self._stats.eingang == 0:
            self._toast_manager.show_info("Keine Dokumente in der Eingangsbox.\nLaden Sie Dokumente hoch oder rufen Sie BiPRO-Lieferungen ab.")
            return
        
        # Auto-Refresh pausieren während der Verarbeitung (BUG-0006 Fix: self._cache statt neue Instanz)
        try:
            self._cache.pause_auto_refresh()
            logger.info("Auto-Refresh für Dokumentenverarbeitung pausiert")
        except Exception as e:
            logger.warning(f"Auto-Refresh pausieren fehlgeschlagen: {e}")
        
        # Processing-Overlay starten (kein Bestaetigungsdialog mehr!)
        self._processing_overlay.start_processing(self._stats.eingang)
        
        self._processing_worker = ProcessingWorker(self.api_client)
        self._processing_worker.progress.connect(self._on_processing_progress)
        self._processing_worker.finished.connect(self._on_processing_finished)
        self._processing_worker.error.connect(self._on_processing_error)
        self._register_worker(self._processing_worker)
        self._processing_worker.start()
    
    def _cancel_processing(self):
        """Bricht Verarbeitung ab."""
        if self._processing_worker:
            self._processing_worker.cancel()
        if hasattr(self, '_processing_overlay'):
            self._processing_overlay.hide()
    
    def _on_processing_progress(self, current: int, total: int, msg: str):
        """Callback fuer Verarbeitungs-Fortschritt."""
        if hasattr(self, '_processing_overlay'):
            self._processing_overlay.update_progress(current, total, msg)
    
    def _on_processing_finished(self, batch_result):
        """Callback wenn Verarbeitung fertig."""
        # Auto-Refresh wieder aktivieren (BUG-0006 Fix: self._cache statt neue Instanz)
        try:
            self._cache.resume_auto_refresh()
            logger.info("Auto-Refresh nach Dokumentenverarbeitung fortgesetzt")
        except Exception as e:
            logger.warning(f"Auto-Refresh fortsetzen fehlgeschlagen: {e}")
        
        # Vorschau-Cache fuer alle verarbeiteten Dokumente invalidieren
        # (Dokumenten-Regeln koennen PDFs veraendern, z.B. leere Seiten entfernen)
        if hasattr(self, '_preview_cache_dir') and self._preview_cache_dir:
            import glob as _glob
            for result in batch_result.results:
                pattern = os.path.join(self._preview_cache_dir, f"{result.document_id}_*")
                for cached_file in _glob.glob(pattern):
                    try:
                        os.unlink(cached_file)
                    except Exception:
                        pass
        
        # Fazit im Overlay anzeigen (kein Popup!)
        if hasattr(self, '_processing_overlay'):
            self._processing_overlay.show_completion(batch_result, auto_close_seconds=10)
        
        # Batch-Abschluss in DB loggen (ohne Kosten)
        history_entry_id = None
        if batch_result.total_documents > 0:
            try:
                from services.document_processor import DocumentProcessor
                processor = DocumentProcessor(self.api_client)
                history_entry_id = processor.log_batch_complete(batch_result)
            except Exception as e:
                logger.warning(f"Batch-Logging fehlgeschlagen: {e}")
        
        # Verzoegerten Kosten-Check starten
        # Bei OpenAI: Akkumulierte Kosten vorhanden, kuerzere Wartezeit
        # Bei OpenRouter: Balance-Diff braucht 90s Verzoegerung
        has_accumulated = batch_result.total_cost_usd and batch_result.total_cost_usd > 0
        has_credits_before = batch_result.credits_before is not None
        if history_entry_id and (has_accumulated or has_credits_before):
            self._start_delayed_cost_check(batch_result, history_entry_id)
    
    def _start_delayed_cost_check(self, batch_result, history_entry_id: int):
        """
        Startet den verzoegerten Kosten-Check.
        
        OpenRouter aktualisiert das Guthaben nicht sofort nach API-Calls.
        Daher warten wir 45 Sekunden, bevor wir das neue Guthaben abrufen
        und die Kosten berechnen.
        """
        from i18n import de as texts
        
        has_accumulated = batch_result.total_cost_usd and batch_result.total_cost_usd > 0
        if has_accumulated and batch_result.provider == 'openai':
            delay_seconds = 5
        elif has_accumulated:
            delay_seconds = 30
        else:
            delay_seconds = 90
        
        logger.info(f"Starte verzoegerten Kosten-Check in {delay_seconds}s (Provider: {batch_result.provider})")
        
        self._delayed_cost_worker = DelayedCostWorker(
            api_client=self.api_client,
            batch_result=batch_result,
            history_entry_id=history_entry_id,
            delay_seconds=delay_seconds
        )
        self._delayed_cost_worker.countdown.connect(self._on_cost_countdown)
        self._delayed_cost_worker.finished.connect(self._on_delayed_cost_finished)
        self._register_worker(self._delayed_cost_worker)
        self._delayed_cost_worker.start()
    
    def _on_cost_countdown(self, remaining: int):
        """Aktualisiert den Credits-Label mit Countdown."""
        from i18n import de as texts
        
        self.credits_label.setText(texts.COSTS_DELAYED_CHECK.format(seconds=remaining))
        self.credits_label.setStyleSheet(f"""
            color: {INFO};
            font-size: {FONT_SIZE_CAPTION};
            font-family: {FONT_BODY};
        """)
    
    def _on_delayed_cost_finished(self, cost_result):
        """Callback wenn verzoegerter Kosten-Check fertig."""
        from ui.toast import ToastManager
        
        if cost_result:
            total_cost = cost_result.get('total_cost_usd', 0)
            cost_per_doc = cost_result.get('cost_per_document_usd', 0)
            docs = cost_result.get('successful_documents', 0)
            provider = cost_result.get('provider', 'unknown')
            source = cost_result.get('cost_source', 'unknown')
            
            logger.info(
                f"Kosten ({provider}, {source}): ${total_cost:.6f} USD "
                f"(${cost_per_doc:.8f}/Dok, {docs} Dokumente)"
            )
            
            if total_cost > 0:
                try:
                    ToastManager.instance().show_info(
                        f"KI-Kosten: ${total_cost:.4f} USD ({docs} Dok., ${cost_per_doc:.6f}/Dok)"
                    )
                except Exception:
                    pass
        else:
            logger.warning("Verzoegerter Kosten-Check: Kein Ergebnis")
        
        # Credits aktualisieren
        self._refresh_credits()
    
    def _on_processing_error(self, error: str):
        """Callback bei Verarbeitungs-Fehler."""
        # Auto-Refresh wieder aktivieren
        try:
            self._cache.resume_auto_refresh()
            logger.info("Auto-Refresh nach Verarbeitungs-Fehler fortgesetzt")
        except Exception as e:
            logger.warning(f"Auto-Refresh fortsetzen fehlgeschlagen: {e}")
        
        # Bei Fehler Overlay verstecken und Fehlermeldung zeigen
        if hasattr(self, '_processing_overlay'):
            self._processing_overlay.hide()
        
        self._toast_manager.show_error(f"Ein Fehler ist aufgetreten:\n\n{error}")
    
    # ================================================================
    # Smart!Scan Versand
    # ================================================================
    
    def _smartscan_box(self, box_type: str):
        """Smart!Scan fuer eine ganze Box starten."""
        from i18n import de as texts
        
        # Permission pruefen
        if not self.auth_api or not self.auth_api.current_user or not self.auth_api.current_user.has_permission('smartscan_send'):
            self._toast_manager.show_warning(texts.PERM_DENIED_SMARTSCAN)
            return
        
        # Alle Dokumente der Box holen (nicht archiviert)
        docs = [d for d in self._documents if d.box_type == box_type and not d.is_archived]
        if not docs:
            return
        
        self._start_smartscan(docs, source_box=box_type)
    
    def _start_smartscan(self, docs, source_box: str = None):
        """Startet SmartScan-Versand mit einfacher Bestaetigung (Einstellungen aus Admin-Config)."""
        from i18n import de as texts
        
        # Permission pruefen
        if not self.auth_api or not self.auth_api.current_user or not self.auth_api.current_user.has_permission('smartscan_send'):
            self._toast_manager.show_warning(texts.PERM_DENIED_SMARTSCAN)
            return
        
        # Einstellungen laden
        try:
            from api.smartscan import SmartScanAPI
            smartscan_api = SmartScanAPI(self.api_client)
            settings = smartscan_api.get_settings()
        except Exception as e:
            logger.error(f"SmartScan-Einstellungen konnten nicht geladen werden: {e}")
            settings = {}
        
        if not settings or not int(settings.get('enabled', 0) or 0):
            self._toast_manager.show_info(texts.SMARTSCAN_DISABLED)
            return
        
        if not settings.get('target_address'):
            self._toast_manager.show_info(texts.SMARTSCAN_NOT_CONFIGURED)
            return
        
        # Einfache Bestaetigung (kein Dialog)
        reply = QMessageBox.question(
            self,
            texts.SMARTSCAN_SEND_CONFIRM_TITLE,
            texts.SMARTSCAN_SEND_CONFIRM.format(count=len(docs)),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        # Alle Werte direkt aus den gespeicherten Admin-Einstellungen
        mode = settings.get('send_mode_default', 'single')
        archive = bool(int(settings.get('archive_after_send', 0) or 0))
        recolor = bool(int(settings.get('recolor_after_send', 0) or 0))
        recolor_color = settings.get('recolor_color') if recolor else None
        
        doc_ids = [d.id for d in docs]
        
        # Worker starten
        self._smartscan_worker = SmartScanWorker(
            self.api_client, mode=mode, document_ids=doc_ids,
            box_type=source_box,
            archive_after=archive, recolor_after=recolor,
            recolor_color=recolor_color
        )
        self._smartscan_worker.progress.connect(self._on_smartscan_progress)
        self._smartscan_worker.completed.connect(self._on_smartscan_finished)
        self._smartscan_worker.error.connect(self._on_smartscan_error)
        # QThread.finished fuer sauberes Cleanup (wenn run() zurueckkehrt)
        self._smartscan_worker.finished.connect(self._cleanup_smartscan_worker)
        
        if hasattr(self, '_active_workers'):
            self._active_workers.append(self._smartscan_worker)
        
        # Loading-Overlay anzeigen (einfache Statusanzeige fuer SmartScan)
        self._show_loading(texts.SMARTSCAN_SENDING)
        
        self._smartscan_worker.start()
    
    def _on_smartscan_progress(self, current: int, total: int, status: str):
        """Fortschritt des SmartScan-Versands."""
        if hasattr(self, '_loading_overlay') and self._loading_overlay.isVisible():
            self._loading_overlay.set_status(status)
    
    def _cleanup_smartscan_worker(self):
        """Raeumt den SmartScan-Worker sauber auf (nicht-blockierend)."""
        worker = getattr(self, '_smartscan_worker', None)
        if worker is None:
            return
        try:
            if worker in self._active_workers:
                self._active_workers.remove(worker)
            worker.deleteLater()
        except RuntimeError:
            pass
        self._smartscan_worker = None
    
    def _on_smartscan_finished(self, job_id: int, result: dict):
        """SmartScan-Versand abgeschlossen."""
        from i18n import de as texts
        
        self._hide_loading()
        
        # Ergebnis anzeigen
        sent = result.get('sent_emails', 0)
        failed = result.get('failed_emails', 0)
        total = result.get('total_documents', 0)
        
        if failed == 0:
            msg = texts.SMARTSCAN_SEND_SUCCESS.format(count=sent if sent else total)
            self._toast_manager.show_success(msg)
        else:
            msg = texts.SMARTSCAN_SEND_PARTIAL.format(sent=sent, total=total, failed=failed)
            self._toast_manager.show_warning(msg)
        
        # Cache invalidieren und neu laden
        self._refresh_all(force_refresh=True)
    
    def _on_smartscan_error(self, error: str):
        """SmartScan-Versand Fehler."""
        from i18n import de as texts
        
        self._hide_loading()
        
        self._toast_manager.show_error(texts.SMARTSCAN_SEND_ERROR.format(error=error))


class _SmartScanDialog(QDialog):
    """Dialog fuer SmartScan Versand-Konfiguration."""
    
    def __init__(self, parent, docs, settings: dict, source_box: str = None):
        super().__init__(parent)
        from i18n import de as texts
        from ui.styles.tokens import (
            get_button_primary_style, get_button_secondary_style,
            DOCUMENT_DISPLAY_COLORS
        )
        
        self._docs = docs
        self._settings = settings
        
        self.setWindowTitle(texts.SMARTSCAN_SEND_TITLE)
        self.setMinimumWidth(450)
        self.setModal(True)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Info: Empfaenger
        target = settings.get('target_address', '')
        info_label = QLabel(texts.SMARTSCAN_SEND_TARGET.format(address=target))
        info_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(info_label)
        
        # Info: Anzahl Dokumente
        doc_label = QLabel(texts.SMARTSCAN_SEND_DOCUMENTS.format(count=len(docs)))
        layout.addWidget(doc_label)
        
        # Geschaetzte Groesse
        total_bytes = sum(getattr(d, 'file_size', 0) or 0 for d in docs)
        if total_bytes > 0:
            if total_bytes > 1024 * 1024:
                size_str = f"{total_bytes / (1024 * 1024):.1f} MB"
            else:
                size_str = f"{total_bytes / 1024:.1f} KB"
            size_label = QLabel(texts.SMARTSCAN_SEND_ESTIMATED_SIZE.format(size=size_str))
            layout.addWidget(size_label)
        
        # Betreff-Vorschau
        subject = settings.get('subject_template', '')
        from datetime import datetime
        rendered_subject = subject.replace('{box}', source_box or '').replace(
            '{date}', datetime.now().strftime('%d.%m.%Y')
        ).replace('{count}', str(len(docs)))
        if rendered_subject:
            subject_label = QLabel(texts.SMARTSCAN_SEND_SUBJECT_PREVIEW.format(subject=rendered_subject))
            subject_label.setWordWrap(True)
            layout.addWidget(subject_label)
        
        layout.addSpacing(10)
        
        # Versandmodus
        form = QFormLayout()
        
        self._mode_combo = QComboBox()
        self._mode_combo.addItem(texts.SMARTSCAN_MODE_SINGLE, 'single')
        self._mode_combo.addItem(texts.SMARTSCAN_MODE_BATCH, 'batch')
        default_mode = settings.get('send_mode_default', 'single')
        idx = self._mode_combo.findData(default_mode)
        if idx >= 0:
            self._mode_combo.setCurrentIndex(idx)
        form.addRow(texts.SMARTSCAN_SEND_MODE_LABEL, self._mode_combo)
        
        layout.addLayout(form)
        
        # Post-Send Aktionen
        self._archive_cb = QCheckBox(texts.SMARTSCAN_SEND_ARCHIVE)
        self._archive_cb.setChecked(bool(settings.get('archive_after_send')))
        layout.addWidget(self._archive_cb)
        
        recolor_layout = QHBoxLayout()
        self._recolor_cb = QCheckBox(texts.SMARTSCAN_SEND_RECOLOR)
        self._recolor_cb.setChecked(bool(settings.get('recolor_after_send')))
        recolor_layout.addWidget(self._recolor_cb)
        
        self._recolor_combo = QComboBox()
        for key, hex_color in DOCUMENT_DISPLAY_COLORS.items():
            self._recolor_combo.addItem(key.capitalize(), key)
        color = settings.get('recolor_color')
        if color:
            cidx = self._recolor_combo.findData(color)
            if cidx >= 0:
                self._recolor_combo.setCurrentIndex(cidx)
        recolor_layout.addWidget(self._recolor_combo)
        recolor_layout.addStretch()
        layout.addLayout(recolor_layout)
        
        layout.addSpacing(10)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        cancel_btn = QPushButton(texts.SMARTSCAN_SEND_CANCEL)
        cancel_btn.setStyleSheet(get_button_secondary_style())
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        send_btn = QPushButton(texts.SMARTSCAN_SEND_BUTTON)
        send_btn.setStyleSheet(get_button_primary_style())
        send_btn.clicked.connect(self.accept)
        btn_layout.addWidget(send_btn)
        
        layout.addLayout(btn_layout)
    
    def get_mode(self) -> str:
        return self._mode_combo.currentData()
    
    def get_archive(self) -> bool:
        return self._archive_cb.isChecked()
    
    def get_recolor(self) -> bool:
        return self._recolor_cb.isChecked()
    
    def get_recolor_color(self) -> str:
        return self._recolor_combo.currentData() if self._recolor_cb.isChecked() else None
