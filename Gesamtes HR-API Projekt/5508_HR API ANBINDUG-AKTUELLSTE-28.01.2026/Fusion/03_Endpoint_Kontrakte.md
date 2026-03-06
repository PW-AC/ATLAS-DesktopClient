# 03 – Endpoint-Kontrakte: PHP-Backend (Strato)

## Grundprinzip

Die PHP-Endpoints auf Strato sind **reine Persistenz-Layer**. Sie:
- Prüfen JWT + Permissions (wie bestehend)
- Speichern/Lesen Daten in MySQL
- Verwalten Dateien auf dem Webspace
- Enthalten **keine** HR-Provider-Logik

Die gesamte Geschäftslogik (Provider-Calls, Delta-Berechnung, Trigger-Ausführung) bleibt im Desktop.

---

## Authentifizierung

Alle Endpoints erfordern:
```
Authorization: Bearer <JWT>
```

Der JWT kommt aus dem bestehenden ATLAS-Auth-System (`POST /auth/login`).

---

## Permissions

| Permission | Beschreibung | Wer |
|-----------|-------------|-----|
| `hr.view` | Arbeitgeber/Mitarbeiter/Snapshots lesen | Alle HR-Nutzer |
| `hr.sync` | Daten synchronisieren | HR-Manager |
| `hr.export` | Exporte generieren/herunterladen | HR-Manager |
| `hr.triggers` | Trigger verwalten | Master |
| `hr.admin` | Arbeitgeber anlegen/löschen/Credentials | Master |

---

## 1. Arbeitgeber

### POST /hr/employers
**Permission:** `hr.admin`
```json
// Request
{
    "name": "Schulte Schlagbaum AG",
    "provider_key": "personio",
    "address": {
        "street": "Musterstr. 1",
        "zip_code": "42699",
        "city": "Solingen",
        "country": "D"
    },
    "settings": {}
}

// Response 201
{
    "id": 1,
    "name": "Schulte Schlagbaum AG",
    "provider_key": "personio",
    "status": "active",
    "created_at": "2026-02-19T10:30:00Z"
}
```

### GET /hr/employers
**Permission:** `hr.view`
```json
// Response 200
[
    {
        "id": 1,
        "name": "Schulte Schlagbaum AG",
        "provider_key": "personio",
        "status": "active",
        "last_sync_at": "2026-02-19T10:35:00Z",
        "employee_count": 45
    }
]
```

### GET /hr/employers/{id}
**Permission:** `hr.view`

### PUT /hr/employers/{id}
**Permission:** `hr.admin`

### DELETE /hr/employers/{id}
**Permission:** `hr.admin`
Soft-Delete: setzt `status = 'deleted'`

---

## 2. Provider-Credentials

### POST /hr/employers/{id}/credentials
**Permission:** `hr.admin`
```json
// Request
{
    "access_key": "papi-...",
    "secret_key": "...",
    "is_demo": false
}

// Response 201
{
    "success": true,
    "key_version": 1,
    "created_at": "2026-02-19T10:31:00Z"
}
```
PHP verschlüsselt mit AES-256-GCM bevor es in `hr_provider_credentials` landet.

### GET /hr/employers/{id}/credentials
**Permission:** `hr.sync`
```json
// Response 200
{
    "access_key": "papi-...",
    "secret_key": "...",
    "is_demo": false,
    "key_version": 1
}
```
PHP entschlüsselt aus der DB. **Nur über HTTPS!**

### GET /hr/employers/{id}/credentials/status
**Permission:** `hr.view`
```json
// Response 200
{
    "has_credentials": true,
    "key_version": 1,
    "updated_at": "2026-02-19T10:31:00Z"
}
```
Gibt **keine** Klartext-Credentials zurück.

---

## 3. Mitarbeiter

