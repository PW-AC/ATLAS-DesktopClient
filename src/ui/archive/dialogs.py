"""
ACENCIA ATLAS - Archiv-Dialoge

Enthaelt SmartScanDialog und DuplicateCompareDialog.
"""

import os
import tempfile
import logging

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QCheckBox, QFormLayout, QFrame, QSplitter,
    QMenu, QMessageBox,
)
from ui.toast import ToastManager
from PySide6.QtCore import Qt, Signal, QTimer

from api.documents import Document

logger = logging.getLogger(__name__)

# PDF-Viewer: Versuche QPdfView zu importieren (Qt6 native PDF)
HAS_PDF_VIEW = False
try:
    from PySide6.QtPdfWidgets import QPdfView
    from PySide6.QtPdf import QPdfDocument
    HAS_PDF_VIEW = True
except ImportError:
    pass

from utils.date_utils import format_date_german


class SmartScanDialog(QDialog):
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


# Backward-Kompatibilitaet: alter Name
_SmartScanDialog = SmartScanDialog


class DuplicateCompareDialog(QDialog):
    """
    Dialog zum Side-by-Side-Vergleich zweier Duplikat-Dokumente.
    
    Zeigt beide Dokumente nebeneinander mit PDF-Vorschau und
    Aktions-Buttons (Loeschen, Archivieren, Verschieben, Farbe) pro Seite.
    """
    
    documents_changed = Signal()
    
    # Box-Emojis (gleich wie SearchResultCard)
    _BOX_EMOJIS = {
        'gdv': '\U0001f4ca', 'courtage': '\U0001f4b0', 'sach': '\U0001f3e0',
        'leben': '\u2764\ufe0f', 'kranken': '\U0001f3e5', 'sonstige': '\U0001f4c1',
        'roh': '\U0001f4e6', 'eingang': '\U0001f4ec', 'verarbeitung': '\U0001f4e5',
        'falsch': '\u26a0\ufe0f'
    }
    
    # Archivierbare Boxen
    _ARCHIVABLE_BOXES = {'gdv', 'courtage', 'sach', 'leben', 'kranken', 'sonstige'}
    
    def __init__(self, doc_left: Document, doc_right: Document,
                 docs_api: 'DocumentsAPI', preview_cache_dir: str = None, parent=None):
        super().__init__(parent)
        self._doc_left = doc_left
        self._doc_right = doc_right
        self._docs_api = docs_api
        self._preview_cache_dir = preview_cache_dir or os.path.join(
            tempfile.gettempdir(), 'bipro_preview_cache')
        self._has_changes = False
        self._left_disabled = False
        self._right_disabled = False
        self._workers = []
        
        # PDF-Dokument-Objekte fuer QPdfView
        self._pdf_doc_left = None
        self._pdf_doc_right = None
        
        # Direkte Widget-Referenzen (statt findChild)
        self._pdf_views = {}      # side -> QPdfView
        self._loading_labels = {} # side -> QLabel
        
        from i18n.de import DUPLICATE_COMPARE_TITLE
        self.setWindowTitle(DUPLICATE_COMPARE_TITLE)
        self.setMinimumSize(1200, 700)
        self.resize(1400, 900)
        
        self._setup_ui()
        # Previews erst nach show() starten (QPdfView braucht sichtbares Fenster)
        QTimer.singleShot(100, self._download_previews)
    
    def _setup_ui(self):
        """Baut das Dialog-Layout auf."""
        from i18n.de import DUPLICATE_COMPARE_CLOSE
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Splitter fuer Links/Rechts
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(2)
        
        # Bestimme Labels: Welches ist das "Original"?
        if self._doc_left.is_duplicate:
            left_label_key = 'this'
            right_label_key = 'original'
        elif self._doc_left.is_content_duplicate:
            left_label_key = 'this'
            right_label_key = 'original'
        else:
            left_label_key = 'original'
            right_label_key = 'copy'
        
        # Linke Seite
        self._left_pane = self._build_document_pane(
            self._doc_left, 'left', left_label_key)
        splitter.addWidget(self._left_pane)
        
        # Rechte Seite
        self._right_pane = self._build_document_pane(
            self._doc_right, 'right', right_label_key)
        splitter.addWidget(self._right_pane)
        
        splitter.setSizes([700, 700])
        main_layout.addWidget(splitter, 1)
        
        # Footer mit Schliessen-Button
        footer = QFrame()
        footer.setStyleSheet("QFrame { background: #f5f5f5; border-top: 1px solid #e0e0e0; }")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(16, 8, 16, 8)
        
        footer_layout.addStretch()
        close_btn = QPushButton(DUPLICATE_COMPARE_CLOSE)
        close_btn.setFixedWidth(140)
        close_btn.setStyleSheet("""
            QPushButton {
                background: #001f3d; color: white; border: none;
                padding: 8px 16px; border-radius: 4px; font-weight: bold;
            }
            QPushButton:hover { background: #002d5c; }
        """)
        close_btn.clicked.connect(self.close)
        footer_layout.addWidget(close_btn)
        footer_layout.addStretch()
        
        main_layout.addWidget(footer)
    
    def _build_document_pane(self, doc: Document, side: str, label_key: str) -> QFrame:
        """Erstellt eine Seite des Vergleichs (Header + Preview + Aktionen)."""
        from i18n.de import (
            DUPLICATE_COMPARE_THIS_DOC, DUPLICATE_COMPARE_COUNTERPART,
            DUPLICATE_COMPARE_COUNTERPART_OF_COPY, DUPLICATE_COMPARE_NO_PREVIEW,
            DUPLICATE_COMPARE_LOADING, DUPLICATE_COMPARE_ACTION_DELETE,
            DUPLICATE_COMPARE_ACTION_ARCHIVE, DUPLICATE_COMPARE_ACTION_UNARCHIVE,
            DUPLICATE_COMPARE_ACTION_MOVE, DUPLICATE_COMPARE_ACTION_COLOR,
            DUPLICATE_TOOLTIP_ARCHIVED
        )
        from api.documents import BOX_DISPLAY_NAMES
        from html import escape
        
        pane = QFrame()
        pane.setObjectName(f"pane_{side}")
        border_color = "#fa9939" if side == 'left' else "#3b82f6"
        pane.setStyleSheet(f"""
            QFrame#{pane.objectName()} {{
                background: white;
                border-top: 3px solid {border_color};
            }}
        """)
        
        layout = QVBoxLayout(pane)
        layout.setContentsMargins(12, 12, 12, 8)
        layout.setSpacing(6)
        
        # --- Header ---
        if label_key == 'this':
            section_label = DUPLICATE_COMPARE_THIS_DOC
        elif label_key == 'original':
            section_label = DUPLICATE_COMPARE_COUNTERPART
        else:
            section_label = DUPLICATE_COMPARE_COUNTERPART_OF_COPY
        
        header_label = QLabel(section_label)
        header_label.setStyleSheet(
            "font-size: 11px; color: #9E9E9E; font-weight: bold; text-transform: uppercase;")
        layout.addWidget(header_label)
        
        # Dateiname
        name_label = QLabel(escape(doc.original_filename))
        name_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #001f3d;")
        name_label.setWordWrap(True)
        layout.addWidget(name_label)
        
        # Meta-Zeile: Box | Datum | Groesse | ggf. Archiviert
        box_emoji = self._BOX_EMOJIS.get(doc.box_type, '\U0001f4c1')
        box_name = BOX_DISPLAY_NAMES.get(doc.box_type, doc.box_type or '')
        date_display = format_date_german(doc.created_at)
        
        meta_parts = [f"{box_emoji} {escape(box_name)}"]
        if date_display:
            meta_parts.append(date_display)
        if doc.file_size:
            size_kb = doc.file_size / 1024
            if size_kb >= 1024:
                meta_parts.append(f"{size_kb / 1024:.1f} MB")
            else:
                meta_parts.append(f"{size_kb:.0f} KB")
        if doc.is_archived:
            meta_parts.append(f"\U0001f4e6 {DUPLICATE_TOOLTIP_ARCHIVED}")
        
        meta_label = QLabel(" | ".join(meta_parts))
        meta_label.setStyleSheet("font-size: 11px; color: #757575;")
        layout.addWidget(meta_label)
        
        # ID
        id_label = QLabel(f"ID: {doc.id}")
        id_label.setStyleSheet("font-size: 10px; color: #BDBDBD;")
        layout.addWidget(id_label)
        
        # --- Vorschau-Bereich ---
        preview_container = QFrame()
        preview_container.setStyleSheet(
            "QFrame { background: #fafafa; border: 1px solid #e0e0e0; border-radius: 4px; }")
        preview_layout = QVBoxLayout(preview_container)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        
        if self._is_pdf(doc) and HAS_PDF_VIEW:
            # Stacked: Loading-Label wird durch QPdfView ersetzt
            from PySide6.QtWidgets import QStackedWidget
            stack = QStackedWidget()
            
            # Seite 0: Loading
            loading_label = QLabel(DUPLICATE_COMPARE_LOADING)
            loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            loading_label.setStyleSheet("color: #9E9E9E; font-size: 12px; padding: 40px;")
            stack.addWidget(loading_label)
            
            # Seite 1: QPdfView (sichtbar und gelayoutet von Anfang an)
            pdf_view = QPdfView(stack)
            pdf_view.setPageMode(QPdfView.PageMode.MultiPage)
            pdf_view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
            stack.addWidget(pdf_view)
            
            # Loading-Seite zuerst anzeigen
            stack.setCurrentIndex(0)
            preview_layout.addWidget(stack)
            
            # Direkte Referenzen speichern
            self._pdf_views[side] = pdf_view
            self._loading_labels[side] = stack  # Stack statt Label, um umzuschalten
        else:
            # Kein PDF oder kein QPdfView
            no_preview = QLabel(DUPLICATE_COMPARE_NO_PREVIEW)
            no_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
            no_preview.setStyleSheet(
                "color: #9E9E9E; font-size: 13px; padding: 60px; font-style: italic;")
            preview_layout.addWidget(no_preview)
        
        layout.addWidget(preview_container, 1)
        
        # --- Status-Overlay (zunachst versteckt) ---
        status_label = QLabel("")
        status_label.setObjectName(f"status_{side}")
        status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_label.setStyleSheet("""
            font-size: 14px; font-weight: bold; color: #ef4444;
            padding: 8px; background: #fff5f5; border: 1px solid #fecaca;
            border-radius: 4px;
        """)
        status_label.setVisible(False)
        layout.addWidget(status_label)
        
        # --- Aktions-Buttons ---
        actions_frame = QFrame()
        actions_frame.setObjectName(f"actions_{side}")
        actions_layout = QHBoxLayout(actions_frame)
        actions_layout.setContentsMargins(0, 4, 0, 0)
        actions_layout.setSpacing(6)
        
        # Loeschen
        delete_btn = QPushButton(DUPLICATE_COMPARE_ACTION_DELETE)
        delete_btn.setStyleSheet("""
            QPushButton {
                background: #fee2e2; color: #991b1b; border: 1px solid #fecaca;
                padding: 6px 12px; border-radius: 3px; font-size: 11px;
            }
            QPushButton:hover { background: #fecaca; }
            QPushButton:disabled { background: #f5f5f5; color: #ccc; border: 1px solid #e0e0e0; }
        """)
        delete_btn.clicked.connect(lambda: self._delete_document(side))
        actions_layout.addWidget(delete_btn)
        
        # Archivieren / Entarchivieren
        if doc.box_type in self._ARCHIVABLE_BOXES:
            if doc.is_archived:
                archive_btn = QPushButton(DUPLICATE_COMPARE_ACTION_UNARCHIVE)
                archive_btn.clicked.connect(lambda: self._unarchive_document(side))
            else:
                archive_btn = QPushButton(DUPLICATE_COMPARE_ACTION_ARCHIVE)
                archive_btn.clicked.connect(lambda: self._archive_document(side))
            archive_btn.setStyleSheet("""
                QPushButton {
                    background: #fef3c7; color: #92400e; border: 1px solid #fde68a;
                    padding: 6px 12px; border-radius: 3px; font-size: 11px;
                }
                QPushButton:hover { background: #fde68a; }
                QPushButton:disabled { background: #f5f5f5; color: #ccc; border: 1px solid #e0e0e0; }
            """)
            actions_layout.addWidget(archive_btn)
        
        # Verschieben (mit Dropdown-Menue)
        move_btn = QPushButton(DUPLICATE_COMPARE_ACTION_MOVE)
        move_btn.setStyleSheet("""
            QPushButton {
                background: #e0f2fe; color: #075985; border: 1px solid #bae6fd;
                padding: 6px 12px; border-radius: 3px; font-size: 11px;
            }
            QPushButton:hover { background: #bae6fd; }
            QPushButton::menu-indicator { subcontrol-position: right center; }
            QPushButton:disabled { background: #f5f5f5; color: #ccc; border: 1px solid #e0e0e0; }
        """)
        move_menu = QMenu(move_btn)
        move_targets = ['gdv', 'courtage', 'sach', 'leben', 'kranken', 'sonstige', 'eingang', 'roh']
        for box_type in move_targets:
            if box_type == doc.box_type:
                continue  # Aktuelle Box ueberspringen
            emoji = self._BOX_EMOJIS.get(box_type, '\U0001f4c1')
            display = BOX_DISPLAY_NAMES.get(box_type, box_type)
            action = move_menu.addAction(f"{emoji} {display}")
            action.triggered.connect(
                lambda checked, bt=box_type, s=side: self._move_document(s, bt))
        move_btn.setMenu(move_menu)
        actions_layout.addWidget(move_btn)
        
        # Farbe (mit Dropdown-Menue)
        color_btn = QPushButton(DUPLICATE_COMPARE_ACTION_COLOR)
        color_btn.setStyleSheet("""
            QPushButton {
                background: #f3e8ff; color: #6b21a8; border: 1px solid #e9d5ff;
                padding: 6px 12px; border-radius: 3px; font-size: 11px;
            }
            QPushButton:hover { background: #e9d5ff; }
            QPushButton::menu-indicator { subcontrol-position: right center; }
            QPushButton:disabled { background: #f5f5f5; color: #ccc; border: 1px solid #e0e0e0; }
        """)
        from ui.styles.tokens import DOCUMENT_DISPLAY_COLORS
        from i18n.de import (DOC_COLOR_GREEN, DOC_COLOR_RED, DOC_COLOR_BLUE,
                              DOC_COLOR_ORANGE, DOC_COLOR_PURPLE, DOC_COLOR_PINK,
                              DOC_COLOR_CYAN, DOC_COLOR_YELLOW, DOC_COLOR_REMOVE)
        color_labels = {
            'green': DOC_COLOR_GREEN, 'red': DOC_COLOR_RED, 'blue': DOC_COLOR_BLUE,
            'orange': DOC_COLOR_ORANGE, 'purple': DOC_COLOR_PURPLE, 'pink': DOC_COLOR_PINK,
            'cyan': DOC_COLOR_CYAN, 'yellow': DOC_COLOR_YELLOW,
        }
        color_menu = QMenu(color_btn)
        for color_key, color_label in color_labels.items():
            hex_color = DOCUMENT_DISPLAY_COLORS.get(color_key, '#ccc')
            action = color_menu.addAction(f"\u25cf {color_label}")
            action.triggered.connect(
                lambda checked, ck=color_key, s=side: self._color_document(s, ck))
        color_menu.addSeparator()
        remove_action = color_menu.addAction(DOC_COLOR_REMOVE)
        remove_action.triggered.connect(lambda: self._color_document(side, None))
        color_btn.setMenu(color_menu)
        actions_layout.addWidget(color_btn)
        
        actions_layout.addStretch()
        layout.addWidget(actions_frame)
        
        return pane
    
    def _is_pdf(self, doc: Document) -> bool:
        """Prueft ob ein Dokument ein PDF ist."""
        if doc.mime_type and 'pdf' in doc.mime_type.lower():
            return True
        name = (doc.original_filename or '').lower()
        return name.endswith('.pdf')
    
    def _download_previews(self):
        """Startet den Download beider PDF-Vorschauen parallel."""
        os.makedirs(self._preview_cache_dir, exist_ok=True)
        
        for side, doc in [('left', self._doc_left), ('right', self._doc_right)]:
            if not self._is_pdf(doc) or not HAS_PDF_VIEW:
                continue
            
            # Cache-Check (sanitisierter Dateiname fuer Windows-Kompatibilitaet)
            from api.documents import safe_cache_filename
            cached = os.path.join(self._preview_cache_dir,
                                  safe_cache_filename(doc.id, doc.original_filename))
            if os.path.exists(cached) and os.path.getsize(cached) > 0:
                self._on_preview_ready(side, cached)
                continue
            
            # Download starten
            from ui.archive.workers import PreviewDownloadWorker
            worker = PreviewDownloadWorker(
                self._docs_api, doc.id, self._preview_cache_dir,
                filename=doc.original_filename,
                cache_dir=self._preview_cache_dir)
            worker.download_finished.connect(
                lambda path, s=side: self._on_preview_ready(s, path))
            worker.download_error.connect(
                lambda err, s=side: self._on_preview_error(s, err))
            self._workers.append(worker)
            worker.start()
    
    def _on_preview_ready(self, side: str, path):
        """Callback wenn PDF-Download fertig ist."""
        if not path or not os.path.exists(path):
            self._on_preview_error(side, "Datei nicht gefunden")
            return
        
        pdf_view = self._pdf_views.get(side)
        stack = self._loading_labels.get(side)
        
        if pdf_view:
            pdf_doc = QPdfDocument(self)
            
            # QPdfDocument.load() kann fehlschlagen bei Sonderzeichen im Pfad.
            # Wir pruefen den Status und laden ggf. von QBuffer als Fallback.
            load_error = pdf_doc.load(path)
            
            # Status pruefen (Error = 2 in QPdfDocument.Error enum)
            if pdf_doc.status() == QPdfDocument.Status.Error:
                logger.warning(f"QPdfDocument.load() fehlgeschlagen fuer {path}, versuche QBuffer-Fallback")
                try:
                    from PySide6.QtCore import QBuffer, QByteArray
                    with open(path, 'rb') as f:
                        data = f.read()
                    # Neues QPdfDocument fuer Buffer-Modus
                    pdf_doc = QPdfDocument(self)
                    self._pdf_buffer = QBuffer(self)  # Buffer muss am Leben bleiben
                    self._pdf_buffer.setData(QByteArray(data))
                    self._pdf_buffer.open(QBuffer.OpenModeFlag.ReadOnly)
                    pdf_doc.load(self._pdf_buffer)
                except Exception as e:
                    logger.error(f"QBuffer-Fallback fehlgeschlagen ({side}): {e}")
                    self._on_preview_error(side, str(e))
                    return
            
            pdf_view.setDocument(pdf_doc)
            
            # Stack auf QPdfView-Seite (Index 1) umschalten
            if stack:
                stack.setCurrentIndex(1)
            
            if side == 'left':
                self._pdf_doc_left = pdf_doc
            else:
                self._pdf_doc_right = pdf_doc
            
            logger.info(f"PDF-Vorschau geladen ({side}): {path}")
    
    def _on_preview_error(self, side: str, error: str):
        """Callback bei Download-Fehler."""
        stack = self._loading_labels.get(side)
        if stack:
            # Loading-Label (Index 0) mit Fehlermeldung aktualisieren
            loading = stack.widget(0)
            if loading:
                from i18n.de import DUPLICATE_COMPARE_NO_PREVIEW
                loading.setText(DUPLICATE_COMPARE_NO_PREVIEW)
                loading.setStyleSheet(
                    "color: #ef4444; font-size: 12px; padding: 40px; font-style: italic;")
        logger.warning(f"PDF-Vorschau Fehler ({side}): {error}")
    
    def _get_doc(self, side: str) -> Document:
        """Gibt das Dokument fuer die angegebene Seite zurueck."""
        return self._doc_left if side == 'left' else self._doc_right
    
    def _is_side_disabled(self, side: str) -> bool:
        """Prueft ob eine Seite bereits deaktiviert ist."""
        return self._left_disabled if side == 'left' else self._right_disabled
    
    def _mark_pane_modified(self, side: str, status_text: str):
        """Markiert eine Seite als modifiziert (deaktiviert Buttons, zeigt Status)."""
        pane = self._left_pane if side == 'left' else self._right_pane
        
        # Status-Label anzeigen
        status = pane.findChild(QLabel, f"status_{side}")
        if status:
            status.setText(status_text)
            status.setVisible(True)
        
        # Aktions-Buttons deaktivieren
        actions = pane.findChild(QFrame, f"actions_{side}")
        if actions:
            for btn in actions.findChildren(QPushButton):
                btn.setEnabled(False)
        
        # Seite als deaktiviert markieren
        if side == 'left':
            self._left_disabled = True
        else:
            self._right_disabled = True
        
        self._has_changes = True
    
    def _delete_document(self, side: str):
        """Loescht das Dokument auf der angegebenen Seite."""
        if self._is_side_disabled(side):
            return
        
        doc = self._get_doc(side)
        from i18n.de import DUPLICATE_COMPARE_CONFIRM_DELETE, DUPLICATE_COMPARE_DELETED
        
        reply = QMessageBox.question(
            self, DUPLICATE_COMPARE_DELETED,
            DUPLICATE_COMPARE_CONFIRM_DELETE.format(filename=doc.original_filename),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        try:
            self._docs_api.delete(doc.id)
            self._mark_pane_modified(side, f"\u274c {DUPLICATE_COMPARE_DELETED}")
        except Exception as e:
            from i18n.de import DUPLICATE_COMPARE_ERROR
            ToastManager.instance().show_error(
                DUPLICATE_COMPARE_ERROR.format(error=str(e)))
    
    def _archive_document(self, side: str):
        """Archiviert das Dokument."""
        if self._is_side_disabled(side):
            return
        doc = self._get_doc(side)
        try:
            self._docs_api.archive_documents([doc.id])
            from i18n.de import DUPLICATE_COMPARE_ARCHIVED
            self._mark_pane_modified(side, f"\U0001f4e6 {DUPLICATE_COMPARE_ARCHIVED}")
        except Exception as e:
            from i18n.de import DUPLICATE_COMPARE_ERROR
            ToastManager.instance().show_error(
                DUPLICATE_COMPARE_ERROR.format(error=str(e)))
    
    def _unarchive_document(self, side: str):
        """Entarchiviert das Dokument."""
        if self._is_side_disabled(side):
            return
        doc = self._get_doc(side)
        try:
            self._docs_api.unarchive_documents([doc.id])
            from i18n.de import DUPLICATE_COMPARE_UNARCHIVED
            self._mark_pane_modified(side, f"\U0001f4e4 {DUPLICATE_COMPARE_UNARCHIVED}")
        except Exception as e:
            from i18n.de import DUPLICATE_COMPARE_ERROR
            ToastManager.instance().show_error(
                DUPLICATE_COMPARE_ERROR.format(error=str(e)))
    
    def _move_document(self, side: str, target_box: str):
        """Verschiebt das Dokument in eine andere Box."""
        if self._is_side_disabled(side):
            return
        doc = self._get_doc(side)
        try:
            self._docs_api.move_documents([doc.id], target_box)
            from i18n.de import DUPLICATE_COMPARE_MOVED
            from api.documents import BOX_DISPLAY_NAMES
            box_name = BOX_DISPLAY_NAMES.get(target_box, target_box)
            emoji = self._BOX_EMOJIS.get(target_box, '\U0001f4c1')
            self._mark_pane_modified(
                side, f"{emoji} {DUPLICATE_COMPARE_MOVED.format(box=box_name)}")
        except Exception as e:
            from i18n.de import DUPLICATE_COMPARE_ERROR
            ToastManager.instance().show_error(
                DUPLICATE_COMPARE_ERROR.format(error=str(e)))
    
    def _color_document(self, side: str, color_key):
        """Setzt die Farbmarkierung des Dokuments."""
        if self._is_side_disabled(side):
            return
        doc = self._get_doc(side)
        try:
            self._docs_api.set_documents_color([doc.id], color_key)
            from i18n.de import DUPLICATE_COMPARE_COLORED, DUPLICATE_COMPARE_COLOR_REMOVED
            if color_key:
                self._mark_pane_modified(side, f"\U0001f3a8 {DUPLICATE_COMPARE_COLORED}")
            else:
                self._mark_pane_modified(side, DUPLICATE_COMPARE_COLOR_REMOVED)
        except Exception as e:
            from i18n.de import DUPLICATE_COMPARE_ERROR
            ToastManager.instance().show_error(
                DUPLICATE_COMPARE_ERROR.format(error=str(e)))
    
    def closeEvent(self, event):
        """Beim Schliessen: Worker stoppen und ggf. Signal senden."""
        for worker in self._workers:
            if worker.isRunning():
                worker.cancel()
                worker.wait(1000)
        
        # PDF-Dokumente freigeben
        if self._pdf_doc_left:
            self._pdf_doc_left.close()
        if self._pdf_doc_right:
            self._pdf_doc_right.close()
        
        if self._has_changes:
            self.documents_changed.emit()
        
        super().closeEvent(event)


__all__ = [
    'SmartScanDialog',
    '_SmartScanDialog',
    'DuplicateCompareDialog',
]
