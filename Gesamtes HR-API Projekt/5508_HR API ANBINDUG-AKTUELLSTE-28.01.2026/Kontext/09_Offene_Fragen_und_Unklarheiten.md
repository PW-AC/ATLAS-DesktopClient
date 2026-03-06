# 09 - Offene Fragen und Unklarheiten

## Unklare oder unverifizierte Aspekte

Die folgenden Punkte konnten durch statische Code-Analyse nicht vollständig geklärt werden.

**Stand:** 29.01.2026 (Version 1.1.0 mit Trigger-System)

---

## Architektur

### 1. UNVERIFIZIERT: Skalierbarkeit

**Frage:** Wie verhält sich die Anwendung bei vielen gleichzeitigen Benutzern?

**Beobachtung:**
- Single-Instance-Design (kein Clustering)
- JSON-Dateien als Datenbank (Locking-Probleme möglich)
- In-Memory Rate-Limiting (nicht cluster-fähig)

**Status:** Nicht getestet, keine Last-Tests dokumentiert.

### 2. UNVERIFIZIERT: Concurrent Access

**Frage:** Wie werden gleichzeitige Schreibzugriffe auf JSON-Dateien behandelt?

**Beobachtung:**
- `EmployerStore` verwendet `threading.Lock()` (`app.py:466`)
- `TriggerStore` verwendet `threading.Lock()` (`app.py:635`)
- `TriggerLogStore` verwendet `threading.Lock()` (`app.py:985`)
- Andere JSON-Dateien (`users.json`, `secrets.json`) haben keine expliziten Locks

**Status:** Potenzielle Race Conditions bei gleichzeitigem Zugriff auf users.json/secrets.json.

---

## Provider-Integration

### 3. UNVERIFIZIERT: Personio Rate-Limits

**Frage:** Welche Rate-Limits hat die Personio API?

**Beobachtung:**
- Keine Dokumentation im Code zu Personio Rate-Limits
- Keine Retry-Logik bei 429-Responses

**Status:** Nicht aus Code ableitbar.

### 4. UNVERIFIZIERT: HRworks Pagination-Limits

**Frage:** Wie viele Datensätze pro Seite liefert HRworks?

**Beobachtung:**
- Pagination via `Link` Header wird verarbeitet (`app.py:2000-2010`)
- Keine explizite Page-Size-Dokumentation

**Status:** Abhängig von HRworks API-Konfiguration.

### 5. UNKLAR: SageHR-Integration

**Frage:** Ist eine echte SageHR-API-Integration geplant?

**Beobachtung:**
- `SageHrProvider` ist nur ein Mock (`app.py:2142-2185`)
- Keine echte API-URL oder Authentifizierung

**Status:** Mock-Implementation, echte Integration nicht vorhanden.

---

## Daten und Speicherung

### 6. UNVERIFIZIERT: Snapshot-Bereinigung

**Frage:** Werden alte Snapshots jemals automatisch gelöscht?

**Beobachtung:**
- Keine Lösch-Logik in `app.py` gefunden
- Kein Cron-Job oder Scheduled Task dokumentiert

**Status:** Snapshots wachsen unbegrenzt. Manuelle Bereinigung erforderlich.

### 7. UNVERIFIZIERT: History-Bereinigung

**Frage:** Werden alte History-Dateien jemals gelöscht?

**Beobachtung:**
- `_history/` enthält rohe API-Antworten
- Keine automatische Bereinigung

**Status:** Wie Snapshots - unbegrenztes Wachstum.

### 8. UNKLAR: employers.json Speicherort

**Frage:** Warum liegt `employers.json` im Root von `acencia_hub/` statt in `data/`?

**Beobachtung:**
- `EmployerStore` verwendet `employers.json` relativ zu sich selbst (`app.py:475`)
- Andere Konfigurationsdateien (users.json, triggers.json) liegen in `data/`

**Status:** Möglicherweise historisch gewachsen. Inkonsistent mit anderen Konfigurationsdateien.

---

## Sicherheit

### 9. UNVERIFIZIERT: Encryption Key Rotation

**Frage:** Wie werden verschlüsselte Credentials bei Key-Wechsel migriert?

**Beobachtung:**
- Fernet-Verschlüsselung verwendet `ACENCIA_MASTER_KEY`
- Keine Migration-Logik bei Key-Änderung

**Status:** Key-Wechsel würde alle verschlüsselten Daten unlesbar machen.

### 10. UNVERIFIZIERT: Backup-Encryption

**Frage:** Werden Backups verschlüsselt?

**Beobachtung:**
- Keine Backup-Funktionalität in der Anwendung
- Snapshots und History sind Klartext-JSON

**Status:** Backup-Verschlüsselung liegt außerhalb der Anwendung.

### 11. UNKLAR: Session-Invalidation bei Passwort-Änderung

**Frage:** Werden bestehende Sessions invalidiert, wenn ein Passwort geändert wird?

**Beobachtung:**
- Passwort-Änderung aktualisiert nur den Hash
- Keine Session-Invalidierung erkennbar

**Status:** Alte Sessions könnten gültig bleiben.

---

## Deployment

### 12. UNVERIFIZIERT: Reverse Proxy Konfiguration

**Frage:** Wie sollte ein Reverse Proxy (nginx/Apache) konfiguriert werden?

