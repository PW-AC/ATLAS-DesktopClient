# 04 - Code-Struktur und Modulübersicht

## Ordnerstruktur

```
ACENCIA_API_Hub/
├── acencia_hub/                    # Hauptanwendung
│   ├── __init__.py                 # Modul-Metadaten (37 Zeilen)
│   ├── app.py                      # Gesamte Anwendungslogik (~5326 Zeilen)
│   ├── updater.py                  # Auto-Update-Funktionalität (165 Zeilen)
│   ├── employers.json              # Arbeitgeber-Konfiguration
│   ├── data/                       # Persistente Benutzerdaten
│   │   ├── users.json              # Benutzerdatenbank
│   │   ├── secrets.json            # GitHub PAT
│   │   ├── triggers.json           # Trigger-Konfiguration + SMTP
│   │   ├── trigger_log.json        # Trigger-Ausführungsprotokoll
│   │   └── force_logout.txt        # Erzwungenes Abmelden (Timestamp)
│   ├── static/                     # Statische Assets
│   │   └── css/
│   │       ├── tokens.css          # Design-Token (138 Zeilen)
│   │       └── style.css           # Komponenten-Styles
│   ├── templates/                  # Jinja2-Templates (18 Dateien)
│   │   ├── base.html               # Basis-Layout
│   │   ├── index.html              # Hauptseite
│   │   ├── login.html              # Anmeldung
│   │   ├── employer_dashboard.html # Mitarbeiter-Übersicht
│   │   ├── employee_detail.html    # Mitarbeiter-Details
│   │   ├── statistics.html         # Statistiken
│   │   ├── exports.html            # Export-Verwaltung
│   │   ├── snapshot_comparison.html# Snapshot-Vergleich
│   │   ├── settings.html           # Master-Einstellungen
│   │   ├── user_settings.html      # Benutzer-Einstellungen
│   │   ├── employer_settings.html  # Arbeitgeber-Einstellungen
│   │   ├── employer_triggers.html  # AG-spezifische Trigger
│   │   ├── add_employer.html       # Arbeitgeber hinzufügen
│   │   ├── triggers.html           # Trigger-Übersicht
│   │   ├── trigger_form.html       # Trigger erstellen/bearbeiten
│   │   ├── trigger_log.html        # Ausführungsprotokoll
│   │   ├── smtp_settings.html      # SMTP-Konfiguration
│   │   └── styleguide.html         # Design-System
│   ├── _snapshots/                 # Generierte Snapshots (dynamisch)
│   ├── _history/                   # API-Response-Backup (dynamisch)
│   └── exports/                    # Generierte Exporte (dynamisch)
├── docs/                           # Dokumentation
│   ├── ARCHITECTURE.md             # Architektur-Übersicht
│   ├── CONFIGURATION.md            # Konfigurations-Dokumentation
│   ├── DEVELOPMENT.md              # Entwicklungs-Dokumentation
│   └── TRIGGERS.md                 # Trigger-System-Dokumentation
├── Sicherheit/                     # Security-Audit und -Umsetzung
│   ├── 00_INDEX.md ... 13_*.md     # IST-Analyse (26 Befunde)
│   ├── Loesung/                    # Lösungsplan
│   └── Umsetzung/                  # Umsetzungs-Protokoll
├── tests/                          # Pytest-Tests
│   ├── __init__.py
│   ├── conftest.py                 # Fixtures
│   ├── test_auth.py                # Auth-Tests
│   └── test_security.py            # Security-Tests
├── venv/                           # Virtuelle Umgebung (ignoriert)
├── requirements.txt                # Python-Abhängigkeiten
├── run.py                          # Produktions-Entry-Point (65 Zeilen)
├── start.bat                       # Windows-Starter (53 Zeilen)
├── AGENTS.md                       # KI-Agent-Dokumentation
├── README.md                       # Projekt-README
├── README_DESIGN.md                # Design-System-Dokumentation
├── .gitignore                      # Git-Ausschlüsse
├── server.log                      # Anwendungs-Log
└── audit.log                       # Audit-Trail
```

---

## app.py - Struktur und Sektionen

Die Hauptdatei `app.py` enthält die gesamte Anwendungslogik (~5326 Zeilen). Sie ist in folgende Sektionen unterteilt:

### Sektion 1: Imports und Setup (Zeilen 1-455)

| Bereich | Zeilen | Beschreibung |
|---------|--------|--------------|
| Imports | 1-17 | Standard-Library und externe Pakete |
| Credential-Verschlüsselung | 18-127 | Fernet-Verschlüsselung für API-Keys |
| Logging-Setup | 130-260 | FileLogger, AuditLogger, PII-Anonymisierung |
| SCS_HEADERS Konstante | 306-312 | Feste Export-Spalten |
| Helper-Funktionen | 315-455 | Utility-Funktionen |

