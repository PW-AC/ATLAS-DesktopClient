#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GDV Parser

Generischer Parser für GDV-Datensätze (Fixed-Width-Format).
Der Parser nutzt die Layout-Metadaten aus gdv_layouts, um Felder
dynamisch aus Zeilen zu extrahieren.

Hauptfunktionen:
- parse_field(): Einzelnes Feld aus einer Zeile extrahieren
- parse_record(): Komplette Zeile parsen
- parse_file(): Ganze Datei einlesen und parsen
- build_line_from_record(): Geparstes Record zurück in Fixed-Width-Zeile umwandeln
"""

import os
import logging
from typing import Optional, Dict, List, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime

# Import der Layout-Definitionen
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from layouts.gdv_layouts import (
    get_layout, get_all_satzarten, LayoutDefinition, FieldDefinition
)


# Logger konfigurieren
logger = logging.getLogger(__name__)


# =============================================================================
# Datenklassen für geparste Datensätze
# =============================================================================

@dataclass
class ParsedField:
    """Ein geparstes Feld mit Metadaten."""
    name: str
    label: str
    value: Any
    raw_value: str
    field_type: str
    start: int
    length: int
    is_valid: bool = True
    error_message: Optional[str] = None


@dataclass
class ParsedRecord:
    """Ein geparstes GDV-Record (eine Zeile)."""
    line_number: int
    satzart: str
    satzart_name: str
    raw_line: str
    fields: Dict[str, ParsedField] = field(default_factory=dict)
    is_known: bool = True
    is_valid: bool = True
    errors: List[str] = field(default_factory=list)
    
    def get_field_value(self, field_name: str, default: Any = None) -> Any:
        """Gibt den Wert eines Feldes zurück."""
        if field_name in self.fields:
            return self.fields[field_name].value
        return default
    
    def get_field_raw(self, field_name: str, default: str = "") -> str:
        """Gibt den Rohwert eines Feldes zurück."""
        if field_name in self.fields:
            return self.fields[field_name].raw_value
        return default
    
    def set_field_value(self, field_name: str, value: Any) -> bool:
        """
        Setzt den Wert eines Feldes.
        
        Returns:
            True wenn erfolgreich, False wenn Feld nicht existiert
        """
        if field_name not in self.fields:
            return False
        
        self.fields[field_name].value = value
        return True
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiert das Record in ein Dictionary."""
        return {
            field_name: pf.value 
            for field_name, pf in self.fields.items()
        }


@dataclass
class ParsedFile:
    """Eine geparste GDV-Datei."""
    filepath: str
    filename: str
    encoding: str
    total_lines: int
    records: List[ParsedRecord] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    def get_records_by_satzart(self, satzart: str) -> List[ParsedRecord]:
        """Filtert Records nach Satzart."""
        return [r for r in self.records if r.satzart == satzart]
    
    def get_record_count_by_satzart(self) -> Dict[str, int]:
        """Zählt Records pro Satzart."""
        counts: Dict[str, int] = {}
        for record in self.records:
            counts[record.satzart] = counts.get(record.satzart, 0) + 1
        return counts


# =============================================================================
# Parsing-Funktionen
# =============================================================================

