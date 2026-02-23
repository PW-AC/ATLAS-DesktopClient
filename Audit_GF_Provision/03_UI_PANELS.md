# Audit: UI Panels (Provision)

**Dateien**: 9 Dateien in `src/ui/provision/`  
**Datum**: 20. Februar 2026

---

## Kritische Befunde

### U1: XempusPanel — PillBadgeDelegate-Konstruktor falsche Argumente

| Feld | Wert |
|------|------|
| **Kategorie** | Bug |
| **Schwere** | Kritisch |
| **Ort** | `xempus_panel.py`, Zeile 270-271 |

**Problem**: `PillBadgeDelegate(self._table, PILL_COLORS)` — Der Konstruktor erwartet `(color_map: dict, label_map=None, parent=None)`, aber hier wird `self._table` (QTableView) als `color_map` und `PILL_COLORS` als `label_map` übergeben.

**Auswirkung**: `AttributeError` bei jedem Paint-Event der Status-Spalte → Panel unbrauchbar.

**Fix**: `PillBadgeDelegate(PILL_COLORS, parent=self._table)`

---

### U2: XempusPanel — Loading-Overlay hat Größe 0x0

| Feld | Wert |
|------|------|
| **Kategorie** | Bug |
| **Schwere** | Kritisch |
| **Ort** | `xempus_panel.py`, Zeilen 302, 306, 484-487 |

**Problem**: `self._loading.show()` ohne vorheriges `setGeometry(self.rect())`. Overlay hat beim ersten Anzeigen Größe 0x0. `resizeEvent` nutzt nur `resize()` statt `setGeometry()`.

**Fix**: Vor `show()` stets `self._loading.setGeometry(self.rect())` aufrufen.

---

## Hohe Befunde

### U3: DashboardPanel — Synchroner API-Call im Main-Thread

| Feld | Wert |
|------|------|
| **Kategorie** | Performance / UX |
| **Schwere** | Hoch |
| **Ort** | `dashboard_panel.py`, Zeile 486-487 |

**Problem**: `_on_ranking_double_click()` ruft `self._api.get_berater_detail()` synchron im UI-Thread auf. Bei langsamem Netzwerk friert die UI ein.

**Fix**: In QThread-Worker auslagern (analog `_DashboardLoadWorker`).

---

### U4: ProvisionspositionenPanel — Synchroner Audit-Log-API-Call

| Feld | Wert |
|------|------|
| **Kategorie** | Performance / UX |
| **Schwere** | Hoch |
| **Ort** | `provisionspositionen_panel.py`, Zeile 718-743 |

**Problem**: `_load_audit()` ruft `self._api.get_audit_log()` synchron auf. Bei jeder Zeilenselektion wird die UI blockiert.

**Fix**: Audit-Load in separaten Worker auslagern.

---

### U5: ZuordnungPanel — Synchroner Auto-Match-API-Call

| Feld | Wert |
|------|------|
| **Kategorie** | Performance / UX |
| **Schwere** | Hoch |
| **Ort** | `zuordnung_panel.py`, Zeile 358-367 |

**Problem**: `_trigger_auto_match()` synchron. Auto-Matching bei 15.000+ Zeilen dauert Sekunden. Kein Loading-Indikator, kein Fehlerhandling.

**Fix**: Worker + Loading-Overlay + Error-Toast.

---

### U6: ZuordnungPanel — 5000er Bulk-Load für Klärfälle

| Feld | Wert |
|------|------|
| **Kategorie** | Performance |
| **Schwere** | Hoch |
| **Ort** | `zuordnung_panel.py`, `_ClearanceLoadWorker`, Zeile 60-68 |

**Problem**: Lädt ALLE 5000 Commissions und filtert client-seitig. Der Server hat `/pm/clearance` für genau diese Counts.

**Fix**: Dedizierten Filter-Parameter nutzen oder Clearance-Endpoint verwenden.

---

### U7: AuszahlungenPanel — Synchroner Positions-Load

