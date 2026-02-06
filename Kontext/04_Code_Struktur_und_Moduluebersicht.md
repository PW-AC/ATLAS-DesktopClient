# 04 - Code-Struktur und Modulübersicht

**Version:** 0.9.3  
**Analyse-Datum:** 2026-02-05

---

## Ordnerstruktur

```
5510_GDV Tool V1/
├── run.py                           # Entry Point
├── requirements.txt                 # Python-Abhängigkeiten
├── AGENTS.md                        # Agent-Anweisungen (aktuell halten!)
├── README.md                        # Projekt-Dokumentation
├── BIPRO_STATUS.md                  # BiPRO-Integrationsstatus
│
├── src/                             # Hauptcode (Python)
│   ├── __init__.py
│   ├── main.py                      # Qt-App Initialisierung
│   │
│   ├── api/                         # Server-API Clients
│   │   ├── __init__.py
│   │   ├── client.py                # Basis-HTTP-Client mit JWT
│   │   ├── auth.py                  # Login/Logout
│   │   ├── documents.py             # Dokumenten-API mit Box-System
│   │   ├── vu_connections.py        # VU-Verbindungen
│   │   ├── gdv_api.py               # GDV-Server-Operationen
│   │   └── openrouter.py            # KI-Klassifikation (GPT-4o)
│   │
│   ├── bipro/                       # BiPRO SOAP Client
│   │   ├── __init__.py
│   │   ├── transfer_service.py      # BiPRO 410 STS + 430 Transfer + SharedTokenManager
│   │   ├── rate_limiter.py          # AdaptiveRateLimiter (NEU v0.9.1)
│   │   └── categories.py            # Kategorie-Code Mapping
│   │
│   ├── config/                      # Konfiguration
│   │   ├── __init__.py
│   │   └── processing_rules.py      # Verarbeitungsregeln + BiPRO-GDV-Codes (999xxx)
│   │
│   ├── domain/                      # Fachliche Modelle
│   │   ├── __init__.py
│   │   ├── models.py                # Contract, Customer, Risk, Coverage
│   │   └── mapper.py                # ParsedRecord → Domain-Objekt
│   │
│   ├── layouts/                     # GDV-Satzart-Definitionen
│   │   ├── __init__.py
│   │   └── gdv_layouts.py           # LAYOUT_0001, LAYOUT_0100, etc.
│   │
│   ├── parser/                      # GDV-Parser
│   │   ├── __init__.py
│   │   └── gdv_parser.py            # Fixed-Width Parser
│   │
│   ├── services/                    # Business-Logik
│   │   ├── __init__.py
│   │   ├── document_processor.py    # Parallele Dokumentenverarbeitung
│   │   └── data_cache.py            # DataCacheService (NEU v0.9.1)
│   │
│   └── ui/                          # Benutzeroberfläche
│       ├── __init__.py
│       ├── main_hub.py              # Navigation
│       ├── bipro_view.py            # BiPRO-Datenabruf (~1972 Zeilen)
│       ├── archive_boxes_view.py    # Dokumentenarchiv mit Box-System
│       ├── archive_view.py          # Legacy-Archiv (noch vorhanden)
│       ├── gdv_editor_view.py       # GDV-Editor View
│       ├── main_window.py           # GDV-Editor Hauptfenster
│       ├── partner_view.py          # Partner-Übersicht
│       ├── user_detail_view.py      # Benutzer-Detail-Ansicht
│       ├── login_dialog.py          # Login-Dialog
│       └── styles/
│           ├── __init__.py
│           └── tokens.py            # ACENCIA Design Tokens
│
├── BiPro-Webspace Spiegelung Live/  # Server-API (LIVE synchronisiert!)
│   ├── README.md
│   ├── .htaccess
│   ├── api/
│   │   ├── .htaccess                # URL-Rewriting, Schutz
│   │   ├── index.php                # API-Router
│   │   ├── config.php               # Credentials (SENSIBEL!)
│   │   ├── auth.php                 # Login/Logout/Token
│   │   ├── documents.php            # Dokumenten-Endpunkte
│   │   ├── gdv.php                  # GDV-Operationen
│   │   ├── credentials.php          # VU-Verbindungen
│   │   ├── shipments.php            # Lieferungen
│   │   └── ai.php                   # OpenRouter API-Key
│   ├── dokumente/                   # Datei-Storage (nicht synchronisiert!)
│   └── setup/                       # DB-Setup-Skripte
│
├── testdata/                        # Testdaten
│   ├── sample.gdv                   # Generierte Testdatei
│   ├── create_testdata.py           # Testdaten erstellen
│   └── test_roundtrip.py            # Roundtrip-Test
│
├── docs/                            # Dokumentation
│   ├── ARCHITECTURE.md
│   ├── DEVELOPMENT.md
│   ├── DOMAIN.md
│   └── BIPRO_ENDPOINTS.md
│
├── Kontext/                         # Diese Dokumentation
│
└── Projekt Ziel/                    # Konzepte, BiPRO-Infos
```

