# 07 - Server, Deployment, Webspace (IST-Zustand)

## Server-Konfiguration

### Waitress WSGI Server

| Aspekt | Wert | Evidenz |
|--------|------|---------|
| Server | Waitress 3.0.0 | `requirements.txt:14` |
| Host | `0.0.0.0` | `run.py:57` |
| Port | `5001` | `run.py:58` |
| SSL/TLS | Nicht konfiguriert | `run.py:64` |
| Worker Threads | Default (4) | Keine Konfiguration |

**Start-Befehl:**

```python
serve(app, host=host, port=port)
```

**Evidenz:** `run.py:64`

### Flask Development Server

| Aspekt | Wert | Evidenz |
|--------|------|---------|
| Debug-Modus | `True` (aktivierbar) | `app.py:2718` |
| Host | `127.0.0.1` | `app.py:2718` |
| Port | `5001` | `app.py:2718` |

**Beobachtung:** Debug-Modus ist im Code aktiviert, wenn `app.py` direkt ausgeführt wird.

## Deployment-Artefakte

### start.bat (Windows)

```batch
@echo off
setlocal

cd /d "%~dp0"
title Acencia Hub Launcher

set VENV_DIR=venv
set REQUIREMENTS_FILE=requirements.txt

# Virtual Environment aktivieren
call "%VENV_DIR%\Scripts\activate.bat"

# Dependencies installieren
python -m pip install -r "%REQUIREMENTS_FILE%"

# Server mit Auto-Restart
:start_server
python -u run.py
timeout /t 3 /nobreak >nul
goto start_server
```

**Evidenz:** `start.bat`

**Beobachtungen:**
- Automatischer Neustart bei Crash/Exit
- 3 Sekunden Verzögerung zwischen Restarts
- Kein Service-Management (keine Windows-Dienst-Integration)

### run.py

- Führt Update-Check durch
- Zeigt IP-Adressen an
- Startet Waitress-Server

**Evidenz:** `run.py`

## Netzwerk-Exposition

### Binding

| Interface | Port | Erreichbar von |
|-----------|------|----------------|
| `0.0.0.0` | 5001 | Alle Netzwerk-Interfaces |

**Beobachtung:** Server ist von allen Geräten im LAN erreichbar.

### IP-Erkennung

```python
hostname = socket.gethostname()
ip_addresses = socket.gethostbyname_ex(hostname)[2]
for ip in ip_addresses:
    if not ip.startswith("127."):
        print(f"    --> http://{ip}:{port} (for other devices)")
```

**Evidenz:** `run.py:23-33`

## Umgebungs-Trennung

### IST-Zustand

| Umgebung | Konfiguration | Evidenz |
|----------|---------------|---------|
| Development | `app.run(debug=True)` | `app.py:2718` |
| Production | Waitress via `run.py` | `run.py:64` |
| Staging | Nicht vorhanden | Keine Konfiguration |

**Beobachtungen:**
- Keine Umgebungsvariablen für Konfiguration
- Keine `.env`-Datei
- Debug-Modus hardcodiert

## CI/CD

### IST-Zustand

**Kein CI/CD vorhanden.**

| Aspekt | Status | Evidenz |
|--------|--------|---------|
| GitHub Actions | Nicht konfiguriert | Kein `.github/workflows/` |
| Jenkins | Nicht konfiguriert | Keine Jenkinsfile |
| GitLab CI | Nicht konfiguriert | Keine `.gitlab-ci.yml` |

### Auto-Update Mechanismus

Der `updater.py` fungiert als rudimentäres Deployment:

1. Download von GitHub (`main` Branch)
2. ZIP extrahieren
3. Dateien kopieren (mit Ausschlüssen)
4. Server wird über `start.bat` Loop neugestartet

**Evidenz:** `updater.py`, `start.bat:41-50`

## Docker / Container

### IST-Zustand

**Kein Docker-Support.**

| Aspekt | Status | Evidenz |
|--------|--------|---------|
| Dockerfile | Nicht vorhanden | Keine Datei |
| docker-compose.yml | Nicht vorhanden | Keine Datei |
| .dockerignore | Nicht vorhanden | Keine Datei |

## Webserver-Konfiguration

### IST-Zustand

**Kein Reverse Proxy konfiguriert.**

| Aspekt | Status |
|--------|--------|
| nginx | Nicht konfiguriert |
| Apache | Nicht konfiguriert |
| IIS | Nicht konfiguriert |
| Traefik | Nicht konfiguriert |

**Beobachtung:** Waitress bedient Anfragen direkt, ohne Reverse Proxy.

## Security Headers (Server-Level)

### Waitress

Waitress setzt keine Security Headers automatisch. Alle Header müssten in der Flask-App gesetzt werden.

**IST-Zustand:** Keine Security Headers.

## Firewall / Netzwerk-Sicherheit

### IST-Zustand

**UNVERIFIZIERT** - Keine Informationen über Firewall-Konfiguration im Projekt.

## Backup-Strategie

### IST-Zustand

**Keine automatische Backup-Strategie.**

| Daten | Backup | Evidenz |
|-------|--------|---------|
| users.json | Nicht vorhanden | Keine Backup-Logik |
| employers.json | Nicht vorhanden | Keine Backup-Logik |
| secrets.json | Nicht vorhanden | Keine Backup-Logik |
| _snapshots/ | Implicit (Datierung) | `app.py:1101` |
| _history/ | Implicit (Datierung) | `app.py:237-238` |

---

**Letzte Aktualisierung:** 28.01.2026
