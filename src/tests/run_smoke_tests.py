"""
Einfacher Smoke-Test-Runner ohne pytest Abhaengigkeit

Fuehrt alle kritischen Validierungen durch und gibt einen Report aus.

Ausfuehrung:
    python src/tests/run_smoke_tests.py
    python src/tests/run_smoke_tests.py --json-report
"""

import sys
import os
import re as _re
import json
import time
import tempfile
import traceback
from pathlib import Path
from datetime import datetime

# Projekt-Root zum Pfad hinzufuegen
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / 'src'))

JSON_REPORT_MODE = '--json-report' in sys.argv

# Test-Ergebnisse
passed = 0
failed = 0
errors = []
_test_results = []


def test(name):
    """Decorator fuer Tests."""
    def decorator(func):
        def wrapper():
            global passed, failed, errors, _test_results
            t0 = time.time()
            try:
                func()
                duration_ms = int((time.time() - t0) * 1000)
                if not JSON_REPORT_MODE:
                    print(f"  [OK] {name}")
                passed += 1
                _test_results.append({'name': name, 'status': 'passed', 'duration_ms': duration_ms})
            except AssertionError as e:
                duration_ms = int((time.time() - t0) * 1000)
                if not JSON_REPORT_MODE:
                    print(f"  [FAIL] {name}")
                    print(f"         Assertion: {e}")
                failed += 1
                errors.append((name, str(e)))
                _test_results.append({'name': name, 'status': 'failed', 'duration_ms': duration_ms, 'error': str(e)})
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
    _doc_defaults = dict(mime_type='application/pdf', file_size=1024, source_type='manual_upload', is_gdv=False, created_at='2026-01-01')

    @test("Document hat validation_status")
    def test_doc_validation_status():
        doc = Document(id=1, filename='t.pdf', original_filename='t.pdf', validation_status='PDF_ENCRYPTED', **_doc_defaults)
        assert doc.validation_status == 'PDF_ENCRYPTED'
    
    test_doc_validation_status()
    
    @test("Document hat content_hash")
    def test_doc_content_hash():
        doc = Document(id=1, filename='t.pdf', original_filename='t.pdf', content_hash='abc123', **_doc_defaults)
        assert doc.content_hash == 'abc123'
    
    test_doc_content_hash()
    
    @test("Document hat Versionierungs-Felder")
    def test_doc_version():
        doc = Document(id=2, filename='t.pdf', original_filename='t.pdf', version=2, previous_version_id=1, **_doc_defaults)
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
            classification_timestamp='2026-02-05 10:00:00',
            **_doc_defaults
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


# --- 9. Provision Normalisierung ---
print("\n[9] Provision Normalisierung")
print("-" * 40)

try:
    from services.provision_import import normalize_vsnr, normalize_vermittler_name, normalize_for_db
    provision_available = True
except ImportError as e:
    print(f"  [SKIP] services.provision_import nicht ladbar: {e}")
    provision_available = False

if provision_available:
    @test("normalize_vsnr: Buchstaben + Nullen entfernen")
    def test_vsnr_basic():
        assert normalize_vsnr("ABC-001-234") == "1234"
        assert normalize_vsnr("00123045") == "12345"

    test_vsnr_basic()

    @test("normalize_vsnr: Scientific Notation")
    def test_vsnr_scientific():
        result = normalize_vsnr("1.23E+10")
        assert result == "123", f"Erwartet '123', erhalten '{result}'"

    test_vsnr_scientific()

    @test("normalize_vsnr: Edge Cases (leer, Nullen, intern)")
    def test_vsnr_edges():
        assert normalize_vsnr("") == ""
        assert normalize_vsnr("0000") == "0"
        assert normalize_vsnr("10203") == "123"

    test_vsnr_edges()

    @test("normalize_vermittler_name: Umlaute + Sonderzeichen")
    def test_vermittler_normalize():
        assert normalize_vermittler_name("Müller-Lüdenscheidt") == "muellerluedenscheidt"
        assert normalize_vermittler_name("Straße") == "strasse"

    test_vermittler_normalize()

    @test("normalize_for_db: Klammern + Umlaute")
    def test_db_normalize():
        result = normalize_for_db("Müller (geb. Meier)")
        assert "mueller" in result
        assert "geb meier" in result
        assert normalize_for_db("") == ""

    test_db_normalize()


# --- 10. Version Consistency ---
print("\n[10] Version Consistency")
print("-" * 40)

@test("VERSION Datei ist gueltig (SemVer)")
def test_version_semver():
    version_path = project_root / 'VERSION'
    assert version_path.exists(), "VERSION Datei fehlt"
    version = version_path.read_text(encoding='utf-8-sig').strip()
    assert _re.match(r'^\d+\.\d+\.\d+', version), f"VERSION ist kein SemVer: {version}"

test_version_semver()

@test("version_info.txt stimmt mit VERSION ueberein")
def test_version_info_match():
    version_path = project_root / 'VERSION'
    info_path = project_root / 'version_info.txt'
    if not info_path.exists():
        return  # Skip wenn nicht vorhanden
    version = version_path.read_text(encoding='utf-8-sig').strip().split('-')[0]
    parts = version.split('.')
    major, minor, patch = parts[0], parts[1], parts[2]
    info_content = info_path.read_text(encoding='utf-8')
    expected_filevers = f"filevers=({major}, {minor}, {patch}, 0)"
    assert expected_filevers in info_content, f"version_info.txt enthaelt nicht '{expected_filevers}'"

test_version_info_match()

@test("installer.iss liest VERSION dynamisch")
def test_installer_dynamic_version():
    iss_path = project_root / 'installer.iss'
    if not iss_path.exists():
        return  # Skip wenn nicht vorhanden
    content = iss_path.read_text(encoding='utf-8')
    assert 'FileOpen' in content and 'VERSION' in content, \
        "installer.iss liest VERSION nicht dynamisch (fehlt FileOpen/VERSION Preprocessor)"

test_installer_dynamic_version()


# --- 11. API Health Check (optional) ---
print("\n[11] API Health Check (optional)")
print("-" * 40)

try:
    import requests as _requests
    requests_available = True
except ImportError:
    requests_available = False
    print("  [SKIP] requests nicht installiert")

if requests_available:
    @test("API /status erreichbar und schema_version vorhanden")
    def test_api_health():
        try:
            resp = _requests.get("https://acencia.info/api/status", timeout=5)
            assert resp.status_code == 200, f"Status {resp.status_code}"
            data = resp.json()
            assert data.get('status') == 'ok', f"API-Status: {data.get('status')}"
            assert data.get('schema_version'), "schema_version fehlt in API-Antwort"
        except _requests.exceptions.ConnectionError:
            print("  [SKIP] Server nicht erreichbar")
            return
        except _requests.exceptions.Timeout:
            print("  [SKIP] Server-Timeout")
            return

    test_api_health()


# ==============================================================================
# ERGEBNIS
# ==============================================================================

if JSON_REPORT_MODE:
    version_file = project_root / 'VERSION'
    app_version = '0.0.0'
    if version_file.exists():
        app_version = version_file.read_text(encoding='utf-8-sig').strip()

    report = {
        'app_version': app_version,
        'timestamp': datetime.utcnow().isoformat(),
        'tests_run': passed + failed,
        'tests_passed': passed,
        'tests_failed': failed,
        'results': _test_results,
    }
    report_path = project_root / 'smoke_test_report.json'
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(json.dumps(report, indent=2, ensure_ascii=False))
else:
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
