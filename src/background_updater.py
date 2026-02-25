"""
ACENCIA ATLAS - Hintergrund-Updater

Headless Update-Check ohne Qt-Abhaengigkeiten.
Wird via --background-update Flag aufgerufen (Scheduled Task / Autostart).

Flow:
1. Lock-File pruefen (verhindert doppelte Ausfuehrung)
2. Token laden (Keyring bevorzugt, Datei-Fallback)
3. Token beim Server validieren
4. Aktuelle Version lesen
5. Update-Check beim Server
6. Bei Update: Download + SHA256-Verifikation + Silent Install (ohne App-Start)
"""

import os
import sys
import json
import hashlib
import tempfile
import subprocess
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional, Dict

import requests

API_BASE_URL = "https://acencia.info/api"
UPDATE_TEMP_DIR = os.path.join(tempfile.gettempdir(), 'bipro_updates')
LOCK_FILE = os.path.join(tempfile.gettempdir(), 'atlas_updater.lock')
TOKEN_FILE = Path.home() / '.bipro_gdv_token.json'

logger = logging.getLogger("background_updater")


def _setup_logging():
    """Konfiguriert Logging fuer den Hintergrund-Updater."""
    app_dir = os.path.dirname(os.path.abspath(__file__))
    log_dir = os.path.join(app_dir, "..", "logs")
    os.makedirs(log_dir, exist_ok=True)

    log_file = os.path.join(log_dir, "background_updater.log")
    handler = RotatingFileHandler(
        log_file, maxBytes=1_048_576, backupCount=2, encoding='utf-8'
    )
    handler.setFormatter(logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    ))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


def _acquire_lock() -> bool:
    """Erstellt Lock-File. Gibt False zurueck wenn bereits gelockt."""
    try:
        if os.path.exists(LOCK_FILE):
            try:
                with open(LOCK_FILE, 'r') as f:
                    pid = int(f.read().strip())
                # Pruefen ob der Prozess noch laeuft (Windows-spezifisch)
                import ctypes
                kernel32 = ctypes.windll.kernel32
                handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
                if handle:
                    kernel32.CloseHandle(handle)
                    logger.info(f"Anderer Updater-Prozess laeuft (PID {pid}), abbrechen")
                    return False
            except (ValueError, OSError):
                pass
            os.unlink(LOCK_FILE)

        with open(LOCK_FILE, 'w') as f:
            f.write(str(os.getpid()))
        return True
    except OSError as e:
        logger.warning(f"Lock-File Fehler: {e}")
        return False


def _release_lock():
    """Entfernt Lock-File."""
    try:
        if os.path.exists(LOCK_FILE):
            os.unlink(LOCK_FILE)
    except OSError:
        pass


def _load_token() -> Optional[str]:
    """Laedt gespeicherten JWT-Token (Keyring bevorzugt, Datei-Fallback)."""
    # Keyring (DPAPI-geschuetzt)
    try:
        import keyring
        data = keyring.get_password("acencia_atlas", "jwt_token")
        if data:
            parsed = json.loads(data)
            token = parsed.get('token')
            if token:
                logger.debug("Token aus Keyring geladen")
                return token
    except Exception:
        pass

    # Datei-Fallback
    try:
        if TOKEN_FILE.exists():
            parsed = json.loads(TOKEN_FILE.read_text())
            token = parsed.get('token')
            if token:
                logger.debug("Token aus Datei geladen")
                return token
    except Exception:
        pass

    return None


def _validate_token(token: str) -> Optional[Dict]:
    """Validiert den Token beim Server und gibt User-Daten zurueck (inkl. update_channel)."""
    try:
        resp = requests.get(
            f"{API_BASE_URL}/auth/verify",
            headers={'Authorization': f'Bearer {token}', 'Accept': 'application/json'},
            timeout=15,
            verify=True,
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get('valid', False):
                return data
        return None
    except Exception as e:
        logger.warning(f"Token-Validierung fehlgeschlagen: {e}")
        return None


def _read_version() -> str:
    """Liest die aktuelle App-Version aus der VERSION-Datei."""
    candidates = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "VERSION"),
        os.path.join(os.path.dirname(sys.executable), "VERSION"),
        os.path.join(getattr(sys, '_MEIPASS', ''), "VERSION"),
    ]
    for path in candidates:
        try:
            with open(path, 'r', encoding='utf-8-sig') as f:
                version = f.read().strip()
                if version:
                    return version
        except (FileNotFoundError, OSError):
            continue
    return "0.0.0"


