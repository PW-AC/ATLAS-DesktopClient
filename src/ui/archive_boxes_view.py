"""
BiPRO-GDV Tool - Dokumentenarchiv mit Box-System

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
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QLabel, QComboBox, QLineEdit,
    QFileDialog, QMessageBox, QMenu, QProgressDialog, QFrame,
    QSplitter, QGroupBox, QTreeWidget, QTreeWidgetItem, QToolBar,
    QApplication, QProgressBar, QInputDialog
)
from PySide6.QtCore import Qt, Signal, QThread, QMimeData, QTimer, QSize
from PySide6.QtGui import QAction, QFont, QColor, QDrag, QBrush

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
    get_button_primary_style, get_button_secondary_style, get_button_ghost_style
)

from api.client import APIClient
from api.documents import (
    DocumentsAPI, Document, BoxStats, 
    BOX_TYPES, BOX_DISPLAY_NAMES, BOX_COLORS
)

# Boxen aus denen nach Download automatisch archiviert wird
ARCHIVABLE_BOXES = {'gdv', 'courtage', 'sach', 'leben', 'kranken', 'sonstige'}

# Import der bestehenden Hilfsklassen aus archive_view
from ui.archive_view import (
    format_date_german, DocumentLoadWorker, UploadWorker, 
    AIRenameWorker, PDFViewerDialog, HAS_PDF_VIEW
)


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


class ToastNotification(QFrame):
    """
    Kleine Toast-Benachrichtigung am unteren Rand.
    
    Verschwindet automatisch nach einigen Sekunden.
    Optional mit Aktions-Button (z.B. "Rückgängig").
    """
    
    action_clicked = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("toastNotification")
        
        # Frame-Styling
        self.setStyleSheet(f"""
            QFrame#toastNotification {{
                background-color: #1a1a2e;
                border-radius: 8px;
                border: 1px solid #2d2d44;
            }}
        """)
        
        # Layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 14, 20, 14)
        layout.setSpacing(20)
        
        # Text-Label mit direktem Styling
        self._text_label = QLabel("")
        self._text_label.setStyleSheet(f"""
            QLabel {{
                color: #ffffff;
                font-family: {FONT_BODY};
                font-size: 14px;
                font-weight: 500;
                background: transparent;
                border: none;
            }}
        """)
        layout.addWidget(self._text_label)
        
        layout.addStretch()
        
        # Aktions-Button mit direktem Styling
        self._action_btn = QPushButton("")
        self._action_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {ACCENT_500};
                border: none;
                font-family: {FONT_BODY};
                font-size: 14px;
                font-weight: 600;
                padding: 6px 12px;
            }}
            QPushButton:hover {{
                color: #ffffff;
                background-color: rgba(255, 255, 255, 0.1);
                border-radius: 4px;
            }}
        """)
        self._action_btn.setVisible(False)
        self._action_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._action_btn.clicked.connect(self._on_action_clicked)
        layout.addWidget(self._action_btn)
        
        # Auto-Hide Timer
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._fade_out)
        
        # Initial versteckt
        self.setVisible(False)
        self.setFixedHeight(64)
    
    def show_message(self, text: str, action_text: str = None, duration_ms: int = 5000):
        """
        Zeigt eine Toast-Nachricht an.
        
        Args:
            text: Die anzuzeigende Nachricht
            action_text: Optional, Text fuer Aktions-Button
            duration_ms: Anzeigedauer in Millisekunden
        """
        self._text_label.setText(text)
        
        if action_text:
            self._action_btn.setText(action_text)
            self._action_btn.setVisible(True)
        else:
            self._action_btn.setVisible(False)
        
        # Positionieren (unten mittig im Parent)
        if self.parent():
            parent_rect = self.parent().rect()
            toast_width = min(500, parent_rect.width() - 40)
            self.setFixedWidth(toast_width)
            x = (parent_rect.width() - toast_width) // 2
            y = parent_rect.height() - self.height() - 20
            self.move(x, y)
        
        self.setVisible(True)
        self.raise_()
        
        # Timer starten
        self._hide_timer.start(duration_ms)
    
    def _on_action_clicked(self):
        """Handler fuer Klick auf Aktions-Button."""
        self._hide_timer.stop()
        self.setVisible(False)
        self.action_clicked.emit()
    
    def _fade_out(self):
        """Versteckt die Toast-Benachrichtigung."""
        self.setVisible(False)
    
    def hide_now(self):
        """Sofort verstecken."""
        self._hide_timer.stop()
        self.setVisible(False)


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
            lines.append(f"✅ {success_count} Dokument(e) erfolgreich verarbeitet")
        
        if failed_count > 0:
            lines.append(f"⚠️ {failed_count} Dokument(e) fehlgeschlagen")
        
        # Dauer anzeigen
        if duration is not None:
            lines.append(f"⏱️ Dauer: {duration:.1f} Sekunden")
        
        if box_counts:
            lines.append("")
            lines.append("Verteilung:")
            for box_name, count in sorted(box_counts.items()):
                lines.append(f"  • {box_name}: {count}")
        
        # KOSTEN-ANZEIGE
        if total_cost is not None:
            lines.append("")
            lines.append("💰 Kosten:")
            lines.append(f"  • Gesamt: ${total_cost:.4f} USD")
            if cost_per_doc is not None and success_count > 0:
                lines.append(f"  • Pro Dokument: ${cost_per_doc:.6f} USD")
        
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
    """Worker zum Hochladen mehrerer Dateien."""
    file_finished = Signal(str, object)  # filename, Document or None
    file_error = Signal(str, str)  # filename, error message
    all_finished = Signal(int, int)  # erfolge, fehler
    progress = Signal(int, int, str)  # current, total, filename
    
    def __init__(self, docs_api: DocumentsAPI, file_paths: list, source_type: str):
        super().__init__()
        self.docs_api = docs_api
        self.file_paths = file_paths
        self.source_type = source_type
    
    def run(self):
        erfolge = 0
        fehler = 0
        total = len(self.file_paths)
        
        for i, file_path in enumerate(self.file_paths):
            filename = Path(file_path).name
            self.progress.emit(i + 1, total, filename)
            
            try:
                doc = self.docs_api.upload(file_path, self.source_type)
                if doc:
                    self.file_finished.emit(filename, doc)
                    erfolge += 1
                else:
                    self.file_error.emit(filename, "Upload fehlgeschlagen")
                    fehler += 1
            except Exception as e:
                self.file_error.emit(filename, str(e))
                fehler += 1
        
        self.all_finished.emit(erfolge, fehler)


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
                result = self.docs_api.download(doc.id, self.target_dir)
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


