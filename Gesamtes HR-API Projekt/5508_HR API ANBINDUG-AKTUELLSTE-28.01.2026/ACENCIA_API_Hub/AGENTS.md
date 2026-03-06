# Agent Instructions for Acencia Hub

**Agent's Responsibility:** This document is the single source of truth for agent collaboration on this project. With every new feature, bug fix, or refactor, you **must** update this document to reflect the changes. Add new sections for new features and update existing sections if their logic changes. This ensures that all agents have the most current information.

---

This document provides guidance for AI agents working on the Acencia Hub project.

## Project Overview

Acencia Hub is a Flask-based web application that connects to various HR provider APIs (like Personio and HRworks) to fetch employee data. It serves as a central dashboard to view employee information, see statistics, generate data exports, and compare historical data snapshots.

## Core Implementation Details

### 1. Provider Abstraction

- The application uses a `BaseProvider` abstract class to define a common interface for all HR providers.
- A `ProviderFactory` is used to instantiate the correct provider class based on the `provider_key` stored in the `employers.json` configuration file.
- When adding a new provider, ensure it inherits from `BaseProvider` and implements the required methods.

### 2. HRworks Provider (`HRworksProvider`)

This provider has been through several iterations. The current, correct implementation is based on the following principles:

- **Authentication:**
    - **Endpoint:** `POST /v2/authentication`
    - **Host (Demo):** `https://api.demo-hrworks.de`
    - **Host (Production):** `https://api.hrworks.de`
    - **Payload:** A JSON body with `{"accessKey": "...", "secretAccessKey": "..."}`. Note the exact camelCase of `secretAccessKey`.
    - **Token:** The response contains a `token` which is used as a `Bearer` token in subsequent requests.

- **Data Fetching:**
    - **Employee List:** `GET /v2/persons/master-data`. This endpoint returns a comprehensive list of all persons with their details.
    - **Employee Detail:** `GET /v2/persons/master-data/{id}`. This should be tried first. If it fails, fall back to searching the full list.
    - **Pagination:** The API uses a `Link` header with `rel="next"` for pagination. The implementation must parse this header to retrieve all pages.
    - **Headers:** All `GET` requests should include `{"Authorization": "Bearer <token>", "Accept": "application/json"}`.

### 3. Delta Export & Snapshots

The delta export functionality is critical and relies on a robust snapshotting system.

-   **SCS Headers:** The export file must have a fixed list of headers in a specific order. This list is defined as the `SCS_HEADERS` constant at the top of `app.py`. Do not generate headers dynamically.
-   **Data Mapping (`_map_to_scs_schema`):** The mapping function must be robust. It should be able to handle data from different providers, which may have either a nested `details` object or a flat structure. The `_getv` helper function is designed for this purpose and should be used to access data, providing fallbacks for different possible key names (e.g., `lastName` or `Nachname`). The function now accepts a `provider_key` to handle provider-specific logic.
-   **Provider-Specific Logic:**
    -   **Personio:** For the email field, the logic prefers the "Persönliche E-Mail" and falls back to the work email if it's not present. Mappings for fields like "Festgehalt", "Mobilnummer", "Arbeitsplatz", "Personalnummer", and "Lohnsteuerklasse" are now correctly handled by looking up their respective labels in the `details` object.
    -   **HRworks:** The provider's normalization logic now replaces missing date values with empty strings instead of `"-"`. The mapping function also cleans up "n/a" values in address fields, replacing them with empty strings.
-   **Snapshotting:** The delta logic relies on creating a snapshot of the data. When `generate_delta_scs_export` is called, it compares the current data against the `...-latest.json` snapshot. It then creates a new dated snapshot (`{safe_emp_name}-{provider_key}-%Y%m%d-%H%M%S.json`) and overwrites the `latest` one.
-   **Snapshot Format:** Each snapshot is a JSON file containing a dictionary where keys are unique employee IDs. The value for each employee is another dictionary containing a `hash` of the employee's data, a `flat` version of their data, and a `core` version mapped to the SCS schema.
-   **File Paths:** All data paths (`exports`, `_snapshots`, `_history`) **must** be bound to `app.root_path` to ensure they are always created relative to the application's root folder, not the current working directory.

### 4. Snapshot Management & Comparison