def _check_for_update(version: str, channel: str = 'stable') -> Optional[Dict]:
    """Prueft beim Server ob ein Update verfuegbar ist."""
    try:
        resp = requests.get(
            f"{API_BASE_URL}/updates/check",
            params={'version': version, 'channel': channel},
            headers={'Accept': 'application/json'},
            timeout=15,
            verify=True,
        )
        resp.raise_for_status()
        data = resp.json()

        if data.get('update_available'):
            return data
        return None
    except Exception as e:
        logger.warning(f"Update-Check fehlgeschlagen: {e}")
        return None


def _download_and_install(update_data: Dict) -> bool:
    """Laedt Update herunter, verifiziert SHA256 und startet Silent-Install."""
    download_url = update_data.get('download_url', '')
    expected_sha256 = update_data.get('sha256', '')
    latest_version = update_data.get('latest_version', 'unknown')
    file_size = update_data.get('file_size', 0)

    if not download_url:
        logger.error("Keine Download-URL im Update-Check")
        return False

    os.makedirs(UPDATE_TEMP_DIR, exist_ok=True)
    _cleanup_old_downloads()

    filename = f"ACENCIA-ATLAS-Setup-{latest_version}.exe"
    target_path = Path(UPDATE_TEMP_DIR) / filename

    logger.info(f"Lade Update herunter: {download_url}")

    try:
        resp = requests.get(download_url, stream=True, timeout=300, verify=True)
        resp.raise_for_status()

        downloaded = 0
        sha256_hash = hashlib.sha256()

        with open(target_path, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=65536):
                if chunk:
                    f.write(chunk)
                    sha256_hash.update(chunk)
                    downloaded += len(chunk)

        logger.info(f"Download abgeschlossen: {downloaded} Bytes")

        # SHA256-Verifikation
        if expected_sha256:
            computed = sha256_hash.hexdigest()
            if computed.lower() != expected_sha256.lower():
                target_path.unlink(missing_ok=True)
                logger.error(f"SHA256-Mismatch! Erwartet: {expected_sha256}, Berechnet: {computed}")
                return False
            logger.info("SHA256-Verifikation erfolgreich")

        # Silent Install OHNE App-Start (/norun=1)
        logger.info(f"Starte Silent-Installation: {target_path}")
        subprocess.Popen(
            [str(target_path), '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/norun=1'],
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        )
        logger.info("Installer gestartet (Hintergrund-Update, kein App-Start)")
        return True

    except requests.RequestException as e:
        logger.error(f"Download-Fehler: {e}")
        target_path.unlink(missing_ok=True)
        return False
    except OSError as e:
        logger.error(f"Installations-Fehler: {e}")
        return False


def _cleanup_old_downloads():
    """Loescht alte heruntergeladene Installer."""
    try:
        if not os.path.exists(UPDATE_TEMP_DIR):
            return
        for f in os.listdir(UPDATE_TEMP_DIR):
            filepath = os.path.join(UPDATE_TEMP_DIR, f)
            if os.path.isfile(filepath) and f.endswith('.exe'):
                try:
                    os.unlink(filepath)
                except OSError:
                    pass
    except OSError:
        pass


def run_background_update() -> int:
    """
    Hauptfunktion des Hintergrund-Updaters.

    Returns:
        Exit-Code (0 = Erfolg/kein Update, 1 = Fehler)
    """
    _setup_logging()
    logger.info("=== Hintergrund-Updater gestartet ===")

    if not _acquire_lock():
        logger.info("Lock aktiv, beende")
        return 0

    try:
        # 1. Token laden
        token = _load_token()
        if not token:
            logger.info("Kein gespeicherter Token, beende")
            return 0

        # 2. Token validieren und User-Daten (inkl. Channel) holen
        verify_data = _validate_token(token)
        if not verify_data:
            logger.info("Token ungueltig/abgelaufen, beende")
            return 0

        update_channel = verify_data.get('update_channel', 'stable')
        logger.info(f"Update-Channel fuer diesen User: {update_channel}")

        # 3. Version lesen
        version = _read_version()
        logger.info(f"Installierte Version: {version}")

        # 4. Update-Check
        update_data = _check_for_update(version, channel=update_channel)
        if not update_data:
            logger.info("Kein Update verfuegbar")
            return 0

        latest = update_data.get('latest_version', '?')
        logger.info(f"Update verfuegbar: {version} -> {latest}")

        # 5. Download + Installation
        if _download_and_install(update_data):
            logger.info("Hintergrund-Update erfolgreich abgeschlossen")
            return 0
        else:
            logger.error("Hintergrund-Update fehlgeschlagen")
            return 1

    except Exception as e:
        logger.error(f"Unerwarteter Fehler: {e}", exc_info=True)
        return 1
    finally:
        _release_lock()
        logger.info("=== Hintergrund-Updater beendet ===")
