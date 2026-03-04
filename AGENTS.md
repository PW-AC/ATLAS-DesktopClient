# AGENTS.md
# ACENCIA ATLAS -- Desktop Client

> **Version**: siehe `VERSION`-Datei (aktuell 2.2.8) | **Stand**: 03.03.2026
> Detaillierte Dokumentation liegt im privaten Submodule `ATLAS_private - Doku - Backend/`.

---

## Projekt-Steckbrief

| Feld | Wert |
|------|------|
| **Name** | ACENCIA ATLAS ("Der Datenkern.") |
| **Typ** | Python-Desktop-App (PySide6/Qt) + PHP-REST-API + MySQL |
| **Zweck** | BiPRO-Datenabruf, Dokumentenarchiv, GDV-Editor, Provisionsmanagement |
| **Nutzer** | Versicherungsvermittler-Team (2-5 Personen) |
| **Entry Point** | `python run.py` |
| **Version** | Siehe `VERSION`-Datei im Root |
| **Hosting** | Hetzner Cloud (CCX13, Nuernberg), `https://acencia.info/api/` |

---

## Architektur (Clean Architecture)

```
Desktop-App (PySide6)             Hetzner Cloud (CCX13, Nuernberg)
├── UI Layer                      ├── Nginx (HTTPS, HTTP/2, Rate-Limiting)
│   ├── main_hub.py               ├── PHP 8.3 FPM + REST API (~33 Endpoints)
│   ├── provision/ (10 Panels)    │   ├── auth.php (JWT)
│   ├── admin/ (17 Panels)        │   ├── documents.php (Archiv)
│   └── message_center_view.py    │   ├── provision.php (GF-Bereich)
├── Presenters (MVP)              │   └── ... (~33 Dateien)
├── Use Cases                     ├── MySQL 8.0 Self-Hosted (60 Tabellen)
├── Domain (Entities, Rules)      ├── Volume 100 GB (/mnt/atlas-volume)
├── Infrastructure (Adapters)     │   ├── dokumente/ (2.589 Dateien, 428 MB)
├── API Clients (~29 Module)      │   ├── releases/ (29 Installer, 5.3 GB)
├── BiPRO SOAP Client             │   └── backups/ (taeglich, 30 Tage)
└── Services (~16 Module)         └── Admin-Panel (/admin-panel/)
```

**Server-Details:** Siehe `ATLAS_private - Doku - Backend/hetzner-migration/INFRASTRUKTUR_DATEN.md`
**Server-Abbild:** Siehe `ATLAS_private - Doku - Backend/ATLAS - Hetzner Server - ABBILD - NICHT LIVE/`

---

## Coding Standards

### Sprache & Style
- **Python**: PEP 8, Type Hints, Google-Style Docstrings
- **Variablen/Funktionen**: Englisch
- **Kommentare/Docstrings**: Deutsch OK
- **UI-Texte**: MUESSEN aus `src/i18n/de.py` stammen -- keine Hardcoded Strings

### Verbotene Patterns
- **KEINE modalen Popups**: `QMessageBox.information/warning/critical` sind VERBOTEN. Stattdessen `ToastManager` aus `ui.toast` verwenden. Erlaubt: Nur `QMessageBox.question()` fuer sicherheitskritische Bestaetigungen.
- **Keine Secrets im Code**
- **Keine `print()`-Reste oder Debug-Ausgaben**
- **Kein blockierender Code auf Main-Thread**: Lange Operationen via QThread-Worker

### Namenskonventionen
- **Klassen**: PascalCase (`ParsedRecord`, `GDVData`)
- **Funktionen/Variablen**: snake_case
- **Datumsanzeige**: DD.MM.YYYY in UI
- **Satzarten**: 4-stellig mit fuehrenden Nullen ("0100", "0200")

### Error-Handling
- Fehler via `ToastManager` (nicht-blockierend)
- Logging: `logging` Standard-Library
- File-Logging: `logs/bipro_gdv.log` (RotatingFileHandler, 5 MB, 3 Backups)

---

## Git-Regeln

- **Branch-Strategie**: `main` (stable) / `beta` (beta) / `dev` (experimental)
- **Kein Direktcommit** auf `main` oder `dev` -- nur ueber PRs
- **Pipeline**: Feature-Branch -> dev -> beta -> main (unveraenderlich)
- **Pipeline-Toolchain**: `ATLAS_private - Doku - Backend/governance/atlas.ps1`
- **CI**: Smoke-Tests + CodeQL auf main/beta, Secret Scanning aktiv
- **Governance-Details**: Siehe `.cursor/rules/git-pipeline.mdc`

---

## Projektstruktur (oeffentlich)

