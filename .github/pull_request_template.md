## Beschreibung

<!-- Was wurde geaendert und warum? -->

## Aenderungstyp

- [ ] Feature (neues Feature)
- [ ] Fix (Bugfix)
- [ ] Refactoring (kein neues Feature, kein Bugfix)
- [ ] Dokumentation
- [ ] Build / CI
- [ ] Sonstiges

## Checkliste

- [ ] VERSION-Datei erhoeht (SemVer: MAJOR.MINOR.PATCH)
- [ ] Smoke Tests bestanden (`python src/tests/run_smoke_tests.py`)
- [ ] Betroffene Dokumentation in `docs/00_CORE/` aktualisiert
- [ ] UI-Texte in `src/i18n/de.py` (keine Hardcoded Strings)
- [ ] Keine Secrets im Code
- [ ] Keine `QMessageBox.information/warning/critical` (ToastManager verwenden)

## Release Gates (nur bei stable/beta)

- [ ] DB-Migrationen erstellt und in `setup/` abgelegt
- [ ] Split-Invariante geprueft (Provisionsmodul)
- [ ] Matching-Konsistenz geprueft

## Risikoanalyse

<!-- Was koennte schief gehen? Welche Bereiche sind betroffen? -->

## Rollback-Strategie

<!-- Wie kann diese Aenderung zurueckgerollt werden? -->

## Screenshots (optional)

<!-- UI-Aenderungen bitte mit Screenshots dokumentieren -->
