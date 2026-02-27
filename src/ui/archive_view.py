"""
ACENCIA ATLAS - Dokumentenarchiv

Ansicht fuer alle Dokumente mit Upload/Download-Funktionen, PDF-Vorschau
und KI-basierter automatischer Benennung.
"""

from typing import Optional, List, Tuple
from datetime import datetime
import tempfile
import os
import logging

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QLabel, QComboBox, QLineEdit,
    QFileDialog, QMessageBox, QMenu, QProgressDialog, QFrame,
    QSplitter, QGroupBox, QFormLayout, QDialog, QToolBar, QApplication
)
from PySide6.QtCore import Qt, Signal, QThread, QUrl, QTimer
from PySide6.QtGui import QAction, QFont, QColor

logger = logging.getLogger(__name__)

# PDF-Viewer: Versuche QPdfView zu importieren (Qt6 native PDF)
HAS_PDF_VIEW = False
HAS_WEBENGINE = False

try:
    from PySide6.QtPdfWidgets import QPdfView
    from PySide6.QtPdf import QPdfDocument
    HAS_PDF_VIEW = True
except ImportError:
    pass

# Fallback: QWebEngineView (braucht PDF.js workaround)
if not HAS_PDF_VIEW:
    try:
        from PySide6.QtWebEngineWidgets import QWebEngineView
        HAS_WEBENGINE = True
    except ImportError:
        pass

from api.client import APIClient
from api.documents import DocumentsAPI, Document


# ═══════════════════════════════════════════════════════════
# Re-Exports: Verschobene Klassen (Backward-Kompatibilitaet)
# ═══════════════════════════════════════════════════════════
from utils.date_utils import format_date_german
from ui.viewers.pdf_viewer import (
    PDFViewerDialog, HAS_PDF_VIEW, _ThumbnailWorker,
    PDFSaveWorker, PDFRefreshWorker,
)
from ui.viewers.spreadsheet_viewer import SpreadsheetViewerDialog
from ui.archive.dialogs import DuplicateCompareDialog

# Legacy-Worker: bleiben hier definiert fuer Backward-Kompatibilitaet
# DocumentLoadWorker, UploadWorker, AIRenameWorker


class DocumentLoadWorker(QThread):
    """Worker zum Laden der Dokumente."""
    finished = Signal(list)
    error = Signal(str)
    
    def __init__(self, docs_api: DocumentsAPI, filters: dict):
        super().__init__()
        self.docs_api = docs_api
        self.filters = filters
    
    def run(self):
        try:
            docs = self.docs_api.list_documents(**self.filters)
            self.finished.emit(docs)
        except Exception as e:
            self.error.emit(str(e))


class UploadWorker(QThread):
    """Worker zum Hochladen von Dateien."""
    finished = Signal(object)  # Document or None
    error = Signal(str)
    progress = Signal(str)
    
    def __init__(self, docs_api: DocumentsAPI, file_path: str, source_type: str):
        super().__init__()
        self.docs_api = docs_api
        self.file_path = file_path
        self.source_type = source_type
    
    def run(self):
        try:
            self.progress.emit("Lade hoch...")
            doc = self.docs_api.upload(self.file_path, self.source_type)
            self.finished.emit(doc)
        except Exception as e:
            self.error.emit(str(e))


# AIRenameWorker: Verschoben nach infrastructure/threading/archive_workers.py
# Re-Export fuer Backward-Kompatibilitaet
from infrastructure.threading.archive_workers import AIRenameWorker




