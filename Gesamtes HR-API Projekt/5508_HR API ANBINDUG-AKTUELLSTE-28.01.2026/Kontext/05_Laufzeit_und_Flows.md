# 05 - Laufzeit und Flows

## Anwendungsstart

### Produktions-Start (via run.py oder start.bat)

```
1. start.bat ausführen
   │
   ├── 2. Virtuelle Umgebung aktivieren (venv\Scripts\activate)
   │
   ├── 3. Dependencies installieren (pip install -r requirements.txt)
   │
   └── 4. python run.py
          │
          ├── 5. Update-Check (updater.run_update())
          │      ├── secrets.json laden für GitHub PAT
          │      ├── ZIP von GitHub herunterladen (wenn PAT vorhanden)
          │      ├── Dateien extrahieren und kopieren (mit Exclusions)
          │      └── Temporäre Dateien aufräumen
          │
          ├── 6. IP-Adressen ermitteln und anzeigen
          │
          └── 7. Waitress Server starten
                 └── serve(app, host='0.0.0.0', port=5001)
```

**Evidenz:** `start.bat`, `run.py:46-64`

### Entwicklungs-Start (via app.py)

```
1. python acencia_hub/app.py
   │
   ├── 2. Flask-App initialisieren
   │      ├── CSRF-Schutz aktivieren (Flask-WTF)
   │      ├── Secret Key aus ACENCIA_SECRET_KEY laden
   │      ├── Session-Konfiguration setzen
   │      ├── Rate-Limiter initialisieren
   │      └── Security Headers registrieren
   │
   └── 3. Flask Development Server starten
          └── app.run(debug=True, host='127.0.0.1', port=5001)
```

**Evidenz:** `app.py:2966-3055`, `app.py:5295+`

---

## Authentifizierungs-Flow

### Login

```
1. GET /login
   └── login.html anzeigen

2. POST /login (username, password)
   │
   ├── 3. Rate-Limiter prüfen (5/Minute)
   │      └── Bei Überschreitung: 429 Too Many Requests
   │
   ├── 4. Account-Lockout prüfen
   │      ├── failed_login_attempts aus Session lesen
   │      └── Bei >= 5 Versuchen in 15min: Zugang gesperrt
   │
   ├── 5. users.json laden
   │
   ├── 6. Benutzer suchen (username)
   │
   ├── 7. Passwort prüfen (check_password_hash / scrypt)
   │      │
   │      ├── ERFOLG:
   │      │   ├── Session erstellen
   │      │   │   ├── username
   │      │   │   ├── kuerzel
   │      │   │   ├── user_info (is_master, theme, allowed_employers)
   │      │   │   └── session.permanent = True
   │      │   ├── Fehlversuche zurücksetzen
   │      │   ├── Audit-Log: LOGIN_SUCCESS
   │      │   └── Redirect → /
   │      │
   │      └── FEHLER:
   │          ├── Fehlversuch zählen
   │          ├── Audit-Log: LOGIN_FAILED
   │          ├── Flash-Nachricht
   │          └── Zurück zu /login
```

**Evidenz:** `app.py:3369-3440`

### Logout

```
1. GET /logout
   │
   ├── 2. Audit-Log: LOGOUT
   │
   ├── 3. Session clearen
   │
   └── 4. Redirect → /login
```

**Evidenz:** `app.py:3442-3452`

### Forced Logout

```
1. Master-User schreibt Timestamp in data/force_logout.txt

2. Bei jedem Request (before_request):
   │
   ├── force_logout.txt lesen
   │
   └── Wenn Timestamp > Session-Login-Zeit:
       ├── Session clearen
       └── Redirect → /login mit Flash "Erzwungenes Abmelden"
```

**Evidenz:** `app.py:1914`, Logik in before_request Handler

---

## Mitarbeiterdaten-Flow

### Mitarbeiterliste abrufen

```
1. GET /employer/<employer_id>
   │
   ├── 2. Zugriffskontrolle prüfen (check_employer_route_access)
   │      ├── is_master → immer Zugriff
   │      └── allowed_employers prüfen
   │
   ├── 3. EmployerStore.get_by_id(employer_id)
   │
   ├── 4. ProviderFactory.create(employer_cfg)
   │      │
   │      ├── provider_key == "personio"
   │      │   └── PersonioProvider(client_id, client_secret)
   │      │
   │      ├── provider_key == "hrworks"
   │      │   └── HRworksProvider(access_key, secret_key, is_demo)
   │      │
   │      └── provider_key == "sagehr"
   │          └── SageHrProvider(access_key, slug)
   │
   ├── 5. provider.list_employees(only_active=True)
   │      │
   │      ├── HRworks:
   │      │   ├── _authenticate() → Bearer Token
   │      │   ├── GET /persons/master-data (paginiert)
   │      │   ├── _normalize_employee_details() für jeden
   │      │   └── Return: (normalized_list, raw_responses)
   │      │
   │      └── Personio:
   │          ├── _authenticate() → Bearer Token
   │          ├── GET /company/employees
   │          ├── _normalize_employee() für jeden
   │          └── Return: (normalized_list, raw_responses)
   │
   ├── 6. save_history_entry() → _history/ (Raw-Backup)
   │
   ├── 7. custom_log() → server.log
   │
   └── 8. render_template('employer_dashboard.html', employees=...)
```