class CreditsWorker(QThread):
    """Worker zum Abrufen der OpenRouter Credits."""
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
    
    def __init__(self, docs_api: DocumentsAPI, doc_ids: List[int], target_box: str):
        super().__init__()
        self.docs_api = docs_api
        self.doc_ids = doc_ids
        self.target_box = target_box
    
    def run(self):
        try:
            moved = self.docs_api.move_documents(self.doc_ids, self.target_box)
            self.finished.emit(moved)
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


class SortableTableWidgetItem(QTableWidgetItem):
    """
    TableWidgetItem mit benutzerdefinierter Sortierung.
    
    Speichert einen separaten Sortier-Wert, der für den Vergleich verwendet wird.
    """
    
    def __init__(self, display_text: str, sort_value: str = ""):
        super().__init__(display_text)
        self._sort_value = sort_value if sort_value else display_text
    
    def __lt__(self, other):
        """Vergleich für Sortierung basierend auf Sortier-Wert."""
        if isinstance(other, SortableTableWidgetItem):
            return self._sort_value < other._sort_value
        return super().__lt__(other)


class DraggableDocumentTable(QTableWidget):
    """
    Tabelle mit Drag-Unterstützung für Dokumente.
    
    Beim Ziehen werden die IDs der ausgewählten Dokumente als Text übertragen.
    Mehrfachauswahl bleibt beim Drag erhalten.
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._drag_start_pos = None
        self._drag_started = False
        self._clicked_on_selected = False
    
    def mousePressEvent(self, event):
        """Speichert Startposition für Drag und prüft ob auf Auswahl geklickt."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_pos = event.position().toPoint()
            self._drag_started = False
            
            # Prüfen ob auf ein bereits ausgewähltes Item geklickt wurde
            item = self.itemAt(event.position().toPoint())
            if item and item.isSelected():
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
        
        # Prüfen ob Mindestdistanz überschritten
        distance = (event.position().toPoint() - self._drag_start_pos).manhattanLength()
        if distance < QApplication.startDragDistance():
            super().mouseMoveEvent(event)
            return
        
        # Drag starten (nur einmal)
        if not self._drag_started:
            self._drag_started = True
            self._start_drag()
    
    def mouseReleaseEvent(self, event):
        """Setzt Drag-Startposition zurück und handhabt Klick auf Auswahl."""
        # Wenn auf ausgewähltes Item geklickt wurde aber kein Drag stattfand
        # -> Auswahl auf dieses Item reduzieren
        if self._clicked_on_selected and not self._drag_started:
            item = self.itemAt(event.position().toPoint())
            if item:
                self.clearSelection()
                self.setCurrentItem(item)
                self.selectRow(item.row())
        
        self._drag_start_pos = None
        self._drag_started = False
        self._clicked_on_selected = False
        super().mouseReleaseEvent(event)
    
    def _start_drag(self):
        """Startet Drag mit Dokument-IDs als MIME-Daten."""
        selected_rows = set()
        for item in self.selectedItems():
            selected_rows.add(item.row())
        
        if not selected_rows:
            return
        
        # Dokument-IDs sammeln
        doc_ids = []
        for row in selected_rows:
            id_item = self.item(row, 0)
            if id_item:
                doc = id_item.data(Qt.ItemDataRole.UserRole)
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
        from PySide6.QtGui import QPixmap, QPainter
        
        # Einfaches Vorschau-Pixmap
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


class BoxSidebar(QWidget):
    """
    Sidebar mit Box-Navigation und Drag & Drop Unterstützung.
    
    Zeigt alle Boxen mit Anzahl und ermoeglicht Navigation.
    Dokumente koennen per Drag & Drop in Boxen verschoben werden.
    """
    box_selected = Signal(str)  # box_type oder '' fuer alle
    documents_dropped = Signal(list, str)  # doc_ids, target_box
    
    # Boxen die als Drop-Ziel erlaubt sind
    DROPPABLE_BOXES = {'gdv', 'courtage', 'sach', 'leben', 'kranken', 'sonstige'}
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(220)
        self.setMaximumWidth(300)
        
        self._stats = BoxStats()
        self._current_box = ''
        
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
        
        layout.addWidget(self.tree)
        
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
    
    def update_stats(self, stats: BoxStats):
        """Aktualisiert die Anzahlen in der Sidebar."""
        self._stats = stats
        
        # Verarbeitung (Eingang + Roh) - Pfeil basierend auf Expanded-Status
        processing_total = stats.eingang + stats.roh
        arrow = "▼" if self.processing_item.isExpanded() else "▶"
        self.processing_item.setText(0, f"{arrow}  📥 Verarbeitung ({processing_total})")
        self.eingang_item.setText(0, f"📬 Eingang ({stats.eingang})")
        self.roh_item.setText(0, f"📦 Rohdaten ({stats.roh})")
        
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
        
        # Verarbeitung ausklappen nur wenn Dokumente in Eingangsbox (nicht Roh)
        if stats.eingang > 0:
            self.processing_item.setExpanded(True)
    
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


