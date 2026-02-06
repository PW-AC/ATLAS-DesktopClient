#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Roundtrip-Test: Datei laden → bearbeiten → speichern → wieder laden

Testet, dass das Speichern und erneute Laden konsistente Daten ergibt.
"""

import os
import sys
import tempfile

# Pfad zum src-Verzeichnis
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src'))

from parser.gdv_parser import parse_file, save_file, build_line_from_record
from domain.mapper import map_parsed_file_to_gdv_data


def test_roundtrip():
    """Testet den vollständigen Roundtrip."""
    print("=" * 80)
    print("GDV Roundtrip-Test")
    print("=" * 80)
    
    # Original-Datei laden
    original_path = os.path.join(os.path.dirname(__file__), "sample.gdv")
    
    if not os.path.exists(original_path):
        print(f"FEHLER: Testdatei nicht gefunden: {original_path}")
        return False
    
    print(f"\n1. Lade Original: {original_path}")
    parsed1 = parse_file(original_path)
    print(f"   → {len(parsed1.records)} Records geladen")
    
    # Bearbeitung simulieren
    print("\n2. Bearbeite Daten...")
    for record in parsed1.records:
        if record.satzart == "0200":
            old_name = record.get_field_value("produktname")
            record.set_field_value("produktname", "TEST-MODIFIZIERT")
            print(f"   → Produktname geändert: '{old_name}' → 'TEST-MODIFIZIERT'")
            break
    
    # In temporäre Datei speichern
    print("\n3. Speichere in temporäre Datei...")
    with tempfile.NamedTemporaryFile(mode='w', suffix='.gdv', delete=False, encoding='latin-1') as f:
        temp_path = f.name
    
    success = save_file(parsed1, temp_path)
    if not success:
        print("   FEHLER: Speichern fehlgeschlagen!")
        return False
    
    print(f"   → Gespeichert: {temp_path}")
    
    # Gespeicherte Datei wieder laden
    print("\n4. Lade gespeicherte Datei erneut...")
    parsed2 = parse_file(temp_path)
    print(f"   → {len(parsed2.records)} Records geladen")
    
    # Vergleichen
    print("\n5. Vergleiche Originaldaten mit neu geladenen Daten...")
    
    errors = []
    
    # Anzahl Records prüfen
    if len(parsed1.records) != len(parsed2.records):
        errors.append(f"Unterschiedliche Anzahl Records: {len(parsed1.records)} vs {len(parsed2.records)}")
    
    # Records einzeln vergleichen
    for i, (rec1, rec2) in enumerate(zip(parsed1.records, parsed2.records)):
        # Satzart prüfen
        if rec1.satzart != rec2.satzart:
            errors.append(f"Record {i+1}: Satzart unterschiedlich: {rec1.satzart} vs {rec2.satzart}")
            continue
        
        # Felder prüfen
        for field_name in rec1.fields:
            val1 = rec1.get_field_value(field_name)
            val2 = rec2.get_field_value(field_name)
            
            # Werte normalisieren für Vergleich
            if val1 is None:
                val1 = ""
            if val2 is None:
                val2 = ""
            
            if isinstance(val1, float) and isinstance(val2, float):
                if abs(val1 - val2) > 0.01:
                    errors.append(f"Record {i+1}, Feld {field_name}: {val1} vs {val2}")
            elif str(val1).strip() != str(val2).strip():
                errors.append(f"Record {i+1}, Feld {field_name}: '{val1}' vs '{val2}'")
    
    # Prüfen, ob die Modifikation erhalten blieb
    print("\n6. Prüfe ob Modifikation erhalten blieb...")
    modified_found = False
    for record in parsed2.records:
        if record.satzart == "0200":
            produktname = record.get_field_value("produktname")
            if produktname and "TEST-MODIFIZIERT" in produktname:
                print(f"   ✓ Modifikation gefunden: '{produktname}'")
                modified_found = True
                break
    
    if not modified_found:
        errors.append("Modifikation wurde nicht gespeichert!")
    
    # Temporäre Datei löschen
    try:
        os.unlink(temp_path)
        print(f"\n7. Temporäre Datei gelöscht: {temp_path}")
    except:
        pass
    
    # Ergebnis
    print("\n" + "=" * 80)
    if errors:
        print("FEHLER gefunden:")
        for error in errors[:10]:  # Maximal 10 Fehler anzeigen
            print(f"  - {error}")
        if len(errors) > 10:
            print(f"  ... und {len(errors) - 10} weitere Fehler")
        return False
    else:
        print("✓ ALLE TESTS BESTANDEN!")
        print("  - Datei wurde korrekt geladen")
        print("  - Modifikationen wurden gespeichert")
        print("  - Gespeicherte Datei wurde korrekt erneut geladen")
        print("  - Alle Werte sind konsistent")
        return True


def test_line_reconstruction():
    """Testet die Rekonstruktion von Zeilen."""
    print("\n" + "=" * 80)
    print("Zeilen-Rekonstruktions-Test")
    print("=" * 80)
    
    original_path = os.path.join(os.path.dirname(__file__), "sample.gdv")
    parsed = parse_file(original_path)
    
    print(f"\nTeste {len(parsed.records)} Records...")
    
    for record in parsed.records[:3]:  # Erste 3 Records testen
        print(f"\n--- Record {record.line_number}: {record.satzart} ---")
        
        # Original-Zeile
        original_line = record.raw_line
        print(f"Original ({len(original_line)} Zeichen): '{original_line[:60]}...'")
        
        # Rekonstruierte Zeile
        reconstructed = build_line_from_record(record)
        print(f"Rekonstruiert ({len(reconstructed)} Zeichen): '{reconstructed[:60]}...'")
        
        # Vergleich
        if len(original_line) == len(reconstructed):
            print(f"✓ Länge korrekt: {len(reconstructed)}")
        else:
            print(f"✗ Länge unterschiedlich: {len(original_line)} vs {len(reconstructed)}")
        
        # Unterschiede finden
        diffs = []
        for i, (c1, c2) in enumerate(zip(original_line, reconstructed)):
            if c1 != c2:
                diffs.append((i, c1, c2))
        
        if diffs:
            print(f"  Unterschiede an {len(diffs)} Positionen:")
            for pos, c1, c2 in diffs[:5]:
                print(f"    Position {pos}: '{c1}' → '{c2}'")
        else:
            print("  ✓ Keine Unterschiede")
    
    print("\nTest abgeschlossen.")


if __name__ == "__main__":
    success = test_roundtrip()
    test_line_reconstruction()
    
    print("\n" + "=" * 80)
    if success:
        print("🎉 Alle Tests erfolgreich!")
    else:
        print("❌ Einige Tests sind fehlgeschlagen.")
    print("=" * 80)