**Evidenz:** `app.py:4406-4465`

### Mitarbeiter-Details abrufen

```
1. GET /employer/<employer_id>/employee/<employee_id>
   │
   ├── 2. Zugriffskontrolle
   │
   ├── 3. Provider instanziieren
   │
   ├── 4. provider.get_employee_details(employee_id)
   │      │
   │      ├── HRworks:
   │      │   ├── GET /persons/master-data/{id}
   │      │   └── Fallback: Suche in Gesamtliste
   │      │
   │      └── Personio:
   │          └── GET /company/employees/{id}
   │
   ├── 5. save_history_entry()
   │
   └── 6. render_template('employee_detail.html', employee=...)
```

**Evidenz:** `app.py:4439-4467`

---

## Export-Flow

### Delta-SCS-Export

```
1. POST /api/employer/<employer_id>/export/delta_scs
   │
   ├── 2. Provider.get_employee_details() für alle aktiven Mitarbeiter
   │
   ├── 3. "Latest" Snapshot laden
   │      └── _snapshots/{name}-{provider}-latest.json
   │
   ├── 4. Hash-Vergleich für jeden Mitarbeiter
   │      ├── added_pids: Neue (nicht im Snapshot)
   │      ├── changed_pids: Geändert (Hash unterschiedlich)
   │      └── removed_pids: Entfernt (nicht mehr aktiv)
   │
   ├── 5. _map_to_scs_schema() für alle relevanten PIDs
   │      └── Normalisiert auf SCS_HEADERS
   │
   ├── 6. XLSX erstellen
   │      ├── Sheet "Mitarbeiter": Alle geänderten Mitarbeiter
   │      └── Sheet "Arbeitgeber": Arbeitgeber-Stammdaten
   │
   ├── 7. Snapshot speichern
   │      ├── Datiert: {name}-{provider}-{timestamp}.json
   │      └── Latest: {name}-{provider}-latest.json überschreiben
   │
   └── 8. JSON Response
          {
              "status": "success",
              "filepath": "...",
              "diff": { "added": [...], "changed": [...], "removed": [...] }
          }
```

**Evidenz:** `app.py:2557-2675`, `AGENTS.md:39-49`

### Standard-Export

```
1. POST /employer/<employer_id>/export/standard
   │
   ├── 2. Provider.list_employees()
   │
   ├── 3. openpyxl Workbook erstellen
   │
   ├── 4. Alle Mitarbeiter als Zeilen einfügen
   │
   └── 5. XLSX speichern und Download anbieten
```

**Evidenz:** `app.py:2473-2507`

---

## Statistik-Flow

### Standard-Statistiken

```
1. GET /api/employer/<employer_id>/statistics
   │
   ├── 2. Provider.list_employees(only_active=False)
   │
   ├── 3. Letzten Snapshot laden (für Fluktuation)
   │
   ├── 4. calculate_statistics(current, previous)
   │      ├── Status-Counts (aktiv, inaktiv, gesamt)
   │      ├── Gender-Distribution
   │      ├── Employment-Type-Distribution
   │      ├── Department-Distribution (Top 5)
   │      ├── Averages (Tenure, Hiring Age)
   │      ├── Turnover Rate
   │      └── Join/Leave Trends (12 Monate)
   │
   └── 5. JSON Response
```

**Evidenz:** `app.py:2779-2829`

### Langzeit-Statistiken

```
1. GET /api/employer/<employer_id>/long_term_statistics
   │
   ├── 2. _get_employee_history_from_snapshots()
   │      ├── Alle datierten Snapshots laden
   │      ├── Timeline für jeden Mitarbeiter erstellen
   │      └── Join/Leave-Dates bestimmen
   │
   ├── 3. calculate_long_term_statistics(history)
   │      ├── Entries per Year
   │      ├── Exits per Year
   │      └── Average Employment Duration
   │
   └── 4. JSON Response
```

**Evidenz:** `app.py:2676-2905`

---

## Snapshot-Vergleich-Flow