def parse_field(
    raw_line: str, 
    field_def: FieldDefinition
) -> ParsedField:
    """
    Extrahiert ein einzelnes Feld aus einer Zeile basierend auf der Felddefinition.
    
    Args:
        raw_line: Die komplette Rohzeile
        field_def: Die Felddefinition mit Start, Länge, Typ etc.
    
    Returns:
        ParsedField mit extrahiertem Wert
    """
    # GDV-Offsets sind 1-basiert, Python ist 0-basiert
    start = field_def["start"] - 1
    length = field_def["length"]
    end = start + length
    field_type = field_def.get("type", "AN")
    decimals = field_def.get("decimals", 0)
    
    # Rohwert extrahieren
    if start >= len(raw_line):
        raw_value = ""
    elif end > len(raw_line):
        raw_value = raw_line[start:]
    else:
        raw_value = raw_line[start:end]
    
    # Wert je nach Typ konvertieren
    value: Any = None
    is_valid = True
    error_message = None
    
    try:
        if field_type == "N":
            # Numerisches Feld
            stripped = raw_value.strip()
            
            # Entferne alle nicht-numerischen Zeichen (außer Minus am Anfang)
            clean_value = ""
            for i, c in enumerate(stripped):
                if c.isdigit():
                    clean_value += c
                elif c == '-' and i == 0:
                    clean_value += c
            
            if clean_value == "" or clean_value == "-":
                value = None
            elif clean_value.lstrip('0-') == "" or clean_value.lstrip('-') == "0" * len(clean_value.lstrip('-')):
                # Nur Nullen
                if decimals and decimals > 0:
                    value = 0.0
                else:
                    value = clean_value if clean_value else None
            else:
                if decimals and decimals > 0:
                    # Implizite Dezimalstellen
                    try:
                        int_value = int(clean_value)
                        value = int_value / (10 ** decimals)
                    except ValueError:
                        value = raw_value  # Fallback
                else:
                    value = clean_value
                    
        elif field_type == "D":
            # Datumsfeld (TTMMJJJJ oder YYYYMMDD)
            stripped = raw_value.strip()
            if stripped == "" or stripped == "0" * 8 or stripped == "00000000":
                value = None
            else:
                # Versuche verschiedene Datumsformate
                if len(stripped) == 8:
                    # Prüfe ob YYYYMMDD oder TTMMJJJJ
                    if stripped[:2].isdigit() and int(stripped[:2]) <= 31:
                        # Wahrscheinlich TTMMJJJJ
                        day = stripped[0:2]
                        month = stripped[2:4]
                        year = stripped[4:8]
                        value = f"{year}-{month}-{day}"
                    else:
                        # YYYYMMDD
                        year = stripped[0:4]
                        month = stripped[4:6]
                        day = stripped[6:8]
                        value = f"{year}-{month}-{day}"
                else:
                    value = stripped
                    
        else:  # AN (alphanumerisch) oder unbekannt
            # Beide Seiten trimmen für saubere Anzeige
            value = raw_value.strip()
            
    except (ValueError, IndexError) as e:
        is_valid = False
        error_message = f"Parsing-Fehler: {e}"
        value = raw_value
    
    return ParsedField(
        name=field_def["name"],
        label=field_def.get("label", field_def["name"]),
        value=value,
        raw_value=raw_value,
        field_type=field_type,
        start=field_def["start"],
        length=length,
        is_valid=is_valid,
        error_message=error_message
    )


