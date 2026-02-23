# PHP Backend Analyse: provision.php

---

## 1. Funktionsinventar

| # | Funktion | Zeilen | Zweck |
|---|----------|--------|-------|
| 1 | `normalizeVsnr()` | 40–54 | VSNR normalisieren (Nicht-Ziffern entfernen, führende Nullen, Scientific Notation) |
| 2 | `normalizeVermittlerName()` | 56–63 | Vermittlernamen normalisieren (lowercase, Umlaute, Sonderzeichen) |
| 3 | `normalizeForDb()` | 65–72 | VN-Namen normalisieren (wie Vermittler + Klammern auflösen) |
| 4 | `getEffectiveRate()` | 74–86 | Effektive Provisionsrate (Override > Modell > 0) — **DEAD CODE** |
| 5 | `syncBeraterToCommissions()` | 100–117 | Berater-ID von Vertrag auf verknüpfte Commissions synchronisieren |
| 6 | `assignBeraterToContract()` | 123–126 | Berater auf Vertrag setzen + Sync |
| 7 | `assignContractToCommission()` | 138–189 | Commission mit Vertrag verknüpfen, Batch-Sync, Splits, Status |
| 8 | `recalculateCommissionSplit()` | 195–253 | Einzel-Split-Berechnung |
| 9 | `batchRecalculateSplits()` | 255–325 | Batch-Split: 3 UPDATE-Queries (Neg/PosOhneTL/PosMitTL) |
| 10 | `autoMatchCommissions()` | 331–451 | 5-Schritt Auto-Matching Engine |
| 11 | `logPmAction()` | 457–469 | Activity-Logging Helper |
| 12 | `handleProvisionRequest()` | 475–518 | Haupt-Dispatcher |
| 13 | `handleEmployeesRoute()` | 524–634 | Mitarbeiter CRUD |
| 14 | `handleContractsRoute()` | 640–754 | Verträge GET + PUT + /unmatched |
| 15 | `handleCommissionsRoute()` | 760–883 | Provisionen GET + match + ignore + recalculate |
| 16 | `handleImportRoute()` | 889–920 | Import-Dispatcher |
| 17 | `handleImportVuListe()` | 922–1074 | VU-Provisionslisten Import |
| 18 | `handleImportXempus()` | 1076–1289 | Xempus-Beratungen Import |
| 19 | `handleDashboardRoute()` | 1295–1468 | Dashboard KPIs + Berater-Detail |
| 20 | `handleMappingsRoute()` | 1474–1548 | Vermittler-Mapping CRUD |
| 21 | `handleAbrechnungenRoute()` | 1554–1673 | Abrechnungen GET/POST/PUT |
| 22 | `handleModelsRoute()` | 1679–1719 | Provisionsmodelle CRUD |
| 23 | `handleMatchSuggestionsRoute()` | 1727–1772 | Match-Suggestions Dispatcher |
| 24 | `getMatchSuggestionsForward()` | 1774–1801 | Forward-Matching (Commission → Contract) |
| 25 | `getMatchSuggestionsReverse()` | 1803–1831 | Reverse-Matching (Contract → Commission) |
| 26 | `buildScoreSql()` | 1833–1854 | SQL CASE-Score Builder |
| 27 | `buildReasonSql()` | 1856–1873 | SQL CASE-Reason Builder |
| 28 | `buildWhereOr()` | 1875–1903 | SQL WHERE OR Builder |
| 29 | `handleAssignRoute()` | 1909–1957 | Transaktionale Zuordnung |
| 30 | `handleClearanceRoute()` | 1961–1992 | Klärfall-Counts |
| 31 | `handleAuditRoute()` | 1998–2037 | PM-Aktivitätshistorie |

---

## 2. Split-Engine Analyse

### 2.1 Invariante: `berater_anteil + tl_anteil + ag_anteil == betrag`

Die Invariante hält **mathematisch immer**, weil `ag_anteil` als Residuum berechnet wird:

```
beraterBrutto = round(betrag × rate / 100, 2)
agAnteil      = round(betrag - beraterBrutto, 2)
```

