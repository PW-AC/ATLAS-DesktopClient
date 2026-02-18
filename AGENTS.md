# AGENTS.md
# Agent Instructions for ACENCIA ATLAS

**Agent's Responsibility:** This document is the single source of truth for agent collaboration on this project. With every new feature, bug fix, or refactor, you **must** update this document to reflect the changes.

---

## WICHTIG: Live-Synchronisierung

### Webspace-Spiegelung

**Der Ordner `BiPro-Webspace Spiegelung Live/` ist LIVE mit dem Strato Webspace synchronisiert!**

| Lokal | Remote |
|-------|--------|
| `BiPro-Webspace Spiegelung Live/` | Strato Webspace `/BiPro/` |
| Änderungen werden in Echtzeit übertragen | Domain: `https://acencia.info/` |

**VORSICHT:** Gelöschte Dateien werden auch auf dem Server gelöscht!

### Ausnahmen von der Synchronisierung

**WICHTIG:** Der Ordner `dokumente/` ist von der Synchronisierung AUSGESCHLOSSEN!

| Ordner | Synchronisiert | Grund |
|--------|----------------|-------|
| `api/` | ✅ Ja | PHP-Code |
| `dokumente/` | ❌ **NEIN** | Server-Dokumentenspeicher (Uploads via API) |
| `releases/` | ❌ **NEIN** | Server-Release-Storage (Installer-Uploads via Admin-API) |
| `setup/` | ✅ Ja | Migrations-Skripte (nach Ausführung löschen!) |

Der `dokumente/` Ordner enthält alle über die API hochgeladenen Dateien. Der `releases/` Ordner enthält die Installer-EXEs fuer Auto-Updates. Eine Synchronisierung würde diese Dateien löschen, da sie lokal nicht existieren.

### Sensible Dateien

Die Datei `BiPro-Webspace Spiegelung Live/api/config.php` enthält:
- Datenbank-Credentials
- Master-Key für Verschlüsselung
- JWT-Secret

**Diese Datei ist per .htaccess geschützt und NICHT direkt über HTTP aufrufbar.**

---

## Project Overview

**ACENCIA ATLAS** ("Der Datenkern.") ist eine Python-Desktop-Anwendung mit Server-Backend für:
- Automatisierten BiPRO-Datenabruf von Versicherungsunternehmen
- Zentrales Dokumentenarchiv für alle Nutzer (mit PDF-Vorschau)
- Erstellen, Anzeigen und Bearbeiten von GDV-Datensätzen

### Architektur (Überblick)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ACENCIA ATLAS v2.1.3                                │
├─────────────────────────────────────────────────────────────────────────────┤
│  Desktop-App (PySide6/Qt)                         Strato Webspace           │
│  ├── UI Layer                                     ├── PHP REST API          │
│  │   ├── main_hub.py (Navigation+DragDrop+Poller) │   ├── auth.php          │
│  │   ├── message_center_view.py (Mitteilungen) ✅ │   ├── messages.php      │
│  │   ├── chat_view.py (1:1 Chat Vollbild) ✅     │   ├── chat.php          │
│  │   ├── bipro_view.py (BiPRO+MailImport) ✅      │   ├── documents.php     │
│  │   ├── archive_boxes_view.py (Archiv) ✅        │   ├── gdv.php           │
│  │   ├── gdv_editor_view.py (GDV-Editor)          │   ├── credentials.php   │
│  │   ├── admin_view.py (Admin, 15 Panels) ✅      │   ├── admin.php         │
│  │   ├── update_dialog.py (Auto-Update) ✅        │   ├── sessions.php      │
│  │   ├── toast.py (Toast+ProgressToast)           │   ├── activity.php      │
│  │   ├── partner_view.py                          │   ├── releases.php      │
│  │   └── main_window.py                           │   ├── incoming_scans.php │
│  │                                                │   ├── smartscan.php      │
│  │                                                │   ├── email_accounts.php │
│  │                                                │   └── lib/permissions.php│
│  ├── API Client                                   ├── MySQL Datenbank       │
│  │   ├── src/api/client.py                        ├── Dokumente-Storage     │
│  │   ├── src/api/documents.py                     └── Releases-Storage      │
│  │   ├── src/api/admin.py (Admin-API)                                       │
│  │   ├── src/api/messages.py (Mitteilungen-API) **NEU v2.0.0**             │
│  │   ├── src/api/chat.py (Chat-API) **NEU v2.0.0**                        │
│  │   ├── src/api/releases.py (Releases-API)                                │
│  │   └── src/api/vu_connections.py                                          │
│  ├── BiPRO SOAP Client ✅ FUNKTIONIERT                                      │
│  │   ├── src/bipro/transfer_service.py (STS + Transfer + SharedTokenManager)│
│  │   ├── src/bipro/bipro_connector.py (SmartAdmin vs. Standard) **NEU**     │
│  │   ├── src/bipro/rate_limiter.py (AdaptiveRateLimiter) **NEU v0.9.1**     │
│  │   └── src/bipro/categories.py (Kategorie-Mapping)                        │
│  ├── Services Layer                                                         │
│  │   ├── src/services/document_processor.py (Klassifikation)                │
│  │   ├── src/services/data_cache.py (Cache + Auto-Refresh-Kontrolle)        │
│  │   ├── src/services/update_service.py (Auto-Update) **NEU v0.9.9**       │
│  │   ├── src/services/empty_page_detector.py (Leere-Seiten) **NEU v2.0.2** │
│  │   ├── src/services/pdf_unlock.py (PDF-Passwort-Entsperrung)              │
│  │   ├── src/services/zip_handler.py (ZIP-Entpackung)                       │
│  │   ├── src/services/msg_handler.py (Outlook MSG-Verarbeitung)             │
│  │   └── src/services/atomic_ops.py (Atomic File Operations)                │
│  └── Parser Layer                                                           │
│      ├── gdv_parser.py                                                      │
│      └── gdv_layouts.py                                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│  Datenflüsse:                                                               │
│  1. Desktop ←→ PHP-API ←→ MySQL/Dateien (Archiv, Auth, VU-Verbindungen)     │
│  2. Desktop → BiPRO SOAP → Versicherer (STS-Token + Transfer-Service)       │
│  3. BiPRO-Dokumente → Automatisch ins Dokumentenarchiv (via API)            │
│  4. Desktop ←→ PHP-API (Messages, Chat, Notifications) **NEU v2.0.0**      │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Tech-Stack

| Komponente | Technologie | Version |
|------------|-------------|---------|
| Desktop | Python + PySide6 | 3.10+ / 6.6.0+ |
| PDF-Viewer | PySide6.QtPdf (QPdfView) | 6.6.0+ |
| Excel-Viewer | openpyxl (read_only) | 3.1.0+ |
| PDF-Verarbeitung | PyMuPDF (fitz) | 1.23+ |
| HTTP Client | requests | 2.31+ |
| BiPRO SOAP | requests (raw XML, kein zeep) | 2.31+ |
| KI/LLM | OpenRouter ODER OpenAI API (GPT-4o/4o-mini) | - |
| Token-Zaehlung | tiktoken | 0.5+ |
| Server API | PHP | 7.4+ |
| Datenbank | MySQL | 8.0 |
| Hosting | Strato Webspace | - |

### Server-Infrastruktur

| Komponente | Details |
|------------|---------|
| Domain | `https://acencia.info/` |
| API Base | `https://acencia.info/api/` |
| DB Server | `database-5019508812.webspace-host.com` |
| DB Name | `dbs15252975` |

---

## Project Goal

### Zweck
- **Primär**: BiPRO-Daten automatisiert von Versicherern abrufen ✅ FUNKTIONIERT
- **Sekundär**: Zentrales Dokumentenarchiv für Team (2-5 Personen) ✅ FUNKTIONIERT
- **Tertiär**: GDV-Dateien visualisieren und bearbeiten für Versicherungsvermittler ✅ FUNKTIONIERT

### Explizit NICHT Ziel
- Keine Web-Oberfläche (Desktop-App mit Server-Backend)
- Keine XML-/JSON-GDV-Varianten (nur klassisches Fixed-Width-Format)
- Keine automatischen Abrufe ohne Benutzerinteraktion (zunächst)

---

## Leitplanken

### Coding Style
- **Python**: PEP 8, Type Hints verwenden
- **Docstrings**: Google-Style für alle öffentlichen Funktionen
- **Sprache in Code**: Englische Variablen/Funktionen, deutsche Kommentare/Docstrings OK
- **UI-Texte**: SOLLTEN in zentraler Datei sein (aktuell noch Handlungsbedarf)

### Patterns
- **Parser**: Generischer Ansatz über Layout-Metadaten (nicht hartcodiert)
- **Domain-Modelle**: Dataclasses mit Factory-Methoden
- **UI**: Separation of Concerns (Widget pro View)
- **BiPRO**: Raw XML mit requests (zeep ist zu strikt für Degenia)
- **Hintergrund-Operationen**: QThread-Worker für lange Operationen
- **KEINE modalen Popups**: `QMessageBox.information/warning/critical/about` sind **VERBOTEN** fuer Info/Erfolg/Warnung/nicht-kritische Fehler. Stattdessen `ToastManager` aus `ui.toast` verwenden (`show_success`, `show_error`, `show_warning`, `show_info`). Erlaubt bleiben NUR: `QMessageBox.question()` fuer sicherheitskritische Bestaetigungen, Authentifizierungs-Dialoge und systemkritische Fehler. **Siehe `docs/ui/UX_RULES.md` fuer Details.**

### Namenskonventionen
- **Satzarten**: Immer 4-stellig mit führenden Nullen (z.B. "0100", "0200")
- **Felder**: snake_case, deutsch (z.B. `versicherungsschein_nr`, `geburtsdatum`)
- **Klassen**: PascalCase (z.B. `ParsedRecord`, `GDVData`)
- **Datumsanzeige**: Deutsches Format in UI (DD.MM.YYYY)

### Error-Handling
- Parser gibt immer `ParsedFile` zurück (auch bei Fehlern)
- Fehler/Warnungen werden in `ParsedFile.errors`/`warnings` gesammelt
- UI zeigt Fehler via `ToastManager` (nicht-blockierend), keine stummen Fehler (siehe `docs/ui/UX_RULES.md`)
- BiPRO-Fehler werden im Log-Bereich angezeigt

### Logging
- Modul: `logging` (Standard-Library)
- Level: `INFO` für normale Operation, `DEBUG` für Entwicklung
- Format: `"%(asctime)s - %(name)s - %(levelname)s - %(message)s"`

### Security/Secrets
- **Keine Secrets im Code** - Das Tool verarbeitet personenbezogene Daten (DSGVO)
- GDV-Dateien können sensible Daten enthalten (Adressen, Geburtsdaten, Bankdaten)
- BiPRO-Credentials werden verschlüsselt auf dem Server gespeichert
- JWT-Token für API-Authentifizierung

### Performance
- Große Dateien (>10.000 Zeilen): Lazy Loading für Tabelle wäre sinnvoll (TODO)
- Encoding-Detection: Mehrere Versuche (CP1252, Latin-1, UTF-8)
- BiPRO-Downloads in Hintergrund-Thread

### Datenmodell-Leitplanken
- **Vertragsschlüssel**: `VU_Nummer|Versicherungsschein_Nr|Sparte`
- **Teildatensätze**: Position 256 enthält Teildatensatz-Nummer (1-9)
- **Datumsformat**: GDV = TTMMJJJJ, intern = YYYY-MM-DD, Anzeige = DD.MM.YYYY
- **Beträge**: GDV = implizite Dezimalstellen, intern = float

---

## Definition of Done (DoD)

- [ ] Code läuft (`python run.py` startet ohne Fehler)
- [ ] Manuelle Tests mit Testdatei `testdata/sample.gdv`
- [ ] BiPRO-Test: Degenia-Verbindung erstellen, Lieferungen abrufen
- [ ] Lint/Format OK (empfohlen: `ruff`)
- [ ] Docstrings für neue öffentliche Funktionen
- [ ] AGENTS.md aktualisiert bei Architekturänderungen
- [ ] Keine Secrets im Code
- [ ] Encoding-Test mit echten GDV-Dateien (Umlaute!)

---

## Features und Funktionen

### 1. BiPRO Datenabruf ✅ FUNKTIONIERT (v0.5.0+, Parallel v0.9.1)
- **Zweck**: Automatisierter Abruf von Lieferungen von Versicherern
- **Ablauf**: 
  1. VU-Verbindung auswählen
  2. Lieferungen werden automatisch geladen (listShipments)
  3. Einzeln/Alle herunterladen (getShipment mit MTOM/XOP-Support)
  4. Automatisch ins Dokumentenarchiv hochladen
- **Parallelisierung (v0.9.1+)**:
  - **ParallelDownloadManager**: QThread mit ThreadPoolExecutor (max. 10 Worker, auto-adjustiert)
  - **Automatische Worker-Anpassung**: Bei wenigen Lieferungen (z.B. 3) nur 3 Worker statt 10
  - **SharedTokenManager**: Thread-sicheres STS-Token-Management (einmal holen, wiederverwenden)
  - **AdaptiveRateLimiter**: Dynamische Anpassung bei Rate Limiting (HTTP 429/503)
  - **PDF-Validierung**: Automatische Reparatur korrupter PDFs mit PyMuPDF
  - **Auto-Refresh-Pause**: Cache-Refresh wird während Downloads pausiert
- **Dateien**:
  - `src/bipro/transfer_service.py` (~1220 Zeilen) → BiPRO 410 STS + BiPRO 430 Transfer
  - `src/bipro/rate_limiter.py` → AdaptiveRateLimiter **NEU v0.9.1**
  - `src/bipro/categories.py` → Kategorie-Code zu Name Mapping
  - `src/ui/bipro_view.py` (~4900+ Zeilen) → UI + ParallelDownloadManager + MailImportWorker
  - `src/services/data_cache.py` → DataCacheService (pause/resume_auto_refresh)
- **Unterstützte VUs**: 
  - ✅ **Degenia** - Vollständig funktionsfähig
  - ✅ **VEMA** - Vollständig funktionsfähig (seit 04.02.2026)
  - 🔜 Weitere geplant (Signal Iduna, Allianz, etc.)

### 2. Dokumentenarchiv mit Box-System ✅ (v0.8.0)
- **Zweck**: Zentrales Archiv mit automatischer Klassifikation und Verarbeitung
- **Box-Typen** (in Anzeigereihenfolge):
  1. **GDV Box** - GDV-Dateien (.gdv, .txt, keine Endung)
  2. **Courtage Box** - Provisions-/Courtage-Abrechnungen (KI-klassifiziert)
  3. **Sach Box** - Sachversicherungs-Dokumente (KI-klassifiziert)
  4. **Leben Box** - Lebensversicherungs-Dokumente (KI-klassifiziert)
  5. **Kranken Box** - Krankenversicherungs-Dokumente (KI-klassifiziert) **NEU v0.8.0**
  6. **Sonstige Box** - Nicht zugeordnete Dokumente
  7. **Roh Archiv** - XML-Rohdateien (BiPRO-Abfragen)
- **Workflow**:
  1. Dokumente landen in **Eingangsbox** (manuell oder BiPRO)
  2. Automatische Verarbeitung verschiebt in **Verarbeitungsbox**
  3. Klassifikation: XML → Roh, GDV-Endung → GDV, PDF → KI-Analyse
  4. KI klassifiziert PDFs nach Courtage/Sach/Leben/Kranken/Sonstige
- **Features**:
  - Sidebar mit Box-Navigation und Live-Zaehler
  - Verarbeitungsbereich eingeklappt (ausklappbar)
  - Farbkodierte Box-Spalte in Tabelle
  - Kontext-Menue zum Verschieben zwischen Boxen
  - **KI-Benennung**: PDFs automatisch umbenennen via OpenRouter
  - PDF-Vorschau (integriert mit QPdfView)
  - **Multi-Upload**: Mehrere Dateien gleichzeitig hochladen **NEU v0.8.0**
  - **Parallele Verarbeitung**: ThreadPoolExecutor mit 4 Workern **NEU v0.8.0**
  - **Robuster Download**: Retry-Logik mit Backoff **NEU v0.8.0**
  - **OpenRouter Credits**: Guthaben-Anzeige im Header **NEU v0.8.0**
- **Dateien**:
  - `src/ui/archive_boxes_view.py` → **Box-basierte UI mit Thread-Cleanup**
  - `src/ui/archive_view.py` → Legacy-View (noch vorhanden)
  - `src/api/documents.py` → Document-Modell mit Box-Feldern
  - `src/services/document_processor.py` → **Parallele Klassifikation** (ThreadPoolExecutor)
  - `src/config/processing_rules.py` → **Konfigurierbare Regeln**
  - `src/api/openrouter.py` → OpenRouter Client (Klassifikation + Credits)
  - `src/api/client.py` → API-Client mit Retry-Logik
  - `BiPro-Webspace Spiegelung Live/api/documents.php` → Backend mit Box-Support

### 2a. KI-basierte PDF-Klassifikation und Benennung (v0.8.0, Optimierung v0.9.4, Keyword-Hints v1.1.0)
- **Zweck**: PDFs automatisch durch KI analysieren, klassifizieren und umbenennen
- **Zweistufige Klassifikation mit Confidence-Scoring (NEU v0.9.4)**:
  - **Stufe 1**: GPT-4o-mini (2 Seiten, ~200 Token, schnell + guenstig)
    - Gibt `confidence: "high"|"medium"|"low"` zurueck
    - Bei "high"/"medium" -> Ergebnis verwenden, fertig
  - **Stufe 2**: GPT-4o (5 Seiten, praeziser) - NUR bei "low" Confidence
    - Gibt zusaetzlich `document_name` zurueck (z.B. "Schriftwechsel", "Vollmacht")
    - Wird nur fuer ~1-5% der Dokumente aufgerufen
- **Keyword-Conflict-Hints (NEU v1.1.0)**:
  - Lokaler Keyword-Scanner (`_build_keyword_hints()`) laeuft auf bereits extrahiertem Text
  - Generiert Hint NUR bei widerspruechlichen Keywords (z.B. Courtage + Leben gleichzeitig)
  - ~95% der Dokumente: 0 extra Tokens, ~0.1ms CPU-Overhead
  - Hint-Faelle:
    - **Courtage + Leben/Sach/Kranken**: Courtage-Keyword hat Vorrang, Warnung dass Sparten-Keyword wahrscheinlich VU-Name ist
    - **Kontoauszug + Provision**: Spezialfall -> courtage (VU-Provisionskonto)
    - **Sach-Keyword allein**: Sicherheits-Hint (KI hat hier nachweislich versagt)
  - Hint wird dem Text-Input vorangestellt (Stufe 1 UND Stufe 2), Prompts bleiben unveraendert
  - KI entscheidet weiterhin selbst -- Hints sind reine Zusatz-Information
- **Courtage-Erkennung (verschaerft v0.9.4)**:
  - Courtage = NUR Provisionsabrechnungen fuer Makler mit Provisionsliste
  - NICHT Courtage: Beitragsrechnungen, Kuendigungen, Mahnungen, Adressaenderungen
  - Negativ-Beispiele im Prompt verhindern False Positives
- **Benennungs-Schema**:
  - **Courtage**: `VU_Courtage_Datum.pdf` (z.B. `Allianz_Courtage_2026-02-04.pdf`)
  - **Sach/Leben/Kranken**: `VU_Sparte.pdf` (z.B. `Degenia_Sach.pdf`)
  - **Sonstige**: `VU_Dokumentname.pdf` (z.B. `VEMA_Schriftwechsel.pdf`) - NEU v0.9.4
- **Text-Extraktion**:
  - Triage: Erste 2 Seiten, max 3000 Zeichen (vorher 1 Seite/2500 - Begleitschreiben-Fix)
  - Detail: Erste 5 Seiten, max 5000 Zeichen (Stufe 2)
  - OCR-Fallback: Vision-OCR bei Bild-PDFs (150 DPI)
- **Dateien**:
  - `src/api/openrouter.py` → `classify_sparte_with_date()`, `_build_keyword_hints()`, `_classify_sparte_request()`, `_classify_sparte_detail()`
  - `src/services/document_processor.py` → Verarbeitungslogik mit Confidence-Handling
  - `src/ui/archive_boxes_view.py` → AIRenameWorker, CreditsWorker
  - `BiPro-Webspace Spiegelung Live/api/ai.php` → GET /ai/key

### 1a. "Alle VUs abholen" ✅ (v0.9.5)
- **Zweck**: Alle BiPRO-Daten von allen aktiven VU-Verbindungen mit einem Klick abrufen
- **Trigger**: Button "Alle VUs abholen" in der BiPRO-Toolbar (immer aktiv, braucht keine VU-Auswahl)
- **Ablauf**:
  1. Alle aktiven VU-Verbindungen ermitteln
  2. Fuer jede VU nacheinander: Credentials holen → Lieferungen abrufen → Alle herunterladen → Ins Archiv
  3. Bei Fehler/keine Lieferungen: VU ueberspringen, naechste VU versuchen
  4. Abschluss-Zusammenfassung mit Gesamtstatistik
