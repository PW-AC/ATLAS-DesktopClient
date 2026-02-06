# Task 03 - Retry Vereinheitlichung

## STATUS: COMPLETE

## Geaenderte Datei
- `src/api/client.py`

## Geaenderte/Neue Methoden

| Methode | Aenderung |
|---------|-----------|
| `_request_with_retry()` | **NEU** - Zentrale Retry-Methode mit exponentiellem Backoff |
| `get()` | Refactored: `self._session.get()` → `self._request_with_retry('GET', ...)` |
| `post()` | Refactored: `self._session.post()` → `self._request_with_retry('POST', ...)` |
| `put()` | Refactored: `self._session.put()` → `self._request_with_retry('PUT', ...)` |
| `delete()` | Refactored: `self._session.delete()` → `self._request_with_retry('DELETE', ...)` |
| `upload_file()` | Refactored: Datei wird in Speicher gelesen + `_request_with_retry('POST', ...)` |
| `_download_file_inner()` | Refactored: Inline-Retry-Loop entfernt, nutzt `_request_with_retry('GET', ...)` |
| `download_file()` | Signatur beibehalten (`max_retries` Parameter fuer Abwaertskompatibilitaet) |

## Zusaetzliche Aenderung
- `import os` hinzugefuegt (fuer `os.path.basename` in `upload_file`)

## Pruefpunkte

| # | Pruefpunkt | Status |
|---|-----------|--------|
| 1 | Alle HTTP-Methoden nutzen `_request_with_retry()` | BESTANDEN |
| 2 | Exponentieller Backoff: 1s, 2s, 4s (`2 ** attempt`) | BESTANDEN |
| 3 | 401 wird NICHT in `_request_with_retry()` retried | BESTANDEN |
| 4 | 401-Retry-Logik (Task 02) funktioniert weiterhin | BESTANDEN |
| 5 | `download_file()` behaelt Streaming-Logik (`stream=True` + `iter_content`) | BESTANDEN |
| 6 | `upload_file()` funktioniert bei Retry (Datei als Bytes im Speicher) | BESTANDEN |

## Backoff-Berechnung

```
Vorher (linear):  wait = RETRY_BACKOFF_FACTOR * (attempt + 1)  →  1s, 2s, 3s
Nachher (exp.):   wait = RETRY_BACKOFF_FACTOR * (2 ** attempt)  →  1s, 2s, 4s
```

## Architektur-Entscheidungen

### Upload-File: Datei in Speicher lesen
Die Datei wird einmalig mit `open(file_path, 'rb').read()` in den Speicher gelesen und als `(filename, bytes)` Tuple an `_request_with_retry()` uebergeben. Bytes-Objekte sind unveraenderlich und koennen bei Retries wiederverwendet werden, im Gegensatz zu File-Handles die nach dem ersten Request verbraucht sind.

### Download-File: Stream nach Retry
`_request_with_retry()` wird mit `stream=True` aufgerufen. Die Retry-Logik behandelt transiente Fehler bei der HTTP-Verbindung. Das Streaming (`iter_content`) erfolgt erst nach erfolgreichem Response und liegt ausserhalb der Retry-Schleife.

### 401 Separation
`_request_with_retry()` behandelt nur transiente Netzwerkfehler (429, 500, 502, 503, 504, Timeout, ConnectionError). Die 401-Behandlung bleibt in den aeusseren Methoden, da sie Token-Refresh erfordert und nicht einfach wiederholt werden kann.

## Oeffentliche API
Alle Methoden-Signaturen sind unveraendert. `download_file.max_retries` bleibt als Parameter fuer Abwaertskompatibilitaet, wird aber intern nicht mehr weitergeleitet (zentrale Konfiguration ueber `MAX_RETRIES`).
