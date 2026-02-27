"""
ACENCIA ATLAS - Draggable Document Table View

Extrahiert aus archive_boxes_view.py:
- DraggableDocumentView
"""

from PySide6.QtWidgets import QTableView, QApplication
from PySide6.QtCore import Qt, QMimeData
from PySide6.QtGui import QDrag, QFont, QColor, QPainter

from ui.archive.models import DocumentTableModel

__all__ = ['DraggableDocumentView']


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
