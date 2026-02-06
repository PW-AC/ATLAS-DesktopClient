"""
BiPRO-GDV Tool - BiPRO Connector

Abstraktionsschicht für BiPRO-Verbindungen.
Wählt automatisch zwischen SmartAdmin-Flow und Standard-Flow.

Verwendung:
    connector = BiPROConnector(connection, credentials)
    
    # Je nach Konfiguration wird SmartAdmin oder Standard genutzt
    if connector.authenticate():
        shipments = connector.list_shipments()
        
        for shipment in shipments:
            content = connector.get_shipment(shipment.id)
"""

from typing import List, Optional, Dict, Any
from dataclasses import dataclass
import logging

from api.vu_connections import VUConnection, VUCredentials

logger = logging.getLogger(__name__)


@dataclass
class BiPROShipment:
    """Vereinfachte Shipment-Darstellung für beide Flows."""
    id: str
    category: str
    created_at: str
    is_confirmed: bool = False
    document_count: int = 0
    raw_data: dict = None


class BiPROConnector:
    """
    Einheitlicher Connector für BiPRO-Verbindungen.
    
    Wählt automatisch:
    - SmartAdmin-Flow: Wenn use_smartadmin_flow=True
    - Standard-Flow: Sonst (bisherige Implementierung)
    """
    
    def __init__(
        self, 
        connection: VUConnection, 
        credentials: VUCredentials,
        use_smartadmin: bool = None
    ):
        """
        Initialisiert den Connector.
        
        Args:
            connection: VU-Verbindung mit URLs und Konfiguration
            credentials: Zugangsdaten
            use_smartadmin: Override für SmartAdmin-Nutzung (None = aus connection)
        """
        self.connection = connection
        self.credentials = credentials
        
        # SmartAdmin-Nutzung bestimmen
        if use_smartadmin is not None:
            self._use_smartadmin = use_smartadmin
        else:
            self._use_smartadmin = getattr(connection, 'use_smartadmin_flow', False)
        
        # Interne Clients
        self._smartadmin_handler = None
        self._smartadmin_token = None
        self._standard_client = None
        self._is_authenticated = False
        
        logger.info(
            f"BiPROConnector initialisiert für {connection.vu_name} "
            f"(SmartAdmin: {self._use_smartadmin})"
        )
    
    @property
    def uses_smartadmin(self) -> bool:
        """Gibt an ob SmartAdmin-Flow verwendet wird."""
        return self._use_smartadmin
    
    @property
    def is_authenticated(self) -> bool:
        """Gibt an ob erfolgreich authentifiziert."""
        return self._is_authenticated
    
    def authenticate(self) -> bool:
        """
        Führt die Authentifizierung durch.
        
        Returns:
            True wenn erfolgreich
        """
        if self._use_smartadmin:
            return self._authenticate_smartadmin()
        else:
            return self._authenticate_standard()
    
    def _authenticate_smartadmin(self) -> bool:
        """SmartAdmin-Authentifizierung."""
        try:
            from api.smartadmin_auth import (
                SmartAdminAuthHandler, 
                SmartAdminCredentials,
                SMARTADMIN_COMPANIES
            )
            from config.smartadmin_endpoints import get_company_by_name, SMARTADMIN_COMPANIES
            
            # SmartAdmin-Company finden
            company_key = getattr(self.connection, 'smartadmin_company_key', None)
            company = None
            
            if company_key and company_key in SMARTADMIN_COMPANIES:
                company = SMARTADMIN_COMPANIES[company_key]
            else:
                # Fallback: Nach Namen suchen
                company = get_company_by_name(self.connection.vu_name)
            
            if not company:
                logger.error(f"SmartAdmin-Company nicht gefunden: {self.connection.vu_name}")
                return False
            
            # Handler erstellen
            self._smartadmin_handler = SmartAdminAuthHandler()
            
            # Credentials aufbauen
            sa_creds = SmartAdminCredentials(
                username=self.credentials.username,
                password=self.credentials.password,
                certificate_path=getattr(self.credentials, 'pfx_path', None),
                certificate_password=getattr(self.credentials, 'pfx_password', None)
            )
            
            # Authentifizieren
            result = self._smartadmin_handler.authenticate(company, sa_creds)
            
            if result.success and result.token:
                self._smartadmin_token = result.token
                self._is_authenticated = True
                logger.info(f"SmartAdmin-Auth erfolgreich für {company.name}")
                return True
            else:
                logger.error(f"SmartAdmin-Auth fehlgeschlagen: {result.error_message}")
                return False
                
        except ImportError as e:
            logger.error(f"SmartAdmin-Module nicht verfügbar: {e}")
            return False
        except Exception as e:
            logger.exception(f"SmartAdmin-Auth Fehler: {e}")
            return False
    
    def _authenticate_standard(self) -> bool:
        """Standard-Authentifizierung (bisherige Implementierung)."""
        try:
            from bipro.transfer_service import TransferServiceClient, BiPROCredentials
            
            # Effektive URLs
            sts_url = self.connection.get_effective_sts_url()
            transfer_url = self.connection.get_effective_transfer_url()
            
            bipro_creds = BiPROCredentials(
                username=self.credentials.username,
                password=self.credentials.password,
                endpoint_url=transfer_url,
                sts_endpoint_url=sts_url,
                vu_name=self.connection.vu_name,
                vu_number=self.connection.vu_number or "",
                pfx_path=getattr(self.credentials, 'pfx_path', ''),
                pfx_password=getattr(self.credentials, 'pfx_password', ''),
                jks_path=getattr(self.credentials, 'jks_path', ''),
                jks_password=getattr(self.credentials, 'jks_password', ''),
                jks_alias=getattr(self.credentials, 'jks_alias', ''),
                jks_key_password=getattr(self.credentials, 'jks_key_password', '')
            )
            
            self._standard_client = TransferServiceClient(bipro_creds)
            self._is_authenticated = True
            logger.info(f"Standard-Auth initialisiert für {self.connection.vu_name}")
            return True
            
        except Exception as e:
            logger.exception(f"Standard-Auth Fehler: {e}")
            return False
    
    def list_shipments(self, confirmed: bool = True) -> List[BiPROShipment]:
        """
        Listet verfügbare Lieferungen auf.
        
        Args:
            confirmed: Nur bestätigte Lieferungen
            
        Returns:
            Liste von BiPROShipment
        """
        if not self._is_authenticated:
            logger.error("Nicht authentifiziert - erst authenticate() aufrufen")
            return []
        
        if self._use_smartadmin:
            return self._list_shipments_smartadmin()
        else:
            return self._list_shipments_standard(confirmed)
    
    def _list_shipments_smartadmin(self) -> List[BiPROShipment]:
        """Shipments mit SmartAdmin-Token abrufen."""
        # TODO: SmartAdmin Transfer-Service implementieren
        # Aktuell Fallback auf Standard
        logger.warning("SmartAdmin-Transfer noch nicht vollständig implementiert - nutze Standard")
        
        if self._smartadmin_token:
            # Hier könnte der SmartAdmin-Transfer-Client genutzt werden
            pass
        
        return []
    
    def _list_shipments_standard(self, confirmed: bool) -> List[BiPROShipment]:
        """Shipments mit Standard-Client abrufen."""
        try:
            if not self._standard_client:
                return []
            
            shipments = self._standard_client.list_shipments(confirmed=confirmed)
            
            # Konvertieren zu BiPROShipment
            result = []
            for s in shipments:
                result.append(BiPROShipment(
                    id=s.id,
                    category=s.category,
                    created_at=s.created_at,
                    is_confirmed=s.is_confirmed,
                    document_count=s.document_count,
                    raw_data={'original': s}
                ))
            return result
            
        except Exception as e:
            logger.exception(f"Shipments abrufen fehlgeschlagen: {e}")
            return []
    
    def get_shipment(self, shipment_id: str) -> Optional[Dict[str, Any]]:
        """
        Ruft eine einzelne Lieferung ab.
        
        Args:
            shipment_id: Lieferungs-ID
            
        Returns:
            Dict mit Lieferungsinhalt oder None
        """
        if not self._is_authenticated:
            logger.error("Nicht authentifiziert")
            return None
        
        if self._use_smartadmin:
            return self._get_shipment_smartadmin(shipment_id)
        else:
            return self._get_shipment_standard(shipment_id)
    
    def _get_shipment_smartadmin(self, shipment_id: str) -> Optional[Dict[str, Any]]:
        """Shipment mit SmartAdmin abrufen."""
        logger.warning("SmartAdmin-Transfer noch nicht implementiert")
        return None
    
    def _get_shipment_standard(self, shipment_id: str) -> Optional[Dict[str, Any]]:
        """Shipment mit Standard-Client abrufen."""
        try:
            if not self._standard_client:
                return None
            
            content = self._standard_client.get_shipment(shipment_id)
            return content
            
        except Exception as e:
            logger.exception(f"Shipment abrufen fehlgeschlagen: {e}")
            return None
    
    def acknowledge_shipment(self, shipment_id: str) -> bool:
        """
        Quittiert eine Lieferung.
        
        Args:
            shipment_id: Lieferungs-ID
            
        Returns:
            True wenn erfolgreich
        """
        if not self._is_authenticated:
            return False
        
        if self._use_smartadmin:
            logger.warning("SmartAdmin-Acknowledge noch nicht implementiert")
            return False
        else:
            try:
                if self._standard_client:
                    return self._standard_client.acknowledge_shipment(shipment_id)
            except Exception as e:
                logger.exception(f"Acknowledge fehlgeschlagen: {e}")
            return False
    
    def close(self):
        """Schließt alle Verbindungen."""
        if self._standard_client:
            try:
                self._standard_client.__exit__(None, None, None)
            except Exception:
                pass
            self._standard_client = None
        
        if self._smartadmin_handler:
            try:
                self._smartadmin_handler.clear_cache()
            except Exception:
                pass
            self._smartadmin_handler = None
        
        self._is_authenticated = False
    
    def __enter__(self):
        """Context Manager Enter."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context Manager Exit."""
        self.close()
        return False


