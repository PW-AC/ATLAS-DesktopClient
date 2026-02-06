# Task 06: Smoke Tests & Minimal CI (P2)

## Problem

Es gibt keine automatisierten Tests die sicherstellen, dass nach Code-Änderungen die App noch funktioniert. Bestehende Tests (`src/tests/run_smoke_tests.py`) prüfen nur Imports und Dataclass-Erstellung.

## Technische Analyse

Bestehend:
- `src/tests/run_smoke_tests.py` (~320 Zeilen): Import-Tests für Module, Dataclass-Tests
- `src/tests/test_smoke.py` (~420 Zeilen): pytest-basierte Version der gleichen Tests
- `testdata/sample.gdv`: Test-GDV-Datei
- `testdata/test_roundtrip.py`: Roundtrip-Test (laden → speichern → vergleichen)

## Zielzustand

### Erweiterte Smoke-Tests
1. **Parser-Roundtrip**: `parse_file("testdata/sample.gdv")` → Records prüfen → `save_file()` → Bit-genauer Vergleich
2. **Domain-Mapping**: ParsedFile → GDVData → Contracts/Customers korrekt
3. **API-Client-Instanziierung**: APIClient erstellen, Config prüfen
4. **Retry-Logik**: Backoff-Berechnung korrekt
5. **DataCache Lock-Safety**: Parallele pause/resume Aufrufe → Counter konsistent
6. **Import-Chain**: Alle Module importierbar (bestehend, erweitern)

### Minimal-CI-Script
- `scripts/run_checks.py`: Lint → Tests → Ergebnis-Summary
- Kein externer CI-Server nötig, lokal ausführbar

## Randbedingungen

- Keine GUI-Tests (PySide6 braucht Display)
- Keine Netzwerk-Tests (kein Server nötig)
- Tests müssen in <30 Sekunden laufen
- Keine neue Test-Dependency (nur stdlib + pytest)

## Nicht-Ziele

- Keine 100% Coverage
- Keine Integration-Tests
- Kein CI/CD-Pipeline-Setup (nur lokales Script)
