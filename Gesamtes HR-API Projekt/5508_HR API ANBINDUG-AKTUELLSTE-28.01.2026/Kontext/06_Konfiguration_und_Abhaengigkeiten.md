# 06 - Konfiguration und Abhängigkeiten

## Konfigurations-Dateien

### 1. requirements.txt

**Ort:** `ACENCIA_API_Hub/requirements.txt`

| Paket | Version | Zweck |
|-------|---------|-------|
| Flask | 3.0.3 | Web-Framework |
| Werkzeug | 3.0.3 | WSGI Utilities, Passwort-Hashing |
| Jinja2 | 3.1.4 | Template Engine |
| itsdangerous | 2.2.0 | Session-Signierung |
| click | 8.1.7 | CLI-Utilities (Flask-Dependency) |
| blinker | 1.8.2 | Signal-Utilities (Flask-Dependency) |
| openpyxl | 3.1.3 | Excel-Export |
| requests | 2.32.3 | HTTP-Client |
| waitress | 3.0.0 | WSGI-Produktionsserver |
| Flask-Limiter | 3.5.0 | Rate-Limiting |
| cryptography | 42.0.0 | Credential-Verschlüsselung |
| Flask-WTF | 1.2.1 | CSRF-Schutz |
| pytest | 8.0.0 | Test-Framework |

**Evidenz:** `requirements.txt`

---

### 2. users.json

**Ort:** `acencia_hub/data/users.json`

**Struktur:**
```json
[
    {
        "username": "admin",
        "password_hash": "scrypt:32768:8:1$...",
        "kuerzel": "ADM",
        "is_master": true,
        "color": "cyan",
        "theme": "light",
        "allowed_employers": []
    }
]
```

| Feld | Typ | Beschreibung |
|------|-----|--------------|
| `username` | String | Login-Name (eindeutig) |
| `password_hash` | String | Werkzeug scrypt-Hash |
| `kuerzel` | String | Log-Kürzel (max. 4 Zeichen) |
| `is_master` | Boolean | Master-Rechte |
| `color` | String | Log-Farbe (red, green, blue, cyan, etc.) |
| `theme` | String | "light" oder "dark" |
| `allowed_employers` | Array | IDs erlaubter Arbeitgeber (leer = alle für Master) |

**Sicherheitshinweis:** NICHT committen – enthält Passwort-Hashes.

**Evidenz:** `docs/CONFIGURATION.md:9-35`

---

### 3. secrets.json

**Ort:** `acencia_hub/data/secrets.json`

**Struktur:**
```json
{
    "github_pat": "ENC:gAAAAABh..." 
}
```

| Feld | Typ | Beschreibung |
|------|-----|--------------|
| `github_pat` | String | GitHub Personal Access Token (verschlüsselt) |

**Sicherheitshinweis:** NIEMALS committen – enthält sensible Tokens.

**Evidenz:** `docs/CONFIGURATION.md:37-51`

---

### 4. triggers.json (NEU)

**Ort:** `acencia_hub/data/triggers.json`

**Struktur:**
```json
{
    "smtp_config": {
        "host": "smtp.example.com",
        "port": 587,
        "username": "user@example.com",
        "password": "ENC:gAAAAABh...",
        "from_email": "noreply@example.com",
        "use_tls": true
    },
    "triggers": [
        {
            "id": "uuid",
            "name": "Mitarbeiter inaktiv",
            "enabled": true,
            "trigger_type": "employee",
            "event": "employee_changed",
            "conditions": [
                {"field": "Status", "operator": "changed_from_to", "from_value": "Aktiv", "to_value": "Inaktiv"}
            ],
            "condition_logic": "AND",
            "action": {
                "type": "email",
                "config": { ... }
            },
            "excluded_employers": [],
            "statistics": { ... }
        }
    ]
}
```

| Sektion | Beschreibung |
|---------|--------------|
| `smtp_config` | SMTP-Server-Einstellungen für E-Mail-Versand |
| `triggers` | Array aller konfigurierten Trigger |

