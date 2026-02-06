# 05 - Laufzeit und Flows

**Version:** 0.9.3  
**Analyse-Datum:** 2026-02-05

---

## Anwendungsstart

```
[python run.py]
    │
    ▼
[sys.path erweitern] ──▶ src/ hinzufügen
    │
    ▼
[main() aufrufen] ──▶ src/main.py
    │
    ▼
[QApplication erstellen]
    │
    ├──▶ App-Name: "BiPRO-GDV Tool"
    ├──▶ Version: "0.8.0"
    ├──▶ Organisation: "ACENCIA GmbH"
    │
    ▼
[Font setzen] ──▶ Open Sans (Fallback: Segoe UI)
    │
    ▼
[Stylesheet setzen] ──▶ get_application_stylesheet()
    │
    ▼
[LoginDialog anzeigen]
    │
    ├──▶ [Abbruch] ──▶ sys.exit(0)
    │
    └──▶ [Erfolg] ──▶ api_client, auth_api
                         │
                         ▼
                    [MainHub erstellen]
                         │
                         ▼
                    [window.show()]
                         │
                         ▼
                    [app.exec()] ──▶ Event-Loop
```

---

## Login-Flow

```
[LoginDialog]
    │
    ▼
[Benutzer gibt ein] ──▶ username, password
    │
    ▼
[POST /auth/login] ─────────────────────────────────▶ PHP API
    │                                                    │
    │ ◀───────────────────────────────────────────────────
    │                                       token, user_data
    ▼
[Token speichern] ──▶ api_client.set_token(token)
    │
    ▼
[AuthAPI.current_user setzen]
    │
    ▼
[dialog.accept()]
```

**API-Request:**
```
POST https://acencia.info/api/auth/login
Content-Type: application/json

{
    "username": "admin",
    "password": "..."
}
```

**API-Response:**
```json
{
    "success": true,
    "data": {
        "token": "eyJ...",
        "user": {
            "id": 1,
            "username": "admin",
            "role": "admin"
        }
    }
}
```

---

## BiPRO-Abruf Flow

### 1. VU-Verbindung auswählen

```
[VU in Liste klicken]
    │
    ▼
[_on_vu_selected()]
    │
    ▼
[Credentials vom Server holen] ───────────────────▶ PHP API
    │                                    GET /vu-connections/{id}/credentials
    ▼
[BiPROCredentials erstellen]
    │
    ├──▶ username, password
    ├──▶ endpoint_url (Transfer)
    └──▶ sts_endpoint_url (STS)
    │
    ▼
[TransferServiceClient erstellen]
    │
    ▼
[ListShipmentsWorker starten] ──▶ QThread
```

### 2. Lieferungen auflisten

```
[ListShipmentsWorker.run()]
    │
    ▼
[_get_sts_token()] ───────────────────────────────▶ BiPRO 410 STS
    │                                                (Degenia)
    │ ◀──────────────────────────────────────────────
    │                                SecurityContextToken
    ▼
[list_shipments()] ───────────────────────────────▶ BiPRO 430 Transfer
    │
    │ ◀──────────────────────────────────────────────
    │                                List[ShipmentInfo]
    ▼
[shipments_loaded.emit(shipments)]
    │
    ▼
[_on_shipments_loaded()] ──▶ Tabelle aktualisieren
```

### 3. Lieferung herunterladen (v0.9.2: Parallelisiert + Timezone-aware)

```
[Download-Button klicken]
    │
    ▼
[DataCacheService.pause_auto_refresh()] ◀───── v0.9.1
    │
    ▼
[ParallelDownloadManager starten] ──▶ QThread + ThreadPoolExecutor
    │                                 (max. 10 Worker, auto-adjustiert auf Anzahl Lieferungen)
    │
    │  ┌───────────────────────────────────────────────────────┐
    │  │ Pro Lieferung (parallel):                             │
    │  │                                                       │
    │  │ [SharedTokenManager.get_valid_token()] ◀── timezone-aware (v0.9.2) │
    │  │     │                                                 │
    │  │     ▼                                                 │
    │  │ [get_shipment()] ───────────▶ BiPRO 430 Transfer     │
    │  │     │                                                 │
    │  │     │ ◀───────────────────── MTOM/XOP Response       │
    │  │     ▼                                                 │
    │  │ [_parse_mtom_response()] ──▶ OHNE strip() (Fix!)    │
    │  │     │                                                 │
    │  │     ▼                                                 │
    │  │ [mime_to_extension()] ──▶ MIME→Endung (v0.9.2)      │
    │  │     │                                                 │
    │  │     ▼                                                 │
    │  │ [_validate_pdf()] ──▶ Magic Bytes prüfen            │
    │  │     │                                                 │
    │  │     ├──▶ OK? ────▶ Speichern                        │
    │  │     └──▶ Korrupt? ▶ PyMuPDF Reparatur → Speichern   │
    │  │                                                       │
    │  │ [Bei 429/503]: AdaptiveRateLimiter                  │
    │  │     → Worker reduzieren, Backoff, Retry             │
    │  └───────────────────────────────────────────────────────┘
    │
    ▼
[Upload ins Archiv] ─────────────────────────────▶ PHP API
    │                        POST /documents + bipro_category
    ▼
[DataCacheService.resume_auto_refresh()] ◀───── v0.9.1
    │
    ▼
[documents_uploaded.emit()]
```

