# Task 06 - Smoke Tests & Minimal CI

## STATUS: COMPLETE

## Erstellte Dateien

| Datei | Beschreibung |
|-------|--------------|
| `src/tests/test_stability.py` | 10 Stabilitäts-Tests (pytest) |
| `scripts/run_checks.py` | Minimal CI Script (Lint + Tests) |
| `requirements-dev.txt` | Dev-Dependencies (pytest, ruff) |

## Tests (10 Stück)

| # | Test | Verifiziert |
|---|------|-------------|
| 1 | `test_api_client_creation` | APIClient Default-Config (timeout=30, base_url, nicht authentifiziert) |
| 2 | `test_api_client_has_auth_refresh` | Task 02: set_auth_refresh_callback, _try_auth_refresh, _auth_refresh_lock |
| 3 | `test_api_client_has_retry` | Task 03: _request_with_retry, MAX_RETRIES=3, RETRY_STATUS_CODES enthält 429+500 |
| 4 | `test_exponential_backoff` | Task 03: Backoff-Berechnung 1.0, 2.0, 4.0 Sekunden |
| 5 | `test_auth_api_has_re_authenticate` | Task 02: AuthAPI.re_authenticate existiert und ist aufrufbar |
| 6 | `test_parser_roundtrip` | GDV-Datei laden → speichern → erneut laden → Satzarten identisch |
| 7 | `test_datacache_pause_resume_attributes` | Task 01: DataCacheService._lock (Class-Level-Lock) existiert |
| 8 | `test_shared_token_manager_structure` | Task 04: SharedTokenManager hat _is_token_valid, get_valid_token, build_soap_header |
| 9 | `test_critical_imports` | 10 Module importierbar (api, parser, domain, bipro, config) |
| 10 | `test_domain_mapping` | ParsedFile → GDVData Mapping mit contracts + customers |

## Testergebnis

```
10 passed in 0.53s
```

Alle Tests bestanden ohne Fehler. Kein Qt/Display erforderlich.

## CI Script

`scripts/run_checks.py` führt aus:
1. **Lint (ruff)** - optional, übersprungen wenn ruff nicht installiert
2. **Tests (pytest)** - `src/tests/test_stability.py -v --tb=short`

Exit Code 0 bei Erfolg, 1 bei Fehlern.

## Ausführung

```bash
# Tests direkt
python -m pytest src/tests/test_stability.py -v

# CI Script
python scripts/run_checks.py

# Dev-Dependencies installieren
pip install -r requirements-dev.txt
```

## Keine bestehenden Dateien geändert

Es wurden ausschließlich neue Dateien erstellt. Keine bestehenden Dateien wurden modifiziert.
