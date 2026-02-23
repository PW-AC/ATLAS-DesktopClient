# Audit: PHP Backend — provision.php

**Datei**: `BiPro-Webspace Spiegelung Live/api/provision.php` (~2038 Zeilen)  
**Datum**: 20. Februar 2026

---

## SQL-Injection: ENTWARNUNG

Alle Queries verwenden parametrisierte Statements (`?`-Platzhalter). Dynamische SQL-Konstruktion nutzt nur Spaltennamen aus hardcodierten `$fields`-Arrays. `LIMIT`/`OFFSET`-Werte werden konsequent mit `(int)` Cast und `min()`/`max()` beschränkt. **Kein SQL-Injection-Risiko identifiziert.**

---

## Kritische Befunde

### B1: SQL-Alias-Bug im Auto-Matching (Subquery-Scope)

| Feld | Wert |
|------|------|
| **Kategorie** | Bug |
| **Schwere** | Kritisch |
| **Ort** | `autoMatchCommissions()`, Zeilen 337-371 |

**Problem**: `$batchFilter` wird als `'AND c.import_batch_id = ?'` definiert (Zeile 332) und in die Subquery eingefügt. Innerhalb der Subquery ist der Alias aber `c2`, nicht `c`:

```php
UPDATE pm_commissions c
INNER JOIN (
    SELECT c2.id AS comm_id, ct.id AS contract_id, ct.berater_id, ...
    FROM pm_commissions c2
    INNER JOIN pm_contracts ct ON c2.vsnr_normalized = ct.vsnr_normalized
    WHERE c2.match_status = 'unmatched' $batchFilter   ← c.import_batch_id statt c2.import_batch_id
) best ON c.id = best.comm_id AND best.rn = 1
SET ...
WHERE c.match_status = 'unmatched' $batchFilter
```

MySQL kann den Alias `c` innerhalb einer Derived Table nicht auflösen (keine LATERAL-Unterstützung). Das erzeugt entweder:
- Einen SQL-Fehler der vom try/catch in `handleImportVuListe()` (Zeile 1057) **still verschluckt** wird
- Oder MySQL löst es als korrelierte Subquery auf (semantisch falsch)

**Auswirkung**: Auto-Matching nach VU-Import schlägt still fehl. `matched_rows` wird 0. Betrifft Step 1 UND Step 2.

**Fix**:
```php
$batchFilterC2 = $batchId ? 'AND c2.import_batch_id = ?' : '';
// $batchFilter weiterhin für die äußere WHERE-Klausel verwenden
```

---

### B2: Fehlende Transaktion bei manuellem Matching

| Feld | Wert |
|------|------|
| **Kategorie** | Bug / Datenintegrität |
| **Schwere** | Kritisch |
| **Ort** | `handleCommissionsRoute()`, Zeile 847-863 |

**Problem**: `/pm/commissions/{id}/match` ruft `assignContractToCommission()` auf (bis zu 5 Schreiboperationen), OHNE Transaktion. Im Gegensatz dazu nutzt `/pm/assign` (Zeile 1926) korrekt `beginTransaction()/commit()/rollBack()`.

**Auswirkung**: Bei Fehler mitten in der Zuordnung: Teilweise zugeordnete Commission (z.B. `contract_id` gesetzt, Splits nicht berechnet).

**Fix**: Transaktion um den Aufruf wickeln, analog zu `handleAssignRoute()`.

---

## Hohe Befunde

### B3: syncBeraterToCommissions() — N+1 Pattern ohne Transaktion

| Feld | Wert |
|------|------|
| **Kategorie** | Bug / Performance |
| **Schwere** | Hoch |
| **Ort** | `syncBeraterToCommissions()`, Zeilen 100-117 |

**Problem**: Erst Bulk-UPDATE auf alle Commissions, dann per-Row `recalculateCommissionSplit()` Loop. Kein Transaktions-Wrapping. Bei 200 Commissions pro Vertrag: 200 SELECTs + 200 UPDATEs.

**Fix**: `batchRecalculateSplits()` mit Contract-Filter nutzen statt Loop.

---

### B4: recalculateCommissionSplit() schluckt Fehler still

| Feld | Wert |
|------|------|
| **Kategorie** | Fehlerbehandlung |
| **Schwere** | Hoch |
| **Ort** | `recalculateCommissionSplit()`, Zeilen 195-253 |

