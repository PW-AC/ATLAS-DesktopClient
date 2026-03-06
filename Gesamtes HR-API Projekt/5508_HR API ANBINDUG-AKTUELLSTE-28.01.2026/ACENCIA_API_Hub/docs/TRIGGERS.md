# Trigger-System - Technische Dokumentation

## Übersicht

Das Trigger-System ermöglicht automatisierte Aktionen bei Änderungen an Mitarbeiterdaten. Es wird beim Delta-Export ausgewertet und basiert auf den normalisierten SCS-Feldern für Provider-Unabhängigkeit.

## Architektur

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Trigger-System Architektur                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────┐                                                        │
│  │  Delta-Export    │  Auslöser: generate_delta_scs_export()                │
│  │  (app.py)        │                                                        │
│  └────────┬─────────┘                                                        │
│           │                                                                  │
│           ▼                                                                  │
│  ┌──────────────────┐     ┌──────────────────┐                              │
│  │  TriggerEngine   │────►│  TriggerStore    │ (Singleton)                  │
│  │  (Zeile 1164)    │     │  (Zeile 624)     │                              │
│  └────────┬─────────┘     └────────┬─────────┘                              │
│           │                        │                                         │
│           │                        ▼                                         │
│           │               ┌──────────────────┐                              │
│           │               │  triggers.json   │ (Konfiguration)              │
│           │               └──────────────────┘                              │
│           │                                                                  │
│           ├────────────────────┬────────────────────┐                       │
│           ▼                    ▼                    ▼                        │
│  ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐            │
│  │  EmailAction     │ │  APIAction       │ │  TriggerLogStore │            │
│  │  (Zeile 1602)    │ │  (Zeile 1742)    │ │  (Zeile 975)     │            │
│  └────────┬─────────┘ └────────┬─────────┘ └────────┬─────────┘            │
│           │                    │                    │                        │
│           ▼                    ▼                    ▼                        │
│      SMTP-Server          Ext. API           trigger_log.json               │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Klassen-Referenz

### TriggerStore (Zeile 624-973)

**Zweck:** Singleton zur Verwaltung der Trigger-Konfiguration und SMTP-Einstellungen.

**Datei:** `data/triggers.json`

**Konstanten:**
```python
TRIGGER_EVENTS = ['employee_changed', 'employee_added', 'employee_removed']
CONDITION_OPERATORS = ['changed', 'changed_to', 'changed_from', 'changed_from_to', 'is_empty', 'is_not_empty', 'contains']
ACTION_TYPES = ['email', 'api']
```

**Wichtige Methoden:**

| Methode | Beschreibung |
|---------|-------------|
| `get_smtp_config()` | Gibt SMTP-Konfiguration zurück (entschlüsselt) |
| `update_smtp_config(config)` | Speichert SMTP-Konfiguration (verschlüsselt) |
| `get_all_triggers()` | Gibt alle Trigger zurück |
| `get_active_triggers()` | Gibt nur aktivierte Trigger zurück |
| `get_triggers_for_employer(employer_id)` | Aktive Trigger ohne Ausschluss für AG |
| `get_trigger_by_id(trigger_id)` | Einzelnen Trigger abrufen |
| `create_trigger(trigger_data)` | Neuen Trigger erstellen |
| `update_trigger(trigger_id, trigger_data)` | Trigger aktualisieren |
| `delete_trigger(trigger_id)` | Trigger löschen |
| `toggle_trigger(trigger_id)` | Trigger aktivieren/deaktivieren |
| `exclude_employer(trigger_id, employer_id)` | AG von Trigger ausschließen |
| `include_employer(trigger_id, employer_id)` | AG-Ausschluss aufheben |
| `update_statistics(trigger_id, success)` | Ausführungsstatistik aktualisieren |

**Sicherheit:**
- SMTP-Passwort wird mit Fernet verschlüsselt gespeichert
- API-Tokens und -Passwörter in Triggern werden verschlüsselt
- Verwendet `encrypt_credential()` / `decrypt_credential()` aus dem bestehenden System

---

### TriggerLogStore (Zeile 975-1162)

**Zweck:** Singleton zur Verwaltung des Trigger-Ausführungsprotokolls.

**Datei:** `data/trigger_log.json`

**Wichtige Methoden:**

| Methode | Beschreibung |
|---------|-------------|
| `log_execution(...)` | Protokolliert eine Ausführung |
| `get_executions(filter)` | Gefilterte Ausführungen abrufen |
| `get_execution_by_id(id)` | Einzelne Ausführung abrufen |
| `mark_as_retried(id)` | Ausführung als wiederholt markieren |