| Feld | Wert |
|------|------|
| **Kategorie** | Performance / UX |
| **Schwere** | Hoch |
| **Ort** | `auszahlungen_panel.py`, Zeile 443 |

**Problem**: `_load_positions()` ruft `self._api.get_commissions()` synchron auf.

**Fix**: Worker verwenden.

---

### U8: XempusPanel — Detail-Worker Signal-Leak

| Feld | Wert |
|------|------|
| **Kategorie** | Bug / Memory |
| **Schwere** | Hoch |
| **Ort** | `xempus_panel.py`, Zeile 435-441 |

**Problem**: Neuer `_DetailLoadWorker` wird erstellt ohne alte Signale zu disconnecten. Bei schnellem Zeilenwechsel: alter Worker beendet nach neuem → doppelte Inhalte oder Crash.

**Fix**: Vor neuem Worker: `try: self._detail_worker.finished.disconnect() / except RuntimeError: pass`

---

### U9: AbrechnungslaeufPanel — Parse-Worker nicht korrekt abbrechbar

| Feld | Wert |
|------|------|
| **Kategorie** | Bug |
| **Schwere** | Hoch |
| **Ort** | `abrechnungslaeufe_panel.py`, Zeile 432-434 |

**Problem**: `_parse_worker.quit()` hat keinen Effekt (kein Event-Loop in `run()`). `wait(2000)` blockiert UI für 2 Sekunden.

**Fix**: `_cancelled`-Flag im Worker, oder Signal-Disconnect + alten Worker ignorieren.

---

## Mittlere Befunde

### U10: Synchrone API-Calls in Dialogen (4 Stellen)

| Feld | Wert |
|------|------|
| **Kategorie** | Performance / UX |
| **Schwere** | Mittel |
| **Ort** | `provisionspositionen_panel.py` 745-749, 808-813; `zuordnung_panel.py` 380, 423, 514 |

**Problem**: `ignore_commission()`, `create_mapping()`, `get_employees()`, `trigger_auto_match()` synchron. Einzeln schnell, `get_employees()` sollte gecacht werden.

---

### U11: Hardcodierte deutsche Strings (15+)

| Feld | Wert |
|------|------|
| **Kategorie** | i18n-Verstoß |
| **Schwere** | Mittel |

| Datei | Zeile | String |
|-------|-------|--------|
| `dashboard_panel.py` | 81 | `"Provision nach Abzug aller Anteile"` |
| `dashboard_panel.py` | 88 | `"Summe aller negativen Korrekturbuchungen"` |
| `abrechnungslaeufe_panel.py` | 183 | `"Aktueller Pruefstatus des Abrechnungslaufs"` |
| `abrechnungslaeufe_panel.py` | 451 | `"Fehler beim Einlesen: {msg}"` |
| `abrechnungslaeufe_panel.py` | 502 | `"Fehler: {msg}"` |
| `provisionspositionen_panel.py` | 137 | `"Zugeordnet = Vertrag + Berater..."` |
| `provisionspositionen_panel.py` | 427 | `"Art"` |
| `provisionspositionen_panel.py` | 446 | `"Berateranteil"` |
| `provisionspositionen_panel.py` | 447 | `"Teamleiter"` |
| `verteilschluessel_panel.py` | 68 | `"Hinterlegtes Provisionsmodell..."` |
| `verteilschluessel_panel.py` | 71-76 | 4 Tooltip-Strings |
| `auszahlungen_panel.py` | 498 | `"CSV exportieren"` |
| `auszahlungen_panel.py` | 526 | `"openpyxl nicht installiert"` |
| `auszahlungen_panel.py` | 529 | `"Excel exportieren"` |
| `widgets.py` | 532 | `"Zeige {start}–{end} von {total}"` |

**Fix**: Alle in `src/i18n/de.py` als Keys anlegen.

---

### U12: FilterChipBar — Stretch-Leak bei wiederholtem set_chips()