def parse_record(raw_line: str, line_number: int = 0) -> ParsedRecord:
    """
    Parst eine komplette GDV-Zeile basierend auf der erkannten Satzart.
    
    WICHTIG: Erkennt auch die Teildatensatz-Nummer (Position 256) und 
    verwendet das passende teildatensatz-spezifische Layout!
    
    Args:
        raw_line: Die Rohzeile
        line_number: Zeilennummer in der Datei (für Fehlerberichte)
    
    Returns:
        ParsedRecord mit allen Feldern
    """
    # Satzart aus den ersten 4 Zeichen extrahieren
    if len(raw_line) < 4:
        return ParsedRecord(
            line_number=line_number,
            satzart="????",
            satzart_name="Ungültig",
            raw_line=raw_line,
            is_known=False,
            is_valid=False,
            errors=["Zeile zu kurz für Satzart-Erkennung (< 4 Zeichen)"]
        )
    
    satzart = raw_line[0:4]
    
    # Teildatensatz-Nummer aus Position 256 (Index 255) lesen
    teildatensatz = None
    if len(raw_line) >= 256:
        td_char = raw_line[255]
        if td_char.isdigit():
            teildatensatz = td_char
    
    # Spezialfall 0220 Teildatensatz 1: Kennziffer bei Position 58-60 prüfen
    # Nur wenn Kennziffer "0" oder " 0" enthält, sind es Personendaten
    # Sonst sind es sonstige Deckungsdaten (z.B. Kennziffer "91")
    wagnisart = None
    if satzart == "0220" and teildatensatz == "1" and len(raw_line) >= 61:
        kennziffer = raw_line[57:61].strip()  # Position 58-61
        # Prüfe ob es Personendaten sind (Kennziffer endet mit "0" und gefolgt von Buchstaben)
        # Bei Personendaten: " 0 S" (Leerzeichen, 0, Leerzeichen, dann Name mit Buchstabe)
        # Bei Deckungsdaten: "91" gefolgt von Zahlen
        pos_60_61 = raw_line[59:62] if len(raw_line) >= 62 else ""
        if pos_60_61 and pos_60_61[0] == "0" and (len(pos_60_61) < 2 or not pos_60_61[1].isdigit()):
            # Kennziffer 0 gefolgt von Leerzeichen oder Buchstabe → Personendaten
            wagnisart = "person"
        else:
            # Andere Kennziffer (z.B. 91) → Sonstige Deckungsdaten
            wagnisart = "sonstige"
            teildatensatz = None  # Verwende generisches Layout
    
    # Layout mit Teildatensatz- und Wagnisart-Unterstützung holen
    layout = get_layout(satzart, teildatensatz, wagnisart)
    
    if not layout:
        # Unbekannte Satzart
        logger.warning(f"Zeile {line_number}: Unbekannte Satzart '{satzart}'")
        return ParsedRecord(
            line_number=line_number,
            satzart=satzart,
            satzart_name=f"Unbekannt ({satzart})",
            raw_line=raw_line,
            is_known=False,
            is_valid=True,  # Syntaktisch gültig, nur unbekannt
            errors=[]
        )
    
    # Record-Name inkl. Teildatensatz-Info und Wagnisart
    satzart_name = layout["name"]
    if wagnisart == "person":
        satzart_name = "Deckungsteil (Personendaten)"
    elif wagnisart == "sonstige":
        satzart_name = "Deckungsteil (Sonstige)"
    
    # Record mit Metadaten initialisieren
    record = ParsedRecord(
        line_number=line_number,
        satzart=satzart,
        satzart_name=satzart_name,
        raw_line=raw_line,
        is_known=True,
        is_valid=True
    )
    
    # Alle Felder parsen
    for field_def in layout["fields"]:
        parsed_field = parse_field(raw_line, field_def)
        record.fields[field_def["name"]] = parsed_field
        
        # Validierung: Pflichtfeld prüfen
        if field_def.get("required", False) and parsed_field.value in (None, ""):
            record.errors.append(
                f"Pflichtfeld '{field_def['label']}' ist leer"
            )
            record.is_valid = False
        
        # Parsing-Fehler übernehmen
        if not parsed_field.is_valid:
            record.errors.append(
                f"Feld '{field_def['label']}': {parsed_field.error_message}"
            )
            record.is_valid = False
    
    return record


def parse_file(
    filepath: str, 
    encoding: str = "cp1252"
) -> ParsedFile:
    """
    Liest und parst eine komplette GDV-Datei.
    
    Args:
        filepath: Pfad zur GDV-Datei
        encoding: Zeichenkodierung (Standard: cp1252/Windows-1252 für deutsche Umlaute)
    
    Returns:
        ParsedFile mit allen Records
    """
    # Versuche verschiedene Encodings für deutsche Umlaute
    encodings_to_try = [encoding, "cp1252", "latin-1", "iso-8859-15", "utf-8"]
    
    lines = None
    used_encoding = encoding
    
    for enc in encodings_to_try:
        try:
            with open(filepath, "r", encoding=enc) as f:
                lines = f.readlines()
            used_encoding = enc
            break
        except (UnicodeDecodeError, LookupError):
            continue
        except FileNotFoundError:
            parsed_file = ParsedFile(
                filepath=filepath,
                filename=os.path.basename(filepath),
                encoding=encoding,
                total_lines=0
            )
            parsed_file.errors.append(f"Datei nicht gefunden: {filepath}")
            return parsed_file
    
    if lines is None:
        # Fallback: Binary lesen und mit Fehlerbehandlung decodieren
        try:
            with open(filepath, "rb") as f:
                content = f.read()
            # Versuche cp1252 mit Ersetzung für ungültige Zeichen
            lines = content.decode("cp1252", errors="replace").splitlines(keepends=True)
            used_encoding = "cp1252 (mit Ersetzung)"
        except Exception as e:
            parsed_file = ParsedFile(
                filepath=filepath,
                filename=os.path.basename(filepath),
                encoding=encoding,
                total_lines=0
            )
            parsed_file.errors.append(f"Fehler beim Lesen: {e}")
            return parsed_file
    
    parsed_file = ParsedFile(
        filepath=filepath,
        filename=os.path.basename(filepath),
        encoding=used_encoding,
        total_lines=0
    )
    
    parsed_file.total_lines = len(lines)
    
    # Zeilen parsen
    for line_number, raw_line in enumerate(lines, start=1):
        # Zeilenende entfernen
        raw_line = raw_line.rstrip("\r\n")
        
        # Leere Zeilen überspringen
        if not raw_line or raw_line.strip() == "":
            parsed_file.warnings.append(
                f"Zeile {line_number}: Leere Zeile übersprungen"
            )
            continue
        
        # Record parsen
        record = parse_record(raw_line, line_number)
        parsed_file.records.append(record)
        
        # Fehler sammeln
        for error in record.errors:
            logger.warning(f"Zeile {line_number}: {error}")
    
    # Zusammenfassung loggen
    counts = parsed_file.get_record_count_by_satzart()
    logger.info(
        f"Datei '{parsed_file.filename}' geparst: "
        f"{len(parsed_file.records)} Records, "
        f"Satzarten: {counts}"
    )
    
    return parsed_file


