# AGENTS.md
# Agent Instructions for BiPRO-GDV Tool

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
| `setup/` | ✅ Ja | Migrations-Skripte (nach Ausführung löschen!) |

Der `dokumente/` Ordner enthält alle über die API hochgeladenen Dateien. Eine Synchronisierung würde diese Dateien löschen, da sie lokal nicht existieren.

### Sensible Dateien

Die Datei `BiPro-Webspace Spiegelung Live/api/config.php` enthält:
- Datenbank-Credentials
- Master-Key für Verschlüsselung
- JWT-Secret

**Diese Datei ist per .htaccess geschützt und NICHT direkt über HTTP aufrufbar.**

---

## Project Overview

Das **BiPRO-GDV Tool** ist eine Python-Desktop-Anwendung mit Server-Backend für:
- Automatisierten BiPRO-Datenabruf von Versicherungsunternehmen
- Zentrales Dokumentenarchiv für alle Nutzer (mit PDF-Vorschau)
- Erstellen, Anzeigen und Bearbeiten von GDV-Datensätzen

### Architektur (Überblick)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         BiPRO-GDV Tool v0.9.3                               │
├─────────────────────────────────────────────────────────────────────────────┤
│  Desktop-App (PySide6/Qt)                         Strato Webspace           │
│  ├── UI Layer                                     ├── PHP REST API          │
│  │   ├── main_hub.py (Navigation)                 │   ├── auth.php          │
│  │   ├── bipro_view.py (BiPRO-Abruf) ✅           │   ├── documents.php     │
│  │   ├── archive_view.py (Dok-Archiv) ✅          │   ├── gdv.php           │
│  │   ├── gdv_editor_view.py                       │   └── credentials.php   │
│  │   ├── partner_view.py                          ├── MySQL Datenbank       │
│  │   └── main_window.py                           └── Dokumente-Storage     │
│  ├── API Client                                                             │
│  │   ├── src/api/client.py                                                  │
│  │   ├── src/api/documents.py                                               │
│  │   └── src/api/vu_connections.py                                          │
│  ├── BiPRO SOAP Client ✅ FUNKTIONIERT                                      │
│  │   ├── src/bipro/transfer_service.py (STS + Transfer + SharedTokenManager)│
│  │   ├── src/bipro/rate_limiter.py (AdaptiveRateLimiter) **NEU v0.9.1**     │
│  │   └── src/bipro/categories.py (Kategorie-Mapping)                        │
│  ├── Services Layer **NEU v0.9.0**                                          │
│  │   ├── src/services/document_processor.py (Klassifikation)                │
│  │   └── src/services/data_cache.py (Cache + Auto-Refresh-Kontrolle)        │
│  └── Parser Layer                                                           │
│      ├── gdv_parser.py                                                      │
│      └── gdv_layouts.py                                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│  Datenflüsse:                                                               │
│  1. Desktop ←→ PHP-API ←→ MySQL/Dateien (Archiv, Auth, VU-Verbindungen)     │
│  2. Desktop → BiPRO SOAP → Versicherer (STS-Token + Transfer-Service)       │
│  3. BiPRO-Dokumente → Automatisch ins Dokumentenarchiv (via API)            │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Tech-Stack

| Komponente | Technologie | Version |
|------------|-------------|---------|
| Desktop | Python + PySide6 | 3.10+ / 6.6.0+ |
| PDF-Viewer | PySide6.QtPdf (QPdfView) | 6.6.0+ |
| PDF-Verarbeitung | PyMuPDF (fitz) | 1.23+ |
| HTTP Client | requests | 2.31+ |
| BiPRO SOAP | requests (raw XML, kein zeep) | 2.31+ |
| KI/LLM | OpenRouter API (GPT-4o) | - |
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

### Namenskonventionen
- **Satzarten**: Immer 4-stellig mit führenden Nullen (z.B. "0100", "0200")
- **Felder**: snake_case, deutsch (z.B. `versicherungsschein_nr`, `geburtsdatum`)
- **Klassen**: PascalCase (z.B. `ParsedRecord`, `GDVData`)
- **Datumsanzeige**: Deutsches Format in UI (DD.MM.YYYY)

### Error-Handling
- Parser gibt immer `ParsedFile` zurück (auch bei Fehlern)
- Fehler/Warnungen werden in `ParsedFile.errors`/`warnings` gesammelt
- UI zeigt Fehler via `QMessageBox`, keine stummen Fehler
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
  - `src/ui/bipro_view.py` (~3800+ Zeilen) → UI + ParallelDownloadManager
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

### 2a. KI-basierte PDF-Klassifikation und Benennung (v0.8.0)
- **Zweck**: PDFs automatisch durch KI analysieren, klassifizieren und umbenennen
- **Benennungs-Schema**:
  - **Courtage**: `Versicherer_Courtage_Sparte_Datum.pdf` (z.B. `Helvetia_Courtage_Leben_2025-01-15.pdf`)
  - **Andere**: `Versicherer_Dokumenttyp_Datum.pdf` (z.B. `Allianz_Privathaftpflicht_2025-01-15.pdf`)
