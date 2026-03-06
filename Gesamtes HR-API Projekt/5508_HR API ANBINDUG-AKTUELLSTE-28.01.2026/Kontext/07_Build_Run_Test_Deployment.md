# 07 - Build, Run, Test und Deployment

## Voraussetzungen

| Komponente | Version | Hinweis |
|------------|---------|---------|
| Python | 3.8+ | Getestet mit 3.13 |
| pip | aktuell | Paketmanager |
| Git | optional | Nur für Updates |

**Evidenz:** `README.md:46-50`, `docs/DEVELOPMENT.md:3-7`

---

## Installation

### 1. Repository klonen / Ordner kopieren

```bash
git clone <repository-url>
cd ACENCIA_API_Hub
```

### 2. Virtuelle Umgebung erstellen

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. Abhängigkeiten installieren

```bash
pip install -r requirements.txt
```

**Evidenz:** `README.md:52-76`, `docs/DEVELOPMENT.md:9-34`

---

## Anwendung starten

### Entwicklung (mit Auto-Reload)

```bash
python acencia_hub/app.py
```

- URL: `http://127.0.0.1:5001`
- Debug-Modus: Aktiviert (wenn `FLASK_DEBUG=true`)
- Auto-Reload: Bei Code-Änderungen

### Produktion (Waitress)

```bash
python run.py
```

- URL: `http://0.0.0.0:5001` (alle Interfaces)
- WSGI-Server: Waitress
- Auto-Update: Prüft GitHub vor Start

### Windows One-Click

```batch
start.bat
```

Dieses Skript:
1. Aktiviert virtuelle Umgebung
2. Installiert/aktualisiert Dependencies
3. Zeigt verfügbare IP-Adressen
4. Startet Server mit Waitress
5. Startet automatisch neu bei Crash

**Evidenz:** `start.bat`, `run.py`, `docs/DEVELOPMENT.md:36-48`

---

## Umgebungsvariablen setzen

### Windows (PowerShell)

```powershell
$env:ACENCIA_SECRET_KEY = "your-secure-random-key-min-32-chars"
$env:ACENCIA_MASTER_KEY = "your-encryption-key"
```

### Windows (CMD / start.bat)

```batch
set ACENCIA_SECRET_KEY=your-secure-random-key-min-32-chars
set ACENCIA_MASTER_KEY=your-encryption-key
python run.py
```

### Linux / macOS

```bash
export ACENCIA_SECRET_KEY="your-secure-random-key-min-32-chars"
export ACENCIA_MASTER_KEY="your-encryption-key"
python run.py
```

**Evidenz:** `Sicherheit/Umsetzung/00_INDEX.md:100-103`

---

## Tests ausführen

### pytest

```bash
# Alle Tests
pytest tests/ -v

# Nur Security-Tests
pytest tests/test_security.py -v

# Nur Auth-Tests
pytest tests/test_auth.py -v

# Mit Coverage
pytest tests/ -v --cov=acencia_hub
```

### Test-Struktur

```
tests/
├── __init__.py         # Paket-Init
├── conftest.py         # Fixtures (app, client)
├── test_auth.py        # Authentifizierungs-Tests
└── test_security.py    # Security-spezifische Tests
```

**Evidenz:** `Sicherheit/Umsetzung/00_INDEX.md:93-98`, `tests/`

---

## Generierte Artefakte

### Log-Dateien

| Datei | Inhalt |
|-------|--------|
| `server.log` | Anwendungs-Log (rotiert bei 10MB) |
| `server.log.1-5` | Backup-Logs |
| `audit.log` | Audit-Trail für Admin-Aktionen |
| `audit.log.1-10` | Backup-Audit-Logs |

### Dynamisch generierte Daten

| Ordner | Inhalt | Format |
|--------|--------|--------|
| `acencia_hub/_snapshots/` | Mitarbeiter-Snapshots | `{name}-{provider}-{timestamp}.json` |
| `acencia_hub/_history/` | Rohe API-Antworten | `{name}-{provider}-history-{timestamp}.json` |
| `acencia_hub/exports/` | Generierte Exporte | `delta-{name}-{provider}-{timestamp}.xlsx` |

