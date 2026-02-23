# Audit: End-to-End Datenfluss

**Datum**: 20. Februar 2026

---

## Flow 1: VU-Import → Auto-Matching → Split-Calculation → Dashboard

### Datenfluss

```
Excel-Datei (Allianz/SwissLife/VB)
  ↓  Python parse_vu_sheet(): Zeile → Dict (vsnr, betrag, art, vermittler_name, ...)
  ↓  Python import_vu_liste(): Sendet rows[] + filename + sheet_name + vu_name + file_hash
  ↓  PHP handleImportVuListe(): Batch erstellen, Duplikat-Check, Multi-Row INSERT
  ↓  PHP autoMatchCommissions(batchId):
  ↓    Step 1: VSNR-Match (pm_commissions.vsnr_normalized JOIN pm_contracts.vsnr_normalized)
  ↓    Step 2: Alt-VSNR-Match (Fallback auf vsnr_alt_normalized)
  ↓    Step 3: Berater-Propagierung (Commission→Contract, GLOBAL — kein batchFilter!)
  ↓    Step 4: Vermittler-Mapping (pm_vermittler_mapping → berater_id)
  ↓    Step 5: Vertragsstatus-Update (GLOBAL — kein batchFilter!)
  ↓  PHP batchRecalculateSplits(): 3 Batch-UPDATEs
  ↓  Dashboard: Aggregation über matched Commissions mit Datumsfilter
```

### Identifizierte Probleme

#### E-F1-1: Batch-Statistiken werden bei Re-Import überschrieben (Mittel)

Wenn die gleiche Datei erneut importiert wird, findet PHP den bestehenden Batch über `file_hash` und überschreibt `imported_rows/skipped_rows/error_rows`. Die historische Information geht verloren.

#### E-F1-2: Python-seitige Skips sind für PHP unsichtbar (Niedrig)

Python filtert Zeilen vorab (keine VSNR, Betrag=0). PHP's `total_rows` zählt nur die gefilterten. Admin sieht nicht, wie viele Zeilen vorab gefiltert wurden.

#### E-F1-3: Commissions ohne Auszahlungsdatum im Dashboard unsichtbar (Mittel)

`NULL BETWEEN x AND y` ist falsy. Gematchte Commissions ohne Datum sind "Geister" im Dashboard.

#### E-F1-4: Normalisierungs-Konsistenz (Bestätigt: OK)

Python normalisiert NICHT vor dem Senden. Normalisierung passiert ausschließlich in PHP (Zeile 977). PHP ist die Single Source of Truth. ✅

#### E-F1-5: Feld-Match Python→PHP (Bestätigt: OK)

Alle 11 Felder korrekt transportiert. `versicherer` wird korrekt aus `vu_name` abgeleitet. ✅

---

## Flow 2: Xempus-Import → Contract Creation → Berater-Assignment

### Datenfluss

```
Excel-Datei (Xempus-Export)
  ↓  Python parse_xempus(): Zeile → Dict (vsnr, berater, status, versicherungsnehmer=ArbN, ...)
  ↓  Filter: Zeilen ohne VSNR werden übersprungen
  ↓  Python import_xempus(): Sendet rows[] + filename + file_hash
  ↓  PHP handleImportXempus():
  ↓    Pro Zeile: Lookup (xempus_id → VSNR → vsnr_normalized)
  ↓    Bestehend: UPDATE mit COALESCE (NULLs füllen)   ← PROBLEM!
  ↓    Neu: INSERT
  ↓  Berater-Auflösung via pm_vermittler_mapping
```

### Identifizierte Probleme

#### E-F2-1: KRITISCH — Xempus Re-Import überschreibt `provision_erhalten` Status

```php
status = COALESCE(?, status)
```

`COALESCE(new_value, old_value)` gibt den ERSTEN nicht-NULL Wert zurück. Da Status immer ein String ist, wird er IMMER überschrieben.

**Szenario**:
1. Xempus-Import: Status = `abgeschlossen`
2. VU-Match: Status → `provision_erhalten`
3. Erneuter Xempus-Import: `COALESCE('abgeschlossen', 'provision_erhalten')` = `'abgeschlossen'` ← Status-Regression!

**Fix**:
```php
status = CASE 
    WHEN status = 'provision_erhalten' THEN status 
    ELSE COALESCE(?, status) 
END
```

#### E-F2-2: parse_xempus vs parse_xempus_full Inkonsistenz (Mittel)

`parse_xempus_full` erlaubt Zeilen ohne VSNR wenn `xempus_id` vorhanden. PHP filtert diese trotzdem raus. Zeilen werden gesendet und still übersprungen.

#### E-F2-3: COALESCE verhindert Datenaktualisierungen (Mittel)

Einmal gesetzte Werte werden NIE durch Xempus-Updates korrigiert. Wenn ein Berater in Xempus wechselt: alte `berater_id` bleibt.

