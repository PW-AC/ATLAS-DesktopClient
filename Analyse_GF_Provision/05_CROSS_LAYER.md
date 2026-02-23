# Cross-Layer-Konsistenz: PHP ↔ Python ↔ UI

---

## 1. Normalisierungsfunktionen — Synchron ✓

| Funktion | Python (provision_import.py) | PHP (provision.php) | Identisch? |
|----------|------------------------------|---------------------|-----------|
| `normalize_vsnr` | Z. 25–39 | Z. 40–54 | ✓ (bis auf INF-Edge) |
| `normalize_vermittler_name` | Z. 42–50 | Z. 56–63 | ✓ |
| `normalize_for_db` | Z. 53–67 | Z. 65–72 | ✓ |

Umlaut-Handling, Klammer-Auflösung, Leerzeichenkollaps — alles konsistent.

**Einziger Unterschied:** Python prüft `not (num != num)` (nur NaN), PHP prüft `is_finite()` (NaN UND INF). Praxis-Risiko: Extrem niedrig.

---

## 2. Datenformat-Konsistenz: Python → PHP

### 2.1 VU-Import Zeilen ✓

| Python Key | PHP-Zugriff | Match? |
|-----------|-------------|--------|
| `vsnr` | `$row['vsnr']` | ✓ |
| `betrag` | `$row['betrag']` | ✓ |
| `art` | `$row['art']` | ✓ |
| `auszahlungsdatum` | `$row['auszahlungsdatum']` | ✓ |
| `vermittler_name` | `$row['vermittler_name']` | ✓ |
| `versicherungsnehmer` | `$row['versicherungsnehmer']` | ✓ |
| `row_hash` | `$row['row_hash']` | ✓ |
| `courtage_rate` | `$row['courtage_rate']` | ✓ |

### 2.2 Xempus-Import Zeilen

| Python Key | PHP-Zugriff | Match? |
|-----------|-------------|--------|
| `xempus_id` | `$row['xempus_id']` | ✓ |
| `vsnr` | `$row['vsnr']` | ✓ |
| `berater` | `$row['berater']` | ✓ |
| `arbn_id` | **nicht gelesen** | ⚠ Überflüssig |
| `arbg_id` | **nicht gelesen** | ⚠ Überflüssig |

### 2.3 Pagination-Parameter ✓

Python sendet `page`/`per_page` als Query-Params, PHP liest sie aus `$_GET`. Konsistent.

### 2.4 Filter-Parameter ✓

Alle Filter korrekt gemappt: `berater_id`, `match_status`, `von`, `bis`, `versicherer`, `q`.

---

## 3. Response-Parsing: PHP → Python

### 3.1 Datenverlust bei defensiven `.get()` Zugriffen

| Endpoint | PHP liefert | Python verliert | Schweregrad |
|----------|-------------|-----------------|------------|
| GET /pm/employees/{id} | `SELECT *` (ohne JOINs) | `model_name`, `model_rate`, `teamleiter_name` → immer None | MEDIUM |
| GET /pm/contracts (unmatched) | `source_type`, `vu_name` (aus JOIN) | Nicht in Contract-Dataclass | MEDIUM |
| GET /pm/commissions | `ct.vsnr AS contract_vsnr` | Nicht in Commission-Dataclass | LOW |
| GET /pm/abrechnungen/{id} PUT | `geprueft_von`, `freigegeben_von` | Nicht in BeraterAbrechnung | LOW |

### 3.2 Reverse-Match-Suggestions — Typ-Inkonsistenz

- Forward (`direction='forward'`): Suggestions werden zu `ContractSearchResult`-Objekten geparst
- Reverse (`direction='reverse'`): Suggestions bleiben rohe Dicts

UI-Code muss zwei verschiedene Datenformate handhaben.

---

## 4. API-Duplizierung: match vs. assign

| Aspekt | `match_commission()` | `assign_contract()` |
|--------|---------------------|---------------------|
| Python-Methode | `provision.py:505` | `provision.py:768` |
| PHP Route | `/pm/commissions/{id}/match` | `/pm/assign` |
| Transaktional | **NEIN** | **JA** |
| `force_override` | Nicht unterstützt | Unterstützt |
| Activity-Logging | Ja | Ja |
| Split-Neuberechnung | Ja | Ja |
| Berater-Sync | Ja | Ja |

**Problem:** Gleiche Funktionalität, unterschiedliche Sicherheitsgarantien. `match_commission()` könnte inkonsistente Daten hinterlassen.

---

## 5. UI ↔ API-Client Konsistenz

### 5.1 Panels nutzen API-Client korrekt ✓

Alle Panels greifen über `ProvisionAPI`-Instanz auf den Server zu. Kein direkter HTTP-Zugriff.

### 5.2 5000-Zeilen-Limit vs. Server-Pagination

`provisionspositionen_panel.py` lädt max. 5000 Zeilen in einem Request und paginiert client-seitig. Die server-seitige Pagination (`page`/`per_page`) wird NICHT genutzt. Inkonsistent mit der API-Fähigkeit.

### 5.3 Fehlende Fehleranzeige

Mehrere API-Calls in UI-Panels haben kein User-Feedback bei Fehlern:
- `verteilschluessel_panel.py:524` — `except APIError: pass`
- `provisionspositionen_panel.py` — Ignore-Fehler werden geloggt aber nicht angezeigt
- `zuordnung_panel.py` — Mapping-Delete-Fehler nicht angezeigt

---

## 6. Split-Berechnung: PHP ↔ UI-Darstellung

### 6.1 `berater_anteil` = Netto

PHP speichert den Netto-Wert (nach TL-Abzug) in `berater_anteil`. Die UI zeigt diesen Wert korrekt als "Berateranteil" an — was semantisch den Auszahlungsbetrag meint.

Aber: Die Verteilschlüssel-Beispielrechnung (verteilschluessel_panel.py:304) zeigt immer `TL: 0,00 €`, weil sie das Model-Rate direkt nutzt statt TL-Override einzubeziehen. Irreführend für den GF.

### 6.2 Rundungskonsistenz

PHP nutzt `round(..., 2)`, Python nutzt keine explizite Rundung bei der Anzeige. `locale.format_string("%.2f", betrag)` wird verwendet → 2 Nachkommastellen. Konsistent.

---

## 7. Activity-Logging Konsistenz

### 7.1 PHP loggt alle PM-Aktionen ✓

`logPmAction()` wird in allen relevanten Handlern aufgerufen:
- Employee CRUD
- Manual Match
- Ignore
- Import (VU + Xempus)
- Auto-Match
- Mapping CRUD
- Abrechnung Status
- Assign

### 7.2 Audit-Endpoint funktional ✓

`GET /pm/audit` liefert PM-Actions aus `activity_log`. Python-Client und UI parsen korrekt.

---

## 8. Zusammenfassung der Cross-Layer-Befunde

| # | Schweregrad | Beschreibung |
|---|------------|--------------|
| 1 | CRITICAL | `match_commission()` nutzt nicht-transaktionalen Endpoint |
| 2 | MEDIUM | Employee-Einzelabruf fehlen JOIN-Felder |
| 3 | MEDIUM | Unmatched-Contracts verliert source_type/vu_name |
| 4 | MEDIUM | Reverse-Suggestions als rohe Dicts |
| 5 | MEDIUM | 5000-Zeilen-Limit statt Server-Pagination |
| 6 | LOW | arbn_id/arbg_id gesendet aber nicht gelesen |
| 7 | LOW | contract_vsnr nicht im Python-Dataclass |
| 8 | LOW | INF-Edge-Case in normalize_vsnr |