# =============================================================================
# Serialisierung (Record → Fixed-Width-Zeile)
# =============================================================================

def format_field_value(
    value: Any, 
    field_def: FieldDefinition
) -> str:
    """
    Formatiert einen Feldwert für die Ausgabe als Fixed-Width.
    
    Args:
        value: Der zu formatierende Wert
        field_def: Die Felddefinition
    
    Returns:
        Formatierter String mit exakter Feldlänge
    """
    length = field_def["length"]
    field_type = field_def.get("type", "AN")
    decimals = field_def.get("decimals", 0)
    
    if value is None:
        value = ""
    
    if field_type == "N":
        # Numerisches Feld: rechtsbündig mit führenden Nullen
        if decimals and decimals > 0:
            # Dezimalzahl zurückkonvertieren
            if isinstance(value, (int, float)):
                int_value = int(value * (10 ** decimals))
                formatted = str(int_value)
            else:
                formatted = str(value).replace(".", "").replace(",", "")
        else:
            formatted = str(value) if value else ""
        
        # Mit führenden Nullen auffüllen
        formatted = formatted.zfill(length)
        
        # Auf exakte Länge kürzen (falls zu lang)
        if len(formatted) > length:
            formatted = formatted[-length:]
            
    elif field_type == "D":
        # Datumsfeld: TTMMJJJJ Format
        if isinstance(value, str) and "-" in value:
            # ISO-Format YYYY-MM-DD → TTMMJJJJ
            parts = value.split("-")
            if len(parts) == 3:
                formatted = f"{parts[2]}{parts[1]}{parts[0]}"
            else:
                formatted = value.replace("-", "")
        elif isinstance(value, datetime):
            formatted = value.strftime("%d%m%Y")
        else:
            formatted = str(value) if value else ""
        
        # Mit Nullen auffüllen
        formatted = formatted.ljust(length, "0")[:length]
        
    else:  # AN (alphanumerisch)
        # Alphanumerisch: linksbündig mit Leerzeichen auffüllen
        formatted = str(value) if value else ""
        formatted = formatted.ljust(length)
        
        # Auf exakte Länge kürzen
        if len(formatted) > length:
            formatted = formatted[:length]
    
    return formatted


