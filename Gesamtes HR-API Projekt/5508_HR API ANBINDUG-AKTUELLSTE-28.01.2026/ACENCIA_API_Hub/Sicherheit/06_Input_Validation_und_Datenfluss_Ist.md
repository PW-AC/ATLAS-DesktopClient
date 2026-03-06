# 06 - Input Validation und Datenfluss (IST-Zustand)

## Eingabequellen

| Quelle | Verwendung | Evidenz |
|--------|------------|---------|
| `request.form` | Alle POST-Formulare | Diverse Routen |
| `request.args` | Query-Parameter | `app.py:1958`, `app.py:2517` |
| `request.get_json()` | Theme-Update | `app.py:1746` |
| URL-Parameter | Route-Parameter | `<employer_id>`, `<employee_id>`, `<path:filename>` |

## Validierung nach Route

### `/login` (POST)

**Eingaben:**
- `username`: String
- `password`: String

**Validierung:**

```python
username = request.form.get('username')
password = request.form.get('password')
user = next((u for u in users if u['username'] == username), None)
if user and check_password_hash(user['password_hash'], password):
```

**Evidenz:** `app.py:1581-1587`

**Beobachtungen:**
- Keine Längenprüfung
- Keine Zeichenfilterung
- Keine Rate-Limiting

### `/settings` (POST) - Add User

**Eingaben:**
- `username`: String
- `password`: String
- `kuerzel`: String (max 4 Zeichen - nur Client-seitig)
- `color`: String (Select)
- `is_master`: String ("true" oder nicht vorhanden)

**Validierung:**

```python
if any(u['username'] == username for u in users):
    flash(f"Benutzername '{username}' existiert bereits.", "error")
elif not password:
    flash("Das Passwort darf nicht leer sein.", "error")
```

**Evidenz:** `app.py:1644-1647`

**Beobachtungen:**
- Keine Username-Sanitization
- Keine Passwort-Mindestlänge
- `kuerzel` wird nicht validiert (außer Client-seitig)
- `color` wird nicht gegen Whitelist geprüft

### `/employer/add` (POST)

**Eingaben:**
- `name`: String
- `provider_key`: String
- `access_key`: String
- `secret_key`: String
- `street`, `zip_code`, `city`: Strings
- `is_demo`: String ("true" oder nicht vorhanden)

**Validierung:** **KEINE**

```python
employer_data = {
    "id": str(uuid.uuid4()),
    "name": request.form.get('name'),
    "provider_key": request.form.get('provider_key'),
    "access_key": request.form.get('access_key'),
    "secret_key": request.form.get('secret_key'),
    # ...
}
employer_store.add(employer_data)
```

**Evidenz:** `app.py:1918-1932`

**Beobachtungen:**
- `provider_key` nicht gegen Whitelist validiert
- `name` nicht sanitiert (wird in Dateinamen verwendet)
- Keine Prüfung, ob Credentials gültig sind

### `/employer/<employer_id>/snapshots/compare` (POST)

**Eingaben:**
- `snapshot1`: Dateiname
- `snapshot2`: Dateiname
- `direction`: "forward" oder "backward"

**Validierung:**

```python
file_a = form.get('snapshot1')
file_b = form.get('snapshot2')
# ...
path1 = os.path.join(snapshots_dir, file1)
path2 = os.path.join(snapshots_dir, file2)
with open(path1, 'r', encoding='utf-8') as f:
    data1 = json.load(f)
```

**Evidenz:** `app.py:2221-2263`

**Beobachtungen:**
- Dateinamen werden vom Client gesendet
- `os.path.join` verhindert absolute Pfade nicht vollständig
- Keine Prüfung, ob Dateien zum aktuellen Arbeitgeber gehören

### `/download/past_export/<path:filename>` (GET)

**Eingaben:**
- `filename`: Pfad-String (kann Slashes enthalten)

**Validierung:**

```python
return send_from_directory(
    app.config['EXPORTS_DIR'],
    filename,
    as_attachment=True
)
```

**Evidenz:** `app.py:2629-2633`

**Beobachtungen:**
- `send_from_directory` hat eingebauten Path-Traversal-Schutz
- Keine Prüfung der Benutzerberechtigung
- Jeder authentifizierte Benutzer kann alle Exporte herunterladen

### `/api/user/theme` (POST)

**Eingaben:**
- JSON: `{"theme": "light" | "dark"}`

**Validierung:**

```python
new_theme = data.get('theme')
if new_theme not in ['light', 'dark']:
    return jsonify({"status": "error", "message": "Ungültiges Theme"}), 400
```

**Evidenz:** `app.py:1747-1749`

**Beobachtung:** Gute Whitelist-Validierung.

## Sanitization

### Dateinamen-Sanitization

```python
def _get_safe_employer_name(name):
    return "".join(c for c in name if c.isalnum() or c in (' ', '_')).rstrip().replace(' ', '_')
```

**Evidenz:** `app.py:159-169`

**Beobachtungen:**
- Entfernt Sonderzeichen
- Erlaubt Leerzeichen (werden zu Unterstrichen)
- Verwendet für Snapshot/Export-Dateinamen

### HTML-Escaping

- Jinja2 escaped automatisch Variablen in Templates
- `{{ variable }}` ist sicher
- `{{ variable|safe }}` würde Escaping deaktivieren (nicht gefunden)

**Evidenz:** Jinja2 default autoescaping

## Datenfluss-Diagramme

### Arbeitgeber-Credentials

```
Benutzer-Input (Form)
        │
        ▼
request.form.get()
        │
        ▼ (KEINE VALIDIERUNG)
employer_data dict
        │
        ▼
EmployerStore.add()
        │
        ▼
employers.json (KLARTEXT)
        │
        ▼
ProviderFactory.get_provider()
        │
        ▼
External API Request
```

### Snapshot-Vergleich

```
Benutzer-Input (Form)
        │
        ▼
snapshot1, snapshot2 Dateinamen
        │
        ▼ (KEINE VALIDIERUNG)
os.path.join(snapshots_dir, filename)
        │
        ▼
open(path, 'r')
        │
        ▼
json.load()
        │
        ▼
Template Rendering
```

## Potenzielle Injection-Punkte

| Typ | Ort | Risiko | Evidenz |
|-----|-----|--------|---------|
| SQL Injection | - | Nicht anwendbar (kein SQL) | Keine DB |
| NoSQL Injection | - | Nicht anwendbar | JSON-Dateien |
| Command Injection | - | Nicht gefunden | Kein subprocess |
| Path Traversal | Snapshot-Vergleich | Mittel (os.path.join Schutz) | `app.py:2256-2257` |
| XSS (Stored) | Arbeitgeber-Name | Niedrig (Jinja2 escaping) | Templates |
| XSS (Reflected) | Flash Messages | Niedrig (Jinja2 escaping) | `base.html:46` |

## Datei-Upload

**IST-Zustand:** Keine Datei-Upload-Funktionalität vorhanden.

---

**Letzte Aktualisierung:** 28.01.2026
