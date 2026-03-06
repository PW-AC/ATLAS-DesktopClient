# 12 - Schwachstellen und Fehlverhalten (IST-Zustand)

## Kritische Schwachstellen (CRITICAL)

### SV-001: Hardcodierter Flask Secret Key

| Aspekt | Wert |
|--------|------|
| **Schweregrad** | KRITISCH |
| **Kategorie** | Secrets Management |
| **Ort** | `app.py:1481` |
| **Beschreibung** | Flask Secret Key ist im Quellcode hardcodiert |
| **Code** | `app.secret_key = 'a-very-secret-key-for-the-app'` |
| **Auswirkung** | Session-Cookies können gefälscht werden; Angreifer kann sich als beliebiger Benutzer ausgeben |
| **Status** | OFFEN |

### SV-002: API-Credentials im Klartext

| Aspekt | Wert |
|--------|------|
| **Schweregrad** | KRITISCH |
| **Kategorie** | Secrets Management |
| **Ort** | `app.py:1923-1924`, `employers.json` |
| **Beschreibung** | HR-Provider API-Keys werden im Klartext in JSON gespeichert |
| **Auswirkung** | Datei-Zugriff ermöglicht Zugriff auf alle HR-Daten |
| **Status** | OFFEN |

### SV-003: Kein HTTPS

| Aspekt | Wert |
|--------|------|
| **Schweregrad** | KRITISCH |
| **Kategorie** | Transport Security |
| **Ort** | `run.py:57-64` |
| **Beschreibung** | Server bindet auf HTTP ohne TLS-Verschlüsselung |
| **Auswirkung** | Credentials und sensible Daten werden unverschlüsselt übertragen |
| **Status** | OFFEN |

### SV-004: Kein CSRF-Schutz

| Aspekt | Wert |
|--------|------|
| **Schweregrad** | KRITISCH |
| **Kategorie** | Web Security |
| **Ort** | Alle POST-Formulare |
| **Beschreibung** | Keine CSRF-Token-Validierung implementiert |
| **Auswirkung** | Cross-Site Request Forgery Angriffe möglich |
| **Status** | OFFEN |

### SV-005: Debug-Modus aktivierbar

| Aspekt | Wert |
|--------|------|
| **Schweregrad** | KRITISCH |
| **Kategorie** | Configuration |
| **Ort** | `app.py:2718` |
| **Beschreibung** | Flask Debug-Modus ist hardcodiert aktiviert bei direkter Ausführung |
| **Code** | `app.run(debug=True, port=port)` |
| **Auswirkung** | Remote Code Execution über Werkzeug Debugger möglich |
| **Status** | OFFEN |

## Hohe Schwachstellen (HIGH)

### SV-006: Keine Brute-Force-Protection

| Aspekt | Wert |
|--------|------|
| **Schweregrad** | HOCH |
| **Kategorie** | Authentication |
| **Ort** | `app.py:1569-1603` |
| **Beschreibung** | Kein Rate-Limiting bei Login-Versuchen |
| **Auswirkung** | Passwörter können durch Brute-Force ermittelt werden |
| **Status** | OFFEN |

### SV-007: GitHub PAT im Klartext

| Aspekt | Wert |
|--------|------|
| **Schweregrad** | HOCH |
| **Kategorie** | Secrets Management |
| **Ort** | `app.py:1676-1677`, `secrets.json` |
| **Beschreibung** | GitHub Personal Access Token wird im Klartext gespeichert |
| **Auswirkung** | Token-Kompromittierung ermöglicht Repository-Zugriff |
| **Status** | OFFEN |

### SV-008: Keine Security Headers

| Aspekt | Wert |
|--------|------|
| **Schweregrad** | HOCH |
| **Kategorie** | Web Security |
| **Ort** | `app.py` (fehlend) |
| **Beschreibung** | Keine Security Headers konfiguriert (CSP, X-Frame-Options, etc.) |
| **Auswirkung** | XSS, Clickjacking und andere Angriffe erleichtert |
| **Status** | OFFEN |

### SV-009: Fehlende Zugriffskontrolle auf Arbeitgeber