- **State Machine**: `_all_vus_mode` Flag, `_vu_queue`, `_all_vus_stats`
- **Callbacks**: Bestehende `_on_parallel_all_finished` und `_on_all_downloads_finished` leiten im all_vus_mode zur naechsten VU weiter
- **Dateien**:
  - `src/ui/bipro_view.py` → `_fetch_all_vus()`, `_process_next_vu()`, `_on_all_vus_*` Callbacks
  - `src/i18n/de.py` → Alle VUs abholen Texte

### 2b. Box-Download (ZIP/Ordner) ✅ (v0.9.5)
- **Zweck**: Gesamten Inhalt einer Box herunterladen (alle nicht-archivierten Dokumente)
- **Trigger**: Rechtsklick auf Box in Sidebar → Herunterladen → ZIP oder Ordner
- **Optionen**:
  - **Als ZIP**: Alle Dokumente in eine ZIP-Datei packen (Speicherort waehlen)
  - **In Ordner**: Alle Dokumente in einen Ordner herunterladen
- **Archivierung**: Nach erfolgreichem Download werden alle Dokumente automatisch archiviert
- **Undo**: Toast-Benachrichtigung mit Rueckgaengig-Option (5 Sekunden)
- **Unterstuetzte Boxen**: GDV, Courtage, Sach, Leben, Kranken, Sonstige, Eingang, Rohdaten
- **Features**:
  - Hintergrund-Download via `BoxDownloadWorker` (QThread)
  - Fortschritts-Dialog mit Abbrechen-Option
  - ZIP-Erstellung mit Komprimierung (ZIP_DEFLATED)
  - Automatische Temp-Verzeichnis-Bereinigung
- **Dateien**:
  - `src/ui/archive_boxes_view.py` → `BoxDownloadWorker`, `BoxSidebar._show_box_context_menu()`, `ArchiveBoxesView._download_box()`
  - `src/i18n/de.py` → Box-Download Texte

### 2c. Verarbeitungs-Ausschluss ✅ (v0.9.5)
- **Zweck**: Manuell bearbeitete Dokumente von der automatischen KI-Verarbeitung ausschliessen
- **Automatischer Ausschluss**:
  - Dokumente die manuell aus der Eingangsbox verschoben werden → `processing_status='manual_excluded'`
  - Dokumente die in der Eingangsbox manuell umbenannt werden → `processing_status='manual_excluded'`
- **Kontextmenue-Optionen**:
  - **"Von Verarbeitung ausschliessen"**: Setzt `processing_status='manual_excluded'` (alle Boxen)
  - **"Erneut fuer Verarbeitung freigeben"**: Verschiebt zurueck in Eingangsbox mit `processing_status='pending'`
- **Document Processor**: Ueberspringt Dokumente mit `processing_status='manual_excluded'` in der Eingangsbox
- **PHP State-Machine**: `manual_excluded` als neuer guelter Status mit Uebergaengen
- **Dateien**:
  - `BiPro-Webspace Spiegelung Live/api/documents.php` → State-Machine + moveDocuments
  - `src/api/documents.py` → `move_documents()` mit optionalem `processing_status`
  - `src/services/document_processor.py` → Filter in `process_inbox()`
  - `src/ui/archive_boxes_view.py` → Auto-Ausschluss + Kontextmenue
  - `src/i18n/de.py` → Verarbeitungs-Ausschluss Texte

### 2d. Tabellen-Vorschau (CSV/Excel) ✅ (v0.9.5)
- **Zweck**: CSV- und Excel-Dateien direkt im Archiv als Tabelle anzeigen
- **Unterstuetzte Formate**:
  - `.csv` - Automatische Delimiter-Erkennung (Komma, Semikolon, Tab, Pipe)
  - `.tsv` - Tab-separierte Dateien
  - `.xlsx` - Moderne Excel-Dateien via openpyxl
  - `.xls` - Hinweis + externes Oeffnen (veraltetes Format)
- **Features**:
  - Automatische Encoding-Erkennung (UTF-8, CP1252, Latin-1)
  - Sheet-Auswahl bei Multi-Sheet Excel-Dateien
  - Performance-Schutz: Max. 5000 Zeilen Vorschau
  - Extern-oeffnen Button fuer vollstaendige Bearbeitung
  - Alternating Row Colors fuer bessere Lesbarkeit
- **Trigger**: Doppelklick, Vorschau-Button, Kontextmenue
- **Dateien**:
  - `src/ui/archive_view.py` → `SpreadsheetViewerDialog`
  - `src/ui/archive_boxes_view.py` → `_is_spreadsheet()`, `_preview_spreadsheet()`
  - `src/i18n/de.py` → Tabellen-Vorschau Texte

### 2e. Admin-/Rechte-/Logging-System ✅ (v0.9.6, Redesign v1.0.9)
- **Zweck**: Umfassendes Logging, granulares Rechte-System und Nutzerverwaltung
- **Kontotypen**: Administrator (alle Rechte) und Benutzer (granulare Rechte)
- **10 Berechtigungen**: vu_connections_manage, bipro_fetch, documents_manage, documents_delete, documents_upload, documents_download, documents_process, documents_history, gdv_edit, smartscan_send
- **Session-Tracking**: Server-seitige Sessions-Tabelle, Admin kann Sessions einsehen/beenden
- **Single-Session-Enforcement**: Pro Nutzer nur eine aktive Session erlaubt, bei Neuanmeldung werden alle bestehenden Sessions automatisch beendet
- **JWT-Gueltigkeit**: 30 Tage (1 Monat), Token + Session laufen nach 30 Tagen ab
- **Activity-Logging**: Jede API-Aktion wird in activity_log-Tabelle geloggt
- **Admin-UI (Redesign v1.0.9)**: Vollbild-Ansicht mit vertikaler Sidebar statt horizontaler Tabs
  - Beim Wechsel in Admin verschwindet die Haupt-Sidebar (BiPRO, Archiv, GDV)
  - Vertikale Navigation links mit 4 Sektionen, getrennt durch orangene Linien:
    - **VERWALTUNG**: Nutzerverwaltung, Sessions, Passwoerter (Panels 0-2)
    - **MONITORING**: Aktivitaetslog, KI-Kosten, Releases (Panels 3-5)
    - **VERARBEITUNG**: KI-Klassifikation (Panel 6), KI-Provider (Panel 7), Modell-Preise (Panel 8), Dokumenten-Regeln (Panel 9) **NEU v2.1.3**
    - **E-MAIL**: E-Mail-Konten, SmartScan-Einstellungen, SmartScan-Historie, E-Mail-Posteingang (Panels 10-13)
    - **KOMMUNIKATION**: Mitteilungen (Panel 14) **NEU v2.0.0**
  - Monochrome `›` Icons in ACENCIA Corporate Design
  - `AdminNavButton` mit Custom-Styling (Primary-900 Hintergrund)
  - "Zurueck zur App" Button oben in der Sidebar
- **Permission Guards**: Buttons in BiPRO/Archiv/GDV deaktiviert bei fehlenden Rechten
- **Dateien**:
  - `BiPro-Webspace Spiegelung Live/api/lib/permissions.php` → Permission-Middleware
  - `BiPro-Webspace Spiegelung Live/api/lib/activity_logger.php` → Zentrales Logging
  - `BiPro-Webspace Spiegelung Live/api/admin.php` → Nutzerverwaltung (nur Admins)
  - `BiPro-Webspace Spiegelung Live/api/sessions.php` → Session-Verwaltung (nur Admins)
  - `BiPro-Webspace Spiegelung Live/api/activity.php` → Aktivitaetslog (nur Admins)
  - `BiPro-Webspace Spiegelung Live/setup/migration_admin.php` → DB-Migration
  - `src/api/admin.py` → AdminAPI Client
  - `src/ui/admin_view.py` → Admin-View mit vertikaler Sidebar + QStackedWidget (15 Panels)
  - `src/ui/main_hub.py` → `_show_admin()` versteckt Haupt-Sidebar, `_leave_admin()` zeigt sie wieder
  - `src/api/auth.py` → User-Model mit account_type, permissions, has_permission()
  - `src/i18n/de.py` → ~80 Admin-/Permission-Texte

### 2f. KI-Kosten-Tracking und -Historie ✅ (v0.9.7)
- **Zweck**: Kosten-Tracking fuer KI-Dokumentenverarbeitung mit verzoegerter Berechnung und Admin-Einsicht
- **Verzoegerter Guthaben-Check**:
  - OpenRouter aktualisiert Guthaben nicht sofort nach API-Calls
  - Nach Verarbeitung: 90 Sekunden warten, dann Guthaben abrufen
  - `DelayedCostWorker` (QThread) mit Countdown-Anzeige im Credits-Label
  - Kosten werden als `batch_cost_update` in processing_history geloggt
- **Admin-Tab "KI-Kosten"** (4. Tab in Admin-View):
  - Statistik-Karten: Gesamtlaeufe, Dokumente, Kosten, Durchschnitte, Erfolgsrate
  - Historie-Tabelle: Datum, Kosten, Kosten/Dok, Dok-Anzahl, Erfolge, Fehler, Dauer, User
  - Zeitraum-Filter: Alle, 7 Tage, 30 Tage, 90 Tage
- **PHP-Endpoints**:
  - `GET /processing_history/costs` - Kosten-Historie aller Verarbeitungslaeufe
  - `GET /processing_history/cost_stats` - Aggregierte Kosten-Statistiken
- **Dateien**:
  - `src/services/document_processor.py` → `log_batch_complete()`, `log_delayed_costs()`
  - `src/ui/archive_boxes_view.py` → `DelayedCostWorker`, `_start_delayed_cost_check()`
  - `src/ui/admin_view.py` → 4. Tab KI-Kosten, `LoadCostDataWorker`
  - `src/api/processing_history.py` → `get_cost_history()`, `get_cost_stats()`
  - `BiPro-Webspace Spiegelung Live/api/processing_history.php` → `getCostHistory()`, `getCostStats()`
  - `src/i18n/de.py` → ~30 neue KI-Kosten Keys

### 2g. Cache- und API-Optimierung ✅ (v0.9.8)
- **Zweck**: Reduzierung der API-Calls fuer bessere Performance und weniger Server-Last
- **Einmal laden, lokal filtern**:
  - Statt pro Box einzeln `GET /documents?box=X` wird einmal `GET /documents` aufgerufen
  - Client-seitig wird nach `box_type` gefiltert
  - Auto-Refresh: 1 API-Call statt 8+ pro 90-Sekunden-Zyklus (87% Reduktion)
- **Vorschau-Performance (3 Optimierungen)**:
  - **filename_override**: `download()` ueberspringt `get_document()` API-Call wenn Filename bekannt (spart 1-3s pro Download)
  - **Persistenter Vorschau-Cache**: `%TEMP%/bipro_preview_cache/` - gleiche Datei wird nur 1x heruntergeladen, danach instant
  - **Cache-Hit ohne Worker**: Bei Cache-Hit wird kein QThread gestartet, kein Progress-Dialog gezeigt - Vorschau oeffnet sofort
  - **Alle Download-Worker optimiert**: PreviewDownloadWorker, MultiDownloadWorker, BoxDownloadWorker, Einzeldownload
- **Box-Wechsel nach Refresh optimiert**:
  - `CacheDocumentLoadWorker` laedt ALLE Dokumente in Cache (1 API-Call), filtert lokal
  - `_should_refresh_box()` prueft zentralen Cache-Zeitstempel statt pro-Box-Tracking
  - Erster Box-Wechsel nach Refresh: 1 API-Call, alle weiteren: instant aus Cache
- **Bulk-Archivierung**:
  - `POST /documents/archive` mit `{"ids": [1,2,3]}` statt N einzelne PUT-Requests
  - `POST /documents/unarchive` analog
  - Fallback auf Einzel-Archivierung bei API-Fehler (Abwaertskompatibilitaet)
- **Client-seitige Stats**:
  - `BoxStats` werden aus dem Dokumente-Cache berechnet statt separater `GET /documents/stats`
  - Fallback auf Server-Endpoint wenn kein Dokumente-Cache vorhanden
- **Dateien**:
  - `src/services/data_cache.py` → `_load_all_documents()`, `_compute_stats_from_cache()`
  - `src/api/documents.py` → `archive_documents()`, `unarchive_documents()` (Bulk-API)
  - `BiPro-Webspace Spiegelung Live/api/documents.php` → `bulkArchiveDocuments()`, `bulkUnarchiveDocuments()`

### 2h. Auto-Update System ✅ (v0.9.9)
- **Zweck**: Automatische Updates an Nutzer verteilen mit Admin-Verwaltung
- **Update-Check**:
  - Beim Login: Synchron nach erfolgreicher Anmeldung
  - Periodisch: Alle 30 Minuten im Hintergrund (UpdateCheckWorker)
- **Drei Modi**:
  - **Optional**: Dialog mit "Jetzt installieren" / "Spaeter"
  - **Pflicht**: Kein Schliessen moeglich, App blockiert bis Update
  - **Veraltet**: Warnung bei deprecated Versionen
- **Installation**: Inno Setup Silent Install (/SILENT /NORESTART)
- **Sicherheit**: SHA256-Hash-Verifikation vor Installation, HTTPS-only
- **Admin-Verwaltung (5. Tab)**:
  - Releases hochladen (EXE direkt im Admin-Bereich)
  - Status aendern: active, mandatory, deprecated, withdrawn
  - Channel zuweisen: stable, beta, internal
  - Mindestversion setzen (alle darunter = Pflicht-Update)
  - Release Notes bearbeiten
  - Download-Zaehler pro Release
  - Loeschen nur bei 0 Downloads (sonst withdrawn)
- **Zentrale Version**: `VERSION`-Datei im Root, gelesen von main.py + build.bat
- **DB-Tabelle**: `releases` mit Version, Channel, Status, SHA256, Dateigroesse, Downloads
- **Dateien**:
  - `VERSION` → Zentrale Versionsdatei
  - `src/services/update_service.py` → UpdateService (check, download, verify, install)
  - `src/ui/update_dialog.py` → UpdateDialog (3 Modi, Progress-Bar)
  - `src/ui/admin_view.py` → 5. Tab Releases (LoadReleasesWorker, UploadReleaseWorker)
  - `src/api/releases.py` → ReleasesAPI Client
  - `src/main.py` → Update-Check nach Login, APP_VERSION aus VERSION-Datei
  - `src/ui/main_hub.py` → Periodischer UpdateCheckWorker (30 Min Timer)
  - `BiPro-Webspace Spiegelung Live/api/releases.php` → CRUD + Public Check
  - `BiPro-Webspace Spiegelung Live/api/index.php` → Routes: /updates/check, /releases/download, /admin/releases, /incoming-scans
  - `BiPro-Webspace Spiegelung Live/setup/migration_releases.php` → DB-Migration
  - `build.bat` → Automatische Version-Sync + SHA256-Generierung
  - `src/i18n/de.py` → ~40 neue Update/Releases Keys

### 2i. Scan-Upload Endpunkt (Power Automate) ✅ (v1.0.2)
- **Zweck**: Eingehende Scan-Dokumente von Microsoft Power Automate / SharePoint empfangen
- **Trigger**: SharePoint-Flow erkennt neue Datei in `/Freigegebene Dokumente/03 Provision`
- **Endpunkt**: `POST /api/incoming-scans`
- **Authentifizierung**: API-Key im Header `X-API-Key` (kein JWT, da externer Aufruf)
- **Request-Body** (JSON):
  - `fileName` (Pflicht): Original-Dateiname
  - `filePath` (Optional): SharePoint-Pfad (nur fuer Logging)
  - `contentType` (Optional): MIME-Type (wird validiert)
  - `fileSize` (Optional): Erwartete Dateigroesse
  - `contentBase64` (Pflicht): Dateiinhalt Base64-kodiert
- **Erlaubte MIME-Types**: PDF, JPG, PNG
- **Ablauf**:
  1. API-Key validieren (timing-safe via `hash_equals()`)
  2. JSON parsen + Pflichtfelder pruefen
  3. MIME-Type gegen Whitelist pruefen (contentType + Extension)
  4. Base64 dekodieren (strict mode)
  5. Dateinamen bereinigen (Path-Traversal-Schutz)
  6. Atomic Write: Staging -> rename() ins Ziel
  7. DB-Insert: `source_type='scan'`, `box_type='eingang'`, `processing_status='pending'`
  8. Activity-Logging mit SharePoint-Pfad als Metadatum
- **Integration**: Dokumente landen in Eingangsbox -> automatische KI-Verarbeitung
- **Sicherheit**: MIME-Whitelist, Path-Traversal-Schutz, Base64-strict, 50 MB Limit, SHA256-Hash
- **Dateien**:
  - `BiPro-Webspace Spiegelung Live/api/incoming_scans.php` → Scan-Upload Handler
  - `BiPro-Webspace Spiegelung Live/api/config.php` → `SCAN_API_KEY`, `SCAN_ALLOWED_MIME_TYPES`
  - `BiPro-Webspace Spiegelung Live/api/index.php` → Route `incoming-scans`
  - `BiPro-Webspace Spiegelung Live/api/documents.php` → `source_type='scan'` in Validierung

