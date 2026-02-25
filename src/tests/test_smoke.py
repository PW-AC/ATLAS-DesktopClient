"""
Smoke-Tests fuer kritische Pfade der BiPRO-Pipeline

Diese Tests pruefen die grundlegende Funktionalitaet der wichtigsten Komponenten.
Sie sind fuer schnelle Validierung gedacht, nicht fuer vollstaendige Abdeckung.

Ausfuehrung:
    python -m pytest src/tests/test_smoke.py -v
    
    Oder einzeln:
    python -m pytest src/tests/test_smoke.py::TestPDFValidation -v
"""

import pytest
import tempfile
import os
from pathlib import Path
from datetime import datetime


# ==============================================================================
# 1. PDF-Validierung Tests
# ==============================================================================

class TestPDFValidation:
    """Tests fuer PDF-Validierungslogik und Reason-Codes."""
    
    def test_pdf_validation_status_enum_exists(self):
        """PDFValidationStatus Enum ist definiert."""
        from config.processing_rules import PDFValidationStatus
        
        assert hasattr(PDFValidationStatus, 'OK')
        assert hasattr(PDFValidationStatus, 'PDF_ENCRYPTED')
        assert hasattr(PDFValidationStatus, 'PDF_CORRUPT')
        assert hasattr(PDFValidationStatus, 'PDF_INCOMPLETE')
        assert hasattr(PDFValidationStatus, 'PDF_XFA')
        assert hasattr(PDFValidationStatus, 'PDF_REPAIRED')
        assert hasattr(PDFValidationStatus, 'PDF_NO_PAGES')
        assert hasattr(PDFValidationStatus, 'PDF_LOAD_ERROR')
    
    def test_validation_status_values(self):
        """Reason-Code Werte sind korrekt."""
        from config.processing_rules import PDFValidationStatus
        
        assert PDFValidationStatus.OK.value == 'OK'
        assert PDFValidationStatus.PDF_ENCRYPTED.value == 'PDF_ENCRYPTED'
        assert PDFValidationStatus.PDF_CORRUPT.value == 'PDF_CORRUPT'
    
    def test_get_validation_status_description(self):
        """Beschreibungen fuer Validation-Status sind vorhanden."""
        from config.processing_rules import (
            PDFValidationStatus, 
            get_validation_status_description
        )
        
        # OK hat eine Beschreibung
        desc = get_validation_status_description(PDFValidationStatus.OK)
        assert desc is not None
        assert len(desc) > 0
        
        # Alle Status haben Beschreibungen
        for status in PDFValidationStatus:
            desc = get_validation_status_description(status)
            assert desc is not None, f"Keine Beschreibung fuer {status.name}"


# ==============================================================================
# 2. GDV-Fallback Tests
# ==============================================================================

class TestGDVFallback:
    """Tests fuer GDV-Fallback-Werte."""
    
    def test_fallback_constants_exist(self):
        """Fallback-Konstanten sind definiert."""
        from config.processing_rules import GDV_FALLBACK_VU, GDV_FALLBACK_DATE
        
        assert GDV_FALLBACK_VU == 'Xvu'
        assert GDV_FALLBACK_DATE == 'kDatum'
    
    def test_gdv_parse_status_enum(self):
        """GDVParseStatus Enum ist definiert."""
        from config.processing_rules import GDVParseStatus
        
        assert hasattr(GDVParseStatus, 'OK')
        assert hasattr(GDVParseStatus, 'NO_VORSATZ')  # Kein 0001-Satz
        assert hasattr(GDVParseStatus, 'INVALID_FORMAT')


# ==============================================================================
# 3. Atomic Operations Tests
# ==============================================================================