A dedicated UI exists for managing and comparing snapshots under the "Snapshots" tab.

-   **Route:** `/employer/<employer_id>/snapshots`
-   **Template:** `snapshot_comparison.html`
-   **Snapshot Listing:** The backend logic in the `snapshot_comparison` route scans the `_snapshots` directory, filters out the `latest` file, sorts the remaining files by date, and marks the most recent one with `(Neuster)`.
-   **Comparison Logic (`compare_snapshots` route):**
    -   **Directional Comparison:** A toggle button on the frontend controls the comparison direction ('forward' or 'backward'). The backend automatically sorts the two selected snapshots by their timestamps to ensure the comparison is always OLD vs. NEW (forward) or NEW vs. OLD (backward), depending on the toggle.
    -   **Diff Generation:** The `_compare_snapshots` function calculates the diff. It identifies added, removed, and changed employees.
    -   **Readability Post-Processing:** The `compare_snapshots` route contains important post-processing logic. It detects if a changed value is a JSON string (typically from a list of complex objects) and "unpacks" it into a more granular, readable, field-by-field comparison. This is crucial for usability.
    -   **Presentation Helpers:** The template (`snapshot_comparison.html`) contains Jinja2 filters to further improve presentation, such as splitting field names (`field.split('::')[-1]`) and replacing `None` with `kein Wert`.

### 5. General Coding Conventions

- When modifying existing functionality, especially the providers or the export logic, refer to the existing robust patterns (`_getv`, `_get_from_path`).
- Do not add new instance variables (like `self._persons_cache`) to providers unless absolutely necessary. The current pattern fetches data on demand.
- Ensure any new provider implementations are correctly handled in the `ProviderFactory`.

### 6. Local Hosting with `Start.bat`

To simplify local hosting for testing and demonstration on a local area network (LAN), a `Start.bat` script has been added. This script provides a "one-click" method to run the application.

-   **Functionality:** The script automates the following steps:
    1.  Activates the Python virtual environment (`venv`).
    2.  Installs or updates all dependencies from `requirements.txt`.
    3.  Detects and displays the machine's local IP addresses.
    4.  Launches the application using the `waitress` WSGI server.
-   **Server:** `waitress` is used instead of Flask's built-in development server. It is a production-quality server that is more robust and suitable for network access.
-   **Network Access:** The server is bound to `0.0.0.0:5001`, making it accessible from other devices on the same network via the IP addresses displayed by the script.
-   **Usage:** Simply run `Start.bat`. A virtual environment named `venv` must exist in the project root.

### 7. Employer Settings

A new "Einstellungen" (Settings) tab has been added to the employer view to manage employer-specific data.

-   **Route:** `/employer/<employer_id>/settings` (handles both `GET` and `POST`)
-   **Template:** `acencia_hub/templates/employer_settings.html`
-   **Functionality:** This page provides a form to view and edit data points for an employer, such as their address (street, zip, city, country), contact details (email, phone, fax), and a comment field.
-   **Data Persistence:**
    -   The data is stored directly in the `employers.json` file for the corresponding employer.
    -   The `EmployerStore` class now has an `update(employer_id, data)` method that merges the updated fields into the existing employer object.
-   **Integration:** The data from this form is used in the "Delta SCS Export." The `generate_delta_scs_export` function reads these values from the employer's configuration object. It's crucial that the keys used in the settings form (`street`, `zip_code`, `city`, `country`, `email`, `phone`, `fax`, `comment`) match what the export function expects.
-   **Navigation:** The link to the settings page has been activated in the tab navigation bar across all relevant employer-view templates (`employer_dashboard.html`, `statistics.html`, etc.).

### 8. UI & Design System

A complete visual overhaul has been implemented. All frontend components are now built using a consistent design system based on design tokens.

-   **Design Tokens (`tokens.css`):**
    -   All colors, fonts, spacing, radii, and shadows are defined as CSS variables in `acencia_hub/static/css/tokens.css`.
    -   **Rule:** You **must not** use hardcoded values (e.g., `#fff`, `16px`, `blue`) in the CSS. Always use a design token (e.g., `var(--color-white)`, `var(--space-4)`, `var(--color-primary-900)`).
    -   Refer to the `tokens.css` file for a full list of available tokens.

