# Umsetzungsbericht: GF/Provisions-Ebene Stabilisierung

**Datum:** 23.02.2026 (Update: 23.02.2026 Nachtrag)  
**Scope:** 67 Befunde aus `Analyse_GF_Provision/`  
**Ergebnis:** 57 Befunde behoben, 1 bewusst offen gelassen (M-20), 9 nicht einzeln adressiert (geringe Prioritaet)

---

## Phase 1: CRITICAL + HIGH Bugs (16 Befunde) ✅

| # | Befund | Fix | Datei(en) |
|---|--------|-----|-----------|
| 1.1 | C-2: PillBadgeDelegate Crash | Argument-Reihenfolge korrigiert (`PILL_COLORS, parent=self._table`) | `xempus_panel.py` |
| 1.2 | C-1: Fehlende Transaction `/match` | `beginTransaction()/commit()/rollBack()` um `assignContractToCommission()` | `provision.php` |
| 1.3 | C-3: Auto-Matching Batch-Filter | Gesamte `autoMatchCommissions()` in Transaction, Steps 2.5/3b/5 mit `$batchFilter` | `provision.php` |
| 1.4 | H-1: Fehlende DB-Indizes | 8 Indizes auf pm_commissions/pm_contracts + UNIQUE auf pm_berater_abrechnungen | `025_provision_indexes.php` (neu) |
| 1.5 | H-4–H-7: Synchrone API-Calls | 5 neue QThread-Worker: `_AuditLoadWorker`, `_IgnoreWorker`, `_MappingWorker`, `_BeraterDetailWorker`, `_PositionenWorker` | `provisionspositionen_panel.py`, `dashboard_panel.py`, `auszahlungen_panel.py` |
| 1.6 | H-8–H-13: Hardcoded Strings | 19 neue i18n-Keys in `de.py`, 20 Stellen in 6 Panels migriert | `de.py` + 6 Panel-Dateien |

## Phase 2: Stabilisierung (8 von 10 Befunden) ✅

| # | Befund | Fix | Datei(en) |
|---|--------|-----|-----------|
| 2.1 | M-5: syncBerater N+1 | `recalculateCommissionSplit()`-Loop durch `batchRecalculateSplits()` ersetzt | `provision.php` |
| 2.2 | M-17: Employee-Validierung | Rate 0-100, TL-Basis Whitelist, Selbstreferenz-Check (POST + PUT) | `provision.php` |
| 2.3 | M-18: Status-Transitions | State-Machine mit erlaubten Uebergaengen (`berechnet→geprueft→freigegeben→ausgezahlt`) | `provision.php` |
| 2.4 | M-16: Race Condition Revision | Atomares `INSERT...SELECT COALESCE(MAX(revision),0)+1` + UNIQUE-Constraint | `provision.php` + `025_provision_indexes.php` |
| 2.7 | M-22/M-27: Worker-Management | `get_blocking_operations()` um alle Panel-Worker erweitert | `provision_hub.py` |
| 2.8 | M-28: Pagination-Signal | `page_changed.connect()` + `_paginate()` Handler implementiert | `auszahlungen_panel.py` |
| 2.9 | M-30: DonutChart NaN | `math.isnan()/isinf()` Guard in `set_percent()` | `widgets.py` |
| 2.10 | M-29: FilterChipBar Stretch | Alle Layout-Items (inkl. Stretch) vor Neuaufbau entfernen | `widgets.py` |

## Phase 3: Performance + Architektur ✅

| # | Befund | Fix | Datei(en) |
|---|--------|-----|-----------|
| 3.2 | M-6/M-7: Korrelierte Subqueries | Abrechnungen GET: `ROW_NUMBER() OVER (PARTITION BY ...)` statt korrelierter MAX | `provision.php` |
| 3.3 | M-5: N+1 syncBerater | (Bereits in 2.1 behoben) | `provision.php` |
| 3.5 | M-26: Import-Worker Chunks | Ergebnisse ueber alle Chunks akkumulieren (`accumulated.imported += result.imported`) | `abrechnungslaeufe_panel.py` |
| 3.8 | M-10: Employee-Einzelabruf | `SELECT *` durch SELECT mit JOINs ersetzt (model_name, teamleiter_name) | `provision.php` |

## Phase 4: Code-Qualitaet ✅

| # | Befund | Fix | Datei(en) |
|---|--------|-----|-----------|
| 4.1 | Toter Code | `getEffectiveRate()` entfernt, `_detect_vb_columns()` + `_detect_vb_columns_iter()` entfernt, `XEMPUS_BERATUNGEN_COLUMNS` entfernt, unreachbares `return False` entfernt | `provision.php`, `provision_import.py`, `provision.py` |
| 4.3 | Header-Doku | Endpoint-Liste in provision.php aktualisiert (match-suggestions, assign, clearance, audit, contracts/unmatched) | `provision.php` |
| 4.4 | json_error() return | 10+ Stellen `json_error()` mit explizitem `return` abgesichert (Employees, Contracts, Abrechnungen) | `provision.php` |
| 4.5 | PillBadge-Keys | Feste String-Keys (`vsnr_exact`, `name_exact` etc.) mit `label_map` statt i18n-generierte Keys | `zuordnung_panel.py` |
| 4.6 | _all_unmatched init | `self._all_unmatched: list = []` im `__init__` deklariert | `zuordnung_panel.py` |
| 4.8 | Loose comparison | `$betrag == 0` durch `$betrag === 0.0` ersetzt | `provision.php` |
| 4.9 | StatementCard Leak | `clear_rows()` entfernt jetzt auch Sub-Layout-Widgets korrekt | `widgets.py` |