class TestAtomicOperations:
    """Tests fuer atomare Dateioperationen."""
    
    def test_calculate_file_hash(self):
        """Hash-Berechnung funktioniert."""
        from services.atomic_ops import calculate_file_hash
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.txt') as f:
            f.write(b'Test content for hashing')
            f.flush()
            temp_path = f.name
        
        try:
            hash_value = calculate_file_hash(temp_path)
            
            # SHA256 Hash ist 64 Zeichen lang (hex)
            assert hash_value is not None
            assert len(hash_value) == 64
            assert all(c in '0123456789abcdef' for c in hash_value)
            
            # Gleicher Inhalt = gleicher Hash
            hash_value2 = calculate_file_hash(temp_path)
            assert hash_value == hash_value2
        finally:
            os.unlink(temp_path)
    
    def test_verify_file_integrity(self):
        """Integritaetspruefung funktioniert."""
        from services.atomic_ops import calculate_file_hash, verify_file_integrity
        
        content = b'Test content for integrity check'
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.txt') as f:
            f.write(content)
            f.flush()
            temp_path = f.name
        
        try:
            expected_hash = calculate_file_hash(temp_path)
            expected_size = len(content)
            
            # Korrekter Hash und Size
            is_valid, msg = verify_file_integrity(temp_path, expected_size, expected_hash)
            assert is_valid, f"Integrity check failed: {msg}"
            
            # Falscher Size
            is_valid, msg = verify_file_integrity(temp_path, expected_size + 100, expected_hash)
            assert not is_valid
            
            # Falscher Hash
            is_valid, msg = verify_file_integrity(temp_path, expected_size, 'invalid_hash')
            assert not is_valid
        finally:
            os.unlink(temp_path)
    
    def test_safe_atomic_write(self):
        """Atomares Schreiben funktioniert."""
        from services.atomic_ops import safe_atomic_write
        
        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = os.path.join(tmpdir, 'test_file.txt')
            content = b'Atomic write test content'
            
            success, target, file_hash = safe_atomic_write(content, target_path, tmpdir)
            
            assert success, f"Atomic write failed"
            assert os.path.exists(target_path)
            
            with open(target_path, 'rb') as f:
                written_content = f.read()
            
            assert written_content == content
            assert file_hash is not None
            assert len(file_hash) == 64
    
    def test_safe_atomic_move(self):
        """Atomares Verschieben funktioniert."""
        from services.atomic_ops import safe_atomic_move
        
        with tempfile.TemporaryDirectory() as tmpdir:
            source_path = os.path.join(tmpdir, 'source.txt')
            target_path = os.path.join(tmpdir, 'target.txt')
            content = b'Move test content'
            
            # Quelldatei erstellen
            with open(source_path, 'wb') as f:
                f.write(content)
            
            success, msg = safe_atomic_move(source_path, target_path)
            
            assert success, f"Atomic move failed: {msg}"
            assert not os.path.exists(source_path)
            assert os.path.exists(target_path)
            
            with open(target_path, 'rb') as f:
                moved_content = f.read()
            
            assert moved_content == content


# ==============================================================================
# 4. Document State Machine Tests
# ==============================================================================

class TestDocumentStateMachine:
    """Tests fuer Dokument-Zustandsuebergaenge."""
    
    def test_processing_status_enum(self):
        """DocumentProcessingStatus Enum ist definiert."""
        from config.processing_rules import DocumentProcessingStatus
        
        # Neue granulare Stati
        assert hasattr(DocumentProcessingStatus, 'DOWNLOADED')
        assert hasattr(DocumentProcessingStatus, 'VALIDATED')
        assert hasattr(DocumentProcessingStatus, 'CLASSIFIED')
        assert hasattr(DocumentProcessingStatus, 'RENAMED')
        assert hasattr(DocumentProcessingStatus, 'ARCHIVED')
        assert hasattr(DocumentProcessingStatus, 'ERROR')
        
        # Legacy-Stati fuer Abwaertskompatibilitaet
        assert hasattr(DocumentProcessingStatus, 'PENDING')
        assert hasattr(DocumentProcessingStatus, 'PROCESSING')
        assert hasattr(DocumentProcessingStatus, 'COMPLETED')
    
    def test_valid_state_transitions(self):
        """Gueltige Statusuebergaenge werden akzeptiert."""
        from config.processing_rules import DocumentProcessingStatus
        
        # downloaded -> processing
        assert DocumentProcessingStatus.is_valid_transition('downloaded', 'processing')
        
        # processing -> validated
        assert DocumentProcessingStatus.is_valid_transition('processing', 'validated')
        
        # validated -> classified
        assert DocumentProcessingStatus.is_valid_transition('validated', 'classified')
        
        # classified -> renamed
        assert DocumentProcessingStatus.is_valid_transition('classified', 'renamed')
        
        # renamed -> archived
        assert DocumentProcessingStatus.is_valid_transition('renamed', 'archived')
        
        # error ist von jedem Status erreichbar
        assert DocumentProcessingStatus.is_valid_transition('processing', 'error')
        assert DocumentProcessingStatus.is_valid_transition('validated', 'error')
    
    def test_invalid_state_transitions(self):
        """Ungueltige Statusuebergaenge werden abgelehnt."""
        from config.processing_rules import DocumentProcessingStatus
        
        # archived -> downloaded (Rueckwaerts nicht erlaubt)
        assert not DocumentProcessingStatus.is_valid_transition('archived', 'downloaded')
        
        # downloaded -> archived (Schritte ueberspringen nicht erlaubt)
        assert not DocumentProcessingStatus.is_valid_transition('downloaded', 'archived')


# ==============================================================================
# 5. Document API Tests
# ==============================================================================

