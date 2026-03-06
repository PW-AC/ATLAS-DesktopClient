# 02 - Architektur (IST-Zustand)

## Komponentenübersicht

### Kern-Module

| Komponente | Datei | Zeilen | Beschreibung |
|------------|-------|--------|--------------|
| Flask-App | `app.py` | 1480-1893 | Flask-Instanz, Konfiguration, Middleware |
| EmployerStore | `app.py` | 253-383 | Singleton für Arbeitgeber-Datenpersistenz |
| BaseProvider | `app.py` | 385-435 | Abstrakte Basisklasse für HR-Provider |
| HRworksProvider | `app.py` | 437-683 | HRworks API-Integration |
| PersonioProvider | `app.py` | 729-898 | Personio API-Integration |
| SageHrProvider | `app.py` | 685-727 | Mock-Provider für Tests |
| ProviderFactory | `app.py` | 900-925 | Factory für Provider-Instanzen |
| Updater | `updater.py` | 1-165 | Auto-Update von GitHub |

### Datenschicht

| Komponente | Pfad | Format | Beschreibung |
|------------|------|--------|--------------|
| Benutzerdaten | `data/users.json` | JSON | Benutzernamen, Passwort-Hashes, Rollen |
| Geheimnisse | `data/secrets.json` | JSON | GitHub PAT |
| Arbeitgeber | `employers.json` | JSON | Provider-Credentials, Konfiguration |
| Snapshots | `_snapshots/*.json` | JSON | Mitarbeiter-Momentaufnahmen |
| History | `_history/*.json` | JSON | Rohe API-Antworten |
| Exporte | `exports/*.xlsx` | XLSX | Generierte Excel-Dateien |

## Architektur-Diagramm

```
┌─────────────────────────────────────────────────────────────────┐
│                         Browser/Client                           │
└─────────────────────────────────────────────────────────────────┘
                                │
                          HTTP (Port 5001)
                          KEIN HTTPS
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Waitress WSGI Server                          │
│                    (run.py / start.bat)                          │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                       Flask Application                          │
│                         (app.py)                                 │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │  Routes     │  │ Middleware  │  │  Session Management     │  │
│  │  (UI + API) │  │ before_req  │  │  (Flask Session)        │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                    Business Logic                            ││
│  │  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌─────────────┐  ││
│  │  │ Provider  │ │ Employer  │ │  Export   │ │  Statistics │  ││
│  │  │  Factory  │ │   Store   │ │  Logic    │ │   Logic     │  ││
│  │  └───────────┘ └───────────┘ └───────────┘ └─────────────┘  ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
         │                    │                    │
         │                    │                    │
         ▼                    ▼                    ▼
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│  External   │      │   Local     │      │   Local     │
│  HR APIs    │      │   JSON      │      │   Files     │
│  (HTTPS)    │      │   Storage   │      │   (XLSX)    │
└─────────────┘      └─────────────┘      └─────────────┘
```

## Datenflüsse

### 1. Authentifizierung

```
Browser → POST /login → session['user_id'] → Cookie
                  │
                  ▼
            users.json (Passwort-Hash-Vergleich)
```

**Evidenz:** `app.py:1569-1603`

### 2. Provider-Authentifizierung

```
Flask App → Provider.__init__() → _authenticate() → External API
                                        │
                                        ▼
                                  Bearer Token (gecacht)
```

**Evidenz:**
- Personio: `app.py:752-767`
- HRworks: `app.py:482-504`

### 3. Mitarbeiterdaten abrufen

```
Browser → /employer/<id> → ProviderFactory → Provider.list_employees()
                                                    │
                                              External API
                                                    │
                                              Normalisierung
                                                    │
                                              Template Rendering
```

**Evidenz:** `app.py:1941-1972`

### 4. Delta-Export

```
Browser → /api/.../export/delta_scs → Provider.list_employees()
                                            │
                                      Snapshot laden
                                            │
                                      Diff berechnen
                                            │
                                      XLSX generieren
                                            │
                                      Snapshot speichern
```

**Evidenz:** `app.py:1083-1184`, `app.py:2495-2564`

## Kritische Pfade

### Datei-Zugriff

| Operation | Pfad-Konstruktion | Evidenz |
|-----------|-------------------|---------|
| Snapshot lesen | `os.path.join(snapshots_dir, filename)` | `app.py:2256-2257` |
| Export lesen | `send_from_directory(EXPORTS_DIR, filename)` | `app.py:2629-2633` |
| History schreiben | `os.path.join(history_dir, filename)` | `app.py:239` |

### Session-Daten

| Key | Inhalt | Evidenz |
|-----|--------|---------|
| `user_id` | Benutzername | `app.py:1588` |
| `user_info` | Dict mit username, kuerzel, is_master, color, theme | `app.py:1589-1595` |
| `login_time` | UTC Timestamp | `app.py:1596` |

## Abhängigkeiten zwischen Komponenten

```
EmployerStore ──────► employers.json
      │
      ▼
ProviderFactory ────► HRworksProvider
      │               PersonioProvider
      │               SageHrProvider
      │
      ▼
External APIs ◄────── requests (HTTPS)
```

## Single Points of Failure

| Komponente | Risiko | Evidenz |
|------------|--------|---------|
| `app.py` | Monolithisch (~2719 Zeilen) | Datei-Größe |
| `users.json` | Keine Backup-Strategie | Kein Backup-Code gefunden |
| `employers.json` | Credentials im Klartext | `app.py:1919-1931` |
| `secret_key` | Hardcodiert | `app.py:1481` |

---

**Letzte Aktualisierung:** 28.01.2026
