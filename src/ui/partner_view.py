# -*- coding: utf-8 -*-
"""
GDV Tool - Partner-Ansicht (Verbessert)

Zeigt alle Partner (Personen/Firmen) aus der GDV-Datei.
- Arbeitgeber/Firmen werden zusammengefasst (nicht pro Vertrag dupliziert)
- Versicherte Personen werden mit ihrem Arbeitgeber verknüpft
- Übersichtliche Darstellung aller Verträge pro Arbeitgeber
"""

import os
import sys
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Set

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QListWidget, 
    QListWidgetItem, QScrollArea, QLabel, QFrame, QGroupBox,
    QGridLayout, QSizePolicy, QTabWidget
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QColor

# Pfad zum src-Verzeichnis
_src_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from parser.gdv_parser import ParsedFile, ParsedRecord
from layouts.gdv_layouts import get_anrede_bezeichnung, get_sparten_bezeichnung


# =============================================================================
# Datenmodell
# =============================================================================

@dataclass
class InsuredPerson:
    """Eine versicherte Person in einem Vertrag."""
    name: str
    vorname: str
    geburtsdatum: str
    vertragsnummer: str
    sparte: str
    sparte_name: str
    
    @property
    def display_name(self) -> str:
        parts = []
        if self.vorname:
            parts.append(self.vorname)
        if self.name:
            parts.append(self.name)
        return " ".join(parts) if parts else "Unbekannt"


@dataclass
class Contract:
    """Ein Versicherungsvertrag."""
    vertragsnummer: str
    sparte: str
    sparte_name: str
    status: str
    status_text: str
    beginn: str
    ende: str
    beitrag: float
    waehrung: str
    zahlungsweise: str
    versicherungssumme: float
    employer_name: str = ""  # Name des Arbeitgebers
    versicherte_personen: List[InsuredPerson] = field(default_factory=list)
    fonds: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class Employer:
    """Ein Arbeitgeber/Firma mit allen Verträgen."""
    id: str
    name: str
    name2: str
    strasse: str
    plz: str
    ort: str
    land: str
    kundennummer: str
    bic: str
    iban: str
    contracts: List[Contract] = field(default_factory=list)
    employees: List['Person'] = field(default_factory=list)
    
    @property
    def display_name(self) -> str:
        if self.name2:
            return f"{self.name} {self.name2}".strip()
        return self.name
    
    @property
    def address_line(self) -> str:
        parts = []
        if self.plz:
            parts.append(self.plz)
        if self.ort:
            parts.append(self.ort)
        return " ".join(parts)
    
    @property
    def total_beitrag(self) -> float:
        return sum(c.beitrag for c in self.contracts if c.beitrag)
    
    @property
    def total_persons(self) -> int:
        persons = set()
        for c in self.contracts:
            for p in c.versicherte_personen:
                persons.add(f"{p.vorname}_{p.name}_{p.geburtsdatum}")
        return len(persons)


@dataclass
class Person:
    """Eine natürliche Person (versicherte Person oder VN)."""
    id: str
    anrede: str
    anrede_text: str
    name: str
    vorname: str
    titel: str
    strasse: str
    plz: str
    ort: str
    land: str
    geburtsdatum: str
    employer: Optional[Employer] = None
    employer_name: str = ""
    contracts: List[Contract] = field(default_factory=list)  # Eigene Verträge
    insured_contracts: List[Contract] = field(default_factory=list)  # Verträge wo versichert
    
    @property
    def display_name(self) -> str:
        parts = []
        if self.anrede_text:
            parts.append(self.anrede_text)
        if self.vorname:
            parts.append(self.vorname)
        if self.name:
            parts.append(self.name)
        return " ".join(parts) if parts else "Unbekannt"
    
    @property
    def address_line(self) -> str:
        parts = []
        if self.plz:
            parts.append(self.plz)
        if self.ort:
            parts.append(self.ort)
        return " ".join(parts)
    
    @property
    def all_contracts_count(self) -> int:
        return len(self.contracts) + len(self.insured_contracts)


