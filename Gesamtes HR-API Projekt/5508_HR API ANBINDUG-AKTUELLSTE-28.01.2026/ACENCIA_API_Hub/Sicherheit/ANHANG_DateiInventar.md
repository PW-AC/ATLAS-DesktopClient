# ANHANG - Datei-Inventar

## Analysierte Projekt-Dateien

### Python-Dateien

| Pfad | Typ | Zweck | Relevanz | Sicherheitsbezug |
|------|-----|-------|----------|------------------|
| `acencia_hub/app.py` | Python | Hauptanwendung, alle Routen und Logik | HOCH | Auth, API, Input |
| `acencia_hub/updater.py` | Python | Auto-Update von GitHub | MITTEL | Supply Chain |
| `acencia_hub/__init__.py` | Python | Modul-Metadaten | NIEDRIG | - |
| `run.py` | Python | Produktions-Entry-Point | MITTEL | Server-Konfiguration |

### Template-Dateien

| Pfad | Typ | Zweck | Relevanz | Sicherheitsbezug |
|------|-----|-------|----------|------------------|
| `acencia_hub/templates/base.html` | HTML/Jinja2 | Basis-Template | HOCH | XSS, CSP |
| `acencia_hub/templates/login.html` | HTML/Jinja2 | Login-Formular | HOCH | Auth, CSRF |
| `acencia_hub/templates/index.html` | HTML/Jinja2 | Hauptseite | MITTEL | - |
| `acencia_hub/templates/add_employer.html` | HTML/Jinja2 | Arbeitgeber hinzufügen | HOCH | Input, Credentials |
| `acencia_hub/templates/employer_dashboard.html` | HTML/Jinja2 | Mitarbeiter-Übersicht | MITTEL | Daten-Anzeige |
| `acencia_hub/templates/employee_detail.html` | HTML/Jinja2 | Mitarbeiter-Details | MITTEL | PII |
| `acencia_hub/templates/exports.html` | HTML/Jinja2 | Export-Verwaltung | MITTEL | Download |
| `acencia_hub/templates/employer_settings.html` | HTML/Jinja2 | Arbeitgeber-Einstellungen | MITTEL | Input |
| `acencia_hub/templates/statistics.html` | HTML/Jinja2 | Statistiken | NIEDRIG | - |
| `acencia_hub/templates/snapshot_comparison.html` | HTML/Jinja2 | Snapshot-Vergleich | MITTEL | Datei-Zugriff |
| `acencia_hub/templates/settings.html` | HTML/Jinja2 | Master-Einstellungen | HOCH | Admin, Secrets |
| `acencia_hub/templates/user_settings.html` | HTML/Jinja2 | Benutzer-Einstellungen | HOCH | Passwort |
| `acencia_hub/templates/styleguide.html` | HTML/Jinja2 | Design-System | NIEDRIG | - |

### Konfigurations-Dateien

| Pfad | Typ | Zweck | Relevanz | Sicherheitsbezug |
|------|-----|-------|----------|------------------|
| `requirements.txt` | Text | Python-Dependencies | HOCH | Supply Chain |
| `start.bat` | Batch | Windows-Starter | MITTEL | Deployment |
| `.gitignore` | Text | Git-Ignore-Regeln | MITTEL | Secrets |

### Daten-Dateien (SENSIBEL)

| Pfad | Typ | Zweck | Relevanz | Sicherheitsbezug |
|------|-----|-------|----------|------------------|
| `acencia_hub/data/users.json` | JSON | Benutzerdaten | KRITISCH | Passwort-Hashes |
| `acencia_hub/data/secrets.json` | JSON | GitHub PAT | KRITISCH | Secrets |
| `employers.json` | JSON | Arbeitgeber-Config | KRITISCH | API-Credentials |

### Statische Dateien

| Pfad | Typ | Zweck | Relevanz | Sicherheitsbezug |
|------|-----|-------|----------|------------------|
| `acencia_hub/static/css/tokens.css` | CSS | Design-Tokens | NIEDRIG | - |
| `acencia_hub/static/css/style.css` | CSS | Stylesheets | NIEDRIG | - |

### Dokumentation

| Pfad | Typ | Zweck | Relevanz | Sicherheitsbezug |
|------|-----|-------|----------|------------------|
| `README.md` | Markdown | Projekt-README | NIEDRIG | - |
| `AGENTS.md` | Markdown | KI-Dokumentation | MITTEL | Architektur |
| `README_DESIGN.md` | Markdown | Design-System | NIEDRIG | - |
| `docs/ARCHITECTURE.md` | Markdown | Architektur | MITTEL | - |
| `docs/DEVELOPMENT.md` | Markdown | Entwicklung | NIEDRIG | - |
| `docs/CONFIGURATION.md` | Markdown | Konfiguration | MITTEL | Secrets-Handling |

### Runtime-Dateien

| Pfad | Typ | Zweck | Relevanz | Sicherheitsbezug |
|------|-----|-------|----------|------------------|
| `server.log` | Text | Log-Datei | MITTEL | PII, Audit |
| `acencia_hub/_snapshots/*.json` | JSON | Datensnapshots | MITTEL | PII |
| `acencia_hub/_history/*.json` | JSON | API-Backup | MITTEL | PII |
| `acencia_hub/exports/*.xlsx` | XLSX | Generierte Exporte | MITTEL | PII |

## Ignorierte Pfade

### Build-Artefakte (nicht analysiert)

| Pfad | Grund |
|------|-------|
| `venv/` | Virtuelle Umgebung (822+ Dateien) |
| `__pycache__/` | Python-Bytecode |
| `acencia_hub/__pycache__/` | Python-Bytecode |

### Generierte Daten (nicht detailliert analysiert)

| Pfad | Grund |
|------|-------|
| `acencia_hub/_history/*.json` | 69+ Dateien, automatisch generiert |
| `acencia_hub/_snapshots/*.json` | Automatisch generiert |
| `acencia_hub/exports/*.xlsx` | Automatisch generiert |

## Statistik

| Kategorie | Anzahl | Analysiert |
|-----------|--------|------------|
| Python-Dateien | 4 | ✅ |
| HTML-Templates | 13 | ✅ |
| CSS-Dateien | 2 | ✅ |
| Konfig-Dateien | 3 | ✅ |
| Daten-Dateien | 3 | ✅ |
| Dokumentation | 6 | ✅ |
| **GESAMT (Projekt)** | **31** | ✅ |
| venv/ (ignoriert) | ~1000+ | ❌ |
| _history/ (ignoriert) | 69+ | ❌ |

---

**Letzte Aktualisierung:** 28.01.2026
