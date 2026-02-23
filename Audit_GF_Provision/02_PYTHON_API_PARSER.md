# Audit: Python API Client + Parser

**Dateien**:  
- `src/api/provision.py` (~680 Zeilen)  
- `src/services/provision_import.py` (~767 Zeilen)  
**Datum**: 20. Februar 2026

---

## provision.py — API Client

### P1: Doppelte Endpoints für Zuordnung

| Feld | Wert |
|------|------|
| **Kategorie** | Inkonsistenz / Tech Debt |
| **Schwere** | Mittel |
| **Ort** | `match_commission()` Zeile 505-515, `assign_contract()` Zeile 768-786 |

**Problem**: Beide Methoden ordnen eine Provision einem Vertrag zu:
- `match_commission()` → `PUT /pm/commissions/{id}/match`
- `assign_contract()` → `PUT /pm/assign`

Beide rufen im PHP `assignContractToCommission()` auf. Aber nur `/pm/assign` ist transaktionssicher + hat Audit-Logging.

**Fix**: `match_commission()` als deprecated markieren, alle Aufrufe zu `assign_contract()` migrieren.

---

### P2: Fehlende `contract_vsnr` in Commission Dataclass

| Feld | Wert |
|------|------|
| **Kategorie** | Missing Feature |
| **Schwere** | Mittel |
| **Ort** | `Commission` Dataclass, Zeile 163-223 |

**Problem**: PHP liefert `ct.vsnr AS contract_vsnr` per JOIN. Python-Dataclass hat kein Feld dafür → Wert wird verworfen.

**Fix**: `contract_vsnr: Optional[str] = None` hinzufügen + `from_dict` parsen.

---

### P3: Reverse-Suggestions werden nicht zu Dataclasses geparst

| Feld | Wert |
|------|------|
| **Kategorie** | Inkonsistenz |
| **Schwere** | Mittel |
| **Ort** | `get_match_suggestions()`, Zeile 760-761 |

**Problem**: Bei `direction='forward'` werden Suggestions zu `ContractSearchResult` geparst. Bei `direction='reverse'` bleiben sie als rohe Dicts.

**Fix**: Bei reverse ebenfalls in typierte Dataclasses parsen.

---

### P4: ContractSearchResult.contract Typ-Inkonsistenz

| Feld | Wert |
|------|------|
| **Kategorie** | Inkonsistenz |
| **Schwere** | Niedrig |
| **Ort** | `ContractSearchResult`, Zeile 127 |

**Problem**: `contract: Contract = None` — Typ sagt `Contract`, Default ist `None`. Sollte `Optional[Contract] = None` sein.

---

### P5: Unreachable Code in delete_employee

| Feld | Wert |
|------|------|
| **Kategorie** | Bug (minor) |
| **Schwere** | Niedrig |
| **Ort** | `delete_employee()`, Zeile 433 |

**Problem**: `return False` nach `except: raise` ist niemals erreichbar.

**Fix**: Zeile entfernen.

---

### P6: get_employee() liefert unvollständige Daten

| Feld | Wert |
|------|------|
| **Kategorie** | Inkonsistenz |
| **Schwere** | Niedrig |
| **Ort** | `get_employee()`, Zeile 393-400 |

**Problem**: PHP `GET /pm/employees/{id}` gibt `SELECT *` zurück — ohne JOINs. `model_name`, `model_rate`, `teamleiter_name` fehlen (die Liste hat JOINs). `effective_rate` gibt 0.0 statt Modellsatz.

**Fix**: PHP `GET /{id}` um gleiche JOINs wie Liste ergänzen.

---

### P7: Inkonsistente Return-Type-Annotations

| Feld | Wert |
|------|------|
| **Kategorie** | Inkonsistenz |
| **Schwere** | Niedrig |
| **Ort** | `get_commissions()` Zeile 471, `get_unmatched_contracts()` Zeile 790 |

**Problem**: Beide als `-> tuple` annotiert statt `-> Tuple[List[...], Optional[PaginationInfo]]`.

---

### P8: monat-Parameter fehlt in get_dashboard_summary

| Feld | Wert |
|------|------|
| **Kategorie** | Missing Feature |
| **Schwere** | Niedrig |
| **Ort** | `get_dashboard_summary()`, Zeile 595 |

**Problem**: PHP unterstützt `$_GET['monat']`, Python exponiert nur `von/bis`. Kein funktionaler Nachteil, aber Convenience fehlt.

---

## provision_import.py — Excel Parser

### P9: Massive Code-Duplikation: parse_xempus vs parse_xempus_full

| Feld | Wert |
|------|------|
| **Kategorie** | Tech Debt / Logik-Risiko |
| **Schwere** | Hoch |
| **Ort** | `parse_xempus()` Zeilen 535-630, `parse_xempus_full()` Zeilen 655-767 |

**Problem**: Die gesamte Row-Parsing-Logik (~70 Zeilen) ist 1:1 dupliziert. Kritische Unterschiede:

| Aspekt | parse_xempus | parse_xempus_full |
|--------|-------------|-------------------|
| Skip-Bedingung | `not vsnr` → skip | `not vsnr and not xempus_id` → skip |
| `_safe()` Return | `''` bei leer | `None` bei leer |

Änderungen müssen an BEIDEN Stellen gemacht werden → Bug-Risiko.

**Fix**: Gemeinsame `_parse_xempus_rows()` Funktion extrahieren.

---

### P10: Hardcodierte Xempus-ID-Spalten (fragil)

| Feld | Wert |
|------|------|
| **Kategorie** | Logik-Risiko |
| **Schwere** | Hoch |
| **Ort** | Zeilen 478-483 |

**Problem**: `XEMPUS_ID_COL = 'AM'`, `XEMPUS_ARBN_ID_COL = 'AN'`, `XEMPUS_ARBG_ID_COL = 'AO'` sind feste Spaltenpositionen. Alle anderen Felder werden per Header-Erkennung (`_detect_xempus_columns`) erkannt.

Wenn Xempus eine Spalte vor AM einfügt, werden IDs aus der falschen Spalte gelesen — still und leise.

**Fix**: xempus_id, arbn_id, arbg_id ebenfalls per Header-Keyword erkennen.

---

### P11: Sheet-Name Case-Sensitivity Bug

| Feld | Wert |
|------|------|
| **Kategorie** | Bug |
| **Schwere** | Mittel |
| **Ort** | `parse_vu_liste()`, Zeile 378 |

**Problem**: `VU_COLUMN_MAPPINGS` hat Keys `'Allianz'`, `'SwissLife'`, `'VB'`. Ein Excel-Sheet namens `'allianz'` oder `'ALLIANZ'` wird nicht gefunden.

**Fix**: Case-insensitives Matching via `{s.lower(): s for s in wb.sheetnames}`.

---

### P12: _parse_amount behandelt Klammer-Negative nicht

| Feld | Wert |
|------|------|
| **Kategorie** | Missing Feature |
| **Schwere** | Mittel |
| **Ort** | `_parse_amount()`, Zeilen 93-110 |

**Problem**: Buchhaltungsformat `(123,45)` für negative Beträge wird nicht erkannt → gibt `None` zurück. In VU-Provisionslisten verbreitet.

**Fix**: Klammer-Erkennung vor dem Parsing:
```python
if s.startswith('(') and s.endswith(')'):
    s = '-' + s[1:-1]
```

---

### P13: parse_vu_sheet überschreibt `art` bei negativen Beträgen

| Feld | Wert |
|------|------|
| **Kategorie** | Logik-Fehler |
| **Schwere** | Mittel |
| **Ort** | `parse_vu_sheet()`, Zeile 306-307 |

**Problem**: `if betrag < 0: art = 'rueckbelastung'` überschreibt den VU-spezifischen Art-Wert blind. Die Originalinformation geht verloren.

PHP prüft `$art === 'rueckbelastung' OR $betrag < 0` separat — die Python-Überschreibung ist also unnötig und sogar schädlich.

**Fix**: Art-Überschreibung entfernen, dem Server die Entscheidung überlassen.

---

### P14: Dead Code — 5+ nie aufgerufene Funktionen/Konstanten

| Feld | Wert |
|------|------|
| **Kategorie** | Tech Debt |
| **Schwere** | Niedrig |
| **Ort** | Diverse |

| Funktion/Konstante | Zeile | Status |
|---------------------|-------|--------|
| `_cell_val(ws, row, col)` | 130-133 | Nie aufgerufen |
| `_detect_vb_columns(ws, header_row)` | 205-218 | Nie aufgerufen |
| `_detect_vb_columns_iter(wb, sheet_name)` | 333-349 | Nie aufgerufen |
| `XEMPUS_BERATUNGEN_COLUMNS` | 463-476 | Nie gelesen |
| `XEMPUS_STATUS_COL`, `XEMPUS_VSNR_COL` | 481-482 | Nie verwendet |

**Fix**: Alle entfernen.

---

### P15: _parse_date behandelt Excel-Seriennummern nicht

| Feld | Wert |
|------|------|
| **Kategorie** | Edge Case |
| **Schwere** | Niedrig |
| **Ort** | `_parse_date()`, Zeilen 113-127 |

**Problem**: Wenn Datumszelle als Zahl formatiert ist (Seriennummer 45678), kommt sie als `int` → kein Format-Match → `None`.

**Fix**: `isinstance(val, (int, float))` → Excel-Datum konvertieren.

---

### P16: normalize_vsnr Infinity-Edge-Case

| Feld | Wert |
|------|------|
| **Kategorie** | Inkonsistenz |
| **Schwere** | Niedrig |
| **Ort** | `normalize_vsnr()`, Zeile 34 |

**Problem**: Python fängt `inf` via OverflowError im except, PHP via `is_finite()` explizit. Funktional identisch, aber PHP ist intentionaler.