def extract_partners_from_file(parsed_file: ParsedFile) -> tuple[List[Employer], List[Person]]:
    """
    Extrahiert Arbeitgeber und Personen aus einer GDV-Datei.
    """
    employers_by_name: Dict[str, Employer] = {}
    persons_by_name: Dict[str, Person] = {}
    contracts_by_vsnr: Dict[str, Contract] = {}
    vsnr_to_employer: Dict[str, str] = {}
    vsnr_to_person: Dict[str, str] = {}
    
    # Status-Mapping (GDV-Standard)
    STATUS_MAP = {
        "1": "Aktiv",
        "2": "Storniert",
        "3": "Ruhend",
        "4": "Beitragsfrei",
        "5": "Leistung",
        "6": "Beitragsfrei gestellt",
        "0": "Antrag",
        "": "Unbekannt"
    }
    
    # Zahlungsweise-Mapping
    ZAHLUNGSWEISE_MAP = {
        "1": "jährlich",
        "2": "halbjährlich",
        "4": "vierteljährlich",
        "12": "monatlich",
        "0": "Einmalbeitrag",
        "": ""
    }
    
    # 1. Pass: Alle 0100 TD1 (Adressdaten) sammeln
    for record in parsed_file.records:
        if record.satzart != "0100":
            continue
        
        satznr = str(record.get_field_value("satznummer", "")).strip()
        if satznr != "1":
            continue
        
        vsnr = str(record.get_field_value("versicherungsschein_nr", "")).strip()
        anrede = str(record.get_field_value("anrede_schluessel", "")).strip()
        name1 = str(record.get_field_value("name1", "")).strip()
        name2 = str(record.get_field_value("name2", "")).strip()
        name3 = str(record.get_field_value("name3", "")).strip()
        
        strasse = str(record.get_field_value("strasse", "")).strip()
        plz = str(record.get_field_value("plz", "")).strip()
        ort = str(record.get_field_value("ort", "")).strip()
        land = str(record.get_field_value("land_kennzeichen", "")).strip()
        gebdat = str(record.get_field_value("geburtsdatum", "")).strip()
        
        if anrede in ("0", "3"):
            # FIRMA/ARBEITGEBER
            employer_key = f"{name1}_{name2}_{ort}".lower().strip("_")
            
            if employer_key not in employers_by_name:
                employers_by_name[employer_key] = Employer(
                    id=employer_key,
                    name=name1,
                    name2=name2,
                    strasse=strasse,
                    plz=plz,
                    ort=ort,
                    land=land,
                    kundennummer="",
                    bic="",
                    iban=""
                )
            
            vsnr_to_employer[vsnr] = employer_key
            
        else:
            # NATÜRLICHE PERSON
            vorname = name3 if name3 else name2
            person_key = f"{name1}_{vorname}_{gebdat}".lower().strip("_")
            
            if person_key not in persons_by_name:
                persons_by_name[person_key] = Person(
                    id=person_key,
                    anrede=anrede,
                    anrede_text=get_anrede_bezeichnung(anrede),
                    name=name1,
                    vorname=vorname,
                    titel=str(record.get_field_value("titel", "")).strip(),
                    strasse=strasse,
                    plz=plz,
                    ort=ort,
                    land=land,
                    geburtsdatum=gebdat if gebdat and gebdat != "None" else ""
                )
            
            vsnr_to_person[vsnr] = person_key
    
    # 2. Pass: Kundennummer und Bankdaten ergänzen
    for record in parsed_file.records:
        if record.satzart != "0100":
            continue
        
        satznr = str(record.get_field_value("satznummer", "")).strip()
        vsnr = str(record.get_field_value("versicherungsschein_nr", "")).strip()
        
        if satznr == "2":
            kundennr = str(record.get_field_value("kundennummer", "")).strip()
            if kundennr and vsnr in vsnr_to_employer:
                emp_key = vsnr_to_employer[vsnr]
                if emp_key in employers_by_name and not employers_by_name[emp_key].kundennummer:
                    employers_by_name[emp_key].kundennummer = kundennr
        
        elif satznr == "4":
            bic = str(record.get_field_value("bic", "")).strip()
            iban = str(record.get_field_value("iban", "")).strip()
            if vsnr in vsnr_to_employer:
                emp_key = vsnr_to_employer[vsnr]
                if emp_key in employers_by_name:
                    if bic and not employers_by_name[emp_key].bic:
                        employers_by_name[emp_key].bic = bic
                    if iban and not employers_by_name[emp_key].iban:
                        employers_by_name[emp_key].iban = iban
    
    # 3. Pass: Verträge (0200) sammeln
    for record in parsed_file.records:
        if record.satzart != "0200":
            continue
        
        satznr = str(record.get_field_value("satznummer", "")).strip()
        if satznr != "1":
            continue
        
        vsnr = str(record.get_field_value("versicherungsschein_nr", "")).strip()
        sparte = str(record.get_field_value("sparte", "")).strip()
        
        # Status korrekt auslesen
        status_raw = record.get_field_value("vertragsstatus", "")
        status = str(status_raw).strip() if status_raw else ""
        status_text = STATUS_MAP.get(status, f"Status {status}" if status else "Aktiv")
        
        # Beitrag
        beitrag = record.get_field_value("gesamtbeitrag", 0)
        if isinstance(beitrag, str):
            try:
                beitrag = float(beitrag.replace(",", ".")) if beitrag else 0
            except:
                beitrag = 0
        
        # Zahlungsweise
        zw_raw = record.get_field_value("zahlungsweise", "")
        zw = str(zw_raw).strip() if zw_raw else ""
        zahlungsweise = ZAHLUNGSWEISE_MAP.get(zw, zw)
        
        # Arbeitgeber-Name für den Vertrag
        employer_name = ""
        if vsnr in vsnr_to_employer:
            emp_key = vsnr_to_employer[vsnr]
            if emp_key in employers_by_name:
                employer_name = employers_by_name[emp_key].display_name
        
        contract = Contract(
            vertragsnummer=vsnr,
            sparte=sparte,
            sparte_name=get_sparten_bezeichnung(sparte),
            status=status,
            status_text=status_text,
            beginn=str(record.get_field_value("vertragsbeginn", "")).strip(),
            ende=str(record.get_field_value("vertragsende", "")).strip(),
            beitrag=beitrag if isinstance(beitrag, (int, float)) else 0,
            waehrung=str(record.get_field_value("waehrung", "EUR")).strip() or "EUR",
            zahlungsweise=zahlungsweise,
            versicherungssumme=0,
            employer_name=employer_name
        )
        
        contracts_by_vsnr[vsnr] = contract
    
    # 4. Pass: Versicherungssummen (0210)
    for record in parsed_file.records:
        if record.satzart == "0210":
            vsnr = str(record.get_field_value("versicherungsschein_nr", "")).strip()
            if vsnr in contracts_by_vsnr:
                vs = record.get_field_value("versicherungssumme_1", 0)
                if isinstance(vs, (int, float)) and vs > 0:
                    contracts_by_vsnr[vsnr].versicherungssumme = vs
    
    # 5. Pass: Versicherte Personen (0220 Personendaten)
    for record in parsed_file.records:
        if record.satzart == "0220" and "Personendaten" in record.satzart_name:
            vsnr = str(record.get_field_value("versicherungsschein_nr", "")).strip()
            if vsnr not in contracts_by_vsnr:
                continue
            
            name = str(record.get_field_value("name", "")).strip()
            vorname = str(record.get_field_value("vorname", "")).strip()
            gebdat = str(record.get_field_value("geburtsdatum", "")).strip()
            sparte = contracts_by_vsnr[vsnr].sparte
            
            if name or vorname:
                insured = InsuredPerson(
                    name=name,
                    vorname=vorname,
                    geburtsdatum=gebdat if gebdat and gebdat != "None" else "",
                    vertragsnummer=vsnr,
                    sparte=sparte,
                    sparte_name=contracts_by_vsnr[vsnr].sparte_name
                )
                contracts_by_vsnr[vsnr].versicherte_personen.append(insured)
    
    # 6. Pass: Fonds (0230)
    for record in parsed_file.records:
        if record.satzart == "0230":
            vsnr = str(record.get_field_value("versicherungsschein_nr", "")).strip()
            if vsnr in contracts_by_vsnr:
                fonds_name = str(record.get_field_value("fonds_name", "")).strip()
                isin = str(record.get_field_value("isin", "")).strip()
                if fonds_name:
                    contracts_by_vsnr[vsnr].fonds.append({"name": fonds_name, "isin": isin})
    
    # 7. Verträge den Arbeitgebern/Personen zuordnen
    for vsnr, contract in contracts_by_vsnr.items():
        if vsnr in vsnr_to_employer:
            emp_key = vsnr_to_employer[vsnr]
            if emp_key in employers_by_name:
                employers_by_name[emp_key].contracts.append(contract)
        elif vsnr in vsnr_to_person:
            person_key = vsnr_to_person[vsnr]
            if person_key in persons_by_name:
                persons_by_name[person_key].contracts.append(contract)
    
    # 8. Personen mit Arbeitgebern verknüpfen UND Verträge zuordnen
    for emp in employers_by_name.values():
        seen_persons = set()
        for contract in emp.contracts:
            for insured in contract.versicherte_personen:
                # Suche passende Person
                person_key = f"{insured.name}_{insured.vorname}_{insured.geburtsdatum}".lower().strip("_")
                
                # Auch ohne Geburtsdatum suchen
                if person_key not in persons_by_name:
                    person_key = f"{insured.name}_{insured.vorname}_".lower().strip("_")
                
                if person_key in persons_by_name:
                    person = persons_by_name[person_key]
                    # Arbeitgeber setzen
                    if not person.employer:
                        person.employer = emp
                        person.employer_name = emp.display_name
                    
                    # Vertrag als "versichert bei" hinzufügen
                    if contract not in person.insured_contracts:
                        person.insured_contracts.append(contract)
                    
                    # Zur Mitarbeiterliste hinzufügen
                    if person_key not in seen_persons:
                        emp.employees.append(person)
                        seen_persons.add(person_key)
    
    # Sortieren
    employers = sorted(employers_by_name.values(), key=lambda e: e.display_name.lower())
    persons = sorted(persons_by_name.values(), key=lambda p: p.display_name.lower())
    
    return employers, persons


