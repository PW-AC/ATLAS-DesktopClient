#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Erstellt eine Beispiel-GDV-Datei zum Testen.
"""

import os
import sys

# Pfad zum src-Verzeichnis hinzufügen
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src'))

from parser.gdv_parser import create_empty_record, build_line_from_record

def create_test_file(output_path: str):
    """Erstellt eine Testdatei mit verschiedenen Satzarten."""
    
    lines = []
    
    # =========================================================================
    # 0001 - Vorsatz
    # =========================================================================
    rec = create_empty_record("0001")
    rec.set_field_value("satzart", "0001")
    rec.set_field_value("vu_nummer", "12345")
    rec.set_field_value("absender", "Muster Versicherung AG")
    rec.set_field_value("adressat", "Mustervermittler GmbH")
    rec.set_field_value("erstellungsdatum_von", "2025-01-01")
    rec.set_field_value("erstellungsdatum_bis", "2025-12-31")
    rec.set_field_value("release_stand", "2025.01")
    rec.set_field_value("vermittler_nr", "VERM-001")
    lines.append(build_line_from_record(rec))
    
    # =========================================================================
    # 0100 - Kunde 1 (Max Mustermann)
    # =========================================================================
    rec = create_empty_record("0100")
    rec.set_field_value("satzart", "0100")
    rec.set_field_value("vu_nummer", "12345")
    rec.set_field_value("versicherungsschein_nr", "VS-2024-001234")
    rec.set_field_value("folge_nr", "01")
    rec.set_field_value("anrede_schluessel", "1")  # Herr
    rec.set_field_value("name1", "Mustermann")
    rec.set_field_value("name2", "Max")
    rec.set_field_value("titel", "Dr.")
    rec.set_field_value("strasse", "Musterstraße 123")
    rec.set_field_value("plz", "12345")
    rec.set_field_value("ort", "Musterstadt")
    rec.set_field_value("land_schluessel", "DEU")
    rec.set_field_value("geburtsdatum", "1985-05-15")
    rec.set_field_value("adresstyp", "01")  # VN
    rec.set_field_value("telefon", "+49 123 4567890")
    rec.set_field_value("email", "max@mustermann.de")
    lines.append(build_line_from_record(rec))
    
    # =========================================================================
    # 0200 - Vertrag 1 (Lebensversicherung)
    # =========================================================================
    rec = create_empty_record("0200")
    rec.set_field_value("satzart", "0200")
    rec.set_field_value("vu_nummer", "12345")
    rec.set_field_value("versicherungsschein_nr", "VS-2024-001234")
    rec.set_field_value("sparte", "010")  # Leben
    rec.set_field_value("vermittler_nr", "VERM-001")
    rec.set_field_value("vertragsstatus", "1")  # lebend
    rec.set_field_value("vertragsbeginn", "2020-01-01")
    rec.set_field_value("vertragsende", "2050-01-01")
    rec.set_field_value("hauptfaelligkeit", "2020-01-01")
    rec.set_field_value("zahlungsweise", "1")  # jährlich
    rec.set_field_value("gesamtbeitrag_brutto", 1200.00)
    rec.set_field_value("gesamtbeitrag_netto", 1100.00)
    rec.set_field_value("waehrung", "EUR")
    rec.set_field_value("produktname", "Kapital-Lebensversicherung")
    rec.set_field_value("antragsdatum", "2019-11-15")
    rec.set_field_value("policierungsdatum", "2019-12-20")
    lines.append(build_line_from_record(rec))
    
    # =========================================================================
    # 0210 - Risiko/Person für Vertrag 1
    # =========================================================================
    rec = create_empty_record("0210")
    rec.set_field_value("satzart", "0210")
    rec.set_field_value("vu_nummer", "12345")
    rec.set_field_value("versicherungsschein_nr", "VS-2024-001234")
    rec.set_field_value("sparte", "010")
    rec.set_field_value("satznummer", "1")
    rec.set_field_value("wagnis_art", "0001")  # Kapital-LV
    rec.set_field_value("wagnis_nr", "000001")
    rec.set_field_value("lfd_person_nr", "P00001")
    rec.set_field_value("person_rolle", "01")  # Versicherte Person
    rec.set_field_value("risikobeginn", "2020-01-01")
    rec.set_field_value("risikoende", "2050-01-01")
    rec.set_field_value("versicherungssumme", 100000.00)
    rec.set_field_value("beitrag", 1200.00)
    rec.set_field_value("tarif_bezeichnung", "KLV-PLUS-2020")
    rec.set_field_value("dynamik_prozent", 3.00)
    lines.append(build_line_from_record(rec))
    
    # =========================================================================
    # 0220 - Deckung 1 für Vertrag 1 (Hauptdeckung)
    # =========================================================================
    rec = create_empty_record("0220")
    rec.set_field_value("satzart", "0220")
    rec.set_field_value("vu_nummer", "12345")
    rec.set_field_value("versicherungsschein_nr", "VS-2024-001234")
    rec.set_field_value("sparte", "010")
    rec.set_field_value("satznummer", "1")
    rec.set_field_value("wagnis_art", "0001")
    rec.set_field_value("wagnis_nr", "000001")
    rec.set_field_value("lfd_deckung_nr", "000001")
    rec.set_field_value("deckungsart", "001")  # Hauptdeckung
    rec.set_field_value("deckungsbezeichnung", "Todesfallleistung")
    rec.set_field_value("deckungssumme", 100000.00)
    rec.set_field_value("deckungsbeitrag", 800.00)
    rec.set_field_value("deckungsbeginn", "2020-01-01")
    rec.set_field_value("deckungsende", "2050-01-01")
    rec.set_field_value("leistungsart", "01")  # Kapital
    lines.append(build_line_from_record(rec))
    
    # =========================================================================
    # 0220 - Deckung 2 für Vertrag 1 (BU-Zusatz)
    # =========================================================================
    rec = create_empty_record("0220")
    rec.set_field_value("satzart", "0220")
    rec.set_field_value("vu_nummer", "12345")
    rec.set_field_value("versicherungsschein_nr", "VS-2024-001234")
    rec.set_field_value("sparte", "010")
    rec.set_field_value("satznummer", "2")
    rec.set_field_value("wagnis_art", "0004")  # BU
    rec.set_field_value("wagnis_nr", "000001")
    rec.set_field_value("lfd_deckung_nr", "000002")
    rec.set_field_value("deckungsart", "002")  # Zusatz
    rec.set_field_value("deckungsbezeichnung", "BU-Zusatzversicherung")
    rec.set_field_value("deckungssumme", 2000.00)  # monatl. Rente
    rec.set_field_value("deckungsbeitrag", 400.00)
    rec.set_field_value("deckungsbeginn", "2020-01-01")
    rec.set_field_value("deckungsende", "2050-01-01")
    rec.set_field_value("leistungsart", "02")  # Rente
    lines.append(build_line_from_record(rec))
    
    # =========================================================================
    # Kunde 2 (Erika Musterfrau)
    # =========================================================================
    rec = create_empty_record("0100")
    rec.set_field_value("satzart", "0100")
    rec.set_field_value("vu_nummer", "12345")
    rec.set_field_value("versicherungsschein_nr", "VS-2024-005678")
    rec.set_field_value("folge_nr", "01")
    rec.set_field_value("anrede_schluessel", "2")  # Frau
    rec.set_field_value("name1", "Musterfrau")
    rec.set_field_value("name2", "Erika")
    rec.set_field_value("strasse", "Beispielweg 45")
    rec.set_field_value("plz", "54321")
    rec.set_field_value("ort", "Beispielheim")
    rec.set_field_value("land_schluessel", "DEU")
    rec.set_field_value("geburtsdatum", "1990-08-22")
    rec.set_field_value("adresstyp", "01")
    rec.set_field_value("email", "erika@musterfrau.de")
    lines.append(build_line_from_record(rec))
    
    # =========================================================================
    # 0200 - Vertrag 2 (Haftpflicht)
    # =========================================================================
    rec = create_empty_record("0200")
    rec.set_field_value("satzart", "0200")
    rec.set_field_value("vu_nummer", "12345")
    rec.set_field_value("versicherungsschein_nr", "VS-2024-005678")
    rec.set_field_value("sparte", "040")  # Haftpflicht
    rec.set_field_value("vermittler_nr", "VERM-001")
    rec.set_field_value("vertragsstatus", "1")
    rec.set_field_value("vertragsbeginn", "2023-04-01")
    rec.set_field_value("vertragsende", "2024-04-01")
    rec.set_field_value("hauptfaelligkeit", "2023-04-01")
    rec.set_field_value("zahlungsweise", "1")
    rec.set_field_value("gesamtbeitrag_brutto", 85.50)
    rec.set_field_value("gesamtbeitrag_netto", 72.00)
    rec.set_field_value("waehrung", "EUR")
    rec.set_field_value("produktname", "Privathaftpflicht Komfort")
    lines.append(build_line_from_record(rec))
    
    # =========================================================================
    # 0210 - Risiko für Vertrag 2
    # =========================================================================
    rec = create_empty_record("0210")
    rec.set_field_value("satzart", "0210")
    rec.set_field_value("vu_nummer", "12345")
    rec.set_field_value("versicherungsschein_nr", "VS-2024-005678")
    rec.set_field_value("sparte", "040")
    rec.set_field_value("satznummer", "1")
    rec.set_field_value("wagnis_art", "0040")  # Privat-HP
    rec.set_field_value("wagnis_nr", "000001")
    rec.set_field_value("lfd_person_nr", "P00002")
    rec.set_field_value("person_rolle", "01")
    rec.set_field_value("risikobeginn", "2023-04-01")
    rec.set_field_value("risikoende", "2024-04-01")
    rec.set_field_value("versicherungssumme", 5000000.00)
    rec.set_field_value("beitrag", 85.50)
    rec.set_field_value("tarif_bezeichnung", "PHV-KOMFORT")
    lines.append(build_line_from_record(rec))
    
    # =========================================================================
    # 0220 - Deckung für Vertrag 2
    # =========================================================================
    rec = create_empty_record("0220")
    rec.set_field_value("satzart", "0220")
    rec.set_field_value("vu_nummer", "12345")
    rec.set_field_value("versicherungsschein_nr", "VS-2024-005678")
    rec.set_field_value("sparte", "040")
    rec.set_field_value("satznummer", "1")
    rec.set_field_value("wagnis_art", "0040")
    rec.set_field_value("wagnis_nr", "000001")
    rec.set_field_value("lfd_deckung_nr", "000001")
    rec.set_field_value("deckungsart", "001")
    rec.set_field_value("deckungsbezeichnung", "Personenschäden")
    rec.set_field_value("deckungssumme", 5000000.00)
    rec.set_field_value("deckungsbeitrag", 60.00)
    rec.set_field_value("deckungsbeginn", "2023-04-01")
    rec.set_field_value("deckungsende", "2024-04-01")
    rec.set_field_value("selbstbeteiligung", 150.00)
    lines.append(build_line_from_record(rec))
    
    # Datei schreiben
    with open(output_path, 'w', encoding='latin-1', newline='\r\n') as f:
        for line in lines:
            f.write(line + '\n')
    
    print(f"Testdatei erstellt: {output_path}")
    print(f"Anzahl Sätze: {len(lines)}")
    
    # Statistik
    satzarten = {}
    for line in lines:
        sa = line[:4]
        satzarten[sa] = satzarten.get(sa, 0) + 1
    
    print("\nSatzarten:")
    for sa, count in sorted(satzarten.items()):
        print(f"  {sa}: {count} Sätze")


if __name__ == "__main__":
    output_path = os.path.join(os.path.dirname(__file__), "sample.gdv")
    create_test_file(output_path)



