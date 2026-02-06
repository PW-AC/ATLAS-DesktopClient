"""
BiPro API - Dokumente

Upload, Download, Verwaltung von Dokumenten mit Box-System.
"""

from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime
import logging
from pathlib import Path

from .client import APIClient, APIError

logger = logging.getLogger(__name__)


# Box-Typen und ihre Anzeige-Reihenfolge
BOX_TYPES = ['eingang', 'verarbeitung', 'gdv', 'courtage', 'sach', 'leben', 'kranken', 'sonstige', 'roh']

BOX_DISPLAY_NAMES = {
    'eingang': 'Eingangs Box',
    'verarbeitung': 'Verarbeitungs Box',
    'gdv': 'GDV Box',
    'courtage': 'Courtage Box',
    'sach': 'Sach Box',
    'leben': 'Leben Box',
    'kranken': 'Kranken Box',
    'sonstige': 'Sonstige Box',
    'roh': 'Roh Archiv',
}

# Box-Farben - Harmonisch mit ACENCIA CI
# Weniger gesättigt, professioneller Look
BOX_COLORS = {
    'eingang': '#f59e0b',      # Amber - Attention
    'verarbeitung': '#f97316', # Orange - In Progress
    'gdv': '#10b981',          # Grün - Primäre Daten
    'courtage': '#6366f1',     # Indigo - Finanzdaten
    'sach': '#3b82f6',         # Blau - Versicherungstyp
    'leben': '#8b5cf6',        # Violett - Versicherungstyp
    'kranken': '#06b6d4',      # Cyan - Versicherungstyp
    'sonstige': '#64748b',     # Grau - Neutral
    'roh': '#78716c',          # Steingrau - Archiv/System
}


