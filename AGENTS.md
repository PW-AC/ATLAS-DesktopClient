# AGENTS.md
# ACENCIA ATLAS -- Desktop Client + Web-Admin-Panel

> **Version**: siehe `VERSION`-Datei (aktuell 2.3.1) | **Stand**: 05.03.2026
> Detaillierte Dokumentation liegt im privaten Submodule `internal/` (ATLAS-Internal).
> Server-Abbild und Backend-Code liegen im eigenstaendigen Repo `ATLAS-Private`.

**Agent's Responsibility:** Dieses Dokument ist die Single Source of Truth fuer Agent-Zusammenarbeit an diesem Projekt. Bei jedem neuen Feature, Bugfix oder Refactor **muss** dieses Dokument aktualisiert werden.

---

## Projekt-Steckbrief

| Feld | Wert |
|------|------|
| **Name** | ACENCIA ATLAS ("Der Datenkern.") |
| **Typ** | Python-Desktop-App (PySide6/Qt) + PHP-REST-API + MySQL + Web-Admin-Panel (Vanilla JS) |
| **Zweck** | BiPRO-Datenabruf, Dokumentenarchiv, GDV-Editor, Provisionsmanagement, Workforce (HR), Server-Administration |
| **Nutzer** | Versicherungsvermittler-Team (2-5 Personen) |
| **Entry Point Desktop** | `python run.py` |
| **Entry Point Admin-Panel** | `https://acencia.info/admin-panel/` |
| **Version** | Siehe `VERSION`-Datei im Root |
| **Hosting** | Hetzner Cloud (CCX13, Nuernberg), `https://acencia.info/api/` |
| **SSH-Zugang** | `ssh root@46.225.16.146` (RSA-Key: Paul-ACENCIA) |

---

## KRITISCHE REGELN FUER ALLE AGENTS

### SSH-Verbindungsmanagement (PFLICHT)

> **WARNUNG: Der Server hat ein SSH-MaxSessions-Limit von 10. Haengende/offene SSH-Verbindungen blockieren den Server und verhindern weitere Zugriffe!**

**Bei JEDER SSH/SCP-Operation gelten diese Regeln OHNE AUSNAHME:**

1. **IMMER Timeouts setzen**: `-o ConnectTimeout=10 -o ServerAliveInterval=5 -o ServerAliveCountMax=2`
2. **IMMER Verbindung nach Aktion SCHLIESSEN**: Bevor eine neue SSH/SCP-Verbindung geoeffnet wird, MUSS die vorherige beendet sein
3. **NIEMALS parallele SSH-Verbindungen oeffnen**: Immer sequentiell, eine Verbindung nach der anderen
4. **NIEMALS eine Verbindung offen lassen und vergessen**: Nach jeder abgeschlossenen Aktion sofort `exit` oder Verbindung beenden
5. **Multi-Datei-Transfers**: IMMER als einzelnen Tarball buendeln, NICHT einzeln per SCP
6. **Bei Timeout/Fehler**: NICHT sofort wiederholen, erst 5 Sekunden warten

**Korrektes Pattern fuer Deployments:**
```bash
# 1. Tar erstellen (lokal)
tar -czf /tmp/deploy.tar.gz datei1 datei2

# 2. Upload (eine SCP-Verbindung, schliesst automatisch)
scp -o ConnectTimeout=10 -o ServerAliveInterval=5 -o ServerAliveCountMax=2 /tmp/deploy.tar.gz root@46.225.16.146:/tmp/deploy.tar.gz

# 3. Entpacken + Aufraeumen (eine SSH-Verbindung, schliesst automatisch)
ssh -o ConnectTimeout=10 -o ServerAliveInterval=5 -o ServerAliveCountMax=2 root@46.225.16.146 "cd /var/www/atlas && tar -xzf /tmp/deploy.tar.gz && rm /tmp/deploy.tar.gz"

# 4. Lokale Temp-Datei loeschen
rm /tmp/deploy.tar.gz
```

**Interaktive SSH-Sessions sind erlaubt**, aber es gilt:
- Immer nur EINE Verbindung gleichzeitig
- Nach Abschluss der Arbeit SOFORT `exit` ausfuehren
- NIEMALS eine zweite Verbindung oeffnen waehrend die erste noch laeuft

**VERBOTENES Pattern:**
```bash
# FALSCH: Mehrere einzelne SCP-Aufrufe (oeffnet N Verbindungen)
scp datei1 root@server:/pfad/   # Verbindung 1
scp datei2 root@server:/pfad/   # Verbindung 2
scp datei3 root@server:/pfad/   # Verbindung 3 -- BLOCKIERT!

# FALSCH: Verbindung offen lassen und neue oeffnen
ssh root@server                 # Verbindung 1 (laeuft noch)
# ... in anderem Terminal ...
ssh root@server                 # Verbindung 2 -- GEFAHR!
```

