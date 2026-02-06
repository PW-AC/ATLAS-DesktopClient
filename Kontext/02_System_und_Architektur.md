# 02 - System und Architektur

**Version:** 0.9.3  
**Analyse-Datum:** 2026-02-05

---

## Systemübersicht

Das BiPRO-GDV Tool ist eine **4-Schichten-Architektur** mit Desktop-Client, Server-Backend, externen Diensten und lokalen Dateien:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Desktop-App (PySide6/Qt)                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                           UI Layer                                          │
│  ┌─────────────┐ ┌─────────────┐ ┌───────────────┐ ┌───────────────────┐   │
│  │ main_hub.py │ │bipro_view.py│ │archive_boxes_ │ │ gdv_editor_view.py│   │
│  │ Navigation  │ │ BiPRO-Abruf │ │ view.py       │ │ GDV-Editor        │   │
│  │             │ │ VU-Verwalt. │ │ Box-System    │ │                   │   │
│  └──────┬──────┘ └──────┬──────┘ └──────┬────────┘ └─────────┬─────────┘   │
└─────────┼───────────────┼───────────────┼───────────────────┼──────────────┘
          │               │               │                   │
          ▼               ▼               ▼                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Service Layer                                       │
│  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐ ┌───────────┐ │
│  │   API Client    │ │   BiPRO Client  │ │ DocumentProcessor│ │  Parser   │ │
│  │   (src/api/)    │ │   (src/bipro/)  │ │ (src/services/) │ │(src/parser)│ │
│  │   - client.py   │ │   - transfer_   │ │   Parallele     │ │- gdv_     │ │
│  │   - documents.py│ │     service.py  │ │   Verarbeitung  │ │  parser.py│ │
│  │   - openrouter  │ │   - categories  │ │   KI-Klassifik. │ │           │ │
│  └────────┬────────┘ └────────┬────────┘ └────────┬────────┘ └─────┬─────┘ │
└───────────┼───────────────────┼───────────────────┼───────────────┼────────┘
            │                   │                   │               │
            ▼                   ▼                   ▼               ▼
