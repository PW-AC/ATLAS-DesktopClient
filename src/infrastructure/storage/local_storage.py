"""
Lokaler Storage fuer Provisionsdaten via QSettings.

Speichert Dateipfade zu Import-Dateien fuer den
Rohdaten-Viewer (Excel-Navigation zu Originalzeilen).
"""

import logging
from typing import Optional

from PySide6.QtCore import QSettings

logger = logging.getLogger(__name__)

_SETTINGS_GROUP = 'ProvisionImport'


class ProvisionLocalStorage:
    """QSettings-Wrapper fuer lokale Dateipfade."""

    def __init__(self):
        self._settings = QSettings('ATLAS', 'DesktopClient')

    def save_import_file_path(self, batch_id: int, filepath: str) -> None:
        """Speichert den lokalen Dateipfad einer VU-Import-Datei."""
        self._settings.beginGroup(_SETTINGS_GROUP)
        self._settings.setValue(f'vu_file_{batch_id}', filepath)
        self._settings.endGroup()
        logger.debug(f"VU-Dateipfad gespeichert: batch={batch_id}, path={filepath}")

    def get_import_file_path(self, batch_id: int) -> Optional[str]:
        """Gibt den lokalen Dateipfad einer VU-Import-Datei zurueck."""
        self._settings.beginGroup(_SETTINGS_GROUP)
        path = self._settings.value(f'vu_file_{batch_id}')
        self._settings.endGroup()
        return str(path) if path else None

    def save_xempus_file_path(self, batch_id: int, filepath: str) -> None:
        """Speichert den lokalen Dateipfad einer Xempus-Import-Datei."""
        self._settings.beginGroup(_SETTINGS_GROUP)
        self._settings.setValue(f'xempus_file_{batch_id}', filepath)
        self._settings.endGroup()

    def get_xempus_file_path(self, batch_id: int) -> Optional[str]:
        """Gibt den lokalen Dateipfad einer Xempus-Import-Datei zurueck."""
        self._settings.beginGroup(_SETTINGS_GROUP)
        path = self._settings.value(f'xempus_file_{batch_id}')
        self._settings.endGroup()
        return str(path) if path else None

    def save_sheet_name(self, batch_id: int, sheet_name: str) -> None:
        """Speichert den Sheet-Namen eines Imports."""
        self._settings.beginGroup(_SETTINGS_GROUP)
        self._settings.setValue(f'sheet_{batch_id}', sheet_name)
        self._settings.endGroup()

    def get_sheet_name(self, batch_id: int) -> Optional[str]:
        """Gibt den Sheet-Namen eines Imports zurueck."""
        self._settings.beginGroup(_SETTINGS_GROUP)
        name = self._settings.value(f'sheet_{batch_id}')
        self._settings.endGroup()
        return str(name) if name else None
