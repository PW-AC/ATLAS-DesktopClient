# Root Cause Analyse

## BUG-0001: SMTP ASCII-Encoding-Fehler

### Root Cause (konkret)
Python's `smtplib.SMTP()` verwendet standardmäßig `socket.getfqdn()` als lokalen Hostnamen für den EHLO-Befehl. Wenn der Windows-Computername Umlaute enthält (z.B. "ü"), versucht SMTP diesen als ASCII zu encodieren, was fehlschlägt.

### Betroffene Dateien/Zeilen
- `app.py`, Zeile ~3836: `server = smtplib.SMTP(smtp_config['host'], ...)`
- `app.py`, Zeile ~1642: `server = smtplib.SMTP(smtp_config['host'], ...)` (EmailAction)

### Warum tritt der Bug auf?
1. Windows erlaubt Umlaute in Computernamen
2. `socket.getfqdn()` gibt diesen Namen mit Umlauten zurück
3. SMTP-Protokoll erwartet ASCII im EHLO-Befehl
4. `smtplib` versucht den Hostnamen als ASCII zu encodieren → Fehler

### Warum wurde er nicht früher erkannt?
- Auf Entwicklungssystemen ohne Umlaute im Hostnamen kein Problem
- Kein Test mit nicht-ASCII Hostnamen durchgeführt
- Der Parameter `local_hostname` ist optional und wird selten verwendet

---

## BUG-0002: NoneType-Fehler bei `contains`-Operator

### Root Cause (konkret)
In `_check_condition()` wird `to_value.lower()` aufgerufen ohne vorherige Null-Prüfung. Wenn das Formularfeld leer ist, ist `to_value = None`.

### Betroffene Dateien/Zeilen
- `app.py`, Zeile ~1455 (vor Fix):
  ```python
  elif operator == 'contains':
      return change is not None and to_value.lower() in str(change.get('new', '')).lower()
  ```

### Warum tritt der Bug auf?
1. Formularfeld "Neuer Wert" kann leer gelassen werden
2. `condition.get('to_value')` gibt None zurück
3. `None.lower()` wirft AttributeError

### Warum wurde er nicht früher erkannt?
- Trigger-Formular wurde immer mit Werten ausgefüllt getestet
- Kein Edge-Case-Test für leere Felder

---

## BUG-0003: str(None) wird zu "None"-String

### Root Cause (konkret)
Python's `str(None)` gibt den String `"None"` zurück, nicht einen leeren String. Dies führt zu falschen Vergleichsergebnissen.

### Betroffene Dateien/Zeilen
- `app.py`, Zeile ~1438, 1441, 1445-1446 (vor Fix):
  ```python
  str(change.get('new', '')).lower() == str(to_value).lower()
  # Wenn to_value=None: str(None) = "None"
  ```

### Warum tritt der Bug auf?
1. `condition.get('from_value')` oder `condition.get('to_value')` kann None sein
2. `str(None)` → `"None"` (nicht `""`)
3. Vergleich `"None" == "None"` ist True, aber semantisch falsch

### Warum wurde er nicht früher erkannt?
- Subtiler Fehler, der nur bei bestimmten Datenkonstellationen auftritt
- Keine explizite None-Behandlung im Code