---

## Dokumentenverarbeitungs-Flow

### 1. Upload (manuell oder BiPRO)

```
[Datei hochladen]
    │
    ▼
[POST /documents] ────────────────────────────────▶ PHP API
    │                    file, source_type, box_type='eingang'
    ▼
[Dokument in Eingangsbox]
```

### 2. Automatische Verarbeitung

```
[DocumentProcessor.process_inbox()]
    │
    ▼
[list_by_box('eingang')] ────────────────────────▶ PHP API
    │
    │ ◀──────────────────────────────────────────────
    │                                List[Document]
    ▼
[ThreadPoolExecutor (4 Worker)]
    │
    │  ┌──────────────────────────────────────────────────────┐
    │  │ Für jedes Dokument parallel:                         │
    │  │                                                       │
    │  │ [_process_document()]                                │
    │  │     │                                                 │
    │  │     ▼                                                 │
    │  │ [In Verarbeitungsbox verschieben]                    │
    │  │     │                                                 │
    │  │     ▼                                                 │
    │  │ [_classify_document()]                               │
    │  │     │                                                 │
    │  │     ├──▶ XML + "Roh"? ─────▶ target_box = 'roh'     │
    │  │     ├──▶ .gdv/.txt?   ─────▶ target_box = 'gdv'     │
    │  │     └──▶ PDF?         ─────▶ KI-Klassifikation      │
    │  │                                    │                  │
    │  │                                    ▼                  │
    │  │                          [_classify_pdf_with_ai()]   │
    │  │                                    │                  │
    │  │                                    ▼                  │
    │  │                          [OpenRouterClient          │
    │  │                           .classify_pdf()]           │
    │  │                                    │                  │
    │  │                                    ▼                  │
    │  │                          [DocumentClassification]    │
    │  │                                    │                  │
    │  │                                    ├──▶ courtage     │
    │  │                                    ├──▶ sach         │
    │  │                                    ├──▶ leben        │
    │  │                                    ├──▶ kranken      │
    │  │                                    └──▶ sonstige     │
    │  │     │                                                 │
    │  │     ▼                                                 │
    │  │ [In Ziel-Box verschieben]                            │
    │  │ [Optional: Umbenennen]                               │
    │  │                                                       │
    │  └──────────────────────────────────────────────────────┘
    │
    ▼
[List[ProcessingResult]]
```

### 3. KI-Klassifikation mit Kosten-Tracking (v0.9.3)

```
[Batch-Verarbeitung starten]
    │
    ▼
[OpenRouterClient.get_credits()] ◀───────────── v0.9.3 Kosten-Tracking
    │                                            credits_before speichern
    ▼
[OpenRouterClient.classify_pdf()]
    │
    ▼
[PDF öffnen] ──▶ PyMuPDF (fitz)
    │
    ▼
[Text extrahieren] ──▶ page.get_text()
    │
    ├──▶ > 100 Zeichen? ──▶ Direkt verwenden
    │
    └──▶ < 100 Zeichen? ──▶ Vision-OCR
                               │
                               ▼
                          [pdf_to_images()]
                               │
                               ▼
                          [extract_text_from_images()] ──▶ OpenRouter
                                                           GPT-4o Vision
    │
    ▼
[classify_document(text)] ──────────────────────▶ OpenRouter
    │                                              GPT-4o + Structured Output
    │ ◀──────────────────────────────────────────────
    │                                DocumentClassification
    │                                {
    │                                  target_box: "courtage",
    │                                  confidence: "high",
    │                                  reasoning: "Provisionsabrechnung",
    │                                  insurer: "Helvetia",
    │                                  document_date_iso: "2025-01-15",
    │                                  document_type: null,
    │                                  insurance_type: "Leben"
    │                                }
    ▼
[generate_filename()] ──▶ "Helvetia_Courtage_Leben_2025-01-15.pdf"
                          "Degenia_2025-01-15.pdf" (Courtage: VU_Name + Datum)
    │
    ▼
[OpenRouterClient.get_credits()] ◀───────────── v0.9.3 Kosten-Tracking
    │                                            credits_after speichern
    ▼
[BatchProcessingResult erstellen]
    │
    ├──▶ total_cost_usd = credits_before - credits_after
    └──▶ cost_per_document_usd = total_cost_usd / successful_documents
```

