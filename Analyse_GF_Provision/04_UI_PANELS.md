# UI Panels Analyse

---

## 1. ProvisionHub (provision_hub.py, ~297 Zeilen)

### 1.1 Lazy Loading — Korrekt implementiert ✓

Panels werden erst beim ersten Navigieren erstellt. `_panels_loaded` Set verhindert doppeltes Laden.

### 1.2 Befunde

| Schweregrad | Zeile | Beschreibung |
|------------|-------|--------------|
| MEDIUM | 232 | Race Condition bei fehlgeschlagenem Panel-Laden: Wenn `insertWidget` fehlschlägt, bleibt der Placeholder entfernt und der Index aus `_panels_loaded` gelöscht. Aber das Panel kann nie wieder geladen werden, weil kein neuer Placeholder existiert. |
| MEDIUM | 288–296 | `get_blocking_operations()` prüft nur `PANEL_IMPORT` Worker. Andere laufende Worker (Auto-Match in Zuordnung, Mapping-Sync) werden nicht geprüft. |
| LOW | 263 | Toast-Manager-Injection: `hasattr(panel, '_toast_manager')` prüft, ob Panel das Attribut hat. Panels ohne `_toast_manager` im `__init__` bekommen keinen Toast-Manager. |
| LOW | — | Kein Cleanup von Worker-Threads bei Panel-Wechsel oder Hub-Schließung. |

---

## 2. Dashboard Panel (dashboard_panel.py, ~548 Zeilen)

### 2.1 KPI-Berechnung

Die 4 KPI-Karten nutzen Werte aus `DashboardSummary` (Server-berechnet). Keine Client-seitige Berechnung → Richtig.

### 2.2 Befunde

| Schweregrad | Zeile | Beschreibung |
|------------|-------|--------------|
| HIGH | 81,88 | Hardcoded Tooltip-Texte: "Provision nach Abzug aller Anteile", "Summe aller negativen Korrekturbuchungen", etc. |
| HIGH | 487–488 | Synchroner API-Call `get_berater_detail()` im Main-Thread bei Doppelklick auf Berater-Ranking. UI friert bei langsamer Verbindung ein. |
| MEDIUM | 411–418 | Vormonats-Trend: `eingang_vormonat = 0.0` wird als falsy behandelt → kein Trend angezeigt. `0.0` ist aber ein gültiger Wert (z.B. erster Monat). |
| LOW | 430–436 | DonutChart bei 0 Positionen: Edge Case korrekt behandelt (0% statt Division-by-Zero). ✓ |

---

## 3. Provisionspositionen Panel (provisionspositionen_panel.py, ~814 Zeilen)

### 3.1 Architektur

Master-Detail-Layout mit FilterChips, PillBadges, ThreeDotMenu, Detail-Seitenpanel mit Originaldaten, Matching-Info, Verteilungs-Kuchendiagramm, Auditlog.

### 3.2 Befunde

| Schweregrad | Zeile | Beschreibung |
|------------|-------|--------------|
| HIGH | 718–743 | Synchroner API-Call für Audit-Log bei JEDER Selektion. Bei schnellem Durchklicken friert UI ein. |
| HIGH | 745–749 | Synchroner API-Call bei Ignore. |
| MEDIUM | 427 | Hardcoded "Art" Label. |
| MEDIUM | 445–448 | Hardcoded "Berateranteil"/"Teamleiter" + `[:20]` Tooltip-Abschneidung als Label. |
| MEDIUM | 575 | Lädt 5000 Datensätze in einem Request. Server-Pagination (`page`/`per_page`) wird nicht genutzt. Client-seitige Pagination über `PaginationBar`. |
| MEDIUM | 647 | Zugriff auf privates `_page_size` statt public Property von `PaginationBar`. |
| MEDIUM | 337–339 | `QSortFilterProxyModel` wird als Sortier-Proxy verwendet, aber `_apply_filter()` filtert manuell über Python-Listen statt den Proxy-Filter zu nutzen. Doppelte Logik. |
| MEDIUM | 809–811 | Zwei synchrone API-Calls nacheinander: `create_mapping()` + `trigger_auto_match()`. Auto-Match kann bei großen Daten Sekunden dauern. |

