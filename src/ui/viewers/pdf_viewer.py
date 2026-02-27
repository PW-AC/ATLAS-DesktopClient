"""
ACENCIA ATLAS - PDF-Viewer-Komponenten

Eigenstaendige Klassen fuer die PDF-Vorschau und -Bearbeitung,
ausgelagert aus archive_view.py.
"""

import os
import logging
import tempfile

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QToolBar, QApplication, QMessageBox, QWidget,
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


class _ThumbnailWorker(QThread):
    """Rendert PDF-Thumbnails im Hintergrund, damit die UI nicht blockiert."""
    thumbnail_ready = Signal(int, bytes, int, int)  # page_idx, img_bytes, w, h

    def __init__(self, pdf_path: str, page_count: int):
        super().__init__()
        self._pdf_path = pdf_path
        self._page_count = page_count

    def run(self):
        try:
            import fitz
            try:
                doc = fitz.open(self._pdf_path)
            except Exception:
                with open(self._pdf_path, 'rb') as f:
                    data = f.read()
                doc = fitz.open(stream=data, filetype="pdf")
            
            for i in range(min(len(doc), self._page_count)):
                page = doc[i]
                zoom = 120.0 / page.rect.width
                mat = fitz.Matrix(zoom, zoom)
                pix = page.get_pixmap(matrix=mat)
                self.thumbnail_ready.emit(i, bytes(pix.samples), pix.width, pix.height)
            
            doc.close()
        except Exception as e:
            logger.warning(f"Thumbnail-Worker Fehler: {e}")


class PDFSaveWorker(QThread):
    """Worker zum asynchronen Speichern eines bearbeiteten PDFs auf dem Server."""
    finished = Signal(bool)   # success
    error = Signal(str)       # error_message
    
    def __init__(self, docs_api, doc_id: int, file_path: str, parent=None):
        super().__init__(parent)
        self.docs_api = docs_api
        self.doc_id = doc_id
        self.file_path = file_path
    
    def run(self):
        try:
            success = self.docs_api.replace_document_file(self.doc_id, self.file_path)
            self.finished.emit(success)
        except Exception as e:
            self.error.emit(str(e))


class PDFRefreshWorker(QThread):
    """Aktualisiert Leere-Seiten-Daten und Textinhalt nach PDF-Bearbeitung."""
    finished = Signal(bool)
    
    def __init__(self, docs_api, doc_id: int, pdf_path: str, parent=None):
        super().__init__(parent)
        self.docs_api = docs_api
        self.doc_id = doc_id
        self.pdf_path = pdf_path
    
    def run(self):
        try:
            from services.empty_page_detector import get_empty_pages
            empty_indices, total_pages = get_empty_pages(self.pdf_path)
            if total_pages > 0:
                self.docs_api.client.put(
                    f'/documents/{self.doc_id}',
                    json_data={
                        'empty_page_count': len(empty_indices),
                        'total_page_count': total_pages
                    }
                )
            
            from services.early_text_extract import extract_and_save_text
            extract_and_save_text(self.docs_api, self.doc_id, self.pdf_path)
            
            self.finished.emit(True)
        except Exception as e:
            logger.error(f"PDF-Refresh nach Bearbeitung fehlgeschlagen fuer Dokument {self.doc_id}: {e}")
            self.finished.emit(False)