def build_line_from_record(record: ParsedRecord) -> str:
    """
    Baut aus einem ParsedRecord eine Fixed-Width-Zeile.
    
    Args:
        record: Das zu serialisierende Record
    
    Returns:
        Die Fixed-Width-Zeile als String
    """
    # Teildatensatz-Nummer aus Satznummer-Feld holen
    teildatensatz = None
    if "satznummer" in record.fields:
        satznr_val = record.fields["satznummer"].value
        if satznr_val and str(satznr_val).strip().isdigit():
            teildatensatz = str(satznr_val).strip()
    
    layout = get_layout(record.satzart, teildatensatz)
    if not layout:
        # Für unbekannte Satzarten: Rohzeile zurückgeben
        return record.raw_line
    
    # Zeile mit Leerzeichen initialisieren (exakte Satzlänge)
    line_length = layout["length"]
    line_chars = [" "] * line_length
    
    # Felder eintragen
    for field_def in layout["fields"]:
        field_name = field_def["name"]
        
        # Wert holen (aus geparstem Feld oder leer)
        if field_name in record.fields:
            value = record.fields[field_name].value
        else:
            value = None
        
        # Wert formatieren
        formatted = format_field_value(value, field_def)
        
        # In Zeile eintragen (1-basierter Offset → 0-basiert)
        start = field_def["start"] - 1
        for i, char in enumerate(formatted):
            if start + i < line_length:
                line_chars[start + i] = char
    
    return "".join(line_chars)


def save_file(
    parsed_file: ParsedFile, 
    output_path: str, 
    encoding: str = "latin-1"
) -> bool:
    """
    Speichert eine ParsedFile als GDV-Datei.
    
    Args:
        parsed_file: Die zu speichernde Datei
        output_path: Zielpfad
        encoding: Zeichenkodierung
    
    Returns:
        True bei Erfolg, False bei Fehler
    """
    try:
        with open(output_path, "w", encoding=encoding, newline="\r\n") as f:
            for record in parsed_file.records:
                line = build_line_from_record(record)
                f.write(line + "\n")
        
        logger.info(f"Datei gespeichert: {output_path} ({len(parsed_file.records)} Records)")
        return True
        
    except Exception as e:
        logger.error(f"Fehler beim Speichern: {e}")
        return False


# =============================================================================
# Hilfsfunktionen
# =============================================================================

def create_empty_record(satzart: str, line_number: int = 0, teildatensatz: str = "1") -> Optional[ParsedRecord]:
    """
    Erstellt ein leeres Record für eine Satzart.
    
    Args:
        satzart: Die gewünschte Satzart
        line_number: Optionale Zeilennummer
        teildatensatz: Der Teildatensatz (Standard: "1")
    
    Returns:
        ParsedRecord mit leeren Feldern oder None bei unbekannter Satzart
    """
    layout = get_layout(satzart, teildatensatz)
    if not layout:
        return None
    
    record = ParsedRecord(
        line_number=line_number,
        satzart=satzart,
        satzart_name=layout["name"],
        raw_line="",
        is_known=True,
        is_valid=True
    )
    
    # Alle Felder mit Standardwerten initialisieren
    for field_def in layout["fields"]:
        # Satzart-Feld mit korrektem Wert
        if field_def["name"] == "satzart":
            default_value = satzart
        else:
            default_value = None
        
        record.fields[field_def["name"]] = ParsedField(
            name=field_def["name"],
            label=field_def.get("label", field_def["name"]),
            value=default_value,
            raw_value="",
            field_type=field_def.get("type", "AN"),
            start=field_def["start"],
            length=field_def["length"],
            is_valid=True
        )
    
    # Raw-Line generieren
    record.raw_line = build_line_from_record(record)
    
    return record


def validate_field_value(
    value: Any, 
    field_def: FieldDefinition
) -> Tuple[bool, Optional[str]]:
    """
    Validiert einen Wert gegen eine Felddefinition.
    
    Args:
        value: Der zu validierende Wert
        field_def: Die Felddefinition
    
    Returns:
        Tuple (is_valid, error_message)
    """
    field_type = field_def.get("type", "AN")
    length = field_def["length"]
    required = field_def.get("required", False)
    
    # Pflichtfeldprüfung
    if required and (value is None or str(value).strip() == ""):
        return False, f"Pflichtfeld '{field_def['label']}' darf nicht leer sein"
    
    if value is None or str(value).strip() == "":
        return True, None  # Leere nicht-Pflichtfelder sind OK
    
    str_value = str(value)
    
    # Typspezifische Validierung
    if field_type == "N":
        # Numerisch: nur Ziffern (und ggf. Dezimalpunkt für Anzeige)
        clean_value = str_value.replace(".", "").replace(",", "").replace("-", "")
        if not clean_value.isdigit():
            return False, f"Feld '{field_def['label']}' muss numerisch sein"
        
        # Längenprüfung (ohne Dezimalzeichen)
        decimals = field_def.get("decimals", 0)
        if decimals:
            # Bei Dezimalzahlen: Prüfe Gesamtstellen
            try:
                float_val = float(str_value.replace(",", "."))
                int_val = int(float_val * (10 ** decimals))
                if len(str(abs(int_val))) > length:
                    return False, f"Wert zu groß für Feld '{field_def['label']}' (max {length} Stellen)"
            except ValueError:
                return False, f"Ungültiger numerischer Wert für '{field_def['label']}'"
        else:
            if len(clean_value) > length:
                return False, f"Wert zu lang für Feld '{field_def['label']}' (max {length} Zeichen)"
                
    elif field_type == "D":
        # Datum: Verschiedene Formate erlaubt
        if len(str_value) > 10:  # YYYY-MM-DD = 10 Zeichen
            return False, f"Ungültiges Datumsformat für '{field_def['label']}'"
            
    else:  # AN
        # Alphanumerisch: Längenprüfung
        if len(str_value) > length:
            return False, f"Text zu lang für Feld '{field_def['label']}' (max {length} Zeichen)"
    
    return True, None


