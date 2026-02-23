# Verbesserungsplan: GF/Provisions-Ebene

---

## Übersicht

Dieser Plan priorisiert alle 67 Befunde in 4 Phasen, geordnet nach Risiko und Aufwand.

| Phase | Ziel | Befunde | Geschätzter Aufwand |
|-------|------|---------|---------------------|
| 1 | CRITICAL + HIGH Bugs fixen | 16 Befunde | ~2–3 Tage |
| 2 | Stabilisierung (Transaktionen, Validierung, Worker) | 15 Befunde | ~3–4 Tage |
| 3 | Performance + Architektur-Verbesserungen | 18 Befunde | ~3–5 Tage |
| 4 | Code-Qualität + Aufräumen | 18 Befunde | ~2–3 Tage |

**Gesamtaufwand:** ~10–15 Tage

---

## Phase 1: CRITICAL + HIGH Bugs fixen (Prio 1)

### 1.1 PillBadgeDelegate Crash in xempus_panel.py fixen
- **Befund:** C-2
- **Datei:** `src/ui/provision/xempus_panel.py` Zeile 270–271
- **Aktion:** Argumente tauschen:
  ```python
  # VORHER (falsch):
  PillBadgeDelegate(self._table, PILL_COLORS)
  # NACHHER (korrekt):
  PillBadgeDelegate(PILL_COLORS, parent=self._table)
  ```
- **Aufwand:** 5 Minuten
- **Risiko:** Keines

### 1.2 Transaction um `/commissions/{id}/match` legen
- **Befund:** C-1
- **Datei:** `BiPro-Webspace Spiegelung Live/api/provision.php` Zeile 847–863
- **Aktion:** `beginTransaction()` / `commit()` / `rollBack()` um den gesamten Block legen, analog zu `handleAssignRoute()` (Z. 1925).
- **Aufwand:** 30 Minuten
- **Risiko:** Niedrig — identisches Pattern wie bestehender `/pm/assign`

### 1.3 Auto-Matching: Batch-Filter konsistent anwenden
- **Befund:** C-3
- **Datei:** `provision.php` Zeile 375–437
- **Aktion:** Schritte 2.5, 3b, 5 mit `$batchFilter` eingrenzen ODER als separaten Housekeeping-Endpoint auslagern, der explizit aufgerufen wird.
- **Option A (schnell):** `$batchFilter` in allen Subqueries einbauen
- **Option B (sauber):** Globale Schritte in eigene Funktion `resolveGlobalDependencies()` auslagern, die nur bei explizitem Trigger läuft
- **Aufwand:** 1–2 Stunden
- **Risiko:** Mittel — muss getestet werden mit bestehenden Daten

### 1.4 DB-Indizes anlegen
- **Befund:** H-1
- **Datei:** Neue Migration `025_provision_indexes.php`
- **Aktion:**
  ```sql
  ALTER TABLE pm_commissions ADD INDEX idx_comm_match_status (match_status);
  ALTER TABLE pm_commissions ADD INDEX idx_comm_berater_id (berater_id);
  ALTER TABLE pm_commissions ADD INDEX idx_comm_contract_id (contract_id);
  ALTER TABLE pm_commissions ADD INDEX idx_comm_auszahlungsdatum (auszahlungsdatum);
  ALTER TABLE pm_commissions ADD INDEX idx_comm_batch_id (import_batch_id);
  ALTER TABLE pm_contracts ADD INDEX idx_contr_berater_id (berater_id);
  ALTER TABLE pm_contracts ADD INDEX idx_contr_status (status);
  -- Composite für häufigste Kombination:
  ALTER TABLE pm_commissions ADD INDEX idx_comm_status_berater (match_status, berater_id);
  ```
- **Aufwand:** 30 Minuten (Migration schreiben + ausführen)
- **Risiko:** Niedrig — rein additive DB-Änderung