### 2j. Dokumenten-Farbmarkierung ✅ (v1.0.3)
- **Zweck**: Dokumente im Archiv farblich markieren fuer visuelle Organisation
- **8 Farben** (blasse, nicht grelle Toene):
  - Gruen (#c8e6c9), Rot (#ffcdd2), Blau (#bbdefb), Orange (#ffe0b2)
  - Lila (#e1bee7), Pink (#f8bbd0), Tuerkis (#b2ebf2), Gelb (#fff9c4)
- **Persistenz**: Farbe bleibt erhalten bei:
  - Verschieben zwischen Boxen
  - Archivieren / Entarchivieren
  - KI-Verarbeitung / Umbenennung
  - Erneute Verarbeitungsfreigabe
  - Farbe wird NUR durch explizite Aenderung oder Entfernung geaendert
- **UI**:
  - Kontextmenue: "Farbe setzen" Untermenue mit farbigen Icons
  - Multi-Selection: Farbe fuer mehrere Dokumente gleichzeitig setzen
  - Tabellenzeilen erhalten blasse Hintergrundfarbe
  - "Farbe entfernen" Option wenn Dokument bereits gefaerbt
  - **Async via DocumentColorWorker** (QThread): Bulk-API-Call blockiert nicht den UI-Thread
  - **Inkrementeller Tabellen-Refresh**: `_update_row_colors()` aktualisiert nur betroffene Zeilen statt Full-Rebuild
- **API**:
  - `PUT /documents/{id}` mit `display_color` Feld
  - `POST /documents/colors` fuer Bulk-Farbmarkierung (analog /documents/archive)
- **Dateien**:
  - `BiPro-Webspace Spiegelung Live/api/documents.php` → `display_color` in allowedFields + `bulkSetDocumentColors()`
  - `src/api/documents.py` → `Document.display_color` + `set_document_color()` + `set_documents_color()`
  - `src/ui/styles/tokens.py` → `DOCUMENT_DISPLAY_COLORS` (8 blasse Farben)
  - `src/ui/archive_boxes_view.py` → Kontextmenue + `_populate_table()` Hintergrundfarbe + `_set_document_color()`
  - `src/i18n/de.py` → ~13 neue Farbmarkierungs-Keys
  - DB: `documents.display_color VARCHAR(20) NULL DEFAULT NULL`

### 2k. Globales Drag & Drop Upload ✅ (v1.0.4)
- **Zweck**: Dateien und Ordner per Drag & Drop aus dem Explorer direkt ins App-Fenster ziehen → Eingangsbox
- **Trigger**: Dateien/Ordner auf das Hauptfenster ziehen (funktioniert in jedem Bereich: BiPRO, Archiv, GDV, Admin)
- **Voraussetzungen**: Benutzer muss angemeldet sein + Recht `documents_upload` besitzen
- **Ordner-Support**: Ordner werden rekursiv durchlaufen (alle Dateien, keine versteckten)
- **MSG-Support**: Outlook .msg Dateien werden automatisch verarbeitet (siehe 2l)
- **Outlook-Direct-Drop**: E-Mails direkt aus Outlook ziehen (OLE FileGroupDescriptorW/FileContents)
- **Features**:
  - Globales Drop auf `MainHub` Fenster (unabhaengig vom aktiven Bereich)
  - Permission-Check vor Upload (`documents_upload`)
  - `DropUploadWorker` (QThread) fuer nicht-blockierenden Upload
  - Toast-Benachrichtigung mit Rueckgaengig-Option (Dokumente wieder entfernen)
  - Auto-Refresh-Pause waehrend Upload
  - Archiv-View wird nach Upload automatisch aktualisiert
  - **Outlook-Drag**: E-Mails direkt aus Outlook ziehen → COM-Automation (pywin32) → SaveAs .msg → Pipeline
  - COM holt die aktuell in Outlook ausgewaehlten E-Mails (Einzel- und Mehrfachauswahl)
  - Temporaere Outlook-Dateien werden nach Upload automatisch aufgeraeumt
- **Abhaengigkeit**: `pywin32>=306` (Windows COM-Automation fuer Outlook-Zugriff)
- **Dateien**:
  - `src/ui/main_hub.py` → `DropUploadWorker`, `dragEnterEvent()`, `dropEvent()`, `_has_outlook_data()`, `_extract_outlook_emails()`, `_collect_files_from_paths()`, `_start_drop_upload()`
  - `src/i18n/de.py` → ~10 neue Drag & Drop Upload Keys

### 2l. Outlook MSG E-Mail-Verarbeitung ✅ (v1.0.4)
- **Zweck**: .msg E-Mails automatisch verarbeiten - Anhaenge extrahieren, E-Mail ins Roh-Archiv
- **Trigger**: .msg Datei hochladen (Drag & Drop ODER Upload-Button im Archiv)
- **Ablauf**:
  1. .msg Datei wird erkannt (Endung .msg)
  2. Anhaenge werden mit `extract-msg` Bibliothek extrahiert
  3. Jeder Anhang wird einzeln in die **Eingangsbox** hochgeladen (→ KI-Verarbeitung)
  4. Die .msg Datei selbst geht in den **Roh-Ordner**
  5. Temporaere Dateien werden nach Upload aufgeraeumt
- **Ohne Anhaenge**: .msg geht nur ins Roh-Archiv
- **Abhaengigkeit**: `extract-msg>=0.50.0` (in requirements.txt)
- **Dateien**:
  - `src/services/msg_handler.py` → `is_msg_file()`, `extract_msg_attachments()`, `MsgExtractResult`
  - `src/ui/archive_boxes_view.py` → `MultiUploadWorker.run()` mit MSG-Handling
  - `src/ui/main_hub.py` → `DropUploadWorker.run()` mit MSG-Handling
  - `src/i18n/de.py` → ~4 neue MSG-Keys
  - `requirements.txt` → `extract-msg>=0.50.0`

### 2m. PDF Passwortschutz-Entsperrung ✅ (v1.0.4, DB-Passwoerter v1.0.5)
- **Zweck**: Passwortgeschuetzte PDFs automatisch entsperren beim Upload
- **Trigger**: Jeder PDF-Upload (Button, Drag & Drop, E-Mail-Anhang, ZIP-Extraktion)
- **Passwoerter**: Dynamisch aus DB-Tabelle `known_passwords` (Typ: pdf), Fallback auf hartcodierte Liste
- **Ablauf**:
  1. Vor dem Upload wird jede PDF mit PyMuPDF (`fitz`) geprueft
  2. Wenn `is_encrypted`: Passwoerter aus DB laden (gecacht pro Session)
  3. Bei Treffer: PDF ohne Passwort ueberschreiben (`PDF_ENCRYPT_NONE`)
  4. Die ungeschuetzte PDF wird hochgeladen (KI-Verarbeitung + Download funktionieren)
  5. Wenn kein Passwort passt: Fehlermeldung, Upload wird uebersprungen
- **Integrationspunkte** (3 Stellen):
  - `MultiUploadWorker.run()` in `archive_boxes_view.py` (Button-Upload)
  - `DropUploadWorker.run()` in `main_hub.py` (Drag & Drop)
  - `extract_msg_attachments()` in `msg_handler.py` (E-Mail-Anhaenge)
- **Keine neue Abhaengigkeit**: PyMuPDF (`fitz`) ist bereits in requirements.txt
- **Dateien**:
  - `src/services/pdf_unlock.py` → `unlock_pdf_if_needed()`, `get_known_passwords()`, `clear_password_cache()`
  - `src/ui/archive_boxes_view.py` → Unlock vor Upload in MultiUploadWorker
  - `src/ui/main_hub.py` → Unlock vor Upload in DropUploadWorker
  - `src/services/msg_handler.py` → Unlock nach PDF-Extraktion aus .msg

### 2n. ZIP-Entpackung beim Upload ✅ (v1.0.5)
- **Zweck**: ZIP-Dateien beim Upload automatisch entpacken, Inhalt in Eingangsbox, ZIP ins Roh-Archiv
- **Trigger**: ZIP-Datei hochladen (Button, Drag & Drop, E-Mail-Anhang)
- **Passwortgeschuetzte ZIPs**: Passwoerter aus DB-Tabelle `known_passwords` (Typ: zip)
- **Unterstuetzte Verschluesselung**: Standard-PKZIP + AES-256 (via pyzipper)
- **Rekursive Verarbeitung**: ZIPs in ZIPs (max. 3 Ebenen), MSGs in ZIPs, PDFs in ZIPs
- **Ablauf**:
  1. ZIP-Datei wird erkannt (Endung .zip)
  2. Entpacken (ggf. mit Passwort aus DB)
  3. Extrahierte Dateien rekursiv verarbeiten:
     - PDFs → entsperren + Eingangsbox
     - MSGs → Anhaenge extrahieren → Eingangsbox, MSG → Roh
     - ZIPs → rekursiv entpacken
     - Sonstige → Eingangsbox
  4. ZIP selbst → Roh-Archiv
- **Abhaengigkeit**: `pyzipper>=0.3.6` (AES-256 ZIP-Support)
- **Dateien**:
  - `src/services/zip_handler.py` → `is_zip_file()`, `extract_zip_contents()`, `ZipExtractResult`
  - `src/ui/archive_boxes_view.py` → `MultiUploadWorker.run()` mit ZIP-Handling
  - `src/ui/main_hub.py` → `DropUploadWorker.run()` mit ZIP-Handling
  - `src/services/msg_handler.py` → ZIP-Anhaenge aus E-Mails durchlassen
  - `src/i18n/de.py` → ~6 neue ZIP-Keys
  - `requirements.txt` → `pyzipper>=0.3.6`

### 2o. Zentrale Passwort-Verwaltung (Admin) ✅ (v1.0.5)
- **Zweck**: PDF- und ZIP-Passwoerter zentral in der Datenbank verwalten statt hartcodiert
- **DB-Tabelle**: `known_passwords` mit `password_type` ENUM('pdf','zip'), `password_value`, `description`, `is_active`
- **PHP API**:
  - Oeffentlich: `GET /passwords?type=pdf|zip` (JWT, aktive Passwoerter)
  - Admin: `GET/POST/PUT/DELETE /admin/passwords` (CRUD, Soft-Delete)
- **Python API Client**: `src/api/passwords.py` → `PasswordsAPI`
- **Session-Cache**: Passwoerter werden einmal pro Session geladen, Cache wird bei Admin-Aenderung geleert
- **Admin-Tab 6** in Admin-View:
  - Tabelle mit Typ, Passwort (maskiert), Beschreibung, Erstellt am, Aktiv-Status
  - Anzeigen/Verbergen Toggle fuer Passwort-Werte
  - Hinzufuegen-Dialog mit Typ-Auswahl
  - Bearbeiten, Deaktivieren, Reaktivieren
  - Typ-Filter (Alle/PDF/ZIP)
- **Seed-Daten**: 4 bekannte PDF-Passwoerter (in DB gespeichert, nicht im Code)
- **Dateien**:
  - `BiPro-Webspace Spiegelung Live/api/passwords.php` → PHP API (Public + Admin)
  - `BiPro-Webspace Spiegelung Live/api/index.php` → Route-Registrierung
  - `src/api/passwords.py` → Python API Client
  - `src/services/pdf_unlock.py` → `get_known_passwords()`, `clear_password_cache()` (dynamisch)
  - `src/ui/admin_view.py` → Tab 6 Passwoerter + `_PasswordDialog`
  - `src/i18n/de.py` → ~35 neue Passwort-Verwaltungs-Keys
  - DB: `known_passwords` Tabelle (Migration 009)

### 2p. Smart!Scan E-Mail-Versand ✅ (v1.0.6)
- **Zweck**: Dokumente (einzeln oder ganze Boxen) per E-Mail an eine konfigurierbare SCS-SmartScan Adresse senden
- **E-Mail-Konten**: SMTP/IMAP Konten mit AES-256-GCM verschluesselten Credentials in DB
- **Versandmodi**: Einzeln (1 Mail pro Dokument) oder Sammelmail (mehrere Docs pro Mail, mit Batch-Splitting)
- **Post-Send-Aktionen**: Dokumente nach Versand archivieren und/oder umfaerben (konfigurierbar, unabhaengig)
- **Idempotenz**: `client_request_id` verhindert Doppelversand (10 Min Fenster)
- **Client-seitiges Chunking**: Max. 10 Dokumente pro API-Call gegen PHP-Timeout
- **Revisionssichere Historie**: Jeder Versand wird mit Dokumenten, SHA256-Hashes, SMTP Message-IDs geloggt
- **PHPMailer v6.9.3**: Robuster SMTP-Versand mit TLS auf Shared Hosting
- **DB-Tabellen**: `email_accounts`, `smartscan_settings`, `smartscan_jobs`, `smartscan_job_items`, `smartscan_emails`
- **UI-Integration**:
  - Admin Panel 10: E-Mail-Konten Verwaltung (CRUD + SMTP-Verbindungstest)
  - Admin Panel 11: SmartScan Einstellungen (Zieladresse, Templates, Modi, Limits, Post-Send-Aktionen)
  - Admin Panel 12: SmartScan Versandhistorie (Filter, Details mit Items + Emails)
  - Gruener Smart!Scan-Toolbar-Button im Archiv (sichtbar nur wenn SmartScan aktiviert)
  - Kontextmenue: "Smart!Scan" in Box-Sidebar und Dokument-Tabelle (Einzel-/Mehrfachauswahl)
  - Einfache Bestaetigung per QMessageBox (kein Dialog), Einstellungen aus Admin-Config
- **Permission**: `smartscan_send` Berechtigung fuer Versand
- **Dateien**:
  - `BiPro-Webspace Spiegelung Live/api/lib/PHPMailer/` → PHPMailer v6.9.3 (3 Dateien)
  - `BiPro-Webspace Spiegelung Live/api/smartscan.php` → Settings + Send + Chunk + Historie
  - `BiPro-Webspace Spiegelung Live/api/email_accounts.php` → Admin CRUD + SMTP-Test + IMAP-Polling
  - `BiPro-Webspace Spiegelung Live/setup/010_smartscan_email.php` → DB-Migration (7 Tabellen)
  - `BiPro-Webspace Spiegelung Live/api/index.php` → Neue Routes
  - `src/api/smartscan.py` → `SmartScanAPI` + `EmailAccountsAPI` Clients
  - `src/ui/admin_view.py` → 4 neue Tabs (7-10)
  - `src/ui/archive_boxes_view.py` → `SmartScanWorker`, `_SmartScanDialog`, Kontextmenue
  - `src/i18n/de.py` → ~120 neue Keys (SMARTSCAN_, EMAIL_ACCOUNT_, EMAIL_INBOX_)

### 2q. IMAP E-Mail-Import ✅ (v1.0.6)
- **Zweck**: Anhaenge aus empfangenen E-Mails automatisch in die Eingangsbox importieren
- **Hybridansatz**: PHP pollt IMAP + speichert Anhaenge in Staging, Python verarbeitet (PDF-Unlock, ZIP-Extract)
- **Konfigurierbare Filter**:
  - Alle Mails oder nur mit Keyword "ATLASabruf" im Betreff/Body
  - Alle Absender oder nur Whitelist
- **Manuell und automatisch**: Button "Postfach abrufen" in Admin oder "Mails abholen" im BiPRO-Bereich
- **DB-Tabellen**: `email_inbox`, `email_inbox_attachments` (mit import_status Tracking)
- **UI**: Admin Panel 12 "E-Mail Posteingang" (Tabelle, Kontextmenue, Detail-Dialog)
- **IMAP-Import-Einstellungen**: Integriert in SmartScan-Settings-Panel (Sektion "E-Mail-Import")
- **Sicherheit**: IMAP TLS, Staging-Cleanup, Absender-Whitelist, MIME-Validierung, SHA256-Hashes
- **Dateien**:
  - `BiPro-Webspace Spiegelung Live/api/email_accounts.php` → IMAP-Polling + Inbox-Endpoints
  - `src/api/smartscan.py` → `EmailAccountsAPI` mit IMAP-Methoden
  - `src/ui/admin_view.py` → Panel 12 IMAP Inbox + Settings-Integration
  - `src/ui/bipro_view.py` → `MailImportWorker`, `_fetch_mails()` (BiPRO-Button)
  - `src/i18n/de.py` → EMAIL_INBOX_, IMAP_IMPORT_ und BIPRO_MAIL_FETCH_ Keys

### 2s. Mail-Import im BiPRO-Bereich ✅ (v1.0.9)
- **Zweck**: IMAP-Mails direkt aus dem BiPRO-Datenabruf-Bereich abholen und Anhaenge importieren
- **Trigger**: Gruener "Mails abholen" Button in der BiPRO-Toolbar (ersetzt den alten "Lieferungen abrufen" Button)
- **Ablauf**:
  1. IMAP-Konto ermitteln (aus SmartScan-Settings `imap_poll_account_id`, Fallback auf erstes aktives IMAP-Konto)
  2. Phase 1: IMAP-Poll (Server-seitig) - Neue Mails abrufen, Anhaenge in Staging speichern
  3. Phase 2: Pending Attachments herunterladen und verarbeiten:
     - ZIP → `extract_zip_contents()` (rekursiv, mit Passwort-Support)
     - MSG → `extract_msg_attachments()` (Anhaenge extrahieren)
     - PDF → `unlock_pdf_if_needed()` (Passwortschutz entfernen)
  4. Verarbeitete Dateien in Eingangsbox hochladen (ZIP/MSG-Originale → Roh-Archiv)
  5. Anhaenge als importiert markieren
- **Parallele Uploads**: ThreadPoolExecutor mit max. 4 Workern, per-Thread API-Client (thread-safe)
- **Progress-Toast**: Zweiphasig mit `ProgressToastWidget`:
  - Phase 1: "Postfach abrufen..." (kein Balken, Server-seitig)
  - Phase 2: "Anhaenge importieren" (Fortschrittsbalken pro Anhang)
- **Nicht-blockierend**: App bleibt waehrend des Imports voll bedienbar
- **Dateien**:
  - `src/ui/bipro_view.py` → `MailImportWorker` (QThread), `_fetch_mails()`, `_on_mail_phase_changed()`
  - `src/ui/toast.py` → `ProgressToastWidget`, `ToastManager.show_progress()`
  - `src/i18n/de.py` → BIPRO_MAIL_FETCH_* Keys (8 Stueck)

### 2r. Tastenkuerzel im Dokumentenarchiv ✅ (v1.0.8)
- **Zweck**: Effiziente Bedienung des Archivs per Tastatur
- **Implementierte Kuerzel**:
  | Taste | Aktion | Kontext-Sensitivitaet |
  |-------|--------|----------------------|
  | F2 | Umbenennen | Nur bei genau 1 Dokument |
  | Entf | Loeschen | Nicht im Suchfeld |
  | Strg+A | Alle auswaehlen | Im Suchfeld: Text auswaehlen |
  | Strg+D | Download | Oeffnet Ordner-Dialog |
  | Strg+F | Suchen | Fokus auf Suchfeld, Text selektiert |
  | Strg+U | Upload | Oeffnet Datei-Dialog |
  | Enter | Vorschau | Nicht in Suchfeld/ComboBox |
  | Esc | Auswahl aufheben | Im Suchfeld: erst Text leeren |
  | Strg+Shift+A | Archivieren | Bulk-Archivierung |
  | F5 | Aktualisieren | Server-Reload erzwingen |
- **Kontext-Scope**: `WidgetWithChildrenShortcut` - Shortcuts nur aktiv wenn Archiv sichtbar
- **Fokus-Handling**: Intelligente Erkennung ob Suchfeld/ComboBox fokussiert → Standard-Verhalten beibehalten
- **Button-Tooltips**: Alle Archiv-Buttons zeigen Shortcut-Hinweis im Tooltip
- **Dateien**:
  - `src/ui/archive_boxes_view.py` → `_setup_shortcuts()`, 7 `_shortcut_*` Handler
  - `src/i18n/de.py` → ~16 neue SHORTCUT_ Keys

### 2t. Duplikat-Erkennung (Dokumentenarchiv) ✅ (v1.1.1, Rich-Tooltip v2.1.0, Navigation+Vergleich v2.1.0)
- **Zweck**: Doppelte Dokumente anhand der SHA256-Prüfziffer erkennen, visuell markieren, navigieren und vergleichen
- **Erkennung**: Server berechnet SHA256-Hash beim Upload, vergleicht gegen ALLE Dokumente (inkl. archivierte)
- **Verhalten**: Duplikate werden trotzdem hochgeladen, aber als Dopplung markiert (version > 1)
- **Visuelle Markierung**: Eigene Spalte (Spalte 0) in der Archiv-Tabelle mit Warn-Icon (⚠)
- **Rich-Tooltip (NEU v2.1.0)**: Beim Hover ueber Duplikat-Icon wird eine HTML-Kachel angezeigt mit:
  - Dateiname des Originals (fett)
  - Box-Emoji + Box-Name | Datum (DD.MM.YYYY) | ggf. "Archiviert"
  - ID in dezenter Schrift
  - Gilt fuer Datei-Duplikate UND Inhaltsduplikate
- **Zum Gegenstueck springen (NEU v2.1.0)**:
  - Klick auf Duplikat-Icon in der Tabelle springt zur Box des Gegenstuecks und selektiert es
  - Kontextmenue-Eintrag "Zum Gegenstueck springen" (nur bei Duplikaten)
  - Nutzt `_jump_to_counterpart()` mit Box-Wechsel + `_pending_select_doc_id`-Pattern
- **Vergleichsansicht (NEU v2.1.0)**:
  - `DuplicateCompareDialog` zeigt beide Dokumente side-by-side
  - Kontextmenue-Eintrag "Duplikat vergleichen" (nur bei Duplikaten)
  - PDF-Vorschau beider Dokumente (paralleler Download via PreviewDownloadWorker)
  - Aktions-Buttons pro Seite: Loeschen, Archivieren/Entarchivieren, Verschieben (Box-Menue), Farbe (8 Farben)
  - Nach Aktion: Seite wird visuell deaktiviert mit Status-Label
  - Beim Schliessen: `documents_changed` Signal triggert `_refresh_all()` in ArchiveBoxesView
- **Toast-Benachrichtigung**: Bei Upload-Erkennung wird Info-Toast angezeigt
- **PHP-Seite**: `listDocuments()` liefert `content_hash`, `version`, `previous_version_id`, `duplicate_of_filename`, `duplicate_of_box_type`, `duplicate_of_created_at`, `duplicate_of_is_archived` (+ analog fuer Content-Duplikate)
- **Python-Seite**: `Document` Dataclass hat 6 Duplikat-Metadaten-Felder (box_type, created_at, is_archived fuer Datei- und Content-Duplikate)
- **Dateien**:
  - `BiPro-Webspace Spiegelung Live/api/documents.php` → `listDocuments()` + `searchDocuments()` + `getDocument()` LEFT JOIN mit Metadaten
  - `src/api/documents.py` → `Document` mit 6 neuen Duplikat-Feldern, `from_dict()` Parsing
  - `src/ui/archive_view.py` → `DuplicateCompareDialog` (Side-by-Side-Vergleich mit PDF-Vorschau + Aktionen)
  - `src/ui/archive_boxes_view.py` → `_on_table_clicked()` (Jump), `_jump_to_counterpart()`, `_open_duplicate_compare()`, Kontextmenue-Erweiterung, `DocumentTableModel._build_duplicate_tooltip()` (Rich-HTML)
  - `src/ui/main_hub.py` → Duplikat-Toast in `_on_drop_upload_finished()`
  - `src/i18n/de.py` → DUPLICATE_* + CONTENT_DUPLICATE_* + DUPLICATE_COMPARE_* Keys (~35 Stueck)

### 2u. Dokument-Historie (Seitenpanel) ✅ (v1.1.2)
- **Zweck**: Aenderungshistorie einzelner Dokumente als Seitenpanel im Archiv anzeigen
- **Berechtigung**: Neue Berechtigung `documents_history` (Admin kann zuweisen)
- **Trigger**: Klick auf ein einzelnes Dokument in der Tabelle (Debounce 300ms)
- **Panel-Aufbau**: Rechts neben der Dokumenten-Tabelle (QSplitter), max. 400px breit
  - Header mit Dokumentname + Schliessen-Button
  - Scrollbare Liste von farbcodierten Historie-Eintraegen
  - Jeder Eintrag: Zeitstempel (DD.MM. HH:MM), Benutzername, Aktion
- **Farbkodierte Aktionen**:
  - Blau: Verschiebungen (move, box_type-Aenderung)
  - Gruen: Downloads
  - Grau: Uploads
  - Rot: Loeschungen
  - Orange: Archivierung/Entarchivierung
  - Lila: Farbmarkierungs-Aenderungen
  - Indigo: Sonstige Updates (Umbenennung, Statusaenderung)
  - Cyan: KI-Klassifikation
- **Datenquelle**: `activity_log`-Tabelle via neuer Endpoint `GET /documents/{id}/history`
- **Performance**: 
  - Client-seitiger Cache (60s TTL)
  - Debounce-Timer (300ms) verhindert Ueberlastung bei schnellem Durchklicken
  - Asynchroner Worker (DocumentHistoryWorker) blockiert nicht die UI
- **Logging-Verbesserung**: Bulk-Moves loggen jetzt pro Dokument (mit source_box + target_box)
- **DB-Migration**: `012_add_documents_history_permission.php` fuegt Berechtigung ein
- **Dateien**:
  - `BiPro-Webspace Spiegelung Live/api/documents.php` → `getDocumentHistory()`, verbessertes Move/Update-Logging
  - `BiPro-Webspace Spiegelung Live/api/index.php` → Route `/documents/{id}/history`
  - `BiPro-Webspace Spiegelung Live/setup/012_add_documents_history_permission.php` → DB-Migration
  - `src/api/documents.py` → `DocumentsAPI.get_document_history()`
  - `src/ui/archive_boxes_view.py` → `DocumentHistoryPanel`, `DocumentHistoryWorker`, QSplitter-Integration
  - `src/i18n/de.py` → HISTORY_* Keys (~20 Stueck)

### 2v. PDF-Bearbeitung in der Vorschau ✅ (v1.1.3, Multi-Selection v2.1.3)
- **Zweck**: PDFs direkt im Vorschau-Dialog bearbeiten (Seiten drehen, loeschen) und gespeichert zurueck auf den Server schreiben
- **Berechtigungen**: `documents_manage` (bestehend) fuer das Ersetzen der Datei auf dem Server
- **Trigger**: PDF-Vorschau im Dokumentenarchiv oeffnen (automatisch im Bearbeitungsmodus)
- **Bearbeitungs-Funktionen**:
  - **Seite rechts drehen** (↻, 90° CW) - Einzel- oder Mehrfachauswahl
  - **Seite links drehen** (↺, 90° CCW) - Einzel- oder Mehrfachauswahl
  - **Seite loeschen** (🗑, mit Bestaetigungsdialog, mindestens 1 Seite muss verbleiben) - Einzel- oder Mehrfachauswahl
  - **Speichern**: Bearbeitetes PDF auf den Server hochladen
- **Multi-Selection (NEU v2.1.3)**:
  - `ExtendedSelection` Modus in Thumbnail-Sidebar (Strg+Klick, Shift+Klick, Strg+A)
  - Statuszeile zeigt "X von Y Seiten ausgewählt" bei Mehrfachauswahl
  - Drehen wirkt auf alle ausgewaehlten Seiten gleichzeitig
  - Loeschen mit Bestaetigungsdialog ("{count} Seiten wirklich löschen?")
  - Auswahl wird nach Aktionen wiederhergestellt
- **Auto-Refresh nach Speichern (NEU v2.1.3)**:
  - `PDFRefreshWorker` (QThread) aktualisiert im Hintergrund nach erfolgreichem Speichern:
    - Leere-Seiten-Erkennung (`get_empty_pages()`) → `empty_page_count`/`total_page_count` Update
    - Text-Extraktion (`extract_and_save_text()`) → `document_ai_data` Update
  - Status "Aktualisiere Dokumentdaten..." waehrend Refresh
- **Architektur**:
  - `QPdfView` (Qt6 native) zeigt das PDF an (read-only Darstellung)
  - `PyMuPDF` (fitz) fuehrt die Manipulationen durch (Drehen, Loeschen)
  - Aenderungen werden in temp-Datei gespeichert, QPdfView wird daraus neu geladen
  - Thumbnail-Sidebar (QListWidget) zeigt Seitenvorschauen (PyMuPDF-gerendert, 150px)
- **Server-Endpoint**: `POST /documents/{id}/replace`
  - Nimmt eine Datei entgegen und ersetzt die bestehende am gleichen `storage_path`
  - `content_hash` und `file_size` werden serverseitig neu berechnet
  - Activity-Log: `file_replaced` mit altem/neuem Hash und Groesse
- **Cache-Invalidierung nach Speichern**:
  - Lokaler Vorschau-Cache (`%TEMP%/bipro_preview_cache/`) wird fuer das Dokument geloescht
  - Dokument-Historie-Cache wird invalidiert
  - Dokumente-Liste wird vom Server neu geladen
- **Abwaertskompatibilitaet**: `PDFViewerDialog` ohne `doc_id`/`docs_api`/`editable` Parameter verhalt sich exakt wie bisher (read-only)
- **Dateien**:
  - `BiPro-Webspace Spiegelung Live/api/documents.php` → `replaceDocumentFile()` + Route in `handleDocumentsRequest()`
  - `src/api/documents.py` → `DocumentsAPI.replace_document_file()`
  - `src/ui/archive_view.py` → `PDFViewerDialog` (erweitert), `PDFSaveWorker`
  - `src/ui/archive_boxes_view.py` → `_on_pdf_saved()`, editable-Aufruf in `_on_preview_download_finished()`
  - `src/i18n/de.py` → PDF_EDIT_* Keys (~14 Stueck)

### 2w. App-Schließ-Schutz ✅ (v1.1.4)
- **Zweck**: App-Schließen verhindern solange kritische Hintergrundoperationen laufen
- **Blockierende Operationen**:
  - `ProcessingWorker` laeuft (KI-Dokumentenverarbeitung aktiv)
  - `DelayedCostWorker` laeuft (KI-Kosten-Ermittlung, Guthaben-Abfrage ausstehend)
  - `SmartScanWorker` laeuft (Smart!Scan E-Mail-Versand aktiv)
- **Verhalten**: `event.ignore()` + Toast-Warnung mit Auflistung der blockierenden Operationen
- **Harter Block**: Kein "Trotzdem beenden?" - Datenverlust/inkonsistente Kosten werden verhindert
- **Architektur**: `ArchiveBoxesView.get_blocking_operations()` liefert Liste, `MainHub.closeEvent()` prueft vor allen anderen Checks
- **Dateien**:
  - `src/ui/archive_boxes_view.py` → `get_blocking_operations()` (neue Methode)
  - `src/ui/main_hub.py` → `closeEvent()` erweitert um Blocking-Check
  - `src/i18n/de.py` → CLOSE_BLOCKED_* Keys (4 Stueck)

### 2y. Leere-Seiten-Erkennung (PDF) ✅ (v2.0.2)
- **Zweck**: Komplett leere und inhaltslose Seiten in PDFs erkennen und im Archiv kennzeichnen
- **4-Stufen-Algorithmus** (Performance-optimiert, bricht frueh ab):
  1. **Text pruefen** (schnell, ~80% der Faelle): `page.get_text("text").strip()`
  2. **Vektor-Objekte pruefen**: `page.get_drawings()` (Linien, Tabellen, Rahmen)
  3. **Bilder pruefen**: `page.get_images(full=True)` (kein Text + keine Vektoren + keine Bilder = leer)
  4. **Pixel-Analyse** (50 DPI, nur bei Bild-Seiten): Durchschnitts-Helligkeit + Standardabweichung
- **Verhalten**: Rein informativ -- Normale Verarbeitung (KI, Benennung, Box-Zuweisung) laeuft IMMER weiter
- **DB-Spalten**: `empty_page_count INT NULL`, `total_page_count INT NULL` in documents-Tabelle
- **Interpretation**: NULL = nicht geprueft, 0/N = keine leeren Seiten, M/N = teilweise, N/N = komplett leer
- **Archiv-Tabelle**: Eigene Spalte (Spalte 1) mit Icons:
  - Leerer Kreis (○) rot: Komplett leer
  - Halb-Kreis (◑) orange: Teilweise leere Seiten
  - Tooltip mit Details ("3 von 8 Seiten leer" / "Komplett leer (5 Seiten)")
- **History-Logging**: `empty_pages_detected` Aktion mit Details (Indizes, Anzahl)
- **Performance**: ~5-20ms/Seite (Stufe 4), typisches 10-Seiten-PDF unter 200ms
- **Phase 2 (geplant)**: Admin-Einstellungen fuer Behandlungsoptionen (Loeschen, Farbe, Verschieben)
- **Dateien**:
  - `src/services/empty_page_detector.py` → `is_page_empty()`, `get_empty_pages()`, `_is_pixmap_blank()`
  - `src/services/document_processor.py` → `_check_and_log_empty_pages()` (3 PDF-Zweige)
  - `src/api/documents.py` → `Document.empty_page_count`, `total_page_count`, `has_empty_pages`, `is_completely_empty`
  - `src/ui/archive_boxes_view.py` → `COL_EMPTY_PAGES` Spalte im `DocumentTableModel`
  - `src/i18n/de.py` → EMPTY_PAGES_* Keys (8 Stueck)
  - `BiPro-Webspace Spiegelung Live/api/documents.php` → SELECT + allowedFields erweitert
  - `BiPro-Webspace Spiegelung Live/setup/016_empty_page_detection.php` → DB-Migration

### 2z. Volltext + KI-Daten-Persistierung ✅ (v2.0.2, Content-Duplikate v2.0.3)
- **Zweck**: Pro Dokument den vollstaendigen extrahierten PDF-Text und die KI-Klassifikations-Rohantwort speichern
- **Separate Tabelle**: `document_ai_data` (1:1 zu documents, NIEMALS in listDocuments() gejoined)
- **DB-Spalten**:
  - `extracted_text` (MEDIUMTEXT): Volltext aller Seiten, mit FULLTEXT-Index
  - `extracted_text_sha256`: SHA256 des Textes (fuer Content-Duplikat-Erkennung)
  - `extraction_method`: text/ocr/mixed/none
  - `extracted_page_count`: Seiten mit tatsaechlichem Text
  - `ai_full_response` (LONGTEXT): KI-Rohantwort (JSON als String)
  - `ai_prompt_text` (MEDIUMTEXT): Verwendeter Prompt
  - `ai_model`: Modell-ID (z.B. openai/gpt-4o-mini)
  - `ai_prompt_version`: Prompt-Version (z.B. v2.0.2)
  - `ai_stage`: triage_only/triage_and_detail/courtage_minimal/none
  - `prompt_tokens`, `completion_tokens`, `total_tokens`: Token-Verbrauch
  - `text_char_count`, `ai_response_char_count`: Zeichenanzahl fuer Analyse
- **Integration**: Nachgelagerter Schritt im document_processor nach Archive, Fehler bricht nichts ab
- **Volltext-Extraktion**: Alle Seiten via PyMuPDF (nicht nur 2-5 wie fuer KI), ~5-50ms
- **Token-Durchreichung**: _usage/_raw_response/_prompt_text in classify_*-Funktionen (openrouter.py)
- **5 Performance-Regeln**: Keine Auto-Joins, kein SELECT*, API strikt getrennt, kein DB-Trigger, kein Lazy-Load im UI
- **CASCADE-Delete**: document_ai_data wird bei Dokument-Loeschung mitgeloescht (DSGVO)
- **Zukunfts-Features**: Volltextsuche, Analyse-Service, Embeddings, Cross-Dokument-Analysen
- **Dateien**:
  - `BiPro-Webspace Spiegelung Live/setup/017_document_ai_data.php` → DB-Migration
  - `BiPro-Webspace Spiegelung Live/api/documents.php` → POST/GET /documents/{id}/ai-data + CASCADE-Delete
  - `src/api/documents.py` → `save_ai_data()`, `get_ai_data()`, `get_missing_ai_data_documents()`
  - `src/api/openrouter.py` → _usage/_raw_response/_prompt_text in classify_*-Funktionen
  - `src/services/document_processor.py` → `_extract_full_text()`, `_persist_ai_data()`
  - `src/i18n/de.py` → AI_DATA_* Keys (5 Stueck)

### 2aa. Content-Duplikat-Erkennung (Inhaltsduplikate) ✅ (v2.0.3)
- **Zweck**: Dokumente mit identischem Inhalt erkennen (auch wenn Dateien verschieden sind, z.B. doppelter Upload oder Scan)
- **Unterschied zu Datei-Duplikaten**: Datei-Duplikat (`content_hash`) = gleiche Bytes, Content-Duplikat = gleicher Text
- **DB-Spalte**: `documents.content_duplicate_of_id` (INT NULL) zeigt auf das Original-Dokument
- **Erkennung**: Beim Speichern von `extracted_text_sha256` wird geprueft ob ein aelteres Dokument denselben Hash hat
- **Archiv-Tabelle**: Spalte 0 zeigt ≡-Icon (indigo) bei Content-Duplikat, ⚠-Icon (amber) bei Datei-Duplikat (hat Prioritaet)
- **Tooltip**: "Inhaltlich identisch mit: {original} (ID: {id})"
- **Document-Model**: `is_content_duplicate`, `has_any_duplicate` Properties
- **PHP-Seite**: `saveDocumentAiData()` setzt `content_duplicate_of_id`, `listDocuments()` liefert `content_duplicate_of_filename`
- **DB-Migration**: `018_content_duplicate_detection.php` fuegt Spalte + Index + Backfill hinzu
- **Dateien**:
  - `BiPro-Webspace Spiegelung Live/setup/018_content_duplicate_detection.php` → DB-Migration
  - `BiPro-Webspace Spiegelung Live/api/documents.php` → `saveDocumentAiData()` Duplikat-Logik, `listDocuments()` JOIN
  - `src/api/documents.py` → `Document.content_duplicate_of_id`, `is_content_duplicate`, `has_any_duplicate`
  - `src/ui/archive_boxes_view.py` → `DocumentTableModel.data()` fuer COL_DUPLICATE mit Content-Duplikat-Icon
  - `src/i18n/de.py` → CONTENT_DUPLICATE_* Keys (3 Stueck)

### 2ab. Proaktive Text-Extraktion (Early Text Extract) ✅ (v2.0.3)
- **Zweck**: Text-Extraktion und Duplikat-Erkennung direkt nach dem Upload, BEVOR die KI-Pipeline laeuft
- **Problem geloest**: Duplikate waren vorher erst sichtbar NACH der KI-Verarbeitung (zu spaet fuer sofortiges Feedback)
- **Integrationspunkte** (4 Stellen):
  - `DropUploadWorker` in `main_hub.py` (Drag & Drop)
  - `MultiUploadWorker` in `archive_boxes_view.py` (Button-Upload)
  - `MailImportWorker` in `bipro_view.py` (IMAP-Anhaenge)
  - BiPRO-Downloads in `bipro_view.py`
- **Ablauf**:
  1. Datei wird hochgeladen → `doc = docs_api.upload(...)`
  2. Sofort danach: `extract_and_save_text(docs_api, doc.id, local_path, filename)`
  3. Text wird extrahiert (PDF via PyMuPDF, Text-Dateien direkt)
  4. SHA256 des Textes wird berechnet
  5. `save_ai_data()` speichert Text + prueft auf Content-Duplikate
  6. Bei Duplikat: `content_duplicate_of_id` wird gesetzt → sofort sichtbar in UI
- **MissingAiDataWorker**: Hintergrund-Worker fuer Scan-Dokumente (Power Automate)
  - Startet einmalig nach erstem Cache-Refresh
  - Holt Dokumente ohne AI-Data via `GET /documents/missing-ai-data`
  - Extrahiert Text und ruft `save_ai_data()` auf
  - Ergebnis: Auch Scans haben sofort Duplikat-Erkennung wenn App geoeffnet wird
- **Performance**: Text-Extraktion ~5-50ms pro Dokument, blockiert nicht den Upload
- **Fehlertoleranz**: Fehler bei Text-Extraktion werden geloggt aber brechen Upload NICHT ab
- **Dateien**:
  - `src/services/early_text_extract.py` → `extract_and_save_text()` Helper
  - `src/ui/main_hub.py` → `DropUploadWorker._upload_single()` + Early-Extract-Call
  - `src/ui/archive_boxes_view.py` → `MultiUploadWorker._upload_single()` + `MissingAiDataWorker`
  - `src/ui/bipro_view.py` → `_upload_single()` + `_download_and_process_shipment_parallel()`
  - `src/api/documents.py` → `get_missing_ai_data_documents()`
  - `BiPro-Webspace Spiegelung Live/api/documents.php` → `GET /documents/missing-ai-data`

### 2ac. ATLAS Index (Volltextsuche) ✅ (v2.0.5, Erweiterungen v2.1.0)
- **Zweck**: Globale Volltextsuche ueber alle Dokumente im Archiv (Dateiname + extrahierter Text)
- **Position**: Virtuelle "Box" ganz oben in der Archiv-Sidebar, vor der Verarbeitungs-Gruppe
- **Kein box_type in DB**: Rein virtuelles UI-Konzept, keine Migration, kein Datenverschieben
- **Backend**: Neuer Endpoint `GET /documents/search?q=...&limit=200&include_raw=0&substring=0`
  - JOIN auf `document_ai_data` NUR im Search-Endpoint (niemals in `listDocuments()`)
  - **Zwei Suchmodi**:
    - Standard: `MATCH ... AGAINST` mit FULLTEXT-Index in `BOOLEAN MODE` (schnell, ganze Woerter)
    - Teilstring: `LIKE '%term%'` auf `extracted_text` (langsamer, findet Teilwoerter) **NEU v2.1.0**
  - Query-Sanitizer: Sonderzeichen (+, -, ", *, etc.) werden entfernt
  - Relevanz-Score: Dateiname=10 Punkte, Text=20 Punkte
  - **Smart Text-Preview** (LOCATE-basiert): Statt immer `LEFT(extracted_text, 2000)` wird der Suchbegriff per `LOCATE()` im Text gefunden und ein 2000-Zeichen-Fenster um den Treffer extrahiert (300 Zeichen davor + 1700 danach). Fallback auf Textanfang wenn nicht gefunden. Bei Mehrwort-Queries wird das laengste Wort fuer LOCATE verwendet. **NEU v2.1.0**
  - **XML/GDV-Filter**: `include_raw=0` (Default) blendet `box_type='roh'` und `is_gdv=1` aus **NEU v2.1.0**
  - LIMIT als `(int)` Cast inline (PDO EMULATE_PREPARES=false Kompatibilitaet)
  - Mindestlaenge 3 Zeichen (Server + Client konsistent)
- **UI: AtlasIndexWidget** (eigene View im QStackedWidget):
  - Suchfeld mit Debounce (400ms) + **Such-Button** (sichtbar wenn Live-Suche deaktiviert) **NEU v2.1.0**
  - Checkbox "Live-Suche (ab 3 Zeichen)" (Default: an, Session-persistent)
  - Checkbox "XML/GDV einbeziehen" (Default: aus) **NEU v2.1.0**
  - Checkbox "Teilstring-Suche" (Default: aus) **NEU v2.1.0**
  - Snippet-basierte Ergebnisdarstellung (Google-Stil)
  - SearchResultCard: Dateiname, Meta-Zeile (Box|VU|Datum), Text-Snippet mit Treffer fett
  - **Verbesserte Snippet-Aufbereitung**: Zweistufige Suche -- erst voller Suchbegriff, dann Einzelwoerter (laengstes zuerst). Findet Snippets auch bei Mehrwort-Suchen zuverlaessig. **NEU v2.1.0**
  - Doppelklick: PDF-Vorschau, Rechtsklick: Vorschau/Download/In Box anzeigen
  - "In Box anzeigen": Wechselt zur echten Box + selektiert Dokument
  - Checkbox-Aenderung loest automatisch Neusuche aus (wenn Query vorhanden)
- **Performance**: FULLTEXT-Index, LIMIT 200, Debounce, SearchWorker (QThread), LOCATE-basiertes Preview
- **Dateien**:
  - `BiPro-Webspace Spiegelung Live/api/documents.php` → `searchDocuments()` mit `include_raw`, `substring`, LOCATE-Preview
  - `src/api/documents.py` → `SearchResult` Dataclass + `search_documents(query, limit, include_raw, substring)`
  - `src/ui/archive_boxes_view.py` → `SearchWorker`, `SearchResultCard`, `AtlasIndexWidget` (3 Checkboxen + Such-Button), BoxSidebar ATLAS Index Item
  - `src/i18n/de.py` → 16 `ATLAS_INDEX_*` Keys (3 neue: SEARCH_BUTTON, INCLUDE_RAW, SUBSTRING_SEARCH)

### 2ad. Konfigurierbare KI-Klassifikation (Admin) ✅ (v2.1.1)
- **Zweck**: KI-Verarbeitungsablauf im Admin-Panel visualisieren und konfigurieren (Prompts, Modelle, Stufen)
- **Sofort-Kostensenkung**: Stufe 2 von GPT-4o auf GPT-4o-mini umgestellt (~17x guenstiger)
- **Admin-Panel**: Neue Sektion "VERARBEITUNG" in der Admin-Sidebar (Panel 6)
- **Pipeline-Visualisierung**: Statische Darstellung der Vorsortierungs-Schritte (XML, GDV, PDF-Validierung, Courtage)
- **Stufe 1 (Pflicht)**: Model-Auswahl, Prompt-Editor (Monospace), Max-Tokens, Versions-Dropdown
- **Stufe 2 (Optional)**: Deaktivierbar (spart Kosten), Trigger konfigurierbar (low / low+medium)
- **Prompt-Versionierung**: Gespeicherte Versionen mit Label, aeltere Versionen aktivierbar
- **Auto-Versionierung**: Bei Prompt-Aenderung wird automatisch neue Version in DB erstellt
- **DB-Tabellen**: `processing_ai_settings` (Single-Row, id=1), `prompt_versions` (Versionierungs-Historie)
- **Dynamische Settings**: `document_processor.py` laedt Settings einmal pro Verarbeitungslauf vom Server
- **Abwaertskompatibilitaet**: Ohne Server-Settings werden Hardcoded-Defaults verwendet
- **Dateien**:
  - `BiPro-Webspace Spiegelung Live/api/processing_settings.php` → PHP API (Public GET + Admin CRUD)
  - `BiPro-Webspace Spiegelung Live/api/index.php` → Route-Registrierung
  - `BiPro-Webspace Spiegelung Live/setup/019_processing_ai_settings.php` → DB-Migration
  - `src/api/processing_settings.py` → Python API Client
  - `src/api/openrouter.py` → Parametrisierbare classify_sparte_with_date() + Untermethoden
  - `src/services/document_processor.py` → _load_ai_settings() + _get_classify_kwargs()
  - `src/ui/admin_view.py` → Panel KI-Klassifikation mit Pipeline + Prompt-Editor + Versionen
  - `src/i18n/de.py` → ~45 neue PROCESSING_AI_ Keys

### 2ae. KI-Provider-System (OpenRouter + OpenAI) ✅ (v2.1.2)
- **Zweck**: Dynamisches Routing von KI-Anfragen ueber OpenRouter ODER direkt ueber OpenAI
- **Motivation**: OpenRouter berechnet ~$0.02 Plattform-Gebuehr PRO API-Call; direkt ueber OpenAI ~96% guenstiger
- **Provider-Verwaltung (Admin)**:
  - Neuer Tab "KI-Provider" in Admin-Sidebar (Sektion VERARBEITUNG)
  - CRUD fuer Provider-Keys (OpenRouter + OpenAI)
  - Keys werden AES-256-GCM verschluesselt in DB gespeichert (`ai_provider_keys`)
  - Nur 1 Key kann gleichzeitig aktiv sein (global fuer alle Nutzer)
  - Verbindungstest pro Key (Test-Anfrage an Provider-API)
  - Maskierte Anzeige (erste 8 + letzte 4 Zeichen)
- **Modell-Preise (Admin)**:
  - Neuer Tab "Modell-Preise" in Admin-Sidebar (Sektion VERARBEITUNG)
  - Tabelle mit Input/Output-Preis pro 1M Tokens pro Modell
  - Admin CRUD + oeffentlicher Endpunkt fuer aktive Preise
  - Preise werden fuer exakte Kostenberechnung pro Request verwendet
- **Dynamisches Routing (PHP-Proxy)**:
  - `ai.php` → `handleClassify()` liest aktiven Provider aus `ai_provider_keys`
  - Modell-Mapping: `openai/gpt-4o-mini` (OpenRouter-Format) → `gpt-4o-mini` (OpenAI-Format)
  - `callOpenRouterProvider()` → `openrouter.ai/api/v1/chat/completions`
  - `callOpenAIProvider()` → `api.openai.com/v1/chat/completions`
  - Fallback auf Legacy-Key aus `config.php` wenn kein Provider in DB aktiv
  - PII-Redaktion (E-Mail, IBAN, Telefon) vor Weiterleitung
- **Exakte Kostenberechnung (pro Request)**:
  - Server berechnet `real_cost_usd` aus `usage.prompt_tokens` + `usage.completion_tokens` + `model_pricing`
  - Jeder Request wird in `ai_requests`-Tabelle geloggt (User, Provider, Model, Tokens, Kosten)
  - Response enthaelt `_cost.real_cost_usd` + `_cost.provider` fuer Client-Logging
- **Akkumulierte Batch-Kosten**:
  - `ProcessingResult.cost_usd`: Kosten pro Dokument (aus Server-Response)
  - `BatchProcessingResult.total_cost_usd`: Summe aller Einzelkosten (sofort verfuegbar)
  - Kosten werden im Fazit-Overlay sofort angezeigt (kein 90s-Warten noetig)
  - OpenAI: 5s Delay statt 90s fuer Kosten-Check (akkumulierte Kosten haben Prioritaet)
  - OpenRouter: Balance-Diff als Fallback, akkumulierte Kosten als Primaerquelle
- **Token-Schaetzung (Client-seitig)**:
  - `tiktoken` Bibliothek fuer praezise Token-Zaehlung vor dem Request
  - `CostCalculator`: `estimate_from_messages()` + `calculate_real_cost()`
  - Geschaetzte Kosten werden mit dem Request an den Server gesendet
- **KI-Klassifikation dynamisch**:
  - Admin-Tab "KI-Klassifikation" zeigt Modelle passend zum aktiven Provider
  - OpenRouter: Alle Modelle (openai/, anthropic/, google/, etc.)
  - OpenAI: Nur OpenAI-Modelle (gpt-4o, gpt-4o-mini, etc.)
  - Provider-Banner zeigt aktiven Provider im Klassifikations-Tab
- **Credits/Usage-Anzeige (provider-aware)**:
  - OpenRouter: Balance-Anzeige (Guthaben - Verbrauch)
  - OpenAI: Monatliche Usage-Anzeige (Billing-API, falls verfuegbar)
  - Service-Account-Keys (`sk-svcacct-*`): Billing-API oft nicht verfuegbar → Hinweis im Log
- **KI-Kosten-Tab (Admin, erweitert)**:
  - Neue Sektion "Einzelne Requests" mit Tabelle aller KI-Anfragen
  - Spalten: Zeit, User, Provider, Modell, Prompt/Completion Tokens, Geschaetzt, Echt
  - Zeitraum-Filter (Alle, 7, 30, 90 Tage)
  - CSV-Export
- **DB-Tabellen** (Migration 020):
  - `ai_provider_keys`: id, provider_type, name, api_key_encrypted, is_active, created_by, timestamps
  - `model_pricing`: id, provider, model_name, input_price_per_million, output_price_per_million, valid_from, is_active
  - `ai_requests`: id, user_id, provider, model, context, document_id, prompt/completion/total_tokens, estimated/real_cost_usd, created_at
- **Dateien**:
  - `BiPro-Webspace Spiegelung Live/api/ai.php` → Zentraler Proxy (Routing, Kosten, PII-Redaktion, Credits)
  - `BiPro-Webspace Spiegelung Live/api/ai_providers.php` → Provider-CRUD (Public + Admin)
  - `BiPro-Webspace Spiegelung Live/api/model_pricing.php` → Modell-Preise + Kosten-Helpers
  - `BiPro-Webspace Spiegelung Live/api/index.php` → Neue Routes (ai-providers, model-pricing)
  - `src/api/ai_providers.py` → Python API Client (AIProviderKey, AIProvidersAPI)
  - `src/api/model_pricing.py` → Python API Client (ModelPrice, ModelPricingAPI)
  - `src/services/cost_calculator.py` → Token-Zaehlung + Kostenberechnung (tiktoken)
  - `src/config/ai_models.py` → Zentrale Modell-Definitionen pro Provider
  - `src/api/openrouter.py` → Server-Kosten propagieren (_server_cost_usd), Provider-Log
  - `src/services/document_processor.py` → Akkumulierte Kosten (ProcessingResult.cost_usd, BatchProcessingResult)
  - `src/ui/archive_boxes_view.py` → Provider-aware Credits/Kosten, verkuerzter Delay bei OpenAI
  - `src/ui/admin_view.py` → 3 neue Panels (KI-Provider, Modell-Preise) + erweiterte KI-Kosten
  - `src/i18n/de.py` → ~65 neue Keys (AI_PROVIDER_, MODEL_PRICING_, AI_COSTS_REQUESTS_)
  - `requirements.txt` → `tiktoken>=0.5.0,<1.0.0`

### 2af. Dokumenten-Regeln (Admin) ✅ (v2.1.3)
- **Zweck**: Konfigurierbare automatische Aktionen bei Duplikaten und leeren Seiten waehrend der Dokumentenverarbeitung
- **Admin-Panel**: Neues Panel "Dokumenten-Regeln" in Sektion VERARBEITUNG (Panel 9)
- **4 Regel-Kategorien**:
  1. **Datei-Duplikate** (gleiche SHA256-Prüfziffer):
     - Keine Aktion / Beide farblich markieren / Nur neue Datei markieren / Neue Datei loeschen / Alte Datei loeschen
  2. **Inhaltsduplikate** (gleicher extrahierter Text, andere Datei):
     - Gleiche Optionen wie Datei-Duplikate (gesondert konfigurierbar)
  3. **Teilweise leere PDFs** (einige Seiten leer):
     - Keine Aktion / Leere Seiten entfernen / Datei farblich markieren
  4. **Komplett leere Dateien** (alle Seiten leer):
     - Keine Aktion / Datei loeschen / Datei farblich markieren
- **Farbauswahl**: 8 Farben (Gruen, Rot, Blau, Orange, Lila, Pink, Tuerkis, Gelb) - Dropdown erscheint nur wenn Aktion Farbe erfordert
- **DB-Tabelle**: `document_rules_settings` (Single-Row, id=1) mit `file_dup_action`, `file_dup_color`, `content_dup_action`, `content_dup_color`, `partial_empty_action`, `partial_empty_color`, `full_empty_action`, `full_empty_color`
- **Integration**: `document_processor._apply_document_rules()` wird nach `_persist_ai_data()` aufgerufen
  - Regeln werden einmal pro Verarbeitungslauf vom Server geladen (`_load_document_rules()`)
  - Fehler bei Regelanwendung werden geloggt aber brechen die Verarbeitung NICHT ab
  - `_remove_empty_pages()`: Laedt PDF herunter, entfernt leere Seiten mit PyMuPDF, laedt bereinigte Version hoch, invalidiert Preview-Cache
  - `_apply_duplicate_rule()`: Farbmarkierung oder Loeschung von Duplikaten (mit Schutz gegen Loeschen beider)
- **Cache-Invalidierung**: Nach Verarbeitungslauf wird der lokale Preview-Cache fuer alle verarbeiteten Dokumente geleert
- **Dateien**:
  - `BiPro-Webspace Spiegelung Live/api/document_rules.php` → PHP API (Public GET + Admin PUT)
  - `BiPro-Webspace Spiegelung Live/api/index.php` → Route-Registrierung (`document-rules`, `admin/document-rules`)
  - `src/api/document_rules.py` → `DocumentRulesSettings` Dataclass + `DocumentRulesAPI` Client
  - `src/services/document_processor.py` → `_load_document_rules()`, `_apply_document_rules()`, `_apply_duplicate_rule()`, `_remove_empty_pages()`
  - `src/ui/admin_view.py` → Panel 9 Dokumenten-Regeln (`_create_document_rules_tab()`, `_load_document_rules()`, `_save_document_rules()`)
  - `src/ui/archive_boxes_view.py` → Preview-Cache-Invalidierung in `_on_processing_finished()`
  - `src/i18n/de.py` → ~35 neue DOC_RULES_* Keys

### 2ag. Cache-Wipe bei ungültiger Session ✅ (v2.1.3)
- **Zweck**: Lokale Caches loeschen wenn beim App-Start keine gueltige Session vorhanden ist
- **Trigger**: `_try_auto_login()` in `LoginDialog` stellt fest, dass der gespeicherte Token ungueltig ist oder kein Token existiert
- **Ablauf**: `_clear_local_caches()` wird aufgerufen und loescht den gesamten `%TEMP%/bipro_preview_cache/` Ordner
- **Grund**: Verhindert, dass nach einem Logout oder einer abgelaufenen Session veraltete PDF-Vorschauen eines anderen Nutzers angezeigt werden
- **Fehlertoleranz**: Fehler beim Loeschen werden nur im Debug-Log vermerkt, kein Crash
- **Dateien**:
  - `src/ui/login_dialog.py` → `_clear_local_caches()`, Aufruf in `_try_auto_login()` else-Zweig

### 2x. Mitteilungszentrale / Communication Hub ✅ (v2.0.0)
- **Zweck**: Zentrales Kommunikations- und Informationsportal in der App
- **Position**: Neue Seite in linker Sidebar VOR BiPRO (Index 0)
- **3 Bereiche**:
  1. **System- & Admin-Mitteilungen** (grosse Kachel): Automatische Systemmeldungen (z.B. Scan-Fehler via API-Key) und Admin-Announcements, Severity-Farben, Read-Status pro User
  2. **Release-Info** (kleine Kachel): Aktuelle Version + Release Notes, expandierbar zu allen Releases
  3. **Nachrichten / 1:1 Chat** (Button → Vollbild): Private Chats zwischen Nutzern, Lesebestaetigung (✓✓), Unread-Badge
- **Polling**: QTimer alle 30s im Main-Thread (KEIN QThread), `GET /notifications/summary`
- **Badge**: Roter Kreis auf "Zentrale"-Button mit Summe aus ungelesenen Chats + System-Meldungen
- **Toast**: Bei neuer Chat-Nachricht Toast mit "Neue Nachricht von ..." + Klick-Aktion zum Chat
- **Chat-Vollbild**: Sidebar wird versteckt (wie Admin), Conversation-Liste links, Nachrichten rechts
- **Admin-Panel**: Panel 14 "Mitteilungen" in Admin-View (CRUD)
- **Sicherheit**: Content-Escaping (htmlspecialchars), Laengenlimits, Autorisierung (nur eigene Chats), kein HTML/Markdown
- **DB-Tabellen**: `messages`, `message_reads`, `private_conversations`, `private_messages`
- **Dateien**:
  - `BiPro-Webspace Spiegelung Live/api/messages.php` → Mitteilungen API (GET/POST/PUT/DELETE)
  - `BiPro-Webspace Spiegelung Live/api/chat.php` → Chat API (Conversations + Messages + Read)
  - `BiPro-Webspace Spiegelung Live/api/notifications.php` → Leichtgewichtiger Polling-Endpoint
  - `BiPro-Webspace Spiegelung Live/api/index.php` → 3 neue Route-Cases
  - `BiPro-Webspace Spiegelung Live/setup/015_message_center.php` → DB-Migration (4 Tabellen)
  - `src/api/messages.py` → MessagesAPI Client
  - `src/api/chat.py` → ChatAPI Client
  - `src/ui/message_center_view.py` → Dashboard-View (3 Kacheln)
  - `src/ui/chat_view.py` → Vollbild-Chat-View
  - `src/ui/main_hub.py` → NavButton + Badge + NotificationPoller + Chat-Sidebar-Hide
  - `src/ui/admin_view.py` → Panel 14 Mitteilungen
  - `src/i18n/de.py` → ~60 neue Keys (MSG_CENTER_, CHAT_, ADMIN_MSG_)

### 3. Datei öffnen/speichern
- **Dateitypen**: *.gdv, *.txt, *.dat, *.vwb
- **Encoding**: CP1252 (Standard), Latin-1, UTF-8 (Fallback)
- **Wichtige Dateien**: `src/parser/gdv_parser.py` → `parse_file()`, `save_file()`

### 4. Satz-Ansicht (Tabelle + Detail)
- **Ablauf**: Datei laden → Records in Tabelle → Auswahl → Detail-Ansicht
- **Dateien**: 
  - `src/ui/main_window.py` → `RecordTableWidget`, `GDVMainWindow`
  - `src/ui/user_detail_view.py` → Benutzerfreundlich (nur wichtige Felder)
  - `src/ui/main_window.py` → `ExpertDetailWidget` (alle Felder)

### 5. Partner-Ansicht
- **Zweck**: Alle Firmen/Personen mit ihren Verträgen auf einen Blick
- **Ablauf**: Extrahiert aus 0100-Sätzen Arbeitgeber (Anrede=0/3) und Personen
- **Dateien**: `src/ui/partner_view.py` → `PartnerView`, `extract_partners_from_file()`

### 6. Daten bearbeiten
- **Benutzer-Ansicht**: Nur editierbare Felder sichtbar
- **Experten-Ansicht**: Alle Felder editierbar (Vorsicht!)
- **Dateien**: `src/ui/user_detail_view.py` Zeile 40-88 → `DROPDOWN_FIELDS`, `READONLY_FIELDS`

---

## GDV-Satzarten (Implementiert)

| Satzart | Name | Teildatensätze | Beschreibung |
|---------|------|----------------|--------------|
| 0001 | Vorsatz | 1 | Datei-Header (VU, Datum, Release) |
| 0100 | Partnerdaten | 1-5 | TD1=Adresse, TD2=Nummern, TD4=Bank |
| 0200 | Vertragsteil | 1 | Grunddaten (Laufzeit, Beitrag, Sparte) |
| 0210 | Spartenspezifisch | 1+ | Wagnisse, Risiken |
| 0220 | Deckungsteil | 1,6+ | TD1=Person, TD6=Bezugsberechtigte |
| 0230 | Fondsanlage | 1+ | Fondsdaten (ISIN, Anteile) |
| 9999 | Nachsatz | 1 | Prüfsummen |

**Layout-Definitionen**: `src/layouts/gdv_layouts.py`

---

## BiPRO-Integration (Details)

### Unterstützte VUs

| VU | Status | STS-Format | Besonderheiten |
|----|--------|------------|----------------|
| **Degenia** | ✅ Funktioniert | Standard BiPRO | `BestaetigeLieferungen=true` ERFORDERLICH |
| **VEMA** | ✅ Funktioniert | VEMA-spezifisch | Consumer-ID ERFORDERLICH, KEIN BestaetigeLieferungen |

**WICHTIG: VU-spezifisches Verhalten!**
Jede VU implementiert BiPRO unterschiedlich. Änderungen für eine VU dürfen NIEMALS andere VUs beeinflussen!
Siehe `docs/BIPRO_ENDPOINTS.md` für Details.

### Unterstützte Normen

| Norm | Beschreibung | Degenia | VEMA |
|------|--------------|---------|------|
| 410 | STS (Security Token Service) | ✅ | ✅ |
| 430.1 | Transfer allgemein | ✅ | ✅ |
| 430.2 | Lieferungen | ✅ | ✅ |
| 430.4 | GDV-Daten | ⚠️ | ⚠️ |
| 430.5 | Dokumente | ✅ | ✅ |
| 420 | TAA (Angebot/Antrag) | ❌ | - |

### BiPRO-Flow (Degenia)

```
1. STS-Token holen (BiPRO 410)
   POST https://transfer.degenia.de/.../410_STS/UserPasswordLogin_2.6.1.1.0
   → UsernameToken → SecurityContextToken (10 Min gültig)

2. listShipments (BiPRO 430)
   POST https://transfer.degenia.de/.../430_Transfer/Service_2.6.1.1.0
   → SecurityContextToken → Liste der Lieferungen

3. getShipment (BiPRO 430)
   POST (gleicher Endpoint)
   → MTOM/XOP-Response mit Dokumenten (PDFs als Binary)

4. acknowledgeShipment (BiPRO 430)
   POST (gleicher Endpoint)
   → Empfang quittieren
```

### Lieferungs-Kategorien

| Code | Bedeutung | Ziel-Box |
|------|-----------|----------|
| 100001000 | Antragsversand | VU (Sparten-KI) |
| 100002000 | Eingangsbestätigung | VU (Sparten-KI) |
| 100005000 | Nachfrage | VU (Sparten-KI) |
| 100007000 | Policierung/Geschäftsvorfall | VU (Sparten-KI) |
| 110011000 | Adressänderung/Vertragsdokumente | VU (Sparten-KI) |
| 120010000 | Nachtrag | VU (Sparten-KI) |
| 140012000 | Mahnung | VU (Sparten-KI) |
| 140013000 | Beitragsrechnung | VU (Sparten-KI) |
| 150013000 | Schaden | VU (Sparten-KI) |
| 160010000 | Kündigung | VU (Sparten-KI) |
| **300001000** | **Provisionsabrechnung** | **Courtage** |
| **300002000** | **Courtageabrechnung** | **Courtage** |
| **300003000** | **Vergütungsübersicht** | **Courtage** |
| **999010010** | **GDV Bestandsdaten** | **GDV** |

Siehe `src/config/processing_rules.py` für vollständige Liste.

### MTOM/XOP-Handling

Degenia liefert Dokumente als MTOM (Message Transmission Optimization Mechanism):
- Response ist Multipart-MIME
- PDFs sind Base64 in separaten Parts referenziert
- `transfer_service.py` enthält `_parse_mtom_response()` und `_split_multipart()`
- **PDF-Magic-Byte-Validierung (NEU v1.1.0)**: Nach MTOM-Extraktion wird geprueft ob Content-Type `application/pdf` tatsaechlich `%PDF` Magic-Bytes hat. Warnung bei Diskrepanz (z.B. GDV-Textdatei als PDF deklariert).
- **Trailing CRLF/LF-Stripping (NEU v1.1.0)**: Konsistentes Entfernen von Boundary-Artefakten bei Binary-Parts in beiden MTOM-Parsern (`transfer_service.py` + `bipro_view.py`).
- **Post-Save Cross-Check (NEU v1.1.0)**: Bei BiPRO-Code 999xxx (GDV) + `.pdf`-Endung wird geprueft ob der Inhalt tatsaechlich PDF ist. Warnung bei Nicht-PDF-Inhalt.

---

## Aktueller Stand (18. Februar 2026)

### Implementiert ✅
- ✅ GDV-Dateien öffnen/parsen/speichern
- ✅ Drei Ansichtsmodi (Partner, Benutzer, Experte)
- ✅ Satzarten 0001, 0100, 0200, 0210, 0220, 0230, 9999
- ✅ Teildatensatz-Unterstützung (0100 TD1-5, 0220 TD1/6)
- ✅ Bearbeitung mit Validierung
- ✅ Deutsche Umlaute (CP1252 Encoding)
- ✅ **BiPRO 410 STS-Authentifizierung (Degenia)**
- ✅ **BiPRO 430 listShipments mit Kategorien**
- ✅ **BiPRO 430 getShipment mit MTOM/XOP**
- ✅ **Dokumentenarchiv mit Server-Backend**
- ✅ **PDF-Vorschau (QPdfView)**
- ✅ **Multi-Download/Multi-Delete im Archiv**
- ✅ **Automatischer Upload von BiPRO-Dokumenten**
- ✅ **Deutsches Datumsformat in allen Ansichten**
- ✅ **Box-System mit 7 Boxen inkl. Kranken-Box (v0.8.0)**
- ✅ **Automatische Dokumenten-Klassifikation (parallel)**
- ✅ **KI-basierte PDF-Klassifikation mit Kontext-Awareness**
- ✅ **Courtage-Erkennung mit insurance_type (Leben/Sach/Kranken)**
- ✅ **Multi-Upload (mehrere Dateien gleichzeitig) (v0.8.0)**
- ✅ **Parallele Verarbeitung (ThreadPoolExecutor) (v0.8.0)**
- ✅ **Robuster Download mit Retry-Logik (v0.8.0)**
- ✅ **OpenRouter Credits-Anzeige (v0.8.0)**
- ✅ **Thread-sicheres Worker-Cleanup (closeEvent) (v0.8.0)**
- ✅ **Robustes JSON-Parsing (_safe_json_loads) (v0.8.0)**
- ✅ **Sichere Dateinamen-Generierung (slug_de) (v0.8.0)**
- ✅ **LoadingOverlay fuer async Box-Wechsel (v0.8.1)**
- ✅ **Async Document-Loading ohne UI-Blockierung (v0.8.1)**
- ✅ **BiPRO-Code-basierte Vorsortierung (v0.9.0)**
- ✅ **Token-optimierte KI-Klassifikation (~90% Einsparung) (v0.9.0)**
- ✅ **GDV-Metadaten aus Datensatz (VU + Datum ohne KI) (v0.9.0)**
- ✅ **Einheitliche Fortschrittsanzeige (BiPRO + Verarbeitung) (v0.9.0)**
- ✅ **Parallele BiPRO-Downloads (max. 10 Worker, auto-adjustiert) (v0.9.1)**
- ✅ **SharedTokenManager: Thread-sicheres STS-Token (v0.9.1)**
- ✅ **AdaptiveRateLimiter: Dynamische Anpassung bei 429/503 (v0.9.1)**
- ✅ **PDF-Validierung und automatische Reparatur (PyMuPDF) (v0.9.1)**
- ✅ **Auto-Refresh-Kontrolle: pause/resume während Operationen (v0.9.1)**
- ✅ **GDV-Erkennung über BiPRO-Code (999xxx) (v0.9.1)**
- ✅ **Fix: if/elif-Struktur document_processor (XML→roh korrekt) (v0.9.1)**
- ✅ **Timezone-aware Datetime-Vergleiche für Token-Validierung (v0.9.2)**
- ✅ **MIME-Type zu Extension Mapping (mime_to_extension) (v0.9.2)**
- ✅ **Automatische Worker-Anpassung bei wenigen Lieferungen (v0.9.2)**
- ✅ **Kosten-Tracking: OpenRouter-Guthaben vor/nach Verarbeitung (v0.9.3)**
- ✅ **BatchProcessingResult mit Kosten-Statistiken (v0.9.3)**
- ✅ **Kosten-Anzeige im Fazit: Gesamt + pro Dokument (v0.9.3)**
- ✅ **Erweiterte Sach-Keywords: Privathaftpflicht, PHV, Tierhalterhaftpflicht (v0.9.3)**
- ✅ **Courtage-Benennung: VU_Name + Datum (z.B. Allianz_Courtage_2026-02-04.pdf) (v0.9.3)**
- ✅ **Verbesserte KI-Klassifikation: Pensionskasse→Leben, Sachversicherung→Sach (v0.9.3)**
- ✅ **Stabilitaets-Upgrade: DataCache Lock, JWT Auto-Refresh, Retry, Token SingleFlight (v0.9.4)**
- ✅ **Deadlock-Schutz: _try_auth_refresh() mit non-blocking acquire (v0.9.4)**
- ✅ **Zentrale _request_with_retry() fuer alle API-Methoden, exp. Backoff (v0.9.4)**
- ✅ **SharedTokenManager Double-Checked Locking (~90% weniger Lock-Contention) (v0.9.4)**
- ✅ **File-Logging: RotatingFileHandler (5 MB, 3 Backups) -> logs/bipro_gdv.log (v0.9.4)**
- ✅ **11 Smoke-Tests inkl. Deadlock-Verifikation (v0.9.4)**
- ✅ **processing_history PHP-Endpoint gefixt (falsche Imports + JSON) (v0.9.4)**
- ✅ **processing_history DB-Tabelle + document_id nullable fuer Batch-Ops (v0.9.4)**
- ✅ **Zweistufige KI-Klassifikation mit Confidence-Scoring (v0.9.4)**
- ✅ **Stufe 1: GPT-4o-mini (2 Seiten), Stufe 2: GPT-4o (5 Seiten) bei low Confidence (v0.9.4)**
- ✅ **Courtage-Definition verschaerft: Negativ-Beispiele im Prompt (v0.9.4)**
- ✅ **Text-Extraktion: 1→2 Seiten (Begleitschreiben-Problem geloest) (v0.9.4)**
- ✅ **Dokumentnamen bei Sonstige aus GPT-4o Stufe 2 (z.B. Schriftwechsel) (v0.9.4)**
- ✅ **Fonts aufgeraeumt: 40+ Dateien auf 3 reduziert (v0.9.4)**
- ✅ **Verarbeitung: 290s → 2.6s (100x schneller durch processing_history Fix) (v0.9.4)**
- ✅ **Git initialisiert + Tag v0.9.4-stable (v0.9.4)**
- ✅ **Tabellen-Vorschau: CSV/XLSX/TSV direkt im Archiv anzeigen (v0.9.5)**
- ✅ **SpreadsheetViewerDialog mit Sheet-Auswahl, Auto-Delimiter, Encoding-Erkennung (v0.9.5)**
- ✅ **Box-Download: Ganze Boxen als ZIP oder in Ordner herunterladen (v0.9.5)**
- ✅ **BoxSidebar Kontextmenue: Rechtsklick auf Box → Herunterladen → ZIP/Ordner (v0.9.5)**
- ✅ **Automatische Archivierung nach Box-Download mit Undo-Option (v0.9.5)**
- ✅ **"Alle VUs abholen" Button: Alle BiPRO-Daten mit einem Klick abrufen (v0.9.5)**
- ✅ **State Machine fuer sequentielle VU-Verarbeitung (fetch → download → naechste VU) (v0.9.5)**
- ✅ **Verarbeitungs-Ausschluss: Manuell verschobene/umbenannte Dokumente werden uebersprungen (v0.9.5)**
- ✅ **Kontextmenue: 'Von Verarbeitung ausschliessen' + 'Erneut fuer Verarbeitung freigeben' (v0.9.5)**
- ✅ **processing_status='manual_excluded' in PHP State-Machine + Python-Client (v0.9.5)**
- ✅ **Admin-/Rechte-System: 9 granulare Berechtigungen (inkl. smartscan_send), Admin/Benutzer-Kontotypen (v0.9.6+)**
- ✅ **Server-seitiges Session-Tracking mit sessions-Tabelle (v0.9.6)**
- ✅ **Single-Session-Enforcement: Pro Nutzer nur eine aktive Session, alte werden bei Login beendet (v2.0.0)**
- ✅ **JWT-Gueltigkeit auf 30 Tage (1 Monat) erhoeht, vorher 8 Stunden (v2.0.0)**
- ✅ **Umfassendes Activity-Logging: activity_log-Tabelle fuer jede API-Aktion (v0.9.6)**
- ✅ **Permission-Middleware: requirePermission() + requireAdmin() in PHP (v0.9.6)**
- ✅ **AdminView: 3-Tab-UI (Nutzerverwaltung, Sessions, Aktivitaetslog) (v0.9.6)**
- ✅ **Nutzerverwaltung: Erstellen, Bearbeiten, Sperren, Passwort aendern, Deaktivieren (v0.9.6)**
- ✅ **Session-Management: Einsicht + Kill (einzeln/alle pro User) mit Auto-Refresh (v0.9.6)**
- ✅ **Permission Guards: Buttons deaktiviert bei fehlenden Rechten (BiPRO, Archiv, GDV) (v0.9.6)**
- ✅ **User-Model erweitert: account_type, permissions, is_admin, has_permission() (v0.9.6)**
- ✅ **Login-Response liefert account_type + permissions, verify() ebenso (v0.9.6)**
- ✅ **i18n: ~80 neue Keys fuer Admin, Permissions, Fehlermeldungen (v0.9.6)**
- ✅ **Verzoegerter Kosten-Check: 90s Wartezeit fuer OpenRouter-Guthaben-Aktualisierung (v0.9.7)**
- ✅ **DelayedCostWorker mit Countdown-Anzeige im Credits-Label (v0.9.7)**
- ✅ **Admin KI-Kosten Tab: Statistik-Karten + Verarbeitungshistorie-Tabelle (v0.9.7)**
- ✅ **PHP-Endpoints: /processing_history/costs + /cost_stats (v0.9.7)**
- ✅ **batch_cost_update History-Eintrag fuer verzoegerte Kostenberechnung (v0.9.7)**
- ✅ **Kosten-Aggregation: Gesamtkosten, Durchschnitt/Dok, Durchschnitt/Lauf, Erfolgsrate (v0.9.7)**
- ✅ **Zeitraum-Filter: Alle, 7 Tage, 30 Tage, 90 Tage (v0.9.7)**
- ✅ **i18n: ~30 neue KI-Kosten Keys (v0.9.7)**
- ✅ **Stabilisierung Archiv: Cache-Only bei Boxwechsel + Vorschau-Download im Worker (Freeze/Crash-Hardening)**
- ✅ **Cache-Optimierung: Alle Dokumente einmal laden, lokal filtern (87% weniger API-Calls) (v0.9.8)**
- ✅ **Bulk-Archivierung: POST /documents/archive + /unarchive (N API-Calls → 1) (v0.9.8)**
- ✅ **Client-seitige Stats: BoxStats aus Dokumente-Cache berechnet (1 API-Call weniger) (v0.9.8)**
- ✅ **Auto-Refresh Optimierung: 1 API-Call statt 8+ pro 90-Sekunden-Zyklus (v0.9.8)**
- ✅ **Box-Wechsel nach Refresh: Cache-Zeitstempel-Check statt pro-Box Server-Calls (v0.9.8)**
- ✅ **Vorschau-Cache: Persistenter lokaler Cache, gleiche Datei nur 1x downloaden (v0.9.8)**
- ✅ **Download-Optimierung: filename_override spart get_document() API-Call (alle Worker) (v0.9.8)**
- ✅ **Auto-Update System: Version-Check bei Login + periodisch, Silent Install (v0.9.9)**
- ✅ **Admin Releases-Tab: Upload, Status (active/mandatory/deprecated/withdrawn), Channel (v0.9.9)**
- ✅ **Zentrale VERSION-Datei: Eine Quelle fuer App-Version, build.bat synchronisiert alle Stellen (v0.9.9)**
- ✅ **SHA256-Verifikation: Hash-Pruefung vor Installer-Ausfuehrung (v0.9.9)**
- ✅ **Pflicht-Updates: App blockiert bis Update installiert, kein Schliessen moeglich (v0.9.9)**
- ✅ **DB releases-Tabelle: Version, Channel, Status, SHA256, Downloads, min_version (v0.9.9)**
- ✅ **Scan-Upload Endpunkt: POST /api/incoming-scans fuer Power Automate / SharePoint (v1.0.2)**
- ✅ **API-Key-Auth: X-API-Key Header mit timing-safe Vergleich (hash_equals) (v1.0.2)**
- ✅ **Scan-Dokumente landen in Eingangsbox (source_type=scan, box_type=eingang) (v1.0.2)**
- ✅ **MIME-Whitelist fuer Scans: Nur PDF, JPG, PNG erlaubt (v1.0.2)**
- ✅ **Dokumenten-Farbmarkierung: 8 blasse Farben persistent ueber alle Operationen (v1.0.3)**
- ✅ **Kontextmenue mit Farb-Untermenue inkl. farbigen Icons und Multi-Selection (v1.0.3)**
- ✅ **Bulk-Farbmarkierung: POST /documents/colors fuer N Dokumente in 1 API-Call (v1.0.3)**
- ✅ **DB: display_color VARCHAR(20) NULL in documents-Tabelle (v1.0.3)**
- ✅ **Globales Drag & Drop Upload: Dateien/Ordner auf Fenster ziehen → Eingangsbox (v1.0.4)**
- ✅ **DropUploadWorker: QThread fuer nicht-blockierenden Upload per Drag & Drop (v1.0.4)**
- ✅ **Ordner-Support: Rekursives Durchlaufen, versteckte Dateien ausgeschlossen (v1.0.4)**
- ✅ **Permission-Guard: documents_upload Recht wird vor Drop-Upload geprueft (v1.0.4)**
- ✅ **i18n: ~9 neue Drag & Drop Upload Keys (v1.0.4)**
- ✅ **MSG E-Mail-Verarbeitung: .msg Anhaenge extrahieren → Eingangsbox, .msg → Roh-Archiv (v1.0.4)**
- ✅ **extract-msg Bibliothek: Outlook .msg Dateien parsen (v1.0.4)**
- ✅ **MsgExtractResult Dataclass: Strukturierte Ergebnisse der MSG-Extraktion (v1.0.4)**
- ✅ **MultiUploadWorker + DropUploadWorker: Automatische MSG-Erkennung und -Verarbeitung (v1.0.4)**
- ✅ **Temporaere Dateien: Automatisches Cleanup nach MSG-Extraktion (v1.0.4)**
- ✅ **Outlook-Direct-Drop: E-Mails direkt aus Outlook ziehen via COM-Automation/pywin32 (v1.0.4)**
- ✅ **COM SaveAs: Outlook-Selection als .msg speichern, Einzel- und Mehrfachauswahl (v1.0.4)**
- ✅ **PDF-Unlock: Passwortgeschuetzte PDFs automatisch entsperren beim Upload (v1.0.4)**
- ✅ **Bekannte Passwoerter (aus DB geladen) werden vor Upload durchprobiert (v1.0.4)**
- ✅ **3 Integrationspunkte: MultiUploadWorker, DropUploadWorker, msg_handler (v1.0.4)**
- ✅ **ZIP-Entpackung: ZIP-Dateien automatisch entpacken beim Upload (v1.0.5)**
- ✅ **Passwortgeschuetzte ZIPs: Standard-PKZIP + AES-256 via pyzipper (v1.0.5)**
- ✅ **Rekursive ZIP-Verarbeitung: ZIPs in ZIPs, MSGs in ZIPs, PDFs in ZIPs (max. 3 Ebenen) (v1.0.5)**
- ✅ **ZIP ins Roh-Archiv: ZIP-Datei selbst wird nach Entpackung ins Roh-Archiv hochgeladen (v1.0.5)**
- ✅ **MSG-Handler: ZIP-Anhaenge aus E-Mails werden ebenfalls durchgelassen (v1.0.5)**
- ✅ **Zentrale Passwort-Verwaltung: DB-Tabelle known_passwords statt hartcodierte Liste (v1.0.5)**
- ✅ **Dynamische PDF-Passwoerter: Von API laden mit Session-Cache + Fallback (v1.0.5)**
- ✅ **PHP API: GET /passwords + Admin CRUD /admin/passwords (v1.0.5)**
- ✅ **Python PasswordsAPI Client: get_passwords(), create/update/delete (v1.0.5)**
- ✅ **Admin-Tab 6 Passwoerter: Tabelle + Hinzufuegen/Bearbeiten/Loeschen/Reaktivieren (v1.0.5)**
- ✅ **Passwort-Maskierung: Anzeigen/Verbergen Toggle im Admin-Tab (v1.0.5)**
- ✅ **Seed-Daten: 4 bekannte PDF-Passwoerter in DB migriert (v1.0.5)**
- ✅ **i18n: ~40 neue Keys fuer ZIP-Verarbeitung + Passwort-Verwaltung (v1.0.5)**
- ✅ **Smart!Scan E-Mail-Versand: Dokumente per E-Mail an SCS-SmartScan senden (v1.0.6)**
- ✅ **PHPMailer v6.9.3: Robuster SMTP-Versand mit TLS auf Shared Hosting (v1.0.6)**
- ✅ **E-Mail-Konten Verwaltung: SMTP/IMAP mit AES-256-GCM Verschluesselung (v1.0.6)**
- ✅ **SmartScan Versandmodi: Einzeln + Sammelmail mit Batch-Splitting (v1.0.6)**
- ✅ **Post-Send-Aktionen: Archivieren + Umfaerben nach erfolgreicher Zustellung (v1.0.6)**
- ✅ **Idempotenz: client_request_id verhindert Doppelversand (10 Min Fenster) (v1.0.6)**
- ✅ **Client-seitiges Chunking: SmartScanWorker mit max 10 Docs pro API-Call (v1.0.6)**
- ✅ **Revisionssichere Historie: Jobs, Items, Emails mit SHA256-Hashes + Message-IDs (v1.0.6)**
- ✅ **SmartScan Kontextmenue: Box-Sidebar + Dokument-Tabelle (Einzel/Multi) (v1.0.6)**
- ✅ **SmartScan Versand-Dialog: Modus, Vorschau, Archivieren/Umfaerben Optionen (v1.0.6)**
- ✅ **Admin-Tabs 7-10: E-Mail-Konten, SmartScan Settings, Historie, IMAP Inbox (v1.0.6)**
- ✅ **IMAP E-Mail-Import: Hybridansatz PHP-Polling + Python-Verarbeitung (v1.0.6)**
- ✅ **IMAP-Filter: Keyword-Modus (ATLASabruf) + Absender-Whitelist (v1.0.6)**
- ✅ **Permission smartscan_send: Granulare Berechtigung fuer SmartScan-Versand (v1.0.6)**
- ✅ **i18n: ~120 neue Keys fuer SmartScan + E-Mail-Konten + IMAP-Import (v1.0.6)**
- ✅ **DB-Migration 010: 7 neue Tabellen fuer E-Mail-System (v1.0.6)**
- ✅ **Toast-System: Alle modalen Info/Erfolg/Warn/Fehler-Popups durch nicht-blockierende Toasts ersetzt (v1.0.7)**
- ✅ **ToastManager: Globaler Manager oben rechts, 4 Typen, Stacking, Hover-Pause, Action-Button (v1.0.7)**
- ✅ **~137 QMessageBox-Aufrufe durch Toast ersetzt in 11 Dateien (v1.0.7)**
- ✅ **UX-Regeln dokumentiert: docs/ui/UX_RULES.md als verbindliche Referenz (v1.0.7)**
- ✅ **Login-Dialog: Validation-Fehler als Inline-Labels statt Popup (v1.0.7)**
- ✅ **Alte ToastNotification-Klasse und show_success_toast() entfernt (v1.0.7)**
- ✅ **Tastenkuerzel im Dokumentenarchiv: F2, Entf, Strg+A/D/F/U, Enter, Esc, Strg+Shift+A, F5 (v1.0.8)**
- ✅ **Shortcut-Kontext: WidgetWithChildrenShortcut - nur aktiv wenn Archiv sichtbar (v1.0.8)**
- ✅ **Intelligente Fokus-Erkennung: Shortcuts beruecksichtigen Suchfeld/ComboBox-Fokus (v1.0.8)**
- ✅ **Button-Tooltips mit Shortcut-Hinweisen aktualisiert (v1.0.8)**
- ✅ **i18n: ~16 neue Shortcut-Keys in de.py (v1.0.8)**
- ✅ **Admin-Redesign: Horizontale Tabs durch vertikale Sidebar ersetzt, Vollbild-Ansicht (v1.0.9)**
- ✅ **Admin-Sidebar: 3 Sektionen (Verwaltung, Monitoring, E-Mail) mit 10 Panels (v1.0.9)**
- ✅ **Haupt-Sidebar versteckt sich beim Wechsel in Admin (main_hub._show_admin) (v1.0.9)**
- ✅ **AdminNavButton: Monochrome Icons, ACENCIA Corporate Design, orangene Trennlinien (v1.0.9)**
- ✅ **Mail-Import in BiPRO-Bereich: "Mails abholen" Button ersetzt "Lieferungen abrufen" (v1.0.9)**
- ✅ **MailImportWorker: QThread mit IMAP-Poll → Attachment-Download → Pipeline → Upload (v1.0.9)**
- ✅ **Parallele Attachment-Verarbeitung: ThreadPoolExecutor (4 Worker, per-Thread API) (v1.0.9)**
- ✅ **Zweiphasiger Progress-Toast: Postfach abrufen + Anhaenge importieren mit Balken (v1.0.9)**
- ✅ **ProgressToastWidget: Neuer Toast-Typ mit Titel, Status, QProgressBar (v1.0.9)**
- ✅ **Smart!Scan Toolbar-Button im Archiv: Gruener Button neben "Zuruecksetzen" (v1.0.9)**
- ✅ **SmartScan-Sichtbarkeit: Button + Kontextmenue nur wenn SmartScan in Admin aktiviert (v1.0.9)**
- ✅ **SmartScan-Bestaetigung vereinfacht: Einfaches Confirm statt mehrstufiger Dialog (v1.0.9)**
- ✅ **i18n: ~20 neue Keys fuer Mail-Import + SmartScan-Button + Admin-Redesign (v1.0.9)**
- ✅ **Keyword-Conflict-Hints: Lokaler Scanner verbessert KI-Klassifikation bei widerspruechlichen Keywords (v1.1.0)**
- ✅ **_build_keyword_hints(): 0 Tokens, ~0.1ms CPU, laeuft auf bereits extrahiertem Text (v1.1.0)**
- ✅ **Conflict-Faelle: Courtage+Leben, Courtage+Sach, Kontoauszug+Provision, Sach-Problemfall (v1.1.0)**
- ✅ **95% der Dokumente: 0 extra Tokens, ~5% mit Konflikt: +30 Tokens Hint (v1.1.0)**
- ✅ **PDF Magic-Byte-Validierung nach MTOM-Extraktion in transfer_service.py + bipro_view.py (v1.1.0)**
- ✅ **Trailing CRLF/LF-Stripping bei MTOM Binary-Parts (v1.1.0)**
- ✅ **Post-Save Cross-Check: BiPRO-Code 999xxx + .pdf Endung vs. tatsaechlicher Inhalt (v1.1.0)**
- ✅ **Duplikat-Erkennung: SHA256-Pruefziffer vergleicht gegen alle Dokumente inkl. archivierte (v1.1.1)**
- ✅ **Duplikat-Spalte in Archiv-Tabelle: Warn-Icon mit Tooltip zum Original-Dokument (v1.1.1)**
- ✅ **Duplikat-Toast: Info-Benachrichtigung bei Upload von Duplikaten (v1.1.1)**
- ✅ **PHP listDocuments: content_hash, version, previous_version_id, duplicate_of_filename (v1.1.1)**
- ✅ **Python Document.duplicate_of_filename + upload() parst Duplikat-Infos (v1.1.1)**
- ✅ **Duplikat-Rich-Tooltip: HTML-Kachel beim Hover mit Dateiname, Box, Datum, Archiv-Status (v2.1.0)**
- ✅ **Duplikat-Metadaten: PHP LEFT JOIN liefert box_type, created_at, is_archived fuer Datei- und Content-Duplikate (v2.1.0)**
- ✅ **Document-Model: 6 neue Felder fuer Duplikat-Metadaten (duplicate_of_box_type/created_at/is_archived + content_*) (v2.1.0)**
- ✅ **Duplikat-Navigation: Klick auf Duplikat-Icon springt zum Gegenstueck in dessen Box (v2.1.0)**
- ✅ **Duplikat-Vergleichsansicht: DuplicateCompareDialog mit Side-by-Side PDF-Vorschau und Aktions-Buttons (v2.1.0)**
- ✅ **Duplikat-Kontextmenue: "Zum Gegenstueck springen" + "Duplikat vergleichen" bei Duplikat-Dokumenten (v2.1.0)**
- ✅ **Dokument-Historie: Seitenpanel im Archiv zeigt Aenderungshistorie pro Dokument (v1.1.2)**
- ✅ **DocumentHistoryPanel: Farbcodierte Eintraege mit Debounce, Cache, async Worker (v1.1.2)**
- ✅ **PHP getDocumentHistory(): GET /documents/{id}/history aus activity_log (v1.1.2)**
- ✅ **Verbessertes Move-Logging: Pro-Dokument-Eintraege mit source_box/target_box (v1.1.2)**
- ✅ **Neue Berechtigung documents_history: Granulare Kontrolle ueber Historie-Einsicht (v1.1.2)**
- ✅ **i18n: ~20 neue HISTORY_* Keys fuer Dokument-Historie (v1.1.2)**
- ✅ **PDF-Bearbeitung in Vorschau: Seiten drehen (CW/CCW), loeschen, speichern (v1.1.3)**
- ✅ **PDFViewerDialog erweitert: Thumbnail-Sidebar, Toolbar mit Rotate/Delete/Save (v1.1.3)**
- ✅ **PDFSaveWorker: Async Upload des bearbeiteten PDFs auf den Server (v1.1.3)**
- ✅ **PHP POST /documents/{id}/replace: Datei ersetzen + content_hash/file_size neu berechnen (v1.1.3)**
- ✅ **Python DocumentsAPI.replace_document_file(): Client-Methode fuer Datei-Ersetzung (v1.1.3)**
- ✅ **Cache-Invalidierung nach PDF-Speichern: Vorschau-Cache + Historie-Cache + Refresh (v1.1.3)**
- ✅ **Ungespeicherte-Aenderungen-Warnung beim Schliessen des PDF-Editors (v1.1.3)**
- ✅ **i18n: ~14 neue PDF_EDIT_* Keys fuer PDF-Bearbeitung (v1.1.3)**
- ✅ **App-Schließ-Schutz: Schliessen blockiert bei laufender KI-Verarbeitung/Kosten-Check/SmartScan (v1.1.4)**
- ✅ **Mitteilungszentrale: Dashboard mit System/Admin-Meldungen, Release-Info, Chat-Button (v2.0.0)**
- ✅ **System-Mitteilungen: API-Key oder Admin-Auth, Severity-Farben, per-User Read-Status (v2.0.0)**
- ✅ **1:1 Chat: Private Nachrichten zwischen Nutzern, Lesebestaetigung, Vollbild-View (v2.0.0)**
- ✅ **Notification-Polling: QTimer 30s im Main-Thread, Badge + Toast bei neuen Nachrichten (v2.0.0)**
- ✅ **Admin Mitteilungen-Panel: Erstellen, Loeschen, Tabelle mit allen Mitteilungen (v2.0.0)**
- ✅ **DB: 4 neue Tabellen (messages, message_reads, private_conversations, private_messages) (v2.0.0)**
- ✅ **i18n: ~60 neue Keys (MSG_CENTER_, CHAT_, ADMIN_MSG_) (v2.0.0)**
- ✅ **get_blocking_operations(): Neue Methode in ArchiveBoxesView prueft blockierende Worker (v1.1.4)**
- ✅ **MainHub.closeEvent(): Blocking-Check vor GDV-Check, Toast-Warnung bei Block (v1.1.4)**
- ✅ **i18n: 4 neue CLOSE_BLOCKED_* Keys fuer Schliess-Schutz (v1.1.4)**
- ✅ **QTableView-Migration: QTableWidget durch QTableView+QAbstractTableModel ersetzt (v2.0.1)**
- ✅ **DocumentTableModel: Virtualisiertes Rendering - nur sichtbare Zeilen werden gerendert (~30 statt 500+)**
- ✅ **DocumentSortFilterProxy: Sortierung (Datum nach ISO) + Textsuche im Proxy statt manueller Iteration**
- ✅ **DraggableDocumentView: QTableView mit Drag-Unterstuetzung (portiert von DraggableDocumentTable)**
- ✅ **Performance: 531 Dokumente: 0.1ms statt ~50s Freeze, 5000 Dokumente: <500ms**
- ✅ **Entfernte Klassen: SortableTableWidgetItem, DraggableDocumentTable (QTableWidget-basiert)**
- ✅ **Leere-Seiten-Erkennung: 4-Stufen-Algorithmus (Text, Vektoren, Bilder, Pixel@50DPI) (v2.0.2)**
- ✅ **empty_page_detector.py: Eigenstaendiges Modul mit is_page_empty() + get_empty_pages() (v2.0.2)**
- ✅ **DB: empty_page_count + total_page_count Spalten in documents-Tabelle (v2.0.2)**
- ✅ **Archiv-Tabelle: Neue Spalte COL_EMPTY_PAGES mit Icons (○ rot / ◑ orange) und Tooltip (v2.0.2)**
- ✅ **document_processor: _check_and_log_empty_pages() in allen 3 PDF-Zweigen nach _validate_pdf() (v2.0.2)**
- ✅ **Rein informativ: Leere-Seiten-Erkennung blockiert NICHT die normale KI-Pipeline (v2.0.2)**
- ✅ **Volltext + KI-Daten-Persistierung: Separates document_ai_data Tabelle (1:1 zu documents) (v2.0.3)**
- ✅ **extracted_text MEDIUMTEXT mit FULLTEXT-Index fuer Volltextsuche (v2.0.3)**
- ✅ **ai_full_response LONGTEXT fuer komplette KI-Rohantworten (v2.0.3)**
- ✅ **text_char_count + ai_response_char_count fuer Groessen-Analyse (v2.0.3)**
- ✅ **Content-Duplikat-Erkennung: documents.content_duplicate_of_id fuer Inhaltsduplikate (v2.0.3)**
- ✅ **extracted_text_sha256 fuer semantische Duplikat-Erkennung (gleicher Text, verschiedene Datei) (v2.0.3)**
- ✅ **Archiv-Tabelle: ≡-Icon (indigo) fuer Content-Duplikate neben ⚠-Icon (amber) fuer Datei-Duplikate (v2.0.3)**
- ✅ **Proaktive Text-Extraktion: Text sofort nach Upload extrahiert (BEVOR KI-Pipeline) (v2.0.3)**
- ✅ **early_text_extract.py: Utility fuer sofortige Text-Extraktion + Duplikat-Check (v2.0.3)**
- ✅ **MissingAiDataWorker: Hintergrund-Worker fuer Scan-Dokumente bei App-Start (v2.0.3)**
- ✅ **GET /documents/missing-ai-data: PHP-Endpoint fuer Dokumente ohne AI-Data (v2.0.3)**
- ✅ **DB-Migration 017: document_ai_data Tabelle mit CASCADE-Delete (v2.0.3)**
- ✅ **DB-Migration 018: content_duplicate_of_id Spalte + Backfill (v2.0.3)**
- ✅ **PDF-Unlock-Fix: api_client korrekt durchgereicht fuer MSG/ZIP-Anhaenge (v2.0.4)**
- ✅ **ValueError-Handling: Passwortgeschuetzte PDFs ohne Passwort crashen nicht mehr (v2.0.4)**
- ✅ **msg_handler.py: api_client Parameter fuer PDF-Unlock in extract_msg_attachments() (v2.0.4)**
- ✅ **document_ai_data Tabelle: Separate 1:1-Tabelle fuer Volltext + KI-Daten (v2.0.2)**
- ✅ **Volltext-Extraktion: Alle Seiten via PyMuPDF, FULLTEXT-Index fuer spaetere Suche (v2.0.2)**
- ✅ **KI-Rohantwort + Prompt + Token-Verbrauch werden pro Dokument persistiert (v2.0.2)**
- ✅ **Token-Durchreichung: _usage/_raw_response/_prompt_text in classify_*-Funktionen (v2.0.2)**
- ✅ **5 Performance-Regeln: Keine Auto-Joins, kein SELECT*, API getrennt, kein Trigger, kein Lazy-Load (v2.0.2)**
- ✅ **CASCADE-Delete: document_ai_data wird bei Dokument-Loeschung mitgeloescht (DSGVO) (v2.0.2)**
- ✅ **PHP-Endpoints: POST/GET /documents/{id}/ai-data (Upsert + Lesen) (v2.0.2)**
- ✅ **ATLAS Index: Virtuelle Such-Box ganz oben in Archiv-Sidebar (v2.0.5)**
- ✅ **GET /documents/search: Volltextsuche mit FULLTEXT-Index + filename LIKE (v2.0.5)**
- ✅ **SearchResult Dataclass: Document + text_preview + relevance_score (v2.0.5)**
- ✅ **AtlasIndexWidget: Snippet-basierte Ergebnisdarstellung (Google-Stil) (v2.0.5)**
- ✅ **SearchWorker: QThread fuer nicht-blockierenden Such-API-Call (v2.0.5)**
- ✅ **BOOLEAN MODE Sanitizer: Sonderzeichen-Entfernung verhindert SQL-Fehler (v2.0.5)**
- ✅ **Client-seitige Snippet-Aufbereitung: Kontext um ersten Treffer mit Bold-Highlighting (v2.0.5)**
- ✅ **Live-Suche Checkbox: Abschaltbar bei Performance-Problemen (v2.0.5)**
- ✅ **"In Box anzeigen": Wechselt zur echten Box + selektiert Dokument in Tabelle (v2.0.5)**
- ✅ **i18n: 13 neue ATLAS_INDEX_* Keys (v2.0.5)**
- ✅ **ATLAS Index XML/GDV-Filter: Rohdaten und GDV-Dateien standardmaessig ausgeblendet (v2.1.0)**
- ✅ **ATLAS Index Teilstring-Suche: LIKE statt FULLTEXT per Checkbox aktivierbar (v2.1.0)**
- ✅ **ATLAS Index Smart-Snippet: LOCATE-basierte Text-Preview-Extraktion um Treffer herum (v2.1.0)**
- ✅ **ATLAS Index Such-Button: Erscheint wenn Live-Suche deaktiviert ist (v2.1.0)**
- ✅ **ATLAS Index Snippet-Fix: Zweistufige Suche (voller Begriff, dann Einzelwoerter) (v2.1.0)**
- ✅ **i18n: 3 neue ATLAS_INDEX_* Keys (SEARCH_BUTTON, INCLUDE_RAW, SUBSTRING_SEARCH) (v2.1.0)**
- ✅ **KI-Klassifikation Admin-Panel: Pipeline-Visualisierung + Prompt-Editor + Modell-Auswahl (v2.1.1)**
- ✅ **Stufe 2 auf GPT-4o-mini umgestellt: ~17x Kostensenkung bei Detail-Klassifikation (v2.1.1)**
- ✅ **Prompt-Versionierung: Gespeicherte Versionen mit Label, aktivierbar im Admin (v2.1.1)**
- ✅ **Konfigurierbare KI-Pipeline: Stufe 2 deaktivierbar, Trigger konfigurierbar (low/low+medium) (v2.1.1)**
- ✅ **Dynamische KI-Settings: document_processor laedt Settings pro Verarbeitungslauf vom Server (v2.1.1)**
- ✅ **DB-Migration 019: processing_ai_settings + prompt_versions Tabellen (v2.1.1)**
- ✅ **PHP API: processing_settings.php mit Public GET + Admin CRUD + Prompt-Versionen (v2.1.1)**
- ✅ **Python ProcessingSettingsAPI Client: get_ai_settings, save, get_versions, activate (v2.1.1)**
- ✅ **openrouter.py parametrisierbar: classify_sparte_with_date() akzeptiert Prompt/Model/Tokens als Parameter (v2.1.1)**
- ✅ **Admin-Sidebar: Neue Sektion VERARBEITUNG mit KI-Klassifikation Panel (Index 6) (v2.1.1)**
- ✅ **i18n: ~45 neue PROCESSING_AI_ Keys fuer KI-Klassifikation Admin-Panel (v2.1.1)**
- ✅ **KI-Provider-System: Dynamisches Routing OpenRouter ↔ OpenAI im Admin konfigurierbar (v2.1.2)**
- ✅ **Provider-Verwaltung (Admin): CRUD fuer API-Keys mit AES-256-GCM Verschluesselung (v2.1.2)**
- ✅ **OpenAI-Direktanbindung: callOpenAIProvider() in ai.php, ~96% Kostenersparnis (v2.1.2)**
- ✅ **Modell-Preise: model_pricing Tabelle mit Input/Output-Preis pro 1M Tokens (v2.1.2)**
- ✅ **Exakte Kostenberechnung: real_cost_usd pro Request aus Tokens + model_pricing (v2.1.2)**
- ✅ **ai_requests Logging: Jeder KI-Call in DB geloggt (User, Provider, Model, Tokens, Kosten) (v2.1.2)**
- ✅ **Akkumulierte Batch-Kosten: ProcessingResult.cost_usd + BatchProcessingResult.total_cost_usd (v2.1.2)**
- ✅ **Token-Schaetzung: tiktoken fuer praezise Token-Zaehlung vor dem Request (v2.1.2)**
- ✅ **CostCalculator: estimate_from_messages() + calculate_real_cost() (v2.1.2)**
- ✅ **Provider-aware Credits: OpenRouter Balance vs. OpenAI Billing, dynamischer Delay (v2.1.2)**
- ✅ **KI-Kosten-Tab erweitert: Einzelne Requests Tabelle mit Zeitraum-Filter (v2.1.2)**
- ✅ **KI-Klassifikation dynamisch: Modell-Liste passt sich aktivem Provider an (v2.1.2)**
- ✅ **Modell-Mapping: openai/gpt-4o-mini (OpenRouter) ↔ gpt-4o-mini (OpenAI) (v2.1.2)**
- ✅ **DB-Migration 020: ai_provider_keys + model_pricing + ai_requests Tabellen (v2.1.2)**
- ✅ **PHP: ai_providers.php + model_pricing.php neue API-Dateien (v2.1.2)**
- ✅ **Python: ai_providers.py + model_pricing.py + cost_calculator.py + ai_models.py (v2.1.2)**
- ✅ **i18n: ~65 neue Keys (AI_PROVIDER_, MODEL_PRICING_, AI_COSTS_REQUESTS_) (v2.1.2)**
- ✅ **PDF-Vorschau Multi-Selection: Strg+Klick, Shift+Klick, Strg+A fuer Mehrfachauswahl in Thumbnail-Sidebar (v2.1.3)**
- ✅ **PDF Bulk-Rotation/Loeschung: Mehrere Seiten gleichzeitig drehen oder loeschen (v2.1.3)**
- ✅ **PDFRefreshWorker: Leere-Seiten + Text nach PDF-Speichern automatisch aktualisieren (v2.1.3)**
- ✅ **Dokumenten-Regeln Admin-Panel: Konfigurierbare Aktionen fuer Duplikate und leere Seiten (v2.1.3)**
- ✅ **4 Regel-Kategorien: Datei-Duplikate, Inhaltsduplikate, teilweise leere PDFs, komplett leere Dateien (v2.1.3)**
- ✅ **Automatische Leere-Seiten-Entfernung: PyMuPDF-basiert mit Server-Upload und Cache-Invalidierung (v2.1.3)**
- ✅ **Duplikat-Regelanwendung: Farbmarkierung oder Loeschung bei Erkennung (v2.1.3)**
- ✅ **DB-Tabelle document_rules_settings: Single-Row-Konfiguration fuer alle Dokumenten-Regeln (v2.1.3)**
- ✅ **PHP API: document_rules.php mit Public GET + Admin PUT (v2.1.3)**
- ✅ **Python DocumentRulesAPI Client: get_rules() + save_rules() (v2.1.3)**
- ✅ **Cache-Wipe bei ungültiger Session: Preview-Cache wird beim Start geleert wenn Session abgelaufen (v2.1.3)**
- ✅ **i18n: ~40 neue Keys (DOC_RULES_*, PDF_EDIT_DELETE_MULTI_*, PDF_EDIT_MIN_ONE_*, PDF_EDIT_MULTI_*, PDF_EDIT_REFRESH*) (v2.1.3)**

### TODO - DRINGEND
- ✅ ~~OpenRouter als Mittelsmann eliminieren~~ → **ERLEDIGT v2.1.2**: KI-Provider-System unterstuetzt jetzt OpenRouter UND direkte OpenAI-API. Umschaltbar im Admin. ~96% Kostenersparnis bei OpenAI-Direktanbindung.

### In Arbeit / Bekannte Issues
- ⚠️ UI-Texte nicht in i18n-Datei (Hardcoded Strings)
- ⚠️ Kein Linter/Formatter konfiguriert
- ⚠️ Keine Unit-Tests (nur manuelle Tests)
- ⚠️ Große Dateien können langsam laden
- ⚠️ Migration `setup/migration_admin.php` muss vor erstem Start ausgefuehrt werden
- ⚠️ Nach Migration: Alle bestehenden JWTs ungueltig (Session-Check), Nutzer muessen sich neu einloggen

### Tech Debt
- `bipro_view.py` ist sehr gross (~4900+ Zeilen) → Aufteilen: ParallelDownloadManager + MailImportWorker in eigene Dateien
- `archive_boxes_view.py` ist sehr gross (~6350 Zeilen) → SmartScanWorker, BoxDownloadWorker, AtlasIndexWidget in eigene Dateien
- `admin_view.py` ist sehr gross (~5200+ Zeilen) → 15 Panels in separate Dateien aufteilen
- `main_hub.py` ist gewachsen (~1324 Zeilen) → NotificationPoller + DropUploadWorker auslagern
- `main_window.py` ist zu gross (~1060 Zeilen) → Aufteilen
- `openrouter.py` ist gross (~1760+ Zeilen) → Triage/Klassifikation separieren
- `partner_view.py` enthaelt viel Datenextraktion → nach `domain/` verschieben
- Inline-Styles in Qt (gegen User-Rule) → CSS-Module einfuehren
- MTOM-Parser in `bipro_view.py` ist Duplikat von `transfer_service.py` → Konsolidieren
- `QFont::setPointSize: Point size <= 0 (-1)` Warnings beim Start → Font-Initialisierung pruefen
- Chat-Polling (30s) erzeugt bei vielen Nutzern Last → WebSocket-Migration in Phase 2 geplant

---

## Tasks (Roadmap)

### Phase 1: Server-Grundgerüst ✅ ABGESCHLOSSEN
- [x] PHP-API Struktur auf Strato
- [x] Datenbank-Schema definiert
- [x] DB-Setup ausgeführt
- [x] Admin-User erstellt
- [x] API-Client in Desktop-App

### Phase 2: Dokumentenarchiv ✅ ABGESCHLOSSEN
- [x] Upload/Download über API
- [x] Archive-View in Desktop-App
- [x] PDF-Vorschau integriert
- [x] Multi-Download/Multi-Delete
- [x] BiPRO-Dokumente automatisch archivieren

### Phase 3: BiPRO Degenia Pilot ✅ ABGESCHLOSSEN
- [x] SOAP-Client für BiPRO 430 mit STS-Token-Flow
- [x] VU-Verbindungsverwaltung
- [x] listShipments mit Kategorien-Anzeige
- [x] getShipment mit MTOM/XOP-Support
- [x] Automatischer Upload ins Archiv
- [ ] acknowledgeShipment testen (optional)

### Phase 4: Erweiterung (NÄCHSTE SCHRITTE)
- [ ] Weitere VUs anbinden (z.B. Signal Iduna, Nürnberger)
- [ ] i18n für UI-Texte
- [ ] Unit-Tests
- [ ] Linter/Formatter einrichten (ruff)
- [ ] Logging-Konfiguration verbessern

---

## Debugging & How-To

### Anwendung starten
```bash
cd "X:\projekte\5510_GDV Tool V1"
python run.py
```

### Parser testen
```bash
cd "X:\projekte\5510_GDV Tool V1"
python -m src.parser.gdv_parser
```

### Testdaten erstellen
```bash
cd "X:\projekte\5510_GDV Tool V1\testdata"
python create_testdata.py
```

### Roundtrip-Test
```bash
cd "X:\projekte\5510_GDV Tool V1\testdata"
python test_roundtrip.py
```

### BiPRO testen
1. App starten: `python run.py`
2. Einloggen als `admin`
3. "BiPRO Datenabruf" in Navigation wählen
4. Degenia-Verbindung auswählen
5. Lieferungen werden automatisch geladen
6. "Alle herunterladen" oder einzeln auswählen

### Typische Probleme

**Problem**: Umlaute werden falsch angezeigt  
**Lösung**: Encoding ist nicht CP1252. Prüfe `parsed_file.encoding` nach dem Laden.

**Problem**: Felder werden nicht korrekt geparst  
**Lösung**: Layout-Definition in `gdv_layouts.py` prüfen. Positionen sind 1-basiert!

**Problem**: Teildatensatz nicht erkannt  
**Lösung**: Position 256 muss die Teildatensatz-Nummer enthalten (1-9).

**Problem**: BiPRO listShipments gibt "keine Lieferungen"  
**Lösung**: VEMA-API-Credentials verwenden (nicht Portal-Passwort!) und STS-Token-Flow nutzen.

**Problem**: BiPRO STS gibt kein Token zurück  
**Lösung**: Portal-Passwort (ACA555) funktioniert NICHT für API. VEMA-Passwort verwenden!

**Problem**: BiPRO Kategorien führen zu Schema-Fehler  
**Lösung**: Degenia akzeptiert nur Requests OHNE `KategorieDerLieferung`. Kategorien werden in Response geliefert.

**Problem**: PDF-Vorschau zeigt nichts an  
**Lösung**: QPdfView benötigt PySide6 >= 6.4. Prüfe Installation: `pip install --upgrade PySide6`

**Problem**: API-Fehler "Unauthorized"  
**Lösung**: JWT-Token abgelaufen. App neu starten oder Abmelden/Anmelden.

**Problem**: XML-Dateien landen in "sonstige" statt "roh"  
**Lösung**: Bug in v0.9.0 - if/elif-Kette war gebrochen. In v0.9.1 behoben.

**Problem**: GDV-Dateien mit .pdf Endung werden als PDF behandelt  
**Lösung**: BiPRO-Code 999xxx wird jetzt korrekt als GDV erkannt (v0.9.1).

**Problem**: PDFs sind nach BiPRO-Download korrupt  
**Lösung**: MTOM-Parsing verbessert + automatische PDF-Reparatur mit PyMuPDF (v0.9.1).

**Problem**: Auto-Refresh läuft während Downloads/Verarbeitung  
**Lösung**: `DataCacheService.pause_auto_refresh()` wird automatisch aufgerufen (v0.9.1).

**Problem**: BiPRO-Download schlägt fehl mit "can't compare offset-naive and offset-aware datetimes"  
**Lösung**: Token-Ablaufzeit von BiPRO ist timezone-aware (+00:00). Fix: `datetime.now(timezone.utc)` statt `datetime.now()` in `transfer_service.py` (v0.9.2).

**Problem**: BiPRO-Dokumente haben .bin Endung statt .pdf  
**Lösung**: MIME-Type zu Extension Mapping via `mime_to_extension()` Funktion. Bei fehlendem Dateinamen wird der MIME-Type (`application/pdf`) zur Endung konvertiert (v0.9.2).

**Problem**: processing_history/create gibt HTTP 500  
**Lösung**: `processing_history.php` hatte falsche Imports (`database.php` statt `lib/db.php`, `helpers.php` statt `lib/response.php`). Zusaetzlich: `require_auth()` → `JWT::requireAuth()`, `get_json_input()` → `get_json_body()`. Fix in v0.9.4.

**Problem**: Verarbeitung dauert 290s fuer 75 Dokumente  
**Lösung**: War verursacht durch processing_history 500er mit 3 Retries x 7s pro Call. Nach Fix: 2.6s fuer 4 Dokumente (v0.9.4).

**Problem**: PDFs werden als Courtage klassifiziert obwohl es Kuendigungen/Mahnungen sind  
**Lösung**: Prompt verschaerft: Courtage = NUR Provisionsabrechnungen. Negativ-Beispiele im Prompt. 6/6 Testdokumente korrekt (v0.9.4).

**Problem**: PDFs mit Begleitschreiben auf Seite 1 werden falsch klassifiziert  
**Lösung**: Text-Extraktion von 1 auf 2 Seiten erhoehen (3000 Zeichen statt 2500). Damit sieht die KI auch den eigentlichen Inhalt (v0.9.4).

**Problem**: Deadlock bei JWT Token-Refresh  
**Lösung**: `_try_auth_refresh()` nutzt `acquire(blocking=False)` statt `with lock:`. Verhindert Deadlock bei rekursivem Aufruf aus `verify_token()` → `get()` → 401 (v0.9.4).

---

## Wichtige Dateipfade

### Desktop-App (Python)

| Pfad | Beschreibung |
|------|--------------|
| `run.py` | Entry Point |
| `src/main.py` | Qt-App Initialisierung |
| `src/parser/gdv_parser.py` | Parser (parse_file, save_file) |
| `src/layouts/gdv_layouts.py` | Satzart-Definitionen |
| `src/domain/models.py` | Domain-Klassen |
| `src/ui/main_hub.py` | Navigation zwischen Bereichen + Schliess-Schutz + NotificationPoller (~1324 Zeilen) |
| `src/ui/message_center_view.py` | **Mitteilungszentrale Dashboard (3 Kacheln) NEU v2.0.0** |
| `src/ui/chat_view.py` | **Vollbild-Chat-View (1:1 Nachrichten) NEU v2.0.0** |
| `src/ui/main_window.py` | GDV-Editor Hauptfenster |
| `src/ui/partner_view.py` | Partner-Übersicht |
| `src/ui/bipro_view.py` | **BiPRO UI (~4900 Zeilen) (VU-Verwaltung, ParallelDownloadManager, MailImportWorker)** |
| `src/ui/archive_boxes_view.py` | **Dokumentenarchiv mit Box-System + QTableView/Model-Architektur + SmartScan + Duplikat + Schliess-Schutz + ATLAS Index (~6350 Zeilen)** |
| `src/ui/archive_view.py` | Legacy-Archiv-View + `PDFViewerDialog` (Multi-Selection + PDFRefreshWorker) + `DuplicateCompareDialog` (Side-by-Side-Vergleich) |
| `src/api/client.py` | API-Base-Client |
| `src/api/documents.py` | **Dokumenten-API (Box-Support, Bulk-Ops, Duplikat-Erkennung, Farbmarkierung, ATLAS Index Suche)** |
| `src/api/vu_connections.py` | VU-Verbindungen API |
| `src/api/openrouter.py` | **OpenRouter Client (Zweistufige KI-Klassifikation + Confidence)** |
| `src/api/processing_history.py` | **Processing-History API Client (Audit-Trail)** |
| `src/api/processing_settings.py` | **Processing-Settings API Client (KI-Klassifikation) NEU v2.1.1** |
| `src/api/document_rules.py` | **DocumentRulesSettings + DocumentRulesAPI Client NEU v2.1.3** |
| `src/api/ai_providers.py` | **KI-Provider API Client (AIProviderKey, AIProvidersAPI) NEU v2.1.2** |
| `src/api/model_pricing.py` | **Modell-Preise + KI-Request-Historie API Client NEU v2.1.2** |
| `src/services/cost_calculator.py` | **Token-Zaehlung (tiktoken) + Kostenberechnung NEU v2.1.2** |
| `src/config/ai_models.py` | **Zentrale Modell-Definitionen pro Provider NEU v2.1.2** |
| `src/services/document_processor.py` | **Automatische Dokumenten-Klassifikation mit Confidence-Handling + AI-Daten-Persistierung + dynamische KI-Settings + akkumulierte Kosten + Dokumenten-Regeln** |
| `src/services/data_cache.py` | **DataCacheService (Cache + Auto-Refresh, Thread-safe v0.9.4)** |
| `src/config/processing_rules.py` | **Konfigurierbare Verarbeitungsregeln + BiPRO-Codes** |
| `src/bipro/transfer_service.py` | BiPRO 430 Client (STS + Transfer + SharedTokenManager, ~1334 Zeilen) |
| `src/bipro/bipro_connector.py` | **BiPRO-Verbindungsabstraktion (SmartAdmin vs. Standard, ~397 Zeilen)** |
| `src/bipro/rate_limiter.py` | **AdaptiveRateLimiter (NEU v0.9.1)** |
| `src/bipro/categories.py` | Kategorie-Code Mapping |
| `src/services/update_service.py` | **UpdateService (Auto-Update Check + Download + Install)** |
| `src/services/zip_handler.py` | **ZIP-Handler (Entpacken, Passwort, rekursiv) NEU v1.0.5** |
| `src/services/pdf_unlock.py` | **PDF-Unlock (dynamische Passwoerter aus DB) v1.0.5** |
| `src/services/empty_page_detector.py` | **Leere-Seiten-Erkennung (4-Stufen: Text, Vektoren, Bilder, Pixel) NEU v2.0.2** |
| `src/services/msg_handler.py` | **MSG-Handler (Outlook .msg Anhaenge extrahieren) NEU v1.0.4** |
| `src/services/atomic_ops.py` | **Atomic File Operations (SHA256, Staging, Safe-Write)** |
| `src/ui/update_dialog.py` | **UpdateDialog (3 Modi: optional/mandatory/deprecated)** |
| `src/ui/toast.py` | **ToastManager + ToastWidget + ProgressToastWidget (Globales Toast-System) v1.0.7/v1.0.9** |
| `src/ui/gdv_editor_view.py` | **GDV-Editor View (RecordTable + Editor, ~648 Zeilen)** |
| `src/ui/login_dialog.py` | **Login-Dialog (Anmeldung + Auto-Login + Cache-Wipe bei ungültiger Session)** |
| `src/ui/user_detail_view.py` | **Benutzerfreundliche Detail-Ansicht (editierbare Felder)** |
| `src/ui/settings_dialog.py` | **Einstellungen-Dialog (Zertifikate verwalten, ~350 Zeilen)** |
| `src/ui/styles/tokens.py` | **ACENCIA Design-Tokens (Farben, Fonts, Styles, ~977 Zeilen)** |
| `docs/ui/UX_RULES.md` | **Verbindliche UI-Regeln: Keine modalen Popups, Toast-Spezifikation NEU v1.0.7** |
| `src/api/releases.py` | **ReleasesAPI Client (Admin CRUD + Public Check)** |
| `src/api/passwords.py` | **PasswordsAPI Client (Passwort-Verwaltung) NEU v1.0.5** |
| `src/api/smartscan.py` | **SmartScanAPI + EmailAccountsAPI Clients (NEU v1.0.6)** |
| `src/api/messages.py` | **MessagesAPI Client (Mitteilungen + Polling) NEU v2.0.0** |
| `src/api/chat.py` | **ChatAPI Client (1:1 Chat-Nachrichten) NEU v2.0.0** |
| `src/api/auth.py` | **AuthAPI Client (Login, User-Model mit Permissions)** |
| `src/api/gdv_api.py` | **GDV API Client (GDV-Dateien server-seitig parsen/speichern)** |
| `src/api/xml_index.py` | **XML-Index API Client (BiPRO-XML-Rohdaten-Index)** |
| `src/api/smartadmin_auth.py` | **SmartAdmin-Authentifizierung (SAML-Token, 47 VUs, ~640 Zeilen)** |
| `src/config/smartadmin_endpoints.py` | **SmartAdmin VU-Endpunkte (47 Versicherer, Auth-Typen)** |
| `src/config/certificates.py` | **Zertifikat-Manager (PFX/P12, X.509)** |
| `src/i18n/de.py` | **Zentrale i18n-Datei (~1170 Keys: DOC_RULES_, AI_PROVIDER_, MODEL_PRICING_, AI_COSTS_REQUESTS_, PROCESSING_AI_, ATLAS_INDEX_, MSG_CENTER_, CHAT_, ADMIN_MSG_, CLOSE_BLOCKED_, DUPLICATE_, SHORTCUT_, SMARTSCAN_, EMAIL_, etc.)** |
| `VERSION` | **Zentrale Versionsdatei (Single Source of Truth)** |
| `BIPRO_STATUS.md` | Aktueller Stand der BiPRO-Integration |

### Server-API (PHP) - LIVE SYNCHRONISIERT!

| Pfad | Beschreibung |
|------|--------------|
| `BiPro-Webspace Spiegelung Live/` | **Synchronisiert mit Strato!** |
| `→ api/config.php` | DB-Credentials, Master-Key (SENSIBEL!) |
| `→ api/index.php` | API-Router |
| `→ api/auth.php` | Login/Logout/Token |
| `→ api/documents.php` | Dokumenten-Endpunkte + ATLAS Index Volltextsuche |
| `→ api/gdv.php` | GDV-Operationen |
| `→ api/credentials.php` | VU-Verbindungen |
| `→ api/shipments.php` | Lieferungen |
| `→ api/processing_history.php` | **Audit-Trail (gefixt v0.9.4)** |
| `→ api/processing_settings.php` | **KI-Klassifikation Einstellungen (Public GET + Admin CRUD) NEU v2.1.1** |
| `→ api/ai.php` | **Zentraler KI-Proxy (OpenRouter/OpenAI Routing, Kosten, PII-Redaktion) v2.1.2** |
| `→ api/ai_providers.php` | **KI-Provider-Verwaltung (CRUD, Aktivierung, Test) NEU v2.1.2** |
| `→ api/model_pricing.php` | **Modell-Preise + Kosten-Helpers + Request-Logging NEU v2.1.2** |
| `→ api/document_rules.php` | **Dokumenten-Regeln Settings (Public GET + Admin PUT) NEU v2.1.3** |
| `→ api/releases.php` | **Release-Verwaltung + Update-Check (NEU v0.9.9)** |
| `→ api/incoming_scans.php` | **Scan-Upload fuer Power Automate (API-Key-Auth) (NEU v1.0.2)** |
| `→ api/passwords.php` | **Passwort-Verwaltung (PDF/ZIP) Public + Admin (NEU v1.0.5)** |
| `→ api/smartscan.php` | **SmartScan Settings + Send + Chunk + Historie (NEU v1.0.6)** |
| `→ api/email_accounts.php` | **E-Mail-Konten CRUD + SMTP-Test + IMAP-Polling (NEU v1.0.6)** |
| `→ api/messages.php` | **Mitteilungen API (System + Admin, Read-Status) NEU v2.0.0** |
| `→ api/chat.php` | **1:1 Chat API (Conversations, Messages, Read) NEU v2.0.0** |
| `→ api/notifications.php` | **Leichtgewichtiger Polling-Endpoint (Unread-Counts + Toast) NEU v2.0.0** |
| `→ api/xml_index.php` | **XML-Index fuer BiPRO-Rohdaten (CRUD + Suche)** |
| `→ api/lib/PHPMailer/` | **PHPMailer v6.9.3 (3 Dateien, SMTP-Versand) (NEU v1.0.6)** |
| `→ releases/` | **Release-Dateien Storage (Installer-EXEs)** |
| `→ dokumente/` | Datei-Storage (nicht web-zugänglich) |

### Sonstige

| Pfad | Beschreibung |
|------|--------------|
| `testdata/sample.gdv` | Test-GDV-Datei |
| `src/tests/run_smoke_tests.py` | **Smoke-Tests (Stabilitaets-Upgrade v0.9.4)** |
| `scripts/run_checks.py` | **Minimal-CI Script (Lint + Tests)** |
| `requirements-dev.txt` | **Dev-Dependencies (pytest, ruff)** |
| `logs/bipro_gdv.log` | **Persistentes Log-File (Rotation 5 MB, 3 Backups)** |
| `tools/decrypt_iwm_password.py` | **IWM FinanzOffice Passwort-Entschluesselung (Analyse-Tool)** |
| `STABILITY_UPGRADE/` | **Audit-Reports des Stabilitaets-Upgrades** |
| `Kontext/` | Generierte Projektanalyse |
| `Bugs/` | Generierte Bug-Analyse |
| `docs/` | ARCHITECTURE.md, DEVELOPMENT.md, DOMAIN.md, BIPRO_ENDPOINTS.md |

---

## Kontakt & Ressourcen

- **GDV-Spezifikation**: https://www.gdv-online.de/vuvm/bestand/
- **BiPRO-Spezifikation**: https://www.bipro.net/
- **API-Dokumentation**: `BiPro-Webspace Spiegelung Live/README.md`
- **Interne Doku**: `GDV- Daten Dokumentation.txt`

### Degenia Ansprechpartner

**Viktor Kerber**  
degenia Versicherungsdienst AG  
Fon: 0671 84003 140  
viktor.kerber@degenia.de