# =============================================================================
# Test / Demo
# =============================================================================

if __name__ == "__main__":
    # Logging konfigurieren für Tests
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    print("=" * 80)
    print("GDV Parser - Test")
    print("=" * 80)
    
    # Test 1: Leeres Record erstellen
    print("\n--- Test 1: Leeres 0200-Record erstellen ---")
    record = create_empty_record("0200")
    if record:
        print(f"Satzart: {record.satzart} ({record.satzart_name})")
        print(f"Anzahl Felder: {len(record.fields)}")
        print(f"Raw-Line Länge: {len(record.raw_line)}")
        print(f"Erste 50 Zeichen: '{record.raw_line[:50]}'")
    
    # Test 2: Zeile parsen
    print("\n--- Test 2: Beispielzeile parsen ---")
    # Simulierte 0200-Zeile (256 Zeichen)
    test_line = (
        "0200"  # Satzart
        "12345"  # VU-Nummer
        "4711-1234567890  "  # Versicherungsschein-Nr (17)
        "010"  # Sparte
        "987654         "  # Vermittler (15)
        "1"  # Status
        "01012020"  # Vertragsbeginn
        "31122030"  # Vertragsende
        "01012020"  # Hauptfälligkeit
        "1"  # Zahlungsweise
        "000000050000"  # Bruttobeitrag (500,00€)
        "000000045000"  # Nettobeitrag (450,00€)
        "EUR"  # Währung
        "Lebensversicherung Plus     "  # Produktname (30)
    )
    # Mit Leerzeichen auf 256 Zeichen auffüllen
    test_line = test_line.ljust(256)
    
    record = parse_record(test_line, 1)
    print(f"Satzart: {record.satzart} ({record.satzart_name})")
    print(f"Gültig: {record.is_valid}")
    print(f"Bekannt: {record.is_known}")
    print("\nGeparste Felder:")
    for name, pf in list(record.fields.items())[:10]:
        print(f"  {name:25}: {pf.value!r}")
    
    # Test 3: Modifikation und Zurückschreiben
    print("\n--- Test 3: Record modifizieren und serialisieren ---")
    record.set_field_value("produktname", "Geändert Test")
    record.set_field_value("gesamtbeitrag_brutto", 750.00)
    
    new_line = build_line_from_record(record)
    print(f"Neue Zeile (erste 100 Zeichen):")
    print(f"'{new_line[:100]}'")
    print(f"Zeilenlänge: {len(new_line)}")
    
    # Test 4: Validierung
    print("\n--- Test 4: Feldvalidierung ---")
    from layouts.gdv_layouts import get_field_by_name
    
    field_def = get_field_by_name("0200", "versicherungsschein_nr")
    if field_def:
        valid, error = validate_field_value("12345678901234567890", field_def)
        print(f"Zu lang (20 Zeichen): valid={valid}, error={error}")
        
        valid, error = validate_field_value("VALID-123", field_def)
        print(f"OK (9 Zeichen): valid={valid}, error={error}")
    
    print("\n" + "=" * 80)
    print("Tests abgeschlossen!")

