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
