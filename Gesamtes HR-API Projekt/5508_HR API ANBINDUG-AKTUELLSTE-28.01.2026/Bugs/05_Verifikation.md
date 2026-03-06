# Verifikation

## BUG-0001: SMTP ASCII-Encoding-Fehler

### Testschritte
1. Einstellungen → SMTP konfigurieren
2. SMTP-Daten eingeben:
   - Host: smtp.web.de
   - Port: 587
   - Benutzer: paul.weimert@web.de
   - Passwort: ********
   - Von: paul.weimert@web.de
3. Test-E-Mail-Adresse eingeben
4. "Test senden" klicken

### Ergebnis vorher
```
[28/Jan/2026 13:27:42] ("PWEI" - SMTP-Test fehlgeschlagen: 'ascii' codec can't encode character '\xfc' in position 12: ordinal not in range(128))
```

### Ergebnis nachher
```
[28/Jan/2026 13:XX:XX] ("PWEI" - SMTP-Test an xxx@xxx.xx erfolgreich)
```
Test-E-Mail wurde erfolgreich zugestellt.

### Status: FIXED ✓

### Verifiziert durch
User-Bestätigung: "sehr gut hat funktioniert!"

---

## BUG-0002: NoneType-Fehler bei `contains`-Operator

### Testschritte (statisch)
1. Code-Review der `_check_condition()` Methode
2. Prüfung dass `to_value` vor `.lower()` auf None geprüft wird

### Ergebnis vorher
```python
elif operator == 'contains':
    return change is not None and to_value.lower() in ...
    # → AttributeError wenn to_value=None
```

### Ergebnis nachher
```python
elif operator == 'contains':
    return change is not None and to_value and safe_str(to_value).lower() in ...
    # → False wenn to_value=None oder leer
```

### Status: FIXED ✓

### Verifiziert durch
- Code-Review
- Linter: Keine Fehler

---

## BUG-0003: str(None) wird zu "None"-String

### Testschritte (statisch)
1. Code-Review der Vergleichsoperationen
2. Prüfung dass `safe_str()` verwendet wird

### Ergebnis vorher
```python
str(None).lower() == str(None).lower()
# "none" == "none" → True (falsch!)
```

### Ergebnis nachher
```python
safe_str(None).lower() == safe_str(None).lower()
# "" == "" → True (korrekt!)
```

### Status: FIXED ✓

### Verifiziert durch
- Code-Review
- Linter: Keine Fehler
