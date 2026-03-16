# DEVELOPMENT.md - ACENCIA ATLAS Desktop Client

> **Stand**: 05.03.2026 | **Version**: 2.3.1

---

## Voraussetzungen

| Tool | Version | Hinweis |
|------|---------|---------|
| **Python** | 3.10+ | Empfohlen: 3.10.x (wie CI) |
| **pip** | aktuell | Fuer Dependency-Installation |
| **Git** | aktuell | Inkl. Submodule-Support |
| **Windows** | 10/11 | Primaere Zielplattform (pywin32, COM) |
| **PyInstaller** | 6.x | Fuer EXE-Build |
| **Inno Setup** | 6.x | Fuer Windows-Installer (optional) |

---

## Lokales Setup

### 1. Repository klonen

```bash
git clone --recurse-submodules <repo-url>
cd ATLAS-DesktopClient
```

Falls Submodule fehlen:
```bash
git submodule update --init --recursive
```

### 2. Virtual Environment erstellen

```bash
python -m venv .venv
.venv\Scripts\activate      # Windows
```

### 3. Dependencies installieren

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### 4. App starten

```bash
python run.py
```

### 5. Login

- **Benutzer**: `admin` (oder vom Administrator erhalten)
- **Server-API**: `https://acencia.info/api/` (automatisch konfiguriert)

---

## Projektstruktur (Kurzuebersicht)

```
ATLAS-DesktopClient/
├── run.py                     # Entry Point
├── VERSION                    # Zentrale Versionsdatei (2.3.1)
├── requirements.txt           # Production Dependencies
├── requirements-dev.txt       # Dev Dependencies (pytest, ruff)
├── requirements-lock.txt      # Gelockte Versionen
├── build_config.spec          # PyInstaller Build-Konfiguration
├── installer.iss              # Inno Setup Installer
├── AGENTS.md                  # Agent-Anweisungen (Single Source of Truth)
├── README.md                  # Projektuebersicht
├── docs/                      # Dokumentation
│   ├── ARCHITECTURE.md        # Architektur
│   ├── DEVELOPMENT.md         # Diese Datei
│   ├── CONFIGURATION.md       # Konfiguration
│   └── DOMAIN.md              # Fachdomaene
└── src/                       # Quellcode (~280 Dateien, ~90.000 Zeilen)
    ├── main.py                # Qt-Anwendung
    ├── api/                   # API-Clients (~30 Module inkl. admin_modules.py)
    ├── bipro/                 # BiPRO SOAP Client
    ├── services/              # Business-Logik
    ├── domain/                # Datenmodelle
    ├── infrastructure/        # Adapter
    ├── presenters/            # MVP-Presenter
    ├── usecases/              # Use Cases
    ├── workforce/             # HR-Modul
    ├── ui/                    # Benutzeroberflaeche
    │   ├── admin/             # Admin-Bereich (17 Panels)
    │   ├── module_admin/      # Modul-Admin-Verwaltung (Shell + 3 Panels)
    │   ├── provision/         # Provision (10 Panels)
    │   └── workforce/         # Workforce (7 Panels)
    ├── config/                # Konfiguration
    ├── i18n/                  # Internationalisierung (3 Sprachen: de, en, ru)
    ├── parser/                # GDV-Parser
    ├── layouts/               # GDV-Layouts
    ├── utils/                 # Hilfsfunktionen
    └── tests/                 # Tests
```

---

## Tests

### Smoke-Tests (eigenes Framework)

```bash
python src/tests/run_smoke_tests.py
```

Gibt einen JSON-Report aus. Wird in der CI automatisch ausgefuehrt.

### pytest

```bash
pytest src/tests/
```

### Test-Dateien

| Datei | Inhalt |
|-------|--------|
| `src/tests/run_smoke_tests.py` | Eigener Smoke-Test-Runner (kein pytest noetig) |
| `src/tests/test_smoke.py` | pytest-Klassen: PDF, GDV, AtomicOps, State Machine, API |
| `src/tests/test_provision.py` | Provision Unit-Tests: VSNR, Vermittler, Abrechnung, Split |
| `src/tests/test_security.py` | Security: NoHardcodedSecrets, ZipBomb, TempFileCleanup |
| `src/tests/test_stability.py` | Stability: API-Client, Auth-Refresh, Retry, Parser, Cache |

### CI (GitHub Actions)

Datei: `.github/workflows/smoke-tests.yml`

- **Trigger**: PR/Push auf `main`, `beta`
- **Runner**: `windows-latest`
- **Python**: 3.10
- **Steps**: Smoke-Tests, Provision-Tests, VERSION-Check
- **Artifacts**: `smoke_test_report.json`, `provision_test_report.json` (30 Tage)

---

## Linting

```bash
ruff check src/
```

Konfiguration: Standard-Ruff-Regeln (keine eigene Konfigdatei).

---

## Build

### EXE-Build (PyInstaller)

