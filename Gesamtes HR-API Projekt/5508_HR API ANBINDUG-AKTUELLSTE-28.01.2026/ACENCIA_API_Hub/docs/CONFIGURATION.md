# ACENCIA Hub - Konfigurations-Dokumentation

## Übersicht

ACENCIA Hub verwendet JSON-Dateien für Konfiguration und Datenpersistenz. Es gibt keine Umgebungsvariablen - alle Einstellungen werden über die Web-UI oder direkt in JSON-Dateien verwaltet.

## Konfigurations-Dateien

### 1. `acencia_hub/data/users.json`

Benutzerdatenbank mit Authentifizierungsinformationen.

```json
[
    {
        "username": "BENUTZERNAME",
        "password_hash": "scrypt:32768:8:1$...",
        "kuerzel": "KÜRZ",
        "is_master": true,
        "color": "red",
        "theme": "light"
    }
]
```

| Feld | Typ | Beschreibung |
|------|-----|-------------|
| `username` | string | Eindeutiger Benutzername (Login) |
| `password_hash` | string | Werkzeug scrypt Passwort-Hash |
| `kuerzel` | string | Kurzbezeichnung für Logs (max. 4 Zeichen) |
| `is_master` | boolean | Master-Benutzer hat erweiterte Rechte |
| `color` | string | Farbe für Log-Ausgaben (red, green, blue, cyan, etc.) |
| `theme` | string | Bevorzugtes Theme ("light" oder "dark") |

**Sicherheitshinweis**: Diese Datei enthält Passwort-Hashes. Nicht in Git committen!

### 2. `acencia_hub/data/secrets.json`

Geheimnisse und API-Tokens.

```json
{
    "github_pat": "ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
}
```

| Feld | Typ | Beschreibung |
|------|-----|-------------|
| `github_pat` | string | GitHub Personal Access Token für Auto-Updates |

**Sicherheitshinweis**: Diese Datei enthält sensible Tokens. Niemals committen!

### 3. `acencia_hub/data/employers.json`

Arbeitgeber-Konfigurationen mit Provider-Zugangsdaten.

```json
{
    "employer-uuid-1234": {
        "id": "employer-uuid-1234",
        "name": "Beispiel GmbH",
        "provider_key": "personio",
        "api_config": {
            "client_id": "xxx",
            "client_secret": "yyy"
        },
        "street": "Musterstraße 1",
        "zip_code": "12345",
        "city": "Musterstadt",
        "country": "Deutschland",
        "email": "hr@beispiel.de",
        "phone": "+49 123 456789",
        "fax": "",
        "comment": "Zusätzliche Infos"
    }
}
```

| Feld | Typ | Beschreibung |
|------|-----|-------------|
| `id` | string | Eindeutige UUID des Arbeitgebers |
| `name` | string | Anzeigename des Arbeitgebers |
| `provider_key` | string | Provider-Typ: "personio", "hrworks", "sagehr" |
| `api_config` | object | Provider-spezifische Zugangsdaten |
| `street`, `zip_code`, etc. | string | Adressdaten für Exporte |

**Sicherheitshinweis**: Enthält API-Credentials. Niemals committen!

## Provider-Konfigurationen

### Personio

```json
{
    "provider_key": "personio",
    "api_config": {
        "client_id": "papi-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
        "client_secret": "papi-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    }
}
```

- **API-Endpunkt**: `https://api.personio.de/v1`
- **Authentifizierung**: OAuth2 Client Credentials
- **Dokumentation**: [Personio Developer Portal](https://developer.personio.de/)

### HRworks

```json
{
    "provider_key": "hrworks",
    "api_config": {
        "access_key": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
        "secret_access_key": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        "use_demo": false
    }
}
```

- **API-Endpunkt (Produktion)**: `https://api.hrworks.de/v2`
- **API-Endpunkt (Demo)**: `https://api.demo-hrworks.de/v2`
- **Authentifizierung**: Access Key / Secret → Bearer Token
- **Dokumentation**: [HRworks API Docs](https://api.hrworks.de/doc/)

| Feld | Typ | Beschreibung |
|------|-----|-------------|
| `access_key` | string | HRworks Access Key |
| `secret_access_key` | string | HRworks Secret Access Key |
| `use_demo` | boolean | `true` für Demo-Umgebung |

### SageHR (Mock)

```json
{
    "provider_key": "sagehr",
    "api_config": {
        "access_key": "beliebig",
        "slug": "beliebig"
    }
}
```

**Hinweis**: SageHR ist aktuell nur ein Mock-Provider für Entwicklungszwecke.

## Server-Konfiguration

### Port ändern

In `run.py`:

```python
port = 5001  # Hier ändern
```

### Host/Binding ändern

In `run.py`:

```python
host = '0.0.0.0'  # Alle Interfaces
# oder
host = '127.0.0.1'  # Nur localhost
```

### Secret Key

In `app.py`:

```python
app.secret_key = 'your-secure-secret-key'
```

**Empfehlung**: In Produktion einen sicheren, zufälligen Key verwenden.

## Datei-Pfade

### Snapshots

Speicherort: `acencia_hub/_snapshots/`

Format: `{ArbeitgeberName}-{provider}-{YYYYMMDD}-{HHMMSS}.json`
Latest: `{ArbeitgeberName}-{provider}-latest.json`

### History (API-Backup)

Speicherort: `acencia_hub/_history/`

Format: `{ArbeitgeberName}-{provider}-history-{YYYYMMDD}-{HHMMSS}-{microseconds}.json`

### Exports

Speicherort: `acencia_hub/exports/`

Standard-Export: `{ArbeitgeberName}_Mitarbeiter_{YYYYMMDD}_{HHMMSS}.xlsx`
Delta-Export: `{ArbeitgeberName}_Delta_SCS_{YYYYMMDD}_{HHMMSS}.xlsx`

## Logging

### Log-Datei

Speicherort: `server.log` (Projekt-Root)

Format:
```
[DD/Mon/YYYY HH:MM:SS] ("KÜRZ" - Nachricht)
```

### Log-Level

Aktuell: `INFO` für alle Logger

Ändern in `app.py`:

```python
file_logger.setLevel(logging.DEBUG)  # Mehr Details
```

## Update-Konfiguration

### Ausgeschlossene Pfade

In `updater.py`:

```python
EXCLUSIONS = [
    ".git",
    "venv",
    ".idea",
    "__pycache__",
    "_snapshots",      # Benutzerdaten behalten
    "_history",        # Benutzerdaten behalten
    "exports",         # Benutzerdaten behalten
    "acencia_hub/data", # Konfiguration behalten
    "acencia_hub/updater.py",
    "start.bat",
]
```

Diese Dateien/Ordner werden bei Updates **nicht überschrieben**.

### GitHub Repository URL

In `updater.py`:

```python
ZIP_URL = "https://github.com/USER/REPO/archive/refs/heads/main.zip"
```

## Empfohlene Sicherheitspraktiken

1. **Niemals committen**:
   - `acencia_hub/data/users.json`
   - `acencia_hub/data/secrets.json`
   - `acencia_hub/data/employers.json`
   - `server.log`
   - `venv/`

2. **Regelmäßig rotieren**:
   - GitHub Personal Access Token
   - Provider API-Credentials

3. **Backups erstellen**:
   - `acencia_hub/data/` Ordner
   - `acencia_hub/_snapshots/` Ordner

4. **Zugriff beschränken**:
   - Server nur im internen Netzwerk betreiben
   - Firewall-Regeln für Port 5001

---

**Letzte Aktualisierung:** 28.01.2026
