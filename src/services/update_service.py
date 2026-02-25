"""
ACENCIA ATLAS - Update-Service

Prueft auf Updates, laedt Installer herunter und startet die Installation.
"""

import os
import sys
import hashlib
import tempfile
import subprocess
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable

import ssl
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context

from api.client import APIClient, APIError

logger = logging.getLogger(__name__)

# Temp-Verzeichnis fuer Downloads
UPDATE_TEMP_DIR = os.path.join(tempfile.gettempdir(), 'bipro_updates')

# SV-016 Fix: Certificate-Pinning fuer Update-Kanal
# SHA256-Fingerprints des acencia.info Zertifikats (aktuell + naechster fuer Rotation)
# Zum Aktualisieren: openssl s_client -connect acencia.info:443 | openssl x509 -pubkey -noout | openssl pkey -pubin -outform DER | openssl dgst -sha256
PINNED_CERT_HASHES = [
    # Platzhalter: Muss mit dem tatsaechlichen Zertifikat-Hash befuellt werden
    # Format: "sha256/BASE64_ENCODED_HASH"
    # Bis dahin: Pinning deaktiviert (nur verify=True)
]


@dataclass
class UpdateInfo:
    """Informationen ueber ein verfuegbares Update."""
    current_version: str
    latest_version: str
    update_available: bool
    mandatory: bool
    deprecated: bool
    release_notes: str = ''
    download_url: str = ''
    sha256: str = ''
    file_size: int = 0
    released_at: str = ''


