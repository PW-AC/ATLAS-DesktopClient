"""
BiPro API - GDV-Operationen

Parsen, Records laden/speichern, Export.
"""

from typing import List, Optional, Dict, Any
from dataclasses import dataclass
import logging
import tempfile
import os

from .client import APIClient, APIError

logger = logging.getLogger(__name__)


@dataclass
class GDVFileMeta:
    """GDV-Datei Metadaten."""
    id: int
    document_id: int
    encoding: str
    release_version: Optional[str]
    vu_number: Optional[str]
    record_count: int
    parsed_at: Optional[str]
    original_filename: str
    
    @classmethod
    def from_dict(cls, data: Dict, doc_filename: str = "") -> 'GDVFileMeta':
        return cls(
            id=data['id'],
            document_id=data['document_id'],
            encoding=data.get('encoding', 'CP1252'),
            release_version=data.get('release_version'),
            vu_number=data.get('vu_number'),
            record_count=data.get('record_count', 0),
            parsed_at=data.get('parsed_at'),
            original_filename=doc_filename or data.get('original_filename', '')
        )


@dataclass
class GDVRecord:
    """Ein GDV-Record vom Server."""
    id: int
    gdv_file_id: int
    line_number: int
    satzart: str
    teildatensatz: int
    raw_content: str
    parsed_fields: Optional[Dict]
    is_modified: bool
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'GDVRecord':
        return cls(
            id=data['id'],
            gdv_file_id=data['gdv_file_id'],
            line_number=data['line_number'],
            satzart=data['satzart'],
            teildatensatz=data.get('teildatensatz', 1),
            raw_content=data['raw_content'],
            parsed_fields=data.get('parsed_fields'),
            is_modified=bool(data.get('is_modified', False))
        )


class GDVAPI:
    """
    GDV-API für Server-Operationen.
    
    Verwendung:
        gdv_api = GDVAPI(client)
        meta = gdv_api.parse_document(doc_id)
        records = gdv_api.get_records(doc_id)
    """
    
    def __init__(self, client: APIClient):
        self.client = client
    
    def get_meta(self, doc_id: int) -> Optional[GDVFileMeta]:
        """
        GDV-Metadaten abrufen.
        
        Args:
            doc_id: Dokument-ID
            
        Returns:
            GDVFileMeta oder None
        """
        try:
            response = self.client.get(f'/gdv/{doc_id}')
            if response.get('success'):
                data = response['data']['gdv_file']
                return GDVFileMeta.from_dict(data)
        except APIError as e:
            logger.error(f"GDV-Meta laden fehlgeschlagen: {e}")
        return None
    
    def parse_document(self, doc_id: int) -> Optional[GDVFileMeta]:
        """
        GDV-Dokument auf dem Server parsen.
        
        Args:
            doc_id: Dokument-ID
            
        Returns:
            GDVFileMeta oder None
        """
        try:
            response = self.client.post(f'/gdv/{doc_id}/parse')
            if response.get('success'):
                data = response['data']
                return GDVFileMeta(
                    id=data['gdv_file_id'],
                    document_id=doc_id,
                    encoding=data.get('encoding', 'CP1252'),
                    release_version=None,
                    vu_number=data.get('vu_number'),
                    record_count=data.get('record_count', 0),
                    parsed_at=None,
                    original_filename=''
                )
        except APIError as e:
            logger.error(f"GDV-Parsen fehlgeschlagen: {e}")
        return None
    
    def get_records(self, doc_id: int, 
                    satzart: Optional[str] = None,
                    teildatensatz: Optional[int] = None,
                    limit: int = 5000,
                    offset: int = 0) -> List[GDVRecord]:
        """
        GDV-Records abrufen.
        
        Args:
            doc_id: Dokument-ID
            satzart: Filter nach Satzart (optional)
            teildatensatz: Filter nach Teildatensatz (optional)
            limit: Max. Anzahl Records
            offset: Start-Offset
            
        Returns:
            Liste von GDVRecord
        """
        params = {
            'limit': limit,
            'offset': offset
        }
        if satzart:
            params['satzart'] = satzart
        if teildatensatz:
            params['teildatensatz'] = teildatensatz
        
        try:
            response = self.client.get(f'/gdv/{doc_id}/records', params=params)
            if response.get('success'):
                return [GDVRecord.from_dict(r) for r in response['data']['records']]
        except APIError as e:
            logger.error(f"GDV-Records laden fehlgeschlagen: {e}")
        return []
    
    def update_records(self, doc_id: int, records: List[Dict]) -> int:
        """
        GDV-Records aktualisieren.
        
        Args:
            doc_id: Dokument-ID
            records: Liste von {'id': int, 'raw_content': str}
            
        Returns:
            Anzahl aktualisierter Records
        """
        try:
            response = self.client.put(f'/gdv/{doc_id}/records', json_data={
                'records': records
            })
            if response.get('success'):
                return response['data'].get('updated', 0)
        except APIError as e:
            logger.error(f"GDV-Records speichern fehlgeschlagen: {e}")
        return 0
    
    def export_to_file(self, doc_id: int, target_path: str) -> Optional[str]:
        """
        GDV-Datei vom Server exportieren.
        
        Args:
            doc_id: Dokument-ID
            target_path: Zielpfad
            
        Returns:
            Pfad zur Datei oder None
        """
        try:
            return self.client.download_file(f'/gdv/{doc_id}/export', target_path)
        except APIError as e:
            logger.error(f"GDV-Export fehlgeschlagen: {e}")
        return None
    
    def download_and_get_path(self, doc_id: int) -> Optional[str]:
        """
        GDV-Datei herunterladen und temporären Pfad zurückgeben.
        
        Für lokale Bearbeitung mit dem GDV-Parser.
        
        Args:
            doc_id: Dokument-ID
            
        Returns:
            Pfad zur temporären Datei oder None
        """
        try:
            # Temporäre Datei erstellen
            temp_dir = tempfile.mkdtemp(prefix='bipro_gdv_')
            temp_path = os.path.join(temp_dir, f'gdv_{doc_id}.gdv')
            
            # Herunterladen
            result = self.client.download_file(f'/documents/{doc_id}', temp_path)
            
            if result and os.path.exists(result):
                return result
            return None
        except APIError as e:
            logger.error(f"GDV-Download fehlgeschlagen: {e}")
        return None
