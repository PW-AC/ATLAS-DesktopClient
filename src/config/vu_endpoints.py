"""
BiPRO-GDV Tool - VU-Endpunkte Konfiguration

Lokale Konfiguration der BiPRO-Endpunkte für Versicherungsgesellschaften.
Enthält STS-URLs, Auth-Arten und Gesellschafts-Mapping.
"""

import os
import json
import logging
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, asdict, field
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


# ============================================================================
# Auth-Arten (wie im IWM FinanzOffice)
# ============================================================================
AUTH_TYPE_PASSWORD = 0       # Benutzername/Passwort + STS-Token
AUTH_TYPE_CERT_WS = 3        # X.509 Zertifikat (WS-Security)
AUTH_TYPE_CERT_TGIC = 4      # X.509 Zertifikat (TGIC/GDV)
AUTH_TYPE_CERT_DEGENIA = 6   # X.509 Zertifikat (Degenia-spezifisch)

AUTH_TYPE_LABELS = {
    AUTH_TYPE_PASSWORD: "Benutzername/Passwort",
    AUTH_TYPE_CERT_WS: "X.509 Zertifikat (WS-Security)",
    AUTH_TYPE_CERT_TGIC: "X.509 Zertifikat (TGIC/GDV)",
    AUTH_TYPE_CERT_DEGENIA: "X.509 Zertifikat (Degenia)",
}


