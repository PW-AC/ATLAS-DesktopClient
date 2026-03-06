# 08 - Secrets, Keys, Config (IST-Zustand)

## Hardcodierte Secrets

### Flask Secret Key

**Kritischer Befund:**

```python
app.secret_key = 'a-very-secret-key-for-the-app'
```

**Evidenz:** `app.py:1481`

**Auswirkungen:**
- Session-Cookies können gefälscht werden, wenn Key bekannt
- Key ist im Quellcode (Repository) sichtbar
- Alle Instanzen verwenden denselben Key

### GitHub Repository URL

```python
ZIP_URL = "https://github.com/paulweimert2006-commits/JULES_WEB4/archive/refs/heads/main.zip"
```

**Evidenz:** `updater.py:12`

**Beobachtung:** Repository-Struktur ist öffentlich bekannt, auch wenn privat.

## Secret-Dateien

### data/users.json

**Inhalt:**
- `username`: Klartext
- `password_hash`: scrypt Hash (sicher)
- `kuerzel`: Klartext
- `is_master`: Boolean
- `color`: String
- `theme`: String

**Evidenz:** `acencia_hub/data/users.json`

**Beobachtungen:**
- Passwort-Hashes sind sicher (scrypt)
- Datei ist JSON, menschenlesbar
- Keine Dateiverschlüsselung

### data/secrets.json

**Inhalt:**
- `github_pat`: GitHub Personal Access Token (Klartext)

**Evidenz:** `app.py:1515-1542`

**Beobachtungen:**
- PAT im Klartext gespeichert
- Keine Verschlüsselung
- PAT hat potenziell Zugriff auf privates Repository

### employers.json

**Inhalt:**
- `id`: UUID
- `name`: Arbeitgeber-Name
- `provider_key`: Provider-Typ
- `access_key`: **API-Zugangsdaten (Klartext)**
- `secret_key`: **API-Geheimnis (Klartext)**
- `is_demo`: Boolean
- `address`: Objekt mit Adressdaten

**Evidenz:** `app.py:1919-1931`

**Beobachtungen:**
- API-Credentials im Klartext
- Keine Verschlüsselung
- Jeder mit Dateizugriff kann Credentials lesen

## Umgang mit Secrets

### Laden von Secrets

```python
def load_secrets():
    if not os.path.exists(SECRETS_FILE):
        return {}
    with open(SECRETS_FILE, 'r', encoding='utf-8') as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}
```

**Evidenz:** `app.py:1515-1528`

**Beobachtungen:**
- Keine Fehlermeldung bei fehlender Datei
- Keine Validierung der Struktur
- Kein Audit-Log beim Zugriff

### Speichern von Secrets

```python
def save_secrets(secrets):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(SECRETS_FILE, 'w', encoding='utf-8') as f:
        json.dump(secrets, f, indent=4, ensure_ascii=False)
```

**Evidenz:** `app.py:1530-1542`

**Beobachtungen:**
- Datei wird komplett überschrieben
- Keine Backup-Erstellung
- Keine Audit-Protokollierung

## Bearer Tokens (Runtime)

### Personio Token

```python
self.bearer_token = r.json()['data']['token']
self.auth_header = {'Authorization': f'Bearer {self.bearer_token}'}
```

**Evidenz:** `app.py:765-766`

### HRworks Token

```python
self.bearer_token = token
self.auth_header = {"Authorization": f"Bearer {self.bearer_token}", "Accept": "application/json"}
```

**Evidenz:** `app.py:501-502`

**Beobachtungen:**
- Tokens in Speicher (Instanzvariablen)
- Keine sichere Speicherung
- Keine Token-Rotation
- Tokens leben bis Provider-Instanz zerstört wird

## Konfiguration

### App-Konfiguration

```python
app.config.update(
    EMPLOYERS_FILE=os.path.join(APP_ROOT, 'employers.json'),
    EXPORTS_DIR=os.path.join(APP_ROOT, 'exports'),
    SNAPSHOTS_DIR=os.path.join(APP_ROOT, '_snapshots'),
    HISTORY_DIR=os.path.join(APP_ROOT, '_history'),
)
```

**Evidenz:** `app.py:1882-1887`

**Beobachtungen:**
- Alle Pfade relativ zu APP_ROOT
- Keine Umgebungsvariablen
- Keine externe Konfigurationsdatei

### Pfad-Konstanten

| Konstante | Wert | Evidenz |
|-----------|------|---------|
| `PROJECT_ROOT` | `..` von `app.py` | `app.py:21` |
| `LOG_FILE_PATH` | `{PROJECT_ROOT}/server.log` | `app.py:22` |
| `DATA_DIR` | `{app.py dir}/data` | `app.py:1484` |
| `USERS_FILE` | `{DATA_DIR}/users.json` | `app.py:1485` |
| `SECRETS_FILE` | `{DATA_DIR}/secrets.json` | `app.py:1486` |

## .gitignore Analyse

### IST-Zustand

```
# In .gitignore:
acencia_hub/data/users.json
acencia_hub/data/secrets.json
acencia_hub/data/employers.json
```

**Evidenz:** `.gitignore`

**Beobachtung:** Sensitive Dateien sind korrekt in .gitignore aufgeführt.

## Zugriffsrechte (Dateisystem)

### IST-Zustand

**UNVERIFIZIERT** - Keine explizite Konfiguration von Dateiberechtigungen.

**Beobachtungen:**
- JSON-Dateien werden mit Standard-Berechtigungen erstellt
- `os.makedirs(..., exist_ok=True)` ohne mode-Parameter
- Keine Prüfung der Berechtigungen

## Zusammenfassung Secret-Typen

| Secret-Typ | Speicherort | Verschlüsselung | Risiko |
|------------|-------------|-----------------|--------|
| Flask Secret Key | Quellcode | Nein | **KRITISCH** |
| Benutzer-Passwörter | users.json | scrypt Hash | Niedrig |
| GitHub PAT | secrets.json | Nein | **HOCH** |
| HR-API Credentials | employers.json | Nein | **KRITISCH** |
| Bearer Tokens | Speicher | Nein | Mittel |

---

**Letzte Aktualisierung:** 28.01.2026
