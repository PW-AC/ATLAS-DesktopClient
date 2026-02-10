# Kontext-Dokumentation - ACENCIA ATLAS

**Projekt:** ACENCIA ATLAS v1.6.0
**Analyse-Datum:** 2026-02-10
**Letzte Aktualisierung:** 2026-02-10 (Re-Analyse)
**Status:** Vollstaendig analysiert (alle 9 Phasen abgeschlossen, Re-Analyse v1.6.0)

---

## Inhaltsverzeichnis

| Nr. | Datei | Inhalt |
|-----|-------|--------|
| 01 | [Projektueberblick.md](01_Projektueberblick.md) | Was ist das Projekt? Zweck, Zielgruppe, Scope |
| 02 | [System_und_Architektur.md](02_System_und_Architektur.md) | 4-Schichten-Architektur, Komponenten, Kommunikation |
| 03 | [Domain_und_Begriffe.md](03_Domain_und_Begriffe.md) | GDV/BiPRO-Fachbegriffe, Domaenenmodell, Satzarten |
| 04 | [Code_Struktur_und_Moduluebersicht.md](04_Code_Struktur_und_Moduluebersicht.md) | Ordnerstruktur, Module, Klassen, Funktionen |
| 05 | [Laufzeit_und_Flows.md](05_Laufzeit_und_Flows.md) | Start, Login, BiPRO-Abruf, Dokumentenverarbeitung, Shutdown |
| 06 | [Konfiguration_und_Abhaengigkeiten.md](06_Konfiguration_und_Abhaengigkeiten.md) | Externe Libs, Server-API, OpenRouter |
| 07 | [Build_Run_Test_Deployment.md](07_Build_Run_Test_Deployment.md) | Installation, Start, Tests, Server-Sync |
| 08 | [Sicherheits_und_Randannahmen.md](08_Sicherheits_und_Randannahmen.md) | Implizite Annahmen, Security-Mechanismen |
| 09 | [Offene_Fragen_und_Unklarheiten.md](09_Offene_Fragen_und_Unklarheiten.md) | UNVERSTANDEN, UNVERIFIZIERT, Gaps |

---

## Projekttyp

- **Kategorie:** Desktop-Anwendung mit Server-Backend
- **Technologie:** Python 3.10+ / PySide6 (Qt) + PHP REST API
- **Domaene:** Versicherungswesen (BiPRO-Datenabruf, GDV-Datenaustausch)
- **Zielgruppe:** Versicherungsvermittler (ACENCIA GmbH, 2-5 Personen)

---

## Hauptfunktionen (v1.6.0)

| Funktion | Status | Beschreibung |
|----------|--------|--------------|
| **BiPRO Datenabruf** | Funktioniert | Automatischer Abruf von Lieferungen (Degenia, VEMA) mit parallelen Downloads, "Alle VUs abholen", Mail-Import (IMAP) |
| **Dokumentenarchiv mit Box-System** | Funktioniert | 8 Boxen, KI-Klassifikation, Smart!Scan E-Mail-Versand, PDF-Bearbeitung, Dokument-Historie, Duplikat-Erkennung, Drag & Drop, ZIP/MSG/PDF-Pipeline |
| **GDV-Editor** | Funktioniert | Oeffnen, Anzeigen, Bearbeiten von GDV-Dateien in 3 Ansichtsmodi |
| **Administration** | Funktioniert | 10 Panels: Nutzerverwaltung, Sessions, Passwoerter, Aktivitaetslog, KI-Kosten, Releases, E-Mail-Konten, SmartScan-Settings, SmartScan-Historie, IMAP-Inbox |
| **Auto-Update** | Funktioniert | Version-Check bei Login + periodisch, Silent Install, Pflicht-Updates |

---

## Schnelleinstieg