### Sektion 2: Helper-Funktionen (Zeilen 315-455)

| Funktion | Zeilen | Beschreibung |
|----------|--------|--------------|
| `_get_from_path()` | 315-343 | Sichere Dictionary-Navigation |
| `_getv()` | 345-364 | Wert-Extraktion mit Label-Lookup |
| `_get_safe_employer_name()` | 366-376 | Dateiname-sichere Strings |
| `_get_value_from_details()` | 378-395 | Wert aus Details-Gruppen |
| `_parse_date()` | 397-413 | Datum-Parsing (mehrere Formate) |
| `_format_date_for_display()` | 415-426 | Formatierung für Anzeige |
| `save_history_entry()` | 428-455 | API-Antwort archivieren |

### Sektion 3: Core Classes - Data Stores (Zeilen 460-1160)

| Klasse | Zeilen | Beschreibung |
|--------|--------|--------------|
| `EmployerStore` | 460-617 | Singleton für Arbeitgeber-Persistenz |
| `TriggerStore` | 624-973 | Singleton für Trigger-Konfiguration |
| `TriggerLogStore` | 975-1160 | Singleton für Trigger-Protokollierung |

### Sektion 4: Trigger-System (Zeilen 1164-1835)

| Klasse/Funktion | Zeilen | Beschreibung |
|-----------------|--------|--------------|
| `TriggerEngine` | 1164-1600 | Trigger-Auswertung und -Ausführung |
| `EmailAction` | 1602-1740 | E-Mail-Versand via SMTP |
| `APIAction` | 1742-1835 | HTTP-Requests an externe APIs |

### Sektion 5: Provider Classes (Zeilen 1837-2390)

| Klasse | Zeilen | Beschreibung |
|--------|--------|--------------|
| `BaseProvider` | 1837-1887 | Abstrakte Basisklasse für Provider |
| `HRworksProvider` | 1889-2141 | HRworks API-Implementierung |
| `SageHrProvider` | 2142-2185 | Mock-Provider |
| `PersonioProvider` | 2186-2360 | Personio API-Implementierung |
| `ProviderFactory` | 2363-2390 | Factory für Provider-Instanzen |

### Sektion 6: Export-Funktionen (Zeilen 2394-2965)

| Funktion | Zeilen | Beschreibung |
|----------|--------|--------------|
| `_map_to_scs_schema()` | 2394-2471 | Daten in SCS-Format transformieren |
| `generate_standard_export()` | 2473-2507 | XLSX-Vollexport |
| `_json_hash()` | 2509-2520 | Hash für Änderungserkennung |
| `_flatten_record()` | 2522-2542 | Record flach machen |
| `_person_key()` | 2544-2555 | Eindeutiger Schlüssel für Person |
| `generate_delta_scs_export()` | 2557-2675 | Delta-Export mit Snapshot |
| `_get_employee_history_from_snapshots()` | 2676-2778 | Historie aus Snapshots |
| `calculate_statistics()` | 2779-2829 | Standard-Statistiken |
| `calculate_long_term_statistics()` | 2830-2905 | Langzeit-Statistiken |
| `_format_stats_for_export()` | 2907-2965 | Statistiken als TXT |

### Sektion 7: Flask App und Routen (Zeilen 2966-5295)

| Bereich | Zeilen | Beschreibung |
|---------|--------|--------------|
| App-Initialisierung | 2966-3055 | Flask, CSRF, Rate-Limiter |
| Security Headers | 3057-3075 | After-Request-Handler |
| Zugriffskontrolle | 3084-3162 | Arbeitgeber-Berechtigungen |
| User-Management | 3164-3355 | load_users, validate_password, lockout |
| Login/Logout | 3357-3450 | Authentifizierungs-Routen |
| Settings-Routen | 3454-3560 | User, Master-Einstellungen |
| **Trigger-Routen** | 3570-3990 | Trigger-CRUD, SMTP, Logs |
| User-Settings | 4095-4170 | Benutzereinstellungen |
| Index/Arbeitgeber | 4303-4405 | Hauptseiten-Routen |
| Mitarbeiter-Routen | 4406-4467 | Dashboard, Details |
| Employer-Routen | 4468-4630 | Exports, Settings, Triggers |
| Statistik-Routen | 4632-4710 | Standard, Langzeit |
| Snapshot-Routen | 4712-4945 | Vergleich, Listing, Delete |
| API-Routen | 4968-5180 | JSON-Endpoints |
| Export-Download | 5197-5260 | Statistik-Export |
| Health-Checks | 5279-5295 | /api/health, /api/ready |

---

## Klassen im Detail

