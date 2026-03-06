# 09 - Logging, Auditing, Monitoring (IST-Zustand)

## Logging-System

### Konfiguration

```python
# File Logger
file_logger = logging.getLogger('file_logger')
file_logger.setLevel(logging.INFO)
file_handler = logging.FileHandler(LOG_FILE_PATH, mode='a', encoding='utf-8')
file_formatter = logging.Formatter('%(message)s')

# Werkzeug Logger (HTTP Access)
werkzeug_log = logging.getLogger('werkzeug')
werkzeug_log.setLevel(logging.INFO)
werkzeug_log.addHandler(file_handler)
```

**Evidenz:** `app.py:24-45`

### Log-Datei

| Aspekt | Wert | Evidenz |
|--------|------|---------|
| Pfad | `{PROJECT_ROOT}/server.log` | `app.py:22` |
| Mode | Append (`'a'`) | `app.py:33` |
| Encoding | UTF-8 | `app.py:33` |
| Rotation | Nicht konfiguriert | Keine RotatingFileHandler |
| Max-Größe | Unbegrenzt | Keine Konfiguration |

### Custom Logging Funktion

```python
def custom_log(kuerzel, message, color_name=None, ip=None):
    now = datetime.now().strftime("%d/%b/%Y %H:%M:%S")
    if ip:
        log_message_plain = f'("{ip}" - {message})'
    else:
        log_message_plain = f'("{kuerzel}" - {message})'
    full_log_plain = f'[{now}] {log_message_plain}'
    file_logger.info(full_log_plain)
    print(full_log_color)
```

**Evidenz:** `app.py:60-92`

### Log-Format

```
[DD/Mon/YYYY HH:MM:SS] ("KÜRZ" - Nachricht)
[DD/Mon/YYYY HH:MM:SS] ("IP" - Nachricht)
```

**Beispiele:**
- `[28/Jan/2026 10:15:30] ("PWEI" - wurde angemeldet)`
- `[28/Jan/2026 10:15:25] ("127.0.0.1" - LOGIN)`

## Geloggte Ereignisse

### Authentifizierung

| Ereignis | Geloggt | Evidenz |
|----------|---------|---------|
| Login-Versuch (unauthentifiziert) | Ja (IP) | `app.py:1842-1843` |
| Erfolgreicher Login | Ja (Kürzel) | `app.py:1597` |
| Fehlgeschlagener Login | Nein | Keine Logging-Zeile |
| Logout | Nein | `app.py:1606-1615` |

### Benutzer-Aktionen

| Ereignis | Geloggt | Evidenz |
|----------|---------|---------|
| Arbeitgeber-Auswahl aufrufen | Ja | `app.py:1904` |
| Mitarbeiter aufrufen | Ja | `app.py:1956` |
| Mitarbeiterdetails aufrufen | Ja | `app.py:1997` |
| Exporte aufrufen | Ja | `app.py:2018` |
| Statistiken aufrufen | Ja | `app.py:2085` |
| Snapshots aufrufen | Ja | `app.py:2105` |
| Snapshots vergleichen | Ja | `app.py:2219` |
| Master-Einstellungen aufrufen | Ja | `app.py:1683` |
| Styleguide aufrufen | Ja | `app.py:2709` |

### Administrative Aktionen

| Ereignis | Geloggt | Evidenz |
|----------|---------|---------|
| Arbeitgeber anlegen | Ja | `app.py:1936` |
| Arbeitgeber löschen | Ja | `app.py:2400` |
| Benutzer anlegen | Nein | `app.py:1637-1658` |
| Benutzer löschen | Nein | `app.py:1660-1667` |
| Server-Neustart | Ja | `app.py:1777` |
| PAT speichern | Nein | `app.py:1673-1678` |

### Downloads

| Ereignis | Geloggt | Evidenz |
|----------|---------|---------|
| Standard-Export Download | Ja | `app.py:2488` |
| Delta-Export generieren | Ja | `app.py:2511` |
| Past Export Download | Ja | `app.py:2627` |

## PII in Logs

### IST-Zustand

| Datentyp | In Logs | Evidenz |
|----------|---------|---------|
| Benutzername (Kürzel) | Ja | Alle custom_log Aufrufe |
| IP-Adresse | Ja (bei Login) | `app.py:1843` |
| Mitarbeiter-Name | Ja | `app.py:1997` |
| Arbeitgeber-Name | Ja | `app.py:1956` |
| Passwörter | Nein | Nicht geloggt |
| API-Credentials | Nein | Nicht geloggt |

**Beobachtungen:**
- Mitarbeiter-Namen werden im Klartext geloggt
- Arbeitgeber-Namen werden im Klartext geloggt
- Potenziell DSGVO-relevant

## Log-Zugriff

### API-Endpunkt

```python
@app.route('/api/logs')
def api_get_logs():
    user_info = session.get('user_info', {})
    if not user_info.get('is_master'):
        return jsonify({"error": "Zugriff verweigert"}), 403
    # ...
    lines = f.readlines()
    last_lines = lines[-200:]
    last_lines.reverse()
```

**Evidenz:** `app.py:1801-1827`

**Beobachtungen:**
- Nur Master-Benutzer können Logs lesen
- Nur letzte 200 Zeilen werden zurückgegeben
- Neueste Einträge zuerst

## Audit-Trails

### IST-Zustand

**Kein dediziertes Audit-System.**

| Anforderung | Status | Evidenz |
|-------------|--------|---------|
| Separate Audit-Datei | ❌ | Nur server.log |
| Unveränderbarkeit | ❌ | Append-Modus, keine Signierung |
| Vollständigkeit | ❌ | Nicht alle Aktionen geloggt |
| Strukturiertes Format | ❌ | Plain Text |

### Fehlende Audit-Events

- Passwort-Änderungen
- Benutzer-Erstellung/Löschung
- Berechtigungsänderungen (is_master)
- Fehlgeschlagene Logins
- API-Credential-Änderungen
- Forced Logout

## Monitoring

### IST-Zustand

**Kein Monitoring implementiert.**

| Aspekt | Status |
|--------|--------|
| Health-Check Endpoint | ❌ |
| Metrics Endpoint | ❌ |
| Prometheus Integration | ❌ |
| Error Tracking (Sentry) | ❌ |
| Performance Monitoring | ❌ |

## Fehler-Logging

### Exception Handling

```python
except Exception as err:
    error_details = traceback.format_exc()
    print(f"ERROR in long-term statistics API for {employer_id}: {err}\n{error_details}")
    return jsonify({"error": f"An internal error occurred: {err}"}), 500
```

**Evidenz:** `app.py:2460-2463`

**Beobachtungen:**
- `print()` statt Logger in manchen Fällen
- Stacktraces werden ausgegeben
- Fehlermeldungen werden an Client weitergegeben

## Zusammenfassung

| Aspekt | Status | Risiko |
|--------|--------|--------|
| Grundlegendes Logging | ✅ Vorhanden | - |
| Log-Rotation | ❌ Fehlt | Hoch (Disk-Overflow) |
| Audit-Trail | ❌ Fehlt | Hoch (Compliance) |
| PII-Handling | ⚠️ Problematisch | Mittel (DSGVO) |
| Monitoring | ❌ Fehlt | Mittel |
| Error Tracking | ❌ Fehlt | Mittel |

---

**Letzte Aktualisierung:** 28.01.2026
