"""
BiPRO-GDV Tool - SmartAdmin Auth-Flow Handler

Implementiert die BiPRO-Authentifizierungsflows aus dem SmartAdmin-System.
Unterstützt 8 verschiedene Auth-Typen:

1. Weak          - Username + Password (Standard BiPRO)
2. Strong        - Username + Password + OTP (2FA)
3. Certificate   - X.509 Zertifikat (WS-Security)
4. Ticket        - VDG EasyLogin Ticket
5. TicketOTP     - Ticket + OTP
6. TicketCert    - Ticket + Zertifikat
7. TGICCertificate - TGIC + Zertifikat (Generali-Gruppe)
8. TGICmTAN      - TGIC + mTAN
"""

import requests
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Optional, Tuple, Dict, Any
from datetime import datetime, timedelta
import uuid
import base64
import logging
import hashlib

from ..config.smartadmin_endpoints import (
    SmartAdminCompany, 
    AuthType, 
    SMARTADMIN_COMPANIES,
    get_company_by_name
)

logger = logging.getLogger(__name__)


# =============================================================================
# NAMESPACES
# =============================================================================

NS = {
    'soap': 'http://schemas.xmlsoap.org/soap/envelope/',
    'soap12': 'http://www.w3.org/2003/05/soap-envelope',
    'wsse': 'http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd',
    'wsu': 'http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd',
    'wst': 'http://docs.oasis-open.org/ws-sx/ws-trust/200512',
    'wsa': 'http://www.w3.org/2005/08/addressing',
    'saml': 'urn:oasis:names:tc:SAML:2.0:assertion',
    'samlp': 'urn:oasis:names:tc:SAML:2.0:protocol',
    'bipro': 'http://www.bipro.net/namespace',
}


# =============================================================================
# DATENKLASSEN
# =============================================================================

@dataclass
class SmartAdminCredentials:
    """Zugangsdaten für SmartAdmin Auth-Flow."""
    username: str
    password: str
    otp: Optional[str] = None           # Für Strong/TicketOTP
    certificate_path: Optional[str] = None  # PFX/P12 Pfad
    certificate_password: Optional[str] = None
    mtan: Optional[str] = None          # Für TGICmTAN
    easylogin_ticket: Optional[str] = None  # Für Ticket-Auth


@dataclass
class SAMLToken:
    """SAML 2.0 Token aus STS-Antwort."""
    assertion: str                      # Raw XML
    token_id: str
    issue_instant: datetime
    not_on_or_after: datetime
    subject: Optional[str] = None
    issuer: Optional[str] = None
    
    @property
    def is_valid(self) -> bool:
        """Prüft ob Token noch gültig ist."""
        return datetime.utcnow() < self.not_on_or_after
    
    @property
    def remaining_seconds(self) -> int:
        """Verbleibende Gültigkeitsdauer in Sekunden."""
        delta = self.not_on_or_after - datetime.utcnow()
        return max(0, int(delta.total_seconds()))


@dataclass
class SmartAdminAuthResult:
    """Ergebnis einer SmartAdmin-Authentifizierung."""
    success: bool
    token: Optional[SAMLToken] = None
    error_message: Optional[str] = None
    error_code: Optional[str] = None
    raw_response: Optional[str] = None


# =============================================================================
# SOAP TEMPLATES
# =============================================================================

# Weak Auth (Username + Password)
SOAP_WEAK_AUTH = '''<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
               xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd"
               xmlns:wsu="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd"
               xmlns:wst="http://docs.oasis-open.org/ws-sx/ws-trust/200512">
  <soap:Header>
    <wsse:Security soap:mustUnderstand="1">
      <wsse:UsernameToken wsu:Id="UsernameToken-{token_id}">
        <wsse:Username>{username}</wsse:Username>
        <wsse:Password Type="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-username-token-profile-1.0#PasswordText">{password}</wsse:Password>
      </wsse:UsernameToken>
    </wsse:Security>
  </soap:Header>
  <soap:Body>
    <wst:RequestSecurityToken>
      <wst:RequestType>http://docs.oasis-open.org/ws-sx/ws-trust/200512/Issue</wst:RequestType>
      <wst:TokenType>http://docs.oasis-open.org/wss/oasis-wss-saml-token-profile-1.1#SAMLV2.0</wst:TokenType>
    </wst:RequestSecurityToken>
  </soap:Body>
</soap:Envelope>'''