### Webspace-Ordner = Live-System

Das Server-Abbild liegt im eigenstaendigen Repository `ATLAS-Private` (nicht mehr im Submodule).
Aenderungen am Server muessen per SSH deployed werden.

### UI-Texte

- **Desktop-App**: MUESSEN aus `src/i18n/de.py` stammen
- **Web-Admin-Panel**: MUESSEN aus `admin-panel/i18n/de.js` stammen
- **Keine Hardcoded Strings** in Komponenten

---

## Architektur (Clean Architecture)

```
Desktop-App (PySide6)             Web-Admin-Panel                  Hetzner Cloud (CCX13, Nuernberg)
├── UI Layer                      ├── index.html (SPA)             ├── Nginx (HTTPS, HTTP/2, Rate-Limiting)
│   ├── main_hub.py               ├── css/ (5 Dateien)             ├── PHP 8.3 FPM + REST API (~48 Dateien)
│   ├── provision/ (10 Panels)    │   └── tokens.css (ACENCIA CI)  │   ├── auth.php (JWT, is_super_admin)
│   ├── workforce/ (7 Panels)                                      │   ├── hr.php (Workforce, 30 Endpoints)
│   ├── admin/ (17 Panels)        ├── js/ (41 Dateien)             │   ├── documents.php (Archiv)
│   ├── module_admin/ (Shell+3)   │   ├── api.js (API Client)      │   ├── admin_modules.php (Module+Rollen)
│   └── message_center_view.py    │   ├── auth.js (JWT + Timeout)   │   ├── server_management.php (13 Endpoints)
├── Presenters (MVP)              │   ├── router.js (Hash-SPA)     │   ├── ai_providers.php (Provider CRUD)
├── Use Cases                     │   ├── components/ (6 Module)   │   ├── model_pricing.php (Preise CRUD)
├── Domain (Entities, Rules)      │   └── panels/ (27 Panels)      │   ├── processing_settings.php (KI-Config)
├── Infrastructure (Adapters)     └── i18n/de.js (~430 Keys)       │   └── ... (~48 Dateien)
├── API Clients (~30 Module)                                       ├── MySQL 8.0 Self-Hosted (~68 Tabellen)
├── BiPRO SOAP Client                                              ├── Volume 100 GB (/mnt/atlas-volume)
└── Services (~16 Module)                                          │   ├── dokumente/ (~2.600 Dateien, ~450 MB)
                                                                   │   ├── releases/ (~30 Installer, ~5.4 GB)
                                                                   │   └── backups/ (taeglich, 30 Tage)
                                                                   └── Admin-Panel (/admin-panel/, ~50 Dateien)
```

**Server-Details:** Siehe `internal/01_docs/hetzner-migration/INFRASTRUKTUR_DATEN.md`
**Server-Abbild:** Siehe eigenstaendiges Repo `ATLAS-Private` (Ordner `00_VPS_ABBILD_NICHT LIVE/`)
**Admin-Panel-Plan:** Siehe `internal/01_docs/04_PRODUCT/`

---

## Coding Standards

### Sprache & Style
- **Python**: PEP 8, Type Hints, Google-Style Docstrings
- **JavaScript (Admin-Panel)**: ES Modules, Vanilla JS (kein Framework), `import`/`export`
- **PHP**: PSR-12 angelehnt, `json_success()`/`json_error()` fuer Responses
- **Variablen/Funktionen**: Englisch
- **Kommentare/Docstrings**: Deutsch OK

### Verbotene Patterns
- **KEINE modalen Popups**: `QMessageBox.information/warning/critical` sind VERBOTEN (Desktop). Stattdessen `ToastManager` aus `ui.toast` verwenden. Erlaubt: Nur `QMessageBox.question()` fuer sicherheitskritische Bestaetigungen.
- **Keine Secrets im Code**
- **Keine `print()`-Reste oder Debug-Ausgaben**
- **Kein blockierender Code auf Main-Thread**: Lange Operationen via QThread-Worker (Desktop)
- **Keine Inline-Styles im Admin-Panel** (CSS-Klassen aus `tokens.css` / `components.css` nutzen)
- **KEINE parallelen SSH-Verbindungen** (siehe SSH-Regeln oben)

### Namenskonventionen
- **Klassen**: PascalCase (`ParsedRecord`, `GDVData`)
- **Funktionen/Variablen**: snake_case (Python/PHP), camelCase (JavaScript)
- **Datumsanzeige**: DD.MM.YYYY in UI
- **Satzarten**: 4-stellig mit fuehrenden Nullen ("0100", "0200")

