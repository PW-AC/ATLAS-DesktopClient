# Bugliste

## BUG-0001: SMTP ASCII-Encoding-Fehler bei Umlaut im Hostnamen

- **Kurzbeschreibung:** SMTP-Test schlägt fehl wenn Windows-Computername Umlaute enthält
- **Betroffene Komponente:** SMTP-Versand (EmailAction, SMTP-Test-Route)
- **Sichtbares Fehlverhalten:** `'ascii' codec can't encode character '\xfc' in position 12: ordinal not in range(128)`
- **Erwartetes Verhalten:** E-Mail wird erfolgreich gesendet
- **Quelle:** User-Report / Log
- **Schweregrad:** KRITISCH
- **Status:** FIXED

---

## BUG-0002: NoneType-Fehler bei `contains`-Operator

- **Kurzbeschreibung:** `_check_condition` wirft AttributeError wenn `to_value` None ist
- **Betroffene Komponente:** TriggerEngine._check_condition()
- **Sichtbares Fehlverhalten:** `'NoneType' object has no attribute 'lower'`
- **Erwartetes Verhalten:** Bedingung wird als nicht erfüllt gewertet
- **Quelle:** Code-Review
- **Schweregrad:** MITTEL
- **Status:** FIXED

---

## BUG-0003: str(None) wird zu "None"-String bei Vergleichen

- **Kurzbeschreibung:** Bei `changed_to`, `changed_from`, `changed_from_to` wird `str(None)` zu "None"
- **Betroffene Komponente:** TriggerEngine._check_condition()
- **Sichtbares Fehlverhalten:** Vergleich schlägt fehl weil "None" != ""
- **Erwartetes Verhalten:** None-Werte werden als leerer String behandelt
- **Quelle:** Code-Review
- **Schweregrad:** MITTEL
- **Status:** FIXED