@dataclass
class Document:
    """Dokument aus dem Archiv"""
    id: int
    filename: str
    original_filename: str
    mime_type: Optional[str]
    file_size: int
    source_type: str  # 'bipro_auto', 'manual_upload', 'self_created'
    is_gdv: bool
    created_at: str
    uploaded_by_name: Optional[str] = None
    vu_name: Optional[str] = None
    shipment_id: Optional[int] = None
    ai_renamed: bool = False
    ai_processing_error: Optional[str] = None
    # Neue Box-System Felder
    box_type: str = 'sonstige'
    processing_status: str = 'completed'
    document_category: Optional[str] = None
    # BiPRO-Kategorie fuer regelbasierte Sortierung
    bipro_category: Optional[str] = None
    # PDF-Validierungsstatus (technisch, unabhaengig von document_category)
    validation_status: Optional[str] = None
    # SHA256-Hash des Dateiinhalts fuer Deduplizierung/Idempotenz
    content_hash: Optional[str] = None
    # Versionierung bei Mehrfachlieferungen
    version: int = 1
    previous_version_id: Optional[int] = None
    # Klassifikations-Audit-Metadaten
    classification_source: Optional[str] = None       # ki_gpt4o, rule_bipro, fallback, etc.
    classification_confidence: Optional[str] = None   # high, medium, low
    classification_reason: Optional[str] = None       # Begruendung
    classification_timestamp: Optional[str] = None    # ISO-Zeitstempel
    # Erweiterte Idempotenz-Felder
    bipro_document_id: Optional[str] = None           # Eindeutige ID aus BiPRO-Response
    source_xml_index_id: Optional[int] = None         # Relation zur XML-Quell-Lieferung
    external_shipment_id: Optional[str] = None        # BiPRO-Lieferungs-ID (extern)
    # Archivierungs-Status (nach Download)
    is_archived: bool = False
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Document':
        return cls(
            id=data['id'],
            filename=data['filename'],
            original_filename=data.get('original_filename', data['filename']),
            mime_type=data.get('mime_type'),
            file_size=data.get('file_size', 0),
            source_type=data.get('source_type', 'manual_upload'),
            is_gdv=bool(data.get('is_gdv', False)),
            created_at=data.get('created_at', ''),
            uploaded_by_name=data.get('uploaded_by_name'),
            vu_name=data.get('vu_name'),
            shipment_id=data.get('shipment_id'),
            ai_renamed=bool(data.get('ai_renamed', False)),
            ai_processing_error=data.get('ai_processing_error'),
            box_type=data.get('box_type', 'sonstige'),
            processing_status=data.get('processing_status', 'completed'),
            document_category=data.get('document_category'),
            bipro_category=data.get('bipro_category'),
            validation_status=data.get('validation_status'),
            content_hash=data.get('content_hash'),
            version=data.get('version', 1),
            previous_version_id=data.get('previous_version_id'),
            classification_source=data.get('classification_source'),
            classification_confidence=data.get('classification_confidence'),
            classification_reason=data.get('classification_reason'),
            classification_timestamp=data.get('classification_timestamp'),
            bipro_document_id=data.get('bipro_document_id'),
            source_xml_index_id=data.get('source_xml_index_id'),
            external_shipment_id=data.get('external_shipment_id'),
            is_archived=bool(data.get('is_archived', False))
        )
    
    @property
    def is_duplicate(self) -> bool:
        """Prueft ob dieses Dokument ein Duplikat (Version > 1) ist."""
        return self.version > 1
    
    @property
    def is_pdf(self) -> bool:
        """Prueft ob das Dokument ein PDF ist."""
        return (self.mime_type == 'application/pdf' or 
                self.original_filename.lower().endswith('.pdf'))
    
    @property
    def is_xml(self) -> bool:
        """Prueft ob das Dokument eine XML-Datei ist."""
        return (self.mime_type in ['application/xml', 'text/xml'] or 
                self.original_filename.lower().endswith('.xml'))
    
    @property
    def source_type_display(self) -> str:
        """Anzeigename fuer Quelle."""
        if self.source_type == 'bipro_auto' or self.source_type.startswith('bipro_'):
            if self.vu_name:
                return self.vu_name  # Nur VU-Name ohne "BiPRO:" Prefix
            return "BiPRO"
        
        mapping = {
            'manual_upload': 'Manuell',
            'self_created': 'Selbst erstellt'
        }
        return mapping.get(self.source_type, self.source_type)
    
    @property
    def box_type_display(self) -> str:
        """Anzeigename fuer Box."""
        return BOX_DISPLAY_NAMES.get(self.box_type, self.box_type)
    
    @property
    def box_color(self) -> str:
        """Farbe fuer die Box."""
        return BOX_COLORS.get(self.box_type, '#9E9E9E')
    
    @property
    def file_size_display(self) -> str:
        """Dateigroesse formatiert."""
        if self.file_size < 1024:
            return f"{self.file_size} B"
        elif self.file_size < 1024 * 1024:
            return f"{self.file_size / 1024:.1f} KB"
        else:
            return f"{self.file_size / 1024 / 1024:.1f} MB"
    
    @property
    def file_extension(self) -> str:
        """Dateiendung (lowercase, mit Punkt)."""
        if '.' in self.original_filename:
            return '.' + self.original_filename.rsplit('.', 1)[1].lower()
        return ''