### Error-Handling
- **Desktop**: Fehler via `ToastManager` (nicht-blockierend)
- **Admin-Panel**: `showToast()` aus `toast.js`, Custom Error Classes (`NetworkError`, `AuthError`, `ForbiddenError`, `APIError`)
- **PHP**: `json_error($message, $statusCode)` mit optionalen `$details`
- Logging: `logging` Standard-Library (Python), `error_log()` (PHP)
- File-Logging: `logs/bipro_gdv.log` (RotatingFileHandler, 5 MB, 3 Backups)

---

## API-Response-Format (PHP -> JS)

Alle PHP-Endpoints nutzen zwei Funktionen:
```php
json_success($data, $message)  // → { success: true, message: "OK", data: $data }
json_error($msg, $status)      // → { success: false, error: $msg }
```

**Hybrid-Unwrapping in `api.js`:**
- Wenn `data.data` ein Objekt ist (kein Array): wird entpackt, Rueckgabe = `data.data`
- Wenn `data.data` ein Array ist: wird NICHT entpackt, Rueckgabe = gesamtes Response-Objekt

Konsequenz fuer Frontend-Panels:
```javascript
// Array-Responses (z.B. json_success($usersArray)):
const resp = await api.get('/admin/users');
tableComp.render(resp.data || resp.users || []);  // resp.data = Array

// Objekt-Responses (z.B. json_success(['entries' => [...], 'pagination' => {...}])):
const resp = await api.get('/admin/server/audit-log');
const data = resp.data || resp;  // resp wird entpackt zu {entries, pagination}
tableComp.render(data.entries || []);
```

---

## Git-Regeln

- **Branch-Strategie**: `main` (stable) / `beta` (beta) / `dev` (experimental)
- **Kein Direktcommit** auf `main` oder `dev` -- nur ueber PRs
- **Pipeline**: Feature-Branch -> dev -> beta -> main (unveraenderlich)
- **Pipeline-Toolchain**: `internal/02_governance/atlas.ps1`
- **CI**: Smoke-Tests + CodeQL auf main/beta, Secret Scanning aktiv
- **Governance-Details**: Siehe `internal/02_governance/README.md` und `.cursor/rules/git-pipeline.mdc`

---

## Web-Admin-Panel (Neu seit v2.3.0)

### Ueberblick
- **URL**: `https://acencia.info/admin-panel/`
- **Technologie**: Vanilla JavaScript (ES Modules), CSS Custom Properties, Hash-basiertes SPA-Routing
- **Authentifizierung**: JWT (`sessionStorage`), 30-Minuten Browser-Inaktivitaets-Timeout
- **Zugriffskontrolle**: Admin (`account_type = 'admin'`) fuer App-Panels, Super-Admin (`is_super_admin = 1`) fuer Server-Panels
- **Design**: ACENCIA CI (tokens.css), Desktop-fokussiert aber mobil bedienbar

### Panel-Uebersicht (27 Panels)

**Verwaltung (4):**
| Panel | Datei | API-Endpoint |
|-------|-------|-------------|
| Nutzerverwaltung | `panels/users.js` | `/admin/users`, `/admin/permissions` |
| Sessions | `panels/sessions.js` | `/admin/sessions` |
| Passwoerter | `panels/passwords.js` | `/passwords` |
| Releases | `panels/releases.js` | `/releases` |

**Monitoring (2):**
| Panel | Datei | API-Endpoint |
|-------|-------|-------------|
| Aktivitaetslog | `panels/activity-log.js` | `/admin/activity` |
| KI-Kosten | `panels/ai-costs.js` | `/processing_history/costs`, `/processing_history/cost_stats`, `/ai/requests` |

**Verarbeitung (4):**
| Panel | Datei | API-Endpoint |
|-------|-------|-------------|
| KI-Klassifikation | `panels/ai-classification.js` | `/admin/processing-settings/ai`, `/admin/processing-settings/prompt-versions` |
| KI-Provider | `panels/ai-providers.js` | `/admin/ai-providers` |
| Modell-Preise | `panels/model-pricing.js` | `/admin/model-pricing` |
| Dokumenten-Regeln | `panels/document-rules.js` | `/admin/document-rules` |

**E-Mail (4):**
| Panel | Datei | API-Endpoint |
|-------|-------|-------------|
| E-Mail-Konten | `panels/email-accounts.js` | `/admin/email-accounts` |
| SmartScan Einstellungen | `panels/smartscan-settings.js` | `/admin/smartscan/settings` |
| SmartScan Historie | `panels/smartscan-history.js` | `/admin/smartscan/history` |
| E-Mail Posteingang | `panels/email-inbox.js` | `/email-inbox` |

**Kommunikation (1):**
| Panel | Datei | API-Endpoint |
|-------|-------|-------------|
| Mitteilungen | `panels/messages.js` | `/messages` |

