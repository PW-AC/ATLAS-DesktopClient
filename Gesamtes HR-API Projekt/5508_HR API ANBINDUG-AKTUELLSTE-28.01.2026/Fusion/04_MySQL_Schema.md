# 04 – MySQL-Schema für HR-Modul

## Übersicht

Alle Tabellen verwenden den Prefix `hr_` und werden in der bestehenden ATLAS-MySQL-Datenbank auf Strato angelegt.

---

## Entity-Relationship-Diagramm

```
hr_employers (1)──────(N) hr_provider_credentials
     │
     ├──(N) hr_employees
     │        │
     │        └──(N) hr_snapshot_employees ──(N)── hr_snapshots
     │
     ├──(N) hr_snapshots
     │        │
     │        ├──(0..1) hr_exports (snapshot_from)
     │        └──(0..1) hr_exports (snapshot_to)
     │
     ├──(N) hr_exports
     │
     └──(N) hr_trigger_runs
              │
              └──(N)── hr_triggers

hr_smtp_config (Singleton, max 1 Zeile)
```

---

## Tabellen

### hr_employers
Arbeitgeber/Mandanten mit Provider-Konfiguration.

```sql
CREATE TABLE hr_employers (
    id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    name            VARCHAR(255) NOT NULL,
    provider_key    ENUM('personio', 'hrworks', 'sagehr') NOT NULL,
    status          ENUM('active', 'inactive', 'deleted') DEFAULT 'active',
    address_json    JSON COMMENT 'Adressdaten: {street, zip_code, city, country}',
    settings_json   JSON COMMENT 'Zusätzliche Einstellungen (E-Mail, Telefon etc.)',
    last_sync_at    DATETIME COMMENT 'Zeitpunkt der letzten Synchronisierung',
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

**Migration von HR-Hub:** `employers.json` → je ein INSERT pro Arbeitgeber.

---

### hr_provider_credentials
Verschlüsselte API-Zugangsdaten. Eine Zeile pro Arbeitgeber.

```sql
CREATE TABLE hr_provider_credentials (
    id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    employer_id     INT UNSIGNED NOT NULL,
    encrypted_blob  VARBINARY(2048) NOT NULL COMMENT 'AES-256-GCM verschlüsselte Credentials',
    iv              VARBINARY(16) NOT NULL COMMENT 'Initialisierungsvektor',
    auth_tag        VARBINARY(16) NOT NULL COMMENT 'Authentifizierungs-Tag',
    key_version     INT UNSIGNED DEFAULT 1 COMMENT 'Version des Verschlüsselungsschlüssels',
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (employer_id) REFERENCES hr_employers(id) ON DELETE CASCADE,
    UNIQUE KEY uk_employer (employer_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

**Verschlüsseltes Blob-Format (JSON vor Verschlüsselung):**
```json
{
    "access_key": "papi-...",
    "secret_key": "...",
    "is_demo": false
}
```

**Wichtig:** PHP ver-/entschlüsselt. Desktop bekommt Klartext nur via HTTPS.

---

### hr_employees
Normalisierte Mitarbeiterdaten, synchronisiert vom Desktop.

```sql
CREATE TABLE hr_employees (
    id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    employer_id     INT UNSIGNED NOT NULL,
    provider_pid    VARCHAR(100) NOT NULL COMMENT 'ID im Quellsystem (Personio/HRworks)',
    first_name      VARCHAR(100),
    last_name       VARCHAR(100),
    email           VARCHAR(255),
    department      VARCHAR(255),
    position        VARCHAR(255),
    status          ENUM('active', 'inactive') DEFAULT 'active',
    join_date       DATE,
    leave_date      DATE,
    details_json    JSON COMMENT 'Vollständige normalisierte Daten inkl. Details-Gruppen',
    data_hash       CHAR(64) COMMENT 'SHA256 für Änderungserkennung',
    last_synced_at  DATETIME,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (employer_id) REFERENCES hr_employers(id) ON DELETE CASCADE,
    UNIQUE KEY uk_employer_pid (employer_id, provider_pid),
    INDEX idx_employer_status (employer_id, status),
    INDEX idx_data_hash (data_hash)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

**Mapping von HR-Hub-Feldern:**
| HR-Hub-Feld | MySQL-Spalte |
|-------------|-------------|
| personId / id | provider_pid |
| firstName | first_name |
| lastName | last_name |
| email | email |
| department | department |
| position | position |
| isActive → active/inactive | status |
| joinDate | join_date |
| leaveDate | leave_date |
| (gesamtes dict) | details_json |
| _json_hash(flatten_record(dict)) | data_hash |

---

### hr_snapshots
Zeitpunktbezogene Momentaufnahmen aller Mitarbeiter.

```sql
CREATE TABLE hr_snapshots (
    id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    employer_id     INT UNSIGNED NOT NULL,
    snapshot_ts     DATETIME NOT NULL,
    employee_count  INT UNSIGNED DEFAULT 0,
    content_hash    CHAR(64) COMMENT 'Hash über alle Employee-Hashes für schnellen Vergleich',
    is_latest       TINYINT(1) DEFAULT 0 COMMENT 'Markiert den aktuellsten Snapshot',
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (employer_id) REFERENCES hr_employers(id) ON DELETE CASCADE,
    INDEX idx_employer_ts (employer_id, snapshot_ts DESC),
    INDEX idx_latest (employer_id, is_latest)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

**Migration von HR-Hub:** Jede Datei in `_snapshots/` → ein INSERT in `hr_snapshots`.

**Vor neuem Snapshot:** `UPDATE hr_snapshots SET is_latest = 0 WHERE employer_id = ? AND is_latest = 1`

---

### hr_snapshot_employees
Mitarbeiter-Stand zum Zeitpunkt eines Snapshots.

```sql
CREATE TABLE hr_snapshot_employees (
    snapshot_id     INT UNSIGNED NOT NULL,
    provider_pid    VARCHAR(100) NOT NULL,
    data_hash       CHAR(64) NOT NULL,
    core_json       JSON NOT NULL COMMENT 'SCS-Schema-Daten für Export',
    flat_json       JSON COMMENT 'Geflattete Daten für Diff-Anzeige',
    dates_json      JSON COMMENT 'Join/Leave-Daten für Langzeit-Statistik',
    PRIMARY KEY (snapshot_id, provider_pid),
    FOREIGN KEY (snapshot_id) REFERENCES hr_snapshots(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

**Mapping von HR-Hub Snapshot-Format:**
```json
// HR-Hub Format (JSON-Datei, pro PID):
{
    "hash": "a1b2c3...",          // → data_hash
    "core": { "Name": "..." },    // → core_json
    "flat": { "firstName": "..." },// → flat_json
    "dates": { "join": "...", "leave": "..." } // → dates_json
}
```

---

### hr_exports
Metadaten und Dateipfade generierter Exporte.

```sql
CREATE TABLE hr_exports (
    id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    employer_id     INT UNSIGNED NOT NULL,
    export_type     ENUM('standard', 'delta_scs') NOT NULL,
    filename        VARCHAR(255) NOT NULL,
    file_path       VARCHAR(500) COMMENT 'Relativer Pfad auf Webspace',
    file_size       INT UNSIGNED,
    snapshot_from   INT UNSIGNED COMMENT 'Basis-Snapshot (NULL bei Standard)',
    snapshot_to     INT UNSIGNED COMMENT 'Ziel-Snapshot',
    diff_summary    JSON COMMENT '{"added": 5, "changed": 3, "removed": 1}',
    created_by      VARCHAR(100) COMMENT 'ATLAS-Benutzername',
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (employer_id) REFERENCES hr_employers(id) ON DELETE CASCADE,
    FOREIGN KEY (snapshot_from) REFERENCES hr_snapshots(id) ON DELETE SET NULL,
    FOREIGN KEY (snapshot_to) REFERENCES hr_snapshots(id) ON DELETE SET NULL,
    INDEX idx_employer_created (employer_id, created_at DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

**Dateispeicherung auf Webspace:** `/files/hr/exports/<filename>.xlsx`

---

### hr_triggers
Trigger-Definitionen.

```sql
CREATE TABLE hr_triggers (
    id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    name            VARCHAR(255) NOT NULL,
    event           ENUM('employee_added', 'employee_removed', 'employee_changed') NOT NULL,
    conditions_json JSON COMMENT '[{field, operator, from_value?, to_value?}]',
    condition_logic ENUM('AND', 'OR') DEFAULT 'AND',
    action_type     ENUM('email', 'api') NOT NULL,
    action_config   JSON NOT NULL COMMENT 'Aktionskonfiguration (recipients/subject/body oder url/method/headers)',
    enabled         TINYINT(1) DEFAULT 1,
    excluded_employers JSON COMMENT '[employer_id, ...]',
    statistics_json JSON COMMENT '{total_executions, last_execution, success_count, error_count}',
    created_by      VARCHAR(100),
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_enabled_event (enabled, event)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

**Migration von HR-Hub:** `data/triggers.json` → `triggers`-Array → je ein INSERT.

---

### hr_trigger_runs
Ausführungsprotokoll für Trigger.

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
    request_json    JSON COMMENT 'Gesendete Daten (ohne Secrets)',
    response_json   JSON COMMENT 'Antwort oder Fehlermeldung',
    can_retry       TINYINT(1) DEFAULT 0,
    retry_of        INT UNSIGNED COMMENT 'Original-Run-ID bei Wiederholung',
    executed_by     VARCHAR(100) DEFAULT 'system',
    executed_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (trigger_id) REFERENCES hr_triggers(id) ON DELETE CASCADE,
    FOREIGN KEY (employer_id) REFERENCES hr_employers(id) ON DELETE CASCADE,
    INDEX idx_employer_executed (employer_id, executed_at DESC),
    INDEX idx_trigger_status (trigger_id, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

---

### hr_smtp_config
Globale SMTP-Einstellungen (Singleton-Tabelle, max. 1 Zeile).

```sql
CREATE TABLE hr_smtp_config (
    id              INT UNSIGNED PRIMARY KEY DEFAULT 1,
    host            VARCHAR(255),
    port            INT UNSIGNED DEFAULT 587,
    username_enc    VARBINARY(512) COMMENT 'AES-256-GCM verschlüsselt',
    password_enc    VARBINARY(512) COMMENT 'AES-256-GCM verschlüsselt',
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

## Speicherabschätzung

| Tabelle | Zeilen (geschätzt pro Mandant) | Größe |
|---------|-------------------------------|-------|
| hr_employers | 5-20 | Minimal |
| hr_provider_credentials | 5-20 | Minimal |
| hr_employees | 50-500 pro AG | ~1 KB/Zeile |
| hr_snapshots | 1-2 pro Woche | Minimal |
| hr_snapshot_employees | 50-500 pro Snapshot | ~2 KB/Zeile |
| hr_exports | 1-2 pro Woche | Minimal (Dateien auf Webspace) |
| hr_triggers | 5-20 | Minimal |
| hr_trigger_runs | Wächst über Zeit | ~1 KB/Zeile, Limit 10.000 |

**Gesamtschätzung:** < 50 MB für 10 Mandanten mit je 200 Mitarbeitern und 1 Jahr Historie.

---

**Erstellt:** 19.02.2026
