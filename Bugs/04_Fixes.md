# Fixes: Auto-Refresh App Freeze

## BUG-0001: Signal-Emission aus threading.Thread

### Fix-Design
Alle Signal-Emissionen aus dem Background-Thread werden über `QTimer.singleShot(0, ...)` explizit im Main-Thread gequeuet.

### Fix-Code

**Datei:** `src/services/data_cache.py`

```python
# VORHER (Deadlock-Gefahr):
self.stats_updated.emit()
self.documents_updated.emit(box_type)
self.connections_updated.emit()
self.refresh_finished.emit()

# NACHHER (Thread-safe):
QTimer.singleShot(0, self.stats_updated.emit)
QTimer.singleShot(0, lambda bt=box_type: self.documents_updated.emit(bt))
QTimer.singleShot(0, self.connections_updated.emit)
QTimer.singleShot(0, self.refresh_finished.emit)
```

### Warum funktioniert das?
`QTimer.singleShot(0, callback)` schedult die Callback-Ausführung im Thread, der den QTimer besitzt - standardmäßig der Main-Thread. Damit wird die Signal-Emission garantiert im Main-Thread ausgeführt.

---

## BUG-0002: Direkter Lock-Zugriff in _refresh_documents()

### Fix-Design
Verwendung der öffentlichen Thread-safe API statt direktem Lock-Zugriff.

### Fix-Code

**Datei:** `src/ui/archive_boxes_view.py`

```python
# VORHER (Deadlock-Gefahr):
with self._cache._cache_lock:
    cache_entry = self._cache._documents_cache.get(cache_key or 'all')
    if cache_entry and not cache_entry.is_expired():
        documents = cache_entry.data
        self._apply_filters_and_display(documents)
        return

# NACHHER (Thread-safe):
documents = self._cache.get_documents(box_type=cache_key, force_refresh=False)
if documents:
    self._apply_filters_and_display(documents)
    return
```

---

## BUG-0003: Direkter Lock-Zugriff in _on_documents_loaded()

### Fix-Design
Entfernung des manuellen Cache-Befüllens - der Cache wird durch die API automatisch verwaltet.

### Fix-Code

**Datei:** `src/ui/archive_boxes_view.py`

```python
# VORHER (Deadlock-Gefahr):
cache_key = self._current_box if self._current_box else 'all'
from services.data_cache import CacheEntry
with self._cache._cache_lock:
    self._cache._documents_cache[cache_key] = CacheEntry(data=documents)

# NACHHER (Thread-safe):
# Cache wird automatisch durch get_documents() bei Bedarf befuellt
# Kein manuelles Befuellen noetig (und kein direkter Lock-Zugriff!)
```

---

## BUG-0004: Direkter Cache-Zugriff in _on_stats_loaded()

### Fix-Design
Verwendung der öffentlichen `invalidate_stats()` Methode.

### Fix-Code

**Datei:** `src/ui/archive_boxes_view.py`

```python
# VORHER (Nicht thread-safe):
self._cache._stats_cache = None  # Invalidieren

# NACHHER (Thread-safe):
self._cache.invalidate_stats()
```

---

## Zusammenfassung der Änderungen

| Datei | Änderung |
|-------|----------|
| `src/services/data_cache.py` | 4x Signal-Emission mit QTimer.singleShot |
| `src/ui/archive_boxes_view.py` | 3x Direkter Cache-Zugriff → Öffentliche API |
