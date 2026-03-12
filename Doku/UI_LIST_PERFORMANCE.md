# ACENCIA ATLAS – Listen- und Scrollbar-Performance

> **Erstellt:** 2026-03-11
> **Scope:** Große Listen (Archiv-Boxen, Dokumente, Provisionen)
> **Zweck:** Empfehlungen für virtualisiertes Scrolling und On-Demand-Loading.

---

## Ist-Zustand

| View | Implementierung | Virtualisierung |
|------|-----------------|-----------------|
| `archive_boxes_view` | QTableView + DocumentTableModel + Delegate | ✓ Qt virtualisiert sichtbare Zeilen |
| `archive_view` (Legacy) | QTableWidget + QTableWidgetItem | ✗ Jedes Item = eigenes Widget |
| `bipro_view` (Shipments) | QTableWidget | ✗ |
| `provision/*` | QTableView + Model (xempus, zuordnung, etc.) | ✓ |
| `workforce/*` | QTableWidget (employees, exports, triggers, etc.) | ✗ |

---

## Empfehlungen

### 1. QTableView + QAbstractTableModel statt QTableWidget

**Vorteil:** Qt ruft `data()` nur für sichtbare Zeilen auf (~30 statt 500+). Kein Item-Spam, kein Rebuild, kein UI-Freeze.

**Referenz:** `archive/models.py` – `DocumentTableModel`, `archive/table.py` – `DraggableDocumentView`.

**Migration:** Views mit QTableWidget (archive_view, bipro_view, workforce/*) analog zu archive_boxes migrieren.

### 2. QListView mit Custom Delegate statt einzelnen Widgets pro Row

Für Listen-artige UIs (keine Tabellen): `QListView` + `QStyledItemDelegate` statt `QListWidget` mit vielen `QListWidgetItem`-Sub-Widgets.

### 3. fetchMore() / canFetchMore() für On-Demand-Loading

**Voraussetzung:** API muss Pagination unterstützen (offset/limit oder cursor).

**Aktuell:** `DocumentsAPI.list_documents()` hat `limit`, aber kein `offset`. Server-seitige Pagination wäre nötig.

**Implementierung (wenn API bereit):**

```python
def canFetchMore(self, parent=QModelIndex()) -> bool:
    return self._has_more and not self._loading

def fetchMore(self, parent=QModelIndex()):
    if self._loading or not self._has_more:
        return
    self._loading = True
    # API-Call mit offset=len(self._documents), limit=100
    # beginInsertRows / endInsertRows
    self._loading = False
```

---

## Nächste Schritte

1. **archive_view:** Migration zu QTableView + DocumentTableModel (oder eigenes Model) – analog archive_boxes.
2. **API:** Pagination für `list_documents` (offset, limit) ergänzen, falls >1000 Dokumente typisch sind.
3. **workforce/bipro:** Bei Performance-Problemen schrittweise auf QTableView+Model umstellen.
