# Release-Strategie

> Stand: 25.02.2026 | Version: 3.4.1

## Versionierung (SemVer)

`VERSION`-Datei im Root ist **Single Source of Truth**.

| Aenderungstyp | Beispiel |
|---------------|----------|
| PATCH (x.x.+1) | Bugfix, kleine Korrekturen |
| MINOR (x.+1.0) | Neues Feature, UI-Erweiterung, API-Erweiterung |
| MAJOR (+1.0.0) | Breaking Change, DB-Strukturaenderung, Matching-Logik-Aenderung |

### Pre-Release-Suffixe

- `stable` Channel: Kein Suffix (z.B. `2.3.0`)
- `beta` Channel: `-beta` Suffix erlaubt (z.B. `2.3.0-beta1`)
- `dev` Channel: Suffix **Pflicht** (z.B. `2.4.0-dev3`)

## Release-Channels

| Channel | Branch | Zielgruppe | Stabilitaet |
|---------|--------|------------|-------------|
| `stable` | `main` | Alle Berater | 100% produktionsreif |
| `beta` | `beta` | Ausgewaehlte Tester, GF | Feature-komplett, getestet |
| `dev` | `dev` | Nur Entwickler | Experimentell, keine Garantie |

### Channel-Zuweisung (Server-seitig)

Jeder User hat ein Feld `update_channel` in der `users`-Tabelle.
- Default: `stable`
- Konfigurierbar im Admin-Panel pro User
- Der Client liest den Channel bei Login/Verify und prueft Updates im zugewiesenen Channel

## Release Gate Engine

### Lebenszyklus

```
Upload --> pending --> [Validieren] --> validated --> [Aktivieren] --> active
                   --> blocked -------> pending (erneut validieren)
                                        active --> mandatory
                                        active --> deprecated
                                        active --> withdrawn
```

### Gate-Checks (Server-seitig)

| # | Gate | Beschreibung | Pflicht fuer |
|---|------|-------------|-------------|
| 1 | Schema-Version | Alle erwarteten DB-Migrationen angewendet? | Alle (wenn `required_schema` gesetzt) |
| 2 | Split-Invariante | `berater_anteil + tl_anteil + ag_anteil == betrag` | stable, beta |
| 3 | Matching-Konsistenz | Keine verwaisten Matchings | stable, beta |
| 4 | Smoke-Test-Report | Tests bestanden, Version korrekt, Report aktuell | stable (Pflicht), beta/dev (optional) |
| 5 | Versions-Konsistenz | SemVer korrekt fuer Channel | Alle |
| 6 | Schema-Struktur | 6 kritische Tabellen, 12 Indexes, 10 Spalten vorhanden | stable, beta |
| 7 | Daten-Integritaet | Keine orphaned FKs, keine fehlenden Berater-Referenzen | stable, beta |

### Invarianten-Klassifikation

**FATAL (Blocker):**
- Split-Verletzung: `berater_anteil + tl_anteil + ag_anteil != betrag` bei gematchten Provisionen
- Orphaned Match: `match_status = 'auto_matched' AND contract_id IS NULL`
- Orphaned FK: `contract_id` oder `berater_id` zeigt auf nicht-existierenden Datensatz

**WARNING (im Report, kein Blocker):**
- Doppelte `row_hash` Werte (kann bei Re-Importen vorkommen)
- Negative Betraege (kann bei Stornos legitim sein)

### Schema-Hash (Audit-Trail)

Gate 6 generiert einen SHA256-Hash ueber alle `SHOW CREATE TABLE` Statements der kritischen Tabellen. Dieser Hash wird im `gate_report` gespeichert, blockiert aber NICHT (verhindert false positives bei neuen Migrationen). Blocker sind NUR fehlende Tabellen, Indexes oder Spalten.

### Endpoints

| Methode | Endpoint | Beschreibung |
|---------|----------|-------------|
| `POST` | `/admin/releases` | Upload (Status = `pending`) |
| `POST` | `/admin/releases/{id}/validate` | Gate-Validierung ausfuehren (7 Gates) |
| `POST` | `/admin/releases/{id}/withdraw` | Release zurueckziehen mit Auto-Fallback |
| `PUT` | `/admin/releases/{id}` | Status aendern (nur erlaubte Uebergaenge) |
| `GET` | `/admin/releases/schema-snapshot` | DB-Schema-Hash + Tabellen-Inventar |

## Release-Flow (End-to-End)

```
 1. Feature in dev entwickeln
 2. PR: dev -> beta (Beta-Test)
 3. Beta-Tester erhalten Update automatisch (channel=beta)
 4. Nach Validierung: PR: beta -> main
 5. VERSION-Datei anpassen (z.B. 2.3.0)
 6. Git Tag: git tag v2.3.0
 7. Smoke Tests ausfuehren: python src/tests/run_smoke_tests.py --json-report
 8. version_info.txt aktualisieren: python scripts/update_version_info.py
 9. Installer bauen (liest VERSION automatisch aus Datei)
10. Upload ueber Admin-Panel (Status = 'pending')
11. Validieren ueber Admin-Panel oder API
12. Wenn alle Gates bestanden: Aktivieren
13. Stable-User erhalten Update automatisch
```

## Rollback-Strategie

1. **Auto-Withdraw**: `POST /admin/releases/{id}/withdraw` -- setzt Release auf `withdrawn` und reaktiviert automatisch das vorherige Release im gleichen Channel
2. **Manueller Withdraw**: Im Admin-Panel ueber den "Zurueckziehen"-Button (mit Bestaetigungs-Dialog)
3. **Git-Rollback**: Revert-Commit, neues Release erstellen
4. **DB-Rollback**: Migrationen sind idempotent, manuelle Rollback-Queries in `docs/01_DEVELOPMENT/MIGRATIONS.md`

## Build-Automatisierung

| Tool | Datei | Liest VERSION aus |
|------|-------|-------------------|
| Inno Setup | `installer.iss` | `VERSION` (Preprocessor) |
| PyInstaller | `version_info.txt` | `scripts/update_version_info.py` |
| Smoke Tests | `src/tests/run_smoke_tests.py` | `VERSION` (bei `--json-report`) |
| Provision Tests | `src/tests/test_provision.py` | `VERSION` (bei `--json-report`) |
| Installer-Verifikation | `scripts/verify_installer.py` | `VERSION` + SHA256 + Dateiname |

## CI-Pipeline (GitHub Actions)

`.github/workflows/smoke-tests.yml` laeuft bei PR/Push auf `main`/`beta`:

1. Smoke Tests (8 Basis-Tests + 3 erweiterte Gruppen)
2. Provision Unit Tests (23 Normalisierungs-Tests)
3. VERSION-Konsistenz-Check
4. Installer-Verifikation (wenn vorhanden, optional)
5. Test-Reports als Artifacts hochladen (30 Tage)

**Hybrid-Ansatz**: CI generiert Reports, Validierung/Aktivierung bleibt manuell im Admin-Panel. Keine API-Credentials in GitHub Secrets.

## Health-Check

`GET /api/status` gibt zurueck:

```json
{
  "status": "ok",
  "timestamp": "2026-02-25T08:30:00+01:00",
  "schema_version": "035_release_gate_status",
  "pending_migrations": 0
}
```