**System (3):**
| Panel | Datei | API-Endpoint |
|-------|-------|-------------|
| Server-Gesundheit | `panels/server-health.js` | `/admin/diagnostics`, `/admin/diagnostics/history` |
| Migrationen | `panels/migrations.js` | `/admin/migrations` |
| System-Status | `panels/system-status.js` | `/system-status` |

**Server (Super-Admin, 9):**
| Panel | Datei | API-Endpoint |
|-------|-------|-------------|
| Fail2Ban | `panels/server-fail2ban.js` | `/admin/server/fail2ban` |
| Firewall | `panels/server-firewall.js` | `/admin/server/firewall` |
| Services | `panels/server-services.js` | `/admin/server/services` |
| System-Info | `panels/server-system.js` | `/admin/server/system-info` |
| Log-Viewer | `panels/server-logs.js` | `/admin/server/logs` |
| SSL/Zertifikate | `panels/server-ssl.js` | `/admin/server/ssl` |
| Backups | `panels/server-backups.js` | `/admin/server/backups` |
| Volume | `panels/server-volume.js` | `/admin/server/volume` |
| Audit-Log | `panels/server-audit-log.js` | `/admin/server/audit-log` |

### Shared Components
| Datei | Zweck |
|-------|-------|
| `components/data-table.js` | Generische Datentabelle mit Aktions-Dropdowns, Pagination |
| `components/form-builder.js` | Dynamischer Formular-Builder (Input, Select, Textarea, Toggle, Multi-Checkbox) |
| `components/modal.js` | Modale Dialoge |
| `components/confirm-dialog.js` | Bestaetigungsdialoge |
| `components/sidebar.js` | Navigations-Sidebar mit Kategorien |
| `components/stats-card.js` | Statistik-Karten-Grid |

### Stolperfallen & Debugging
- **`[object Object]` in Tabellen**: Pruefen ob API-Response korrekt entpackt wird (Hybrid-Unwrapping, siehe oben)
- **"rows is not iterable"**: `data-table.js` erwartet Arrays. Wenn ein Objekt uebergeben wird, sucht es automatisch nach dem ersten Array-Property
- **Feld-Namen**: PHP-API-Feldnamen muessen EXAKT mit JS-Frontend-Zugriffen uebereinstimmen (z.B. `total_cost_usd` nicht `total_cost`, `entries` nicht `costs`)
- **Super-Admin-Check**: Server-Panels brauchen `is_super_admin = 1` in der `users`-Tabelle. Erster Super-Admin: User `admin`
- **Browser-Cache**: Nach Deployments `Ctrl+Shift+R` fuer Hard-Refresh noetig

---

## Projektstruktur (oeffentlich)

```
src/                                Python Desktop-App (~280 Dateien, ~90.000 Zeilen)
  ui/                               UI-Layer (PySide6)
    admin/                          Admin-Bereich
      panels/                       17 Admin-Panels
    module_admin/                   Modul-Admin-Verwaltung (Shell + 3 Panels)
      module_admin_shell.py         Generische Shell mit Tabs (Zugriff, Rollen, Konfiguration)
      access_panel.py               User-Zugriff + Rollen-Zuweisung pro Modul
      roles_panel.py                Rollen-CRUD + Rechtezuweisung pro Modul
      config_panel.py               Modul-spezifische Konfigurationspanels
    archive/                        Dokumentenarchiv (Sidebar, Table, Widgets, Workers)
    provision/                      Provisionsmanagement (10 Panels + Hub)
    workforce/                      Workforce/HR (7 Panels + Hub)
    viewers/                        PDF- und Spreadsheet-Viewer
    styles/                         Design-Tokens
  api/                              API-Client-Module (~30 Dateien)
    admin_modules.py                Modul- und Rollenverwaltung API (10 Methoden)
    openrouter/                     KI-Integration (Klassifikation, OCR, ~6 Dateien)
  bipro/                            BiPRO SOAP Client (~7 Dateien)
  services/                         Business-Services (~16 Dateien)
  config/                           Konfiguration (VU-Endpoints, Zertifikate, ~7 Dateien)
  domain/                           Datenmodelle
    archive/                        Archiv-Domain (Classifier, Rules, Entities, ~8 Dateien)
    provision/                      Provisions-Domain (Entities, Parser, Normalisierung, ~6 Dateien)
  infrastructure/                   Adapter & Repositories (Clean Architecture, ~23 Dateien)
    api/                            API-Repositories (Provision)
    archive/                        Archiv-Adapter (AI, SmartScan, PDF, Hash, ~10 Dateien)
    storage/                        Lokaler Speicher
    threading/                      Worker-Threads (Archive, Provision, Freeze-Detector)
  presenters/                       Presenter-Layer (MVP, ~12 Dateien)
    archive/                        Archiv-Presenter
    provision/                      Provisions-Presenter (~8 Dateien)
  usecases/                         Use-Case-Layer (~26 Dateien)
    archive/                        Archiv-Use-Cases (~15 Dateien)
    provision/                      Provisions-Use-Cases (~10 Dateien)
  parser/                           GDV-Parser
  layouts/                          GDV-Satzlayouts
  utils/                            Hilfsfunktionen (date_utils)
  workforce/                        Workforce/HR-Modul (~15 Dateien, ~2400 Zeilen)
    api_client.py                   WorkforceApiClient (PHP-Backend-Kommunikation)
    workers.py                      QThread-Worker (Sync, Delta, Export, Stats)
    constants.py                    SCS_HEADERS, Trigger-Events, Operatoren
    helpers.py                      Utility-Funktionen (Hash, Flatten, Date-Parse)
    providers/                      HR-API-Anbindungen (Personio, HRworks, SageHR)
    services/                       Geschaeftslogik (Sync, Delta, Export, Snapshot, Trigger, Stats)
  i18n/                             Internationalisierung (~2600 Keys, 3 Sprachen: de, en, ru)
  tests/                            Smoke-, Stability- und Security-Tests (7 Dateien)
run.py                              Entry Point (+ --background-update Weiche)
VERSION                             Versionsdatei (aktuell 2.3.1)
requirements.txt                    Dependencies (16 Pakete)
build_config.spec                   PyInstaller-Konfiguration
installer.iss                       Inno Setup Installer-Skript
```

