# 01 - Plan Übersicht

## Zusammenfassung

Dieses Dokument beschreibt den Maßnahmenplan zur Behebung der 26 identifizierten Sicherheitsbefunde im ACENCIA Hub Projekt.

## Priorisierung nach Schweregrad und Aufwand

### P0 - Kritisch (Sofort umsetzen)

| ID | Befund | Aufwand | Abhängigkeiten |
|----|--------|---------|----------------|
| SV-001 | Hardcodierter Secret Key | Niedrig | Keine |
| SV-005 | Debug-Modus aktivierbar | Niedrig | Keine |
| SV-003 | Kein HTTPS | Mittel | Reverse Proxy |
| SV-004 | Kein CSRF-Schutz | Mittel | Flask-WTF |
| SV-002 | API-Credentials im Klartext | Hoch | Encryption-Modul |

### P1 - Hoch (Kurzfristig)

| ID | Befund | Aufwand | Abhängigkeiten |
|----|--------|---------|----------------|
| SV-006 | Keine Brute-Force-Protection | Mittel | Flask-Limiter |
| SV-008 | Keine Security Headers | Niedrig | Keine |
| SV-009 | Fehlende Arbeitgeber-Zugriffskontrolle | Mittel | Datenmodell-Änderung |
| SV-007 | GitHub PAT im Klartext | Mittel | SV-002 (gleicher Fix) |
| SV-010 | Keine Log-Rotation | Niedrig | Keine |
| SV-011 | Keine Tests | Hoch | pytest Setup |

### P2 - Mittel (Mittelfristig)

| ID | Befund | Aufwand |
|----|--------|---------|
| SV-012 | Keine Passwort-Policy | Niedrig |
| SV-013 | Kein Session-Timeout | Niedrig |
| SV-014 | PII in Logs | Mittel |
| SV-015 | Keine Input-Validierung | Mittel |
| SV-016 | Kein Audit-Trail | Mittel |
| SV-017 | Update ohne Signatur | Hoch |
| SV-018 | Secure Cookie fehlt | Niedrig |
| SV-019 | Keine SRI-Hashes | Niedrig |

### P3 - Niedrig (Langfristig)

| ID | Befund | Aufwand |
|----|--------|---------|
| SV-020 | Keine Account-Lockout | Mittel |
| SV-021 | Failed Logins nicht geloggt | Niedrig |
| SV-022 | Monolithische Codebasis | Hoch |
| SV-023 | Unbegrenzte Datenspeicherung | Mittel |

### P4 - Info (Optional)

| ID | Befund | Aufwand |
|----|--------|---------|
| SV-024 | Kein CI/CD | Hoch |
| SV-025 | Keine Health-Checks | Niedrig |
| SV-026 | Keine Lockfile | Niedrig |

## Ressourcen-Schätzung

| Phase | Befunde | Geschätzter Aufwand |
|-------|---------|---------------------|
| P0 | 5 | Hoch |
| P1 | 6 | Hoch |
| P2 | 8 | Mittel |
| P3 | 4 | Mittel |
| P4 | 3 | Niedrig |

## Abhängigkeitsgraph

```
SV-001 (Secret Key)
    └── Keine Abhängigkeiten

SV-005 (Debug Mode)
    └── Keine Abhängigkeiten

SV-003 (HTTPS)
    └── Externe Abhängigkeit: Reverse Proxy / Zertifikat

SV-004 (CSRF)
    └── SV-003 (HTTPS sollte zuerst implementiert werden)
    └── Flask-WTF Installation

SV-002 (API-Credentials)
    └── SV-003 (HTTPS Voraussetzung für sicheren Transport)
    └── SV-007 (kann zusammen implementiert werden)

SV-006 (Rate-Limiting)
    └── Flask-Limiter Installation

SV-008 (Security Headers)
    └── SV-003 (HSTS erfordert HTTPS)

SV-009 (Arbeitgeber-RBAC)
    └── Datenmodell-Erweiterung

SV-011 (Tests)
    └── pytest Installation
    └── Sollte nach anderen Fixes laufen
```

## Kritische Pfade

### Pfad 1: Transport-Sicherheit
```
SV-003 (HTTPS) → SV-004 (CSRF) → SV-018 (Secure Cookie)
```

### Pfad 2: Secrets-Management
```
SV-001 (Secret Key) → SV-002/SV-007 (Credential-Verschlüsselung)
```

### Pfad 3: Authentifizierung
```
SV-006 (Rate-Limit) → SV-020 (Lockout) → SV-012 (Passwort-Policy)
```

## Nicht-funktionale Anforderungen

| Anforderung | Betroffene Fixes |
|-------------|------------------|
| Abwärtskompatibilität | SV-002, SV-007 (Migration erforderlich) |
| Performance | SV-006 (Rate-Limiting Overhead) |
| Benutzerfreundlichkeit | SV-004 (CSRF-Token), SV-012 (Passwort-Policy) |
| Betrieb | SV-003 (HTTPS-Setup), SV-010 (Log-Rotation) |

---

**Letzte Aktualisierung:** 28.01.2026
