"""
BiPRO 430 Transfer Service Client

Implementiert die BiPRO 430 Norm für den Datentransfer.
Operationen:
- listShipments: Bereitstehende Lieferungen auflisten
- getShipment: Lieferung abrufen
- acknowledgeShipment: Empfang quittieren

================================================================================
WICHTIG: VU-SPEZIFISCHES VERHALTEN
================================================================================

JEDE Versicherungsgesellschaft (VU) kann EIGENE Anforderungen an:
- Authentifizierung (STS-Format, SOAPAction-Header, etc.)
- Request-Formate (Pflichtfelder, Namespace-Präfixe, etc.)
- Response-Formate (XML-Struktur, Namespace-Präfixe, etc.)

DESIGN-PRINZIP:
---------------
Änderungen für eine VU (z.B. Allianz) dürfen NIEMALS das Verhalten 
für andere VUs (z.B. AXA, Degenia, VEMA) beeinflussen!

ARCHITEKTUR:
------------
Der Code verwendet VU-Erkennung (_detect_vema(), etc.) und bedingte Logik,
um für jede VU das korrekte Format zu verwenden:

    if self._is_vema:
        # VEMA-spezifisches Format
    else:
        # Standard BiPRO / andere VUs

BEKANNTE VU-UNTERSCHIEDE:
-------------------------

| VU       | SOAPAction | STS-Format      | BestaetigeLieferungen | Consumer-ID |
|----------|------------|-----------------|------------------------|-------------|
| Degenia  | Leer ("")  | Standard BiPRO  | ERFORDERLICH (true)   | Nicht nötig |
| VEMA     | Leer ("")  | VEMA-spezifisch | NICHT SENDEN          | ERFORDERLICH|
| (andere) | Je nach VU | Je nach VU      | Je nach VU            | Je nach VU  |

HINZUFÜGEN NEUER VUs:
---------------------
1. VU-Erkennung hinzufügen (z.B. _detect_allianz())
2. VU-spezifische Logik in _get_sts_token(), list_shipments(), etc.
3. NIEMALS bestehende VU-Logik ändern, NUR NEUE Bedingungen hinzufügen
4. Dokumentation in BIPRO_ENDPOINTS.md aktualisieren
5. Tests für die neue VU hinzufügen

Siehe auch: docs/BIPRO_ENDPOINTS.md für VU-spezifische Dokumentation
================================================================================
"""

from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import logging
import base64
import os
import re
import threading

try:
    import requests
except ImportError:
    raise ImportError("requests-Bibliothek nicht installiert. Bitte: pip install requests")

logger = logging.getLogger(__name__)

# Proxy komplett deaktivieren (auch Windows System-Proxy)
for proxy_var in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy', 'NO_PROXY', 'no_proxy']:
    os.environ.pop(proxy_var, None)
os.environ['NO_PROXY'] = '*'
os.environ['no_proxy'] = '*'


@dataclass
class BiPROCredentials:
    """
    BiPRO-Zugangsdaten.
    
    Unterstützt drei Authentifizierungsmethoden:
    1. Username/Password + STS-Token (z.B. Degenia, VEMA)
    2. PFX-Zertifikat (z.B. easy Login) - empfohlen
    3. PEM-Zertifikat + Key (alternativ)
    """
    username: str
    password: str
    endpoint_url: str
    vu_name: str = ""
    vu_number: str = ""
    sts_endpoint_url: str = ""  # Optional: STS-Endpoint für Token
    consumer_id: str = ""       # Applikationskennung (z.B. für VEMA)
    
    # easy Login / X.509-Zertifikat Authentifizierung
    # Option 1: PFX-Datei (enthält Zertifikat + Key)
    pfx_path: str = ""        # Pfad zur PFX-Datei (.pfx oder .p12)
    pfx_password: str = ""    # Passwort für die PFX-Datei
    
    # Option 2: JKS-Datei (Java KeyStore)
    jks_path: str = ""        # Pfad zur JKS-Datei (.jks)
    jks_password: str = ""    # Passwort für den KeyStore
    jks_alias: str = ""       # Alias des Zertifikats im KeyStore
    jks_key_password: str = ""  # Passwort für den Key (oft gleich wie KeyStore)
    
    # Option 3: Separate PEM-Dateien
    cert_path: str = ""       # Pfad zum Zertifikat (.pem)
    key_path: str = ""        # Pfad zum Private Key (.pem)
    key_password: str = ""    # Optional: Passwort für den Key
    
    @property
    def uses_certificate(self) -> bool:
        """Prüft ob Zertifikats-Auth verwendet wird."""
        return bool(self.pfx_path) or bool(self.jks_path) or bool(self.cert_path and self.key_path)
    
    @property
    def uses_pfx(self) -> bool:
        """Prüft ob PFX-Zertifikat verwendet wird."""
        return bool(self.pfx_path)
    
    @property
    def uses_jks(self) -> bool:
        """Prüft ob JKS-Zertifikat verwendet wird."""
        return bool(self.jks_path)
    
    @property
    def auth_method(self) -> str:
        """Gibt die verwendete Authentifizierungsmethode zurück."""
        if self.uses_pfx:
            return "X.509-Zertifikat PFX (easy Login)"
        elif self.uses_jks:
            return "X.509-Zertifikat JKS (Java KeyStore)"
        elif self.cert_path and self.key_path:
            return "X.509-Zertifikat PEM"
        elif self.sts_endpoint_url or '410_STS' in self.endpoint_url.replace('430', '410'):
            return "STS-Token"
        else:
            return "UsernameToken"


@dataclass
@dataclass
class ShipmentInfo:
    """Informationen über eine bereitstehende Lieferung."""
    shipment_id: str
    created_at: Optional[str] = None
    category: Optional[str] = None
    available_until: Optional[str] = None
    transfer_count: int = 1
    contains_only_data: bool = False
    status: str = 'listed'
    
    @classmethod
    def from_xml(cls, xml_text: str) -> List['ShipmentInfo']:
        """Extrahiert ShipmentInfo-Liste aus XML-Response."""
        shipments = []
        
        # Alle Lieferung-Blöcke finden (verschiedene Namespace-Prefixe: tran:, t:, oder ohne)
        pattern = r'<(?:tran:|t:)?Lieferung[^>]*>(.*?)</(?:tran:|t:)?Lieferung>'
        matches = re.findall(pattern, xml_text, re.DOTALL)
        
        logger.debug(f"Gefundene Lieferungen: {len(matches)}")
        
        for match in matches:
            def extract(tag):
                # Verschiedene Namespace-Prefixe unterstützen
                m = re.search(f'<(?:tran:|t:)?{tag}>([^<]*)</(?:tran:|t:)?{tag}>', match)
                return m.group(1) if m else None
            
            shipment_id = extract('ID') or ''
            if shipment_id:
                logger.debug(f"Lieferung gefunden: ID={shipment_id}")
                shipments.append(cls(
                    shipment_id=shipment_id,
                    created_at=extract('Einstellzeitpunkt'),
                    category=extract('Kategorie'),
                    available_until=extract('VerfuegbarBis'),
                    transfer_count=int(extract('AnzahlTransfers') or 1),
                    contains_only_data=(extract('EnthaeltNurDaten') == 'true'),
                    status='listed'
                ))
        
        return shipments


