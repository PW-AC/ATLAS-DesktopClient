# Entwickler-Dokumentation - ACENCIA ATLAS v3.0.0

**Stand:** 19. Februar 2026

## Lokales Setup

### Voraussetzungen

- Python 3.10 oder höher
- pip (Python Package Manager)
- Internetzugang (für Server-API und BiPRO-Tests)
- Optional: venv für virtuelle Umgebung

### Installation

```bash
# Repository klonen/öffnen
cd "X:\projekte\5510_GDV Tool V1"

# Optional: Virtuelle Umgebung erstellen
python -m venv .venv
.venv\Scripts\activate  # Windows

# Abhängigkeiten installieren
pip install -r requirements.txt
```

### IDE-Empfehlungen

- **Cursor** (empfohlen) mit Python-Extension
- **VS Code** mit Python-Extension
- **PyCharm** (Community oder Professional)

---

## Anwendung starten

```bash
# Standard
python run.py

# Mit Debug-Logging
python -c "import logging; logging.basicConfig(level=logging.DEBUG); exec(open('run.py').read())"
```

---

## Projekt-Struktur

Siehe `README.md` fuer die vollstaendige Projektstruktur.

### Wichtigste Verzeichnisse

| Verzeichnis | Beschreibung | Zeilen (gesamt) |
|-------------|--------------|-----------------|
| `src/ui/` | Benutzeroberflaeche (PySide6) | ~26.400 |
| `src/ui/provision/` | Provisionsmanagement (7 Panels + Hub) | ~2.400 |
| `src/api/` | Server-API Clients (inkl. KI-Provider, Provision) | ~7.000 |
| `src/bipro/` | BiPRO SOAP Client | ~2.400 |
| `src/services/` | Business-Logik (inkl. CostCalculator, provision_import) | ~4.200 |
| `src/domain/` | Fachliche Modelle | ~1.100 |
| `src/parser/` | GDV Fixed-Width Parser | ~750 |
| `src/config/` | Konfiguration + Regeln + Modelle | ~2.110 |
| `src/i18n/` | Internationalisierung | ~1.380+ |

---

## Entwicklungs-Workflow

### 1. Feature entwickeln

1. Änderungen in entsprechender Datei vornehmen
2. Manuell testen mit `python run.py`
3. Testdatei laden: `testdata/sample.gdv` oder echte Datei
4. Bei Architekturänderungen: AGENTS.md aktualisieren

### 2. Parser-Änderungen

Bei Änderungen am Parser oder Layouts:

```bash
# Parser-Modul direkt testen
python -m src.parser.gdv_parser

# Roundtrip-Test
cd testdata
python test_roundtrip.py
```

### 3. Layout-Änderungen (neue Felder/Satzarten)

1. `src/layouts/gdv_layouts.py` bearbeiten
2. Neue Felddefinition hinzufügen:
```python
{"name": "neues_feld", "label": "Neues Feld", "start": 100, "length": 10, "type": "AN"}
```
3. Bei neuer Satzart: `RECORD_LAYOUTS` erweitern
4. Optional: Domain-Modell und Mapper erweitern

---

## Tests

### Manuelle Tests (aktuell)

```bash
# Testdaten neu erstellen
cd testdata
python create_testdata.py

# Roundtrip-Test (laden → modifizieren → speichern → laden)
python test_roundtrip.py
```

### Mit echten Daten testen

Echte GDV-Dateien befinden sich in `Echte daten Beispiel/`:
- Gothaer, Nürnberger, R+V, Signal Iduna, Stuttgarter, etc.
- **Wichtig**: Diese Dateien enthalten personenbezogene Daten!

---

## Code-Konventionen

### Python-Style

- **PEP 8** einhalten
- **Type Hints** für Funktionsparameter und Rückgabewerte
- **Docstrings** (Google-Style) für öffentliche Funktionen

```python
def parse_record(raw_line: str, line_number: int = 0) -> ParsedRecord:
    """
    Parst eine komplette GDV-Zeile.
    
    Args:
        raw_line: Die Rohzeile (256 Zeichen)
        line_number: Zeilennummer für Fehlerberichte
    
    Returns:
        ParsedRecord mit allen Feldern
    """
```

### Namenskonventionen

