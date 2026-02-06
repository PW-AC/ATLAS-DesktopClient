"""
BiPro API - VU-Verbindungen

Verwaltung der Versicherer-Verbindungen und Credentials.
"""

from typing import List, Optional, Dict, Any
from dataclasses import dataclass
import logging

from .client import APIClient, APIError

logger = logging.getLogger(__name__)


# ============================================================================
# URL-Ableitungslogik (STS ↔ Transfer)
# ============================================================================

def derive_sts_url(url: str) -> str:
    """
    Leitet die STS-URL aus einer Transfer-URL ab.
    
    Typische Muster:
    - /430_Transfer/ → /410_STS/
    - /Transfer/ → /STS/
    - /transfer/ → /sts/
    - TransferService → UserPasswordLogin (VEMA)
    """
    if not url:
        return ""
    
    # Bereits eine STS-URL?
    if '/STS/' in url or '/sts/' in url or '410_STS' in url or 'SecurityTokenService' in url:
        return url
    # VEMA-Stil: UserPasswordLogin ist bereits die STS-URL
    if 'UserPasswordLogin' in url or 'X509Login' in url or 'VDGTicketLogin' in url:
        return url
    
    # Transfer → STS Transformation
    result = url
    
    # BiPRO-Standard: 430_Transfer → 410_STS
    if '430_Transfer' in result:
        result = result.replace('430_Transfer', '410_STS')
        result = result.replace('Service_', 'UserPasswordLogin_')
        return result
    
    # VEMA-Stil: TransferService → UserPasswordLogin
    if 'TransferService' in result:
        result = result.replace('TransferService', 'UserPasswordLogin')
        return result
    
    # Generische Muster
    if '/Transfer/' in result:
        result = result.replace('/Transfer/', '/STS/')
    elif '/transfer/' in result:
        result = result.replace('/transfer/', '/sts/')
    
    return result


def derive_transfer_url(url: str) -> str:
    """
    Leitet die Transfer-URL aus einer STS-URL ab.
    
    Typische Muster:
    - /410_STS/ → /430_Transfer/
    - /STS/ → /Transfer/
    - UserPasswordLogin → TransferService (VEMA)
    """
    if not url:
        return ""
    
    # Bereits eine Transfer-URL?
    if '/Transfer/' in url or '/transfer/' in url or '430_Transfer' in url or 'TransferService' in url:
        return url
    
    # STS → Transfer Transformation
    result = url
    
    # BiPRO-Standard: 410_STS → 430_Transfer
    if '410_STS' in result:
        result = result.replace('410_STS', '430_Transfer')
        result = result.replace('UserPasswordLogin_', 'Service_')
        result = result.replace('X509Login_', 'Service_')
        result = result.replace('VDGTicketLogin_', 'Service_')
        return result
    
    # VEMA-Stil: UserPasswordLogin → TransferService
    if 'UserPasswordLogin' in result:
        result = result.replace('UserPasswordLogin', 'TransferService')
        return result
    if 'X509Login' in result:
        result = result.replace('X509Login', 'TransferService')
        return result
    if 'VDGTicketLogin' in result:
        result = result.replace('VDGTicketLogin', 'TransferService')
        return result
    
    # Generische Muster
    if '/STS/' in result:
        result = result.replace('/STS/', '/Transfer/')
    elif '/sts/' in result:
        result = result.replace('/sts/', '/transfer/')
    
    # SecurityTokenService → TransferService
    if 'SecurityTokenService' in result:
        result = result.replace('SecurityTokenService', 'TransferService')
    
    return result