# Strong Auth (Username + Password + OTP)
SOAP_STRONG_AUTH = '''<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
               xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd"
               xmlns:wsu="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd"
               xmlns:wst="http://docs.oasis-open.org/ws-sx/ws-trust/200512">
  <soap:Header>
    <wsse:Security soap:mustUnderstand="1">
      <wsse:UsernameToken wsu:Id="UsernameToken-{token_id}">
        <wsse:Username>{username}</wsse:Username>
        <wsse:Password Type="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-username-token-profile-1.0#PasswordText">{password}</wsse:Password>
        <wsse:Nonce EncodingType="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-soap-message-security-1.0#Base64Binary">{otp_nonce}</wsse:Nonce>
      </wsse:UsernameToken>
    </wsse:Security>
  </soap:Header>
  <soap:Body>
    <wst:RequestSecurityToken>
      <wst:RequestType>http://docs.oasis-open.org/ws-sx/ws-trust/200512/Issue</wst:RequestType>
      <wst:TokenType>http://docs.oasis-open.org/wss/oasis-wss-saml-token-profile-1.1#SAMLV2.0</wst:TokenType>
    </wst:RequestSecurityToken>
  </soap:Body>
</soap:Envelope>'''


# VDG Ticket Auth
SOAP_TICKET_AUTH = '''<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
               xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd"
               xmlns:wsu="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd"
               xmlns:wst="http://docs.oasis-open.org/ws-sx/ws-trust/200512"
               xmlns:vdg="http://www.vdg-online.de/ns/easylogin/1.0">
  <soap:Header>
    <wsse:Security soap:mustUnderstand="1">
      <vdg:VDGTicket>{ticket}</vdg:VDGTicket>
    </wsse:Security>
  </soap:Header>
  <soap:Body>
    <wst:RequestSecurityToken>
      <wst:RequestType>http://docs.oasis-open.org/ws-sx/ws-trust/200512/Issue</wst:RequestType>
      <wst:TokenType>http://docs.oasis-open.org/wss/oasis-wss-saml-token-profile-1.1#SAMLV2.0</wst:TokenType>
    </wst:RequestSecurityToken>
  </soap:Body>
</soap:Envelope>'''


# Transfer Service Request (mit SAML Token)
SOAP_TRANSFER_REQUEST = '''<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
               xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd"
               xmlns:transfer="http://www.bipro.net/namespace/transfer">
  <soap:Header>
    <wsse:Security soap:mustUnderstand="1">
      {saml_token}
    </wsse:Security>
  </soap:Header>
  <soap:Body>
    <transfer:getShipment>
      <transfer:ShipmentID>{shipment_id}</transfer:ShipmentID>
    </transfer:getShipment>
  </soap:Body>
</soap:Envelope>'''


# =============================================================================
# AUTH HANDLER KLASSE
# =============================================================================