**Problem**: Bei nicht gefundenem Berater oder Commission kehrt die Funktion ohne Logging zurück. Gelöschte Berater mit bestehenden Commissions = stille Fehler.

**Fix**: `error_log()` mit Details, oder Exception zurückgeben.

---

### B5: Fehlende return nach json_error()

| Feld | Wert |
|------|------|
| **Kategorie** | Bug (potentiell) |
| **Schwere** | Hoch |
| **Ort** | Zeilen 529, 546, 574, 589, 602, 728, 741 (und weitere) |

**Problem**: `json_error()` wird ohne nachfolgendes `return` aufgerufen. Wenn `json_error()` nicht intern `exit()` aufruft, läuft der Code weiter → doppelte HTTP-Responses.

**Fix**: Überall `return json_error(...)` oder separates `return`.

---

### B6: Xempus-Import erstellt immer neue Batch-Einträge

| Feld | Wert |
|------|------|
| **Kategorie** | Logik-Fehler |
| **Schwere** | Hoch |
| **Ort** | `handleImportXempus()`, Zeile 1083-1087 |

**Problem**: Im Gegensatz zum VU-Import (der per `file_hash` prüft ob der Batch existiert) erstellt Xempus IMMER einen neuen Batch.

**Fix**: Gleiche `file_hash`-Prüfung wie bei VU-Import.

---

### B7: Intra-Batch Duplikate nicht erkannt (VU-Import)

| Feld | Wert |
|------|------|
| **Kategorie** | Logik-Fehler |
| **Schwere** | Hoch |
| **Ort** | `handleImportVuListe()`, Zeilen 955-989 |

**Problem**: `$existingHashes` wird nur mit DB-Werten befüllt. Doppelte Zeilen im selben Import werden beide eingefügt.

**Fix**: Nach Skip-Check: `$existingHashes[$rowHash] = true;` hinzufügen.

---

### B8: Contracts GET — korrelierte Subqueries (Performance)

| Feld | Wert |
|------|------|
| **Kategorie** | Performance |
| **Schwere** | Hoch |
| **Ort** | `handleContractsRoute()`, Zeilen 716-725 |

**Problem**: Zwei korrelierte Subqueries (`COUNT(*)`, `SUM(betrag)`) pro Vertrag. Bei LIMIT 2000: 4000+ zusätzliche Queries.

**Fix**: LEFT JOIN mit GROUP BY:
```sql
LEFT JOIN (
    SELECT contract_id, COUNT(*) AS provision_count, COALESCE(SUM(betrag),0) AS provision_summe
    FROM pm_commissions GROUP BY contract_id
) cs ON cs.contract_id = c.id
```

---

## Mittlere Befunde

### B9: Keine Validierung von Provisionssätzen/Raten

| Feld | Wert |
|------|------|
| **Kategorie** | Fehlende Validierung |
| **Schwere** | Mittel |
| **Ort** | `handleEmployeesRoute()` POST/PUT, `handleModelsRoute()` POST/PUT |

**Problem**: `commission_rate_override`, `tl_override_rate`, `commission_rate` ohne Bereichsprüfung. Werte wie -50 oder 300 möglich.

**Fix**: `0 <= rate <= 100` bei POST und PUT.

---

### B10: Status-Übergänge bei Abrechnungen nicht erzwungen

| Feld | Wert |
|------|------|
| **Kategorie** | Fehlende Geschäftslogik |
| **Schwere** | Mittel |
| **Ort** | `handleAbrechnungenRoute()` PUT, Zeilen 1635-1669 |

**Problem**: Jeder Status kann direkt in jeden anderen übergehen. Kein State-Machine.

**Fix**: Erlaubte Übergänge definieren (`berechnet→geprueft`, `geprueft→freigegeben/berechnet`, `freigegeben→ausgezahlt`).

---

### B11: Auto-Matching Steps 3+5 ohne batchFilter

| Feld | Wert |
|------|------|
| **Kategorie** | Logik-Fehler |
| **Schwere** | Mittel |
| **Ort** | `autoMatchCommissions()`, Zeilen 407-437 |

**Problem**: Step 3 (Berater-Propagierung zum Vertrag) und Step 5 (Vertragsstatus-Update) haben keinen `$batchFilter` → modifizieren ALLE Daten im System, nicht nur den aktuellen Batch.