┌───────────────────┐ ┌───────────────────┐ ┌───────────────┐ ┌─────────────┐
│  Strato Webspace  │ │   Versicherer     │ │  OpenRouter   │ │   Lokales   │
│  PHP REST API     │ │   BiPRO Services  │ │  API (KI)     │ │ Dateisystem │
│  MySQL Datenbank  │ │   (z.B. Degenia)  │ │  GPT-4o       │ │ GDV-Dateien │
│  Dokumente-Speicher│ │                   │ │               │ │             │
└───────────────────┘ └───────────────────┘ └───────────────┘ └─────────────┘
```

---

## Schichten im Detail

### 1. UI Layer (`src/ui/`)

| Komponente | Datei | Zeilen | Beschreibung |
|------------|-------|--------|--------------|
| MainHub | `main_hub.py` | ~395 | Navigation, Sidebar, Bereichswechsel |
| BiPROView | `bipro_view.py` | **~3865** | VU-Verbindungen, Lieferungsliste, **ParallelDownloadManager (v0.9.1)** |
| ArchiveBoxesView | `archive_boxes_view.py` | ~1400 | Box-System, PDF-Vorschau, KI-Verarbeitung |
| GDVEditorView | `gdv_editor_view.py` | - | GDV-Dateien bearbeiten |
| PartnerView | `partner_view.py` | ~1165 | Firmen/Personen-Übersicht |
| MainWindow | `main_window.py` | ~914 | GDV-Editor Hauptfenster |
| LoginDialog | `login_dialog.py` | - | JWT-Authentifizierung |

**Design-System:** ACENCIA Corporate Identity via `src/ui/styles/tokens.py`
- Dunkle Sidebar (#001f3d)
- Orange Akzente (#fa9939)
- Tenor Sans (Headlines), Open Sans (Body)

### 2. Service Layer

#### API Client (`src/api/`)

| Klasse | Datei | Beschreibung |
|--------|-------|--------------|
| APIClient | `client.py` | Basis-HTTP-Client mit JWT, Retry-Logik |
| DocumentsAPI | `documents.py` | Dokumenten-CRUD, Box-Operationen |
| OpenRouterClient | `openrouter.py` | KI-Klassifikation, PDF-OCR |
| AuthAPI | `auth.py` | Login/Logout |
| VUConnectionsAPI | `vu_connections.py` | VU-Verbindungen verwalten |

#### BiPRO Client (`src/bipro/`)

| Klasse | Datei | Beschreibung |
|--------|-------|--------------|
| TransferServiceClient | `transfer_service.py` | BiPRO 410 STS + BiPRO 430 Transfer |
| **SharedTokenManager** | `transfer_service.py` | **Thread-sicheres STS-Token-Management, timezone-aware (v0.9.2)** |
| BiPROCredentials | `transfer_service.py` | Zugangsdaten (Username/Password oder Zertifikat) |
| ShipmentInfo | `transfer_service.py` | Lieferungs-Metadaten |
| ShipmentContent | `transfer_service.py` | Lieferungs-Inhalt (Dokumente) |
| **AdaptiveRateLimiter** | `rate_limiter.py` | **Dynamische Rate-Anpassung bei 429/503 (v0.9.1)** |

**Wichtig (v0.9.2):** Token-Ablaufzeiten werden jetzt timezone-aware verglichen (`datetime.now(timezone.utc)`), da Degenia UTC-Zeitstempel zurückgibt.

#### Document Processor & Services (`src/services/`)

| Klasse | Datei | Beschreibung |
|--------|-------|--------------|
| DocumentProcessor | `document_processor.py` | Parallele Verarbeitung (ThreadPoolExecutor) |
| ProcessingResult | `document_processor.py` | Ergebnis einer Verarbeitung |
| **BatchProcessingResult** | `document_processor.py` | **Batch-Ergebnis mit Kosten-Tracking (v0.9.3)** |
| **DataCacheService** | `data_cache.py` | **Singleton-Cache mit pause/resume_auto_refresh (v0.9.1)** |

**Neu in v0.9.3 - Kosten-Tracking:**
- `credits_before`: OpenRouter-Guthaben vor Verarbeitung
- `credits_after`: OpenRouter-Guthaben nach Verarbeitung
- `total_cost_usd`: Gesamtkosten in USD
- `cost_per_document_usd`: Durchschnittskosten pro Dokument

### 3. Parser Layer (`src/parser/`, `src/layouts/`)

| Komponente | Datei | Beschreibung |
|------------|-------|--------------|
| GDV Parser | `gdv_parser.py` | Fixed-Width Parser (256 Bytes/Zeile) |
| Layout-Definitionen | `gdv_layouts.py` | Satzart-Strukturen als Metadaten |

### 4. Domain Layer (`src/domain/`)

| Klasse | Datei | Beschreibung |
|--------|-------|--------------|
| GDVData | `models.py` | Container für alle geladenen Daten |
| Contract | `models.py` | Versicherungsvertrag |
| Customer | `models.py` | Kunde/Partner |
| Risk | `models.py` | Wagnis |
| Coverage | `models.py` | Deckung |

---

## Datenflüsse

### 1. BiPRO-Abruf (v0.9.2: Parallelisiert + Timezone-aware)

```
[VU auswählen]
    │
    ▼ (automatisch)
[STS-Token holen] ─────────────────────────────────────▶ BiPRO 410 STS
    │                                                    (Degenia)
    │ SecurityContextToken
    ▼
[listShipments] ───────────────────────────────────────▶ BiPRO 430 Transfer
    │
    │ Liste der Lieferungen
    ▼
[Tabelle aktualisieren]
    │
    ▼ (Download klicken)
[DataCacheService.pause_auto_refresh()] ←─────────────── v0.9.1
    │
    ▼
[ParallelDownloadManager] ←──────────────────────────── v0.9.2
    │ (max. 10 Worker, auto-adjustiert auf Lieferungsanzahl)
    │
    ├──▶ [SharedTokenManager] ──▶ Token wiederverwenden
    │
    ├──▶ [AdaptiveRateLimiter] ─▶ Backoff bei 429/503
    │
    └──▶ [getShipment (parallel)] ────────────────────▶ BiPRO 430 Transfer
              │
              │ MTOM/XOP Response mit Dokumenten
              ▼
         [MTOM parsen] ──▶ PDFs extrahieren
              │
              ▼
         [PDF validieren/reparieren] ←──────────────── v0.9.1 (PyMuPDF)
              │
              ▼
         [Archiv-Upload] ─────────────────────────────▶ PHP REST API
    │
    ▼
[DataCacheService.resume_auto_refresh()] ←────────────── v0.9.1
    │
    ▼
[Automatische Klassifikation] ─────────────────────────▶ OpenRouter (GPT-4o)
    │
    ▼