@dataclass
class BoxStats:
    """Statistiken fuer alle Boxen."""
    eingang: int = 0
    verarbeitung: int = 0
    gdv: int = 0
    courtage: int = 0
    sach: int = 0
    leben: int = 0
    kranken: int = 0
    sonstige: int = 0
    roh: int = 0
    total: int = 0
    # Archivierte Zaehlungen
    gdv_archived: int = 0
    courtage_archived: int = 0
    sach_archived: int = 0
    leben_archived: int = 0
    kranken_archived: int = 0
    sonstige_archived: int = 0
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'BoxStats':
        return cls(
            eingang=data.get('eingang', 0),
            verarbeitung=data.get('verarbeitung', 0),
            gdv=data.get('gdv', 0),
            courtage=data.get('courtage', 0),
            sach=data.get('sach', 0),
            leben=data.get('leben', 0),
            kranken=data.get('kranken', 0),
            sonstige=data.get('sonstige', 0),
            roh=data.get('roh', 0),
            total=data.get('total', 0),
            # Archivierte
            gdv_archived=data.get('gdv_archived', 0),
            courtage_archived=data.get('courtage_archived', 0),
            sach_archived=data.get('sach_archived', 0),
            leben_archived=data.get('leben_archived', 0),
            kranken_archived=data.get('kranken_archived', 0),
            sonstige_archived=data.get('sonstige_archived', 0)
        )
    
    def get_count(self, box_type: str) -> int:
        """Gibt die Anzahl fuer einen Box-Typ zurueck."""
        return getattr(self, box_type, 0)