### 1.5 Synchrone API-Calls in Worker auslagern (5 Stellen)
- **Befund:** H-4 bis H-7
- **Dateien:**
  - `dashboard_panel.py:487` → `_BeraterDetailWorker`
  - `provisionspositionen_panel.py:718` → `_AuditLoadWorker`
  - `provisionspositionen_panel.py:745` → `_IgnoreWorker`
  - `provisionspositionen_panel.py:809` → `_MappingCreateWorker`
  - `auszahlungen_panel.py:443` → `_PositionenLoadWorker`
- **Pattern:** Gleich wie bestehender `_LoadWorker`:
  ```python
  class _AuditLoadWorker(QThread):
      finished = Signal(list)
      error = Signal(str)
      def run(self):
          try:
              entries = self._api.get_audit_log(...)
              self.finished.emit(entries)
          except Exception as e:
              self.error.emit(str(e))
  ```
- **Aufwand:** 2–3 Stunden (5 Worker + Signal-Verdrahtung)
- **Risiko:** Niedrig — bewährtes Pattern

### 1.6 Hardcoded Strings in i18n migrieren (~15 Stellen)
- **Befund:** H-8 bis H-13
- **Dateien:** dashboard_panel, provisionspositionen_panel, zuordnung_panel, abrechnungslaeufe_panel, auszahlungen_panel, verteilschluessel_panel, widgets.py
- **Aktion:** ~30 neue Keys in `src/i18n/de.py` anlegen und in den Panels referenzieren
- **Aufwand:** 1–2 Stunden
- **Risiko:** Keines

---

## Phase 2: Stabilisierung (Prio 2)

### 2.1 Transaktionen für alle kritischen Operationen
- **Befunde:** M-5 (syncBerater), autoMatchCommissions, handleImportVuListe
- **Aktion:**
  - `autoMatchCommissions()` in Transaction wrappen
  - `handleImportVuListe()` Import + Match in Transaction wrappen
  - `syncBeraterToCommissions()` mit `batchRecalculateSplits()` ersetzen (statt N einzelne Calls)
- **Aufwand:** 2 Stunden

### 2.2 Employee-Feld-Validierung
- **Befund:** M-17
- **Datei:** `provision.php` Zeile 544+
- **Aktion:**
  ```php
  // Rate-Validierung
  if (isset($data['commission_rate_override']) && 
      ($data['commission_rate_override'] < 0 || $data['commission_rate_override'] > 100)) {
      json_error('Rate muss zwischen 0 und 100 liegen', 400);
  }
  // TL-Basis-Validierung
  if (isset($data['tl_override_basis']) && 
      !in_array($data['tl_override_basis'], ['berater_anteil', 'gesamt_courtage'])) {
      json_error('Ungueltige TL-Override-Basis', 400);
  }
  // Selbstreferenz
  if (isset($data['teamleiter_id']) && $data['teamleiter_id'] == $id) {
      json_error('Mitarbeiter kann nicht sein eigener Teamleiter sein', 400);
  }
  ```
- **Aufwand:** 1 Stunde

### 2.3 Abrechnungs-Status-Transitions validieren
- **Befund:** M-18
- **Datei:** `provision.php` Zeile 1641+
- **Aktion:** State-Machine mit erlaubten Übergängen:
  ```php
  $allowedTransitions = [
      'berechnet' => ['geprueft'],
      'geprueft' => ['berechnet', 'freigegeben'],
      'freigegeben' => ['geprueft', 'ausgezahlt'],
      'ausgezahlt' => [],  // Terminal-Status
  ];
  ```
- **Aufwand:** 30 Minuten

### 2.4 Race Condition bei Revisions-Erstellung
- **Befund:** M-16
- **Datei:** `provision.php` Zeile 1611
- **Aktion:** UNIQUE-Constraint `(abrechnungsmonat, berater_id, revision)` + INSERT mit `SELECT MAX(revision) + 1` in einer Abfrage:
  ```sql
  INSERT INTO pm_berater_abrechnungen (abrechnungsmonat, berater_id, revision, ...)
  SELECT ?, ?, COALESCE(MAX(revision), 0) + 1, ...
  FROM pm_berater_abrechnungen WHERE abrechnungsmonat = ? AND berater_id = ?
  ```