---

## 4. Zuordnung & Klärfälle Panel (zuordnung_panel.py, ~926 Zeilen)

### 4.1 Klärfall-Kategorien

4 Typen via Server-Endpoint (`GET /pm/clearance`):
- `no_contract` — Kein Vertrag gefunden
- `unknown_vermittler` — VU-Vermittler nicht zugeordnet
- `no_model` — Berater hat kein Provisionsmodell
- `no_split` — Split-Berechnung fehlt

### 4.2 Befunde

| Schweregrad | Zeile | Beschreibung |
|------------|-------|--------------|
| HIGH | 884 | Hardcoded Fehlertext: `f"Fehler: {msg}"` |
| MEDIUM | 61–63 | Doppeltes Laden: `get_commissions(match_status='unmatched', limit=1000)` + `get_commissions(limit=5000)`. Die unmatched-Daten sind eine Teilmenge. Ein einzelner Call + Client-Filter wäre effizienter. |
| MEDIUM | 802–812 | PillBadge-Keys werden aus i18n-Texten generiert: `texts.PROVISION_MATCH_DLG_SCORE_VSNR_EXACT.lower().replace(" ", "_")`. Wenn die Übersetzung Umlaute enthält, matcht der Lookup nie. |
| MEDIUM | 316 | `_all_unmatched` wird erst in `_on_loaded` erstellt (nicht in `__init__`). Theoretisch `AttributeError` möglich. |
| LOW | 439–440 | Mapping-Bearbeitung als Delete + Create statt Update. Nicht atomar — wenn Create fehlschlägt, ist das Mapping weg. |

---

## 5. Abrechnungsläufe Panel (abrechnungslaeufe_panel.py, ~503 Zeilen)

### 5.1 Import-Flow

VU- und Xempus-Dateien werden in Chunks (à 5000 Zeilen) an den Server gesendet. Parsing erfolgt lokal in Python, Upload via API.

### 5.2 Befunde

| Schweregrad | Zeile | Beschreibung |
|------------|-------|--------------|
| HIGH | 451,502 | Hardcoded Fehlertexte: "Fehler beim Einlesen:", "Fehler:" |
| MEDIUM | 159 | Import-Worker emittiert nur den `result` des LETZTEN Chunks. Statistiken (imported, skipped, errors) der vorherigen Chunks gehen verloren. |
| MEDIUM | 432–434 | `QThread.quit()` bei synchronem Worker (kein Event-Loop) ist wirkungslos. Worker läuft weiter und emittiert Signale an möglicherweise neuen Worker. |
| MEDIUM | 184 | Hardcoded Tooltip "Aktueller Pruefstatus des Abrechnungslaufs" |

---

## 6. Verteilschlüssel Panel (verteilschluessel_panel.py, ~608 Zeilen)

### 6.1 Aufbau

Provisionsmodelle als Karten mit Beispielrechnung + Mitarbeiter-Tabelle mit Rollen-Badges.

### 6.2 Befunde

| Schweregrad | Zeile | Beschreibung |
|------------|-------|--------------|
| MEDIUM | 67–79 | Hardcoded Tooltip-Texte (3 Stellen): "Hinterlegtes Provisionsmodell...", "Individueller Provisionssatz", "Prozentualer Anteil fuer die Teamleitung" |
| MEDIUM | 304 | Beispielrechnung ignoriert TL-Override: Zeigt immer `TL: 0,00 €`, auch wenn das Modell einen TL-Anteil hat. Irreführend. |
| LOW | 524 | Stiller Fehler: `except APIError: pass` bei Deactivate — User bekommt kein Feedback. |

---

## 7. Auszahlungen Panel (auszahlungen_panel.py, ~587 Zeilen)

### 7.1 Aufbau

StatementCards mit Monatsabrechnungen, Status-Workflow-Buttons, CSV/Excel-Export.

### 7.2 Befunde