**Fall 1 — Rückbelastung/Negativ (Z. 219–225):**
```
berater_anteil = beraterBrutto, tl_anteil = 0, ag_anteil = agAnteil
SUM = beraterBrutto + 0 + (betrag - beraterBrutto) = betrag ✓
```

**Fall 2 — Positiv ohne TL:** Identisch. ✓

**Fall 3 — Positiv mit TL (Z. 228–252):**
```
tlAnteil = min(round(beraterBrutto × tlRate / 100, 2), beraterBrutto)
beraterNetto = round(beraterBrutto - tlAnteil, 2)
SUM = beraterNetto + tlAnteil + agAnteil
    = (beraterBrutto - tlAnteil) + tlAnteil + (betrag - beraterBrutto) = betrag ✓
```

Die `batchRecalculateSplits()` (Z. 255–325) verwendet exakt dieselben Formeln in SQL. ✓

### 2.2 Semantisches Problem: `berater_anteil` ist NETTO

Die Spalte heißt `berater_anteil`, speichert aber den **Netto**-Wert (nach TL-Abzug). Für Debugging und Auswertungen verwirrend. Der Brutto-Wert (vor TL-Abzug) ist nirgends persistent gespeichert.

### 2.3 TL-Override kann Berater auf 0 setzen

Bei `tl_override_basis = 'gesamt_courtage'` und TL-Rate > Berater-Rate:
```
Beispiel: betrag=100, berater_rate=10% → brutto=10
          tl_rate=20%, basis=gesamt_courtage → tl=20
          LEAST(20, 10) = 10 → berater_netto = 0
```
Keine Warnung oder Plausibilitätsprüfung. Geschäftlich problematisch.

---

## 3. Auto-Matching-Engine

### 3.1 Die 5 Schritte

| Schritt | Beschreibung | Batch-Filter? |
|---------|-------------|---------------|
| 1 | VSNR Match (`vsnr_normalized`) | ✓ Ja |
| 2 | Alt-VSNR Match (`vsnr_alt_normalized`) | ✓ Ja |
| 2.5 | Xempus Berater-Resolve | **✗ GLOBAL** |
| 3 | VU Vermittler-Mapping | ✓ (teilweise) |
| 3b | Propagation zu Vertrag | **✗ GLOBAL** |
| 4 | Split Recalculate | ✓ Ja |
| 5 | Contract Status Update | **✗ GLOBAL** |

### 3.2 VSNR-Kollisionsgefahr

`normalizeVsnr()` entfernt ALLE Nicht-Ziffern:
- `"ABC-12345"` → `"12345"`
- `"XYZ-12345"` → `"12345"`

Da kein VU-Abgleich stattfindet, können Commissions von VU-A dem falschen Vertrag von VU-B zugeordnet werden, wenn der Ziffernteil identisch ist.

### 3.3 Neuester-Vertrag-Heuristik

Bei mehreren Verträgen mit gleicher VSNR gewinnt der neueste (`ORDER BY ct.created_at DESC`). Bei echten Duplikaten (Altvertrag vs. Neuvertrag bei VU-Wechsel) könnte der falsche gewählt werden.

### 3.4 NULL VSNRs

NULL VSNRs matchen nicht (`NULL = NULL` ist FALSE in SQL). Commissions ohne VSNR bleiben `unmatched`. **Korrektes Verhalten.**

---

## 4. SQL-Probleme

### 4.1 Fehlende Indizes

| Spalte | Geschätzte Query-Häufigkeit |
|--------|---------------------------|
| `pm_commissions.match_status` | >20 Queries nutzen WHERE match_status |
| `pm_commissions.berater_id` | JOIN + WHERE, hoch |
| `pm_commissions.contract_id` | JOIN, hoch |
| `pm_commissions.auszahlungsdatum` | BETWEEN in Dashboard/Abrechnungen |
| `pm_contracts.berater_id` | JOIN, mittel |
| `pm_contracts.status` | WHERE-Filter, mittel |

**Empfehlung:** Composite-Index `(match_status, berater_id)` auf `pm_commissions`.

### 4.2 N+1 Query-Patterns