class ArchiveView(QWidget):
    """
    Dokumentenarchiv-Ansicht.
    
    Zeigt alle Dokumente vom Server mit Filter- und Such-Funktionen.
    """
    
    # Signal wenn ein GDV-Dokument geöffnet werden soll
    open_gdv_requested = Signal(int, str)  # doc_id, original_filename
    
    def __init__(self, api_client: APIClient, parent=None):
        super().__init__(parent)
        
        self.api_client = api_client
        self.docs_api = DocumentsAPI(api_client)
        from infrastructure.archive.document_repository import DocumentRepository
        self._repo = DocumentRepository(api_client)
        
        self._documents: List[Document] = []
        self._load_worker = None
        self._upload_worker = None
        self._ai_rename_worker = None
        self._toast_manager = None
        
        self._setup_ui()
        self.refresh_documents()
    
    def _toast(self, method: str, message: str) -> None:
        """Sichere Toast-Ausgabe (kein Crash falls kein ToastManager gesetzt)."""
        if self._toast_manager:
            getattr(self._toast_manager, method)(message)
        else:
            logger.warning(f"Toast ({method}): {message}")
    
    def _setup_ui(self):
        """UI aufbauen."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # Header
        header_layout = QHBoxLayout()
        
        title = QLabel("Dokumentenarchiv")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        header_layout.addWidget(title)
        
        header_layout.addStretch()
        
        # Refresh-Button
        refresh_btn = QPushButton("🔄 Aktualisieren")
        refresh_btn.clicked.connect(self.refresh_documents)
        header_layout.addWidget(refresh_btn)
        
        # Vorschau-Button
        self.preview_btn = QPushButton("👁️ Vorschau")
        self.preview_btn.setToolTip("PDF-Vorschau (Doppelklick auf PDF)")
        self.preview_btn.clicked.connect(self._preview_selected)
        header_layout.addWidget(self.preview_btn)
        
        # Download-Button fuer Mehrfachauswahl
        self.download_selected_btn = QPushButton("Ausgewaehlte herunterladen")
        self.download_selected_btn.clicked.connect(self._download_selected)
        header_layout.addWidget(self.download_selected_btn)
        
        # KI-Benennung Button
        self.ai_rename_btn = QPushButton("KI-Benennung")
        self.ai_rename_btn.setToolTip(
            "PDFs automatisch durch KI umbenennen.\n"
            "Extrahiert Versicherer, Typ und Datum."
        )
        self.ai_rename_btn.clicked.connect(self._ai_rename_selected)
        header_layout.addWidget(self.ai_rename_btn)
        
        # Upload-Button
        upload_btn = QPushButton("Hochladen")
        upload_btn.clicked.connect(self._upload_document)
        header_layout.addWidget(upload_btn)
        
        layout.addLayout(header_layout)
        
        # Filter-Bereich
        filter_group = QGroupBox("Filter")
        filter_layout = QHBoxLayout(filter_group)
        
        # Quelle-Filter
        filter_layout.addWidget(QLabel("Quelle:"))
        self.source_filter = QComboBox()
        self.source_filter.addItem("Alle", "")
        self.source_filter.addItem("BiPRO (automatisch)", "bipro_auto")
        self.source_filter.addItem("Manuell hochgeladen", "manual_upload")
        self.source_filter.addItem("Selbst erstellt", "self_created")
        self.source_filter.addItem("Scan", "scan")
        self.source_filter.currentIndexChanged.connect(self._apply_filter)
        filter_layout.addWidget(self.source_filter)
        
        # GDV-Filter
        filter_layout.addWidget(QLabel("Typ:"))
        self.type_filter = QComboBox()
        self.type_filter.addItem("Alle", "")
        self.type_filter.addItem("Nur GDV-Dateien", "gdv")
        self.type_filter.currentIndexChanged.connect(self._apply_filter)
        filter_layout.addWidget(self.type_filter)
        
        # Suche
        filter_layout.addWidget(QLabel("Suche:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Dateiname...")
        self.search_input.textChanged.connect(self._filter_table)
        filter_layout.addWidget(self.search_input)
        
        filter_layout.addStretch()
        
        layout.addWidget(filter_group)
        
        # Dokumenten-Tabelle
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "ID", "Dateiname", "Quelle", "GDV", "KI", "Groesse", "Hochgeladen", "Von"
        ])
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)
        
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)  # Mehrfachauswahl mit Ctrl/Shift
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        self.table.doubleClicked.connect(self._on_double_click)
        
        layout.addWidget(self.table)
        
        # Status-Zeile
        self.status_label = QLabel("Lade Dokumente...")
        self.status_label.setStyleSheet("color: gray;")
        layout.addWidget(self.status_label)
    
    def refresh_documents(self):
        """Dokumente vom Server laden."""
        self.status_label.setText("Lade Dokumente...")
        self.table.setEnabled(False)
        
        filters = {}
        
        # Quelle-Filter
        source = self.source_filter.currentData()
        if source:
            filters['source'] = source
        
        # Typ-Filter
        type_filter = self.type_filter.currentData()
        if type_filter == 'gdv':
            filters['is_gdv'] = True
        
        self._load_worker = DocumentLoadWorker(self.docs_api, filters)
        self._load_worker.finished.connect(self._on_documents_loaded)
        self._load_worker.error.connect(self._on_load_error)
        self._load_worker.start()
    
    def _on_documents_loaded(self, documents: List[Document]):
        """Callback wenn Dokumente geladen wurden."""
        self._documents = documents
        self._populate_table()
        self.table.setEnabled(True)
        self.status_label.setText(f"{len(documents)} Dokument(e) gefunden")
    
    def _on_load_error(self, error: str):
        """Callback bei Ladefehler."""
        self.table.setEnabled(True)
        self.status_label.setText(f"Fehler: {error}")
        self._toast("show_error", f"Dokumente konnten nicht geladen werden:\n{error}")
    
    def _populate_table(self):
        """Tabelle mit Dokumenten füllen."""
        self.table.setRowCount(len(self._documents))
        
        for row, doc in enumerate(self._documents):
            # ID
            id_item = QTableWidgetItem(str(doc.id))
            id_item.setData(Qt.ItemDataRole.UserRole, doc)
            self.table.setItem(row, 0, id_item)
            
            # Dateiname
            name_item = QTableWidgetItem(doc.original_filename)
            self.table.setItem(row, 1, name_item)
            
            # Quelle
            source_item = QTableWidgetItem(doc.source_type_display)
            if doc.source_type == 'bipro_auto':
                source_item.setForeground(QColor("#2196F3"))
            elif doc.source_type == 'self_created':
                source_item.setForeground(QColor("#4CAF50"))
            elif doc.source_type == 'scan':
                source_item.setForeground(QColor("#9C27B0"))  # Lila fuer Scan
            self.table.setItem(row, 2, source_item)
            
            # GDV
            gdv_item = QTableWidgetItem("Ja" if doc.is_gdv else "")
            if doc.is_gdv:
                gdv_item.setForeground(QColor("#4CAF50"))
            self.table.setItem(row, 3, gdv_item)
            
            # KI-Benennung Status
            if doc.ai_renamed:
                ai_item = QTableWidgetItem("Ja")
                ai_item.setForeground(QColor("#9C27B0"))  # Lila fuer KI
                ai_item.setToolTip("Durch KI umbenannt")
            elif doc.ai_processing_error:
                ai_item = QTableWidgetItem("Fehler")
                ai_item.setForeground(QColor("#F44336"))  # Rot fuer Fehler
                ai_item.setToolTip(f"Fehler: {doc.ai_processing_error}")
            elif doc.is_pdf:
                ai_item = QTableWidgetItem("-")
                ai_item.setToolTip("Noch nicht durch KI verarbeitet")
            else:
                ai_item = QTableWidgetItem("")
                ai_item.setToolTip("Keine PDF-Datei")
            self.table.setItem(row, 4, ai_item)
            
            # Groesse
            size_item = QTableWidgetItem(doc.file_size_display)
            size_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row, 5, size_item)
            
            # Datum im deutschen Format
            date_item = QTableWidgetItem(format_date_german(doc.created_at))
            date_item.setToolTip(doc.created_at or "")  # Original als Tooltip
            self.table.setItem(row, 6, date_item)
            
            # Hochgeladen von
            by_item = QTableWidgetItem(doc.uploaded_by_name or "")
            self.table.setItem(row, 7, by_item)
    
    def _filter_table(self):
        """Tabelle nach Suchbegriff filtern."""
        search_text = self.search_input.text().lower()
        
        for row in range(self.table.rowCount()):
            filename_item = self.table.item(row, 1)
            if filename_item:
                matches = search_text in filename_item.text().lower()
                self.table.setRowHidden(row, not matches)
    
    def _apply_filter(self):
        """Filter anwenden und neu laden."""
        self.refresh_documents()
    
    def _show_context_menu(self, position):
        """Kontextmenü für Tabellenzeilen."""
        item = self.table.itemAt(position)
        if not item:
            return
        
        selected_docs = self._get_selected_documents()
        
        if not selected_docs:
            return
        
        menu = QMenu(self)
        
        if len(selected_docs) == 1:
            # Einzelauswahl
            doc = selected_docs[0]
            
            # PDF Vorschau (als erstes fuer PDFs)
            if self._is_pdf(doc):
                preview_action = QAction("Vorschau", self)
                preview_action.triggered.connect(lambda: self._preview_document(doc))
                menu.addAction(preview_action)
            
            # Download
            download_action = QAction("Herunterladen", self)
            download_action.triggered.connect(lambda: self._download_document(doc))
            menu.addAction(download_action)
            
            # GDV oeffnen
            if doc.is_gdv:
                open_action = QAction("Im GDV-Editor oeffnen", self)
                open_action.triggered.connect(lambda: self._open_in_gdv_editor(doc))
                menu.addAction(open_action)
            
            # KI-Benennung (nur fuer PDFs, die noch nicht umbenannt sind)
            if doc.is_pdf and not doc.ai_renamed:
                menu.addSeparator()
                ai_rename_action = QAction("KI-Benennung", self)
                ai_rename_action.triggered.connect(lambda: self._ai_rename_documents([doc]))
                menu.addAction(ai_rename_action)
            
            menu.addSeparator()
            
            # Loeschen
            delete_action = QAction("Loeschen", self)
            delete_action.triggered.connect(lambda: self._delete_document(doc))
            menu.addAction(delete_action)
        else:
            # Mehrfachauswahl
            download_all_action = QAction(f"{len(selected_docs)} Dokumente herunterladen", self)
            download_all_action.triggered.connect(self._download_selected)
            menu.addAction(download_all_action)
            
            # KI-Benennung fuer mehrere (nur PDFs zaehlen)
            pdf_docs = [d for d in selected_docs if d.is_pdf and not d.ai_renamed]
            if pdf_docs:
                ai_rename_action = QAction(f"KI-Benennung ({len(pdf_docs)} PDFs)", self)
                ai_rename_action.triggered.connect(lambda: self._ai_rename_documents(pdf_docs))
                menu.addAction(ai_rename_action)
            
            menu.addSeparator()
            
            # Mehrfach loeschen
            delete_all_action = QAction(f"{len(selected_docs)} Dokumente loeschen", self)
            delete_all_action.triggered.connect(self._delete_selected)
            menu.addAction(delete_all_action)
        
        menu.exec(self.table.viewport().mapToGlobal(position))
    
    def _on_double_click(self, index):
        """Doppelklick auf Zeile."""
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
    
    def _is_pdf(self, doc: Document) -> bool:
        """Prüft ob das Dokument ein PDF ist."""
        filename = doc.original_filename.lower()
        mime = (doc.mime_type or "").lower()
        return filename.endswith('.pdf') or 'pdf' in mime
    
    def _preview_selected(self):
        """Zeigt Vorschau für das ausgewählte Dokument."""
        selected_docs = self._get_selected_documents()
        
        if not selected_docs:
            self._toast("show_info", "Bitte ein Dokument auswählen.")
            return
        
        if len(selected_docs) > 1:
            self._toast("show_info", "Bitte nur ein Dokument für die Vorschau auswählen.")
            return
        
        doc = selected_docs[0]
        
        if self._is_pdf(doc):
            self._preview_document(doc)
        elif doc.is_gdv:
            self._open_in_gdv_editor(doc)
        else:
            self._toast(
                "show_info",
                f"Für '{doc.original_filename}' ist keine Vorschau verfügbar. "
                "Vorschau ist nur für PDF-Dateien und GDV-Dateien möglich."
            )
    
    def _preview_document(self, doc: Document):
        """PDF-Vorschau anzeigen."""
        # Temporäres Verzeichnis
        temp_dir = tempfile.mkdtemp(prefix='bipro_preview_')
        temp_path = os.path.join(temp_dir, doc.original_filename)
        
        # PDF herunterladen
        progress = QProgressDialog("Lade Vorschau...", "Abbrechen", 0, 0, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.show()
        
        try:
            result = self.docs_api.download(doc.id, temp_dir, filename_override=doc.original_filename)
            progress.close()
            
            if result and os.path.exists(result):
                # Viewer öffnen
                viewer = PDFViewerDialog(result, f"Vorschau: {doc.original_filename}", self)
                viewer.exec()
            else:
                self._toast("show_error", "PDF konnte nicht geladen werden.")
        except Exception as e:
            progress.close()
            self._toast("show_error", f"Vorschau fehlgeschlagen:\n{e}")
    
    def _upload_document(self):
        """Dokument hochladen."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Dokument hochladen",
            "",
            "Alle Dateien (*);;GDV-Dateien (*.gdv *.txt *.dat);;PDF (*.pdf)"
        )
        
        if not file_path:
            return
        
        # Quelle auswählen
        source_type = 'manual_upload'
        
        # Progress-Dialog
        progress = QProgressDialog("Lade hoch...", "Abbrechen", 0, 0, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.show()
        
        self._upload_worker = UploadWorker(self.docs_api, file_path, source_type)
        self._upload_worker.finished.connect(lambda doc: self._on_upload_finished(doc, progress))
        self._upload_worker.error.connect(lambda err: self._on_upload_error(err, progress))
        self._upload_worker.start()
    
    def _on_upload_finished(self, doc: Optional[Document], progress: QProgressDialog):
        """Callback nach Upload."""
        progress.close()
        
        if doc:
            self._toast("show_success", f"Dokument '{doc.original_filename}' erfolgreich hochgeladen.")
            self.refresh_documents()
        else:
            self._toast("show_error", "Upload fehlgeschlagen.")
    
    def _on_upload_error(self, error: str, progress: QProgressDialog):
        """Callback bei Upload-Fehler."""
        progress.close()
        self._toast("show_error", f"Upload fehlgeschlagen:\n{error}")
    
    def _download_document(self, doc: Document):
        """Dokument herunterladen."""
        target_dir = QFileDialog.getExistingDirectory(
            self,
            "Speicherort wählen",
            ""
        )
        
        if not target_dir:
            return
        
        result = self.docs_api.download(doc.id, target_dir, filename_override=doc.original_filename)
        
        if result:
            self._toast("show_success", f"Dokument gespeichert:\n{result}")
        else:
            self._toast("show_error", "Download fehlgeschlagen.")
    
    def _open_in_gdv_editor(self, doc: Document):
        """GDV-Dokument im Editor öffnen."""
        self.open_gdv_requested.emit(doc.id, doc.original_filename)
    
    def _delete_document(self, doc: Document):
        """Dokument löschen."""
        reply = QMessageBox.question(
            self,
            "Löschen bestätigen",
            f"Dokument '{doc.original_filename}' wirklich löschen?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            if self.docs_api.delete(doc.id):
                # Erfolgreich gelöscht - keine Meldung, nur Refresh
                self.refresh_documents()
            else:
                # Nur bei Fehler eine Meldung anzeigen
                self._toast("show_error", "Löschen fehlgeschlagen.")
    
    def _delete_selected(self):
        """Mehrere ausgewählte Dokumente löschen."""
        selected_docs = self._get_selected_documents()
        
        if not selected_docs:
            return
        
        reply = QMessageBox.question(
            self,
            "Löschen bestätigen",
            f"Wirklich {len(selected_docs)} Dokument(e) löschen?\n\n"
            "Diese Aktion kann nicht rückgängig gemacht werden!",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        # Progress-Dialog mit Fortschrittsanzeige
        progress = QProgressDialog(
            "Lösche Dokumente...",
            "Abbrechen",
            0, len(selected_docs),
            self
        )
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setAutoClose(True)  # Automatisch schließen wenn fertig
        progress.setMinimumDuration(0)  # Sofort anzeigen
        
        success_count = 0
        for i, doc in enumerate(selected_docs):
            # Abbruch prüfen
            if progress.wasCanceled():
                break
            
            # Fortschritt aktualisieren
            progress.setValue(i)
            progress.setLabelText(f"Lösche {i+1}/{len(selected_docs)}: {doc.original_filename}")
            QApplication.processEvents()  # UI aktualisieren
            
            # Dokument löschen
            if self.docs_api.delete(doc.id):
                success_count += 1
        
        # Abschluss
        progress.setValue(len(selected_docs))
        
        # Daten neu laden (kein Pop-up nach Abschluss!)
        self.refresh_documents()
    
    def _get_selected_documents(self) -> List[Document]:
        """Gibt alle ausgewählten Dokumente zurück."""
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
    
    def _download_selected(self):
        """Ausgewählte Dokumente herunterladen."""
        selected_docs = self._get_selected_documents()
        
        if not selected_docs:
            self._toast(
                "show_info",
                "Bitte mindestens ein Dokument auswählen. "
                "Tipp: Mit Strg+Klick oder Shift+Klick mehrere auswählen."
            )
            return
        
        # Zielordner wählen
        target_dir = QFileDialog.getExistingDirectory(
            self,
            f"Speicherort für {len(selected_docs)} Dokument(e) wählen",
            ""
        )
        
        if not target_dir:
            return
        
        # Downloads durchführen
        success_count = 0
        failed_count = 0
        
        progress = QProgressDialog(
            f"Lade {len(selected_docs)} Dokument(e) herunter...",
            "Abbrechen",
            0, len(selected_docs),
            self
        )
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.show()
        
        for i, doc in enumerate(selected_docs):
            if progress.wasCanceled():
                break
            
            progress.setValue(i)
            progress.setLabelText(f"Lade: {doc.original_filename}")
            
            result = self.docs_api.download(doc.id, target_dir, filename_override=doc.original_filename)
            if result:
                success_count += 1
            else:
                failed_count += 1
        
        progress.close()
        
        # Zusammenfassung
        if failed_count == 0:
            self._toast(
                "show_success",
                f"{success_count} Dokument(e) erfolgreich heruntergeladen. Speicherort: {target_dir}"
            )
        else:
            self._toast(
                "show_warning",
                f"Download: {success_count} erfolgreich, {failed_count} fehlgeschlagen. Speicherort: {target_dir}"
            )
    
    # ========================================
    # KI-Benennung
    # ========================================
    
    def _ai_rename_selected(self):
        """KI-Benennung fuer ausgewaehlte Dokumente starten."""
        selected_docs = self._get_selected_documents()
        
        # Nur PDFs filtern, die noch nicht umbenannt sind
        pdf_docs = [d for d in selected_docs if d.is_pdf and not d.ai_renamed]
        
        if not pdf_docs:
            # Wenn nichts ausgewaehlt oder keine PDFs, alle unbennannten anbieten
            all_unrenamed = [d for d in self._documents if d.is_pdf and not d.ai_renamed]
            
            if not all_unrenamed:
                self._toast(
                    "show_info",
                    "Keine PDFs ohne KI-Benennung gefunden. Alle PDFs wurden bereits verarbeitet."
                )
                return
            
            reply = QMessageBox.question(
                self,
                "KI-Benennung",
                f"Keine PDFs ausgewaehlt.\n\n"
                f"Sollen alle {len(all_unrenamed)} unbennannten PDFs verarbeitet werden?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                pdf_docs = all_unrenamed
            else:
                return
        
        self._ai_rename_documents(pdf_docs)
    
    def _ai_rename_documents(self, documents: List[Document]):
        """Startet die KI-Benennung fuer die uebergebenen Dokumente."""
        if not documents:
            return
        
        # Bestaetigung
        reply = QMessageBox.question(
            self,
            "KI-Benennung starten",
            f"{len(documents)} PDF(s) werden durch KI analysiert und umbenannt.\n\n"
            "Das kann je nach Dokumentenanzahl einige Minuten dauern.\n"
            "Die Dokumente werden im Format 'Versicherer_Typ_Datum.pdf' benannt.\n\n"
            "Fortfahren?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        # Progress-Dialog
        self._ai_progress = QProgressDialog(
            "Initialisiere KI-Benennung...",
            "Abbrechen",
            0, len(documents),
            self
        )
        self._ai_progress.setWindowTitle("KI-Benennung")
        self._ai_progress.setWindowModality(Qt.WindowModality.WindowModal)
        self._ai_progress.setMinimumDuration(0)
        self._ai_progress.setValue(0)
        self._ai_progress.canceled.connect(self._cancel_ai_rename)
        self._ai_progress.show()
        
        # Worker starten
        self._ai_rename_worker = AIRenameWorker(
            self.api_client,
            self._repo,
            documents
        )
        self._ai_rename_worker.progress.connect(self._on_ai_rename_progress)
        self._ai_rename_worker.single_finished.connect(self._on_ai_rename_single)
        self._ai_rename_worker.finished.connect(self._on_ai_rename_finished)
        self._ai_rename_worker.error.connect(self._on_ai_rename_error)
        self._ai_rename_worker.start()
    
    def _cancel_ai_rename(self):
        """Bricht die KI-Benennung ab."""
        if self._ai_rename_worker:
            self._ai_rename_worker.cancel()
    
    def _on_ai_rename_progress(self, current: int, total: int, filename: str):
        """Callback fuer Fortschritt."""
        if hasattr(self, '_ai_progress') and self._ai_progress:
            self._ai_progress.setValue(current)
            self._ai_progress.setLabelText(f"Verarbeite: {filename}\n({current}/{total})")
    
    def _on_ai_rename_single(self, doc_id: int, success: bool, result: str):
        """Callback wenn ein einzelnes Dokument fertig ist."""
        logger.info(f"KI-Benennung Dokument {doc_id}: {'OK' if success else 'FEHLER'} - {result}")
    
    def _on_ai_rename_finished(self, results: List[Tuple[int, bool, str]]):
        """Callback wenn alle Dokumente verarbeitet wurden."""
        if hasattr(self, '_ai_progress') and self._ai_progress:
            self._ai_progress.close()
        
        # Statistik
        success_count = sum(1 for _, success, _ in results if success)
        failed_count = len(results) - success_count
        
        # Detaillierte Ergebnisse
        details = []
        for doc_id, success, result in results[:10]:  # Maximal 10 anzeigen
            status = "OK" if success else "FEHLER"
            details.append(f"  {status}: {result}")
        
        if len(results) > 10:
            details.append(f"  ... und {len(results) - 10} weitere")
        
        detail_text = "\n".join(details)
        
        if failed_count == 0:
            self._toast(
                "show_success",
                f"KI-Benennung: Alle {success_count} Dokument(e) erfolgreich umbenannt."
            )
        else:
            self._toast(
                "show_warning",
                f"KI-Benennung: {success_count} erfolgreich, {failed_count} fehlgeschlagen."
            )
        
        # Tabelle aktualisieren
        self.refresh_documents()
    
    def _on_ai_rename_error(self, error: str):
        """Callback bei globalem Fehler."""
        if hasattr(self, '_ai_progress') and self._ai_progress:
            self._ai_progress.close()
        
        self._toast("show_error", f"KI-Benennung Fehler: {error}")


# =============================================================================
# DuplicateCompareDialog - Side-by-Side Vergleich von Duplikaten
# =============================================================================