| Schweregrad | Zeile | Beschreibung |
|------------|-------|--------------|
| HIGH | 443–445 | Synchroner API-Call `get_commissions()` im Main-Thread bei jeder Zeilen-Auswahl. UI friert ein. |
| HIGH | 526–527 | Hardcoded Error "openpyxl nicht installiert" |
| MEDIUM | 498,529 | Hardcoded Dialog-Titel "CSV exportieren" / "Excel exportieren" |
| MEDIUM | 283–284 | `PaginationBar.page_changed` Signal ist NICHT verbunden. Pagination-Buttons erscheinen, tun aber nichts — Tabelle zeigt immer alle Daten. |

---

## 8. Xempus Panel (xempus_panel.py, ~488 Zeilen)

### 8.1 Befunde

| Schweregrad | Zeile | Beschreibung |
|------------|-------|--------------|
| **CRITICAL** | 270–271 | `PillBadgeDelegate(self._table, PILL_COLORS)` — Argumente vertauscht! Signatur ist `(color_map, label_map, parent)`. `self._table` (QTableView) wird als `color_map` verwendet → `AttributeError` beim Rendern. |
| MEDIUM | 151–155 | `from datetime import datetime` innerhalb der `data()`-Methode bei jedem Zellenaufruf. Minimaler Performance-Hit. |

---

## 9. Widgets (widgets.py, ~816 Zeilen)

### 9.1 PillBadgeDelegate

| Schweregrad | Zeile | Beschreibung |
|------------|-------|--------------|
| LOW | 74 | Font "Open Sans" hardcoded statt aus Design-Tokens |
| MEDIUM | 97–98 | `sizeHint` nutzt `option.rect.width()` — kann 0 sein vor Layout-Initialisierung |

### 9.2 DonutChartWidget

| Schweregrad | Zeile | Beschreibung |
|------------|-------|--------------|
| MEDIUM | set_percent | NaN-Handling fehlt. `max(0.0, float('nan'))` = `nan` in Python → `span = int(nan / 100 * 360 * 16)` → ValueError |

### 9.3 FilterChipBar

| Schweregrad | Zeile | Beschreibung |
|------------|-------|--------------|
| MEDIUM | 190 | Stretch-Item akkumuliert bei jedem `set_chips()`. Buttons werden gelöscht, aber Stretch bleibt. Bei wiederholten Aufrufen sammeln sich leere Stretch-Items. |

### 9.4 PaginationBar

| Schweregrad | Zeile | Beschreibung |
|------------|-------|--------------|
| LOW | 531 | Hardcoded "Zeige X–Y von Z" Text |

### 9.5 StatementCard

| Schweregrad | Zeile | Beschreibung |
|------------|-------|--------------|
| LOW | 569–581 | `clear_rows()` erkennt Sub-Layouts (`item.layout()`) aber löscht sie nicht → Memory-Leak bei wiederholtem clear+add |

---

## 10. Querschnitts-Befunde

### 10.1 Synchrone API-Calls im UI-Thread

**5 Stellen** mit synchronen API-Calls im Main-Thread, die die UI blockieren:

1. `dashboard_panel.py:487` — Berater-Detail
2. `provisionspositionen_panel.py:718` — Audit-Log
3. `provisionspositionen_panel.py:745` — Ignore
4. `provisionspositionen_panel.py:809` — Mapping-Erstellung + Auto-Match
5. `auszahlungen_panel.py:443` — Positionen laden

**Pattern-Lösung:** QThread-Worker mit Signal/Slot wie bei `_LoadWorker` im Dashboard.

### 10.2 Hardcoded Strings

**~15 Stellen** mit hardcoded deutschen Texten statt i18n-Keys. Verstößt gegen die User-Regel "Alle Texte aus zentraler Textdatei".

### 10.3 Worker-Thread-Management

- Kein zentrales Worker-Cleanup bei Hub-Schließung
- `QThread.quit()` wird bei synchronen Workern verwendet (wirkungslos)
- Potenzielle Signal-Emissionen an bereits gelöschte Widgets
