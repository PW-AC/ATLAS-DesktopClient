# Python API Client + Import-Service Analyse

---

## 1. Dataclass-Korrektheit (provision.py)

### 1.1 Typ-Annotationen

| Befund | Schweregrad | Zeile | Beschreibung |
|--------|------------|-------|--------------|
| `ContractSearchResult.contract: Contract = None` | LOW | 127 | Typ ist `Contract`, Default `None`. Korrekt wäre `Optional[Contract] = None` |
| `DashboardSummary.per_berater: List[Dict]` | LOW | 240 | Untypisiert — Feld-Zugriffe nicht typ-sicher |
| `BeraterAbrechnung` fehlen Audit-Felder | LOW | 317 | `geprueft_von`, `freigegeben_von`, `freigegeben_am` nicht im Dataclass |
| `Commission` fehlt `contract_vsnr` | LOW | 163 | PHP liefert `ct.vsnr AS contract_vsnr`, Python ignoriert es |

### 1.2 `from_dict()` Defensivität

Alle Dataclasses nutzen `.get()` mit Default-Werten — defensive Zugriffe. **Keine Crashes bei fehlenden Feldern.** Allerdings führt das zu stillem Datenverlust:

- **Employee-Einzelabruf:** PHP gibt `SELECT *` zurück (ohne JOINs). `model_name`, `model_rate`, `teamleiter_name` sind immer `None`. Bei Listen-Abruf sind sie vorhanden (LEFT JOIN).
- **Unmatched-Contracts:** PHP liefert `source_type`, `vu_name` aus JOIN. `Contract.from_dict()` ignoriert sie.

---

## 2. API-Methoden-Vollständigkeit

### 2.1 Alle 20 PHP-Endpoints abgedeckt ✓

Jeder PHP-Endpoint hat eine korrespondierende Python-Methode.

### 2.2 Problembefunde

| Befund | Schweregrad | Beschreibung |
|--------|------------|--------------|
| `match_commission()` sendet `berater_id` | LOW | PHP ignoriert diesen Parameter — berater_id wird immer vom Vertrag abgeleitet |
| `match_commission()` fehlt `force_override` | MEDIUM | Kann bestehende Zuordnung nicht überschreiben. Dafür gibt es `assign_contract()`, aber die API-Oberfläche ist verwirrend |
| Reverse-Match-Suggestions als rohe Dicts | MEDIUM | Bei `direction='forward'` → `ContractSearchResult` Objekte. Bei `direction='reverse'` → rohe Dicts. Inkonsistent |
| `delete_employee()` unreachbares `return False` | LOW | Nach `raise` in except-Block |

### 2.3 Duplizierte Funktionalität

`match_commission()` und `assign_contract()` machen dasselbe, aber:

| Aspekt | `match_commission()` | `assign_contract()` |
|--------|---------------------|---------------------|
| PHP Route | `/pm/commissions/{id}/match` | `/pm/assign` |
| Transaktional | **Nein** | **Ja** |
| `force_override` | Nicht unterstützt | Unterstützt |
| Return-Typ | `bool` | `Dict` |

**Empfehlung:** `match_commission()` als Wrapper um `assign_contract()` implementieren oder deprecated markieren.

---

## 3. Import-Service (provision_import.py)

### 3.1 VU_COLUMN_MAPPINGS

Aktuell 3 VU-Formate hardcodiert (Allianz, SwissLife, VB). Die Mappings enthalten:
- `betrag_col`: Spalte mit dem Provisionsbetrag
- `vsnr_col`: Spalte mit der Versicherungsscheinnummer
- `art_col`: Spalte mit der Provisionsart
- `datum_col`: Spalte mit dem Auszahlungsdatum
- `vn_col`: Spalte mit dem Versicherungsnehmer
- `vermittler_col`: Spalte mit dem Vermittlernamen

**Korrektheit der Spalten:** Laut AGENTS.md in v3.2.0 korrigiert (Allianz=AE, SwissLife=U, VB=C für vn_col).

### 3.2 Normalisierungs-Funktionen — PHP/Python-Vergleich

| Funktion | Python | PHP | Status |
|----------|--------|-----|--------|
| `normalize_vsnr` | Z. 25–39 | Z. 40–54 | ✓ Funktional identisch (bis auf INF-Edge-Case) |
| `normalize_vermittler_name` | Z. 42–50 | Z. 56–63 | ✓ Identisch |
| `normalize_for_db` | Z. 53–67 | Z. 65–72 | ✓ Identisch |

**INF-Edge-Case:** Python prüft `not (num != num)` (NaN), PHP prüft `is_finite()` (NaN UND INF). Bei VSNR-Werten extrem unwahrscheinlich.

### 3.3 parse_xempus() vs. parse_xempus_full() — Inkonsistenz

`parse_xempus()` (Z. 595): Skippt IMMER wenn VSNR fehlt — auch mit xempus_id.
`parse_xempus_full()` (Z. 715): Akzeptiert Zeilen MIT xempus_id OHNE VSNR.

Die `full`-Variante ist korrekt. Die einfache Variante verliert Zeilen.

### 3.4 Excel-Parsing Edge Cases

- **Leere Zellen:** `_safe()` Helper gibt `None` zurück bei `None`, leeren Strings, oder `'None'`
- **Merged Cells:** Keine explizite Behandlung. openpyxl gibt `None` für gemergte Zellen zurück → werden als leer behandelt
- **Datumsformate:** 4 Formate unterstützt: `%d.%m.%Y`, `%d.%m.%y`, `%Y-%m-%d`, `%d/%m/%Y`. Kein US-Format, kein ISO mit Uhrzeit
- **Dezimaltrennzeichen:** `_parse_amount()` ersetzt Komma durch Punkt — korrekt für deutsche Excel-Dateien
- **Encoding:** openpyxl liest .xlsx direkt (XML-basiert, UTF-8) — keine Encoding-Probleme

### 3.5 Toter Code

| Code | Zeile | Beschreibung |
|------|-------|--------------|
| `_detect_vb_columns()` | 205–218 | Dynamische VB-Spalten-Erkennung, nie aufgerufen |
| `_detect_vb_columns_iter()` | 333–349 | Iterative Variante, nie aufgerufen |
| `XEMPUS_BERATUNGEN_COLUMNS` | 463–476 | Dict mit Column-Definitionen, nie referenziert |

### 3.6 betrag=0 Handling

VU-Zeilen mit `betrag == 0` werden übersprungen (Z. 282–284). Falls VU-Listen legitime 0,00€-Zeilen enthalten (Storno + Gegenbuchung in einer Zeile), gehen diese verloren.

### 3.7 Überflüssige Daten im Netzwerk

`arbn_id` und `arbg_id` werden von `parse_xempus_full()` extrahiert und via `import_xempus()` an PHP gesendet. PHP liest diese Felder nicht und speichert sie nicht.

---

## 4. Datenfluss-Probleme

### 4.1 Timeout bei großen Imports

Python `import_vu_liste()` sendet alle Zeilen in einem Request mit 120s Timeout. PHP führt dann Batch-Insert + Auto-Matching aus. Bei 15.000+ Zeilen kann das > 120s dauern.

**Empfehlung:** Chunked Upload oder separaten Match-Trigger nach Import.

### 4.2 Pagination-Parameter korrekt

Python sendet `page`/`per_page` als Query-Params, PHP liest sie korrekt. Limits (min 10, max 200) werden server-seitig erzwungen. ✓

### 4.3 Filter-Parameter korrekt

Alle Filter (`berater_id`, `match_status`, `von`, `bis`, `versicherer`, `q`) werden korrekt gemappt. ✓