**Beobachtung:**
- Keine Beispiel-Konfiguration im Repository
- Keine Dokumentation zu Header-Forwarding

**Status:** Nicht dokumentiert.

### 13. UNVERIFIZIERT: Produktions-Hardening

**Frage:** Welche zusätzlichen Hardening-Maßnahmen sind für Produktion erforderlich?

**Beobachtung:**
- `FLASK_DEBUG` Umgebungsvariable existiert
- Keine Checkliste für Produktions-Deployment

**Status:** Nicht dokumentiert.

---

## Entwicklung

### 14. UNKLAR: Test-Coverage

**Frage:** Wie hoch ist die aktuelle Test-Coverage?

**Beobachtung:**
- Tests existieren in `tests/`
- Keine Coverage-Reports im Repository

**Status:** Coverage unbekannt.

### 15. UNVERIFIZIERT: API-Dokumentation

**Frage:** Gibt es eine OpenAPI/Swagger-Spezifikation?

**Beobachtung:**
- Keine `openapi.yaml` oder `swagger.json` gefunden
- API-Routen nur im Code dokumentiert

**Status:** Keine formale API-Dokumentation.

---

## Widersprüche und Inkonsistenzen

### 16. Inkonsistenz: Dateipfade

| Datei | Pfad-Referenz |
|-------|---------------|
| `employers.json` | Relativ zu `app.py` |
| `users.json` | Absolut via `DATA_DIR` |
| `secrets.json` | Absolut via `SECRETS_FILE` |

**Beobachtung:** Unterschiedliche Strategien für Pfadauflösung.

### 17. Inkonsistenz: Provider-Normalisierung

| Provider | `isActive` Quelle |
|----------|-------------------|
| HRworks | `raw.get("isActive")` oder `status == "active"` |
| Personio | `status == "active"` |
| SageHR | Hardcoded `True` |

**Beobachtung:** Unterschiedliche Logik zur Bestimmung des Aktiv-Status.

### 18. Inkonsistenz: Datumsformate

| Kontext | Format |
|---------|--------|
| API-Input (HRworks) | `YYYY-MM-DD` |
| API-Input (Personio) | `YYYY-MM-DD` |
| Normalisiertes Output | `DD.MM.YYYY` |
| Snapshot-Timestamps | `YYYYMMDD-HHMMSS` |

**Beobachtung:** Mehrere Datumsformate im Einsatz.

---

## Dokumentations-Lücken

### 19. Fehlende Dokumentation: Error-Codes

**Frage:** Welche HTTP-Status-Codes werden bei welchen Fehlern zurückgegeben?

**Status:** Nicht systematisch dokumentiert.

### 20. Fehlende Dokumentation: Provider-spezifische Felder

**Frage:** Welche dynamischen Felder unterstützt jeder Provider?

**Beobachtung:**
- `PersonioProvider` hat `KEY_TO_LABEL_MAP` mit 50+ Feldern
- HRworks-Felder sind implizit in Normalisierung

**Status:** Nur teilweise im Code dokumentiert.

---

## Trigger-System-spezifische Fragen (NEU)

### 21. UNVERIFIZIERT: Trigger-Performance bei vielen Mitarbeitern

**Frage:** Wie verhält sich das Trigger-System bei sehr großen Datenmengen?

**Beobachtung:**
- TriggerEngine iteriert über alle betroffenen Mitarbeiter (`app.py:1164-1600`)
- Bei `send_individual=true` wird pro Mitarbeiter eine E-Mail gesendet
- Keine Batch-Verarbeitung oder Queue implementiert

**Status:** Performance-Tests mit großen Datensätzen ausstehend.

---

### 22. UNKLAR: Chevron-Abhängigkeit

**Frage:** Ist die `chevron` Library (Mustache-Templates) obligatorisch?

**Beobachtung:**
- `EmailAction` nutzt chevron für Template-Rendering (`app.py:1620-1650`)
- Fallback auf einfache `{{variable}}`-Ersetzung existiert
- Chevron ist NICHT in requirements.txt

**Status:** Funktioniert ohne chevron, aber mit eingeschränktem Template-Support (keine Listen-Iteration).

---

### 23. UNVERIFIZIERT: SMTP-Timeouts

**Frage:** Welche Timeouts werden für SMTP-Verbindungen verwendet?

**Beobachtung:**
- Keine expliziten Timeout-Parameter in EmailAction
- Standard-Python-smtplib-Timeouts gelten

**Status:** Könnte bei langsamen SMTP-Servern zu Problemen führen.

---

## Empfohlene Klärungen

Für zukünftige Agenten oder Entwickler sollten folgende Punkte geklärt werden:

1. **Skalierbarkeits-Anforderungen** definieren
2. **Data Retention Policy** festlegen
3. **Backup-Strategie** dokumentieren
4. **Reverse Proxy Beispiel-Config** erstellen
5. **API-Dokumentation** (OpenAPI) erstellen
6. **Test-Coverage-Ziel** definieren
7. **SageHR-Integration** Entscheidung treffen
8. **Trigger-Performance-Tests** durchführen (NEU)
9. **SMTP-Timeout-Konfiguration** erwägen (NEU)

---

**Letzte Aktualisierung:** 29.01.2026