# =============================================================================
# Widgets
# =============================================================================

class PartnerListWidget(QListWidget):
    """Liste der Partner (Arbeitgeber oder Personen)."""
    
    item_selected = Signal(object)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._items = []
        self._setup_ui()
    
    def _setup_ui(self):
        self.setStyleSheet("""
            QListWidget {
                border: 1px solid #ddd;
                border-radius: 8px;
                background: white;
                font-size: 13px;
            }
            QListWidget::item {
                padding: 12px 15px;
                border-bottom: 1px solid #eee;
            }
            QListWidget::item:selected {
                background-color: #1a73e8;
                color: white;
            }
            QListWidget::item:hover:!selected {
                background-color: #f5f5f5;
            }
        """)
        self.itemSelectionChanged.connect(self._on_selection_changed)
    
    def set_employers(self, employers: List[Employer]):
        self._items = employers
        self.clear()
        
        for emp in employers:
            icon = "🏢"
            contract_count = len(emp.contracts)
            person_count = emp.total_persons
            
            info_parts = []
            if contract_count > 0:
                info_parts.append(f"{contract_count} Vertr.")
            if person_count > 0:
                info_parts.append(f"{person_count} Pers.")
            info = " • ".join(info_parts) if info_parts else ""
            
            text = f"{icon} {emp.display_name}\n     {emp.address_line}"
            if info:
                text += f" • {info}"
            
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, emp)
            self.addItem(item)
    
    def set_persons(self, persons: List[Person]):
        self._items = persons
        self.clear()
        
        for person in persons:
            icon = "👤"
            
            info_parts = []
            if person.employer_name:
                info_parts.append(f"bei {person.employer_name[:25]}")
            total_contracts = person.all_contracts_count
            if total_contracts > 0:
                info_parts.append(f"{total_contracts} Vertr.")
            info = " • ".join(info_parts) if info_parts else ""
            
            text = f"{icon} {person.display_name}\n     {person.address_line}"
            if info:
                text += f" • {info}"
            
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, person)
            self.addItem(item)
    
    def _on_selection_changed(self):
        items = self.selectedItems()
        if items:
            data = items[0].data(Qt.ItemDataRole.UserRole)
            self.item_selected.emit(data)