# ============================================================================
# Bekannte BiPRO-Endpunkte (extrahiert aus IWM FinanzOffice)
# ============================================================================
KNOWN_ENDPOINTS = {
    # =========================================================================
    # STS-Endpunkte (Benutzername/Passwort) - AUTH_TYPE_PASSWORD (0)
    # =========================================================================
    "aig": {
        "name": "AIG",
        "sts_url": "https://www.aigportal.de/X4/httpstarter/WS/1/STS/UserPasswordLogin_2.5.0.1.1",
        "auth_type": AUTH_TYPE_PASSWORD,
        "bipro_version": "2.5.0.1.1"
    },
    "alte_leipziger": {
        "name": "Alte Leipziger",
        "sts_url": "",
        "auth_type": AUTH_TYPE_PASSWORD,
        "bipro_version": "2.6.1.1.0",
        "note": "URL bei VU anfragen"
    },
    "arag": {
        "name": "ARAG",
        "sts_url": "",
        "auth_type": AUTH_TYPE_PASSWORD,
        "bipro_version": "2.6.1.1.0",
        "note": "URL bei VU anfragen"
    },
    "axa": {
        "name": "AXA",
        "sts_url": "https://entry.axa.de/sts/services/UsernamePasswordLogin",
        "auth_type": AUTH_TYPE_PASSWORD,
        "bipro_version": "2.1.0.1.0"
    },
    "barmenia": {
        "name": "Barmenia",
        "sts_url": "",
        "auth_type": AUTH_TYPE_CERT_DEGENIA,
        "bipro_version": "2.6.1.1.0",
        "note": "Degenia-Zertifikat erforderlich"
    },
    "basler": {
        "name": "Basler/Baloise",
        "sts_url": "https://bipro.vs-gruppe.de/ibis/services/BSG.UsernamePasswordLogin_2.1.0.1.0",
        "auth_type": AUTH_TYPE_PASSWORD,
        "bipro_version": "2.1.0.1.0"
    },
    "canada_life": {
        "name": "Canada Life",
        "sts_url": "",
        "auth_type": AUTH_TYPE_PASSWORD,
        "bipro_version": "2.6.1.1.0",
        "note": "URL bei VU anfragen"
    },
    "concordia": {
        "name": "Concordia",
        "sts_url": "",
        "auth_type": AUTH_TYPE_PASSWORD,
        "bipro_version": "2.6.1.1.0",
        "note": "URL bei VU anfragen"
    },
    "condor": {
        "name": "Condor",
        "sts_url": "",
        "auth_type": AUTH_TYPE_PASSWORD,
        "bipro_version": "2.6.1.1.0",
        "note": "URL bei VU anfragen"
    },
    "continentale": {
        "name": "Continentale",
        "sts_url": "https://www2.continentale.de/bipro410-ws/SecurityTokenService_2.1.0.1.0",
        "auth_type": AUTH_TYPE_CERT_DEGENIA,
        "bipro_version": "2.1.0.1.0",
        "note": "Degenia-Zertifikat erforderlich"
    },
    "degenia": {
        "name": "Degenia",
        "sts_url": "https://transfer.degenia.de/X4/httpstarter/ReST/BiPRO/410_STS/UserPasswordLogin_2.6.1.1.0",
        "transfer_url": "https://transfer.degenia.de/X4/httpstarter/ReST/BiPRO/430_Transfer/Service_2.6.1.1.0",
        "auth_type": AUTH_TYPE_PASSWORD,
        "bipro_version": "2.6.1.1.0"
    },
    "deurag": {
        "name": "DEURAG",
        "sts_url": "",
        "auth_type": AUTH_TYPE_PASSWORD,
        "bipro_version": "2.6.1.1.0",
        "note": "URL bei VU anfragen"
    },
    "dialog_leben": {
        "name": "Dialog Lebensversicherung",
        "sts_url": "",
        "auth_type": AUTH_TYPE_CERT_TGIC,
        "bipro_version": "2.6.1.1.0",
        "note": "TGIC/GDV-Zertifikat erforderlich"
    },
    "dialog_sach": {
        "name": "Dialog Versicherung (Sach)",
        "sts_url": "",
        "auth_type": AUTH_TYPE_CERT_TGIC,
        "bipro_version": "2.6.1.1.0",
        "note": "TGIC/GDV-Zertifikat erforderlich"
    },
    "die_bayerische": {
        "name": "Die Bayerische",
        "sts_url": "",
        "auth_type": AUTH_TYPE_PASSWORD,
        "bipro_version": "2.6.1.1.0",
        "note": "URL bei VU anfragen"
    },
    "dmb_rechtsschutz": {
        "name": "DMB Rechtsschutz",
        "sts_url": "",
        "auth_type": AUTH_TYPE_PASSWORD,
        "bipro_version": "2.6.1.1.0",
        "note": "URL bei VU anfragen"
    },
    "domcura": {
        "name": "Domcura",
        "sts_url": "",
        "auth_type": AUTH_TYPE_PASSWORD,
        "bipro_version": "2.6.1.1.0",
        "note": "URL bei VU anfragen"
    },
    "generali": {
        "name": "Generali",
        "sts_url": "",
        "auth_type": AUTH_TYPE_PASSWORD,
        "bipro_version": "2.6.1.1.0",
        "note": "URL bei VU anfragen"
    },
    "german_broker_net": {
        "name": "germanBroker.net",
        "sts_url": "",
        "auth_type": AUTH_TYPE_PASSWORD,
        "bipro_version": "2.6.1.1.0",
        "note": "URL bei VU anfragen"
    },
    "gothaer": {
        "name": "Gothaer",
        "sts_url": "https://public-api.gothaer.de/bipro/SecurityTokenService/n410/v1-0/services/UserPasswordLogin",
        "auth_type": AUTH_TYPE_PASSWORD,
        "bipro_version": "2.5.0.1.0"
    },
    "hansemerkur": {
        "name": "HanseMerkur",
        "sts_url": "",
        "auth_type": AUTH_TYPE_CERT_TGIC,
        "bipro_version": "2.6.1.1.0",
        "note": "TGIC/GDV-Zertifikat erforderlich"
    },
    "hdi": {
        "name": "HDI",
        "sts_url": "https://easy.hdi-gerling.de/bipro-sts/services/SecurityTokenService_1.1.0.5.0",
        "auth_type": AUTH_TYPE_CERT_DEGENIA,
        "bipro_version": "1.1.0.5.0",
        "note": "Degenia-Zertifikat, alternativ VDG-Portal"
    },
    "helvetia": {
        "name": "Helvetia",
        "sts_url": "https://www.helvetia.com/de/helbssts/STS/UserPassword",
        "auth_type": AUTH_TYPE_PASSWORD,
        "bipro_version": "2.1.0.1.0"
    },
    "inter": {
        "name": "INTER Krankenversicherung",
        "sts_url": "",
        "auth_type": AUTH_TYPE_CERT_DEGENIA,
        "bipro_version": "2.6.1.1.0",
        "note": "Degenia-Zertifikat erforderlich"
    },
    "itzehoer": {
        "name": "Itzehoer",
        "sts_url": "",
        "auth_type": AUTH_TYPE_PASSWORD,
        "bipro_version": "2.6.1.1.0",
        "note": "URL bei VU anfragen"
    },
    "janitos": {
        "name": "Janitos",
        "sts_url": "",
        "auth_type": AUTH_TYPE_PASSWORD,
        "bipro_version": "2.6.1.1.0",
        "note": "URL bei VU anfragen"
    },
    "konzept_marketing": {
        "name": "Konzept & Marketing",
        "sts_url": "",
        "auth_type": AUTH_TYPE_PASSWORD,
        "bipro_version": "2.6.1.1.0",
        "note": "URL bei VU anfragen"
    },
    "kravag": {
        "name": "KRAVAG",
        "sts_url": "",
        "auth_type": AUTH_TYPE_PASSWORD,
        "bipro_version": "2.6.1.1.0",
        "note": "URL bei VU anfragen"
    },
    "ks_auxilia": {
        "name": "KS Auxilia",
        "sts_url": "",
        "auth_type": AUTH_TYPE_PASSWORD,
        "bipro_version": "2.6.1.1.0",
        "note": "URL bei VU anfragen"
    },
    "lv1871": {
        "name": "LV1871",
        "sts_url": "https://bipro-services.lv1871.de/BiPRO/410_STS/VDGTicketLogin_2.1.1.1.1",
        "auth_type": AUTH_TYPE_CERT_DEGENIA,
        "bipro_version": "2.1.1.1.1",
        "note": "Verwendet VDG-Portal, Degenia-Zertifikat"
    },
    "mannheimer": {
        "name": "Mannheimer",
        "sts_url": "https://www2.continentale.de/bipro410-ws/SecurityTokenService_2.1.0.1.0",
        "auth_type": AUTH_TYPE_CERT_DEGENIA,
        "bipro_version": "2.1.0.1.0",
        "note": "Gleicher Endpunkt wie Continentale, Degenia-Zertifikat"
    },
    "muenchener_verein": {
        "name": "Münchener Verein",
        "sts_url": "",
        "auth_type": AUTH_TYPE_PASSWORD,
        "bipro_version": "2.6.1.1.0",
        "note": "URL bei VU anfragen"
    },
    "nuernberger": {
        "name": "Nürnberger",
        "sts_url": "",
        "auth_type": AUTH_TYPE_PASSWORD,
        "bipro_version": "2.6.1.1.0",
        "note": "URL bei VU anfragen"
    },
    "ostangler": {
        "name": "Ostangler Brandgilde",
        "sts_url": "",
        "auth_type": AUTH_TYPE_PASSWORD,
        "bipro_version": "2.6.1.1.0",
        "note": "URL bei VU anfragen"
    },
    "provinzial_rheinland": {
        "name": "Provinzial Rheinland",
        "sts_url": "",
        "auth_type": AUTH_TYPE_CERT_TGIC,
        "bipro_version": "2.6.1.1.0",
        "note": "TGIC/GDV-Zertifikat erforderlich"
    },
    "rheinland": {
        "name": "Rheinland Versicherung",
        "sts_url": "",
        "auth_type": AUTH_TYPE_PASSWORD,
        "bipro_version": "2.6.1.1.0",
        "note": "URL bei VU anfragen"
    },
    "rhion": {
        "name": "Rhion",
        "sts_url": "",
        "auth_type": AUTH_TYPE_PASSWORD,
        "bipro_version": "2.6.1.1.0",
        "note": "URL bei VU anfragen"
    },
    "roland": {
        "name": "Roland Rechtsschutz",
        "sts_url": "https://www.roland-portal.de/ibis/services/UsernamePasswordLogin_2.5.0.1.0",
        "auth_type": AUTH_TYPE_PASSWORD,
        "bipro_version": "2.5.0.1.0"
    },
    "rv": {
        "name": "R+V",
        "sts_url": "",
        "auth_type": AUTH_TYPE_PASSWORD,
        "bipro_version": "2.6.1.1.0",
        "note": "URL bei VU anfragen"
    },
    "signal_iduna": {
        "name": "Signal Iduna",
        "sts_url": "",
        "auth_type": AUTH_TYPE_PASSWORD,
        "bipro_version": "2.6.1.1.0",
        "note": "URL bei VU anfragen"
    },
    "stuttgarter": {
        "name": "Stuttgarter",
        "sts_url": "https://bipro-ws.stuttgarter.de/sts/services/sts_webservice_2.1.0.1.2.STSUNPService_2.1.0.1.2",
        "auth_type": AUTH_TYPE_PASSWORD,
        "bipro_version": "2.1.0.1.2"
    },
    "sv_sparkassen": {
        "name": "SV SparkassenVersicherung",
        "sts_url": "",
        "auth_type": AUTH_TYPE_CERT_TGIC,
        "bipro_version": "2.6.1.1.0",
        "note": "TGIC/GDV-Zertifikat erforderlich"
    },
    "swisslife": {
        "name": "Swiss Life",
        "sts_url": "https://www.swisslife-weboffice.de/BiPRO/410_STS/UserPasswordLogin_2.5.0.1.0",
        "auth_type": AUTH_TYPE_PASSWORD,
        "bipro_version": "2.5.0.1.0"
    },
    "vema": {
        "name": "VEMA",
        "sts_url": "",
        "auth_type": AUTH_TYPE_PASSWORD,
        "bipro_version": "2.6.1.1.0",
        "note": "URL bei VU anfragen"
    },
    "versicherungskammer_bayern": {
        "name": "Versicherungskammer Bayern",
        "sts_url": "",
        "auth_type": AUTH_TYPE_CERT_TGIC,
        "bipro_version": "2.6.1.1.0",
        "note": "TGIC/GDV-Zertifikat erforderlich"
    },
    "volkswohlbund": {
        "name": "Volkswohlbund",
        "sts_url": "",
        "auth_type": AUTH_TYPE_PASSWORD,
        "bipro_version": "2.6.1.1.0",
        "note": "Verwendet VDG-Portal"
    },
    "wwk": {
        "name": "WWK",
        "sts_url": "",
        "auth_type": AUTH_TYPE_CERT_DEGENIA,
        "bipro_version": "2.6.1.1.0",
        "note": "Verwendet VDG-Portal, Degenia-Zertifikat"
    },
    "wuerttembergische": {
        "name": "Württembergische",
        "sts_url": "",
        "auth_type": AUTH_TYPE_CERT_TGIC,
        "bipro_version": "2.6.1.1.0",
        "note": "Adam Riese, TGIC/GDV-Zertifikat"
    },
    "zurich": {
        "name": "Zurich",
        "sts_url": "",
        "auth_type": AUTH_TYPE_PASSWORD,
        "bipro_version": "2.6.1.1.0",
        "note": "URL bei VU anfragen"
    },
    
    # =========================================================================
    # Zertifikatsbasierte Endpunkte - AUTH_TYPE_CERT_WS (3)
    # =========================================================================
    "allianz": {
        "name": "Allianz",
        "sts_url": "",
        "transfer_url": "https://www.biprohub.eu/soap/TransferService",
        "auth_type": AUTH_TYPE_CERT_WS,
        "bipro_version": "2.6.1.1.0",
        "note": "BiPROHub - WS-Security Zertifikat"
    },
    "haftpflichtkasse": {
        "name": "Haftpflichtkasse Darmstadt",
        "sts_url": "https://suh.haftpflichtkasse.de/BiPRO/410_STS_X509_2.7.0.1.0",
        "auth_type": AUTH_TYPE_CERT_WS,
        "bipro_version": "2.7.0.1.0"
    },
    "interrisk": {
        "name": "InterRisk",
        "sts_url": "https://bipro.interrisk.de/410_STS/X509Login_2.5.0.1.0",
        "auth_type": AUTH_TYPE_CERT_WS,
        "bipro_version": "2.5.0.1.0"
    },
    "vhv": {
        "name": "VHV",
        "sts_url": "",
        "transfer_url": "",
        "auth_type": AUTH_TYPE_CERT_WS,
        "bipro_version": "2.6.1.1.0",
        "note": "VHV Broker-Auth Zertifikat"
    },
    "wuestenrot": {
        "name": "Wüstenrot",
        "sts_url": "",
        "transfer_url": "https://dp-pu.ww-intern.de:3829/vdz-basis-kern-web/dokumentenverwaltung",
        "auth_type": AUTH_TYPE_CERT_TGIC,
        "bipro_version": "2.1.0.1.0"
    },
    
    # VDG-Portal (zentrale Authentifizierung)
    "vdg_portal": {
        "name": "VDG-Portal",
        "sts_url": "https://easy-login.vdg-portal.de/VDGAuthPortal/services/STS",
        "auth_type": AUTH_TYPE_PASSWORD,
        "bipro_version": "2.1.0.1.0",
        "note": "Zentrale Auth für HDI, LV1871, Volkswohlbund, WWK"
    },
}


