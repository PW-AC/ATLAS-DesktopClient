# AGENTS.md
# ACENCIA ATLAS -- Desktop Client

> **Version**: siehe `VERSION`-Datei (aktuell 2.2.6)
> Detaillierte Dokumentation liegt im privaten Submodule `ATLAS_private - Doku - Backend/`.

---

## Projekt-Steckbrief

| Feld | Wert |
|------|------|
| **Name** | ACENCIA ATLAS |
| **Typ** | Python-Desktop-App (PySide6/Qt) |
| **Entry Point** | `python run.py` |
| **Version** | Siehe `VERSION`-Datei im Root |

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

### Namenskonventionen
- **Klassen**: PascalCase (`ParsedRecord`, `GDVData`)
- **Funktionen/Variablen**: snake_case
- **Datumsanzeige**: DD.MM.YYYY in UI

### Error-Handling
- Fehler via `ToastManager` (nicht-blockierend)
- Logging: `logging` Standard-Library
- File-Logging: `logs/bipro_gdv.log` (RotatingFileHandler, 5 MB, 3 Backups)

---

## Git-Regeln

- **Branch-Strategie**: `main` (stable) / `beta` (beta) / `dev` (experimental)
- **Kein Direktcommit** auf `main` oder `dev`
- **Pipeline**: Feature-Branch -> dev -> beta -> main
- Pipeline-Skripte: siehe `ATLAS_private - Doku - Backend/governance/`

---

## Projektstruktur (oeffentlich)

```
src/                           Python Desktop-App (~130 Dateien, ~63.000 Zeilen)
  ui/                          UI-Layer (PySide6)
    admin/                     Admin-Bereich (16 Panels)
      panels/                  Einzelne Admin-Panels
    archive/                   Dokumentenarchiv (Workers)
    provision/                 Provisionsmanagement (9 Panels)
    styles/                    Design-Tokens
  api/                         API-Client-Module (~22 Dateien)
    openrouter/                KI-Integration (Klassifikation, OCR)
  bipro/                       BiPRO SOAP Client (~7 Dateien)
  services/                    Business-Services (~14 Dateien)
  config/                      Konfiguration (VU-Endpoints, Zertifikate)
  domain/                      Datenmodelle (GDV, Xempus)
  parser/                      GDV-Parser
  i18n/                        Internationalisierung (~1917 Keys)
  tests/                       Smoke- und Stability-Tests (5 Dateien)
run.py                         Entry Point
VERSION                        Versionsdatei (aktuell 2.2.6)
requirements.txt               Dependencies
```

## Interne Dokumentation

Detaillierte Architektur, API-Docs, Security, Governance und Backend-Code
liegen im privaten Submodule:

```
ATLAS_private - Doku - Backend/     (Git Submodule, privat)
  docs/                             Kern- und Entwickler-Dokumentation (3-Stufen-Hierarchie)
    00_CORE/                        Kern-Dokumentation (6 Dateien + Bibel)
    01_DEVELOPMENT/                 Entwickler-Dokumentation
    02_SECURITY/                    Sicherheit & Berechtigungen
    03_REFERENCE/                   Referenz-Material
    04_PRODUCT/                     Produkt-Planung (Roadmap, Ideas)
    99_ARCHIVE/                     Historische Dokumente
  governance/                       Pipeline-Skripte
  build-tools/                      Build-Werkzeuge
  scripts/                          Hilfsskripte
  testdata/                         Testdaten (inkl. Provision)
  BiPro-Webspace Spiegelung Live/   PHP REST-API Backend (~29 Dateien, ~14.600 Zeilen)
    api/lib/                        Shared Libraries (DB, JWT, Crypto, Permissions)
    setup/                          DB-Migrationen (26 Skripte)
  AGENTS.md                         Vollstaendige Agent-Instruktionen (Single Source of Truth)
```
