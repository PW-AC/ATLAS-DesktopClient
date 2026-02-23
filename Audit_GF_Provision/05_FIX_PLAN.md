# Fix-Plan: GF / Provisionsmanagement

**Datum**: 20. Februar 2026  
**Priorität**: Kritisch → Hoch → Mittel → Niedrig

---

## Phase 1: Kritische Bugs (Geschätzter Aufwand: 1-2 Tage)

Diese Bugs blockieren Kernfunktionalität oder verursachen Datenverlust.

### 1.1 Auto-Matching Alias-Fix (B1)
**Datei**: `provision.php` → `autoMatchCommissions()`  
**Aufwand**: ~30 Minuten  
**Änderung**: Neuen Alias-Variablen `$batchFilterC2` erzeugen und in Subqueries von Step 1 und Step 2 verwenden. `$batchFilter` weiterhin in äußerer WHERE-Klausel.

```php
// Vorher:
$batchFilter = $batchId ? 'AND c.import_batch_id = ?' : '';

// Nachher:
$batchFilter = $batchId ? 'AND c.import_batch_id = ?' : '';
$batchFilterC2 = $batchId ? 'AND c2.import_batch_id = ?' : '';
// In Subquery: $batchFilterC2 statt $batchFilter verwenden
```

---

### 1.2 Abrechnungs-Deadlock lösen (E-F3-1)
**Datei**: `provision.php` → `handleAbrechnungenRoute()` PUT  
**Aufwand**: ~15 Minuten  
**Änderung**: Lock-Check anpassen, damit `→ ausgezahlt` trotz `is_locked` möglich ist.

```php
// Vorher:
if ((int)$existing['is_locked']) json_error('Abrechnung ist gesperrt', 403);

// Nachher:
if ((int)$existing['is_locked'] && $newStatus !== 'ausgezahlt') {
    json_error('Abrechnung ist gesperrt', 403);
}
```

---

### 1.3 Xempus Status-Schutz (E-F2-1)
**Datei**: `provision.php` → `handleImportXempus()` UPDATE  
**Aufwand**: ~15 Minuten  
**Änderung**: Status nicht überschreiben wenn bereits `provision_erhalten`.

```php
// Vorher:
status = COALESCE(?, status)

// Nachher:
status = CASE 
    WHEN status = 'provision_erhalten' THEN status 
    ELSE COALESCE(?, status) 
END
```

---

### 1.4 XempusPanel PillBadgeDelegate-Fix (U1)
**Datei**: `xempus_panel.py`  
**Aufwand**: ~5 Minuten  
**Änderung**: Einzeiler-Fix.

```python
# Vorher:
PillBadgeDelegate(self._table, PILL_COLORS)

# Nachher:
PillBadgeDelegate(PILL_COLORS, parent=self._table)
```

---

### 1.5 XempusPanel Loading-Overlay-Fix (U2)
**Datei**: `xempus_panel.py`  
**Aufwand**: ~10 Minuten  
**Änderung**: `setGeometry(self.rect())` vor `show()` und in `resizeEvent`.

---

### 1.6 Transaktion um manuelles Matching (B2)
**Datei**: `provision.php` → `handleCommissionsRoute()` PUT match  
**Aufwand**: ~20 Minuten  
**Änderung**: `Database::beginTransaction()` / `commit()` / `rollBack()` um `assignContractToCommission()`.

---

## Phase 2: Hohe Priorität (Geschätzter Aufwand: 3-5 Tage)

### 2.1 Synchrone API-Calls in Worker auslagern (U3-U7)
**Betroffene Dateien**: 5 Panels  
**Aufwand**: ~1 Tag  
**Stellen**:
- `dashboard_panel.py`: `get_berater_detail()` → `_BeraterDetailWorker`
- `provisionspositionen_panel.py`: `get_audit_log()` → `_AuditLoadWorker`
- `zuordnung_panel.py`: `trigger_auto_match()` → `_AutoMatchWorker`
- `auszahlungen_panel.py`: `get_commissions()` → `_PositionsLoadWorker`
- `zuordnung_panel.py`: `create_mapping()` → bereits existierender `_MappingSyncWorker` nutzen

**Pattern**: Standard QThread-Worker mit `finished(object)` Signal + Loading-Overlay.

---

### 2.2 syncBeraterToCommissions Batch-Optimierung (B3)
**Datei**: `provision.php`  
**Aufwand**: ~2 Stunden  
**Änderung**: Per-Row-Loop durch `batchRecalculateSplits()` mit Contract-Filter ersetzen. Dazu `batchRecalculateSplits()` um optionalen `$contractId` Parameter erweitern.

---

### 2.3 Intra-Batch Duplikat-Erkennung (B7)
**Datei**: `provision.php` → `handleImportVuListe()`  
**Aufwand**: ~10 Minuten  
**Änderung**: Eine Zeile nach dem Skip-Check: `$existingHashes[$rowHash] = true;`

---

### 2.4 Contracts GET Performance (B8)
**Datei**: `provision.php` → `handleContractsRoute()` GET  
**Aufwand**: ~1 Stunde  
**Änderung**: Korrelierte Subqueries durch LEFT JOIN mit aggregierter Subquery ersetzen.

---

### 2.5 Code-Duplikation parse_xempus auflösen (P9)
**Datei**: `provision_import.py`  
**Aufwand**: ~2 Stunden  
**Änderung**: Gemeinsame `_parse_xempus_rows(ws, columns, require_vsnr=True)` Funktion. Beide Varianten rufen diese auf.