@dataclass
class VUConnection:
    """VU-Verbindung mit erweiterten BiPRO-Feldern."""
    id: int
    vu_name: str
    vu_number: Optional[str]
    endpoint_url: str              # Legacy-Feld (Kompatibilität)
    auth_type: str
    is_active: bool
    last_sync: Optional[str]
    created_at: str
    # Erweiterte Felder
    sts_url: str = ""              # BiPRO 410 STS-Endpunkt
    transfer_url: str = ""         # BiPRO 430 Transfer-Endpunkt
    extranet_url: str = ""         # BiPRO 440 Extranet-Endpunkt
    bipro_version: str = "2.6.1.1.0"
    auth_type_code: int = 0        # 0=Passwort, 3=WS-Cert, 4=TGIC, 6=Degenia
    certificate_id: Optional[str] = None
    note: Optional[str] = None
    # SmartAdmin-Felder
    use_smartadmin_flow: bool = False  # SmartAdmin-Auth-Flow verwenden
    smartadmin_company_key: Optional[str] = None  # Schlüssel aus SMARTADMIN_COMPANIES
    # Consumer-ID / Applikationskennung (z.B. für VEMA)
    consumer_id: Optional[str] = None
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'VUConnection':
        return cls(
            id=data['id'],
            vu_name=data['vu_name'],
            vu_number=data.get('vu_number'),
            endpoint_url=data.get('endpoint_url', ''),
            auth_type=data.get('auth_type', 'wsse'),
            is_active=bool(data.get('is_active', True)),
            last_sync=data.get('last_sync'),
            created_at=data.get('created_at', ''),
            # Erweiterte Felder
            sts_url=data.get('sts_url') or '',
            transfer_url=data.get('transfer_url') or '',
            extranet_url=data.get('extranet_url') or '',
            bipro_version=data.get('bipro_version') or '2.6.1.1.0',
            auth_type_code=int(data.get('auth_type_code') or 0),
            certificate_id=data.get('certificate_id'),
            note=data.get('note'),
            # SmartAdmin-Felder
            use_smartadmin_flow=bool(data.get('use_smartadmin_flow', False)),
            smartadmin_company_key=data.get('smartadmin_company_key'),
            # Consumer-ID
            consumer_id=data.get('consumer_id')
        )
    
    def get_effective_sts_url(self) -> str:
        """Gibt die effektive STS-URL zurück (mit Fallback-Logik)."""
        if self.sts_url:
            logger.debug(f"STS-URL direkt: {self.sts_url}")
            return self.sts_url
        # Fallback: Von endpoint_url oder transfer_url ableiten
        derived = derive_sts_url(self.endpoint_url or self.transfer_url)
        logger.debug(f"STS-URL abgeleitet von '{self.endpoint_url or self.transfer_url}': {derived}")
        return derived
    
    def get_effective_transfer_url(self) -> str:
        """Gibt die effektive Transfer-URL zurück (mit Fallback-Logik)."""
        if self.transfer_url:
            logger.debug(f"Transfer-URL direkt: {self.transfer_url}")
            return self.transfer_url
        # Fallback: Von endpoint_url oder sts_url ableiten
        derived = derive_transfer_url(self.endpoint_url or self.sts_url)
        logger.debug(f"Transfer-URL abgeleitet von '{self.endpoint_url or self.sts_url}': {derived}")
        return derived


@dataclass
class VUCredentials:
    """
    VU-Credentials fuer BiPRO-Authentifizierung.
    
    Unterstuetzt drei Modi:
    1. Username/Password (vom Server)
    2. PFX-Zertifikat (lokal)
    3. JKS-Zertifikat (lokal, Java KeyStore)
    """
    username: str
    password: str
    # PFX-Zertifikat (lokal gespeichert)
    pfx_path: str = ""
    pfx_password: str = ""
    # JKS-Zertifikat (lokal gespeichert)
    jks_path: str = ""
    jks_password: str = ""
    jks_alias: str = ""
    jks_key_password: str = ""
    
    @property
    def uses_certificate(self) -> bool:
        """Prueft ob Zertifikats-Auth verwendet wird."""
        return bool(self.pfx_path) or bool(self.jks_path)
    
    @property
    def auth_method(self) -> str:
        """Gibt die Auth-Methode zurueck."""
        if self.pfx_path:
            return "certificate_pfx"
        elif self.jks_path:
            return "certificate_jks"
        return "password"


