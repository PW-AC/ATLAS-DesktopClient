# Reproduktion: Auto-Refresh App Freeze

## Reproduktionsschritte (User-Report)

1. App starten und einloggen
2. Zur Archiv-Ansicht (ArchiveBoxesView) navigieren
3. 90 Sekunden warten (Auto-Refresh Intervall)
4. **ERGEBNIS:** App friert komplett ein, muss geschlossen werden

## Statische Reproduktion (Code-Pfad)

### Deadlock-Szenario für BUG-0001/0002/0003

```
Thread-Flow:

T1: Main-Thread (UI)
T2: Background-Thread (threading.Thread in DataCacheService)

Ablauf:
─────────────────────────────────────────────────────────────────────
Zeit  │ T1 (Main-Thread)              │ T2 (Background-Thread)
─────────────────────────────────────────────────────────────────────
t0    │                               │ Timer löst _on_auto_refresh() aus
t1    │                               │ _refresh_all_background() startet
t2    │                               │ self._cache_lock.acquire() ✓
t3    │                               │ self._load_documents() läuft
t4    │                               │ QTimer.singleShot(0, signal.emit)
t5    │ Signal kommt an              │ (wartet auf Main-Thread)
t6    │ _on_cache_documents_updated() │ 
t7    │ _load_documents_from_cache()  │
t8    │ get_documents() aufgerufen    │
t9    │ self._cache_lock.acquire()    │ self._cache_lock hält Lock
      │ ↳ BLOCKIERT!                  │ ↳ wartet auf Signal-Verarbeitung
─────────────────────────────────────────────────────────────────────
      │        ⚡ DEADLOCK ⚡           │
─────────────────────────────────────────────────────────────────────
```

### Warum tritt der Deadlock auf?

1. `threading.Thread` hat keine Qt Event-Loop
2. Ohne Event-Loop kann `QueuedConnection` nicht garantieren, dass Signals korrekt gepuffert werden
3. Der Background-Thread hält den Lock während er auf die Signal-Verarbeitung wartet
4. Der Main-Thread braucht den Lock um das Signal zu verarbeiten
5. **Zirkuläre Abhängigkeit → Deadlock**

## Betroffene Dateien

| Datei | Kritische Zeilen |
|-------|------------------|
| `src/services/data_cache.py` | 322 (threading.Thread), 332/344/349/357 (emit) |
| `src/ui/archive_boxes_view.py` | 1107, 1211-1217, 1252-1253 (Lock-Zugriffe) |
