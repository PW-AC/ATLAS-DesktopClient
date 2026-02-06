# Change Plan: Task 02 - JWT 401 Auto-Refresh

## Betroffene Dateien

| Datei | Änderung |
|-------|----------|
| `src/api/client.py` | 401-Retry-Logik, Token-Refresh-Callback, Thread-sicherer Refresh |
| `src/api/auth.py` | `re_authenticate()` Methode (nutzt gespeicherten Token-File) |
| `src/main.py` | AuthAPI-Referenz an APIClient übergeben |

## Neue Methoden

### `APIClient._request_with_auth_retry(method, url, **kwargs)` 
- Zentrale Request-Methode die bei 401 einen Token-Refresh versucht
- Max. 1 Retry pro Request
- Thread-safe: Lock um Token-Refresh

### `APIClient.set_auth_callback(callback: Callable)`
- Registriert eine Callback-Funktion die bei 401 aufgerufen wird
- Callback gibt `True` zurück wenn Token erfolgreich erneuert, `False` wenn nicht
- Pattern: Dependency Injection statt direkter AuthAPI-Referenz

### `AuthAPI.re_authenticate() -> bool`
- Versucht automatische Re-Authentifizierung
- Strategie: Gespeicherter Token prüfen → falls ungültig, AuthState zurücksetzen
- Returns: True wenn neuer Token gesetzt

## Geänderte Methoden

### `APIClient.get/post/put/delete/upload_file`
- Nutzen intern `_request_with_auth_retry()` statt direktem `self._session.request()`
- Keine Änderung der öffentlichen API

### `APIClient._handle_response()`
- KEINE Änderung (wirft weiterhin bei 401)
- Die Retry-Logik sitzt eine Ebene höher

## Lock-Strategie

```python
class APIClient:
    def __init__(self, ...):
        ...
        self._auth_refresh_lock = threading.Lock()
        self._auth_callback: Optional[Callable] = None
    
    def _try_auth_refresh(self) -> bool:
        with self._auth_refresh_lock:
            if self._auth_callback:
                return self._auth_callback()
            return False
```

## Migration Steps

1. `APIClient` bekommt `_auth_refresh_lock` und `_auth_callback`
2. Neue Methode `set_auth_callback()` 
3. `get/post/put/delete/upload_file` wrappen Request in try/except APIError(401)
4. `AuthAPI` bekommt `re_authenticate()` 
5. In `src/main.py`: Nach Login `client.set_auth_callback(auth.re_authenticate)` setzen

## Risikoanalyse

- **Endlos-Loop**: Verhindert durch max. 1 Retry (Flag `_is_retrying`)
- **Race Condition**: Lock stellt sicher nur ein Thread refreshed
- **Token-File**: Bereits existierend in `AuthAPI._load_saved_token()` 
- **Kein Backend-Change**: Re-Auth nutzt `/auth/verify` oder scheitert graceful

## Validierung

- 401 bei normalem API-Call → automatischer Retry
- 401 nach Re-Auth-Versuch → Exception propagiert (kein Endlos-Loop)
- Parallele Threads: Nur einer refreshed, andere warten
