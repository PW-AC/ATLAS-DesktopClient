# Entwickler-Dokumentation - BiPRO-GDV Tool v0.8.0+

**Stand:** 04. Februar 2026

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

```
5510_GDV Tool V1/
├── run.py                    # Entry Point (fügt src/ zum Path hinzu)
├── requirements.txt          # Python-Abhängigkeiten
├── AGENTS.md                 # Agent-Anweisungen
├── README.md
│
├── src/                      # Hauptcode
│   ├── __init__.py
│   ├── main.py              # Qt-App, Stylesheet, main()
│   │
│   ├── domain/              # Fachliche Modelle
│   │   ├── __init__.py
│   │   ├── models.py        # Dataclasses: Contract, Customer, etc.
│   │   └── mapper.py        # ParsedRecord → Domain-Objekt
│   │
│   ├── layouts/             # GDV-Satzart-Definitionen
│   │   ├── __init__.py
│   │   └── gdv_layouts.py   # LAYOUT_0001, LAYOUT_0100, etc.
│   │
│   ├── parser/              # GDV-Parser
│   │   ├── __init__.py
│   │   └── gdv_parser.py    # parse_file(), save_file(), etc.
│   │
│   ├── services/            # Business-Logik (NEU v0.8.0)
│   │   ├── __init__.py
│   │   └── document_processor.py  # Parallele Dokumentenverarbeitung
│   │
│   ├── config/              # Konfiguration (NEU v0.8.0)
│   │   ├── __init__.py
│   │   └── processing_rules.py    # Verarbeitungsregeln
│   │
│   └── ui/                  # Benutzeroberfläche
│       ├── __init__.py
│       ├── main_hub.py      # Navigation
│       ├── bipro_view.py    # BiPRO-Abruf
│       ├── archive_boxes_view.py  # Dokumentenarchiv (NEU v0.8.0)
│       ├── main_window.py   # GDV-Editor
│       ├── user_detail_view.py
│       └── partner_view.py
│
├── testdata/                # Testdaten
│   ├── sample.gdv          # Generierte Testdatei
│   ├── create_testdata.py  # Testdaten erstellen
│   └── test_roundtrip.py   # Roundtrip-Test
│
├── Echte daten Beispiel/    # Echte GDV-Dateien (nicht committen!)
│
└── docs/                    # Dokumentation
    ├── ARCHITECTURE.md
    ├── DEVELOPMENT.md       # Diese Datei
    └── DOMAIN.md
```

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

### Logging aktivieren

In `src/main.py` wird Logging konfiguriert:

```python
logging.basicConfig(
    level=logging.INFO,  # Auf DEBUG setzen für mehr Output
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
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

Qt-Stylesheets werden in `src/main.py` definiert:
```python
app.setStyleSheet("""
    QMainWindow { background-color: #ffffff; }
    ...
""")
```

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

---

## Build & Packaging

### PyInstaller (geplant)

```bash
pip install pyinstaller
pyinstaller --onefile --windowed run.py
```

**Hinweis**: Aktuell nicht konfiguriert/getestet.

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

### Linter einrichten (TODO)

```bash
pip install ruff
ruff check src/
```

### Unit-Tests einrichten (TODO)

```bash
pip install pytest
pytest tests/
```

---

## Kontakt

Bei Fragen zur Entwicklung: AGENTS.md konsultieren oder Codebase durchsuchen.