class DocumentsAPI:
    """
    Dokumenten-API mit Box-System.
    
    Verwendung:
        docs_api = DocumentsAPI(client)
        documents = docs_api.list_documents()
        docs_api.list_by_box('gdv')
        docs_api.get_box_stats()
        docs_api.move_documents([1, 2, 3], 'sach')
    """
    
    def __init__(self, client: APIClient):
        self.client = client
    
    def list_documents(self, 
                       box_type: Optional[str] = None,
                       vu_id: Optional[int] = None,
                       source: Optional[str] = None,
                       is_gdv: Optional[bool] = None,
                       from_date: Optional[str] = None,
                       to_date: Optional[str] = None,
                       processing_status: Optional[str] = None,
                       is_archived: Optional[bool] = None) -> List[Document]:
        """
        Liste aller Dokumente abrufen.
        
        Args:
            box_type: Filter nach Box ('eingang', 'verarbeitung', 'gdv', etc.)
            vu_id: Filter nach VU
            source: Filter nach Quelle ('bipro_auto', 'manual_upload', 'self_created')
            is_gdv: Nur GDV-Dateien
            is_archived: Filter nach Archivierungs-Status (True/False/None=alle)
            from_date: Ab Datum (YYYY-MM-DD)
            to_date: Bis Datum (YYYY-MM-DD)
            processing_status: Filter nach Verarbeitungsstatus
            
        Returns:
            Liste von Document-Objekten
        """
        params = {}
        if box_type:
            params['box'] = box_type
        if vu_id:
            params['vu'] = vu_id
        if source:
            params['source'] = source
        if is_gdv is not None:
            params['is_gdv'] = '1' if is_gdv else '0'
        if from_date:
            params['from'] = from_date
        if to_date:
            params['to'] = to_date
        if processing_status:
            params['processing_status'] = processing_status
        if is_archived is not None:
            params['is_archived'] = '1' if is_archived else '0'
        
        try:
            response = self.client.get('/documents', params=params)
            if response.get('success'):
                return [Document.from_dict(d) for d in response['data']['documents']]
            return []
        except APIError as e:
            logger.error(f"Dokumente laden fehlgeschlagen: {e}")
            return []
    
    def list_by_box(self, box_type: str) -> List[Document]:
        """
        Dokumente einer bestimmten Box abrufen.
        
        Args:
            box_type: Box-Typ ('eingang', 'verarbeitung', 'gdv', etc.)
            
        Returns:
            Liste von Document-Objekten
        """
        return self.list_documents(box_type=box_type)
    
    def get_box_stats(self) -> BoxStats:
        """
        Statistiken fuer alle Boxen abrufen.
        
        Returns:
            BoxStats-Objekt mit Anzahl pro Box
        """
        try:
            response = self.client.get('/documents/stats')
            if response.get('success'):
                return BoxStats.from_dict(response['data'])
            return BoxStats()
        except APIError as e:
            logger.error(f"Box-Statistiken laden fehlgeschlagen: {e}")
            return BoxStats()
    
    def move_documents(self, doc_ids: List[int], target_box: str) -> int:
        """
        Dokumente in eine andere Box verschieben.
        
        Args:
            doc_ids: Liste von Dokument-IDs
            target_box: Ziel-Box ('gdv', 'courtage', 'sach', etc.)
            
        Returns:
            Anzahl verschobener Dokumente
        """
        if not doc_ids:
            return 0
        
        try:
            response = self.client.post('/documents/move', json_data={
                'document_ids': doc_ids,
                'target_box': target_box
            })
            if response.get('success'):
                moved = response['data'].get('moved_count', 0)
                logger.info(f"{moved} Dokument(e) nach '{target_box}' verschoben")
                return moved
            return 0
        except APIError as e:
            logger.error(f"Verschieben fehlgeschlagen: {e}")
            return 0
    
    def get_document(self, doc_id: int) -> Optional[Document]:
        """Einzelnes Dokument abrufen."""
        docs = self.list_documents()
        for doc in docs:
            if doc.id == doc_id:
                return doc
        return None
    
    def upload(self, file_path: str, 
               source_type: str = 'manual_upload',
               shipment_id: Optional[str] = None,
               vu_name: Optional[str] = None,
               box_type: str = 'eingang',
               bipro_category: Optional[str] = None,
               validation_status: Optional[str] = None) -> Optional[Document]:
        """
        Dokument hochladen.
        
        Args:
            file_path: Pfad zur Datei
            source_type: Quelle ('manual_upload', 'self_created', 'bipro_auto')
            shipment_id: Zugehoerige BiPRO-Lieferungs-ID (optional)
            vu_name: Name des Versicherers (optional, fuer BiPRO)
            box_type: Ziel-Box (Standard: 'eingang')
            bipro_category: BiPRO-Kategorie-Code (z.B. '300001000' fuer Provision)
            validation_status: PDF-Validierungsstatus (OK, PDF_ENCRYPTED, PDF_CORRUPT, etc.)
            
        Returns:
            Erstelltes Document oder None bei Fehler
        """
        additional_data = {
            'source_type': source_type,
            'box_type': box_type
        }
        if shipment_id:
            additional_data['shipment_id'] = str(shipment_id)
        if vu_name:
            additional_data['vu_name'] = vu_name
        if bipro_category:
            additional_data['bipro_category'] = bipro_category
        if validation_status:
            additional_data['validation_status'] = validation_status
        
        try:
            response = self.client.upload_file(
                '/documents',
                file_path,
                additional_data
            )
            
            if response.get('success'):
                data = response['data']
                logger.info(f"Dokument hochgeladen: {data.get('original_filename')} -> Box: {box_type}, BiPRO-Kat: {bipro_category}")
                
                # Minimales Document-Objekt zurueckgeben
                return Document(
                    id=data['id'],
                    filename=data['filename'],
                    original_filename=data.get('original_filename', data['filename']),
                    mime_type=None,
                    file_size=0,
                    source_type=source_type,
                    is_gdv=data.get('is_gdv', False),
                    created_at=datetime.now().isoformat(),
                    box_type=data.get('box_type', box_type),
                    processing_status=data.get('processing_status', 'pending'),
                    bipro_category=data.get('bipro_category', bipro_category)
                )
            return None
        except APIError as e:
            logger.error(f"Upload fehlgeschlagen: {e}")
            return None
    
    def download(self, doc_id: int, target_dir: str, 
                  filename_override: Optional[str] = None) -> Optional[str]:
        """
        Dokument herunterladen mit robuster Fehlerbehandlung.
        
        Args:
            doc_id: Dokument-ID
            target_dir: Zielverzeichnis
            filename_override: Optionaler Dateiname (sonst original_filename)
            
        Returns:
            Pfad zur heruntergeladenen Datei oder None
        """
        # Erst Dokument-Info holen für Dateinamen
        doc = self.get_document(doc_id)
        if not doc:
            logger.error(f"Dokument {doc_id} nicht gefunden")
            return None
        
        # Dateinamen bestimmen
        filename = filename_override or doc.original_filename
        
        # Sicherstellen, dass Zielverzeichnis existiert
        target_dir_path = Path(target_dir)
        if not target_dir_path.exists():
            try:
                target_dir_path.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                logger.error(f"Konnte Zielverzeichnis nicht erstellen: {e}")
                return None
        
        target_path = target_dir_path / filename
        
        # Bei Namenskollision: Suffix hinzufuegen
        if target_path.exists():
            base = target_path.stem
            ext = target_path.suffix
            counter = 1
            while target_path.exists():
                target_path = target_dir_path / f"{base}_{counter}{ext}"
                counter += 1
            logger.info(f"Datei existiert, verwende: {target_path.name}")
        
        try:
            result = self.client.download_file(
                f'/documents/{doc_id}',
                str(target_path)
            )
            logger.info(f"Dokument heruntergeladen: {result}")
            return result
        except APIError as e:
            logger.error(f"Download fehlgeschlagen fuer Dokument {doc_id}: {e}")
            # Teilweise geschriebene Datei entfernen
            if target_path.exists():
                try:
                    target_path.unlink()
                except OSError:
                    pass
            return None
    
    def delete(self, doc_id: int) -> bool:
        """
        Dokument löschen.
        
        Args:
            doc_id: Dokument-ID
            
        Returns:
            True wenn erfolgreich
        """
        try:
            response = self.client.delete(f'/documents/{doc_id}')
            if response.get('success'):
                logger.info(f"Dokument {doc_id} gelöscht")
                return True
            return False
        except APIError as e:
            logger.error(f"Löschen fehlgeschlagen: {e}")
            return False
    
    def get_gdv_documents(self) -> List[Document]:
        """Nur GDV-Dateien abrufen."""
        return self.list_documents(is_gdv=True)
    
    def update(self, doc_id: int, 
               original_filename: Optional[str] = None,
               ai_renamed: Optional[bool] = None,
               ai_processing_error: Optional[str] = None,
               box_type: Optional[str] = None,
               processing_status: Optional[str] = None,
               document_category: Optional[str] = None,
               validation_status: Optional[str] = None,
               classification_source: Optional[str] = None,
               classification_confidence: Optional[str] = None,
               classification_reason: Optional[str] = None,
               classification_timestamp: Optional[str] = None,
               content_hash: Optional[str] = None,
               bipro_document_id: Optional[str] = None,
               source_xml_index_id: Optional[int] = None,
               is_archived: Optional[bool] = None) -> bool:
        """
        Dokument-Metadaten aktualisieren.
        
        Args:
            doc_id: Dokument-ID
            original_filename: Neuer Dateiname
            ai_renamed: KI-Umbenennung abgeschlossen
            ai_processing_error: Fehlermeldung bei KI-Verarbeitung
            box_type: Neue Box
            processing_status: Neuer Verarbeitungsstatus
            document_category: Dokumenten-Kategorie
            validation_status: Validierungsstatus (OK, PDF_CORRUPT, etc.)
            classification_source: Klassifikationsquelle (ki_gpt4o, rule_bipro, etc.)
            classification_confidence: Konfidenz (high, medium, low)
            classification_reason: Begruendung der Klassifikation
            classification_timestamp: ISO-Zeitstempel der Klassifikation
            content_hash: SHA256 Hash des Inhalts
            bipro_document_id: BiPRO Dokument-ID
            source_xml_index_id: Relation zur XML-Quell-Lieferung
            is_archived: Archivierungs-Status (nach Download)
            
        Returns:
            True wenn erfolgreich
        """
        data = {}
        if original_filename is not None:
            data['original_filename'] = original_filename
        if ai_renamed is not None:
            data['ai_renamed'] = 1 if ai_renamed else 0
        if ai_processing_error is not None:
            data['ai_processing_error'] = ai_processing_error
        if box_type is not None:
            data['box_type'] = box_type
        if processing_status is not None:
            data['processing_status'] = processing_status
        if document_category is not None:
            data['document_category'] = document_category
        if validation_status is not None:
            data['validation_status'] = validation_status
        if classification_source is not None:
            data['classification_source'] = classification_source
        if classification_confidence is not None:
            data['classification_confidence'] = classification_confidence
        if classification_reason is not None:
            data['classification_reason'] = classification_reason
        if classification_timestamp is not None:
            data['classification_timestamp'] = classification_timestamp
        if content_hash is not None:
            data['content_hash'] = content_hash
        if bipro_document_id is not None:
            data['bipro_document_id'] = bipro_document_id
        if source_xml_index_id is not None:
            data['source_xml_index_id'] = source_xml_index_id
        if is_archived is not None:
            data['is_archived'] = 1 if is_archived else 0
        
        if not data:
            logger.warning("Keine Aenderungen angegeben")
            return False
        
        try:
            response = self.client.put(f'/documents/{doc_id}', json_data=data)
            if response.get('success'):
                logger.info(f"Dokument {doc_id} aktualisiert: {list(data.keys())}")
                return True
            return False
        except APIError as e:
            logger.error(f"Update fehlgeschlagen: {e}")
            return False
    
    def rename_document(self, doc_id: int, new_filename: str, mark_ai_renamed: bool = True) -> bool:
        """
        Dokument umbenennen (Convenience-Methode).
        
        Args:
            doc_id: Dokument-ID
            new_filename: Neuer Dateiname
            mark_ai_renamed: Als KI-umbenannt markieren
            
        Returns:
            True wenn erfolgreich
        """
        return self.update(
            doc_id,
            original_filename=new_filename,
            ai_renamed=mark_ai_renamed if mark_ai_renamed else None
        )
    
    def archive_document(self, doc_id: int) -> bool:
        """
        Dokument archivieren (nach Download).
        
        Archivierte Dokumente werden in den normalen Box-Ansichten ausgeblendet
        und nur noch in der "Archiviert"-Sub-Box und im Gesamt-Archiv angezeigt.
        
        Args:
            doc_id: Dokument-ID
            
        Returns:
            True wenn erfolgreich
        """
        logger.info(f"Archiviere Dokument {doc_id}")
        return self.update(doc_id, is_archived=True)
    
    def unarchive_document(self, doc_id: int) -> bool:
        """
        Dokument entarchivieren.
        
        Das Dokument wird wieder in der normalen Box-Ansicht angezeigt.
        
        Args:
            doc_id: Dokument-ID
            
        Returns:
            True wenn erfolgreich
        """
        logger.info(f"Entarchiviere Dokument {doc_id}")
        return self.update(doc_id, is_archived=False)
    
    def archive_documents(self, doc_ids: List[int]) -> int:
        """
        Mehrere Dokumente archivieren.
        
        Args:
            doc_ids: Liste von Dokument-IDs
            
        Returns:
            Anzahl erfolgreich archivierter Dokumente
        """
        count = 0
        for doc_id in doc_ids:
            if self.archive_document(doc_id):
                count += 1
        return count
    
    def unarchive_documents(self, doc_ids: List[int]) -> int:
        """
        Mehrere Dokumente entarchivieren.
        
        Args:
            doc_ids: Liste von Dokument-IDs
            
        Returns:
            Anzahl erfolgreich entarchivierter Dokumente
        """
        count = 0
        for doc_id in doc_ids:
            if self.unarchive_document(doc_id):
                count += 1
        return count
    
    def get_unrenamed_pdfs(self) -> List[Document]:
        """Alle PDFs abrufen, die noch nicht durch KI umbenannt wurden."""
        all_docs = self.list_documents()
        return [d for d in all_docs if d.is_pdf and not d.ai_renamed]
