#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GDV Domain-Modelle

Fachliche Klassen für die Darstellung von GDV-Daten:
- FileMeta: Metadaten der Datei (aus 0001)
- Customer: Kundendaten (aus 0100)
- Contract: Vertragsdaten (aus 0200)
- Risk: Wagnisse/Risiken (aus 0210)
- Coverage: Deckungen (aus 0220)

Die Klassen bilden eine hierarchische Struktur:
FileMeta
  └── Customers[]
  └── Contracts[]
        └── Risks[]
        └── Coverages[]
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
import uuid


# =============================================================================
# Enums für kodierte Werte
# =============================================================================

class Anrede(Enum):
    """Anrede-Schlüssel."""
    OHNE = "0"
    HERR = "1"
    FRAU = "2"
    FIRMA = "3"
    
    @classmethod
    def from_code(cls, code: str) -> "Anrede":
        for item in cls:
            if item.value == str(code).strip():
                return item
        return cls.OHNE
    
    def to_display(self) -> str:
        mapping = {
            Anrede.OHNE: "",
            Anrede.HERR: "Herr",
            Anrede.FRAU: "Frau",
            Anrede.FIRMA: "Firma"
        }
        return mapping.get(self, "")


class Vertragsstatus(Enum):
    """Vertragsstatus."""
    UNBEKANNT = "0"
    LEBEND = "1"
    STORNIERT = "2"
    RUHEND = "3"
    BEITRAGSFREI = "4"
    
    @classmethod
    def from_code(cls, code: str) -> "Vertragsstatus":
        for item in cls:
            if item.value == str(code).strip():
                return item
        return cls.UNBEKANNT
    
    def to_display(self) -> str:
        mapping = {
            Vertragsstatus.UNBEKANNT: "Unbekannt",
            Vertragsstatus.LEBEND: "Lebend",
            Vertragsstatus.STORNIERT: "Storniert",
            Vertragsstatus.RUHEND: "Ruhend",
            Vertragsstatus.BEITRAGSFREI: "Beitragsfrei"
        }
        return mapping.get(self, "Unbekannt")


class Zahlungsweise(Enum):
    """Zahlungsweise."""
    UNBEKANNT = "0"
    JAEHRLICH = "1"
    HALBJAEHRLICH = "2"
    VIERTELJAEHRLICH = "3"
    MONATLICH = "4"
    EINMALBEITRAG = "5"
    
    @classmethod
    def from_code(cls, code: str) -> "Zahlungsweise":
        for item in cls:
            if item.value == str(code).strip():
                return item
        return cls.UNBEKANNT
    
    def to_display(self) -> str:
        mapping = {
            Zahlungsweise.UNBEKANNT: "Unbekannt",
            Zahlungsweise.JAEHRLICH: "Jährlich",
            Zahlungsweise.HALBJAEHRLICH: "Halbjährlich",
            Zahlungsweise.VIERTELJAEHRLICH: "Vierteljährlich",
            Zahlungsweise.MONATLICH: "Monatlich",
            Zahlungsweise.EINMALBEITRAG: "Einmalbeitrag"
        }
        return mapping.get(self, "Unbekannt")


class PersonenRolle(Enum):
    """Rolle einer Person im Vertrag."""
    UNBEKANNT = "00"
    VERSICHERTE_PERSON = "01"
    BEZUGSBERECHTIGTER = "02"
    BEITRAGSZAHLER = "03"
    PRAEMIENTRAEGER = "04"
    
    @classmethod
    def from_code(cls, code: str) -> "PersonenRolle":
        code_str = str(code).strip().zfill(2)
        for item in cls:
            if item.value == code_str:
                return item
        return cls.UNBEKANNT
    
    def to_display(self) -> str:
        mapping = {
            PersonenRolle.UNBEKANNT: "Unbekannt",
            PersonenRolle.VERSICHERTE_PERSON: "Versicherte Person",
            PersonenRolle.BEZUGSBERECHTIGTER: "Bezugsberechtigter",
            PersonenRolle.BEITRAGSZAHLER: "Beitragszahler",
            PersonenRolle.PRAEMIENTRAEGER: "Prämienträger"
        }
        return mapping.get(self, "Unbekannt")


class Deckungsart(Enum):
    """Art der Deckung."""
    UNBEKANNT = "000"
    HAUPTDECKUNG = "001"
    ZUSATZDECKUNG = "002"
    BAUSTEIN = "003"
    
    @classmethod
    def from_code(cls, code: str) -> "Deckungsart":
        code_str = str(code).strip().zfill(3)
        for item in cls:
            if item.value == code_str:
                return item
        return cls.UNBEKANNT
    
    def to_display(self) -> str:
        mapping = {
            Deckungsart.UNBEKANNT: "Unbekannt",
            Deckungsart.HAUPTDECKUNG: "Hauptdeckung",
            Deckungsart.ZUSATZDECKUNG: "Zusatzdeckung",
            Deckungsart.BAUSTEIN: "Baustein"
        }
        return mapping.get(self, "Unbekannt")


