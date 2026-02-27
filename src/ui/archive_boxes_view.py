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
    Qt, Signal, QMimeData, QTimer, QSize,
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
    Document, BoxStats, SearchResult,
    BOX_TYPES, BOX_TYPES_ADMIN, BOX_DISPLAY_NAMES, BOX_COLORS
)

# Boxen aus denen nach Download automatisch archiviert wird
# DEPRECATED: Verwende domain.archive.archive_rules.ARCHIVABLE_BOXES
from domain.archive.archive_rules import ARCHIVABLE_BOXES as _ARCHIVABLE_BOXES
ARCHIVABLE_BOXES = _ARCHIVABLE_BOXES

# Import der bestehenden Hilfsklassen aus archive_view
from ui.archive_view import (
    format_date_german, DocumentLoadWorker, UploadWorker, 
    AIRenameWorker, PDFViewerDialog, HAS_PDF_VIEW,
    SpreadsheetViewerDialog
)

# Worker-Klassen aus eigenem Modul
from ui.archive.workers import CacheDocumentLoadWorker


# ═══════════════════════════════════════════════════════════
# Physisch verschobene Klassen (Re-Imports fuer Backward-Kompatibilitaet)
# ═══════════════════════════════════════════════════════════
from ui.archive.widgets import DocumentHistoryPanel, LoadingOverlay, ProcessingProgressOverlay
from ui.archive.models import DocumentTableModel, DocumentSortFilterProxy, ColorBackgroundDelegate
from ui.archive.table import DraggableDocumentView
from ui.archive.search_widget import SearchResultCard, AtlasIndexWidget
from ui.archive.sidebar import BoxSidebar
from ui.archive.dialogs import SmartScanDialog as _SmartScanDialog




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
        # API-Zugriff nur ueber Presenter (Clean Architecture)
        
        # Presenter (Clean Architecture)
        from presenters.archive.archive_presenter import ArchivePresenter
        self._presenter = ArchivePresenter(api_client, auth_api=auth_api)
        self._presenter.set_view(self)
        
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
    
    @property
    def presenter(self):
        """Zugriff auf den ArchivePresenter (Clean Architecture)."""
        return self._presenter
    
    def _load_smartscan_status(self):
        """Laedt den SmartScan-Enabled-Status ueber den Presenter."""
        self._smartscan_enabled = self._presenter.load_smartscan_status()
    
    
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
        return self._presenter.get_blocking_operations()

    def closeEvent(self, event):
        """Wird aufgerufen wenn das Widget geschlossen wird."""
        # Historie-Timer stoppen
        if self._history_debounce_timer is not None:
            self._history_debounce_timer.stop()
        
        # ATLAS Index Widget bereinigen
        if hasattr(self, '_atlas_index_widget'):
            self._atlas_index_widget.cleanup()
        
        # Presenter bereinigt alle Worker
        if hasattr(self, '_presenter'):
            self._presenter.cleanup()
        
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
        self._atlas_index_widget = AtlasIndexWidget(self._presenter.repository)
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
        
        # SmartScan-Status nur alle 5 Minuten aktualisieren (statt bei jedem
        # 20-Sekunden-Refresh). _load_smartscan_status() ist ein SYNCHRONER
        # API-Call auf dem Main Thread - zu haeufig verursacht UI-Haenger.
        now = datetime.now()
        last_ss_check = getattr(self, '_last_smartscan_check', None)
        if last_ss_check is None or (now - last_ss_check).total_seconds() > 300:
            self._last_smartscan_check = now
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
        self._presenter.check_missing_ai_data(self._on_missing_ai_data_finished)
    
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
        
        self._presenter.load_avg_cost_stats(self._on_avg_cost_loaded)
    
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
        self._presenter.load_credits(self._on_credits_loaded)
    
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
            self._presenter.load_stats(self._on_stats_loaded, self._on_stats_error)
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
        # Stats-Cache invalidieren - wird beim naechsten Auto-Refresh erneuert.
        # KEIN get_stats(force_refresh=True) hier! Das wuerde einen synchronen
        # API-Call auf dem Main Thread machen und die UI blockieren.
        self._cache.invalidate_stats()
    
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
        self._presenter.register_worker(self._load_worker)
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
        counterpart = self._presenter.get_document(counterpart_id)
        if not counterpart:
            from ui.toast import ToastManager
            from i18n.de import DUPLICATE_COMPARE_NOT_FOUND
            toast = ToastManager.instance()
            if toast:
                toast.show_warning(DUPLICATE_COMPARE_NOT_FOUND)
            return
        from ui.archive_view import DuplicateCompareDialog
        dialog = DuplicateCompareDialog(
            doc, counterpart, self._presenter.get_docs_api_for_dialog(),
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
        
        self._presenter.load_document_history(
            doc.id, self._on_history_loaded, self._on_history_error,
        )
    
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
        
        self._presenter.set_document_color(
            doc_ids, color,
            finished_callback=self._on_color_finished,
            error_callback=self._on_color_error,
        )
    
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
        self._presenter.move_documents(
            doc_ids, target_box,
            processing_status=processing_status,
            finished_callback=lambda count: self._on_move_finished(count, target_name, len(documents)),
            error_callback=self._on_move_error,
        )
    
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
            self._last_archive_data = None
            
            documents = data['documents']
            action = data['action']
            
            if action == 'archive':
                self._presenter.unarchive_documents(documents)
            else:
                self._presenter.archive_documents(documents)
            
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
                self._presenter.move_documents_sync(ids, box_type)
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
        
        self._preview_worker = self._presenter.start_preview_download(
            doc.id, self._preview_cache_dir,
            filename=doc.original_filename,
            cache_dir=self._preview_cache_dir,
            finished_callback=self._on_preview_download_finished,
            error_callback=self._on_preview_download_error,
        )

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
                    docs_api=self._presenter.get_docs_api_for_dialog(),
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
        
        self._multi_upload_worker = self._presenter.start_multi_upload(
            file_paths, 'manual_upload',
            progress_callback=self._on_multi_upload_progress,
            file_finished_callback=self._on_file_uploaded,
            file_error_callback=self._on_file_upload_error,
            all_finished_callback=self._on_multi_upload_finished,
        )
    
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
        
        dl_result = self._presenter.download_and_archive(doc, target_dir)
        
        if dl_result.success:
            if dl_result.auto_archived:
                self._last_archive_data = {
                    'documents': [doc],
                    'action': 'archive',
                }
                self._cache.invalidate_documents()
                self._refresh_stats()
                self._refresh_documents(force_refresh=True)
                self._toast_manager.show_success(ARCHIVE_DOWNLOAD_NOTE, action_text=MOVE_UNDO, action_callback=self._on_toast_undo_clicked)
            else:
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
        self._download_worker = self._presenter.start_multi_download(
            selected_docs, target_dir,
            progress_callback=self._on_download_progress,
            file_finished_callback=self._on_file_downloaded,
            file_error_callback=self._on_file_download_error,
            all_finished_callback=self._on_multi_download_finished,
        )
    
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
        
        # DownloadDocument-UseCase archiviert bereits einzeln pro Datei.
        # Hier nur ermitteln wie viele archiviert wurden fuer Refresh + Toast.
        docs_map = getattr(self, '_download_documents_map', {})
        
        archivable_docs = []
        for doc_id in erfolgreiche_doc_ids:
            doc = docs_map.get(doc_id)
            if doc and doc.box_type in ARCHIVABLE_BOXES and not doc.is_archived:
                archivable_docs.append(doc)
        
        archived_count = len(archivable_docs)
        
        if archived_count > 0:
            self._cache.invalidate_documents()
            self._last_archive_data = {
                'documents': archivable_docs,
                'action': 'archive',
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
        self._box_download_worker = self._presenter.start_box_download(
            box_type, target_path, mode,
            progress_callback=self._on_box_download_progress,
            finished_callback=self._on_box_download_finished,
            status_callback=self._on_box_download_status,
            error_callback=self._on_box_download_error,
        )
    
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
            archived_count = self._presenter.archive_by_ids(erfolgreiche_doc_ids)
        
        if archived_count > 0:
            self._cache.invalidate_documents()
            
            self._last_archive_data = None
            
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
        """Schliesst Dokumente von der automatischen Verarbeitung aus."""
        from i18n.de import PROCESSING_EXCLUDED_TOAST, PROCESSING_EXCLUDED_MULTI
        
        if not documents:
            return
        
        result = self._presenter.exclude_from_processing(documents)
        
        if result.changed_count > 0:
            affected_boxes = set(d.box_type for d in documents)
            affected_boxes.add('sonstige')
            for box_type in affected_boxes:
                self._cache.invalidate_documents(box_type)
            self._refresh_stats()
            self._refresh_documents(force_refresh=True)
            
            if result.changed_count == 1:
                self._toast_manager.show_info(PROCESSING_EXCLUDED_TOAST)
            else:
                self._toast_manager.show_info(PROCESSING_EXCLUDED_MULTI.format(count=result.changed_count))
    
    def _include_for_processing(self, documents: List[Document]):
        """Gibt Dokumente erneut fuer die Verarbeitung frei (zurueck in Eingangsbox)."""
        from i18n.de import PROCESSING_INCLUDED_TOAST, PROCESSING_INCLUDED_MULTI
        
        if not documents:
            return
        
        result = self._presenter.include_for_processing(documents)
        
        if result.changed_count > 0:
            affected_boxes = set(d.box_type for d in documents)
            affected_boxes.add('eingang')
            for box_type in affected_boxes:
                self._cache.invalidate_documents(box_type)
            
            self._refresh_stats()
            self._refresh_documents(force_refresh=True)
            
            if result.changed_count == 1:
                self._toast_manager.show_success(PROCESSING_INCLUDED_TOAST)
            else:
                self._toast_manager.show_success(PROCESSING_INCLUDED_MULTI.format(count=result.changed_count))
    
    def _archive_documents(self, documents: List[Document]):
        """Archiviert die ausgewaehlten Dokumente (Bulk-API)."""
        from i18n.de import ARCHIVE_SUCCESS_SINGLE, ARCHIVE_SUCCESS_MULTI, MOVE_UNDO
        
        if not documents:
            return
        
        result = self._presenter.archive_documents(documents)
        
        if result.changed_count > 0:
            self._last_archive_data = {
                'documents': documents,
                'action': 'archive',
            }
            
            self._cache.invalidate_documents()
            self._refresh_stats()
            self._refresh_documents(force_refresh=True)
            
            if result.changed_count == 1:
                self._toast_manager.show_success(ARCHIVE_SUCCESS_SINGLE, action_text=MOVE_UNDO, action_callback=self._on_toast_undo_clicked)
            else:
                self._toast_manager.show_success(
                    ARCHIVE_SUCCESS_MULTI.format(count=result.changed_count),
                    action_text=MOVE_UNDO, action_callback=self._on_toast_undo_clicked
                )
    
    def _unarchive_documents(self, documents: List[Document]):
        """Entarchiviert die ausgewaehlten Dokumente (Bulk-API)."""
        from i18n.de import UNARCHIVE_SUCCESS_SINGLE, UNARCHIVE_SUCCESS_MULTI, MOVE_UNDO
        
        if not documents:
            return
        
        result = self._presenter.unarchive_documents(documents)
        
        if result.changed_count > 0:
            self._last_archive_data = {
                'documents': documents,
                'action': 'unarchive',
            }
            
            self._cache.invalidate_documents()
            self._refresh_stats()
            self._refresh_documents(force_refresh=True)
            
            if result.changed_count == 1:
                self._toast_manager.show_success(UNARCHIVE_SUCCESS_SINGLE, action_text=MOVE_UNDO, action_callback=self._on_toast_undo_clicked)
            else:
                self._toast_manager.show_success(
                    UNARCHIVE_SUCCESS_MULTI.format(count=result.changed_count),
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
            result = self._presenter.delete_document(doc)
            if result.deleted_count > 0:
                self._refresh_all()
            else:
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
            result = self._presenter.delete_documents(selected_docs)
            logger.info(f"Bulk-Delete: {result.deleted_count}/{result.total_requested} Dokument(e) geloescht")
            
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
        
        result = self._presenter.rename_document(doc, new_name_without_ext)
        
        if result.success:
            if result.excluded_from_processing:
                logger.info(
                    f"Dokument {doc.id} manuell umbenannt in Eingangsbox "
                    f"-> processing_status='manual_excluded'"
                )
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
        
        self._ai_rename_worker = self._presenter.start_ai_rename(
            documents,
            progress_callback=self._on_ai_progress,
            finished_callback=self._on_ai_finished,
            error_callback=self._on_ai_error,
        )
    
    def _cancel_ai_rename(self):
        """Bricht KI-Benennung ab."""
        self._presenter.cancel_ai_rename()
    
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
        
        self._processing_worker = self._presenter.start_processing(
            progress_callback=self._on_processing_progress,
            finished_callback=self._on_processing_finished,
            error_callback=self._on_processing_error,
        )
    
    def _cancel_processing(self):
        """Bricht Verarbeitung ab."""
        self._presenter.cancel_processing()
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
        
        history_entry_id = None
        if batch_result.total_documents > 0:
            try:
                history_entry_id = self._presenter.log_batch_complete(batch_result)
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
        
        self._delayed_cost_worker = self._presenter.start_delayed_cost_check(
            batch_result, history_entry_id,
            delay_seconds=delay_seconds,
            countdown_callback=self._on_cost_countdown,
            finished_callback=self._on_delayed_cost_finished,
        )
    
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
        
        settings = self._presenter.get_smartscan_settings()
        
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
        self._smartscan_worker = self._presenter.start_smartscan(
            mode, doc_ids,
            box_type=source_box,
            archive_after=archive,
            recolor_after=recolor,
            recolor_color=recolor_color,
            progress_callback=self._on_smartscan_progress,
            completed_callback=self._on_smartscan_finished,
            error_callback=self._on_smartscan_error,
        )
        
        self._show_loading(texts.SMARTSCAN_SENDING)
    
    def _on_smartscan_progress(self, current: int, total: int, status: str):
        """Fortschritt des SmartScan-Versands."""
        if hasattr(self, '_loading_overlay') and self._loading_overlay.isVisible():
            self._loading_overlay.set_status(status)
    
    def _cleanup_smartscan_worker(self):
        """Raeumt die View-seitige SmartScan-Referenz auf."""
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