| Element | Konvention | Beispiel |
|---------|------------|----------|
| Variablen | snake_case | `parsed_file` |
| Funktionen | snake_case | `parse_record()` |
| Klassen | PascalCase | `ParsedRecord` |
| Konstanten | UPPER_SNAKE | `LAYOUT_0100` |
| Private | _prefix | `_setup_ui()` |

### GDV-spezifisch

- Satzarten: 4-stellig mit führenden Nullen (`"0100"`, nicht `"100"`)
- Positionen: 1-basiert (wie in GDV-Dokumentation)
- Feldnamen: Deutsch, snake_case (`versicherungsschein_nr`)

---

## Debugging

### Logging

Logging ist konfiguriert in `src/main.py`:
- **Konsole**: `INFO` Level
- **File-Logging**: `logs/bipro_gdv.log` (RotatingFileHandler, 5 MB, 3 Backups)
- **Format**: `"%(asctime)s - %(name)s - %(levelname)s - %(message)s"`

```bash
# Log-Datei ansehen
type logs\bipro_gdv.log

# Oder in Echtzeit beobachten
Get-Content logs\bipro_gdv.log -Wait
```

### Parser debuggen

```python
# In Python-Konsole
from src.parser.gdv_parser import parse_file, parse_record

# Datei parsen
parsed = parse_file("testdata/sample.gdv")
print(f"Records: {len(parsed.records)}")
print(f"Satzarten: {parsed.get_record_count_by_satzart()}")

# Einzelnes Record untersuchen
record = parsed.records[0]
print(f"Satzart: {record.satzart}")
for name, field in record.fields.items():
    print(f"  {name}: {field.value} (raw: '{field.raw_value}')")
```

### UI debuggen

**Design-Tokens** in `src/ui/styles/tokens.py`:
- Farben (ACENCIA Corporate Design: Primary, Secondary, Accent)
- Dokumenten-Farbpalette
- Font-Konfiguration

**UI-Regeln** in `docs/ui/UX_RULES.md`:
- Keine modalen Popups (QMessageBox) - stattdessen Toast-Benachrichtigungen
- Toast-System: `ToastManager` in `src/ui/toast.py`
- Alle UI-Texte aus `src/i18n/de.py`

**QFont Warnings**: `QFont::setPointSize: Point size <= 0 (-1)` beim Start sind bekannt und harmlos (Font-Initialisierung).

---

## Häufige Aufgaben

### Neues Feld zu Satzart hinzufügen

1. **Layout definieren** (`gdv_layouts.py`):
```python
# In LAYOUT_0100_TD1["fields"] einfügen:
{"name": "neues_feld", "label": "Neues Feld", "start": 200, "length": 10, "type": "AN", "editable": True}
```

2. **Optional: Domain-Modell erweitern** (`models.py`):
```python
@dataclass
class Customer:
    ...
    neues_feld: str = ""
```

3. **Optional: Mapping erweitern** (`mapper.py`):
```python
def map_0100_to_customer(record: ParsedRecord) -> Customer:
    return Customer(
        ...
        neues_feld=safe_str(record.get_field_value("neues_feld")),
    )
```

4. **Optional: UI erweitern** (`user_detail_view.py`):
```python
# In IMPORTANT_FIELDS["0100"] einfügen:
IMPORTANT_FIELDS = {
    "0100": [..., "neues_feld"],
}
```

### Neue Satzart hinzufügen

1. **Layout definieren** (`gdv_layouts.py`):
```python
LAYOUT_0XXX: LayoutDefinition = {
    "satzart": "0XXX",
    "name": "Neue Satzart",
    "description": "Beschreibung",
    "length": 256,
    "fields": [
        {"name": "satzart", "label": "Satzart", "start": 1, "length": 4, "type": "N"},
        # ... weitere Felder
    ]
}

# Zu Registry hinzufügen:
RECORD_LAYOUTS["0XXX"] = LAYOUT_0XXX
```

2. **Farbe in Tabelle** (`main_window.py`):
```python
# In RecordTableWidget._populate_table():
colors = {
    "0001": "#e3f2fd",
    "0XXX": "#neuefarbe",  # Neu
    ...
}
```

### Provisionsmanagement testen (v3.0.0)

Der GF-Bereich (Provisionsmanagement) hat eigene Test-Workflows:

