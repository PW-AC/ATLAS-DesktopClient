#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GDV Tool - Benutzerfreundliche Detailansicht

Zeigt nur die wesentlichen Felder in einer übersichtlichen Darstellung.
Technische Felder (Satznummer, Reserve, etc.) werden ausgeblendet.
Felder mit festen Werten werden als Dropdown angezeigt.
Nicht-editierbare Felder sind schreibgeschützt.
"""

import os
import sys

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
    QLineEdit, QComboBox, QScrollArea, QFrame, QGroupBox,
    QPushButton, QMessageBox, QSizePolicy
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

# Pfad zum src-Verzeichnis
_src_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from parser.gdv_parser import ParsedRecord
from layouts.gdv_layouts import (
    get_layout, get_anrede_bezeichnung, get_sparten_bezeichnung,
    SPARTEN_BEZEICHNUNGEN, ANREDE_BEZEICHNUNGEN, TEILDATENSATZ_LAYOUTS
)


# =============================================================================
# Konfiguration: Welche Felder werden angezeigt und wie
# =============================================================================

# Felder die NICHT angezeigt werden sollen (technische Felder)
HIDDEN_FIELDS = {
    "satznummer", "reserve", "reserve_0200_1", "reserve_0210", "reserve_0220",
    "reserve_0230", "reserve_9999", "buendelungskennzeichen", "folge_nr",
    "zusatz_info", "adresstyp", "leerstelle", "leerstelle1", "leer", "leer2",
    "leer_td4", "kennzeichen_vs", "summenart_1", "wagnisart", "lfd_nummer_wagnis", 
    "wagnisart_lfd", "version_satzarten", "inkasso_art", "kennziffer",
    "reserve_td2", "reserve_td3", "reserve_td4", "reserve_td5", "bank_daten",
    "reserve_0220_td1", "deckungsdaten", "bezug_text"
}

# Felder die NICHT editierbar sein sollen
READONLY_FIELDS = {
    "satzart", "vu_nummer", "versicherungsschein_nr", "sparte"
}

# Felder mit Dropdown-Auswahl (Schlüsselfelder)
DROPDOWN_FIELDS = {
    "anrede_schluessel": {
        "0": "Firma",
        "1": "Herr", 
        "2": "Frau",
        "3": "Firma (mit Ansprechpartner)"
    },
    "vertragsstatus": {
        "1": "Lebend/Aktiv",
        "2": "Storniert",
        "3": "Ruhend",
        "4": "Beitragsfrei",
        "5": "Anwartschaft"
    },
    "zahlungsweise": {
        "1": "Jährlich",
        "2": "Halbjährlich",
        "4": "Vierteljährlich",
        "12": "Monatlich",
        "0": "Einmalbeitrag"
    },
    "geschlecht": {
        "0": "Unbekannt",
        "1": "Männlich",
        "2": "Weiblich"
    },
    "land_kennzeichen": {
        "D": "Deutschland",
        "A": "Österreich",
        "CH": "Schweiz",
        "": "Nicht angegeben"
    }
}

# Benutzerfreundliche Labels für Felder
FRIENDLY_LABELS = {
    # 0001 - Vorsatz
    "absender": "Versicherung",
    "adressat": "Empfänger/Vermittler",
    "erstellungsdatum_von": "Erstellt am",
    "erstellungsdatum_bis": "Gültig bis",
    "geschaeftsstelle": "Vermittlernummer",
    
    # 0100 - Partnerdaten (Teildatensatz 1: Adresse)
    "anrede_schluessel": "Anrede",
    "name1": "Name / Firma",
    "name2": "Firmenname (Teil 2)",
    "name3": "Vorname / Zusatz",
    "titel": "Titel",
    "strasse": "Straße",
    "plz": "PLZ",
    "ort": "Ort",
    "land_kennzeichen": "Land",
    "geburtsdatum": "Geburtsdatum",
    
    # 0100 - Partnerdaten (Teildatensatz 2: Nummern)
    "kundennummer": "Kundennummer",
    "referenznummer": "Referenznummer",
    "zusatznummer": "Zusatznummer",
    "steuer_id": "Steuer-ID",
    
    # 0100 - Partnerdaten (Teildatensatz 4: Bank)
    "bankname": "Bankname",
    "bankort": "Bankort",
    "bic": "BIC",
    "iban": "IBAN",
    
    # 0200 - Vertrag
    "versicherungsschein_nr": "Vertragsnummer",
    "sparte": "Sparte",
    "vertragsstatus": "Status",
    "vertragsbeginn": "Vertragsbeginn",
    "vertragsende": "Vertragsende",
    "hauptfaelligkeit": "Hauptfälligkeit",
    "zahlungsweise": "Zahlungsweise",
    "gesamtbeitrag": "Beitrag (€)",
    "waehrung": "Währung",
    
    # 0210 - Spartenspezifisch
    "versicherungssumme_1": "Versicherungssumme (€)",
    
    # 0220 - Deckungen (Teildatensatz 1: Person)
    "name": "Name (Vers. Person)",
    "vorname": "Vorname (Vers. Person)",
    "geschlecht": "Geschlecht",
    
    # 0220 - Deckungen (Teildatensatz 6: Bezugsberechtigte)
    "vorname_bezug": "Vorname (Bezugsber.)",
    "name_bezug": "Name (Bezugsber.)",
    "anteil": "Anteil (%)",
    
    # 0230 - Fonds
    "fonds_name": "Fondsname",
    "isin": "ISIN",
    "fonds_anteil": "Fondsanteile",
    "prozent_anteil": "Anteil (%)",
    "stichtag": "Stichtag",
    
    # 9999 - Nachsatz
    "anzahl_saetze": "Anzahl Datensätze",
    "gesamtbeitrag": "Gesamtsumme Beiträge"
}

# Wichtige Felder pro Satzart (in Anzeigereihenfolge)
IMPORTANT_FIELDS = {
    "0001": ["absender", "adressat", "erstellungsdatum_von", "erstellungsdatum_bis", "geschaeftsstelle"],
    "0100": ["anrede_schluessel", "name1", "name3", "name2", "titel", "strasse", "plz", "ort", "land_kennzeichen", "geburtsdatum"],
    "0200": ["versicherungsschein_nr", "sparte", "vertragsstatus", "vertragsbeginn", "vertragsende", "hauptfaelligkeit", "zahlungsweise", "gesamtbeitrag", "waehrung"],
    "0210": ["versicherungsschein_nr", "sparte", "waehrung", "versicherungssumme_1"],
    "0220": ["versicherungsschein_nr", "sparte", "name", "vorname", "geburtsdatum", "geschlecht"],
    "0230": ["versicherungsschein_nr", "fonds_name", "isin", "fonds_anteil", "prozent_anteil", "stichtag"],
    "9999": ["anzahl_saetze", "gesamtbeitrag", "summe_vs"]
}

# Wichtige Felder pro Teildatensatz (überschreibt IMPORTANT_FIELDS wenn passend)
IMPORTANT_FIELDS_BY_TD = {
    "0100": {
        "1": ["anrede_schluessel", "name1", "name3", "name2", "titel", "strasse", "plz", "ort", "land_kennzeichen", "geburtsdatum"],
        "2": ["kundennummer", "referenznummer", "zusatznummer", "steuer_id"],
        "3": [],  # Kommunikationsdaten - meist leer
        "4": ["bankname", "bankort", "bic", "iban"],  # KORRIGIERT: Bankdaten
        "5": [],  # Zusatzdaten - meist leer
    },
    "0220": {
        "1": ["versicherungsschein_nr", "name", "vorname", "geburtsdatum", "geschlecht"],
        "6": ["versicherungsschein_nr", "vorname_bezug", "name_bezug", "anteil"],
    }
}


class UserDetailWidget(QWidget):
    """Benutzerfreundliche Detailansicht für GDV-Datensätze."""
    
    record_changed = Signal(ParsedRecord)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_record = None
        self._field_widgets = {}
        self._setup_ui()
    
    def _setup_ui(self):
        """Erstellt die UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)
        
        # Header
        self._header_label = QLabel("Kein Datensatz ausgewählt")
        self._header_label.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        self._header_label.setStyleSheet("color: #1a73e8; padding-bottom: 5px;")
        layout.addWidget(self._header_label)
        
        # Untertitel mit VU/Vertragsnummer
        self._subtitle_label = QLabel("")
        self._subtitle_label.setStyleSheet("color: #5f6368; font-size: 12px; margin-bottom: 10px;")
        layout.addWidget(self._subtitle_label)
        
        # Trennlinie
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("background-color: #e0e0e0;")
        layout.addWidget(line)
        
        # Scroll-Bereich für Felder
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea { 
                border: none; 
                background: transparent;
            }
            QScrollArea > QWidget > QWidget { 
                background: transparent; 
            }
        """)
        
        self._fields_container = QWidget()
        self._fields_layout = QVBoxLayout(self._fields_container)
        self._fields_layout.setSpacing(12)
        self._fields_layout.setContentsMargins(0, 10, 0, 10)
        
        scroll.setWidget(self._fields_container)
        layout.addWidget(scroll, 1)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self._apply_btn = QPushButton("💾 Änderungen speichern")
        self._apply_btn.setStyleSheet("""
            QPushButton {
                background-color: #1a73e8;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #1557b0;
            }
            QPushButton:disabled {
                background-color: #e0e0e0;
                color: #9e9e9e;
            }
        """)
        self._apply_btn.clicked.connect(self._on_apply_changes)
        self._apply_btn.setEnabled(False)
        btn_layout.addWidget(self._apply_btn)
        
        layout.addLayout(btn_layout)
    
    def set_record(self, record):
        """Zeigt einen Datensatz an."""
        self._current_record = record
        self._field_widgets.clear()
        
        # Alte Widgets entfernen
        while self._fields_layout.count():
            item = self._fields_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        if not record:
            self._header_label.setText("Kein Datensatz ausgewählt")
            self._subtitle_label.setText("")
            self._apply_btn.setEnabled(False)
            return
        
        # Teildatensatz ermitteln
        satzart = record.satzart
        teildatensatz = None
        if "satznummer" in record.fields:
            satznr_val = record.fields["satznummer"].value
            if satznr_val and str(satznr_val).strip().isdigit():
                teildatensatz = str(satznr_val).strip()
        
        # Layout mit Teildatensatz-Unterstützung holen
        layout_def = get_layout(satzart, teildatensatz)
        name = layout_def["name"] if layout_def else f"Satzart {satzart}"
        
        self._header_label.setText(name)
        
        # Untertitel
        vu = str(record.get_field_value("vu_nummer", "") or "").strip()
        vsnr = str(record.get_field_value("versicherungsschein_nr", "") or "").strip()
        sparte_code = str(record.get_field_value("sparte", "") or "").strip()
        sparte_name = get_sparten_bezeichnung(sparte_code) if sparte_code else ""
        
        subtitle_parts = []
        if vu:
            subtitle_parts.append(f"VU: {vu}")
        if vsnr:
            subtitle_parts.append(f"Vertrag: {vsnr}")
        if sparte_name and satzart != "0001":
            subtitle_parts.append(f"Sparte: {sparte_name}")
        
        self._subtitle_label.setText(" | ".join(subtitle_parts))
        
        # Felder anzeigen - Teildatensatz-spezifisch wenn verfügbar
        important = None
        if satzart in IMPORTANT_FIELDS_BY_TD and teildatensatz:
            td_fields = IMPORTANT_FIELDS_BY_TD[satzart]
            if teildatensatz in td_fields:
                important = td_fields[teildatensatz]
        
        if important is None:
            important = IMPORTANT_FIELDS.get(satzart, [])
        
        # Wenn keine wichtigen Felder definiert, alle nicht-hidden Felder zeigen
        if not important and layout_def:
            important = [f["name"] for f in layout_def["fields"] if f["name"] not in HIDDEN_FIELDS]
        
        # Sonderfall: Leere Teildatensätze (2, 3, 5 bei 0100)
        if not important:
            # Zeige Hinweis statt leerer Ansicht
            hint = QLabel("Dieser Teildatensatz enthält keine relevanten Daten für die Benutzeransicht.\n\n"
                         "Wechseln Sie zur Experten-Ansicht (Strg+E) um alle Felder zu sehen.")
            hint.setStyleSheet("color: #5f6368; font-style: italic; padding: 20px;")
            hint.setWordWrap(True)
            self._fields_layout.addWidget(hint)
            self._apply_btn.setEnabled(False)
            return
        
        for field_name in important:
            if field_name not in record.fields:
                continue
            
            parsed_field = record.fields[field_name]
            value = parsed_field.value
            
            # Wert aufbereiten
            if value is None:
                value = ""
            elif isinstance(value, float):
                value = f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            else:
                value = str(value).strip()
            
            # Leere Felder überspringen (außer bei wichtigen)
            if not value and field_name not in ["anrede_schluessel", "vertragsstatus", "zahlungsweise"]:
                continue
            
            # Widget erstellen
            self._create_field_row(field_name, value, parsed_field)
        
        self._apply_btn.setEnabled(True)
    
    def _create_field_row(self, field_name, value, parsed_field):
        """Erstellt eine Zeile für ein Feld."""
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(10)
        
        # Label
        label_text = FRIENDLY_LABELS.get(field_name, parsed_field.label)
        label = QLabel(label_text)
        label.setMinimumWidth(150)
        label.setMaximumWidth(180)
        label.setStyleSheet("font-weight: 500; color: #3c4043;")
        row_layout.addWidget(label)
        
        # Widget (je nach Feldtyp)
        is_readonly = field_name in READONLY_FIELDS
        
        if field_name in DROPDOWN_FIELDS and not is_readonly:
            # Dropdown für Schlüsselfelder
            widget = QComboBox()
            options = DROPDOWN_FIELDS[field_name]
            
            for code, text in options.items():
                widget.addItem(text, code)
            
            # Aktuellen Wert setzen
            current_index = widget.findData(str(value))
            if current_index >= 0:
                widget.setCurrentIndex(current_index)
            
            widget.setStyleSheet("""
                QComboBox {
                    padding: 8px 12px;
                    border: 1px solid #dadce0;
                    border-radius: 6px;
                    background: white;
                    min-width: 200px;
                }
                QComboBox:focus {
                    border-color: #1a73e8;
                }
                QComboBox::drop-down {
                    border: none;
                    width: 30px;
                }
            """)
            
        elif field_name == "sparte":
            # Sparte als Text anzeigen (nur lesen)
            sparte_name = get_sparten_bezeichnung(str(value))
            widget = QLineEdit(sparte_name)
            widget.setReadOnly(True)
            widget.setStyleSheet("""
                QLineEdit {
                    padding: 8px 12px;
                    border: 1px solid #dadce0;
                    border-radius: 6px;
                    background: #f8f9fa;
                    color: #5f6368;
                }
            """)
            
        else:
            # Standard-Textfeld
            widget = QLineEdit(str(value))
            
            if is_readonly:
                widget.setReadOnly(True)
                widget.setStyleSheet("""
                    QLineEdit {
                        padding: 8px 12px;
                        border: 1px solid #dadce0;
                        border-radius: 6px;
                        background: #f8f9fa;
                        color: #5f6368;
                    }
                """)
            else:
                widget.setStyleSheet("""
                    QLineEdit {
                        padding: 8px 12px;
                        border: 1px solid #dadce0;
                        border-radius: 6px;
                        background: white;
                    }
                    QLineEdit:focus {
                        border-color: #1a73e8;
                        outline: none;
                    }
                """)
        
        widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        row_layout.addWidget(widget)
        
        self._field_widgets[field_name] = widget
        self._fields_layout.addWidget(row)
    
    def _on_apply_changes(self):
        """Übernimmt die Änderungen."""
        if not self._current_record:
            return
        
        # Werte aus Widgets lesen und in Record übertragen
        for field_name, widget in self._field_widgets.items():
            if field_name in READONLY_FIELDS:
                continue
            
            if isinstance(widget, QComboBox):
                new_value = widget.currentData()
            else:
                new_value = widget.text().strip()
            
            if field_name in self._current_record.fields:
                pf = self._current_record.fields[field_name]
                
                # Wert konvertieren
                if pf.field_type == "N" and new_value:
                    try:
                        # Deutsche Zahlenformat -> Float
                        clean = new_value.replace(".", "").replace(",", ".")
                        new_value = float(clean) if "." in clean else new_value
                    except ValueError:
                        pass
                
                pf.value = new_value if new_value else None
        
        # Signal senden
        self.record_changed.emit(self._current_record)
        
        QMessageBox.information(
            self, "Gespeichert",
            "Die Änderungen wurden übernommen.\n"
            "Speichern Sie die Datei, um sie dauerhaft zu sichern."
        )

