# 02 - Maßnahmenkatalog

## SV-001: Hardcodierter Flask Secret Key

| Aspekt | Wert |
|--------|------|
| **Kategorie** | Secrets Management |
| **Schweregrad** | KRITISCH |
| **Betroffene Komponenten** | `app.py:1481` |
| **Root Cause** | Secret Key direkt im Quellcode definiert |
| **Fix-Strategie** | Secret Key aus Umgebungsvariable oder secrets.json laden |
| **Konkrete Änderungen** | `app.py` - Secret Key Initialisierung ändern |
| **Sicherheitswirkung** | Verhindert Session-Fälschung bei bekanntem Quellcode |
| **Regressionen** | Bestehende Sessions werden invalidiert |
| **Verifikation** | Given: Neuer Secret Key; When: Session-Cookie manipuliert; Then: Zugriff verweigert |
| **Status** | GEPLANT |

---

## SV-002: API-Credentials im Klartext

| Aspekt | Wert |
|--------|------|
| **Kategorie** | Secrets Management |
| **Schweregrad** | KRITISCH |
| **Betroffene Komponenten** | `app.py:1919-1931`, `employers.json` |
| **Root Cause** | Credentials werden ohne Verschlüsselung gespeichert |
| **Fix-Strategie** | Symmetrische Verschlüsselung mit Master-Key aus Umgebungsvariable |
| **Konkrete Änderungen** | `app.py` - Neue Funktionen `encrypt_credential()`, `decrypt_credential()`; EmployerStore anpassen |
| **Sicherheitswirkung** | Datei-Zugriff allein reicht nicht mehr für API-Zugang |
| **Regressionen** | Bestehende employers.json muss migriert werden |
| **Verifikation** | Given: Verschlüsselte Credentials; When: employers.json gelesen; Then: Klartext nicht sichtbar |
| **Status** | GEPLANT |

---

## SV-003: Kein HTTPS

| Aspekt | Wert |
|--------|------|
| **Kategorie** | Transport Security |
| **Schweregrad** | KRITISCH |
| **Betroffene Komponenten** | `run.py:57-64`, Deployment |
| **Root Cause** | Waitress ohne TLS-Konfiguration |
| **Fix-Strategie** | Option A: Reverse Proxy (nginx) mit TLS; Option B: Waitress hinter stunnel |
| **Konkrete Änderungen** | Neue Datei `nginx.conf` oder Anpassung `run.py` für TLS |
| **Sicherheitswirkung** | Verschlüsselte Übertragung aller Daten |
| **Regressionen** | Zertifikat-Management erforderlich; URL-Änderung (http → https) |
| **Verifikation** | Given: HTTPS konfiguriert; When: Verbindung ohne TLS; Then: Redirect oder Ablehnung |
| **Status** | GEPLANT |

---

## SV-004: Kein CSRF-Schutz

| Aspekt | Wert |
|--------|------|
| **Kategorie** | Web Security |
| **Schweregrad** | KRITISCH |
| **Betroffene Komponenten** | Alle POST-Formulare, Templates |
| **Root Cause** | Flask-WTF nicht installiert, keine Token-Validierung |
| **Fix-Strategie** | Flask-WTF installieren, CSRFProtect aktivieren, Token in alle Formulare |
| **Konkrete Änderungen** | `requirements.txt` - Flask-WTF hinzufügen; `app.py` - CSRFProtect initialisieren; Alle Templates - `{{ csrf_token() }}` hinzufügen |
| **Sicherheitswirkung** | CSRF-Angriffe werden verhindert |
| **Regressionen** | API-Calls von Frontend benötigen CSRF-Header |
| **Verifikation** | Given: CSRF aktiviert; When: POST ohne Token; Then: 400 Bad Request |
| **Status** | GEPLANT |

---

## SV-005: Debug-Modus aktivierbar

| Aspekt | Wert |
|--------|------|
| **Kategorie** | Configuration |
| **Schweregrad** | KRITISCH |
| **Betroffene Komponenten** | `app.py:2718` |
| **Root Cause** | `debug=True` hardcodiert in `app.run()` |
| **Fix-Strategie** | Debug-Modus über Umgebungsvariable steuern, Default: False |
| **Konkrete Änderungen** | `app.py:2718` - `debug=os.getenv('FLASK_DEBUG', 'false').lower() == 'true'` |
| **Sicherheitswirkung** | Verhindert RCE über Werkzeug Debugger |
| **Regressionen** | Entwickler müssen explizit Debug aktivieren |
| **Verifikation** | Given: Produktions-Deployment; When: Exception auftritt; Then: Kein interaktiver Debugger |
| **Status** | GEPLANT |

