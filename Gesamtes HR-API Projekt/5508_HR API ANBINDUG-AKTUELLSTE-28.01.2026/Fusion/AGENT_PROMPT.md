# AGENT PROMPT: HR-Modul → ATLAS Integration (Fusion)

## Deine Aufgabe

Du bist ein Coding-Agent, der das **HR-Modul als eigenständiges Modul in die ATLAS Desktop-Anwendung integrieren** soll. Das HR-Modul existiert als Prototyp (ACENCIA HR-Hub, Flask-basiert) und muss als vollwertiges ATLAS-Modul neu gebaut werden – mit PHP-Backend-Endpoints, MySQL-Tabellen, Python-Desktop-Logik und PySide6-UI.

**WICHTIG:** Lies ALLE referenzierten Dokumente vollständig, bevor du eine einzige Zeile Code schreibst.

---

## Phase 0: Pflichtlektüre (IN DIESER REIHENFOLGE)

Bevor du irgendetwas implementierst, MUSST du diese Dokumente lesen und verstehen:

### Über das Quellprojekt (HR-Hub)

1. `Kontext/00_INDEX.md` → Inhaltsverzeichnis der Projektanalyse
2. `Kontext/01_Projektueberblick.md` → Was ist der HR-Hub, was tut er
3. `Kontext/02_System_und_Architektur.md` → Tech-Stack, Architektur, Routen
4. `Kontext/03_Domain_und_Begriffe.md` → Alle Fachbegriffe (Employer, Provider, Snapshot, SCS, Delta, Trigger...)
5. `Kontext/04_Code_Struktur_und_Moduluebersicht.md` → Komplette Code-Anatomie von app.py (5326 Zeilen)
6. `Kontext/05_Laufzeit_und_Flows.md` → Alle Datenflüsse (Login, Mitarbeiter, Delta-Export, Trigger, etc.)
7. `Kontext/06_Konfiguration_und_Abhaengigkeiten.md` → Abhängigkeiten und Konfiguration
8. `ACENCIA_API_Hub/AGENTS.md` → Detaillierte technische Agenten-Dokumentation
9. `ACENCIA_API_Hub/docs/ARCHITECTURE.md` → Architektur-Dokumentation
10. `ACENCIA_API_Hub/docs/TRIGGERS.md` → Trigger-System-Dokumentation

### Über die ATLAS-Integration (Fusion)

11. `Fusion/00_INDEX.md` → Übersicht der Fusions-Dokumentation
12. `Fusion/01_Zielarchitektur.md` → Architektur-Diagramm, Verantwortlichkeiten, Datenflüsse
13. `Fusion/02_Modul_Mapping.md` → Exakte Zuordnung: app.py Zeilen → neue Dateien
14. `Fusion/03_Endpoint_Kontrakte.md` → PHP-Endpoint-Spezifikation (Request/Response)
15. `Fusion/04_MySQL_Schema.md` → Komplettes DB-Schema mit allen 9 Tabellen
16. `Fusion/05_API_Client_Spezifikation.md` → HRApiClient Python-Klasse
17. `Fusion/06_Migrations_Checkliste.md` → 6-Phasen-Implementierungsplan

### Über ATLAS selbst

18. Untersuche die ATLAS-Projektstruktur (PySide6-App, `src/`-Verzeichnis)
19. Verstehe das bestehende Auth-System (JWT, Login, Permissions)
20. Verstehe den bestehenden BaseApiClient (HTTP-Client mit JWT-Support)
21. Verstehe die bestehende Modul-Registrierung (Sidebar, Navigation)
22. Verstehe das bestehende Logging-System
23. Verstehe die bestehende PHP-API-Struktur auf Strato

---

## Das Quellprojekt: ACENCIA HR-Hub

### Was es ist

Eine Flask-Web-Anwendung (~5326 Zeilen in einer einzigen `app.py`), die als zentrales HR-Dashboard dient. Sie:

- Verbindet sich mit HR-Provider-APIs (Personio, HRworks, SageHR)
- Normalisiert Mitarbeiterdaten aus verschiedenen Systemen
- Erstellt Delta-Exporte im SCS-Format für Lohnabrechnung
- Verwaltet Snapshots für historische Vergleiche
- Berechnet Standard- und Langzeit-Statistiken
- Führt automatisierte Trigger-Aktionen aus (E-Mail, API-Calls)
- Unterstützt Multi-Mandanten (mehrere Arbeitgeber)
- Hat ein komplettes Benutzer- und Rechtesystem

