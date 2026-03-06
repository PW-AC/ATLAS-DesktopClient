# 02 - System und Architektur

## Architektur-Diagramm

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              ACENCIA Hub                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │
│  │   Browser   │    │   Waitress  │    │  Flask App  │    │  Providers  │  │
│  │   (Client)  │◄──►│   (WSGI)    │◄──►│  (app.py)   │◄──►│  (API)      │  │
│  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘  │
│                                               │                     ▲        │
│                                               ▼                     │        │
│                                        ┌─────────────┐              │        │
│                                        │  JSON Data  │              │        │
│                                        │  Storage    │              │        │
│                                        └─────────────┘              │        │
│                                                                     │        │
│  ┌──────────────────────────────────────────────────────────────────┘        │
│  │  Externe HR-Provider APIs                                                 │
│  │  ├── Personio API (https://api.personio.de/v1)                           │
│  │  ├── HRworks API (https://api.hrworks.de/v2 / api.demo-hrworks.de/v2)    │
│  │  └── SageHR API (Mock-Implementierung)                                   │
│  └───────────────────────────────────────────────────────────────────────────│
└─────────────────────────────────────────────────────────────────────────────┘
```

**Evidenz:** `docs/ARCHITECTURE.md:9-31`

---

## Tech-Stack

| Komponente | Technologie | Version | Zweck | Evidenz |
|------------|-------------|---------|-------|---------|
| Sprache | Python | 3.8+ | Anwendungslogik | `requirements.txt` |
| Web-Framework | Flask | 3.0.3 | HTTP-Handling, Routing | `requirements.txt:2` |
| Template-Engine | Jinja2 | 3.1.4 | HTML-Rendering | `requirements.txt:4` |
| WSGI-Server | Waitress | 3.0.0 | Produktions-Server | `requirements.txt:14` |
| HTTP-Client | requests | 2.32.3 | API-Kommunikation | `requirements.txt:11` |
| Excel-Export | openpyxl | 3.1.3 | XLSX-Generierung | `requirements.txt:10` |
| Passwort-Hashing | Werkzeug | 3.0.3 | scrypt-Hashing | `requirements.txt:3` |
| Rate-Limiting | Flask-Limiter | 3.5.0 | Brute-Force-Schutz | `requirements.txt:20` |
| CSRF-Schutz | Flask-WTF | 1.2.1 | Formular-Sicherheit | `requirements.txt:23` |
| Verschlüsselung | cryptography | 42.0.0 | Credential-Encryption | `requirements.txt:22` |
| Tests | pytest | 8.0.0 | Unit-Tests | `requirements.txt:25` |

---

## Komponenten-Übersicht

### 1. Präsentationsschicht (Frontend)

| Komponente | Dateien | Beschreibung |
|------------|---------|--------------|
| Base-Template | `templates/base.html` | Layout, Navigation, Theme-Logik |
| CSS-Tokens | `static/css/tokens.css` | Design-Variablen (Farben, Spacing) |
| Styles | `static/css/style.css` | Komponenten-Styles |
| 13 Templates | `templates/*.html` | Seiten-spezifische Templates |

**Evidenz:** `acencia_hub/templates/`, `acencia_hub/static/css/`

### 2. Anwendungsschicht (Backend)

| Komponente | Datei | Zeilen | Beschreibung |
|------------|-------|--------|--------------|
| Flask-App | `app.py` | ~5326 | Gesamte Anwendungslogik inkl. Trigger-System |
| Updater | `updater.py` | ~165 | GitHub Auto-Update |
| Modul-Init | `__init__.py` | ~37 | Metadaten |

**Evidenz:** `acencia_hub/*.py`

### 3. Datenschicht (Storage)

| Datei/Ordner | Typ | Inhalt |
|--------------|-----|--------|
| `data/users.json` | JSON | Benutzerdatenbank |
| `data/secrets.json` | JSON | GitHub PAT |
| `data/triggers.json` | JSON | Trigger-Konfiguration und SMTP |
| `data/trigger_log.json` | JSON | Trigger-Ausführungsprotokoll |
| `employers.json` | JSON | Arbeitgeber-Konfiguration |
| `_snapshots/` | JSON-Dateien | Mitarbeiter-Snapshots |
| `_history/` | JSON-Dateien | Rohe API-Antworten |
| `exports/` | XLSX-Dateien | Generierte Exporte |
| `server.log` | Text | Anwendungs-Log |
| `audit.log` | Text | Audit-Trail |

**Evidenz:** `app.py:3164-3230`, `docs/CONFIGURATION.md`

---

## Klassen-Hierarchie

```
BaseProvider (ABC)                     [Zeile 1837]
├── HRworksProvider                    [Zeile 1889]
├── SageHrProvider                     [Zeile 2142]
└── PersonioProvider                   [Zeile 2186]

EmployerStore (Singleton)              [Zeile 460]
└── Thread-safe JSON persistence

TriggerStore (Singleton)               [Zeile 624]
└── Trigger-Konfiguration und SMTP

TriggerLogStore (Singleton)            [Zeile 975]
└── Trigger-Ausführungsprotokoll

TriggerEngine                          [Zeile 1164]
├── EmailAction                        [Zeile 1602]
└── APIAction                          [Zeile 1742]

ProviderFactory                        [Zeile 2363]
└── Erstellt Provider basierend auf provider_key
```

**Evidenz:** `app.py:460-2390`

---

## Routen-Übersicht

### UI-Routen

| Route | Methoden | Template | Beschreibung |
|-------|----------|----------|--------------|
| `/` | GET | `index.html` | Hauptseite, Arbeitgeber-Liste |
| `/login` | GET, POST | `login.html` | Anmeldung |
| `/logout` | GET | - | Abmeldung |
| `/employer/add` | GET, POST | `add_employer.html` | Arbeitgeber hinzufügen |
| `/employer/<id>` | GET | `employer_dashboard.html` | Mitarbeiter-Übersicht |
| `/employer/<id>/employee/<eid>` | GET | `employee_detail.html` | Mitarbeiter-Details |
| `/employer/<id>/statistics` | GET | `statistics.html` | Statistiken |
| `/employer/<id>/exports` | GET | `exports.html` | Export-Verwaltung |
| `/employer/<id>/snapshots` | GET | `snapshot_comparison.html` | Snapshot-Vergleich |
| `/employer/<id>/settings` | GET, POST | `employer_settings.html` | Arbeitgeber-Einstellungen |
| `/employer/<id>/triggers` | GET | `employer_triggers.html` | AG-spezifische Trigger |
| `/settings` | GET, POST | `settings.html` | Master-Einstellungen |
| `/settings/triggers` | GET | `triggers.html` | Trigger-Übersicht |
| `/settings/triggers/new` | GET, POST | `trigger_form.html` | Neuer Trigger |
| `/settings/triggers/<id>/edit` | GET, POST | `trigger_form.html` | Trigger bearbeiten |
| `/settings/smtp` | GET, POST | `smtp_settings.html` | SMTP-Konfiguration |
| `/settings/trigger-log` | GET | `trigger_log.html` | Ausführungsprotokoll |
| `/user-settings` | GET, POST | `user_settings.html` | Benutzer-Einstellungen |
| `/styleguide` | GET | `styleguide.html` | Design-System |

### API-Routen

| Route | Methoden | Response | Beschreibung |
|-------|----------|----------|--------------|
| `/api/employer/<id>/employees` | GET | JSON | Mitarbeiterliste |
| `/api/employer/<id>/statistics` | GET | JSON | Standard-Statistiken |
| `/api/employer/<id>/long_term_statistics` | GET | JSON | Langzeit-Statistiken |
| `/api/employer/<id>/export/delta_scs` | POST | JSON | Delta-Export generieren |
| `/api/employer/<id>/past_exports` | GET | JSON | Liste vergangener Exporte |
| `/api/employer/<id>/snapshots/compare` | POST | JSON | Snapshot-Vergleich |
| `/api/triggers/fields` | GET | JSON | SCS-Felder für Trigger-UI |
| `/api/trigger-log` | GET | JSON | Trigger-Ausführungslog |
| `/api/trigger-log/<id>/retry` | POST | JSON | Trigger-Ausführung wiederholen |
| `/api/health` | GET | JSON | Health-Check (SV-025) |
| `/api/ready` | GET | JSON | Readiness-Check (SV-025) |

### Download-Routen

| Route | Beschreibung |
|-------|--------------|
| `/download/export/<filename>` | Export-Datei herunterladen |
| `/download/past_export/<filename>` | Vergangenen Export herunterladen |
| `/employer/<id>/export/statistics/standard` | Standard-Statistik TXT |
| `/employer/<id>/export/statistics/longterm` | Langzeit-Statistik TXT |

**Evidenz:** `app.py:2966-5295`

---

## Datenflüsse

### 1. Mitarbeiterdaten abrufen

```
1. Browser → GET /employer/<id>
2. Flask Route → EmployerStore.get_by_id()
3. ProviderFactory.create() → Provider-Instanz
4. Provider.list_employees() → HR-API-Request
5. API Response → normalize_employee()
6. Template Rendering → Browser
```

**Evidenz:** `docs/ARCHITECTURE.md:125-138`

### 2. Delta-Export generieren

```
1. Browser → POST /api/employer/<id>/export/delta_scs
2. Flask API Route
3. Provider.get_employee_details() für alle Mitarbeiter
4. Snapshot laden (_snapshots/*-latest.json)
5. Diff berechnen (neue/geänderte/entfernte PIDs)
6. _map_to_scs_schema() → SCS-Format
7. openpyxl → XLSX generieren
8. Neuen Snapshot speichern
9. JSON Response → Browser (Dateiname + Diff)
10. Browser → Download
```

**Evidenz:** `docs/ARCHITECTURE.md:140-162`, `app.py:1229-1426`

### 3. Authentifizierung

```
1. Browser → POST /login (Benutzername, Passwort)
2. Rate-Limiter prüft (5/Minute)
3. Account-Lockout prüft (5 Versuche, 15min Sperre)
4. load_users() → users.json
5. check_password_hash() → Werkzeug scrypt
6. Session erstellen (user_info, theme, allowed_employers)
7. Redirect → /
```

**Evidenz:** `app.py:3369-3440`

---

## Provider-Authentifizierung

### Personio

```
POST https://api.personio.de/v1/auth
{
    "client_id": "...",
    "client_secret": "..."
}
→ Bearer Token
```

**Evidenz:** `app.py:988-1010`

### HRworks

```
POST https://api.hrworks.de/v2/authentication
{
    "accessKey": "...",
    "secretAccessKey": "..."
}
→ Bearer Token
```

**Evidenz:** `app.py:713-735`, `AGENTS.md:25-30`

---

## Sicherheits-Middleware

| Middleware | Zweck | Evidenz |
|------------|-------|---------|
| `add_security_headers()` | X-Frame-Options, CSP, etc. | `app.py:1808-1827` |
| `check_employer_route_access()` | Arbeitgeber-Zugriffskontrolle | `app.py:1871-1908` |
| CSRF-Schutz | Flask-WTF CSRFProtect | `app.py:1728-1741` |
| Rate-Limiter | Flask-Limiter | `app.py:1781-1796` |

---

## Session-Management

| Aspekt | Konfiguration | Evidenz |
|--------|---------------|---------|
| Secret Key | `ACENCIA_SECRET_KEY` Env-Var | `app.py:1748-1754` |
| Timeout | 8 Stunden | `app.py:1762-1763` |
| Cookie Flags | HttpOnly, SameSite=Lax | `app.py:1771-1774` |
| Secure Flag | Nur wenn `HTTPS_ENABLED=true` | `app.py:1774` |

---

**Letzte Aktualisierung:** 29.01.2026
