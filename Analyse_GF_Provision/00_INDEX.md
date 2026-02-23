# Analyse: GF/Provisions-Ebene (ACENCIA ATLAS)

**Datum:** 23. Februar 2026  
**Scope:** Vollständige Analyse der Geschäftsführer-/Provisions-Management-Ebene  
**Status:** Abgeschlossen  

---

## Inhaltsverzeichnis

| # | Dokument | Inhalt |
|---|----------|--------|
| 00 | `00_INDEX.md` | Dieses Inhaltsverzeichnis |
| 01 | `01_ZUSAMMENFASSUNG.md` | Executive Summary: Alle Befunde nach Schweregrad |
| 02 | `02_PHP_BACKEND.md` | PHP Backend (provision.php): Logik, SQL, Matching, Splits |
| 03 | `03_PYTHON_API_CLIENT.md` | Python API Client + Import-Service: Dataclasses, Parsing, Normalisierung |
| 04 | `04_UI_PANELS.md` | UI Panels: Dashboard, Positionen, Zuordnung, Abrechnungen, etc. |
| 05 | `05_CROSS_LAYER.md` | Cross-Layer-Konsistenz: PHP ↔ Python ↔ UI |
| 06 | `06_VERBESSERUNGSPLAN.md` | Konkreter Maßnahmenplan mit Prioritäten und Aufwandsschätzung |

---

## Analysierte Dateien

### PHP Backend
- `BiPro-Webspace Spiegelung Live/api/provision.php` (~2038 Zeilen)
- `BiPro-Webspace Spiegelung Live/api/index.php` (PM-Routing)
- `BiPro-Webspace Spiegelung Live/setup/024_provision_matching_v2.php` (DB-Migration)

### Python API + Services
- `src/api/provision.py` (~830 Zeilen)
- `src/services/provision_import.py` (~650 Zeilen)

### Python UI
- `src/ui/provision/provision_hub.py` (~297 Zeilen)
- `src/ui/provision/dashboard_panel.py` (~548 Zeilen)
- `src/ui/provision/provisionspositionen_panel.py` (~814 Zeilen)
- `src/ui/provision/zuordnung_panel.py` (~926 Zeilen)
- `src/ui/provision/abrechnungslaeufe_panel.py` (~503 Zeilen)
- `src/ui/provision/verteilschluessel_panel.py` (~608 Zeilen)
- `src/ui/provision/auszahlungen_panel.py` (~587 Zeilen)
- `src/ui/provision/xempus_panel.py` (~488 Zeilen)
- `src/ui/provision/widgets.py` (~816 Zeilen)
- `src/ui/provision/__init__.py`

### Sonstige
- `src/ui/styles/tokens.py` (PILL_COLORS, ROLE_BADGE_COLORS, etc.)
- `src/i18n/de.py` (PROVISION_* Keys)

---

## Gesamtstatistik

| Schweregrad | Anzahl |
|-------------|--------|
| CRITICAL | 3 |
| HIGH | 13 |
| MEDIUM | 33 |
| LOW | 18 |
| **Gesamt** | **67** |
