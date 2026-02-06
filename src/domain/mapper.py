#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GDV Domain Mapper

Mapping-Funktionen zur Umwandlung von ParsedRecords in Domain-Objekte.
Angepasst an die echte GDV-Spezifikation.
"""

import logging
from typing import Optional, Dict, List

import sys
import os

# Pfad für Imports konfigurieren
_src_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

# Domain-Modelle importieren
try:
    from .models import (
        FileMeta, Customer, Contract, Risk, Coverage, GDVData,
        Anrede, Vertragsstatus, Zahlungsweise, PersonenRolle, 
        Deckungsart, Leistungsart
    )
except ImportError:
    from models import (
        FileMeta, Customer, Contract, Risk, Coverage, GDVData,
        Anrede, Vertragsstatus, Zahlungsweise, PersonenRolle, 
        Deckungsart, Leistungsart
    )

# Parser importieren
from parser.gdv_parser import ParsedRecord, ParsedFile


logger = logging.getLogger(__name__)


# =============================================================================
# Hilfsfunktionen
# =============================================================================

def safe_float(value, default: float = 0.0) -> float:
    """Konvertiert einen Wert sicher in float."""
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    try:
        # Entferne nicht-numerische Zeichen außer Punkt und Minus
        cleaned = str(value).replace(",", ".").strip()
        # Nur Ziffern, Punkt und Minus behalten
        cleaned = ''.join(c for c in cleaned if c.isdigit() or c in '.-')
        if cleaned:
            return float(cleaned)
        return default
    except (ValueError, TypeError):
        return default


def safe_int(value, default: int = 0) -> int:
    """Konvertiert einen Wert sicher in int."""
    if value is None:
        return default
    if isinstance(value, int):
        return value
    try:
        return int(float(str(value).strip().replace(',', '.')))
    except (ValueError, TypeError):
        return default


def safe_str(value, default: str = "") -> str:
    """Konvertiert einen Wert sicher in string."""
    if value is None:
        return default
    return str(value).strip()


# =============================================================================
# Mapping-Funktionen: ParsedRecord → Domain-Objekt
# =============================================================================

def map_0001_to_file_meta(record: ParsedRecord) -> FileMeta:
    """
    Mappt einen 0001-Satz auf FileMeta.
    
    Args:
        record: Das geparste 0001-Record
    
    Returns:
        FileMeta-Objekt
    """
    return FileMeta(
        vu_nummer=safe_str(record.get_field_value("vu_nummer")),
        absender=safe_str(record.get_field_value("absender")),
        adressat=safe_str(record.get_field_value("adressat")),
        erstellungsdatum_von=safe_str(record.get_field_value("erstellungsdatum_von")),
        erstellungsdatum_bis=safe_str(record.get_field_value("erstellungsdatum_bis")),
        release_stand=safe_str(record.get_field_value("zusatzdaten", ""))[:20],  # Aus Zusatzdaten
        vermittler_nr=safe_str(record.get_field_value("vermittler_nr")),
        source_line_number=record.line_number
    )


def map_0100_to_customer(record: ParsedRecord) -> Customer:
    """
    Mappt einen 0100-Satz auf Customer.
    
    Args:
        record: Das geparste 0100-Record
    
    Returns:
        Customer-Objekt
    """
    anrede_code = safe_str(record.get_field_value("anrede_schluessel"))
    
    return Customer(
        vu_nummer=safe_str(record.get_field_value("vu_nummer")),
        versicherungsschein_nr=safe_str(record.get_field_value("versicherungsschein_nr")),
        folge_nr=safe_str(record.get_field_value("folge_nr")),
        anrede=Anrede.from_code(anrede_code),
        name1=safe_str(record.get_field_value("name1")),
        name2=safe_str(record.get_field_value("name2")),
        name3=safe_str(record.get_field_value("name3")),
        titel=safe_str(record.get_field_value("titel")),
        strasse=safe_str(record.get_field_value("strasse")),
        plz=safe_str(record.get_field_value("plz")),
        ort=safe_str(record.get_field_value("ort")),
        land=safe_str(record.get_field_value("land_kennzeichen")) or "D",
        geburtsdatum=safe_str(record.get_field_value("geburtsdatum")) or None,
        adresstyp=safe_str(record.get_field_value("adresstyp")),
        telefon="",  # In separatem Teildatensatz
        email="",    # In separatem Teildatensatz
        source_line_number=record.line_number
    )


def map_0200_to_contract(record: ParsedRecord) -> Contract:
    """
    Mappt einen 0200-Satz auf Contract.
    
    Args:
        record: Das geparste 0200-Record
    
    Returns:
        Contract-Objekt
    """
    status_code = safe_str(record.get_field_value("vertragsstatus"))
    zahlungsweise_code = safe_str(record.get_field_value("zahlungsweise"))
    
    return Contract(
        vu_nummer=safe_str(record.get_field_value("vu_nummer")),
        versicherungsschein_nr=safe_str(record.get_field_value("versicherungsschein_nr")),
        sparte=safe_str(record.get_field_value("sparte")),
        vermittler_nr=safe_str(record.get_field_value("geschaeftsstelle")),
        vertragsstatus=Vertragsstatus.from_code(status_code),
        vertragsbeginn=safe_str(record.get_field_value("vertragsbeginn")) or None,
        vertragsende=safe_str(record.get_field_value("vertragsende")) or None,
        hauptfaelligkeit=safe_str(record.get_field_value("hauptfaelligkeit")) or None,
        zahlungsweise=Zahlungsweise.from_code(zahlungsweise_code),
        gesamtbeitrag_brutto=safe_float(record.get_field_value("gesamtbeitrag")),
        gesamtbeitrag_netto=safe_float(record.get_field_value("beitrag_in_we")),
        waehrung=safe_str(record.get_field_value("waehrung")) or "EUR",
        produktname="",  # Nicht in 0200
        antragsdatum=None,
        policierungsdatum=None,
        kuendigungsfrist=0,
        vertragsbedingungen="",
        source_line_number=record.line_number
    )


def map_0210_to_risk(record: ParsedRecord) -> Risk:
    """
    Mappt einen 0210-Satz auf Risk.
    
    Args:
        record: Das geparste 0210-Record
    
    Returns:
        Risk-Objekt
    """
    return Risk(
        vu_nummer=safe_str(record.get_field_value("vu_nummer")),
        versicherungsschein_nr=safe_str(record.get_field_value("versicherungsschein_nr")),
        sparte=safe_str(record.get_field_value("sparte")),
        satznummer=safe_str(record.get_field_value("satznummer")),
        wagnis_art=safe_str(record.get_field_value("summenart_1")),
        wagnis_nr=safe_str(record.get_field_value("folge_nr")),
        lfd_person_nr="",
        person_rolle=PersonenRolle.UNBEKANNT,
        risikobeginn=None,
        risikoende=None,
        versicherungssumme=safe_float(record.get_field_value("versicherungssumme")),
        beitrag=0.0,
        tarif_bezeichnung="",
        beruf_schluessel="",
        dynamik_prozent=0.0,
        selbstbeteiligung=0.0,
        source_line_number=record.line_number
    )


def map_0220_to_coverage(record: ParsedRecord) -> Coverage:
    """
    Mappt einen 0220-Satz auf Coverage.
    
    Args:
        record: Das geparste 0220-Record
    
    Returns:
        Coverage-Objekt
    """
    return Coverage(
        vu_nummer=safe_str(record.get_field_value("vu_nummer")),
        versicherungsschein_nr=safe_str(record.get_field_value("versicherungsschein_nr")),
        sparte=safe_str(record.get_field_value("sparte")),
        satznummer=safe_str(record.get_field_value("satznummer")),
        wagnis_art=safe_str(record.get_field_value("wagnisart")),
        wagnis_nr=safe_str(record.get_field_value("lfd_nummer")),
        lfd_deckung_nr="",
        deckungsart=Deckungsart.UNBEKANNT,
        deckungsbezeichnung=f"{safe_str(record.get_field_value('person_name'))} {safe_str(record.get_field_value('person_vorname'))}".strip(),
        deckungssumme=0.0,
        deckungsbeitrag=0.0,
        deckungsbeginn=None,
        deckungsende=None,
        selbstbeteiligung=0.0,
        leistungsart=Leistungsart.UNBEKANNT,
        rentenfaktor=0.0,
        klausel_code="",
        zusatzinfo="",
        source_line_number=record.line_number
    )


# =============================================================================
# Haupt-Mapping-Funktion: ParsedFile → GDVData
# =============================================================================

def make_contract_key(vu: str, vsnr: str, sparte: str) -> str:
    """Erstellt einen eindeutigen Vertragsschlüssel."""
    # Normalisiere die Werte
    vu = safe_str(vu).strip()
    vsnr = safe_str(vsnr).strip()
    sparte = safe_str(sparte).strip()
    return f"{vu}|{vsnr}|{sparte}"


def map_parsed_file_to_gdv_data(parsed_file: ParsedFile) -> GDVData:
    """
    Mappt eine ParsedFile auf GDVData mit allen Domain-Objekten.
    
    Die Funktion:
    1. Extrahiert FileMeta aus 0001
    2. Erstellt Customers aus 0100
    3. Erstellt Contracts aus 0200
    4. Fügt Risks (0210) zu den jeweiligen Contracts hinzu
    5. Fügt Coverages (0220) zu den jeweiligen Contracts hinzu
    6. Verknüpft Customers mit Contracts
    
    Args:
        parsed_file: Die geparste GDV-Datei
    
    Returns:
        GDVData mit allen gemappten Objekten
    """
    gdv_data = GDVData()
    
    # Temporäres Dictionary für Verträge (Key → Contract)
    contracts_dict: Dict[str, Contract] = {}
    
    # Nur Teildatensatz 1 für 0200 verarbeiten (Haupt-Vertragsdaten)
    processed_0200_keys = set()
    
    # Alle Records durchgehen
    for record in parsed_file.records:
        satzart = record.satzart
        satznummer = safe_str(record.get_field_value("satznummer", "1"))
        
        if satzart == "0001":
            # Vorsatz → FileMeta (nur erster Teildatensatz)
            if satznummer == "1" or not gdv_data.file_meta:
                gdv_data.file_meta = map_0001_to_file_meta(record)
                gdv_data.file_meta.source_file = parsed_file.filepath
                gdv_data.file_meta.encoding = parsed_file.encoding
                logger.debug(f"FileMeta erstellt: {gdv_data.file_meta}")
            
        elif satzart == "0100":
            # Adressteil → Customer (nur Teildatensatz 1 = Adressdaten)
            if satznummer == "1":
                customer = map_0100_to_customer(record)
                gdv_data.add_customer(customer)
                logger.debug(f"Customer erstellt: {customer}")
            
        elif satzart == "0200":
            # Vertragsteil → Contract (nur Teildatensatz 1)
            if satznummer == "1":
                contract = map_0200_to_contract(record)
                key = contract.contract_key
                
                if key in processed_0200_keys:
                    logger.warning(
                        f"Doppelter Vertrag: {key} (Zeile {record.line_number}), "
                        f"wird ignoriert"
                    )
                else:
                    processed_0200_keys.add(key)
                    contracts_dict[key] = contract
                    gdv_data.add_contract(contract)
                    logger.debug(f"Contract erstellt: {contract}")
                
        elif satzart == "0210":
            # Spartenspezifisch → Risk
            risk = map_0210_to_risk(record)
            key = make_contract_key(risk.vu_nummer, risk.versicherungsschein_nr, risk.sparte)
            
            if key in contracts_dict:
                contracts_dict[key].add_risk(risk)
                logger.debug(f"Risk zu Vertrag {key} hinzugefügt")
            else:
                # Suche nach passendem Vertrag mit ähnlichem Schlüssel
                found = False
                for existing_key in contracts_dict:
                    if risk.versicherungsschein_nr in existing_key:
                        contracts_dict[existing_key].add_risk(risk)
                        found = True
                        break
                
                if not found:
                    logger.debug(
                        f"0210 ohne passenden 0200: {key} (Zeile {record.line_number})"
                    )
                
        elif satzart == "0220":
            # Deckungsteil → Coverage
            coverage = map_0220_to_coverage(record)
            key = make_contract_key(coverage.vu_nummer, coverage.versicherungsschein_nr, coverage.sparte)
            
            if key in contracts_dict:
                contracts_dict[key].add_coverage(coverage)
                logger.debug(f"Coverage zu Vertrag {key} hinzugefügt")
            else:
                # Suche nach passendem Vertrag mit ähnlichem Schlüssel
                found = False
                for existing_key in contracts_dict:
                    if coverage.versicherungsschein_nr in existing_key:
                        contracts_dict[existing_key].add_coverage(coverage)
                        found = True
                        break
                
                if not found:
                    logger.debug(
                        f"0220 ohne passenden 0200: {key} (Zeile {record.line_number})"
                    )
        
        # 0230, 9999 und andere Satzarten werden zunächst ignoriert
    
    # Kunden mit Verträgen verknüpfen
    gdv_data.link_customers_to_contracts()
    
    # Statistik loggen
    stats = gdv_data.get_statistics()
    logger.info(
        f"Mapping abgeschlossen: {stats['contracts_count']} Verträge, "
        f"{stats['customers_count']} Kunden, {stats['risks_count']} Risiken, "
        f"{stats['coverages_count']} Deckungen"
    )
    
    return gdv_data


# =============================================================================
# Reverse Mapping: Domain-Objekt → ParsedRecord (für Speichern)
# =============================================================================

def domain_to_record_values(obj, satzart: str) -> Dict[str, any]:
    """
    Extrahiert Feldwerte aus einem Domain-Objekt für eine Satzart.
    
    Args:
        obj: Das Domain-Objekt (FileMeta, Customer, Contract, Risk, Coverage)
        satzart: Die Ziel-Satzart
    
    Returns:
        Dictionary mit Feldnamen → Werten
    """
    values = {"satzart": satzart}
    
    if satzart == "0001" and isinstance(obj, FileMeta):
        values.update({
            "vu_nummer": obj.vu_nummer,
            "absender": obj.absender,
            "adressat": obj.adressat,
            "erstellungsdatum_von": obj.erstellungsdatum_von,
            "erstellungsdatum_bis": obj.erstellungsdatum_bis,
            "vermittler_nr": obj.vermittler_nr,
        })
        
    elif satzart == "0100" and isinstance(obj, Customer):
        values.update({
            "vu_nummer": obj.vu_nummer,
            "versicherungsschein_nr": obj.versicherungsschein_nr,
            "folge_nr": obj.folge_nr,
            "anrede_schluessel": obj.anrede.value,
            "name1": obj.name1,
            "name2": obj.name2,
            "name3": obj.name3,
            "titel": obj.titel,
            "strasse": obj.strasse,
            "plz": obj.plz,
            "ort": obj.ort,
            "land_kennzeichen": obj.land,
            "geburtsdatum": obj.geburtsdatum,
            "adresstyp": obj.adresstyp,
        })
        
    elif satzart == "0200" and isinstance(obj, Contract):
        values.update({
            "vu_nummer": obj.vu_nummer,
            "versicherungsschein_nr": obj.versicherungsschein_nr,
            "sparte": obj.sparte,
            "geschaeftsstelle": obj.vermittler_nr,
            "vertragsstatus": obj.vertragsstatus.value,
            "vertragsbeginn": obj.vertragsbeginn,
            "vertragsende": obj.vertragsende,
            "hauptfaelligkeit": obj.hauptfaelligkeit,
            "zahlungsweise": obj.zahlungsweise.value,
            "gesamtbeitrag": obj.gesamtbeitrag_brutto,
            "beitrag_in_we": obj.gesamtbeitrag_netto,
            "waehrung": obj.waehrung,
        })
        
    elif satzart == "0210" and isinstance(obj, Risk):
        values.update({
            "vu_nummer": obj.vu_nummer,
            "versicherungsschein_nr": obj.versicherungsschein_nr,
            "sparte": obj.sparte,
            "satznummer": obj.satznummer,
            "versicherungssumme": obj.versicherungssumme,
        })
        
    elif satzart == "0220" and isinstance(obj, Coverage):
        values.update({
            "vu_nummer": obj.vu_nummer,
            "versicherungsschein_nr": obj.versicherungsschein_nr,
            "sparte": obj.sparte,
            "satznummer": obj.satznummer,
            "wagnisart": obj.wagnis_art,
            "lfd_nummer": obj.wagnis_nr,
        })
    
    return values


# =============================================================================
# Test / Demo
# =============================================================================

if __name__ == "__main__":
    import logging
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    print("=" * 80)
    print("GDV Mapper - Test")
    print("=" * 80)
    
    # Lade und mappe die Testdatei
    from parser.gdv_parser import parse_file
    
    # Versuche echte GDV-Datei
    test_files = [
        r"c:\Users\PaulWeimert\OneDrive - ACENCIA GmbH\Desktop\GDV-Bestandsdatei.gdv",
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "testdata", "sample.gdv")
    ]
    
    for test_file in test_files:
        if os.path.exists(test_file):
            print(f"\nLade Datei: {test_file}")
            parsed = parse_file(test_file)
            
            print(f"Geparst: {len(parsed.records)} Records")
            print(f"Satzarten: {parsed.get_record_count_by_satzart()}")
            
            print(f"\nMappe zu Domain-Objekten...")
            gdv_data = map_parsed_file_to_gdv_data(parsed)
            
            print(f"\n{gdv_data}")
            print(f"Statistiken: {gdv_data.get_statistics()}")
            
            if gdv_data.customers:
                print("\n--- Erste 5 Kunden ---")
                for cust in gdv_data.customers[:5]:
                    print(f"  {cust.vollstaendiger_name} ({cust.adresse_einzeilig})")
            
            if gdv_data.contracts:
                print("\n--- Erste 5 Verträge ---")
                for contract in gdv_data.contracts[:5]:
                    print(f"  {contract.versicherungsschein_nr} | {contract.sparte_name}")
                    print(f"    Status: {contract.vertragsstatus.to_display()}")
                    print(f"    Beitrag: {contract.gesamtbeitrag_brutto:,.2f} EUR")
            
            break
    else:
        print("Keine Testdatei gefunden.")
