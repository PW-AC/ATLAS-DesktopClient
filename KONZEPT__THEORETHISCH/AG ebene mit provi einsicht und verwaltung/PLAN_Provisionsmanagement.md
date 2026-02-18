# ACENCIA ATLAS – Provisionsmanagement-Modul
## Technischer Umsetzungsplan (Phase 1)

**Stand**: 13. Februar 2026
**Grundlage**: Geklärtes Provisionsmodell aus Konzeptionierung + GF-Gespräch

---

## 1. Geklärtes Geschäftsmodell

### Rahmendaten

| Parameter | Wert |
|-----------|------|
| Mitarbeiter gesamt | ~13 |
| Consulter | 3–5 |
| Teamleiter (TL) | 1 |
| Provisionsmodelle | 1–5 (nur unterschiedliche Prozentsätze) |
| Gemeinschaftsgeschäft / Splits | Nein |
| Staffelmodelle | Ja, aber Phase 2 |
| GF-Override | Nein – GF = AG (behält was übrig bleibt) |

### Provisionsfluss (verbindlich)

```
VU zahlt Courtage an AG (Betrag X)
    │
    ├── VSNR → Vertrag identifizieren → Berater identifizieren
    │
    ├── Berater-Anteil brutto: Y% von X
    │      │
    │      ├── Berater hat TL?
    │      │     → JA: TL-Override wird vom Berater-Anteil ABGEZOGEN
    │      │           Zwei konfigurierbare Varianten:
    │      │
    │      │           Variante A: TL bekommt Z% vom BERATER-ANTEIL
    │      │                       TL = Z% × (Y% × X)
    │      │
    │      │           Variante B: TL bekommt Z% von der GESAMT-COURTAGE
    │      │                       TL = Z% × X
    │      │
    │      │           Berater netto = Berater brutto - TL-Anteil
    │      │
    │      │     → NEIN: Berater bekommt vollen Berater-Anteil (Y% * X)
    │      │
    │      └── AG-Anteil: X - (Y% * X) = immer fix! (unberührt vom TL-Override)
    │
    └── Bei Rückbelastung: gleiche Logik, negativer Betrag
```

### Rechenbeispiel Variante A (TL-Override vom Berater-Anteil)

```
VU-Courtage:         1.000,00 €
Berater-Satz (Y%):   40%
TL-Override (Z%):     10% vom Berater-Anteil

Berater-Anteil brutto:   400,00 €
TL-Override:              40,00 € (10% von 400 €)
Berater netto:           360,00 € (400 € - 40 €)
AG behält:               600,00 € (immer: 1000 € - 400 €)

Kontrollsumme: 360 + 40 + 600 = 1.000 ✓
```

### Rechenbeispiel Variante B (TL-Override von Gesamt-Courtage)

```
VU-Courtage:         1.000,00 €
Berater-Satz (Y%):   40%
TL-Override (Z%):     10% von Gesamt-Courtage

Berater-Anteil brutto:   400,00 €
TL-Override:             100,00 € (10% von 1.000 €)
Berater netto:           300,00 € (400 € - 100 €)
AG behält:               600,00 € (immer: 1000 € - 400 €)

Kontrollsumme: 300 + 100 + 600 = 1.000 ✓
```

**Konfiguration**: Die Variante wird pro Teamleiter in `pm_employees.tl_override_basis` festgelegt (`berater_anteil` oder `gesamt_courtage`). Standard ist Variante A.

**Sicherheitsregel**: Der TL-Anteil darf nie größer sein als der Berater-Anteil brutto (Cap).

---

## 2. Datenquellen

### 2a. VU-Provisionslisten (bereits vorhanden)

- **Quelle**: Courtage-Box im Dokumentenarchiv (BiPRO 300xxx + manuelle Uploads)
- **Format**: Excel/CSV (15.000+ Zeilen, 42 Spalten)
- **Wichtige Spalten**:
  - `Neue / zuletzt gültige VSNR` → Primärschlüssel für Matching
  - `Provisions-Betrag` → Betrag X
  - `Art` → AP / BP / Rückbelastung
  - `Auszahlungs-datum`
  - `Versicherungsnehmer`
  - `Vermittler` / `Vermittler2`
  - `Ratenanzahl` / `Raten-Nummer`
  - `Provisions-basissumme`

### 2b. Xempus Advisor Export (manueller Import)