class Leistungsart(Enum):
    """Art der Leistung."""
    UNBEKANNT = "00"
    KAPITAL = "01"
    RENTE = "02"
    KOMBINIERT = "03"
    
    @classmethod
    def from_code(cls, code: str) -> "Leistungsart":
        code_str = str(code).strip().zfill(2)
        for item in cls:
            if item.value == code_str:
                return item
        return cls.UNBEKANNT
    
    def to_display(self) -> str:
        mapping = {
            Leistungsart.UNBEKANNT: "Unbekannt",
            Leistungsart.KAPITAL: "Kapitalleistung",
            Leistungsart.RENTE: "Rentenleistung",
            Leistungsart.KOMBINIERT: "Kombiniert"
        }
        return mapping.get(self, "Unbekannt")


# =============================================================================
# Sparten-Definitionen
# =============================================================================

SPARTEN: Dict[str, str] = {
    "010": "Leben",
    "020": "Kranken",
    "030": "Unfall",
    "040": "Haftpflicht",
    "050": "Kraftfahrt",
    "051": "Kfz-Haftpflicht",
    "052": "Kfz-Kasko",
    "053": "Kfz-Unfall",
    "060": "Rechtsschutz",
    "070": "Hausrat",
    "080": "Wohngebäude",
    "090": "Transport/Reise",
    "100": "Gewerbe-Sach",
    "110": "Technische Vers.",
    "120": "Berufshaftpflicht",
    "130": "D&O",
}


def get_sparte_name(code: str) -> str:
    """Gibt den Namen einer Sparte zurück."""
    return SPARTEN.get(str(code).strip().zfill(3), f"Sparte {code}")


# =============================================================================
# Domain-Klassen
# =============================================================================

@dataclass
class FileMeta:
    """
    Metadaten der GDV-Datei (aus Satzart 0001).
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    vu_nummer: str = ""
    absender: str = ""
    adressat: str = ""
    erstellungsdatum_von: Optional[str] = None
    erstellungsdatum_bis: Optional[str] = None
    release_stand: str = ""
    vermittler_nr: str = ""
    
    # Technische Metadaten
    source_file: str = ""
    encoding: str = "latin-1"
    import_timestamp: Optional[datetime] = None
    
    # Referenz zum Original-Record
    source_line_number: int = 0
    
    def __str__(self) -> str:
        return f"FileMeta(VU={self.vu_nummer}, Release={self.release_stand})"


@dataclass
class Customer:
    """
    Kundendaten (aus Satzart 0100).
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    vu_nummer: str = ""
    versicherungsschein_nr: str = ""
    folge_nr: str = ""
    
    # Persönliche Daten
    anrede: Anrede = Anrede.OHNE
    name1: str = ""  # Nachname oder Firma
    name2: str = ""  # Vorname
    name3: str = ""  # Zusatz
    titel: str = ""
    
    # Adresse
    strasse: str = ""
    plz: str = ""
    ort: str = ""
    land: str = "DEU"
    
    # Weitere Daten
    geburtsdatum: Optional[str] = None
    adresstyp: str = ""
    telefon: str = ""
    email: str = ""
    
    # Referenz
    source_line_number: int = 0
    
    @property
    def vollstaendiger_name(self) -> str:
        """Gibt den vollständigen Namen zurück."""
        parts = []
        if self.anrede != Anrede.OHNE:
            parts.append(self.anrede.to_display())
        if self.titel:
            parts.append(self.titel)
        if self.name2:
            parts.append(self.name2)
        if self.name1:
            parts.append(self.name1)
        return " ".join(parts)
    
    @property
    def adresse_einzeilig(self) -> str:
        """Gibt die Adresse einzeilig zurück."""
        parts = []
        if self.strasse:
            parts.append(self.strasse)
        if self.plz and self.ort:
            parts.append(f"{self.plz} {self.ort}")
        elif self.ort:
            parts.append(self.ort)
        return ", ".join(parts)
    
    def __str__(self) -> str:
        return f"Customer({self.vollstaendiger_name})"


