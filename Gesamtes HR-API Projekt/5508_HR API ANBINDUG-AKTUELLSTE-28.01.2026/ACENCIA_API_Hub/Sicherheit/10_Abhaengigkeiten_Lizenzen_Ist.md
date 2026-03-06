# 10 - Abhängigkeiten und Lizenzen (IST-Zustand)

## Requirements

### requirements.txt

```
# Flask and its dependencies
Flask==3.0.3
Werkzeug==3.0.3
Jinja2==3.1.4
itsdangerous==2.2.0
click==8.1.7
blinker==1.8.2

# Application-specific dependencies
openpyxl==3.1.3
requests==2.32.3

# WSGI Server for hosting
waitress==3.0.0
```

**Evidenz:** `requirements.txt`

## Dependency-Analyse

### Direkte Abhängigkeiten

| Paket | Version | Zweck | Lizenz |
|-------|---------|-------|--------|
| Flask | 3.0.3 | Web-Framework | BSD-3-Clause |
| Werkzeug | 3.0.3 | WSGI, Passwort-Hashing | BSD-3-Clause |
| Jinja2 | 3.1.4 | Template-Engine | BSD-3-Clause |
| itsdangerous | 2.2.0 | Signierung | BSD-3-Clause |
| click | 8.1.7 | CLI-Framework | BSD-3-Clause |
| blinker | 1.8.2 | Signale | MIT |
| openpyxl | 3.1.3 | Excel-Erstellung | MIT |
| requests | 2.32.3 | HTTP-Client | Apache-2.0 |
| waitress | 3.0.0 | WSGI-Server | ZPL-2.1 |

### Transitive Abhängigkeiten

**UNVERIFIZIERT** - Vollständige Liste transitiver Abhängigkeiten nicht analysiert.

Bekannte transitive Abhängigkeiten:
- `MarkupSafe` (Jinja2)
- `charset-normalizer`, `idna`, `urllib3`, `certifi` (requests)
- `et_xmlfile` (openpyxl)

## Lockfiles

### IST-Zustand

| Datei | Vorhanden | Evidenz |
|-------|-----------|---------|
| `requirements.txt` | ✅ Mit Versionen | `requirements.txt` |
| `Pipfile.lock` | ❌ | Nicht gefunden |
| `poetry.lock` | ❌ | Nicht gefunden |
| `pip-tools` (requirements.in) | ❌ | Nicht gefunden |

**Beobachtungen:**
- Versionen sind gepinnt (gut)
- Keine Hash-Verifizierung
- Keine transitiven Versionen fixiert

## Bekannte Schwachstellen

### Automatischer Audit

**UNVERIFIZIERT** - Kein automatischer Security-Audit durchgeführt.

Befehle zur manuellen Prüfung:
```bash
pip-audit
safety check -r requirements.txt
```

### Manuelle Prüfung (Stand 28.01.2026)

| Paket | Version | CVEs bekannt |
|-------|---------|--------------|
| Flask | 3.0.3 | UNVERIFIZIERT |
| Werkzeug | 3.0.3 | UNVERIFIZIERT |
| Jinja2 | 3.1.4 | UNVERIFIZIERT |
| requests | 2.32.3 | UNVERIFIZIERT |
| openpyxl | 3.1.3 | UNVERIFIZIERT |
| waitress | 3.0.0 | UNVERIFIZIERT |

## Lizenz-Kompatibilität

### Projekt-Lizenz

```
Dieses Projekt ist proprietär und gehört Acencia.
```

**Evidenz:** `README.md:236`

### Lizenz-Matrix

| Abhängigkeit | Lizenz | Kompatibel mit proprietär |
|--------------|--------|---------------------------|
| Flask | BSD-3-Clause | ✅ Ja |
| Werkzeug | BSD-3-Clause | ✅ Ja |
| Jinja2 | BSD-3-Clause | ✅ Ja |
| itsdangerous | BSD-3-Clause | ✅ Ja |
| click | BSD-3-Clause | ✅ Ja |
| blinker | MIT | ✅ Ja |
| openpyxl | MIT | ✅ Ja |
| requests | Apache-2.0 | ✅ Ja |
| waitress | ZPL-2.1 | ✅ Ja |

**Beobachtung:** Alle Lizenzen sind mit proprietärer Nutzung kompatibel.

## Dependency-Update-Strategie

### IST-Zustand

| Aspekt | Status |
|--------|--------|
| Automatische Updates | ❌ |
| Dependabot | ❌ |
| Renovate | ❌ |
| Manuelle Prüfung | UNVERIFIZIERT |

### Auto-Update via GitHub

Der `updater.py` aktualisiert das gesamte Projekt, inkl. `requirements.txt`:

```python
# Dependencies werden bei jedem Start aktualisiert
python -m pip install -r requirements.txt
```

**Evidenz:** `start.bat:34`

## Externe Ressourcen (CDN)

### Google Fonts

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;600&family=Tenor+Sans&display=swap" rel="stylesheet">
```

**Evidenz:** `base.html:9-11`

**Beobachtungen:**
- Externe JavaScript/CSS-Ressourcen
- Keine Subresource Integrity (SRI) Hashes
- Abhängigkeit von Google-Diensten

## Zusammenfassung

| Aspekt | Status | Risiko |
|--------|--------|--------|
| Versionspinning | ✅ Vorhanden | Niedrig |
| Lockfile | ❌ Fehlt | Mittel |
| Security Audit | ❌ Nicht automatisiert | Hoch |
| Lizenz-Compliance | ✅ Kompatibel | Niedrig |
| SRI für CDN | ❌ Fehlt | Mittel |

---

**Letzte Aktualisierung:** 28.01.2026
