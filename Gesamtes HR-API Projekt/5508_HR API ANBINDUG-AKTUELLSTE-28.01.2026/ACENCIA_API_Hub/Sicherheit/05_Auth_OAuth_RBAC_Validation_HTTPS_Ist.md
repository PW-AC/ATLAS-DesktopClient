# 05 - Auth, OAuth, RBAC, Validation, HTTPS (IST-Zustand)

## Authentifizierung

### Benutzer-Authentifizierung

| Aspekt | IST-Zustand | Evidenz |
|--------|-------------|---------|
| Methode | Benutzername + Passwort | `app.py:1580-1587` |
| Passwort-Hashing | Werkzeug scrypt (sicher) | `app.py:1587`, `app.py:1651` |
| Hash-Parameter | `scrypt:32768:8:1` | `data/users.json` |
| Session-Speicherung | Flask Session (Cookie-basiert) | `app.py:1588-1596` |
| Session-Signierung | Ja (via secret_key) | Flask default |
| Session-Verschlüsselung | Nein | Flask default |

### Session-Management

| Aspekt | IST-Zustand | Evidenz |
|--------|-------------|---------|
| Session-Timeout | Nicht konfiguriert | Keine Konfiguration gefunden |
| Logout | `session.clear()` | `app.py:1613` |
| Forced Logout | Timestamp-basiert | `app.py:1544-1567` |
| Login-Zeit Tracking | Ja (UTC Timestamp) | `app.py:1596` |

### Cookie-Konfiguration

| Attribut | Wert | Evidenz |
|----------|------|---------|
| HttpOnly | Ja (Flask default) | Flask default |
| Secure | Nein | Keine HTTPS-Konfiguration |
| SameSite | Lax (Flask default) | Flask default |
| Domain | Nicht gesetzt | Flask default |
| Path | / | Flask default |

## Provider-Authentifizierung (OAuth / API Keys)

### Personio

| Aspekt | Wert | Evidenz |
|--------|------|---------|
| Endpunkt | `https://api.personio.de/v1/auth` | `app.py:763` |
| Methode | OAuth2 Client Credentials | `app.py:763` |
| Payload | `{"client_id": ..., "client_secret": ...}` | `app.py:763` |
| Token-Speicherung | Instanzvariable `self.bearer_token` | `app.py:765` |
| Token-Erneuerung | Bei Instanziierung | `app.py:751` |

### HRworks

| Aspekt | Wert | Evidenz |
|--------|------|---------|
| Endpunkt | `{base_url}/authentication` | `app.py:493` |
| Methode | Access Key / Secret | `app.py:494` |
| Payload | `{"accessKey": ..., "secretAccessKey": ...}` | `app.py:494` |
| Token-Speicherung | Instanzvariable `self.bearer_token` | `app.py:501` |

### Token-Caching

**Evidenz:** `app.py:459-461`, `app.py:750-751`

**Beobachtungen:**
- Tokens werden pro Provider-Instanz gecacht
- Keine automatische Token-Erneuerung bei Ablauf
- Tokens leben bis Provider-Instanz zerstört wird

## RBAC (Role-Based Access Control)

### Rollen

| Rolle | Feld | Evidenz |
|-------|------|---------|
| Normal User | `is_master: false` | `users.json` |
| Master User | `is_master: true` | `users.json` |

### Berechtigungsprüfung

**Master-Only Routes:**

```python
# Beispiel aus app.py:1628-1631
user_info = session.get('user_info', {})
if not user_info.get('is_master'):
    flash("Zugriff verweigert. Nur für Master-Benutzer.", "error")
    return redirect(url_for('index'))
```

**Evidenz:**
- `/settings`: `app.py:1628-1631`
- `/api/system/restart`: `app.py:1773-1775`
- `/api/logs`: `app.py:1809-1811`

### Fehlende Berechtigungsprüfungen

| Route | Problem | Evidenz |
|-------|---------|---------|
| `/employer/<id>/*` | Keine Prüfung, ob Benutzer Zugriff auf Arbeitgeber hat | Alle Employer-Routen |
| `/download/past_export/<filename>` | Keine Prüfung der Zugehörigkeit | `app.py:2614-2633` |

## Input-Validation (Übersicht)

### Server-seitige Validierung

| Route | Validierung | Evidenz |
|-------|-------------|---------|
| `/login` | Nur Existenz-Check | `app.py:1585-1587` |
| `/settings` (add_user) | Username-Duplikat, Passwort nicht leer | `app.py:1644-1647` |
| `/employer/add` | Keine | `app.py:1918-1931` |
| `/employer/<id>/settings` | Keine | `app.py:2044-2057` |

### Client-seitige Validierung

| Feld | Validierung | Evidenz |
|------|-------------|---------|
| `username` | `required` | `login.html:14` |
| `password` | `required` | `login.html:18` |
| `kuerzel` | `required`, `maxlength="4"` | `settings.html:27` |
| `name` (Employer) | `required` | `add_employer.html:18` |

## HTTPS / TLS

### IST-Zustand

| Aspekt | Wert | Evidenz |
|--------|------|---------|
| TLS-Konfiguration | **NICHT VORHANDEN** | Keine SSL-Konfiguration |
| Server-Binding | `0.0.0.0:5001` (HTTP) | `run.py:57-58` |
| Waitress TLS | Nicht konfiguriert | `run.py:64` |

### Externe Verbindungen

| Ziel | Protokoll | Evidenz |
|------|-----------|---------|
| Personio API | HTTPS | `app.py:736` |
| HRworks API | HTTPS | `app.py:444-445` |
| GitHub (Update) | HTTPS | `updater.py:12` |
| Google Fonts | HTTPS | `base.html:9-11` |

## Security Headers

### IST-Zustand

**Keine Security Headers konfiguriert.**

| Header | Status | Empfohlen |
|--------|--------|-----------|
| Content-Security-Policy | ❌ Fehlt | Ja |
| X-Frame-Options | ❌ Fehlt | Ja |
| X-Content-Type-Options | ❌ Fehlt | Ja |
| Strict-Transport-Security | ❌ Fehlt | Ja (bei HTTPS) |
| X-XSS-Protection | ❌ Fehlt | Ja |
| Referrer-Policy | ❌ Fehlt | Ja |

**Evidenz:** Keine Header-Konfiguration in `app.py` gefunden.

## CSRF-Schutz

### IST-Zustand

| Aspekt | Wert | Evidenz |
|--------|------|---------|
| CSRF-Token | **NICHT IMPLEMENTIERT** | Keine Token in Templates |
| Flask-WTF | Nicht installiert | `requirements.txt` |

**Beobachtungen:**
- Alle POST-Formulare ohne CSRF-Schutz
- API-Endpunkte ohne CSRF-Schutz
- State-ändernde Operationen über GET möglich (z.B. `/employer/<id>/export/standard`)

---

**Letzte Aktualisierung:** 28.01.2026