@dataclass
class ShipmentContent:
    """Inhalt einer abgerufenen Lieferung."""
    shipment_id: str
    documents: List[Dict]  # Liste von {filename, content_base64, mime_type}
    metadata: Dict
    raw_xml: str


class TransferServiceClient:
    """
    BiPRO 430 Transfer Service Client.
    
    Verwendet den korrekten BiPRO-Flow:
    1. STS-Token holen (BiPRO 410)
    2. Mit Token Transfer-Service aufrufen (BiPRO 430)
    
    Verwendung:
        credentials = BiPROCredentials(
            username="user",
            password="pass",
            endpoint_url="https://..."
        )
        client = TransferServiceClient(credentials)
        
        # Lieferungen auflisten
        shipments = client.list_shipments()
        
        # Lieferung abrufen
        content = client.get_shipment(shipment_id)
    """
    
    # Bekannte Endpoints
    KNOWN_ENDPOINTS = {
        'degenia': {
            'transfer': 'https://transfer.degenia.de/X4/httpstarter/ReST/BiPRO/430_Transfer/Service_2.6.1.1.0',
            'sts': 'https://transfer.degenia.de/X4/httpstarter/ReST/BiPRO/410_STS/UserPasswordLogin_2.6.1.1.0'
        },
        'biprohub': {
            'transfer': 'https://www.biprohub.eu/soap/TransferService',
            'auth': 'certificate',  # easyLogin (X.509 Zertifikat)
            'description': 'BiPROHub - Zentraler Hub fuer mehrere VUs (z.B. Allianz)'
        }
    }
    
    def __init__(self, credentials: BiPROCredentials):
        self.credentials = credentials
        self._token: Optional[str] = None
        self._token_expires: Optional[datetime] = None
        self._uses_certificate = credentials.uses_certificate
        
        # STS-Endpoint ableiten falls nicht angegeben (nur für Username/Password)
        if not credentials.uses_certificate:
            if not credentials.sts_endpoint_url:
                # Aus Transfer-URL den STS-URL ableiten
                if '430_Transfer' in credentials.endpoint_url:
                    self.sts_url = credentials.endpoint_url.replace(
                        '430_Transfer/Service',
                        '410_STS/UserPasswordLogin'
                    )
                else:
                    self.sts_url = self.KNOWN_ENDPOINTS['degenia']['sts']
            else:
                self.sts_url = credentials.sts_endpoint_url
        else:
            self.sts_url = None  # Kein STS bei Zertifikats-Auth
        
        self.transfer_url = credentials.endpoint_url
        
        # VU-spezifische Einstellungen erkennen
        self._is_vema = self._detect_vema()
        if self._is_vema:
            logger.info("VEMA-Modus erkannt - verwende VEMA-spezifisches Format")
        
        # Session für alle Requests
        self.session = requests.Session()
        self.session.verify = True
        self.session.trust_env = False
        self.session.proxies = {'http': '', 'https': ''}
        
        # Temporäre PEM-Dateien (für PFX-Konvertierung)
        self._temp_cert_file = None
        self._temp_key_file = None
        
        # X.509-Zertifikat konfigurieren (easy Login)
        if credentials.uses_certificate:
            if credentials.uses_pfx:
                # PFX-Datei zu PEM konvertieren
                self._setup_pfx_certificate(credentials.pfx_path, credentials.pfx_password)
            elif credentials.uses_jks:
                # JKS-Datei zu PEM konvertieren
                self._setup_jks_certificate(
                    credentials.jks_path, 
                    credentials.jks_password,
                    credentials.jks_alias,
                    credentials.jks_key_password or credentials.jks_password
                )
            else:
                # PEM-Dateien direkt verwenden
                logger.info(f"Verwende PEM-Zertifikat: {credentials.cert_path}")
                self.session.cert = (credentials.cert_path, credentials.key_path)
        
        logger.info(f"Auth-Methode: {credentials.auth_method}")
    
    def _setup_pfx_certificate(self, pfx_path: str, pfx_password: str):
        """
        Konvertiert PFX-Zertifikat zu temporären PEM-Dateien für requests.
        
        Args:
            pfx_path: Pfad zur PFX-Datei
            pfx_password: Passwort für die PFX-Datei
        """
        import tempfile
        
        try:
            from cryptography.hazmat.primitives.serialization import pkcs12, Encoding, PrivateFormat, NoEncryption
            from cryptography.hazmat.backends import default_backend
        except ImportError:
            raise ImportError(
                "cryptography-Bibliothek nicht installiert.\n"
                "Bitte installieren: pip install cryptography"
            )
        
        logger.info(f"Lade PFX-Zertifikat: {pfx_path}")
        
        # Pruefen ob Datei existiert
        if not os.path.exists(pfx_path):
            raise Exception(f"PFX-Datei nicht gefunden: {pfx_path}")
        
        # PFX-Datei laden
        try:
            with open(pfx_path, 'rb') as f:
                pfx_data = f.read()
            logger.info(f"PFX-Datei gelesen: {len(pfx_data)} Bytes")
        except Exception as e:
            raise Exception(f"PFX-Datei konnte nicht gelesen werden: {e}")
        
        # PFX entschlüsseln
        password_bytes = pfx_password.encode('utf-8') if pfx_password else None
        logger.info(f"PFX-Passwort: {'gesetzt' if password_bytes else 'leer'}")
        
        try:
            private_key, certificate, additional_certs = pkcs12.load_key_and_certificates(
                pfx_data, 
                password_bytes, 
                default_backend()
            )
            logger.info(f"PFX entschluesselt: Key={private_key is not None}, Cert={certificate is not None}, Chain={len(additional_certs) if additional_certs else 0}")
        except Exception as e:
            logger.error(f"PFX-Entschluesselung fehlgeschlagen: {e}")
            raise Exception(f"PFX-Datei konnte nicht entschluesselt werden.\nMoegliche Ursache: Falsches Passwort.\n\nDetails: {e}")
        
        if not private_key or not certificate:
            raise Exception("PFX-Datei enthält kein gueltiges Zertifikat oder keinen Private Key")
        
        # Temporäre PEM-Dateien erstellen
        self._temp_cert_file = tempfile.NamedTemporaryFile(
            mode='wb', suffix='.pem', delete=False, prefix='bipro_cert_'
        )
        self._temp_key_file = tempfile.NamedTemporaryFile(
            mode='wb', suffix='.pem', delete=False, prefix='bipro_key_'
        )
        
        # Zertifikat als PEM schreiben
        cert_pem = certificate.public_bytes(Encoding.PEM)
        self._temp_cert_file.write(cert_pem)
        
        # Zusätzliche Zertifikate (CA-Chain) anhängen falls vorhanden
        if additional_certs:
            for cert in additional_certs:
                self._temp_cert_file.write(cert.public_bytes(Encoding.PEM))
        
        self._temp_cert_file.close()
        
        # Private Key als PEM schreiben (unverschlüsselt)
        key_pem = private_key.private_bytes(
            Encoding.PEM,
            PrivateFormat.TraditionalOpenSSL,
            NoEncryption()
        )
        self._temp_key_file.write(key_pem)
        self._temp_key_file.close()
        
        # Session mit Zertifikat konfigurieren
        self.session.cert = (self._temp_cert_file.name, self._temp_key_file.name)
        
        logger.info(f"PFX-Zertifikat erfolgreich geladen")
    
    def _setup_jks_certificate(self, jks_path: str, jks_password: str, 
                                alias: str = "", key_password: str = ""):
        """
        Konvertiert JKS-Zertifikat (Java KeyStore) zu temporaeren PEM-Dateien.
        
        Args:
            jks_path: Pfad zur JKS-Datei
            jks_password: Passwort fuer den KeyStore
            alias: Alias des Zertifikats (optional, nimmt erstes wenn leer)
            key_password: Passwort fuer den Key (optional, nutzt jks_password)
        """
        import tempfile
        
        try:
            import jks
        except ImportError:
            raise ImportError(
                "pyjks-Bibliothek nicht installiert.\n"
                "Bitte installieren: pip install pyjks"
            )
        
        logger.info(f"Lade JKS-Zertifikat: {jks_path}")
        
        # Pruefen ob Datei existiert
        if not os.path.exists(jks_path):
            raise Exception(f"JKS-Datei nicht gefunden: {jks_path}")
        
        # JKS laden
        try:
            keystore = jks.KeyStore.load(jks_path, jks_password)
            logger.info(f"JKS geladen: {len(keystore.private_keys)} Private Keys, {len(keystore.certs)} Zertifikate")
        except Exception as e:
            logger.error(f"JKS konnte nicht geladen werden: {e}")
            raise Exception(f"JKS-Datei konnte nicht geladen werden.\nMoegliche Ursache: Falsches Passwort.\n\nDetails: {e}")
        
        # Alias finden
        if alias:
            if alias not in keystore.private_keys:
                available = list(keystore.private_keys.keys())
                raise Exception(f"Alias '{alias}' nicht gefunden. Verfuegbar: {available}")
            pk_entry = keystore.private_keys[alias]
        else:
            # Ersten Private Key nehmen
            if not keystore.private_keys:
                raise Exception("Keine Private Keys im KeyStore gefunden")
            alias = list(keystore.private_keys.keys())[0]
            pk_entry = keystore.private_keys[alias]
            logger.info(f"Verwende Alias: {alias}")
        
        # Key-Passwort verwenden falls angegeben
        actual_key_password = key_password or jks_password
        
        # Private Key entschluesseln falls noetig
        if pk_entry.is_decrypted():
            private_key_der = pk_entry.pkey
        else:
            try:
                pk_entry.decrypt(actual_key_password)
                private_key_der = pk_entry.pkey
            except Exception as e:
                raise Exception(f"Private Key konnte nicht entschluesselt werden: {e}")
        
        # Zertifikate aus der Kette
        cert_chain_der = pk_entry.cert_chain
        
        if not cert_chain_der:
            raise Exception("Keine Zertifikate im Private Key Entry gefunden")
        
        # DER zu PEM konvertieren
        from cryptography.hazmat.primitives.serialization import (
            Encoding, PrivateFormat, NoEncryption, load_der_private_key
        )
        from cryptography import x509
        from cryptography.hazmat.backends import default_backend
        
        # Private Key laden und zu PEM konvertieren
        try:
            private_key = load_der_private_key(private_key_der, password=None, backend=default_backend())
        except Exception as e:
            raise Exception(f"Private Key konnte nicht geladen werden: {e}")
        
        # Temporaere PEM-Dateien erstellen
        self._temp_cert_file = tempfile.NamedTemporaryFile(
            mode='wb', suffix='.pem', delete=False, prefix='bipro_jks_cert_'
        )
        self._temp_key_file = tempfile.NamedTemporaryFile(
            mode='wb', suffix='.pem', delete=False, prefix='bipro_jks_key_'
        )
        
        # Zertifikate als PEM schreiben
        for cert_tuple in cert_chain_der:
            cert_type, cert_der = cert_tuple
            cert = x509.load_der_x509_certificate(cert_der, default_backend())
            self._temp_cert_file.write(cert.public_bytes(Encoding.PEM))
        
        self._temp_cert_file.close()
        
        # Private Key als PEM schreiben
        key_pem = private_key.private_bytes(
            Encoding.PEM,
            PrivateFormat.TraditionalOpenSSL,
            NoEncryption()
        )
        self._temp_key_file.write(key_pem)
        self._temp_key_file.close()
        
        # Session konfigurieren
        self.session.cert = (self._temp_cert_file.name, self._temp_key_file.name)
        
        logger.info(f"JKS-Zertifikat erfolgreich geladen (Alias: {alias})")
    
    # ==========================================================================
    # VU-ERKENNUNG
    # ==========================================================================
    # Jede VU kann eigene Erkennungsmethoden haben.
    # WICHTIG: Neue VU hinzufügen = NEUE Methode erstellen, NICHT bestehende ändern!
    #
    # Beispiel für neue VU:
    #   def _detect_allianz(self) -> bool:
    #       return 'allianz' in self.credentials.vu_name.lower()
    # ==========================================================================
    
    def _detect_vema(self) -> bool:
        """
        Erkennt ob es sich um eine VEMA-Verbindung handelt.
        
        VEMA benötigt spezielle Behandlung:
        - Anderes STS-Request-Format (wsa:Action Header)
        - Leerer SOAPAction-Header
        - Consumer-ID ERFORDERLICH
        - KEIN BestaetigeLieferungen Element
        """
        # Prüfe VU-Name
        if self.credentials.vu_name:
            vu_lower = self.credentials.vu_name.lower()
            if 'vema' in vu_lower:
                return True
        
        # Prüfe URL
        urls_to_check = [
            self.credentials.endpoint_url,
            self.credentials.sts_endpoint_url,
            self.transfer_url,
            self.sts_url if hasattr(self, 'sts_url') and self.sts_url else ''
        ]
        for url in urls_to_check:
            if url and 'vemaeg.de' in url.lower():
                return True
        
        return False
    
    def _get_soap_action(self, operation: str) -> str:
        """Gibt den korrekten SOAPAction-Header für die Operation zurück."""
        # Leerer SOAPAction-Header funktioniert für VEMA und Degenia
        # (Degenia akzeptiert beide Varianten)
        return '""'
    
    def _escape_xml(self, text: str) -> str:
        """Escaped alle 5 XML-Entities fuer sichere XML-Generierung."""
        return (text
                .replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;')
                .replace('"', '&quot;')
                .replace("'", '&apos;'))
    
    def _get_sts_token(self) -> Optional[str]:
        """
        Holt ein SecurityContextToken vom STS-Service (BiPRO 410).
        
        Returns:
            Token-String oder None bei Fehler
        """
        logger.info(f"Hole STS-Token von: {self.sts_url}")
        
        pw_escaped = self._escape_xml(self.credentials.password)
        
        # Consumer-ID loggen falls vorhanden
        if self.credentials.consumer_id:
            logger.info(f"Consumer-ID: {self.credentials.consumer_id}")
        
        # VU-spezifisches STS-Request-Format
        if self._is_vema:
            # VEMA-Format: wsa:Action Header, mustUnderstand="1", RequestSecurityToken ohne Prefix
            body = f'''<?xml version="1.0" encoding="utf-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                  xmlns:xsd="http://www.w3.org/2001/XMLSchema"
                  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
   <soapenv:Header>
      <wsa:Action soapenv:actor="" soapenv:mustUnderstand="0" xmlns:wsa="http://schemas.xmlsoap.org/ws/2004/08/addressing/">http://schemas.xmlsoap.org/ws/2005/02/trust/RST/SCT</wsa:Action>
      <wsse:Security soapenv:actor="" soapenv:mustUnderstand="1" xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd">
         <wsse:UsernameToken xmlns:bipro="http://www.bipro.net/namespace">
            <wsse:Username>{self.credentials.username}</wsse:Username>
            <wsse:Password Type="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-username-token-profile-1.0#PasswordText">{pw_escaped}</wsse:Password>
         </wsse:UsernameToken>
      </wsse:Security>
   </soapenv:Header>
   <soapenv:Body>
      <RequestSecurityToken xmlns="http://schemas.xmlsoap.org/ws/2005/02/trust">
         <TokenType>http://schemas.xmlsoap.org/ws/2005/02/sc/sct</TokenType>
         <RequestType>http://schemas.xmlsoap.org/ws/2005/02/trust/Issue</RequestType>
      </RequestSecurityToken>
   </soapenv:Body>
</soapenv:Envelope>'''
        else:
            # Standard BiPRO-Format (z.B. Degenia)
            body = f'''<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                  xmlns:wst="http://schemas.xmlsoap.org/ws/2005/02/trust"
                  xmlns:nac="http://www.bipro.net/namespace/nachrichten">
   <soapenv:Header>
      <wsse:Security xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd">
         <wsse:UsernameToken>
            <wsse:Username>{self.credentials.username}</wsse:Username>
            <wsse:Password Type="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-username-token-profile-1.0#PasswordText">{pw_escaped}</wsse:Password>
         </wsse:UsernameToken>
      </wsse:Security>
   </soapenv:Header>
   <soapenv:Body>
      <wst:RequestSecurityToken>
         <wst:TokenType>http://schemas.xmlsoap.org/ws/2005/02/sc/sct</wst:TokenType>
         <wst:RequestType>http://schemas.xmlsoap.org/ws/2005/02/trust/Issue</wst:RequestType>
         <nac:BiPROVersion>2.6.1.1.0</nac:BiPROVersion>
      </wst:RequestSecurityToken>
   </soapenv:Body>
</soapenv:Envelope>'''
        
        # SOAPAction: VU-spezifisch
        headers = {
            'Content-Type': 'text/xml; charset=utf-8',
            'SOAPAction': self._get_soap_action('http://schemas.xmlsoap.org/ws/2005/02/trust/RST/Issue')
        }
        
        try:
            response = self.session.post(
                self.sts_url,
                data=body.encode('utf-8'),
                headers=headers,
                timeout=30
            )
            
            logger.debug(f"STS Response Status: {response.status_code}")
            logger.debug(f"STS Response: {response.text[:500]}")
            
            # Token extrahieren
            match = re.search(r'<wsc:Identifier>([^<]+)</wsc:Identifier>', response.text)
            if match:
                token = match.group(1)
                logger.info(f"STS-Token erhalten: {token[:30]}...")
                
                # Token-Ablaufzeit extrahieren (wsu:Expires oder Lifetime/Expires)
                expires_match = re.search(
                    r'<wsu:Expires>([^<]+)</wsu:Expires>|'
                    r'<Expires>([^<]+)</Expires>|'
                    r'<wst:Lifetime>.*?<wsu:Expires>([^<]+)</wsu:Expires>.*?</wst:Lifetime>',
                    response.text, 
                    re.DOTALL
                )
                if expires_match:
                    expires_str = expires_match.group(1) or expires_match.group(2) or expires_match.group(3)
                    try:
                        # ISO-8601 Format parsen (z.B. 2026-02-03T14:30:00Z)
                        expires_str = expires_str.replace('Z', '+00:00')
                        self._token_expires = datetime.fromisoformat(expires_str)
                        logger.info(f"Token gueltig bis: {self._token_expires}")
                    except ValueError as e:
                        logger.warning(f"Token-Ablaufzeit konnte nicht geparst werden: {expires_str} ({e})")
                        # Fallback: 10 Minuten Gueltigkeit annehmen (typisch fuer BiPRO)
                        self._token_expires = datetime.now(timezone.utc) + timedelta(minutes=10)
                else:
                    # Kein Ablaufdatum gefunden - konservativer Fallback
                    logger.debug("Kein Token-Ablaufdatum in Response gefunden, nehme 10 Minuten an")
                    self._token_expires = datetime.now(timezone.utc) + timedelta(minutes=10)
                
                return token
            else:
                logger.error("Kein Token in STS-Response gefunden")
                # Mehr Details loggen für Debugging
                if response.status_code != 200:
                    logger.error(f"STS Response Status: {response.status_code}")
                # Fehler aus Response extrahieren
                error_match = re.search(r'<(?:faultstring|nac:Text)>([^<]+)</(?:faultstring|nac:Text)>', response.text)
                if error_match:
                    logger.error(f"STS Fehlermeldung: {error_match.group(1)}")
                logger.error(f"STS Response (erste 1000 Zeichen): {response.text[:1000]}")
                return None
                
        except Exception as e:
            logger.error(f"STS-Request fehlgeschlagen: {e}")
            return None
    
    def _ensure_token(self) -> bool:
        """
        Stellt sicher, dass die Authentifizierung bereit ist.
        
        Bei Zertifikats-Auth (easy Login): Immer True (Zertifikat ist in Session)
        Bei STS-Token: Token holen falls nicht vorhanden oder abgelaufen
        """
        # Bei Zertifikats-Auth brauchen wir kein Token
        if self._uses_certificate:
            return True
        
        # Pruefen ob Token vorhanden und noch gueltig (mit 1 Minute Buffer)
        token_valid = False
        if self._token is not None:
            if self._token_expires is not None:
                # Token ist gueltig wenn Ablaufzeit > jetzt + 1 Minute Buffer
                # WICHTIG: Beide Zeiten muessen timezone-aware sein!
                buffer = timedelta(minutes=1)
                token_valid = datetime.now(timezone.utc) + buffer < self._token_expires
                if not token_valid:
                    logger.info("STS-Token abgelaufen oder bald ablaufend, hole neues Token")
            else:
                # Kein Ablaufdatum bekannt - Token als gueltig annehmen
                token_valid = True
        
        # STS-Token holen falls nicht vorhanden oder abgelaufen
        if not token_valid:
            self._token = self._get_sts_token()
        
        return self._token is not None
    
    def _build_soap_header(self) -> str:
        """
        Baut den SOAP-Header basierend auf der Auth-Methode.
        
        Bei Zertifikats-Auth: Leerer Security-Header (Auth über SSL)
        Bei STS-Token: SecurityContextToken mit Token
        """
        if self._uses_certificate:
            # Bei Zertifikats-Auth: Minimaler Header
            # Die Authentifizierung erfolgt über SSL-Client-Zertifikat
            return '''<soapenv:Header/>'''
        else:
            # STS-Token im Header
            return f'''<soapenv:Header>
      <wsse:Security xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd">
         <wsc:SecurityContextToken xmlns:wsc="http://schemas.xmlsoap.org/ws/2005/02/sc">
            <wsc:Identifier>{self._token}</wsc:Identifier>
         </wsc:SecurityContextToken>
      </wsse:Security>
   </soapenv:Header>'''
    
    def test_connection(self) -> bool:
        """Testet die Verbindung zum Service."""
        try:
            if not self._ensure_token():
                return False
            # Einfacher Test: Liste abrufen
            self.list_shipments()
            return True
        except Exception as e:
            logger.error(f"Verbindungstest fehlgeschlagen: {e}")
            return False
    
    def list_shipments(self, confirmed: bool = True) -> List[ShipmentInfo]:
        """
        Listet bereitstehende Lieferungen auf.
        
        BiPRO Operation: listShipments
        
        Args:
            confirmed: True (default) = Lieferungen abrufen und als empfangen bestaetigen
                       False = Nur auflisten ohne Bestaetigung
        
        Returns:
            Liste von ShipmentInfo
        """
        # Token holen
        if not self._ensure_token():
            raise Exception("Konnte kein STS-Token erhalten. Bitte Zugangsdaten prüfen.")
        
        logger.info(f"Rufe listShipments auf (confirmed={confirmed})...")
        
        soap_header = self._build_soap_header()
        
        # Consumer-ID (nac: Namespace, nicht pm:!)
        consumer_id_xml = ""
        if self.credentials.consumer_id:
            consumer_id_xml = f"<nac:ConsumerID>{self.credentials.consumer_id}</nac:ConsumerID>"
            logger.info(f"Consumer-ID im Request: {self.credentials.consumer_id}")
        
        # BestaetigeLieferungen: VU-spezifisch
        # - VEMA braucht es NICHT (stört sogar)
        # - Degenia und andere BRAUCHEN es!
        if self._is_vema:
            bestaetigen_xml = ""
        else:
            # Degenia: true = neue Lieferungen abrufen
            bestaetigen_xml = f"<tran:BestaetigeLieferungen>{str(confirmed).lower()}</tran:BestaetigeLieferungen>"
        
        body = f'''<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                  xmlns:tran="http://www.bipro.net/namespace/transfer"
                  xmlns:nac="http://www.bipro.net/namespace/nachrichten"
                  xmlns:bas="http://www.bipro.net/namespace/basis">
   {soap_header}
   <soapenv:Body>
      <tran:listShipments>
         <tran:Request>
            <nac:BiPROVersion>2.6.1.1.0</nac:BiPROVersion>
            {consumer_id_xml}
            {bestaetigen_xml}
         </tran:Request>
      </tran:listShipments>
   </soapenv:Body>
</soapenv:Envelope>'''
        
        # SOAPAction: VU-spezifisch (VEMA braucht leer, andere spezifisch)
        headers = {
            'Content-Type': 'text/xml; charset=utf-8',
            'SOAPAction': self._get_soap_action('listShipments')
        }
        
        try:
            response = self.session.post(
                self.transfer_url,
                data=body.encode('utf-8'),
                headers=headers,
                timeout=60
            )
            
            logger.debug(f"listShipments Response Status: {response.status_code}")
            
            # Status prüfen (verschiedene Namespace-Präfixe: nac:, n:, oder ohne)
            if re.search(r'<(?:nac:|n:)?StatusID>NOK</(?:nac:|n:)?StatusID>', response.text):
                # Fehlermeldung extrahieren
                error_match = re.search(r'<(?:nac:|n:)?Text>([^<]+)</(?:nac:|n:)?Text>', response.text)
                error_text = error_match.group(1) if error_match else "Unbekannter Fehler"
                raise Exception(f"BiPRO Fehler: {error_text}")
            
            # Lieferungen parsen
            shipments = ShipmentInfo.from_xml(response.text)
            
            logger.info(f"listShipments: {len(shipments)} Lieferung(en) gefunden")
            
            # Wenn keine Lieferungen, prüfen ob es eine Hinweis-Meldung gibt
            if len(shipments) == 0:
                # Vollständige Response loggen für Debug
                logger.info(f"listShipments Response (erste 2000 Zeichen): {response.text[:2000]}")
                if '04001' in response.text:
                    logger.info("BiPRO Meldung: Keine Lieferungen vorhanden")
                elif '04000' in response.text:
                    logger.info("BiPRO Meldung: Aufruf erfolgreich")
            
            return shipments
            
        except requests.RequestException as e:
            logger.error(f"listShipments Request fehlgeschlagen: {e}")
            raise
    
    def get_shipment(self, shipment_id: str) -> ShipmentContent:
        """
        Ruft eine Lieferung ab.
        
        BiPRO Operation: getShipment
        
        Unterstützt MTOM/XOP Multipart-Responses (wie bei Degenia).
        
        Args:
            shipment_id: ID der Lieferung
            
        Returns:
            ShipmentContent mit Dokumenten
        """
        if not self._ensure_token():
            raise Exception("Konnte kein STS-Token erhalten")
        
        logger.info(f"Rufe getShipment auf für ID: {shipment_id}")
        
        soap_header = self._build_soap_header()
        
        # Consumer-ID (nac: Namespace!)
        consumer_id_xml = ""
        if self.credentials.consumer_id:
            consumer_id_xml = f"<nac:ConsumerID>{self.credentials.consumer_id}</nac:ConsumerID>"
        
        body = f'''<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                  xmlns:tran="http://www.bipro.net/namespace/transfer"
                  xmlns:nac="http://www.bipro.net/namespace/nachrichten"
                  xmlns:bas="http://www.bipro.net/namespace/basis">
   {soap_header}
   <soapenv:Body>
      <tran:getShipment>
         <tran:Request>
            <nac:BiPROVersion>2.6.1.1.0</nac:BiPROVersion>
            {consumer_id_xml}
            <tran:ID>{shipment_id}</tran:ID>
         </tran:Request>
      </tran:getShipment>
   </soapenv:Body>
</soapenv:Envelope>'''
        
        # SOAPAction: VU-spezifisch (VEMA braucht leer, andere spezifisch)
        headers = {
            'Content-Type': 'text/xml; charset=utf-8',
            'SOAPAction': self._get_soap_action('getShipment')
        }
        
        try:
            response = self.session.post(
                self.transfer_url,
                data=body.encode('utf-8'),
                headers=headers,
                timeout=120
            )
            
            logger.info(f"getShipment Response Status: {response.status_code}")
            logger.info(f"getShipment Response Länge: {len(response.content)} Bytes")
            
            documents = []
            metadata = {}
            raw_content = response.content
            
            # Prüfen ob MTOM/XOP Multipart Response
            content_type = response.headers.get('Content-Type', '')
            is_mtom = 'multipart' in content_type.lower() or raw_content[:2] == b'--'
            
            if is_mtom:
                logger.info("MTOM/XOP Multipart Response erkannt")
                documents, metadata = self._parse_mtom_response(raw_content, content_type)
            else:
                # Normaler XML-Response (Base64-encoded)
                logger.info("Standard XML Response")
                documents, metadata = self._parse_xml_response(response.text)
            
            logger.info(f"getShipment: {len(documents)} Dokument(e) gefunden")
            
            # Raw Content für Archiv (nur XML-Teil bei MTOM)
            if is_mtom:
                # Extrahiere nur den XML-Teil für raw_xml
                parts = self._split_multipart(raw_content, content_type)
                raw_xml = parts[0].decode('utf-8', errors='replace') if parts else response.text
            else:
                raw_xml = response.text
            
            return ShipmentContent(
                shipment_id=shipment_id,
                documents=documents,
                metadata=metadata,
                raw_xml=raw_xml
            )
            
        except requests.RequestException as e:
            logger.error(f"getShipment Request fehlgeschlagen: {e}")
            raise
    
    def _extract_boundary(self, content_type: str) -> Optional[bytes]:
        """
        Extrahiert die Boundary aus dem Content-Type Header.
        
        Args:
            content_type: HTTP Content-Type Header Wert
            
        Returns:
            Boundary als bytes oder None wenn nicht gefunden
        """
        if not content_type:
            return None
        
        # Pattern: boundary="uuid:12345" oder boundary=uuid:12345
        # Auch mit Quotes oder ohne
        match = re.search(r'boundary="([^"]+)"', content_type, re.IGNORECASE)
        if not match:
            match = re.search(r'boundary=([^;\s]+)', content_type, re.IGNORECASE)
        
        if match:
            boundary = match.group(1)
            logger.debug(f"Boundary aus Content-Type Header extrahiert: {boundary}")
            return boundary.encode('utf-8')
        
        return None
    
    def _split_multipart(self, content: bytes, content_type: str = "") -> list:
        """
        Splittet MIME Multipart Content in Teile.
        
        Args:
            content: Raw bytes des Multipart-Contents
            content_type: HTTP Content-Type Header (empfohlen für korrekte Boundary)
            
        Returns:
            Liste der MIME-Parts
        """
        # Boundary aus Content-Type Header extrahieren (bevorzugt)
        boundary = self._extract_boundary(content_type)
        
        # Fallback: Boundary aus erster Zeile des Contents (legacy)
        if boundary is None:
            logger.debug("Keine Boundary im Header, versuche erste Zeile")
            first_line_end = content.find(b'\r\n')
            if first_line_end == -1:
                first_line_end = content.find(b'\n')
            
            if first_line_end == -1:
                logger.warning("Keine Boundary gefunden, gebe gesamten Content zurück")
                return [content]
            
            boundary = content[:first_line_end].strip()
            if boundary.startswith(b'--'):
                boundary = boundary[2:]
            logger.debug(f"Boundary aus erster Zeile: {boundary[:50]}...")
        
        logger.info(f"MTOM Boundary: {boundary[:50]}..." if len(boundary) > 50 else f"MTOM Boundary: {boundary}")
        
        # Nach Boundary splitten
        delimiter = b'--' + boundary
        parts = content.split(delimiter)
        
        logger.debug(f"Content nach Boundary-Split: {len(parts)} Teile")
        
        # Leere und End-Marker entfernen
        result = []
        for i, part in enumerate(parts):
            part = part.strip()
            if part and part != b'--' and not part.startswith(b'--'):
                # Header vom Body trennen
                header_end = part.find(b'\r\n\r\n')
                if header_end == -1:
                    header_end = part.find(b'\n\n')
                
                if header_end != -1:
                    result.append(part)
                    logger.debug(f"Part {i}: {len(part)} Bytes")
        
        logger.info(f"MTOM: {len(result)} gültige Parts nach Filterung")
        return result
    
    def _parse_mtom_response(self, content: bytes, content_type: str = "") -> tuple:
        """
        Parst eine MTOM/XOP Multipart Response.
        
        Args:
            content: Raw bytes der MTOM Response
            content_type: HTTP Content-Type Header für Boundary-Extraktion
        
        Returns:
            (documents, metadata)
        """
        documents = []
        metadata = {}
        
        # Multipart aufteilen - Content-Type für korrekte Boundary übergeben
        parts = self._split_multipart(content, content_type)
        logger.info(f"MTOM: {len(parts)} Teil(e) gefunden")
        
        if not parts:
            return documents, metadata
        
        # Content-IDs und Binärdaten sammeln
        binary_parts = {}  # content_id -> (content_type, data)
        xml_part = None
        
        for part in parts:
            # Header und Body trennen - konsistent den tatsächlich gefundenen Separator verwenden
            header_end_crlf = part.find(b'\r\n\r\n')
            header_end_lf = part.find(b'\n\n')
            
            # Den früheren (korrekten) Separator wählen
            if header_end_crlf != -1 and (header_end_lf == -1 or header_end_crlf < header_end_lf):
                header_end = header_end_crlf
                separator_len = 4  # \r\n\r\n
            elif header_end_lf != -1:
                header_end = header_end_lf
                separator_len = 2  # \n\n
            else:
                logger.debug(f"Kein Header/Body-Separator in Part gefunden, überspringe")
                continue
            
            headers_raw = part[:header_end].decode('utf-8', errors='replace').lower()
            body = part[header_end + separator_len:]
            
            # Content-ID extrahieren - robusteres Pattern für verschiedene Varianten
            # Unterstützt: <cid>, cid, url-encoded cid, mit/ohne spitze Klammern
            cid_match = re.search(r'content-id:\s*<?([^>\s\r\n]+)>?', headers_raw)
            content_id = cid_match.group(1) if cid_match else None
            
            # URL-Decoding für Content-ID falls nötig (z.B. %40 -> @)
            if content_id and '%' in content_id:
                try:
                    from urllib.parse import unquote
                    content_id = unquote(content_id)
                except ImportError:
                    pass
            
            # Content-Type extrahieren
            ct_match = re.search(r'content-type:\s*([^\s;]+)', headers_raw)
            content_type = ct_match.group(1) if ct_match else 'application/octet-stream'
            
            if 'xml' in content_type or 'soap' in content_type:
                xml_part = body
            elif content_id:
                binary_parts[content_id] = (content_type, body)
                logger.info(f"MTOM Binary Part: {content_id}, Type: {content_type}, Size: {len(body)}")
        
        # XML parsen und Dokumente extrahieren
        if xml_part:
            xml_text = xml_part.decode('utf-8', errors='replace')
            logger.debug(f"MTOM XML Teil (erste 1000 Zeichen): {xml_text[:1000]}")
            
            # Dateiname aus XML extrahieren - VEMA verwendet verschiedene Namespace-Präfixe
            # a:, allg:, gevo:, oder ohne Präfix
            datei_pattern = r'<(?:gevo:|a:|allg:)?Datei[^>]*>(.*?)</(?:gevo:|a:|allg:)?Datei>'
            datei_matches = re.findall(datei_pattern, xml_text, re.DOTALL)
            
            logger.debug(f"Gefundene Datei-Blöcke: {len(datei_matches)}")
            
            if not datei_matches:
                # Alternatives Pattern - direkte Suche nach Dateiname und XOP
                # VEMA-Format: <a:Dateiname>...</a:Dateiname>
                filename_pattern = r'<(?:a:|allg:|gevo:)?Dateiname>([^<]+)</(?:a:|allg:|gevo:)?Dateiname>'
                filename_matches = re.findall(filename_pattern, xml_text)
                logger.debug(f"Gefundene Dateinamen: {filename_matches}")
                
                # XOP Include finden
                xop_pattern = r'<xop:Include\s+href="cid:([^"]+)"'
                xop_matches = re.findall(xop_pattern, xml_text)
                logger.debug(f"Gefundene XOP-Referenzen: {xop_matches}")
                
                for i, cid in enumerate(xop_matches):
                    if cid in binary_parts:
                        content_type, data = binary_parts[cid]
                        filename = filename_matches[i] if i < len(filename_matches) else f'dokument_{i+1}.pdf'
                        
                        documents.append({
                            'filename': filename,
                            'content_bytes': data,
                            'mime_type': content_type
                        })
                        logger.info(f"Dokument extrahiert: {filename}, {len(data)} Bytes")
            else:
                for datei_xml in datei_matches:
                    # VEMA verwendet a:Dateiname statt allg:Dateiname
                    filename_match = re.search(r'<(?:a:|allg:|gevo:)?Dateiname>([^<]+)</(?:a:|allg:|gevo:)?Dateiname>', datei_xml)
                    xop_match = re.search(r'href="cid:([^"]+)"', datei_xml)
                    
                    if xop_match:
                        cid = xop_match.group(1)
                        if cid in binary_parts:
                            content_type, data = binary_parts[cid]
                            filename = filename_match.group(1) if filename_match else f'dokument.pdf'
                            
                            documents.append({
                                'filename': filename,
                                'content_bytes': data,
                                'mime_type': content_type
                            })
                            logger.info(f"Dokument extrahiert: {filename}, {len(data)} Bytes")
            
            # Metadaten extrahieren - verschiedene Namespace-Präfixe
            kategorie_match = re.search(r'<(?:tran:|t:)?Kategorie>([^<]+)</(?:tran:|t:)?Kategorie>', xml_text)
            if kategorie_match:
                metadata['category'] = kategorie_match.group(1)
            
            vsnr_match = re.search(r'<(?:a:|allg:|t:)?Versicherungsscheinnummer>([^<]+)</(?:a:|allg:|t:)?Versicherungsscheinnummer>', xml_text)
            if vsnr_match:
                metadata['versicherungsschein_nr'] = vsnr_match.group(1)
        
        # Falls keine XOP-Referenzen, aber Binary Parts vorhanden
        if not documents and binary_parts:
            for cid, (content_type, data) in binary_parts.items():
                # Dateityp aus Magic Bytes ermitteln
                if data[:4] == b'%PDF':
                    ext = 'pdf'
                elif data[:2] == b'\xff\xd8':
                    ext = 'jpg'
                elif data[:8] == b'\x89PNG\r\n\x1a\n':
                    ext = 'png'
                else:
                    ext = 'bin'
                
                documents.append({
                    'filename': f'dokument_{len(documents)+1}.{ext}',
                    'content_bytes': data,
                    'mime_type': content_type
                })
        
        # Debug-Logging bei 0 Dokumenten für Fehlersuche
        if not documents:
            logger.warning("MTOM: Keine Dokumente extrahiert!")
            logger.warning(f"  - Binary Parts gefunden: {len(binary_parts)}")
            logger.warning(f"  - XML Part vorhanden: {xml_part is not None}")
            if binary_parts:
                for cid, (ct, data) in binary_parts.items():
                    logger.warning(f"  - Unzugeordneter Binary Part: CID={cid}, Type={ct}, Size={len(data)} Bytes")
            if xml_part:
                # Ersten Teil des XML ausgeben für Diagnose
                xml_preview = xml_part.decode('utf-8', errors='replace')[:2000]
                logger.warning(f"  - XML Preview: {xml_preview}")
        else:
            logger.info(f"MTOM: {len(documents)} Dokument(e) erfolgreich extrahiert")
            for doc in documents:
                logger.info(f"  - {doc['filename']}: {len(doc['content_bytes'])} Bytes, {doc['mime_type']}")
        
        return documents, metadata
    
    def _parse_xml_response(self, xml_text: str) -> tuple:
        """Parst eine normale XML Response mit Base64-encoded Content."""
        documents = []
        metadata = {}
        
        # Dokumente mit Base64-Content suchen
        doc_pattern = r'<[^>]*Dokument[^>]*>(.*?)</[^>]*Dokument>'
        doc_matches = re.findall(doc_pattern, xml_text, re.DOTALL)
        
        for i, doc_xml in enumerate(doc_matches):
            filename_match = re.search(r'<[^>]*Dateiname[^>]*>([^<]+)</[^>]*Dateiname>', doc_xml)
            content_match = re.search(r'<[^>]*(?:Inhalt|Content|Daten)[^>]*>([A-Za-z0-9+/=\s]+)</[^>]*(?:Inhalt|Content|Daten)>', doc_xml)
            
            if content_match:
                content = content_match.group(1).replace('\n', '').replace(' ', '').replace('\r', '')
                if len(content) > 50:
                    try:
                        decoded = base64.b64decode(content)
                        filename = filename_match.group(1) if filename_match else f'dokument_{i+1}.pdf'
                        
                        documents.append({
                            'filename': filename,
                            'content_bytes': decoded,
                            'mime_type': 'application/pdf'
                        })
                    except:
                        pass
        
        # Metadaten
        kategorie_match = re.search(r'<[^>]*Kategorie[^>]*>([^<]+)</[^>]*Kategorie>', xml_text)
        if kategorie_match:
            metadata['category'] = kategorie_match.group(1)
        
        return documents, metadata
    
    def acknowledge_shipment(self, shipment_id: str) -> bool:
        """
        Quittiert den Empfang einer Lieferung.
        
        BiPRO Operation: acknowledgeShipment
        
        Args:
            shipment_id: ID der Lieferung
            
        Returns:
            True wenn erfolgreich
        """
        if not self._ensure_token():
            raise Exception("Konnte kein STS-Token erhalten")
        
        logger.info(f"Rufe acknowledgeShipment auf für ID: {shipment_id}")
        
        soap_header = self._build_soap_header()
        
        # Consumer-ID (nac: Namespace!)
        consumer_id_xml = ""
        if self.credentials.consumer_id:
            consumer_id_xml = f"<nac:ConsumerID>{self.credentials.consumer_id}</nac:ConsumerID>"
        
        body = f'''<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                  xmlns:tran="http://www.bipro.net/namespace/transfer"
                  xmlns:nac="http://www.bipro.net/namespace/nachrichten"
                  xmlns:bas="http://www.bipro.net/namespace/basis">
   {soap_header}
   <soapenv:Body>
      <tran:acknowledgeShipment>
         <tran:Request>
            <nac:BiPROVersion>2.6.1.1.0</nac:BiPROVersion>
            {consumer_id_xml}
            <tran:ID>{shipment_id}</tran:ID>
         </tran:Request>
      </tran:acknowledgeShipment>
   </soapenv:Body>
</soapenv:Envelope>'''
        
        # SOAPAction: VU-spezifisch (VEMA braucht leer, andere spezifisch)
        headers = {
            'Content-Type': 'text/xml; charset=utf-8',
            'SOAPAction': self._get_soap_action('acknowledgeShipment')
        }
        
        try:
            response = self.session.post(
                self.transfer_url,
                data=body.encode('utf-8'),
                headers=headers,
                timeout=30
            )
            
            # Prüfe auf OK-Status mit verschiedenen Namespace-Präfixen (nac:, n:, oder ohne)
            success = bool(re.search(r'<(?:nac:|n:)?StatusID>OK</(?:nac:|n:)?StatusID>', response.text))
            
            if success:
                logger.info(f"acknowledgeShipment erfolgreich: {shipment_id}")
            else:
                # Fehlermeldung extrahieren
                error_match = re.search(r'<(?:nac:|n:)?Text>([^<]+)</(?:nac:|n:)?Text>', response.text)
                error_text = error_match.group(1) if error_match else "Unbekannter Fehler"
                logger.warning(f"acknowledgeShipment fehlgeschlagen für {shipment_id}: {error_text}")
                logger.debug(f"acknowledgeShipment Response: {response.text[:1000]}")
            
            return success
            
        except requests.RequestException as e:
            logger.error(f"acknowledgeShipment Request fehlgeschlagen: {e}")
            raise
    
    def close(self):
        """Schliesst die Verbindung und raeumt auf."""
        self._token = None
        self.session.close()
        
        # Temporäre PEM-Dateien löschen (von PFX-Konvertierung)
        if self._temp_cert_file:
            try:
                os.unlink(self._temp_cert_file.name)
                logger.debug(f"Temp-Zertifikat geloescht: {self._temp_cert_file.name}")
            except:
                pass
        
        if self._temp_key_file:
            try:
                os.unlink(self._temp_key_file.name)
                logger.debug(f"Temp-Key geloescht: {self._temp_key_file.name}")
            except:
                pass
        
        logger.debug("BiPRO-Verbindung geschlossen")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False