**Sicherheitshinweis:** NICHT committen – enthält SMTP-Passwort und API-Tokens (verschlüsselt).

**Evidenz:** `app.py:624-973`, `docs/TRIGGERS.md:255-304`

---

### 5. trigger_log.json (NEU)

**Ort:** `acencia_hub/data/trigger_log.json`

**Struktur:**
```json
{
    "executions": [
        {
            "id": "uuid",
            "trigger_id": "trigger-uuid",
            "trigger_name": "Trigger-Name",
            "event": "employee_changed",
            "employer_id": "employer-uuid",
            "employer_name": "Firma XY",
            "executed_at": "2026-01-28T10:30:00Z",
            "executed_by": "admin",
            "affected_employees": [...],
            "action_type": "email",
            "action_details": {...},
            "status": "success",
            "error_message": null,
            "can_retry": true
        }
    ]
}
```

| Feld | Beschreibung |
|------|--------------|
| `executions` | Array aller Trigger-Ausführungen |

**Evidenz:** `app.py:975-1160`, `docs/TRIGGERS.md:105-125`

---

### 6. employers.json

**Ort:** `acencia_hub/employers.json`

**Struktur:**
```json
[
    {
        "id": "uuid-1234",
        "name": "Beispiel GmbH",
        "provider_key": "personio",
        "access_key": "ENC:gAAAAABh...",
        "secret_key": "ENC:gAAAAABh...",
        "use_demo": false,
        "address": {
            "street": "Musterstraße 1",
            "zip_code": "12345",
            "city": "Musterstadt",
            "country": "Deutschland"
        },
        "email": "hr@beispiel.de",
        "phone": "+49 123 456789",
        "fax": "",
        "comment": "Zusätzliche Infos"
    }
]
```

**Provider-spezifische Felder:**

| Provider | Felder |
|----------|--------|
| `personio` | `access_key` (client_id), `secret_key` (client_secret) |
| `hrworks` | `access_key`, `secret_key`, `use_demo` |
| `sagehr` | `access_key`, `slug` |

**Sicherheitshinweis:** NICHT committen – enthält API-Credentials.

**Evidenz:** `docs/CONFIGURATION.md:53-143`

---

## Umgebungsvariablen

| Variable | Beschreibung | Erforderlich | Default |
|----------|--------------|--------------|---------|
| `ACENCIA_SECRET_KEY` | Flask Session Secret Key | Ja (Produktion) | Zufällig generiert |
| `ACENCIA_MASTER_KEY` | Fernet-Verschlüsselungsschlüssel | Ja (Produktion) | - |
| `FLASK_DEBUG` | Debug-Modus aktivieren | Nein | false |
| `HTTPS_ENABLED` | Secure Cookie aktivieren | Nein | false |
| `ANONYMIZE_PII_LOGS` | PII-Anonymisierung in Logs | Nein | true |

**Evidenz:** `Sicherheit/Umsetzung/00_INDEX.md:63-71`, `app.py:2991-3045`

---

## Server-Konfiguration

### Port und Host

**Ort:** `run.py:57-58`

```python
host = '0.0.0.0'  # Alle Interfaces
port = 5001
```

### Flask-Konfiguration

**Ort:** `app.py:2991-3045`

```python
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=8)
app.config['SESSION_REFRESH_EACH_REQUEST'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('HTTPS_ENABLED', 'false').lower() == 'true'
```

---

## Dateipfade

### Relative Pfade (zu app.py)

| Pfad | Beschreibung |
|------|--------------|
| `./employers.json` | Arbeitgeber-Konfiguration |
| `./data/users.json` | Benutzerdatenbank |
| `./data/secrets.json` | Geheimnisse |
| `./data/triggers.json` | Trigger-Konfiguration + SMTP |
| `./data/trigger_log.json` | Trigger-Ausführungsprotokoll |
| `./data/force_logout.txt` | Forced-Logout-Timestamp |
| `./_snapshots/` | Snapshot-Dateien |
| `./_history/` | API-Response-Backup |
| `./exports/` | Generierte Exporte |
| `./static/css/` | Stylesheets |
| `./templates/` | Jinja2-Templates |

