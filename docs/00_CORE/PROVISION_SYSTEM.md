# ACENCIA ATLAS - Provisionsmanagement (GF-Bereich)

**Letzte Aktualisierung:** 24. Februar 2026
**Versionen:** v3.0.0 (Initial), v3.1.0 (GF-Rework), v3.2.0 (Matching V2), v3.2.1/v3.2.2 (Stabilisierung), v3.3.0 (Xempus Insight), v3.4.0 (Refactoring: Workers/Models/Dialogs extrahiert)

---

## Zweck und Zielgruppe

Das Provisionsmanagement ist das Geschaeftsfuehrer-Modul von ACENCIA ATLAS. Es ermoeglicht:

- **Provisionsabrechnung**: VU-Provisionslisten importieren und automatisch Vertraegen/Beratern zuordnen
- **Berater-Verwaltung**: Mitarbeiter mit Rollen, Provisionssaetzen und Teamleiter-Zuordnungen verwalten
- **Xempus-Datenanalyse**: Xempus-Exporte (Arbeitgeber, Tarife, Beratungen) importieren und mit VU-Daten abgleichen
- **Monatsabrechnungen**: Berater-Abrechnungen generieren, pruefen, freigeben und als ausgezahlt markieren
- **Klaerfaelle loesen**: Nicht zugeordnete Provisionen manuell oder per Multi-Level-Matching Vertraegen zuweisen

### Zugang
- `provision_access` Berechtigung noetig (nicht automatisch fuer Admins)
- `provision_manage` fuer Gefahrenzone und Rechtevergabe an andere
- Eigener Vollbild-Hub mit Sidebar (wie Admin-Bereich)

---

## Architektur

```
┌───────────────────────────────────────────────────────────────────┐
│ ProvisionHub (provision_hub.py, 328 Zeilen)                       │
│ ┌────────────┐  ┌──────────────────────────────────────────────┐  │
│ │ Sidebar    │  │ QStackedWidget (8 Panels, Lazy-Loading)      │  │
│ │ 8 Eintraege│  │                                              │  │
│ │ + Zurueck  │  │  Panel 0: Dashboard (~436 Z.)                │  │
│ └────────────┘  │  Panel 1: Abrechnungslaeufe (~276 Z.)        │  │
│                  │  Panel 2: Provisionspositionen (~657 Z.)     │  │
│                  │  Panel 3: Xempus Insight (~784 Z.) [4 Tabs]  │  │
│                  │  Panel 4: Zuordnung & Klaerfaelle (~398 Z.)  │  │
│                  │  Panel 5: Verteilschluessel (~648 Z.)        │  │
│                  │  Panel 6: Auszahlungen (~491 Z.)             │  │
│                  │  Panel 7: Einstellungen (341 Z.)             │  │
│                  └──────────────────────────────────────────────┘  │
│                                                                    │
│  Shared: widgets.py (821 Z.), workers.py (~640 Z., 24 Worker),    │
│          models.py (~1.179 Z., 12 Models), dialogs.py (~348 Z.)   │
└───────────────────────────────────────────────────────────────────┘
```

### Dateien (Python)