```bash
python -m PyInstaller build_config.spec --clean --noconfirm
```

Ergebnis: `dist/ACENCIA-ATLAS/` (Ordner mit EXE und allen Dependencies)

### Installer-Build (Inno Setup)

```bash
# Voraussetzung: Inno Setup 6 installiert
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
```

Ergebnis: `Output/ACENCIA-ATLAS-Setup-<version>.exe`

### Automatischer Build + Release

Im Submodule `internal/06_build-tools/`:

```bash
# Nur Build
build.bat

# Vollstaendiger Release (Version-Increment, Build, Upload)
0_release.bat
```

---

## Hintergrund-Updater

```bash
python run.py --background-update
```

Startet den headless Background-Updater (`src/background_updater.py`), der:
- Auto-Login mit persistiertem Token versucht
- BiPRO-Lieferungen im Hintergrund abruft
- Als Scheduled Task bei Windows-Anmeldung gestartet wird (Installer konfiguriert)

---

## Debugging-Tipps

### Log-Dateien

- **Konsole**: Alle Log-Meldungen erscheinen im Terminal
- **Datei**: `logs/bipro_gdv.log` (RotatingFileHandler, 5 MB, 3 Backups)
- **Log-Level**: Standard `INFO`, aenderbar in `src/main.py`

### Haeufige Probleme

| Problem | Loesung |
|---------|---------|
| `ModuleNotFoundError` | `pip install -r requirements.txt` in aktiviertem venv |
| `QFont::setPointSize: Point size <= 0` | Harmlose Qt-Warnung, wird unterdrueckt |
| App startet nicht (2. Instanz) | Single-Instance-Mutex aktiv. Vorherige Instanz beenden |
| 401-Fehler bei API-Calls | Token abgelaufen. Neu einloggen oder Token-Datei loeschen |
| BiPRO-Timeout | VU-Server nicht erreichbar. Rate-Limiting pruefen |
| KI-Klassifikation schlaegt fehl | API-Key pruefen (Admin → KI-Provider), Credits pruefen |

### Qt-Inspector

Fuer UI-Debugging kann der Qt-Inspector aktiviert werden:
```bash
set QT_DEBUG_PLUGINS=1
python run.py
```

### API-Debugging

Alle API-Requests werden ueber `src/api/client.py` geloggt. Fuer detailliertes Logging:
```python
import logging
logging.getLogger('api').setLevel(logging.DEBUG)
```

---

## Coding-Standards

### Python

- **Style**: PEP 8
- **Type Hints**: Pflicht fuer Funktionssignaturen
- **Docstrings**: Google-Style
- **Variablen/Funktionen**: Englisch
- **Kommentare**: Deutsch erlaubt

### Verbotene Patterns

- `QMessageBox.information/warning/critical` → `ToastManager` verwenden
- `print()` → `logging` verwenden
- Inline-Styles → Design-Tokens aus `ui/styles/tokens.py`
- Hardcoded Strings in UI → `i18n/de.py`
- Blockierender Code auf Main-Thread → QThread-Worker

### Namenskonventionen

| Element | Konvention | Beispiel |
|---------|-----------|---------|
| Klassen | PascalCase | `ParsedRecord`, `GDVData` |
| Funktionen | snake_case | `load_documents()` |
| Variablen | snake_case | `document_count` |
| Konstanten | UPPER_SNAKE | `MAX_RETRIES` |
| Dateien | snake_case | `archive_boxes_view.py` |
| i18n-Keys | UPPER_PREFIX_ | `ARCHIVE_UPLOAD_SUCCESS` |
| Datumsanzeige | DD.MM.YYYY | `05.03.2026` |

---

## Release-Prozess

1. **VERSION aktualisieren**: `VERSION`-Datei im Root (SemVer: `MAJOR.MINOR.PATCH`)
2. **version_info.txt aktualisieren**: Windows-EXE-Metadaten
3. **Changelog**: In README.md eintragen
4. **AGENTS.md**: Aktueller-Stand-Sektion aktualisieren
5. **Build**: `build.bat` oder manuell PyInstaller + Inno Setup
6. **Upload**: Release-Installer auf Server hochladen
7. **PR erstellen**: Feature-Branch → dev → beta → main

### Branch-Strategie

```
main (stable) ← beta ← dev ← feature-branch
```

- **Kein Direktcommit** auf `main` oder `dev`
- **Pipeline-Tool**: `internal/02_governance/atlas.ps1`
- **PR-Template**: `.github/pull_request_template.md`

---

## Nuetzliche Befehle

```bash
# App starten
python run.py

# Tests
python src/tests/run_smoke_tests.py
pytest src/tests/

# Linting
ruff check src/

# Build
python -m PyInstaller build_config.spec --clean --noconfirm

# Dependencies aktualisieren
pip install -r requirements.txt --upgrade

# Git Submodule aktualisieren
git submodule update --init --recursive
```