- **Aufwand:** 1 Stunde

### 2.5 VSNR-Normalisierung: Buchstaben beibehalten
- **Befund:** H-2
- **Aktion:** `normalizeVsnr()` ändern: Buchstaben beibehalten, nur Sonderzeichen und Leerzeichen entfernen, Lowercase:
  ```
  "ABC-12345" → "abc12345"
  "XYZ-12345" → "xyz12345"
  ```
  Erfordert Re-Normalisierung aller bestehenden Daten (Backfill-Migration).
- **Aufwand:** 2–3 Stunden (PHP + Python + Migration + Test)
- **Risiko:** HOCH — Bestehendes Matching kann sich ändern. Vorher Backup!

### 2.6 VU-Abgleich im Auto-Matching
- **Befund:** M-20
- **Aktion:** In Step 1 (VSNR-Match) zusätzlich `versicherer` in den JOIN einbeziehen:
  ```sql
  INNER JOIN pm_contracts ct 
    ON c2.vsnr_normalized = ct.vsnr_normalized
    AND (c2.versicherer = ct.versicherer OR ct.versicherer IS NULL)
  ```
- **Aufwand:** 1 Stunde
- **Risiko:** Mittel — Muss getestet werden. Fallback auf reinen VSNR-Match bei fehlender VU.

### 2.7 Worker-Thread-Management verbessern
- **Befund:** M-22, M-27
- **Aktion:**
  - `provision_hub.py`: `get_blocking_operations()` um alle Worker-Panels erweitern
  - `abrechnungslaeufe_panel.py`: `requestInterruption()` statt `quit()` verwenden
  - Hub-Schließung: Alle laufenden Worker stoppen
- **Aufwand:** 1–2 Stunden

### 2.8 Pagination-Signal verbinden
- **Befund:** M-28
- **Datei:** `auszahlungen_panel.py` Zeile 283
- **Aktion:** `self._pagination.page_changed.connect(self._on_page_changed)` + Handler implementieren
- **Aufwand:** 30 Minuten

### 2.9 DonutChart NaN-Handling
- **Befund:** M-30
- **Datei:** `widgets.py` (DonutChartWidget)
- **Aktion:**
  ```python
  import math
  def set_percent(self, value: float):
      if math.isnan(value) or math.isinf(value):
          value = 0.0
      self._percent = max(0.0, min(100.0, value))
  ```
- **Aufwand:** 5 Minuten

### 2.10 FilterChipBar Stretch-Akkumulation
- **Befund:** M-29
- **Datei:** `widgets.py` Zeile 177–190
- **Aktion:** In `set_chips()` auch Stretch-Items entfernen:
  ```python
  while self._layout.count():
      item = self._layout.takeAt(0)
      if item.widget():
          item.widget().deleteLater()
  ```
- **Aufwand:** 10 Minuten

---

## Phase 3: Performance + Architektur (Prio 3)

### 3.1 Server-seitige Pagination nutzen
- **Befund:** M-9
- **Datei:** `provisionspositionen_panel.py`
- **Aktion:** Statt `limit=5000` die server-seitige `page`/`per_page` API nutzen. Beim Blättern wird jeweils eine neue Seite geladen.
- **Aufwand:** 2–3 Stunden (Panel-Umbau + Loading-State)

### 3.2 Korrelierte Subqueries optimieren
- **Befund:** M-6, M-7
- **Datei:** `provision.php` Contracts GET + Abrechnungen GET
- **Aktion:**
  - Contracts: Subqueries durch LEFT JOIN + GROUP BY ersetzen
  - Abrechnungen: Window-Funktion `ROW_NUMBER() OVER (PARTITION BY ...)` statt korrelierter MAX
- **Aufwand:** 2 Stunden

### 3.3 N+1 in syncBeraterToCommissions beheben
- **Befund:** M-5
- **Datei:** `provision.php` Zeile 100–117
- **Aktion:** `recalculateCommissionSplit()`-Loop durch `batchRecalculateSplits()` mit `contract_id`-Filter ersetzen:
  ```php
  batchRecalculateSplits("AND c.contract_id = ?", [$contractId]);
  ```
