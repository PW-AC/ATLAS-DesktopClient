# AGENTS.md
# Agent Instructions for ACENCIA ATLAS

> **Version**: 3.4.0 | **Stand**: 25.02.2026
> Diese Datei ist der Einstiegspunkt fuer jeden KI-Agenten. Lies zuerst nur diese Datei.
> Weitere Dokumentation findest du unter `docs/`. Lies sie nur, wenn die Aufgabe es erfordert.

---

## 1. Projekt-Steckbrief

| Feld | Wert |
|------|------|
| **Name** | ACENCIA ATLAS ("Der Datenkern.") |
| **Typ** | Python-Desktop-App (PySide6/Qt) + PHP-REST-API + MySQL |
| **Zweck** | BiPRO-Datenabruf, Dokumentenarchiv, GDV-Editor, Provisionsmanagement |
| **Nutzer** | Versicherungsvermittler-Team (2-5 Personen) |
| **Hosting** | Strato Webspace, `https://acencia.info/api/` |
| **Version** | Siehe `VERSION`-Datei im Root |
| **Entry Point** | `python run.py` |

---

## 2. Kontext-Hierarchie (3 Stufen)

**Regel**: Lies immer nur die Stufe, die du fuer die aktuelle Aufgabe brauchst.

### Stufe 1: Diese Datei (AGENTS.md)
- Projekt-Steckbrief, Regeln, Ordnerstruktur, Leitplanken
- **Immer gelesen** (Cursor Workspace Rule)

### Stufe 2: Fokussierte Dokumentation (`docs/00_CORE/*.md`)
- Lies nur die Datei(en), die zur Aufgabe passen

| Datei | Wann lesen |
|-------|------------|
| `SYSTEM_OVERVIEW.md` | Allgemeine Fragen zum Projekt, Tech-Stack, Zielgruppe |
| `FEATURES.md` | Features, UX, Nutzer-Perspektive, was die App fuer den Nutzer tut |
| `ARCHITEKTUR.md` | Systemarchitektur, Datenfluss, Dateistruktur, Zeilenangaben |
| `API_DB.md` | API-Endpoints, DB-Tabellen, Datenbank-Schema |
| `DOMAIN.md` | Fachliche Datenmodelle, Satzarten, GDV-Felder, PM-Entitaeten |
| `PROVISION_SYSTEM.md` | Provisionsmanagement-Spezifika (Import, Matching, Splits, UI) |

**Ergaenzende Entwickler-Dokumentation** (`docs/01_DEVELOPMENT/`):

| Datei | Wann lesen |
|-------|------------|
| `GIT_GOVERNANCE.md` | Branch-Strategie, PR-Regeln, Secret Policy, CODEOWNERS |
| `RELEASE_STRATEGY.md` | Release-Channels, Gate Engine, SemVer, Release-Flow |

### Stufe 3: Die Bibel (`docs/00_CORE/ATLAS_KOMPLETT.md`)
- **~2200 Zeilen**, enthaelt ALLE Details zu ALLEN Features
- **Nur lesen wenn**: Stufe 2 nicht ausreicht, tiefere Details noetig, Feature-spezifische Implementierung gesucht
- **Niemals primaer bearbeiten**: Aenderungen gehoeren in die jeweilige Stufe-2-Datei

---

## 3. Dokumentations-Struktur