### Relative Pfade (zu Projekt-Root)

| Pfad | Beschreibung |
|------|--------------|
| `./server.log` | Anwendungs-Log |
| `./audit.log` | Audit-Trail |
| `./venv/` | Virtuelle Umgebung |

**Evidenz:** `app.py:119-121`, `app.py:1911-1914`

---

## Externe Abhängigkeiten

### HR-Provider APIs

| Provider | Produktions-URL | Demo-URL |
|----------|----------------|----------|
| Personio | `https://api.personio.de/v1` | - |
| HRworks | `https://api.hrworks.de/v2` | `https://api.demo-hrworks.de/v2` |
| SageHR | Mock (keine echte API) | - |

**Evidenz:** `app.py:1896-1897`, `app.py:2191`

### GitHub (Auto-Update)

| Aspekt | Wert |
|--------|------|
| Repository | `paulweimert2006-commits/JULES_WEB4` |
| Branch | `main` |
| Methode | ZIP-Download über GitHub API |
| Authentifizierung | Personal Access Token |

**Evidenz:** `updater.py:12`

### CDN (Frontend)

| Ressource | URL | Verwendung |
|-----------|-----|------------|
| Google Fonts | `https://fonts.googleapis.com` | Open Sans, Tenor Sans |
| Chart.js | `https://cdn.jsdelivr.net/npm/chart.js` | Statistik-Diagramme |

**Evidenz:** `base.html:15-17`, `statistics.html`

---

## Update-Ausschlüsse

Folgende Dateien/Ordner werden bei Auto-Updates NICHT überschrieben:

```python
EXCLUSIONS = [
    ".git",
    "venv",
    ".idea",
    "__pycache__",
    "_snapshots",      # Benutzerdaten
    "_history",        # Benutzerdaten
    "exports",         # Benutzerdaten
    "acencia_hub/data", # Konfiguration
    "acencia_hub/updater.py",
    "start.bat",
]
```

**Evidenz:** `updater.py:19-30`

---

## Logging-Konfiguration

### server.log

| Aspekt | Wert |
|--------|------|
| Handler | RotatingFileHandler |
| Max Size | 10 MB |
| Backup Count | 5 |
| Format | `[DD/Mon/YYYY HH:MM:SS] ("KÜRZ" - Nachricht)` |
| PII-Anonymisierung | Aktiviert (default) |

**Evidenz:** `app.py:130-150`, `app.py:199-260`

### audit.log

| Aspekt | Wert |
|--------|------|
| Handler | RotatingFileHandler |
| Max Size | 10 MB |
| Backup Count | 10 |
| Format | `YYYY-MM-DD HH:MM:SS - USER=... ACTION=... TARGET=...` |

**Evidenz:** `app.py:151-197`

---

## Rate-Limiting

| Route | Limit |
|-------|-------|
| `/login` (POST) | 5 pro Minute |
| Global (Default) | 200 pro Tag, 50 pro Stunde |

**Evidenz:** `app.py:3035-3045`

---

## Passwort-Policy

| Anforderung | Wert |
|-------------|------|
| Mindestlänge | 8 Zeichen |
| Großbuchstaben | Mindestens 1 |
| Kleinbuchstaben | Mindestens 1 |
| Ziffern | Mindestens 1 |

**Evidenz:** `app.py:3236-3270`

---

## Account-Lockout

| Aspekt | Wert |
|--------|------|
| Max. Fehlversuche | 5 |
| Sperrzeit | 15 Minuten |

**Evidenz:** `app.py:3271-3330`

---

**Letzte Aktualisierung:** 29.01.2026
