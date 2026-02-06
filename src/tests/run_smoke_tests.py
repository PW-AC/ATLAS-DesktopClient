"""
Einfacher Smoke-Test-Runner ohne pytest Abhaengigkeit

Fuehrt alle kritischen Validierungen durch und gibt einen Report aus.

Ausfuehrung:
    python src/tests/run_smoke_tests.py
"""

import sys
import os
import tempfile
import traceback
from pathlib import Path
from datetime import datetime

# Projekt-Root zum Pfad hinzufuegen
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / 'src'))

# Test-Ergebnisse
passed = 0
failed = 0
errors = []


def test(name):
    """Decorator fuer Tests."""
    def decorator(func):
        def wrapper():
            global passed, failed, errors
            try:
                func()
                print(f"  [OK] {name}")
                passed += 1
            except AssertionError as e:
                print(f"  [FAIL] {name}")
                print(f"         Assertion: {e}")
                failed += 1
                errors.append((name, str(e)))
            except Exception as e:
                print(f"  [ERROR] {name}")
                print(f"          {type(e).__name__}: {e}")
                failed += 1
                errors.append((name, f"{type(e).__name__}: {e}"))
        return wrapper
    return decorator


# ==============================================================================
# TESTS
# ==============================================================================

print("\n" + "=" * 70)
print("BiPRO Pipeline - Smoke Tests")
print("=" * 70)
print(f"Ausfuehrung: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")


# --- 1. PDF-Validierung ---
print("\n[1] PDF-Validierung")
print("-" * 40)

@test("PDFValidationStatus Enum existiert")
def test_pdf_validation_status_enum():
    from config.processing_rules import PDFValidationStatus
    assert hasattr(PDFValidationStatus, 'OK')
    assert hasattr(PDFValidationStatus, 'PDF_ENCRYPTED')
    assert hasattr(PDFValidationStatus, 'PDF_CORRUPT')
    assert hasattr(PDFValidationStatus, 'PDF_INCOMPLETE')
    assert hasattr(PDFValidationStatus, 'PDF_XFA')

test_pdf_validation_status_enum()

@test("Validation-Status Beschreibungen vorhanden")
def test_validation_descriptions():
    from config.processing_rules import PDFValidationStatus, get_validation_status_description
    for status in PDFValidationStatus:
        desc = get_validation_status_description(status)
        assert desc is not None and len(desc) > 0, f"Keine Beschreibung fuer {status.name}"

test_validation_descriptions()


# --- 2. GDV-Fallback ---
print("\n[2] GDV-Fallback")
print("-" * 40)

@test("GDV Fallback-Konstanten definiert")
def test_gdv_fallback_constants():
    from config.processing_rules import GDV_FALLBACK_VU, GDV_FALLBACK_DATE
    assert GDV_FALLBACK_VU == 'Xvu'
    assert GDV_FALLBACK_DATE == 'kDatum'

test_gdv_fallback_constants()

@test("GDVParseStatus Enum existiert")
def test_gdv_parse_status():
    from config.processing_rules import GDVParseStatus
    assert hasattr(GDVParseStatus, 'OK')
    assert hasattr(GDVParseStatus, 'NO_VORSATZ')  # Kein 0001-Satz

test_gdv_parse_status()


# --- 3. Atomic Operations ---
print("\n[3] Atomic Operations")
print("-" * 40)

# Import-Test fuer atomic_ops zuerst
try:
    from services.atomic_ops import calculate_file_hash, verify_file_integrity, safe_atomic_write
    atomic_ops_available = True
except ImportError as e:
    print(f"  [SKIP] Atomic Operations Module nicht ladbar: {e}")
    atomic_ops_available = False

if atomic_ops_available:
    @test("calculate_file_hash funktioniert")
    def test_calculate_hash():
        with tempfile.NamedTemporaryFile(delete=False, suffix='.txt') as f:
            f.write(b'Test content')
            f.flush()
            temp_path = f.name
        
        try:
            hash_value = calculate_file_hash(temp_path)
            assert hash_value is not None
            assert len(hash_value) == 64  # SHA256 hex
        finally:
            os.unlink(temp_path)
    
    test_calculate_hash()
    
    @test("verify_file_integrity funktioniert")
    def test_verify_integrity():
        content = b'Integrity test'
        with tempfile.NamedTemporaryFile(delete=False, suffix='.txt') as f:
            f.write(content)
            f.flush()
            temp_path = f.name
        
        try:
            expected_hash = calculate_file_hash(temp_path)
            is_valid, _ = verify_file_integrity(temp_path, len(content), expected_hash)
            assert is_valid
            
            # Falscher Hash
            is_valid, _ = verify_file_integrity(temp_path, len(content), 'wrong_hash')
            assert not is_valid
        finally:
            os.unlink(temp_path)
    
    test_verify_integrity()
    
    @test("safe_atomic_write funktioniert")
    def test_atomic_write():
        with tempfile.TemporaryDirectory() as tmpdir:
            target = os.path.join(tmpdir, 'test.txt')
            content = b'Atomic write'
            
            success, _, file_hash = safe_atomic_write(content, target, tmpdir)
            assert success
            assert os.path.exists(target)
            assert file_hash is not None
    
    test_atomic_write()


# --- 4. Document State Machine ---
print("\n[4] Document State Machine")
print("-" * 40)

@test("DocumentProcessingStatus Enum existiert")
def test_processing_status_enum():
    from config.processing_rules import DocumentProcessingStatus
    assert hasattr(DocumentProcessingStatus, 'DOWNLOADED')
    assert hasattr(DocumentProcessingStatus, 'VALIDATED')
    assert hasattr(DocumentProcessingStatus, 'CLASSIFIED')
    assert hasattr(DocumentProcessingStatus, 'RENAMED')
    assert hasattr(DocumentProcessingStatus, 'ARCHIVED')
    assert hasattr(DocumentProcessingStatus, 'ERROR')

