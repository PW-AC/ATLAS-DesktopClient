# Task 01 - DataCache Race Condition Fix

## STATUS: COMPLETE

## Geänderte Datei

`src/services/data_cache.py`

## Geänderte Methoden

| # | Methode | Änderung |
|---|---------|----------|
| 1 | `pause_auto_refresh()` | `_pause_count += 1` und `_was_running_before_pause` Zustandslesen unter `self._cache_lock`. Timer-Stop (`QTimer.stop()`) außerhalb des Locks. Lokale Variable `should_stop` als Lock-Exit-Flag. |
| 2 | `resume_auto_refresh()` | `_pause_count -= 1` und `_was_running_before_pause` Lesung unter `self._cache_lock`. Timer-Start (`QTimer.start()`) außerhalb des Locks. Lokale Variable `should_resume` als Lock-Exit-Flag. |
| 3 | `is_auto_refresh_paused()` | `_pause_count > 0` Read unter `self._cache_lock`. |
| 4 | `_on_auto_refresh()` | `_refresh_in_progress` Check unter `self._cache_lock`. Early-Return innerhalb des Lock-Blocks. `refresh_all_async()` Aufruf außerhalb des Locks. |
| 5 | `refresh_all_async()` | `_refresh_in_progress` Check und Set (`= True`) atomar unter `self._cache_lock`. `emit()` und Thread-Start außerhalb des Locks. |
| 6 | `_refresh_all_background()` | Im `finally`-Block: `_refresh_in_progress = False` unter `self._cache_lock`. `QTimer.singleShot()` außerhalb des Locks. |

## Prüfpunkte

| # | Prüfpunkt | Ergebnis |
|---|-----------|----------|
| 1 | Alle `_pause_count` Zugriffe unter Lock | ✅ BESTANDEN (Zeilen 322, 323, 342, 343, 344, 353) |
| 2 | Alle `_refresh_in_progress` Zugriffe unter Lock | ✅ BESTANDEN (Zeilen 358, 371, 373, 413; Zeile 109 ist `__init__`, single-threaded) |
| 3 | Alle `_was_running_before_pause` Zugriffe unter Lock | ✅ BESTANDEN (Zeile 326 Write unter Lock; Zeile 328 Read außerhalb aber durch lokale `should_stop` Variable geschützt; Zeile 344 Read unter Lock) |
| 4 | Kein Lock während Timer-Operationen oder `emit()` | ✅ BESTANDEN (`stop()` Z.329, `start()` Z.347, `emit()` Z.375, `QTimer.singleShot()` Z.414 — alle außerhalb Lock) |
| 5 | Keine verschachtelten Lock-Aufrufe (Deadlock-Risiko) | ✅ BESTANDEN (`_on_auto_refresh()` released Lock vor `refresh_all_async()` Aufruf; keine Methode hält Lock während Aufruf einer anderen Lock-Methode) |

## Pattern

Alle Fixes folgen dem gleichen Pattern:
1. **Lock acquire** → Shared State lesen/schreiben → Entscheidung in lokale Variable kopieren → **Lock release**
2. Außerhalb des Locks: Qt-Operationen (Timer start/stop, Signal emit) basierend auf lokaler Variable

Dieses Pattern verhindert Race Conditions UND vermeidet Deadlocks durch Qt's Main-Thread-Affinität.

## Öffentliche API

Keine Änderungen an der öffentlichen API. Alle Methodensignaturen und Rückgabewerte sind identisch.
