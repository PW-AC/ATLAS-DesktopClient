# 03 - Domain und Begriffe

## Zentrale Domänen-Begriffe

Diese Begriffe werden im Code und in der Dokumentation verwendet. Die Definitionen sind aus dem Code abgeleitet, nicht interpretiert.

---

### Arbeitgeber (Employer)

**Definition:** Ein Mandant/Kunde, der HR-Daten in einem externen System (Provider) verwaltet.

| Attribut | Typ | Beschreibung |
|----------|-----|--------------|
| `id` | UUID-String | Eindeutige Kennung |
| `name` | String | Anzeigename |
| `provider_key` | String | Provider-Typ: `personio`, `hrworks`, `sagehr` |
| `api_config` | Object | Provider-spezifische Credentials |
| `address` | Object | Adressdaten für Exporte |
| `email`, `phone`, `fax` | String | Kontaktdaten |
| `comment` | String | Zusätzliche Infos |

**Evidenz:** `app.py:459-614` (EmployerStore), `docs/CONFIGURATION.md:53-86`

---

### Provider

**Definition:** Ein externes HR-System, das über eine API angebunden wird.

| Provider | Klasse | API-Basis | Status |
|----------|--------|-----------|--------|
| Personio | `PersonioProvider` | `https://api.personio.de/v1` | Vollständig |
| HRworks | `HRworksProvider` | `https://api.hrworks.de/v2` | Vollständig |
| HRworks Demo | `HRworksProvider` | `https://api.demo-hrworks.de/v2` | Vollständig |
| SageHR | `SageHrProvider` | - | Mock |

**Evidenz:** `app.py:616-1140`

---

### Mitarbeiter (Employee)

**Definition:** Eine Person, die in einem HR-System eines Arbeitgebers erfasst ist.

**Normalisiertes Format (nach Provider-Abstraktion):**

| Attribut | Typ | Beschreibung |
|----------|-----|--------------|
| `personId` | String | Eindeutige ID im Provider |
| `personnelNumber` | String | Personalnummer |
| `firstName` | String | Vorname |
| `lastName` | String | Nachname |
| `email` | String | E-Mail-Adresse |
| `birthday` | String | Geburtsdatum (DD.MM.YYYY) |
| `gender` | String | Geschlecht |
| `position` | String | Position/Stelle |
| `department` | String | Abteilung |
| `employmentType` | String | Beschäftigungsart |
| `status` | String | Status (`active`, `inactive`) |
| `isActive` | Boolean | Aktiv-Flag |
| `joinDate` | String | Eintrittsdatum |
| `leaveDate` | String | Austrittsdatum (wenn vorhanden) |
| `details` | Object | Gruppierte Detail-Informationen |

**Evidenz:** `app.py:839-919` (HRworks), `app.py:1015-1140` (Personio)

---

### Snapshot

**Definition:** Ein JSON-Abbild aller Mitarbeiterdaten eines Arbeitgebers zu einem bestimmten Zeitpunkt.

**Dateiformat:**
- Datiert: `{ArbeitgeberName}-{provider}-{YYYYMMDD}-{HHMMSS}.json`
- Aktuell: `{ArbeitgeberName}-{provider}-latest.json`

**Struktur:**
```json
{
  "pid-123": {
    "hash": "md5-hash-der-daten",
    "flat": { /* flache Mitarbeiter-Daten */ },
    "core": { /* SCS-Schema-gemappte Daten */ },
    "dates": {
      "join": "2020-01-15",
      "leave": null
    }
  }
}
```

**Evidenz:** `AGENTS.md:47-48`, `app.py:1229-1426`

---

### SCS-Schema (Export-Format)

**Definition:** Ein festes Export-Format für Lohnabrechnung/HR-Systeme mit definierten Spalten.

**Header (in fester Reihenfolge):**
```
Name, Vorname, Geschlecht, Titel, Geburtsdatum,
Strasse, Hausnummer, PLZ, Ort, Land, Kommentar,
Email, Telefon, Personalnummer, Position, Firmeneintritt,
Bruttogehalt, VWL, geldwerterVorteil, SteuerfreibetragJahr, SteuerfreibetragMonat,
SV_Brutto, Steuerklasse, Religion, Kinder, Abteilung, Arbeitsplatz, Arbeitgeber
```

**Evidenz:** `app.py:306-312` (SCS_HEADERS)

---

### Delta-Export

**Definition:** Ein Export, der nur neue und geänderte Mitarbeiter seit dem letzten Snapshot enthält.

