# 04 - Funktionen und Flows (IST-Zustand)

## Kernfunktionen

### 1. Benutzer-Authentifizierung

**Flow:**
```
1. POST /login mit username, password
2. load_users() → users.json
3. check_password_hash(stored_hash, password)
4. Bei Erfolg: session['user_id'], session['user_info'], session['login_time']
5. Redirect zu /
```

**Evidenz:** `app.py:1569-1603`

**Beobachtungen:**
- Keine Brute-Force-Protection
- Keine Account-Lockout-Policy
- Keine Passwort-Komplexitäts-Anforderungen
- Session-Daten unverschlüsselt im Cookie

### 2. Arbeitgeber-Verwaltung

**Flow: Hinzufügen**
```
1. POST /employer/add
2. Formulardaten extrahieren (inkl. access_key, secret_key)
3. UUID generieren
4. EmployerStore.add() → employers.json
5. Credentials im Klartext gespeichert
```

**Evidenz:** `app.py:1907-1939`

**Flow: Löschen**
```
1. POST /employer/<id>/delete
2. EmployerStore.delete()
3. Keine Löschung von Snapshots/History/Exports
```

**Evidenz:** `app.py:2382-2404`

### 3. Mitarbeiterdaten abrufen

**Flow:**
```
1. GET /employer/<id>
2. EmployerStore.get_by_id()
3. ProviderFactory.get_provider() → Provider-Instanz
4. Provider.list_employees() → External API Call
5. save_history_entry() → _history/
6. Template Rendering
```

**Evidenz:** `app.py:1941-1972`

**Beobachtungen:**
- API-Credentials werden bei jedem Aufruf verwendet
- Keine Caching-Strategie für API-Antworten (außer Bearer Token)
- History wird unbegrenzt gespeichert

### 4. Export-Generierung

**Flow: Standard-Export**
```
1. GET /employer/<id>/export/standard
2. Provider.list_employees()
3. generate_standard_export() → XLSX erstellen
4. Datei in exports/ speichern
5. send_from_directory() → Download
```

**Evidenz:** `app.py:2465-2493`

**Flow: Delta-SCS-Export**
```
1. GET /api/employer/<id>/export/delta_scs
2. Provider.list_employees()
3. Vorherigen Snapshot laden (_snapshots/*-latest.json)
4. Diff berechnen (hinzugefügt, geändert, entfernt)
5. XLSX generieren
6. Neuen Snapshot speichern
7. JSON Response mit Download-URL
```

**Evidenz:** `app.py:2495-2564`, `app.py:1083-1184`

### 5. Snapshot-Vergleich

**Flow:**
```
1. POST /employer/<id>/snapshots/compare
2. Zwei Snapshot-Dateinamen aus Form
3. Dateien laden aus _snapshots/
4. _compare_snapshots() → Diff berechnen
5. Template Rendering mit Ergebnissen
```

**Evidenz:** `app.py:2203-2346`

**Beobachtungen:**
- Dateinamen werden vom Client gesendet
- Keine Validierung, ob Dateien zum Arbeitgeber gehören
- Potenzielle Path Traversal (begrenzt durch os.path.join)

### 6. Auto-Update

**Flow:**
```
1. run.py startet → updater.run_update()
2. GitHub PAT aus secrets.json laden
3. ZIP von GitHub herunterladen
4. In update_temp/ extrahieren
5. Dateien kopieren (mit Ausschlüssen)
6. Server neu starten (via start.bat Loop)
```

**Evidenz:** `updater.py:92-165`, `run.py:46-54`

**Beobachtungen:**
- Keine Signaturprüfung des Downloads
- Keine Integritätsprüfung
- PAT wird als HTTP-Header gesendet

## Kritische Funktionen

### Passwort-Änderung

**Evidenz:** `app.py:1711-1727`

```python
if action == 'change_password':
    if not check_password_hash(user['password_hash'], current_password):
        flash("Das aktuelle Passwort ist nicht korrekt.", "error")
    elif new_password != confirm_password:
        flash("Die neuen Passwörter stimmen nicht überein.", "error")
    elif not new_password:
        flash("Das neue Passwort darf nicht leer sein.", "error")
    else:
        user['password_hash'] = generate_password_hash(new_password)
        write_users(users)
```

**Beobachtungen:**
- Keine Mindestlänge für Passwörter
- Keine Komplexitätsanforderungen
- Keine Passwort-Historie

### Benutzer-Verwaltung (Master)

**Evidenz:** `app.py:1637-1667`

**Beobachtungen:**
- Master kann andere Master erstellen
- Keine Bestätigung bei kritischen Aktionen (außer JavaScript confirm())
- Keine Audit-Logs für Benutzeränderungen

### System-Neustart

**Evidenz:** `app.py:1765-1798`

```python
def shutdown_server():
    os._exit(0)  # Harter Exit
```

**Beobachtungen:**
- `os._exit(0)` umgeht alle Cleanup-Routinen
- Response wird möglicherweise nicht gesendet
- Keine graceful Shutdown-Logik

### Datei-Download

**Evidenz:** `app.py:2614-2633`

```python
@app.route('/download/past_export/<path:filename>')
def download_past_export(filename):
    return send_from_directory(
        app.config['EXPORTS_DIR'],
        filename,
        as_attachment=True
    )
```

**Beobachtungen:**
- `<path:filename>` erlaubt Slashes
- `send_from_directory` verhindert Path Traversal (Flask-Schutz)
- Keine Prüfung, ob Benutzer Zugriff auf diese Datei haben sollte

## Datenverarbeitung

### Sensitive Daten

| Datentyp | Speicherort | Verschlüsselung | Evidenz |
|----------|-------------|-----------------|---------|
| Passwörter | users.json | scrypt Hash | `app.py:1651` |
| API Keys | employers.json | Klartext | `app.py:1923-1924` |
| GitHub PAT | secrets.json | Klartext | `app.py:1676-1677` |
| Bearer Tokens | Speicher | Klartext (Instanzvariable) | `app.py:459`, `app.py:750` |
| Session | Cookie | Flask signiert (nicht verschlüsselt) | Flask default |

### Daten-Retention

| Datentyp | Retention | Automatische Löschung | Evidenz |
|----------|-----------|----------------------|---------|
| History | Unbegrenzt | Nein | `app.py:221-247` |
| Snapshots | Unbegrenzt | Nein | `app.py:1143-1148` |
| Exporte | Unbegrenzt | Nein | `app.py:1180-1182` |
| Logs | Unbegrenzt | Nein | `app.py:33` |

---

**Letzte Aktualisierung:** 28.01.2026
