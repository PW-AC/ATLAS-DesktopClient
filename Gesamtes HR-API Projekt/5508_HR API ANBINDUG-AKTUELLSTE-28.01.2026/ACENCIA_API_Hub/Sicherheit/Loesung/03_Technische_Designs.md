# 03 - Technische Designs

## Wiederverwendbare Fix-Bausteine

### Baustein 1: Credential-Verschlüsselung

**Verwendung für:** SV-002, SV-007

**Design:**
```
Umgebungsvariable ACENCIA_MASTER_KEY
         │
         ▼
cryptography.Fernet(key)
         │
    ┌────┴────┐
    ▼         ▼
encrypt()  decrypt()
    │         │
    ▼         ▼
employers.json  Provider-Instanzen
secrets.json
```

**Dateien:**
- `app.py` - Neue Funktionen `encrypt_credential()`, `decrypt_credential()`
- Anpassungen in `EmployerStore`, `load_secrets()`, `save_secrets()`

**Abhängigkeiten:**
- `cryptography` Paket in requirements.txt

**Migrationslogik:**
- Beim Start prüfen, ob Credentials verschlüsselt sind
- Falls nicht: automatisch verschlüsseln und speichern

---

### Baustein 2: Security Headers Middleware

**Verwendung für:** SV-008

**Design:**
```python
@app.after_request
def add_security_headers(response):
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    if request.is_secure:
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    # CSP - permissiv für Google Fonts
    response.headers['Content-Security-Policy'] = "default-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; script-src 'self' 'unsafe-inline'"
    return response
```

**Dateien:**
- `app.py` - Neue Funktion nach Flask-App-Initialisierung

---

### Baustein 3: Rate-Limiter

**Verwendung für:** SV-006

**Design:**
```python
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def login():
    # ...
```

**Dateien:**
- `requirements.txt` - Flask-Limiter hinzufügen
- `app.py` - Limiter initialisieren und auf kritische Routen anwenden

---

### Baustein 4: CSRF-Schutz

**Verwendung für:** SV-004

**Design:**
```python
from flask_wtf.csrf import CSRFProtect

csrf = CSRFProtect(app)
```

**Template-Änderungen:**
```html
<form method="post">
    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}"/>
    <!-- Formular-Felder -->
</form>
```

**API-Calls (JavaScript):**
```javascript
fetch(url, {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content
    },
    body: JSON.stringify(data)
});
```

**Dateien:**
- `requirements.txt` - Flask-WTF hinzufügen
- `app.py` - CSRFProtect initialisieren
- `base.html` - Meta-Tag für CSRF-Token
- Alle Templates mit POST-Formularen

---

### Baustein 5: Arbeitgeber-Zugriffskontrolle

**Verwendung für:** SV-009

**Design:**
```python
def requires_employer_access(f):
    @wraps(f)
    def decorated_function(employer_id, *args, **kwargs):
        user_info = session.get('user_info', {})
        
        # Master hat immer Zugriff
        if user_info.get('is_master'):
            return f(employer_id, *args, **kwargs)
        
        # Prüfe allowed_employers
        allowed = user_info.get('allowed_employers', [])
        if employer_id not in allowed:
            flash("Zugriff verweigert.", "error")
            return redirect(url_for('index'))
        
        return f(employer_id, *args, **kwargs)
    return decorated_function
```

**Datenmodell-Erweiterung (users.json):**
```json
{
    "username": "user",
    "allowed_employers": ["uuid-1", "uuid-2"]
}
```

**Dateien:**
- `app.py` - Decorator-Funktion
- Anwendung auf alle `/employer/<id>/*` Routen
- UI für Arbeitgeber-Zuweisung in Master-Einstellungen

---

### Baustein 6: Passwort-Validierung

**Verwendung für:** SV-012

**Design:**
```python
def validate_password(password: str) -> tuple[bool, str]:
    """
    Validiert ein Passwort gegen die Policy.
    
    Returns:
        tuple[bool, str]: (Gültig, Fehlermeldung wenn ungültig)
    """
    if len(password) < 8:
        return False, "Passwort muss mindestens 8 Zeichen lang sein."
    if not any(c.isupper() for c in password):
        return False, "Passwort muss mindestens einen Großbuchstaben enthalten."
    if not any(c.islower() for c in password):
        return False, "Passwort muss mindestens einen Kleinbuchstaben enthalten."
    if not any(c.isdigit() for c in password):
        return False, "Passwort muss mindestens eine Ziffer enthalten."
    return True, ""
```

**Dateien:**
- `app.py` - Funktion und Anwendung in `settings()`, `user_settings()`

---

### Baustein 7: Log-Rotation

**Verwendung für:** SV-010

**Design:**
```python
from logging.handlers import RotatingFileHandler

file_handler = RotatingFileHandler(
    LOG_FILE_PATH,
    mode='a',
    maxBytes=10*1024*1024,  # 10 MB
    backupCount=5,
    encoding='utf-8'
)
```

**Dateien:**
- `app.py:33` - FileHandler durch RotatingFileHandler ersetzen

---

### Baustein 8: Session-Timeout

**Verwendung für:** SV-013

**Design:**
```python
from datetime import timedelta

app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=8)
app.config['SESSION_REFRESH_EACH_REQUEST'] = True
```

**Dateien:**
- `app.py` - App-Konfiguration erweitern

---

### Baustein 9: Audit-Logger

**Verwendung für:** SV-016

**Design:**
```python
audit_logger = logging.getLogger('audit')
audit_handler = RotatingFileHandler('audit.log', maxBytes=10*1024*1024, backupCount=10)
audit_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
audit_logger.addHandler(audit_handler)

def audit_log(user: str, action: str, target: str, details: str = ""):
    """Protokolliert administrative Aktionen."""
    audit_logger.info(f"USER={user} ACTION={action} TARGET={target} DETAILS={details}")
```

**Anwendung:**
```python
# Bei Benutzer-Erstellung
audit_log(current_user, "CREATE_USER", new_username, f"is_master={is_master}")

# Bei Benutzer-Löschung
audit_log(current_user, "DELETE_USER", deleted_username)
```

**Dateien:**
- `app.py` - Audit-Logger und Funktion
- Aufrufe in allen Admin-Aktionen

---

### Baustein 10: Health-Check Endpoints

**Verwendung für:** SV-025

**Design:**
```python
@app.route('/health')
def health():
    """Basis Health-Check."""
    return jsonify({"status": "healthy"}), 200

@app.route('/ready')
def ready():
    """Readiness-Check mit Dependency-Prüfung."""
    checks = {
        "employers_file": os.path.exists(app.config['EMPLOYERS_FILE']),
        "users_file": os.path.exists(USERS_FILE),
        "exports_dir": os.path.isdir(app.config['EXPORTS_DIR'])
    }
    all_ok = all(checks.values())
    return jsonify({"status": "ready" if all_ok else "not_ready", "checks": checks}), 200 if all_ok else 503
```

**Dateien:**
- `app.py` - Neue Routen (ohne Auth-Prüfung)

---

**Letzte Aktualisierung:** 28.01.2026