| Datei | Zeilen | Zweck |
|-------|--------|-------|
| `src/ui/provision/provision_hub.py` | ~340 | Hub mit Sidebar + 8 Panels |
| `src/ui/provision/dashboard_panel.py` | ~436 | 4 KPI-Karten, DonutChart, Berater-Ranking |
| `src/ui/provision/abrechnungslaeufe_panel.py` | ~276 | Import + Batch-Historie |
| `src/ui/provision/provisionspositionen_panel.py` | ~657 | Master-Detail, FilterChips, PillBadges |
| `src/ui/provision/xempus_insight_panel.py` | ~784 | 4-Tab Xempus-Analyse |
| `src/ui/provision/xempus_panel.py` | ~333 | Xempus-Beratungen-Liste |
| `src/ui/provision/zuordnung_panel.py` | ~398 | Klaerfaelle + Reverse-Matching |
| `src/ui/provision/verteilschluessel_panel.py` | ~648 | Modell-Karten + Mitarbeiter |
| `src/ui/provision/auszahlungen_panel.py` | ~491 | StatementCards, Status-Workflow |
| `src/ui/provision/settings_panel.py` | 341 | Gefahrenzone (Reset) |
| `src/ui/provision/widgets.py` | 821 | 9 Shared Widgets |
| `src/ui/provision/workers.py` | ~640 | **24 QThread-Worker (Refactoring v3.4.0)** |
| `src/ui/provision/models.py` | ~1.179 | **12 QAbstractTableModel-Klassen (Refactoring v3.4.0)** |
| `src/ui/provision/dialogs.py` | ~348 | **MatchContractDialog + DiffDialog (Refactoring v3.4.0)** |
| `src/api/provision.py` | ~859 | API Client (40+ Methoden, 11 Dataclasses) |
| `src/api/xempus.py` | 377 | Xempus API Client |
| `src/domain/xempus_models.py` | 375 | 9 Xempus-Dataclasses |
| `src/services/provision_import.py` | 738 | VU/Xempus Excel-Parser |
| `src/services/xempus_parser.py` | 404 | Xempus 5-Sheet Parser |

### Dateien (PHP)

| Datei | Zeilen | Zweck |
|-------|--------|-------|
| `provision.php` | ~2.480 | Hauptbackend (32+ Routes, Split-Engine, Auto-Matching) |
| `xempus.php` | 1.360 | Xempus Insight Engine (4-Phasen-Import, CRUD, Stats) |

---

## Datenmodell

> **Detaillierte Feld-Definitionen**: Siehe `docs/00_CORE/DOMAIN.md` Abschnitt "Provisionsmanagement-Datenmodell"

### PM-Tabellen (7 Stueck)
| Tabelle | Zweck |
|---------|-------|
| `pm_commission_models` | Provisionssatzmodelle (Rate, Name) |
| `pm_employees` | Mitarbeiter (Rolle, Provisionssatz, TL-Zuordnung) |
| `pm_contracts` | Vertraege aus Xempus (VSNR, VU, Berater, Status) |
| `pm_commissions` | Provisionsbuchungen (Betrag, Match-Status, Splits) |
| `pm_vermittler_mapping` | VU-Vermittlername → interner Berater |
| `pm_berater_abrechnungen` | Monats-Snapshots (Revisioniert, Status-Workflow) |
| `pm_import_batches` | Import-Tracking (Source, Rows, Fehler) |

---

## Xempus Insight Engine (v3.3.0)

### 9 Tabellen

| Tabelle | Zweck |
|---------|-------|
| `xempus_employers` | Arbeitgeber (Name, Adresse, Kontakt) |
| `xempus_tariffs` | Tarife pro AG (Versicherer, Typ, Gruppenvertrag) |
| `xempus_subsidies` | AG-Zuschuesse (Typ, Betrag, Frequenz) |
| `xempus_employees` | Arbeitnehmer (Name, Geburtstag, Status) |
| `xempus_consultations` | Beratungen (VSNR, VU, Sparte, Status, Berater) |
| `xempus_raw_rows` | Rohdaten pro Sheet (JSON, row_hash) |
| `xempus_import_batches` | Import-Tracking (4 Phasen + Content-Hash) |
| `xempus_commission_matches` | Consultation ↔ Commission Matches |
| `xempus_status_mappings` | Xempus-Status → interner Status |

### 4-Phasen-Import

```
Phase 1: RAW Ingest
  Excel → xempus_parser.py → API chunked POST → xempus_raw_rows
  (jede Zeile als JSON mit row_hash, Sheet-Name, batch_id)

Phase 2: Normalize + Parse (Server-seitig)
  xempus.php → handleXempusParseRoute()
  raw_rows → xempus_employers, _tariffs, _subsidies, _employees, _consultations
  Upsert-Logik: Bestehende Datensaetze aktualisieren, neue erstellen

Phase 3: Snapshot Update (automatisch in Phase 2)
  Diff-Berechnung: Neue/geaenderte/entfernte Entitaeten
  is_active Flag aktualisieren (entfernte → inactive)

Phase 4: Finalize
  Content-Hash berechnen, import_phase='complete'
  Batch als abgeschlossen markieren
```