class VUConnectionsAPI:
    """
    API für VU-Verbindungsverwaltung.
    
    Verwendung:
        vu_api = VUConnectionsAPI(client)
        connections = vu_api.list_connections()
        creds = vu_api.get_credentials(connection_id)
    """
    
    def __init__(self, client: APIClient):
        self.client = client
    
    def list_connections(self) -> List[VUConnection]:
        """
        Alle VU-Verbindungen abrufen.
        
        Returns:
            Liste von VUConnection
        """
        try:
            response = self.client.get('/vu-connections')
            if response.get('success'):
                return [VUConnection.from_dict(c) for c in response['data']['connections']]
        except APIError as e:
            logger.error(f"VU-Verbindungen laden fehlgeschlagen: {e}")
        return []
    
    def get_connection(self, connection_id: int) -> Optional[VUConnection]:
        """
        Einzelne VU-Verbindung abrufen.
        
        Args:
            connection_id: Verbindungs-ID
            
        Returns:
            VUConnection oder None
        """
        try:
            response = self.client.get(f'/vu-connections/{connection_id}')
            if response.get('success'):
                return VUConnection.from_dict(response['data']['connection'])
        except APIError as e:
            logger.error(f"VU-Verbindung laden fehlgeschlagen: {e}")
        return None
    
    def create_connection(
        self, 
        vu_name: str, 
        endpoint_url: str = "",
        username: str = "",
        password: str = "",
        vu_number: str = None,
        auth_type: str = 'wsse',
        # Erweiterte Felder
        sts_url: str = "",
        transfer_url: str = "",
        extranet_url: str = "",
        bipro_version: str = "2.6.1.1.0",
        auth_type_code: int = 0,
        certificate_id: str = None,
        note: str = None,
        # SmartAdmin-Felder
        use_smartadmin_flow: bool = False,
        smartadmin_company_key: str = None,
        # Consumer-ID (Applikationskennung)
        consumer_id: str = None
    ) -> Optional[int]:
        """
        Neue VU-Verbindung erstellen.
        
        Args:
            vu_name: Name des Versicherers
            endpoint_url: Legacy BiPRO-Endpoint (Kompatibilität)
            username: Benutzername (für Password-Auth)
            password: Passwort (für Password-Auth)
            vu_number: VU-Nummer (optional)
            auth_type: Auth-Typ String ('basic', 'wsse', 'certificate')
            sts_url: BiPRO 410 STS-Endpunkt URL
            transfer_url: BiPRO 430 Transfer-Endpunkt URL
            extranet_url: BiPRO 440 Extranet-Endpunkt URL
            bipro_version: BiPRO-Version (z.B. "2.6.1.1.0")
            auth_type_code: Numerischer Auth-Typ (0, 3, 4, 6)
            certificate_id: ID des lokalen Zertifikats
            note: Notiz
            use_smartadmin_flow: SmartAdmin-Auth-Flow verwenden
            smartadmin_company_key: Schlüssel aus SMARTADMIN_COMPANIES
            consumer_id: Consumer-ID / Applikationskennung (z.B. für VEMA)
            
        Returns:
            ID der neuen Verbindung oder None
        """
        try:
            data = {
                'vu_name': vu_name,
                'vu_number': vu_number,
                'endpoint_url': endpoint_url,
                'auth_type': auth_type,
                'sts_url': sts_url,
                'transfer_url': transfer_url,
                'extranet_url': extranet_url,
                'bipro_version': bipro_version,
                'auth_type_code': auth_type_code,
                'certificate_id': certificate_id,
                'note': note,
                'use_smartadmin_flow': 1 if use_smartadmin_flow else 0,
                'smartadmin_company_key': smartadmin_company_key,
                'consumer_id': consumer_id
            }
            
            # Credentials nur hinzufügen wenn vorhanden
            if username or password:
                data['credentials'] = {
                    'username': username,
                    'password': password
                }
            
            response = self.client.post('/vu-connections', json_data=data)
            if response.get('success'):
                return response['data']['id']
        except APIError as e:
            logger.error(f"VU-Verbindung erstellen fehlgeschlagen: {e}")
        return None
    
    def update_connection(self, connection_id: int, **kwargs) -> bool:
        """
        VU-Verbindung aktualisieren.
        
        Args:
            connection_id: Verbindungs-ID
            **kwargs: Zu aktualisierende Felder
            
        Returns:
            True wenn erfolgreich
        """
        try:
            response = self.client.put(f'/vu-connections/{connection_id}', json_data=kwargs)
            return response.get('success', False)
        except APIError as e:
            logger.error(f"VU-Verbindung aktualisieren fehlgeschlagen: {e}")
        return False
    
    def delete_connection(self, connection_id: int) -> bool:
        """
        VU-Verbindung löschen.
        
        Args:
            connection_id: Verbindungs-ID
            
        Returns:
            True wenn erfolgreich
        """
        try:
            response = self.client.delete(f'/vu-connections/{connection_id}')
            return response.get('success', False)
        except APIError as e:
            logger.error(f"VU-Verbindung löschen fehlgeschlagen: {e}")
        return False
    
    def get_credentials(self, connection_id: int) -> Optional[VUCredentials]:
        """
        Credentials für eine Verbindung abrufen.
        
        ACHTUNG: Diese werden entschlüsselt übertragen!
        Nur temporär nutzen, danach aus dem Speicher löschen.
        
        Args:
            connection_id: Verbindungs-ID
            
        Returns:
            VUCredentials oder None
        """
        try:
            response = self.client.get(f'/vu-connections/{connection_id}/credentials')
            
            if not response.get('success'):
                error_msg = response.get('error', 'Unbekannter Fehler')
                logger.error(f"Credentials abrufen fehlgeschlagen: {error_msg}")
                return None
            
            data = response.get('data', {})
            creds = data.get('credentials')
            
            if not creds:
                logger.error("Keine Credentials in der Antwort enthalten")
                return None
            
            username = creds.get('username')
            password = creds.get('password')
            
            if not username or not password:
                logger.error("Username oder Password fehlt in den Credentials")
                return None
            
            return VUCredentials(
                username=username,
                password=password
            )
            
        except APIError as e:
            logger.error(f"Credentials abrufen fehlgeschlagen: {e}")
            return None
        except Exception as e:
            logger.error(f"Unerwarteter Fehler beim Credentials abrufen: {e}")
            return None
