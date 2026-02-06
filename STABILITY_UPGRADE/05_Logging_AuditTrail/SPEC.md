# Task 05: Logging & Audit Trail (P2)

## Problem

Logging geht nur an die Console (stdout). Beim Schließen der App sind alle Logs verloren. Kein Audit-Trail, kein Debugging nach Fehler möglich.

## Root Cause

`src/main.py` Zeile 19-22 konfiguriert nur `logging.basicConfig()` mit Default-StreamHandler. Kein FileHandler, keine Rotation.

## Technische Analyse

- Python's `logging` Modul ist thread-safe (internes Lock im Handler)
- `RotatingFileHandler` ist ebenfalls thread-safe
- Alle Module nutzen `logging.getLogger(__name__)` korrekt
- Kein Logging-Handler-Konflikt zu erwarten

## Zielzustand

- File-Logging mit `RotatingFileHandler`
- Log-Datei: `logs/bipro_gdv.log`
- Rotation: 5 MB pro Datei, 3 Backup-Dateien
- Format: Timestamp + Module + Level + Message (wie bestehend)
- Console-Logging bleibt erhalten (Dual-Output)
- `logs/` Ordner in `.gitignore`

## Randbedingungen

- `logs/` Ordner muss automatisch erstellt werden wenn er nicht existiert
- App muss auch ohne Schreibrechte für Logs starten können (Fallback auf Console-only)
- Keine Abhängigkeit auf externe Logging-Libraries

## Performance-Vorgaben

- File-IO darf UI nicht blockieren (RotatingFileHandler ist non-blocking für normale Größen)
- Rotation muss automatisch und unterbrechungsfrei laufen

## Thread-Safety-Vorgaben

- `RotatingFileHandler` ist thread-safe (nutzt internen Lock)
- Keine zusätzlichen Maßnahmen nötig

## Nicht-Ziele

- Kein strukturiertes Logging (JSON)
- Kein Remote-Logging
- Kein Log-Level-Konfiguration über UI
- Keine Änderung bestehender Log-Messages