test_processing_status_enum()

@test("Gueltige State-Transitions")
def test_valid_transitions():
    from config.processing_rules import DocumentProcessingStatus
    assert DocumentProcessingStatus.is_valid_transition('downloaded', 'processing')
    assert DocumentProcessingStatus.is_valid_transition('processing', 'validated')
    assert DocumentProcessingStatus.is_valid_transition('validated', 'classified')
    assert DocumentProcessingStatus.is_valid_transition('processing', 'error')

test_valid_transitions()

@test("Ungueltige State-Transitions werden abgelehnt")
def test_invalid_transitions():
    from config.processing_rules import DocumentProcessingStatus
    assert not DocumentProcessingStatus.is_valid_transition('archived', 'downloaded')
    assert not DocumentProcessingStatus.is_valid_transition('downloaded', 'archived')

test_invalid_transitions()


# --- 5. Document Dataclass ---
print("\n[5] Document Dataclass")
print("-" * 40)

# Import-Test fuer api.documents
try:
    from api.documents import Document
    documents_available = True
except ImportError as e:
    print(f"  [SKIP] api.documents nicht ladbar: {e}")
    documents_available = False

if documents_available:
    @test("Document hat validation_status")
    def test_doc_validation_status():
        doc = Document(id=1, filename='t.pdf', original_filename='t.pdf', validation_status='PDF_ENCRYPTED')
        assert doc.validation_status == 'PDF_ENCRYPTED'
    
    test_doc_validation_status()
    
    @test("Document hat content_hash")
    def test_doc_content_hash():
        doc = Document(id=1, filename='t.pdf', original_filename='t.pdf', content_hash='abc123')
        assert doc.content_hash == 'abc123'
    
    test_doc_content_hash()
    
    @test("Document hat Versionierungs-Felder")
    def test_doc_version():
        doc = Document(id=2, filename='t.pdf', original_filename='t.pdf', version=2, previous_version_id=1)
        assert doc.version == 2
        assert doc.previous_version_id == 1
        assert doc.is_duplicate
    
    test_doc_version()
    
    @test("Document hat Klassifikations-Audit-Felder")
    def test_doc_audit():
        doc = Document(
            id=1, filename='t.pdf', original_filename='t.pdf',
            classification_source='ki_gpt4o',
            classification_confidence='high',
            classification_reason='Test',
            classification_timestamp='2026-02-05 10:00:00'
        )
        assert doc.classification_source == 'ki_gpt4o'
        assert doc.classification_confidence == 'high'
    
    test_doc_audit()


# --- 6. Processing History ---
print("\n[6] Processing History")
print("-" * 40)

# Import-Test fuer api.processing_history
try:
    from api.processing_history import HistoryEntry
    history_available = True
except ImportError as e:
    print(f"  [SKIP] api.processing_history nicht ladbar: {e}")
    history_available = False

if history_available:
    @test("HistoryEntry Dataclass existiert")
    def test_history_entry():
        entry = HistoryEntry(
            id=1, document_id=100, previous_status='processing',
            new_status='classified', action='classify', action_details=None,
            success=True, error_message=None, classification_source='ki',
            classification_result='sach', duration_ms=1000,
            created_at='2026-02-05', created_by='system'
        )
        assert entry.document_id == 100
        assert entry.success is True
    
    test_history_entry()
    
    @test("HistoryEntry.from_dict funktioniert")
    def test_history_from_dict():
        data = {
            'id': 5, 'document_id': 200, 'previous_status': 'downloaded',
            'new_status': 'processing', 'action': 'start', 'success': True,
            'created_at': '2026-02-05'
        }
        entry = HistoryEntry.from_dict(data)
        assert entry.document_id == 200
    
    test_history_from_dict()


# --- 7. XML Index ---
print("\n[7] XML Index")
print("-" * 40)

# Import-Test fuer api.xml_index
try:
    from api.xml_index import XmlIndexEntry
    xml_index_available = True
except ImportError as e:
    print(f"  [SKIP] api.xml_index nicht ladbar: {e}")
    xml_index_available = False

if xml_index_available:
    @test("XmlIndexEntry Dataclass existiert")
    def test_xml_index_entry():
        entry = XmlIndexEntry(
            id=1, external_shipment_id='SHIP-001', filename='resp.xml',
            raw_path='roh/resp.xml', file_size=1024, bipro_category='999010010',
            vu_name='Allianz', content_hash='abc', shipment_date='2026-02-05',
            created_at='2026-02-05'
        )
        assert entry.external_shipment_id == 'SHIP-001'
    
    test_xml_index_entry()


# --- 8. Import Tests ---
print("\n[8] Import Tests")
print("-" * 40)

# Import-Tests fuer Kernmodule
try:
    from services.document_processor import DocumentProcessor, ProcessingResult
    processor_available = True
except ImportError as e:
    print(f"  [SKIP] services.document_processor nicht ladbar: {e}")
    processor_available = False

if processor_available:
    @test("document_processor importierbar")
    def test_import_processor():
        assert DocumentProcessor is not None
        assert ProcessingResult is not None
    
    test_import_processor()


# ==============================================================================
# ERGEBNIS
# ==============================================================================

print("\n" + "=" * 70)
print("ERGEBNIS")
print("=" * 70)
print(f"\n  Bestanden: {passed}")
print(f"  Fehlgeschlagen: {failed}")
print(f"  Gesamt: {passed + failed}")

if errors:
    print("\n  FEHLERDETAILS:")
    for name, msg in errors:
        print(f"    - {name}: {msg}")

print("\n" + "=" * 70)

# Exit-Code
sys.exit(0 if failed == 0 else 1)