# =============================================================================
# SharedTokenManager - Thread-safe Token-Sharing für parallele Downloads
# =============================================================================

class SharedTokenManager:
    """
    Thread-safe Token-Manager für parallele BiPRO-Downloads.
    
    Verwaltet ein STS-Token zentral und stellt es mehreren Worker-Threads
    zur Verfügung. Das Token wird automatisch erneuert wenn es abläuft.
    
    Usage:
        manager = SharedTokenManager(credentials)
        manager.initialize()
        
        # In Worker-Threads:
        token = manager.get_valid_token()
        soap_header = manager.build_soap_header()
        
        # Am Ende:
        manager.close()
    """
    
    def __init__(self, credentials: BiPROCredentials):
        """
        Initialisiert den Token-Manager.
        
        Args:
            credentials: BiPRO-Zugangsdaten
        """
        self._credentials = credentials
        self._client: Optional[TransferServiceClient] = None
        self._lock = threading.Lock()
        self._initialized = False
    
    def initialize(self) -> bool:
        """
        Initialisiert den Client und holt das erste Token.
        
        Returns:
            True wenn erfolgreich, False bei Fehler
        """
        with self._lock:
            if self._initialized:
                return True
            
            try:
                self._client = TransferServiceClient(self._credentials)
                self._client.__enter__()  # Session initialisieren
                
                # Erstes Token holen
                if not self._client._ensure_token():
                    logger.error("SharedTokenManager: Konnte kein initiales Token holen")
                    return False
                
                self._initialized = True
                logger.info("SharedTokenManager initialisiert")
                return True
                
            except Exception as e:
                logger.error(f"SharedTokenManager Initialisierung fehlgeschlagen: {e}")
                return False
    
    def _is_token_valid(self) -> bool:
        """
        Prueft ob das aktuelle Token noch gueltig ist (lock-free).
        
        Kann ohne Lock aufgerufen werden, da einzelne Attribut-Reads
        in Python durch den GIL geschuetzt sind.
        
        Returns:
            True wenn Token vorhanden und noch gueltig
        """
        if not self._client or not self._client._token:
            return False
        if self._client._uses_certificate:
            return True  # Zertifikats-Auth braucht kein Token
        if self._client._token_expires is None:
            return True  # Kein Expiry bekannt, als gueltig annehmen
        buffer = timedelta(minutes=1)
        return datetime.now(timezone.utc) + buffer < self._client._token_expires
    
    def get_valid_token(self) -> Optional[str]:
        """
        Gibt ein gueltiges Token zurueck (thread-safe).
        
        Verwendet Double-Checked Locking:
        - Schneller Pfad: Token gueltig -> kein Lock noetig
        - Langsamer Pfad: Token abgelaufen -> Lock fuer Refresh
        
        Returns:
            Gueltiges Token oder None bei Fehler
        """
        if not self._initialized or not self._client:
            logger.error("SharedTokenManager nicht initialisiert")
            return None
        
        # Schneller Pfad: Token noch gueltig (kein Lock)
        if self._is_token_valid():
            return self._client._token
        
        # Langsamer Pfad: Token erneuern (mit Lock)
        with self._lock:
            # Double-Check: Anderer Thread koennte bereits refreshed haben
            if self._is_token_valid():
                return self._client._token
            
            # Tatsaechlich refreshen
            logger.info("SharedTokenManager: Token-Refresh gestartet")
            if self._client._ensure_token():
                return self._client._token
            
            logger.error("SharedTokenManager: Token-Refresh fehlgeschlagen")
            return None
    
    def build_soap_header(self) -> str:
        """
        Baut den SOAP-Header mit dem aktuellen Token (thread-safe).
        
        Verwendet Double-Checked Locking wie get_valid_token().
        
        Returns:
            SOAP-Header als String
        """
        if not self._initialized or not self._client:
            raise Exception("SharedTokenManager nicht initialisiert")
        
        # Schneller Pfad
        if self._is_token_valid():
            return self._client._build_soap_header()
        
        # Langsamer Pfad
        with self._lock:
            if self._is_token_valid():
                return self._client._build_soap_header()
            
            logger.info("SharedTokenManager: Token-Refresh fuer SOAP-Header")
            self._client._ensure_token()
            return self._client._build_soap_header()
    
    def get_session(self) -> requests.Session:
        """
        Gibt die konfigurierte Session zurück.
        
        ACHTUNG: Die Session selbst ist nicht thread-safe für parallele Requests!
        Für parallele Downloads sollte jeder Worker eine eigene Session erstellen.
        
        Returns:
            requests.Session
        """
        if not self._initialized or not self._client:
            raise Exception("SharedTokenManager nicht initialisiert")
        return self._client.session
    
    def get_transfer_url(self) -> str:
        """Gibt die Transfer-URL zurück."""
        if not self._initialized or not self._client:
            raise Exception("SharedTokenManager nicht initialisiert")
        return self._client.transfer_url
    
    def get_consumer_id(self) -> str:
        """Gibt die Consumer-ID zurück."""
        return self._credentials.consumer_id or ""
    
    def uses_certificate(self) -> bool:
        """Gibt zurück ob Zertifikats-Auth verwendet wird."""
        return self._credentials.uses_certificate
    
    def is_vema(self) -> bool:
        """Gibt zurück ob VEMA-Modus aktiv ist."""
        if not self._initialized or not self._client:
            return False
        return self._client._is_vema
    
    @property
    def credentials(self) -> BiPROCredentials:
        """Gibt die Credentials zurück."""
        return self._credentials
    
    def close(self):
        """Schließt den Token-Manager und gibt Ressourcen frei."""
        with self._lock:
            if self._client:
                self._client.close()
                self._client = None
            self._initialized = False
            logger.info("SharedTokenManager geschlossen")
    
    def __enter__(self):
        self.initialize()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False
