# Bug-Liste: Auto-Refresh App Freeze

## BUG-0001: Signal-Emission aus threading.Thread

- **Kurzbeschreibung:** Signals wurden direkt aus einem `threading.Thread` emittiert
- **Betroffene Komponente:** `src/services/data_cache.py`
- **Sichtbares Fehlverhalten:** App friert nach Auto-Refresh ein
- **Erwartetes Verhalten:** App sollte responsiv bleiben
- **Quelle:** Code-Analyse
- **Status:** ✅ FIXED

---

## BUG-0002: Direkter Lock-Zugriff in _refresh_documents()

- **Kurzbeschreibung:** Direkter Zugriff auf `_cache._cache_lock` in UI-Methode
- **Betroffene Komponente:** `src/ui/archive_boxes_view.py` (Zeile 1211-1217)
- **Sichtbares Fehlverhalten:** Deadlock wenn Background-Thread Lock hält
- **Erwartetes Verhalten:** Thread-safe Zugriff über öffentliche API
- **Quelle:** Code-Analyse
- **Status:** ✅ FIXED

**Original-Code:**
```python
with self._cache._cache_lock:
    cache_entry = self._cache._documents_cache.get(cache_key or 'all')
    if cache_entry and not cache_entry.is_expired():
        documents = cache_entry.data
        self._apply_filters_and_display(documents)
        return
```

---

## BUG-0003: Direkter Lock-Zugriff in _on_documents_loaded()

- **Kurzbeschreibung:** Manuelles Cache-Befüllen mit direktem Lock-Zugriff
- **Betroffene Komponente:** `src/ui/archive_boxes_view.py` (Zeile 1252-1253)
- **Sichtbares Fehlverhalten:** Deadlock wenn Background-Thread Lock hält
- **Erwartetes Verhalten:** Cache wird automatisch durch API befüllt
- **Quelle:** Code-Analyse
- **Status:** ✅ FIXED

**Original-Code:**
```python
from services.data_cache import CacheEntry
with self._cache._cache_lock:
    self._cache._documents_cache[cache_key] = CacheEntry(data=documents)
```

---

## BUG-0004: Direkter Cache-Zugriff in _on_stats_loaded()

- **Kurzbeschreibung:** Direkter Zugriff auf `_cache._stats_cache`
- **Betroffene Komponente:** `src/ui/archive_boxes_view.py` (Zeile 1188)
- **Sichtbares Fehlverhalten:** Nicht thread-safe, potenzielle Race Condition
- **Erwartetes Verhalten:** Verwendung der öffentlichen `invalidate_stats()` Methode
- **Quelle:** Code-Analyse
- **Status:** ✅ FIXED

**Original-Code:**
```python
self._cache._stats_cache = None  # Invalidieren
```

---

## BUG-0005: Synchroner API-Call in _on_stats_loaded()

- **Kurzbeschreibung:** `get_stats(force_refresh=True)` macht synchronen Server-Call im Main-Thread
- **Betroffene Komponente:** `src/ui/archive_boxes_view.py` (Zeile 1189)
- **Sichtbares Fehlverhalten:** UI kann kurzzeitig einfrieren bei langsamer Netzwerkverbindung
- **Erwartetes Verhalten:** Asynchroner Call oder Weglassen (Cache wird bereits durch Worker befüllt)
- **Quelle:** Code-Analyse
- **Status:** ⚠️ RISIKO (nicht kritisch für Deadlock, aber suboptimal)

**Betroffener Code:**
```python
self._cache.get_stats(force_refresh=True)  # Neu laden in Cache
```

---

## BUG-0006: Synchroner API-Call in _load_connections()

- **Kurzbeschreibung:** `vu_api.list_connections()` macht synchronen Server-Call im Main-Thread
- **Betroffene Komponente:** `src/ui/bipro_view.py` (Zeile 2570, 2580)
- **Sichtbares Fehlverhalten:** UI kann kurzzeitig einfrieren bei langsamer Netzwerkverbindung
- **Erwartetes Verhalten:** Asynchroner Call mit QThread-Worker
- **Quelle:** Code-Analyse
- **Status:** ⚠️ RISIKO (nicht kritisch für Deadlock)

**Betroffener Code:**
```python
self._connections = self.vu_api.list_connections()
```
