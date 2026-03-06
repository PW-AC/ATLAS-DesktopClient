# 08 - Sicherheit und Randannahmen

## Implementierte Security-Mechanismen

Die Anwendung hat ein umfangreiches Security-Audit durchlaufen. Von 26 identifizierten Befunden wurden 20 umgesetzt.

### Authentifizierung

| Mechanismus | Implementation | Evidenz |
|-------------|----------------|---------|
| Passwort-Hashing | Werkzeug scrypt | `app.py:14` |
| Passwort-Policy | Min. 8 Zeichen, Groß/Klein/Zahl | `app.py:1988-2030` |
| Session-Timeout | 8 Stunden | `app.py:1762-1763` |
| Account-Lockout | 5 Versuche, 15min Sperre | `app.py:2000-2050` |
| Failed-Login-Logging | Audit-Log | `app.py:2080-2100` |

### Autorisierung

| Mechanismus | Implementation | Evidenz |
|-------------|----------------|---------|
| Master/Normal-User | `is_master` Flag | `app.py:1853-1854` |
| Arbeitgeber-Zugriffskontrolle | `allowed_employers` + Before-Request | `app.py:1836-1908` |
| Audit-Logging | Separate audit.log | `app.py:151-188` |

### Transport-Sicherheit

| Mechanismus | Status | Evidenz |
|-------------|--------|---------|
| HTTPS | NICHT IMPLEMENTIERT (Reverse Proxy erforderlich) | - |
| Session Cookie Secure | Nur wenn `HTTPS_ENABLED=true` | `app.py:1774` |
| Session Cookie HttpOnly | Aktiviert | `app.py:1771` |
| Session Cookie SameSite | Lax | `app.py:1772` |

### Web-Sicherheit

| Mechanismus | Implementation | Evidenz |
|-------------|----------------|---------|
| CSRF-Schutz | Flask-WTF CSRFProtect | `app.py:1728-1741` |
| Rate-Limiting | Flask-Limiter (5/min Login) | `app.py:1781-1796` |
| Security Headers | After-Request-Handler | `app.py:1808-1827` |

### Security Headers (implementiert)

```
X-Frame-Options: DENY
X-Content-Type-Options: nosniff
X-XSS-Protection: 1; mode=block
Referrer-Policy: strict-origin-when-cross-origin
Content-Security-Policy: default-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; ...
Strict-Transport-Security: max-age=31536000; includeSubDomains (nur bei HTTPS)
```

### Datenschutz

| Mechanismus | Implementation | Evidenz |
|-------------|----------------|---------|
| Credential-Verschlüsselung | Fernet (cryptography) | `app.py:23-127` |
| SMTP-Passwort-Verschlüsselung | Fernet (in triggers.json) | `app.py:700-750` |
| PII-Anonymisierung in Logs | Namen werden gekürzt | `app.py:199-260` |
| Log-Rotation | 10MB, 5 Backups | `app.py:130-150` |

---

## Offene Security-Befunde (BLOCKED)

| Befund | Status | Grund |
|--------|--------|-------|
| SV-003: HTTPS | BLOCKED | Reverse Proxy erforderlich |
| SV-017: Update-Signatur | BLOCKED | GPG-Integration ausstehend |
| SV-019: SRI für Fonts | BLOCKED | Google Fonts unterstützt kein SRI |
| SV-022: Code-Refactoring | BLOCKED | Architekturentscheidung |
| SV-023: Data Retention | BLOCKED | Policy ausstehend |
| SV-024: CI/CD | BLOCKED | Infrastruktur ausstehend |

**Evidenz:** `Sicherheit/Umsetzung/00_INDEX.md:14-24`

---

## Implizite Annahmen

Die folgenden Annahmen sind im Code nicht explizit dokumentiert, aber aus der Implementation ableitbar:

### Netzwerk-Annahmen

| Annahme | Basis |
|---------|-------|
| Betrieb im geschlossenen LAN | Kein HTTPS, lokale IP-Bindung |
| Keine öffentliche Internet-Exposition | Fehlende WAF/DDoS-Schutz |
| Vertrauenswürdige Netzwerk-Teilnehmer | Keine IP-Whitelist |

### Benutzer-Annahmen

| Annahme | Basis |
|---------|-------|
| Benutzer sind authentifiziert | Session-basierter Zugriff |
| Master-User ist vertrauenswürdig | Voller Systemzugriff |
| Begrenzte Benutzeranzahl | JSON-Datei als Datenbank |

### Daten-Annahmen

| Annahme | Basis |
|---------|-------|
| HR-Daten sind sensibel | Verschlüsselung, Zugriffskontrolle |
| Snapshot-Integrität | Hash-basierte Änderungserkennung |
| Arbeitgeber-Isolation | Zugriffskontrolle pro Arbeitgeber |

### Infrastruktur-Annahmen