class ArchiveBoxesView(QWidget):
    """
    Dokumentenarchiv mit Box-System.
    
    Ersetzt die alte ArchiveView mit neuem Layout:
    - Sidebar links mit Box-Navigation
    - Hauptbereich rechts mit Dokumententabelle
    
    Features:
    - Zentraler Cache fuer Server-Daten
    - Auto-Refresh alle 90 Sekunden
    - Daten bleiben beim View-Wechsel erhalten
    """
    
    # Signal wenn ein GDV-Dokument geoeffnet werden soll
    open_gdv_requested = Signal(int, str)  # doc_id, original_filename
    
    def __init__(self, api_client: APIClient, parent=None):
        super().__init__(parent)
        
        self.api_client = api_client
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
        
        # Liste aller aktiven Worker fuer Cleanup
        self._active_workers: List[QThread] = []
        
        # Flag ob erste Ladung erfolgt ist
        self._initial_load_done = False
        
        # Tracking: Wann wurde welche Box zuletzt manuell aktualisiert?
        # Key: box_type (oder '' fuer alle), Value: datetime
        self._last_manual_refresh: Dict[str, datetime] = {}
        
        # Tracking: Welche Boxen wurden seit dem letzten manuellen Refresh bereits geladen?
        # Key: box_type (oder '' fuer alle), Value: datetime
        self._last_box_load: Dict[str, datetime] = {}
        
        self._setup_ui()
        
        # Loading-Overlay erstellen (ueber der Tabelle)
        self._loading_overlay = LoadingOverlay(self)
        self._loading_overlay.setVisible(False)
        
        # Processing-Overlay erstellen (fuer Dokumentenverarbeitung)
        self._processing_overlay = ProcessingProgressOverlay(self)
        self._processing_overlay.close_requested.connect(self._on_processing_overlay_closed)
        
        # Toast-Benachrichtigung erstellen
        self._toast = ToastNotification(self)
        self._toast.action_clicked.connect(self._on_toast_undo_clicked)
        
        # Speicher fuer Undo-Funktion beim Verschieben
        self._last_move_data = None  # (doc_ids, original_boxes, target_box)
        
        # Initiales Laden (aus Cache oder Server)
        self._refresh_all(force_refresh=False)
        
        # Auto-Refresh starten (alle 90 Sekunden)
        self._cache.start_auto_refresh(90)
    
    def _register_worker(self, worker: QThread):
        """Registriert einen Worker fuer sauberes Cleanup."""
        self._active_workers.append(worker)
        # Wenn Worker fertig, aus Liste entfernen und aufräumen
        worker.finished.connect(lambda: self._unregister_worker(worker))
    
    def _unregister_worker(self, worker: QThread):
        """Entfernt einen Worker aus der aktiven Liste."""
        if worker in self._active_workers:
            self._active_workers.remove(worker)
        # Sicher löschen
        worker.deleteLater()
    
    def closeEvent(self, event):
        """Wird aufgerufen wenn das Widget geschlossen wird."""
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
        super().closeEvent(event)
    
    def resizeEvent(self, event):
        """Positioniert die Overlays bei Groessenaenderung."""
        super().resizeEvent(event)
        if hasattr(self, '_loading_overlay'):
            self._loading_overlay.setGeometry(self.rect())
        if hasattr(self, '_processing_overlay'):
            self._processing_overlay.setGeometry(self.rect())
        # Toast neu positionieren wenn sichtbar
        if hasattr(self, '_toast') and self._toast.isVisible():
            parent_rect = self.rect()
            toast_width = min(500, parent_rect.width() - 40)
            self._toast.setFixedWidth(toast_width)
            x = (parent_rect.width() - toast_width) // 2
            y = parent_rect.height() - self._toast.height() - 20
            self._toast.move(x, y)
    
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
        
        splitter.addWidget(main_widget)
        
        # Splitter-Proportionen (Sidebar : Hauptbereich = 1:4)
        splitter.setSizes([200, 800])
        
        layout.addWidget(splitter)
    
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
        self.credits_label.setToolTip("OpenRouter API Guthaben")
        header_layout.addWidget(self.credits_label)
        
        header_layout.addSpacing(20)
        
        # Verarbeiten-Button (PRIMÄR - Orange)
        self.process_btn = QPushButton("Verarbeiten")
        self.process_btn.setToolTip("Dokumente aus der Eingangsbox automatisch verarbeiten")
        self.process_btn.setStyleSheet(get_button_primary_style())
        self.process_btn.clicked.connect(self._start_processing)
        header_layout.addWidget(self.process_btn)
        
        # Aktualisieren (Sekundär) - Erzwingt Server-Reload
        refresh_btn = QPushButton("Aktualisieren")
        refresh_btn.setStyleSheet(get_button_secondary_style())
        refresh_btn.setToolTip("Daten vom Server neu laden (Cache leeren)")
        refresh_btn.clicked.connect(lambda: self._refresh_all(force_refresh=True))
        header_layout.addWidget(refresh_btn)
        
        # Vorschau (Ghost)
        self.preview_btn = QPushButton("Vorschau")
        self.preview_btn.setStyleSheet(get_button_ghost_style())
        self.preview_btn.clicked.connect(self._preview_selected)
        header_layout.addWidget(self.preview_btn)
        
        # Download (Ghost)
        self.download_btn = QPushButton("Herunterladen")
        self.download_btn.setStyleSheet(get_button_ghost_style())
        self.download_btn.clicked.connect(self._download_selected)
        header_layout.addWidget(self.download_btn)
        
        # KI-Benennung (Ghost)
        self.ai_btn = QPushButton("KI-Benennung")
        self.ai_btn.setToolTip("PDFs automatisch durch KI umbenennen")
        self.ai_btn.setStyleSheet(get_button_ghost_style())
        self.ai_btn.clicked.connect(self._ai_rename_selected)
        header_layout.addWidget(self.ai_btn)
        
        # Upload (Sekundär)
        self.upload_btn = QPushButton("Hochladen")
        self.upload_btn.setStyleSheet(get_button_secondary_style())
        self.upload_btn.clicked.connect(self._upload_document)
        header_layout.addWidget(self.upload_btn)
        
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
        filter_layout.addWidget(QLabel("Suche:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Dateiname...")
        self.search_input.textChanged.connect(self._filter_table)
        filter_layout.addWidget(self.search_input)
        
        # Zurücksetzen-Button
        reset_btn = QPushButton("Zurücksetzen")
        reset_btn.setToolTip("Filter und Sortierung zurücksetzen")
        reset_btn.clicked.connect(self._reset_filters)
        filter_layout.addWidget(reset_btn)
        
        filter_layout.addStretch()
        
        return filter_group
    
    def _create_table(self):
        """Erstellt die Dokumenten-Tabelle mit Drag-Unterstützung."""
        self.table = DraggableDocumentTable()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Dateiname", "Box", "Quelle", "Art", "KI", "Datum", "Von"
        ])
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)  # Dateiname
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # Box
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)  # Quelle
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # Art
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)  # KI (schmal)
        header.resizeSection(4, 35)  # Feste Breite für KI-Spalte
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)  # Datum
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)  # Von
        
        # Sortieren aktivieren (Klick auf Header zum Sortieren)
        self.table.setSortingEnabled(True)
        # Standard: Nach Datum absteigend (neueste zuerst)
        self.table.sortByColumn(5, Qt.SortOrder.DescendingOrder)
        
        # Zeilenhöhe fest anpassen (nicht vom Nutzer änderbar)
        self.table.verticalHeader().setDefaultSectionSize(36)
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        self.table.doubleClicked.connect(self._on_double_click)
        
        # Fokus-Umrandung entfernen
        self.table.setStyleSheet("""
            QTableWidget::item:focus {
                outline: none;
                border: none;
            }
            QTableWidget:focus {
                outline: none;
            }
        """)
        
        # Drag aktivieren (Drop wird von Sidebar gehandhabt)
        self.table.setDragEnabled(True)
        self.table.setDragDropMode(QTableWidget.DragDropMode.DragOnly)
    
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
        """
        # Nur Statistiken vom Server holen
        self._refresh_stats(force_refresh=True)
        
        # Aktuelle Box direkt vom Server laden (Cache fuer diese Box invalidieren)
        box_type = self._current_box if self._current_box else None
        documents = self._cache.get_documents(box_type=box_type, force_refresh=True)
        self._apply_filters_and_display(documents)
    
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
    
    def _load_documents_from_cache(self):
        """
        Laedt Dokumente aus dem Cache und aktualisiert die UI.
        
        Wird von Auto-Refresh Callbacks aufgerufen, nachdem Daten
        bereits im Hintergrund geladen wurden.
        """
        # Thread-safe Zugriff ueber oeffentliche API (kein direkter Lock-Zugriff!)
        # Verhindert Deadlocks bei Auto-Refresh aus Background-Thread
        box_type = self._current_box if self._current_box else None
        documents = self._cache.get_documents(box_type=box_type, force_refresh=False)
        
        # Filter anwenden (Quelle)
        source = self.source_filter.currentData() if hasattr(self, 'source_filter') else None
        if source:
            documents = [d for d in documents if d.source == source]
        
        self._documents = documents
        self._populate_table()
        self.table.setEnabled(True)
        
        box_name = BOX_DISPLAY_NAMES.get(self._current_box, "Gesamt Archiv")
        self.status_label.setText(f"{len(documents)} Dokument(e) in {box_name}")
    
    def _refresh_credits(self):
        """Laedt das OpenRouter-Guthaben im Hintergrund."""
        self._credits_worker = CreditsWorker(self.api_client)
        self._credits_worker.finished.connect(self._on_credits_loaded)
        self._register_worker(self._credits_worker)
        self._credits_worker.start()
    
    def _on_credits_loaded(self, credits: Optional[dict]):
        """Callback wenn Credits geladen wurden (ACENCIA Design)."""
        if credits:
            balance = credits.get('balance', 0)
            total_credits = credits.get('total_credits', 0)
            total_usage = credits.get('total_usage', 0)
            
            # Farbkodierung basierend auf verbleibendem Guthaben
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
                f"Verbraucht: ${total_usage:.2f}\n"
                f"Verbleibend: ${balance:.2f}"
            )
        else:
            self.credits_label.setText("")
            self.credits_label.setToolTip("")
    
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
        
        WICHTIG: Verwendet immer Worker fuer Server-Calls um UI nicht zu blockieren.
        
        Args:
            force_refresh: True = Vom Server, False = Aus Cache (falls vorhanden)
        """
        self.status_label.setText("Lade Dokumente...")
        
        # Pruefen ob archivierte Box
        is_archived_box = self._current_box and self._current_box.endswith("_archived")
        actual_box = self._current_box.replace("_archived", "") if is_archived_box else self._current_box
        
        # Cache nur fuer normale Boxen verwenden (nicht fuer archivierte)
        # Der Cache-Service kennt keine is_archived Filter
        if not force_refresh and not is_archived_box:
            cache_key = self._current_box if self._current_box else None
            # Schneller Check ob Daten im RAM-Cache sind (ohne API-Call!)
            # WICHTIG: Oeffentliche API verwenden, NICHT direkten Lock-Zugriff!
            # Direkter Zugriff auf _cache_lock kann zu Deadlocks fuehren wenn
            # der Background-Thread den Lock haelt.
            documents = self._cache.get_documents(box_type=cache_key, force_refresh=False)
            if documents:
                # Daten sind im RAM -> direkt anzeigen (schnell!)
                # Bei normalen Boxen nur nicht-archivierte anzeigen
                documents = [d for d in documents if not d.is_archived]
                self._apply_filters_and_display(documents)
                return
        
        # Daten nicht im Cache oder force_refresh -> Worker starten
        # Loading-Overlay anzeigen
        if is_archived_box:
            box_name = f"{BOX_DISPLAY_NAMES.get(actual_box, 'Box')} Archiviert"
        else:
            box_name = BOX_DISPLAY_NAMES.get(self._current_box, "Archiv")
        self._show_loading(f"{box_name} wird geladen...")
        self.table.setEnabled(False)
        
        filters = {}
        
        # Box-Filter - bei archivierten Boxen den Basis-Box-Typ verwenden
        if actual_box:
            filters['box_type'] = actual_box
        
        # is_archived Filter
        if is_archived_box:
            filters['is_archived'] = True
        elif actual_box:
            # Normale Box: Nur nicht-archivierte anzeigen
            filters['is_archived'] = False
        # Gesamt Archiv (None): Alle Dokumente (archiviert + nicht archiviert)
        
        # Quelle-Filter
        source = self.source_filter.currentData()
        if source:
            filters['source'] = source
        
        self._load_worker = DocumentLoadWorker(self.docs_api, filters)
        self._load_worker.finished.connect(self._on_documents_loaded)
        self._load_worker.error.connect(self._on_load_error)
        self._register_worker(self._load_worker)
        self._load_worker.start()
    
    def _on_documents_loaded(self, documents: List[Document]):
        """Callback wenn Dokumente geladen wurden."""
        # Loading-Overlay verstecken
        self._hide_loading()
        
        self._apply_filters_and_display(documents)
        
        # Cache wird automatisch durch get_documents() bei Bedarf befuellt
        # Kein manuelles Befuellen noetig (und kein direkter Lock-Zugriff!)
    
    def _apply_filters_and_display(self, documents: List[Document]):
        """Wendet Filter an und zeigt Dokumente in der Tabelle."""
        # Quelle-Filter anwenden
        source = self.source_filter.currentData() if hasattr(self, 'source_filter') else None
        if source:
            documents = [d for d in documents if d.source_type == source]
        
        # Art-Filter anwenden (Dateityp)
        file_type = self.type_filter.currentData() if hasattr(self, 'type_filter') else None
        if file_type:
            documents = [d for d in documents if self._get_file_type(d) == file_type]
        
        # KI-Filter anwenden
        ki_status = self.ki_filter.currentData() if hasattr(self, 'ki_filter') else None
        if ki_status == "yes":
            documents = [d for d in documents if d.ai_renamed]
        elif ki_status == "no":
            documents = [d for d in documents if not d.ai_renamed and d.is_pdf]
        
        self._documents = documents
        self._populate_table()
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
        QMessageBox.warning(self, "Fehler", f"Dokumente konnten nicht geladen werden:\n{error}")
    
    def _populate_table(self):
        """Fuellt die Tabelle mit Dokumenten."""
        # Sortierung temporär deaktivieren während des Befüllens
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(self._documents))
        
        # Flags fuer nicht-editierbare Items
        readonly_flags = Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled
        
        for row, doc in enumerate(self._documents):
            # Dateiname (nicht direkt editierbar - nur ueber Kontextmenue)
            # Document-Referenz wird hier als UserRole gespeichert
            name_item = QTableWidgetItem(doc.original_filename)
            name_item.setData(Qt.ItemDataRole.UserRole, doc)
            name_item.setFlags(readonly_flags)
            self.table.setItem(row, 0, name_item)
            
            # Box mit Farbkodierung
            box_item = QTableWidgetItem(doc.box_type_display)
            box_color = QColor(doc.box_color)
            box_item.setForeground(QBrush(box_color))
            box_item.setFont(QFont("Open Sans", 9, QFont.Weight.Medium))
            box_item.setFlags(readonly_flags)
            self.table.setItem(row, 1, box_item)
            
            # Quelle
            source_item = QTableWidgetItem(doc.source_type_display)
            if doc.source_type == 'bipro_auto':
                source_item.setForeground(QColor(INFO))  # ACENCIA Hellblau
            source_item.setFlags(readonly_flags)
            self.table.setItem(row, 2, source_item)
            
            # Art (Dateityp)
            file_type = self._get_file_type(doc)
            type_item = QTableWidgetItem(file_type)
            # Farbkodierung nach Typ
            if file_type == "GDV":
                type_item.setForeground(QColor(SUCCESS))  # Grün
            elif file_type == "PDF":
                type_item.setForeground(QColor(ERROR))  # Rot (auffällig)
            elif file_type == "XML":
                type_item.setForeground(QColor(INFO))  # Hellblau
            type_item.setFlags(readonly_flags)
            self.table.setItem(row, 3, type_item)
            
            # KI-Status (schlanke Spalte)
            if doc.ai_renamed:
                ai_item = QTableWidgetItem("✓")
                ai_item.setForeground(QColor(SUCCESS))  # Grün
                ai_item.setToolTip("KI-verarbeitet")
            elif doc.ai_processing_error:
                ai_item = QTableWidgetItem("✗")
                ai_item.setForeground(QColor(ERROR))  # Rot
                ai_item.setToolTip(doc.ai_processing_error)
            elif doc.is_pdf:
                ai_item = QTableWidgetItem("-")
            else:
                ai_item = QTableWidgetItem("")
            ai_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            ai_item.setFlags(readonly_flags)
            self.table.setItem(row, 4, ai_item)
            
            # Datum (deutsches Format) - mit ISO-Format für korrekte Sortierung
            date_item = SortableTableWidgetItem(
                format_date_german(doc.created_at),
                doc.created_at or ""  # ISO-Format für Sortierung
            )
            date_item.setFlags(readonly_flags)
            self.table.setItem(row, 5, date_item)
            
            # Hochgeladen von
            by_item = QTableWidgetItem(doc.uploaded_by_name or "")
            by_item.setFlags(readonly_flags)
            self.table.setItem(row, 6, by_item)
        
        # Sortierung wieder aktivieren
        self.table.setSortingEnabled(True)
    
    def _get_file_type(self, doc) -> str:
        """Ermittelt den Dateityp für die Anzeige."""
        # GDV hat Priorität
        if doc.is_gdv:
            return "GDV"
        
        # Dateiendung extrahieren
        ext = doc.file_extension.lower() if hasattr(doc, 'file_extension') else ""
        if not ext and '.' in doc.original_filename:
            ext = '.' + doc.original_filename.rsplit('.', 1)[-1].lower()
        
        # Bekannte Typen
        type_map = {
            '.pdf': 'PDF',
            '.xml': 'XML',
            '.txt': 'TXT',
            '.gdv': 'GDV',
            '.dat': 'DAT',
            '.vwb': 'VWB',
            '.csv': 'CSV',
            '.xlsx': 'Excel',
            '.xls': 'Excel',
            '.doc': 'Word',
            '.docx': 'Word',
            '.jpg': 'Bild',
            '.jpeg': 'Bild',
            '.png': 'Bild',
            '.gif': 'Bild',
            '.zip': 'ZIP',
        }
        
        return type_map.get(ext, ext.upper().lstrip('.') if ext else '?')
    
    def _filter_table(self):
        """Filtert die Tabelle nach Suchbegriff."""
        search_text = self.search_input.text().lower()
        
        for row in range(self.table.rowCount()):
            filename_item = self.table.item(row, 1)
            if filename_item:
                matches = search_text in filename_item.text().lower()
                self.table.setRowHidden(row, not matches)
    
    def _apply_filter(self):
        """Wendet Filter an (aus Cache, kein Server-Request)."""
        self._refresh_documents(force_refresh=False)
    
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
        
        # Sortierung auf Standard zurücksetzen (Datum absteigend)
        self.table.sortByColumn(5, Qt.SortOrder.DescendingOrder)
        
        # Tabelle neu laden
        self._refresh_documents(force_refresh=False)
    
    def _on_box_selected(self, box_type: str):
        """Handler wenn eine Box in der Sidebar ausgewaehlt wird."""
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
            logger.info(f"Box '{box_type}' seit manuellem Refresh noch nicht geladen - hole Daten vom Server")
            self._refresh_documents(force_refresh=True)
            # Als geladen markieren
            self._last_box_load[box_type] = datetime.now()
        else:
            # Dokumente aus Cache laden (kein Server-Request!)
            self._refresh_documents(force_refresh=False)
    
    def _should_refresh_box(self, box_type: str) -> bool:
        """
        Prueft ob eine Box seit dem letzten manuellen Refresh neu geladen werden muss.
        
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
        
        # Wann wurde diese Box zuletzt geladen?
        last_load = self._last_box_load.get(box_type)
        
        # Wenn noch nie geladen ODER letzte Ladung vor dem manuellen Refresh
        if not last_load or last_load < last_manual:
            return True
        
        return False
    
    def _show_context_menu(self, position):
        """Zeigt das Kontextmenue."""
        item = self.table.itemAt(position)
        if not item:
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
        
        menu.addSeparator()
        
        # ===== Verschieben =====
        move_menu = QMenu("Verschieben nach...", menu)
        
        # Boxen der ausgewaehlten Dokumente ermitteln (diese nicht anbieten)
        current_boxes = set(d.box_type for d in selected_docs if d.box_type)
        
        for box_type in ['gdv', 'courtage', 'sach', 'leben', 'kranken', 'sonstige']:
            # Box ueberspringen wenn alle Dokumente bereits dort sind
            if box_type in current_boxes and len(current_boxes) == 1:
                continue
            box_name = BOX_DISPLAY_NAMES.get(box_type, box_type)
            action = QAction(box_name, self)
            action.triggered.connect(lambda checked, bt=box_type: self._move_documents(selected_docs, bt))
            move_menu.addAction(action)
        
        menu.addMenu(move_menu)
        
        # ===== KI-Benennung =====
        pdf_docs = [d for d in selected_docs if d.is_pdf and not d.ai_renamed]
        if pdf_docs:
            menu.addSeparator()
            ai_action = QAction(f"KI-Benennung ({len(pdf_docs)} PDF{'s' if len(pdf_docs) > 1 else ''})", self)
            ai_action.triggered.connect(lambda: self._ai_rename_documents(pdf_docs))
            menu.addAction(ai_action)
        
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
    
    def _on_double_click(self, index):
        """Handler fuer Doppelklick."""
        row = index.row()
        doc_item = self.table.item(row, 0)
        if doc_item:
            doc: Document = doc_item.data(Qt.ItemDataRole.UserRole)
            if doc.is_gdv:
                self._open_in_gdv_editor(doc)
            elif self._is_pdf(doc):
                self._preview_document(doc)
            else:
                self._download_document(doc)
    
    def _get_selected_documents(self) -> List[Document]:
        """Gibt alle ausgewaehlten Dokumente zurueck."""
        selected_docs = []
        selected_rows = set()
        
        for item in self.table.selectedItems():
            selected_rows.add(item.row())
        
        for row in selected_rows:
            doc_item = self.table.item(row, 0)
            if doc_item:
                doc = doc_item.data(Qt.ItemDataRole.UserRole)
                if doc:
                    selected_docs.append(doc)
        
        return selected_docs
    
    def _is_pdf(self, doc: Document) -> bool:
        """Prueft ob das Dokument ein PDF ist."""
        return doc.is_pdf
    
    # ========================================
    # Aktionen
    # ========================================
    
    def _move_documents(self, documents: List[Document], target_box: str):
        """
        Verschiebt Dokumente sofort in eine andere Box (ohne Bestätigung).
        
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
        
        # Sofort verschieben (kein Bestätigungsdialog)
        self._move_worker = DocumentMoveWorker(self.docs_api, doc_ids, target_box)
        self._move_worker.finished.connect(lambda count: self._on_move_finished(count, target_name, len(documents)))
        self._move_worker.error.connect(self._on_move_error)
        self._register_worker(self._move_worker)
        self._move_worker.start()
    
    def _on_move_finished(self, count: int, target_name: str, total: int):
        """Callback nach Verschieben - zeigt Toast statt MessageBox."""
        from i18n.de import MOVE_SUCCESS_SINGLE, MOVE_SUCCESS_MULTI, MOVE_UNDO
        
        # Toast-Nachricht erstellen
        if total == 1:
            message = MOVE_SUCCESS_SINGLE.format(box=target_name)
        else:
            message = MOVE_SUCCESS_MULTI.format(count=count, box=target_name)
        
        # Toast anzeigen mit Undo-Button (5 Sekunden)
        self._toast.show_message(message, action_text=MOVE_UNDO, duration_ms=5000)
        
        # Leichtgewichtiger Refresh - nur Stats und aktuelle Ansicht
        self._refresh_after_move()
    
    def _on_move_error(self, error: str):
        """Callback bei Verschiebe-Fehler."""
        QMessageBox.warning(self, "Fehler", f"Verschieben fehlgeschlagen:\n{error}")
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
            for box_type in affected_boxes:
                self._cache.invalidate_documents(box_type)
            
            # Refresh
            self._refresh_stats()
            self._refresh_documents(force_refresh=True)
            self._toast.show_message(MOVE_UNDONE)
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
        self._toast.show_message(MOVE_UNDONE)
    
    def _preview_selected(self):
        """Zeigt Vorschau fuer ausgewaehltes Dokument."""
        selected_docs = self._get_selected_documents()
        
        if not selected_docs:
            QMessageBox.information(self, "Info", "Bitte ein Dokument auswaehlen.")
            return
        
        if len(selected_docs) > 1:
            QMessageBox.information(self, "Info", "Bitte nur ein Dokument fuer die Vorschau auswaehlen.")
            return
        
        doc = selected_docs[0]
        
        if self._is_pdf(doc):
            self._preview_document(doc)
        elif doc.is_gdv:
            self._open_in_gdv_editor(doc)
        else:
            QMessageBox.information(
                self,
                "Keine Vorschau",
                f"Fuer '{doc.original_filename}' ist keine Vorschau verfuegbar."
            )
    
    def _preview_document(self, doc: Document):
        """Zeigt PDF-Vorschau."""
        temp_dir = tempfile.mkdtemp(prefix='bipro_preview_')
        
        progress = QProgressDialog("Lade Vorschau...", "Abbrechen", 0, 0, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.show()
        
        try:
            result = self.docs_api.download(doc.id, temp_dir)
            progress.close()
            
            if result and os.path.exists(result):
                viewer = PDFViewerDialog(result, f"Vorschau: {doc.original_filename}", self)
                viewer.exec()
            else:
                QMessageBox.warning(self, "Fehler", "PDF konnte nicht geladen werden.")
        except Exception as e:
            progress.close()
            QMessageBox.warning(self, "Fehler", f"Vorschau fehlgeschlagen:\n{e}")
    
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
        
        self._upload_results = {'erfolge': [], 'fehler': []}
        
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
            self._upload_progress.setValue(current)
            self._upload_progress.setLabelText(f"Lade hoch ({current}/{total}):\n{filename}")
    
    def _on_file_uploaded(self, filename: str, doc: Document):
        """Callback wenn eine Datei erfolgreich hochgeladen wurde."""
        self._upload_results['erfolge'].append(filename)
    
    def _on_file_upload_error(self, filename: str, error: str):
        """Callback bei Upload-Fehler einer Datei."""
        self._upload_results['fehler'].append(f"{filename}: {error}")
    
    def _on_multi_upload_finished(self, erfolge: int, fehler: int):
        """Callback wenn alle Uploads abgeschlossen sind."""
        if hasattr(self, '_upload_progress') and self._upload_progress:
            self._upload_progress.close()
        
        # Zusammenfassung anzeigen
        if fehler == 0:
            QMessageBox.information(
                self,
                "Upload abgeschlossen",
                f"{erfolge} Dokument(e) erfolgreich in die Eingangsbox hochgeladen."
            )
        else:
            fehler_text = "\n".join(self._upload_results['fehler'][:5])
            if len(self._upload_results['fehler']) > 5:
                fehler_text += f"\n... und {len(self._upload_results['fehler']) - 5} weitere"
            
            QMessageBox.warning(
                self,
                "Upload abgeschlossen",
                f"Erfolgreich: {erfolge}\nFehlgeschlagen: {fehler}\n\nFehler:\n{fehler_text}"
            )
        
        self._refresh_all()
        
        # Auto-Refresh wieder aktivieren
        self._cache.resume_auto_refresh()
    
    def _download_document(self, doc: Document):
        """Ladet ein Dokument herunter und archiviert es bei Erfolg (nur Target-Boxen)."""
        from i18n.de import ARCHIVE_DOWNLOAD_NOTE, MOVE_UNDO
        
        target_dir = QFileDialog.getExistingDirectory(self, "Speicherort waehlen", "")
        
        if not target_dir:
            return
        
        result = self.docs_api.download(doc.id, target_dir)
        
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
                    self._cache.invalidate_documents(doc.box_type)
                    self._refresh_stats()
                    self._refresh_documents(force_refresh=True)
                    # Toast mit Rueckgaengig
                    self._toast.show_message(ARCHIVE_DOWNLOAD_NOTE, MOVE_UNDO)
            else:
                # Nur Download-Erfolg ohne Archivierung
                self._toast.show_message("Download erfolgreich")
        else:
            self._toast.show_message("Download fehlgeschlagen")
    
    def _download_selected(self):
        """Ladet ausgewaehlte Dokumente im Hintergrund herunter."""
        selected_docs = self._get_selected_documents()
        
        if not selected_docs:
            QMessageBox.information(self, "Info", "Bitte mindestens ein Dokument auswaehlen.")
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
                if self.docs_api.archive_document(doc_id):
                    archived_count += 1
                    archived_doc_ids.append(doc_id)
                    affected_boxes.add(doc.box_type)
        
        # Cache fuer betroffene Boxen invalidieren
        for box_type in affected_boxes:
            self._cache.invalidate_documents(box_type)
        
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
                self._toast.show_message(
                    ARCHIVE_DOWNLOAD_NOTE_MULTI.format(count=archived_count),
                    MOVE_UNDO
                )
            else:
                self._toast.show_message(f"{erfolge} Dokument(e) heruntergeladen")
        else:
            # Bei Fehlern nur Toast mit Zusammenfassung
            self._toast.show_message(f"{erfolge} heruntergeladen, {fehler} fehlgeschlagen")
        
        # Aufraeumen
        self._download_documents_map = {}
    
    def _archive_documents(self, documents: List[Document]):
        """Archiviert die ausgewaehlten Dokumente."""
        from i18n.de import ARCHIVE_SUCCESS_SINGLE, ARCHIVE_SUCCESS_MULTI, MOVE_UNDO
        
        if not documents:
            return
        
        doc_ids = [d.id for d in documents]
        affected_boxes = set(d.box_type for d in documents)
        
        # Archivieren
        archived_count = self.docs_api.archive_documents(doc_ids)
        
        if archived_count > 0:
            # Daten fuer Rueckgaengig speichern
            self._last_archive_data = {
                'doc_ids': doc_ids,
                'boxes': affected_boxes,
                'action': 'archive'
            }
            
            # Cache fuer betroffene Boxen invalidieren
            for box_type in affected_boxes:
                self._cache.invalidate_documents(box_type)
            
            # Stats und Anzeige aktualisieren
            self._refresh_stats()
            self._refresh_documents(force_refresh=True)
            
            # Toast mit Rueckgaengig-Option
            if archived_count == 1:
                self._toast.show_message(ARCHIVE_SUCCESS_SINGLE, MOVE_UNDO)
            else:
                self._toast.show_message(
                    ARCHIVE_SUCCESS_MULTI.format(count=archived_count),
                    MOVE_UNDO
                )
    
    def _unarchive_documents(self, documents: List[Document]):
        """Entarchiviert die ausgewaehlten Dokumente."""
        from i18n.de import UNARCHIVE_SUCCESS_SINGLE, UNARCHIVE_SUCCESS_MULTI, MOVE_UNDO
        
        if not documents:
            return
        
        doc_ids = [d.id for d in documents]
        affected_boxes = set(d.box_type for d in documents)
        
        # Entarchivieren
        unarchived_count = self.docs_api.unarchive_documents(doc_ids)
        
        if unarchived_count > 0:
            # Daten fuer Rueckgaengig speichern
            self._last_archive_data = {
                'doc_ids': doc_ids,
                'boxes': affected_boxes,
                'action': 'unarchive'
            }
            
            # Cache fuer betroffene Boxen invalidieren
            for box_type in affected_boxes:
                self._cache.invalidate_documents(box_type)
            
            # Stats und Anzeige aktualisieren
            self._refresh_stats()
            self._refresh_documents(force_refresh=True)
            
            # Toast mit Rueckgaengig-Option
            if unarchived_count == 1:
                self._toast.show_message(UNARCHIVE_SUCCESS_SINGLE, MOVE_UNDO)
            else:
                self._toast.show_message(
                    UNARCHIVE_SUCCESS_MULTI.format(count=unarchived_count),
                    MOVE_UNDO
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
                QMessageBox.warning(self, "Fehler", "Loeschen fehlgeschlagen.")
    
    def _delete_selected(self):
        """Loescht ausgewaehlte Dokumente."""
        selected_docs = self._get_selected_documents()
        
        if not selected_docs:
            return
        
        reply = QMessageBox.question(
            self,
            "Loeschen bestaetigen",
            f"Wirklich {len(selected_docs)} Dokument(e) loeschen?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        # Auto-Refresh pausieren
        self._cache.pause_auto_refresh()
        
        try:
            # Progress-Dialog mit Fortschrittsanzeige
            progress = QProgressDialog(
                "Loesche Dokumente...",
                "Abbrechen",
                0, len(selected_docs),
                self
            )
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.setAutoClose(True)  # Automatisch schließen wenn fertig
            progress.setMinimumDuration(0)  # Sofort anzeigen
            
            success_count = 0
            for i, doc in enumerate(selected_docs):
                # Abbruch pruefen
                if progress.wasCanceled():
                    break
                
                # Fortschritt aktualisieren
                progress.setValue(i)
                progress.setLabelText(f"Loesche {i+1}/{len(selected_docs)}: {doc.original_filename}")
                QApplication.processEvents()  # UI aktualisieren
                
                # Dokument loeschen
                if self.docs_api.delete(doc.id):
                    success_count += 1
            
            # Abschluss
            progress.setValue(len(selected_docs))
            
            # Daten neu laden (kein Pop-up nach Abschluss!)
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
            QMessageBox.warning(self, RENAME_DOCUMENT, RENAME_EMPTY_NAME)
            return
        
        # Vollstaendigen Namen mit urspruenglicher Endung zusammensetzen
        new_name = new_name_without_ext + file_extension
        
        # Wenn Name unveraendert, nichts tun
        if new_name == current_name:
            return
        
        # Umbenennen (NICHT als KI-umbenannt markieren)
        success = self.docs_api.rename_document(doc.id, new_name, mark_ai_renamed=False)
        
        if success:
            # Tabelle aktualisieren
            self._refresh_all(force_refresh=True)
        else:
            QMessageBox.warning(self, RENAME_DOCUMENT, RENAME_ERROR)
    
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
                QMessageBox.information(
                    self,
                    "KI-Benennung",
                    "Keine PDFs ohne KI-Benennung gefunden."
                )
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
            QMessageBox.information(
                self,
                "KI-Benennung abgeschlossen",
                f"Alle {success_count} Dokument(e) erfolgreich umbenannt."
            )
        else:
            QMessageBox.warning(
                self,
                "KI-Benennung mit Fehlern",
                f"Erfolgreich: {success_count}\n"
                f"Fehlgeschlagen: {failed_count}"
            )
        
        self._refresh_all()
    
    def _on_ai_error(self, error: str):
        """Callback bei KI-Fehler."""
        if hasattr(self, '_ai_progress') and self._ai_progress:
            self._ai_progress.close()
        
        # Auto-Refresh wieder aktivieren
        self._cache.resume_auto_refresh()
        
        QMessageBox.critical(
            self,
            "KI-Benennung Fehler",
            f"Ein Fehler ist aufgetreten:\n\n{error}"
        )
    
    # ========================================
    # Automatische Verarbeitung
    # ========================================
    
    def _start_processing(self):
        """Startet die automatische Verarbeitung."""
        # Pruefen ob Dokumente in der Eingangsbox sind
        if self._stats.eingang == 0:
            QMessageBox.information(
                self,
                "Verarbeitung",
                "Keine Dokumente in der Eingangsbox.\n\n"
                "Laden Sie Dokumente hoch oder rufen Sie BiPRO-Lieferungen ab."
            )
            return
        
        # Auto-Refresh pausieren während der Verarbeitung
        try:
            from services.data_cache import DataCacheService
            cache = DataCacheService()
            cache.pause_auto_refresh()
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
        # Auto-Refresh wieder aktivieren
        try:
            from services.data_cache import DataCacheService
            cache = DataCacheService()
            cache.resume_auto_refresh()
            logger.info("Auto-Refresh nach Dokumentenverarbeitung fortgesetzt")
        except Exception as e:
            logger.warning(f"Auto-Refresh fortsetzen fehlgeschlagen: {e}")
        
        # Fazit im Overlay anzeigen (kein Popup!)
        # batch_result ist jetzt BatchProcessingResult mit Kosten-Informationen
        if hasattr(self, '_processing_overlay'):
            self._processing_overlay.show_completion(batch_result, auto_close_seconds=10)
    
    def _on_processing_error(self, error: str):
        """Callback bei Verarbeitungs-Fehler."""
        # Auto-Refresh wieder aktivieren
        try:
            from services.data_cache import DataCacheService
            cache = DataCacheService()
            cache.resume_auto_refresh()
            logger.info("Auto-Refresh nach Verarbeitungs-Fehler fortgesetzt")
        except Exception as e:
            logger.warning(f"Auto-Refresh fortsetzen fehlgeschlagen: {e}")
        
        # Bei Fehler Overlay verstecken und Fehlermeldung zeigen
        if hasattr(self, '_processing_overlay'):
            self._processing_overlay.hide()
        
        QMessageBox.critical(
            self,
            "Verarbeitung Fehler",
            f"Ein Fehler ist aufgetreten:\n\n{error}"
        )
