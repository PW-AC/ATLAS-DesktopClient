"""
ACENCIA ATLAS - Archiv UI-Widgets

Extrahiert aus archive_boxes_view.py:
- DocumentHistoryPanel
- LoadingOverlay
- ProcessingProgressOverlay
"""

from typing import Optional, Dict
from datetime import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QProgressBar, QApplication,
)
from PySide6.QtCore import Qt, Signal, QTimer

from ui.styles.tokens import (
    PRIMARY_500, PRIMARY_900, PRIMARY_100, PRIMARY_0,
    ACCENT_500, ACCENT_100,
    TEXT_PRIMARY, TEXT_SECONDARY,
    BG_PRIMARY, BG_SECONDARY, BORDER_DEFAULT,
    SUCCESS, WARNING, ERROR,
    FONT_HEADLINE, FONT_BODY, FONT_MONO,
    FONT_SIZE_H2, FONT_SIZE_BODY, FONT_SIZE_CAPTION,
    RADIUS_MD,
)

from api.documents import BOX_DISPLAY_NAMES, BOX_COLORS


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


__all__ = [
    'DocumentHistoryPanel',
    'LoadingOverlay',
    'ProcessingProgressOverlay',
]
