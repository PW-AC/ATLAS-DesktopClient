"""
BiPRO-GDV Tool - GDV Editor View

Der GDV-Editor als eigenständiges Widget für das Hauptfenster.
Basiert auf dem bestehenden GDV-Editor Code.

Design: ACENCIA Corporate Identity
"""

import os
import tempfile
from typing import Optional, List

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTableWidget, QTableWidgetItem, QHeaderView, QLabel,
    QComboBox, QPushButton, QFileDialog, QMessageBox,
    QStackedWidget, QFrame, QToolBar, QGroupBox, QTabBar
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QColor

from api.client import APIClient
from api.gdv_api import GDVAPI
from api.documents import DocumentsAPI

from parser.gdv_parser import ParsedFile, ParsedRecord, parse_file, save_file, create_empty_record
from domain.mapper import map_parsed_file_to_gdv_data
from layouts.gdv_layouts import get_layout, get_all_satzarten, get_anrede_bezeichnung, get_sparten_bezeichnung

# ACENCIA Design Tokens
from ui.styles.tokens import (
    PRIMARY_900, PRIMARY_500, PRIMARY_100, PRIMARY_0,
    ACCENT_500,
    TEXT_PRIMARY, TEXT_SECONDARY,
    BG_PRIMARY, BG_SECONDARY, BORDER_DEFAULT,
    SUCCESS, WARNING, ERROR,
    FONT_HEADLINE, FONT_BODY, FONT_MONO,
    FONT_SIZE_H2, FONT_SIZE_BODY, FONT_SIZE_CAPTION,
    RADIUS_MD,
    get_button_primary_style, get_button_secondary_style, get_button_ghost_style
)


class RecordTableWidget(QTableWidget):
    """Tabelle für GDV-Records."""
    
    record_selected = Signal(object)  # ParsedRecord
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self._records: List[ParsedRecord] = []
        self._filter_satzart = ""
        
        self.setColumnCount(6)
        self.setHorizontalHeaderLabels([
            "Zeile", "Satzart", "TD", "Sparte", "Beschreibung", "Schlüsselinfo"
        ])
        
        header = self.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.setAlternatingRowColors(True)
        
        self.itemSelectionChanged.connect(self._on_selection_changed)
    
    def set_records(self, records: List[ParsedRecord]):
        """Setzt die Records und aktualisiert die Tabelle."""
        self._records = records
        self._refresh_table()
    
    def set_filter(self, satzart: str):
        """Setzt den Satzart-Filter."""
        self._filter_satzart = satzart
        self._refresh_table()
    
    def _refresh_table(self):
        """Aktualisiert die Tabelle."""
        self.setRowCount(0)
        
        for record in self._records:
            if self._filter_satzart and record.satzart != self._filter_satzart:
                continue
            
            row = self.rowCount()
            self.insertRow(row)
            
            # Zeile
            item = QTableWidgetItem(str(record.line_number))
            item.setData(Qt.ItemDataRole.UserRole, record)
            self.setItem(row, 0, item)
            
            # Satzart
            self.setItem(row, 1, QTableWidgetItem(record.satzart))
            
            # Teildatensatz (aus Feld oder Position 256)
            td = record.get_field_value('teildatensatz', '1')
            if not td and len(record.raw_line) >= 256:
                td = record.raw_line[255]  # Position 256 (0-basiert: 255)
            self.setItem(row, 2, QTableWidgetItem(str(td or '1')))
            
            # Sparte
            sparte = record.fields.get('sparte', '')
            sparte_text = get_sparten_bezeichnung(sparte) if sparte else ""
            self.setItem(row, 3, QTableWidgetItem(sparte_text))
            
            # Beschreibung
            desc = self._get_record_description(record)
            self.setItem(row, 4, QTableWidgetItem(desc))
            
            # Schlüsselinfo
            key_info = self._get_key_info(record)
            self.setItem(row, 5, QTableWidgetItem(key_info))
    
    def _get_record_description(self, record: ParsedRecord) -> str:
        """Gibt eine Beschreibung für den Record zurück."""
        satzart_names = {
            '0001': 'Vorsatz',
            '0100': 'Partnerdaten',
            '0200': 'Vertragsteil',
            '0210': 'Spartenspezifisch',
            '0220': 'Deckungsteil',
            '0230': 'Fondsanlage',
            '9999': 'Nachsatz'
        }
        return satzart_names.get(record.satzart, f'Satzart {record.satzart}')
    
    def _get_key_info(self, record: ParsedRecord) -> str:
        """Gibt Schlüsselinformationen für den Record zurück."""
        parts = []
        
        if record.satzart == '0100':
            name = record.fields.get('name1', '')
            vorname = record.fields.get('vorname', '')
            if name:
                parts.append(f"{name} {vorname}".strip())
        
        elif record.satzart in ['0200', '0210', '0220']:
            vs_nr = record.fields.get('versicherungsschein_nr', '')
            if vs_nr:
                parts.append(f"VS: {vs_nr}")
        
        return ", ".join(parts)
    
    def _on_selection_changed(self):
        """Callback bei Auswahl-Änderung."""
        items = self.selectedItems()
        if items:
            record = items[0].data(Qt.ItemDataRole.UserRole)
            if record:
                self.record_selected.emit(record)