-   **Component Styles (`style.css`):**
    -   The main stylesheet is `acencia_hub/static/css/style.css`. It contains a CSS reset and styles for all major UI components (cards, buttons, forms, tables, etc.).
    -   When modifying styles, find the appropriate component section and make your changes there.

-   **Dark/Light Mode:**
    -   The application supports both light (default) and dark themes. The theme is toggled via a switch in the header and is session-based.
    -   The theming works by applying a `data-theme="dark"` attribute to the `<body>` tag.
    -   Dark theme colors are defined as overrides in `tokens.css` under the `[data-theme="dark"]` selector.
    -   **Rule:** Any new or modified component **must** be tested in both light and dark modes to ensure it is legible and visually correct.

-   **Styleguide (`/styleguide`):**
    -   A live styleguide is available at the `/styleguide` route when the application is running.
    -   **Rule:** Before building a new UI element, you **must** check the styleguide to see if an existing component can be used. If you create a major new reusable component, you must add it to the `styleguide.html` template.

-   **Language:**
    -   All user-facing text in the templates must be in **German**.

By adhering to this token-based system, we ensure the UI remains consistent, maintainable, and easy to extend.

### 9. Refined Delta Export UI & Past Exports

The user interface and experience for the Delta SCS Export feature have been significantly enhanced. The previous synchronous download link has been replaced with an asynchronous, API-driven workflow that provides more feedback to the user.

-   **Asynchronous Flow:**
    -   The "Delta-SCS-Export generieren" button in `exports.html` no longer triggers a direct download. Instead, it makes a `fetch` request to a new API endpoint: `/api/employer/<employer_id>/export/delta_scs`.
    -   This endpoint returns a JSON response indicating the outcome: `status: 'success'`, `status: 'no_changes'`, or `status: 'error'`.

-   **Dynamic UI Feedback:**
    -   Based on the API response, the frontend displays temporary notifications (toasts).
    -   A successful export shows a "SCS-Export wurde generiert" message and programmatically triggers the file download.
    -   If no changes are detected, a "Keine neuen Mitarbeiter..." message is shown.
    -   This logic is handled by the JavaScript within `acencia_hub/templates/exports.html`.

-   **"Änderungen anzeigen" Preview Panel:**
    -   On success, the notification includes an "Änderungen anzeigen" link.
    -   Clicking this link opens a slide-up panel from the bottom of the screen, showing a preview of the new and changed employees included in the export.
    -   The panel's structure is defined in `exports.html` and styled in `style.css` (`.diff-panel-container`).

-   **Past Exports Feature:**
    -   A new "Vergangene Exporte" section has been added to `exports.html`.
    -   It fetches a list of previously generated delta exports from the new API endpoint `/api/employer/<employer_id>/past_exports`.
    -   The dropdown displays exports formatted as `dd.MM.yyyy__HH:mm`.
    -   The "Herunterladen" button uses the `/download/past_export/<path:filename>` route to serve the selected file.

### 10. Statistics View (Standard & Long-Term)

The Statistics tab provides two distinct modes for analyzing employee data: a "Standard" view based on the current data from the HR provider, and a "Langzeit" (Long-Term) view based on historical snapshots.

-   **Frontend Toggle:** The view is controlled by a toggle switch on the `/employer/<employer_id>/statistics` page. The state is managed by the JavaScript within `statistics.html`.

-   **History Saving:**
    -   As a new archival feature, every raw response from a provider's API is now saved as a timestamped `.json` file in the `/acencia_hub/_history/` directory. This is for raw data backup and is **not** used by the application logic.
    -   The provider methods (`list_employees`, `get_employee_details`) were refactored to return a tuple `(processed_data, raw_data)` to enable this.

-   **Long-Term Analysis Data Source:**
    -   The long-term analysis is powered exclusively by the data in the `_snapshots` directory. It does **not** use the `_history` folder.
    -   **Important:** The snapshot generation process in `generate_delta_scs_export` was enhanced. Each employee record in a snapshot now includes a `dates` object (e.g., `{"join": "2020-01-15", "leave": null}`). This provides a standardized source for join/leave dates. This was achieved by using the `_getv` helper to robustly extract dates from the full employee detail object before it's flattened.