```bash
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
| `VERSION` | Zentrale Versionsdatei (1.6.0) |
| `src/main.py` | Qt-App Initialisierung, Login, Update-Check |
| `src/ui/main_hub.py` | Navigation, Drag & Drop, Schliess-Schutz (~1145 Zeilen) |
| `src/ui/bipro_view.py` | BiPRO UI + ParallelDownloadManager + MailImportWorker (~4950 Zeilen) |
| `src/ui/archive_boxes_view.py` | Dokumentenarchiv mit Box-System (~5380 Zeilen) |
| `src/ui/admin_view.py` | Admin-View mit 10 Panels, vertikaler Sidebar (~4000 Zeilen) |
| `src/ui/toast.py` | ToastManager + ProgressToastWidget (~558 Zeilen) |
| `src/bipro/transfer_service.py` | BiPRO 410/430 SOAP-Client (~1520 Zeilen) |
| `src/services/document_processor.py` | Parallele Dokumentenverarbeitung + KI (~1515 Zeilen) |
| `src/api/openrouter.py` | KI-Klassifikation zweistufig (~1880 Zeilen) |
| `src/api/documents.py` | Dokumenten-API mit Box-Support (~864 Zeilen) |
| `src/i18n/de.py` | Zentrale i18n-Datei (~910 Keys) |
| `BiPro-Webspace Spiegelung Live/api/` | PHP REST API (LIVE synchronisiert!) |

---

## Analysestatus

| Phase | Status |
|-------|--------|
| Phase 0: Orientierung | Abgeschlossen |
| Phase 1: Strukturverstaendnis | Abgeschlossen |
| Phase 2: Architektur | Abgeschlossen |
| Phase 3: Domain | Abgeschlossen |
| Phase 4: Code-Analyse | Abgeschlossen |
| Phase 5: Laufzeit | Abgeschlossen |
| Phase 6: Konfiguration | Abgeschlossen |
| Phase 7: Build/Run/Test | Abgeschlossen |
| Phase 8: Sicherheit | Abgeschlossen |
| Phase 9: Unklarheiten | Abgeschlossen |

---

## Aenderungen seit letzter Analyse (v1.0.1 -> v1.6.0)

| Version | Datum | Hauptaenderungen |
|---------|-------|------------------|
| v1.0.2 | 08.02.2026 | Scan-Upload Endpunkt fuer Power Automate (API-Key-Auth) |
| v1.0.3 | 09.02.2026 | Dokumenten-Farbmarkierung (8 Farben, persistent) |
| v1.0.4 | 09.02.2026 | Globales Drag & Drop, MSG-Verarbeitung, PDF-Unlock, Outlook Direct-Drop |
| v1.0.5 | 09.02.2026 | ZIP-Entpackung (AES-256), zentrale Passwort-Verwaltung |
| v1.0.6 | 09.02.2026 | Smart!Scan E-Mail-Versand, IMAP-Import, PHPMailer |
| v1.0.7 | 10.02.2026 | Toast-System ersetzt alle modalen Popups (~137 QMessageBox -> Toast) |
| v1.0.8 | 10.02.2026 | Tastenkuerzel im Dokumentenarchiv (10 Shortcuts) |
| v1.0.9 | 10.02.2026 | Admin-Redesign (vertikale Sidebar, 10 Panels), Mail-Import in BiPRO, ProgressToast |
| v1.1.0 | 10.02.2026 | Keyword-Conflict-Hints, PDF Magic-Byte-Validierung, MTOM-Fixes |
| v1.1.1 | 10.02.2026 | Duplikat-Erkennung (SHA256) |
| v1.1.2 | 10.02.2026 | Dokument-Historie (Seitenpanel, 8 Aktionsfarben) |
| v1.1.3 | 10.02.2026 | PDF-Bearbeitung in Vorschau (Drehen, Loeschen, Speichern) |
| v1.1.4 | 10.02.2026 | App-Schliess-Schutz (blockiert bei KI-Verarbeitung/SmartScan) |