### Tech-Stack (IST / wird abgelöst)

| Komponente | Aktuell | Wird zu |
|------------|---------|---------|
| Framework | Flask 3.0.3 | PySide6 (ATLAS Desktop) |
| Templates | Jinja2 | PySide6 Views (QWidget) |
| Datenhaltung | JSON-Dateien | MySQL via PHP-API |
| Auth | Flask-Sessions | ATLAS JWT |
| Server | Waitress (WSGI) | Entfällt (Desktop-App) |
| HTTP | Direkt (requests) | ATLAS BaseApiClient |

### Kernklassen (aus app.py)

| Klasse | Zeilen | Zweck | Übernahme |
|--------|--------|-------|-----------|
| `BaseProvider` (ABC) | 1837-1887 | Interface für HR-APIs | 1:1 |
| `HRworksProvider` | 1889-2141 | HRworks API v2 | 1:1 (Import-Pfade anpassen) |
| `PersonioProvider` | 2186-2362 | Personio API v1 | 1:1 (Import-Pfade anpassen) |
| `SageHrProvider` | 2142-2185 | Mock-Provider | 1:1 |
| `ProviderFactory` | 2363-2390 | Factory-Pattern | 1:1 |
| `TriggerEngine` | 1164-1600 | Trigger-Auswertung | 1:1 (API statt JSON-Store) |
| `EmailAction` | 1602-1740 | SMTP E-Mail-Versand | 1:1 |
| `APIAction` | 1742-1835 | HTTP-Requests | 1:1 |
| `EmployerStore` | 460-617 | JSON-Persistenz | ENTFÄLLT (→ PHP-API) |
| `TriggerStore` | 624-973 | JSON-Persistenz | ENTFÄLLT (→ PHP-API) |
| `TriggerLogStore` | 975-1160 | JSON-Persistenz | ENTFÄLLT (→ PHP-API) |

### Kern-Funktionen (aus app.py)

| Funktion | Zeilen | Zweck | Übernahme |
|----------|--------|-------|-----------|
| `SCS_HEADERS` | 306-313 | Feste Export-Spalten | 1:1 → constants.py |
| `_get_from_path()` | 315-343 | Sichere Dict-Navigation | 1:1 → helpers.py |
| `_getv()` | 345-364 | Wert-Extraktion | 1:1 → helpers.py |
| `_get_safe_employer_name()` | 366-376 | Dateiname-Bereinigung | 1:1 → helpers.py |
| `_parse_date()` | 397-413 | Datum-Parsing | 1:1 → helpers.py |
| `_json_hash()` | 2509-2520 | SHA256 für Änderungserkennung | 1:1 → helpers.py |
| `_flatten_record()` | 2522-2542 | Dict abflachen | 1:1 → helpers.py |
| `_person_key()` | 2544-2555 | Eindeutige Person-ID | 1:1 → helpers.py |
| `_map_to_scs_schema()` | 2394-2471 | SCS-Format-Mapping | 1:1 → export_service.py |
| `generate_standard_export()` | 2473-2507 | XLSX-Vollexport | 1:1 → export_service.py |
| `generate_delta_scs_export()` | 2557-2675 | Delta-Export | Anpassung (API statt FS) |
| `_compare_snapshots()` | 4712-4762 | Snapshot-Diff | 1:1 → snapshot_service.py |
| `calculate_statistics()` | 2779-2829 | Standard-KPIs | 1:1 → stats_service.py |
| `calculate_long_term_statistics()` | 2830-2905 | Langzeit-KPIs | 1:1 → stats_service.py |

---

## Das Zielsystem: ATLAS

### Architektur