class EmployerDetailWidget(QWidget):
    """Detailansicht für einen Arbeitgeber."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: #f8f9fa; }")
        
        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(20, 20, 20, 20)
        self._content_layout.setSpacing(15)
        
        scroll.setWidget(self._content)
        layout.addWidget(scroll)
        
        self._show_placeholder()
    
    def _show_placeholder(self):
        self._clear()
        label = QLabel("Wählen Sie einen Arbeitgeber aus der Liste")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("color: #999; font-size: 16px; padding: 50px;")
        self._content_layout.addWidget(label)
    
    def _clear(self):
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
    
    def set_employer(self, emp: Optional[Employer]):
        self._clear()
        
        if not emp:
            self._show_placeholder()
            return
        
        # Header
        header = self._create_header(emp)
        self._content_layout.addWidget(header)
        
        # Adresse
        if emp.strasse or emp.ort:
            self._content_layout.addWidget(self._create_address_box(emp))
        
        # Bank
        if emp.bic or emp.iban:
            self._content_layout.addWidget(self._create_bank_box(emp))
        
        # Versicherte Personen
        if emp.total_persons > 0:
            self._content_layout.addWidget(self._create_persons_box(emp))
        
        # Verträge
        if emp.contracts:
            self._content_layout.addWidget(self._create_contracts_box(emp))
        
        self._content_layout.addStretch()
    
    def _create_header(self, emp: Employer) -> QWidget:
        widget = QWidget()
        widget.setStyleSheet("background: white; border-radius: 12px;")
        
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        
        name = QLabel(f"🏢 {emp.display_name}")
        name.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        name.setStyleSheet("color: #1a73e8;")
        name.setWordWrap(True)
        layout.addWidget(name)
        
        if emp.kundennummer:
            kn = QLabel(f"Kundennummer: {emp.kundennummer}")
            kn.setStyleSheet("color: #666;")
            layout.addWidget(kn)
        
        stats = []
        stats.append(f"{len(emp.contracts)} Verträge")
        stats.append(f"{emp.total_persons} versicherte Personen")
        if emp.total_beitrag > 0:
            beitrag = f"{emp.total_beitrag:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            stats.append(f"Gesamtbeitrag: {beitrag} €")
        
        stats_label = QLabel(" • ".join(stats))
        stats_label.setStyleSheet("color: #888; margin-top: 5px;")
        layout.addWidget(stats_label)
        
        return widget
    
    def _create_address_box(self, emp: Employer) -> QGroupBox:
        box = QGroupBox("📍 Adresse")
        box.setStyleSheet(self._groupbox_style())
        
        layout = QGridLayout(box)
        layout.setContentsMargins(15, 25, 15, 15)
        layout.setSpacing(8)
        
        row = 0
        if emp.strasse:
            layout.addWidget(QLabel("Straße:"), row, 0)
            layout.addWidget(QLabel(emp.strasse), row, 1)
            row += 1
        
        if emp.plz or emp.ort:
            layout.addWidget(QLabel("PLZ / Ort:"), row, 0)
            layout.addWidget(QLabel(f"{emp.plz} {emp.ort}".strip()), row, 1)
            row += 1
        
        if emp.land:
            layout.addWidget(QLabel("Land:"), row, 0)
            layout.addWidget(QLabel(emp.land), row, 1)
        
        layout.setColumnStretch(1, 1)
        return box
    
    def _create_bank_box(self, emp: Employer) -> QGroupBox:
        box = QGroupBox("🏦 Bankverbindung")
        box.setStyleSheet(self._groupbox_style())
        
        layout = QGridLayout(box)
        layout.setContentsMargins(15, 25, 15, 15)
        layout.setSpacing(8)
        
        row = 0
        if emp.iban:
            layout.addWidget(QLabel("IBAN:"), row, 0)
            iban = emp.iban.replace(" ", "")
            iban_fmt = " ".join([iban[i:i+4] for i in range(0, len(iban), 4)])
            lbl = QLabel(iban_fmt)
            lbl.setStyleSheet("font-family: monospace;")
            layout.addWidget(lbl, row, 1)
            row += 1
        
        if emp.bic:
            layout.addWidget(QLabel("BIC:"), row, 0)
            lbl = QLabel(emp.bic)
            lbl.setStyleSheet("font-family: monospace;")
            layout.addWidget(lbl, row, 1)
        
        layout.setColumnStretch(1, 1)
        return box
    
    def _create_persons_box(self, emp: Employer) -> QGroupBox:
        """Zeigt alle versicherten Personen."""
        persons = {}
        for contract in emp.contracts:
            for ins in contract.versicherte_personen:
                key = f"{ins.vorname}_{ins.name}_{ins.geburtsdatum}"
                if key not in persons:
                    persons[key] = {"person": ins, "contracts": []}
                persons[key]["contracts"].append(contract)
        
        box = QGroupBox(f"👥 Versicherte Personen ({len(persons)})")
        box.setStyleSheet(self._groupbox_style())
        
        layout = QVBoxLayout(box)
        layout.setContentsMargins(15, 25, 15, 15)
        layout.setSpacing(8)
        
        for data in list(persons.values())[:20]:
            person = data["person"]
            contracts = data["contracts"]
            
            card = QFrame()
            card.setStyleSheet("background: #f0f7ff; border-radius: 6px; padding: 8px;")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(10, 8, 10, 8)
            card_layout.setSpacing(4)
            
            name_lbl = QLabel(f"👤 {person.display_name}")
            name_lbl.setStyleSheet("font-weight: bold; color: #333;")
            card_layout.addWidget(name_lbl)
            
            if person.geburtsdatum:
                geb_lbl = QLabel(f"Geb.: {person.geburtsdatum}")
                geb_lbl.setStyleSheet("color: #666; font-size: 11px;")
                card_layout.addWidget(geb_lbl)
            
            contract_texts = [f"{c.sparte_name} ({c.vertragsnummer[-8:]})" for c in contracts[:3]]
            if len(contracts) > 3:
                contract_texts.append(f"+{len(contracts)-3} weitere")
            contracts_lbl = QLabel("Verträge: " + ", ".join(contract_texts))
            contracts_lbl.setStyleSheet("color: #555; font-size: 11px;")
            contracts_lbl.setWordWrap(True)
            card_layout.addWidget(contracts_lbl)
            
            layout.addWidget(card)
        
        if len(persons) > 20:
            more = QLabel(f"... und {len(persons) - 20} weitere Personen")
            more.setStyleSheet("color: #888; font-style: italic;")
            layout.addWidget(more)
        
        return box
    
    def _create_contracts_box(self, emp: Employer) -> QGroupBox:
        box = QGroupBox(f"📋 Verträge ({len(emp.contracts)})")
        box.setStyleSheet(self._groupbox_style())
        
        layout = QVBoxLayout(box)
        layout.setContentsMargins(15, 25, 15, 15)
        layout.setSpacing(10)
        
        for contract in emp.contracts[:15]:
            card = self._create_contract_card(contract)
            layout.addWidget(card)
        
        if len(emp.contracts) > 15:
            more = QLabel(f"... und {len(emp.contracts) - 15} weitere Verträge")
            more.setStyleSheet("color: #888; font-style: italic;")
            layout.addWidget(more)
        
        return box
    
    def _create_contract_card(self, contract: Contract) -> QFrame:
        card = QFrame()
        card.setStyleSheet("background: #f8f9fa; border: 1px solid #e8e8e8; border-radius: 8px;")
        
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(6)
        
        # Header
        header = QHBoxLayout()
        title = QLabel(f"📄 {contract.vertragsnummer}")
        title.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        header.addWidget(title)
        
        sparte = QLabel(contract.sparte_name)
        sparte.setStyleSheet("background: #e3f2fd; color: #1565c0; padding: 2px 6px; border-radius: 3px; font-size: 10px;")
        header.addWidget(sparte)
        
        # Status mit korrekten Farben
        status_colors = {
            "1": ("#e8f5e9", "#2e7d32"),  # Aktiv - grün
            "2": ("#ffebee", "#c62828"),  # Storniert - rot
            "3": ("#fff3e0", "#ef6c00"),  # Ruhend - orange
            "4": ("#e3f2fd", "#1565c0"),  # Beitragsfrei - blau
            "5": ("#f3e5f5", "#7b1fa2"),  # Leistung - lila
            "6": ("#e3f2fd", "#1565c0"),  # Beitragsfrei gestellt - blau
            "0": ("#fafafa", "#666"),     # Antrag - grau
            "": ("#e8f5e9", "#2e7d32"),   # Default: Aktiv - grün
        }
        bg, fg = status_colors.get(contract.status, ("#e8f5e9", "#2e7d32"))
        status = QLabel(contract.status_text)
        status.setStyleSheet(f"background: {bg}; color: {fg}; padding: 2px 6px; border-radius: 3px; font-size: 10px;")
        header.addWidget(status)
        header.addStretch()
        
        layout.addLayout(header)
        
        # Details
        if contract.beginn:
            lz = f"Laufzeit: {contract.beginn}"
            if contract.ende:
                lz += f" - {contract.ende}"
            layout.addWidget(QLabel(lz))
        
        if contract.beitrag > 0:
            beitrag = f"{contract.beitrag:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            bt = f"Beitrag: {beitrag} {contract.waehrung}"
            if contract.zahlungsweise:
                bt += f" ({contract.zahlungsweise})"
            layout.addWidget(QLabel(bt))
        
        if contract.versicherte_personen:
            names = [p.display_name for p in contract.versicherte_personen[:3]]
            if len(contract.versicherte_personen) > 3:
                names.append(f"+{len(contract.versicherte_personen)-3}")
            vp = QLabel(f"Versicherte: {', '.join(names)}")
            vp.setStyleSheet("color: #666; font-size: 11px;")
            layout.addWidget(vp)
        
        return card
    
    def _groupbox_style(self) -> str:
        return """
            QGroupBox {
                background: white;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 15px;
                font-weight: bold;
                font-size: 13px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 5px;
            }
        """


class PersonDetailWidget(QWidget):
    """Detailansicht für eine Person."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: #f8f9fa; }")
        
        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(20, 20, 20, 20)
        self._content_layout.setSpacing(15)
        
        scroll.setWidget(self._content)
        layout.addWidget(scroll)
        
        self._show_placeholder()
    
    def _show_placeholder(self):
        self._clear()
        label = QLabel("Wählen Sie eine Person aus der Liste")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("color: #999; font-size: 16px; padding: 50px;")
        self._content_layout.addWidget(label)
    
    def _clear(self):
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
    
    def set_person(self, person: Optional[Person]):
        self._clear()
        
        if not person:
            self._show_placeholder()
            return
        
        # Header
        header = QWidget()
        header.setStyleSheet("background: white; border-radius: 12px;")
        h_layout = QVBoxLayout(header)
        h_layout.setContentsMargins(20, 20, 20, 20)
        
        name = QLabel(f"👤 {person.display_name}")
        name.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        name.setStyleSheet("color: #1a73e8;")
        h_layout.addWidget(name)
        
        if person.geburtsdatum:
            geb = QLabel(f"Geburtsdatum: {person.geburtsdatum}")
            geb.setStyleSheet("color: #666;")
            h_layout.addWidget(geb)
        
        # Statistik
        total = person.all_contracts_count
        stats = QLabel(f"{total} Verträge")
        if person.employer_name:
            stats.setText(f"Angestellt bei: {person.employer_name} • {total} Verträge")
        stats.setStyleSheet("color: #888; margin-top: 5px;")
        h_layout.addWidget(stats)
        
        self._content_layout.addWidget(header)
        
        # Arbeitgeber
        if person.employer:
            emp_box = QGroupBox("🏢 Arbeitgeber")
            emp_box.setStyleSheet(self._groupbox_style())
            emp_layout = QVBoxLayout(emp_box)
            emp_layout.setContentsMargins(15, 25, 15, 15)
            
            emp_name = QLabel(f"🏢 {person.employer.display_name}")
            emp_name.setStyleSheet("font-weight: bold; color: #333;")
            emp_layout.addWidget(emp_name)
            
            if person.employer.ort:
                emp_addr = QLabel(f"📍 {person.employer.plz} {person.employer.ort}".strip())
                emp_addr.setStyleSheet("color: #666;")
                emp_layout.addWidget(emp_addr)
            
            self._content_layout.addWidget(emp_box)
        
        # Adresse
        if person.strasse or person.ort:
            addr_box = QGroupBox("📍 Adresse")
            addr_box.setStyleSheet(self._groupbox_style())
            addr_layout = QGridLayout(addr_box)
            addr_layout.setContentsMargins(15, 25, 15, 15)
            
            row = 0
            if person.strasse:
                addr_layout.addWidget(QLabel("Straße:"), row, 0)
                addr_layout.addWidget(QLabel(person.strasse), row, 1)
                row += 1
            if person.plz or person.ort:
                addr_layout.addWidget(QLabel("PLZ / Ort:"), row, 0)
                addr_layout.addWidget(QLabel(f"{person.plz} {person.ort}".strip()), row, 1)
            
            addr_layout.setColumnStretch(1, 1)
            self._content_layout.addWidget(addr_box)
        
        # ALLE Verträge (eigene + versichert bei)
        all_contracts = []
        
        # Verträge, bei denen die Person versichert ist (über Arbeitgeber)
        for c in person.insured_contracts:
            all_contracts.append((c, "versichert"))
        
        # Eigene Verträge
        for c in person.contracts:
            if c not in person.insured_contracts:
                all_contracts.append((c, "eigen"))
        
        if all_contracts:
            contracts_box = QGroupBox(f"📋 Verträge ({len(all_contracts)})")
            contracts_box.setStyleSheet(self._groupbox_style())
            c_layout = QVBoxLayout(contracts_box)
            c_layout.setContentsMargins(15, 25, 15, 15)
            c_layout.setSpacing(10)
            
            for contract, contract_type in all_contracts[:15]:
                card = self._create_contract_card(contract, contract_type)
                c_layout.addWidget(card)
            
            if len(all_contracts) > 15:
                more = QLabel(f"... und {len(all_contracts) - 15} weitere Verträge")
                more.setStyleSheet("color: #888; font-style: italic;")
                c_layout.addWidget(more)
            
            self._content_layout.addWidget(contracts_box)
        
        self._content_layout.addStretch()
    
    def _create_contract_card(self, contract: Contract, contract_type: str) -> QFrame:
        card = QFrame()
        card.setStyleSheet("background: #f8f9fa; border: 1px solid #e8e8e8; border-radius: 8px;")
        
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(6)
        
        # Header
        header = QHBoxLayout()
        title = QLabel(f"📄 {contract.vertragsnummer}")
        title.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        header.addWidget(title)
        
        sparte = QLabel(contract.sparte_name)
        sparte.setStyleSheet("background: #e3f2fd; color: #1565c0; padding: 2px 6px; border-radius: 3px; font-size: 10px;")
        header.addWidget(sparte)
        
        # Status
        status_colors = {
            "1": ("#e8f5e9", "#2e7d32"),
            "2": ("#ffebee", "#c62828"),
            "3": ("#fff3e0", "#ef6c00"),
            "4": ("#e3f2fd", "#1565c0"),
            "5": ("#f3e5f5", "#7b1fa2"),
            "6": ("#e3f2fd", "#1565c0"),
            "0": ("#fafafa", "#666"),
            "": ("#e8f5e9", "#2e7d32"),
        }
        bg, fg = status_colors.get(contract.status, ("#e8f5e9", "#2e7d32"))
        status = QLabel(contract.status_text)
        status.setStyleSheet(f"background: {bg}; color: {fg}; padding: 2px 6px; border-radius: 3px; font-size: 10px;")
        header.addWidget(status)
        header.addStretch()
        
        layout.addLayout(header)
        
        # Arbeitgeber (wenn versicherter Vertrag)
        if contract.employer_name:
            emp_lbl = QLabel(f"🏢 Arbeitgeber: {contract.employer_name}")
            emp_lbl.setStyleSheet("color: #1565c0; font-size: 11px;")
            layout.addWidget(emp_lbl)
        
        # Laufzeit
        if contract.beginn:
            lz = f"Laufzeit: {contract.beginn}"
            if contract.ende:
                lz += f" - {contract.ende}"
            layout.addWidget(QLabel(lz))
        
        # Beitrag
        if contract.beitrag > 0:
            beitrag = f"{contract.beitrag:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            bt = f"Beitrag: {beitrag} {contract.waehrung}"
            if contract.zahlungsweise:
                bt += f" ({contract.zahlungsweise})"
            layout.addWidget(QLabel(bt))
        
        return card
    
    def _groupbox_style(self) -> str:
        return """
            QGroupBox {
                background: white;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 15px;
                font-weight: bold;
                font-size: 13px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 5px;
            }
        """


