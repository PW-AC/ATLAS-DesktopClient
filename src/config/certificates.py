"""
BiPRO-GDV Tool - Zertifikat-Manager

Verwaltet X.509-Zertifikate lokal für BiPRO-Authentifizierung.
Zertifikate werden im lokalen Datenverzeichnis gespeichert.
"""

import os
import json
import logging
import shutil
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


def get_certificates_dir() -> Path:
    """Gibt das Verzeichnis für Zertifikate zurück."""
    # Im Benutzer-Appdata-Verzeichnis
    if os.name == 'nt':
        base = Path(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')))
    else:
        base = Path.home() / '.local' / 'share'
    
    cert_dir = base / 'BiPRO-GDV-Tool' / 'certificates'
    cert_dir.mkdir(parents=True, exist_ok=True)
    return cert_dir


def get_certificates_index_path() -> Path:
    """Gibt den Pfad zur Zertifikats-Index-Datei zurück."""
    return get_certificates_dir() / 'index.json'


@dataclass
class CertificateInfo:
    """Informationen über ein gespeichertes Zertifikat."""
    id: str                    # Eindeutige ID (UUID)
    name: str                  # Anzeigename
    filename: str              # Dateiname im Zertifikatsverzeichnis
    subject_cn: str            # Common Name des Inhabers
    issuer_cn: str             # Common Name des Ausstellers
    valid_from: str            # ISO-Datum
    valid_until: str           # ISO-Datum
    serial_number: str         # Seriennummer
    created_at: str            # Import-Datum
    password_hint: str = ""    # Optional: Passwort-Hinweis (NICHT das Passwort!)
    
    @property
    def is_expired(self) -> bool:
        """Prüft ob das Zertifikat abgelaufen ist."""
        try:
            valid_until = datetime.fromisoformat(self.valid_until.replace('Z', '+00:00'))
            return datetime.now(valid_until.tzinfo) > valid_until
        except (ValueError, TypeError):
            return False
    
    @property
    def days_until_expiry(self) -> int:
        """Gibt die Tage bis zum Ablauf zurück (negativ = abgelaufen)."""
        try:
            valid_until = datetime.fromisoformat(self.valid_until.replace('Z', '+00:00'))
            delta = valid_until - datetime.now(valid_until.tzinfo)
            return delta.days
        except (ValueError, TypeError):
            return 0
    
    @property
    def full_path(self) -> str:
        """Gibt den vollständigen Pfad zur Zertifikatsdatei zurück."""
        return str(get_certificates_dir() / self.filename)
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiert zu Dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CertificateInfo':
        """Erstellt aus Dictionary."""
        return cls(**data)


class CertificateManager:
    """
    Verwaltet X.509-Zertifikate lokal.
    
    Verwendung:
        manager = CertificateManager()
        
        # Zertifikat importieren
        cert_info = manager.import_certificate("/path/to/cert.pfx", "password", "Mein Zertifikat")
        
        # Alle Zertifikate auflisten
        certs = manager.list_certificates()
        
        # Zertifikat abrufen
        cert = manager.get_certificate("cert-id")
        
        # Zertifikat löschen
        manager.delete_certificate("cert-id")
    """
    
    def __init__(self):
        self._index: List[CertificateInfo] = []
        self._load_index()
    
    def _load_index(self):
        """Lädt den Zertifikats-Index."""
        index_path = get_certificates_index_path()
        if index_path.exists():
            try:
                with open(index_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._index = [CertificateInfo.from_dict(c) for c in data]
                logger.info(f"Zertifikats-Index geladen: {len(self._index)} Zertifikate")
            except Exception as e:
                logger.error(f"Fehler beim Laden des Zertifikats-Index: {e}")
                self._index = []
        else:
            self._index = []
    
    def _save_index(self):
        """Speichert den Zertifikats-Index."""
        index_path = get_certificates_index_path()
        try:
            with open(index_path, 'w', encoding='utf-8') as f:
                json.dump([c.to_dict() for c in self._index], f, indent=2)
            logger.info(f"Zertifikats-Index gespeichert: {len(self._index)} Zertifikate")
        except Exception as e:
            logger.error(f"Fehler beim Speichern des Zertifikats-Index: {e}")
    
    def list_certificates(self) -> List[CertificateInfo]:
        """Gibt alle Zertifikate zurück."""
        return self._index.copy()
    
    def get_certificate(self, cert_id: str) -> Optional[CertificateInfo]:
        """Gibt ein Zertifikat anhand der ID zurück."""
        for cert in self._index:
            if cert.id == cert_id:
                return cert
        return None
    
    def import_certificate(self, source_path: str, password: str, 
                          display_name: str = "", password_hint: str = "") -> CertificateInfo:
        """
        Importiert ein Zertifikat.
        
        Args:
            source_path: Pfad zur PFX/P12-Datei
            password: Passwort für die Datei
            display_name: Optionaler Anzeigename
            password_hint: Optionaler Passwort-Hinweis
            
        Returns:
            CertificateInfo mit Zertifikatsdetails
            
        Raises:
            ValueError: Bei ungültigem Passwort oder Datei
            FileNotFoundError: Wenn Datei nicht existiert
        """
        import uuid
        
        if not os.path.exists(source_path):
            raise FileNotFoundError(f"Datei nicht gefunden: {source_path}")
        
        # Zertifikat laden und validieren
        try:
            from cryptography.hazmat.primitives.serialization import pkcs12
            from cryptography.hazmat.backends import default_backend
            
            with open(source_path, 'rb') as f:
                pfx_data = f.read()
            
            password_bytes = password.encode('utf-8') if password else None
            private_key, certificate, chain = pkcs12.load_key_and_certificates(
                pfx_data, password_bytes, default_backend()
            )
            
            if not certificate:
                raise ValueError("Datei enthält kein gültiges Zertifikat")
            
        except Exception as e:
            if 'password' in str(e).lower() or 'mac' in str(e).lower():
                raise ValueError("Falsches Passwort oder ungültige Datei")
            raise ValueError(f"Zertifikat konnte nicht geladen werden: {e}")
        
        # Zertifikatsinformationen extrahieren
        subject_cn = self._extract_cn(certificate.subject)
        issuer_cn = self._extract_cn(certificate.issuer)
        valid_from = certificate.not_valid_before_utc.isoformat()
        valid_until = certificate.not_valid_after_utc.isoformat()
        serial = format(certificate.serial_number, 'x')
        
        # Eindeutige ID und Dateiname generieren
        cert_id = str(uuid.uuid4())
        original_name = os.path.basename(source_path)
        safe_name = f"{cert_id}_{original_name}"
        
        # Datei ins Zertifikatsverzeichnis kopieren
        dest_path = get_certificates_dir() / safe_name
        shutil.copy2(source_path, dest_path)
        
        # Anzeigename falls nicht angegeben
        if not display_name:
            display_name = subject_cn or original_name
        
        # Index-Eintrag erstellen
        cert_info = CertificateInfo(
            id=cert_id,
            name=display_name,
            filename=safe_name,
            subject_cn=subject_cn,
            issuer_cn=issuer_cn,
            valid_from=valid_from,
            valid_until=valid_until,
            serial_number=serial,
            created_at=datetime.now().isoformat(),
            password_hint=password_hint
        )
        
        self._index.append(cert_info)
        self._save_index()
        
        logger.info(f"Zertifikat importiert: {display_name} (ID: {cert_id})")
        return cert_info
    
    def _extract_cn(self, name) -> str:
        """Extrahiert den Common Name aus einem X.509 Name."""
        from cryptography.x509.oid import NameOID
        try:
            cn_attrs = name.get_attributes_for_oid(NameOID.COMMON_NAME)
            if cn_attrs:
                return cn_attrs[0].value
        except Exception:
            pass
        return str(name)
    
    def delete_certificate(self, cert_id: str) -> bool:
        """
        Löscht ein Zertifikat.
        
        Args:
            cert_id: ID des Zertifikats
            
        Returns:
            True wenn erfolgreich
        """
        cert = self.get_certificate(cert_id)
        if not cert:
            return False
        
        # Datei löschen
        try:
            cert_path = Path(cert.full_path)
            if cert_path.exists():
                cert_path.unlink()
        except Exception as e:
            logger.error(f"Fehler beim Löschen der Zertifikatsdatei: {e}")
        
        # Aus Index entfernen
        self._index = [c for c in self._index if c.id != cert_id]
        self._save_index()
        
        logger.info(f"Zertifikat gelöscht: {cert.name} (ID: {cert_id})")
        return True
    
    def update_certificate_name(self, cert_id: str, new_name: str) -> bool:
        """Aktualisiert den Anzeigenamen eines Zertifikats."""
        cert = self.get_certificate(cert_id)
        if not cert:
            return False
        
        cert.name = new_name
        self._save_index()
        return True


# Singleton-Instanz
_manager: Optional[CertificateManager] = None


def get_certificate_manager() -> CertificateManager:
    """Gibt die Singleton-Instanz des Zertifikat-Managers zurück."""
    global _manager
    if _manager is None:
        _manager = CertificateManager()
    return _manager