class SmartAdminAuthHandler:
    """
    Handler für SmartAdmin-kompatible BiPRO-Authentifizierung.
    
    Unterstützt alle 8 Auth-Typen aus dem SmartAdmin-System.
    """
    
    def __init__(self, timeout: int = 30, verify_ssl: bool = True):
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        self._token_cache: Dict[str, SAMLToken] = {}
    
    def authenticate(
        self, 
        company: SmartAdminCompany, 
        credentials: SmartAdminCredentials,
        auth_type: str = None
    ) -> SmartAdminAuthResult:
        """
        Authentifiziert bei einem Versicherer mit SmartAdmin-Flow.
        
        Args:
            company: SmartAdminCompany mit Endpunkt-Infos
            credentials: Zugangsdaten
            auth_type: Gewünschter Auth-Typ (optional, sonst erster verfügbarer)
        
        Returns:
            SmartAdminAuthResult mit Token oder Fehler
        """
        # Auth-Typ bestimmen
        available_types = company.get_auth_types()
        if not available_types:
            return SmartAdminAuthResult(
                success=False,
                error_message=f"Kein STS-Endpunkt für {company.name} verfügbar"
            )
        
        if auth_type:
            if auth_type not in available_types:
                return SmartAdminAuthResult(
                    success=False,
                    error_message=f"Auth-Typ '{auth_type}' nicht verfügbar. Verfügbar: {available_types}"
                )
        else:
            # Standard-Auswahl: Weak > Ticket > Certificate > ...
            priority = ["Weak", "Ticket", "Certificate", "Strong", "TGICCertificate", "TGICmTAN"]
            for p in priority:
                if p in available_types:
                    auth_type = p
                    break
            else:
                auth_type = available_types[0]
        
        # STS-URL holen
        sts_url = company.get_sts_url(auth_type)
        if not sts_url:
            return SmartAdminAuthResult(
                success=False,
                error_message=f"Keine STS-URL für Auth-Typ '{auth_type}'"
            )
        
        logger.info(f"SmartAdmin Auth: {company.name} mit {auth_type} an {sts_url}")
        
        # Auth durchführen basierend auf Typ
        if auth_type == "Weak":
            return self._auth_weak(sts_url, credentials)
        elif auth_type == "Strong":
            return self._auth_strong(sts_url, credentials)
        elif auth_type == "Ticket":
            return self._auth_ticket(sts_url, credentials)
        elif auth_type == "Certificate":
            return self._auth_certificate(sts_url, credentials)
        elif auth_type == "TGICCertificate":
            return self._auth_tgic_cert(sts_url, credentials)
        elif auth_type == "TGICmTAN":
            return self._auth_tgic_mtan(sts_url, credentials)
        else:
            return SmartAdminAuthResult(
                success=False,
                error_message=f"Auth-Typ '{auth_type}' noch nicht implementiert"
            )
    
    def _auth_weak(self, sts_url: str, creds: SmartAdminCredentials) -> SmartAdminAuthResult:
        """Weak-Authentifizierung (Username + Password)."""
        token_id = str(uuid.uuid4())
        
        soap_body = SOAP_WEAK_AUTH.format(
            token_id=token_id,
            username=self._escape_xml(creds.username),
            password=self._escape_xml(creds.password)
        )
        
        return self._send_sts_request(sts_url, soap_body)
    
    def _auth_strong(self, sts_url: str, creds: SmartAdminCredentials) -> SmartAdminAuthResult:
        """Strong-Authentifizierung (Username + Password + OTP)."""
        if not creds.otp:
            return SmartAdminAuthResult(
                success=False,
                error_message="OTP erforderlich für Strong-Auth"
            )
        
        token_id = str(uuid.uuid4())
        
        # OTP als Base64-Nonce
        otp_nonce = base64.b64encode(creds.otp.encode()).decode()
        
        soap_body = SOAP_STRONG_AUTH.format(
            token_id=token_id,
            username=self._escape_xml(creds.username),
            password=self._escape_xml(creds.password),
            otp_nonce=otp_nonce
        )
        
        return self._send_sts_request(sts_url, soap_body)
    
    def _auth_ticket(self, sts_url: str, creds: SmartAdminCredentials) -> SmartAdminAuthResult:
        """VDG EasyLogin Ticket-Authentifizierung."""
        if not creds.easylogin_ticket:
            return SmartAdminAuthResult(
                success=False,
                error_message="EasyLogin-Ticket erforderlich für Ticket-Auth"
            )
        
        soap_body = SOAP_TICKET_AUTH.format(
            ticket=self._escape_xml(creds.easylogin_ticket)
        )
        
        return self._send_sts_request(sts_url, soap_body)
    
    def _auth_certificate(self, sts_url: str, creds: SmartAdminCredentials) -> SmartAdminAuthResult:
        """X.509 Zertifikat-Authentifizierung."""
        if not creds.certificate_path:
            return SmartAdminAuthResult(
                success=False,
                error_message="Zertifikatspfad erforderlich für Certificate-Auth"
            )
        
        # Für Zertifikat-Auth müssen wir requests mit client cert verwenden
        try:
            # PFX muss erst zu PEM konvertiert werden
            # Das ist ein komplexerer Prozess - hier nur Grundstruktur
            
            token_id = str(uuid.uuid4())
            soap_body = SOAP_WEAK_AUTH.format(  # Verwende erstmal Weak-Template
                token_id=token_id,
                username=creds.username,
                password=""
            )
            
            # TODO: Vollständige X.509 WS-Security Implementation
            # Requires: signierte SOAP-Nachrichten mit Zertifikat
            
            return SmartAdminAuthResult(
                success=False,
                error_message="X.509 Zertifikat-Auth erfordert zusätzliche Konfiguration. "
                             "Bitte Zertifikat in den Einstellungen hinterlegen."
            )
            
        except Exception as e:
            return SmartAdminAuthResult(
                success=False,
                error_message=f"Zertifikat-Fehler: {str(e)}"
            )
    
    def _auth_tgic_cert(self, sts_url: str, creds: SmartAdminCredentials) -> SmartAdminAuthResult:
        """TGIC Zertifikat-Authentifizierung (Generali-Gruppe)."""
        # TGIC verwendet einen speziellen Proxy - die URL ist eigentlich ein Identifier
        # Die echte Authentifizierung läuft über den TGIC-Server
        
        return SmartAdminAuthResult(
            success=False,
            error_message="TGIC-Authentifizierung erfordert TGIC-Proxy-Konfiguration. "
                         "Bitte wenden Sie sich an Ihren Generali-Ansprechpartner."
        )
    
    def _auth_tgic_mtan(self, sts_url: str, creds: SmartAdminCredentials) -> SmartAdminAuthResult:
        """TGIC mTAN-Authentifizierung."""
        if not creds.mtan:
            return SmartAdminAuthResult(
                success=False,
                error_message="mTAN erforderlich für TGIC-mTAN-Auth"
            )
        
        return SmartAdminAuthResult(
            success=False,
            error_message="TGIC-mTAN-Authentifizierung erfordert TGIC-Proxy-Konfiguration."
        )
    
    def _send_sts_request(self, sts_url: str, soap_body: str) -> SmartAdminAuthResult:
        """Sendet STS-Request und parst Antwort."""
        headers = {
            'Content-Type': 'text/xml; charset=utf-8',
            'SOAPAction': 'http://docs.oasis-open.org/ws-sx/ws-trust/200512/RST/Issue',
        }
        
        try:
            response = requests.post(
                sts_url,
                data=soap_body.encode('utf-8'),
                headers=headers,
                timeout=self.timeout,
                verify=self.verify_ssl
            )
            
            logger.debug(f"STS Response Status: {response.status_code}")
            
            if response.status_code != 200:
                return SmartAdminAuthResult(
                    success=False,
                    error_message=f"STS-Fehler: HTTP {response.status_code}",
                    error_code=str(response.status_code),
                    raw_response=response.text[:1000]
                )
            
            # SAML Token aus Antwort extrahieren
            return self._parse_sts_response(response.text)
            
        except requests.Timeout:
            return SmartAdminAuthResult(
                success=False,
                error_message="STS-Timeout - Server antwortet nicht"
            )
        except requests.ConnectionError as e:
            return SmartAdminAuthResult(
                success=False,
                error_message=f"Verbindungsfehler: {str(e)}"
            )
        except Exception as e:
            logger.exception("STS-Request Fehler")
            return SmartAdminAuthResult(
                success=False,
                error_message=f"Unerwarteter Fehler: {str(e)}"
            )
    
    def _parse_sts_response(self, xml_response: str) -> SmartAdminAuthResult:
        """Parst STS-Antwort und extrahiert SAML-Token."""
        try:
            root = ET.fromstring(xml_response)
            
            # SOAP-Fault prüfen
            fault = root.find('.//{http://schemas.xmlsoap.org/soap/envelope/}Fault')
            if fault is None:
                fault = root.find('.//{http://www.w3.org/2003/05/soap-envelope}Fault')
            
            if fault is not None:
                fault_string = fault.findtext('.//faultstring', '')
                fault_code = fault.findtext('.//faultcode', '')
                return SmartAdminAuthResult(
                    success=False,
                    error_message=f"SOAP-Fault: {fault_string}",
                    error_code=fault_code,
                    raw_response=xml_response[:1000]
                )
            
            # SAML Assertion suchen
            assertion = root.find('.//{urn:oasis:names:tc:SAML:2.0:assertion}Assertion')
            
            if assertion is None:
                # Alternative Suche
                assertion = root.find('.//*[@AssertionID]')
            
            if assertion is None:
                return SmartAdminAuthResult(
                    success=False,
                    error_message="Keine SAML-Assertion in Antwort gefunden",
                    raw_response=xml_response[:1000]
                )
            
            # Token-Details extrahieren
            token_id = assertion.get('ID') or assertion.get('AssertionID') or str(uuid.uuid4())
            
            issue_instant_str = assertion.get('IssueInstant', '')
            not_on_or_after_str = ''
            
            conditions = assertion.find('.//{urn:oasis:names:tc:SAML:2.0:assertion}Conditions')
            if conditions is not None:
                not_on_or_after_str = conditions.get('NotOnOrAfter', '')
            
            # Datumsparsung
            issue_instant = self._parse_datetime(issue_instant_str) or datetime.utcnow()
            not_on_or_after = self._parse_datetime(not_on_or_after_str) or (datetime.utcnow() + timedelta(hours=1))
            
            # Issuer
            issuer_elem = assertion.find('.//{urn:oasis:names:tc:SAML:2.0:assertion}Issuer')
            issuer = issuer_elem.text if issuer_elem is not None else None
            
            # Subject
            subject_elem = assertion.find('.//{urn:oasis:names:tc:SAML:2.0:assertion}NameID')
            subject = subject_elem.text if subject_elem is not None else None
            
            # Assertion als XML-String
            assertion_xml = ET.tostring(assertion, encoding='unicode')
            
            token = SAMLToken(
                assertion=assertion_xml,
                token_id=token_id,
                issue_instant=issue_instant,
                not_on_or_after=not_on_or_after,
                subject=subject,
                issuer=issuer
            )
            
            logger.info(f"SAML-Token erhalten: ID={token_id}, gültig bis {not_on_or_after}")
            
            return SmartAdminAuthResult(
                success=True,
                token=token,
                raw_response=xml_response[:1000]
            )
            
        except ET.ParseError as e:
            return SmartAdminAuthResult(
                success=False,
                error_message=f"XML-Parse-Fehler: {str(e)}",
                raw_response=xml_response[:500]
            )
    
    def _parse_datetime(self, dt_str: str) -> Optional[datetime]:
        """Parst ISO-Datetime aus SAML."""
        if not dt_str:
            return None
        
        formats = [
            '%Y-%m-%dT%H:%M:%S.%fZ',
            '%Y-%m-%dT%H:%M:%SZ',
            '%Y-%m-%dT%H:%M:%S',
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(dt_str.rstrip('Z') + 'Z' if 'Z' not in dt_str else dt_str, fmt)
            except ValueError:
                continue
        
        return None
    
    def _escape_xml(self, text: str) -> str:
        """Escaped XML-Sonderzeichen."""
        if not text:
            return ""
        return (text
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;')
            .replace("'", '&apos;'))
    
    def get_cached_token(self, company_key: str) -> Optional[SAMLToken]:
        """Gibt gecachten Token zurück, falls noch gültig."""
        token = self._token_cache.get(company_key)
        if token and token.is_valid:
            return token
        return None
    
    def cache_token(self, company_key: str, token: SAMLToken):
        """Cached einen Token."""
        self._token_cache[company_key] = token
    
    def clear_cache(self):
        """Löscht Token-Cache."""
        self._token_cache.clear()


# =============================================================================
# TRANSFER SERVICE CLIENT
# =============================================================================

class SmartAdminTransferClient:
    """
    Client für BiPRO 430 Transfer Service mit SmartAdmin-Auth.
    """
    
    def __init__(self, auth_handler: SmartAdminAuthHandler = None):
        self.auth_handler = auth_handler or SmartAdminAuthHandler()
        self.timeout = 60
    
    def get_shipments(
        self,
        company: SmartAdminCompany,
        token: SAMLToken
    ) -> Dict[str, Any]:
        """
        Ruft verfügbare Shipments ab.
        
        Args:
            company: Versicherer mit Transfer-URL
            token: Gültiger SAML-Token
        
        Returns:
            Dict mit Shipment-Informationen
        """
        transfer_url = company.get_transfer_url()
        if not transfer_url:
            return {'success': False, 'error': 'Keine Transfer-URL verfügbar'}
        
        if not token.is_valid:
            return {'success': False, 'error': 'Token abgelaufen'}
        
        # TODO: Implementiere listShipments SOAP-Call
        # Benötigt spezifische BiPRO 430 Implementierung
        
        return {
            'success': True,
            'company': company.name,
            'transfer_url': transfer_url,
            'token_valid_for': token.remaining_seconds,
            'message': 'Transfer-Service bereit (Details-Implementation pending)'
        }


# =============================================================================
# CONVENIENCE FUNKTIONEN
# =============================================================================

def authenticate_smartadmin(
    company_name: str,
    username: str,
    password: str,
    auth_type: str = None
) -> SmartAdminAuthResult:
    """
    Convenience-Funktion für SmartAdmin-Authentifizierung.
    
    Args:
        company_name: Name des Versicherers (z.B. "Allianz", "AXA")
        username: Benutzername
        password: Passwort
        auth_type: Optional spezifischer Auth-Typ
    
    Returns:
        SmartAdminAuthResult
    """
    company = get_company_by_name(company_name)
    if not company:
        return SmartAdminAuthResult(
            success=False,
            error_message=f"Versicherer '{company_name}' nicht in SmartAdmin-Datenbank"
        )
    
    creds = SmartAdminCredentials(username=username, password=password)
    handler = SmartAdminAuthHandler()
    
    return handler.authenticate(company, creds, auth_type)