### POST /hr/employees/bulk
**Permission:** `hr.sync`
```json
// Request
{
    "employer_id": 1,
    "employees": [
        {
            "provider_pid": "12345",
            "first_name": "Max",
            "last_name": "Mustermann",
            "email": "max@firma.de",
            "department": "IT",
            "position": "Entwickler",
            "status": "active",
            "join_date": "2020-01-15",
            "leave_date": null,
            "details_json": { "...normalisierte Details..." },
            "data_hash": "a1b2c3d4..."
        }
    ]
}

// Response 200
{
    "inserted": 5,
    "updated": 38,
    "unchanged": 2,
    "total": 45
}
```
Verwendet `INSERT ... ON DUPLICATE KEY UPDATE` auf `(employer_id, provider_pid)`.

### GET /hr/employers/{id}/employees
**Permission:** `hr.view`
```json
// Query: ?status=active&search=Muster&page=1&limit=50

// Response 200
{
    "data": [
        {
            "id": 1,
            "provider_pid": "12345",
            "first_name": "Max",
            "last_name": "Mustermann",
            "department": "IT",
            "status": "active"
        }
    ],
    "pagination": {
        "page": 1,
        "limit": 50,
        "total": 45,
        "pages": 1
    }
}
```

### GET /hr/employers/{id}/employees/{employee_id}
**Permission:** `hr.view`
```json
// Response 200
{
    "id": 1,
    "provider_pid": "12345",
    "first_name": "Max",
    "last_name": "Mustermann",
    "details_json": { "...vollständige normalisierte Daten..." },
    "last_synced_at": "2026-02-19T10:35:00Z"
}
```

---

## 4. Snapshots

### POST /hr/snapshots
**Permission:** `hr.sync`
```json
// Request
{
    "employer_id": 1,
    "snapshot_data": {
        "12345": {
            "hash": "a1b2c3...",
            "core": { "Name": "Mustermann", "Vorname": "Max", ... },
            "flat": { "firstName": "Max", ... },
            "dates": { "join": "15.01.2020", "leave": null }
        }
    }
}

// Response 201
{
    "id": 42,
    "snapshot_ts": "2026-02-19T10:35:00Z",
    "employee_count": 45,
    "content_hash": "xyz..."
}
```

### GET /hr/employers/{id}/snapshots
**Permission:** `hr.view`
```json
// Response 200
[
    {
        "id": 42,
        "snapshot_ts": "2026-02-19T10:35:00Z",
        "employee_count": 45,
        "is_latest": true
    },
    {
        "id": 41,
        "snapshot_ts": "2026-02-18T09:00:00Z",
        "employee_count": 44,
        "is_latest": false
    }
]
```

### GET /hr/snapshots/{snapshot_id}
**Permission:** `hr.view`
```json
// Response 200
{
    "id": 42,
    "employer_id": 1,
    "snapshot_ts": "2026-02-19T10:35:00Z",
    "employee_count": 45,
    "data": {
        "12345": { "hash": "...", "core": {...}, "flat": {...}, "dates": {...} }
    }
}
```

### GET /hr/employers/{id}/snapshots/latest
**Permission:** `hr.view`
Gibt den Snapshot mit `is_latest = true` zurück.

### DELETE /hr/snapshots/{snapshot_id}
**Permission:** `hr.admin`

---

## 5. Exports

### POST /hr/exports
**Permission:** `hr.export`
```
Content-Type: multipart/form-data

Fields:
  - file: <xlsx-binary>
  - employer_id: 1
  - export_type: "delta_scs"
  - snapshot_from_id: 41
  - snapshot_to_id: 42
  - diff_summary: '{"added": 1, "changed": 3, "removed": 0}'

// Response 201
{
    "id": 15,
    "filename": "delta-SchulteSchlagbaum_AG-personio-20260219-103500.xlsx",
    "download_url": "/hr/exports/15/download",
    "created_at": "2026-02-19T10:35:00Z"
}
```

### GET /hr/employers/{id}/exports
**Permission:** `hr.view`
```json
// Response 200
[
    {
        "id": 15,
        "export_type": "delta_scs",
        "filename": "delta-SchulteSchlagbaum_AG-personio-20260219-103500.xlsx",
        "created_at": "2026-02-19T10:35:00Z",
        "diff_summary": { "added": 1, "changed": 3, "removed": 0 },
        "download_url": "/hr/exports/15/download"
    }
]
```

