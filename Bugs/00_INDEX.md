# Bug-Analyse: ACENCIA ATLAS v1.6.0

**Datum:** 10. Februar 2026 (Re-Analyse)  
**Methode:** Statische Code-Analyse aller kritischen Module  
**Analysierte Dateien:** ~61 Python-Quelldateien + ~17 PHP-Dateien  
**Gefundene Bugs:** 39 (4 CRITICAL, 11 HIGH, 14 MEDIUM, 10 LOW)  
**Status:** Re-analysiert auf Basis v1.6.0 Codebase

---

## Navigation

| Datei | Inhalt |
|-------|--------|
| [01_Bugliste.md](01_Bugliste.md) | Alle identifizierten Bugs mit Schweregrad |
| [02_Reproduktion.md](02_Reproduktion.md) | Reproduktionsschritte pro Bug |
| [03_Root_Cause_Analyse.md](03_Root_Cause_Analyse.md) | Ursachenanalyse |
| [04_Fixes.md](04_Fixes.md) | Fix-Design & Umsetzungsplan |
| [05_Verifikation.md](05_Verifikation.md) | Testdokumentation |
| [06_Regressionen_und_Risiken.md](06_Regressionen_und_Risiken.md) | Nebenwirkungen |

---

## Schweregrad-Uebersicht

| Schweregrad | Anzahl | Beschreibung |
|-------------|--------|--------------|
| **CRITICAL** | 4 | Crash, Datenverlust, Sicherheitsluecke |
| **HIGH** | 11 | Falsches Verhalten, falsche Daten, Sicherheitsrisiko |
| **MEDIUM** | 14 | Edge-Cases, Resource-Leaks, Race-Conditions |
| **LOW** | 10 | Kosmetisch, Performance, Code-Qualitaet |

## Re-Analyse-Ergebnis (v1.6.0)

Die Re-Analyse vom 10.02.2026 hat bestaetigt, dass alle 39 identifizierten Bugs weiterhin im Code vorhanden sind. Zusaetzlich wurden folgende Muster in der erweiterten Exploration bestaetigt:

### Bestaetigte uebergreifende Probleme

| Kategorie | Betroffene Dateien | Beschreibung |
|-----------|-------------------|--------------|
| **Worker-Lifecycle** | main_hub.py, bipro_view.py, update_dialog.py | QThread-Worker werden nicht sauber per `deleteLater()` aufgeraeumt; Signale bleiben verbunden |
| **Bare except** | transfer_service.py, bipro_view.py, archive_view.py, partner_view.py | `except:` oder `except Exception: pass` faengt SystemExit/KeyboardInterrupt oder schluckt Fehler |
| **API Response Parsing** | documents.py, update_service.py | Direkter Dict-Zugriff (`response['data']`) statt sicherem `response.get('data', {})` |
| **Temp-File-Cleanup** | main_hub.py, transfer_service.py | Temporaere Dateien/Verzeichnisse werden bei Fehlern nicht bereinigt |

### Neue Findings (zusaetzlich zu bestehender Bugliste)

| ID | Datei | Bug | Severity | Status |
|----|-------|-----|----------|--------|
| NEW-01 | `archive_view.py:1034` | IndexError bei leerem Spreadsheet (leeres XLSX) | MEDIUM | Kein Fix noetig (Guard vorhanden) |
| NEW-02 | `archive_boxes_view.py:3791` | DocumentHistoryWorker: alter Worker nicht gestoppt vor Neustart | MEDIUM | **GEFIXT** (quit+wait vor Neustart) |
| NEW-03 | `document_processor.py:672,741` | KI-Ergebnis None-Check fehlt vor `.get()` Aufruf | HIGH | **GEFIXT** (None→{} Fallback) |
| NEW-04 | `main_hub.py:860-943` | Outlook temp dir Leak bei leerer Selektion | HIGH | **GEFIXT** (sofortige Bereinigung) |

### Weitere Code-Quality-Fixes (10.02.2026)

| Datei | Fix | Kategorie |
|-------|-----|-----------|
| `transfer_service.py` | Bare `except:` → `except Exception:` / `except OSError:` | Code-Qualitaet |
| `bipro_view.py` | Bare `except:` → `except Exception:` / `except OSError:` | Code-Qualitaet |
| `archive_view.py` | Bare `except:` → `except (ValueError, IndexError):` / `except OSError:` | Code-Qualitaet |
| `partner_view.py` | Bare `except:` → `except (ValueError, TypeError):` | Code-Qualitaet |
| `toast.py` | Swallowed exception → logging.warning() | Code-Qualitaet |

## Top-Priority Bugs (noch offen)

| ID | Modul | Bug | Severity |
|----|-------|-----|----------|
| BUG-0001 | `toast.py` | `clear_all()` crasht bei ProgressToastWidget | CRITICAL |
| BUG-0002 | `documents.py` | `set_document_color()` crasht mit TypeError | CRITICAL |
| BUG-0003 | `archive_boxes_view.py` | `self._current_documents` existiert nicht → AttributeError | CRITICAL |
| BUG-0004 | `documents.php` | HTTP Header Injection via Dateiname | CRITICAL |
| BUG-0005 | `archive_boxes_view.py` | SmartScan sendet falsche Dokumente nach Sortierung | HIGH |
| BUG-0006 | `archive_boxes_view.py` | Auto-Refresh-Pause bei Verarbeitung wirkungslos | HIGH |
| BUG-0009 | `transfer_service.py` | XML-Injection bei Username/Consumer-ID/Token | HIGH |
| BUG-0012 | `toast.py` | Toast-Erstellung aus Worker-Threads crasht Qt | HIGH |
| BUG-0025 | `main_hub.py` | DropUploadWorker hat keine cancel()-Methode | MEDIUM |