---

## Kernmodule im Detail

### `src/main.py`

Entry Point der Qt-Anwendung.

| Funktion | Beschreibung |
|----------|--------------|
| `main()` | Startet QApplication, zeigt LoginDialog, erstellt MainHub |

**Flow:**
1. QApplication erstellen
2. Font und Stylesheet setzen (ACENCIA Design)
3. LoginDialog anzeigen
4. Bei Erfolg: MainHub erstellen und anzeigen

### `src/ui/main_hub.py`

Navigation zwischen den Bereichen.

| Klasse | Beschreibung |
|--------|--------------|
| `NavButton` | Sidebar-Button mit Hover/Active-States |
| `MainHub` | QMainWindow mit Sidebar und QStackedWidget |

**Bereiche:**
- BiPRO Datenabruf (Index 0)
- Dokumentenarchiv (Index 1)
- GDV Editor (Index 2)
- VU-Verbindungen (Index 3) - zeigt Info, verweist auf BiPRO

**Lazy Loading:** Views werden erst bei erstem Zugriff geladen.

### `src/ui/bipro_view.py` (~3865 Zeilen, v0.9.1)

BiPRO-Datenabruf mit VU-Verwaltung und parallelen Downloads.

| Klasse | Beschreibung |
|--------|--------------|
| `BiPROView` | Hauptwidget |
| `VUConnectionDialog` | Dialog zum Erstellen/Bearbeiten von VU-Verbindungen |
| `ShipmentTableWidget` | Tabelle mit Lieferungen |
| `DownloadWorker` | QThread für sequentielle Downloads (Legacy) |
| `ListShipmentsWorker` | QThread für Lieferungs-Abfrage |
| **`ParallelDownloadManager`** | **QThread mit ThreadPoolExecutor für parallele Downloads (v0.9.1)** |
| **`BiPROProgressOverlay`** | **Fortschrittsanzeige für Downloads** |

**Neue Methoden (v0.9.1):**
- `_validate_pdf()` - PDF-Validierung und Reparatur mit PyMuPDF
- `_parse_mtom_response()` - Verbesserte MTOM-Parsing ohne strip()
- `_on_parallel_progress()` - Callback für Fortschritt
- `_on_parallel_all_finished()` - Callback mit Auto-Refresh Resume

**Signale:**
- `documents_uploaded` - Emittiert wenn Dokumente ins Archiv hochgeladen wurden

### `src/ui/archive_boxes_view.py`

Dokumentenarchiv mit Box-System.

| Klasse | Beschreibung |
|--------|--------------|
| `ArchiveBoxesView` | Hauptwidget mit Sidebar |
| `BoxSidebar` | Navigation mit Live-Zählern |
| `DocumentTableWidget` | Tabelle mit Dokumenten |
| `PDFViewerDialog` | Integrierte PDF-Vorschau (QPdfView) |
| `MultiUploadWorker` | Paralleler Upload mehrerer Dateien |
| `MultiDownloadWorker` | Paralleler Download |
| `AIRenameWorker` | KI-Umbenennung im Hintergrund |
| `CreditsWorker` | OpenRouter-Guthaben abrufen |

**Features:**
- Box-Navigation mit Zählern
- Kontext-Menü zum Verschieben
- PDF-Vorschau
- KI-Klassifikation
- OpenRouter Credits-Anzeige

### `src/bipro/transfer_service.py` (~1220 Zeilen)

BiPRO 410/430 SOAP-Client mit Thread-sicherem Token-Management.

| Klasse | Beschreibung |
|--------|--------------|
| `BiPROCredentials` | Zugangsdaten (Username/Password oder Zertifikat) |
| `ShipmentInfo` | Metadaten einer Lieferung |
| `ShipmentContent` | Inhalt mit Dokumenten |
| `TransferServiceClient` | SOAP-Client |
| **`SharedTokenManager`** | **Thread-sicheres STS-Token-Management (v0.9.1)** |

