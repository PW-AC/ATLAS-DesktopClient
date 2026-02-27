"""
ACENCIA ATLAS - Box Sidebar Navigation

Extrahiert aus archive_boxes_view.py:
- BoxSidebar
"""

from typing import Optional, Dict

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QFrame,
    QTreeWidget, QTreeWidgetItem, QMenu,
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QAction, QFont, QColor, QBrush

from api.documents import BOX_COLORS, BoxStats
from ui.styles.tokens import (
    PRIMARY_900, PRIMARY_500, PRIMARY_100,
    ACCENT_500, ACCENT_100,
    TEXT_PRIMARY, TEXT_SECONDARY,
    BG_PRIMARY, BORDER_DEFAULT,
    FONT_BODY, FONT_MONO,
    FONT_SIZE_BODY, FONT_SIZE_CAPTION,
    RADIUS_MD,
)

__all__ = ['BoxSidebar']


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
