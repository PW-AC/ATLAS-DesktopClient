# Bug-Analyse: Auto-Refresh App Freeze

**Analyse-Datum:** 2026-02-03
**Betroffene Komponente:** DataCacheService, ArchiveBoxesView, BiPROView
**Symptom:** App friert nach Auto-Refresh ein

## Übersicht

| ID | Bug | Status | Schwere |
|----|-----|--------|---------|
| BUG-0001 | Signal-Emission aus threading.Thread | ✅ FIXED | KRITISCH |
| BUG-0002 | Direkter Lock-Zugriff in _refresh_documents() | ✅ FIXED | KRITISCH |
| BUG-0003 | Direkter Lock-Zugriff in _on_documents_loaded() | ✅ FIXED | KRITISCH |
| BUG-0004 | Direkter Cache-Zugriff in _on_stats_loaded() | ✅ FIXED | MITTEL |
| BUG-0005 | Synchroner API-Call in _on_stats_loaded() | ⚠️ RISIKO | NIEDRIG |
| BUG-0006 | Synchroner API-Call in _load_connections() | ⚠️ RISIKO | NIEDRIG |

## Navigation

- [01_Bugliste.md](01_Bugliste.md) - Alle identifizierten Bugs
- [02_Reproduktion.md](02_Reproduktion.md) - Reproduktionsschritte
- [03_Root_Cause_Analyse.md](03_Root_Cause_Analyse.md) - Ursachenanalyse
- [04_Fixes.md](04_Fixes.md) - Fix-Design & -Umsetzung
- [05_Verifikation.md](05_Verifikation.md) - Testdokumentation
- [06_Regressionen_und_Risiken.md](06_Regressionen_und_Risiken.md) - Nebenwirkungen

## Zusammenfassung

Das Einfrieren der App wurde durch **Deadlocks** verursacht, die entstanden wenn:
1. Background-Thread den `_cache_lock` hielt
2. Main-Thread gleichzeitig versuchte den Lock zu bekommen

Die primären Fixes waren:
1. `QTimer.singleShot(0, ...)` für Signal-Emission aus threading.Thread
2. Entfernung aller direkten Lock-Zugriffe (`_cache._cache_lock`) in UI-Komponenten
3. Verwendung der öffentlichen Thread-safe API-Methoden
