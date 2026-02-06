# Change Plan: Task 01 - DataCache Race Condition Fix

## Betroffene Dateien

| Datei | Änderung |
|-------|----------|
| `src/services/data_cache.py` | Lock-Schutz für `_pause_count`, `_refresh_in_progress`, `_was_running_before_pause` |

## Geänderte Methoden

### `pause_auto_refresh()` (Zeile 305-328)
- Wrap `_pause_count += 1` und Zustandsprüfung in `with self._cache_lock:`
- Timer-Stop AUSSERHALB des Locks (QTimer darf nur im Main-Thread gestoppt werden)

### `resume_auto_refresh()` (Zeile 330-344)
- Wrap `_pause_count -= 1` und Zustandsprüfung in `with self._cache_lock:`
- Timer-Start AUSSERHALB des Locks

### `is_auto_refresh_paused()` (Zeile 346-348)
- Wrap Read in `with self._cache_lock:`

### `_on_auto_refresh()` (Zeile 350-357)
- Wrap `_refresh_in_progress` Check in `with self._cache_lock:`

### `refresh_all_async()` (Zeile 359-373)
- Wrap `_refresh_in_progress` Check und Set in `with self._cache_lock:`

### `_refresh_all_background()` (Zeile 375-407)
- Wrap `_refresh_in_progress = False` in `with self._cache_lock:` im finally-Block

## Lock-Strategie

- Verwende bestehenden `self._cache_lock` (kein neuer Lock)
- Lock nur um Variablen-Zugriffe, NICHT um Netzwerk-Calls oder Timer-Operationen
- Pattern: Read/Modify unter Lock → Aktion außerhalb Lock

```python
def pause_auto_refresh(self):
    with self._cache_lock:
        self._pause_count += 1
        should_stop = (self._pause_count == 1)
        if should_stop:
            self._was_running_before_pause = self._auto_refresh_timer.isActive()
    
    # Timer-Stop außerhalb Lock (Main-Thread Operation)
    if should_stop and self._was_running_before_pause:
        self._auto_refresh_timer.stop()
        logger.info("Auto-Refresh pausiert")
```

## Risikoanalyse

- **Deadlock-Risiko**: NIEDRIG (Lock wird nie während Netzwerk-IO gehalten)
- **Performance-Impact**: KEINER (Lock nur um Counter-Operationen, Microsekunden)
- **Regression**: NIEDRIG (nur Lock hinzugefügt, keine Logikänderung)

## Validierung

- `_pause_count` kann nicht mehr durch parallele Aufrufe verloren gehen
- `_refresh_in_progress` hat konsistenten Zustand
- Bestehende Smoke-Tests müssen weiterhin passen