```
docs/
  00_CORE/           ← Kern-Dokumentation (Single Source of Truth)
    SYSTEM_OVERVIEW.md
    FEATURES.md
    ARCHITEKTUR.md
    API_DB.md
    DOMAIN.md
    PROVISION_SYSTEM.md
    ATLAS_KOMPLETT.md  ← Bibel (Stufe 3, Read-Only fuer Agenten)
  01_DEVELOPMENT/    ← Entwickler-Dokumentation
    DEVELOPMENT_GUIDE.md
    UX_RULES.md
    BUILD_README.md
    RELEASE_HOWTO.md
    RELEASE_FEATURES_HISTORY.txt
    MIGRATIONS.md
    GIT_GOVERNANCE.md
    RELEASE_STRATEGY.md
  02_SECURITY/       ← Sicherheit & Berechtigungen
    SECURITY.md
    PERMISSIONS.md
  03_REFERENCE/      ← Referenz-Material
    BIPRO_ENDPOINTS.md
    DEPLOYMENT.md
    GDV_DATEN_DOKUMENTATION.txt
  04_PRODUCT/        ← Produkt-Planung
    IDEAS.md
    ROADMAP.md
  99_ARCHIVE/        ← Historische Dokumente (nicht bearbeiten)
    Audit_BiPRO_Pipeline/
    Audit_GF_Provision/
    Analyse_GF_Provision/
    Konzepte_Provision/
    Design_Mockups_GF/
```

---

## 4. Verbindliche Regeln

### 4.1 Dokumentations-Governance
- **Keine neuen Markdown-Dateien** erstellen, die nicht eindeutig einem `docs/` Ordner zugeordnet sind
- **Jede Information genau einmal** -- keine Duplikate zwischen Dateien
- **ATLAS_KOMPLETT.md ist Read-Only** fuer Agenten; Aenderungen gehoeren in die jeweilige Stufe-2-Datei
- **Bei Architektur-Aenderungen**: Betroffene Stufe-2-Datei aktualisieren

### 4.2 Live-Synchronisierung
**VORSICHT:** `BiPro-Webspace Spiegelung Live/` ist LIVE mit dem Strato Webspace synchronisiert!

| Ordner | Synchronisiert | Bemerkung |
|--------|----------------|-----------|
| `api/` | Ja | PHP-Code -- Aenderungen sind sofort produktiv |
| `dokumente/` | **NEIN** | Server-Dokumentenspeicher |
| `releases/` | **NEIN** | Installer-Storage |

- Geloeschte Dateien werden auch auf dem Server geloescht!
- `config.php` enthaelt DB-Credentials, Master-Key, JWT-Secret (per .htaccess geschuetzt)
- **Kein Move/Rename in/aus dem Live-Ordner** bei Dokumentations-Refactoring

### 4.3 Coding Style
- **Python**: PEP 8, Type Hints, Google-Style Docstrings
- **Variablen/Funktionen**: Englisch
- **Kommentare/Docstrings**: Deutsch OK
- **UI-Texte**: MUESSEN aus `src/i18n/de.py` stammen -- keine Hardcoded Strings
- **KEINE modalen Popups**: `QMessageBox.information/warning/critical` sind VERBOTEN fuer Info/Warnung/Fehler. Stattdessen `ToastManager` aus `ui.toast` verwenden. Erlaubt: Nur `QMessageBox.question()` fuer sicherheitskritische Bestaetigungen. Siehe `docs/01_DEVELOPMENT/UX_RULES.md`.
- **Hintergrund-Operationen**: QThread-Worker fuer lange Operationen
- **BiPRO**: Raw XML mit requests (kein zeep)

### 4.4 Namenskonventionen
- **Satzarten**: 4-stellig mit fuehrenden Nullen ("0100", "0200")
- **Felder**: snake_case, deutsch (`versicherungsschein_nr`, `geburtsdatum`)
- **Klassen**: PascalCase (`ParsedRecord`, `GDVData`)
- **Datumsanzeige**: DD.MM.YYYY in UI

### 4.5 Error-Handling & Logging
- Parser gibt immer `ParsedFile` zurueck (auch bei Fehlern)
- Fehler via `ToastManager` (nicht-blockierend)
- Logging: `logging` Standard-Library, `INFO` normal, `DEBUG` Entwicklung
- File-Logging: `logs/bipro_gdv.log` (RotatingFileHandler, 5 MB, 3 Backups)