```
src/                                Python Desktop-App (~246 Dateien, ~82.000 Zeilen)
  ui/                               UI-Layer (PySide6)
    admin/                          Admin-Bereich
      panels/                       17 Admin-Panels
    archive/                        Dokumentenarchiv (Sidebar, Table, Widgets, Workers)
    provision/                      Provisionsmanagement (10 Panels + Hub)
    viewers/                        PDF- und Spreadsheet-Viewer
    styles/                         Design-Tokens
  api/                              API-Client-Module (~29 Dateien)
    openrouter/                     KI-Integration (Klassifikation, OCR, ~6 Dateien)
  bipro/                            BiPRO SOAP Client (~7 Dateien)
  services/                         Business-Services (~16 Dateien)
  config/                           Konfiguration (VU-Endpoints, Zertifikate, ~6 Dateien)
  domain/                           Datenmodelle
    archive/                        Archiv-Domain (Classifier, Rules, Entities, ~8 Dateien)
    provision/                      Provisions-Domain (Entities, Parser, Normalisierung, ~6 Dateien)
  infrastructure/                   Adapter & Repositories (Clean Architecture, ~20 Dateien)
    api/                            API-Repositories (Provision)
    archive/                        Archiv-Adapter (AI, SmartScan, PDF, Hash, ~10 Dateien)
    storage/                        Lokaler Speicher
    threading/                      Worker-Threads (Archive, Provision)
  presenters/                       Presenter-Layer (MVP, ~16 Dateien)
    archive/                        Archiv-Presenter
    provision/                      Provisions-Presenter (~8 Dateien)
  usecases/                         Use-Case-Layer (~25 Dateien)
    archive/                        Archiv-Use-Cases (~15 Dateien)
    provision/                      Provisions-Use-Cases (~10 Dateien)
  parser/                           GDV-Parser
  layouts/                          GDV-Satzlayouts
  utils/                            Hilfsfunktionen (date_utils)
  i18n/                             Internationalisierung (~2400 Keys, 2637 Zeilen)
  tests/                            Smoke-, Stability- und Security-Tests (7 Dateien)
run.py                              Entry Point (+ --background-update Weiche)
VERSION                             Versionsdatei (aktuell 2.2.8)
requirements.txt                    Dependencies (15 Pakete)
build_config.spec                   PyInstaller-Konfiguration
installer.iss                       Inno Setup Installer-Skript
```

## Interne Dokumentation

Detaillierte Architektur, API-Docs, Security, Governance und Backend-Code
liegen im privaten Submodule:

```
ATLAS_private - Doku - Backend/     (Git Submodule, privat)
  docs/                             Kern- und Entwickler-Dokumentation (3-Stufen-Hierarchie)
    00_CORE/                        Kern-Dokumentation (7 Dateien inkl. Bibel)
    01_DEVELOPMENT/                 Entwickler-Dokumentation (10 Dateien)
    02_SECURITY/                    Sicherheit & Berechtigungen (2 Dateien)
    03_REFERENCE/                   Referenz-Material (3 Dateien)
    04_PRODUCT/                     Produkt-Planung (Roadmap, Ideas)
    99_ARCHIVE/                     Historische Dokumente (4 Unterordner)
  governance/                       Pipeline-Skripte (atlas.ps1 + 14 Einzelskripte + 3 Flows)
  build-tools/                      Build-Werkzeuge (9 Dateien)
  scripts/                          Hilfsskripte (10 Python-Dateien)
  testdata/                         Testdaten (inkl. Provision)
  ChatGPT-Kontext/                  KI-Kontext-Dateien (11 Markdown-Dateien)
  BiPro-Webspace Spiegelung Live/   PHP REST-API Backend (~76 Dateien, ~22.800 eigene Zeilen)
    api/                            33 PHP-Endpoints
    api/lib/                        Shared Libraries (DB, JWT, Crypto, Permissions, PHPMailer)
    setup/                          DB-Migrationen (34 Skripte, 005-041)
  ATLAS - Hetzner Server - ABBILD - NICHT LIVE/
    README.md                       Sync-Anleitung und Ordnerstruktur
    Abbild/                         Lokale Kopie des Servers (etc/, var/www/, opt/)
  hetzner-migration/                Server-Migration Strato → Hetzner (abgeschlossen 03.03.2026)
    00_MIGRATIONSPLAN.md            Gesamtueberblick + Fortschritt
    INFRASTRUKTUR_DATEN.md          Live-Infrastruktur-Werte (IPs, Credentials, Pfade)
    server-mirror/                  (Legacy, ersetzt durch ABBILD)
    configs/                        Vorbereitete Config-Templates
    scripts/                        Setup- und Sync-Scripts
  AGENTS.md                         Vollstaendige Agent-Instruktionen (Single Source of Truth)
```
