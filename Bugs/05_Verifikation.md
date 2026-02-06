# Verifikation: Auto-Refresh App Freeze

## BUG-0001: Signal-Emission aus threading.Thread

### Testschritte
1. App starten und einloggen
2. Zur Archiv-Ansicht navigieren
3. 90+ Sekunden warten (Auto-Refresh auslösen)
4. Prüfen ob App responsiv bleibt

### Ergebnis vorher
App friert ein, muss geschlossen werden

### Ergebnis nachher
⏳ **AUSSTEHEND** - Muss vom Benutzer getestet werden

### Status: PENDING_TEST

---

## BUG-0002: Direkter Lock-Zugriff in _refresh_documents()

### Testschritte
1. Zur Archiv-Ansicht navigieren
2. Zwischen Boxen wechseln während Auto-Refresh läuft

### Ergebnis vorher
Potentieller Deadlock bei ungünstigem Timing

### Ergebnis nachher
⏳ **AUSSTEHEND** - Muss vom Benutzer getestet werden

### Status: PENDING_TEST

---

## BUG-0003: Direkter Lock-Zugriff in _on_documents_loaded()

### Testschritte
1. Dokument hochladen oder verschieben
2. Während Auto-Refresh aktiv

### Ergebnis vorher
Potentieller Deadlock bei ungünstigem Timing

### Ergebnis nachher
⏳ **AUSSTEHEND** - Muss vom Benutzer getestet werden

### Status: PENDING_TEST

---

## BUG-0004: Direkter Cache-Zugriff in _on_stats_loaded()

### Testschritte
1. Stats-Refresh auslösen
2. Während Auto-Refresh aktiv

### Ergebnis vorher
Potentielle Race Condition

### Ergebnis nachher
⏳ **AUSSTEHEND** - Muss vom Benutzer getestet werden

### Status: PENDING_TEST

---

## Code-Verifikation

### Direkter Lock-Zugriff in UI-Komponenten

```bash
# Suche nach verbleibenden direkten Lock-Zugriffen
grep -r "_cache\._" src/ui/
```

**Ergebnis:** Keine Treffer ✅

### QTimer.singleShot in data_cache.py

```python
# Alle Signal-Emissionen in _refresh_all_background():
QTimer.singleShot(0, self.stats_updated.emit)       # Zeile 332
QTimer.singleShot(0, lambda bt=box_type: ...)       # Zeile 344
QTimer.singleShot(0, self.connections_updated.emit) # Zeile 349
QTimer.singleShot(0, self.refresh_finished.emit)    # Zeile 357
```

**Ergebnis:** Alle Emissionen verwenden QTimer.singleShot ✅

### Linter-Check

```
ReadLints: src/services/data_cache.py
ReadLints: src/ui/archive_boxes_view.py
```

**Ergebnis:** Keine Linter-Fehler ✅