---

## SV-006: Keine Brute-Force-Protection

| Aspekt | Wert |
|--------|------|
| **Kategorie** | Authentication |
| **Schweregrad** | HOCH |
| **Betroffene Komponenten** | `app.py:1569-1603` |
| **Root Cause** | Kein Rate-Limiting auf Login-Route |
| **Fix-Strategie** | Flask-Limiter installieren, Login-Route limitieren (z.B. 5/Minute) |
| **Konkrete Änderungen** | `requirements.txt` - Flask-Limiter; `app.py` - Limiter initialisieren und auf `/login` anwenden |
| **Sicherheitswirkung** | Brute-Force-Angriffe werden verlangsamt |
| **Regressionen** | Legitime Benutzer könnten temporär gesperrt werden |
| **Verifikation** | Given: Rate-Limit 5/min; When: 6 Login-Versuche in 1 Minute; Then: 429 Too Many Requests |
| **Status** | GEPLANT |

---

## SV-007: GitHub PAT im Klartext

| Aspekt | Wert |
|--------|------|
| **Kategorie** | Secrets Management |
| **Schweregrad** | HOCH |
| **Betroffene Komponenten** | `app.py:1676-1677`, `secrets.json` |
| **Root Cause** | PAT wird ohne Verschlüsselung gespeichert |
| **Fix-Strategie** | Gleiche Verschlüsselung wie SV-002 verwenden |
| **Konkrete Änderungen** | `app.py` - `save_secrets()` und `load_secrets()` mit Verschlüsselung |
| **Sicherheitswirkung** | PAT nicht mehr im Klartext lesbar |
| **Regressionen** | Bestehender PAT muss neu eingegeben werden |
| **Verifikation** | Given: Verschlüsselter PAT; When: secrets.json gelesen; Then: Kein Klartext |
| **Status** | GEPLANT |

---

## SV-008: Keine Security Headers

| Aspekt | Wert |
|--------|------|
| **Kategorie** | Web Security |
| **Schweregrad** | HOCH |
| **Betroffene Komponenten** | `app.py` (fehlend) |
| **Root Cause** | Keine Header-Konfiguration implementiert |
| **Fix-Strategie** | `@app.after_request` Handler mit Security Headers |
| **Konkrete Änderungen** | `app.py` - Neue Funktion `add_security_headers()` |
| **Sicherheitswirkung** | XSS, Clickjacking, MIME-Sniffing erschwert |
| **Regressionen** | CSP könnte Inline-Scripts blockieren |
| **Verifikation** | Given: Security Headers; When: Response empfangen; Then: X-Frame-Options, CSP etc. vorhanden |
| **Status** | GEPLANT |

---

## SV-009: Fehlende Arbeitgeber-Zugriffskontrolle

| Aspekt | Wert |
|--------|------|
| **Kategorie** | Authorization |
| **Schweregrad** | HOCH |
| **Betroffene Komponenten** | Alle `/employer/<id>/*` Routen |
| **Root Cause** | Keine Prüfung, ob Benutzer Zugriff auf Arbeitgeber hat |
| **Fix-Strategie** | Benutzer-Arbeitgeber-Zuordnung in Datenmodell; Decorator für Zugriffsprüfung |
| **Konkrete Änderungen** | `users.json` - Feld `allowed_employers` hinzufügen; `app.py` - Decorator `@requires_employer_access` |
| **Sicherheitswirkung** | Benutzer sehen nur zugewiesene Arbeitgeber |
| **Regressionen** | Master-Benutzer sollten alle sehen können; Migration bestehender Benutzer |
| **Verifikation** | Given: Benutzer ohne Zugriff auf Arbeitgeber X; When: GET /employer/X; Then: 403 Forbidden |
| **Status** | GEPLANT |

---

## SV-010: Keine Log-Rotation

| Aspekt | Wert |
|--------|------|
| **Kategorie** | Operations |
| **Schweregrad** | HOCH |
| **Betroffene Komponenten** | `app.py:33` |
| **Root Cause** | `FileHandler` ohne Rotation |
| **Fix-Strategie** | `RotatingFileHandler` verwenden |
| **Konkrete Änderungen** | `app.py:33` - `FileHandler` durch `RotatingFileHandler` ersetzen (z.B. 10MB, 5 Backups) |
| **Sicherheitswirkung** | Verhindert Disk-Overflow |
| **Regressionen** | Alte Logs werden überschrieben |
| **Verifikation** | Given: Rotation bei 10MB; When: Log erreicht 10MB; Then: Neue Datei erstellt, Backup vorhanden |
| **Status** | GEPLANT |

