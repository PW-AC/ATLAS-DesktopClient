# Reproduktion

## BUG-0001: SMTP ASCII-Encoding-Fehler

### Voraussetzungen
- Windows-Computer mit Umlaut im Hostnamen (z.B. "DESKTOP-BÜRO")
- Konfigurierte SMTP-Einstellungen

### Reproduktionsschritte
1. Einstellungen → SMTP konfigurieren öffnen
2. SMTP-Daten eingeben (Host, Port, Benutzer, Passwort)
3. Test-E-Mail-Adresse eingeben
4. "Test senden" klicken

### Erwartetes Ergebnis
Test-E-Mail wird gesendet

### Tatsächliches Ergebnis (vor Fix)
```
SMTP-Test fehlgeschlagen: 'ascii' codec can't encode character '\xfc' in position 12: ordinal not in range(128)
```

### Reproduzierbar
JA - 100% reproduzierbar auf Systemen mit Umlaut im Hostnamen

---

## BUG-0002: NoneType-Fehler bei `contains`-Operator

### Voraussetzungen
- Trigger mit `contains`-Operator erstellt
- Feld "Neuer Wert" leer gelassen

### Reproduktionsschritte (statisch)
1. Trigger erstellen mit Event "employee_changed"
2. Bedingung: Feld "Name", Operator "contains", Wert leer lassen
3. Delta-Export ausführen mit Mitarbeiter-Änderungen

### Codepfad
```
TriggerEngine.evaluate_and_execute()
  → _process_changed_employees()
    → _check_condition()
      → to_value.lower()  # to_value ist None → AttributeError
```

### Reproduzierbar
TEILWEISE_REPRODUZIERBAR - Nur bei leeren Feldern im Trigger-Formular

---

## BUG-0003: str(None) wird zu "None"-String

### Voraussetzungen
- Trigger mit `changed_to` oder `changed_from` Operator
- Datenbankfeld enthält None statt leerem String

### Reproduktionsschritte (statisch)
1. Mitarbeiter-Daten mit None-Wert in einem Feld
2. Trigger: "Status" `changed_to` "" (leerer String)
3. Delta-Export ausführen

### Codepfad
```
_check_condition()
  → str(change.get('old', '')).lower()  # Wenn old=None → "none"
  → str(from_value).lower()              # Wenn from_value=None → "none"
  → "none" == "none" → TRUE (falsch positiv)
```

### Reproduzierbar
TEILWEISE_REPRODUZIERBAR - Abhängig von Datenbankzustand
