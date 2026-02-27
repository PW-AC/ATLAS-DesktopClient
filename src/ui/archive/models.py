"""
ACENCIA ATLAS - Archiv Datenmodelle

Extrahiert aus archive_boxes_view.py:
- DocumentTableModel
- DocumentSortFilterProxy
- ColorBackgroundDelegate
"""

from typing import Optional, List

from PySide6.QtWidgets import QStyledItemDelegate
from PySide6.QtCore import (
    Qt, QAbstractTableModel, QModelIndex, QSortFilterProxyModel
)
from PySide6.QtGui import QFont, QColor, QBrush, QPainter

from api.documents import Document, BOX_DISPLAY_NAMES, BOX_COLORS
from ui.styles.tokens import SUCCESS, ERROR, INFO, DOCUMENT_DISPLAY_COLORS
from utils.date_utils import format_date_german


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

        box_emojis = {
            'gdv': '📊', 'courtage': '💰', 'sach': '🏠', 'leben': '❤️',
            'kranken': '🏥', 'sonstige': '📁', 'roh': '📦', 'eingang': '📬',
            'verarbeitung': '📥', 'falsch': '⚠️'
        }
        box_emoji = box_emojis.get(box_type, '📁') if box_type else '📁'
        box_display = BOX_DISPLAY_NAMES.get(box_type, box_type) if box_type else ''

        date_display = ''
        if created_at:
            try:
                date_part = created_at[:10]  # YYYY-MM-DD
                parts = date_part.split('-')
                if len(parts) == 3:
                    date_display = f"{parts[2]}.{parts[1]}.{parts[0]}"
            except (IndexError, ValueError):
                date_display = created_at[:10] if created_at else ''

        meta_parts = []
        if box_display:
            meta_parts.append(f"{box_emoji} {escape(box_display)}")
        if date_display:
            meta_parts.append(date_display)
        if is_archived:
            meta_parts.append(f"📦 {DUPLICATE_TOOLTIP_ARCHIVED}")
        meta_line = " &nbsp;|&nbsp; ".join(meta_parts) if meta_parts else ''

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
            left_doc = model.data(left, Qt.ItemDataRole.UserRole)
            right_doc = model.data(right, Qt.ItemDataRole.UserRole)
            left_val = left_doc.created_at or "" if left_doc else ""
            right_val = right_doc.created_at or "" if right_doc else ""
            return left_val < right_val
        
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


__all__ = [
    'DocumentTableModel',
    'DocumentSortFilterProxy',
    'ColorBackgroundDelegate',
]