**Diff-Kategorien:**
- `added_pids`: Neue Mitarbeiter (nicht im vorherigen Snapshot)
- `changed_pids`: Geänderte Mitarbeiter (Hash unterschiedlich)
- `removed_pids`: Entfernte Mitarbeiter (nicht mehr aktiv)

**Evidenz:** `app.py:1295-1380`, `AGENTS.md:39-49`

---

### Benutzer (User)

**Definition:** Ein Anwender der ACENCIA Hub Anwendung.

| Attribut | Typ | Beschreibung |
|----------|-----|--------------|
| `username` | String | Login-Name |
| `password_hash` | String | scrypt-Hash |
| `kuerzel` | String | Kürzel für Logs (max. 4 Zeichen) |
| `is_master` | Boolean | Master-Rechte |
| `color` | String | Farbe für Logs |
| `theme` | String | `light` oder `dark` |
| `allowed_employers` | Array | Zugewiesene Arbeitgeber-IDs |

**Evidenz:** `docs/CONFIGURATION.md:11-35`, `app.py:1836-1869`

---

### Master-Benutzer

**Definition:** Benutzer mit erweiterten Rechten für System-Verwaltung.

**Zusätzliche Berechtigungen:**
- Benutzerverwaltung (erstellen, löschen, Passwort ändern)
- System-Einstellungen (GitHub PAT)
- Zugriff auf alle Arbeitgeber (keine Einschränkung)
- Log-Einsicht
- Update-Funktion

**Evidenz:** `app.py:1853-1854`, `README.md:171-177`

---

### History (API-Backup)

**Definition:** Rohe, unverarbeitete API-Antworten, die zur Archivierung gespeichert werden.

**Dateiformat:** `{ArbeitgeberName}-{provider}-history-{YYYYMMDD}-{HHMMSS}-{microseconds}.json`

**Hinweis:** Wird NICHT für Anwendungslogik verwendet, nur als Backup.

**Evidenz:** `app.py:427-453` (save_history_entry), `AGENTS.md:155-160`

---

### Design-Token

**Definition:** CSS-Variable für konsistente UI-Gestaltung.

**Kategorien:**
- Farben (Primary, Accent, Neutral, Semantic)
- Typographie (Font-Family, Weights, Line-Height)
- Spacing (space-1 bis space-10)
- Radii (Eckenradien)
- Shadows
- Motion/Transitions

**Evidenz:** `static/css/tokens.css`

---

## Provider-spezifische Begriffe

### Personio

| Begriff | Beschreibung |
|---------|--------------|
| `client_id` | OAuth2 Client-ID |
| `client_secret` | OAuth2 Client-Secret |
| `dynamic_XXXXX` | Benutzerdefinierte Felder |

**Evidenz:** `app.py:973`, `docs/CONFIGURATION.md:93-105`

### HRworks

| Begriff | Beschreibung |
|---------|--------------|
| `accessKey` | API-Zugangsschlüssel |
| `secretAccessKey` | Geheimer API-Schlüssel |
| `use_demo` | Boolean für Demo-Umgebung |
| `organizationUnit` | Abteilungsobjekt |
| `costCenter` | Kostenstelle |

**Evidenz:** `app.py:668-735`, `AGENTS.md:21-35`

---

## Sicherheits-Begriffe

| Begriff | Beschreibung | Evidenz |
|---------|--------------|---------|
| CSRF-Token | Cross-Site Request Forgery Schutz | `app.py:1728-1741` |
| Fernet | Symmetrische Verschlüsselung (cryptography) | `app.py:23-111` |
| scrypt | Passwort-Hashing (Werkzeug) | `app.py:14` |
| Rate-Limiting | Anfragen-Begrenzung | `app.py:1781-1796` |
| Account-Lockout | Temporäre Sperrung nach Fehlversuchen | `app.py:2000-2050` |
| Audit-Log | Protokoll administrativer Aktionen | `app.py:151-188` |
| PII | Personally Identifiable Information | `app.py:199-247` |

---

## Statistik-Begriffe

| Begriff | Beschreibung | Berechnung |
|---------|--------------|------------|
| Fluktuation | Anteil ausgeschiedener Mitarbeiter | (Ausgeschiedene / Aktive) * 100 |
| Tenure | Betriebszugehörigkeit | (Heute - Eintrittsdatum) in Jahren |
| Hiring Age | Eintrittsalter | (Eintrittsdatum - Geburtstag) in Jahren |

**Evidenz:** `app.py:2779-2905`

---

## Trigger-System-Begriffe

### Trigger

**Definition:** Eine konfigurierbare Regel, die bei bestimmten Ereignissen (Events) automatisch Aktionen ausführt.