| Annahme | Basis |
|---------|-------|
| Windows-Server | `start.bat`, PowerShell-Pfade |
| Persistente Dateisystem-Speicherung | JSON-Dateien |
| Kein Load-Balancing | Single-Instance-Design |

---

## Vertrauensgrenzen

```
┌─────────────────────────────────────────────────────────────────┐
│                    VERTRAUENSBEREICH                            │
│                                                                 │
│  ┌─────────────┐     ┌─────────────────────────────────────┐  │
│  │   Browser   │     │         ACENCIA Hub Server          │  │
│  │  (LAN User) │◄───►│  ┌───────────────────────────────┐  │  │
│  └─────────────┘     │  │  Flask App + Waitress         │  │  │
│                      │  │  ├── Session Management       │  │  │
│                      │  │  ├── Arbeitgeber-Zugriff      │  │  │
│                      │  │  └── Credential-Verschlüsselung│ │  │
│                      │  └───────────────────────────────┘  │  │
│                      │  ┌───────────────────────────────┐  │  │
│                      │  │  Dateisystem                  │  │  │
│                      │  │  ├── users.json (Hashes)      │  │  │
│                      │  │  ├── employers.json (ENC)     │  │  │
│                      │  │  └── _snapshots/ (Klartext)   │  │  │
│                      │  └───────────────────────────────┘  │  │
│                      └─────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                               │
                               │ HTTPS (zu Provider APIs)
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                 EXTERNE SYSTEME (Nicht vertrauenswürdig)        │
│                                                                 │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │   Personio API  │  │   HRworks API   │  │   GitHub API    │ │
│  │   (HTTPS)       │  │   (HTTPS)       │  │   (HTTPS)       │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

---

## Sensible Daten-Klassifizierung

### Hochsensibel (verschlüsselt)

| Daten | Speicherort | Schutz |
|-------|-------------|--------|
| API-Credentials | `employers.json` | Fernet-Verschlüsselung |
| GitHub PAT | `secrets.json` | Fernet-Verschlüsselung |
| SMTP-Passwort | `triggers.json` | Fernet-Verschlüsselung |
| API-Tokens (Trigger) | `triggers.json` | Fernet-Verschlüsselung |
| Passwörter | `users.json` | scrypt-Hash (nicht umkehrbar) |

### Sensibel (Klartext, geschützt durch Zugriffskontrolle)

| Daten | Speicherort | Schutz |
|-------|-------------|--------|
| Mitarbeiterdaten | `_snapshots/` | Arbeitgeber-Zugriffskontrolle |
| API-Rohdaten | `_history/` | Dateisystem-Berechtigungen |
| Exporte | `exports/` | Dateisystem-Berechtigungen |

### Log-Daten (anonymisiert)

| Daten | Speicherort | Schutz |
|-------|-------------|--------|
| Anwendungs-Logs | `server.log` | PII-Anonymisierung |
| Audit-Trail | `audit.log` | Nur Admin-Aktionen |

---

## Bekannte Risiken

### Top 5 verbleibende Risiken

| # | Risiko | Schweregrad | Mitigation |
|---|--------|-------------|------------|
| 1 | Kein HTTPS | KRITISCH | Reverse Proxy einrichten |
| 2 | Google Fonts ohne SRI | MITTEL | Fonts lokal hosten |
| 3 | Auto-Update ohne Signatur | MITTEL | GPG-Signatur implementieren |
| 4 | Monolithische Codebasis | NIEDRIG | Schrittweise modularisieren |
| 5 | Keine Data Retention Policy | NIEDRIG | Automatische Bereinigung |

**Evidenz:** `Sicherheit/Umsetzung/00_INDEX.md:105-112`

---

## Compliance-Hinweise

### DSGVO-Relevanz

| Aspekt | Status | Hinweis |
|--------|--------|---------|
| Personenbezogene Daten | JA | Mitarbeiterdaten |
| Speicherbegrenzung | UNVERIFIZIERT | Keine automatische Löschung |
| Auskunftsrecht | UNVERIFIZIERT | Keine Selbstauskunft-Funktion |
| Löschrecht | MANUELL | Über Export-Löschung möglich |
| Audit-Trail | JA | audit.log |
| Verschlüsselung | TEILWEISE | Credentials ja, Snapshots nein |

**Hinweis:** Diese Auflistung ist keine Rechtsberatung. Eine vollständige DSGVO-Prüfung wurde nicht durchgeführt.

---

## Sicherheits-Empfehlungen (nicht implementiert)

Folgende Empfehlungen wurden im Audit identifiziert, aber nicht umgesetzt:

1. **HTTPS aktivieren** - Reverse Proxy (nginx/Apache) mit TLS-Zertifikat
2. **Fonts lokal hosten** - Statt Google Fonts CDN
3. **Update-Signatur** - GPG-signierte Releases
4. **Regelmäßige Security-Updates** - Dependencies aktuell halten
5. **Penetration Testing** - Externe Sicherheitsprüfung

---

**Letzte Aktualisierung:** 29.01.2026