class PDFViewerDialog(QDialog):
    """
    Dialog zur PDF-Vorschau und -Bearbeitung.
    
    Zeigt PDFs direkt in der App an ohne separaten Download.
    Verwendet QPdfView (Qt6 native) oder öffnet extern als Fallback.
    
    Bearbeitungsmodus (editable=True):
    - Thumbnail-Sidebar links mit Seitenvorschau
    - Seiten drehen (CW/CCW) und loeschen
    - Bearbeitetes PDF auf dem Server speichern
    """
    
    # Signal wenn PDF gespeichert wurde (fuer Cache-Invalidierung)
    pdf_saved = Signal(int)  # doc_id
    
    def __init__(self, pdf_path: str, title: str = "PDF-Vorschau", parent=None,
                 doc_id: int = None, docs_api=None, editable: bool = False):
        super().__init__(parent)
        self.pdf_path = pdf_path
        self.pdf_document = None
        self._doc_id = doc_id
        self._docs_api = docs_api
        self._editable = editable and doc_id is not None and docs_api is not None
        self._fitz_doc = None
        self._change_count = 0
        self._save_worker = None
        self._refresh_data_worker = None
        self._temp_pdf_path = None
        self.setWindowTitle(title)
        self.setMinimumSize(900, 700)
        self.resize(1200 if self._editable else 1000, 900 if self._editable else 800)
        
        self._setup_ui()
        
        # PyMuPDF laden fuer Bearbeitung
        if self._editable:
            self._load_fitz_document()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Toolbar
        toolbar = QToolBar()
        toolbar.setMovable(False)
        
        # Titel
        title_label = QLabel(f"  {os.path.basename(self.pdf_path)}")
        title_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        toolbar.addWidget(title_label)
        
        toolbar.addSeparator()
        
        # Zoom-Buttons (für QPdfView)
        if HAS_PDF_VIEW:
            zoom_in_btn = QPushButton("Zoom +")
            zoom_in_btn.setToolTip("Vergroessern")
            zoom_in_btn.clicked.connect(self._zoom_in)
            toolbar.addWidget(zoom_in_btn)
            
            zoom_out_btn = QPushButton("Zoom -")
            zoom_out_btn.setToolTip("Verkleinern")
            zoom_out_btn.clicked.connect(self._zoom_out)
            toolbar.addWidget(zoom_out_btn)
            
            fit_width_btn = QPushButton("Breite")
            fit_width_btn.setToolTip("An Breite anpassen")
            fit_width_btn.clicked.connect(self._fit_width)
            toolbar.addWidget(fit_width_btn)
            
            fit_page_btn = QPushButton("Seite")
            fit_page_btn.setToolTip("Ganze Seite")
            fit_page_btn.clicked.connect(self._fit_page)
            toolbar.addWidget(fit_page_btn)
            
            toolbar.addSeparator()
        
        # Bearbeitungs-Buttons (nur im Edit-Modus)
        if self._editable:
            from i18n.de import (
                PDF_EDIT_ROTATE_CCW, PDF_EDIT_ROTATE_CW,
                PDF_EDIT_DELETE_PAGE, PDF_EDIT_SAVE
            )
            
            _edit_btn_style = """
                QPushButton {
                    padding: 4px 10px;
                    border: 1px solid #cbd5e1;
                    border-radius: 4px;
                    background-color: #f8fafc;
                    font-size: 11px;
                }
                QPushButton:hover { background-color: #e2e8f0; }
                QPushButton:pressed { background-color: #cbd5e1; }
            """
            _delete_btn_style = """
                QPushButton {
                    padding: 4px 10px;
                    border: 1px solid #fca5a5;
                    border-radius: 4px;
                    background-color: #fef2f2;
                    color: #dc2626;
                    font-size: 11px;
                }
                QPushButton:hover { background-color: #fee2e2; }
                QPushButton:pressed { background-color: #fecaca; }
            """
            
            rotate_ccw_btn = QPushButton(PDF_EDIT_ROTATE_CCW)
            rotate_ccw_btn.setToolTip(PDF_EDIT_ROTATE_CCW)
            rotate_ccw_btn.setStyleSheet(_edit_btn_style)
            rotate_ccw_btn.clicked.connect(self._rotate_ccw)
            toolbar.addWidget(rotate_ccw_btn)
            
            rotate_cw_btn = QPushButton(PDF_EDIT_ROTATE_CW)
            rotate_cw_btn.setToolTip(PDF_EDIT_ROTATE_CW)
            rotate_cw_btn.setStyleSheet(_edit_btn_style)
            rotate_cw_btn.clicked.connect(self._rotate_cw)
            toolbar.addWidget(rotate_cw_btn)
            
            self._delete_page_btn = QPushButton(PDF_EDIT_DELETE_PAGE)
            self._delete_page_btn.setToolTip(PDF_EDIT_DELETE_PAGE)
            self._delete_page_btn.setStyleSheet(_delete_btn_style)
            self._delete_page_btn.clicked.connect(self._delete_page)
            toolbar.addWidget(self._delete_page_btn)
            
            toolbar.addSeparator()
            
            self._save_btn = QPushButton(PDF_EDIT_SAVE)
            self._save_btn.setToolTip(PDF_EDIT_SAVE)
            self._save_btn.setEnabled(False)
            self._save_btn.setStyleSheet("""
                QPushButton {
                    background-color: #059669;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 4px 12px;
                    font-weight: bold;
                }
                QPushButton:hover { background-color: #047857; }
                QPushButton:disabled { background-color: #9ca3af; }
            """)
            self._save_btn.clicked.connect(self._save_pdf)
            toolbar.addWidget(self._save_btn)
            
            toolbar.addSeparator()
        
        # Spacer um die rechten Elemente nach rechts zu druecken
        if self._editable:
            from PySide6.QtWidgets import QSizePolicy
            spacer = QWidget()
            spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            toolbar.addWidget(spacer)
            
            from i18n.de import PDF_EDIT_NO_CHANGES
            self._edit_status_label = QLabel(PDF_EDIT_NO_CHANGES)
            self._edit_status_label.setStyleSheet(
                "color: #6b7280; font-size: 11px; padding: 0 8px;"
            )
            toolbar.addWidget(self._edit_status_label)
            
            toolbar.addSeparator()
        
        # Extern oeffnen
        open_external_btn = QPushButton("Extern oeffnen")
        open_external_btn.setToolTip("Mit System-PDF-Viewer oeffnen")
        open_external_btn.clicked.connect(self._open_external)
        toolbar.addWidget(open_external_btn)
        
        # Schließen
        close_btn = QPushButton("Schliessen")
        close_btn.clicked.connect(self.close)
        toolbar.addWidget(close_btn)
        
        layout.addWidget(toolbar)
        
        # Inline-Status-Label fuer Fehler (statt modaler Dialoge)
        self._status_label = QLabel("")
        self._status_label.setVisible(False)
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)
        
        # Hauptbereich: Thumbnails (optional) + PDF-Viewer
        if HAS_PDF_VIEW:
            if self._editable:
                # Splitter: Thumbnails links, QPdfView rechts
                from PySide6.QtWidgets import QSplitter, QListWidget, QListWidgetItem
                splitter = QSplitter(Qt.Orientation.Horizontal)
                
                # Thumbnail-Liste mit Mehrfachauswahl (Strg+Klick, Shift+Klick, Strg+A)
                self._thumbnail_list = QListWidget()
                from PySide6.QtWidgets import QAbstractItemView
                from PySide6.QtCore import QSize
                self._thumbnail_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
                self._thumbnail_list.setIconSize(QSize(120, 160))
                self._thumbnail_list.setMinimumWidth(145)
                self._thumbnail_list.setMaximumWidth(160)
                self._thumbnail_list.setSpacing(2)
                self._thumbnail_list.setStyleSheet("""
                    QListWidget {
                        background-color: #f1f5f9;
                        border: none;
                        border-right: 1px solid #e2e8f0;
                        font-size: 10px;
                    }
                    QListWidget::item {
                        padding: 3px;
                        border-radius: 3px;
                    }
                    QListWidget::item:selected {
                        background-color: #dbeafe;
                        border: 2px solid #3b82f6;
                    }
                """)
                self._thumbnail_list.itemSelectionChanged.connect(self._on_thumbnail_selection_changed)
                splitter.addWidget(self._thumbnail_list)
                
                # QPdfView
                self.pdf_document = QPdfDocument(self)
                self.pdf_view = QPdfView(self)
                self.pdf_view.setDocument(self.pdf_document)
                self.pdf_view.setPageMode(QPdfView.PageMode.MultiPage)
                self.pdf_view.setZoomMode(QPdfView.ZoomMode.FitInView)
                splitter.addWidget(self.pdf_view)
                
                splitter.setSizes([150, 950])
                
                layout.addWidget(splitter)
            else:
                # Read-only: Nur QPdfView (wie bisher)
                self.pdf_document = QPdfDocument(self)
                self.pdf_view = QPdfView(self)
                self.pdf_view.setDocument(self.pdf_document)
                self.pdf_view.setPageMode(QPdfView.PageMode.MultiPage)
                self.pdf_view.setZoomMode(QPdfView.ZoomMode.FitInView)
                layout.addWidget(self.pdf_view)
            
            # PDF laden
            error = self.pdf_document.load(self.pdf_path)
            if error != QPdfDocument.Error.None_:
                self._status_label.setText(f"PDF konnte nicht geladen werden: {error}")
                self._status_label.setStyleSheet(
                    "color: #dc2626; background: #fef2f2; padding: 6px 12px; border-radius: 4px;"
                )
                self._status_label.setVisible(True)
            
            self._zoom_factor = 1.0
        else:
            # Fallback: Hinweis und Button zum externen Öffnen
            fallback_widget = QWidget()
            fallback_layout = QVBoxLayout(fallback_widget)
            fallback_layout.addStretch()
            
            info_label = QLabel(
                "PDF-Vorschau nicht verfuegbar.\n\n"
                "Fuer die integrierte PDF-Ansicht wird\n"
                "PySide6 >= 6.4 benoetigt.\n\n"
                "Das PDF wird extern geoeffnet."
            )
            info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            info_label.setFont(QFont("Segoe UI", 11))
            fallback_layout.addWidget(info_label)
            
            open_btn = QPushButton("PDF extern oeffnen")
            open_btn.setMinimumSize(200, 50)
            open_btn.clicked.connect(self._open_external)
            fallback_layout.addWidget(open_btn, alignment=Qt.AlignmentFlag.AlignCenter)
            
            # Automatisch extern öffnen wenn kein Viewer verfügbar
            self._open_external()
            
            fallback_layout.addStretch()
            layout.addWidget(fallback_widget)
    
    # ========================================
    # PyMuPDF Integration (Bearbeitungsmodus)
    # ========================================
    
    def _load_fitz_document(self):
        """Laedt das PDF mit PyMuPDF fuer Bearbeitungsoperationen."""
        try:
            import fitz
            try:
                self._fitz_doc = fitz.open(self.pdf_path)
            except Exception:
                # Fallback: Datei als Bytes laden (Workaround fuer MuPDF-Probleme
                # mit Sonderzeichen wie '...' in Windows-Pfaden)
                logger.warning(f"PyMuPDF Pfad-Oeffnung fehlgeschlagen, versuche Bytes-Fallback: {self.pdf_path}")
                with open(self.pdf_path, 'rb') as f:
                    data = f.read()
                self._fitz_doc = fitz.open(stream=data, filetype="pdf")
            self._refresh_thumbnails()
        except Exception as e:
            logger.error(f"PyMuPDF konnte PDF nicht laden: {e}")
            self._status_label.setText(f"PDF-Bearbeitung nicht verfuegbar: {e}")
            self._status_label.setStyleSheet(
                "color: #dc2626; background: #fef2f2; padding: 6px 12px; border-radius: 4px;"
            )
            self._status_label.setVisible(True)
    
    def _refresh_thumbnails(self):
        """Rendert Thumbnails asynchron in einem Worker-Thread.
        
        Platzhalter-Items werden sofort erstellt, die eigentlichen Pixmaps
        werden im Hintergrund gerendert und per Signal stueckweise eingesetzt.
        """
        if not self._fitz_doc or not hasattr(self, '_thumbnail_list'):
            return
        
        from PySide6.QtGui import QPixmap, QImage, QIcon
        from PySide6.QtCore import QSize
        from PySide6.QtWidgets import QListWidgetItem
        
        page_count = len(self._fitz_doc)
        
        self._thumbnail_list.blockSignals(True)
        self._thumbnail_list.clear()
        
        for i in range(page_count):
            item = QListWidgetItem()
            item.setText(f"S. {i + 1}")
            item.setData(Qt.ItemDataRole.UserRole, i)
            self._thumbnail_list.addItem(item)
        
        self._thumbnail_list.setIconSize(QSize(120, 160))
        self._thumbnail_list.blockSignals(False)
        
        if self._thumbnail_list.count() > 0:
            self._thumbnail_list.setCurrentRow(0)
        
        self._thumb_worker = _ThumbnailWorker(self.pdf_path, page_count)
        self._thumb_worker.thumbnail_ready.connect(self._on_thumbnail_ready)
        self._thumb_worker.start()
    
    def _on_thumbnail_ready(self, page_idx: int, img_bytes: bytes, width: int, height: int):
        """Callback fuer einen fertig gerenderten Thumbnail."""
        if not hasattr(self, '_thumbnail_list') or page_idx >= self._thumbnail_list.count():
            return
        from PySide6.QtGui import QPixmap, QImage, QIcon
        img = QImage(img_bytes, width, height, width * 3, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(img)
        item = self._thumbnail_list.item(page_idx)
        if item:
            item.setIcon(QIcon(pixmap))
    
    def _get_selected_page_indices(self) -> list:
        """Gibt die Indizes aller ausgewaehlten Seiten zurueck (sortiert)."""
        if not hasattr(self, '_thumbnail_list'):
            return []
        indices = []
        for item in self._thumbnail_list.selectedItems():
            idx = item.data(Qt.ItemDataRole.UserRole)
            if idx is not None:
                indices.append(idx)
        return sorted(indices)
    
    def _on_thumbnail_selection_changed(self):
        """Scrollt die PDF-Ansicht zur zuletzt ausgewaehlten Seite."""
        if not hasattr(self, 'pdf_view'):
            return
        indices = self._get_selected_page_indices()
        if not indices:
            return
        try:
            from PySide6.QtCore import QPointF
            navigator = self.pdf_view.pageNavigator()
            navigator.jump(indices[-1], QPointF(0, 0))
        except Exception as e:
            logger.debug(f"Seiten-Navigation fehlgeschlagen: {e}")
        self._update_edit_status()
    
    def _rotate_cw(self):
        """Dreht die ausgewaehlte Seite 90 Grad im Uhrzeigersinn."""
        self._rotate_page(90)
    
    def _rotate_ccw(self):
        """Dreht die ausgewaehlte Seite 90 Grad gegen den Uhrzeigersinn."""
        self._rotate_page(-90)
    
    def _rotate_page(self, degrees: int):
        """Dreht alle ausgewaehlten Seiten um die angegebenen Grad."""
        if not self._fitz_doc:
            return
        
        page_indices = self._get_selected_page_indices()
        if not page_indices:
            return
        
        for idx in page_indices:
            page = self._fitz_doc[idx]
            page.set_rotation((page.rotation + degrees) % 360)
        
        self._change_count += len(page_indices)
        self._apply_changes_and_refresh(page_indices[0], selected_pages=page_indices)
    
    def _delete_page(self):
        """Loescht alle ausgewaehlten Seiten nach Bestaetigung."""
        if not self._fitz_doc:
            return
        
        from i18n.de import (PDF_EDIT_DELETE_CONFIRM, PDF_EDIT_DELETE_MULTI_CONFIRM,
                              PDF_EDIT_MIN_ONE_PAGE)
        
        page_indices = self._get_selected_page_indices()
        if not page_indices:
            return
        
        # Pruefung: Mindestens eine Seite muss verbleiben
        if len(page_indices) >= len(self._fitz_doc):
            self._status_label.setText(PDF_EDIT_MIN_ONE_PAGE)
            self._status_label.setStyleSheet(
                "color: #f59e0b; background: #fffbeb; padding: 6px 12px; border-radius: 4px;"
            )
            self._status_label.setVisible(True)
            return
        
        # Bestaetigung (Einzel- vs. Mehrfachauswahl)
        if len(page_indices) == 1:
            confirm_msg = PDF_EDIT_DELETE_CONFIRM.format(page=page_indices[0] + 1)
        else:
            confirm_msg = PDF_EDIT_DELETE_MULTI_CONFIRM.format(count=len(page_indices))
        
        reply = QMessageBox.question(
            self, "Seite loeschen",
            confirm_msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        # Loeschen in umgekehrter Reihenfolge (hoechster Index zuerst),
        # damit sich die Indizes der noch zu loeschenden Seiten nicht verschieben.
        for idx in sorted(page_indices, reverse=True):
            self._fitz_doc.delete_page(idx)
        
        self._change_count += len(page_indices)
        
        # Neue Auswahl: erste verbleibende Seite nach der ersten geloeschten
        new_idx = min(page_indices[0], len(self._fitz_doc) - 1)
        self._apply_changes_and_refresh(new_idx)
    
    def _apply_changes_and_refresh(self, select_page: int = 0,
                                    selected_pages: list = None):
        """Speichert das geaenderte PDF temporaer und aktualisiert die Anzeige.
        
        Args:
            select_page: Einzelne Seite die ausgewaehlt werden soll (Fallback)
            selected_pages: Liste von Seiten die nach Refresh selektiert werden sollen
        """
        if not self._fitz_doc:
            return
        
        import fitz
        
        # Alternierende Temp-Dateien: A und B
        # PyMuPDF kann nicht an die gleiche Datei speichern, von der es gelesen hat.
        temp_dir = tempfile.gettempdir()
        old_path = self._temp_pdf_path
        
        # Zwischen A und B wechseln
        path_a = os.path.join(temp_dir, f'bipro_edit_{os.getpid()}_a.pdf')
        path_b = os.path.join(temp_dir, f'bipro_edit_{os.getpid()}_b.pdf')
        
        if old_path == path_a:
            new_path = path_b
        else:
            new_path = path_a
        
        self._fitz_doc.save(new_path)
        self._temp_pdf_path = new_path
        
        # QPdfView neu laden
        if HAS_PDF_VIEW and self.pdf_document:
            self.pdf_document.close()
            self.pdf_document.load(new_path)
        
        # fitz-Dokument neu laden
        self._fitz_doc.close()
        self._fitz_doc = fitz.open(new_path)
        
        # Alte Temp-Datei aufraemen
        if old_path and old_path != new_path and os.path.exists(old_path):
            try:
                os.unlink(old_path)
            except Exception:
                pass
        
        # Thumbnails aktualisieren
        self._refresh_thumbnails()
        
        # Seiten-Auswahl wiederherstellen
        if hasattr(self, '_thumbnail_list'):
            page_count = self._thumbnail_list.count()
            if selected_pages and len(selected_pages) > 1:
                # Mehrfachauswahl wiederherstellen
                self._thumbnail_list.blockSignals(True)
                self._thumbnail_list.clearSelection()
                for idx in selected_pages:
                    if idx < page_count:
                        self._thumbnail_list.item(idx).setSelected(True)
                self._thumbnail_list.blockSignals(False)
                self._on_thumbnail_selection_changed()
            elif select_page < page_count:
                self._thumbnail_list.setCurrentRow(select_page)
        
        # UI aktualisieren
        self._update_edit_status()
        self._status_label.setVisible(False)
    
    def _update_edit_status(self):
        """Aktualisiert die Statusbar mit Aenderungszaehler."""
        if not hasattr(self, '_edit_status_label'):
            return
        
        from i18n.de import (PDF_EDIT_CHANGES, PDF_EDIT_NO_CHANGES, PDF_EDIT_STATUS,
                              PDF_EDIT_MULTI_SELECTED)
        
        page_count = len(self._fitz_doc) if self._fitz_doc else 0
        indices = self._get_selected_page_indices()
        
        parts = []
        if page_count > 0 and indices:
            if len(indices) == 1:
                parts.append(PDF_EDIT_STATUS.format(current=indices[0] + 1, total=page_count))
            else:
                parts.append(PDF_EDIT_MULTI_SELECTED.format(
                    selected=len(indices), total=page_count))
        
        if self._change_count > 0:
            parts.append(PDF_EDIT_CHANGES.format(count=self._change_count))
        else:
            parts.append(PDF_EDIT_NO_CHANGES)
        
        self._edit_status_label.setText("  |  ".join(parts))
        
        # Save-Button aktivieren wenn Aenderungen vorhanden
        if hasattr(self, '_save_btn'):
            self._save_btn.setEnabled(self._change_count > 0)
    
    def _save_pdf(self):
        """Speichert das bearbeitete PDF auf dem Server."""
        if not self._fitz_doc or not self._docs_api or self._doc_id is None:
            return
        
        from i18n.de import PDF_EDIT_SAVING
        
        # Finales PDF in temp-Datei speichern
        save_path = os.path.join(tempfile.gettempdir(), f'bipro_save_{self._doc_id}.pdf')
        self._fitz_doc.save(save_path, garbage=4, deflate=True)
        
        # Save-Button deaktivieren waehrend Upload
        self._save_btn.setEnabled(False)
        self._save_btn.setText(PDF_EDIT_SAVING)
        
        # Worker starten
        self._save_worker = PDFSaveWorker(self._docs_api, self._doc_id, save_path)
        self._save_worker.finished.connect(self._on_save_finished)
        self._save_worker.error.connect(self._on_save_error)
        self._save_worker.start()
    
    def _on_save_finished(self, success: bool):
        """Callback nach dem Speichern."""
        from i18n.de import (PDF_EDIT_SAVE, PDF_EDIT_SAVE_SUCCESS, PDF_EDIT_SAVE_ERROR,
                              PDF_EDIT_REFRESHING)
        
        self._save_btn.setText(PDF_EDIT_SAVE)
        
        if success:
            self._change_count = 0
            self._update_edit_status()
            self._status_label.setText(PDF_EDIT_SAVE_SUCCESS)
            self._status_label.setStyleSheet(
                "color: #059669; background: #ecfdf5; padding: 6px 12px; border-radius: 4px;"
            )
            self._status_label.setVisible(True)
            # Signal fuer Cache-Invalidierung
            self.pdf_saved.emit(self._doc_id)
            
            # Leere-Seiten + Textinhalt im Hintergrund aktualisieren
            if self._docs_api and self._doc_id is not None and self._temp_pdf_path:
                self._status_label.setText(PDF_EDIT_REFRESHING)
                self._status_label.setStyleSheet(
                    "color: #2563eb; background: #eff6ff; padding: 6px 12px; border-radius: 4px;"
                )
                self._refresh_data_worker = PDFRefreshWorker(
                    self._docs_api, self._doc_id, self._temp_pdf_path
                )
                self._refresh_data_worker.finished.connect(self._on_refresh_data_finished)
                self._refresh_data_worker.start()
        else:
            self._save_btn.setEnabled(True)
            self._status_label.setText(PDF_EDIT_SAVE_ERROR.format(error="Server-Fehler"))
            self._status_label.setStyleSheet(
                "color: #dc2626; background: #fef2f2; padding: 6px 12px; border-radius: 4px;"
            )
            self._status_label.setVisible(True)
    
    def _on_refresh_data_finished(self, success: bool):
        """Callback nach dem Aktualisieren von Leere-Seiten und Textinhalt."""
        from i18n.de import PDF_EDIT_REFRESH_SUCCESS, PDF_EDIT_SAVE_SUCCESS
        
        if success:
            self._status_label.setText(PDF_EDIT_REFRESH_SUCCESS)
            self._status_label.setStyleSheet(
                "color: #059669; background: #ecfdf5; padding: 6px 12px; border-radius: 4px;"
            )
        else:
            self._status_label.setText(PDF_EDIT_SAVE_SUCCESS)
            self._status_label.setStyleSheet(
                "color: #059669; background: #ecfdf5; padding: 6px 12px; border-radius: 4px;"
            )
    
    def _on_save_error(self, error_msg: str):
        """Callback bei Speicher-Fehler."""
        from i18n.de import PDF_EDIT_SAVE, PDF_EDIT_SAVE_ERROR
        
        self._save_btn.setText(PDF_EDIT_SAVE)
        self._save_btn.setEnabled(True)
        self._status_label.setText(PDF_EDIT_SAVE_ERROR.format(error=error_msg))
        self._status_label.setStyleSheet(
            "color: #dc2626; background: #fef2f2; padding: 6px 12px; border-radius: 4px;"
        )
        self._status_label.setVisible(True)
    
    # ========================================
    # Zoom (QPdfView)
    # ========================================
    
    def _zoom_in(self):
        if HAS_PDF_VIEW:
            self._zoom_factor = min(4.0, self._zoom_factor + 0.25)
            self.pdf_view.setZoomFactor(self._zoom_factor)
            self.pdf_view.setZoomMode(QPdfView.ZoomMode.Custom)
    
    def _zoom_out(self):
        if HAS_PDF_VIEW:
            self._zoom_factor = max(0.25, self._zoom_factor - 0.25)
            self.pdf_view.setZoomFactor(self._zoom_factor)
            self.pdf_view.setZoomMode(QPdfView.ZoomMode.Custom)
    
    def _fit_width(self):
        if HAS_PDF_VIEW:
            self.pdf_view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
            self._zoom_factor = self.pdf_view.zoomFactor()
    
    def _fit_page(self):
        if HAS_PDF_VIEW:
            self.pdf_view.setZoomMode(QPdfView.ZoomMode.FitInView)
            self._zoom_factor = self.pdf_view.zoomFactor()
    
    def _open_external(self):
        """Oeffnet das PDF mit dem System-Standard-Viewer."""
        import subprocess
        import sys
        
        try:
            if sys.platform == 'win32':
                os.startfile(self.pdf_path)
            elif sys.platform == 'darwin':
                subprocess.run(['open', self.pdf_path])
            else:
                subprocess.run(['xdg-open', self.pdf_path])
        except Exception as e:
            self._status_label.setText(f"Konnte PDF nicht oeffnen: {e}")
            self._status_label.setStyleSheet(
                "color: #dc2626; background: #fef2f2; padding: 6px 12px; border-radius: 4px;"
            )
            self._status_label.setVisible(True)
    
    def showEvent(self, event):
        """Maximiert den Dialog im Bearbeitungsmodus beim ersten Anzeigen."""
        super().showEvent(event)
        if self._editable and not getattr(self, '_was_shown', False):
            self._was_shown = True
            self.showMaximized()
    
    def closeEvent(self, event):
        """Warnt bei ungespeicherten Aenderungen."""
        if self._change_count > 0:
            from i18n.de import PDF_EDIT_UNSAVED, PDF_EDIT_UNSAVED_CONFIRM
            reply = QMessageBox.question(
                self, PDF_EDIT_UNSAVED, PDF_EDIT_UNSAVED_CONFIRM,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        
        # Laufende Worker sauber beenden bevor der Dialog zerstoert wird
        for worker_attr in ('_save_worker', '_refresh_data_worker'):
            worker = getattr(self, worker_attr, None)
            if worker and worker.isRunning():
                worker.quit()
                worker.wait(3000)
        
        # Cleanup
        if self._fitz_doc:
            try:
                self._fitz_doc.close()
            except Exception:
                pass
        
        # Temp-Dateien aufraemen (beide alternierenden + save-Datei)
        temp_dir = tempfile.gettempdir()
        for suffix in ['_a.pdf', '_b.pdf']:
            p = os.path.join(temp_dir, f'bipro_edit_{os.getpid()}{suffix}')
            if os.path.exists(p):
                try:
                    os.unlink(p)
                except Exception:
                    pass
        
        save_path = os.path.join(temp_dir, f'bipro_save_{self._doc_id}.pdf') if self._doc_id else None
        if save_path and os.path.exists(save_path):
            try:
                os.unlink(save_path)
            except Exception:
                pass
        
        super().closeEvent(event)


__all__ = [
    "HAS_PDF_VIEW",
    "HAS_WEBENGINE",
    "_ThumbnailWorker",
    "PDFSaveWorker",
    "PDFRefreshWorker",
    "PDFViewerDialog",
]
