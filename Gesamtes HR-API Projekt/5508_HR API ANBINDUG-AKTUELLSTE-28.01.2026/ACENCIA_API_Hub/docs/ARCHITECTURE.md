# ACENCIA Hub - Architektur-Dokumentation

## Überblick

ACENCIA Hub ist eine Flask-basierte Web-Anwendung für die Integration verschiedener HR-Provider-APIs. Die Anwendung folgt einer klassischen MVC-ähnlichen Architektur mit klarer Trennung zwischen Datenebene, Geschäftslogik und Präsentation.

## System-Architektur

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
│  │  ├── Personio API (https://api.personio.de)                              │
│  │  ├── HRworks API (https://api.hrworks.de / api.demo-hrworks.de)          │
│  │  └── SageHR API (Mock)                                                    │
│  └───────────────────────────────────────────────────────────────────────────│
└─────────────────────────────────────────────────────────────────────────────┘
```

## Komponenten-Übersicht

### 1. Entry Points

| Datei | Beschreibung |
|-------|-------------|
| `run.py` | Produktions-Entry-Point mit Waitress-Server |
| `start.bat` | Windows-Batch-Skript für einfachen Start |
| `acencia_hub/app.py` | Flask-Anwendung (auch direkt ausführbar) |

### 2. Kern-Module

#### `acencia_hub/app.py` (~2700 Zeilen)

Die Hauptanwendung enthält:

- **Helper-Funktionen** (Zeilen 60-250)
  - `custom_log()` - Logging mit Farben
  - `_get_from_path()` - Sichere Dictionary-Navigation
  - `_getv()` - Wertextraktion mit Fallbacks
  - `save_history_entry()` - API-Antworten archivieren

- **EmployerStore** (Klasse, Singleton)
  - Verwaltet Arbeitgeber-Konfigurationen
  - Liest/schreibt `employers.json`
  - Thread-sicher mit Lock

- **Provider-Klassen**
  - `BaseProvider` - Abstrakte Basisklasse
  - `PersonioProvider` - Personio API Integration
  - `HRworksProvider` - HRworks API Integration
  - `SageHrProvider` - Mock-Provider für Tests

- **ProviderFactory**
  - Instanziiert Provider basierend auf `provider_key`

- **Export-Funktionen**
  - `generate_standard_export()` - XLSX-Vollexport
  - `generate_delta_scs_export()` - Delta-Export für SCS
  - `_map_to_scs_schema()` - Daten-Mapping

- **Flask-Routen**
  - UI-Routen (index, employer, employee, etc.)
  - API-Routen (/api/*)
  - Download-Routen

#### `acencia_hub/updater.py`

- Automatische Updates von GitHub
- Lädt ZIP-Archiv herunter
- Kopiert Dateien mit Ausschlüssen

### 3. Daten-Schicht

```
acencia_hub/
├── data/
│   ├── users.json        # Benutzerdatenbank (Passwort-Hashes)
│   ├── secrets.json      # GitHub PAT, andere Geheimnisse
│   ├── triggers.json     # Trigger-Konfiguration und SMTP (NEU)
│   ├── trigger_log.json  # Trigger-Ausführungsprotokoll (NEU)
│   └── force_logout.txt  # Zeitstempel für erzwungenes Logout
├── _snapshots/           # Arbeitgeber-Snapshots (JSON)
├── _history/             # Rohdaten-Backup der API-Antworten
└── exports/              # Generierte Export-Dateien (XLSX)
```

### 4. Frontend-Schicht

```
acencia_hub/
├── static/
│   └── css/
│       ├── tokens.css    # Design-Token (Farben, Spacing, etc.)
│       └── style.css     # Komponenten-Styles
└── templates/
    ├── base.html              # Basis-Template mit Navigation
    ├── index.html             # Hauptseite (Arbeitgeber-Liste)
    ├── login.html             # Anmeldeseite
    ├── employer_dashboard.html # Mitarbeiter-Übersicht
    ├── employee_detail.html   # Mitarbeiter-Details
    ├── statistics.html        # Statistik-Dashboard
    ├── exports.html           # Export-Verwaltung
    ├── snapshot_comparison.html # Snapshot-Vergleich
    ├── settings.html          # System-Einstellungen
    ├── user_settings.html     # Benutzer-Einstellungen
    ├── employer_settings.html # Arbeitgeber-Einstellungen
    ├── employer_triggers.html # Arbeitgeber-spezifische Trigger (NEU)
    ├── add_employer.html      # Neuen Arbeitgeber hinzufügen
    ├── triggers.html          # Trigger-Übersicht (NEU)
    ├── trigger_form.html      # Trigger erstellen/bearbeiten (NEU)
    ├── trigger_log.html       # Ausführungsprotokoll (NEU)
    ├── smtp_settings.html     # SMTP-Konfiguration (NEU)
    └── styleguide.html        # Design-System-Dokumentation
```

## Trigger-System (NEU)

Das Trigger-System ermöglicht automatisierte Aktionen bei Mitarbeiterdaten-Änderungen:

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Trigger-Architektur                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Delta-Export ──► TriggerEngine ──► Bedingungsprüfung               │
│                        │                   │                         │
│                        │           ┌───────┴───────┐                │
│                        │           │               │                 │
│                        ▼           ▼               ▼                 │
│                   EmailAction   APIAction    TriggerLogStore        │
│                        │           │               │                 │
│                        ▼           ▼               ▼                 │
│                   SMTP-Server  Ext. API    trigger_log.json         │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Komponenten

| Klasse | Beschreibung |
|--------|-------------|
| `TriggerStore` | Singleton, verwaltet triggers.json |
| `TriggerLogStore` | Singleton, verwaltet trigger_log.json |
| `TriggerEngine` | Evaluiert Trigger, führt Aktionen aus |
| `EmailAction` | SMTP-basierter E-Mail-Versand |
| `APIAction` | HTTP-Requests an externe APIs |

### Datenfluss bei Trigger-Ausführung

```
Delta-Export generieren
        │
        ▼
TriggerEngine.evaluate_and_execute(employer, diff, current_data)
        │
        ├──► Lade aktive Trigger für Arbeitgeber
        │
        ├──► Für jeden Trigger:
        │         │
        │         ├── Bestimme betroffene Mitarbeiter
        │         ├── Prüfe Bedingungen (AND/OR)
        │         ├── Baue Template-Kontext
        │         └── Führe Aktion aus (Email/API)
        │
        └──► Protokolliere Ausführungen
```

## Datenfluss

### 1. Mitarbeiterdaten abrufen

```
Browser → Flask Route → ProviderFactory → Provider.list_employees()
                                                    │
                                                    ▼
                                              HR-API Request
                                                    │
                                                    ▼
                              Normalisierte Daten ← API Response
                                        │
                                        ▼
                              Template Rendering → Browser
```

### 2. Delta-Export generieren

```
Browser → API Route → Provider.get_employee_details()
                              │
                              ▼
                    Aktuelle Daten laden
                              │
                              ▼
                    Snapshot laden (_snapshots/*-latest.json)
                              │
                              ▼
                    Diff berechnen (neu, geändert, entfernt)
                              │
                              ▼
                    XLSX generieren → exports/
                              │
                              ▼
                    Neuen Snapshot speichern
                              │
                              ▼
                    JSON Response → Browser (Download)
```

## Provider-Abstraktion

```python
class BaseProvider(ABC):
    """Abstrakte Basisklasse für alle HR-Provider"""
    
    @abstractmethod
    def list_employees(self) -> Tuple[List[dict], Any]:
        """Gibt Liste aller Mitarbeiter zurück"""
        pass
    
    @abstractmethod
    def get_employee_details(self, employee_id) -> Tuple[dict, Any]:
        """Gibt Details eines Mitarbeiters zurück"""
        pass
    
    @abstractmethod
    def normalize_employee(self, data: dict) -> dict:
        """Normalisiert Mitarbeiterdaten in einheitliches Format"""
        pass
```

## Authentifizierung & Sicherheit

### Session-Management
- Flask-Sessions mit Secret Key
- Session-basiertes Theme-Preference
- Forced-Logout-Mechanismus über Timestamp-Datei

### Passwort-Sicherheit
- Werkzeug `scrypt` Hashing
- Sichere Passwort-Vergleiche

### Provider-Authentifizierung
- **Personio**: OAuth2 Client Credentials
- **HRworks**: Access Key / Secret Key → Bearer Token

## Design-System

Das Frontend verwendet ein Token-basiertes Design-System:

- **tokens.css**: Definiert alle Variablen (Farben, Spacing, etc.)
- **style.css**: Komponenten-basierte Styles
- **Hell/Dunkel-Modus**: Via `data-theme="dark"` Attribut

Siehe `/styleguide` Route für Live-Dokumentation.

## Abhängigkeiten

| Paket | Version | Zweck |
|-------|---------|-------|
| Flask | 3.0.3 | Web-Framework |
| Werkzeug | 3.0.3 | WSGI Utilities, Passwort-Hashing |
| Jinja2 | 3.1.4 | Template Engine |
| requests | 2.32.3 | HTTP-Client für API-Calls |
| openpyxl | 3.1.3 | Excel-Export |
| waitress | 3.0.0 | Produktions-WSGI-Server |

---

**Letzte Aktualisierung:** 28.01.2026 (Trigger-System hinzugefügt)
