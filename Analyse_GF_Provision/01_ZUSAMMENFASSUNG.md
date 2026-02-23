# Executive Summary: Alle Befunde nach Schweregrad

---

## CRITICAL (3 Befunde)

### C-1: Fehlende Transaktion bei `commissions/{id}/match`
- **Datei:** `provision.php` Zeile 847–863
- **Problem:** `assignContractToCommission()` führt 6+ DB-Operationen aus (Update Commission, Batch-Sync Siblings, recalculateSplits, Update Contract Status) — alles OHNE Transaction. Der neuere `/pm/assign`-Endpoint (Z. 1925) wrappt korrekt in `beginTransaction()/commit()/rollBack()`, aber der ältere `/match`-Endpoint nicht.
- **Auswirkung:** Bei Fehler in Schritt 2 (Geschwister-Update) oder Schritt 3 (Split) bleibt die DB in inkonsistentem Zustand. Berater-Anteil + TL-Anteil + AG-Anteil ≠ Betrag für Geschwister-Commissions.
- **Lösung:** Transaction um den gesamten `assignContractToCommission()`-Aufruf in `handleCommissionsRoute` Zeile 847 legen.

### C-2: PillBadgeDelegate mit falscher Argument-Reihenfolge (xempus_panel.py)
- **Datei:** `xempus_panel.py` Zeile 270–271
- **Problem:** `PillBadgeDelegate(self._table, PILL_COLORS)` — Die Signatur ist `(color_map, label_map=None, parent=None)`. Dadurch wird `self._table` (ein QTableView) als `color_map` interpretiert. Beim Rendern wird `self._table.get(lookup_key)` aufgerufen → `AttributeError` / Crash.
- **Auswirkung:** Status-Badges im Xempus-Panel funktionieren gar nicht / Crash zur Laufzeit.
- **Lösung:** Argumente tauschen: `PillBadgeDelegate(PILL_COLORS, parent=self._table)`.

### C-3: Auto-Matching Schritte ohne Batch-Filter (Global-Scope)
- **Datei:** `provision.php` Zeile 375–437
- **Problem:** Schritte 2.5 (Xempus Berater-Resolve), 3b (Propagation zu Vertrag) und 5 (Contract Status Update) laufen GLOBAL — ohne `$batchFilter`. Beim Import eines neuen Batches werden diese Schritte auf ALLE Daten angewendet.
- **Auswirkung:** Unerwünschte Statusänderungen bei Verträgen anderer Batches. Race Conditions bei parallelen Imports. Performance-Probleme bei großen Datenbeständen.
- **Lösung:** `$batchFilter` in allen 5 Matching-Schritten konsistent anwenden, oder die globalen Schritte als separate "Housekeeping"-Funktion auslagern.

---

## HIGH (13 Befunde)

### H-1: Fehlende Indizes auf häufig gefilterten Spalten
- **Datei:** `provision.php` / DB-Schema
- **Betroffene Spalten:** `pm_commissions.match_status`, `berater_id`, `contract_id`, `import_batch_id`, `auszahlungsdatum`; `pm_contracts.berater_id`, `status`
- **Auswirkung:** Langsame Queries bei wachsendem Datenbestand (15.000+ Zeilen bekannt).

### H-2: VSNR-Normalisierung entfernt Buchstaben → Kollisionsgefahr
- **Datei:** `provision.php` Zeile 40–54
- **Problem:** `preg_replace('/\D/', '', $s)` entfernt ALLE Nicht-Ziffern. "ABC-12345" und "XYZ-12345" werden identisch. Kein VU-Abgleich im Matching.
- **Auswirkung:** Falsches Matching bei VSNRs verschiedener VUs mit gleichem Ziffernteil.

### H-3: Duplizierte Match-Funktionalität (match vs. assign)
- **Datei:** `provision.py` Zeile 505 vs. 768
- **Problem:** Zwei Python-Methoden für dieselbe Aufgabe. `/match` ist nicht transaktional, `/assign` schon. Verwirrende API-Oberfläche.

### H-4–H-7: Synchrone API-Calls im UI-Thread (4 Stellen)
- **dashboard_panel.py:487** — Berater-Detail bei Doppelklick
- **provisionspositionen_panel.py:718** — Audit-Log bei Selektion
- **provisionspositionen_panel.py:745** — Ignore bei Rechtsklick
- **auszahlungen_panel.py:443** — Positionen bei Zeilen-Auswahl
- **Auswirkung:** UI friert bei langsamer Netzwerkverbindung ein.

### H-8–H-13: Hardcoded deutsche Strings statt i18n (~15 Stellen)
- **dashboard_panel.py:81,88** — Tooltip-Texte
- **provisionspositionen_panel.py:427,445–448** — Feld-Labels
- **zuordnung_panel.py:884** — Fehlertext
- **abrechnungslaeufe_panel.py:451,502** — Fehlertexte
- **auszahlungen_panel.py:498,527,529** — Dialog-Titel + Fehlertext
- **verteilschluessel_panel.py:67–79** — Tooltip-Texte
- **widgets.py:531** — Pagination-Text "Zeige X–Y von Z"

---

## MEDIUM (33 Befunde)

### Logik / Berechnung
- **M-1:** `berater_anteil` Spalte speichert Netto-Wert (nach TL-Abzug), Name suggeriert Brutto (provision.php:249)
- **M-2:** TL-Override mit Basis `gesamt_courtage` kann Berater auf 0 setzen, keine Warnung (provision.php:236)
- **M-3:** Vormonatswert `0.0` wird als falsy ignoriert → kein Trend angezeigt (dashboard_panel.py:411)
- **M-4:** Beispielrechnung in Verteilschlüssel ignoriert TL-Override (verteilschluessel_panel.py:304)

