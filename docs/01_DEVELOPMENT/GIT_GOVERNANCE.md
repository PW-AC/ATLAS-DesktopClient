# Git Governance

> Stand: 25.02.2026 | Version: 3.4.0

## Repository

| Feld | Wert |
|------|------|
| **Name** | acencia-atlas-desktop (ATLAS-DesktopClient) |
| **Hosting** | GitHub (public) |
| **Remote** | `https://github.com/paulweimert2006-commits/ATLAS-DesktopClient.git` |

## Branch-Strategie

| Branch | Channel | Zweck | Protection |
|--------|---------|-------|------------|
| `main` | stable | Produktiv, nur PRs aus `beta` | Require PR, Status Checks, No direct push |
| `beta` | beta | Fast stabil, Feature-komplett | Require PR, Status Checks empfohlen |
| `dev` | dev | Experimentell, Refactoring | Keine Protection |

### Feature-Workflow

```
feature/* --> dev --> PR --> beta --> PR --> main
fix/*     --> dev --> PR --> beta --> PR --> main
refactor/* --> dev --> PR --> beta --> PR --> main
chore/*   --> dev --> PR --> beta --> PR --> main
```

### Branch-Naming-Konventionen

- `feature/beschreibung` -- Neues Feature
- `fix/beschreibung` -- Bugfix
- `refactor/beschreibung` -- Refactoring
- `chore/beschreibung` -- Build, CI, Tooling

## PR-Regeln

Ein PR darf **nicht** gemerged werden wenn:

1. VERSION-Datei nicht erhoeht (SemVer)
2. Smoke Tests fehlschlagen
3. PR-Beschreibung fehlt (Template nutzen!)
4. Betroffene Dokumentation nicht aktualisiert
5. UI-Texte nicht in `src/i18n/de.py`
6. `QMessageBox.information/warning/critical` verwendet (ToastManager nutzen!)

## Branch Protection Rules (GitHub)

### main (manuell konfigurieren)

1. Repository Settings > Branches > Add rule
2. Branch name pattern: `main`
3. Aktivieren:
   - [x] Require a pull request before merging
   - [x] Require status checks to pass before merging
   - [x] Require linear history
   - [x] Do not allow bypassing the above settings

### beta

1. Branch name pattern: `beta`
2. Aktivieren:
   - [x] Require a pull request before merging
   - [x] Require status checks to pass (empfohlen)

## Secret Policy

| Datei | Im Repo? | Geschuetzt durch |
|-------|----------|-----------------|
| `config.php` | NEIN | `.gitignore` |
| `config.example.php` | JA | Nur Platzhalter |
| `*.pem`, `*.key` | NEIN | `.gitignore` |
| `.env`, `.env.*` | NEIN | `.gitignore` |

## CODEOWNERS

Definiert in `.github/CODEOWNERS`. Repository-Owner wird automatisch als Reviewer bei PRs hinzugefuegt.

## CI/CD

GitHub Actions Workflow: `.github/workflows/smoke-tests.yml`
- Trigger: PRs und Pushes auf `main` und `beta`
- Steps: Python Setup, Dependencies, Smoke Tests, VERSION-Check

### Weitere Workflows

| Workflow | Trigger | Zweck |
|----------|---------|-------|
| CodeQL Analysis | PR + Push auf main/beta | SAST-Scanning (Python, Actions) |
| Dependabot | Automatisch | Vulnerability-Alerts fuer Dependencies |

## Security Features (GitHub)

| Feature | Status | Aktiviert seit |
|---------|--------|----------------|
| Secret Scanning | Aktiv | 25.02.2026 |
| Push Protection | Aktiv | 25.02.2026 |
| Dependabot Alerts | Aktiv | 25.02.2026 |
| CodeQL Analysis | Aktiv | 25.02.2026 |

## Dependabot-Alerts (Stand 25.02.2026)

21 offene Alerts, davon:

| Severity | Anzahl | Pakete |
|----------|--------|--------|
| Critical | 1 | waitress |
| High | 7 | cryptography (3x), urllib3 (3x), waitress |
| Medium | 11 | werkzeug (4x), jinja2 (3x), requests, cryptography (2x), Jinja2 |
| Low | 2 | flask, cryptography |

**Bewertung:** Nur `requests` und `cryptography` sind direkte Abhaengigkeiten (requirements.txt). `urllib3` ist transitive Abhaengigkeit von `requests`. Flask, Werkzeug, Waitress und Jinja2 sind KEINE Abhaengigkeiten dieses Projekts -- die Alerts stammen vermutlich aus dem GitHub-Dependency-Graph (Lockfile oder vergangene Installationen).

**Handlungsbedarf:**
- `cryptography` auf >=44.0.0 aktualisieren (behebt High-Alerts)
- `requests`/`urllib3` auf aktuelle Version pruefen