---

### 2.6 Hardcodierte Xempus-Spalten → Header-Detection (P10)
**Datei**: `provision_import.py`  
**Aufwand**: ~1 Stunde  
**Änderung**: `_detect_xempus_columns` um Keywords für `xempus_id`, `arbn_id`, `arbg_id` erweitern. Feste Buchstaben-Konstanten als Fallback beibehalten.

---

### 2.7 Worker Signal-Leaks fixen (U8, U15)
**Dateien**: `xempus_panel.py`, `zuordnung_panel.py`  
**Aufwand**: ~30 Minuten  
**Änderung**: Vor neuem Worker: `try: old_worker.finished.disconnect() / except RuntimeError: pass`

---

## Phase 3: Mittlere Priorität (Geschätzter Aufwand: 1-2 Wochen)

### 3.1 Fehlende Validierungen (B9, B12, B13, B15, B20)
- Raten: `0 <= rate <= 100` bei POST/PUT
- Zirkuläre TL-Referenz: `teamleiter_id != eigene_id`
- Berater-Existenz bei Contract PUT
- Datumsformat: Regex-Validierung
- Rollen bei PUT validieren

### 3.2 Status-Machine für Abrechnungen (B10)
Erlaubte Übergänge definieren:
```php
$transitions = [
    'berechnet' => ['geprueft'],
    'geprueft' => ['freigegeben', 'berechnet'],
    'freigegeben' => ['ausgezahlt'],
    'ausgezahlt' => [],
];
```

### 3.3 i18n-Strings migrieren (U11)
15+ hardcodierte Strings in `de.py` überführen. Neue Keys nach bestehendem Pattern (`PROVISION_*`).

### 3.4 Mapping-Kaskadierung (E-F4-1)
Nach Mapping-Update: Retroaktives Update aller betroffenen Commissions (mit `match_status = 'auto_matched'` Filter).

### 3.5 Dashboard: Commissions ohne Datum (E-F1-3)
Option A: Pflichtfeld-Validierung für `auszahlungsdatum`  
Option B: Separate "Ohne Datum" Zeile im Dashboard

### 3.6 FilterChipBar Stretch-Leak (U12)
Layout komplett leeren vor Neuaufbau in `set_chips()`.

### 3.7 Debounce für Suche/Filter (U14, U16)
300ms Debounce-Timer in ProvisionspositionenPanel und DashboardPanel.

### 3.8 json_error() return-Statements (B5)
Alle Stellen prüfen und `return` hinzufügen.

### 3.9 COALESCE-Problem bei Xempus-Updates (E-F2-3)
Für `berater_id` und `status`: Explizites Override statt COALESCE.

### 3.10 recalculateCommissionSplit Fehlerlogging (B4)
`error_log()` bei nicht gefundenem Berater/Commission.

---

## Phase 4: Verbesserungen (Fortlaufend)

### 4.1 Dead Code entfernen (P14)
5+ nie aufgerufene Funktionen/Konstanten in `provision_import.py`.

### 4.2 Un-Match Funktion (B21)
Neue Route `PUT /pm/commissions/{id}/unmatch` zum Zurücksetzen auf `unmatched`.

### 4.3 Doppel-Abrechnungs-Sperre (E-F3-2)
`last_billed_monat` Feld auf `pm_commissions`.

### 4.4 Python-Skips melden (E-F1-2)
`python_skipped` Count im Import-Request mitsenden.

### 4.5 AuszahlungenPanel Pagination verbinden (U18)
`page_changed` Signal verbinden + `_paginate()` implementieren.

### 4.6 Xempus Batch-Duplikat-Schutz (B6)
`file_hash`-Prüfung wie bei VU-Import.

### 4.7 ProvisionHub Blocking-Operations sauberer (U20)
`get_blocking_operations()` im AbrechnungslaeufPanel implementieren.

### 4.8 Sheet-Name Case-Sensitivity (P11)
Case-insensitives Matching in `parse_vu_liste()`.

### 4.9 Klammer-Negative Beträge (P12)
`(123,45)` als `-123.45` erkennen in `_parse_amount()`.

### 4.10 Art-Überschreibung entfernen (P13)
Python soll `art` nicht bei negativen Beträgen überschreiben — PHP entscheidet.

### 4.11 Doppelte Endpoints konsolidieren (P1)
`match_commission()` deprecated, alle zu `assign_contract()` migrieren.

### 4.12 VerteilschluesselPanel Fehlerhandling (U19)
Toast statt `pass` im `except APIError`.

### 4.13 Steps 3+5 im Auto-Matching auf Batch beschränken (B11)
`WHERE c.import_batch_id = ?` hinzufügen.

---

## Zusammenfassung: Aufwand-Schätzung

| Phase | Befunde | Aufwand | Risiko ohne Fix |
|-------|---------|---------|-----------------|
| Phase 1 | 6 kritische | 1-2 Tage | **Datenverlust, tote Funktionen** |
| Phase 2 | 7 hohe | 3-5 Tage | **UI-Freezes, Performance** |
| Phase 3 | 10 mittlere | 1-2 Wochen | **Edge Cases, schleichende Bugs** |
| Phase 4 | 13 niedrige | Fortlaufend | **Tech Debt, UX-Polishing** |