@dataclass
class Risk:
    """
    Wagnis/Risiko (aus Satzart 0210).
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    vu_nummer: str = ""
    versicherungsschein_nr: str = ""
    sparte: str = ""
    satznummer: str = ""
    
    # Wagnis-Details
    wagnis_art: str = ""
    wagnis_nr: str = ""
    
    # Personenzuordnung
    lfd_person_nr: str = ""
    person_rolle: PersonenRolle = PersonenRolle.UNBEKANNT
    
    # Zeitraum
    risikobeginn: Optional[str] = None
    risikoende: Optional[str] = None
    
    # Werte
    versicherungssumme: float = 0.0
    beitrag: float = 0.0
    
    # Tarif
    tarif_bezeichnung: str = ""
    beruf_schluessel: str = ""
    dynamik_prozent: float = 0.0
    selbstbeteiligung: float = 0.0
    
    # Referenz
    source_line_number: int = 0
    
    @property
    def sparte_name(self) -> str:
        return get_sparte_name(self.sparte)
    
    def __str__(self) -> str:
        return f"Risk(Wagnis={self.wagnis_art}, Summe={self.versicherungssumme:,.2f})"


@dataclass
class Coverage:
    """
    Deckung/Leistungsbaustein (aus Satzart 0220).
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    vu_nummer: str = ""
    versicherungsschein_nr: str = ""
    sparte: str = ""
    satznummer: str = ""
    
    # Wagnis-Zuordnung
    wagnis_art: str = ""
    wagnis_nr: str = ""
    lfd_deckung_nr: str = ""
    
    # Deckungsdetails
    deckungsart: Deckungsart = Deckungsart.UNBEKANNT
    deckungsbezeichnung: str = ""
    deckungssumme: float = 0.0
    deckungsbeitrag: float = 0.0
    
    # Zeitraum
    deckungsbeginn: Optional[str] = None
    deckungsende: Optional[str] = None
    
    # Weitere Details
    selbstbeteiligung: float = 0.0
    leistungsart: Leistungsart = Leistungsart.UNBEKANNT
    rentenfaktor: float = 0.0
    klausel_code: str = ""
    zusatzinfo: str = ""
    
    # Referenz
    source_line_number: int = 0
    
    @property
    def sparte_name(self) -> str:
        return get_sparte_name(self.sparte)
    
    def __str__(self) -> str:
        return f"Coverage({self.deckungsbezeichnung}, Summe={self.deckungssumme:,.2f})"


@dataclass
class Contract:
    """
    Vertrag (aus Satzart 0200, inkl. 0210 und 0220).
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    vu_nummer: str = ""
    versicherungsschein_nr: str = ""
    sparte: str = ""
    
    # Vermittler
    vermittler_nr: str = ""
    
    # Status
    vertragsstatus: Vertragsstatus = Vertragsstatus.UNBEKANNT
    
    # Zeitraum
    vertragsbeginn: Optional[str] = None
    vertragsende: Optional[str] = None
    hauptfaelligkeit: Optional[str] = None
    
    # Zahlung
    zahlungsweise: Zahlungsweise = Zahlungsweise.UNBEKANNT
    gesamtbeitrag_brutto: float = 0.0
    gesamtbeitrag_netto: float = 0.0
    waehrung: str = "EUR"
    
    # Produkt
    produktname: str = ""
    
    # Weitere Daten
    antragsdatum: Optional[str] = None
    policierungsdatum: Optional[str] = None
    kuendigungsfrist: int = 0
    vertragsbedingungen: str = ""
    
    # Verknüpfte Objekte
    risks: List[Risk] = field(default_factory=list)
    coverages: List[Coverage] = field(default_factory=list)
    customer: Optional[Customer] = None
    
    # Referenz
    source_line_number: int = 0
    
    @property
    def sparte_name(self) -> str:
        return get_sparte_name(self.sparte)
    
    @property
    def contract_key(self) -> str:
        """Eindeutiger Schlüssel: VU|VSNR|Sparte."""
        return f"{self.vu_nummer}|{self.versicherungsschein_nr}|{self.sparte}"
    
    @property
    def gesamtdeckungssumme(self) -> float:
        """Summe aller Deckungssummen."""
        return sum(c.deckungssumme for c in self.coverages)
    
    def add_risk(self, risk: Risk) -> None:
        """Fügt ein Risiko zum Vertrag hinzu."""
        self.risks.append(risk)
    
    def add_coverage(self, coverage: Coverage) -> None:
        """Fügt eine Deckung zum Vertrag hinzu."""
        self.coverages.append(coverage)
    
    def __str__(self) -> str:
        return f"Contract({self.versicherungsschein_nr}, {self.sparte_name})"


@dataclass
class GDVData:
    """
    Container für alle geladenen GDV-Daten.
    """
    file_meta: Optional[FileMeta] = None
    customers: List[Customer] = field(default_factory=list)
    contracts: List[Contract] = field(default_factory=list)
    
    # Lookup-Dictionaries
    _contracts_by_key: Dict[str, Contract] = field(default_factory=dict, repr=False)
    _customers_by_vsnr: Dict[str, List[Customer]] = field(default_factory=dict, repr=False)
    
    def add_contract(self, contract: Contract) -> None:
        """Fügt einen Vertrag hinzu und aktualisiert Lookup."""
        self.contracts.append(contract)
        self._contracts_by_key[contract.contract_key] = contract
    
    def add_customer(self, customer: Customer) -> None:
        """Fügt einen Kunden hinzu und aktualisiert Lookup."""
        self.customers.append(customer)
        key = customer.versicherungsschein_nr
        if key not in self._customers_by_vsnr:
            self._customers_by_vsnr[key] = []
        self._customers_by_vsnr[key].append(customer)
    
    def get_contract(self, vu: str, vsnr: str, sparte: str) -> Optional[Contract]:
        """Sucht einen Vertrag anhand des Schlüssels."""
        key = f"{vu}|{vsnr}|{sparte}"
        return self._contracts_by_key.get(key)
    
    def get_customers_for_contract(self, vsnr: str) -> List[Customer]:
        """Gibt alle Kunden für eine Versicherungsschein-Nr zurück."""
        return self._customers_by_vsnr.get(vsnr, [])
    
    def link_customers_to_contracts(self) -> None:
        """Verknüpft Kunden mit ihren Verträgen."""
        for contract in self.contracts:
            customers = self.get_customers_for_contract(contract.versicherungsschein_nr)
            if customers:
                # Erster Kunde (Adresstyp 01 = VN) wird als Hauptkunde gesetzt
                for cust in customers:
                    if cust.adresstyp == "01":
                        contract.customer = cust
                        break
                if not contract.customer and customers:
                    contract.customer = customers[0]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Gibt Statistiken über die geladenen Daten zurück."""
        sparten_count: Dict[str, int] = {}
        for contract in self.contracts:
            sparte_name = contract.sparte_name
            sparten_count[sparte_name] = sparten_count.get(sparte_name, 0) + 1
        
        return {
            "customers_count": len(self.customers),
            "contracts_count": len(self.contracts),
            "risks_count": sum(len(c.risks) for c in self.contracts),
            "coverages_count": sum(len(c.coverages) for c in self.contracts),
            "sparten": sparten_count,
            "gesamtbeitrag": sum(c.gesamtbeitrag_brutto for c in self.contracts)
        }
    
    def __str__(self) -> str:
        stats = self.get_statistics()
        return (
            f"GDVData(Kunden={stats['customers_count']}, "
            f"Verträge={stats['contracts_count']}, "
            f"Risiken={stats['risks_count']}, "
            f"Deckungen={stats['coverages_count']})"
        )


