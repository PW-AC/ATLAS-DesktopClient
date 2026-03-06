# 06 – Migrations-Checkliste

## Übersicht

Schritt-für-Schritt-Anleitung für die Integration des HR-Moduls in ATLAS.
Jeder Schritt ist unabhängig testbar.

---

## Phase 1: Datenbankaufbau (PHP/MySQL)

- [ ] **1.1** MySQL-Tabellen anlegen (siehe 04_MySQL_Schema.md)
  - hr_employers
  - hr_provider_credentials
  - hr_employees
  - hr_snapshots
  - hr_snapshot_employees
  - hr_exports
  - hr_triggers
  - hr_trigger_runs
  - hr_smtp_config

- [ ] **1.2** Permissions in ATLAS-Auth-System eintragen
  - hr.view, hr.sync, hr.export, hr.triggers, hr.admin

- [ ] **1.3** PHP-Endpoints implementieren (siehe 03_Endpoint_Kontrakte.md)
  - [ ] CRUD /hr/employers
  - [ ] POST/GET /hr/employers/{id}/credentials
  - [ ] POST /hr/employees/bulk
  - [ ] GET /hr/employers/{id}/employees
  - [ ] POST/GET /hr/snapshots
  - [ ] POST/GET /hr/exports + Download
  - [ ] CRUD /hr/triggers
  - [ ] POST/GET /hr/trigger-runs
  - [ ] GET/PUT /hr/smtp-config

- [ ] **1.4** PHP-Endpoints testen (Postman/curl)

---

## Phase 2: Desktop-Module (Python)

- [ ] **2.1** Extrahierte Module in ATLAS-Projektstruktur kopieren
  - `Fusion/extrahierte_module/hr/` → `src/hr/` (oder äquivalent)

- [ ] **2.2** Dependencies prüfen/hinzufügen
  - `requests` (wahrscheinlich schon vorhanden)
  - `openpyxl` (für Excel-Export)
  - `chevron` (optional, für Mustache-Templates in Triggern)

- [ ] **2.3** API-Client implementieren (`hr/api_client.py`)
  - Bestehenden ATLAS-BaseClient verwenden
  - Alle Methoden aus 05_API_Client_Spezifikation.md

- [ ] **2.4** Provider-Klassen testen
  - HRworksProvider mit echten Test-Credentials
  - PersonioProvider mit echten Test-Credentials
  - Normalisierung validieren

- [ ] **2.5** Services integrieren
  - [ ] SyncService: Provider → API-Client → MySQL
  - [ ] DeltaService: Snapshot-Vergleich + Excel
  - [ ] ExportService: XLSX-Generierung + Upload
  - [ ] SnapshotService: Vergleich, Historie
  - [ ] TriggerService: Auswertung + E-Mail/API
  - [ ] StatsService: Standard + Langzeit

---

## Phase 3: UI (PySide6)

- [ ] **3.1** Sidebar-Eintrag "HR" hinzufügen

- [ ] **3.2** Arbeitgeber-Übersicht (View)
  - Liste aller Arbeitgeber
  - Status-Anzeige (letzte Sync, Mitarbeiterzahl)
  - Buttons: Hinzufügen, Bearbeiten, Löschen

- [ ] **3.3** Mitarbeiter-Dashboard (View)
  - Mitarbeiterliste mit Filter (Aktiv/Ehemalig/Alle)
  - Suche
  - Detail-Ansicht bei Klick

- [ ] **3.4** Export-Bereich (View)
  - "Standard-Export" Button
  - "Delta-SCS-Export" Button mit Diff-Anzeige
  - Liste vergangener Exporte mit Download

- [ ] **3.5** Snapshot-Vergleich (View)
  - Dropdown: Snapshot A, Snapshot B
  - Richtung (vorwärts/rückwärts)
  - Diff-Anzeige (added/changed/removed)

- [ ] **3.6** Trigger-Verwaltung (View, nur Master)
  - Liste aller Trigger
  - Erstellen/Bearbeiten-Formular
  - SMTP-Konfiguration
  - Ausführungsprotokoll

- [ ] **3.7** Statistiken (View)
  - Standard-Statistiken mit Charts
  - Langzeit-Statistiken mit Charts
  - TXT-Export für beide

---

## Phase 4: Datenmigration (einmalig)

- [ ] **4.1** Bestehende Arbeitgeber migrieren
  - `employers.json` → `hr_employers` + `hr_provider_credentials`

- [ ] **4.2** Bestehende Snapshots migrieren
  - `_snapshots/*.json` → `hr_snapshots` + `hr_snapshot_employees`

- [ ] **4.3** Bestehende Trigger migrieren
  - `data/triggers.json` → `hr_triggers` + `hr_smtp_config`

- [ ] **4.4** Bestehende Trigger-Logs migrieren
  - `data/trigger_log.json` → `hr_trigger_runs`

- [ ] **4.5** Bestehende Exporte migrieren (optional)
  - `exports/*.xlsx` → Webspace + `hr_exports`

---

## Phase 5: Test & Validierung

- [ ] **5.1** Mitarbeiterdaten abrufen (Personio + HRworks)
- [ ] **5.2** Delta-Export generieren und vergleichen mit HR-Hub-Ergebnis
- [ ] **5.3** Snapshot-Vergleich validieren
- [ ] **5.4** Trigger-Ausführung testen (E-Mail + API)
- [ ] **5.5** Statistiken validieren (Standard + Langzeit)
- [ ] **5.6** Export-Download vom Webspace testen
- [ ] **5.7** Permissions testen (hr.view vs. hr.admin)

---

## Phase 6: Abschluss

- [ ] **6.1** HR-Hub-Standalone abschalten
- [ ] **6.2** Dokumentation aktualisieren (README, AGENTS.md)
- [ ] **6.3** Release-Notes erstellen

---

## Abhängigkeiten zwischen Phasen

```
Phase 1 (DB + PHP) ──────┐
                          ├── Phase 2 (Desktop-Module)
                          │         │
                          │         ├── Phase 3 (UI)
                          │         │
Phase 4 (Migration) ─────┤         │
                          │         │
                          └─────────┴── Phase 5 (Test)
                                              │
                                              └── Phase 6 (Abschluss)
```

Phase 1 und Phase 2 können teilweise parallel laufen.
Phase 4 kann nach Phase 1 + Phase 2 starten.

---

## Risiken

| Risiko | Wahrscheinlichkeit | Auswirkung | Mitigation |
|--------|-------------------|-----------|-----------|
| Provider-API-Änderungen | Niedrig | Hoch | Provider-Tests vor Deployment |
| Snapshot-Format-Inkompatibilität | Mittel | Mittel | Migrationsskript validieren |
| SMTP von Desktop geblockt | Mittel | Mittel | Fallback: API-Proxy über PHP |
| Große Snapshots → langsame API | Niedrig | Mittel | Pagination, Kompression |

---

**Erstellt:** 19.02.2026
