# Change Plan: Task 06 - Smoke Tests & Minimal CI

## Betroffene Dateien

| Datei | Änderung |
|-------|----------|
| `src/tests/test_stability.py` | Neue Test-Datei für Stabilitäts-Tests |
| `scripts/run_checks.py` | Neues CI-Script (Lint + Tests) |
| `requirements-dev.txt` | Dev-Dependencies (ruff, pytest) |

## Neue Tests in `test_stability.py`

```python
# 1. Parser-Roundtrip
def test_parser_roundtrip():
    parsed = parse_file("testdata/sample.gdv")
    assert len(parsed.records) > 0
    # Save and reload
    save_file(parsed, tmp_path)
    reparsed = parse_file(tmp_path)
    assert len(parsed.records) == len(reparsed.records)

# 2. Domain-Mapping
def test_domain_mapping():
    parsed = parse_file("testdata/sample.gdv")
    gdv_data = map_parsed_file_to_gdv_data(parsed)
    assert len(gdv_data.contracts) > 0

# 3. DataCache Thread-Safety
def test_datacache_pause_resume_threadsafe():
    # 10 Threads parallel pause/resume
    # Am Ende: _pause_count == 0

# 4. Retry Backoff Calculation
def test_retry_backoff():
    # Exponentieller Backoff: 1, 2, 4
    
# 5. APIClient Instantiation
def test_api_client_creation():
    client = APIClient()
    assert client.config.timeout == 30
```

## CI-Script `scripts/run_checks.py`

```python
# 1. Lint (ruff) - wenn installiert
# 2. Tests (pytest)
# 3. Summary mit Exit-Code
```

## `requirements-dev.txt` (neu)

```
pytest>=7.0.0
ruff>=0.1.0
```

## Risikoanalyse

- **Kein Risiko**: Nur neue Dateien, keine bestehenden Änderungen
- **PySide6-Imports**: Tests die PySide6 brauchen werden übersprungen wenn kein Display

## Validierung

- `python -m pytest src/tests/test_stability.py -v` → alle grün
- `python scripts/run_checks.py` → Exit 0