| Feld | Wert |
|------|------|
| **Kategorie** | Memory / Bug |
| **Schwere** | Mittel |
| **Ort** | `widgets.py`, Zeile 176-190 |

**Problem**: Jeder `set_chips()`-Aufruf fügt einen neuen `addStretch()` hinzu, ohne die alten QSpacerItems zu entfernen.

**Fix**: Gesamtes Layout leeren vor Neuaufbau.

---

### U13: ProvisionHub — Toast-Manager-Injection fragil

| Feld | Wert |
|------|------|
| **Kategorie** | UX / Architektur |
| **Schwere** | Mittel |
| **Ort** | `provision_hub.py`, Zeile 262-264 |

**Problem**: `_toast_manager` wird per Attribut-Zuweisung gesetzt. Panels die vor dem Setzen geladen werden erhalten `None`.

**Fix**: Toast-Manager als Konstruktor-Parameter oder setter der an geladene Panels propagiert.

---

### U14: ProvisionspositionenPanel — Kein Debounce bei Suche

| Feld | Wert |
|------|------|
| **Kategorie** | Performance |
| **Schwere** | Mittel |
| **Ort** | `provisionspositionen_panel.py`, Zeile 614-640 |

**Problem**: Suchfeld-Eingabe triggert `_apply_filter()` bei jedem Tastendruck. Bei 5000 Positionen: komplette Listen-Iteration pro Keystroke.

**Fix**: Debounce-Timer (300ms).

---

### U15: ZuordnungPanel — _mapping_worker nicht proper gemanagt

| Feld | Wert |
|------|------|
| **Kategorie** | Bug / Memory |
| **Schwere** | Mittel |
| **Ort** | `zuordnung_panel.py`, Zeile 537-542 |

**Problem**: Alter Worker-Signale werden bei neuem Mapping-Dialog nicht disconnectet.

---

## Niedrige Befunde

### U16: DashboardPanel — Kein Debounce bei Datumsfilter

| Feld | Wert |
|------|------|
| **Kategorie** | Performance |
| **Schwere** | Niedrig |
| **Ort** | `dashboard_panel.py`, Zeile 196, 210 |

**Problem**: Jede Monatsänderung triggert sofort `_load_data()`. Schnelles Durchscrollen → viele API-Calls.

---

### U17: XempusPanel — resizeColumnsToContents bei jedem Filter

| Feld | Wert |
|------|------|
| **Kategorie** | Performance |
| **Schwere** | Niedrig |
| **Ort** | `xempus_panel.py`, Zeile 365-369 |

**Problem**: Bei jedem Filter-Wechsel traversiert Qt alle Zeilen. Sollte nur beim initialen Laden aufgerufen werden.

---

### U18: AuszahlungenPanel — Pagination nicht verbunden

| Feld | Wert |
|------|------|
| **Kategorie** | Bug |
| **Schwere** | Niedrig |
| **Ort** | `auszahlungen_panel.py`, Zeile 282-284 |

**Problem**: `PaginationBar` erstellt, `set_total()` aufgerufen, aber `page_changed` Signal NICHT verbunden → Buttons tun nichts.

---

### U19: VerteilschluesselPanel — Deactivate/Activate schluckt Fehler

| Feld | Wert |
|------|------|
| **Kategorie** | Fehlerbehandlung |
| **Schwere** | Niedrig |
| **Ort** | `verteilschluessel_panel.py`, Zeile 518-534 |

**Problem**: `except APIError: pass` → kein Nutzer-Feedback bei Fehlern.

---

### U20: ProvisionHub — get_blocking_operations greift auf private Attribute zu

| Feld | Wert |
|------|------|
| **Kategorie** | Architektur |
| **Schwere** | Niedrig |
| **Ort** | `provision_hub.py`, Zeile 288-296 |

**Problem**: Direkter Zugriff auf `runs_panel._import_worker`. Besser: `get_blocking_operations()` im Panel implementieren.
