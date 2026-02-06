#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GDV Layout-Definitionen (Korrigiert basierend auf echter GDV-Spezifikation)

Dieses Modul enthält die Metadaten für GDV-Satzarten.
Basierend auf der offiziellen GDV-Spezifikation und Analyse echter Dateien.

Referenz: https://www.gdv-online.de/vuvm/bestand/

WICHTIG: 
- Alle Positionen sind 1-basiert (wie in GDV-Dokumentation)
- Teildatensätze (satznummer) haben UNTERSCHIEDLICHE Feldlayouts!
"""

from typing import TypedDict, List, Dict, Optional


class FieldDefinition(TypedDict, total=False):
    """Definition eines einzelnen Feldes."""
    name: str
    label: str
    start: int
    length: int
    type: str  # N, AN, D (Datum)
    required: bool
    description: str
    decimals: Optional[int]
    editable: bool  # Ob das Feld bearbeitet werden darf


class LayoutDefinition(TypedDict):
    """Definition einer Satzart."""
    satzart: str
    name: str
    description: str
    length: int
    fields: List[FieldDefinition]


# =============================================================================
# Satzart 0001 - Vorsatz (Datei-Header)
# =============================================================================
LAYOUT_0001: LayoutDefinition = {
    "satzart": "0001",
    "name": "Vorsatz",
    "description": "Header der GDV-Datei mit Metadaten zur Datenlieferung",
    "length": 256,
    "fields": [
        {"name": "satzart", "label": "Satzart", "start": 1, "length": 4, "type": "N", "required": True, "editable": False},
        {"name": "vu_nummer", "label": "VU-Nummer", "start": 5, "length": 5, "type": "AN", "required": True, "editable": False},
        {"name": "absender", "label": "Absender", "start": 10, "length": 30, "type": "AN", "required": False, "editable": False},
        {"name": "adressat", "label": "Adressat", "start": 40, "length": 30, "type": "AN", "required": False, "editable": False},
        {"name": "erstellungsdatum_von", "label": "Erstellungsdatum Von", "start": 70, "length": 8, "type": "D", "required": False, "editable": False},
        {"name": "erstellungsdatum_bis", "label": "Erstellungsdatum Bis", "start": 78, "length": 8, "type": "D", "required": False, "editable": False},
        {"name": "geschaeftsstelle", "label": "Geschäftsstelle/Vermittler", "start": 86, "length": 10, "type": "AN", "required": False, "editable": False},
        {"name": "version_satzarten", "label": "Versionen Satzarten", "start": 96, "length": 160, "type": "AN", "required": False, "editable": False},
        {"name": "satznummer", "label": "Satznummer", "start": 256, "length": 1, "type": "N", "required": False, "editable": False},
    ]
}


# =============================================================================
# Satzart 0100 - Partnerdaten/Adressteil
# ACHTUNG: Teildatensatz 1 = Adressdaten, Teildatensatz 2-5 = andere Daten!
# =============================================================================
LAYOUT_0100_TD1: LayoutDefinition = {
    "satzart": "0100",
    "teildatensatz": 1,
    "name": "Partnerdaten (Adresse)",
    "description": "Kundendaten / Adressinformationen - Teildatensatz 1",
    "length": 256,
    "fields": [
        {"name": "satzart", "label": "Satzart", "start": 1, "length": 4, "type": "N", "required": True, "editable": False},
        {"name": "vu_nummer", "label": "VU-Nummer", "start": 5, "length": 5, "type": "AN", "required": True, "editable": False},
        {"name": "buendelungskennzeichen", "label": "Bündelungskennzeichen", "start": 10, "length": 1, "type": "AN", "required": False, "editable": False},
        {"name": "sparte", "label": "Sparte", "start": 11, "length": 3, "type": "N", "required": False, "editable": False},
        {"name": "versicherungsschein_nr", "label": "Versicherungsschein-Nr.", "start": 14, "length": 17, "type": "AN", "required": True, "editable": False},
        {"name": "folge_nr", "label": "Folgenummer", "start": 31, "length": 2, "type": "N", "required": False, "editable": False},
        {"name": "geschaeftsstelle", "label": "Geschäftsstelle/Vermittler", "start": 33, "length": 10, "type": "AN", "required": False, "editable": False},
        {"name": "anrede_schluessel", "label": "Anrede (Schlüssel)", "start": 43, "length": 1, "type": "N", "required": False, "editable": True,
         "description": "0=Firma, 1=Herr, 2=Frau, 3=Firma mit Ansprechpartner"},
        {"name": "name1", "label": "Name 1 / Nachname / Firma", "start": 44, "length": 30, "type": "AN", "required": False, "editable": True},
        {"name": "name2", "label": "Name 2 / Vorname", "start": 74, "length": 30, "type": "AN", "required": False, "editable": True},
        {"name": "name3", "label": "Name 3 / Zusatz", "start": 104, "length": 30, "type": "AN", "required": False, "editable": True},
        {"name": "titel", "label": "Titel", "start": 134, "length": 20, "type": "AN", "required": False, "editable": True},
        {"name": "land_kennzeichen", "label": "Länderkennzeichen", "start": 154, "length": 3, "type": "AN", "required": False, "editable": True},
        {"name": "plz", "label": "PLZ", "start": 157, "length": 6, "type": "AN", "required": False, "editable": True},
        {"name": "ort", "label": "Ort", "start": 163, "length": 25, "type": "AN", "required": False, "editable": True},
        {"name": "strasse", "label": "Straße", "start": 188, "length": 30, "type": "AN", "required": False, "editable": True},
        {"name": "geburtsdatum", "label": "Geburtsdatum", "start": 218, "length": 8, "type": "D", "required": False, "editable": True},
        {"name": "zusatz_info", "label": "Zusatz-Info", "start": 226, "length": 3, "type": "AN", "required": False, "editable": False},
        {"name": "adresstyp", "label": "Adresstyp", "start": 229, "length": 2, "type": "AN", "required": False, "editable": False},
        {"name": "reserve", "label": "Reservefeld", "start": 231, "length": 25, "type": "AN", "required": False, "editable": False},
        {"name": "satznummer", "label": "Satznummer", "start": 256, "length": 1, "type": "N", "required": False, "editable": False},
    ]
}

LAYOUT_0100_TD2: LayoutDefinition = {
    "satzart": "0100",
    "teildatensatz": 2,
    "name": "Partnerdaten (Nummern)",
    "description": "Kundennummern, Referenzen - Teildatensatz 2",
    "length": 256,
    "fields": [
        {"name": "satzart", "label": "Satzart", "start": 1, "length": 4, "type": "N", "required": True, "editable": False},
        {"name": "vu_nummer", "label": "VU-Nummer", "start": 5, "length": 5, "type": "AN", "required": True, "editable": False},
        {"name": "buendelungskennzeichen", "label": "Bündelungskennzeichen", "start": 10, "length": 1, "type": "AN", "required": False, "editable": False},
        {"name": "sparte", "label": "Sparte", "start": 11, "length": 3, "type": "N", "required": False, "editable": False},
        {"name": "versicherungsschein_nr", "label": "Versicherungsschein-Nr.", "start": 14, "length": 17, "type": "AN", "required": True, "editable": False},
        {"name": "folge_nr", "label": "Folgenummer", "start": 31, "length": 2, "type": "N", "required": False, "editable": False},
        {"name": "geschaeftsstelle", "label": "Geschäftsstelle/Vermittler", "start": 33, "length": 10, "type": "AN", "required": False, "editable": False},
        {"name": "anrede_schluessel", "label": "Anrede (Schlüssel)", "start": 43, "length": 1, "type": "N", "required": False, "editable": False},
        {"name": "kundennummer", "label": "Kundennummer", "start": 44, "length": 30, "type": "AN", "required": False, "editable": False},
        {"name": "referenznummer", "label": "Referenznummer", "start": 74, "length": 30, "type": "AN", "required": False, "editable": False},
        {"name": "zusatznummer", "label": "Zusatznummer", "start": 104, "length": 30, "type": "AN", "required": False, "editable": False},
        {"name": "steuer_id", "label": "Steuer-ID", "start": 134, "length": 20, "type": "AN", "required": False, "editable": False},
        {"name": "reserve_td2", "label": "Reservefeld", "start": 154, "length": 102, "type": "AN", "required": False, "editable": False},
        {"name": "satznummer", "label": "Satznummer", "start": 256, "length": 1, "type": "N", "required": False, "editable": False},
    ]
}

LAYOUT_0100_TD3: LayoutDefinition = {
    "satzart": "0100",
    "teildatensatz": 3,
    "name": "Partnerdaten (Kommunikation)",
    "description": "Kommunikationsdaten - Teildatensatz 3",
    "length": 256,
    "fields": [
        {"name": "satzart", "label": "Satzart", "start": 1, "length": 4, "type": "N", "required": True, "editable": False},
        {"name": "vu_nummer", "label": "VU-Nummer", "start": 5, "length": 5, "type": "AN", "required": True, "editable": False},
        {"name": "buendelungskennzeichen", "label": "Bündelungskennzeichen", "start": 10, "length": 1, "type": "AN", "required": False, "editable": False},
        {"name": "sparte", "label": "Sparte", "start": 11, "length": 3, "type": "N", "required": False, "editable": False},
        {"name": "versicherungsschein_nr", "label": "Versicherungsschein-Nr.", "start": 14, "length": 17, "type": "AN", "required": True, "editable": False},
        {"name": "folge_nr", "label": "Folgenummer", "start": 31, "length": 2, "type": "N", "required": False, "editable": False},
        {"name": "reserve_td3", "label": "Kommunikationsdaten", "start": 33, "length": 223, "type": "AN", "required": False, "editable": False},
        {"name": "satznummer", "label": "Satznummer", "start": 256, "length": 1, "type": "N", "required": False, "editable": False},
    ]
}

LAYOUT_0100_TD4: LayoutDefinition = {
    "satzart": "0100",
    "teildatensatz": 4,
    "name": "Partnerdaten (Bank)",
    "description": "Bankverbindung - Teildatensatz 4",
    "length": 256,
    "fields": [
        {"name": "satzart", "label": "Satzart", "start": 1, "length": 4, "type": "N", "required": True, "editable": False},
        {"name": "vu_nummer", "label": "VU-Nummer", "start": 5, "length": 5, "type": "AN", "required": True, "editable": False},
        {"name": "buendelungskennzeichen", "label": "Bündelungskennzeichen", "start": 10, "length": 1, "type": "AN", "required": False, "editable": False},
        {"name": "sparte", "label": "Sparte", "start": 11, "length": 3, "type": "N", "required": False, "editable": False},
        {"name": "versicherungsschein_nr", "label": "Versicherungsschein-Nr.", "start": 14, "length": 17, "type": "AN", "required": True, "editable": False},
        {"name": "folge_nr", "label": "Folgenummer", "start": 31, "length": 2, "type": "N", "required": False, "editable": False},
        {"name": "geschaeftsstelle", "label": "Geschäftsstelle/Vermittler", "start": 33, "length": 10, "type": "AN", "required": False, "editable": False},
        # KORRIGIERT: Bankname und Bankort getrennt
        {"name": "bankname", "label": "Bankname", "start": 43, "length": 40, "type": "AN", "required": False, "editable": False},
        {"name": "bankort", "label": "Bankort", "start": 83, "length": 25, "type": "AN", "required": False, "editable": False},
        {"name": "kontoinhaber", "label": "Kontoinhaber", "start": 108, "length": 30, "type": "AN", "required": False, "editable": False},
        {"name": "leer_td4", "label": "Leerfeld", "start": 138, "length": 49, "type": "AN", "required": False, "editable": False},
        # KORRIGIERT: BIC bei Position 187, IBAN bei Position 209
        {"name": "bic", "label": "BIC", "start": 187, "length": 11, "type": "AN", "required": False, "editable": True},
        {"name": "leer_td4_2", "label": "Leerfeld 2", "start": 198, "length": 11, "type": "AN", "required": False, "editable": False},
        {"name": "iban", "label": "IBAN", "start": 209, "length": 34, "type": "AN", "required": False, "editable": True},
        {"name": "reserve_td4", "label": "Reservefeld", "start": 243, "length": 13, "type": "AN", "required": False, "editable": False},
        {"name": "satznummer", "label": "Satznummer", "start": 256, "length": 1, "type": "N", "required": False, "editable": False},
    ]
}

LAYOUT_0100_TD5: LayoutDefinition = {
    "satzart": "0100",
    "teildatensatz": 5,
    "name": "Partnerdaten (Zusatz)",
    "description": "Zusätzliche Partnerdaten - Teildatensatz 5",
    "length": 256,
    "fields": [
        {"name": "satzart", "label": "Satzart", "start": 1, "length": 4, "type": "N", "required": True, "editable": False},
        {"name": "vu_nummer", "label": "VU-Nummer", "start": 5, "length": 5, "type": "AN", "required": True, "editable": False},
        {"name": "buendelungskennzeichen", "label": "Bündelungskennzeichen", "start": 10, "length": 1, "type": "AN", "required": False, "editable": False},
        {"name": "sparte", "label": "Sparte", "start": 11, "length": 3, "type": "N", "required": False, "editable": False},
        {"name": "versicherungsschein_nr", "label": "Versicherungsschein-Nr.", "start": 14, "length": 17, "type": "AN", "required": True, "editable": False},
        {"name": "folge_nr", "label": "Folgenummer", "start": 31, "length": 2, "type": "N", "required": False, "editable": False},
        {"name": "reserve_td5", "label": "Zusatzdaten", "start": 33, "length": 223, "type": "AN", "required": False, "editable": False},
        {"name": "satznummer", "label": "Satznummer", "start": 256, "length": 1, "type": "N", "required": False, "editable": False},
    ]
}

# Standard-Layout für 0100 (TD1)
LAYOUT_0100 = LAYOUT_0100_TD1


# =============================================================================
# Satzart 0200 - Allgemeiner Vertragsteil
# =============================================================================
LAYOUT_0200: LayoutDefinition = {
    "satzart": "0200",
    "name": "Allgemeiner Vertragsteil",
    "description": "Grundlegende Vertragsdaten (Laufzeit, Zahlungsweise, Prämien)",
    "length": 256,
    "fields": [
        {"name": "satzart", "label": "Satzart", "start": 1, "length": 4, "type": "N", "required": True, "editable": False},
        {"name": "vu_nummer", "label": "VU-Nummer", "start": 5, "length": 5, "type": "AN", "required": True, "editable": False},
        {"name": "buendelungskennzeichen", "label": "Bündelungskennzeichen", "start": 10, "length": 1, "type": "AN", "required": False, "editable": False},
        {"name": "sparte", "label": "Sparte", "start": 11, "length": 3, "type": "N", "required": True, "editable": False},
        {"name": "versicherungsschein_nr", "label": "Versicherungsschein-Nr.", "start": 14, "length": 17, "type": "AN", "required": True, "editable": False},
        {"name": "folge_nr", "label": "Folgenummer", "start": 31, "length": 2, "type": "N", "required": False, "editable": False},
        {"name": "geschaeftsstelle", "label": "Geschäftsstelle/Vermittler", "start": 33, "length": 10, "type": "AN", "required": False, "editable": False},
        {"name": "vertragsstatus", "label": "Vertragsstatus", "start": 43, "length": 1, "type": "N", "required": False, "editable": True},
        {"name": "vertragsbeginn", "label": "Vertragsbeginn", "start": 44, "length": 8, "type": "D", "required": False, "editable": True},
        {"name": "vertragsende", "label": "Vertragsende", "start": 52, "length": 8, "type": "D", "required": False, "editable": True},
        {"name": "gesamtbeitrag", "label": "Gesamtbeitrag", "start": 60, "length": 12, "type": "N", "required": False, "decimals": 2, "editable": True},
        {"name": "hauptfaelligkeit", "label": "Hauptfälligkeit", "start": 72, "length": 8, "type": "D", "required": False, "editable": True},
        {"name": "zahlungsweise", "label": "Zahlungsweise", "start": 80, "length": 1, "type": "N", "required": False, "editable": True},
        {"name": "inkasso_art", "label": "Inkasso-Art", "start": 81, "length": 8, "type": "AN", "required": False, "editable": False},
        {"name": "lfd_beitrag", "label": "Laufender Beitrag", "start": 89, "length": 14, "type": "N", "required": False, "decimals": 2, "editable": True},
        {"name": "leer_0200", "label": "Leerfeld", "start": 103, "length": 10, "type": "AN", "required": False, "editable": False},
        # KORRIGIERT: Währung bei Position 113
        {"name": "waehrung", "label": "Währung", "start": 113, "length": 3, "type": "AN", "required": False, "editable": False},
        {"name": "risiko_vs", "label": "Risiko-Versicherungssumme", "start": 116, "length": 12, "type": "N", "required": False, "decimals": 2, "editable": True},
        {"name": "reserve_0200_1", "label": "Reservefeld", "start": 128, "length": 128, "type": "AN", "required": False, "editable": False},
        {"name": "satznummer", "label": "Satznummer", "start": 256, "length": 1, "type": "N", "required": False, "editable": False},
    ]
}


# =============================================================================
# Satzart 0210 - Spartenspezifischer Vertragsteil
# =============================================================================
LAYOUT_0210: LayoutDefinition = {
    "satzart": "0210",
    "name": "Spartenspezifischer Vertragsteil",
    "description": "Wagnisse, Risiken, versicherte Personen je nach Sparte",
    "length": 256,
    "fields": [
        {"name": "satzart", "label": "Satzart", "start": 1, "length": 4, "type": "N", "required": True, "editable": False},
        {"name": "vu_nummer", "label": "VU-Nummer", "start": 5, "length": 5, "type": "AN", "required": True, "editable": False},
        {"name": "buendelungskennzeichen", "label": "Bündelungskennzeichen", "start": 10, "length": 1, "type": "AN", "required": False, "editable": False},
        {"name": "sparte", "label": "Sparte", "start": 11, "length": 3, "type": "N", "required": True, "editable": False},
        {"name": "versicherungsschein_nr", "label": "Versicherungsschein-Nr.", "start": 14, "length": 17, "type": "AN", "required": True, "editable": False},
        {"name": "folge_nr", "label": "Folgenummer", "start": 31, "length": 2, "type": "N", "required": False, "editable": False},
        {"name": "geschaeftsstelle", "label": "Geschäftsstelle", "start": 33, "length": 10, "type": "AN", "required": False, "editable": False},
        {"name": "leer_0210", "label": "Leerfeld", "start": 43, "length": 1, "type": "AN", "required": False, "editable": False},
        # KORRIGIERT: Währung bei Position 44
        {"name": "waehrung", "label": "Währung", "start": 44, "length": 3, "type": "AN", "required": False, "editable": False},
        {"name": "summenart_1", "label": "Summenart 1", "start": 47, "length": 1, "type": "AN", "required": False, "editable": False},
        {"name": "versicherungssumme_1", "label": "Versicherungssumme 1", "start": 48, "length": 14, "type": "N", "required": False, "decimals": 2, "editable": True},
        {"name": "kennzeichen_vs", "label": "Kennzeichen VS", "start": 62, "length": 1, "type": "AN", "required": False, "editable": False},
        {"name": "reserve_0210", "label": "Spartenspezifische Daten", "start": 63, "length": 193, "type": "AN", "required": False, "editable": False},
        {"name": "satznummer", "label": "Satznummer", "start": 256, "length": 1, "type": "N", "required": False, "editable": False},
    ]
}


# =============================================================================
# Satzart 0220 - Deckungen / Leistungsbausteine
# KORRIGIERT: Teildatensatz 1 hat Personendaten ab Position 62!
# =============================================================================
LAYOUT_0220_TD1: LayoutDefinition = {
    "satzart": "0220",
    "teildatensatz": 1,
    "name": "Deckungsteil (Personendaten)",
    "description": "Versicherte Person mit Name, Vorname, Geburtsdatum",
    "length": 256,
    "fields": [
        {"name": "satzart", "label": "Satzart", "start": 1, "length": 4, "type": "N", "required": True, "editable": False},
        {"name": "vu_nummer", "label": "VU-Nummer", "start": 5, "length": 5, "type": "AN", "required": True, "editable": False},
        {"name": "buendelungskennzeichen", "label": "Bündelungskennzeichen", "start": 10, "length": 1, "type": "AN", "required": False, "editable": False},
        {"name": "sparte", "label": "Sparte", "start": 11, "length": 3, "type": "N", "required": True, "editable": False},
        {"name": "versicherungsschein_nr", "label": "Versicherungsschein-Nr.", "start": 14, "length": 17, "type": "AN", "required": True, "editable": False},
        {"name": "folge_nr", "label": "Folgenummer", "start": 31, "length": 2, "type": "N", "required": False, "editable": False},
        {"name": "geschaeftsstelle", "label": "Geschäftsstelle/Vermittler", "start": 33, "length": 10, "type": "AN", "required": False, "editable": False},
        {"name": "leerstelle1", "label": "Leerstelle", "start": 43, "length": 15, "type": "AN", "required": False, "editable": False},
        # KORRIGIERT: Sparte/Kennziffer bei Position 58-60
        {"name": "kennziffer", "label": "Kennziffer/Sparte", "start": 58, "length": 3, "type": "AN", "required": False, "editable": False},
        {"name": "leer2", "label": "Leerfeld", "start": 61, "length": 1, "type": "AN", "required": False, "editable": False},
        # KORRIGIERT: Name beginnt bei Position 62!
        {"name": "name", "label": "Name (Person)", "start": 62, "length": 30, "type": "AN", "required": False, "editable": True},
        # KORRIGIERT: Vorname beginnt bei Position 92!
        {"name": "vorname", "label": "Vorname (Person)", "start": 92, "length": 30, "type": "AN", "required": False, "editable": True},
        # KORRIGIERT: Geburtsdatum bei Position 122-129!
        {"name": "geburtsdatum", "label": "Geburtsdatum", "start": 122, "length": 8, "type": "D", "required": False, "editable": True},
        {"name": "geschlecht", "label": "Geschlecht", "start": 130, "length": 1, "type": "N", "required": False, "editable": True},
        {"name": "reserve_0220_td1", "label": "Weitere Daten", "start": 131, "length": 125, "type": "AN", "required": False, "editable": False},
        {"name": "satznummer", "label": "Satznummer", "start": 256, "length": 1, "type": "N", "required": False, "editable": False},
    ]
}

LAYOUT_0220_TD6: LayoutDefinition = {
    "satzart": "0220",
    "teildatensatz": 6,
    "name": "Deckungsteil (Bezugsberechtigte)",
    "description": "Bezugsberechtigte Person",
    "length": 256,
    "fields": [
        {"name": "satzart", "label": "Satzart", "start": 1, "length": 4, "type": "N", "required": True, "editable": False},
        {"name": "vu_nummer", "label": "VU-Nummer", "start": 5, "length": 5, "type": "AN", "required": True, "editable": False},
        {"name": "buendelungskennzeichen", "label": "Bündelungskennzeichen", "start": 10, "length": 1, "type": "AN", "required": False, "editable": False},
        {"name": "sparte", "label": "Sparte", "start": 11, "length": 3, "type": "N", "required": True, "editable": False},
        {"name": "versicherungsschein_nr", "label": "Versicherungsschein-Nr.", "start": 14, "length": 17, "type": "AN", "required": True, "editable": False},
        {"name": "folge_nr", "label": "Folgenummer", "start": 31, "length": 2, "type": "N", "required": False, "editable": False},
        {"name": "geschaeftsstelle", "label": "Geschäftsstelle/Vermittler", "start": 33, "length": 10, "type": "AN", "required": False, "editable": False},
        {"name": "leerstelle1", "label": "Leerstelle", "start": 43, "length": 15, "type": "AN", "required": False, "editable": False},
        {"name": "kennziffer", "label": "Kennziffer", "start": 58, "length": 5, "type": "AN", "required": False, "editable": False},
        {"name": "vorname_bezug", "label": "Vorname (Bezugsber.)", "start": 63, "length": 30, "type": "AN", "required": False, "editable": True},
        {"name": "name_bezug", "label": "Name (Bezugsber.)", "start": 93, "length": 30, "type": "AN", "required": False, "editable": True},
        {"name": "anteil", "label": "Anteil %", "start": 123, "length": 6, "type": "N", "required": False, "editable": True},
        {"name": "bezug_text", "label": "Bezugsrecht Text", "start": 129, "length": 127, "type": "AN", "required": False, "editable": False},
        {"name": "satznummer", "label": "Satznummer", "start": 256, "length": 1, "type": "N", "required": False, "editable": False},
    ]
}

# Standard-Layout für 0220 - generisch für andere Teildatensätze
LAYOUT_0220_OTHER: LayoutDefinition = {
    "satzart": "0220",
    "name": "Deckungsteil (Sonstige)",
    "description": "Deckungsdaten - verschiedene Teildatensätze",
    "length": 256,
    "fields": [
        {"name": "satzart", "label": "Satzart", "start": 1, "length": 4, "type": "N", "required": True, "editable": False},
        {"name": "vu_nummer", "label": "VU-Nummer", "start": 5, "length": 5, "type": "AN", "required": True, "editable": False},
        {"name": "buendelungskennzeichen", "label": "Bündelungskennzeichen", "start": 10, "length": 1, "type": "AN", "required": False, "editable": False},
        {"name": "sparte", "label": "Sparte", "start": 11, "length": 3, "type": "N", "required": True, "editable": False},
        {"name": "versicherungsschein_nr", "label": "Versicherungsschein-Nr.", "start": 14, "length": 17, "type": "AN", "required": True, "editable": False},
        {"name": "folge_nr", "label": "Folgenummer", "start": 31, "length": 2, "type": "N", "required": False, "editable": False},
        {"name": "geschaeftsstelle", "label": "Geschäftsstelle/Vermittler", "start": 33, "length": 10, "type": "AN", "required": False, "editable": False},
        {"name": "deckungsdaten", "label": "Deckungsdaten", "start": 43, "length": 213, "type": "AN", "required": False, "editable": False},
        {"name": "satznummer", "label": "Satznummer", "start": 256, "length": 1, "type": "N", "required": False, "editable": False},
    ]
}

# Standard-Layout für 0220 (TD1 für Rückwärtskompatibilität)
LAYOUT_0220 = LAYOUT_0220_TD1


# =============================================================================
# Satzart 0230 - Fondsanlage
# =============================================================================
LAYOUT_0230: LayoutDefinition = {
    "satzart": "0230",
    "name": "Fondsanlage",
    "description": "Fondsdaten für fondsgebundene Versicherungen",
    "length": 256,
    "fields": [
        {"name": "satzart", "label": "Satzart", "start": 1, "length": 4, "type": "N", "required": True, "editable": False},
        {"name": "vu_nummer", "label": "VU-Nummer", "start": 5, "length": 5, "type": "AN", "required": True, "editable": False},
        {"name": "buendelungskennzeichen", "label": "Bündelungskennzeichen", "start": 10, "length": 1, "type": "AN", "required": False, "editable": False},
        {"name": "sparte", "label": "Sparte", "start": 11, "length": 3, "type": "N", "required": True, "editable": False},
        {"name": "versicherungsschein_nr", "label": "Versicherungsschein-Nr.", "start": 14, "length": 17, "type": "AN", "required": True, "editable": False},
        {"name": "folge_nr", "label": "Folgenummer", "start": 31, "length": 2, "type": "N", "required": False, "editable": False},
        {"name": "wagnisart_lfd", "label": "Wagnisart/Lfd.Nr.", "start": 33, "length": 2, "type": "AN", "required": False, "editable": False},
        {"name": "fonds_nummer", "label": "Fonds-Nummer", "start": 35, "length": 4, "type": "N", "required": False, "editable": False},
        {"name": "leerstelle", "label": "Leerstelle", "start": 39, "length": 16, "type": "AN", "required": False, "editable": False},
        {"name": "isin", "label": "ISIN", "start": 55, "length": 12, "type": "AN", "required": False, "editable": False},
        {"name": "fonds_name", "label": "Fondsname", "start": 67, "length": 50, "type": "AN", "required": False, "editable": False},
        {"name": "fonds_anteil", "label": "Fondsanteil", "start": 117, "length": 14, "type": "N", "required": False, "decimals": 7, "editable": False},
        {"name": "stichtag", "label": "Stichtag", "start": 131, "length": 8, "type": "D", "required": False, "editable": False},
        {"name": "prozent_anteil", "label": "Prozentanteil", "start": 139, "length": 7, "type": "N", "required": False, "decimals": 4, "editable": False},
        {"name": "reserve_0230", "label": "Reservefeld", "start": 146, "length": 110, "type": "AN", "required": False, "editable": False},
        {"name": "satznummer", "label": "Satznummer", "start": 256, "length": 1, "type": "N", "required": False, "editable": False},
    ]
}


# =============================================================================
# Satzart 9999 - Nachsatz (Datei-Ende)
# =============================================================================
LAYOUT_9999: LayoutDefinition = {
    "satzart": "9999",
    "name": "Nachsatz",
    "description": "Datei-Ende mit Prüfsummen",
    "length": 256,
    "fields": [
        {"name": "satzart", "label": "Satzart", "start": 1, "length": 4, "type": "N", "required": True, "editable": False},
        {"name": "anzahl_saetze", "label": "Anzahl Sätze", "start": 5, "length": 10, "type": "N", "required": False, "editable": False},
        {"name": "geschaeftsstelle", "label": "Geschäftsstelle/Vermittler", "start": 15, "length": 10, "type": "AN", "required": False, "editable": False},
        {"name": "leer", "label": "Leerfeld", "start": 25, "length": 1, "type": "AN", "required": False, "editable": False},
        {"name": "gesamtbeitrag", "label": "Gesamtbeitrag", "start": 26, "length": 15, "type": "N", "required": False, "decimals": 2, "editable": False},
        {"name": "summe_vs", "label": "Summe Versicherungssummen", "start": 41, "length": 15, "type": "N", "required": False, "decimals": 2, "editable": False},
        {"name": "reserve_9999", "label": "Reservefeld", "start": 56, "length": 200, "type": "AN", "required": False, "editable": False},
        {"name": "satznummer", "label": "Satznummer", "start": 256, "length": 1, "type": "N", "required": False, "editable": False},
    ]
}


# =============================================================================
# Teildatensatz-spezifische Layouts
# =============================================================================
TEILDATENSATZ_LAYOUTS = {
    "0100": {
        "1": LAYOUT_0100_TD1,
        "2": LAYOUT_0100_TD2,
        "3": LAYOUT_0100_TD3,
        "4": LAYOUT_0100_TD4,
        "5": LAYOUT_0100_TD5,
    },
    "0220": {
        "1": LAYOUT_0220_TD1,
        "6": LAYOUT_0220_TD6,
        # Andere Teildatensätze nutzen das generische Layout
    }
}


# =============================================================================
# Zentrale Registry aller Layouts (Standard-Layouts)
# =============================================================================
RECORD_LAYOUTS: Dict[str, LayoutDefinition] = {
    "0001": LAYOUT_0001,
    "0100": LAYOUT_0100,
    "0200": LAYOUT_0200,
    "0210": LAYOUT_0210,
    "0220": LAYOUT_0220,
    "0230": LAYOUT_0230,
    "9999": LAYOUT_9999,
}


# =============================================================================
# Hilfsfunktionen
# =============================================================================

def get_layout(satzart: str, teildatensatz: str = None, wagnisart: str = None) -> Optional[LayoutDefinition]:
    """
    Gibt das Layout für eine Satzart zurück.
    
    Args:
        satzart: Die Satzart (z.B. "0100", "0220")
        teildatensatz: Optional die Teildatensatz-Nummer (z.B. "1", "2")
        wagnisart: Optional die Wagnisart bei 0220 (z.B. "person", "sonstige")
    
    Returns:
        Das passende Layout oder None
    """
    # Spezialfall 0220: Wagnisart bestimmt das Layout
    if satzart == "0220" and wagnisart == "sonstige":
        return LAYOUT_0220_OTHER
    
    # Prüfe ob es ein teildatensatz-spezifisches Layout gibt
    if teildatensatz and satzart in TEILDATENSATZ_LAYOUTS:
        td_layouts = TEILDATENSATZ_LAYOUTS[satzart]
        if teildatensatz in td_layouts:
            return td_layouts[teildatensatz]
        # Fallback auf generisches Layout für diese Satzart
        if satzart == "0220":
            return LAYOUT_0220_OTHER
    
    # Standard-Layout zurückgeben
    return RECORD_LAYOUTS.get(satzart)


def get_all_satzarten() -> List[str]:
    """Gibt eine Liste aller unterstützten Satzarten zurück."""
    return list(RECORD_LAYOUTS.keys())


def get_field_by_name(satzart: str, field_name: str, teildatensatz: str = None) -> Optional[FieldDefinition]:
    """Gibt die Felddefinition für ein bestimmtes Feld zurück."""
    layout = get_layout(satzart, teildatensatz)
    if not layout:
        return None
    for field in layout["fields"]:
        if field["name"] == field_name:
            return field
    return None


def get_layout_info(satzart: str, teildatensatz: str = None) -> str:
    """Gibt eine formatierte Beschreibung eines Layouts zurück."""
    layout = get_layout(satzart, teildatensatz)
    if not layout:
        return f"Unbekannte Satzart: {satzart}"
    
    td_info = f" (Teildatensatz {teildatensatz})" if teildatensatz else ""
    lines = [
        f"Satzart {layout['satzart']}{td_info}: {layout['name']}",
        f"Beschreibung: {layout['description']}",
        f"Satzlänge: {layout['length']} Bytes",
        f"Felder: {len(layout['fields'])}",
        "",
        "Feldübersicht:",
        "-" * 80,
    ]
    
    for field in layout["fields"]:
        req = "*" if field.get("required", False) else " "
        decimals = f" ({field.get('decimals', 0)} Dez.)" if field.get("decimals") else ""
        edit = "✏️" if field.get("editable", True) else "🔒"
        lines.append(
            f"  {req} {edit} {field['name']:25} | Pos {field['start']:3}-{field['start']+field['length']-1:3} "
            f"| Länge {field['length']:3} | Typ {field['type']}{decimals}"
        )
    
    return "\n".join(lines)


# =============================================================================
# Sparten-Bezeichnungen
# =============================================================================
SPARTEN_BEZEICHNUNGEN: Dict[str, str] = {
    "000": "Allgemein",
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
    "140": "Luftfahrt",
    "170": "Feuer",
    "190": "Einbruchdiebstahl",
}

# Anrede-Schlüssel Mapping
ANREDE_BEZEICHNUNGEN: Dict[str, str] = {
    "0": "Firma",
    "1": "Herr",
    "2": "Frau",
    "3": "Firma (mit Ansprechpartner)",
}


def get_sparten_bezeichnung(code: str) -> str:
    """Gibt die Bezeichnung für einen Sparten-Code zurück."""
    code = str(code).strip().zfill(3) if code else ""
    return SPARTEN_BEZEICHNUNGEN.get(code, f"Sparte {code}" if code else "Unbekannt")


def get_anrede_bezeichnung(code: str) -> str:
    """Gibt die Anrede für einen Schlüssel zurück."""
    code = str(code).strip() if code else ""
    return ANREDE_BEZEICHNUNGEN.get(code, "")


# =============================================================================
# Test / Demo
# =============================================================================
if __name__ == "__main__":
    print("=" * 80)
    print("GDV Layout-Definitionen (Mit Teildatensatz-Unterstützung)")
    print("=" * 80)
    
    for satzart in get_all_satzarten():
        print()
        print(get_layout_info(satzart))
        
        # Zeige auch Teildatensätze
        if satzart in TEILDATENSATZ_LAYOUTS:
            for td in TEILDATENSATZ_LAYOUTS[satzart]:
                print()
                print(get_layout_info(satzart, td))
