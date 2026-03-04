# AGENTS.md
# ACENCIA ATLAS -- Desktop Client + Web-Admin-Panel

> **Version**: siehe `VERSION`-Datei (aktuell 2.3.1) | **Stand**: 04.03.2026
> Detaillierte Dokumentation liegt im privaten Submodule `ATLAS_private - Doku - Backend/`.

**Agent's Responsibility:** Dieses Dokument ist die Single Source of Truth fuer Agent-Zusammenarbeit an diesem Projekt. Bei jedem neuen Feature, Bugfix oder Refactor **muss** dieses Dokument aktualisiert werden.

---

## Projekt-Steckbrief

| Feld | Wert |
|------|------|
| **Name** | ACENCIA ATLAS ("Der Datenkern.") |
| **Typ** | Python-Desktop-App (PySide6/Qt) + PHP-REST-API + MySQL + Web-Admin-Panel (Vanilla JS) |
| **Zweck** | BiPRO-Datenabruf, Dokumentenarchiv, GDV-Editor, Provisionsmanagement, Server-Administration |
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

Der Ordner `ATLAS_private - Doku - Backend/ATLAS - Hetzner Server - ABBILD - NICHT LIVE/Abbild/var/www/atlas/` ist die lokale Kopie des Live-Servers. Aenderungen hier muessen per SSH auf den Server deployed werden, um wirksam zu werden. Der Ordner selbst ist NICHT live synchronisiert.

### UI-Texte

- **Desktop-App**: MUESSEN aus `src/i18n/de.py` stammen
- **Web-Admin-Panel**: MUESSEN aus `admin-panel/i18n/de.js` stammen
- **Keine Hardcoded Strings** in Komponenten

---

## Architektur (Clean Architecture)

```
Desktop-App (PySide6)             Web-Admin-Panel                  Hetzner Cloud (CCX13, Nuernberg)
├── UI Layer                      ├── index.html (SPA)             ├── Nginx (HTTPS, HTTP/2, Rate-Limiting)
│   ├── main_hub.py               ├── css/ (5 Dateien)             ├── PHP 8.3 FPM + REST API (~47 Dateien)
│   ├── provision/ (10 Panels)    │   └── tokens.css (ACENCIA CI)  │   ├── auth.php (JWT, is_super_admin)
│   ├── admin/ (17 Panels)        ├── js/ (41 Dateien)             │   ├── documents.php (Archiv)
│   └── message_center_view.py    │   ├── api.js (API Client)      │   ├── server_management.php (13 Endpoints)
├── Presenters (MVP)              │   ├── auth.js (JWT + Timeout)   │   ├── ai_providers.php (Provider CRUD)
├── Use Cases                     │   ├── router.js (Hash-SPA)     │   ├── model_pricing.php (Preise CRUD)
├── Domain (Entities, Rules)      │   ├── components/ (6 Module)   │   ├── processing_settings.php (KI-Config)
├── Infrastructure (Adapters)     │   └── panels/ (27 Panels)      │   └── ... (~47 Dateien)
├── API Clients (~29 Module)      └── i18n/de.js (~430 Keys)       ├── MySQL 8.0 Self-Hosted (~63 Tabellen)
├── BiPRO SOAP Client                                              ├── Volume 100 GB (/mnt/atlas-volume)
└── Services (~16 Module)                                          │   ├── dokumente/ (~2.600 Dateien, ~450 MB)
                                                                   │   ├── releases/ (~30 Installer, ~5.4 GB)
                                                                   │   └── backups/ (taeglich, 30 Tage)
                                                                   └── Admin-Panel (/admin-panel/, ~50 Dateien)
```

