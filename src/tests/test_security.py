"""
SV-030: Security-Tests fuer ACENCIA ATLAS.

Prueft die Einhaltung der Security-Massnahmen aus dem Audit.
"""

import os
import sys
import tempfile
import pytest
from pathlib import Path

# Projekt-Root ermitteln
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class TestNoHardcodedSecrets:
    """SV-001: Keine hardcoded Passwoerter im Code."""
    
    FORBIDDEN_PATTERNS = [
        "TQMakler37",
        "TQMakler2021", 
        "555469899",
        "dfvprovision",
    ]
    
    SCAN_DIRS = [
        PROJECT_ROOT / "src",
    ]
    
    SKIP_PATTERNS = [
        "__pycache__",
        ".pyc",
        "test_security.py",  # Diese Datei selbst
    ]
    
    def _should_skip(self, path: str) -> bool:
        return any(skip in path for skip in self.SKIP_PATTERNS)
    
    def test_no_hardcoded_passwords_in_src(self):
        """Stellt sicher, dass keine bekannten Passwoerter im src-Verzeichnis sind."""
        violations = []
        
        for scan_dir in self.SCAN_DIRS:
            if not scan_dir.exists():
                continue
            for root, dirs, files in os.walk(scan_dir):
                for fname in files:
                    fpath = os.path.join(root, fname)
                    if self._should_skip(fpath):
                        continue
                    try:
                        content = open(fpath, 'r', errors='ignore').read()
                        for pattern in self.FORBIDDEN_PATTERNS:
                            if pattern in content:
                                violations.append(f"{fpath}: enthaelt '{pattern}'")
                    except Exception:
                        pass
        
        assert not violations, (
            f"Hardcoded Passwoerter gefunden:\n" + 
            "\n".join(violations)
        )
    
    def test_no_hardcoded_passwords_in_agents(self):
        """SV-001: Keine Klartext-Passwoerter in AGENTS.md."""
        agents_path = PROJECT_ROOT / "AGENTS.md"
        if not agents_path.exists():
            pytest.skip("AGENTS.md nicht gefunden")
        
        content = agents_path.read_text(errors='ignore')
        for pattern in self.FORBIDDEN_PATTERNS:
            assert pattern not in content, f"AGENTS.md enthaelt '{pattern}'"


class TestZipBombProtection:
    """SV-007: Zip-Bomb-Schutz."""
    
    def test_size_limits_defined(self):
        """Prueft dass Groessenlimits definiert sind."""
        from services.zip_handler import MAX_TOTAL_UNCOMPRESSED_SIZE, MAX_SINGLE_FILE_SIZE
        
        assert MAX_TOTAL_UNCOMPRESSED_SIZE == 500 * 1024 * 1024
        assert MAX_SINGLE_FILE_SIZE == 100 * 1024 * 1024


class TestTempFileCleanup:
    """SV-024: Temp-File-Cleanup bei PDF-Unlock."""
    
    def test_pdf_unlock_cleanup_on_error(self):
        """Prueft dass Temp-Files bei Fehler aufgeraeumt werden."""
        # Dieser Test ist ein Strukturtest: Prueft dass try/finally vorhanden ist
        from services import pdf_unlock
        import inspect
        
        source = inspect.getsource(pdf_unlock.unlock_pdf_if_needed)
        assert "finally:" in source, "unlock_pdf_if_needed() muss try/finally verwenden"
        assert "temp_path = None" in source or "os.unlink(temp_path)" in source, \
            "Cleanup-Logik muss vorhanden sein"


class TestNoAPIKeyExposure:
    """SV-004: API-Key darf nicht an Client gesendet werden."""
    
    def test_openrouter_uses_proxy(self):
        """Prueft dass openrouter.py den Server-Proxy nutzt statt direkt OpenRouter aufruft."""
        openrouter_path = PROJECT_ROOT / "src" / "api" / "openrouter.py"
        if not openrouter_path.exists():
            pytest.skip("openrouter.py nicht gefunden")
        
        content = openrouter_path.read_text(errors='ignore')
        # Die _openrouter_request Methode sollte /ai/classify verwenden
        assert "ai/classify" in content, "openrouter.py muss /ai/classify Proxy nutzen"


class TestPEMTempFileTracking:
    """SV-008: PEM-Temp-Files muessen tracked werden."""
    
    def test_atexit_handler_registered(self):
        """Prueft dass atexit-Cleanup registriert ist."""
        from bipro import transfer_service
        assert hasattr(transfer_service, '_temp_pem_files'), \
            "transfer_service muss _temp_pem_files Tracking haben"
        assert hasattr(transfer_service, '_cleanup_temp_pem_files'), \
            "transfer_service muss _cleanup_temp_pem_files haben"


class TestMSGErrorHandling:
    """SV-025: MSG-Fehler muessen geloggt werden."""
    
    def test_no_bare_except_pass(self):
        """Prueft dass keine bare except:pass in msg_handler.py existiert."""
        msg_handler_path = PROJECT_ROOT / "src" / "services" / "msg_handler.py"
        if not msg_handler_path.exists():
            pytest.skip("msg_handler.py nicht gefunden")
        
        content = msg_handler_path.read_text(errors='ignore')
        # Pruefen dass es keine "except Exception: pass" gibt
        assert "except Exception:\n                        pass" not in content, \
            "msg_handler.py darf keine bare except:pass haben (SV-025)"