```
┌──────────────────────────────────────────────────────────────────────────┐
│                     ATLAS Desktop (PySide6 / Python)                     │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │  Bestehende Module                                                  │ │
│  │  ├── BiPRO, Archiv, GDV, Admin                                     │ │
│  │  ├── src/api/* (bestehende API-Clients)                            │ │
│  │  └── Auth-System (JWT, Login, Permissions)                          │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │  NEUES HR-MODUL (deine Aufgabe)                                     │ │
│  │                                                                      │ │
│  │  hr/providers/          hr/services/          hr/views/             │ │
│  │  ├── base.py            ├── sync_service.py   ├── employers_view   │ │
│  │  ├── hrworks.py         ├── delta_service.py  ├── employees_view   │ │
│  │  ├── personio.py        ├── export_service.py ├── exports_view     │ │
│  │  └── sagehr.py          ├── snapshot_service  ├── snapshots_view   │ │
│  │                         ├── trigger_service   ├── triggers_view    │ │
│  │  hr/api_client.py       └── stats_service.py  └── stats_view      │ │
│  │  (PHP-Backend-Komm.)                                                │ │
│  └─────────────┬───────────────────────────┬──────────────────────────┘ │
│                │                           │                            │
│       ┌────────┘                           └────────┐                   │
│       ▼                                             ▼                   │
│  ┌─────────────────┐                    ┌─────────────────────┐        │
│  │ HR-Provider APIs │                    │ PHP REST-API        │        │
│  │ (HTTPS direkt)   │                    │ (Strato, JWT)       │        │
│  │ ┌─────────────┐  │                    │ /hr/* Endpoints     │        │
│  │ │ Personio    │  │                    └──────────┬──────────┘        │
│  │ │ HRworks     │  │                               │                   │
│  │ │ SageHR      │  │                               ▼                   │
│  │ └─────────────┘  │                    ┌─────────────────────┐        │
│  └─────────────────┘                    │ MySQL (Strato)      │        │
│                                          │ hr_* Tabellen       │        │
│                                          └─────────────────────┘        │
│                                                     │                   │
│                                                     ▼                   │
│                                          ┌─────────────────────┐        │
│                                          │ Webspace (Strato)   │        │
│                                          │ /files/hr/exports/  │        │
│                                          └─────────────────────┘        │
└──────────────────────────────────────────────────────────────────────────┘
```

### Verantwortlichkeiten Desktop vs. PHP

**Desktop (Python/PySide6) – Geschäftslogik:**
- Provider-API-Calls (Personio, HRworks direkt via HTTPS)
- Daten normalisieren (Provider-spezifische normalize-Methoden)
- Delta berechnen (Hash-Vergleich lokal)
- Excel generieren (openpyxl lokal)
- Trigger auswerten und ausführen (E-Mail via smtplib, API via requests)
- Statistiken berechnen (lokal)
- UI rendern (PySide6 Views, QThread für Non-blocking)

**PHP-Backend (Strato) – Reine Persistenz:**
- JWT-Auth prüfen (wie bestehend)
- Permissions prüfen (hr.view, hr.sync, hr.export, hr.triggers, hr.admin)
- CRUD für alle hr_*-Tabellen
- Credentials AES-256-GCM ver-/entschlüsseln
- Export-Dateien auf Webspace verwalten
- **Keine** HR-Provider-Logik im PHP!

### Auth-Flow (kein eigenes Auth)

```
1. Nutzer startet ATLAS Desktop
2. Login → POST /auth/login → JWT
3. JWT wird in allen API-Calls verwendet
4. HR-Modul nutzt denselben JWT
5. PHP prüft hr.* Permissions:
   - hr.view       → Arbeitgeber/Mitarbeiter sehen
   - hr.sync       → Daten synchronisieren
   - hr.export     → Exporte generieren
   - hr.triggers   → Trigger verwalten (Master only)
   - hr.admin      → Arbeitgeber verwalten
```

---

## MySQL-Schema (9 Tabellen)

Alle Tabellen mit Prefix `hr_` in der bestehenden ATLAS-MySQL-Datenbank:

### hr_employers
```sql
CREATE TABLE hr_employers (
    id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    name            VARCHAR(255) NOT NULL,
    provider_key    ENUM('personio', 'hrworks', 'sagehr') NOT NULL,
    status          ENUM('active', 'inactive', 'deleted') DEFAULT 'active',
    address_json    JSON COMMENT 'Adressdaten: {street, zip_code, city, country}',
    settings_json   JSON COMMENT 'Zusätzliche Einstellungen',
    last_sync_at    DATETIME,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

### hr_provider_credentials
```sql
CREATE TABLE hr_provider_credentials (
    id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    employer_id     INT UNSIGNED NOT NULL,
    encrypted_blob  VARBINARY(2048) NOT NULL COMMENT 'AES-256-GCM verschlüsselt',
    iv              VARBINARY(16) NOT NULL,
    auth_tag        VARBINARY(16) NOT NULL,
    key_version     INT UNSIGNED DEFAULT 1,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (employer_id) REFERENCES hr_employers(id) ON DELETE CASCADE,
    UNIQUE KEY uk_employer (employer_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

### hr_employees
```sql
CREATE TABLE hr_employees (
    id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    employer_id     INT UNSIGNED NOT NULL,
    provider_pid    VARCHAR(100) NOT NULL,
    first_name      VARCHAR(100),
    last_name       VARCHAR(100),
    email           VARCHAR(255),
    department      VARCHAR(255),
    position        VARCHAR(255),
    status          ENUM('active', 'inactive') DEFAULT 'active',
    join_date       DATE,
    leave_date      DATE,
    details_json    JSON,
    data_hash       CHAR(64),
    last_synced_at  DATETIME,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (employer_id) REFERENCES hr_employers(id) ON DELETE CASCADE,
    UNIQUE KEY uk_employer_pid (employer_id, provider_pid),
    INDEX idx_employer_status (employer_id, status),
    INDEX idx_data_hash (data_hash)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

### hr_snapshots
```sql
CREATE TABLE hr_snapshots (
    id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    employer_id     INT UNSIGNED NOT NULL,
    snapshot_ts     DATETIME NOT NULL,
    employee_count  INT UNSIGNED DEFAULT 0,
    content_hash    CHAR(64),
    is_latest       TINYINT(1) DEFAULT 0,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (employer_id) REFERENCES hr_employers(id) ON DELETE CASCADE,
    INDEX idx_employer_ts (employer_id, snapshot_ts DESC),
    INDEX idx_latest (employer_id, is_latest)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

### hr_snapshot_employees
```sql
CREATE TABLE hr_snapshot_employees (
    snapshot_id     INT UNSIGNED NOT NULL,
    provider_pid    VARCHAR(100) NOT NULL,
    data_hash       CHAR(64) NOT NULL,
    core_json       JSON NOT NULL COMMENT 'SCS-Schema-Daten',
    flat_json       JSON,
    dates_json      JSON,
    PRIMARY KEY (snapshot_id, provider_pid),
    FOREIGN KEY (snapshot_id) REFERENCES hr_snapshots(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

### hr_exports
```sql
CREATE TABLE hr_exports (
    id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    employer_id     INT UNSIGNED NOT NULL,
    export_type     ENUM('standard', 'delta_scs') NOT NULL,
    filename        VARCHAR(255) NOT NULL,
    file_path       VARCHAR(500),
    file_size       INT UNSIGNED,
    snapshot_from   INT UNSIGNED,
    snapshot_to     INT UNSIGNED,
    diff_summary    JSON,
    created_by      VARCHAR(100),
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (employer_id) REFERENCES hr_employers(id) ON DELETE CASCADE,
    FOREIGN KEY (snapshot_from) REFERENCES hr_snapshots(id) ON DELETE SET NULL,
    FOREIGN KEY (snapshot_to) REFERENCES hr_snapshots(id) ON DELETE SET NULL,
    INDEX idx_employer_created (employer_id, created_at DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

### hr_triggers
```sql
CREATE TABLE hr_triggers (
    id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    name            VARCHAR(255) NOT NULL,
    event           ENUM('employee_added', 'employee_removed', 'employee_changed') NOT NULL,
    conditions_json JSON,
    condition_logic ENUM('AND', 'OR') DEFAULT 'AND',
    action_type     ENUM('email', 'api') NOT NULL,
    action_config   JSON NOT NULL,
    enabled         TINYINT(1) DEFAULT 1,
    excluded_employers JSON,
    statistics_json JSON,
    created_by      VARCHAR(100),
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_enabled_event (enabled, event)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

### hr_trigger_runs
```sql
CREATE TABLE hr_trigger_runs (
    id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    trigger_id      INT UNSIGNED NOT NULL,
    employer_id     INT UNSIGNED NOT NULL,
    employee_pid    VARCHAR(100),
    employee_name   VARCHAR(200),
    event           ENUM('employee_added', 'employee_removed', 'employee_changed'),
    status          ENUM('success', 'error', 'retried') NOT NULL,
    action_type     ENUM('email', 'api') NOT NULL,
    request_json    JSON,
    response_json   JSON,
    can_retry       TINYINT(1) DEFAULT 0,
    retry_of        INT UNSIGNED,
    executed_by     VARCHAR(100) DEFAULT 'system',
    executed_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (trigger_id) REFERENCES hr_triggers(id) ON DELETE CASCADE,
    FOREIGN KEY (employer_id) REFERENCES hr_employers(id) ON DELETE CASCADE,
    INDEX idx_employer_executed (employer_id, executed_at DESC),
    INDEX idx_trigger_status (trigger_id, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

### hr_smtp_config
```sql
CREATE TABLE hr_smtp_config (
    id              INT UNSIGNED PRIMARY KEY DEFAULT 1,
    host            VARCHAR(255),
    port            INT UNSIGNED DEFAULT 587,
    username_enc    VARBINARY(512),
    password_enc    VARBINARY(512),
    iv              VARBINARY(16),
    auth_tag        VARBINARY(16),
    use_tls         TINYINT(1) DEFAULT 1,
    from_email      VARCHAR(255),
    from_name       VARCHAR(255) DEFAULT 'ACENCIA HR',
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CHECK (id = 1)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

---

## PHP-Endpoint-Kontrakte

Alle Endpoints unter `/hr/*`, authentifiziert via JWT aus ATLAS-Auth-System.

### Permissions

| Permission | Beschreibung | Wer |
|-----------|-------------|-----|
| `hr.view` | Lesen (Arbeitgeber, Mitarbeiter, Snapshots) | Alle HR-Nutzer |
| `hr.sync` | Synchronisieren | HR-Manager |
| `hr.export` | Exporte | HR-Manager |
| `hr.triggers` | Trigger verwalten | Master |
| `hr.admin` | Arbeitgeber verwalten | Master |

### Endpoint-Liste

**Arbeitgeber:**
- `POST /hr/employers` (hr.admin) → Neuen Arbeitgeber anlegen
- `GET /hr/employers` (hr.view) → Alle Arbeitgeber auflisten
- `GET /hr/employers/{id}` (hr.view) → Einzelner Arbeitgeber
- `PUT /hr/employers/{id}` (hr.admin) → Arbeitgeber aktualisieren
- `DELETE /hr/employers/{id}` (hr.admin) → Soft-Delete

**Credentials:**
- `POST /hr/employers/{id}/credentials` (hr.admin) → Credentials speichern (PHP verschlüsselt)
- `GET /hr/employers/{id}/credentials` (hr.sync) → Credentials holen (PHP entschlüsselt)
- `GET /hr/employers/{id}/credentials/status` (hr.view) → Nur Status (kein Klartext)

**Mitarbeiter:**
- `POST /hr/employees/bulk` (hr.sync) → Bulk-Upsert (INSERT ON DUPLICATE KEY UPDATE)
- `GET /hr/employers/{id}/employees` (hr.view) → Paginiert, filterbar
- `GET /hr/employers/{id}/employees/{eid}` (hr.view) → Details

**Snapshots:**
- `POST /hr/snapshots` (hr.sync) → Neuen Snapshot speichern
- `GET /hr/employers/{id}/snapshots` (hr.view) → Snapshot-Liste
- `GET /hr/snapshots/{id}` (hr.view) → Snapshot mit Daten
- `GET /hr/employers/{id}/snapshots/latest` (hr.view) → Aktuellster Snapshot
- `DELETE /hr/snapshots/{id}` (hr.admin)

**Exports:**
- `POST /hr/exports` (hr.export) → Multipart Upload (XLSX + Metadaten)
- `GET /hr/employers/{id}/exports` (hr.view) → Export-Liste
- `GET /hr/exports/{id}/download` (hr.export) → Download

**Trigger:**
- `GET /hr/triggers` (hr.triggers) → Alle Trigger
- `POST /hr/triggers` (hr.triggers) → Neuer Trigger
- `PUT /hr/triggers/{id}` (hr.triggers) → Trigger aktualisieren
- `DELETE /hr/triggers/{id}` (hr.triggers) → Trigger löschen
- `PATCH /hr/triggers/{id}/toggle` (hr.triggers) → Aktivieren/Deaktivieren
- `PATCH /hr/triggers/{id}/exclude-employer` (hr.triggers) → AG ausschließen

**Trigger-Runs:**
- `POST /hr/trigger-runs` (hr.sync) → Ausführung loggen
- `GET /hr/trigger-runs` (hr.triggers) → Paginiert, filterbar

**SMTP:**
- `GET /hr/smtp-config` (hr.triggers) → Konfiguration (ohne Klartext-Passwort)
- `PUT /hr/smtp-config` (hr.triggers) → Konfiguration speichern
- `GET /hr/smtp-config/decrypted` (hr.triggers) → Mit Klartext-Passwort

**Fehler-Responses (einheitlich):**
```json
{ "error": "error_code", "message": "Beschreibung", "fields": {} }
```
Status-Codes: 400, 401, 403, 404, 500

Vollständige Request/Response-Beispiele: siehe `Fusion/03_Endpoint_Kontrakte.md`

---

## Python API-Client (Desktop → PHP)

```python
class HRApiClient:
    def __init__(self, base_client):  # Bestehender ATLAS BaseApiClient mit JWT

    # Employers
    def get_employers() -> list[dict]
    def get_employer(id) -> dict
    def create_employer(data) -> dict
    def update_employer(id, data) -> dict
    def delete_employer(id) -> bool

    # Credentials
    def save_credentials(employer_id, creds) -> dict
    def get_credentials(employer_id) -> dict
    def get_credentials_status(employer_id) -> dict

    # Employees
    def bulk_sync_employees(employer_id, employees) -> dict
    def get_employees(employer_id, **filters) -> dict
    def get_employee(employer_id, employee_id) -> dict

    # Snapshots
    def save_snapshot(employer_id, snapshot_data) -> dict
    def get_snapshots(employer_id) -> list[dict]
    def get_snapshot(snapshot_id) -> dict
    def get_latest_snapshot(employer_id) -> dict | None
    def delete_snapshot(snapshot_id) -> bool

    # Exports
    def upload_export(employer_id, file_path, metadata) -> dict
    def get_exports(employer_id) -> list[dict]
    def download_export(export_id, save_path) -> str

    # Triggers
    def get_triggers() -> list[dict]
    def create_trigger(data) -> dict
    def update_trigger(id, data) -> dict
    def delete_trigger(id) -> bool
    def toggle_trigger(id) -> dict
    def exclude_employer(trigger_id, employer_id, exclude) -> dict

    # Trigger-Runs
    def log_trigger_run(data) -> dict
    def get_trigger_runs(**filters) -> dict

    # SMTP
    def get_smtp_config() -> dict
    def update_smtp_config(data) -> dict
    def get_smtp_config_decrypted() -> dict
```

---

## Extrahierte Module (bereits vorbereitet)

Unter `Fusion/extrahierte_module/hr/` liegen fertig extrahierte Python-Module aus app.py:

```
hr/
├── __init__.py              # Modul-Dokumentation
├── constants.py             # SCS_HEADERS, TRIGGER_EVENTS, CONDITION_OPERATORS, ACTION_TYPES
├── helpers.py               # get_from_path, getv, get_safe_employer_name, parse_date,
│                            # format_date_for_display, json_hash, flatten_record, person_key
├── providers/
│   ├── __init__.py          # ProviderFactory + PROVIDER_MAP
│   ├── base.py              # BaseProvider (ABC)
│   ├── hrworks.py           # HRworksProvider
│   ├── personio.py          # PersonioProvider
│   └── sagehr.py            # SageHrProvider (Mock)
└── services/
    ├── __init__.py
    ├── sync_service.py      # SyncService
    ├── delta_service.py     # DeltaService
    ├── export_service.py    # ExportService (map_to_scs_schema, generate_standard_export)
    ├── snapshot_service.py  # SnapshotService (compare_snapshots, get_history)
    ├── trigger_service.py   # TriggerEngine, EmailAction, APIAction
    └── stats_service.py     # StatsService (Standard + Langzeit)
```

Diese Module enthalten die 1:1-portierte Geschäftslogik. Sie müssen:
- In die ATLAS-Projektstruktur integriert werden
- Import-Pfade angepasst werden (von `hr.` auf den ATLAS-Modul-Pfad)
- JSON-Datei-Zugriffe durch API-Client-Calls ersetzt werden

---

## Kern-Datenfluss: Delta-Export (wichtigster Prozess)

```
1. Nutzer klickt "Delta-Export" in ATLAS
   │
   ├── 2. QThread startet (Non-blocking UI)
   │      │
   │      ├── 3. hr_api_client.get_credentials(employer_id)
   │      │      └── GET /hr/employers/{id}/credentials → PHP entschlüsselt AES-256-GCM
   │      │
   │      ├── 4. ProviderFactory.create(provider_key, credentials)
   │      │      └── Provider.list_employees() → HTTPS an Personio/HRworks direkt
   │      │
   │      ├── 5. hr_api_client.get_latest_snapshot(employer_id)
   │      │      └── GET /hr/employers/{id}/snapshots/latest → MySQL
   │      │
   │      ├── 6. delta_service.calculate_diff(current, previous)
   │      │      └── Lokal: Hash-Vergleich → added/changed/removed
   │      │
   │      ├── 7. export_service.generate_scs_excel(diff, employer)
   │      │      └── Lokal: openpyxl → XLSX in temporäres Verzeichnis
   │      │
   │      ├── 8. hr_api_client.save_snapshot(employer_id, current_hashes)
   │      │      └── POST /hr/snapshots → MySQL
   │      │
   │      ├── 9. hr_api_client.upload_export(employer_id, xlsx_bytes)
   │      │      └── POST /hr/exports → Webspace + MySQL
   │      │
   │      ├── 10. trigger_service.evaluate_and_execute(employer, diff, current)
   │      │       ├── E-Mail: smtplib direkt vom Desktop
   │      │       └── API: requests direkt vom Desktop
   │      │
   │      └── 11. hr_api_client.log_trigger_runs(results)
   │             └── POST /hr/trigger-runs → MySQL
   │
   └── 12. UI aktualisiert (Signal → Slot)
```

---

## SCS-Header (Festes Export-Format)

Die Export-Spalten sind fest definiert und DÜRFEN NICHT dynamisch generiert werden:

```python
SCS_HEADERS = [
    "Name", "Vorname", "Geschlecht", "Titel", "Geburtsdatum",
    "Strasse", "Hausnummer", "PLZ", "Ort", "Land", "Kommentar",
    "Email", "Telefon", "Personalnummer", "Position", "Firmeneintritt",
    "Bruttogehalt", "VWL", "geldwerterVorteil", "SteuerfreibetragJahr", "SteuerfreibetragMonat",
    "SV_Brutto", "Steuerklasse", "Religion", "Kinder", "Abteilung", "Arbeitsplatz", "Arbeitgeber",
    "Status"
]
```

---

## Trigger-System

### Events
- `employee_added` – Neuer Mitarbeiter
- `employee_removed` – Mitarbeiter entfernt
- `employee_changed` – Daten geändert

### Operatoren
- `changed` – Beliebige Änderung
- `changed_to` – Neuer Wert ist X
- `changed_from` – Alter Wert war X
- `changed_from_to` – Von X nach Y
- `is_empty` – Feld jetzt leer
- `is_not_empty` – Feld jetzt nicht leer
- `contains` – Neuer Wert enthält Substring

### Aktionstypen
- `email` – SMTP-E-Mail mit Mustache-Templates
- `api` – HTTP-Request (GET/POST/PUT/PATCH/DELETE) mit Auth (Bearer/Basic/API-Key)

### Template-Variablen
- SCS-Felder: `{{Name}}`, `{{Vorname}}`, `{{Email}}`, etc.
- Meta: `{{_changedField}}`, `{{_oldValue}}`, `{{_newValue}}`
- Kontext: `{{_employerName}}`, `{{_employerId}}`, `{{_timestamp}}`
- Iteration: `{{#_employees}}...{{/_employees}}`

---

## Was NICHT übernommen wird

| Komponente | Grund | Ersatz |
|-----------|-------|--------|
| Flask-App | Desktop-App braucht keinen Webserver | PySide6 |
| Jinja2-Templates (18 Stück) | Web-UI | PySide6-Views |
| Flask-Sessions | Desktop-App | JWT aus ATLAS |
| users.json | Eigene Benutzerverwaltung | ATLAS-Auth-System |
| CSRF-Schutz | Kein Web-Formular | Entfällt |
| Rate-Limiter | PHP-Backend hat eigenes | PHP-seitig |
| Waitress/Werkzeug | Kein Webserver | Entfällt |
| updater.py | Auto-Update | ATLAS hat eigenes Update |
| JSON-Datei-Persistenz | employers.json, triggers.json, etc. | MySQL via PHP-API |
| CSS/Tokens | Web-Design | QSS-Styles in ATLAS |

---

## Implementierungs-Phasen

### Phase 1: Datenbankaufbau (PHP/MySQL)
1. MySQL-Tabellen anlegen (9 Tabellen, siehe Schema oben)
2. Permissions im ATLAS-Auth-System eintragen (hr.view, hr.sync, hr.export, hr.triggers, hr.admin)
3. PHP-Endpoints implementieren (alle unter /hr/*)
4. PHP-Endpoints testen

### Phase 2: Desktop-Module (Python)
1. Extrahierte Module in ATLAS-Projektstruktur einbinden
2. Dependencies hinzufügen (openpyxl, chevron)
3. HRApiClient implementieren (basierend auf ATLAS BaseApiClient)
4. Provider-Klassen testen (HRworks + Personio mit echten Credentials)
5. Services integrieren (Sync, Delta, Export, Snapshot, Trigger, Stats)

### Phase 3: UI (PySide6)
1. Sidebar-Eintrag "HR" hinzufügen
2. Arbeitgeber-Übersicht
3. Mitarbeiter-Dashboard mit Filter und Detail
4. Export-Bereich (Standard + Delta-SCS)
5. Snapshot-Vergleich
6. Trigger-Verwaltung (nur Master)
7. Statistiken mit Charts

### Phase 4: Datenmigration (einmalig)
1. employers.json → hr_employers + hr_provider_credentials
2. _snapshots/*.json → hr_snapshots + hr_snapshot_employees
3. data/triggers.json → hr_triggers + hr_smtp_config
4. data/trigger_log.json → hr_trigger_runs

### Phase 5: Test & Validierung
### Phase 6: Abschluss

Phase 1 und 2 können teilweise parallel laufen.

---

## Provider-spezifische Details

### HRworks API v2
- **Auth:** `POST /v2/authentication` mit `{"accessKey": "...", "secretAccessKey": "..."}`
- **Host Prod:** `https://api.hrworks.de`
- **Host Demo:** `https://api.demo-hrworks.de`
- **Mitarbeiter:** `GET /v2/persons/master-data` (paginiert via `Link`-Header mit `rel="next"`)
- **Detail:** `GET /v2/persons/master-data/{id}` (Fallback: Suche in Gesamtliste)

### Personio API v1
- **Auth:** `POST /v1/auth` mit `{"client_id": "...", "client_secret": "..."}`
- **Host:** `https://api.personio.de`
- **Mitarbeiter:** `GET /v1/company/employees`
- **Detail:** `GET /v1/company/employees/{id}`
- **Besonderheiten:** Dynamische Felder (`dynamic_XXXXX`), Label-basierte Daten-Extraktion

### SageHR
- Mock-Implementierung, keine echte API

---

## Threading (PySide6)

ALLE API-Calls und Provider-Calls MÜSSEN in Worker-Threads laufen:

```python
class HRWorker(QRunnable):
    class Signals(QObject):
        finished = Signal(dict)
        error = Signal(str)
        progress = Signal(str)

    def __init__(self, task_fn, *args):
        super().__init__()
        self.task_fn = task_fn
        self.args = args
        self.signals = self.Signals()

    def run(self):
        try:
            result = self.task_fn(*self.args)
            self.signals.finished.emit(result)
        except Exception as e:
            self.signals.error.emit(str(e))
```

---

## Coding-Regeln

1. **Deutsche Docstrings** – Google-Style, alle öffentlichen Funktionen/Klassen
2. **Type Hints** – Überall verwenden
3. **Keine hardcodierten Strings in UI** – Zentrale i18n-Datei
4. **CSS-Module / QSS** – Keine Inline-Styles
5. **Provider-Pattern beachten** – `_getv()` und `_get_from_path()` für robuste Datenextraktion
6. **SCS_HEADERS sind fix** – Nicht dynamisch generieren
7. **Fehlerbehandlung** – Try/Except um alle kritischen Operationen
8. **Logging** – ATLAS-Logger verwenden
9. **Secrets** – Nie im Klartext loggen oder speichern
10. **Non-blocking UI** – QThread/ThreadPool für alle I/O-Operationen

---

## Quelldateien-Referenz

Die vollständige Quell-Implementierung liegt in:
- `ACENCIA_API_Hub/acencia_hub/app.py` (~5326 Zeilen) – Monolithische Quelldatei
- `Fusion/extrahierte_module/hr/` – Bereits extrahierte Module

**Erstellt:** 04.03.2026
**Zweck:** Vollständiger Kontext für die ATLAS-Integration des HR-Moduls