| Aspekt | Wert |
|--------|------|
| **Schweregrad** | HOCH |
| **Kategorie** | Authorization |
| **Ort** | Alle `/employer/<id>/*` Routen |
| **Beschreibung** | Jeder authentifizierte Benutzer kann auf alle Arbeitgeber zugreifen |
| **Auswirkung** | Unbefugter Zugriff auf sensible HR-Daten |
| **Status** | OFFEN |

### SV-010: Keine Log-Rotation

| Aspekt | Wert |
|--------|------|
| **Schweregrad** | HOCH |
| **Kategorie** | Operations |
| **Ort** | `app.py:33` |
| **Beschreibung** | Log-Datei wächst unbegrenzt (Append-Modus, keine Rotation) |
| **Auswirkung** | Disk-Overflow, Denial of Service |
| **Status** | OFFEN |

### SV-011: Keine automatisierten Tests

| Aspekt | Wert |
|--------|------|
| **Schweregrad** | HOCH |
| **Kategorie** | Quality Assurance |
| **Ort** | Projekt-Root (fehlend) |
| **Beschreibung** | Keine Unit-, Integration- oder Security-Tests vorhanden |
| **Auswirkung** | Fehler und Sicherheitslücken bleiben unentdeckt |
| **Status** | OFFEN |

## Mittlere Schwachstellen (MEDIUM)

### SV-012: Keine Passwort-Policy

| Aspekt | Wert |
|--------|------|
| **Schweregrad** | MITTEL |
| **Kategorie** | Authentication |
| **Ort** | `app.py:1647`, `app.py:1722-1723` |
| **Beschreibung** | Keine Mindestlänge oder Komplexitätsanforderungen für Passwörter |
| **Auswirkung** | Schwache Passwörter möglich |
| **Status** | OFFEN |

### SV-013: Kein Session-Timeout

| Aspekt | Wert |
|--------|------|
| **Schweregrad** | MITTEL |
| **Kategorie** | Session Management |
| **Ort** | `app.py` (fehlend) |
| **Beschreibung** | Sessions laufen nie automatisch ab |
| **Auswirkung** | Gestohlene Sessions bleiben dauerhaft gültig |
| **Status** | OFFEN |

### SV-014: PII in Logs

| Aspekt | Wert |
|--------|------|
| **Schweregrad** | MITTEL |
| **Kategorie** | Privacy / DSGVO |
| **Ort** | `app.py:1997` und andere |
| **Beschreibung** | Mitarbeiter- und Arbeitgebernamen werden im Klartext geloggt |
| **Auswirkung** | Datenschutz-Compliance-Risiko |
| **Status** | OFFEN |

### SV-015: Keine Input-Validierung bei Arbeitgeber-Erstellung

| Aspekt | Wert |
|--------|------|
| **Schweregrad** | MITTEL |
| **Kategorie** | Input Validation |
| **Ort** | `app.py:1918-1932` |
| **Beschreibung** | Provider-Key und Name werden nicht validiert |
| **Auswirkung** | Ungültige Daten können gespeichert werden |
| **Status** | OFFEN |

### SV-016: Kein Audit-Trail für administrative Aktionen

| Aspekt | Wert |
|--------|------|
| **Schweregrad** | MITTEL |
| **Kategorie** | Auditing |
| **Ort** | `app.py:1637-1667` |
| **Beschreibung** | Benutzer-Erstellung/Löschung wird nicht geloggt |
| **Auswirkung** | Fehlende Nachvollziehbarkeit bei Sicherheitsvorfällen |
| **Status** | OFFEN |

### SV-017: Auto-Update ohne Signaturprüfung

| Aspekt | Wert |
|--------|------|
| **Schweregrad** | MITTEL |
| **Kategorie** | Supply Chain |
| **Ort** | `updater.py:92-142` |
| **Beschreibung** | ZIP-Download wird nicht kryptographisch verifiziert |
| **Auswirkung** | Man-in-the-Middle könnte Malware einschleusen |
| **Status** | OFFEN |

### SV-018: Secure Cookie-Flag fehlt

