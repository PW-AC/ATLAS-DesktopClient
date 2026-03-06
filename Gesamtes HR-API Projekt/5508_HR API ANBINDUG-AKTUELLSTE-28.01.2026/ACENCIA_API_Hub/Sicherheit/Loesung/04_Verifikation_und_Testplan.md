# 04 - Verifikation und Testplan

## Test-Szenarien pro Maßnahme

### SV-001: Secret Key externalisiert

**Test 1: Secret Key aus Umgebung**
```
Given: ACENCIA_SECRET_KEY ist in Umgebung gesetzt
When: Anwendung startet
Then: Secret Key wird aus Umgebung geladen
```

**Test 2: Fehlender Secret Key**
```
Given: ACENCIA_SECRET_KEY ist NICHT gesetzt
When: Anwendung startet
Then: Anwendung startet NICHT oder verwendet sicheren Random-Key
```

**Test 3: Session-Integrität**
```
Given: Anwendung mit neuem Secret Key
When: Alter Session-Cookie verwendet
Then: Session ungültig, Redirect zu Login
```

---

### SV-002: API-Credentials verschlüsselt

**Test 1: Verschlüsselung beim Speichern**
```
Given: Neuer Arbeitgeber mit Credentials
When: Arbeitgeber gespeichert
Then: employers.json enthält verschlüsselte Werte (Base64)
```

**Test 2: Entschlüsselung beim Laden**
```
Given: Verschlüsselte Credentials in employers.json
When: Provider instanziiert
Then: API-Aufruf funktioniert mit entschlüsselten Credentials
```

**Test 3: Falscher Master-Key**
```
Given: Verschlüsselte Credentials
When: Falscher ACENCIA_MASTER_KEY
Then: Entschlüsselung schlägt fehl, Fehlermeldung
```

---

### SV-003: HTTPS aktiv

**Test 1: HTTPS-Verbindung**
```
Given: Server mit TLS konfiguriert
When: Verbindung über HTTPS
Then: Verbindung erfolgreich, Zertifikat gültig
```

**Test 2: HTTP-Redirect**
```
Given: HTTPS konfiguriert
When: Verbindung über HTTP
Then: Redirect zu HTTPS (301/302)
```

---

### SV-004: CSRF-Schutz aktiv

**Test 1: POST ohne Token**
```
Given: CSRF aktiviert
When: POST /login ohne csrf_token
Then: 400 Bad Request
```

**Test 2: POST mit gültigem Token**
```
Given: CSRF aktiviert
When: POST /login mit gültigem csrf_token
Then: Request wird verarbeitet
```

**Test 3: API mit X-CSRFToken Header**
```
Given: CSRF aktiviert
When: POST /api/user/theme mit X-CSRFToken Header
Then: Request wird verarbeitet
```

---

### SV-005: Debug-Modus deaktiviert

**Test 1: Produktionsmodus**
```
Given: FLASK_DEBUG nicht gesetzt oder 'false'
When: Exception in Route
Then: Generic Error Page, kein Werkzeug Debugger
```

**Test 2: Entwicklungsmodus**
```
Given: FLASK_DEBUG='true'
When: Exception in Route
Then: Werkzeug Debugger verfügbar
```

---

### SV-006: Rate-Limiting aktiv

**Test 1: Unter Limit**
```
Given: Rate-Limit 5/Minute auf /login
When: 3 Requests in 1 Minute
Then: Alle Requests erfolgreich
```

**Test 2: Über Limit**
```
Given: Rate-Limit 5/Minute auf /login
When: 6 Requests in 1 Minute
Then: Request 6 erhält 429 Too Many Requests
```

**Test 3: Limit-Reset**
```
Given: Limit erreicht
When: 1 Minute wartet
Then: Nächster Request erfolgreich
```

---

### SV-008: Security Headers

**Test 1: X-Frame-Options**
```
Given: Security Headers aktiv
When: Response empfangen
Then: X-Frame-Options: DENY vorhanden
```

**Test 2: Content-Security-Policy**
```
Given: Security Headers aktiv
When: Response empfangen
Then: CSP Header vorhanden
```

**Test 3: HSTS (nur bei HTTPS)**
```
Given: HTTPS aktiv
When: Response empfangen
Then: Strict-Transport-Security Header vorhanden
```

---

### SV-009: Arbeitgeber-Zugriffskontrolle

**Test 1: Master-Zugriff**
```
Given: Master-Benutzer angemeldet
When: GET /employer/beliebige-id
Then: Zugriff gewährt
```

**Test 2: Autorisierter Benutzer**
```
Given: Normaler Benutzer mit allowed_employers=['id-1']
When: GET /employer/id-1
Then: Zugriff gewährt
```

**Test 3: Nicht autorisierter Benutzer**
```
Given: Normaler Benutzer mit allowed_employers=['id-1']
When: GET /employer/id-2
Then: 403 Forbidden oder Redirect
```

---

### SV-010: Log-Rotation

**Test 1: Rotation bei Größe**
```
Given: RotatingFileHandler mit maxBytes=1MB
When: Log erreicht 1MB
Then: server.log.1 erstellt, server.log neu
```

**Test 2: Backup-Limit**
```
Given: backupCount=5
When: 6. Rotation
Then: Nur 5 Backups vorhanden, älteste gelöscht
```

---

### SV-011: Automatisierte Tests

**Test 1: pytest läuft**
```
Given: pytest installiert, tests/ vorhanden
When: pytest ausgeführt
Then: Tests laufen, Exit-Code 0 bei Erfolg
```

**Test 2: Login-Test vorhanden**
```
Given: tests/test_auth.py existiert
When: pytest tests/test_auth.py
Then: Login-Szenarien werden getestet
```

---

### SV-012: Passwort-Policy

**Test 1: Zu kurzes Passwort**
```
Given: Passwort "abc"
When: validate_password("abc")
Then: (False, "Passwort muss mindestens 8 Zeichen...")
```

**Test 2: Gültiges Passwort**
```
Given: Passwort "Secure123!"
When: validate_password("Secure123!")
Then: (True, "")
```

---

### SV-013: Session-Timeout

**Test 1: Session läuft ab**
```
Given: PERMANENT_SESSION_LIFETIME = 8h
When: Session älter als 8h
Then: Benutzer muss sich neu anmelden
```

---

## Manueller Test-Katalog

### Sicherheits-Checkliste

- [ ] Secret Key nicht im Quellcode
- [ ] Credentials nicht im Klartext in JSON-Dateien
- [ ] HTTPS aktiv und funktionsfähig
- [ ] CSRF-Token in allen Formularen
- [ ] Debug-Modus in Produktion deaktiviert
- [ ] Rate-Limiting funktioniert
- [ ] Security Headers in allen Responses
- [ ] Arbeitgeber-Zugriff eingeschränkt
- [ ] Log-Rotation aktiv
- [ ] Tests laufen erfolgreich

---

**Letzte Aktualisierung:** 28.01.2026