# =============================================================================
# Test / Demo
# =============================================================================

if __name__ == "__main__":
    # Demo: Objekte erstellen
    print("=" * 80)
    print("GDV Domain-Modelle - Test")
    print("=" * 80)
    
    # FileMeta
    meta = FileMeta(
        vu_nummer="12345",
        absender="Test Versicherung",
        release_stand="2025.01"
    )
    print(f"\n{meta}")
    
    # Customer
    customer = Customer(
        vu_nummer="12345",
        versicherungsschein_nr="VS-001",
        anrede=Anrede.HERR,
        titel="Dr.",
        name2="Max",
        name1="Mustermann",
        strasse="Musterstr. 1",
        plz="12345",
        ort="Musterstadt"
    )
    print(f"\n{customer}")
    print(f"Voller Name: {customer.vollstaendiger_name}")
    print(f"Adresse: {customer.adresse_einzeilig}")
    
    # Contract
    contract = Contract(
        vu_nummer="12345",
        versicherungsschein_nr="VS-001",
        sparte="010",
        vertragsstatus=Vertragsstatus.LEBEND,
        gesamtbeitrag_brutto=1200.00,
        produktname="Lebensversicherung Plus"
    )
    
    # Risk
    risk = Risk(
        versicherungsschein_nr="VS-001",
        sparte="010",
        wagnis_art="0001",
        versicherungssumme=100000.00,
        beitrag=1200.00
    )
    contract.add_risk(risk)
    
    # Coverage
    coverage = Coverage(
        versicherungsschein_nr="VS-001",
        sparte="010",
        deckungsbezeichnung="Todesfallleistung",
        deckungssumme=100000.00,
        deckungsbeitrag=800.00
    )
    contract.add_coverage(coverage)
    
    print(f"\n{contract}")
    print(f"Sparte: {contract.sparte_name}")
    print(f"Status: {contract.vertragsstatus.to_display()}")
    print(f"Risiken: {len(contract.risks)}")
    print(f"Deckungen: {len(contract.coverages)}")
    print(f"Gesamtdeckungssumme: {contract.gesamtdeckungssumme:,.2f} EUR")
    
    # GDVData Container
    data = GDVData()
    data.file_meta = meta
    data.add_customer(customer)
    data.add_contract(contract)
    data.link_customers_to_contracts()
    
    print(f"\n{data}")
    print(f"Statistiken: {data.get_statistics()}")



