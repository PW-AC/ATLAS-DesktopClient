# Fixes

## BUG-0001: SMTP ASCII-Encoding-Fehler

### Fix-Strategie
Explizit einen ASCII-sicheren `local_hostname` an `smtplib.SMTP()` übergeben.

### Implementierung

**Datei:** `app.py`

**Änderung 1:** SMTP-Test-Route (Zeile ~3818)
```python
# NEU: Explizit ASCII-sicheren lokalen Hostnamen setzen
local_hostname = 'localhost'
try:
    hostname = socket.gethostname()
    hostname.encode('ascii')  # Prüft auf ASCII-Kompatibilität
    local_hostname = hostname
except (UnicodeEncodeError, socket.error):
    local_hostname = 'localhost'

server = smtplib.SMTP(smtp_config['host'], smtp_config.get('port', 587), local_hostname=local_hostname)
```

**Änderung 2:** EmailAction.execute() (Zeile ~1628)
```python
# Gleiche Logik wie oben
local_hostname = 'localhost'
try:
    hostname = socket.gethostname()
    hostname.encode('ascii')
    local_hostname = hostname
except (UnicodeEncodeError, socket.error):
    local_hostname = 'localhost'

server = smtplib.SMTP(smtp_config['host'], ..., local_hostname=local_hostname)
```

### Side Effects
Keine - `local_hostname='localhost'` ist ein gültiger Fallback für SMTP EHLO.

---

## BUG-0002 + BUG-0003: NoneType und str(None) Fehler

### Fix-Strategie
1. `from_value` und `to_value` mit `or ''` auf leeren String setzen wenn None
2. Helper-Funktion `safe_str()` für sichere String-Konvertierung
3. Zusätzliche Prüfung bei `contains` ob `to_value` nicht leer ist

### Implementierung

**Datei:** `app.py`, Methode `_check_condition()` (Zeile ~1408)

```python
def _check_condition(self, condition, changes):
    field = condition.get('field')
    operator = condition.get('operator')
    from_value = condition.get('from_value') or ''   # FIX: None → ''
    to_value = condition.get('to_value') or ''       # FIX: None → ''
    
    # ... (Änderung finden) ...
    
    # FIX: Helper für sichere String-Konvertierung
    def safe_str(val):
        return str(val) if val is not None else ''
    
    if operator == 'changed_to':
        return change is not None and safe_str(change.get('new', '')).lower() == safe_str(to_value).lower()
    
    elif operator == 'changed_from':
        return change is not None and safe_str(change.get('old', '')).lower() == safe_str(from_value).lower()
    
    elif operator == 'changed_from_to':
        return (change is not None and 
                safe_str(change.get('old', '')).lower() == safe_str(from_value).lower() and
                safe_str(change.get('new', '')).lower() == safe_str(to_value).lower())
    
    # FIX: Zusätzliche Prüfung ob to_value nicht leer
    elif operator == 'contains':
        return change is not None and to_value and safe_str(to_value).lower() in safe_str(change.get('new', '')).lower()
```

### Side Effects
- `contains` mit leerem Wert gibt jetzt False zurück (vorher: Crash)
- Vergleiche mit None-Werten funktionieren jetzt korrekt