-   **Backend Logic & API:**
    -   `_get_employee_history_from_snapshots()`: This function reads all dated snapshots for an employer, builds a comprehensive timeline for every employee ever recorded, and intelligently determines their effective join and leave dates.
    -   `calculate_long_term_statistics()`: This function consumes the history generated above to calculate metrics like "entries/exits per year" and "average employment duration".
    -   **API Endpoint:** The long-term data is served by the new endpoint: `/api/employer/<employer_id>/long_term_statistics`.

-   **Export Functionality:**
    -   The statistics page now includes export buttons for both views.
    -   `_format_stats_for_export()`: A helper function that formats the statistics dictionaries into a human-readable string for `.txt` file export.
    -   **Export Routes:** The downloads are handled by two new routes:
        -   `/employer/<employer_id>/export/statistics/standard`
        -   `/employer/<employer_id>/export/statistics/longterm`

### 11. Documentation Standards

**IMPORTANT:** All code in this project now follows comprehensive documentation standards:

-   **Complete Docstring Coverage:** Every public function, method, and class has a complete docstring explaining its purpose, parameters, and return values.
-   **German Documentation:** All docstrings are written in German to match the application's language.
-   **Google Style Docstrings:** The project follows Google-style docstring conventions for consistency.
-   **Type Hints:** All functions use proper type hints for better code quality and IDE support.

**When adding new code:**
-   **MUST:** Add complete docstrings to all public functions and classes
-   **MUST:** Use German language for all docstrings
-   **MUST:** Include parameter descriptions and return value descriptions
-   **MUST:** Use proper type hints
-   **MUST:** Follow the existing naming conventions

**Example docstring format:**
```python
def example_function(param1: str, param2: int) -> dict:
    """
    Kurze Beschreibung der Funktion.
    
    Args:
        param1 (str): Beschreibung des ersten Parameters
        param2 (int): Beschreibung des zweiten Parameters
    
    Returns:
        dict: Beschreibung des Rückgabewerts
    
    Raises:
        ValueError: Beschreibung wann dieser Fehler auftritt
    """
```

### 12. File Structure & Organization

The project follows a clear structure:

```
acencia_hub/
├── __init__.py          # Module documentation and metadata
├── app.py              # Main application with all routes, classes, and logic
├── updater.py          # Automatic update functionality
├── data/               # User and configuration data
│   ├── users.json      # User database
│   ├── secrets.json    # Secrets (GitHub PAT, etc.)
│   └── force_logout.txt # Forced logout mechanism
├── static/             # Static files
│   └── css/           # Stylesheets with design token system
├── templates/          # Jinja2 templates
├── _snapshots/        # Automatically created data snapshots
├── _history/          # Raw data backup of API responses
└── exports/           # Generated export files
```

**Key Files:**
-   `app.py`: Contains all Flask routes, provider classes, business logic, and helper functions
-   `updater.py`: Handles automatic updates from GitHub
-   `__init__.py`: Module documentation and version information

### 13. Error Handling & Logging

The application includes comprehensive error handling and logging:

-   **Custom Logging System:** `custom_log()` function for consistent logging with colors and file output
-   **Error Handling:** Try-catch blocks around all critical operations
-   **User Feedback:** Flash messages for user-facing errors
-   **API Error Responses:** Proper HTTP status codes and JSON error messages
-   **Log File:** All logs are written to `server.log` in the project root

### 14. Security Considerations

-   **Password Hashing:** Uses Werkzeug's secure password hashing
-   **Session Management:** Secure session handling with forced logout capability
-   **Master User System:** Hierarchical user permissions
-   **Input Validation:** Form validation and sanitization
-   **File Path Security:** Safe file operations with path validation

### 15. Performance Considerations

-   **Singleton Pattern:** EmployerStore uses singleton pattern for efficient data access
-   **Lazy Loading:** Provider data is fetched on demand
-   **Caching:** Bearer tokens are cached to avoid repeated authentication
-   **Pagination:** HRworks API pagination is properly handled
-   **Background Processing:** Heavy operations are designed to not block the UI

### 16. Trigger-System (NEU)

Das Trigger-System ermöglicht automatisierte Aktionen basierend auf Mitarbeiterdaten-Änderungen.