```
1. POST /api/employer/<employer_id>/snapshots/compare
   {
       "snapshot1": "...-20250115-120000.json",
       "snapshot2": "...-20250120-120000.json",
       "direction": "forward"
   }
   │
   ├── 2. Beide Snapshots laden
   │
   ├── 3. Nach Timestamp sortieren (basierend auf direction)
   │
   ├── 4. _compare_snapshots(old_snapshot, new_snapshot)
   │      ├── added: In new, nicht in old
   │      ├── removed: In old, nicht in new
   │      └── changed: Hash unterschiedlich
   │
   ├── 5. Post-Processing für Lesbarkeit
   │      └── JSON-Werte "entpacken" für bessere Diff-Anzeige
   │
   └── 6. JSON Response mit Diff-Details
```

**Evidenz:** `app.py:4712-4905`, `AGENTS.md:53-63`

---

## Theme-Wechsel-Flow

```
1. User klickt Theme-Toggle im Header
   │
   ├── 2. JavaScript: applyTheme(theme)
   │      └── document.body.setAttribute('data-theme', theme)
   │
   └── 3. JavaScript: persistTheme(theme)
          │
          └── POST /api/update_theme { "theme": "dark" }
                 │
                 ├── Session['user_info']['theme'] aktualisieren
                 │
                 └── users.json aktualisieren
```

**Evidenz:** `base.html:91-151`, `app.py:3200-3250`

---

## Auto-Update-Flow

```
1. run.py startet
   │
   └── 2. updater.run_update()
          │
          ├── 3. secrets.json laden
          │      └── github_pat lesen (entschlüsselt)
          │
          ├── 4. Wenn kein PAT: Abbruch mit Warnung
          │
          ├── 5. ZIP herunterladen
          │      └── GET https://github.com/.../archive/refs/heads/main.zip
          │           Header: Authorization: token {PAT}
          │
          ├── 6. ZIP extrahieren → update_temp/
          │
          ├── 7. copy_files() mit Exclusions:
          │      ├── .git/
          │      ├── venv/
          │      ├── __pycache__/
          │      ├── _snapshots/
          │      ├── _history/
          │      ├── exports/
          │      ├── acencia_hub/data/
          │      ├── acencia_hub/updater.py
          │      └── start.bat
          │
          └── 8. update_temp/ löschen
```

**Evidenz:** `updater.py:92-165`

---

## Trigger-Ausführungs-Flow (NEU)

```
1. Delta-Export generiert Diff
   │
   └── 2. TriggerEngine.evaluate_and_execute()
          │
          ├── 3. TriggerStore.get_triggers_for_employer(employer_id)
          │      └── Aktive Trigger ohne Ausschluss für diesen AG
          │
          ├── 4. Für jeden Trigger:
          │      │
          │      ├── 5. Event-Typ prüfen (added/removed/changed)
          │      │
          │      ├── 6. Betroffene Mitarbeiter identifizieren
          │      │      ├── employee_added: diff['added']
          │      │      ├── employee_removed: diff['removed']
          │      │      └── employee_changed: diff['changed']
          │      │
          │      ├── 7. Bedingungen prüfen (_check_condition)
          │      │      ├── Für jeden betroffenen Mitarbeiter
          │      │      ├── Operatoren anwenden
          │      │      └── AND/OR-Logik (condition_logic)
          │      │
          │      ├── 8. Template-Kontext erstellen (_build_context)
          │      │      ├── SCS-Felder einsetzen
          │      │      ├── Meta-Felder (_changedField, _oldValue, etc.)
          │      │      └── Arbeitgeber-Daten
          │      │
          │      └── 9. Aktion ausführen (_execute_action)
          │             │
          │             ├── action.type == "email":
          │             │   └── EmailAction.execute()
          │             │       ├── Mustache-Template rendern
          │             │       ├── SMTP-Verbindung aufbauen
          │             │       └── E-Mail senden
          │             │
          │             └── action.type == "api":
          │                 └── APIAction.execute()
          │                     ├── URL + Body rendern
          │                     ├── Auth-Header setzen
          │                     └── HTTP-Request senden
          │
          └── 10. Ausführung protokollieren (TriggerLogStore)
                 └── trigger_log.json aktualisieren
```

**Evidenz:** `app.py:1164-1600`, `docs/TRIGGERS.md:162-179`

---

## Shutdown

Die Anwendung hat keinen expliziten Shutdown-Handler. Beim Beenden (CTRL+C oder Signal):

1. Waitress stoppt Anfragen
2. Python-Prozess endet
3. Offene Dateien werden vom OS geschlossen
4. Bei `start.bat`: Automatischer Neustart nach 3 Sekunden

**Hinweis:** Es gibt keinen graceful shutdown mit Cleanup-Logik.

**Evidenz:** `start.bat:47-50`

---

**Letzte Aktualisierung:** 29.01.2026