**`syncBeraterToCommissions` (Z. 100–117):**
Jedes `recalculateCommissionSplit` führt 2–3 SELECTs + 1 UPDATE aus. Bei N Commissions pro Vertrag: 3N+2 Queries.

**`handleImportXempus` (Z. 1234–1268):**
Einzelne UPDATEs pro existierendem Vertrag. Bei 1000 Verträgen → 1000 Queries.

### 4.3 Korrelierte Subqueries

**Contracts GET (Z. 718–719):** 2 korrelierte Subqueries pro Zeile bei LIMIT 500.
**Abrechnungen GET (Z. 1568–1572):** O(N²) für MAX(revision).

---

## 5. Transaktionssicherheit

### 5.1 CRITICAL: `/commissions/{id}/match` ohne Transaction

`handleCommissionsRoute` Zeile 847–863 ruft `assignContractToCommission()` OHNE Transaktion auf. Diese Funktion führt 6+ DB-Operationen durch:
1. Update Commission (contract_id, berater_id, match_status)
2. Batch-Sync Geschwister-Commissions
3. recalculateCommissionSplit pro Geschwister
4. Update Contract Status

Vergleich: `handleAssignRoute()` (Z. 1925) wrappt korrekt in `beginTransaction()/commit()`.

### 5.2 Weitere fehlende Transaktionen

- `batchRecalculateSplits()` — 3 UPDATEs ohne Transaction
- `autoMatchCommissions()` — 5 Schritte ohne Transaction
- `handleImportVuListe()` — Batch-Insert + autoMatch ohne umschließende Transaction

---

## 6. Validierungslücken

### 6.1 Employee-Felder (Z. 544–564)

Nicht validiert:
- `commission_rate_override` — könnte negativ oder > 100 sein
- `tl_override_rate` — könnte negativ sein
- `tl_override_basis` — nur 'berater_anteil'/'gesamt_courtage' erlaubt, nicht geprüft
- `teamleiter_id` — keine Prüfung auf Existenz oder Rolle
- Selbstreferenz: Mitarbeiter könnte sich selbst als Teamleiter setzen

### 6.2 Abrechnungs-Status-Übergänge (Z. 1641–1644)

Jeder gültige Status kann von jedem anderen gesetzt werden. Kein State-Machine-Enforcement:
- `ausgezahlt` → `berechnet` (Rücksprung!)
- `berechnet` → `ausgezahlt` (Überspringen!)

### 6.3 Race Condition bei Revision (Z. 1611–1615)

Read-Then-Write ohne Lock. Zwei gleichzeitige POST-Requests könnten dieselbe Revision erzeugen.

---

## 7. Route-Mapping

### 7.1 Vollständigkeit: Alle Routen korrekt gemappt ✓

Alle 20 Route-Handler in `provision.php` werden korrekt über `handleProvisionRequest()` dispatcht. Routing in `index.php` (Z. 116–122) funktioniert.

### 7.2 Fehlende Route: GET /pm/contracts/{id}

Ein einzelner Vertrag per ID kann nicht abgerufen werden. GET springt direkt in die gefilterte Listenansicht.

### 7.3 Veraltete Header-Dokumentation

Die Routen `match-suggestions`, `assign`, `clearance`, `audit` fehlen im Datei-Header (Z. 11–27).

---

## 8. DB-Migration (024)

### 8.1 Bedingte UNIQUE-Constraints

Wenn bei Migration Duplikate existieren, wird der UNIQUE-Constraint auf `xempus_id` NICHT gesetzt — nur eine Warnung. Keine Mechanismen zur Duplikat-Bereinigung oder nachträglichen Constraint-Erstellung.

### 8.2 Fehlende Operational-Indizes

Die Migration 024 fügt Indizes für normalisierte Spalten hinzu, aber die operationalen Indizes (match_status, berater_id, etc.) fehlen — sowohl in 024 als auch in früheren Migrationen.

### 8.3 Backfill korrekt

Die `normalizeForDbMigration()`-Funktion ist identisch mit `normalizeForDb()`. Backfill ist idempotent (`WHERE ... IS NULL`).