class UpdateService:
    """
    Service fuer automatische Updates.
    
    Prueft auf verfuegbare Updates, laedt Installer herunter,
    verifiziert den Hash und startet die Silent-Installation.
    
    Verwendung:
        service = UpdateService(api_client)
        info = service.check_for_update('0.9.8')
        if info and info.update_available:
            path = service.download_update(info, progress_callback=on_progress)
            service.install_update(path)
    """
    
    def __init__(self, api_client: APIClient, channel: str = 'stable'):
        self._client = api_client
        self._channel = channel if channel in ('stable', 'beta', 'dev') else 'stable'
    
    def check_for_update(self, current_version: str) -> Optional[UpdateInfo]:
        """
        Prueft ob ein Update verfuegbar ist.
        
        Args:
            current_version: Aktuelle App-Version
            
        Returns:
            UpdateInfo wenn Update/Deprecated, None bei Fehler oder kein Update
        """
        try:
            response = self._client.get(
                '/updates/check',
                params={'version': current_version, 'channel': self._channel}
            )
            
            info = UpdateInfo(
                current_version=response.get('current_version', current_version),
                latest_version=response.get('latest_version', current_version),
                update_available=response.get('update_available', False),
                mandatory=response.get('mandatory', False),
                deprecated=response.get('deprecated', False),
                release_notes=response.get('release_notes', ''),
                download_url=response.get('download_url', ''),
                sha256=response.get('sha256', ''),
                file_size=response.get('file_size', 0),
                released_at=response.get('released_at', ''),
            )
            
            # Nur zurueckgeben wenn es etwas Relevantes gibt
            if info.update_available or info.mandatory or info.deprecated:
                logger.info(
                    f"Update-Check: verfuegbar={info.update_available}, "
                    f"pflicht={info.mandatory}, veraltet={info.deprecated}, "
                    f"aktuell={info.current_version}, neueste={info.latest_version}"
                )
                return info
            
            logger.debug(f"Kein Update verfuegbar (aktuell: {current_version})")
            return None
            
        except APIError as e:
            logger.warning(f"Update-Check fehlgeschlagen: {e}")
            return None
        except Exception as e:
            logger.warning(f"Update-Check Fehler: {e}")
            return None
    
    def download_update(
        self,
        update_info: UpdateInfo,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> Path:
        """
        Laedt den Installer herunter und verifiziert den SHA256-Hash.
        
        Args:
            update_info: UpdateInfo mit download_url und sha256
            progress_callback: Optional - wird mit (bytes_downloaded, total_bytes) aufgerufen
            
        Returns:
            Pfad zur heruntergeladenen Datei
            
        Raises:
            UpdateDownloadError: Bei Download-/Verifikationsfehler
        """
        # Temp-Verzeichnis erstellen
        os.makedirs(UPDATE_TEMP_DIR, exist_ok=True)
        
        # Alte Downloads bereinigen
        self._cleanup_old_downloads()
        
        filename = f"ACENCIA-ATLAS-Setup-{update_info.latest_version}.exe"
        target_path = Path(UPDATE_TEMP_DIR) / filename
        
        logger.info(f"Lade Update herunter: {update_info.download_url} -> {target_path}")
        
        try:
            response = requests.get(
                update_info.download_url,
                stream=True,
                timeout=300,  # 5 Minuten Timeout fuer grosse Dateien
                verify=True
            )
            response.raise_for_status()
            
            total_size = update_info.file_size or int(response.headers.get('content-length', 0))
            downloaded = 0
            sha256_hash = hashlib.sha256()
            
            with open(target_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=65536):
                    if chunk:
                        f.write(chunk)
                        sha256_hash.update(chunk)
                        downloaded += len(chunk)
                        if progress_callback:
                            progress_callback(downloaded, total_size)
            
            logger.info(f"Download abgeschlossen: {downloaded} Bytes")
            
            # SHA256-Verifikation
            if update_info.sha256:
                computed_hash = sha256_hash.hexdigest()
                if computed_hash.lower() != update_info.sha256.lower():
                    # Datei loeschen bei Hash-Mismatch
                    target_path.unlink(missing_ok=True)
                    logger.error(
                        f"SHA256-Mismatch! Erwartet: {update_info.sha256}, "
                        f"Berechnet: {computed_hash}"
                    )
                    raise UpdateDownloadError("SHA256-Hash stimmt nicht ueberein")
                logger.info("SHA256-Verifikation erfolgreich")
            
            return target_path
            
        except requests.RequestException as e:
            logger.error(f"Download-Fehler: {e}")
            target_path.unlink(missing_ok=True)
            raise UpdateDownloadError(f"Download fehlgeschlagen: {e}")
    
    def install_update(self, installer_path: Path,
                       launch_after_install: bool = True) -> None:
        """
        Startet die Silent-Installation.
        
        Verwendet Inno Setup Silent-Parameter:
        /VERYSILENT - Komplett unsichtbare Installation
        /SUPPRESSMSGBOXES - Keine Dialoge
        /NORESTART - Kein Windows-Neustart
        /norun=1 - App NICHT starten nach Installation (nur bei launch_after_install=False)
        
        Args:
            installer_path: Pfad zur Installer-EXE
            launch_after_install: True = App startet nach Install (Standard),
                                  False = nur installieren (Hintergrund-Updater)
        """
        if not installer_path.exists():
            raise UpdateDownloadError(f"Installer nicht gefunden: {installer_path}")
        
        logger.info(f"Starte Installation: {installer_path} (launch={launch_after_install})")
        
        try:
            args = [str(installer_path), '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART']
            if not launch_after_install:
                args.append('/norun=1')
            subprocess.Popen(
                args,
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
            )
            logger.info("Installer gestartet, beende App...")
        except OSError as e:
            logger.error(f"Installer konnte nicht gestartet werden: {e}")
            raise UpdateDownloadError(f"Installation fehlgeschlagen: {e}")
    
    def _cleanup_old_downloads(self) -> None:
        """Loescht alte heruntergeladene Installer."""
        try:
            if not os.path.exists(UPDATE_TEMP_DIR):
                return
            for f in os.listdir(UPDATE_TEMP_DIR):
                filepath = os.path.join(UPDATE_TEMP_DIR, f)
                if os.path.isfile(filepath) and f.endswith('.exe'):
                    try:
                        os.unlink(filepath)
                        logger.debug(f"Alter Download geloescht: {f}")
                    except OSError:
                        pass  # In Benutzung, ignorieren
        except OSError:
            pass


class UpdateDownloadError(Exception):
    """Fehler beim Herunterladen oder Verifizieren eines Updates."""
    pass