### UI (4-Tab Panel)
1. **Arbeitgeber**: Tabelle mit Tarif-Details
2. **Statistiken**: Uebersicht (AG-Anzahl, ArbN, Beratungen, Match-Rate)
3. **Import**: Upload + 4-Phasen-Progress
4. **Status-Mapping**: Xempus-Status ↔ Interner Status konfigurieren

---

## Split-Engine

Die Split-Berechnung laeuft in 3 optimierten Batch-SQL-Updates:

### Schritt A: Rueckbelastungen (negative Betraege)
```
berater_anteil = betrag × rate / 100
tl_anteil = 0  (Teamleiter traegt Verluste nicht mit)
ag_anteil = betrag - berater_anteil
```

### Schritt B: Positive Provisionen OHNE Teamleiter
```
berater_anteil = betrag × rate / 100
tl_anteil = 0
ag_anteil = betrag - berater_anteil
```

### Schritt C: Positive Provisionen MIT Teamleiter
```
berater_brutto = betrag × rate / 100

Wenn tl_override_basis = 'berater_anteil':
  tl_anteil = berater_brutto × tl_rate / 100

Wenn tl_override_basis = 'gesamt_courtage':
  tl_anteil = betrag × tl_rate / 100

berater_anteil = berater_brutto - tl_anteil
ag_anteil = betrag - berater_brutto
```

**Invariante**: `berater_anteil + tl_anteil + ag_anteil == betrag` (immer)

---

## Auto-Matching (5+2 Schritte)

Das Auto-Matching laeuft als eine Transaktion:

1. **VSNR-Match**: `pm_commissions.vsnr_normalized = pm_contracts.vsnr_normalized`
   → Setzt `berater_id`, `contract_id`, `match_status='auto_matched'`

1.5 **Xempus-Consultation-Match** (v3.3.0):
   → `pm_commissions.vsnr_normalized = xempus_consultations.versicherungsscheinnummer`
   → Setzt `xempus_consultation_id`, Confidence 0.85

2. **Alt-VSNR-Match**: Fallback auf `contracts.vsnr_alt_normalized`

2.5 **Berater via Xempus** (v3.3.0):
   → Vertraege ohne berater_id bekommen Berater aus Xempus-Beratung

3. **Berater via VU Vermittler-Mapping**:
   → `pm_vermittler_mapping` ordnet VU-Vermittlernamen Beratern zu

4. **batchRecalculateSplits()**: 3 Batch-UPDATEs (siehe Split-Engine)

5. **Vertragsstatus-Update**: Vertraege mit positiver Provision → `status='provision_erhalten'`

Performance: ~11 Sekunden fuer 15.010 Provisionszeilen

---

## Multi-Level-Matching (manuell)

`GET /pm/match-suggestions` liefert gewichtete Vorschlaege:

| Score | Typ | Beschreibung |
|-------|-----|--------------|
| 100 | VSNR exakt | Normalisierte VSNR stimmt ueberein |
| 90 | Alt-VSNR | Match ueber alternative VSNR |
| 70 | Name exakt | Versicherungsnehmer-Name normalisiert identisch |
| 40 | Name partiell | Teiluebereinstimmung im Namen |

Unterstuetzt Forward (Commission → Contract) und Reverse (Contract → Commission).

---

## Normalisierung

### VSNR (Versicherungsscheinnummer)
```
normalizeVsnr("00-123.045") → "12345"
```
- Nicht-Ziffern entfernen
- ALLE Nullen entfernen (nicht nur fuehrende)
- Scientific Notation (z.B. aus Excel "1.23E+05") → Integer