**Daten-Import testen:**
1. App starten, in den Provisions-Bereich wechseln
2. **Import-Panel**: VU-Provisionsliste (Excel) oder Xempus-Export hochladen
3. Pruefen: Import-Historie zeigt Batch mit Zeilen-Statistik

**Matching testen:**
1. Mindestens 1 Mitarbeiter + 1 Vermittler-Mapping anlegen
2. **Provisionen-Panel**: "Automatisch zuordnen" klicken
3. Pruefen: Match-Status wechselt von "unmatched" zu "auto_matched"
4. Pruefen: Splits (berater_anteil + tl_anteil + ag_anteil == betrag)

**Split-Engine pruefen:**
- Rueckbelastungen: `tl_anteil == 0` (Teamleiter traegt Verluste nicht mit)
- Positive ohne TL: `tl_anteil == 0`, `berater_anteil + ag_anteil == betrag`
- Positive mit TL: `berater_anteil + tl_anteil + ag_anteil == betrag`
- TL-Override-Basis: `berater_anteil` (Standard) oder `gesamt_courtage`

**API-Smoke-Test:**
```bash
python scripts/smoke_test.py
```

**Bekannte Besonderheiten:**
- `batchRecalculateSplits()` fuehrt 3 Batch-UPDATEs aus (optimiert von per-Row-Loop)
- Auto-Matching hat 5 Schritte (VSNR → Alt-VSNR → Vermittler → Splits → Status)
- Dashboard `per_berater` Felder sind explizit Float-gecastet (Fix in v3.0.0)
- `VuImportWorker` nutzt `ThreadPoolExecutor` (max 15 Worker) fuer parallelen Import

---

## Build & Packaging

### Build (PyInstaller + Inno Setup)

```bash
# Vollstaendiger Build: PyInstaller + Inno Setup
build.bat

# Nur PyInstaller (ohne Installer)
build_simple.bat

# Debug-Build (mit Konsole)
build_debug.bat
```

**`build.bat` macht folgendes**:
1. Liest Version aus `VERSION`-Datei
2. Generiert `version_info.txt` (Windows-Metadaten)
3. PyInstaller: Erstellt EXE mit allen Assets (Fonts, Icons)
4. Inno Setup: Erstellt Installer-EXE mit SHA256-Hash
5. Output in `Output/ACENCIA-ATLAS-Setup-{version}.exe`

### Release-Prozess

Siehe `RELEASE_HOWTO.md` fuer den vollstaendigen Release-Prozess.

**Kurzfassung**:
1. `VERSION`-Datei aktualisieren
2. `build.bat` ausfuehren
3. Installer in Admin → Releases hochladen
4. Status auf "active" oder "mandatory" setzen

---

## Troubleshooting

### "ModuleNotFoundError: No module named 'src'"

Der `src/`-Pfad wird nicht gefunden. Lösung:
```bash
# Immer vom Projekt-Root starten:
cd "X:\projekte\5510_GDV Tool V1"
python run.py
```

### Umlaute werden falsch angezeigt

GDV-Dateien verwenden CP1252 (Windows-1252). Der Parser versucht mehrere Encodings:
1. CP1252
2. Latin-1 (ISO-8859-1)
3. UTF-8

Prüfen: `parsed_file.encoding` nach dem Laden.

### Felder werden nicht richtig geparst

1. Prüfe Layout-Definition in `gdv_layouts.py`
2. Positionen sind **1-basiert** (wie in GDV-Dokumentation)
3. Teildatensatz-Nummer aus Position 256 prüfen

### Qt/PySide6-Fehler

```bash
# PySide6 neu installieren
pip uninstall pyside6
pip install pyside6>=6.6.0
```

---

## Empfohlene Erweiterungen

### Linter + Tests (eingerichtet seit v0.9.4)

```bash
# Dev-Dependencies installieren
pip install -r requirements-dev.txt

# Lint
ruff check src/ --select E,F --ignore E501,F401

# Stabilitaets-Tests (11 Tests)
python -m pytest src/tests/test_stability.py -v

# Alles zusammen (Lint + Tests)
python scripts/run_checks.py
```

---

## Kontakt

Bei Fragen zur Entwicklung: AGENTS.md konsultieren oder Codebase durchsuchen.