#### Architektur

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Trigger-System                                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────────┐  │
│  │TriggerStore │    │TriggerEngine│    │  Aktionen               │  │
│  │(Singleton)  │───►│             │───►│  ├── EmailAction        │  │
│  │             │    │             │    │  └── APIAction          │  │
│  └─────────────┘    └─────────────┘    └─────────────────────────┘  │
│        │                  │                        │                 │
│        │                  │                        │                 │
│        ▼                  ▼                        ▼                 │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────────┐  │
│  │triggers.json│    │Delta-Export │    │TriggerLogStore          │  │
│  │(Konfig)     │    │(Auslöser)   │    │(Protokoll)              │  │
│  └─────────────┘    └─────────────┘    └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

#### Komponenten

-   **TriggerStore** (`app.py`, Zeile ~650):
    -   Singleton-Klasse für Trigger-Konfiguration
    -   Speichert in `data/triggers.json`
    -   Verwaltet SMTP-Konfiguration (global)
    -   CRUD-Operationen für Trigger
    -   Verschlüsselt sensible Daten (Passwörter, Tokens)

-   **TriggerLogStore** (`app.py`, Zeile ~1050):
    -   Protokolliert alle Trigger-Ausführungen
    -   Speichert in `data/trigger_log.json`
    -   Unterstützt Filterung und Pagination

-   **TriggerEngine** (`app.py`, Zeile ~1165):
    -   Wird bei Delta-Export aufgerufen
    -   Evaluiert Trigger-Bedingungen
    -   Führt Aktionen aus (Email, API)
    -   Unterstützt AND/OR-Logik für Bedingungen

-   **EmailAction** (`app.py`, Zeile ~1600):
    -   Sendet E-Mails via konfiguriertem SMTP
    -   Mustache-Template-Rendering für dynamische Inhalte
    -   Option: Einzelne E-Mail pro Mitarbeiter oder Sammel-E-Mail

-   **APIAction** (`app.py`, Zeile ~1745):
    -   HTTP-Requests an externe APIs
    -   Unterstützt: GET, POST, PUT, PATCH, DELETE
    -   Auth: None, Bearer, Basic, API-Key

#### Datenmodell

**triggers.json:**
```json
{
  "smtp_config": {
    "host": "smtp.example.com",
    "port": 587,
    "username": "user@example.com",
    "password": "ENC:...",
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
        "config": {
          "recipients": ["hr@example.com"],
          "subject": "Mitarbeiter {{Vorname}} {{Name}} inaktiv",
          "body": "...",
          "send_individual": true
        }
      },
      "excluded_employers": []
    }
  ]
}
```

#### Events und Operatoren

**Events:**
-   `employee_changed` - Mitarbeiterdaten geändert
-   `employee_added` - Neuer Mitarbeiter
-   `employee_removed` - Mitarbeiter entfernt

**Operatoren:**
-   `changed` - Feld hat sich geändert
-   `changed_to` - Feld hat neuen Wert X
-   `changed_from` - Feld hatte alten Wert X
-   `changed_from_to` - Feld änderte von X zu Y
-   `is_empty` - Feld ist jetzt leer
-   `is_not_empty` - Feld ist jetzt nicht leer
-   `contains` - Neuer Wert enthält Substring

#### Template-Variablen

In E-Mail und API-Body verfügbar:
-   `{{Vorname}}`, `{{Name}}`, `{{Email}}`, etc. (alle SCS_HEADERS)
-   `{{_changedField}}` - Name des geänderten Feldes
-   `{{_oldValue}}`, `{{_newValue}}` - Alte/neue Werte
-   `{{_employerName}}`, `{{_employerId}}` - Arbeitgeber-Daten
-   `{{_timestamp}}` - Zeitstempel
-   `{{#_employees}}...{{/_employees}}` - Iteration bei Sammel-Aktion

#### UI-Routen

| Route | Beschreibung |
|-------|-------------|
| `/settings/triggers` | Trigger-Übersicht |
| `/settings/triggers/new` | Neuer Trigger |
| `/settings/triggers/<id>/edit` | Trigger bearbeiten |
| `/settings/smtp` | SMTP-Konfiguration |
| `/settings/trigger-log` | Ausführungsprotokoll |
| `/employer/<id>/triggers` | Arbeitgeber-spezifische Trigger |

