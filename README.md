# ACENCIA ATLAS

**Der Datenkern.** Desktop-App fuer Versicherungsvermittler mit:
- **Mitteilungszentrale** - System-/Admin-Meldungen, Release-Info, 1:1 Chat mit Lesebestaetigung
- **BiPRO-Datenabruf** - Automatisierter Abruf von Lieferungen von Versicherern + IMAP Mail-Import
- **Dokumentenarchiv mit Box-System** - Zentrales Archiv mit KI-Klassifikation und Smart!Scan
- **Provisionsmanagement** - VU-Provisionen importieren, Berater verwalten, automatisch zuordnen, abrechnen
- **Workforce / HR** - Arbeitgeber- und Mitarbeiterverwaltung, HR-Provider-Anbindung, Delta-Exporte, Trigger
- **GDV-Editor** - Erstellung, Ansicht und Bearbeitung von GDV-Datensaetzen
- **Administration** - Nutzerverwaltung, E-Mail-Konten, KI-Kosten, Releases, Mitteilungen (17 Panels)

![Python 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)
![PySide6](https://img.shields.io/badge/GUI-PySide6-green.svg)
![Status](https://img.shields.io/badge/BiPRO-Funktioniert-brightgreen.svg)
![KI](https://img.shields.io/badge/KI-OpenRouter%20%7C%20OpenAI-purple.svg)
![License](https://img.shields.io/badge/License-Proprietary-red.svg)

---

## Features

### Mitteilungszentrale (NEU v2.0.0)
- **System- & Admin-Mitteilungen**: Automatische Meldungen (z.B. Scan-Fehler) und Admin-Announcements
- **Severity-Farben**: Info, Warnung, Fehler, Kritisch mit passenden Farben
- **Per-User Read-Status**: Badge zeigt ungelesene Mitteilungen
- **Release-Info**: Aktuelle Version + Release Notes, expandierbar zu allen Releases
- **1:1 Chat**: Private Nachrichten zwischen Nutzern mit Lesebestaetigung
- **Notification-Badge**: Roter Kreis im Menue bei ungelesenen Nachrichten
- **Toast-Benachrichtigung**: Bei neuer Chat-Nachricht "Neue Nachricht von ..."
- **Vollbild-Chat**: Eigene Ansicht mit Conversation-Liste und Nachrichtenverlauf

### BiPRO Datenabruf
- **Automatischer Abruf** von Lieferungen (Dokumente, Vertragsaenderungen)
- **VU-Verbindungen verwalten** (Degenia, VEMA)
- **Kategorien-Anzeige** (Vertragsdokumente, Geschaeftsvorfaelle, etc.)
- **Download einzeln oder alle** mit automatischem Archiv-Upload
- **Alle VUs abholen**: Alle aktiven VU-Verbindungen nacheinander abrufen
- **MTOM/XOP-Support** fuer Binaerdaten (PDFs)
- **Parallele Downloads** (max. 10 Worker, auto-adjustiert)
- **Adaptive Rate Limiting** (dynamische Anpassung bei 429/503)
- **PDF-Validierung** mit automatischer Reparatur
- **Mail-Import**: IMAP-Mails abholen und Anhaenge in Eingangsbox importieren (mit Progress-Toast)

### Dokumentenarchiv mit Box-System
- **ATLAS Index**: Globale Volltextsuche ueber alle Dokumente (Dateiname + OCR-Text), Live-Suche, Snippet-Vorschau (NEU v2.1.0)
- **8 Boxen**: GDV, Courtage, Sach, Leben, Kranken, Sonstige, Roh, Falsch
- **KI-Klassifikation**: Zweistufig mit Confidence-Scoring (GPT-4o-mini + GPT-4o Fallback)
- **Parallele Verarbeitung**: 4 Dokumente gleichzeitig (ThreadPoolExecutor)
- **KI-Benennung**: Automatische Umbenennung nach Schema `Versicherer_Typ_Datum.pdf`
- **Multi-Upload**: Mehrere Dateien gleichzeitig hochladen (inkl. Drag & Drop)
- **PDF-Vorschau** direkt in der App (QPdfView) + Tabellen-Vorschau (CSV/XLSX)
- **PDF-Bearbeitung**: Seiten drehen und loeschen direkt in der Vorschau, Mehrfachauswahl (Strg+Klick), Speichern auf Server
- **Dokumenten-Regeln**: Automatische Aktionen bei Duplikaten und leeren Seiten (Admin-konfigurierbar)
- **Smart!Scan**: Dokumente per E-Mail versenden (Toolbar-Button + Kontextmenue)
- **Box-Download**: Ganze Boxen als ZIP oder in Ordner herunterladen
- **Farbmarkierung**: 8 Farben fuer visuelle Organisation
- **Duplikat-Erkennung**: SHA256-Pruefziffer erkennt doppelte Dokumente (inkl. archivierte) + Content-Duplikate (gleicher Text)
- **Dokument-Historie**: Seitenpanel zeigt farbcodierte Aenderungshistorie pro Dokument
- **Tastenkuerzel**: F2, Entf, Strg+A/D/F/U, Enter, Esc, F5
- **Automatische Verarbeitung**: ZIP-Entpacken, PDF-Entsperren, MSG-Anhaenge extrahieren
- **KI-Kosten**: Provider-aware Anzeige (OpenRouter Balance / OpenAI akkumulierte Kosten)
- **Schliess-Schutz**: App kann nicht geschlossen werden waehrend KI-Verarbeitung oder SmartScan laeuft

### Provisionsmanagement (GF-Bereich, NEU v3.0.0)
- **Eigenstaendiger Hub**: Vollbild-Ansicht mit 7 Panels (wie Admin-Bereich)
- **VU-Provisionslisten importieren**: Allianz, SwissLife, VB (Excel, paralleler Import)
- **Xempus-Beratungen importieren**: Vertraege mit VSNR, VU, Sparte, Beitrag
- **Mitarbeiter-Verwaltung**: CRUD mit Rollen (Consulter, Teamleiter, Backoffice), Provisionssaetze
- **Automatisches Matching**: VSNR-basiert, Batch-JOIN fuer 15.000+ Zeilen in ~11s
- **Vermittler-Zuordnung**: VU-Vermittlernamen auf interne Berater mappen
- **Split-Berechnung**: Berater-Anteil, Teamleiter-Abzug, AG-Anteil (mit TL-Override)
- **Dashboard**: KPI-Karten, Berater-Ranking, Monats- und YTD-Werte
- **Monatsabrechnungen**: Generieren, Revisionierung, Status-Workflow (berechnet → ausgezahlt)
- **Berechtigung**: `provision_manage` (aktuell Admin-only)

### GDV-Editor
- **GDV-Dateien oeffnen**: `.gdv`, `.txt`, `.dat`, `.vwb`
- **Drei Ansichtsmodi**:
  - **Partner-Ansicht**: Alle Arbeitgeber und Personen mit ihren Vertraegen
  - **Benutzer-Ansicht**: Nur wichtige Felder, benutzerfreundlich
  - **Experten-Ansicht**: Alle Felder, volle Kontrolle
- **Daten bearbeiten und speichern**
- **Neue Saetze erstellen**: 0001, 0100, 0200, 0210, 0220, 0230, 9999

### Workforce / HR (NEU v2.3.0)
- **Eigener Hub**: Vollbild-Ansicht mit 7 Panels (wie Provision)
- **Arbeitgeber-Verwaltung**: CRUD, Credentials, Provider-Anbindung (HRworks, Personio, SageHR)
- **Mitarbeiter**: Paginierte Ansicht, Suche, Status-Filter
- **HR-Provider-Integration**: Direktanbindung an HRworks und Personio APIs
- **Delta-SCS-Export**: Automatischer Snapshot-Vergleich, XLSX-Generierung, Upload
- **Trigger-System**: Automatisierte Aktionen bei Mitarbeiterdaten-Aenderungen (E-Mail + API)
- **Snapshots**: HR-Daten-Snapshots speichern und vergleichen
- **Statistiken**: HR-Uebersichten und Kennzahlen
- **SMTP-Konfiguration**: E-Mail-Einstellungen fuer Trigger-Benachrichtigungen
- **Berechtigungen**: `hr.view`, `hr.sync`, `hr.export`, `hr.triggers`, `hr.admin`

### Administration (Vollbild-Ansicht mit vertikaler Sidebar, 17 Panels)
- **Nutzerverwaltung**: Erstellen, Bearbeiten, Sperren, 9 granulare Berechtigungen, Modul-Freischaltung
- **Session-Management**: Aktive Sessions einsehen und beenden
- **Passwort-Verwaltung**: PDF/ZIP-Passwoerter zentral verwalten
- **Aktivitaetslog**: Alle API-Aktionen protokolliert
- **KI-Kosten**: Verarbeitungshistorie, Kosten-Statistiken, Einzelne Requests, Zeitraum-Filter
- **KI-Provider**: OpenRouter/OpenAI Keys verwalten, aktivieren, testen (NEU v2.1.2)
- **Modell-Preise**: Input/Output-Preis pro Modell fuer exakte Kostenberechnung (NEU v2.1.2)
- **Dokumenten-Regeln**: Automatische Aktionen bei Duplikaten/leeren Seiten konfigurieren (NEU v2.1.3)
- **Releases**: Auto-Update Verwaltung (Upload, Status, Channel, SHA256)
- **E-Mail-Konten**: SMTP/IMAP mit verschluesselten Credentials
- **Smart!Scan-Einstellungen**: Zieladresse, Templates, Modi, Post-Send-Aktionen
- **Smart!Scan-Historie**: Revisionssichere Versandhistorie
- **E-Mail-Posteingang**: IMAP Inbox mit Anhang-Details
- **Mitteilungen**: System-/Admin-Mitteilungen erstellen und verwalten (NEU v2.0.0)

### Modul-Admin (NEU v2.3.1)
- **Modulare Zugriffssteuerung**: Core, Provision, Workforce als eigenstaendige Module
- **Account-Typen**: user, admin, super_admin (3-stufig)
- **Modul-Freischaltung**: Pro User einzeln freischaltbar, Dashboard zeigt nur freigeschaltete Module
- **Modul-Rollen**: Pro Modul konfigurierbare Rollen mit granularen Berechtigungen
- **Modul-Admin-Shell**: Eigenstaendige Verwaltungsoberflaeche mit 3 Tabs (Zugriff, Rollen, Konfiguration)
- **Live-Entzug**: Modul-Zugriff kann zur Laufzeit entzogen werden (Heartbeat-gesteuert)

---

## Quickstart

### Voraussetzungen

- Python 3.10 oder höher
- Windows 10/11 (getestet)
- Internetzugang (für Server-API und BiPRO)

### Installation

```bash
# Repository klonen oder Ordner oeffnen
cd "X:\projekte\5530_ATLAS MIT GIT\ATLAS-DesktopClient"

# Abhaengigkeiten installieren
pip install -r requirements.txt
```

### Starten

```bash
python run.py
```

### Login

- **Benutzer**: `admin`
- **Passwort**: (vom Administrator)

---

## Verwendung

### BiPRO Datenabruf

1. **Navigation** → **BiPRO Datenabruf**
2. VU-Verbindung in der Liste auswaehlen (Lieferungen laden automatisch)
3. Lieferungen werden mit Kategorie und Datum angezeigt
4. **"Alle herunterladen"** oder einzeln auswaehlen und **"Ausgewaehlte herunterladen"**
5. **"Alle VUs abholen"**: Alle aktiven VU-Verbindungen nacheinander abrufen
6. **"Mails abholen"**: IMAP-Mails abrufen, Anhaenge in Eingangsbox importieren
7. Dokumente werden automatisch ins Archiv hochgeladen

### Dokumentenarchiv

1. **Navigation** → **Dokumentenarchiv**
2. **ATLAS Index** (oben in Sidebar): Globale Volltextsuche mit Live-Suche, Snippet-Vorschau und Filtern
3. Boxen in der Sidebar auswaehlen (GDV, Courtage, Sach, Leben, etc.)
4. **PDF-Vorschau**: Doppelklick auf PDF oder Vorschau-Button
5. **Download**: Rechtsklick → "Herunterladen" oder Toolbar-Button
6. **Upload**: Hochladen-Button oder Drag & Drop aus dem Explorer
7. **Smart!Scan**: Gruener Button in der Toolbar oder Rechtsklick → Smart!Scan
8. **Box-Download**: Rechtsklick auf Box in Sidebar → Herunterladen (ZIP/Ordner)
9. **Tastenkuerzel**: F2 (Umbenennen), Entf (Loeschen), Strg+D (Download), F5 (Aktualisieren)

### GDV-Editor

1. **Navigation** → **GDV Editor**
2. **Menue** → **Datei** → **GDV-Datei oeffnen** (Strg+O)
3. Saetze werden in der Tabelle angezeigt
4. Felder im rechten Panel bearbeiten
5. **Menue** → **Datei** → **Speichern** (Strg+S)

### Mitteilungszentrale

1. **Navigation** → **Zentrale** (erster Eintrag in der Sidebar)
2. System- und Admin-Mitteilungen in der grossen Kachel
3. Aktuelle Version und Release Notes in der kleinen Kachel
4. **"Chats oeffnen"** fuer private 1:1 Nachrichten (Vollbild-Ansicht)

### Provisionsmanagement

1. **Navigation** → **Provisionen** (nur fuer Admins mit `provision_manage` Berechtigung)
2. **Import**: VU-Provisionslisten (Excel) oder Xempus-Beratungen importieren
3. **Mitarbeiter**: Berater, Teamleiter und Backoffice anlegen mit Provisionssaetzen
4. **Vermittler-Zuordnung**: VU-Vermittlernamen auf interne Berater mappen
5. **Auto-Match**: Button "Automatisch zuordnen" ordnet Provisionen den Beratern zu
6. **Dashboard**: KPI-Karten und Berater-Ranking pruefen
7. **Abrechnungen**: Monatsabrechnungen generieren und freigeben

### Workforce / HR

1. **Navigation** → **Workforce** (nur mit `hr.view` Berechtigung)
2. **Arbeitgeber**: Provider-Anbindung konfigurieren (HRworks, Personio), Credentials verwalten
3. **Mitarbeiter**: Paginierte Liste, Suche, Status-Filter, Detail-Ansicht
4. **Sync**: Mitarbeiterdaten von HR-Provider synchronisieren
5. **Exporte**: Delta-SCS-Exporte generieren und herunterladen (XLSX)
6. **Snapshots**: HR-Daten-Snapshots erstellen und vergleichen
7. **Trigger**: Automatisierte Aktionen bei Aenderungen (E-Mail, API-Calls)
8. **SMTP**: E-Mail-Konfiguration fuer Trigger-Benachrichtigungen

### Administration

1. **Navigation** → **Administration** (nur fuer Admins sichtbar)
2. Vertikale Sidebar links mit 17 Panels in 5 Sektionen
3. **Verwaltung**: Nutzer, Sessions, Passwoerter
4. **Monitoring**: Aktivitaetslog, KI-Kosten, Releases
5. **Verarbeitung**: KI-Klassifikation, KI-Provider, Modell-Preise, Dokumenten-Regeln
6. **E-Mail**: Konten, SmartScan-Settings, Historie, Posteingang
7. **Kommunikation**: Mitteilungen erstellen und verwalten
8. **System**: Server-Gesundheit, Migrationen

---

## Projektstruktur

```
ATLAS-DesktopClient/
├── run.py                     # Entry Point
├── VERSION                    # Zentrale Versionsdatei (aktuell 2.3.1)
├── requirements.txt           # Python-Abhaengigkeiten
├── requirements-dev.txt       # Dev-Dependencies (pytest, ruff)
├── requirements-lock.txt      # Gelockte Dependencies
├── AGENTS.md                  # Agent-Anweisungen (aktuell halten!)
├── README.md                  # Diese Datei
├── build_config.spec          # PyInstaller Build-Konfiguration
├── installer.iss              # Inno Setup Installer-Konfiguration
│
├── src/                       # Quellcode (~280 Dateien, ~90.000 Zeilen)
│   ├── main.py               # Qt-Anwendung
│   ├── background_updater.py # Headless Hintergrund-Updater
│   │
│   ├── api/                  # Server-API Clients (~29 Dateien)
│   │   ├── client.py         # Base-Client mit JWT-Auth + Retry
│   │   ├── documents.py      # Dokumenten-Operationen (Box-Support)
│   │   ├── provision.py      # Provisions-API
│   │   ├── auth.py           # Login/Logout, User-Model, Permissions, Module
│   │   ├── admin_modules.py  # Modul- und Rollenverwaltung API (NEU)
│   │   ├── xempus.py         # Xempus Insight Engine API
│   │   ├── bipro_events.py   # BiPRO-Events API
│   │   ├── smartscan.py      # SmartScan + EmailAccounts API
│   │   ├── openrouter/       # KI-Integration (Klassifikation, OCR)
│   │   └── ...               # (20 weitere Module)
│   │
│   ├── bipro/                # BiPRO SOAP Client (7 Dateien)
│   │   ├── transfer_service.py  # BiPRO 410 STS + 430 Transfer
│   │   ├── workers.py        # 6 QThread-Worker
│   │   ├── bipro_connector.py   # SmartAdmin vs. Standard-Flow
│   │   └── ...
│   │
│   ├── services/             # Business-Logik (14 Dateien)
│   │   ├── document_processor.py  # KI-Klassifikation (~2.327 Z.)
│   │   ├── data_cache.py     # Cache + Auto-Refresh (~620 Z.)
│   │   ├── provision_import.py    # VU/Xempus-Parser
│   │   ├── xempus_parser.py  # Xempus 5-Sheet Parser
│   │   └── ...
│   │
│   ├── domain/               # Datenmodelle (GDV + Xempus)
│   ├── config/               # Konfiguration (VU-Endpoints, Zertifikate)
│   ├── i18n/                 # Internationalisierung (~2.600 Keys, 3 Sprachen: de, en, ru)
│   ├── layouts/              # GDV-Satzart-Definitionen
│   ├── parser/               # GDV Fixed-Width Parser
│   ├── tests/                # Tests (7 Dateien: Smoke, Security, Stability, Provision)
│   │
│   └── ui/                   # Benutzeroberflaeche (~60 Dateien)
│       ├── app_router.py     # Routing-Shell (QStackedWidget: Dashboard, Core, Ledger, Workforce)
│       ├── dashboard_screen.py # Startbildschirm mit Modul-Kacheln
│       ├── main_hub.py       # Navigation + Drag & Drop + NotificationPoller
│       ├── bipro_view.py     # BiPRO Datenabruf
│       ├── archive_boxes_view.py  # Dokumentenarchiv
│       ├── message_center_view.py # Mitteilungszentrale
│       ├── chat_view.py      # Vollbild-Chat 1:1
│       ├── admin/             # Admin-Bereich (17 Panels)
│       │   ├── admin_shell.py    # Shell mit Sidebar
│       │   └── panels/          # 17 Panel-Dateien
│       ├── module_admin/      # Modul-Admin-Verwaltung (NEU)
│       │   ├── module_admin_shell.py  # Shell mit 3 Tabs
│       │   ├── access_panel.py  # User-Zugriff + Rollen
│       │   ├── roles_panel.py   # Rollen-CRUD
│       │   └── config_panel.py  # Modul-Konfiguration
│       ├── provision/         # Provisionsmanagement (10 Panels)
│       │   ├── provision_hub.py  # Hub mit Sidebar
│       │   ├── dashboard_panel.py # KPI + Berater-Ranking
│       │   └── ...               # (12 weitere Dateien)
│       ├── workforce/         # Workforce/HR (7 Panels)
│       │   ├── workforce_hub.py  # Hub mit Sidebar
│       │   └── *_view.py        # 7 View-Panels
│       ├── archive/           # Archiv-Worker + Widgets
│       ├── viewers/           # PDF- und Spreadsheet-Viewer
│       ├── gdv_editor_view.py # GDV-Editor
│       ├── toast.py           # Toast-Benachrichtigungen + Progress
│       └── styles/tokens.py   # Design-Tokens (Farben, Fonts)
│
├── ATLAS_private - Doku - Backend/  # Git Submodule (privat)
│   ├── BiPro-Webspace Spiegelung Live/  # Server-API (LIVE synchronisiert!)
│   │   ├── api/               # PHP REST API (29 Dateien, ~14.600 Zeilen)
│   │   │   ├── index.php      # Router
│   │   │   ├── lib/           # Shared Libraries (DB, JWT, Crypto, Permissions)
│   │   │   └── lib/PHPMailer/ # SMTP-Versand
│   │   └── setup/             # DB-Migrationen (26 Skripte)
│   ├── docs/                  # Technische Dokumentation
│   │   ├── 00_CORE/           # Kern-Dokumentation
│   │   ├── 01_DEVELOPMENT/    # Entwickler-Dokumentation
│   │   ├── 02_SECURITY/       # Sicherheit
│   │   ├── 03_REFERENCE/      # Referenz-Material
│   │   └── 04_PRODUCT/        # Produkt-Planung
│   ├── governance/            # Pipeline-Skripte
│   └── testdata/              # Testdaten
```

---

## BiPRO-Integration

### Unterstützte Versicherer

| Versicherer | Status | Normen |
|-------------|--------|--------|
| Degenia | ✅ Funktioniert | 410 STS, 430 Transfer |
| VEMA | ✅ Funktioniert | 410 STS, 430 Transfer |
| Weitere | 🔜 Geplant | - |

### Technischer Ablauf

1. **STS-Authentifizierung** (BiPRO 410): Holt Security-Token
2. **listShipments** (BiPRO 430): Listet verfügbare Lieferungen
3. **getShipment** (BiPRO 430): Lädt Lieferung herunter (MTOM/XOP)
4. **Archivierung**: Automatischer Upload ins Dokumentenarchiv

Siehe `BIPRO_STATUS.md` für Details.

---

## GDV-Format

Das GDV-Format ist ein Branchenstandard für den Datenaustausch zwischen Versicherungsunternehmen und Vermittlern.

### Merkmale

- **Fixed-Width**: 256 Bytes pro Zeile
- **Satzart**: Erste 4 Zeichen identifizieren den Satztyp
- **Encoding**: CP1252 (Windows-1252) für deutsche Umlaute

### Unterstützte Satzarten

| Satzart | Name | Beschreibung |
|---------|------|--------------|
| 0001 | Vorsatz | Datei-Header |
| 0100 | Partnerdaten | Adressen, Nummern, Bankdaten |
| 0200 | Vertragsteil | Grunddaten des Vertrags |
| 0210 | Spartenspezifisch | Wagnisse, Risiken |
| 0220 | Deckungsteil | Versicherte Personen, Leistungen |
| 0230 | Fondsanlage | ISIN, Fondsanteile |
| 9999 | Nachsatz | Prüfsummen |

---

## Konfiguration

### Server-API

Die Desktop-App verbindet sich mit:
- **API**: `https://acencia.info/api/`
- **Authentifizierung**: JWT-Token

### Umgebungsvariablen

Keine erforderlich (Konfiguration in App).

---

## Entwicklung

Siehe [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) fuer Setup, Build und Workflow.

Weitere Dokumentation:
- [AGENTS.md](AGENTS.md) - Agent-Anweisungen und aktuelle Architektur (Single Source of Truth)
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) - Detaillierte Architektur mit Datenfluss-Diagrammen
- [docs/CONFIGURATION.md](docs/CONFIGURATION.md) - Alle Konfigurationsoptionen
- [docs/DOMAIN.md](docs/DOMAIN.md) - Fachdomaene: Begriffe, Entitaeten, Workflows

---

## Lizenz

Proprietär - Nur für internen Gebrauch bei ACENCIA GmbH.

---

## Changelog

### v2.3.1 (05. Maerz 2026)
- **NEU**: Modul-System: Modulare Zugriffssteuerung fuer Core, Provision und Workforce
- **NEU**: Account-Typen erweitert: user, admin, super_admin (3-stufig)
- **NEU**: Modul-Freischaltung pro User: Dashboard zeigt nur freigeschaltete Module
- **NEU**: Modul-Admin-Shell: Eigenstaendige Verwaltung mit 3 Tabs (Zugriff, Rollen, Konfiguration)
- **NEU**: Modul-Rollen: Pro Modul konfigurierbare Rollen mit granularen Berechtigungen
- **NEU**: AdminModulesAPI: 10 neue API-Methoden fuer Modul- und Rollenverwaltung
- **NEU**: PHP-Backend admin_modules.php: Module, Rollen, User-Module, User-Rollen Endpoints
- **NEU**: Live-Modul-Entzug: GlobalHeartbeat ueberwacht Modul-Aenderungen in Echtzeit
- **NEU**: DB-Migrationen 045-050: modules, user_modules, roles, role_permissions, user_roles, backfill
- **NEU**: i18n erweitert auf 3 Sprachen (Deutsch, Englisch, Russisch), ~2600 Keys
- **NEU**: ~30 neue i18n-Keys (MODULE_ADMIN_*, ACCOUNT_TYPE_*, ACCESS_LEVEL_*, ROLE_*)

### v3.0.0 (19. Februar 2026)
- **NEU**: Provisionsmanagement (GF-Bereich): Eigenstaendiger Hub mit 7 Panels
- **NEU**: VU-Provisionslisten Import: 3 Formate (Allianz, SwissLife, VB), paralleler Import
- **NEU**: Xempus-Beratungen Import: Vertraege mit VSNR, VU, Berater-Zuordnung
- **NEU**: Mitarbeiter-CRUD: Rollen (Consulter/Teamleiter/Backoffice), Provisionssaetze, TL-Override
- **NEU**: Auto-Matching: 5-Schritt Batch-JOIN, ~11s fuer 15.010 Zeilen
- **NEU**: Split-Engine: 3 Batch-UPDATEs (Rueckbelastung, Positive ohne TL, Positive mit TL)
- **NEU**: Dashboard: KPI-Karten + Berater-Ranking mit Monats- und YTD-Werten
- **NEU**: Vermittler-Zuordnung: VU-Name → interner Berater, ungeloeste Vermittler
- **NEU**: Monatsabrechnungen: Generieren, Revision, Status-Workflow (berechnet→ausgezahlt)
- **NEU**: PHP Backend provision.php (~1100 Zeilen, 15+ Routen unter /pm/)
- **NEU**: Python ProvisionAPI (9 Dataclasses, defensive .get()-Zugriffe)
- **NEU**: VU/Xempus-Parser (provision_import.py, Column-Mappings, Normalisierung)
- **NEU**: 7 pm_* DB-Tabellen + 2 Permissions (provision_manage, provision_view)
- **NEU**: ~214 neue i18n-Keys (PROVISION_*)

### v2.1.3 (18. Februar 2026)
- **NEU**: PDF-Vorschau Mehrfachauswahl: Strg+Klick, Shift+Klick, Strg+A fuer Seiten-Multi-Selection
- **NEU**: PDF Bulk-Operationen: Mehrere Seiten gleichzeitig drehen oder loeschen
- **NEU**: PDF Auto-Refresh: Leere-Seiten-Erkennung und Text-Extraktion nach Speichern automatisch aktualisiert
- **NEU**: Dokumenten-Regeln Admin-Panel: Konfigurierbare Aktionen bei Duplikaten und leeren Seiten
- **NEU**: 4 Regel-Kategorien: Datei-Duplikate, Inhaltsduplikate, teilweise leere PDFs, komplett leere Dateien
- **NEU**: Automatische Leere-Seiten-Entfernung (PyMuPDF) mit Server-Upload und Cache-Invalidierung
- **NEU**: Cache-Wipe: Preview-Cache wird bei ungültiger Session beim App-Start geleert
- **NEU**: DB-Tabelle document_rules_settings + PHP API document_rules.php
- **NEU**: ~40 neue i18n-Keys (DOC_RULES_*, PDF_EDIT_*)

### v2.1.2 (18. Februar 2026)
- **NEU**: KI-Provider-System: OpenRouter und OpenAI dynamisch umschaltbar im Admin
- **NEU**: Provider-Verwaltung: API-Keys mit AES-256-GCM Verschluesselung, CRUD, Verbindungstest
- **NEU**: OpenAI-Direktanbindung: ~96% Kostenersparnis gegenueber OpenRouter
- **NEU**: Modell-Preise: Input/Output-Preis pro 1M Tokens fuer exakte Kostenberechnung
- **NEU**: Exakte Kostenberechnung pro KI-Request (real_cost_usd aus Tokens + Pricing)
- **NEU**: ai_requests-Tabelle: Jeder KI-Call geloggt (User, Provider, Model, Tokens, Kosten)
- **NEU**: Akkumulierte Batch-Kosten: Sofortige Kostenanzeige im Verarbeitungs-Fazit
- **NEU**: Token-Schaetzung via tiktoken vor dem Request (CostCalculator)
- **NEU**: KI-Kosten-Tab erweitert: Einzelne Requests mit Zeitraum-Filter
- **NEU**: KI-Klassifikation: Modell-Liste passt sich automatisch aktivem Provider an
- **NEU**: Admin-Sidebar: 2 neue Panels (KI-Provider, Modell-Preise) in Sektion VERARBEITUNG
- **NEU**: DB-Migration 020: ai_provider_keys + model_pricing + ai_requests

### v2.1.0 (13. Februar 2026)
- **NEU**: ATLAS Index: Globale Volltextsuche ueber alle Dokumente (Dateiname + OCR-extrahierter Text)
- **NEU**: ATLAS Index erscheint als virtuelle Box ganz oben in der Archiv-Sidebar
- **NEU**: Live-Suche (Debounce 400ms) mit abschaltbarer Checkbox + Such-Button
- **NEU**: Snippet-basierte Ergebnisdarstellung (Google-Stil) mit Treffer-Hervorhebung
- **NEU**: Smart Text-Preview: LOCATE-basierte Extraktion um Treffer herum (statt immer Textanfang)
- **NEU**: XML/GDV-Rohdaten standardmaessig ausgeblendet (Checkbox zum Einbeziehen)
- **NEU**: Teilstring-Suche optional per Checkbox (LIKE statt FULLTEXT)
- **NEU**: "In Box anzeigen" Kontextmenue-Option navigiert zur Quell-Box und selektiert Dokument
- **NEU**: Doppelklick auf Suchergebnis oeffnet PDF-Vorschau

### v2.0.4 (13. Februar 2026)
- **FIX**: PDF-Unlock fuer MSG/ZIP-Anhaenge funktioniert jetzt (api_client korrekt durchgereicht)
- **FIX**: Passwortgeschuetzte PDFs ohne Passwort crashen die App nicht mehr (ValueError-Handling)
- **FIX**: msg_handler.py akzeptiert jetzt api_client Parameter fuer PDF-Unlock

### v2.0.3 (13. Februar 2026)
- **NEU**: Volltext + KI-Daten-Persistierung: Separates `document_ai_data` Tabelle (1:1 zu documents)
- **NEU**: Volltextsuche vorbereitet: `extracted_text` MEDIUMTEXT mit FULLTEXT-Index
- **NEU**: Komplette KI-Rohantworten: `ai_full_response` LONGTEXT fuer Debugging/Analyse
- **NEU**: Groessen-Analyse: `text_char_count` + `ai_response_char_count` Spalten
- **NEU**: Content-Duplikat-Erkennung: Dokumente mit identischem Inhalt erkennen (auch bei verschiedener Datei)
- **NEU**: ≡-Icon (indigo) fuer Content-Duplikate neben ⚠-Icon (amber) fuer Datei-Duplikate
- **NEU**: Proaktive Text-Extraktion: Text wird sofort nach Upload extrahiert (BEVOR KI-Pipeline)
- **NEU**: MissingAiDataWorker: Hintergrund-Worker fuer Scan-Dokumente bei App-Start
- **NEU**: DB-Migration 017 (`document_ai_data`) + 018 (`content_duplicate_of_id`)

### v2.0.2 (12. Februar 2026)
- **NEU**: Leere-Seiten-Erkennung (PDF): 4-Stufen-Algorithmus (Text, Vektor, Bild, Pixel-Analyse)
- **NEU**: Markierung leerer Seiten im Archiv (Icon-Spalte mit Tooltip)
- **NEU**: DB-Felder `empty_page_count` + `total_page_count` in documents-Tabelle
- **NEU**: QTableView-Migration: QTableWidget durch QTableView+QAbstractTableModel ersetzt (Performance)

### v2.0.0 (11. Februar 2026)
- **NEU**: Mitteilungszentrale: Dashboard mit System-/Admin-Meldungen, Release-Info, Chat-Button
- **NEU**: 1:1 Private Chat: Vollbild-View, Lesebestaetigung, Conversation-Liste
- **NEU**: Notification-Polling: QTimer 30s, Badge + Toast bei neuen Nachrichten
- **NEU**: Admin-Panel "Mitteilungen" (Panel 10): CRUD fuer System-/Admin-Meldungen
- **NEU**: 4 neue DB-Tabellen: messages, message_reads, private_conversations, private_messages
- **NEU**: 3 neue PHP-API-Dateien: messages.php, chat.php, notifications.php
- **NEU**: 2 neue Python-API-Clients: messages.py, chat.py
- **NEU**: ~60 neue i18n-Keys (MSG_CENTER_, CHAT_, ADMIN_MSG_)

### v1.1.4 (10. Februar 2026)
- **NEU**: App-Schliess-Schutz: Schliessen blockiert bei laufender KI-Verarbeitung, Kosten-Check oder SmartScan-Versand
- **NEU**: `get_blocking_operations()` in ArchiveBoxesView prueft blockierende Worker sicher (C++-Object-Schutz)

### v1.1.3 (10. Februar 2026)
- **NEU**: PDF-Bearbeitung in der Vorschau: Seiten drehen (CW/CCW), loeschen, speichern auf Server
- **NEU**: Thumbnail-Sidebar im PDF-Viewer mit Seitenvorschauen
- **NEU**: Server-Endpoint POST /documents/{id}/replace fuer Datei-Ersetzung
- **NEU**: Cache-Invalidierung nach PDF-Speichern (Vorschau + Historie + Dokumente)

### v1.1.2 (10. Februar 2026)
- **NEU**: Dokument-Historie: Seitenpanel im Archiv zeigt farbcodierte Aenderungshistorie
- **NEU**: 8 farbcodierte Aktionstypen (Upload, Download, Verschieben, Loeschen, etc.)
- **NEU**: Neue Berechtigung `documents_history` fuer granulare Kontrolle
- **NEU**: Verbessertes Move-Logging: Pro-Dokument-Eintraege mit source_box/target_box

### v1.1.1 (10. Februar 2026)
- **NEU**: Duplikat-Erkennung: SHA256-Pruefziffer vergleicht gegen alle Dokumente (inkl. archivierte)
- **NEU**: Duplikat-Spalte in Archiv-Tabelle mit Warn-Icon und Tooltip zum Original
- **NEU**: Toast-Benachrichtigung bei Upload von Duplikaten

### v1.1.0 (10. Februar 2026)
- **NEU**: Keyword-Conflict-Hints fuer verbesserte KI-Klassifikation
- **NEU**: PDF Magic-Byte-Validierung nach MTOM-Extraktion
- **NEU**: Post-Save Cross-Check fuer BiPRO GDV-Dateien

### v1.0.9 (10. Februar 2026)
- **NEU**: Admin-Redesign: Vertikale Sidebar statt horizontaler Tabs, Vollbild-Ansicht
- **NEU**: Mail-Import im BiPRO-Bereich: "Mails abholen" Button mit IMAP-Poll + Attachment-Pipeline
- **NEU**: ProgressToastWidget: Nicht-blockierender Fortschritts-Toast mit Balken
- **NEU**: Smart!Scan-Toolbar-Button im Archiv (sichtbar wenn aktiviert)
- **NEU**: Vereinfachte SmartScan-Bestaetigung (Einfaches Confirm statt Dialog)

### v1.0.8 (10. Februar 2026)
- **NEU**: Tastenkuerzel im Dokumentenarchiv (F2, Entf, Strg+A/D/F/U, Enter, Esc, F5)

### v1.0.7 (10. Februar 2026)
- **NEU**: Toast-System ersetzt alle modalen Popups (~137 QMessageBox → Toast)
- **NEU**: UX-Regeln dokumentiert (docs/ui/UX_RULES.md)

### v1.0.6 (09. Februar 2026)
- **NEU**: Smart!Scan E-Mail-Versand (Einzel + Sammelmail, Post-Send-Aktionen)
- **NEU**: E-Mail-Konten-Verwaltung (SMTP/IMAP, AES-256-GCM)
- **NEU**: IMAP E-Mail-Import (Hybridansatz, Filter, Absender-Whitelist)
- **NEU**: SmartScan-Versandhistorie (revisionssicher)

### v1.0.5 (09. Februar 2026)
- **NEU**: ZIP-Entpackung beim Upload (inkl. AES-256, rekursiv)
- **NEU**: Zentrale Passwort-Verwaltung (DB statt hartcodiert)

### v1.0.4 (09. Februar 2026)
- **NEU**: Globales Drag & Drop Upload (Dateien/Ordner + Outlook Direct-Drop)
- **NEU**: MSG E-Mail-Verarbeitung (Anhaenge extrahieren)
- **NEU**: PDF Passwortschutz-Entsperrung beim Upload

### v1.0.3 (09. Februar 2026)
- **NEU**: Dokumenten-Farbmarkierung (8 Farben, persistent)

### v1.0.2 (08. Februar 2026)
- **NEU**: Scan-Upload Endpunkt fuer Power Automate

### v1.0.1 (09. Februar 2026)
- **RELEASE**: Erste stabile Release-Version

### v0.9.x (04.-07. Februar 2026)
- Parallele BiPRO-Downloads, KI-Klassifikation, Admin-System, Cache-Optimierung, Auto-Update
- Siehe AGENTS.md fuer vollstaendige Historie
