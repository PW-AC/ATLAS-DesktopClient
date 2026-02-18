"""
BiPro API - KI-Klassifikation Einstellungen

Verwaltung der KI-Verarbeitungseinstellungen (Prompts, Modelle, Stufen).
Oeffentlicher Endpunkt fuer document_processor + Admin-CRUD fuer Prompt-Versionierung.
"""

from typing import Optional, Dict, List
import logging

from .client import APIClient, APIError

logger = logging.getLogger(__name__)


class ProcessingSettingsAPI:
    """
    API-Client fuer KI-Klassifikation Einstellungen.
    
    Verwendung:
        settings_api = ProcessingSettingsAPI(client)
        settings = settings_api.get_ai_settings()
    """
    
    def __init__(self, client: APIClient):
        self.client = client
    
    # ================================================================
    # Oeffentliche Endpunkte (JWT erforderlich, kein Admin)
    # ================================================================
    
    def get_ai_settings(self) -> Dict:
        """
        Aktive KI-Einstellungen laden (Prompts, Modelle, Stage-Config).
        
        Wird vom document_processor bei jedem Verarbeitungslauf aufgerufen.
        
        Returns:
            Dict mit stage1_*, stage2_* Feldern
        """
        try:
            response = self.client.get('/processing-settings/ai')
            if response.get('success'):
                return response['data'].get('settings', {})
        except APIError as e:
            logger.error(f"Fehler beim Laden der KI-Einstellungen: {e}")
            raise
        return {}
    
    # ================================================================
    # Admin-Endpunkte (Admin-Rechte erforderlich)
    # ================================================================
    
    def get_ai_settings_admin(self) -> Dict:
        """
        KI-Einstellungen mit Versionsinfo laden (Admin).
        
        Returns:
            Dict mit settings, active_stage1_version, active_stage2_version
        """
        try:
            response = self.client.get('/admin/processing-settings/ai')
            if response.get('success'):
                return response.get('data', {})
        except APIError as e:
            logger.error(f"Fehler beim Laden der KI-Einstellungen (Admin): {e}")
            raise
        return {}
    
    def save_ai_settings(self, data: Dict) -> Dict:
        """
        KI-Einstellungen speichern (Admin).
        
        Bei Prompt-Aenderung wird automatisch eine neue Version erstellt.
        
        Args:
            data: Dict mit stage1_*, stage2_* Feldern
            
        Returns:
            Aktualisierte Settings
        """
        try:
            response = self.client.put('/admin/processing-settings/ai', json_data=data)
            if response.get('success'):
                return response['data'].get('settings', {})
        except APIError as e:
            logger.error(f"Fehler beim Speichern der KI-Einstellungen: {e}")
            raise
        return {}
    
    def get_prompt_versions(self, stage: Optional[str] = None) -> List[Dict]:
        """
        Prompt-Versionen auflisten (Admin).
        
        Args:
            stage: Optional - 'stage1' oder 'stage2' zum Filtern
            
        Returns:
            Liste von Prompt-Version-Dicts
        """
        try:
            url = '/admin/processing-settings/prompt-versions'
            if stage:
                url += f'?stage={stage}'
            response = self.client.get(url)
            if response.get('success'):
                return response['data'].get('versions', [])
        except APIError as e:
            logger.error(f"Fehler beim Laden der Prompt-Versionen: {e}")
            raise
        return []
    
    def activate_prompt_version(self, version_id: int) -> Dict:
        """
        Eine gespeicherte Prompt-Version aktivieren (Admin).
        
        Args:
            version_id: ID der zu aktivierenden Version
            
        Returns:
            Aktualisierte Settings
        """
        try:
            response = self.client.post(
                f'/admin/processing-settings/prompt-versions/{version_id}/activate'
            )
            if response.get('success'):
                return response['data'].get('settings', {})
        except APIError as e:
            logger.error(f"Fehler beim Aktivieren der Prompt-Version {version_id}: {e}")
            raise
        return {}
