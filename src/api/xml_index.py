"""
BiPro API - XML Index

Client fuer die XML-Rohdaten-Indexierung.
Separiert von documents fuer saubere Trennung von Dokumenten und Rohdaten.
"""

from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime
import logging

from .client import APIClient, APIError

logger = logging.getLogger(__name__)


@dataclass
class XmlIndexEntry:
    """Eintrag im XML-Rohdaten-Index"""
    id: int
    external_shipment_id: Optional[str]
    filename: str
    raw_path: str
    file_size: int
    bipro_category: Optional[str]
    vu_name: Optional[str]
    content_hash: Optional[str]
    shipment_date: Optional[str]
    created_at: str
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'XmlIndexEntry':
        return cls(
            id=data['id'],
            external_shipment_id=data.get('external_shipment_id'),
            filename=data['filename'],
            raw_path=data['raw_path'],
            file_size=data.get('file_size', 0),
            bipro_category=data.get('bipro_category'),
            vu_name=data.get('vu_name'),
            content_hash=data.get('content_hash'),
            shipment_date=data.get('shipment_date'),
            created_at=data.get('created_at', '')
        )


class XmlIndexAPI:
    """
    API-Client fuer XML-Rohdaten-Index.
    
    Getrennt von DocumentsAPI, da XML-Rohdaten ein separates Archiv sind.
    """
    
    def __init__(self, client: APIClient):
        self.client = client
    
    def list(self, 
             vu_name: Optional[str] = None,
             bipro_category: Optional[str] = None,
             shipment_id: Optional[str] = None,
             from_date: Optional[str] = None,
             to_date: Optional[str] = None,
             limit: int = 100,
             offset: int = 0) -> List[XmlIndexEntry]:
        """
        Listet indexierte XML-Dateien.
        
        Args:
            vu_name: Filter nach VU-Name
            bipro_category: Filter nach BiPRO-Kategorie
            shipment_id: Filter nach Lieferungs-ID
            from_date: Datum von (YYYY-MM-DD)
            to_date: Datum bis (YYYY-MM-DD)
            limit: Max. Anzahl Ergebnisse
            offset: Offset fuer Pagination
            
        Returns:
            Liste von XmlIndexEntry
        """
        params = {'limit': limit, 'offset': offset}
        
        if vu_name:
            params['vu_name'] = vu_name
        if bipro_category:
            params['bipro_category'] = bipro_category
        if shipment_id:
            params['shipment_id'] = shipment_id
        if from_date:
            params['from'] = from_date
        if to_date:
            params['to'] = to_date
        
        response = self.client.get('/xml_index', params)
        
        if response.get('success'):
            entries = response.get('data', {}).get('entries', [])
            return [XmlIndexEntry.from_dict(e) for e in entries]
        return []
    
    def search(self, query: str) -> List[XmlIndexEntry]:
        """
        Volltextsuche im XML-Index.
        
        Args:
            query: Suchbegriff (min. 3 Zeichen)
            
        Returns:
            Liste von XmlIndexEntry
        """
        if len(query) < 3:
            logger.warning("Suchbegriff zu kurz (min. 3 Zeichen)")
            return []
        
        response = self.client.get('/xml_index/search', {'q': query})
        
        if response.get('success'):
            entries = response.get('data', {}).get('entries', [])
            return [XmlIndexEntry.from_dict(e) for e in entries]
        return []
    
    def get(self, entry_id: int) -> Optional[XmlIndexEntry]:
        """
        Holt einen einzelnen Index-Eintrag.
        
        Args:
            entry_id: ID des Eintrags
            
        Returns:
            XmlIndexEntry oder None
        """
        response = self.client.get(f'/xml_index/{entry_id}')
        
        if response.get('success'):
            return XmlIndexEntry.from_dict(response['data'])
        return None
    
    def create(self,
               filename: str,
               raw_path: str,
               external_shipment_id: Optional[str] = None,
               bipro_category: Optional[str] = None,
               vu_name: Optional[str] = None,
               file_size: int = 0,
               content_hash: Optional[str] = None,
               shipment_date: Optional[str] = None) -> Optional[int]:
        """
        Erstellt neuen Index-Eintrag.
        
        Args:
            filename: Originaler Dateiname
            raw_path: Pfad im Roh-Archiv
            external_shipment_id: BiPRO-Lieferungs-ID
            bipro_category: BiPRO-Kategorie-Code
            vu_name: Name des Versicherers
            file_size: Dateigroesse in Bytes
            content_hash: SHA256-Hash
            shipment_date: Datum der Lieferung
            
        Returns:
            ID des erstellten Eintrags oder None
        """
        data = {
            'filename': filename,
            'raw_path': raw_path,
        }
        
        if external_shipment_id:
            data['external_shipment_id'] = external_shipment_id
        if bipro_category:
            data['bipro_category'] = bipro_category
        if vu_name:
            data['vu_name'] = vu_name
        if file_size:
            data['file_size'] = file_size
        if content_hash:
            data['content_hash'] = content_hash
        if shipment_date:
            data['shipment_date'] = shipment_date
        
        try:
            response = self.client.post('/xml_index', data)
            
            if response.get('success'):
                logger.info(f"XML indexiert: {filename}")
                return response['data']['id']
            return None
        except APIError as e:
            logger.error(f"XML-Index fehlgeschlagen: {e}")
            return None
    
    def delete(self, entry_id: int) -> bool:
        """
        Loescht einen Index-Eintrag.
        
        Args:
            entry_id: ID des Eintrags
            
        Returns:
            True bei Erfolg
        """
        try:
            response = self.client.delete(f'/xml_index/{entry_id}')
            return response.get('success', False)
        except APIError as e:
            logger.error(f"XML-Index Loeschung fehlgeschlagen: {e}")
            return False
    
    def index_xml_file(self,
                       filepath: str,
                       raw_path: str,
                       shipment_id: Optional[str] = None,
                       bipro_category: Optional[str] = None,
                       vu_name: Optional[str] = None,
                       shipment_date: Optional[str] = None) -> Optional[int]:
        """
        Convenience-Methode: Indexiert eine XML-Datei mit automatischer Hash-Berechnung.
        
        Args:
            filepath: Lokaler Pfad zur Datei
            raw_path: Pfad im Roh-Archiv (relativ)
            shipment_id: BiPRO-Lieferungs-ID
            bipro_category: BiPRO-Kategorie
            vu_name: VU-Name
            shipment_date: Lieferungsdatum
            
        Returns:
            ID des erstellten Eintrags oder None
        """
        import os
        import hashlib
        from pathlib import Path
        
        if not os.path.exists(filepath):
            logger.error(f"Datei nicht gefunden: {filepath}")
            return None
        
        # Metadaten extrahieren
        filename = Path(filepath).name
        file_size = os.path.getsize(filepath)
        
        # Hash berechnen
        hasher = hashlib.sha256()
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(65536), b''):
                hasher.update(chunk)
        content_hash = hasher.hexdigest()
        
        return self.create(
            filename=filename,
            raw_path=raw_path,
            external_shipment_id=shipment_id,
            bipro_category=bipro_category,
            vu_name=vu_name,
            file_size=file_size,
            content_hash=content_hash,
            shipment_date=shipment_date
        )