**Filter-Parameter für `get_executions()`:**
- `employer_id` - Nach Arbeitgeber
- `trigger_id` - Nach Trigger
- `status` - success/error/skipped
- `from_date` / `to_date` - Zeitraum (ISO-Format)
- `limit` / `offset` - Pagination

**Log-Entry Struktur:**
```json
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
  "can_retry": true,
  "retry_of": null
}
```

---

### TriggerEngine (Zeile 1164-1597)

**Zweck:** Evaluiert Trigger-Bedingungen und führt Aktionen aus.

**Hauptmethode:**
```python
def evaluate_and_execute(self, employer_cfg, diff, current_data, executed_by='system'):
    """
    Wird von generate_delta_scs_export() aufgerufen.
    
    Args:
        employer_cfg: Arbeitgeber-Konfiguration aus employers.json
        diff: Dict mit 'added', 'removed', 'changed' Listen
        current_data: Aktuelle Mitarbeiterdaten (pid -> data)
        executed_by: Benutzername für Protokollierung
    
    Returns:
        list: Ausführungsergebnisse
    """
```

**Interne Methoden:**

| Methode | Beschreibung |
|---------|-------------|
| `_process_added_employees()` | Verarbeitet neue Mitarbeiter |
| `_process_removed_employees()` | Verarbeitet entfernte Mitarbeiter |
| `_process_changed_employees()` | Verarbeitet geänderte Mitarbeiter + Bedingungsprüfung |
| `_check_condition()` | Prüft einzelne Bedingung gegen Änderungen |
| `_build_context()` | Erstellt Template-Kontext für Aktionen |
| `_execute_action()` | Delegiert an EmailAction/APIAction |
| `retry_execution()` | Wiederholt fehlgeschlagene Ausführung |

**Bedingungslogik (`_check_condition`):**
```python
def _check_condition(self, condition, changes):
    """
    Prüft ob eine Bedingung durch die Änderungen erfüllt ist.
    
    Operatoren:
    - changed: Feld hat sich geändert
    - changed_to: Neuer Wert == to_value
    - changed_from: Alter Wert == from_value
    - changed_from_to: Alter Wert == from_value AND Neuer Wert == to_value
    - is_empty: Neuer Wert ist leer
    - is_not_empty: Neuer Wert ist nicht leer
    - contains: Neuer Wert enthält to_value (case-insensitive)
    """
```

**Option: Einzelne Aktion pro Mitarbeiter:**
```python
send_individual = action_config.get('send_individual', True)
if send_individual and len(affected_employees) > 1:
    # Für jeden Mitarbeiter separate Aktion ausführen
    for emp in affected_employees:
        # ... einzelne Ausführung
else:
    # Sammel-Aktion für alle Mitarbeiter
```

---

### EmailAction (Zeile 1602-1740)

**Zweck:** Sendet E-Mails via SMTP mit Template-Rendering.

**Methode:**
```python
def execute(self, config, context, smtp_config):
    """
    Args:
        config: {recipients, subject, body, send_individual}
        context: Template-Variablen
        smtp_config: SMTP-Server-Konfiguration
    
    Returns:
        tuple: (success, details, error_message)
    """
```

**Template-Rendering:**
- Verwendet `chevron` für Mustache-Syntax (falls installiert)
- Fallback: Einfache `{{variable}}`-Ersetzung
- Unterstützt Listen-Iteration: `{{#_employees}}...{{/_employees}}`

**SMTP-Sicherheit:**
- Verwendet `EmailMessage` (moderne Python email API)
- ASCII-sicherer `local_hostname` für EHLO (Bug-Fix für Umlaute im Windows-Hostnamen)
- TLS-Unterstützung (Standard: aktiviert)

---

### APIAction (Zeile 1742-1835)

**Zweck:** Führt HTTP-Requests an externe APIs aus.

**Methode:**
```python
def execute(self, config, context):
    """
    Args:
        config: {url, method, headers, auth, body, timeout_seconds, retry_on_failure}
        context: Template-Variablen für URL/Body-Rendering
    
    Returns:
        tuple: (success, details, error_message)
    """
```

**Unterstützte HTTP-Methoden:** GET, POST, PUT, PATCH, DELETE

**Authentifizierungstypen:**
| Typ | Konfiguration |
|-----|---------------|
| `none` | Keine Authentifizierung |
| `bearer` | `auth.token` als Bearer-Header |
| `basic` | `auth.username` + `auth.password` |
| `api_key` | `auth.api_key` im Header `auth.api_key_header` |

**Body-Handling:**
- Template-Rendering auf Body-String angewendet
- Versucht JSON-Parsing, Fallback auf Raw-String
- `json=` für Dict, `data=` für String

---

## Datenstrukturen

