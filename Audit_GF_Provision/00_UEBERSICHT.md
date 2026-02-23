# Audit: GF / Provisionsmanagement — Gesamtübersicht

**Datum**: 20. Februar 2026  
**Scope**: Komplette GF/Provisions-Ebene (PHP Backend, Python API/Parser, UI Panels, E2E Datenfluss)  
**Status**: Nur Analyse — KEINE Code-Änderungen

---

## Geprüfte Dateien

| Datei | Zeilen | Bereich |
|-------|--------|---------|
| `BiPro-Webspace Spiegelung Live/api/provision.php` | ~2038 | PHP Backend |
| `src/api/provision.py` | ~680 | Python API Client |
| `src/services/provision_import.py` | ~767 | VU/Xempus-Parser |
| `src/ui/provision/provision_hub.py` | ~230 | Hub/Navigation |
| `src/ui/provision/dashboard_panel.py` | ~383 | Dashboard |
| `src/ui/provision/abrechnungslaeufe_panel.py` | ~300 | Import-Panel |
| `src/ui/provision/provisionspositionen_panel.py` | ~380 | VU-Provisionen |
| `src/ui/provision/xempus_panel.py` | ~490 | Xempus-Beratungen |
| `src/ui/provision/zuordnung_panel.py` | ~290 | Zuordnung & Klärfälle |
| `src/ui/provision/verteilschluessel_panel.py` | ~250 | Verteilschlüssel & Rollen |
| `src/ui/provision/auszahlungen_panel.py` | ~340 | Auszahlungen & Reports |
| `src/ui/provision/widgets.py` | ~550 | Shared Widgets |

---

## Ergebnis-Zusammenfassung

| Schweregrad | Backend (PHP) | Parser (Python) | UI (Panels) | E2E Datenfluss | **Gesamt** |
|-------------|:-------------:|:---------------:|:-----------:|:--------------:|:----------:|
| **Kritisch** | 2 | 0 | 2 | 2 | **6** |
| **Hoch** | 5 | 2 | 7 | 1 | **15** |
| **Mittel** | 7 | 5 | 6 | 4 | **22** |
| **Niedrig** | 5 | 8 | 5 | 3 | **21** |
| **Gesamt** | **19** | **15** | **20** | **10** | **64** |

---

## Kritische Befunde (sofortige Behebung empfohlen)

| # | Bereich | Befund | Dokument |
|---|---------|--------|----------|
| B1 | Backend | SQL-Alias-Bug im Auto-Matching (`$batchFilter` nutzt falschen Alias `c` statt `c2` in Subquery) — Matching schlägt still fehl | `01_BACKEND_PHP.md` |
| B2 | Backend | Fehlende Transaktion bei manuellem Match — Dateninkonsistenz möglich | `01_BACKEND_PHP.md` |
| U1 | UI | XempusPanel: PillBadgeDelegate-Konstruktor — Argumente vertauscht → AttributeError bei jedem Paint | `03_UI_PANELS.md` |
| U2 | UI | XempusPanel: Loading-Overlay hat Größe 0x0 beim ersten Anzeigen | `03_UI_PANELS.md` |
| E1 | E2E | Abrechnungs-Deadlock: `is_locked=1` bei `freigegeben` blockiert auch `→ ausgezahlt` | `04_E2E_DATENFLUSS.md` |
| E2 | E2E | Xempus Re-Import überschreibt `provision_erhalten` Status via `COALESCE` | `04_E2E_DATENFLUSS.md` |

---

## Dokumente in diesem Ordner

| Datei | Inhalt |
|-------|--------|
| `00_UEBERSICHT.md` | Diese Datei — Gesamtübersicht |
| `01_BACKEND_PHP.md` | PHP Backend Audit (21 Befunde) |
| `02_PYTHON_API_PARSER.md` | Python API Client + Parser Audit (16 Befunde) |
| `03_UI_PANELS.md` | UI Panels Audit (20 Befunde) |
| `04_E2E_DATENFLUSS.md` | End-to-End Datenfluss-Analyse (10 Befunde) |
| `05_FIX_PLAN.md` | Priorisierter Maßnahmenplan |

---

## Empfohlene Reihenfolge der Behebung

### Phase 1: Kritische Bugs (1-2 Tage)
1. **B1**: Auto-Matching Alias-Fix (Einzeiler pro Query)
2. **E1**: Abrechnungs-Deadlock lösen (`is_locked`-Check anpassen)
3. **E2**: Xempus Status-Schutz (CASE statt COALESCE)
4. **U1**: PillBadgeDelegate-Konstruktor fixen (Einzeiler)
5. **U2**: Loading-Overlay Größe setzen
6. **B2**: Transaktion um manuelles Matching wickeln

### Phase 2: Hohe Priorität (3-5 Tage)
7. Alle synchronen API-Calls in UI-Thread → Worker auslagern (7 Stellen)
8. syncBeraterToCommissions() → batchRecalculateSplits() nutzen
9. Intra-Batch Duplikat-Erkennung (VU-Import)
10. Contracts GET Performance (korrelierte Subqueries → LEFT JOIN)
11. Code-Duplikation parse_xempus/parse_xempus_full auflösen
12. Hardcodierte Xempus-Spalten → Header-Detection

### Phase 3: Mittlere Priorität (1-2 Wochen)
13. Fehlende Validierungen (Raten, Datumsformate, Rollen, Berater-Existenz)
14. Status-Machine für Abrechnungen erzwingen
15. 15+ hardcodierte i18n-Strings in de.py überführen
16. Mapping-Änderung kaskadieren (retroaktive Berater-Updates)
17. Dashboard: Commissions ohne Datum sichtbar machen
18. Diverse Memory-/Signal-Leaks in Panels beheben

### Phase 4: Verbesserungen (fortlaufend)
19. Dead Code entfernen (5+ Funktionen/Konstanten)
20. Un-Match Funktion implementieren
21. Doppel-Abrechnungs-Sperre
22. Python-Skips an PHP melden
23. Debounce für Filter/Suche in allen Panels
24. Pagination in AuszahlungenPanel verbinden
