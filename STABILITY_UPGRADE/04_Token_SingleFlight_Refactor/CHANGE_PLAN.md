# Change Plan: Task 04 - Token SingleFlight Refactor

## Betroffene Dateien

| Datei | Änderung |
|-------|----------|
| `src/bipro/transfer_service.py` | `SharedTokenManager` Methoden refactored |

## Geänderte Methoden

### `SharedTokenManager.get_valid_token()`
Vorher:
```python
def get_valid_token(self):
    with self._lock:
        if self._client._ensure_token():
            return self._client._token
        return None
```

Nachher (Double-Checked Locking):
```python
def get_valid_token(self):
    if not self._initialized or not self._client:
        return None
    
    # Schneller Pfad: Token noch gültig? (read-only, keine Mutation)
    if self._is_token_valid():
        return self._client._token
    
    # Langsamer Pfad: Token erneuern (mit Lock)
    with self._lock:
        # Nochmal prüfen (anderer Thread könnte refreshed haben)
        if self._is_token_valid():
            return self._client._token
        
        # Tatsächlich refreshen
        if self._client._ensure_token():
            return self._client._token
        return None
```

### `SharedTokenManager.build_soap_header()`
Gleiches Pattern wie `get_valid_token()`.

### Neue Hilfsmethode: `SharedTokenManager._is_token_valid() -> bool`
```python
def _is_token_valid(self) -> bool:
    """Prüft ob das Token noch gültig ist (lock-free)."""
    if not self._client or not self._client._token:
        return False
    if self._client._token_expires is None:
        return True  # Kein Expiry bekannt → als gültig annehmen
    buffer = timedelta(minutes=1)
    return datetime.now(timezone.utc) + buffer < self._client._token_expires
```

## Risikoanalyse

- **Stale Read**: Im schnellen Pfad wird `_token` und `_token_expires` ohne Lock gelesen. In Python ist das für einfache Attribut-Zuweisungen sicher (GIL schützt einzelne Zuweisungen).
- **TOCTOU**: Zwischen `_is_token_valid()` und `return self._client._token` könnte Token ablaufen. Risiko: Minimal (1 Minute Buffer).
- **Regression**: Lock-Schutz für Mutation bleibt erhalten, nur Read ist lock-free.

## Validierung

- 10 parallele Worker: Token wird nur 1x geholt
- Schneller Pfad: Kein Lock-Contention
- Token-Ablauf: Korrekt erkannt und erneuert