- **Quelle**: Manueller Excel-Export aus Xempus Advisor
- **Format**: Excel (.xlsx), mehrere Sheets
- **Relevantes Sheet**: „Beratungen" (17.000+ Zeilen, 62 Spalten)
- **Wichtige Spalten**:
  - `Versicherungsscheinnummer` → VSNR für Matching
  - `Status` → Pipeline-Status
  - `Berater` → Mitarbeiter-Zuordnung
  - `Versicherer`
  - `Gesamtbeitrag`
  - `Beginn`
  - `Datum Entscheidung`
  - `Typ` / `Durchführungsweg` / `Tarif`

---

## 3. Datenmodell (MySQL)

### 3a. Tabelle `pm_employees` (Mitarbeiter/Berater)

```sql
CREATE TABLE pm_employees (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    -- Verknüpfung mit bestehendem ATLAS User-System
    user_id         INT NULL,                          -- FK → users.id (optional)
    
    -- Stammdaten
    name            VARCHAR(200) NOT NULL,
    role            ENUM('consulter', 'teamleiter', 'backoffice') NOT NULL DEFAULT 'consulter',
    
    -- Provisionssatz
    commission_rate DECIMAL(5,2) NOT NULL DEFAULT 0,   -- Y% (z.B. 40.00)
    
    -- TL-Override (nur relevant wenn role = 'teamleiter')
    tl_override_rate DECIMAL(5,2) NOT NULL DEFAULT 0,  -- Z% (z.B. 10.00)
    
    -- Team-Zuordnung
    teamleiter_id   INT NULL,                          -- FK → pm_employees.id
    
    -- Verwaltung
    is_active       TINYINT(1) NOT NULL DEFAULT 1,
    notes           TEXT NULL,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (teamleiter_id) REFERENCES pm_employees(id) ON DELETE SET NULL,
    INDEX idx_role (role),
    INDEX idx_teamleiter (teamleiter_id),
    INDEX idx_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

**Hinweis**: `commission_rate` ist der Prozentsatz, den der Berater von der VU-Courtage bekommt. `tl_override_rate` ist der Prozentsatz, den der TL vom Berater-Anteil seiner Teammitglieder bekommt.

### 3b. Tabelle `pm_contracts` (Zentrale Vertragstabelle)

```sql
CREATE TABLE pm_contracts (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    
    -- Identifikation
    vsnr            VARCHAR(50) NOT NULL,              -- Versicherungsscheinnummer
    vsnr_alt        VARCHAR(50) NULL,                  -- Alte VSNR (bei Umnummerierung)
    
    -- Vertragsdaten
    versicherer     VARCHAR(200) NULL,
    versicherungsnehmer VARCHAR(300) NULL,
    sparte          VARCHAR(100) NULL,                 -- Leben/Sach/Kranken/etc.
    tarif           VARCHAR(200) NULL,
    beitrag         DECIMAL(12,2) NULL,                -- Gesamtbeitrag
    beginn          DATE NULL,
    
    -- Zuordnung
    berater_id      INT NULL,                          -- FK → pm_employees.id
    
    -- Status
    status          ENUM(
                        'angebot',           -- Aus Xempus: noch kein Abschluss
                        'offen',             -- Beratung läuft
                        'abgeschlossen',     -- Vertrag besteht
                        'provision_erhalten', -- Mindestens 1 Provision eingegangen
                        'provision_fehlt',   -- Abgeschlossen aber keine Provision
                        'storniert',         -- Vertrag storniert
                        'rueckbelastung'     -- Rückbelastung erhalten
                    ) NOT NULL DEFAULT 'offen',
    
    -- Import-Metadaten
    source          ENUM('xempus', 'vu_liste', 'manuell') NOT NULL DEFAULT 'manuell',
    xempus_id       VARCHAR(100) NULL,                 -- ID aus Xempus-Export
    import_batch_id INT NULL,                          -- FK → pm_import_batches.id
    
    -- Verwaltung
    notes           TEXT NULL,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (berater_id) REFERENCES pm_employees(id) ON DELETE SET NULL,
    UNIQUE INDEX idx_vsnr (vsnr),
    INDEX idx_vsnr_alt (vsnr_alt),
    INDEX idx_berater (berater_id),
    INDEX idx_status (status),
    INDEX idx_versicherer (versicherer),
    INDEX idx_source (source)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### 3c. Tabelle `pm_commissions` (Provisionseingänge/-ausgänge)

```sql
CREATE TABLE pm_commissions (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    
    -- Verknüpfung
    contract_id     INT NULL,                          -- FK → pm_contracts.id (NULL wenn kein Match)
    vsnr            VARCHAR(50) NOT NULL,              -- Original-VSNR aus VU-Liste
    
    -- Provisionsdaten
    betrag          DECIMAL(12,2) NOT NULL,            -- Positiv = Eingang, Negativ = Rückbelastung
    art             ENUM('ap', 'bp', 'rueckbelastung', 'sonstige') NOT NULL DEFAULT 'ap',
    auszahlungsdatum DATE NULL,
    
    -- Raten-Info
    rate_nummer     INT NULL DEFAULT NULL,             -- z.B. 3 von 12
    rate_anzahl     INT NULL DEFAULT NULL,             -- z.B. 12
    
    -- VU-Daten
    versicherer     VARCHAR(200) NULL,
    provisions_basissumme DECIMAL(12,2) NULL,
    vermittler_name VARCHAR(200) NULL,                 -- Vermittler-Name aus VU-Liste
    
    -- Berechnete Aufteilung (wird bei Zuordnung befüllt)
    berater_id      INT NULL,                          -- Zugeordneter Berater
    berater_anteil  DECIMAL(12,2) NULL,                -- Berechneter Berater-Anteil
    tl_anteil       DECIMAL(12,2) NULL,                -- Berechneter TL-Anteil
    ag_anteil       DECIMAL(12,2) NULL,                -- Berechneter AG-Anteil
    
    -- Matching-Status
    match_status    ENUM(
                        'unmatched',       -- Kein Vertrag gefunden
                        'auto_matched',    -- Automatisch über VSNR
                        'manual_matched',  -- Manuell zugeordnet
                        'ignored'          -- Bewusst ignoriert
                    ) NOT NULL DEFAULT 'unmatched',
    match_confidence DECIMAL(3,2) NULL,                -- 0.00-1.00
    
    -- Import-Metadaten
    import_batch_id INT NULL,                          -- FK → pm_import_batches.id
    source_row      INT NULL,                          -- Zeilennummer im Import
    
    -- Verwaltung
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (contract_id) REFERENCES pm_contracts(id) ON DELETE SET NULL,
    FOREIGN KEY (berater_id) REFERENCES pm_employees(id) ON DELETE SET NULL,
    INDEX idx_contract (contract_id),
    INDEX idx_vsnr (vsnr),
    INDEX idx_berater (berater_id),
    INDEX idx_match (match_status),
    INDEX idx_auszahlung (auszahlungsdatum),
    INDEX idx_art (art),
    INDEX idx_batch (import_batch_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### 3d. Tabelle `pm_berater_abrechnungen` (Berechnete Auszahlungen)

```sql
CREATE TABLE pm_berater_abrechnungen (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    
    -- Zeitraum
    abrechnungsmonat DATE NOT NULL,                    -- Erster des Monats (z.B. 2026-02-01)
    
    -- Berater
    berater_id      INT NOT NULL,                      -- FK → pm_employees.id
    
    -- Berechnete Beträge
    brutto_provision DECIMAL(12,2) NOT NULL DEFAULT 0, -- Summe aller Berater-Anteile
    tl_abzug        DECIMAL(12,2) NOT NULL DEFAULT 0,  -- TL-Override-Abzug
    netto_provision  DECIMAL(12,2) NOT NULL DEFAULT 0,  -- brutto - tl_abzug
    rueckbelastungen DECIMAL(12,2) NOT NULL DEFAULT 0,  -- Summe Rückbelastungen
    auszahlung       DECIMAL(12,2) NOT NULL DEFAULT 0,  -- netto - rueckbelastungen
    
    -- TL-Einnahmen (nur für TL-Rolle)
    tl_override_summe DECIMAL(12,2) NOT NULL DEFAULT 0, -- Summe aller Overrides von Team
    
    -- Status
    status          ENUM('berechnet', 'geprueft', 'freigegeben', 'ausgezahlt') 
                    NOT NULL DEFAULT 'berechnet',
    geprueft_von    INT NULL,                          -- User-ID
    freigegeben_von INT NULL,                          -- User-ID
    freigegeben_am  DATETIME NULL,
    
    -- Verwaltung
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (berater_id) REFERENCES pm_employees(id),
    UNIQUE INDEX idx_monat_berater (abrechnungsmonat, berater_id),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### 3e. Tabelle `pm_import_batches` (Import-Historie)

```sql
CREATE TABLE pm_import_batches (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    
    -- Import-Info
    source_type     ENUM('vu_liste', 'xempus') NOT NULL,
    filename        VARCHAR(500) NOT NULL,
    file_hash       VARCHAR(64) NULL,                  -- SHA256 gegen Doppelimport
    
    -- Ergebnis
    total_rows      INT NOT NULL DEFAULT 0,
    imported_rows   INT NOT NULL DEFAULT 0,
    matched_rows    INT NOT NULL DEFAULT 0,
    error_rows      INT NOT NULL DEFAULT 0,
    
    -- Verwaltung
    imported_by     INT NOT NULL,                      -- User-ID
    notes           TEXT NULL,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_source (source_type),
    INDEX idx_hash (file_hash)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### 3f. Tabelle `pm_vermittler_mapping` (Vermittler-Name → Berater)

```sql
CREATE TABLE pm_vermittler_mapping (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    
    -- Mapping
    vermittler_name VARCHAR(200) NOT NULL,             -- Name aus VU-Liste
    berater_id      INT NOT NULL,                      -- FK → pm_employees.id
    
    -- Verwaltung
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (berater_id) REFERENCES pm_employees(id) ON DELETE CASCADE,
    UNIQUE INDEX idx_name (vermittler_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

**Zweck**: VU-Listen verwenden oft andere Namen als das interne System. Dieses Mapping übersetzt z.B. "Müller, Hans (VM-Nr: 12345)" → Berater-ID 7.

---

## 4. PHP-API-Endpoints

### 4a. Mitarbeiter-Verwaltung

| Method | Endpoint | Beschreibung | Auth |
|--------|----------|-------------|------|
| GET | `/pm/employees` | Alle Mitarbeiter (aktive) | Admin |
| GET | `/pm/employees/{id}` | Einzelner Mitarbeiter | Admin |
| POST | `/pm/employees` | Mitarbeiter anlegen | Admin |
| PUT | `/pm/employees/{id}` | Mitarbeiter bearbeiten | Admin |
| DELETE | `/pm/employees/{id}` | Mitarbeiter deaktivieren (Soft) | Admin |

### 4b. Verträge

| Method | Endpoint | Beschreibung | Auth |
|--------|----------|-------------|------|
| GET | `/pm/contracts` | Verträge listen (Filter: berater, status, versicherer) | Admin |
| GET | `/pm/contracts/{id}` | Einzelner Vertrag mit Provisionshistorie | Admin |
| PUT | `/pm/contracts/{id}` | Vertrag bearbeiten (Berater-Zuordnung, Status) | Admin |
| GET | `/pm/contracts/unmatched` | Provisionen ohne Vertragszuordnung | Admin |

### 4c. Provisionen

| Method | Endpoint | Beschreibung | Auth |
|--------|----------|-------------|------|
| GET | `/pm/commissions` | Provisionen listen (Filter: monat, berater, art, match_status) | Admin |
| PUT | `/pm/commissions/{id}/match` | Manuelles Matching (contract_id + berater_id) | Admin |
| PUT | `/pm/commissions/{id}/ignore` | Provision ignorieren | Admin |
| POST | `/pm/commissions/recalculate` | Aufteilung neu berechnen (nach Satzänderung) | Admin |

### 4d. Import

| Method | Endpoint | Beschreibung | Auth |
|--------|----------|-------------|------|
| POST | `/pm/import/vu-liste` | VU-Provisionsliste importieren (Excel/CSV) | Admin |
| POST | `/pm/import/xempus` | Xempus-Export importieren (Excel) | Admin |
| POST | `/pm/import/match` | Auto-Matching auslösen (VSNR-Abgleich) | Admin |
| GET | `/pm/import/batches` | Import-Historie | Admin |

### 4e. Dashboard / Auswertungen

| Method | Endpoint | Beschreibung | Auth |
|--------|----------|-------------|------|
| GET | `/pm/dashboard/summary` | GF-Übersicht (Monat, YTD, pro Berater) | Admin |
| GET | `/pm/dashboard/berater/{id}` | Berater-Detailansicht | Admin |
| GET | `/pm/dashboard/unmatched` | Nicht zugeordnete Provisionen | Admin |
| GET | `/pm/dashboard/missing` | Abschlüsse ohne Provision | Admin |
| GET | `/pm/dashboard/storno` | Stornoquote + Rückbelastungen | Admin |
| GET | `/pm/abrechnungen` | Monatliche Abrechnungen | Admin |
| POST | `/pm/abrechnungen/generate` | Monatsabrechnung generieren | Admin |

### 4f. Vermittler-Mapping

| Method | Endpoint | Beschreibung | Auth |
|--------|----------|-------------|------|
| GET | `/pm/mappings` | Alle Vermittler-Mappings | Admin |
| POST | `/pm/mappings` | Neues Mapping anlegen | Admin |
| DELETE | `/pm/mappings/{id}` | Mapping löschen | Admin |

---

## 5. Python-Module (Desktop-App)

### 5a. API Client

```
src/api/provision.py
    ├── ProvisionAPI (Basis-Client)
    │   ├── Employees CRUD
    │   ├── Contracts CRUD
    │   ├── Commissions CRUD
    │   ├── Import (upload_vu_liste, upload_xempus, trigger_matching)
    │   ├── Dashboard (get_summary, get_berater_detail, get_unmatched, ...)
    │   ├── Abrechnungen (generate, list)
    │   └── Mappings CRUD
```

### 5b. Import-Service

```
src/services/provision_import.py
    ├── VUListeParser
    │   ├── parse_excel(filepath) → List[RawCommission]
    │   ├── detect_columns(df) → ColumnMapping
    │   └── validate_rows(rows) → ValidationResult
    │
    ├── XempusParser
    │   ├── parse_excel(filepath) → List[RawContract]
    │   ├── find_beratungen_sheet(workbook) → Sheet
    │   └── validate_rows(rows) → ValidationResult
    │
    └── MatchingEngine
        ├── auto_match_by_vsnr(commissions, contracts) → MatchResult
        ├── resolve_vermittler(name, mappings) → Optional[BeraterID]
        └── calculate_split(commission, berater, teamleiter) → SplitResult
```

### 5c. UI-Module

```
src/ui/provision/
    ├── provision_hub.py           -- Hauptnavigation (wie Admin-View)
    │   ├── Dashboard-Panel
    │   ├── Mitarbeiter-Panel
    │   ├── Verträge-Panel
    │   ├── Provisionen-Panel
    │   ├── Import-Panel
    │   └── Abrechnungen-Panel
    │
    ├── provision_dashboard.py     -- GF-Dashboard
    │   ├── SummaryCards (Monat, YTD, Storno, Pipeline)
    │   ├── BeraterTable (Ranking)
    │   ├── UnmatchedAlert (offene Zuordnungen)
    │   └── MissingAlert (Abschlüsse ohne Provision)
    │
    ├── provision_employees.py     -- Mitarbeiterverwaltung
    │   ├── EmployeeTable
    │   ├── EmployeeDialog (Anlegen/Bearbeiten)
    │   └── TeamView (Hierarchie-Darstellung)
    │
    ├── provision_import.py        -- Import-Wizard
    │   ├── Step 1: Datei auswählen + Typ (VU/Xempus)
    │   ├── Step 2: Spalten-Mapping prüfen/korrigieren
    │   ├── Step 3: Vorschau (erste 20 Zeilen)
    │   ├── Step 4: Import + Matching-Ergebnis
    │   └── Step 5: Unmatched-Übersicht mit manuellem Matching
    │
    ├── provision_contracts.py     -- Vertragsübersicht
    │   ├── ContractTable (Filter: Status, Berater, VU)
    │   ├── ContractDetail (Provisionshistorie pro Vertrag)
    │   └── StatusMatrix (Xempus-Status vs. Provisions-Status)
    │
    └── provision_abrechnungen.py  -- Monatsabrechnungen
        ├── AbrechnungTable (Monat, Berater, Beträge)
        ├── AbrechnungDetail (Einzelpositionen)
        └── ExportButton (Excel/PDF)
```

---

## 6. Berechnungslogik (Provisions-Engine)

### 6a. Automatisches Matching (Kernalgorithmus)

```
Für jede importierte Provision (pm_commissions):

1. VSNR-Lookup:
   → Suche pm_contracts WHERE vsnr = commission.vsnr
   → Fallback: Suche WHERE vsnr_alt = commission.vsnr
   → Match gefunden? → match_status = 'auto_matched', confidence = 1.0

2. Vermittler-Zuordnung:
   → Suche pm_vermittler_mapping WHERE vermittler_name = commission.vermittler_name
   → Match gefunden? → berater_id setzen
   → Kein Match? → Vermittler in "unbekannte Vermittler"-Liste

3. Aufteilungsberechnung:
   → berater = pm_employees WHERE id = berater_id
   → berater_anteil = betrag * (berater.commission_rate / 100)
   → Hat berater einen TL?
      → JA: tl = pm_employees WHERE id = berater.teamleiter_id
             tl_anteil = berater_anteil * (tl.tl_override_rate / 100)
             berater_anteil = berater_anteil - tl_anteil
      → NEIN: tl_anteil = 0
   → ag_anteil = betrag - berater_anteil - tl_anteil

4. Vertragsstatus aktualisieren:
   → commission.art = 'ap' oder 'bp'?
      → contract.status = 'provision_erhalten'
   → commission.art = 'rueckbelastung'?
      → contract.status = 'rueckbelastung'
```

### 6b. Monatsabrechnung generieren

```
Für jeden aktiven Berater, für Monat M:

1. Alle pm_commissions WHERE berater_id = X 
   AND auszahlungsdatum BETWEEN M-Start AND M-Ende
   AND match_status IN ('auto_matched', 'manual_matched')

2. Summieren:
   brutto = SUM(berater_anteil) WHERE art IN ('ap', 'bp')
   tl_abzug = SUM(tl_anteil) WHERE art IN ('ap', 'bp')
   netto = brutto - tl_abzug
   rueckbelastungen = SUM(berater_anteil) WHERE art = 'rueckbelastung'  (negativ!)
   auszahlung = netto + rueckbelastungen  (Rückbelastungen sind negativ)

3. Für Teamleiter zusätzlich:
   tl_override_summe = SUM(tl_anteil) aller Team-Mitglieder im Monat

4. Insert/Update pm_berater_abrechnungen
```

---

## 7. Import-Workflow

### 7a. VU-Provisionsliste importieren

```
Schritt 1: Admin wählt Excel/CSV-Datei
Schritt 2: System erkennt Spalten automatisch (Heuristik):
           - "VSNR" / "Versicherungsschein" → vsnr
           - "Betrag" / "Provision" → betrag
           - "Datum" / "Auszahlung" → auszahlungsdatum
           - "Art" → art
           - "Vermittler" → vermittler_name
Schritt 3: Admin prüft/korrigiert Spalten-Mapping
Schritt 4: Daten werden in pm_commissions geschrieben
Schritt 5: Auto-Matching läuft (VSNR → Vertrag, Vermittler → Berater)
Schritt 6: Ergebnis-Übersicht:
           - X von Y Provisionen zugeordnet
           - Z Provisionen ohne Vertrag
           - W unbekannte Vermittler
```

### 7b. Xempus-Export importieren

```
Schritt 1: Admin wählt .xlsx-Datei
Schritt 2: System findet Sheet "Beratungen" (oder Admin wählt)
Schritt 3: Spalten-Mapping:
           - "Versicherungsscheinnummer" → vsnr
           - "Status" → status
           - "Berater" → berater (→ pm_vermittler_mapping)
           - "Versicherer" → versicherer
           - "Gesamtbeitrag" → beitrag
           - "Beginn" → beginn
Schritt 4: Daten werden in pm_contracts geschrieben
           - Existiert VSNR bereits? → Update statt Insert
           - Neuer Status überschreibt alten (mit Historisierung)
Schritt 5: Re-Matching aller unmatched Provisionen gegen neue Verträge
Schritt 6: Ergebnis-Übersicht:
           - X neue Verträge, Y aktualisiert
           - Z Provisionen jetzt zugeordnet
```

### 7c. Duplikat-Schutz

- `pm_import_batches.file_hash` (SHA256) verhindert doppelten Import derselben Datei
- VSNR in `pm_contracts` ist UNIQUE → bei Re-Import Update statt Duplikat
- Admin kann Import-Batch rückgängig machen (Soft-Delete aller zugehörigen Rows)

---

## 8. GF-Dashboard (UI-Konzept)

### 8a. Übersicht (Startseite)

```
┌──────────────────────────────────────────────────────────┐
│  PROVISIONSMANAGEMENT           Februar 2026       [▼]   │
├──────────┬──────────┬──────────┬──────────┬─────────────┤
│ Provision│ Provision│  Offene  │  Storno- │  Pipeline   │
│  Monat   │   YTD    │ Zuordnun.│  quote   │  (offen)    │
│ 12.450 € │ 98.200 € │    7     │   3,2%   │  45.000 €   │
├──────────┴──────────┴──────────┴──────────┴─────────────┤
│                                                          │
│  BERATER-ÜBERSICHT                                       │
│ ┌────────────┬──────────┬─────────┬────────┬──────────┐ │
│ │ Berater    │ Brutto   │TL-Abzug │ Netto  │ Storno   │ │
│ ├────────────┼──────────┼─────────┼────────┼──────────┤ │
│ │ Müller, H. │ 4.200 €  │  420 €  │3.780 € │   0 €    │ │
│ │ Schmidt, A.│ 3.100 €  │  310 €  │2.790 € │ -200 €   │ │
│ │ Weber, K.  │ 2.800 €  │  280 €  │2.520 € │   0 €    │ │
│ │ ...        │          │         │        │          │ │
│ └────────────┴──────────┴─────────┴────────┴──────────┘ │
│                                                          │
│  ⚠ HANDLUNGSBEDARF                                       │
│  • 7 Provisionen ohne Vertragszuordnung                  │
│  • 3 Abschlüsse seit >60 Tagen ohne Provision            │
│  • 2 unbekannte Vermittler in letztem Import             │
└──────────────────────────────────────────────────────────┘
```

### 8b. Berater-Detailansicht

```
┌──────────────────────────────────────────────────────────┐
│  BERATER: Hans Müller              Consulter    [40%]    │
│  Team: Teamleiter Schmidt (Override: 10%)                │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  Provision Monat: 3.780 € netto  │  YTD: 28.500 €       │
│  Verträge: 45 aktiv              │  Pipeline: 12 offen   │
│                                                          │
│  LETZTE PROVISIONSEINGÄNGE                               │
│ ┌──────────┬─────────────┬────────┬─────┬───────┬─────┐ │
│ │ Datum    │ VSNR        │ VU     │ Art │Betrag │Anteil│ │
│ ├──────────┼─────────────┼────────┼─────┼───────┼─────┤ │
│ │05.02.2026│VS-123456    │Allianz │ AP  │1.000€ │360€  │ │
│ │03.02.2026│VS-789012    │Degenia │ BP  │  200€ │ 72€  │ │
│ │01.02.2026│VS-345678    │VEMA    │ AP  │  500€ │180€  │ │
│ └──────────┴─────────────┴────────┴─────┴───────┴─────┘ │
└──────────────────────────────────────────────────────────┘
```

---

## 9. Integration in ATLAS

### 9a. Navigation

- Neuer Eintrag in der linken Sidebar: **"Provision"** (nach Archiv, vor GDV)
- Icon: Geld-Symbol (€) oder Chart-Symbol
- Sichtbar nur für: `account_type = 'admin'` (= GF-Ebene)

### 9b. Neue Permission

- `provision_manage` → Zugriff auf Provisionsmanagement
- `provision_view` → Nur Lese-Zugriff (z.B. für TL eigenes Team)

### 9c. Bestehende Systeme nutzen

| ATLAS-Feature | Nutzung im Provi-Modul |
|---------------|------------------------|
| Courtage-Box | VU-Listen liegen bereits dort → Import-Button |
| Activity-Log | Alle Provi-Aktionen loggen |
| User-System | Admin = GF, Berater = eigene Daten sehen |
| Toast-System | Import-Ergebnisse, Matching-Alerts |
| i18n/de.py | Alle Texte zentral |

### 9d. Courtage-Box-Integration

Die VU-Provisionslisten in der Courtage-Box könnten direkt als Import-Quelle dienen:
- Button "Als Provisionsliste importieren" im Kontextmenü der Courtage-Box
- System erkennt bereits heruntergeladene PDFs/Excel-Dateien
- Spart manuellen Upload-Schritt

---

## 10. Phasen-Roadmap

### Phase 1: Grundgerüst (MVP)

**Ziel**: Provisionen sichtbar machen, Berater-Zuordnung, GF-Übersicht

| # | Aufgabe | Aufwand |
|---|---------|---------|
| 1 | DB-Migration (6 Tabellen) | 1 Tag |
| 2 | PHP-API: Employees CRUD | 1 Tag |
| 3 | PHP-API: Import (VU-Liste + Xempus) | 2–3 Tage |
| 4 | PHP-API: Auto-Matching + Berechnung | 2 Tage |
| 5 | PHP-API: Dashboard-Endpoints | 1 Tag |
| 6 | Python: API-Client `provision.py` | 1 Tag |
| 7 | Python: Import-Service (Parser) | 2–3 Tage |
| 8 | Python: UI – Mitarbeiter-Panel | 1 Tag |
| 9 | Python: UI – Import-Wizard | 2–3 Tage |
| 10 | Python: UI – Dashboard | 2 Tage |
| 11 | Python: UI – Provisionsübersicht | 1–2 Tage |
| 12 | Integration in MainHub (Sidebar) | 0,5 Tage |
| **Gesamt Phase 1** | | **~15–20 Tage** |

### Phase 2: Erweiterungen

- Staffelmodelle (ab Umsatz X mehr %)
- Monatsabrechnungen generieren + PDF-Export
- Forecast (Pipeline-Wert * Abschlusswahrscheinlichkeit)
- Xempus automatischer Re-Import (Scheduler)
- Courtage-Box-Integration (direkter Import)
- Berater-Selbstansicht (eigene Provisionen sehen)

### Phase 3: Intelligence (→ Verbindung mit Insight Engine)

- Courtage-Trend-Analyse pro VU
- Anomalie-Erkennung (plötzlicher Rückgang)
- Storno-Frühwarnung
- Weekly Intelligence Report (Provi-Kapitel)

---

## 11. Risiken und Mitigationen

| Risiko | Mitigation |
|--------|-----------|
| VSNR-Format unterscheidet sich zwischen Xempus und VU | VSNR-Normalisierung (Leerzeichen, Bindestriche, führende Nullen entfernen) |
| VU-Listen haben unterschiedliche Spaltenformate | Spalten-Mapping im Import-Wizard (einmal konfigurieren, merken) |
| Vermittler-Name in VU-Liste ≠ Berater-Name in System | `pm_vermittler_mapping`-Tabelle (einmal pflegen) |
| Ratenprovisionen werden als Gesamtprovision gezählt | `rate_nummer` + `rate_anzahl` Felder, Berechnung berücksichtigt Raten |
| Doppelimport gleicher Liste | SHA256-Hash pro Import-Batch, Warnung bei bekanntem Hash |
| Berater-Wechsel bei bestehendem Vertrag | Historisierung: alter Berater bleibt in pm_commissions, neuer in pm_contracts |

---

## 12. Dateien (geplante Struktur)

### Server (PHP)

```
BiPro-Webspace Spiegelung Live/
    api/
        provision.php              -- Hauptrouter für alle PM-Endpoints
        lib/provision_engine.php   -- Berechnungslogik
    setup/
        0XX_provision_tables.php   -- DB-Migration
```

### Desktop (Python)

```
src/
    api/
        provision.py               -- API-Client
    services/
        provision_import.py        -- VU-Liste + Xempus Parser
        provision_engine.py        -- Lokale Berechnungslogik (optional)
    ui/
        provision/
            provision_hub.py       -- Hauptnavigation
            provision_dashboard.py -- GF-Dashboard
            provision_employees.py -- Mitarbeiterverwaltung
            provision_import.py    -- Import-Wizard
            provision_contracts.py -- Vertragsübersicht
            provision_abrechnungen.py -- Monatsabrechnungen
    i18n/
        de.py                      -- ~80-100 neue PROVISION_* Keys
```

---

## 13. Entscheidungen (offen, vor Implementierung zu klären)

| # | Frage | Optionen |
|---|-------|----------|
| 1 | Import auf Client oder Server? | **Server empfohlen**: Excel-Datei hochladen, PHP parst → weniger Abhängigkeiten |
| 2 | Berechnung auf Client oder Server? | **Server**: Single Source of Truth, keine Inkonsistenzen |
| 3 | Eigene Sidebar oder Admin-Unterbereich? | **Eigene Sidebar** empfohlen: Provisionsmanagement ist eigenständig genug |
| 4 | Wer sieht was? | Admin (GF) = alles, TL = eigenes Team, Berater = nur sich selbst |
| 5 | VU-Liste: Ganzes Excel oder nur relevante Spalten? | Ganzes Excel hochladen, Server extrahiert relevante Spalten |
