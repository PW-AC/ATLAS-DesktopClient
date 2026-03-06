# 01 - Systemübersicht (IST-Zustand)

## Projekttyp

**Web-Anwendung** - Flask-basierte Single-Page-Application mit Server-Side-Rendering

## Tech-Stack

| Komponente | Technologie | Version | Evidenz |
|------------|-------------|---------|---------|
| Sprache | Python | 3.8+ (3.13 in venv) | `requirements.txt` |
| Framework | Flask | 3.0.3 | `requirements.txt:2` |
| Template-Engine | Jinja2 | 3.1.4 | `requirements.txt:4` |
| WSGI-Server | Waitress | 3.0.0 | `requirements.txt:14` |
| HTTP-Client | requests | 2.32.3 | `requirements.txt:11` |
| Excel-Export | openpyxl | 3.1.3 | `requirements.txt:10` |
| Passwort-Hashing | Werkzeug | 3.0.3 | `requirements.txt:3` |

## Zielumgebung

| Aspekt | IST-Zustand | Evidenz |
|--------|-------------|---------|
| Deployment-Typ | Lokaler Windows-Server | `start.bat` |
| Netzwerk | LAN-Zugriff (0.0.0.0:5001) | `run.py:57-58` |
| Betriebssystem | Windows | `start.bat`, PowerShell-Pfade |
| Reverse Proxy | NICHT VORHANDEN | UNVERIFIZIERT |
| HTTPS/TLS | NICHT KONFIGURIERT | Keine TLS-Konfiguration gefunden |

## Start- und Build-Hinweise

### Entwicklung

```bash
python acencia_hub/app.py
```
**Evidenz:** `app.py:2712-2718`

### Produktion

```bash
start.bat
# oder
python run.py
```
**Evidenz:** `start.bat`, `run.py`

### Abhängigkeiten installieren

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```
**Evidenz:** `start.bat:31-34`, `README.md:60-75`

## Projektstruktur

```
ACENCIA_API_Hub/
├── acencia_hub/           # Hauptanwendung
│   ├── app.py            # ~2719 Zeilen - Gesamte Anwendungslogik
│   ├── updater.py        # Auto-Update von GitHub
│   ├── __init__.py       # Modul-Metadaten
│   ├── data/             # Persistente Daten
│   │   └── users.json    # Benutzerdatenbank
│   ├── static/css/       # Stylesheets
│   ├── templates/        # 13 Jinja2-Templates
│   ├── _snapshots/       # Generierte Snapshots (JSON)
│   ├── _history/         # API-Response-Backup (JSON)
│   └── exports/          # Generierte Exporte (XLSX)
├── venv/                 # Virtuelle Umgebung
├── docs/                 # Dokumentation
├── requirements.txt      # Python-Abhängigkeiten
├── run.py               # Produktions-Entry-Point
├── start.bat            # Windows-Starter
├── server.log           # Log-Datei
├── AGENTS.md            # KI-Dokumentation
└── README.md            # Projekt-README
```

## Ignorierte Build-Artefakte

Folgende Pfade wurden von der Analyse ausgeschlossen:

- `venv/` - Virtuelle Umgebung (822+ Python-Dateien)
- `__pycache__/` - Python-Bytecode
- `acencia_hub/_history/` - 69+ JSON-Dateien mit API-Rohdaten
- `acencia_hub/_snapshots/` - Generierte Snapshot-Dateien
- `acencia_hub/exports/` - Generierte Export-Dateien

## Externe Abhängigkeiten

### HR-Provider APIs

| Provider | API-Endpunkt | Evidenz |
|----------|-------------|---------|
| Personio | `https://api.personio.de/v1` | `app.py:736` |
| HRworks (Prod) | `https://api.hrworks.de/v2` | `app.py:444` |
| HRworks (Demo) | `https://api.demo-hrworks.de/v2` | `app.py:445` |
| SageHR | Mock-Implementierung | `app.py:685-727` |

### Update-Mechanismus

| Aspekt | Wert | Evidenz |
|--------|------|---------|
| GitHub-Repo | `paulweimert2006-commits/JULES_WEB4` | `updater.py:12` |
| Branch | `main` | `updater.py:12` |
| Auth | GitHub PAT | `updater.py:107-108` |

---

**Letzte Aktualisierung:** 28.01.2026
