#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GDV Tool - Hauptfenster

Das Hauptfenster mit:
- Menüleiste
- Satzlisten-Tabelle (links)
- Detail-Ansicht (rechts) - umschaltbar zwischen Benutzer- und Experten-Ansicht
- Statusleiste
"""

import os
import sys
from typing import Optional, List

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTableWidget, QTableWidgetItem, QHeaderView, QLabel,
    QScrollArea, QFormLayout, QLineEdit, QComboBox, QPushButton,
    QFileDialog, QMessageBox, QStatusBar, QGroupBox, QFrame,
    QTabWidget, QToolBar, QSpacerItem, QSizePolicy, QStackedWidget
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QFont, QColor, QIcon

# Pfad zum src-Verzeichnis
_src_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from parser.gdv_parser import ParsedFile, ParsedRecord, parse_file, create_empty_record
from domain.mapper import map_parsed_file_to_gdv_data
from domain.models import GDVData
from layouts.gdv_layouts import (
    get_layout, get_all_satzarten, SPARTEN_BEZEICHNUNGEN, 
    get_anrede_bezeichnung, get_sparten_bezeichnung
)
from ui.user_detail_view import UserDetailWidget
from ui.partner_view import PartnerView
from ui.archive_view import ArchiveView
from ui.bipro_view import BiPROView


class ExpertDetailWidget(QWidget):
    """Experten-Ansicht: Zeigt alle Felder eines Records."""
    
    record_changed = Signal(ParsedRecord)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_record = None
        self._field_editors = {}
        self._toast_manager = None
        self._setup_ui()
    
    def _setup_ui(self):
        """Erstellt die UI-Elemente."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Header
        header_layout = QHBoxLayout()
        self._header_label = QLabel("Kein Satz ausgewählt")
        self._header_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        self._header_label.setStyleSheet("color: #333; padding: 10px 0;")
        header_layout.addWidget(self._header_label)
        
        expert_badge = QLabel("⚙️ EXPERTEN-ANSICHT")
        expert_badge.setStyleSheet("""
            background-color: #ff9800;
            color: white;
            padding: 4px 10px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: bold;
        """)
        header_layout.addWidget(expert_badge)
        header_layout.addStretch()
        
        layout.addLayout(header_layout)
        
        # Info-Zeile
        self._info_label = QLabel("")
        self._info_label.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(self._info_label)
        
        # Trennlinie
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("background-color: #ddd;")
        layout.addWidget(line)
        
        # Scroll-Bereich für Felder
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        
        self._fields_container = QWidget()
        self._fields_layout = QFormLayout(self._fields_container)
        self._fields_layout.setSpacing(8)
        self._fields_layout.setContentsMargins(0, 10, 0, 10)
        
        scroll.setWidget(self._fields_container)
        layout.addWidget(scroll, 1)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self._apply_btn = QPushButton("Änderungen übernehmen")
        self._apply_btn.setStyleSheet("""
            QPushButton {
                background-color: #ff9800;
                color: white;
                padding: 8px 16px;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #f57c00;
            }
            QPushButton:disabled {
                background-color: #ccc;
            }
        """)
        self._apply_btn.clicked.connect(self._on_apply_changes)
        self._apply_btn.setEnabled(False)
        btn_layout.addWidget(self._apply_btn)
        
        self._reset_btn = QPushButton("Zurücksetzen")
        self._reset_btn.setStyleSheet("""
            QPushButton {
                background-color: #f0f0f0;
                color: #333;
                padding: 8px 16px;
                border: 1px solid #ccc;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
        """)
        self._reset_btn.clicked.connect(self._on_reset)
        self._reset_btn.setEnabled(False)
        btn_layout.addWidget(self._reset_btn)
        
        layout.addLayout(btn_layout)
    
    def set_record(self, record):
        """Zeigt die Details eines Records an."""
        self._current_record = record
        self._field_editors.clear()
        
        while self._fields_layout.count():
            item = self._fields_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        if not record:
            self._header_label.setText("Kein Satz ausgewählt")
            self._info_label.setText("")
            self._apply_btn.setEnabled(False)
            self._reset_btn.setEnabled(False)
            return
        
        # Teildatensatz ermitteln
        teildatensatz = None
        if "satznummer" in record.fields:
            satznr_val = record.fields["satznummer"].value
            if satznr_val and str(satznr_val).strip().isdigit():
                teildatensatz = str(satznr_val).strip()
        
        self._header_label.setText(f"Satzart {record.satzart}: {record.satzart_name}")
        self._info_label.setText(f"Zeile {record.line_number} | {len(record.fields)} Felder | Alle Felder editierbar")
        
        # Layout mit Teildatensatz-Unterstützung holen
        layout_def = get_layout(record.satzart, teildatensatz)
        
        for field_name, parsed_field in record.fields.items():
            label_text = parsed_field.label
            if layout_def:
                field_def = next((f for f in layout_def["fields"] if f["name"] == field_name), None)
                if field_def and field_def.get("required"):
                    label_text += " *"
            
            label = QLabel(label_text)
            label.setStyleSheet("font-weight: 500; color: #333;")
            
            editor = QLineEdit()
            value = parsed_field.value
            
            display_value = ""
            if value is not None:
                if isinstance(value, float):
                    display_value = f"{value:.2f}"
                else:
                    display_value = str(value).strip()
            
            if field_name == "anrede_schluessel" and display_value:
                anrede_text = get_anrede_bezeichnung(display_value)
                if anrede_text:
                    display_value = f"{display_value} ({anrede_text})"
            elif field_name == "sparte" and display_value:
                sparte_text = get_sparten_bezeichnung(display_value)
                display_value = f"{display_value} ({sparte_text})"
            
            editor.setText(display_value)
            
            tooltip = (
                f"Feld: {field_name}\n"
                f"Typ: {parsed_field.field_type}\n"
                f"Position: {parsed_field.start}-{parsed_field.start + parsed_field.length - 1}\n"
                f"Länge: {parsed_field.length}\n"
                f"Rohwert: '{parsed_field.raw_value[:50]}...'" if len(parsed_field.raw_value) > 50 else f"Rohwert: '{parsed_field.raw_value}'"
            )
            editor.setToolTip(tooltip)
            
            editor.setStyleSheet("""
                QLineEdit {
                    padding: 6px;
                    border: 1px solid #ccc;
                    border-radius: 4px;
                }
                QLineEdit:focus {
                    border-color: #ff9800;
                }
            """)
            
            self._field_editors[field_name] = editor
            self._fields_layout.addRow(label, editor)
        
        self._apply_btn.setEnabled(True)
        self._reset_btn.setEnabled(True)
    
    def _on_apply_changes(self):
        if not self._current_record:
            return
        
        for field_name, editor in self._field_editors.items():
            new_value = editor.text()
            
            # Klammern entfernen bei Schlüsselfeldern
            if "(" in new_value:
                new_value = new_value.split("(")[0].strip()
            
            if field_name in self._current_record.fields:
                parsed_field = self._current_record.fields[field_name]
                
                if parsed_field.field_type == "N":
                    try:
                        if "." in new_value or "," in new_value:
                            parsed_field.value = float(new_value.replace(",", "."))
                        elif new_value.strip():
                            parsed_field.value = new_value.strip()
                        else:
                            parsed_field.value = None
                    except ValueError:
                        parsed_field.value = new_value
                else:
                    parsed_field.value = new_value if new_value else None
        
        self.record_changed.emit(self._current_record)
        if self._toast_manager:
            self._toast_manager.show_success(
                "Änderungen übernommen. Speichern Sie die Datei, um sie dauerhaft zu sichern."
            )
    
    def _on_reset(self):
        if self._current_record:
            self.set_record(self._current_record)


