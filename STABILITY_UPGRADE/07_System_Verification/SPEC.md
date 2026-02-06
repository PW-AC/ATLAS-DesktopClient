# Task 07: System-Verifikation

## Zweck

Finale Verifikation nach allen Änderungen. Prüft ob das Gesamtsystem konsistent ist.

## Prüfpunkte

1. **Import-Chain**: Alle Module importierbar (`python -c "from src.api.client import APIClient"` etc.)
2. **Smoke-Tests**: `pytest src/tests/` grün
3. **Keine ungeschützten Shared States**: Grep nach `_pause_count`, `_refresh_in_progress` → alle unter Lock
4. **Retry auf allen Methoden**: `APIClient.get/post/put/delete/upload_file` nutzen `_request_with_retry`
5. **401-Retry**: `APIClient` hat `_auth_callback` und Retry-Logik
6. **Token SingleFlight**: `SharedTokenManager.get_valid_token()` hat Double-Checked Locking
7. **File-Logging**: `logs/` Ordner wird erstellt, RotatingFileHandler konfiguriert
8. **Keine Regressions**: Bestehende Tests passen noch

## Output

`STABILITY_UPGRADE/07_System_Verification/IMPLEMENTATION_REPORT.md` mit:
- Checklist aller Prüfpunkte (bestanden/nicht bestanden)
- Falls nicht bestanden: Was genau ist das Problem
- Gesamtstatus: PASS oder FAIL

## Nicht-Ziele

- Kein neuer Code
- Keine Fixes (die gehören in die jeweiligen Task-Ordner)