**Kosten-Anzeige im Fazit (v0.9.3):**
- Gesamtkosten: `$0.0234 USD`
- Pro Dokument: `$0.000234 USD`

---

## GDV-Editor Flow

### 1. Datei öffnen

```
[Menü → Datei → Öffnen]
    │
    ▼
[QFileDialog] ──▶ Pfad auswählen
    │
    ▼
[parse_file(path)]
    │
    ├──▶ [Encoding erkennen] ──▶ CP1252 → Latin-1 → UTF-8
    │
    ├──▶ [Zeilen lesen] ──▶ 256 Bytes pro Zeile
    │
    └──▶ [parse_record()] für jede Zeile
             │
             ├──▶ Satzart aus Position 1-4
             ├──▶ Teildatensatz aus Position 256
             └──▶ Layout nachschlagen → Felder parsen
    │
    ▼
[ParsedFile]
    │
    ▼
[map_parsed_file_to_gdv_data()]
    │
    ▼
[GDVData] ──▶ contracts, customers, risks, coverages
    │
    ▼
[UI aktualisieren]
    │
    ├──▶ [RecordTableWidget] ──▶ Alle Sätze in Tabelle
    ├──▶ [DetailWidget] ──▶ Felder des ausgewählten Satzes
    └──▶ [PartnerView] ──▶ Firmen/Personen (0100)
```

### 2. Speichern

```
[Menü → Datei → Speichern]
    │
    ▼
[save_file(parsed_file, path)]
    │
    ▼
[Für jeden Record]
    │
    ├──▶ Zeile aus 256 Leerzeichen initialisieren
    │
    ├──▶ Felder an Position schreiben
    │
    └──▶ Mit originalem Encoding kodieren
    │
    ▼
[Datei schreiben]
```

---

## Shutdown-Flow

```
[Fenster schließen]
    │
    ▼
[closeEvent()]
    │
    ├──▶ [Ungespeicherte Änderungen prüfen]
    │         │
    │         ├──▶ Ja → Bestätigung anfordern
    │         │
    │         └──▶ Nein → Fortfahren
    │
    ├──▶ [Worker-Threads aufräumen]
    │         │
    │         └──▶ BiPROView.cleanup() falls geladen
    │
    └──▶ [event.accept()]
```

---

## Thread-Übersicht

| Thread | Klasse | Datei | Zweck |
|--------|--------|-------|-------|
| Main | - | - | Qt Event-Loop, UI |
| ListShipments | `ListShipmentsWorker` | `bipro_view.py` | BiPRO-Lieferungen abfragen |
| Download (Legacy) | `DownloadWorker` | `bipro_view.py` | Sequentielle Downloads |
| **ParallelDownload** | **`ParallelDownloadManager`** | `bipro_view.py` | **Parallele Downloads (v0.9.1)** |
| MultiUpload | `MultiUploadWorker` | `archive_boxes_view.py` | Mehrere Dateien hochladen |
| MultiDownload | `MultiDownloadWorker` | `archive_boxes_view.py` | Mehrere Dateien herunterladen |
| AIRename | `AIRenameWorker` | `archive_boxes_view.py` | KI-Umbenennung |
| Credits | `CreditsWorker` | `archive_boxes_view.py` | OpenRouter-Guthaben abrufen |
| Processing | `ThreadPoolExecutor` | `document_processor.py` | Parallele Dokumentenverarbeitung |
| **ProcessingWorker** | `ProcessingWorker` | `archive_boxes_view.py` | Verarbeitung im Hintergrund |

**Thread-Sicherheit (v0.9.2):** 
- `closeEvent()` wartet auf Worker-Beendigung
- Progress-Callbacks mit `threading.Lock`
- **SharedTokenManager:** `threading.Lock` für Token-Zugriff, **timezone-aware Token-Vergleich**
- **AdaptiveRateLimiter:** `threading.Lock` für Worker-Zähler
- **DataCacheService:** Counter-basiertes pause/resume für verschachtelte Aufrufe
- **Worker-Anpassung:** Automatische Reduktion auf Lieferungsanzahl wenn < max_workers
