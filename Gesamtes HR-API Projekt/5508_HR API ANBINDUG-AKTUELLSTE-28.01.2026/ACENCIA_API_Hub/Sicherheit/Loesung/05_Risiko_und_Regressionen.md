# 05 - Risiko und Regressionen

## Migrationsrisiken

### SV-001: Secret Key Externalisierung

| Risiko | Auswirkung | Mitigierung |
|--------|------------|-------------|
| Alle Sessions invalidiert | Benutzer müssen sich neu anmelden | Ankündigung vor Deployment |
| Vergessener Umgebungsvariable | App startet nicht | Fallback auf generierter Key mit Warnung |

### SV-002: Credential-Verschlüsselung

| Risiko | Auswirkung | Mitigierung |
|--------|------------|-------------|
| Unverschlüsselte Daten nicht mehr lesbar | Provider-Verbindung schlägt fehl | Automatische Migration beim Start |
| Master-Key verloren | Credentials nicht entschlüsselbar | Backup des Master-Keys; Fallback: Credentials neu eingeben |
| Performance-Overhead | Langsameres Laden | Caching der entschlüsselten Werte |

### SV-003: HTTPS-Einführung

| Risiko | Auswirkung | Mitigierung |
|--------|------------|-------------|
| Zertifikat-Probleme | Keine Verbindung möglich | Selbstsigniertes Zertifikat für Test; Let's Encrypt für Produktion |
| Interne URLs brechen | Bookmarks/Links funktionieren nicht | HTTP → HTTPS Redirect |
| Mixed Content | Externe Ressourcen blockiert | CSP anpassen; SRI-Hashes |

### SV-004: CSRF-Schutz

| Risiko | Auswirkung | Mitigierung |
|--------|------------|-------------|
| API-Calls ohne Token schlagen fehl | JavaScript-Funktionalität bricht | X-CSRFToken Header in allen fetch-Calls |
| Externe Integrationen | Drittanbieter können nicht mehr posten | API-Endpunkte explizit vom CSRF ausnehmen |
| Template-Vergessen | Formulare funktionieren nicht | Code-Review; automatisierte Tests |

### SV-006: Rate-Limiting

| Risiko | Auswirkung | Mitigierung |
|--------|------------|-------------|
| Legitime Benutzer gesperrt | Temporärer Zugriffsverlust | Großzügige Limits; Whitelist für bekannte IPs |
| Shared NAT | Alle Benutzer hinter einer IP gesperrt | Benutzer-basiertes Limiting als Alternative |

### SV-009: Arbeitgeber-Zugriffskontrolle

| Risiko | Auswirkung | Mitigierung |
|--------|------------|-------------|
| Bestehende Benutzer haben keinen Zugriff | Sofortiger Zugriffsverlust | Migration: alle existierenden Arbeitgeber zuweisen |
| Admin-Overhead | Mehr Verwaltungsaufwand | Gruppen/Rollen statt individuelle Zuweisung |

## Fallback-Strategien

### Plan A: Vollständige Implementierung

Alle Maßnahmen werden wie geplant umgesetzt.

### Plan B: Rollback bei kritischen Problemen

| Maßnahme | Rollback-Strategie |
|----------|---------------------|
| SV-001 | Alten Secret Key temporär wiederherstellen |
| SV-002 | Backup von employers.json vor Migration |
| SV-003 | HTTP weiterhin parallel betreiben |
| SV-004 | CSRF-Schutz temporär deaktivieren (`app.config['WTF_CSRF_ENABLED'] = False`) |
| SV-006 | Limiter deaktivieren (`limiter.enabled = False`) |

### Plan C: Teilweise Implementierung

Falls Ressourcen begrenzt:

**Kritisch (MUSS):**
- SV-001, SV-005 (niedrigster Aufwand, höchste Wirkung)

**Hoch (SOLLTE):**
- SV-003, SV-004, SV-008

**Mittel (KANN):**
- Alle anderen

## Regressions-Checkliste

### Vor Deployment prüfen

- [ ] Alle bestehenden Routen erreichbar
- [ ] Login funktioniert
- [ ] Provider-Verbindungen funktionieren (Personio, HRworks)
- [ ] Exporte werden korrekt generiert
- [ ] Snapshots werden korrekt erstellt
- [ ] Master-Einstellungen funktionieren
- [ ] Theme-Wechsel funktioniert
- [ ] Downloads funktionieren

### Nach Deployment prüfen

- [ ] Keine erhöhte Fehlerrate in Logs
- [ ] Keine Benutzer-Beschwerden
- [ ] Performance akzeptabel
- [ ] Monitoring zeigt keine Anomalien

## Risiko-Matrix

| Maßnahme | Umsetzungsrisiko | Regressionsrisiko | Gesamtrisiko |
|----------|------------------|-------------------|--------------|
| SV-001 | Niedrig | Niedrig | **NIEDRIG** |
| SV-002 | Mittel | Mittel | **MITTEL** |
| SV-003 | Hoch | Mittel | **HOCH** |
| SV-004 | Mittel | Hoch | **HOCH** |
| SV-005 | Niedrig | Niedrig | **NIEDRIG** |
| SV-006 | Niedrig | Mittel | **MITTEL** |
| SV-007 | Mittel | Niedrig | **MITTEL** |
| SV-008 | Niedrig | Niedrig | **NIEDRIG** |
| SV-009 | Hoch | Hoch | **HOCH** |
| SV-010 | Niedrig | Niedrig | **NIEDRIG** |
| SV-011 | Niedrig | Keine | **NIEDRIG** |

## Empfohlene Test-Umgebung

Vor Produktions-Deployment:

1. **Lokale Testumgebung** mit Kopie der Produktionsdaten (anonymisiert)
2. **Staging-Server** mit identischer Konfiguration
3. **Manueller Durchlauf** aller Kernfunktionen
4. **Automatisierte Tests** (nach SV-011)

---

**Letzte Aktualisierung:** 28.01.2026
