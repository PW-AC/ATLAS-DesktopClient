# Change Plan: Task 03 - Retry Vereinheitlichung

## Betroffene Dateien

| Datei | Änderung |
|-------|----------|
| `src/api/client.py` | Zentrale `_request_with_retry()`, alle Methoden refactored |

## Neue Methoden

### `APIClient._request_with_retry(method, url, **kwargs) -> requests.Response`
- Zentrale Retry-Logik für alle HTTP-Methoden
- Exponentieller Backoff: `RETRY_BACKOFF_FACTOR * (2 ** attempt)`
- Retries auf: RETRY_STATUS_CODES + Timeout + ConnectionError
- Max. `MAX_RETRIES` Versuche
- Logging bei jedem Retry-Versuch

## Geänderte Methoden

### `get()`, `post()`, `put()`, `delete()`
- Refactored: Nutzen `_request_with_retry()` statt direktem `self._session.request()`
- Öffentliche API bleibt identisch

### `upload_file()`
- Refactored: Nutzt `_request_with_retry()` 
- Besonderheit: Datei muss bei Retry erneut geöffnet werden → Callback-Pattern oder Retry um gesamten Block

### `download_file()`
- Bestehende Retry-Logik wird durch `_request_with_retry()` ersetzt
- Streaming-Logik (iter_content) bleibt im Methoden-Body
- Backoff wird von linear auf exponentiell umgestellt

## Entfernte Logik

- Inline-Retry in `download_file()` wird durch zentrale Methode ersetzt
- Duplikat-Code entfernt

## Backoff-Konfiguration

```python
MAX_RETRIES = 3
RETRY_STATUS_CODES = {429, 500, 502, 503, 504}
RETRY_BACKOFF_FACTOR = 1.0  # 1s, 2s, 4s

def _calculate_backoff(self, attempt: int) -> float:
    return RETRY_BACKOFF_FACTOR * (2 ** attempt)
```

## Risikoanalyse

- **Doppel-Retry**: 401-Retry (Task 02) + Netzwerk-Retry können zusammenwirken. 401 wird aus RETRY_STATUS_CODES ausgeschlossen.
- **Upload-Retry**: Datei muss bei Retry erneut gelesen werden. Lösung: Retry um gesamten `with open()` Block.
- **Idempotenz**: Alle Server-Endpoints sind idempotent (kein doppelter Upload-Schaden).

## Validierung

- Transiente Fehler (500) → Retry + Erfolg
- Permanente Fehler (404) → Sofort Exception
- 429 → Retry mit Backoff
- ConnectionError → Retry
- Timeout → Retry
- 401 → KEIN Retry hier (Task 02 übernimmt)