**Methoden:**
- `_get_sts_token()` - BiPRO 410 Token holen
- `list_shipments()` - Lieferungen auflisten
- `get_shipment()` - Lieferung abrufen (MTOM/XOP)
- `acknowledge_shipment()` - Empfang quittieren
- `_parse_mtom_response()` - Multipart-Response parsen

**SharedTokenManager (v0.9.1):**
- `get_valid_token()` - Token mit 1-Minute-Buffer vor Ablauf erneuern
- Thread-sicher mit `threading.Lock`
- Wird von ParallelDownloadManager verwendet

**Authentifizierung:**
1. Username/Password + STS-Token (Degenia)
2. PFX-Zertifikat (easy Login)
3. JKS-Zertifikat (Java KeyStore)
4. PEM-Zertifikat + Key

### `src/bipro/rate_limiter.py` (NEU v0.9.1)

Adaptive Rate-Limiting für parallele Downloads.

| Klasse | Beschreibung |
|--------|--------------|
| `RetryInfo` | Metadaten für Retry (Versuche, Backoff) |
| `AdaptiveRateLimiter` | Dynamische Worker-Anpassung |

**Methoden:**
- `on_rate_limit_detected()` - Worker reduzieren, Backoff erhöhen
- `on_success()` - Nach X Erfolgen Worker erhöhen
- `should_retry()` - Prüft ob Retry erlaubt

### `src/services/document_processor.py`

Parallele Dokumentenverarbeitung mit korrigierter if/elif-Logik (v0.9.1) und Kosten-Tracking (v0.9.3).

| Klasse | Beschreibung |
|--------|--------------|
| `ProcessingResult` | Ergebnis einer Verarbeitung |
| **`BatchProcessingResult`** | **Batch-Ergebnis mit Kosten-Tracking (v0.9.3)** |
| `DocumentProcessor` | Verarbeitungs-Service |

**BatchProcessingResult Attribute (v0.9.3):**
- `credits_before` - OpenRouter-Guthaben vor Verarbeitung
- `credits_after` - OpenRouter-Guthaben nach Verarbeitung
- `total_cost_usd` - Gesamtkosten in USD
- `cost_per_document_usd` - Durchschnittskosten pro Dokument
- `get_cost_summary()` - Formatierte Kosten-Zusammenfassung

**Methoden:**
- `process_inbox()` - Alle Dokumente in Eingangsbox verarbeiten (parallel) **mit Kosten-Tracking (v0.9.3)**
- `_process_document()` - Einzelnes Dokument klassifizieren
- `_is_xml_raw()` - XML-Rohdatei erkennen
- `_is_gdv_file()` - GDV-Datei über Endung erkennen
- **`_is_bipro_gdv()`** - **GDV über BiPRO-Code (999xxx) erkennen (v0.9.1)**
- `_is_bipro_courtage()` - Courtage über BiPRO-Code (300xxx) erkennen
- `_classify_pdf_with_ai()` - KI-Klassifikation via OpenRouter

**if/elif-Kette (v0.9.1 korrigiert):**
```python
if _is_xml_raw():      → 'roh'
elif _is_gdv_file():   → 'gdv' (Endung)
elif _is_bipro_gdv():  → 'gdv' (BiPRO 999xxx)  # NEU
elif is_pdf + bipro:   → Courtage/Sparte
elif is_pdf:           → KI-Klassifikation
else:                  → 'sonstige'
```

**Threading:** `ThreadPoolExecutor` mit 4 Workern (konfigurierbar)

### `src/services/data_cache.py` (NEU v0.9.1)

Zentraler Daten-Cache mit Auto-Refresh-Kontrolle.

| Klasse | Beschreibung |
|--------|--------------|
| `CacheEntry` | Cache-Eintrag mit Timestamp |
| `DataCacheService` | Singleton-Service |

**Methoden:**
- `get_documents()` / `get_stats()` - Daten aus Cache oder Server
- `start_auto_refresh()` - Timer starten (90s Standard)
- `stop_auto_refresh()` - Timer stoppen
- **`pause_auto_refresh()`** - **Temporär pausieren (Counter-basiert)**
- **`resume_auto_refresh()`** - **Fortsetzen nach Pause**