---

## SV-011: Keine automatisierten Tests

| Aspekt | Wert |
|--------|------|
| **Kategorie** | Quality Assurance |
| **Schweregrad** | HOCH |
| **Betroffene Komponenten** | Projekt-Root |
| **Root Cause** | Kein Test-Framework eingerichtet |
| **Fix-Strategie** | pytest einrichten, grundlegende Tests für kritische Funktionen |
| **Konkrete Änderungen** | Neuer Ordner `tests/`; `requirements.txt` - pytest hinzufügen; Mindestens: Login-Tests, Provider-Tests |
| **Sicherheitswirkung** | Sicherheits-Regressionen werden erkannt |
| **Regressionen** | Keine |
| **Verifikation** | Given: Tests vorhanden; When: `pytest` ausgeführt; Then: Tests laufen erfolgreich |
| **Status** | GEPLANT |

---

## SV-012 bis SV-026

(Detaillierte Maßnahmen für mittlere, niedrige und informelle Befunde - Format analog zu oben)

### SV-012: Keine Passwort-Policy
- **Fix-Strategie**: Validierung in `settings()` und `user_settings()` hinzufügen
- **Konkrete Änderungen**: `app.py` - Funktion `validate_password()`; Mindestlänge 8, Komplexität

### SV-013: Kein Session-Timeout
- **Fix-Strategie**: `PERMANENT_SESSION_LIFETIME` konfigurieren
- **Konkrete Änderungen**: `app.py` - `app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=8)`

### SV-014: PII in Logs
- **Fix-Strategie**: Anonymisierung oder Pseudonymisierung in `custom_log()`
- **Konkrete Änderungen**: `app.py:60-92` - Optionale Anonymisierung von Namen

### SV-015: Keine Input-Validierung
- **Fix-Strategie**: Whitelist für `provider_key`, Längenprüfungen
- **Konkrete Änderungen**: `app.py:1918-1932` - Validierung hinzufügen

### SV-016: Kein Audit-Trail
- **Fix-Strategie**: Separate Audit-Log-Datei für administrative Aktionen
- **Konkrete Änderungen**: Neuer Logger `audit_logger`, Aufrufe in Admin-Routen

### SV-017: Update ohne Signatur
- **Fix-Strategie**: GPG-Signatur oder Checksum-Verifizierung
- **Konkrete Änderungen**: `updater.py` - Signatur-Prüfung hinzufügen

### SV-018: Secure Cookie fehlt
- **Fix-Strategie**: `SESSION_COOKIE_SECURE = True` (nach HTTPS-Setup)
- **Konkrete Änderungen**: `app.py` - Cookie-Konfiguration

### SV-019: Keine SRI-Hashes
- **Fix-Strategie**: Integrity-Attribute zu externen Ressourcen hinzufügen
- **Konkrete Änderungen**: `base.html:9-11` - `integrity="sha384-..."` hinzufügen

### SV-020: Fehlende Account-Lockout
- **Fix-Strategie**: Fehlversuch-Zähler pro Benutzer, temporäre Sperre
- **Konkrete Änderungen**: `users.json` - Feld `failed_attempts`, `locked_until`

### SV-021: Failed Logins nicht geloggt
- **Fix-Strategie**: `custom_log()` bei fehlgeschlagenem Login
- **Konkrete Änderungen**: `app.py:1599-1601` - Log-Aufruf hinzufügen

### SV-022: Monolithische Codebasis
- **Fix-Strategie**: Refactoring in Module (routes.py, providers.py, utils.py)
- **Konkrete Änderungen**: Neue Dateien, Imports anpassen

### SV-023: Unbegrenzte Datenspeicherung
- **Fix-Strategie**: Cleanup-Job für alte Snapshots/History (z.B. > 90 Tage)
- **Konkrete Änderungen**: Neue Funktion `cleanup_old_data()`, Aufruf beim Start

### SV-024: Kein CI/CD
- **Fix-Strategie**: GitHub Actions Workflow einrichten
- **Konkrete Änderungen**: `.github/workflows/ci.yml`

### SV-025: Keine Health-Checks
- **Fix-Strategie**: `/health` und `/ready` Endpunkte hinzufügen
- **Konkrete Änderungen**: `app.py` - Neue Routen

### SV-026: Keine Lockfile
- **Fix-Strategie**: pip-tools oder poetry einsetzen
- **Konkrete Änderungen**: `requirements.in` + `pip-compile`

---

**Letzte Aktualisierung:** 28.01.2026