## Interne Dokumentation

Detaillierte Architektur, API-Docs, Security, Governance und Build-Tools
liegen im privaten Submodule `internal/` (ATLAS-Internal):

```
internal/                           (Git Submodule, privat, ATLAS-Internal.git)
  01_docs/                          Kern- und Entwickler-Dokumentation (3-Stufen-Hierarchie, 53 Dateien)
    00_CORE/                        Kern-Dokumentation (7 Dateien inkl. ATLAS_KOMPLETT.md)
    01_DEVELOPMENT/                 Entwickler-Dokumentation (10 Dateien)
    02_SECURITY/                    Sicherheit, Berechtigungen & Rollen (3 Dateien)
    03_REFERENCE/                   Referenz-Material (3 Dateien)
    04_PRODUCT/                     Produkt-Planung (Roadmap, Ideas)
    99_ARCHIVE/                     Historische Dokumente (4 Unterordner)
  02_governance/                    Pipeline-Skripte (atlas.ps1 + 14 Einzelskripte + 3 Flows)
  06_build-tools/                   Build-Werkzeuge (10 Dateien)
  07_scripts/                       Hilfsskripte (10 Python-Dateien)
  08_testdata/                      Testdaten (inkl. Provision)
  ChatGPT-Doku/                     KI-Kontext-Dateien (4 Module)
  HR-API-Projekt/                   Altes HR-API-Projekt (Referenz)
```

Server-Abbild und Backend-Code liegen im eigenstaendigen Repo `ATLAS-Private`:

```
ATLAS-Private/                      (eigenstaendiges Repo, privat, ATLAS-Private.git)
  00_VPS_ABBILD_NICHT LIVE/         Lokale Kopie des Servers (etc/, var/www/, opt/)
  05_Local_dev_Backend/             Lokales Backend fuer Entwicklung
  BIPRO- Dokumentation/             BiPRO-Referenzdokumentation
  GDV- Dokumentation/               GDV-Referenzdokumentation
```

## Server-Deployment (Hetzner)

### Deployment-Ablauf
1. Dateien lokal im ATLAS-Private Repo unter `00_VPS_ABBILD_NICHT LIVE/Abbild/var/www/atlas/` bearbeiten
2. Als Tarball buendeln und per SCP hochladen (SSH-Regeln beachten!)
3. Per SSH entpacken: `cd /var/www/atlas && tar -xzf /tmp/deploy.tar.gz`
4. PHP-Aenderungen wirken sofort (PHP-FPM interpretiert bei jedem Request neu)
5. JS/CSS-Aenderungen: Browser-Cache leeren (`Ctrl+Shift+R`)
6. DB-Migrationen: `ssh root@46.225.16.146 "cd /var/www/atlas/api && php -r \"require 'config.php'; require 'setup/042_migration.php';\""`

### Wichtige Server-Pfade
| Pfad | Beschreibung |
|------|-------------|
| `/var/www/atlas/` | Web-Root (API + Admin-Panel) |
| `/var/www/atlas/api/` | PHP REST-API |
| `/var/www/atlas/api/config.php` | DB-Credentials, API-Keys (NUR auf Server!) |
| `/var/www/atlas/admin-panel/` | Web-Admin-Panel |
| `/mnt/atlas-volume/` | Persistenter Storage (Dokumente, Releases, Backups) |
| `/etc/sudoers.d/atlas-admin` | sudo-Rechte fuer www-data (Server-Management) |
| `/etc/php/8.3/fpm/conf.d/99-atlas.ini` | PHP-FPM Config (disable_functions angepasst!) |