### triggers.json
```json
{
  "smtp_config": {
    "host": "smtp.example.com",
    "port": 587,
    "username": "user@example.com",
    "password": "ENC:gAAA...",
    "from_email": "noreply@example.com",
    "use_tls": true
  },
  "triggers": [
    {
      "id": "uuid",
      "name": "Trigger-Name",
      "enabled": true,
      "trigger_type": "employee",
      "event": "employee_changed",
      "conditions": [
        {
          "field": "Status",
          "operator": "changed_from_to",
          "from_value": "Aktiv",
          "to_value": "Inaktiv"
        }
      ],
      "condition_logic": "AND",
      "action": {
        "type": "email",
        "config": {
          "recipients": ["hr@example.com"],
          "subject": "{{Vorname}} {{Name}} inaktiv",
          "body": "...",
          "send_individual": true
        }
      },
      "excluded_employers": [],
      "statistics": {
        "total_executions": 0,
        "last_execution": null,
        "success_count": 0,
        "error_count": 0
      },
      "created_at": "2026-01-28T10:00:00Z",
      "created_by": "admin"
    }
  ]
}
```

---

## Template-Variablen

### SCS-Felder (alle verfügbar)
```
{{Name}}, {{Vorname}}, {{Geschlecht}}, {{Titel}}, {{Geburtsdatum}},
{{Strasse}}, {{Hausnummer}}, {{PLZ}}, {{Ort}}, {{Land}}, {{Kommentar}},
{{Email}}, {{Telefon}}, {{Personalnummer}}, {{Position}}, {{Firmeneintritt}},
{{Bruttogehalt}}, {{VWL}}, {{geldwerterVorteil}}, {{SteuerfreibetragJahr}},
{{SteuerfreibetragMonat}}, {{SV_Brutto}}, {{Steuerklasse}}, {{Religion}},
{{Kinder}}, {{Abteilung}}, {{Arbeitsplatz}}, {{Arbeitgeber}}, {{Status}}
```

### Meta-Felder
```
{{_changedField}}   - Name des geänderten Feldes
{{_oldValue}}       - Vorheriger Wert
{{_newValue}}       - Neuer Wert
{{_allChanges}}     - Alle Änderungen formatiert
{{_employerId}}     - Arbeitgeber-ID
{{_employerName}}   - Arbeitgeber-Name
{{_triggerName}}    - Trigger-Name
{{_timestamp}}      - Ausführungszeitpunkt
{{_employeeCount}}  - Anzahl betroffener Mitarbeiter
```

### Listen-Iteration (Sammel-Modus)
```
{{#_employees}}
- {{Vorname}} {{Name}}: {{_changedField}}
{{/_employees}}
```

---

## UI-Routen

| Route | Methode | Beschreibung | Berechtigung |
|-------|---------|--------------|--------------|
| `/settings/triggers` | GET | Trigger-Übersicht | Master |
| `/settings/triggers/new` | GET/POST | Neuer Trigger | Master |
| `/settings/triggers/<id>/edit` | GET/POST | Trigger bearbeiten | Master |
| `/settings/triggers/<id>/delete` | POST | Trigger löschen | Master |
| `/settings/triggers/<id>/toggle` | POST | Aktivieren/Deaktivieren | Master |
| `/settings/smtp` | GET/POST | SMTP-Konfiguration | Master |
| `/settings/smtp/test` | POST | Test-E-Mail senden | Master |
| `/settings/trigger-log` | GET | Ausführungsprotokoll | Master |
| `/api/trigger-log` | GET | Log-API (JSON) | Auth |
| `/api/trigger-log/<id>/retry` | POST | Ausführung wiederholen | Master |
| `/api/triggers/fields` | GET | SCS-Felder für UI | Auth |
| `/employer/<id>/triggers` | GET | AG-spezifische Trigger | Auth |
| `/employer/<id>/triggers/<tid>/toggle-exclude` | POST | AG ausschließen/einschließen | Master |

---

## Bekannte Einschränkungen

1. **Trigger werden nur bei Delta-Export ausgewertet** - Nicht bei normalem Datenabruf
2. **Keine zeitbasierten Trigger** - Nur ereignisbasiert
3. **Keine Aggregate-Bedingungen** - Nur Einzelfeld-Prüfungen
4. **chevron optional** - Fallback auf einfache Ersetzung ohne Listen-Support

---

## Behobene Bugs

| Bug | Beschreibung | Fix |
|-----|-------------|-----|
| BUG-0001 | SMTP EHLO mit Umlaut im Windows-Hostname | `local_hostname='localhost'` Fallback |
| BUG-0002 | NoneType bei `contains`-Operator | Null-Check vor `.lower()` |
| BUG-0003 | `str(None)` → "None" statt "" | `safe_str()` Helper |

---

**Letzte Aktualisierung:** 28.01.2026
