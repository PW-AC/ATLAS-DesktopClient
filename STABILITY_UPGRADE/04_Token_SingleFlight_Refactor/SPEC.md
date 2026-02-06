# Task 04: Token SingleFlight Refactor (P1)

## Problem

`SharedTokenManager.get_valid_token()` und `build_soap_header()` halten `self._lock` während des gesamten `_ensure_token()` Calls. Wenn `_ensure_token()` ein neues STS-Token holt (HTTP-Call, ~1-3 Sekunden), blockieren alle anderen Worker-Threads.

## Root Cause

```python
def get_valid_token(self):
    with self._lock:  # Lock für 1-3 Sekunden gehalten!
        self._client._ensure_token()  # <- HTTP-Call
        return self._client._token
```

Alle 10 Worker müssen warten bis ein Thread den Token-Refresh abgeschlossen hat.

## Technische Analyse

Datei: `src/bipro/transfer_service.py`
- `SharedTokenManager` (ab Zeile 1314)
- `_lock = threading.Lock()` (Zeile 1342)
- `get_valid_token()` (Zeile 1373-1391): Lock um gesamten Block inkl. `_ensure_token()`
- `build_soap_header()` (Zeile 1393-1406): Lock um gesamten Block inkl. `_ensure_token()`
- `_ensure_token()` (Zeile 666-695 in TransferServiceClient): Prüft Token-Expiry, ruft ggf. `_get_sts_token()` auf
- `_get_sts_token()` (ab Zeile ~600): HTTP POST an STS-Endpoint (1-3s)

Double-Refresh ist aktuell verhindert (Lock), aber Performance ist schlecht.

## Zielzustand

- Double-Checked Locking: Schneller Pfad ohne Lock wenn Token gültig
- Nur bei Token-Refresh wird Lock gehalten
- Token-Validitätsprüfung ist lock-free (atomic read)
- HTTP-Call wird INNERHALB des Locks gehalten (korrekt, da sonst Double-Refresh möglich)
- Aber: Nur ein Thread blockiert, andere sehen sofort das erneuerte Token

## Randbedingungen

- `TransferServiceClient._token` und `_token_expires` sind Instanz-Variablen des Clients
- `SharedTokenManager._client` ist der einzige Zugriffspunkt
- Token-Lifetime: 10 Minuten, 1 Minute Buffer vor Expiry
- `_ensure_token()` mutiert `self._token` und `self._token_expires`

## Performance-Vorgaben

- Schneller Pfad (Token gültig): KEIN Lock-Overhead
- Langsamer Pfad (Token-Refresh): Max. 1 Thread blockiert für HTTP-Call, andere warten kurz

## Thread-Safety-Vorgaben

- Kein Double-Refresh (nur ein Thread darf gleichzeitig STS-Token holen)
- Keine Race Condition beim Token-Lesen
- `_token` und `_token_expires` müssen konsistent sein

## Nicht-Ziele

- Keine Änderung von `TransferServiceClient` (nur `SharedTokenManager`)
- Kein Token-Caching über Manager-Lifecycle hinaus
- Keine Änderung der Token-Lifetime
