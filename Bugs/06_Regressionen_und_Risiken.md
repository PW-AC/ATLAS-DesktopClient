# Regressionen und Risiken

## Mögliche Regressionen

### 1. Cache-Aktualisierung nach Dokumenten-Load

**Betroffener Code:** `_on_documents_loaded()` in archive_boxes_view.py

**Risiko:** Das manuelle Cache-Befüllen wurde entfernt. Wenn der Worker Daten lädt, werden diese jetzt NICHT mehr im zentralen Cache gespeichert.

**Auswirkung:** Bei erneutem Anfordern der gleichen Daten wird ein neuer API-Call gemacht statt aus dem Cache zu lesen.

**Bewertung:** ⚠️ AKZEPTABEL - Der Cache wird beim nächsten Auto-Refresh (90s) oder bei explizitem `get_documents()` Call befüllt. Performance-Impact minimal.

**Langfristige Lösung:** Eine öffentliche `update_documents(box_type, documents)` Methode zum Cache-Service hinzufügen.

---

### 2. Stats-Refresh nach manuellem Load

**Betroffener Code:** `_on_stats_loaded()` in archive_boxes_view.py

**Risiko:** Nach dem Fix wird `get_stats(force_refresh=True)` aufgerufen, was einen **synchronen** API-Call macht.

**Auswirkung:** UI kann kurz blockieren bei langsamer Netzwerkverbindung.

**Bewertung:** ⚠️ NIEDRIG - Bereits vorher vorhanden, nicht durch den Fix eingeführt.

**Langfristige Lösung:** Stats-Refresh asynchron machen oder den redundanten Call entfernen (Cache wird bereits durch Worker befüllt).

---

## Verbleibende Risiken

### 1. threading.Thread vs QThread

**Problem:** `DataCacheService` verwendet weiterhin `threading.Thread` statt `QThread`.

**Risiko:** Bei zukünftigen Änderungen könnte das Problem wieder auftreten, wenn Entwickler `QueuedConnection` als ausreichend ansehen.

**Empfehlung:** Dokumentation hinzufügen oder Refactoring zu QThread.

---

### 2. Synchrone API-Calls im Main-Thread

**Betroffene Stellen:**
- `src/ui/archive_boxes_view.py`: `_on_stats_loaded()` Zeile 1189
- `src/ui/bipro_view.py`: `_load_connections()` Zeilen 2570, 2580

**Risiko:** UI kann bei langsamer Netzwerkverbindung einfrieren (nicht Deadlock, aber schlechte UX).

**Empfehlung:** Asynchrone Worker für alle API-Calls verwenden.

---

## Getestete angrenzende Funktionen

| Funktion | Getestet | Ergebnis |
|----------|----------|----------|
| Box-Wechsel | Code-Review | OK |
| Dokument-Upload | Code-Review | OK |
| Stats-Refresh | Code-Review | OK - mit Einschränkung (synchron) |
| Auto-Refresh | Ausstehend | - |

---

## Architektur-Empfehlungen

1. **STRICT API BOUNDARY:** UI-Komponenten sollten NIEMALS auf `_cache._*` Attribute zugreifen
2. **QThread statt threading.Thread:** Für bessere Qt-Integration
3. **Async-Only Pattern:** Alle Server-Calls über Worker-Threads
4. **Type Hints:** Öffentliche API klar typisieren um Missbrauch zu verhindern