### PHP disable_functions (WICHTIG)
In `/etc/php/8.3/fpm/conf.d/99-atlas.ini` sind `exec` und `shell_exec` AKTIV (nicht disabled), weil `server_management.php` diese fuer Systemkommandos benoetigt. Alle anderen gefaehrlichen Funktionen (`passthru`, `system`, `proc_open`, `popen`, `dl`) bleiben disabled.

---

## Definition of Done (DoD)

Jede Aenderung am Projekt muss folgende Kriterien erfuellen:

- [ ] **Build laeuft**: `python -m PyInstaller build_config.spec --clean --noconfirm` erfolgreich
- [ ] **Tests laufen**: `python src/tests/run_smoke_tests.py` + `pytest src/tests/` gruen
- [ ] **Lint ok**: `ruff check src/` ohne Fehler
- [ ] **i18n**: Alle neuen UI-Texte in `src/i18n/de.py` (Desktop) bzw. `admin-panel/i18n/de.js` (Web)
- [ ] **Keine Secrets im Repo**: Keine API-Keys, Passwoerter, Tokens im Code
- [ ] **Keine modalen Popups**: `ToastManager` statt `QMessageBox.information/warning/critical`
- [ ] **Kein blockierender Code auf Main-Thread**: Lange Operationen via QThread-Worker
- [ ] **Docs aktualisiert**: AGENTS.md und README.md bei Feature-Aenderungen aktualisieren
- [ ] **VERSION**: Bei Release-wuerdigen Aenderungen VERSION-Datei aktualisieren
- [ ] **PR-Checkliste**: `.github/pull_request_template.md` abarbeiten

---

## Aktueller Stand (05.03.2026)

### Implementiert (Komplett)
- **Desktop-App**: Voll funktionsfaehig mit 4 Hauptmodulen + Modul-Admin:
  - **Core** (MainHub): BiPRO-Datenabruf, Dokumentenarchiv mit KI, GDV-Editor, Mitteilungszentrale, Chat
  - **Provision** (ProvisionHub): 10 Panels - Dashboard, Performance, Import, VU-Zuordnung, Xempus, Freie Provisionen, Klaerung, Verteilung, Auszahlungen, Einstellungen
  - **Workforce** (WorkforceHub): 7 Panels - Arbeitgeber, Mitarbeiter, Exporte, Snapshots, Statistiken, Trigger, SMTP
  - **Admin** (AdminShell): 17 Panels - Nutzer, Sessions, Passwoerter, Aktivitaet, KI-Kosten, Releases, KI-Klassifikation, KI-Provider, Modell-Preise, Dokumenten-Regeln, E-Mail-Konten, SmartScan-Einstellungen, SmartScan-Historie, E-Mail-Posteingang, Mitteilungen, Server-Gesundheit, Migrationen
  - **Modul-Admin** (ModuleAdminShell): 3 Tabs pro Modul - Zugriff, Rollen, Konfiguration