### EmployerStore

```python
class EmployerStore:
    """Singleton zur Verwaltung der Arbeitgeber-Datenpersistenz."""
    
    _instance, _lock = None, Lock()  # Thread-safe Singleton
    
    def __new__(cls): ...           # Singleton-Pattern
    def __init__(filepath): ...     # Initialisierung
    def _read_data(): ...           # JSON lesen (+ Entschlüsselung)
    def _write_data(data): ...      # JSON schreiben (+ Verschlüsselung)
    def get_all(): ...              # Alle Arbeitgeber
    def get_by_id(id): ...          # Einzelner Arbeitgeber
    def add(data): ...              # Arbeitgeber hinzufügen
    def delete(id): ...             # Arbeitgeber löschen
    def update(id, data): ...       # Arbeitgeber aktualisieren
```

**Evidenz:** `app.py:460-617`

### TriggerStore

```python
class TriggerStore:
    """Singleton zur Verwaltung der Trigger-Konfiguration."""
    
    TRIGGER_EVENTS = ['employee_changed', 'employee_added', 'employee_removed']
    CONDITION_OPERATORS = ['changed', 'changed_to', 'changed_from', ...]
    ACTION_TYPES = ['email', 'api']
    
    def get_smtp_config(): ...          # SMTP-Konfiguration (entschlüsselt)
    def update_smtp_config(config): ... # SMTP speichern (verschlüsselt)
    def get_all_triggers(): ...         # Alle Trigger
    def get_active_triggers(): ...      # Nur aktivierte
    def get_triggers_for_employer(id): ... # Für Arbeitgeber (ohne Ausschlüsse)
    def create_trigger(data): ...       # Trigger erstellen
    def update_trigger(id, data): ...   # Trigger aktualisieren
    def delete_trigger(id): ...         # Trigger löschen
    def toggle_trigger(id): ...         # Aktivieren/Deaktivieren
    def exclude_employer(tid, eid): ... # AG ausschließen
```

**Evidenz:** `app.py:624-973`

### TriggerLogStore

```python
class TriggerLogStore:
    """Singleton zur Verwaltung des Trigger-Ausführungsprotokolls."""
    
    def log_execution(...): ...         # Ausführung protokollieren
    def get_executions(filter): ...     # Gefilterte Abfrage
    def get_execution_by_id(id): ...    # Einzelne Ausführung
    def mark_as_retried(id): ...        # Als wiederholt markieren
```

**Evidenz:** `app.py:975-1160`

### TriggerEngine

```python
class TriggerEngine:
    """Evaluiert Trigger-Bedingungen und führt Aktionen aus."""
    
    def evaluate_and_execute(employer_cfg, diff, current_data, executed_by): ...
    def _process_added_employees(): ...      # Neue Mitarbeiter
    def _process_removed_employees(): ...    # Entfernte Mitarbeiter
    def _process_changed_employees(): ...    # Geänderte Mitarbeiter
    def _check_condition(condition, changes): ... # Bedingungsprüfung
    def _build_context(): ...                # Template-Kontext erstellen
    def _execute_action(): ...               # Aktion ausführen
    def retry_execution(execution_id): ...   # Wiederholung
```

**Evidenz:** `app.py:1164-1600`

### EmailAction / APIAction

```python
class EmailAction:
    """Sendet E-Mails via SMTP mit Template-Rendering."""
    def execute(config, context, smtp_config): ...

class APIAction:
    """Führt HTTP-Requests an externe APIs aus."""
    def execute(config, context): ...  # Unterstützt GET, POST, PUT, PATCH, DELETE
```

**Evidenz:** `app.py:1602-1835`

### BaseProvider (ABC)

```python
class BaseProvider(ABC):
    """Abstrakte Basisklasse für alle HR-Provider."""
    
    def __init__(access_key, secret_key, slug): ...
    
    @abstractmethod
    def list_employees(only_active) -> tuple[list, list]: ...
    
    @abstractmethod
    def get_employee_details(employee_id) -> tuple[dict, dict]: ...
```

**Evidenz:** `app.py:1837-1887`

### HRworksProvider

```python
class HRworksProvider(BaseProvider):
    """Provider für HRworks API v2."""
    
    API_BASE_URL = "https://api.hrworks.de/v2"
    DEMO_API_BASE_URL = "https://api.demo-hrworks.de/v2"
    
    def __init__(access_key, secret_key, is_demo=False): ...
    def _authenticate(): ...                    # Bearer Token holen
    def _get_all_persons(only_active): ...     # Paginierte Abfrage
    def list_employees(only_active): ...        # Normalisierte Liste
    def get_employee_details(employee_id): ...  # Einzelne Details
    def _normalize_employee_details(raw): ...   # Normalisierung
```