def get_config_dir() -> Path:
    """Gibt das Konfigurationsverzeichnis zurück."""
    if os.name == 'nt':
        base = Path(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')))
    else:
        base = Path.home() / '.local' / 'share'
    
    config_dir = base / 'BiPRO-GDV-Tool' / 'config'
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_vu_config_path() -> Path:
    """Gibt den Pfad zur VU-Konfigurationsdatei zurück."""
    return get_config_dir() / 'vu_connections.json'


@dataclass
class VUEndpointConfig:
    """Konfiguration einer VU-Verbindung."""
    id: str                          # Eindeutige ID
    name: str                        # Anzeigename (z.B. "Allianz")
    vu_number: str = ""              # GDV VU-Nummer
    sts_url: str = ""                # STS-Endpunkt URL
    transfer_url: str = ""           # Transfer-Endpunkt URL (optional, oft abgeleitet)
    auth_type: int = AUTH_TYPE_PASSWORD  # Auth-Art (0, 3, 4, 6)
    bipro_version: str = "2.6.1.1.0" # BiPRO-Version
    
    # Credentials (nur für Password-Auth)
    username: str = ""
    password: str = ""               # Verschlüsselt gespeichert
    
    # Zertifikat (für Zertifikats-Auth)
    certificate_id: str = ""         # ID des Zertifikats im CertificateManager
    certificate_password: str = ""   # Passwort für das Zertifikat (verschlüsselt)
    
    # Status
    is_active: bool = True
    last_sync: str = ""              # Letzter erfolgreicher Abruf
    created_at: str = ""
    modified_at: str = ""
    
    # Notizen
    note: str = ""
    
    @property
    def uses_certificate(self) -> bool:
        """Prüft ob Zertifikats-Auth verwendet wird."""
        return self.auth_type in (AUTH_TYPE_CERT_WS, AUTH_TYPE_CERT_TGIC, AUTH_TYPE_CERT_DEGENIA)
    
    @property
    def auth_type_label(self) -> str:
        """Gibt das Label der Auth-Art zurück."""
        return AUTH_TYPE_LABELS.get(self.auth_type, "Unbekannt")
    
    @property
    def effective_transfer_url(self) -> str:
        """Gibt die effektive Transfer-URL zurück (abgeleitet falls nicht gesetzt)."""
        if self.transfer_url:
            return self.transfer_url
        # Aus STS-URL ableiten
        if self.sts_url and '410_STS' in self.sts_url:
            return self.sts_url.replace('410_STS', '430_Transfer').replace(
                'UserPasswordLogin', 'Service'
            ).replace('X509Login', 'Service')
        return self.sts_url
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiert zu Dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'VUEndpointConfig':
        """Erstellt aus Dictionary."""
        # Alte Felder ignorieren, nur bekannte verwenden
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)
    
    @classmethod
    def from_known_endpoint(cls, key: str, config_id: str = "") -> Optional['VUEndpointConfig']:
        """Erstellt aus einem bekannten Endpunkt."""
        import uuid
        
        if key not in KNOWN_ENDPOINTS:
            return None
        
        endpoint = KNOWN_ENDPOINTS[key]
        return cls(
            id=config_id or str(uuid.uuid4()),
            name=endpoint['name'],
            sts_url=endpoint.get('sts_url', ''),
            transfer_url=endpoint.get('transfer_url', ''),
            auth_type=endpoint.get('auth_type', AUTH_TYPE_PASSWORD),
            bipro_version=endpoint.get('bipro_version', '2.6.1.1.0'),
            note=endpoint.get('note', ''),
            created_at=datetime.now().isoformat()
        )