- **Aufwand:** 30 Minuten

### 3.4 Xempus-Import Batch-Updates
- **Befund:** M-8
- **Aktion:** Einzelne UPDATEs durch CASE-Expression oder Temporary Table + JOIN ersetzen
- **Aufwand:** 2 Stunden

### 3.5 Import-Worker Chunk-Aggregation
- **Befund:** M-26
- **Datei:** `abrechnungslaeufe_panel.py` Zeile 136–159
- **Aktion:** Ergebnisse über alle Chunks akkumulieren statt nur letzten zurückzugeben:
  ```python
  total_result = ImportResult()
  for chunk in chunks:
      result = self._api.import_vu_liste(chunk)
      total_result.imported += result.imported
      total_result.skipped += result.skipped
  self.finished.emit(total_result)
  ```
- **Aufwand:** 30 Minuten

### 3.6 Doppeltes Laden im Zuordnung-Panel eliminieren
- **Befund:** M-23
- **Datei:** `zuordnung_panel.py` Zeile 61–63
- **Aktion:** Einmal `get_commissions(limit=5000)` laden und client-seitig filtern
- **Aufwand:** 30 Minuten

### 3.7 `match_commission()` als Wrapper um `assign_contract()` refactoren
- **Befund:** H-3, M-12
- **Aktion:** `match_commission()` deprecated markieren und intern `assign_contract()` aufrufen. Oder: `/commissions/{id}/match` PHP-Route intern auf `/pm/assign` umleiten.
- **Aufwand:** 1 Stunde

### 3.8 Employee-Einzelabruf mit JOINs
- **Befund:** M-10
- **Datei:** `provision.php` Zeile 527–530
- **Aktion:** `SELECT *` durch SELECT mit JOINs ersetzen (analog zur Listen-Query):
  ```sql
  SELECT e.*, m.name AS model_name, m.commission_rate AS model_rate, 
         tl.name AS teamleiter_name
  FROM pm_employees e
  LEFT JOIN pm_commission_models m ON e.commission_model_id = m.id
  LEFT JOIN pm_employees tl ON e.teamleiter_id = tl.id
  WHERE e.id = ?
  ```
- **Aufwand:** 15 Minuten

### 3.9 Reverse-Match-Suggestions typisieren
- **Befund:** M-13
- **Datei:** `provision.py` Zeile 760–762
- **Aktion:** Reverse-Suggestions in `CommissionSearchResult`-Dataclass parsen (neu anlegen)
- **Aufwand:** 30 Minuten

### 3.10 Verteilschlüssel-Beispielrechnung mit TL-Override
- **Befund:** M-4
- **Datei:** `verteilschluessel_panel.py` Zeile 304
- **Aktion:** TL-Rate des Modells in die Beispielrechnung einbeziehen
- **Aufwand:** 30 Minuten

---

## Phase 4: Code-Qualität + Aufräumen (Prio 4)

### 4.1 Toter Code entfernen
- `getEffectiveRate()` in provision.php (Z. 74–86)
- `_detect_vb_columns()` und `_detect_vb_columns_iter()` in provision_import.py
- `XEMPUS_BERATUNGEN_COLUMNS` in provision_import.py
- Unreachbares `return False` in provision.py:433

### 4.2 `parse_xempus()` mit `parse_xempus_full()` vereinheitlichen
- **Befund:** M-14 (provision_import.py:595 vs. 715)
- **Aktion:** Die einfache Variante anpassen: Zeilen mit xempus_id OHNE VSNR akzeptieren

### 4.3 Header-Dokumentation in provision.php aktualisieren
- **Befund:** L-6
- Neue Routen (match-suggestions, assign, clearance, audit) im Header ergänzen

### 4.4 `json_error()` mit explizitem `return` absichern
- **Befund:** M-21 (provision.php:529, 576, 601)
- Oder: Sicherstellen dass `json_error()` immer `exit()` aufruft

