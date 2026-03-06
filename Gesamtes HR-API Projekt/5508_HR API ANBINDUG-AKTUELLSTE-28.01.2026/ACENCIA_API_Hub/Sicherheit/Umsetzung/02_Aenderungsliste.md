# Änderungsliste - Security-Umsetzung

## Geänderte Dateien

| Datei | Änderungstyp | Befund-ID | Beschreibung |
|-------|--------------|-----------|--------------|
| `acencia_hub/app.py` | Geändert | SV-001 | Secret Key aus Umgebungsvariable |
| `acencia_hub/app.py` | Geändert | SV-002 | encrypt_credential/decrypt_credential |
| `acencia_hub/app.py` | Geändert | SV-004 | CSRFProtect Initialisierung |
| `acencia_hub/app.py` | Geändert | SV-005 | Debug-Modus aus Umgebungsvariable |
| `acencia_hub/app.py` | Geändert | SV-006 | Flask-Limiter auf Login |
| `acencia_hub/app.py` | Geändert | SV-007 | save_secrets/load_secrets mit Verschlüsselung |
| `acencia_hub/app.py` | Geändert | SV-008 | add_security_headers Middleware |
| `acencia_hub/app.py` | Geändert | SV-009 | check_employer_route_access |
| `acencia_hub/app.py` | Geändert | SV-010 | RotatingFileHandler |
| `acencia_hub/app.py` | Geändert | SV-012 | validate_password |
| `acencia_hub/app.py` | Geändert | SV-013 | PERMANENT_SESSION_LIFETIME |
| `acencia_hub/app.py` | Geändert | SV-014 | anonymize_log_message |
| `acencia_hub/app.py` | Geändert | SV-015 | validate_employer_input |
| `acencia_hub/app.py` | Geändert | SV-016 | audit_log Funktion |
| `acencia_hub/app.py` | Geändert | SV-018 | SESSION_COOKIE_* Flags |
| `acencia_hub/app.py` | Geändert | SV-020 | Account-Lockout Logik |
| `acencia_hub/app.py` | Geändert | SV-021 | Failed Login Logging |
| `acencia_hub/app.py` | Geändert | SV-025 | /health und /ready Endpoints |
| `requirements.txt` | Geändert | Multiple | Security Dependencies hinzugefügt |
| `acencia_hub/templates/base.html` | Geändert | SV-004, SV-019 | CSRF Meta-Tag, SRI-Hinweis |
| `acencia_hub/templates/login.html` | Geändert | SV-004 | CSRF-Token |
| `acencia_hub/templates/settings.html` | Geändert | SV-004 | CSRF-Tokens in Formularen |
| `acencia_hub/templates/user_settings.html` | Geändert | SV-004 | CSRF-Token |
| `acencia_hub/templates/add_employer.html` | Geändert | SV-004 | CSRF-Token |
| `acencia_hub/templates/employer_settings.html` | Geändert | SV-004 | CSRF-Token |
| `acencia_hub/templates/index.html` | Geändert | SV-004 | CSRF-Token |
| `acencia_hub/templates/snapshot_comparison.html` | Geändert | SV-004 | CSRF-Tokens |

## Neue Dateien

| Datei | Befund-ID | Beschreibung |
|-------|-----------|--------------|
| `tests/__init__.py` | SV-011 | Test-Paket Initialisierung |
| `tests/conftest.py` | SV-011 | pytest Fixtures |
| `tests/test_security.py` | SV-011 | Security-Tests |
| `tests/test_auth.py` | SV-011 | Auth-Tests |
| `Sicherheit/Umsetzung/` | - | Umsetzungsdokumentation |

---

**Letzte Aktualisierung:** 28.01.2026
