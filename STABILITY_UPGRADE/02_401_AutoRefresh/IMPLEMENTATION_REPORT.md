# Task 02 - JWT 401 Auto-Refresh: Implementation Report

## STATUS: COMPLETE

---

## Geaenderte Dateien

### 1. `src/api/client.py`

| Aenderung | Details |
|-----------|---------|
| **Import hinzugefuegt** | `import threading` (Zeile 9) |
| **Import erweitert** | `Callable` zu `from typing import Optional, Dict, Any, Callable` (Zeile 10) |
| **`__init__` erweitert** | `_auth_refresh_callback: Optional[Callable[[], bool]] = None` (Zeile 52) |
| **`__init__` erweitert** | `_auth_refresh_lock = threading.Lock()` (Zeile 53) |
| **Neue Methode** | `set_auth_refresh_callback(callback)` - Registriert Refresh-Callback (Zeile 83-90) |
| **Neue Methode** | `_try_auth_refresh()` - Thread-safe Refresh-Ausfuehrung mit Lock (Zeile 92-97) |
| **`get()` erweitert** | 401-Retry mit `except APIError` Block (Zeile 136-151) |
| **`post()` erweitert** | 401-Retry mit `except APIError` Block (Zeile 171-187) |
| **`put()` erweitert** | 401-Retry mit `except APIError` Block (Zeile 206-221) |
| **`delete()` erweitert** | 401-Retry mit `except APIError` Block (Zeile 239-253) |
| **`upload_file()` erweitert** | 401-Retry mit `except APIError` Block, inkl. Header-Refresh (Zeile 280-301) |
| **`download_file()` umgebaut** | 401-Retry als Wrapper um neue `_download_file_inner()` (Zeile 308-334) |
| **Neue Methode** | `_download_file_inner()` - Innere Download-Logik mit 401 sofort-raise (Zeile 336-416) |

### 2. `src/api/auth.py`

| Aenderung | Details |
|-----------|---------|
| **Neue Methode** | `re_authenticate()` - Automatische Re-Authentifizierung (Zeile 208-249) |

Strategie der `re_authenticate()` Methode:
1. Token aus `~/.bipro_gdv_token.json` laden
2. Token im Client setzen
3. Token via `/auth/verify` validieren
4. Bei Erfolg: User-Objekt wiederherstellen, `True` zurueckgeben
5. Bei Fehler: Token clearen, `False` zurueckgeben

### 3. `src/main.py`

| Aenderung | Details |
|-----------|---------|
| **Zeile 129-130** | `api_client.set_auth_refresh_callback(auth_api.re_authenticate)` nach Login-Erfolg |

---

## Pruefpunkte

| # | Pruefpunkt | Status |
|---|-----------|--------|
| 1 | `set_auth_refresh_callback()` existiert und wird in `main.py` aufgerufen | ✅ |
| 2 | `re_authenticate()` existiert in `AuthAPI` | ✅ |
| 3 | `get()` hat 401-Retry | ✅ |
| 4 | `post()` hat 401-Retry | ✅ |
| 5 | `put()` hat 401-Retry | ✅ |
| 6 | `delete()` hat 401-Retry | ✅ |
| 7 | `upload_file()` hat 401-Retry | ✅ |
| 8 | `download_file()` hat 401-Retry | ✅ |
| 9 | Kein Endlos-Loop moeglich (nur 1 Retry pro Aufruf) | ✅ |
| 10 | Thread-safe (`_auth_refresh_lock` um Refresh-Callback) | ✅ |
| 11 | `Callable` korrekt importiert in `client.py` | ✅ |
| 12 | `threading` korrekt importiert in `client.py` | ✅ |
| 13 | Oeffentliche API aller Methoden unveraendert (gleiche Parameter, gleiche Returns) | ✅ |
| 14 | Keine Linter-Fehler | ✅ |

---

## Architektur-Entscheidungen

### Kein Endlos-Loop
Jede HTTP-Methode hat exakt ein `try/except APIError` mit einem einzigen Retry. Der Retry-Block hat ein inneres `except APIError: raise` ohne erneuten Refresh-Versuch. Damit ist max. 1 Retry garantiert.

### Thread-Safety
`_try_auth_refresh()` verwendet `threading.Lock()`. Wenn mehrere Threads gleichzeitig einen 401 erhalten, wird nur ein Thread den Refresh durchfuehren. Alle anderen warten auf den Lock und fuehren den Callback danach aus (was schnell True/False zurueckgibt, da der Token bereits erneuert/fehlgeschlagen ist).

### download_file Sonderbehandlung
`download_file()` hat eine eigene Retry-Logik (fuer 429/500/502/503/504). Die 401-Behandlung wurde als Wrapper um eine neue `_download_file_inner()` Methode implementiert, damit die bestehende Retry-Logik nicht vermischt wird. In `_download_file_inner()` wird 401 sofort als `APIError` geworfen (nicht in die Retry-Schleife aufgenommen).

### upload_file Header-Refresh
`upload_file()` baut Authorization-Header manuell (nicht ueber `_get_headers()`). Daher wird beim Retry der Header neu aufgebaut, um den erneuerten Token zu verwenden.