# =============================================================================
# HELPER FUNKTIONEN
# =============================================================================

def create_connector(
    connection: VUConnection, 
    credentials: VUCredentials
) -> BiPROConnector:
    """
    Factory-Funktion für BiPROConnector.
    
    Args:
        connection: VU-Verbindung
        credentials: Zugangsdaten
        
    Returns:
        Konfigurierter BiPROConnector
    """
    return BiPROConnector(connection, credentials)


def test_connection(
    connection: VUConnection, 
    credentials: VUCredentials
) -> Dict[str, Any]:
    """
    Testet eine VU-Verbindung.
    
    Args:
        connection: VU-Verbindung
        credentials: Zugangsdaten
        
    Returns:
        Dict mit Testergebnis
    """
    result = {
        'success': False,
        'vu_name': connection.vu_name,
        'auth_method': 'SmartAdmin' if connection.use_smartadmin_flow else 'Standard',
        'error': None,
        'details': {}
    }
    
    try:
        with BiPROConnector(connection, credentials) as connector:
            if connector.authenticate():
                result['success'] = True
                result['details']['authenticated'] = True
                
                # Versuche Shipments zu listen
                try:
                    shipments = connector.list_shipments(confirmed=True)
                    result['details']['shipment_count'] = len(shipments)
                except Exception as e:
                    result['details']['shipment_error'] = str(e)
            else:
                result['error'] = 'Authentifizierung fehlgeschlagen'
                
    except Exception as e:
        result['error'] = str(e)
    
    return result