class VUEndpointManager:
    """
    Verwaltet VU-Endpunkt-Konfigurationen lokal.
    
    Verwendung:
        manager = VUEndpointManager()
        
        # Alle Verbindungen auflisten
        connections = manager.list_connections()
        
        # Neue Verbindung aus bekanntem Endpunkt erstellen
        conn = manager.create_from_known("allianz")
        
        # Verbindung speichern
        manager.save_connection(conn)
    """
    
    def __init__(self):
        self._connections: List[VUEndpointConfig] = []
        self._load()
    
    def _load(self):
        """Lädt die Konfiguration."""
        config_path = get_vu_config_path()
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._connections = [VUEndpointConfig.from_dict(c) for c in data]
                logger.info(f"VU-Konfiguration geladen: {len(self._connections)} Verbindungen")
            except Exception as e:
                logger.error(f"Fehler beim Laden der VU-Konfiguration: {e}")
                self._connections = []
        else:
            self._connections = []
    
    def _save(self):
        """Speichert die Konfiguration."""
        config_path = get_vu_config_path()
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump([c.to_dict() for c in self._connections], f, indent=2)
            logger.info(f"VU-Konfiguration gespeichert: {len(self._connections)} Verbindungen")
        except Exception as e:
            logger.error(f"Fehler beim Speichern der VU-Konfiguration: {e}")
    
    def list_connections(self, active_only: bool = False) -> List[VUEndpointConfig]:
        """Gibt alle Verbindungen zurück."""
        if active_only:
            return [c for c in self._connections if c.is_active]
        return self._connections.copy()
    
    def get_connection(self, connection_id: str) -> Optional[VUEndpointConfig]:
        """Gibt eine Verbindung anhand der ID zurück."""
        for conn in self._connections:
            if conn.id == connection_id:
                return conn
        return None
    
    def create_from_known(self, endpoint_key: str) -> Optional[VUEndpointConfig]:
        """Erstellt eine neue Verbindung aus einem bekannten Endpunkt."""
        return VUEndpointConfig.from_known_endpoint(endpoint_key)
    
    def save_connection(self, connection: VUEndpointConfig) -> bool:
        """Speichert oder aktualisiert eine Verbindung."""
        connection.modified_at = datetime.now().isoformat()
        
        # Existierende aktualisieren oder neu hinzufügen
        for i, conn in enumerate(self._connections):
            if conn.id == connection.id:
                self._connections[i] = connection
                self._save()
                return True
        
        # Neue Verbindung
        if not connection.created_at:
            connection.created_at = datetime.now().isoformat()
        self._connections.append(connection)
        self._save()
        return True
    
    def delete_connection(self, connection_id: str) -> bool:
        """Löscht eine Verbindung."""
        original_count = len(self._connections)
        self._connections = [c for c in self._connections if c.id != connection_id]
        
        if len(self._connections) < original_count:
            self._save()
            return True
        return False
    
    def update_last_sync(self, connection_id: str):
        """Aktualisiert den letzten Sync-Zeitpunkt."""
        conn = self.get_connection(connection_id)
        if conn:
            conn.last_sync = datetime.now().isoformat()
            self._save()
    
    def get_known_endpoints(self) -> Dict[str, Dict]:
        """Gibt alle bekannten Endpunkte zurück."""
        return KNOWN_ENDPOINTS.copy()


# Singleton-Instanz
_manager: Optional[VUEndpointManager] = None


def get_vu_endpoint_manager() -> VUEndpointManager:
    """Gibt die Singleton-Instanz des VU-Endpoint-Managers zurück."""
    global _manager
    if _manager is None:
        _manager = VUEndpointManager()
    return _manager