| Aspekt | Wert |
|--------|------|
| **Schweregrad** | MITTEL |
| **Kategorie** | Session Management |
| **Ort** | Flask-Konfiguration (fehlend) |
| **Beschreibung** | Session-Cookie ohne Secure-Flag (wird auch über HTTP gesendet) |
| **Auswirkung** | Session-Hijacking bei HTTP-Verbindung |
| **Status** | OFFEN |

### SV-019: Keine SRI-Hashes für externe Ressourcen

| Aspekt | Wert |
|--------|------|
| **Schweregrad** | MITTEL |
| **Kategorie** | Supply Chain |
| **Ort** | `base.html:9-11` |
| **Beschreibung** | Google Fonts ohne Subresource Integrity |
| **Auswirkung** | CDN-Kompromittierung könnte Malware ausliefern |
| **Status** | OFFEN |

## Niedrige Schwachstellen (LOW)

### SV-020: Fehlende Account-Lockout-Policy

| Aspekt | Wert |
|--------|------|
| **Schweregrad** | NIEDRIG |
| **Kategorie** | Authentication |
| **Ort** | `app.py:1569-1603` |
| **Beschreibung** | Accounts werden nie gesperrt, egal wie viele Fehlversuche |
| **Auswirkung** | Unbegrenztes Raten möglich (in Kombination mit SV-006) |
| **Status** | OFFEN |

### SV-021: Fehlgeschlagene Logins nicht geloggt

| Aspekt | Wert |
|--------|------|
| **Schweregrad** | NIEDRIG |
| **Kategorie** | Logging |
| **Ort** | `app.py:1599-1601` |
| **Beschreibung** | Flash-Nachricht wird angezeigt, aber kein Log-Eintrag |
| **Auswirkung** | Angriffsversuche bleiben unbemerkt |
| **Status** | OFFEN |

### SV-022: Monolithische Codebasis

| Aspekt | Wert |
|--------|------|
| **Schweregrad** | NIEDRIG |
| **Kategorie** | Code Quality |
| **Ort** | `app.py` (~2719 Zeilen) |
| **Beschreibung** | Gesamte Anwendungslogik in einer Datei |
| **Auswirkung** | Erschwerte Wartung und Security-Audits |
| **Status** | OFFEN |

### SV-023: Unbegrenzte Datenspeicherung

| Aspekt | Wert |
|--------|------|
| **Schweregrad** | NIEDRIG |
| **Kategorie** | Data Retention |
| **Ort** | `app.py:1143-1148`, `app.py:221-247` |
| **Beschreibung** | Snapshots und History werden nie automatisch gelöscht |
| **Auswirkung** | Speicherplatz-Probleme, DSGVO-Compliance |
| **Status** | OFFEN |

## Informational (INFO)

### SV-024: Kein CI/CD-Pipeline

| Aspekt | Wert |
|--------|------|
| **Schweregrad** | INFO |
| **Kategorie** | DevOps |
| **Ort** | Projekt-Root (fehlend) |
| **Beschreibung** | Keine automatisierte Build/Test/Deploy-Pipeline |
| **Status** | OFFEN |

### SV-025: Keine Health-Check-Endpoints

| Aspekt | Wert |
|--------|------|
| **Schweregrad** | INFO |
| **Kategorie** | Operations |
| **Ort** | `app.py` (fehlend) |
| **Beschreibung** | Kein `/health` oder `/ready` Endpoint für Monitoring |
| **Status** | OFFEN |

### SV-026: Keine Lockfile für Dependencies

| Aspekt | Wert |
|--------|------|
| **Schweregrad** | INFO |
| **Kategorie** | Supply Chain |
| **Ort** | Projekt-Root |
| **Beschreibung** | Nur requirements.txt, kein pip-tools oder poetry Lockfile |
| **Status** | OFFEN |

---

## Statistik

| Schweregrad | Anzahl |
|-------------|--------|
| KRITISCH | 5 |
| HOCH | 6 |
| MITTEL | 8 |
| NIEDRIG | 4 |
| INFO | 3 |
| **GESAMT** | **26** |

---

**Letzte Aktualisierung:** 28.01.2026