class RecordTableWidget(QTableWidget):
    """Tabelle zur Anzeige aller Records."""
    
    record_selected = Signal(ParsedRecord)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._records = []
        self._filtered_records = []
        self._current_filter = ""
        self._setup_ui()
    
    def _setup_ui(self):
        self.setColumnCount(5)
        self.setHorizontalHeaderLabels(["Zeile", "Satzart", "Bezeichnung", "Schlüsselfeld 1", "Schlüsselfeld 2"])
        
        header = self.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        
        self.setColumnWidth(0, 60)
        self.setColumnWidth(1, 70)
        
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.verticalHeader().setVisible(False)
        
        self.setStyleSheet("""
            QTableWidget {
                border: 1px solid #ddd;
                gridline-color: #eee;
            }
            QTableWidget::item { padding: 6px; }
            QTableWidget::item:selected {
                background-color: #1a73e8;
                color: white;
            }
            QHeaderView::section {
                background-color: #f5f5f5;
                padding: 8px;
                border: none;
                border-bottom: 2px solid #ddd;
                font-weight: bold;
            }
        """)
        
        self.itemSelectionChanged.connect(self._on_selection_changed)
    
    def set_records(self, records):
        self._records = records
        self._apply_filter()
    
    def set_filter(self, satzart):
        self._current_filter = satzart
        self._apply_filter()
    
    def _apply_filter(self):
        if self._current_filter and self._current_filter != "Alle":
            self._filtered_records = [r for r in self._records if r.satzart == self._current_filter]
        else:
            self._filtered_records = self._records.copy()
        self._populate_table()
    
    def _populate_table(self):
        self.setRowCount(len(self._filtered_records))
        
        for row, record in enumerate(self._filtered_records):
            item = QTableWidgetItem(str(record.line_number))
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.setItem(row, 0, item)
            
            item = QTableWidgetItem(record.satzart)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            colors = {
                "0001": "#e3f2fd", "0100": "#e8f5e9", "0200": "#fff3e0",
                "0210": "#fce4ec", "0220": "#f3e5f5", "0230": "#e0f7fa",
                "9999": "#fafafa"
            }
            if record.satzart in colors:
                item.setBackground(QColor(colors[record.satzart]))
            self.setItem(row, 1, item)
            
            # Satzart-Name mit Teildatensatz-Info
            satzart_name = record.satzart_name
            self.setItem(row, 2, QTableWidgetItem(satzart_name))
            
            key1 = key2 = ""
            
            if record.satzart == "0001":
                key1 = str(record.get_field_value("absender", "") or "").strip()
                key2 = str(record.get_field_value("adressat", "") or "").strip()
            elif record.satzart == "0100":
                anrede = get_anrede_bezeichnung(str(record.get_field_value("anrede_schluessel", "") or ""))
                name1 = str(record.get_field_value("name1", "") or "").strip()
                name2 = str(record.get_field_value("name2", "") or "").strip()
                name3 = str(record.get_field_value("name3", "") or "").strip()
                vorname = name2 if name2 and not name3 else name3
                if anrede and name1:
                    key1 = f"{anrede} {vorname} {name1}".strip() if vorname else f"{anrede} {name1}"
                elif name1:
                    key1 = f"{vorname} {name1}".strip() if vorname else name1
                else:
                    key1 = vorname or ""
                key2 = str(record.get_field_value("ort", "") or "").strip()
            elif record.satzart == "0200":
                key1 = str(record.get_field_value("versicherungsschein_nr", "") or "").strip()
                sparte = str(record.get_field_value("sparte", "") or "").strip()
                key2 = get_sparten_bezeichnung(sparte)
            elif record.satzart == "0210":
                key1 = str(record.get_field_value("versicherungsschein_nr", "") or "").strip()
                key2 = str(record.get_field_value("waehrung", "") or "").strip()
            elif record.satzart == "0220":
                key1 = str(record.get_field_value("versicherungsschein_nr", "") or "").strip()
                name = str(record.get_field_value("name", "") or "").strip()
                vorname = str(record.get_field_value("vorname", "") or "").strip()
                key2 = f"{vorname} {name}".strip() if vorname or name else ""
            elif record.satzart == "0230":
                key1 = str(record.get_field_value("versicherungsschein_nr", "") or "").strip()
                key2 = str(record.get_field_value("fonds_name", "") or "").strip()
            elif record.satzart == "9999":
                key1 = str(record.get_field_value("anzahl_saetze", "") or "").strip() + " Sätze"
                key2 = ""
            
            self.setItem(row, 3, QTableWidgetItem(str(key1) if key1 else ""))
            self.setItem(row, 4, QTableWidgetItem(str(key2) if key2 else ""))
    
    def _on_selection_changed(self):
        selected = self.selectedItems()
        if selected:
            row = selected[0].row()
            if 0 <= row < len(self._filtered_records):
                self.record_selected.emit(self._filtered_records[row])
    
    def get_current_record(self):
        selected = self.selectedItems()
        if selected:
            row = selected[0].row()
            if 0 <= row < len(self._filtered_records):
                return self._filtered_records[row]
        return None


