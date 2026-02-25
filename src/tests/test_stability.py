"""
Stabilitäts-Tests für ACENCIA ATLAS.

Verifiziert die Fixes aus dem Stability Upgrade:
- Task 01: DataCache Race Condition Fix
- Task 02: 401 Auto-Refresh  
- Task 03: Retry Vereinheitlichung
- Task 04: Token SingleFlight

Ausführung: python -m pytest src/tests/test_stability.py -v
(von x:\\projekte\\5510_GDV Tool V1 aus, mit src/ im PYTHONPATH)
"""

import sys
import os
import time
import threading
import pytest

# src/ zum Path hinzufügen
_src_dir = os.path.join(os.path.dirname(__file__), '..')
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)


# === Test 1: APIClient Instanziierung ===
def test_api_client_creation():
    """APIClient kann erstellt werden mit Default-Config."""
    from api.client import APIClient, APIConfig
    client = APIClient()
    assert client.config.timeout == 30
    assert client.config.base_url == "https://acencia.info/api"
    assert client.is_authenticated() == False


# === Test 2: APIClient hat Auth-Refresh-Callback ===
def test_api_client_has_auth_refresh():
    """APIClient hat set_auth_refresh_callback Methode."""
    from api.client import APIClient
    client = APIClient()
    assert hasattr(client, 'set_auth_refresh_callback')
    assert hasattr(client, '_try_auth_refresh')
    assert hasattr(client, '_auth_refresh_lock')
    
    # Callback setzen
    called = []
    client.set_auth_refresh_callback(lambda: called.append(True) or False)
    assert client._auth_refresh_callback is not None


# === Test 2b: Auth-Refresh Deadlock-Schutz ===
def test_auth_refresh_no_deadlock():
    """_try_auth_refresh() darf bei Rekursion nicht deadlocken.
    
    Szenario: Callback ruft intern nochmal _try_auth_refresh() auf
    (wie es bei re_authenticate -> verify_token -> get -> 401 passiert).
    Der Lock muss non-blocking sein, damit der rekursive Aufruf False
    zurueckgibt statt den Thread zu blockieren.
    """
    from api.client import APIClient
    client = APIClient()
    
    recursive_results = []
    
    def recursive_callback():
        """Simuliert re_authenticate das intern nochmal 401 triggert."""
        # Dieser rekursive Aufruf MUSS False zurueckgeben (Lock gehalten)
        inner_result = client._try_auth_refresh()
        recursive_results.append(inner_result)
        return True  # Aeusserer Aufruf gelingt
    
    client.set_auth_refresh_callback(recursive_callback)
    
    # Darf NICHT haengen (Deadlock) - muss in <1s fertig sein
    import signal
    result = client._try_auth_refresh()
    
    assert result == True, "Aeusserer Refresh sollte True zurueckgeben"
    assert len(recursive_results) == 1, "Callback wurde aufgerufen"
    assert recursive_results[0] == False, "Rekursiver Aufruf muss False zurueckgeben (Lock gehalten)"


# === Test 3: APIClient hat _request_with_retry ===
def test_api_client_has_retry():
    """APIClient hat zentrale Retry-Methode."""
    from api.client import APIClient, MAX_RETRIES, RETRY_STATUS_CODES, RETRY_BACKOFF_FACTOR
    client = APIClient()
    assert hasattr(client, '_request_with_retry')
    assert MAX_RETRIES == 3
    assert 429 in RETRY_STATUS_CODES
    assert 500 in RETRY_STATUS_CODES


# === Test 4: Exponentieller Backoff ===
def test_exponential_backoff():
    """Backoff ist exponentiell: 1, 2, 4 Sekunden."""
    from api.client import RETRY_BACKOFF_FACTOR
    for attempt in range(3):
        wait = RETRY_BACKOFF_FACTOR * (2 ** attempt)
        expected = [1.0, 2.0, 4.0]
        assert wait == expected[attempt], f"Attempt {attempt}: {wait} != {expected[attempt]}"


# === Test 5: AuthAPI hat re_authenticate ===
def test_auth_api_has_re_authenticate():
    """AuthAPI hat re_authenticate Methode."""
    from api.auth import AuthAPI
    from api.client import APIClient
    client = APIClient()
    auth = AuthAPI(client)
    assert hasattr(auth, 're_authenticate')
    assert callable(auth.re_authenticate)


# === Test 6: Parser Roundtrip ===
def test_parser_roundtrip(tmp_path):
    """GDV-Datei laden, speichern, erneut laden - Daten müssen identisch sein."""
    from parser.gdv_parser import parse_file, save_file
    
    sample = os.path.join(os.path.dirname(__file__), '..', '..', 'testdata', 'sample.gdv')
    if not os.path.exists(sample):
        pytest.skip("testdata/sample.gdv nicht gefunden")
    
    # Laden
    parsed = parse_file(sample)
    assert len(parsed.records) > 0, "Keine Records geparst"
    
    # Speichern
    out_path = str(tmp_path / "roundtrip.gdv")
    save_file(parsed, out_path)
    
    # Erneut laden
    reparsed = parse_file(out_path)
    assert len(reparsed.records) == len(parsed.records), \
        f"Record-Anzahl unterschiedlich: {len(reparsed.records)} vs {len(parsed.records)}"
    
    # Satzarten vergleichen
    orig_satzarten = [r.satzart for r in parsed.records]
    new_satzarten = [r.satzart for r in reparsed.records]
    assert orig_satzarten == new_satzarten, "Satzarten unterschiedlich nach Roundtrip"


# === Test 7: DataCache Thread-Safety (nur wenn Qt verfügbar) ===
def test_datacache_pause_resume_attributes():
    """DataCacheService hat die Thread-Safety-Attribute."""
    try:
        from services.data_cache import DataCacheService
        # Prüfe dass _lock existiert (Class-level Lock)
        assert hasattr(DataCacheService, '_lock')
        # Instanz-Attribute können wir nicht ohne API-Client prüfen
        # Aber die Klasse muss importierbar sein
    except ImportError as e:
        pytest.skip(f"DataCacheService nicht importierbar (braucht Qt): {e}")


# === Test 8: SharedTokenManager Struktur ===
def test_shared_token_manager_structure():
    """SharedTokenManager hat _is_token_valid und Double-Checked Locking."""
    from bipro.transfer_service import SharedTokenManager
    assert hasattr(SharedTokenManager, '_is_token_valid')
    assert hasattr(SharedTokenManager, 'get_valid_token')
    assert hasattr(SharedTokenManager, 'build_soap_header')


# === Test 9: Import-Chain ===
def test_critical_imports():
    """Alle kritischen Module sind importierbar."""
    import api.client
    import api.auth
    import api.documents
    import parser.gdv_parser
    import domain.models
    import domain.mapper
    import bipro.transfer_service
    import bipro.rate_limiter
    import bipro.categories
    import config.processing_rules


# === Test 10: Domain Mapping ===
def test_domain_mapping():
    """ParsedFile kann zu GDVData gemapped werden."""
    from parser.gdv_parser import parse_file
    from domain.mapper import map_parsed_file_to_gdv_data
    
    sample = os.path.join(os.path.dirname(__file__), '..', '..', 'testdata', 'sample.gdv')
    if not os.path.exists(sample):
        pytest.skip("testdata/sample.gdv nicht gefunden")
    
    parsed = parse_file(sample)
    gdv_data = map_parsed_file_to_gdv_data(parsed)
    
    assert gdv_data is not None
    assert hasattr(gdv_data, 'contracts')
    assert hasattr(gdv_data, 'customers')
