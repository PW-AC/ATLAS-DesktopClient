# 07 - Build, Run, Test, Deployment

**Version:** 0.9.3  
**Analyse-Datum:** 2026-02-05

---

## Installation

### Voraussetzungen

| Komponente | Version | Beschreibung |
|------------|---------|--------------|
| Python | 3.10+ | Laufzeitumgebung |
| pip | aktuell | Paketmanager |
| Internet | - | Für Server-API und BiPRO |
| Windows | 10/11 | Getestete Plattform |

### Setup

```bash
# 1. Repository/Ordner öffnen
cd "X:\projekte\5510_GDV Tool V1"

# 2. Optional: Virtuelle Umgebung
python -m venv .venv
.venv\Scripts\activate  # Windows

# 3. Abhängigkeiten installieren
pip install -r requirements.txt
```

---

## Anwendung starten

### Standard

```bash
cd "X:\projekte\5510_GDV Tool V1"
python run.py
```

### Mit Debug-Logging

```bash
python -c "import logging; logging.basicConfig(level=logging.DEBUG); exec(open('run.py').read())"
```

### Login

| Feld | Wert |
|------|------|
| Benutzer | `admin` |
| Passwort | (vom Administrator) |

---

## Tests

### Manuelle Tests (aktuell)

Es gibt keine automatisierten Unit-Tests. Tests erfolgen manuell.

#### Parser testen

```bash
cd "X:\projekte\5510_GDV Tool V1"
python -m src.parser.gdv_parser
```

#### Testdaten erstellen

```bash
cd "X:\projekte\5510_GDV Tool V1\testdata"
python create_testdata.py
```

#### Roundtrip-Test

```bash
cd "X:\projekte\5510_GDV Tool V1\testdata"
python test_roundtrip.py
```

#### BiPRO testen

1. App starten: `python run.py`
2. Einloggen als `admin`
3. "BiPRO Datenabruf" in Navigation wählen
4. Degenia-Verbindung auswählen
5. Lieferungen werden automatisch geladen
6. "Alle herunterladen" oder einzeln auswählen

### Testdateien

| Datei | Beschreibung |
|-------|--------------|
| `testdata/sample.gdv` | Generierte GDV-Testdatei |
| `Echte daten Beispiel/` | Echte GDV-Dateien (nicht committen!) |

---

## Server-Synchronisierung

### WICHTIG: Live-Synchronisierung

**Der Ordner `BiPro-Webspace Spiegelung Live/` ist LIVE mit dem Strato Webspace synchronisiert!**

| Lokal | Remote |
|-------|--------|
| `BiPro-Webspace Spiegelung Live/` | Strato Webspace `/BiPro/` |
| Änderungen werden in Echtzeit übertragen | Domain: `https://acencia.info/` |

**VORSICHT:** Gelöschte Dateien werden auch auf dem Server gelöscht!

### Ausnahmen von der Synchronisierung

| Ordner | Synchronisiert | Grund |
|--------|----------------|-------|
| `api/` | ✅ Ja | PHP-Code |
| `dokumente/` | ❌ **NEIN** | Server-Dokumentenspeicher |
| `setup/` | ✅ Ja | Migrations-Skripte |

### Synchronisierungs-Tool

- **Tool:** WinSCP (oder ähnlich)
- **Richtung:** Lokal → Webspace (Echtzeit)

---

## Datenbank-Setup

### Initiales Setup

Setup-Skripte befinden sich in `BiPro-Webspace Spiegelung Live/setup/`:

```bash
# Nach Ausführung löschen!
php setup/001_initial_schema.php
php setup/002_create_admin.php
# etc.
```

### Migrations

Neue Migrations in `setup/` ablegen und ausführen:

```bash
php setup/005_add_box_columns.php
```

**WICHTIG:** Nach Ausführung die Skripte löschen!

---

## Packaging (geplant)

### PyInstaller

```bash
pip install pyinstaller
pyinstaller --onefile --windowed run.py
```

**Status:** Nicht konfiguriert/getestet.

---

## Debugging

### Typische Probleme

#### "ModuleNotFoundError: No module named 'src'"

**Ursache:** Falsches Arbeitsverzeichnis

**Lösung:**
```bash
cd "X:\projekte\5510_GDV Tool V1"
python run.py
```

#### Umlaute werden falsch angezeigt

**Ursache:** Falsches Encoding der GDV-Datei

**Prüfen:**
```python
from src.parser.gdv_parser import parse_file
parsed = parse_file("datei.gdv")
print(parsed.encoding)  # Sollte 'cp1252' sein
```

#### Felder werden nicht richtig geparst

**Ursache:** Layout-Definition stimmt nicht

**Prüfen:**
- Positionen in `gdv_layouts.py` sind 1-basiert!
- Teildatensatz-Nummer aus Position 256

#### BiPRO: "keine Lieferungen"

**Ursache:** Falsche Credentials oder keine Daten

**Prüfen:**
- VEMA-API-Credentials verwenden (nicht Portal-Passwort!)
- STS-Token-Flow wird verwendet

#### BiPRO: STS gibt kein Token zurück

**Ursache:** Falsches Passwort

**Lösung:** VEMA-Passwort verwenden, nicht Portal-Passwort (ACA555)

#### PDF-Vorschau zeigt nichts an

**Ursache:** PySide6 Version zu alt

**Lösung:**
```bash
pip install --upgrade PySide6
# Benötigt PySide6 >= 6.4
```

#### API-Fehler "Unauthorized"

**Ursache:** JWT-Token abgelaufen

**Lösung:** App neu starten oder Abmelden/Anmelden

---

## Logging

### Konfiguration

**Quelle:** `src/main.py`

```python
logging.basicConfig(
    level=logging.INFO,  # DEBUG für mehr Output
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
```

### Log-Level ändern

```python
# In src/main.py
level=logging.DEBUG  # Für Entwicklung
```

---

## Entwicklungs-Workflow

### 1. Feature entwickeln

1. Änderungen in entsprechender Datei vornehmen
2. Manuell testen mit `python run.py`
3. Testdatei laden: `testdata/sample.gdv`
4. Bei Architekturänderungen: **AGENTS.md aktualisieren!**

### 2. Parser-Änderungen

Bei Änderungen am Parser oder Layouts:

```bash
# Parser-Modul direkt testen
python -m src.parser.gdv_parser

# Roundtrip-Test
cd testdata
python test_roundtrip.py
```

### 3. Server-API ändern

1. PHP-Datei in `BiPro-Webspace Spiegelung Live/api/` bearbeiten
2. Wird automatisch synchronisiert
3. Im Browser testen: `https://acencia.info/api/...`

---

## Artefakte

### Erzeugte Dateien

| Artefakt | Pfad | Beschreibung |
|----------|------|--------------|
| GDV-Dateien | Benutzerdefiniert | Vom GDV-Editor gespeichert |
| Temporäre PDFs | `%TEMP%` | Für PDF-Vorschau |
| Log-Output | stdout | Konsolenausgabe |

### Keine erzeugten Artefakte

- Kein Build-Output (keine Kompilierung)
- Keine generierten Konfigurationsdateien
- Keine Caches