### Konfigurationsdaten

| Datei | Inhalt |
|-------|--------|
| `acencia_hub/data/users.json` | Benutzerdatenbank |
| `acencia_hub/data/secrets.json` | GitHub PAT |
| `acencia_hub/data/triggers.json` | Trigger-Konfiguration + SMTP |
| `acencia_hub/data/trigger_log.json` | Trigger-Ausführungsprotokoll |
| `acencia_hub/employers.json` | Arbeitgeber-Konfiguration |

**Evidenz:** `docs/CONFIGURATION.md:175-196`

---

## Deployment-Optionen

### Option 1: Lokales LAN-Deployment (Standard)

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Browser   │────►│   ACENCIA   │────►│  HR APIs    │
│  (LAN)      │◄────│   (Port     │◄────│  (Internet) │
│             │     │    5001)    │     │             │
└─────────────┘     └─────────────┘     └─────────────┘
```

- Kein Reverse Proxy
- Kein HTTPS
- Direkter Zugriff im LAN

### Option 2: Mit Reverse Proxy (empfohlen)

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Browser   │────►│   nginx/    │────►│   ACENCIA   │────►│  HR APIs    │
│             │◄────│   Apache    │◄────│   (Port     │◄────│             │
│             │     │  (HTTPS)    │     │    5001)    │     │             │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
```

- TLS-Terminierung am Proxy
- `HTTPS_ENABLED=true` setzen
- Header-Forwarding konfigurieren

**Hinweis:** Die Anwendung ist für Option 1 konzipiert. Option 2 erfordert externe Konfiguration.

**Evidenz:** `Sicherheit/12_Schwachstellen_und_Fehlverhalten_Ist.md:26-38`

---

## Auto-Update

### Funktionsweise

1. Bei jedem Start von `run.py` wird `updater.run_update()` aufgerufen
2. Liest GitHub PAT aus `secrets.json`
3. Lädt ZIP von GitHub-Repository herunter
4. Extrahiert und kopiert Dateien (mit Ausschlüssen)
5. Löscht temporäre Dateien

### Ausgeschlossene Dateien

```python
EXCLUSIONS = [
    ".git", "venv", ".idea", "__pycache__",
    "_snapshots", "_history", "exports",
    "acencia_hub/data", "acencia_hub/updater.py", "start.bat"
]
```

### Manuelles Update

```bash
git pull origin main
pip install -r requirements.txt
```

**Evidenz:** `updater.py`, `README.md:183-193`

---

## Health-Checks

### Endpoints

| Endpoint | Beschreibung | Response |
|----------|--------------|----------|
| `GET /api/health` | Basis-Health-Check | `{"status": "healthy"}` |
| `GET /api/ready` | Readiness-Check | `{"status": "ready"}` |

**Evidenz:** `app.py` (SV-025 Fix)

---

## Backup-Empfehlungen

### Regelmäßig sichern

| Pfad | Inhalt | Priorität |
|------|--------|-----------|
| `acencia_hub/data/` | Benutzer, Secrets, Arbeitgeber | HOCH |
| `acencia_hub/_snapshots/` | Mitarbeiter-Snapshots | MITTEL |
| `server.log`, `audit.log` | Logs | NIEDRIG |

### Nicht sichern (regenerierbar)

- `venv/`
- `__pycache__/`
- `acencia_hub/exports/` (optional)
- `acencia_hub/_history/` (Backup der API)

**Evidenz:** `docs/CONFIGURATION.md:249-265`

---

## Fehlerbehebung

### Port bereits belegt

```bash
# Windows
netstat -an | findstr 5001
taskkill /F /PID <pid>
```

### Provider-Verbindungsfehler

1. Zugangsdaten in `employers.json` prüfen
2. `server.log` auf Fehler prüfen
3. Netzwerkverbindung testen
4. Demo-Modus für HRworks testen

### Session-Probleme

1. `ACENCIA_SECRET_KEY` prüfen (Warnung im Log?)
2. Browser-Cookies löschen
3. `data/force_logout.txt` löschen

**Evidenz:** `docs/DEVELOPMENT.md:139-180`

---

**Letzte Aktualisierung:** 29.01.2026