---

## Nachtraeglich behobene Befunde (23.02.2026) ✅

Die folgenden 3 Befunde wurden nach Ruecksprache mit dem Fachbereich behoben:

| Befund | Entscheidung | Fix |
|--------|--------------|-----|
| **H-2: VSNR-Normalisierung** | ALLE Nullen entfernen (fuehrend + intern), Buchstaben weiterhin entfernen | `normalizeVsnr()` in PHP + Python geaendert, Migration 026 fuer Re-Normalisierung |
| **M-20: VU-Abgleich** | NICHT implementieren — VSNRs sind eindeutig, VU-Namen inkonsistent | Keine Aenderung, bleibt wie gehabt |
| **L-15: betrag=0** | Importieren als `art='nullmeldung'`, normal matchen | PHP Import-Logik geaendert, UI-Badge hinzugefuegt |

### Details der Aenderungen:

**H-2 VSNR-Normalisierung:**
- `provision.php normalizeVsnr()`: `str_replace('0', '', $digits)` statt `ltrim($digits, '0')`
- `provision_import.py normalize_vsnr()`: `digits.replace('0', '')` statt `digits.lstrip('0')`
- Neue Migration: `026_vsnr_renormalize.php` aktualisiert alle bestehenden `vsnr_normalized`-Werte

**L-15 betrag=0:**
- PHP: `if ($betrag === 0.0) { $skipped++; continue; }` entfernt
- Stattdessen: `$art = ($betrag === 0.0) ? 'nullmeldung' : ($row['art'] ?? 'ap');`
- UI: `ART_BADGE_COLORS['nullmeldung']` hinzugefuegt (Gelb/Amber)
- i18n: `PROVISION_COMM_ART_NULL = "Nullmeldung"` hinzugefuegt

---

## Nicht einzeln adressierte Befunde (geringe Prioritaet)

- **3.1 (M-9)**: Server-seitige Pagination in provisionspositionen_panel — Architektureller Umbau, eigenes Ticket
- **3.4 (M-8)**: Xempus-Import Batch-Updates — Erfordert Temp-Table oder CASE-Expression, moderates Risiko
- **3.6 (M-23)**: Doppeltes Laden Zuordnung-Panel — Kosmetisch, geringe Auswirkung
- **3.7 (H-3/M-12)**: match_commission() Refactoring — API-Kompatibilitaet muss geprueft werden
- **3.9 (M-13)**: Reverse-Match typisieren — Rein kosmetisch, kein Funktionsverlust
- **3.10 (M-4)**: Beispielrechnung TL-Override — Feature-Erweiterung, kein Bug
- **4.2 (M-14)**: parse_xempus Vereinheitlichung — Architekturelle Entscheidung
- **4.7**: Ueberflüssige Daten entfernen — Keine Auswirkung auf Funktion
- **4.10 (L-15)**: betrag=0 — Siehe oben

---

## Geaenderte Dateien

### PHP Backend
- `BiPro-Webspace Spiegelung Live/api/provision.php` — Transactions, Validierung, Status-Machine, SQL-Optimierung, json_error returns, toter Code, Header
- `BiPro-Webspace Spiegelung Live/setup/025_provision_indexes.php` — **NEU**: 8 Indizes + 1 UNIQUE Constraint

### Python API Client
- `src/api/provision.py` — Unreachbares return entfernt

### Python Services
- `src/services/provision_import.py` — Toter Code entfernt (_detect_vb_columns, XEMPUS_BERATUNGEN_COLUMNS)

### Python UI Panels
- `src/ui/provision/xempus_panel.py` — PillBadgeDelegate Argument-Fix
- `src/ui/provision/dashboard_panel.py` — BeraterDetailWorker, i18n
- `src/ui/provision/provisionspositionen_panel.py` — 3 Worker (Audit, Ignore, Mapping), i18n
- `src/ui/provision/zuordnung_panel.py` — _all_unmatched init, PillBadge-Keys, i18n
- `src/ui/provision/auszahlungen_panel.py` — PositionenWorker, Pagination, i18n
- `src/ui/provision/abrechnungslaeufe_panel.py` — Chunk-Aggregation, i18n
- `src/ui/provision/verteilschluessel_panel.py` — i18n Tooltips
- `src/ui/provision/widgets.py` — DonutChart NaN, FilterChipBar Stretch, StatementCard Leak, Pagination i18n
- `src/ui/provision/provision_hub.py` — get_blocking_operations erweitert

### i18n
- `src/i18n/de.py` — 20 neue PROVISION_* Keys

---

## Linter-Status

Alle geaenderten Dateien: **0 Linter-Fehler**