### 4.5 PillBadge-Keys stabilisieren
- **Befund:** M-24 (zuordnung_panel.py:802)
- **Aktion:** Feste String-Keys statt aus i18n generierte Keys verwenden

### 4.6 `_all_unmatched` in `__init__` deklarieren
- **Befund:** M-25 (zuordnung_panel.py:316)
- `self._all_unmatched = []` im `__init__` setzen

### 4.7 Überflüssige Daten entfernen
- `arbn_id`/`arbg_id` nicht mehr an PHP senden (oder PHP zum Speichern bringen)
- `berater_id` aus `match_commission()` entfernen

### 4.8 Loose comparison `== 0` durch `=== 0.0` ersetzen
- **Befund:** L-4 (provision.php:979)

### 4.9 StatementCard Layout-Leak fixen
- **Befund:** L-18 (widgets.py:569)

### 4.10 betrag=0 Handling überdenken
- **Befund:** L-15 (provision_import.py:282)
- Entscheidung: 0,00€-Zeilen importieren oder bewusst überspringen?

---

## Empfohlene Reihenfolge

```
Phase 1.1 → SOFORT (5 Min): PillBadgeDelegate-Crash fixen
Phase 1.2 → SOFORT (30 Min): Transaction um /match legen
Phase 1.4 → Tag 1 (30 Min): DB-Indizes anlegen
Phase 1.3 → Tag 1 (1–2h): Auto-Matching Batch-Filter
Phase 1.5 → Tag 1–2 (2–3h): Synchrone Calls in Worker
Phase 1.6 → Tag 2 (1–2h): i18n Strings
Phase 2.1–2.10 → Tag 3–6: Stabilisierung
Phase 3.1–3.10 → Tag 7–11: Performance
Phase 4.1–4.10 → Tag 12–14: Aufräumen
```

---

## Risiko-Matrix

| Maßnahme | Aufwand | Risiko | Impact |
|----------|---------|--------|--------|
| 1.1 PillBadge-Fix | 5 Min | Keines | Crash beseitigt |
| 1.2 Transaction | 30 Min | Niedrig | Datenintegrität |
| 1.3 Batch-Filter | 1–2h | Mittel | Datenintegrität + Performance |
| 1.4 Indizes | 30 Min | Niedrig | Performance bei 15k+ Zeilen |
| 2.5 VSNR-Normalisierung | 2–3h | **HOCH** | Matching-Korrektheit, aber bestehendes Matching ändert sich |
| 2.6 VU-Abgleich | 1h | Mittel | Matching-Präzision |
| 3.1 Server-Pagination | 2–3h | Niedrig | Speicher + Performance |

---

## Bonus-Empfehlungen (nicht in Befunden, aber wertvoll)

### B-1: Berater-Brutto als eigene Spalte speichern
Aktuell ist `berater_anteil` der Netto-Wert. Für Auswertungen und Debugging wäre eine zusätzliche Spalte `berater_brutto` hilfreich.

### B-2: Integration-Tests für Split-Engine
Automatisierte Tests für:
- Positive Provision ohne TL
- Positive Provision mit TL (Basis berater_anteil)
- Positive Provision mit TL (Basis gesamt_courtage)
- Negative Rückbelastung
- Edge Cases (betrag=0, rate=0, rate=100)

### B-3: Matching-Confidence verbessern
Aktuell: VSNR-Match → confidence=1.0, Alt-VSNR → confidence=0.9. Könnte verbessert werden durch:
- VU-Abgleich als Multiplikator
- VN-Name-Ähnlichkeit als Bonus
- Betrags-Plausibilität

### B-4: Export-Funktion für Provisionsabrechnungen
PDF-Export mit Briefkopf für die monatliche Berater-Abrechnung (derzeit nur CSV/Excel).

### B-5: Dashboard-KPIs periodisch cachen
Dashboard-Summary-Query aggregiert über alle Commissions bei jedem Aufruf. Bei 15k+ Zeilen könnte ein Cache (materialized view oder PHP-Cache mit TTL) sinnvoll sein.