class GDVEditorView(QWidget):
    """
    GDV-Editor View.
    
    Bietet alle Funktionen des ursprünglichen GDV-Editors:
    - Datei öffnen/speichern (lokal und Server)
    - Record-Tabelle
    - Detail-Ansicht
    - Benutzer-/Experten-Modus
    """
    
    def __init__(self, api_client: APIClient = None, parent=None):
        super().__init__(parent)
        
        self.api_client = api_client
        self.gdv_api = GDVAPI(api_client) if api_client else None
        self.docs_api = DocumentsAPI(api_client) if api_client else None
        
        self._parsed_file: Optional[ParsedFile] = None
        self._current_filepath: Optional[str] = None
        self._server_doc_id: Optional[int] = None
        self._has_unsaved_changes = False
        self._expert_mode = False
        
        self._setup_ui()
    
    def _setup_ui(self):
        """UI aufbauen (ACENCIA Design)."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Toolbar (ACENCIA Style)
        toolbar = QFrame()
        toolbar.setStyleSheet(f"""
            QFrame {{
                background-color: {BG_SECONDARY};
                border-bottom: 1px solid {BORDER_DEFAULT};
            }}
        """)
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(16, 12, 16, 12)
        
        # Titel (ACENCIA Style)
        title = QLabel("GDV Editor")
        title.setStyleSheet(f"""
            font-family: {FONT_HEADLINE};
            font-size: {FONT_SIZE_H2};
            color: {TEXT_PRIMARY};
            font-weight: 400;
        """)
        toolbar_layout.addWidget(title)
        
        toolbar_layout.addStretch()
        
        # Buttons (ACENCIA Style)
        self.btn_new = QPushButton("Neu")
        self.btn_new.setStyleSheet(get_button_ghost_style())
        self.btn_new.clicked.connect(self._on_new)
        toolbar_layout.addWidget(self.btn_new)
        
        self.btn_open = QPushButton("Öffnen")
        self.btn_open.setStyleSheet(get_button_secondary_style())
        self.btn_open.clicked.connect(self._on_open)
        toolbar_layout.addWidget(self.btn_open)
        
        self.btn_save = QPushButton("Speichern")
        self.btn_save.setStyleSheet(get_button_primary_style())
        self.btn_save.clicked.connect(self._on_save)
        toolbar_layout.addWidget(self.btn_save)
        
        toolbar_layout.addSpacing(20)
        
        self.btn_upload = QPushButton("Ins Archiv")
        self.btn_upload.setStyleSheet(get_button_ghost_style())
        self.btn_upload.clicked.connect(self._on_upload_to_archive)
        self.btn_upload.setEnabled(False)
        if self.api_client:
            toolbar_layout.addWidget(self.btn_upload)
        
        layout.addWidget(toolbar)
        
        # Filter-Zeile (ACENCIA Style)
        filter_frame = QFrame()
        filter_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {BG_PRIMARY};
                border-bottom: 1px solid {BORDER_DEFAULT};
            }}
        """)
        filter_layout = QHBoxLayout(filter_frame)
        filter_layout.setContentsMargins(16, 8, 16, 8)
        
        # Ansicht-Auswahl als Tabs (ACENCIA Style)
        ansicht_label = QLabel("Ansicht:")
        ansicht_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: {FONT_SIZE_CAPTION};")
        filter_layout.addWidget(ansicht_label)
        
        self.view_combo = QComboBox()
        self.view_combo.setMaximumWidth(150)
        self.view_combo.addItem("Partner", "partner")
        self.view_combo.addItem("Datensätze", "records")
        self.view_combo.addItem("Experte", "expert")
        self.view_combo.currentIndexChanged.connect(self._on_view_changed)
        filter_layout.addWidget(self.view_combo)
        
        filter_layout.addSpacing(20)
        
        # Satzart-Filter
        filter_label = QLabel("Filter:")
        filter_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: {FONT_SIZE_CAPTION};")
        filter_layout.addWidget(filter_label)
        
        self.filter_combo = QComboBox()
        self.filter_combo.setMaximumWidth(180)
        self.filter_combo.addItem("Alle Satzarten", "")
        self.filter_combo.currentIndexChanged.connect(self._on_filter_changed)
        filter_layout.addWidget(self.filter_combo)
        
        filter_layout.addStretch()
        
        self.status_label = QLabel("Keine Datei geladen")
        self.status_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: {FONT_SIZE_CAPTION};")
        self.status_label.setStyleSheet("color: #666;")
        filter_layout.addWidget(self.status_label)
        
        layout.addWidget(filter_frame)
        
        # Haupt-Stack für verschiedene Ansichten
        self.main_stack = QStackedWidget()
        
        # === Partner-Ansicht (Index 0) ===
        from ui.partner_view import PartnerView
        self.partner_view = PartnerView()
        self.main_stack.addWidget(self.partner_view)
        
        # === Datensatz-Ansicht (Index 1) ===
        records_widget = QWidget()
        records_layout = QVBoxLayout(records_widget)
        records_layout.setContentsMargins(0, 0, 0, 0)
        
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Linke Seite: Record-Tabelle
        self.record_table = RecordTableWidget()
        self.record_table.record_selected.connect(self._on_record_selected)
        splitter.addWidget(self.record_table)
        
        # Rechte Seite: Detail-Ansicht
        self.detail_stack = QStackedWidget()
        
        # Benutzer-Ansicht
        from ui.user_detail_view import UserDetailWidget
        self.user_detail = UserDetailWidget()
        self.user_detail.record_changed.connect(self._on_record_changed)
        self.detail_stack.addWidget(self.user_detail)
        
        # Placeholder
        placeholder = QLabel("Wählen Sie einen Datensatz aus der Liste")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setStyleSheet("color: #999; font-size: 14px;")
        self.detail_stack.addWidget(placeholder)
        
        self.detail_stack.setCurrentIndex(1)  # Placeholder zeigen
        
        splitter.addWidget(self.detail_stack)
        splitter.setSizes([500, 700])
        
        records_layout.addWidget(splitter)
        self.main_stack.addWidget(records_widget)
        
        # === Experten-Ansicht (Index 2) - lazy load ===
        self._expert_widget = None
        self._expert_detail = None
        expert_placeholder = QLabel("Experten-Ansicht wird geladen...")
        expert_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_stack.addWidget(expert_placeholder)
        
        # Standard: Partner-Ansicht
        self.main_stack.setCurrentIndex(0)
        
        layout.addWidget(self.main_stack)
    
    def has_unsaved_changes(self) -> bool:
        """Prüft ob ungespeicherte Änderungen vorliegen."""
        return self._has_unsaved_changes
    
    def load_from_server(self, doc_id: int, filename: str):
        """Lädt eine GDV-Datei vom Server."""
        if not self.gdv_api:
            return
        
        self.status_label.setText(f"Lade {filename} vom Server...")
        
        temp_path = self.gdv_api.download_and_get_path(doc_id)
        
        if temp_path:
            self._load_file(temp_path)
            self._current_filepath = None
            self._server_doc_id = doc_id
            self.status_label.setText(f"{filename} (Server)")
            self.btn_upload.setEnabled(True)
        else:
            QMessageBox.warning(self, "Fehler", f"Datei konnte nicht geladen werden.")
    
    def _load_file(self, filepath: str):
        """Lädt eine GDV-Datei."""
        try:
            self._parsed_file = parse_file(filepath)
            self._current_filepath = filepath
            self._has_unsaved_changes = False
            
            # Filter aktualisieren
            self._update_filter_combo()
            
            # Tabellen aktualisieren
            self.record_table.set_records(self._parsed_file.records)
            if hasattr(self, '_expert_table') and self._expert_table:
                self._expert_table.set_records(self._parsed_file.records)
            
            # Partner-Ansicht aktualisieren
            self.partner_view.set_parsed_file(self._parsed_file)
            
            # Zur Partner-Ansicht wechseln (Standard)
            self.view_combo.setCurrentIndex(0)
            self.main_stack.setCurrentIndex(0)
            
            # Status
            filename = os.path.basename(filepath)
            record_count = len(self._parsed_file.records)
            self.status_label.setText(f"{filename} - {record_count} Datensätze")
            
            self.btn_upload.setEnabled(True)
            
        except Exception as e:
            QMessageBox.critical(self, "Fehler", f"Datei konnte nicht geladen werden:\n{e}")
    
    def _update_filter_combo(self):
        """Aktualisiert die Filter-Combobox."""
        self.filter_combo.clear()
        self.filter_combo.addItem("Alle Satzarten", "")
        
        if self._parsed_file:
            satzarten = set(r.satzart for r in self._parsed_file.records)
            for sa in sorted(satzarten):
                name = {
                    '0001': 'Vorsatz',
                    '0100': 'Partnerdaten', 
                    '0200': 'Vertragsteil',
                    '0210': 'Spartenspezifisch',
                    '0220': 'Deckungsteil',
                    '0230': 'Fondsanlage',
                    '9999': 'Nachsatz'
                }.get(sa, sa)
                self.filter_combo.addItem(f"{sa} - {name}", sa)
    
    def _on_new(self):
        """Neue GDV-Datei erstellen."""
        if self._has_unsaved_changes:
            reply = QMessageBox.question(
                self, "Ungespeicherte Änderungen",
                "Es gibt ungespeicherte Änderungen. Fortfahren?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        
        # Leere Datei erstellen
        self._parsed_file = ParsedFile(
            filepath='',
            filename='Neue_Datei.gdv',
            encoding='CP1252',
            total_lines=0,
            records=[]
        )
        self._current_filepath = None
        self._server_doc_id = None
        self._has_unsaved_changes = False
        
        # Vorsatz und Nachsatz hinzufügen
        vorsatz = create_empty_record('0001')
        nachsatz = create_empty_record('9999')
        self._parsed_file.records = [vorsatz, nachsatz]
        
        self._update_filter_combo()
        self.record_table.set_records(self._parsed_file.records)
        self.status_label.setText("Neue Datei (ungespeichert)")
        self.btn_upload.setEnabled(False)
    
    def _on_open(self):
        """GDV-Datei öffnen."""
        if self._has_unsaved_changes:
            reply = QMessageBox.question(
                self, "Ungespeicherte Änderungen",
                "Es gibt ungespeicherte Änderungen. Fortfahren?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "GDV-Datei öffnen",
            "",
            "GDV-Dateien (*.gdv *.txt *.dat *.vwb);;Alle Dateien (*)"
        )
        
        if filepath:
            self._load_file(filepath)
    
    def _on_save(self):
        """GDV-Datei speichern."""
        if not self._parsed_file:
            return
        
        if self._current_filepath:
            filepath = self._current_filepath
        else:
            filepath, _ = QFileDialog.getSaveFileName(
                self,
                "GDV-Datei speichern",
                "",
                "GDV-Dateien (*.gdv);;Alle Dateien (*)"
            )
            if not filepath:
                return
        
        try:
            save_file(self._parsed_file, filepath)
            self._current_filepath = filepath
            self._has_unsaved_changes = False
            self.status_label.setText(f"{os.path.basename(filepath)} - Gespeichert")
            self.btn_upload.setEnabled(True)
        except Exception as e:
            QMessageBox.critical(self, "Fehler", f"Speichern fehlgeschlagen:\n{e}")
    
    def _on_upload_to_archive(self):
        """Aktuelle Datei ins Archiv hochladen."""
        if not self.docs_api or not self._current_filepath:
            # Erst speichern
            if self._parsed_file and not self._current_filepath:
                self._on_save()
                if not self._current_filepath:
                    return
        
        if self._current_filepath:
            doc = self.docs_api.upload(self._current_filepath, 'manual_upload')
            if doc:
                QMessageBox.information(
                    self, "Erfolg",
                    f"Datei wurde ins Archiv hochgeladen."
                )
            else:
                QMessageBox.warning(self, "Fehler", "Upload fehlgeschlagen.")
    
    def _on_view_changed(self, index):
        """Ansicht geändert."""
        view_type = self.view_combo.currentData()
        
        if view_type == "partner":
            self.main_stack.setCurrentIndex(0)
            # Partner-View aktualisieren
            if self._parsed_file:
                self.partner_view.set_parsed_file(self._parsed_file)
        
        elif view_type == "records":
            self.main_stack.setCurrentIndex(1)
            self._expert_mode = False
        
        elif view_type == "expert":
            self._expert_mode = True
            # Experten-Widget erstellen falls nicht vorhanden
            if self._expert_widget is None:
                self._setup_expert_view()
            self.main_stack.setCurrentIndex(2)
    
    def _setup_expert_view(self):
        """Erstellt die Experten-Ansicht."""
        from ui.main_window import ExpertDetailWidget
        
        self._expert_widget = QWidget()
        expert_layout = QVBoxLayout(self._expert_widget)
        expert_layout.setContentsMargins(0, 0, 0, 0)
        
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Record-Tabelle (gleiche wie bei Datensatz-Ansicht)
        self._expert_table = RecordTableWidget()
        self._expert_table.record_selected.connect(self._on_expert_record_selected)
        if self._parsed_file:
            self._expert_table.set_records(self._parsed_file.records)
        splitter.addWidget(self._expert_table)
        
        # Experten-Detail-Widget
        self._expert_detail = ExpertDetailWidget()
        self._expert_detail.record_changed.connect(self._on_record_changed)
        splitter.addWidget(self._expert_detail)
        
        splitter.setSizes([500, 700])
        expert_layout.addWidget(splitter)
        
        # Alten Placeholder ersetzen
        old_widget = self.main_stack.widget(2)
        self.main_stack.removeWidget(old_widget)
        self.main_stack.insertWidget(2, self._expert_widget)
    
    def _on_expert_record_selected(self, record):
        """Record in Experten-Ansicht ausgewählt."""
        if self._expert_detail:
            self._expert_detail.set_record(record)
    
    def _on_filter_changed(self, index):
        """Filter geändert."""
        satzart = self.filter_combo.currentData() or ""
        self.record_table.set_filter(satzart)
        if hasattr(self, '_expert_table') and self._expert_table:
            self._expert_table.set_filter(satzart)
    
    def _on_record_selected(self, record: ParsedRecord):
        """Record ausgewählt."""
        if self._expert_mode and self._expert_detail:
            self._expert_detail.set_record(record)
            self.detail_stack.setCurrentWidget(self._expert_detail)
        else:
            self.user_detail.set_record(record)
            self.detail_stack.setCurrentWidget(self.user_detail)
    
    def _on_record_changed(self, record: ParsedRecord):
        """Record wurde geändert."""
        self._has_unsaved_changes = True
        self.record_table.set_records(self._parsed_file.records)
        
        filename = os.path.basename(self._current_filepath) if self._current_filepath else "Neue Datei"
        self.status_label.setText(f"{filename} * (geändert)")
