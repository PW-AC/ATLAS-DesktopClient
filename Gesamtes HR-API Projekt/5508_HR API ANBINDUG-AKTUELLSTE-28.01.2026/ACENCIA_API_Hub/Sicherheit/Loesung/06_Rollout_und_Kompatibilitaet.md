# 06 - Rollout und Kompatibilität

## Empfohlene Umsetzungsreihenfolge

### Sprint 1: Quick Wins (Niedrig-Risiko, Hohe Wirkung)

| Reihenfolge | Maßnahme | Aufwand | Risiko |
|-------------|----------|---------|--------|
| 1 | SV-005: Debug-Modus deaktivieren | 5 min | Niedrig |
| 2 | SV-001: Secret Key externalisieren | 30 min | Niedrig |
| 3 | SV-010: Log-Rotation | 15 min | Niedrig |
| 4 | SV-008: Security Headers | 30 min | Niedrig |
| 5 | SV-021: Failed Logins loggen | 10 min | Niedrig |

**Gesamtaufwand Sprint 1:** ~1.5 Stunden

### Sprint 2: Authentication & Session

| Reihenfolge | Maßnahme | Aufwand | Risiko |
|-------------|----------|---------|--------|
| 6 | SV-006: Rate-Limiting | 1h | Mittel |
| 7 | SV-012: Passwort-Policy | 30 min | Niedrig |
| 8 | SV-013: Session-Timeout | 15 min | Niedrig |
| 9 | SV-018: Secure Cookie (nach HTTPS) | 5 min | Niedrig |
| 10 | SV-020: Account-Lockout | 1h | Mittel |

**Gesamtaufwand Sprint 2:** ~3 Stunden

### Sprint 3: Secrets & Encryption

| Reihenfolge | Maßnahme | Aufwand | Risiko |
|-------------|----------|---------|--------|
| 11 | SV-002: Credential-Verschlüsselung | 3h | Mittel |
| 12 | SV-007: PAT-Verschlüsselung (gleicher Fix) | inkl. | Mittel |
| 13 | Migrations-Script für bestehende Daten | 1h | Mittel |

**Gesamtaufwand Sprint 3:** ~4 Stunden

### Sprint 4: Transport Security

| Reihenfolge | Maßnahme | Aufwand | Risiko |
|-------------|----------|---------|--------|
| 14 | SV-003: HTTPS (Reverse Proxy Setup) | 4h | Hoch |
| 15 | SV-004: CSRF-Schutz | 2h | Hoch |
| 16 | SV-019: SRI-Hashes | 30 min | Niedrig |

**Gesamtaufwand Sprint 4:** ~6.5 Stunden

### Sprint 5: Authorization & Audit

| Reihenfolge | Maßnahme | Aufwand | Risiko |
|-------------|----------|---------|--------|
| 17 | SV-009: Arbeitgeber-Zugriffskontrolle | 4h | Hoch |
| 18 | SV-016: Audit-Trail | 2h | Niedrig |
| 19 | SV-014: PII-Anonymisierung in Logs | 1h | Niedrig |

**Gesamtaufwand Sprint 5:** ~7 Stunden

### Sprint 6: Quality & Testing

| Reihenfolge | Maßnahme | Aufwand | Risiko |
|-------------|----------|---------|--------|
| 20 | SV-011: Test-Framework Setup | 2h | Keine |
| 21 | Unit-Tests für kritische Funktionen | 4h | Keine |
| 22 | SV-015: Input-Validierung | 2h | Niedrig |

**Gesamtaufwand Sprint 6:** ~8 Stunden

### Sprint 7: Cleanup & Optional

| Reihenfolge | Maßnahme | Aufwand | Risiko |
|-------------|----------|---------|--------|
| 23 | SV-023: Data Retention/Cleanup | 2h | Niedrig |
| 24 | SV-017: Update-Signaturprüfung | 4h | Mittel |
| 25 | SV-022: Code-Refactoring | 8h+ | Mittel |
| 26 | SV-024: CI/CD-Pipeline | 4h | Keine |
| 27 | SV-025: Health-Check Endpoints | 30 min | Keine |
| 28 | SV-026: Lockfile einführen | 30 min | Keine |

**Gesamtaufwand Sprint 7:** ~19+ Stunden

## Kompatibilität

### Bestehende Benutzer

| Änderung | Auswirkung | Maßnahme |
|----------|------------|----------|
| Secret Key | Session ungültig | Benutzer müssen sich neu anmelden |
| Passwort-Policy | Schwache Passwörter | Bestehende Passwörter bleiben gültig; bei nächster Änderung Policy durchgesetzt |
| CSRF-Token | JavaScript-Anpassungen | Template-Update vor Deployment |
| Session-Timeout | Automatisches Logout | Benutzer informieren |

### Bestehende Daten

| Daten | Migration | Rollback |
|-------|-----------|----------|
| users.json | Keine Migration nötig | - |
| employers.json | Automatische Verschlüsselung | Backup vor Migration |
| secrets.json | Automatische Verschlüsselung | Backup vor Migration |
| _snapshots/ | Keine Änderung | - |
| _history/ | Keine Änderung | - |

### Browser-Kompatibilität

| Feature | Browser-Support |
|---------|-----------------|
| CSRF-Token | Alle modernen Browser |
| Secure Cookie | Erfordert HTTPS |
| SRI-Hashes | Chrome 45+, Firefox 43+, Safari 11+ |
| CSP | Chrome 25+, Firefox 23+, Safari 7+ |

## Deployment-Checkliste

### Vor dem Deployment

- [ ] Backup aller Daten (users.json, employers.json, secrets.json)
- [ ] Backup des aktuellen Code-Stands
- [ ] Umgebungsvariablen vorbereitet
- [ ] Zertifikate bereit (für HTTPS)
- [ ] Benutzer informiert (Session-Invalidierung)

### Deployment-Schritte

1. **Wartungsmodus aktivieren** (falls vorhanden)
2. **Backup erstellen**
3. **Code aktualisieren**
4. **requirements.txt installieren**
5. **Umgebungsvariablen setzen**
6. **Server neu starten**
7. **Smoke Tests durchführen**
8. **Wartungsmodus deaktivieren**

### Nach dem Deployment

- [ ] Login funktioniert
- [ ] Provider-Verbindungen funktionieren
- [ ] Exporte funktionieren
- [ ] Keine Fehler in Logs
- [ ] Security Headers vorhanden (Browser DevTools)
- [ ] HTTPS funktioniert (falls implementiert)

## Rollback-Prozedur

Bei kritischen Problemen:

1. **Server stoppen**
2. **Code auf vorherigen Stand zurücksetzen**
3. **Daten-Backup wiederherstellen** (falls nötig)
4. **Umgebungsvariablen zurücksetzen**
5. **Server starten**
6. **Verifizieren**

---

**Letzte Aktualisierung:** 28.01.2026