**Empfehlung**: Für `berater_id` und `status` explizites Override statt COALESCE.

#### E-F2-4: Kein Batch-Duplikat-Schutz bei Xempus (Niedrig)

Immer neuer Batch-Eintrag, auch bei identischem `file_hash`.

---

## Flow 3: Manual Matching → Split Recalculation → Payout

### Datenfluss

```
Admin: Ungematchte Commission auswählen
  ↓  PUT /pm/commissions/{id}/match   ← ODER PUT /pm/assign (transaktionssicher)
  ↓  PHP assignContractToCommission():
  ↓    1. Commission: contract_id + berater_id + match_status='manual_matched'
  ↓    2. recalculateCommissionSplit()
  ↓    3. Siblings: VSNR-Match → gleiche Zuordnung
  ↓    4. Vertrag: status → 'provision_erhalten'
  ↓
  ↓  Abrechnung generieren: POST /pm/abrechnungen {monat}
  ↓    Pro Berater: brutto - tl_abzug = netto, netto + rueck = auszahlung
  ↓
  ↓  Status-Workflow: berechnet → geprueft → freigegeben → ausgezahlt
```

### Identifizierte Probleme

#### E-F3-1: KRITISCH — Abrechnungs-Deadlock: freigegeben → ausgezahlt blockiert

```php
if ((int)$existing['is_locked']) json_error('Abrechnung ist gesperrt', 403);
// ...
if ($newStatus === 'freigegeben') {
    $sets[] = 'is_locked = 1';
}
```

Bei `freigegeben` wird `is_locked = 1` gesetzt. Danach blockiert die Lock-Prüfung JEDE Statusänderung — auch den Übergang zu `ausgezahlt`!

**Ergebnis**: Freigegebene Abrechnungen können NIEMALS den Status `ausgezahlt` erreichen.

**Fix**:
```php
if ((int)$existing['is_locked'] && $newStatus !== 'ausgezahlt') {
    json_error('Abrechnung ist gesperrt', 403);
}
```

#### E-F3-2: Keine Doppel-Abrechnungs-Sperre (Mittel)

Kein `is_billed`-Feld auf `pm_commissions`. Eine Commission kann in mehreren Monatsabrechnungen auftauchen wenn das `auszahlungsdatum` nachträglich korrigiert wird.

#### E-F3-3: Single-Row Split statt Batch in syncBeraterToCommissions (Niedrig)

Per-Row Loop statt `batchRecalculateSplits()`. Bei 100+ Provisionen pro Vertrag: 200+ Queries statt 3.

---

## Flow 4: Vermittler-Mapping → Re-Matching

### Datenfluss

```
Admin: Mapping erstellen (VU-Vermittlername → interner Berater)
  ↓  POST /pm/mappings {vermittler_name, berater_id}
  ↓  PHP: normalizeVermittlerName() → INSERT/UPDATE pm_vermittler_mapping
  ↓
  ↓  Client: POST /pm/import/match (Auto-Match triggern)
  ↓  PHP autoMatchCommissions():
  ↓    Step 4: vermittler_name_normalized JOIN pm_vermittler_mapping
  ↓    ABER: Nur WHERE berater_id IS NULL  ← PROBLEM!
```

### Identifizierte Probleme

#### E-F4-1: HOCH — Mapping-Änderung kaskadiert nicht

Wenn ein Mapping von Berater 5 auf Berater 8 geändert wird, werden bestehende Commissions mit Berater 5 NICHT aktualisiert (weil `berater_id IS NULL`-Filter).

**Fix**: Nach Mapping-Update gezieltes Re-Sync:
```sql
UPDATE pm_commissions c
INNER JOIN pm_vermittler_mapping m ON c.vermittler_name_normalized = m.vermittler_name_normalized
SET c.berater_id = m.berater_id
WHERE c.berater_id != m.berater_id
  AND c.match_status IN ('auto_matched')
```

#### E-F4-2: Mapping-Löschung ohne Rückwirkung (Niedrig)

DELETE entfernt nur den Mapping-Eintrag. Bereits zugeordnete Commissions behalten berater_id. Wahrscheinlich beabsichtigt, sollte aber kommuniziert werden.

---

## Zusammenfassung: Kritische Pfad-Unterbrechungen

| Problem | Auswirkung | Workaround vorhanden? |
|---------|------------|----------------------|
| Auto-Matching Alias-Bug (B1) | Matching nach Import schlägt still fehl | Manuelles `POST /pm/import/match` ohne batchId |
| Status-Regression (E-F2-1) | `provision_erhalten` geht bei Re-Import verloren | Xempus nicht erneut importieren |
| Abrechnungs-Deadlock (E-F3-1) | Freigegebene Abrechnungen bleiben gesperrt | Direktes SQL-UPDATE auf DB |
| Mapping kaskadiert nicht (E-F4-1) | Berater-Änderung wirkt nicht retroaktiv | Manuelles Re-Match jeder Commission |