class GDVMainWindow(QMainWindow):
    """Hauptfenster der GDV-Anwendung."""
    
    def __init__(self, api_client=None, auth_api=None):
        super().__init__()
        
        # API-Verbindung (optional, für Server-Funktionen)
        self._api_client = api_client
        self._auth_api = auth_api
        
        self._parsed_file = None
        self._gdv_data = None
        self._current_filepath = None
        self._server_doc_id = None  # Dokument-ID wenn vom Server geladen
        self._has_unsaved_changes = False
        self._expert_mode = False
        self._partner_view_mode = False
        self._toast_manager = None
        
        # Fenstertitel mit Benutzername falls eingeloggt
        if auth_api and auth_api.current_user:
            title = f"ACENCIA ATLAS - {auth_api.current_user.username}"
        else:
            title = "ACENCIA ATLAS"
        self.setWindowTitle(title)
        self.setMinimumSize(1400, 900)
        
        self._setup_ui()
        self._setup_menu()
        self._setup_toolbar()
        self._setup_statusbar()
        self._update_window_title()
    
    def _setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Filter-Leiste
        filter_widget = QWidget()
        filter_widget.setStyleSheet("background-color: #f5f5f5; border-bottom: 1px solid #ddd;")
        filter_layout = QHBoxLayout(filter_widget)
        filter_layout.setContentsMargins(10, 8, 10, 8)
        
        filter_label = QLabel("Filter Satzart:")
        filter_label.setStyleSheet("font-weight: bold;")
        filter_layout.addWidget(filter_label)
        
        self._filter_combo = QComboBox()
        self._filter_combo.addItem("Alle")
        for satzart in get_all_satzarten():
            layout = get_layout(satzart)
            if layout:
                self._filter_combo.addItem(f"{satzart} - {layout['name']}", satzart)
        self._filter_combo.setMinimumWidth(200)
        self._filter_combo.currentIndexChanged.connect(self._on_filter_changed)
        filter_layout.addWidget(self._filter_combo)
        
        filter_layout.addStretch()
        
        self._stats_label = QLabel("Keine Datei geladen")
        self._stats_label.setStyleSheet("color: #666;")
        filter_layout.addWidget(self._stats_label)
        
        main_layout.addWidget(filter_widget)
        
        # Haupt-Stack für verschiedene Ansichten
        self._main_stack = QStackedWidget()
        
        # === Ansicht 1: Satz-Ansicht (bisherige Ansicht) ===
        satz_view = QWidget()
        satz_layout = QVBoxLayout(satz_view)
        satz_layout.setContentsMargins(0, 0, 0, 0)
        
        # Splitter für Tabelle und Details
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Linke Seite: Tabelle
        table_container = QWidget()
        table_layout = QVBoxLayout(table_container)
        table_layout.setContentsMargins(10, 10, 5, 10)
        
        self._record_table = RecordTableWidget()
        self._record_table.record_selected.connect(self._on_record_selected)
        table_layout.addWidget(self._record_table)
        
        splitter.addWidget(table_container)
        
        # Rechte Seite: Stacked Widget für Benutzer-/Experten-Ansicht
        detail_container = QWidget()
        detail_layout = QVBoxLayout(detail_container)
        detail_layout.setContentsMargins(5, 10, 10, 10)
        
        self._detail_stack = QStackedWidget()
        
        # Benutzer-Ansicht (Standard)
        self._user_detail = UserDetailWidget()
        self._user_detail.record_changed.connect(self._on_record_changed)
        self._detail_stack.addWidget(self._user_detail)
        
        # Experten-Ansicht
        self._expert_detail = ExpertDetailWidget()
        self._expert_detail.record_changed.connect(self._on_record_changed)
        self._detail_stack.addWidget(self._expert_detail)
        
        detail_layout.addWidget(self._detail_stack)
        splitter.addWidget(detail_container)
        
        splitter.setSizes([700, 500])
        satz_layout.addWidget(splitter, 1)
        
        self._main_stack.addWidget(satz_view)
        
        # === Ansicht 2: Partner-Ansicht (NEU) ===
        self._partner_view = PartnerView()
        self._main_stack.addWidget(self._partner_view)
        
        main_layout.addWidget(self._main_stack, 1)
    
    def _setup_menu(self):
        menubar = self.menuBar()
        
        # Datei-Menü
        file_menu = menubar.addMenu("&Datei")
        
        open_action = QAction("GDV-Datei &öffnen...", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self._on_open_file)
        file_menu.addAction(open_action)
        
        new_action = QAction("&Neue GDV-Datei", self)
        new_action.setShortcut("Ctrl+N")
        new_action.triggered.connect(self._on_new_file)
        file_menu.addAction(new_action)
        
        file_menu.addSeparator()
        
        save_action = QAction("&Speichern", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self._on_save_file)
        file_menu.addAction(save_action)
        
        save_as_action = QAction("Speichern &unter...", self)
        save_as_action.setShortcut("Ctrl+Shift+S")
        save_as_action.triggered.connect(self._on_save_file_as)
        file_menu.addAction(save_as_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("&Beenden", self)
        exit_action.setShortcut("Alt+F4")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Bearbeiten-Menü
        edit_menu = menubar.addMenu("&Bearbeiten")
        
        add_record_action = QAction("Neuen &Satz hinzufügen...", self)
        add_record_action.setShortcut("Ctrl+Shift+N")
        add_record_action.triggered.connect(self._on_add_record)
        edit_menu.addAction(add_record_action)
        
        delete_record_action = QAction("Satz &löschen", self)
        delete_record_action.setShortcut("Delete")
        delete_record_action.triggered.connect(self._on_delete_record)
        edit_menu.addAction(delete_record_action)
        
        # Ansicht-Menü
        view_menu = menubar.addMenu("&Ansicht")
        
        # Partner-Ansicht (NEU)
        self._partner_view_action = QAction("👥 Partner-Ansicht", self)
        self._partner_view_action.setShortcut("Ctrl+P")
        self._partner_view_action.setCheckable(True)
        self._partner_view_action.setChecked(False)
        self._partner_view_action.triggered.connect(self._toggle_partner_view)
        view_menu.addAction(self._partner_view_action)
        
        view_menu.addSeparator()
        
        self._expert_action = QAction("⚙️ Experten-Ansicht", self)
        self._expert_action.setShortcut("Ctrl+E")
        self._expert_action.setCheckable(True)
        self._expert_action.setChecked(False)
        self._expert_action.triggered.connect(self._toggle_expert_mode)
        view_menu.addAction(self._expert_action)
        
        # Server-Menü (nur wenn API-Client vorhanden)
        if self._api_client:
            server_menu = menubar.addMenu("&Server")
            
            bipro_action = QAction("🔄 BiPRO Datenabruf...", self)
            bipro_action.setShortcut("Ctrl+B")
            bipro_action.triggered.connect(self._on_open_bipro)
            server_menu.addAction(bipro_action)
            
            archive_action = QAction("📁 Dokumentenarchiv...", self)
            archive_action.setShortcut("Ctrl+D")
            archive_action.triggered.connect(self._on_open_archive)
            server_menu.addAction(archive_action)
            
            server_menu.addSeparator()
            
            upload_action = QAction("📤 Dokument hochladen...", self)
            upload_action.triggered.connect(self._on_upload_to_archive)
            server_menu.addAction(upload_action)
            
            server_menu.addSeparator()
            
            logout_action = QAction("🚪 Abmelden", self)
            logout_action.triggered.connect(self._on_logout)
            server_menu.addAction(logout_action)
        
        # Hilfe-Menü
        help_menu = menubar.addMenu("&Hilfe")
        
        about_action = QAction("Ü&ber ACENCIA ATLAS", self)
        about_action.triggered.connect(self._on_about)
        help_menu.addAction(about_action)
    
    def _setup_toolbar(self):
        toolbar = QToolBar("Hauptwerkzeugleiste")
        toolbar.setMovable(False)
        toolbar.setStyleSheet("""
            QToolBar {
                background-color: #f5f5f5;
                border-bottom: 1px solid #ddd;
                padding: 4px;
                spacing: 4px;
            }
            QToolButton {
                padding: 6px 12px;
                border-radius: 4px;
            }
            QToolButton:hover { background-color: #e0e0e0; }
        """)
        self.addToolBar(toolbar)
        
        open_action = toolbar.addAction("📂 Öffnen")
        open_action.triggered.connect(self._on_open_file)
        
        save_action = toolbar.addAction("💾 Speichern")
        save_action.triggered.connect(self._on_save_file)
        
        toolbar.addSeparator()
        
        add_action = toolbar.addAction("➕ Neuer Satz")
        add_action.triggered.connect(self._on_add_record)
        
        delete_action = toolbar.addAction("🗑️ Löschen")
        delete_action.triggered.connect(self._on_delete_record)
        
        toolbar.addSeparator()
        
        # Partner-Ansicht Button (NEU)
        self._partner_view_btn = toolbar.addAction("👥 Partner-Ansicht")
        self._partner_view_btn.setCheckable(True)
        self._partner_view_btn.triggered.connect(self._toggle_partner_view)
        
        toolbar.addSeparator()
        
        # Experten-Modus Button
        self._expert_btn = toolbar.addAction("⚙️ Experten-Ansicht")
        self._expert_btn.setCheckable(True)
        self._expert_btn.triggered.connect(self._toggle_expert_mode)
    
    def _setup_statusbar(self):
        self._statusbar = self.statusBar()
        self._statusbar.showMessage("Bereit - Keine Datei geladen")
    
    def _toggle_expert_mode(self, checked=None):
        if checked is None:
            checked = not self._expert_mode
        
        self._expert_mode = checked
        self._expert_action.setChecked(checked)
        self._expert_btn.setChecked(checked)
        
        # Ansicht wechseln
        if checked:
            self._detail_stack.setCurrentWidget(self._expert_detail)
            self._statusbar.showMessage("⚙️ Experten-Ansicht aktiv - Alle Felder editierbar", 3000)
        else:
            self._detail_stack.setCurrentWidget(self._user_detail)
            self._statusbar.showMessage("Benutzer-Ansicht aktiv", 3000)
        
        # Aktuelles Record neu anzeigen
        record = self._record_table.get_current_record()
        if record:
            if self._expert_mode:
                self._expert_detail.set_record(record)
            else:
                self._user_detail.set_record(record)
    
    def _toggle_partner_view(self, checked=None):
        """Wechselt zwischen Satz-Ansicht und Partner-Ansicht."""
        if checked is None:
            checked = not self._partner_view_mode
        
        self._partner_view_mode = checked
        self._partner_view_action.setChecked(checked)
        self._partner_view_btn.setChecked(checked)
        
        if checked:
            # Zur Partner-Ansicht wechseln
            self._main_stack.setCurrentWidget(self._partner_view)
            self._statusbar.showMessage("👥 Partner-Ansicht aktiv - Alle Partner auf einen Blick", 3000)
            # Partner-Daten aktualisieren
            if self._parsed_file:
                self._partner_view.set_parsed_file(self._parsed_file)
        else:
            # Zur Satz-Ansicht wechseln
            self._main_stack.setCurrentIndex(0)
            self._statusbar.showMessage("Satz-Ansicht aktiv", 3000)
    
    def _update_window_title(self):
        title = "GDV Tool v0.3.0"
        if self._current_filepath:
            filename = os.path.basename(self._current_filepath)
            title = f"{filename} - {title}"
        if self._has_unsaved_changes:
            title = f"* {title}"
        self.setWindowTitle(title)
    
    def _update_statistics(self):
        if not self._parsed_file:
            self._stats_label.setText("Keine Datei geladen")
            return
        
        counts = self._parsed_file.get_record_count_by_satzart()
        total = len(self._parsed_file.records)
        
        parts = [f"Gesamt: {total} Sätze"]
        for satzart in sorted(counts.keys()):
            parts.append(f"{satzart}: {counts[satzart]}")
        
        self._stats_label.setText(" | ".join(parts))
    
    def _on_open_file(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self, "GDV-Datei öffnen", "",
            "GDV-Dateien (*.gdv *.txt *.dat *.vwb *.TXT *.DAT *.VWB);;Alle Dateien (*.*)"
        )
        if filepath:
            self._load_file(filepath)
    
    def _load_file(self, filepath):
        try:
            self._statusbar.showMessage(f"Lade {filepath}...")
            
            self._parsed_file = parse_file(filepath)
            self._current_filepath = filepath
            
            if self._parsed_file.errors:
                if self._toast_manager:
                    self._toast_manager.show_warning(
                        "Warnungen beim Laden: " + "; ".join(self._parsed_file.errors[:3])
                    )
            
            self._gdv_data = map_parsed_file_to_gdv_data(self._parsed_file)
            
            self._record_table.set_records(self._parsed_file.records)
            self._user_detail.set_record(None)
            self._expert_detail.set_record(None)
            self._filter_combo.setCurrentIndex(0)
            
            # Partner-Ansicht aktualisieren (auch wenn nicht aktiv)
            self._partner_view.set_parsed_file(self._parsed_file)
            
            self._has_unsaved_changes = False
            self._update_window_title()
            self._update_statistics()
            
            self._statusbar.showMessage(f"Datei geladen: {len(self._parsed_file.records)} Sätze", 5000)
            
        except Exception as e:
            if self._toast_manager:
                self._toast_manager.show_error(f"Fehler beim Laden: {str(e)}")
            self._statusbar.showMessage("Fehler beim Laden der Datei")
    
    def _on_new_file(self):
        if self._has_unsaved_changes:
            reply = QMessageBox.question(self, "Ungespeicherte Änderungen",
                "Es gibt ungespeicherte Änderungen. Fortfahren?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply != QMessageBox.StandardButton.Yes:
                return
        
        self._parsed_file = ParsedFile(filepath="", filename="Neue Datei.gdv",
            encoding="latin-1", total_lines=0)
        
        vorsatz = create_empty_record("0001", 1)
        if vorsatz:
            self._parsed_file.records.append(vorsatz)
        
        self._current_filepath = None
        self._gdv_data = map_parsed_file_to_gdv_data(self._parsed_file)
        
        self._record_table.set_records(self._parsed_file.records)
        self._user_detail.set_record(None)
        self._expert_detail.set_record(None)
        
        self._has_unsaved_changes = True
        self._update_window_title()
        self._update_statistics()
        self._statusbar.showMessage("Neue Datei erstellt")
    
    def _on_save_file(self):
        if not self._current_filepath:
            self._on_save_file_as()
            return
        self._save_to_file(self._current_filepath)
    
    def _on_save_file_as(self):
        if not self._parsed_file:
            if self._toast_manager:
                self._toast_manager.show_warning("Keine Datei zum Speichern vorhanden.")
            return
        
        filepath, _ = QFileDialog.getSaveFileName(self, "GDV-Datei speichern",
            self._current_filepath or "export.gdv",
            "GDV-Dateien (*.gdv);;Textdateien (*.txt);;Alle Dateien (*.*)")
        
        if filepath:
            self._save_to_file(filepath)
    
    def _save_to_file(self, filepath):
        try:
            from parser.gdv_parser import save_file
            self._parsed_file.filepath = filepath
            success = save_file(self._parsed_file, filepath)
            
            if success:
                self._current_filepath = filepath
                self._has_unsaved_changes = False
                self._update_window_title()
                self._statusbar.showMessage(f"Datei gespeichert: {filepath}", 5000)
            else:
                raise Exception("Speichern fehlgeschlagen")
        except Exception as e:
            if self._toast_manager:
                self._toast_manager.show_error(f"Fehler beim Speichern: {str(e)}")
    
    def _on_add_record(self):
        if not self._parsed_file:
            if self._toast_manager:
                self._toast_manager.show_warning("Bitte zuerst eine Datei öffnen oder erstellen.")
            return
        
        from PySide6.QtWidgets import QInputDialog
        items = [f"{sa} - {get_layout(sa)['name']}" for sa in get_all_satzarten()]
        item, ok = QInputDialog.getItem(self, "Neuen Satz hinzufügen",
            "Satzart auswählen:", items, 0, False)
        
        if not ok:
            return
        
        satzart = item.split(" - ")[0]
        new_line_number = len(self._parsed_file.records) + 1
        new_record = create_empty_record(satzart, new_line_number)
        
        if new_record:
            self._parsed_file.records.append(new_record)
            self._record_table.set_records(self._parsed_file.records)
            self._has_unsaved_changes = True
            self._update_window_title()
            self._update_statistics()
            self._statusbar.showMessage(f"Neuer Satz {satzart} hinzugefügt", 3000)
    
    def _on_delete_record(self):
        record = self._record_table.get_current_record()
        if not record:
            if self._toast_manager:
                self._toast_manager.show_warning("Bitte wählen Sie einen Satz zum Löschen aus.")
            return
        
        reply = QMessageBox.question(self, "Satz löschen",
            f"Möchten Sie den Satz {record.satzart} (Zeile {record.line_number}) wirklich löschen?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        self._parsed_file.records.remove(record)
        self._record_table.set_records(self._parsed_file.records)
        self._user_detail.set_record(None)
        self._expert_detail.set_record(None)
        
        self._has_unsaved_changes = True
        self._update_window_title()
        self._update_statistics()
        self._statusbar.showMessage("Satz gelöscht", 3000)
    
    def _on_record_selected(self, record):
        if self._expert_mode:
            self._expert_detail.set_record(record)
        else:
            self._user_detail.set_record(record)
    
    def _on_record_changed(self, record):
        self._has_unsaved_changes = True
        self._update_window_title()
        self._record_table.set_records(self._parsed_file.records)
    
    def _on_filter_changed(self, index):
        if index == 0:
            self._record_table.set_filter("")
        else:
            satzart = self._filter_combo.itemData(index)
            self._record_table.set_filter(satzart)
    
    def _on_about(self):
        if self._toast_manager:
            self._toast_manager.show_info(
                "ACENCIA ATLAS - Der Datenkern. Desktop-App für BiPRO-Datenabruf und GDV-Bearbeitung. © 2025 ACENCIA GmbH"
            )
    
    # === Server/Archiv-Methoden ===
    
    def _on_open_bipro(self):
        """Öffnet das BiPRO Datenabruf-Fenster."""
        if not self._api_client:
            if self._toast_manager:
                self._toast_manager.show_warning("Keine Server-Verbindung.")
            return
        
        # BiPRO-Fenster erstellen
        self._bipro_window = QMainWindow(self)
        self._bipro_window.setWindowTitle("Datenabruf")
        self._bipro_window.setMinimumSize(1000, 700)
        
        bipro_view = BiPROView(self._api_client, self._bipro_window)
        bipro_view.documents_uploaded.connect(self._on_documents_uploaded)
        
        self._bipro_window.setCentralWidget(bipro_view)
        self._bipro_window.show()
    
    def _on_documents_uploaded(self):
        """Callback wenn neue Dokumente ins Archiv hochgeladen wurden."""
        self._statusbar.showMessage("Neue Dokumente im Archiv", 3000)
    
    def _on_open_archive(self):
        """Öffnet das Dokumentenarchiv in einem neuen Fenster."""
        if not self._api_client:
            if self._toast_manager:
                self._toast_manager.show_warning("Keine Server-Verbindung.")
            return
        
        # Archiv-Fenster erstellen
        self._archive_window = QMainWindow(self)
        self._archive_window.setWindowTitle("Dokumentenarchiv")
        self._archive_window.setMinimumSize(1000, 600)
        
        archive_view = ArchiveView(self._api_client, self._archive_window)
        archive_view._toast_manager = self._toast_manager
        archive_view.open_gdv_requested.connect(self._on_open_gdv_from_archive)
        
        self._archive_window.setCentralWidget(archive_view)
        self._archive_window.show()
    
    def _on_open_gdv_from_archive(self, doc_id: int, filename: str):
        """Öffnet eine GDV-Datei aus dem Archiv."""
        if not self._api_client:
            return
        
        # Prüfen auf ungespeicherte Änderungen
        if self._has_unsaved_changes:
            reply = QMessageBox.question(
                self,
                "Ungespeicherte Änderungen",
                "Es gibt ungespeicherte Änderungen. Trotzdem fortfahren?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        
        from api.gdv_api import GDVAPI
        gdv_api = GDVAPI(self._api_client)
        
        # Datei vom Server herunterladen
        self._statusbar.showMessage(f"Lade {filename} vom Server...")
        
        temp_path = gdv_api.download_and_get_path(doc_id)
        
        if temp_path:
            # Datei mit bestehendem Parser öffnen
            self._load_file(temp_path)
            
            # Titel anpassen um zu zeigen dass es vom Server ist
            self._current_filepath = None  # Kein lokaler Pfad
            self._server_doc_id = doc_id  # Server-Dokument-ID merken
            self.setWindowTitle(f"ACENCIA ATLAS - {filename} (Server)")
            self._statusbar.showMessage(f"{filename} vom Server geladen", 3000)
        else:
            if self._toast_manager:
                self._toast_manager.show_warning(
                    f"Datei '{filename}' konnte nicht vom Server geladen werden."
                )
    
    def _on_upload_to_archive(self):
        """Lädt die aktuelle GDV-Datei ins Archiv hoch."""
        if not self._api_client:
            if self._toast_manager:
                self._toast_manager.show_warning("Keine Server-Verbindung.")
            return
        
        if not self._current_filepath:
            if self._toast_manager:
                self._toast_manager.show_warning("Bitte zuerst eine GDV-Datei öffnen oder speichern.")
            return
        
        from api.documents import DocumentsAPI
        docs_api = DocumentsAPI(self._api_client)
        
        doc = docs_api.upload(self._current_filepath, 'manual_upload')
        
        if doc:
            if self._toast_manager:
                self._toast_manager.show_success(
                    f"Datei '{doc.original_filename}' erfolgreich ins Archiv hochgeladen."
                )
        else:
            if self._toast_manager:
                self._toast_manager.show_error("Upload fehlgeschlagen.")
    
    def _on_logout(self):
        """Benutzer abmelden."""
        if self._auth_api:
            reply = QMessageBox.question(
                self,
                "Abmelden",
                "Wirklich abmelden?\n\nUngespeicherte Änderungen gehen verloren.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self._auth_api.logout()
                self.close()
                # Die Anwendung wird neu gestartet werden müssen für neuen Login
    
    def closeEvent(self, event):
        if self._has_unsaved_changes:
            reply = QMessageBox.question(self, "Ungespeicherte Änderungen",
                "Es gibt ungespeicherte Änderungen. Wirklich beenden?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        event.accept()