class TestDocumentDataclass:
    """Tests fuer Document Dataclass."""
    
    def test_document_has_validation_status(self):
        """Document Dataclass hat validation_status Feld."""
        from api.documents import Document
        
        doc = Document(
            id=1,
            filename='test.pdf',
            original_filename='test.pdf',
            validation_status='PDF_ENCRYPTED'
        )
        
        assert doc.validation_status == 'PDF_ENCRYPTED'
    
    def test_document_has_content_hash(self):
        """Document Dataclass hat content_hash Feld."""
        from api.documents import Document
        
        doc = Document(
            id=1,
            filename='test.pdf',
            original_filename='test.pdf',
            content_hash='abc123def456'
        )
        
        assert doc.content_hash == 'abc123def456'
    
    def test_document_has_version_fields(self):
        """Document Dataclass hat Versionierungs-Felder."""
        from api.documents import Document
        
        doc = Document(
            id=2,
            filename='test_v2.pdf',
            original_filename='test.pdf',
            version=2,
            previous_version_id=1
        )
        
        assert doc.version == 2
        assert doc.previous_version_id == 1
        assert doc.is_duplicate  # version > 1
    
    def test_document_has_audit_fields(self):
        """Document Dataclass hat Klassifikations-Audit-Felder."""
        from api.documents import Document
        
        doc = Document(
            id=1,
            filename='test.pdf',
            original_filename='test.pdf',
            classification_source='ki_gpt4o',
            classification_confidence='high',
            classification_reason='KI-Klassifikation erkannte Sach-Dokument',
            classification_timestamp='2026-02-05 10:30:00'
        )
        
        assert doc.classification_source == 'ki_gpt4o'
        assert doc.classification_confidence == 'high'
        assert doc.classification_reason is not None
        assert doc.classification_timestamp is not None
    
    def test_document_from_dict(self):
        """Document.from_dict parst alle Felder korrekt."""
        from api.documents import Document
        
        data = {
            'id': 42,
            'filename': 'doc.pdf',
            'original_filename': 'original.pdf',
            'validation_status': 'OK',
            'content_hash': 'hash123',
            'version': 3,
            'previous_version_id': 41,
            'classification_source': 'rule_bipro',
            'classification_confidence': 'high'
        }
        
        doc = Document.from_dict(data)
        
        assert doc.id == 42
        assert doc.validation_status == 'OK'
        assert doc.content_hash == 'hash123'
        assert doc.version == 3
        assert doc.previous_version_id == 41
        assert doc.classification_source == 'rule_bipro'


# ==============================================================================
# 6. Processing History Tests
# ==============================================================================

class TestProcessingHistory:
    """Tests fuer Processing-History Dataclass."""
    
    def test_history_entry_dataclass(self):
        """HistoryEntry Dataclass ist definiert."""
        from api.processing_history import HistoryEntry
        
        entry = HistoryEntry(
            id=1,
            document_id=100,
            previous_status='processing',
            new_status='classified',
            action='classify',
            action_details={'category': 'sach'},
            success=True,
            error_message=None,
            classification_source='ki_gpt4o',
            classification_result='sparte_sach',
            duration_ms=1500,
            created_at='2026-02-05 10:30:00',
            created_by='system'
        )
        
        assert entry.document_id == 100
        assert entry.success is True
        assert entry.classification_source == 'ki_gpt4o'
    
    def test_history_entry_from_dict(self):
        """HistoryEntry.from_dict parst korrekt."""
        from api.processing_history import HistoryEntry
        
        data = {
            'id': 5,
            'document_id': 200,
            'previous_status': 'downloaded',
            'new_status': 'processing',
            'action': 'start_processing',
            'success': True,
            'created_at': '2026-02-05 10:00:00'
        }
        
        entry = HistoryEntry.from_dict(data)
        
        assert entry.id == 5
        assert entry.document_id == 200
        assert entry.action == 'start_processing'


# ==============================================================================
# 7. XML Index Tests
# ==============================================================================

class TestXmlIndex:
    """Tests fuer XML-Index Dataclass."""
    
    def test_xml_index_entry_dataclass(self):
        """XmlIndexEntry Dataclass ist definiert."""
        from api.xml_index import XmlIndexEntry
        
        entry = XmlIndexEntry(
            id=1,
            external_shipment_id='SHIP-001',
            filename='response.xml',
            raw_path='roh/2026/02/response.xml',
            file_size=1024,
            bipro_category='999010010',
            vu_name='Allianz',
            content_hash='abc123',
            shipment_date='2026-02-05 09:00:00',
            created_at='2026-02-05 09:05:00'
        )
        
        assert entry.external_shipment_id == 'SHIP-001'
        assert entry.bipro_category == '999010010'


# ==============================================================================
# 8. Integration Tests (Optional - erfordern API-Zugang)
# ==============================================================================

@pytest.mark.skip(reason="Erfordert laufende Backend-API")
class TestAPIIntegration:
    """Integrationstests fuer Backend-API (manuell aktivieren)."""
    
    def test_documents_api_list(self):
        """DocumentsAPI kann Dokumente auflisten."""
        from api.client import APIClient
        from api.documents import DocumentsAPI
        
        # Hier muessen echte Credentials verwendet werden
        client = APIClient(base_url='https://acencia.info/api')
        client.login('test', 'test')
        
        docs_api = DocumentsAPI(client)
        docs, total = docs_api.list(limit=5)
        
        assert isinstance(docs, list)
        assert isinstance(total, int)


# ==============================================================================
# Main
# ==============================================================================

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