### SQL / Performance
- **M-5:** N+1 in `syncBeraterToCommissions` — recalculateCommissionSplit in Loop (provision.php:100–117)
- **M-6:** Korrelierte Subqueries in Contracts GET — 2 pro Zeile bei LIMIT 500 (provision.php:718–719)
- **M-7:** Korrelierte Subquery in Abrechnungen GET — O(N²) für MAX(revision) (provision.php:1568–1572)
- **M-8:** N+1 bei Xempus Updates — einzelne UPDATEs pro Vertrag (provision.php:1234–1268)
- **M-9:** 5000 Datensätze in einem Request statt Server-Pagination (provisionspositionen_panel.py:575)

### API / Datenfluss
- **M-10:** Employee-Einzelabruf fehlen JOIN-Felder (model_name, model_rate, teamleiter_name) (provision.py:393, provision.php:527)
- **M-11:** Unmatched-Contracts verliert source_type/vu_name (provision.py:802, provision.php:674)
- **M-12:** `match_commission()` hat kein `force_override` Parameter (provision.py:505)
- **M-13:** Reverse-Match-Suggestions als rohe Dicts statt typisierte Objekte (provision.py:760)
- **M-14:** `parse_xempus()` skippt Zeilen ohne VSNR, `parse_xempus_full()` akzeptiert sie (provision_import.py:595 vs. 715)
- **M-15:** VU-Import bei 15k+ Zeilen kann 120s-Timeout überschreiten (provision.py:549)

### Edge Cases / Validierung
- **M-16:** Race Condition bei Abrechnungs-Revision (Read-Then-Write ohne Lock) (provision.php:1611)
- **M-17:** Fehlende Feld-Validierung bei Employee (Rate negativ, TL-Basis ungültig, Selbstreferenz) (provision.php:544)
- **M-18:** Fehlende Status-Transition-Prüfung bei Abrechnungen (jeder Sprung erlaubt) (provision.php:1641)
- **M-19:** Neuester Vertrag gewinnt bei Multi-Match (ROW_NUMBER ORDER BY created_at DESC) (provision.php:340)
- **M-20:** Kein Versicherer-Abgleich im Auto-Matching (provision.php:337)
- **M-21:** `json_error()` ohne explizites `return` (provision.php:529, 576, 601)

### UI-spezifisch
- **M-22:** Hub prüft nur Import-Worker als Blocking-Op, nicht Mapping/Auto-Match (provision_hub.py:288)
- **M-23:** Doppeltes Laden aller Commissions im Zuordnung-Panel (zuordnung_panel.py:61)
- **M-24:** PillBadge-Keys aus i18n-Texten generiert (fragil bei Übersetzungsänderung) (zuordnung_panel.py:802)
- **M-25:** `_all_unmatched` Attribut ohne __init__-Deklaration (zuordnung_panel.py:316)
- **M-26:** Nur letzter Chunk-Result wird emittiert (Import-Worker) (abrechnungslaeufe_panel.py:159)
- **M-27:** `QThread.quit()` wirkungslos bei synchronem Worker (abrechnungslaeufe_panel.py:432)
- **M-28:** Pagination `page_changed` Signal nicht verbunden im Auszahlungen-Panel (auszahlungen_panel.py:283)
- **M-29:** FilterChipBar Stretch-Items akkumulieren bei wiederholtem `set_chips()` (widgets.py:190)
- **M-30:** DonutChartWidget NaN-Handling fehlt (widgets.py:set_percent)
- **M-31:** `_page_size` privater Zugriff statt public Property (provisionspositionen_panel.py:647)
- **M-32:** QSortFilterProxyModel nie zum Filtern genutzt (provisionspositionen_panel.py:337)
- **M-33:** Sync API-Calls bei Mapping-Erstellung (provisionspositionen_panel.py:809)

---

## LOW (18 Befunde)

| # | Beschreibung | Datei:Zeile |
|---|-------------|-------------|
| L-1 | `getEffectiveRate()` Dead Code | provision.php:74 |
| L-2 | Positive Rückbelastung nicht validiert | provision.php:219 |
| L-3 | LIMIT nicht parametrisiert (aber int-gecastet) | provision.php:683 |
| L-4 | Loose comparison `== 0` statt `=== 0` | provision.php:979 |
| L-5 | DELETE ohne Existenzprüfung | provision.php:1537 |
| L-6 | Header-Dokumentation veraltet | provision.php:11 |
| L-7 | `ContractSearchResult.contract` Default None bei Typ Contract | provision.py:127 |
| L-8 | Commission fehlt `contract_vsnr` Feld | provision.py:163 |
| L-9 | BeraterAbrechnung fehlt Audit-Felder | provision.py:317 |
| L-10 | `per_berater: List[Dict]` statt typisierter Dataclass | provision.py:240 |
| L-11 | `match_commission()` sendet berater_id, PHP ignoriert es | provision.py:510 |
| L-12 | Unreachbares `return False` nach `raise` | provision.py:433 |
| L-13 | Toter Code: `_detect_vb_columns()`, `XEMPUS_BERATUNGEN_COLUMNS` | provision_import.py:205,463 |
| L-14 | `normalize_vsnr()` schließt INF nicht aus (PHP tut es) | provision_import.py:34 |
| L-15 | VU-Zeilen mit betrag=0 werden übersprungen | provision_import.py:282 |
| L-16 | arbn_id/arbg_id gesendet, PHP ignoriert | provision_import.py:619 |
| L-17 | Toast-Manager Injection stillschweigend | provision_hub.py:263 |
| L-18 | StatementCard clear_rows() leakt Layouts | widgets.py:569 |
