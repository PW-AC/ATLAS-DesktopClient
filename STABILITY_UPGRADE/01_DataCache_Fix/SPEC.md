# Task 01: DataCache Race Condition Fix (P0)

## Problem

`DataCacheService` in `src/services/data_cache.py` hat eine Race Condition bei `_pause_count` und `_refresh_in_progress`. Diese Variablen werden von mehreren Threads gelesen und geschrieben, ohne Lock-Schutz.

## Root Cause

- `_pause_count += 1` und `_pause_count -= 1` sind in Python **nicht atomar** (read-modify-write)
- `_refresh_in_progress = True/False` ist ein Boolean ohne Lock
- Mehrere Threads rufen `pause_auto_refresh()` / `resume_auto_refresh()` gleichzeitig auf (z.B. BiPRO-Download + Dokumenten-Verarbeitung)

## Technische Analyse

Betroffene Methoden (alle in `src/services/data_cache.py`):
- `pause_auto_refresh()` (Zeile 305): `self._pause_count += 1` ohne Lock
- `resume_auto_refresh()` (Zeile 330): `self._pause_count -= 1` ohne Lock  
- `is_auto_refresh_paused()` (Zeile 346): `return self._pause_count > 0` ohne Lock
- `_on_auto_refresh()` (Zeile 350): `if self._refresh_in_progress:` ohne Lock
- `refresh_all_async()` (Zeile 359): `self._refresh_in_progress = True` ohne Lock
- `_refresh_all_background()` (Zeile 406): `self._refresh_in_progress = False` ohne Lock

Es existiert bereits ein `self._cache_lock = threading.Lock()` (Zeile 101) der für Cache-Daten genutzt wird. Diesen Lock für die Counter/Flags mitnutzen.

## Zielzustand

- Alle Zugriffe auf `_pause_count`, `_was_running_before_pause` und `_refresh_in_progress` sind durch `_cache_lock` geschützt
- Keine Race Condition bei parallelen pause/resume Aufrufen
- Auto-Refresh pausiert zuverlässig während Downloads/Verarbeitung
- Keine Deadlocks (Lock-Reihenfolge beachten)

## Randbedingungen

- `_cache_lock` ist ein `threading.Lock()` (nicht reentrant). Keine verschachtelten Lock-Aufrufe!
- QTimer-Callbacks laufen im Main-Thread (kein Lock nötig für Timer-Start/Stop selbst)
- `_refresh_all_background()` läuft in einem separaten daemon-Thread
- Signals müssen via `QTimer.singleShot(0, ...)` im Main-Thread emittiert werden (bereits korrekt)

## Performance-Vorgaben

- Lock-Contention minimal (Lock nur um Counter-Operationen, nicht um ganze Methoden)
- Keine Verhaltensänderung im Happy Path

## Thread-Safety-Vorgaben

- `_pause_count` darf nur unter Lock gelesen und geschrieben werden
- `_refresh_in_progress` darf nur unter Lock gelesen und geschrieben werden
- Kein Lock während Netzwerk-Calls halten

## Nicht-Ziele

- Keine Änderung der Cache-Logik selbst
- Keine Änderung der Signal-Emission
- Keine Änderung des Singleton-Patterns
- Keine neuen Features