### Vermittlername
```
normalizeVermittlerName("Müller-Schmidt, Hans") → "muellerschmidthans"
```
- Lowercase, Umlaute → ae/oe/ue/ss, Sonderzeichen entfernen

### Versicherungsnehmer (VN)
```
normalizeForDb("Müller GmbH (Niederlassung Berlin)") → "mueller gmbh niederlassung berlin"
```
- Lowercase, Umlaute → ae/oe/ue/ss, Klammern aufloesen, Sonderzeichen entfernen

---

## VU-Import (Excel-Parser)

### Unterstuetzte Formate
| VU | Header-Signatur (Auto-Erkennung) | VN-Spalte | Betrag-Spalte |
|----|----------------------------------|-----------|---------------|
| **Allianz** | "Geschaeftspartner" in Spalte A | AE | AK |
| **SwissLife** | "Vers-Nr" in Spalte A | U | AB |
| **VB (Versicherungsbuero)** | "Vermittler" in Spalte B | C | M |

### Xempus-Import
- 5 Excel-Sheets: ArbG, ArbG-Tarife, ArbG-Zuschüsse, ArbN, Beratungen
- Spalten-Mappings fuer jeden Sheet-Typ
- Xempus-IDs (AM/AN/AO) fuer Vertragserkennung
- Status-Handling: "Nicht gewünscht" → Skip, "Beantragt" → beantragt, "Unberaten" → offen

---

## Abrechnungen (Status-Workflow)

```
berechnet → geprueft → freigegeben → ausgezahlt
```

- **berechnet**: Automatisch generiert
- **geprueft**: GF hat geprueft
- **freigegeben**: Zur Auszahlung freigegeben
- **ausgezahlt**: Geld wurde ueberwiesen

Revisionierung: Bei erneuter Generierung wird automatisch eine neue Revision erstellt.

---

## Shared Widgets (widgets.py)

| Widget | Zweck |
|--------|-------|
| `PillBadgeDelegate` | Farbige Status-Badges in Tabellen (Match-Status, Rolle, Art) |
| `DonutChartWidget` | Kreis-Diagramm fuer Zuordnungsquote |
| `FilterChipBar` | Horizontale Filter-Chips zum Filtern von Tabellen |
| `SectionHeader` | Ueberschrift mit optionaler Action-Button |
| `ThreeDotMenuDelegate` | Drei-Punkte-Menue in Tabellen-Zeilen |
| `KpiCard` | KPI-Kachel mit Hauptwert, Subline, Tooltip, Extra-Labels |
| `PaginationBar` | Seiten-Navigation fuer server-seitige Pagination |
| `StatementCard` | Abrechnungs-Karte mit Berater, Betraegen, Status |
| `ActivityFeedWidget` | Audit-Log als vertikaler Feed |

---

## Klaerfall-Typen

| Typ | Beschreibung | Loesung |
|-----|--------------|---------|
| `no_contract` | Provision hat keinen passenden Vertrag | Manuelles Matching via MatchContractDialog |
| `unknown_vermittler` | VU-Vermittlername unbekannt | Vermittler-Mapping erstellen |
| `no_model` | Berater hat kein Provisionsmodell | Modell zuweisen |
| `no_split` | Split-Berechnung fehlt | Splits neu berechnen |

---

## API-Endpunkte (Provision, 32 Routes)

Siehe `04_API_ENDPOINTS_UND_DATENBANK.md` fuer die vollstaendige Liste.

Wichtigste:
- `POST /pm/import/vu-liste` → VU-Provisionsliste importieren
- `POST /pm/import/match` → Auto-Matching ausloesen
- `GET /pm/clearance` → Klaerfall-Counts
- `GET /pm/match-suggestions` → Multi-Level-Matching
- `PUT /pm/assign` → Transaktionale Zuordnung
- `POST /pm/xempus/import` → Xempus RAW Ingest
- `POST /pm/reset` → Gefahrenzone (nur provision_manage)