**Verwendung:**
- BiPRO-Downloads: Pausiert während `ParallelDownloadManager` läuft
- Dokumentenverarbeitung: Pausiert während `process_inbox()` läuft

### `src/api/openrouter.py` (~1054 Zeilen)

KI-Client für PDF-Klassifikation mit erweiterter Keyword-Erkennung (v0.9.3).

| Klasse | Beschreibung |
|--------|--------------|
| `DocumentClassification` | Ergebnis der Klassifikation |
| `ExtractedDocumentData` | Legacy-Datenstruktur |
| `OpenRouterClient` | API-Client |

**Methoden:**
- `get_credits()` - Guthaben abrufen **(für Kosten-Tracking, v0.9.3)**
- `pdf_to_images()` - PDF zu Base64-Bildern (PyMuPDF)
- `extract_text_from_images()` - Vision-OCR
- `classify_document()` - Text klassifizieren (Structured Output)
- `classify_pdf()` - Kompletter Workflow
- `classify_sparte_with_date()` - Sparten-Klassifikation mit Datumsextraktion

**Erweiterte Sach-Keywords (v0.9.3):**
- Privathaftpflicht, PHV, Tierhalterhaftpflicht, Hundehaftpflicht
- Haus- und Grundbesitzerhaftpflicht, Bauherrenhaftpflicht
- Jagdhaftpflicht, Gewaesserschadenhaftpflicht

**Erweiterte Leben-Keywords (v0.9.3):**
- Pensionskasse, Rentenanstalt

**Courtage-Benennung (v0.9.3):**
- Format: `VU_Name + Dokumentdatum` (z.B. `Degenia_2025-01-15.pdf`)

**Hilfsfunktionen:**
- `_safe_json_loads()` - Robustes JSON-Parsing
- `slug_de()` - Sichere Dateinamen (deutsche Umlaute)

### `src/parser/gdv_parser.py` (~786 Zeilen)

Fixed-Width GDV-Parser.

| Klasse | Beschreibung |
|--------|--------------|
| `ParsedField` | Einzelnes Feld |
| `ParsedRecord` | Einzelne Zeile/Satz |
| `ParsedFile` | Komplette Datei |

**Funktionen:**
- `parse_file()` - Datei laden und parsen
- `save_file()` - Datei speichern
- `parse_record()` - Einzelne Zeile parsen

**Encoding:** CP1252 → Latin-1 → UTF-8 (Fallback-Kette)

### `src/api/documents.py`

Dokumenten-API mit Box-System.

| Klasse | Beschreibung |
|--------|--------------|
| `Document` | Dokument-Datenstruktur |
| `BoxStats` | Statistiken für alle Boxen |
| `DocumentsAPI` | API-Client |

**Box-Operationen:**
- `list_by_box()` - Dokumente einer Box
- `get_box_stats()` - Zähler pro Box
- `move_documents()` - Dokumente verschieben
- `update()` - Metadaten aktualisieren

### `src/ui/styles/tokens.py` (~990 Zeilen)

ACENCIA Design Tokens.

| Kategorie | Beispiele |
|-----------|-----------|
| Primärfarben | `PRIMARY_900 = "#001f3d"`, `PRIMARY_500 = "#88a9c3"` |
| Akzentfarben | `ACCENT_500 = "#fa9939"` |
| Fonts | `FONT_HEADLINE = "Tenor Sans"`, `FONT_BODY = "Open Sans"` |
| Spacing | `SPACING_SM = "8px"`, `SPACING_MD = "16px"` |

**Funktionen:**
- `get_application_stylesheet()` - Komplettes Qt-Stylesheet
- `get_button_primary_style()` - Orange Button
- `show_error_dialog()` - Strukturierter Fehler-Dialog

---

## PHP API Struktur

### `BiPro-Webspace Spiegelung Live/api/`

| Datei | Endpunkte |
|-------|-----------|
| `auth.php` | POST /auth/login, POST /auth/logout |
| `documents.php` | GET/POST/PUT/DELETE /documents |
| `credentials.php` | GET/POST/DELETE /vu-connections |
| `shipments.php` | GET /shipments |
| `gdv.php` | GDV-spezifische Operationen |
| `ai.php` | GET /ai/key (OpenRouter API-Key) |
| `config.php` | Datenbank-Credentials, Master-Key |

**WICHTIG:** Der Ordner ist LIVE mit dem Strato Webspace synchronisiert!