# =============================================================================
# Haupt-Widget
# =============================================================================

class PartnerView(QWidget):
    """Partner-Ansicht mit Tabs für Arbeitgeber und Personen."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._parsed_file = None
        self._employers: List[Employer] = []
        self._persons: List[Person] = []
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Header
        header = QWidget()
        header.setStyleSheet("background: #f5f5f5; border-bottom: 1px solid #ddd;")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(15, 10, 15, 10)
        
        title = QLabel("👥 Partner-Ansicht")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        h_layout.addWidget(title)
        
        self._stats_label = QLabel("")
        self._stats_label.setStyleSheet("color: #666;")
        h_layout.addWidget(self._stats_label)
        h_layout.addStretch()
        
        layout.addWidget(header)
        
        # Tabs
        tabs = QTabWidget()
        tabs.setStyleSheet("""
            QTabWidget::pane { border: none; }
            QTabBar::tab { padding: 10px 20px; font-weight: bold; }
            QTabBar::tab:selected { background: #1a73e8; color: white; border-radius: 4px 4px 0 0; }
        """)
        
        # Tab 1: Arbeitgeber
        emp_widget = QWidget()
        emp_layout = QHBoxLayout(emp_widget)
        emp_layout.setContentsMargins(0, 0, 0, 0)
        
        emp_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        emp_list_container = QWidget()
        emp_list_layout = QVBoxLayout(emp_list_container)
        emp_list_layout.setContentsMargins(10, 10, 5, 10)
        self._employer_list = PartnerListWidget()
        self._employer_list.item_selected.connect(self._on_employer_selected)
        emp_list_layout.addWidget(self._employer_list)
        emp_splitter.addWidget(emp_list_container)
        
        self._employer_detail = EmployerDetailWidget()
        emp_splitter.addWidget(self._employer_detail)
        emp_splitter.setSizes([350, 700])
        
        emp_layout.addWidget(emp_splitter)
        tabs.addTab(emp_widget, "🏢 Arbeitgeber / Firmen")
        
        # Tab 2: Personen
        person_widget = QWidget()
        person_layout = QHBoxLayout(person_widget)
        person_layout.setContentsMargins(0, 0, 0, 0)
        
        person_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        person_list_container = QWidget()
        person_list_layout = QVBoxLayout(person_list_container)
        person_list_layout.setContentsMargins(10, 10, 5, 10)
        self._person_list = PartnerListWidget()
        self._person_list.item_selected.connect(self._on_person_selected)
        person_list_layout.addWidget(self._person_list)
        person_splitter.addWidget(person_list_container)
        
        self._person_detail = PersonDetailWidget()
        person_splitter.addWidget(self._person_detail)
        person_splitter.setSizes([350, 700])
        
        person_layout.addWidget(person_splitter)
        tabs.addTab(person_widget, "👤 Versicherte Personen")
        
        layout.addWidget(tabs, 1)
    
    def set_parsed_file(self, parsed_file: Optional[ParsedFile]):
        self._parsed_file = parsed_file
        
        if not parsed_file:
            self._employers = []
            self._persons = []
            self._employer_list.clear()
            self._person_list.clear()
            self._employer_detail.set_employer(None)
            self._person_detail.set_person(None)
            self._stats_label.setText("")
            return
        
        # Partner extrahieren
        self._employers, self._persons = extract_partners_from_file(parsed_file)
        
        # Listen füllen
        self._employer_list.set_employers(self._employers)
        self._person_list.set_persons(self._persons)
        
        # Statistik
        total_contracts = sum(len(e.contracts) for e in self._employers)
        total_contracts += sum(len(p.contracts) for p in self._persons)
        self._stats_label.setText(f"{len(self._employers)} Arbeitgeber • {len(self._persons)} Personen • {total_contracts} Verträge")
        
        # Ersten Eintrag auswählen
        if self._employers:
            self._employer_list.setCurrentRow(0)
        if self._persons:
            self._person_list.setCurrentRow(0)
    
    def _on_employer_selected(self, employer: Employer):
        self._employer_detail.set_employer(employer)
    
    def _on_person_selected(self, person: Person):
        self._person_detail.set_person(person)