- **Klassifikation**:
  - **Kontext-Aware**: KI analysiert HAUPTZWECK, nicht nur Keywords
  - **Direktes Box-Assignment**: target_box wird direkt von KI bestimmt
  - **insurance_type**: Bei Courtage wird Sparte (Leben/Sach/Kranken) mitgegeben
- **Ablauf**:
  1. PDFs im Archiv auswählen oder automatische Verarbeitung
  2. PDF → Textextraktion (PyMuPDF) oder Vision-OCR wenn wenig Text
  3. Klassifikation via OpenRouter (GPT-4o) mit Structured Output
  4. Direktes Box-Assignment + Umbenennung auf Server
- **Robustheit (v0.8.0)**:
  - `_safe_json_loads()`: Robustes JSON-Parsing (Codefences, Whitespace)
  - `slug_de()`: Sichere Dateinamen-Generierung (Umlaute, Sonderzeichen)
  - Retry-Logik: 4 Versuche mit Backoff bei 429/502/503/504
  - `date_granularity`: Datum-Format je nach Genauigkeit (day/month/year)
- **Dateien**:
  - `src/api/openrouter.py` → OpenRouterClient, DocumentClassification, get_credits()
  - `src/ui/archive_boxes_view.py` → AIRenameWorker, CreditsWorker
  - `BiPro-Webspace Spiegelung Live/api/ai.php` → GET /ai/key

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

---

## Aktueller Stand (05. Februar 2026)

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

### In Arbeit / Bekannte Issues
- ⚠️ UI-Texte nicht in i18n-Datei (Hardcoded Strings)
- ⚠️ Kein Linter/Formatter konfiguriert
- ⚠️ Keine Unit-Tests (nur manuelle Tests)
- ⚠️ Große Dateien können langsam laden

### Tech Debt
- `bipro_view.py` ist sehr groß (~3800+ Zeilen) → Aufteilen: ParallelDownloadManager nach eigene Datei
- `main_window.py` ist zu groß (~914 Zeilen) → Aufteilen
- `openrouter.py` ist groß (~1500+ Zeilen) → Triage/Klassifikation separieren
- `partner_view.py` enthält viel Datenextraktion → nach `domain/` verschieben
- Inline-Styles in Qt (gegen User-Rule) → CSS-Module einführen
- MTOM-Parser in `bipro_view.py` ist Duplikat von `transfer_service.py` → Konsolidieren

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
| `src/ui/main_hub.py` | Navigation zwischen Bereichen |
| `src/ui/main_window.py` | GDV-Editor Hauptfenster |
| `src/ui/partner_view.py` | Partner-Übersicht |
| `src/ui/bipro_view.py` | **BiPRO UI (~3800+ Zeilen) (VU-Verwaltung, ParallelDownloadManager)** |
| `src/ui/archive_boxes_view.py` | **Dokumentenarchiv mit Box-System (NEU)** |
| `src/ui/archive_view.py` | Legacy-Archiv-View |
| `src/api/client.py` | API-Base-Client |
| `src/api/documents.py` | Dokumenten-API (mit Box-Support) |
| `src/api/vu_connections.py` | VU-Verbindungen API |
| `src/api/openrouter.py` | **OpenRouter Client (KI-Benennung)** |
| `src/services/document_processor.py` | **Automatische Dokumenten-Klassifikation** |
| `src/services/data_cache.py` | **DataCacheService (Cache + Auto-Refresh-Kontrolle)** |
| `src/config/processing_rules.py` | **Konfigurierbare Verarbeitungsregeln + BiPRO-Codes** |
| `src/bipro/transfer_service.py` | BiPRO 430 Client (STS + Transfer + SharedTokenManager) |
| `src/bipro/rate_limiter.py` | **AdaptiveRateLimiter (NEU v0.9.1)** |
| `src/bipro/categories.py` | Kategorie-Code Mapping |
| `BIPRO_STATUS.md` | Aktueller Stand der BiPRO-Integration |

### Server-API (PHP) - LIVE SYNCHRONISIERT!

| Pfad | Beschreibung |
|------|--------------|
| `BiPro-Webspace Spiegelung Live/` | **Synchronisiert mit Strato!** |
| `→ api/config.php` | DB-Credentials, Master-Key (SENSIBEL!) |
| `→ api/index.php` | API-Router |
| `→ api/auth.php` | Login/Logout/Token |
| `→ api/documents.php` | Dokumenten-Endpunkte |
| `→ api/gdv.php` | GDV-Operationen |
| `→ api/credentials.php` | VU-Verbindungen |
| `→ api/shipments.php` | Lieferungen |
| `→ dokumente/` | Datei-Storage (nicht web-zugänglich) |

### Sonstige

| Pfad | Beschreibung |
|------|--------------|
| `testdata/sample.gdv` | Test-GDV-Datei |
| `Projekt Ziel/` | Konzepte, BiPRO-Infos, Degenia SOAP-UI |
| `Kontext/` | Generierte Projektanalyse |
| `docs/` | ARCHITECTURE.md, DEVELOPMENT.md, DOMAIN.md |

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
