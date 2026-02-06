# Kontext-Dokumentation - BiPRO-GDV Tool

**Projekt:** BiPRO-GDV Tool v0.9.3  
**Analyse-Datum:** 2026-02-04  
**Letzte Aktualisierung:** 2026-02-05  
**Status:** Vollständig analysiert

---

## Inhaltsverzeichnis

| Nr. | Datei | Inhalt |
|-----|-------|--------|
| 01 | [Projektueberblick.md](01_Projektueberblick.md) | Was ist das Projekt? Zweck, Zielgruppe, Scope |
| 02 | [System_und_Architektur.md](02_System_und_Architektur.md) | 4-Schichten-Architektur, Komponenten, Kommunikation |
| 03 | [Domain_und_Begriffe.md](03_Domain_und_Begriffe.md) | GDV/BiPRO-Fachbegriffe, Domänenmodell, Satzarten |
| 04 | [Code_Struktur_und_Moduluebersicht.md](04_Code_Struktur_und_Moduluebersicht.md) | Ordnerstruktur, Module, Klassen, Funktionen |
| 05 | [Laufzeit_und_Flows.md](05_Laufzeit_und_Flows.md) | Start, Login, BiPRO-Abruf, Dokumentenverarbeitung |
| 06 | [Konfiguration_und_Abhaengigkeiten.md](06_Konfiguration_und_Abhaengigkeiten.md) | Externe Libs, Server-API, OpenRouter |
| 07 | [Build_Run_Test_Deployment.md](07_Build_Run_Test_Deployment.md) | Installation, Start, Tests, Server-Sync |
| 08 | [Sicherheits_und_Randannahmen.md](08_Sicherheits_und_Randannahmen.md) | Implizite Annahmen, Security-Mechanismen |
| 09 | [Offene_Fragen_und_Unklarheiten.md](09_Offene_Fragen_und_Unklarheiten.md) | UNVERSTANDEN, UNVERIFIZIERT, Gaps |

---

## Projekttyp

- **Kategorie:** Desktop-Anwendung mit Server-Backend
- **Technologie:** Python 3.10+ / PySide6 (Qt) + PHP REST API
- **Domäne:** Versicherungswesen (BiPRO-Datenabruf, GDV-Datenaustausch)
- **Zielgruppe:** Versicherungsvermittler (ACENCIA GmbH, 2-5 Personen)

---

## Hauptfunktionen (v0.9.3)

| Funktion | Status | Beschreibung |
|----------|--------|--------------|
| **BiPRO Datenabruf** | ✅ Funktioniert | Automatischer Abruf von Lieferungen (Degenia, VEMA) **mit parallelen Downloads, timezone-aware Token (v0.9.2)** |
| **Dokumentenarchiv mit Box-System** | ✅ Funktioniert | 7 Boxen, KI-Klassifikation, parallele Verarbeitung, **Kosten-Tracking (v0.9.3)** |
| **GDV-Editor** | ✅ Funktioniert | Öffnen, Anzeigen, Bearbeiten von GDV-Dateien |

---

## Schnelleinstieg

```bash
# Start
cd "X:\projekte\5510_GDV Tool V1"
pip install -r requirements.txt
python run.py
```

Login: `admin` + Passwort vom Administrator

---

## Wichtige Dateien

| Pfad | Beschreibung |
|------|--------------|
| `run.py` | Entry Point |
| `src/main.py` | Qt-App Initialisierung, Login |
| `src/ui/main_hub.py` | Navigation zwischen Bereichen |
| `src/ui/bipro_view.py` | BiPRO-Datenabruf UI **+ ParallelDownloadManager + mime_to_extension (v0.9.2)** |
| `src/ui/archive_boxes_view.py` | Dokumentenarchiv mit Box-System |
| `src/bipro/transfer_service.py` | BiPRO 410/430 SOAP-Client **+ SharedTokenManager + timezone-aware (v0.9.2)** |
| `src/bipro/rate_limiter.py` | **AdaptiveRateLimiter (NEU v0.9.1)** |
| `src/services/document_processor.py` | Parallele Dokumentenverarbeitung **+ BatchProcessingResult mit Kosten-Tracking (v0.9.3)** |
| `src/services/data_cache.py` | **DataCacheService mit pause/resume (v0.9.1)** |
| `src/config/processing_rules.py` | Verarbeitungsregeln **+ BiPRO-GDV-Codes (v0.9.1)** |
| `src/api/openrouter.py` | KI-Klassifikation (GPT-4o) **+ erweiterte Sach-Keywords + Guthaben-API (v0.9.3)** |
| `BiPro-Webspace Spiegelung Live/api/` | PHP REST API (LIVE synchronisiert!) |

---

## Analysestatus

| Phase | Status |
|-------|--------|
| Orientierung | ✅ |
| Strukturverständnis | ✅ |
| Architektur | ✅ |
| Domain | ✅ |
| Code-Analyse | ✅ |
| Laufzeit | ✅ |
| Konfiguration | ✅ |
| Build/Run/Test | ✅ |
| Sicherheit | ✅ |
| Unklarheiten | ✅ |

---

## Änderungen seit v0.3.0

| Version | Datum | Hauptänderungen |
|---------|-------|-----------------|
| v0.4.0 | Jan 2026 | BiPRO-Client Grundgerüst, VU-Verbindungsverwaltung |
| v0.5.0 | Feb 2026 | BiPRO funktioniert (Degenia), Dokumentenarchiv, PDF-Vorschau |
| v0.6.0 | Feb 2026 | KI-basierte PDF-Analyse via OpenRouter |
| v0.7.0 | Feb 2026 | Box-System (7 Boxen), automatische Klassifikation |
| v0.8.0 | Feb 2026 | Kranken-Box, Multi-Upload, parallele Verarbeitung, Credits-Anzeige |
| v0.9.0 | Feb 2026 | BiPRO-Code-Vorsortierung, Token-optimierte KI, GDV-Metadaten |
| v0.9.1 | 04.02.2026 | Parallele BiPRO-Downloads, SharedTokenManager, AdaptiveRateLimiter, Auto-Refresh-Kontrolle, PDF-Validierung/-Reparatur, GDV über BiPRO-Code (999xxx), Fix if/elif-Struktur |
| v0.9.2 | 05.02.2026 | Timezone-aware Token-Validierung (Degenia-Fix), MIME-Type→Extension Mapping (.pdf statt .bin), Auto Worker-Anpassung |
| **v0.9.3** | **05.02.2026** | **OpenRouter Kosten-Tracking (vor/nach Verarbeitung), erweiterte Sach-Keywords (Privathaftpflicht, PHV, etc.), Courtage-Benennung (VU_Name + Datum), Pensionskasse→Leben** |
