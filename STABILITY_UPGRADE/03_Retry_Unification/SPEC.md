# Task 03: Retry Vereinheitlichung (P1)

## Problem

Nur `APIClient.download_file()` hat Retry-Logik. Alle anderen Methoden (`get`, `post`, `put`, `delete`, `upload_file`) haben keine. Transiente Netzwerkfehler (429, 500, 502, 503, 504, Timeout, ConnectionError) führen bei diesen Methoden zu sofortigem Fehler.

## Root Cause

Retry wurde historisch nur für Downloads implementiert. Die anderen Methoden wurden früh im Projekt erstellt und nie nachgerüstet.

## Technische Analyse

Bestehende Retry-Config in `src/api/client.py`:
- `MAX_RETRIES = 3` (Zeile 16)
- `RETRY_STATUS_CODES = {429, 500, 502, 503, 504}` (Zeile 17)  
- `RETRY_BACKOFF_FACTOR = 1.0` (Zeile 18)

Bestehende Retry in `download_file()` (Zeile 228-289):
- Linearer Backoff: `wait_time = RETRY_BACKOFF_FACTOR * (attempt + 1)` → 1s, 2s, 3s
- Retries auf: Retryable Status Codes, Timeout, ConnectionError
- Nicht retryable: andere RequestException

Ziel: Exponentieller Backoff für alle Methoden.

## Zielzustand

- Zentrale `_request_with_retry()` Methode
- Alle HTTP-Methoden (get, post, put, delete, upload_file, download_file) nutzen Retry
- Exponentieller Backoff: `backoff * 2^attempt` (1s, 2s, 4s)
- Retryable: `{429, 500, 502, 503, 504}` + `Timeout` + `ConnectionError`
- Nicht retryable: 4xx (außer 429), andere Exceptions
- 401 wird NICHT retried (das macht Task 02)

## Randbedingungen

- Task 02 (401 Auto-Refresh) muss VORHER abgeschlossen sein
- Die 401-Retry-Logik aus Task 02 und die Netzwerk-Retry-Logik hier müssen zusammenspielen
- `download_file()` hat spezielle Streaming-Logik (iter_content) die erhalten bleiben muss
- `upload_file()` öffnet eine Datei - bei Retry muss die Datei erneut geöffnet werden

## Performance-Vorgaben

- Max. 3 Retries (bestehend)
- Exponentieller Backoff: 1s, 2s, 4s (max ~7s Gesamtwartezeit)
- Kein Retry bei idempotenz-unsicheren Operationen? → Alle unsere API-Calls sind idempotent (Server-seitig)

## Thread-Safety-Vorgaben

- Retry-Logik muss thread-safe sein (keine shared state)
- `time.sleep()` blockiert nur den aufrufenden Thread (korrekt)

## Nicht-Ziele

- Kein Circuit Breaker
- Keine Jitter-Strategie (zu komplex für den Nutzen)
- Keine Änderung der Retry-Konfiguration (bleibt 3 Retries)