**Evidenz:** `app.py:1889-2141`

### PersonioProvider

```python
class PersonioProvider(BaseProvider):
    """Provider für Personio API v1."""
    
    PERSONIO_API_BASE_URL = "https://api.personio.de/v1"
    KEY_TO_LABEL_MAP = { ... }  # Dynamische Feld-Labels
    KEY_TO_GROUP_MAP = { ... }  # Detail-Gruppierung
    
    def __init__(access_key, secret_key): ...
    def _authenticate(): ...
    def list_employees(only_active): ...
    def get_employee_details(employee_id): ...
    def _normalize_employee(raw): ...
```

**Evidenz:** `app.py:2186-2360`

### ProviderFactory

```python
class ProviderFactory:
    """Factory zum Erstellen von Provider-Instanzen."""
    
    @staticmethod
    def create(employer_cfg) -> BaseProvider:
        # Liest provider_key aus employer_cfg
        # Erstellt passende Provider-Instanz
```

**Evidenz:** `app.py:2363-2390`

---

## Templates-Übersicht

| Template | Extends | Beschreibung |
|----------|---------|--------------|
| `base.html` | - | Basis-Layout (Header, Footer, Theme) |
| `index.html` | base | Arbeitgeber-Liste |
| `login.html` | base | Anmeldung |
| `add_employer.html` | base | Arbeitgeber hinzufügen (dynamisches Formular) |
| `employer_dashboard.html` | base | Mitarbeiter-Liste mit Tabs |
| `employee_detail.html` | base | Mitarbeiter-Detailansicht |
| `statistics.html` | base | Statistik-Dashboard (Standard/Langzeit) |
| `exports.html` | base | Export-Verwaltung mit Diff-Panel |
| `snapshot_comparison.html` | base | Snapshot-Vergleich |
| `settings.html` | base | Master-Einstellungen |
| `user_settings.html` | base | Benutzer-Einstellungen |
| `employer_settings.html` | base | Arbeitgeber-Einstellungen |
| `employer_triggers.html` | base | AG-spezifische Trigger-Einstellungen |
| `triggers.html` | base | Trigger-Übersicht (Master) |
| `trigger_form.html` | base | Trigger erstellen/bearbeiten |
| `trigger_log.html` | base | Ausführungsprotokoll |
| `smtp_settings.html` | base | SMTP-Konfiguration |
| `styleguide.html` | base | Design-System-Dokumentation |

**Evidenz:** `acencia_hub/templates/`

---

## CSS-Struktur

### tokens.css (Design-Token)

| Kategorie | Beispiele |
|-----------|-----------|
| Primary Colors | `--color-primary-900`, `--color-primary-400`, `--color-primary-50` |
| Accent Colors | `--color-accent`, `--color-accent-50` |
| Neutral Colors | `--color-neutral-900` bis `--color-neutral-50` |
| Semantic Colors | `--color-text-primary`, `--color-bg-body`, `--color-border` |
| Typography | `--font-display`, `--font-body`, `--font-weight-*` |
| Spacing | `--space-1` (4px) bis `--space-10` (64px) |
| Radii | `--radius-sm`, `--radius-base`, `--radius-lg` |
| Shadows | `--shadow-sm`, `--shadow-md`, `--shadow-lg` |
| Motion | `--duration-fast`, `--ease-out` |

### Dark-Theme Override

```css
[data-theme="dark"] {
    --color-text-primary: var(--color-neutral-100);
    --color-bg-body: #0a1929;
    --color-bg-surface: var(--color-primary-900);
    ...
}
```

**Evidenz:** `static/css/tokens.css:124-137`

---

## Test-Struktur

```
tests/
├── __init__.py         # Paket-Initialisierung
├── conftest.py         # pytest Fixtures (app, client, etc.)
├── test_auth.py        # Authentifizierungs-Tests
└── test_security.py    # Security-spezifische Tests
```

**Evidenz:** `ACENCIA_API_Hub/tests/`, `Sicherheit/Umsetzung/00_INDEX.md:77-80`

---

## Ignorierte Ordner

Folgende Ordner werden von Git/Analyse ausgeschlossen:

| Ordner | Grund |
|--------|-------|
| `venv/` | Virtuelle Umgebung |
| `__pycache__/` | Python-Bytecode |
| `acencia_hub/_history/` | Dynamisch generiert, sensible Daten |
| `acencia_hub/_snapshots/` | Dynamisch generiert, sensible Daten |
| `acencia_hub/exports/` | Dynamisch generiert |
| `acencia_hub/data/` | Sensible Konfiguration |
| `*.log` | Log-Dateien |

**Evidenz:** `.gitignore`

---

**Letzte Aktualisierung:** 29.01.2026