**Server-Details:** Siehe `ATLAS_private - Doku - Backend/hetzner-migration/INFRASTRUKTUR_DATEN.md`
**Server-Abbild:** Siehe `ATLAS_private - Doku - Backend/ATLAS - Hetzner Server - ABBILD - NICHT LIVE/`
**Admin-Panel-Plan:** Siehe `ATLAS_private - Doku - Backend/docs/04_PRODUCT/ADMIN_PANEL_ERWEITERUNG_PLAN.md`

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
- **Pipeline-Toolchain**: `ATLAS_private - Doku - Backend/governance/atlas.ps1`
- **CI**: Smoke-Tests + CodeQL auf main/beta, Secret Scanning aktiv
- **Governance-Details**: Siehe `.cursor/rules/git-pipeline.mdc`

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
VERSION                             Versionsdatei (aktuell 2.3.1)
requirements.txt                    Dependencies (15 Pakete)
build_config.spec                   PyInstaller-Konfiguration
installer.iss                       Inno Setup Installer-Skript
```

## Interne Dokumentation

Detaillierte Architektur, API-Docs, Security, Governance und Backend-Code
liegen im privaten Submodule:

```
ATLAS_private - Doku - Backend/     (Git Submodule, privat)
  docs/                             Kern- und Entwickler-Dokumentation (3-Stufen-Hierarchie, 53 Dateien)
    00_CORE/                        Kern-Dokumentation (7 Dateien inkl. ATLAS_KOMPLETT.md)
    01_DEVELOPMENT/                 Entwickler-Dokumentation (10 Dateien)
    02_SECURITY/                    Sicherheit & Berechtigungen (2 Dateien)
    03_REFERENCE/                   Referenz-Material (3 Dateien)
    04_PRODUCT/                     Produkt-Planung (Roadmap, Ideas, ADMIN_PANEL_ERWEITERUNG_PLAN.md)
    99_ARCHIVE/                     Historische Dokumente (4 Unterordner)
  governance/                       Pipeline-Skripte (atlas.ps1 + 14 Einzelskripte + 3 Flows)
  build-tools/                      Build-Werkzeuge (9 Dateien)
  scripts/                          Hilfsskripte (10 Python-Dateien)
  testdata/                         Testdaten (inkl. Provision)
  ChatGPT-Kontext/                  KI-Kontext-Dateien (11 Markdown-Dateien)
  BiPro-Webspace Spiegelung Live/   PHP REST-API Backend (~76 Dateien, ~22.800 eigene Zeilen)
    api/                            33 PHP-Endpoints (+ lib/, setup/)
    api/lib/                        Shared Libraries (DB, JWT, Crypto, Permissions, PHPMailer)
    api/setup/                      DB-Migrationen (36 Skripte, 005-043)
  ATLAS - Hetzner Server - ABBILD - NICHT LIVE/
    README.md                       Sync-Anleitung und Ordnerstruktur
    Abbild/                         Lokale Kopie des Servers (etc/, var/www/, opt/)
      var/www/atlas/                Gesamtes Web-Root inkl. Admin-Panel
        admin-panel/                Web-Admin-Panel (~50 Dateien, Vanilla JS SPA)
        api/                        PHP REST-API (~47 Dateien)
  hetzner-migration/                Server-Migration Strato -> Hetzner (abgeschlossen 03.03.2026)
    INFRASTRUKTUR_DATEN.md          Live-Infrastruktur-Werte (IPs, Credentials, Pfade)
  AGENTS.md                         Vollstaendige Agent-Instruktionen (Single Source of Truth)
```

## Server-Deployment (Hetzner)

### Deployment-Ablauf
1. Dateien lokal unter `ATLAS - Hetzner Server - ABBILD - NICHT LIVE/Abbild/var/www/atlas/` bearbeiten
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

## Aktueller Stand (04.03.2026)

### Implementiert
- Desktop-App: Voll funktionsfaehig (BiPRO, Archiv, GDV, Provision, 17 Admin-Panels)
- Web-Admin-Panel: 27 Panels deployed und funktionsfaehig
  - 17 bestehende Desktop-Admin-Funktionen ins Web repliziert
  - 9 neue Server-Management-Panels (Super-Admin)
  - 1 System-Status-Panel (bereits vorhanden, erweitert)
- PHP-API: ~47 Endpoints, inkl. 13 neue Server-Management-Endpoints
- DB-Migrationen: Bis 043 (is_excluded, is_super_admin, server_audit_log)
- Server: Hetzner Cloud, SSL, Fail2Ban, Backups, sudoers konfiguriert

### Bekannte Einschraenkungen / Tech Debt
- KI-Provider und Modell-Preise: Muessen im Web-Panel manuell konfiguriert werden (Desktop-Client nutzt config.php-Fallback)
- Volume "Groesste Dateien": Abhaengig von www-data Dateiberechtigungen auf dem Server
- Kein WebSocket-Support (Polling-basiert, Live-Logs/Metriken)
- Kein Dark Mode im Web-Admin-Panel
- Kein Release-Upload im Browser
- Admin-Panel hat keine automatische Cache-Invalidierung (manueller Hard-Refresh noetig)