#### Wichtige Hinweise

-   Trigger werden nur bei Delta-Export ausgewertet (nicht bei normalem Datenabruf)
-   Nur Master-Benutzer können Trigger erstellen/bearbeiten
-   SMTP-Passwort und API-Tokens werden verschlüsselt gespeichert
-   Bei Hostnamen mit Umlauten wird `localhost` als SMTP-EHLO verwendet

---

## Aktueller Stand (28.01.2026)

### Implementierte Features ✅
- **Arbeitgeber-Verwaltung**: Multi-Mandanten-System mit Provider-Konfiguration
- **Provider-Integrationen**: Personio, HRworks (vollständig), SageHR (Mock)
- **Mitarbeiter-Management**: Übersicht, Detailansicht, Status-Filter
- **Statistiken**: Standard- und Langzeit-Analyse mit Export
- **Export-System**: Standard-XLSX, Delta-SCS-Export mit Diff-Anzeige
- **Snapshot-Management**: Automatische Snapshots, Vergleich, History
- **Benutzerverwaltung**: Multi-User mit Master-Rechten, Themes
- **Automatische Updates**: GitHub-Integration mit PAT
- **Design-System**: Token-basiertes CSS, Hell/Dunkel-Modus
- **Logging**: Umfassende Protokollierung in `server.log`
- **Trigger-System** (NEU): Automatisierte E-Mail/API-Aktionen bei Datenänderungen
  - Konfigurierbares Event-System (employee_changed, added, removed)
  - E-Mail-Versand mit Mustache-Templates
  - API-Aufrufe mit Auth (Bearer, Basic, API-Key)
  - Ausführungsprotokoll mit Retry-Funktion
  - Arbeitgeber-spezifische Ausschlüsse
  - Option: Einzelne E-Mail pro Mitarbeiter

### Bekannte Einschränkungen / Tech Debt
- `app.py` ist sehr groß (~5300 Zeilen) - könnte in Module aufgeteilt werden
- SageHR-Provider ist nur ein Mock
- Begrenzte Unit-Tests vorhanden (nur Auth und Security)
- Keine automatische Snapshot-Bereinigung (alte Snapshots werden nicht gelöscht)

### Letzte Änderungen (28.01.2026)
- **Trigger-System implementiert**: Vollständige Event-basierte Automatisierung
- **SMTP-Bug behoben**: Windows-Computernamen mit Umlauten werden korrekt behandelt
- **Trigger-Bedingungen stabilisiert**: None-Werte in Vergleichen werden korrekt behandelt
- **Status-Feld hinzugefügt**: "Aktiv/Inaktiv" als triggerbares SCS-Feld
- **Einzelne E-Mails pro Mitarbeiter**: Option für individuellen Versand

### Behobene Bugs (28.01.2026)
| Bug-ID | Beschreibung | Fix |
|--------|-------------|-----|
| BUG-0001 | SMTP EHLO mit Umlaut im Hostname | `local_hostname='localhost'` Fallback |
| BUG-0002 | NoneType bei `contains`-Operator | Null-Check vor `.lower()` |
| BUG-0003 | `str(None)` → "None" statt "" | `safe_str()` Helper-Funktion |

Dokumentation: `./Bugs/` Ordner

## Tasks / Roadmap

### Hohe Priorität
1. **Unit-Tests erweitern** - Trigger-System, Provider-Klassen, Export-Logik
2. **app.py aufteilen** - In separate Module (routes.py, providers.py, triggers.py, utils.py)
3. **Snapshot-Bereinigung** - Alte Snapshots automatisch nach X Tagen löschen

### Mittlere Priorität
4. **SageHR-Provider implementieren** - Echte API-Anbindung statt Mock
5. **Trigger-Vorschau** - Test-Modus vor Live-Aktivierung
6. **Performance-Optimierung** - Caching für API-Aufrufe

### Niedrige Priorität
7. **API-Dokumentation** - OpenAPI/Swagger-Spec erstellen
8. **Docker-Support** - Dockerfile für Container-Deployment
9. **Trigger-Templates** - Vordefinierte Trigger-Vorlagen

---

**Last Updated:** 28.01.2026  
**Version:** 1.1.0 (Trigger-System)  
**Maintainer:** Acencia Team