| Attribut | Typ | Beschreibung |
|----------|-----|--------------|
| `id` | UUID-String | Eindeutige Kennung |
| `name` | String | Anzeigename |
| `enabled` | Boolean | Aktivierungsstatus |
| `trigger_type` | String | Immer `employee` |
| `event` | String | `employee_changed`, `employee_added`, `employee_removed` |
| `conditions` | Array | Liste von Bedingungen |
| `condition_logic` | String | `AND` oder `OR` |
| `action` | Object | Auszuführende Aktion |
| `excluded_employers` | Array | Ausgeschlossene Arbeitgeber-IDs |

**Evidenz:** `app.py:624-973` (TriggerStore), `docs/TRIGGERS.md:255-304`

---

### Trigger-Events

**Definition:** Ereignistypen, die Trigger auslösen können.

| Event | Beschreibung |
|-------|--------------|
| `employee_changed` | Mitarbeiterdaten haben sich geändert |
| `employee_added` | Neuer Mitarbeiter wurde hinzugefügt |
| `employee_removed` | Mitarbeiter wurde entfernt/deaktiviert |

**Evidenz:** `app.py:631` (TRIGGER_EVENTS)

---

### Trigger-Operatoren

**Definition:** Vergleichsoperatoren für Trigger-Bedingungen.

| Operator | Beschreibung |
|----------|--------------|
| `changed` | Feld hat sich geändert (beliebiger Wert) |
| `changed_to` | Feld hat neuen Wert X |
| `changed_from` | Feld hatte vorher Wert X |
| `changed_from_to` | Feld änderte von X zu Y |
| `is_empty` | Feld ist jetzt leer |
| `is_not_empty` | Feld ist jetzt nicht leer |
| `contains` | Neuer Wert enthält Substring |

**Evidenz:** `app.py:632` (CONDITION_OPERATORS), `docs/TRIGGERS.md:161-176`

---

### Trigger-Aktionen

**Definition:** Aktionstypen, die ein Trigger ausführen kann.

| Aktionstyp | Klasse | Beschreibung |
|------------|--------|--------------|
| `email` | `EmailAction` | E-Mail via SMTP senden |
| `api` | `APIAction` | HTTP-Request an externe API |

**Evidenz:** `app.py:1602-1835` (EmailAction, APIAction)

---

### SMTP-Konfiguration

**Definition:** Einstellungen für den E-Mail-Versand bei Trigger-Aktionen.

| Attribut | Typ | Beschreibung |
|----------|-----|--------------|
| `host` | String | SMTP-Server-Adresse |
| `port` | Integer | SMTP-Port (587 für TLS) |
| `username` | String | SMTP-Benutzername |
| `password` | String | SMTP-Passwort (verschlüsselt) |
| `from_email` | String | Absender-Adresse |
| `use_tls` | Boolean | TLS-Verschlüsselung aktivieren |

**Evidenz:** `app.py:700-750` (TriggerStore.get_smtp_config)

---

### Trigger-Log-Eintrag

**Definition:** Protokolleintrag einer Trigger-Ausführung.

| Attribut | Typ | Beschreibung |
|----------|-----|--------------|
| `id` | UUID-String | Eindeutige Kennung |
| `trigger_id` | String | Referenz zum Trigger |
| `trigger_name` | String | Name des Triggers |
| `event` | String | Auslösendes Event |
| `employer_id` | String | Betroffener Arbeitgeber |
| `executed_at` | String | Ausführungszeitpunkt (ISO) |
| `affected_employees` | Array | Liste betroffener Mitarbeiter |
| `action_type` | String | `email` oder `api` |
| `status` | String | `success`, `error`, `skipped` |
| `error_message` | String | Fehlermeldung (wenn vorhanden) |
| `can_retry` | Boolean | Wiederholung möglich |

**Evidenz:** `app.py:975-1160` (TriggerLogStore), `docs/TRIGGERS.md:105-125`

---

### Template-Variablen (Trigger)

**Definition:** Platzhalter für dynamische Werte in Trigger-Aktionen.

| Kategorie | Beispiele |
|-----------|-----------|
| SCS-Felder | `{{Name}}`, `{{Vorname}}`, `{{Email}}`, etc. |
| Meta-Felder | `{{_changedField}}`, `{{_oldValue}}`, `{{_newValue}}` |
| Arbeitgeber | `{{_employerId}}`, `{{_employerName}}` |
| Ausführung | `{{_triggerName}}`, `{{_timestamp}}`, `{{_employeeCount}}` |

**Evidenz:** `docs/TRIGGERS.md:309-339`

---

**Letzte Aktualisierung:** 29.01.2026