### 4.6 Security
- Keine Secrets im Code (DSGVO-relevante Daten)
- BiPRO-Credentials verschluesselt auf Server (AES-256-GCM)
- JWT-Token fuer API-Auth (30 Tage Gueltigkeit)
- Single-Session-Enforcement pro Nutzer

### 4.7 Provisions-Berechtigungen (Sonderregel)
- `provision_access` und `provision_manage` werden NICHT automatisch an Admins vergeben
- Muessen explizit zugewiesen werden
- Nur Nutzer mit `provision_manage` koennen diese Rechte an andere vergeben

### 4.8 Git-Governance & Release-Regeln
- **Branch-Strategie**: `main` (stable) / `develop` (beta) / `dev` (experimental)
- **Kein Direktcommit** auf `main` -- nur ueber PR aus `develop`
- **VERSION-Datei** ist Single Source of Truth fuer Versionierung
- **Release Gate Engine**: Releases starten als `pending`, muessen alle Gates passieren bevor Aktivierung
- **Release-Channels**: `stable`, `beta`, `dev` -- pro User server-seitig konfigurierbar
- Details: `docs/01_DEVELOPMENT/GIT_GOVERNANCE.md` und `docs/01_DEVELOPMENT/RELEASE_STRATEGY.md`

---

## 5. Architektur-Ueberblick (Kurzform)

```
Desktop-App (PySide6)          Strato Webspace
├── UI Layer                   ├── PHP REST API
│   ├── main_hub.py            │   ├── auth.php
│   ├── bipro_view.py          │   ├── documents.php
│   ├── archive_boxes_view.py  │   ├── provision.php
│   ├── provision/ (8 Panels)  │   ├── ai.php (Proxy)
│   ├── admin/ (15 Panels)     │   └── ... (~27 Dateien)
│   └── message_center_view.py │
├── API Clients                ├── MySQL Datenbank
│   ├── client.py (Base)       ├── Dokumente-Storage
│   ├── documents.py           └── Releases-Storage
│   ├── provision.py           
│   └── ... (~15 Module)       
├── BiPRO SOAP Client          
│   ├── transfer_service.py    
│   └── workers.py             
├── Services                   
│   ├── document_processor.py  
│   ├── provision_import.py    
│   └── ... (~10 Module)       
└── Parser                     
    ├── gdv_parser.py          
    └── gdv_layouts.py         
```

### Haupt-Bereiche der App
1. **Mitteilungszentrale** -- System-Meldungen, Release-Info, 1:1 Chat
2. **BiPRO Datenabruf** -- Lieferungen von VUs abrufen, IMAP-Mail-Import
3. **Dokumentenarchiv** -- Box-System (7 Boxen), KI-Klassifikation, ATLAS Index (Volltextsuche)
4. **GDV-Editor** -- GDV-Dateien oeffnen/parsen/bearbeiten/speichern
5. **Provisionsmanagement** -- Dashboard, Import, Matching, Abrechnungen (GF-Bereich)
6. **Admin-Bereich** -- 15 Panels (Nutzer, Sessions, KI, E-Mail, SmartScan, etc.)

---

## 6. Tech-Stack (Kompakt)

| Komponente | Technologie |
|------------|-------------|
| Desktop | Python 3.10+ / PySide6 6.6+ |
| PDF | PyMuPDF (fitz) + QPdfView |
| HTTP | requests 2.31+ |
| BiPRO | Raw XML (kein zeep) |
| KI | OpenRouter ODER OpenAI (dynamisch umschaltbar) |
| Token-Zaehlung | tiktoken |
| Server | PHP 7.4+ / MySQL 8.0 |
| Hosting | Strato (`acencia.info`) |

---

## 7. Wichtige Dateipfade (Top 20)