- **Modul-System**: Modulare Zugriffssteuerung mit Rollen und Berechtigungen (Migrationen 045-050, 5 neue DB-Tabellen)
- **Workforce-Modul**: HR-Provider-Integration (Personio, HRworks, SageHR Mock), Delta-SCS-Export, Trigger-System (E-Mail + API), 30 PHP-Endpoints (/hr/*), 9 DB-Tabellen (hr_*), 5 Permissions, Migration 044
- **Web-Admin-Panel**: 27 Panels deployed (17 Desktop-Admin repliziert + 9 Server-Management + 1 System-Status)
- **PHP-API**: ~48 Endpoints inkl. 13 Server-Management + 30 HR/Workforce + Modul-Verwaltung
- **DB-Migrationen**: Bis 050 (hr_module, account_type, modules, user_modules, permissions, roles, role_permissions, user_roles, backfill)
- **Server**: Hetzner Cloud (CCX13), SSL, Fail2Ban, Backups, sudoers konfiguriert

### Bekannte Einschraenkungen / Tech Debt
- KI-Provider und Modell-Preise: Muessen im Web-Panel manuell konfiguriert werden (Desktop-Client nutzt config.php-Fallback)
- Volume "Groesste Dateien": Abhaengig von www-data Dateiberechtigungen auf dem Server
- Kein WebSocket-Support (Polling-basiert, Live-Logs/Metriken)
- Kein Dark Mode im Web-Admin-Panel
- Kein Release-Upload im Browser
- Admin-Panel hat keine automatische Cache-Invalidierung (manueller Hard-Refresh noetig)
- Workforce: SageHR-Provider ist nur Mock (keine echte API)
- Workforce: Datenmigration aus HR-Hub JSON-Dateien noch nicht durchgefuehrt

---

## Workforce-Modul (HR)

### Ueberblick
- **UI-Name**: "Workforce" (eigener Hub, wie Provision/Ledger)
- **DB-Tabellen**: `hr_*` (9 Tabellen, Migration 044)
- **PHP-Endpoints**: `/hr/*` (30 Endpoints in `api/hr.php`)
- **Permissions**: `hr.view`, `hr.sync`, `hr.export`, `hr.triggers`, `hr.admin` (explizit, nicht auto-Admin)
- **Python-Modul**: `src/workforce/` (Provider, Services, API-Client, Worker)
- **i18n-Prefix**: `WF_` (~200 Keys)

### Architektur
- **Provider-Calls**: Desktop -> HR-API direkt (Personio, HRworks), NICHT ueber PHP
- **Persistenz**: Desktop -> PHP-API -> MySQL (CRUD, Bulk-Upsert, Snapshots, Exports)
- **Credentials**: PHP verschluesselt/entschluesselt (AES-256-GCM via Crypto-Klasse)
- **Trigger**: Desktop wertet aus + fuehrt aus (E-Mail via smtplib, API via requests)
- **Exports**: Desktop generiert XLSX (openpyxl), uploaded an PHP/Volume

### Kern-Datenfluss (Delta-Export)
1. Credentials vom PHP-Backend holen (entschluesselt)
2. Provider-API direkt aufrufen (Personio/HRworks)
3. Letzten Snapshot vom PHP-Backend laden
4. Delta berechnen (Hash-Vergleich lokal)
5. XLSX generieren (openpyxl lokal)
6. Neuen Snapshot speichern (PHP)
7. Export hochladen (PHP/Volume)
8. Trigger auswerten und ausfuehren (Desktop)
9. Trigger-Runs loggen (PHP)

### Dateien
| Datei | Zweck |
|-------|-------|
| `src/workforce/api_client.py` | WorkforceApiClient (30+ Methoden) |
| `src/workforce/workers.py` | QThread-Worker (Sync, Delta, Standard, Stats) |
| `src/workforce/providers/` | BaseProvider, HRworks, Personio, SageHR |
| `src/workforce/services/` | Sync, Delta, Export, Snapshot, Trigger, Stats |
| `src/ui/workforce/workforce_hub.py` | Hub mit Sidebar (7 Panels) |
| `src/ui/workforce/*_view.py` | 7 View-Panels |
| `api/hr.php` | 30 PHP-Endpoints |
| `api/setup/044_hr_module.php` | DB-Migration (9 Tabellen + 5 Permissions) |

---

## Modul-System (Rollen & Zugriffssteuerung)

### Ueberblick
- **Zweck**: Modulare Zugriffssteuerung -- jedes Modul (Core, Provision, Workforce) kann pro User freigeschaltet und mit Rollen/Rechten versehen werden
- **Account-Typen**: `user`, `admin`, `super_admin` (3-stufig, Migration 045)
- **Module**: `core`, `provision`, `workforce` (registriert in `modules`-Tabelle, Migration 046)
- **Zugangslevel pro Modul**: `user` (Standard-Zugriff) oder `admin` (Modul-Admin, darf Rollen/Zugriff verwalten)
- **Rollen**: Modul-spezifische Rollen mit konfigurierbaren Rechten (z.B. `provision.manager`, `hr.admin`)
- **PHP-Endpoints**: `/admin/modules`, `/admin/modules/{key}/roles`, `/admin/modules/{key}/users`

### Architektur

```
AppRouter (Modul-Check)
├── has_module("core")      → MainHub
├── has_module("provision") → ProvisionHub
├── has_module("workforce") → WorkforceHub
├── is_module_admin("core")      → ModuleAdminShell (Core)
├── is_module_admin("provision") → ModuleAdminShell (Provision)
└── is_module_admin("workforce") → ModuleAdminShell (Workforce)

ModuleAdminShell (pro Modul)
├── Tab 1: Zugriff (ModuleAccessPanel)    → User mit Zugriff, Rollen-Zuweisung
├── Tab 2: Rollen (ModuleRolesPanel)      → Rollen CRUD, Rechte zuweisen
└── Tab 3: Konfiguration (ModuleConfigPanel) → Modul-spezifische Config-Panels
```

### Datenfluss (Modul-Freischaltung)
1. Super-Admin/Admin schaltet User fuer ein Modul frei (Nutzerverwaltung)
2. `user_modules`-Eintrag wird erstellt (`is_enabled=true`, `access_level='user'`)
3. Dashboard zeigt nur freigeschaltete Module als Kacheln
4. GlobalHeartbeat prueft Modul-Aenderungen (`modules_updated`-Signal)
5. Entzogener Zugriff fuehrt sofort zurueck zum Dashboard

### DB-Tabellen (Migrationen 045-050)

| Tabelle | Migration | Beschreibung |
|---------|-----------|-------------|
| `users.account_type` | 045 | ENUM erweitert: user, admin, super_admin |
| `modules` | 046 | Registrierte Module (key, name, description) |
| `user_modules` | 047 | User ↔ Modul (is_enabled, access_level) |
| `permissions` | 048 | Erweitert um module_key, Rollen-Tabelle erstellt |
| `roles` | 048 | Modul-spezifische Rollen (role_key, name, description) |
| `role_permissions` | 049 | Rolle ↔ Permission Mapping |
| `user_roles` | 049 | User ↔ Rolle Mapping pro Modul |

### Dateien

| Datei | Zweck |
|-------|-------|
| `src/api/admin_modules.py` | AdminModulesAPI (10 Methoden: Module, Rollen, User-Zugriff) |
| `src/ui/module_admin/module_admin_shell.py` | Generische Shell mit 3 Tabs |
| `src/ui/module_admin/access_panel.py` | User-Tabelle + Rollen-Zuweisungsdialog |
| `src/ui/module_admin/roles_panel.py` | Rollen-CRUD + Rechte-Verwaltung |
| `src/ui/module_admin/config_panel.py` | Einbettung bestehender Admin-Panels |
| `src/ui/app_router.py` | Modul-Check + Lazy-Init der Module |
| `api/admin_modules.php` | PHP-Backend (Module, Rollen, User-Module, User-Rollen) |
| `api/setup/045_extend_account_type.php` | account_type ENUM erweitern |
| `api/setup/046_create_modules.php` | modules-Tabelle erstellen |
| `api/setup/047_create_user_modules.php` | user_modules-Tabelle erstellen |
| `api/setup/048_extend_permissions_create_roles.php` | Rollen + Permissions |
| `api/setup/049_create_role_permissions_user_roles.php` | Mapping-Tabellen |
| `api/setup/050_backfill_user_modules.php` | Bestehende User → Core-Modul |

---

## Bekannte TODOs im Code

| Datei | TODO |
|-------|------|
| `src/bipro/bipro_connector.py` L.211 | SmartAdmin Transfer-Service implementieren |
| `src/ui/admin/panels/email_inbox.py` L.320 | API-Call zum Ignorieren |
| `src/api/smartadmin_auth.py` L.346 | Vollstaendige X.509 WS-Security Implementation |
| `src/api/smartadmin_auth.py` L.595 | listShipments SOAP-Call implementieren |

---

## Tasks (Roadmap)

### Kurzfristig (naechste Sprints)
1. **SageHR-Provider realisieren**: Mock durch echte API-Anbindung ersetzen
2. **HR-Datenmigration**: Bestehende JSON-Daten aus HR-Hub in neue DB-Tabellen migrieren
3. **SmartAdmin BiPRO**: Transfer-Service fuer SmartAdmin-Anbindung implementieren (TODO im Code)
4. **E-Mail-Inbox Ignorieren**: API-Call zum Ignorieren von E-Mails im Posteingang

### Mittelfristig
5. **Dark Mode (Web-Admin-Panel)**: Aktuell nur Light-Theme
6. **WebSocket-Support**: Polling-basierte Benachrichtigungen durch WebSockets ersetzen
7. **Release-Upload im Browser**: Aktuell nur per Desktop-Client moeglich
8. **Cache-Invalidierung (Admin-Panel)**: Automatische Aktualisierung statt manueller Hard-Refresh

### Langfristig
9. **Weitere BiPRO-Versicherer**: Anbindung weiterer VUs ueber BiPRO-Standard
10. **X.509 WS-Security**: Vollstaendige Implementation fuer SmartAdmin

---

## Weitere Dokumentation

| Dokument | Beschreibung |
|----------|-------------|
| [README.md](README.md) | Projektuebersicht, Features, Quickstart, Changelog |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Detaillierte Architektur mit Datenfluss-Diagrammen |
| [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) | Lokales Setup, Build, Test, Debugging |
| [docs/CONFIGURATION.md](docs/CONFIGURATION.md) | Alle Konfigurationsoptionen und Umgebungsvariablen |
| [docs/DOMAIN.md](docs/DOMAIN.md) | Fachdomaene: Begriffe, Entitaeten, Workflows |
| `ATLAS_private - Doku - Backend/docs/` | Interne Kern- und Entwickler-Dokumentation (53 Dateien) |
