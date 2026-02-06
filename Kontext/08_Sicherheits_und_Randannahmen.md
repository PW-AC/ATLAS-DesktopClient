# 08 - Sicherheits- und Randannahmen

**Version:** 0.9.3  
**Analyse-Datum:** 2026-02-05

---

## Erkennbare Security-Mechanismen

### Authentifizierung

| Mechanismus | Implementierung | Datei |
|-------------|-----------------|-------|
| JWT-Token | Server stellt Token bei Login aus | `api/auth.php` |
| Bearer-Header | Token wird bei jeder Anfrage mitgesendet | `src/api/client.py` |
| Token-Ablauf | Implementiert (Dauer: UNVERIFIZIERT) | Server-seitig |

### Autorisierung

| Mechanismus | Implementierung |
|-------------|-----------------|
| Rollen-System | `user.role` in JWT (admin/user) |
| Endpunkt-Schutz | Alle API-Endpunkte prüfen Token |

### Datenverschlüsselung

| Daten | Verschlüsselung | Details |
|-------|-----------------|---------|
| Transport | HTTPS | Alle Verbindungen |
| VU-Credentials | AES (Server-seitig) | Master-Key in config.php |
| Passwörter | bcrypt-Hash | In MySQL |

### BiPRO-Sicherheit

| Mechanismus | Implementierung |
|-------------|-----------------|
| STS-Token | 10 Minuten Gültigkeit |
| X.509-Zertifikate | Unterstützt (PFX, JKS, PEM) |
| Proxy-Deaktivierung | Alle Proxy-Umgebungsvariablen werden gelöscht |

---

## Sensible Daten

### Im Projekt

| Datei | Inhalt | Schutz |
|-------|--------|--------|
| `api/config.php` | DB-Credentials, Master-Key, JWT-Secret | .htaccess (Deny) |
| `BIPRO_STATUS.md` | BiPRO-Credentials (VEMA) | Nur lokal |

### In der Anwendung

| Daten | Speicherort | Schutz |
|-------|-------------|--------|
| GDV-Daten | Lokale Dateien + Server | Benutzer-Verantwortung |
| PDF-Dokumente | Server (`/dokumente/`) | JWT-Authentifizierung |
| VU-Credentials | MySQL (verschlüsselt) | AES + Master-Key |

---

## Implizite Annahmen

### Benutzer-Annahmen

| Annahme | Implikation |
|---------|-------------|
| Benutzer ist authentifiziert | Alle UI-Bereiche verfügbar |
| Benutzer hat Internetzugang | Server-API und BiPRO erreichbar |
| Benutzer arbeitet lokal | Keine Offline-Funktionalität |
| Single-User-Betrieb | Keine gleichzeitige Bearbeitung |

### Technische Annahmen

| Annahme | Implikation |
|---------|-------------|
| Server ist erreichbar | Kein Offline-Mode |
| BiPRO-Token sind gültig | Automatische Erneuerung (UNVERIFIZIERT) |
| OpenRouter ist verfügbar | KI-Klassifikation funktioniert |
| GDV-Dateien sind CP1252 | Fallback auf Latin-1, UTF-8 |
| PDFs haben Text | OCR als Fallback |

### Server-Annahmen

| Annahme | Implikation |
|---------|-------------|
| MySQL ist erreichbar | Alle Operationen funktionieren |
| Dateisystem ist beschreibbar | Dokumenten-Upload funktioniert |
| PHP 7.4+ läuft | API funktioniert |

---

## Erkennbare Risiken

### Deskriptiv (keine Bewertung)

| Bereich | Beobachtung |
|---------|-------------|
| **Secrets im Code** | `BIPRO_STATUS.md` enthält VEMA-Credentials |
| **Live-Sync** | Lokale Änderungen werden sofort auf Server übertragen |
| **Kein Rate-Limiting** | API hat keine erkennbare Drosselung |
| **Keine CSRF-Protection** | Für Desktop-App nicht relevant |
| **Logging** | Keine Audit-Logs erkennbar |
| **Backup** | Keine automatischen Backups erkennbar |

### Token-Handling

| Beobachtung | Datei |
|-------------|-------|
| Token wird im Speicher gehalten | `src/api/client.py` |
| Kein Token-Refresh implementiert | Client-seitig |
| Token-Ablauf wird nicht geprüft | UNVERIFIZIERT |

### Fehlerbehandlung

| Beobachtung | Datei |
|-------------|-------|
| API-Fehler werden geloggt | `src/api/client.py` |
| Benutzer sieht Fehlermeldungen | UI via QMessageBox |
| Keine strukturierte Fehler-Sammlung | Logs nur in stdout |

---

## Netzwerk-Kommunikation

### Ausgehende Verbindungen

| Ziel | Protokoll | Port | Zweck |
|------|-----------|------|-------|
| `acencia.info` | HTTPS | 443 | PHP REST API |
| `transfer.degenia.de` | HTTPS | 443 | BiPRO (Degenia) |
| `openrouter.ai` | HTTPS | 443 | KI-Klassifikation |

### Keine eingehenden Verbindungen

Die Desktop-App öffnet keine Server-Sockets.

---

## Datenschutz (DSGVO-relevant)

### Verarbeitete personenbezogene Daten

| Datentyp | Quelle | Speicherort |
|----------|--------|-------------|
| Namen, Adressen | GDV-Dateien (0100) | Lokal + ggf. Server |
| Geburtsdaten | GDV-Dateien (0100) | Lokal + ggf. Server |
| Bankdaten (IBAN, BIC) | GDV-Dateien (0100 TD4) | Lokal + ggf. Server |
| Vertragsdaten | GDV-Dateien (0200) | Lokal + ggf. Server |
| Versicherungsdokumente | BiPRO-Downloads | Server (`/dokumente/`) |

### Datenflüsse

```
[Versicherer] ──BiPRO──▶ [Desktop-App] ──API──▶ [Server]
                              │
                              ▼
                        [Lokale Dateien]
```

---

## Nicht implementiert (erkennbar)

| Feature | Status |
|---------|--------|
| Multi-Faktor-Authentifizierung | ❌ |
| Passwort-Ablauf | ❌ |
| Audit-Logging | ❌ |
| Datenverschlüsselung at-rest (lokal) | ❌ |
| Automatisches Token-Refresh | ❌ |
| Session-Timeout (Client) | ❌ |
| IP-Whitelist | ❌ |

---

## Härtungs-Maßnahmen (erkennbar)

| Maßnahme | Implementierung |
|----------|-----------------|
| HTTPS für alle Verbindungen | ✅ |
| Passwort-Hashing (bcrypt) | ✅ |
| Credential-Verschlüsselung (AES) | ✅ |
| .htaccess Schutz für sensible Dateien | ✅ |
| Proxy-Deaktivierung für BiPRO | ✅ |
| SSL-Verifizierung | ✅ (session.verify = True) |