| Pfad | Zweck |
|------|-------|
| `run.py` | Entry Point (+ `--background-update` Weiche fuer Hintergrund-Updater) |
| `VERSION` | Zentrale Versionsdatei |
| `src/main.py` | Qt-App Initialisierung + Update-Check |
| `src/background_updater.py` | Headless Hintergrund-Updater (kein Qt, Scheduled Task) |
| `src/ui/auto_update_window.py` | Zero-Interaction Pflicht-Update-Fenster |
| `src/ui/main_hub.py` | Navigation, DragDrop, Polling (~1529 Z.) |
| `src/ui/bipro_view.py` | BiPRO UI (~3530 Z.) |
| `src/ui/archive_boxes_view.py` | Dokumentenarchiv (~5645 Z.) |
| `src/ui/provision/provision_hub.py` | PM-Hub mit 7 Panels |
| `src/ui/provision/workers.py` | **24 QThread-Worker fuer PM (Refactoring v3.4.0)** |
| `src/ui/provision/models.py` | **12 QAbstractTableModel-Klassen + Helper fuer PM (Refactoring v3.4.0)** |
| `src/ui/provision/dialogs.py` | **MatchContractDialog + DiffDialog fuer PM (Refactoring v3.4.0)** |
| `src/ui/admin/admin_shell.py` | Admin mit 15 Panels |
| `src/services/document_processor.py` | KI-Dokumentenverarbeitung |
| `src/services/provision_import.py` | VU/Xempus-Parser |
| `src/bipro/transfer_service.py` | BiPRO SOAP Client (~1329 Z.) |
| `src/bipro/workers.py` | BiPRO Worker-Klassen (~1699 Z.) |
| `src/api/client.py` | API-Base-Client |
| `src/api/documents.py` | Dokumenten-API |
| `src/api/provision.py` | Provisions-API (~859 Z.) |
| `src/i18n/de.py` | Zentrale i18n-Datei (~2179 Z., ~1400+ Keys) |
| `BiPro-Webspace Spiegelung Live/api/index.php` | API-Router |
| `src/api/bipro_events.py` | BiPRO-Events API-Client (~135 Z.) |
| `BiPro-Webspace Spiegelung Live/api/provision.php` | PM-Backend (~2480 Z.) |
| `BiPro-Webspace Spiegelung Live/api/bipro_events.php` | BiPRO-Events Backend (~278 Z.) |
| `BiPro-Webspace Spiegelung Live/api/documents.php` | Dokumenten-Backend |
| `BiPro-Webspace Spiegelung Live/api/ai.php` | KI-Proxy (OpenRouter/OpenAI) |

---

## 8. Definition of Done (DoD)

- [ ] Code laeuft (`python run.py` startet ohne Fehler)
- [ ] Manuelle Tests mit Testdatei `testdata/sample.gdv`
- [ ] Lint/Format OK (empfohlen: `ruff`)
- [ ] Docstrings fuer neue oeffentliche Funktionen
- [ ] Betroffene Stufe-2-Dokumentation aktualisiert
- [ ] Keine Secrets im Code
- [ ] UI-Texte in `src/i18n/de.py`

---

## 9. Debugging Quick-Reference

```bash
# App starten
python run.py

# Parser testen
python -m src.parser.gdv_parser

# Smoke-Tests
python -m src.tests.run_smoke_tests
```

**Haeufige Probleme**: Siehe `docs/00_CORE/ATLAS_KOMPLETT.md` Abschnitt "Debugging & How-To".

---

## 10. Agent-Verantwortung

Bei jeder Aenderung am Projekt MUSS der Agent:
1. Die betroffene Stufe-2-Datei in `docs/00_CORE/` aktualisieren
2. Bei neuen Features: `docs/01_DEVELOPMENT/RELEASE_FEATURES_HISTORY.txt` ergaenzen
3. Bei DB-Migrationen: `docs/01_DEVELOPMENT/MIGRATIONS.md` ergaenzen
4. Bei Berechtigungs-Aenderungen: `docs/02_SECURITY/PERMISSIONS.md` ergaenzen
5. ATLAS_KOMPLETT.md NICHT direkt bearbeiten (wird separat synchronisiert)