**Fix**: WHERE-Klausel auf `c.import_batch_id` einschränken.

---

### B12: Zirkuläre Teamleiter-Referenz möglich

| Feld | Wert |
|------|------|
| **Kategorie** | Fehlende Validierung |
| **Schwere** | Mittel |
| **Ort** | `handleEmployeesRoute()` POST/PUT |

**Problem**: Mitarbeiter kann sich selbst als Teamleiter zuweisen.

**Fix**: `if ($data['teamleiter_id'] == $id) json_error(...)`.

---

### B13: Contract PUT — berater_id ohne Existenzprüfung

| Feld | Wert |
|------|------|
| **Kategorie** | Fehlende Validierung |
| **Schwere** | Mittel |
| **Ort** | `handleContractsRoute()` PUT, Zeilen 731-748 |

**Problem**: `berater_id` wird direkt in DB geschrieben. Nicht-existenter Berater → stille Split-Fehler.

**Fix**: Existenzprüfung vor UPDATE.

---

### B14: Abrechnungen: Null-Abrechnungen für Berater ohne Provisionen

| Feld | Wert |
|------|------|
| **Kategorie** | Geschäftslogik |
| **Schwere** | Mittel |
| **Ort** | `handleAbrechnungenRoute()` POST, Zeilen 1590-1626 |

**Problem**: Für JEDEN aktiven Berater wird eine Abrechnung erstellt, auch ohne Provisionen im Monat.

**Fix**: `if ($brutto == 0 && $rueckbelastungen == 0) continue;`

---

### B15: Keine Datumsformat-Validierung

| Feld | Wert |
|------|------|
| **Kategorie** | Fehlende Validierung |
| **Schwere** | Mittel |
| **Ort** | Dashboard, Contracts, Commissions GET-Filter |

**Problem**: `$_GET['von']`, `$_GET['bis']`, `$_GET['monat']` ohne Formatprüfung. Wert "abc" → `date('Y-m-t', strtotime('abc-01'))` = `1970-01-31`.

**Fix**: Regex `'/^\d{4}-\d{2}(-\d{2})?$/'` validieren.

---

### B16: Clearance-Total mischt unterschiedliche Einheiten

| Feld | Wert |
|------|------|
| **Kategorie** | Logik-Fehler |
| **Schwere** | Mittel |
| **Ort** | `handleClearanceRoute()`, Zeile 1983 |

**Problem**: `total` addiert Commissions-Zeilen + DISTINCT Vermittler + Mitarbeiter = semantisch wertlos.

**Fix**: `total` entfernen oder nur gleichartige Counts addieren.

---

## Niedrige Befunde

### B17: Race Condition bei parallelem Auto-Matching

| Feld | Wert |
|------|------|
| **Kategorie** | Concurrency |
| **Schwere** | Niedrig |
| **Ort** | `autoMatchCommissions()` |

**Problem**: Kein Locking. Paralleles Auto-Matching → doppeltes Matching möglich. Unwahrscheinlich bei 2-5 Nutzern.

---

### B18: Mapping-Löschung ohne Kaskade

| Feld | Wert |
|------|------|
| **Kategorie** | Fehlende Geschäftslogik |
| **Schwere** | Niedrig |
| **Ort** | `handleMappingsRoute()` DELETE |

**Problem**: Bestehende Commissions behalten berater_id nach Mapping-Löschung.

---

### B19: Clearance-Route — 4 separate COUNT-Queries

| Feld | Wert |
|------|------|
| **Kategorie** | Performance |
| **Schwere** | Niedrig |
| **Ort** | `handleClearanceRoute()` |

**Problem**: 4 Queries statt 1 kombinierter Query mit CASE WHEN.

---

### B20: Employee PUT — keine Rollen-Validierung

| Feld | Wert |
|------|------|
| **Kategorie** | Fehlende Validierung |
| **Schwere** | Niedrig |
| **Ort** | `handleEmployeesRoute()` PUT |

**Problem**: POST validiert Rolle, PUT nicht → ungültige Rollen möglich.

---

### B21: Kein "Un-Match" möglich

| Feld | Wert |
|------|------|
| **Kategorie** | Fehlende Funktion |
| **Schwere** | Niedrig |
| **Ort** | `handleCommissionsRoute()` |

**Problem**: Keine Route zum Zurücksetzen einer Zuordnung (Status zurück auf `unmatched`).
