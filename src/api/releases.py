"""
BiPro API - Releases / Auto-Update

API-Client fuer Release-Verwaltung (Admin) und Update-Check (Public).
"""

from typing import Optional, Dict, Any, List
import logging

from .client import APIClient, APIError

logger = logging.getLogger(__name__)


class ReleasesAPI:
    """
    API-Client fuer Release-Endpunkte.
    
    Verwendung:
        releases_api = ReleasesAPI(client)
        releases = releases_api.get_releases()
        releases_api.update_release(1, status='mandatory')
    """
    
    def __init__(self, client: APIClient):
        self.client = client
    
    # ================================================================
    # Oeffentlich: Update-Check
    # ================================================================
    
    def check_for_update(self, current_version: str, channel: str = 'stable') -> Dict:
        """
        Prueft ob ein Update verfuegbar ist.
        
        Args:
            current_version: Aktuelle App-Version (z.B. '0.9.8')
            channel: Update-Channel ('stable', 'beta', 'dev')
            
        Returns:
            Dict mit update_available, mandatory, deprecated, etc.
        """
        try:
            response = self.client.get(
                '/updates/check',
                params={'version': current_version, 'channel': channel}
            )
            return response
        except APIError as e:
            logger.error(f"Update-Check fehlgeschlagen: {e}")
            raise
    
    def get_public_releases(self) -> List[Dict]:
        """
        Oeffentliche Release-Liste (fuer Mitteilungszentrale).
        Gibt aktive/mandatory Releases zurueck (ohne Admin-Felder).
        Keine Admin-Rechte erforderlich.
        """
        try:
            response = self.client.get('/releases')
            if response.get('success'):
                return response['data'].get('releases', [])
        except APIError as e:
            logger.warning(f"Oeffentliche Releases nicht verfuegbar: {e}")
        return []
    
    # ================================================================
    # Admin: Release-Verwaltung
    # ================================================================
    
    def get_releases(self) -> List[Dict]:
        """Alle Releases auflisten (nur Admin)."""
        try:
            response = self.client.get('/admin/releases')
            if response.get('success'):
                return response['data'].get('releases', [])
        except APIError as e:
            logger.error(f"Fehler beim Laden der Releases: {e}")
            raise
        return []
    
    def get_release(self, release_id: int) -> Optional[Dict]:
        """Einzelnes Release abrufen (nur Admin)."""
        try:
            response = self.client.get(f'/admin/releases/{release_id}')
            if response.get('success'):
                return response['data'].get('release')
        except APIError as e:
            logger.error(f"Fehler beim Laden des Releases {release_id}: {e}")
            raise
        return None
    
    def create_release(self, file_path: str, version: str, channel: str = 'stable',
                       release_notes: str = '', min_version: str = '',
                       smoke_test_report: str = '', required_schema: str = '') -> Dict:
        """
        Neues Release hochladen (nur Admin). Status startet als 'pending'.
        
        Args:
            file_path: Pfad zur EXE-Datei
            version: Versionsnummer (z.B. '1.0.0')
            channel: 'stable', 'beta' oder 'dev'
            release_notes: Release Notes (Markdown)
            min_version: Optionale Mindestversion
            smoke_test_report: JSON-String des Smoke-Test-Reports
            required_schema: Erwartete Schema-Migration (z.B. '035_release_gate_status')
        """
        additional_data = {
            'version': version,
            'channel': channel,
            'release_notes': release_notes,
        }
        if min_version:
            additional_data['min_version'] = min_version
        if smoke_test_report:
            additional_data['smoke_test_report'] = smoke_test_report
        if required_schema:
            additional_data['required_schema'] = required_schema
        
        try:
            response = self.client.upload_file(
                '/admin/releases',
                file_path=file_path,
                additional_data=additional_data
            )
            if response.get('success'):
                return response['data'].get('release', {})
        except APIError as e:
            logger.error(f"Fehler beim Erstellen des Releases: {e}")
            raise
        return {}
    
    def validate_release(self, release_id: int) -> Dict:
        """
        Release-Validierung ausfuehren (Gate Engine).
        
        Args:
            release_id: ID des Releases
            
        Returns:
            Dict mit gate_report und aktualisiertem Release
        """
        try:
            response = self.client.post(f'/admin/releases/{release_id}/validate')
            if response.get('success'):
                return response.get('data', {})
        except APIError as e:
            logger.error(f"Fehler bei Release-Validierung: {e}")
            raise
        return {}
    
    def update_release(self, release_id: int, status: str = None,
                       channel: str = None, release_notes: str = None,
                       min_version: str = None) -> Dict:
        """
        Release bearbeiten (nur Admin).
        
        Args:
            release_id: ID des Releases
            status: 'active', 'mandatory', 'deprecated', 'withdrawn'
            channel: 'stable', 'beta', 'dev'
            release_notes: Release Notes Text
            min_version: Mindestversion (None um zu loeschen)
        """
        data = {}
        if status is not None:
            data['status'] = status
        if channel is not None:
            data['channel'] = channel
        if release_notes is not None:
            data['release_notes'] = release_notes
        if min_version is not None:
            data['min_version'] = min_version
        
        try:
            response = self.client.put(f'/admin/releases/{release_id}', json_data=data)
            if response.get('success'):
                return response['data'].get('release', {})
        except APIError as e:
            logger.error(f"Fehler beim Aktualisieren des Releases {release_id}: {e}")
            raise
        return {}
    
    def withdraw_release(self, release_id: int) -> Dict:
        """
        Release zurueckziehen mit Auto-Fallback auf vorheriges Release.

        Args:
            release_id: ID des aktiven/mandatory Releases

        Returns:
            Dict mit withdrawn_release, fallback_release und message
        """
        try:
            response = self.client.post(f'/admin/releases/{release_id}/withdraw')
            if response.get('success'):
                return response.get('data', {})
        except APIError as e:
            logger.error(f"Fehler beim Withdraw von Release {release_id}: {e}")
            raise
        return {}

    def delete_release(self, release_id: int) -> bool:
        """
        Release loeschen (nur Admin, nur wenn 0 Downloads).
        
        Raises:
            APIError: 409 wenn Downloads existieren
        """
        try:
            response = self.client.delete(f'/admin/releases/{release_id}')
            return response.get('success', False)
        except APIError as e:
            logger.error(f"Fehler beim Loeschen des Releases {release_id}: {e}")
            raise