### GET /hr/exports/{export_id}/download
**Permission:** `hr.export`
```
Response: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
```

---

## 6. Trigger

### GET /hr/triggers
**Permission:** `hr.triggers`
```json
// Response 200
[
    {
        "id": 1,
        "name": "Austritt-Benachrichtigung",
        "event": "employee_changed",
        "conditions": [
            { "field": "Status", "operator": "changed_from_to", "from_value": "active", "to_value": "inactive" }
        ],
        "condition_logic": "AND",
        "action_type": "email",
        "action_config": {
            "recipients": ["hr@firma.de"],
            "subject": "{{Vorname}} {{Name}} ausgetreten",
            "body": "Der Mitarbeiter {{Vorname}} {{Name}} hat das Unternehmen verlassen."
        },
        "enabled": true,
        "excluded_employers": []
    }
]
```

### POST /hr/triggers
**Permission:** `hr.triggers`

### PUT /hr/triggers/{id}
**Permission:** `hr.triggers`

### PATCH /hr/triggers/{id}/toggle
**Permission:** `hr.triggers`
```json
// Response 200
{ "enabled": false }
```

### DELETE /hr/triggers/{id}
**Permission:** `hr.triggers`

### PATCH /hr/triggers/{id}/exclude-employer
**Permission:** `hr.triggers`
```json
// Request
{ "employer_id": 1, "exclude": true }
```

---

## 7. Trigger-Runs

### POST /hr/trigger-runs
**Permission:** `hr.sync`
```json
// Request
{
    "trigger_id": 1,
    "employer_id": 1,
    "employee_pid": "12345",
    "status": "success",
    "action_type": "email",
    "request_json": { "recipients": ["hr@firma.de"], "subject": "Max Mustermann ausgetreten" },
    "response_json": null
}

// Response 201
{ "id": 100, "executed_at": "2026-02-19T10:35:01Z" }
```

### GET /hr/trigger-runs
**Permission:** `hr.triggers`
```json
// Query: ?employer_id=1&trigger_id=&status=error&page=1&limit=50

// Response 200
{
    "data": [...],
    "pagination": { "page": 1, "limit": 50, "total": 23 }
}
```

---

## 8. SMTP-Konfiguration

### GET /hr/smtp-config
**Permission:** `hr.triggers`
```json
// Response 200
{
    "host": "smtp.firma.de",
    "port": 587,
    "username": "noreply@firma.de",
    "use_tls": true,
    "from_email": "noreply@firma.de",
    "from_name": "ACENCIA HR",
    "has_password": true
}
```
Passwort wird NIE im Klartext zurückgegeben.

### PUT /hr/smtp-config
**Permission:** `hr.triggers`
```json
// Request
{
    "host": "smtp.firma.de",
    "port": 587,
    "username": "noreply@firma.de",
    "password": "...",
    "use_tls": true,
    "from_email": "noreply@firma.de",
    "from_name": "ACENCIA HR"
}
```

### GET /hr/smtp-config/decrypted
**Permission:** `hr.triggers`
Gibt das Passwort im Klartext zurück (für Desktop-SMTP-Versand).

---

## Fehler-Responses (einheitlich)

```json
// 400 Bad Request
{ "error": "validation_error", "message": "...", "fields": { "name": "Pflichtfeld" } }

// 401 Unauthorized
{ "error": "unauthorized", "message": "Token ungültig oder abgelaufen" }

// 403 Forbidden
{ "error": "forbidden", "message": "Keine Berechtigung: hr.admin erforderlich" }

// 404 Not Found
{ "error": "not_found", "message": "Arbeitgeber nicht gefunden" }

// 500 Internal Server Error
{ "error": "internal_error", "message": "Unerwarteter Fehler" }
```

---

**Erstellt:** 19.02.2026
