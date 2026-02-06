# Root Cause Analyse: Auto-Refresh App Freeze

## BUG-0001: Signal-Emission aus threading.Thread

### Root Cause (konkret)
`threading.Thread` hat keine Qt Event-Loop. Qt's `QueuedConnection` funktioniert nur zuverlässig, wenn beide Threads Qt-Threads mit Event-Loops sind. Bei einem reinen Python-Thread kann die Signal-Emission nicht korrekt gepuffert werden.

### Betroffene Dateien/Zeilen
- `src/services/data_cache.py`: Zeile 322 (thread = threading.Thread)
- `src/services/data_cache.py`: Zeilen 332, 344, 349, 357 (Signal-Emissionen)

### Warum tritt der Bug auf?
Der Code nimmt an, dass `QueuedConnection` ausreicht um Thread-sichere Signal-Emission zu garantieren. Das stimmt nur für Qt-Threads mit Event-Loop.

### Warum wurde er nicht früher erkannt?
- Der Bug tritt nur unter bestimmten Timing-Bedingungen auf
- Bei schnellen API-Antworten ist das Race-Window klein
- Ohne explizites Threading-Debugging schwer zu identifizieren

---

## BUG-0002: Direkter Lock-Zugriff in _refresh_documents()

### Root Cause (konkret)
UI-Code greift direkt auf interne Cache-Variablen (`_cache._cache_lock`, `_cache._documents_cache`) zu, statt die thread-safe öffentliche API zu verwenden.

### Betroffene Dateien/Zeilen
- `src/ui/archive_boxes_view.py`: Zeilen 1211-1217

### Warum tritt der Bug auf?
Performance-Optimierung: Der Entwickler wollte einen schnellen Cache-Check ohne API-Overhead. Die Konsequenz (Deadlock bei Concurrent Access) wurde nicht bedacht.

### Warum wurde er nicht früher erkannt?
- Funktioniert meistens, wenn kein Auto-Refresh läuft
- Deadlock tritt nur bei ungünstigem Timing auf

---

## BUG-0003: Direkter Lock-Zugriff in _on_documents_loaded()

### Root Cause (konkret)
Manuelles Befüllen des Caches umgeht die Thread-Safety-Garantien der öffentlichen API.

### Betroffene Dateien/Zeilen
- `src/ui/archive_boxes_view.py`: Zeilen 1252-1253

### Warum tritt der Bug auf?
Versuch, den Cache "von außen" zu aktualisieren um erneute API-Calls zu vermeiden.

### Warum wurde er nicht früher erkannt?
- Gleiche Gründe wie BUG-0002

---

## BUG-0004: Direkter Cache-Zugriff in _on_stats_loaded()

### Root Cause (konkret)
Direkter Zugriff auf `_cache._stats_cache` ohne Lock-Schutz.

### Betroffene Dateien/Zeilen
- `src/ui/archive_boxes_view.py`: Zeile 1188

### Warum tritt der Bug auf?
Inkonsistente Nutzung der Cache-API - teils öffentliche Methoden, teils direkter Zugriff.

### Warum wurde er nicht früher erkannt?
- Weniger kritisch als die Lock-Zugriffe, da keine direkte Lock-Interaktion

---

## Grundlegendes Architektur-Problem

```
┌─────────────────────────────────────────────────────────────────┐
│                    URSACHEN-KETTE                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. threading.Thread statt QThread                              │
│     ↓                                                           │
│  2. Keine Qt Event-Loop im Background-Thread                    │
│     ↓                                                           │
│  3. QueuedConnection funktioniert nicht wie erwartet            │
│     ↓                                                           │
│  4. Signal-Emission blockiert nicht-deterministisch             │
│     ↓                                                           │
│  5. UI-Code greift direkt auf Locks zu                          │
│     ↓                                                           │
│  6. Zirkuläre Lock-Abhängigkeit                                 │
│     ↓                                                           │
│  ⚡ DEADLOCK                                                     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Empfehlung für nachhaltige Lösung

1. **Kurzfristig (implementiert):** `QTimer.singleShot(0, ...)` für alle Signal-Emissionen
2. **Mittelfristig:** Refactoring von `threading.Thread` zu `QThread`
3. **Langfristig:** Strikte Trennung zwischen Cache-Internals und öffentlicher API durchsetzen