[In Ziel-Box verschieben]
```

### 2. Dokumentenarchiv (v0.9.1: if/elif-Kette korrigiert)

```
[Upload / BiPRO-Download]
    │
    ▼
[Eingangsbox]
    │
    ▼ (automatische Verarbeitung)
[DataCacheService.pause_auto_refresh()] ←────────────── v0.9.1
    │
    ▼
[Verarbeitungsbox]
    │
    ├──▶ XML? ─────────────────▶ [Roh Archiv]         ← if _is_xml_raw()
    │
    ├──▶ GDV (Endung)? ────────▶ [GDV Box]            ← elif _is_gdv_file()
    │
    ├──▶ GDV (BiPRO 999xxx)? ──▶ [GDV Box] ←───────── v0.9.1 elif _is_bipro_gdv()
    │
    ├──▶ PDF + BiPRO-Code? ────▶ [Courtage/Sparte]    ← elif doc.is_pdf and bipro_category
    │         │
    │         ├──▶ 300xxx? ────▶ [Courtage Box]
    │         │
    │         └──▶ Andere? ────▶ [KI für Sparte]
    │
    ├──▶ PDF (ohne BiPRO)? ────▶ [KI-Klassifikation]  ← elif doc.is_pdf
    │         │
    │         ├──▶ Courtage? ──▶ [Courtage Box]
    │         ├──▶ Sach? ──────▶ [Sach Box]
    │         ├──▶ Leben? ─────▶ [Leben Box]
    │         ├──▶ Kranken? ───▶ [Kranken Box]
    │         └──▶ Sonstige ───▶ [Sonstige Box]
    │
    └──▶ Unbekannt ────────────▶ [Sonstige Box]       ← else
    │
    ▼
[DataCacheService.resume_auto_refresh()] ←────────────── v0.9.1
```

### 3. GDV-Editor

```
[GDV-Datei öffnen]
    │
    ▼ parse_file()
[ParsedFile] ─────▶ Records, Felder, Encoding
    │
    ▼ map_parsed_file_to_gdv_data()
[GDVData]
    │
    ├──▶ [RecordTableWidget] ──▶ Satz-Übersicht
    │
    ├──▶ [DetailWidget] ───────▶ Felder bearbeiten
    │
    └──▶ [PartnerView] ────────▶ Firmen/Personen
```

---

## Externe Systeme

### 1. Strato Webspace (PHP REST API)

| Aspekt | Details |
|--------|---------|
| Domain | `https://acencia.info/` |
| API Base | `https://acencia.info/api/` |
| DB Server | `database-5019508812.webspace-host.com` |
| DB Name | `dbs15252975` |
| **Synchronisation** | `BiPro-Webspace Spiegelung Live/` ist LIVE synchronisiert! |

### 2. BiPRO Services (Versicherer)

| VU | STS-Endpoint | Transfer-Endpoint | Status |
|----|--------------|-------------------|--------|
| Degenia | `https://transfer.degenia.de/.../410_STS/...` | `https://transfer.degenia.de/.../430_Transfer/...` | ✅ Funktioniert |
| Weitere | - | - | 🔜 Geplant |

### 3. OpenRouter (KI)

| Aspekt | Details |
|--------|---------|
| Base URL | `https://openrouter.ai/api/v1` |
| Modell | GPT-4o (Vision + Structured Output) |
| Verwendung | PDF-Klassifikation, OCR, Entity-Extraktion |
| API-Key | Wird vom Server abgerufen (`/api/ai/key`) |
| **Kosten-Tracking (v0.9.3)** | Guthaben-Abfrage vor/nach Verarbeitung |

**Erweiterte Klassifikation (v0.9.3):**
- **Sach**: Privathaftpflicht, PHV, Tierhalterhaftpflicht, Hundehaftpflicht, Bauherrenhaftpflicht
- **Leben**: Pensionskasse, Rentenanstalt
- **Courtage**: Benennung mit `VU_Name + Datum`

---

## Kommunikationsprotokolle

| Verbindung | Protokoll | Authentifizierung |
|------------|-----------|-------------------|
| Desktop ↔ PHP API | HTTPS REST | JWT Bearer Token |
| Desktop ↔ BiPRO | HTTPS SOAP | STS-Token (BiPRO 410) oder X.509 |
| Desktop ↔ OpenRouter | HTTPS REST | Bearer Token |
| PHP API ↔ MySQL | TCP | Credentials in config.php |
