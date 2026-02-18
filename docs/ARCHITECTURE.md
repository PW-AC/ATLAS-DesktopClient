# Architektur - ACENCIA ATLAS v2.1.3

**Stand:** 18. Februar 2026

**Primaere Referenz: `AGENTS.md`** - Dieses Dokument enthaelt ergaenzende Architektur-Details. Fuer den aktuellen Feature-Stand und Debugging-Tipps siehe `AGENTS.md`.

## Neue Features in v2.1.3 (Dokumenten-Regeln + PDF Multi-Selection)

### Dokumenten-Regeln (Admin-konfigurierbar)
- **Zweck**: Automatische Aktionen bei Duplikaten und leeren Seiten waehrend der Dokumentenverarbeitung
- **Admin-Panel**: Panel 9 in Sektion VERARBEITUNG (nach KI-Klassifikation, KI-Provider, Modell-Preise)
- **4 Regel-Kategorien**: Datei-Duplikate, Inhaltsduplikate, teilweise leere PDFs, komplett leere Dateien
- **Aktionen**: Farbmarkierung (8 Farben), Loeschen, Leere-Seiten-Entfernung
- **Integration**: `document_processor._apply_document_rules()` nach `_persist_ai_data()`
- **DB-Tabelle**: `document_rules_settings` (Single-Row, id=1)

### PDF-Vorschau Multi-Selection
- **Thumbnail-Sidebar**: `ExtendedSelection` Modus (Strg+Klick, Shift+Klick, Strg+A)
- **Bulk-Operationen**: Mehrere Seiten gleichzeitig drehen oder loeschen
- **Auto-Refresh**: `PDFRefreshWorker` aktualisiert Leere-Seiten + Text nach Speichern

### Cache-Wipe bei ungültiger Session
- **Trigger**: `_try_auto_login()` stellt fest, dass Token ungueltig/nicht vorhanden
- **Aktion**: `_clear_local_caches()` loescht `%TEMP%/bipro_preview_cache/`

### Neue Endpunkte
| Endpunkt | Datei | Beschreibung |
|----------|-------|--------------|
| GET /document-rules | document_rules.php | Dokumenten-Regeln laden (Public, JWT) |
| PUT /admin/document-rules | document_rules.php | Regeln speichern (Admin) |

### Neue Python-Klassen
| Klasse | Datei | Beschreibung |
|--------|-------|--------------|
| `DocumentRulesSettings` | `src/api/document_rules.py` | Dataclass fuer Regel-Konfiguration |
| `DocumentRulesAPI` | `src/api/document_rules.py` | API Client (get_rules, save_rules) |
| `PDFRefreshWorker` | `src/ui/archive_view.py` | QThread: Leere-Seiten + Text nach Speichern aktualisieren |

### Neue DB-Tabelle (Migration 021)
| Tabelle | Beschreibung |
|---------|--------------|
| `document_rules_settings` | Single-Row: file_dup_action/color, content_dup_action/color, partial_empty_action/color, full_empty_action/color |

---

## Neue Features in v2.1.2 (KI-Provider-System)

### Dynamisches KI-Routing (OpenRouter ↔ OpenAI)
- **Zweck**: Provider-unabhaengige KI-Nutzung mit dynamischer Umschaltung im Admin
- **Architektur**: PHP-Proxy (`ai.php`) routet Requests je nach aktivem Provider
- **Modell-Mapping**: `mapModelName()` konvertiert zwischen Formaten (openai/gpt-4o-mini ↔ gpt-4o-mini)
- **PII-Redaktion**: Vor Weiterleitung an Provider werden E-Mail, IBAN, Telefon entfernt
- **Fallback**: Legacy-Key aus `config.php` wenn kein Provider in DB aktiv

### Provider-Verwaltung
- **DB-Tabelle**: `ai_provider_keys` mit `provider_type` ENUM('openrouter','openai'), AES-256-GCM verschluesselte Keys
- **Aktivierung**: Nur 1 Key gleichzeitig aktiv (global), alle anderen werden deaktiviert
- **Verbindungstest**: Test-Request an Provider-API mit minimalem Prompt
- **Admin-UI**: Eigenes Panel in Sektion VERARBEITUNG (CRUD, Aktivierung, Test, maskierte Keys)

### Exakte Kostenberechnung
- **Server-seitig**: `model_pricing.php` → `calculateCost()` berechnet USD aus Tokens + gespeicherten Preisen
- **Request-Logging**: Jeder KI-Call wird in `ai_requests` geloggt (User, Provider, Model, Tokens, geschaetzt + echt)
- **Client-seitig**: `CostCalculator` (tiktoken) zaehlt Tokens vor dem Request fuer Schaetzung
- **Akkumulation**: `ProcessingResult.cost_usd` → `BatchProcessingResult.total_cost_usd` (Summe aller Einzel-Kosten)
- **UI**: Sofortige Kostenanzeige im Fazit-Overlay, verkuerzter Delay (5s OpenAI statt 90s OpenRouter)

### Neue DB-Tabellen (Migration 020)
| Tabelle | Beschreibung |
|---------|--------------|
| `ai_provider_keys` | id, provider_type, name, api_key_encrypted, is_active, created_by, timestamps |
| `model_pricing` | id, provider, model_name, input/output_price_per_million, valid_from, is_active |
| `ai_requests` | id, user_id, provider, model, context, document_id, tokens, costs, created_at |

### Neue PHP-Endpunkte
| Endpunkt | Datei | Beschreibung |
|----------|-------|--------------|
| GET /ai/providers/active | ai_providers.php | Aktiver Provider (Public, JWT) |
| GET/POST/PUT/DELETE /admin/ai-providers | ai_providers.php | Admin CRUD |
| POST /admin/ai-providers/{id}/activate | ai_providers.php | Key aktivieren |
| POST /admin/ai-providers/{id}/test | ai_providers.php | Verbindungstest |
| GET /ai/pricing | model_pricing.php | Aktive Preise (Public, JWT) |
| GET/POST/PUT/DELETE /admin/model-pricing | model_pricing.php | Admin CRUD |
| GET /ai/requests | ai.php | KI-Request-Historie (Admin, mit period-Filter) |
| POST /ai/classify | ai.php | KI-Klassifikation (routed zum aktiven Provider) |
| GET /ai/credits | ai.php | Provider-Credits (OpenRouter) / Usage (OpenAI) |

### Neue Python-Klassen
| Klasse | Datei | Beschreibung |
|--------|-------|--------------|
| `AIProviderKey` | `src/api/ai_providers.py` | Dataclass fuer Provider-Key |
| `AIProvidersAPI` | `src/api/ai_providers.py` | API Client (CRUD, activate, test) |
| `ModelPrice` | `src/api/model_pricing.py` | Dataclass fuer Modell-Preis |
| `ModelPricingAPI` | `src/api/model_pricing.py` | API Client (CRUD, get_ai_requests) |
| `CostCalculator` | `src/services/cost_calculator.py` | Token-Zaehlung (tiktoken) + Kostenberechnung |
| `CostEstimate` / `RealCost` | `src/services/cost_calculator.py` | Dataclasses fuer Kosten |

### Datenfluss KI-Klassifikation (v2.1.2)
```
[document_processor] ──classify_sparte_with_date()──▶ [openrouter.py]
    │                                                      │
    │ _doc_cost_usd += _server_cost_usd                   │ _openrouter_request()
    │                                                      │     POST /ai/classify
    ▼                                                      ▼
[ProcessingResult]                                   [ai.php → handleClassify()]
    │ cost_usd                                             │ getActiveProvider()
    │                                                      │ mapModelName()
    ▼                                                      │ callOpenAIProvider() ODER
[BatchProcessingResult]                                    │ callOpenRouterProvider()
    │ total_cost_usd = Σ cost_usd                         │ calculateCost() → logAiRequest()
    │                                                      │
    ▼                                                      ▼
[archive_boxes_view]                                 [_cost: {real_cost_usd, provider}]
    │ show_completion() → Sofort-Anzeige
    │ _start_delayed_cost_check() → 5s/30s/90s
    ▼
[KI-Kosten-Toast mit Provider + Quelle]
```

---

## Neue Features in v2.1.0 (ATLAS Index Volltextsuche)

### ATLAS Index - Globale Dokumentensuche
- **Zweck**: Virtuelle "Box" ganz oben in der Archiv-Sidebar, globale Volltextsuche ueber Dateinamen und extrahierten Text
- **Architektur-Prinzip**: Eigener Endpoint `GET /documents/search` -- JOIN auf `document_ai_data` NUR hier, niemals in `listDocuments()`
- **Zwei Suchmodi**: FULLTEXT `BOOLEAN MODE` (Standard, schnell) oder `LIKE '%term%'` (Teilstring, langsamer)
- **Smart Text-Preview**: `LOCATE()` findet den Suchbegriff im Text, `SUBSTRING()` extrahiert ein 2000-Zeichen-Fenster um den Treffer (300 vor + 1700 nach). Fallback auf Textanfang bei Nicht-Treffer.
- **XML/GDV-Filter**: Standardmaessig ausgeblendet (`box_type != 'roh' AND is_gdv = 0`), per Checkbox einbeziehbar
- **UI**: `AtlasIndexWidget` im `QStackedWidget` (Page 1 neben Document-Table Page 0)
  - Suchfeld + Such-Button (bei deaktivierter Live-Suche sichtbar)
  - 3 Checkboxen: Live-Suche, XML/GDV einbeziehen, Teilstring-Suche
  - `SearchResultCard`: Snippet-basierte Ergebnisse mit zweistufiger Treffer-Suche (voller Begriff, dann Einzelwoerter)
  - `SearchWorker` (QThread): Nicht-blockierende API-Aufrufe
- **Performance**: FULLTEXT-Index, LIMIT 200, Debounce 400ms, LOCATE-basiertes Preview, SearchWorker

### Neuer PHP-Endpoint
| Endpunkt | Datei | Beschreibung |
|----------|-------|--------------|
| GET /documents/search | documents.php | Volltextsuche mit FULLTEXT/LIKE, include_raw, substring, LOCATE-Preview |

### Neue Python-Klassen
| Klasse | Datei | Beschreibung |
|--------|-------|--------------|
| `SearchResult` | `src/api/documents.py` | Dataclass: Document + text_preview + relevance_score |
| `SearchWorker` | `src/ui/archive_boxes_view.py` | QThread fuer async Suche |
| `SearchResultCard` | `src/ui/archive_boxes_view.py` | QFrame fuer Suchergebnis-Karte mit Snippet |
| `AtlasIndexWidget` | `src/ui/archive_boxes_view.py` | QWidget fuer Such-Interface |

## Neue Features in v2.0.3/v2.0.4 (Volltext-Persistierung + Content-Duplikate)

### Volltext + KI-Daten-Persistierung (v2.0.3)
- **Separate Tabelle**: `document_ai_data` (1:1 zu `documents`, NIEMALS in `listDocuments()` gejoined)
- **Spalten**: `extracted_text` (MEDIUMTEXT), `ai_full_response` (LONGTEXT), `extracted_text_sha256`, `text_char_count`, `ai_response_char_count`
- **Indexes**: `FULLTEXT INDEX` auf `extracted_text` fuer zukuenftige Volltextsuche
- **Performance**: Strikte Trennung - keine Auto-Joins, separate Endpoints, kein Lazy-Load im UI
- **CASCADE-Delete**: `document_ai_data` wird bei Dokument-Loeschung mitgeloescht (DSGVO)

### Content-Duplikat-Erkennung (v2.0.3)
- **Unterschied zu Datei-Duplikaten**: Datei-Duplikat (`content_hash`) = gleiche Bytes, Content-Duplikat (`extracted_text_sha256`) = gleicher Text
- **DB-Spalte**: `documents.content_duplicate_of_id` (INT NULL) zeigt auf das Original-Dokument
- **Erkennung**: Beim Speichern von `extracted_text_sha256` wird geprueft ob ein aelteres Dokument denselben Hash hat
- **UI**: Archiv-Tabelle zeigt ≡-Icon (indigo) fuer Content-Duplikate, ⚠-Icon (amber) fuer Datei-Duplikate (Prioritaet)

### Proaktive Text-Extraktion (v2.0.3)
- **Problem geloest**: Duplikate waren vorher erst sichtbar NACH der KI-Verarbeitung (zu spaet)
- **Loesung**: `extract_and_save_text()` wird direkt nach Upload aufgerufen, BEVOR die KI-Pipeline
- **MissingAiDataWorker**: Hintergrund-Worker fuer Scan-Dokumente (Power Automate) bei App-Start

### PDF-Unlock-Fix (v2.0.4)
- **Problem**: PDF-Anhaenge aus MSG/ZIP-Dateien wurden nicht entsperrt ("Keine PDF-Passwoerter verfuegbar")
- **Ursache**: `api_client` Parameter fehlte beim Aufruf von `unlock_pdf_if_needed()`
- **Fix**: Alle Aufrufe in `main_hub.py`, `archive_boxes_view.py`, `bipro_view.py` und `msg_handler.py` korrigiert
- **ValueError-Handling**: Passwortgeschuetzte PDFs ohne Passwort crashen die App nicht mehr

### Neue Datenbank-Migrationen
| Script | Beschreibung |
|--------|--------------|
| `017_document_ai_data.php` | Volltext + KI-Daten-Tabelle mit CASCADE-Delete |
| `018_content_duplicate_detection.php` | `content_duplicate_of_id` Spalte + Backfill |

## Neue Features in v2.0.0 (Mitteilungszentrale)

### Mitteilungszentrale / Communication Hub
- **Neue Seite**: Erster Eintrag in linker Sidebar (Index 0 im QStackedWidget)
- **3 Kacheln**: System-/Admin-Mitteilungen (gross), Release-Info (klein), Chats-Button (klein)
- **System-Mitteilungen**: API-Key-Auth (fuer externe Flows wie Power Automate) ODER JWT-Admin
- **Per-User Read-Status**: `message_reads`-Tabelle fuer korrekte Badges
- **Severity-Farben**: info (blau), warning (gelb), error (rot), critical (dunkelrot)

### 1:1 Private Chat
- **Vollbild-View**: Sidebar wird versteckt (Pattern wie Admin-View)
- **Conversation-Liste links**: Mit letzter Nachricht + Unread-Badge
- **Nachrichten rechts**: Message-Bubbles mit Zeitstempel + Lesebestaetigung (Haekchen)
- **Neuer Chat**: Dialog mit verfuegbaren Nutzern (mit denen noch kein Chat existiert)
- **Sortierung**: `private_conversations.updated_at` wird serverseitig beim Senden aktualisiert

### Notification-Polling
- **QTimer im Main-Thread**: Alle 30 Sekunden `GET /notifications/summary`
- **Lightweight**: Nur 2 COUNT-Queries + optional latest_chat_message
- **Badge**: Roter Kreis auf "Zentrale"-NavButton mit Summe ungelesener Chats + Meldungen
- **Toast**: Bei neuer Chat-Nachricht, Klick oeffnet den entsprechenden Chat
- **Deduplizierung**: `?last_message_ts=X` verhindert wiederholte Toasts

### Admin-Panel "Mitteilungen" (Panel 14)
- **CRUD**: Neue Mitteilung erstellen (Titel, Beschreibung, Severity), Loeschen
- **Tabelle**: Alle Mitteilungen mit Zeitstempel, Quelle, Severity
- **4. Sektion**: "KOMMUNIKATION" in der Admin-Sidebar

### Neue DB-Tabellen (Migration 015)
| Tabelle | Beschreibung |
|---------|--------------|
| `messages` | System- + Admin-Mitteilungen (title, description, severity, source, sender_name) |
| `message_reads` | Per-User Read-Tracking (PK: message_id + user_id) |
| `private_conversations` | 1:1 Chat-Konversationen (user1_id < user2_id, UNIQUE) |
| `private_messages` | Chat-Nachrichten (sender_id, receiver_id, content, read_at) |

### Neue PHP-Endpunkte
| Endpunkt | Datei | Beschreibung |
|----------|-------|--------------|
| GET/POST /messages | messages.php | Mitteilungen CRUD + Bulk-Read |
| PUT /messages/read | messages.php | Bulk-Read-Markierung |
| DELETE /messages/{id} | messages.php | Admin-Loeschung |
| GET/POST /chat/conversations | chat.php | Chat-Liste + Neuen Chat starten |
| GET/POST /chat/conversations/{id}/messages | chat.php | Nachrichten lesen/senden |
| PUT /chat/conversations/{id}/read | chat.php | Als gelesen markieren |
| GET /chat/users | chat.php | Verfuegbare Chat-Partner |
| GET /notifications/summary | notifications.php | Polling (Unread-Counts + Toast) |

### Neue Python-Dateien
| Datei | Zeilen | Beschreibung |
|-------|--------|--------------|
| `src/ui/message_center_view.py` | ~639 | Dashboard mit 3 Kacheln + LoadMessagesWorker + LoadReleasesWorker |
| `src/ui/chat_view.py` | ~739 | Vollbild-Chat + LoadConversationsWorker + SendMessageWorker |
| `src/api/messages.py` | ~143 | MessagesAPI Client (CRUD + Polling) |
| `src/api/chat.py` | ~153 | ChatAPI Client (Conversations + Messages) |

### QStackedWidget-Indizes (main_hub.py)
| Index | View | Beschreibung |
|-------|------|--------------|
| 0 | Mitteilungszentrale | Dashboard (NEU v2.0.0) |
| 1 | BiPRO | Datenabruf + Mail-Import |
| 2 | Archiv | Dokumentenarchiv mit Boxen |
| 3 | GDV | Editor |
| 4 | Admin | Vollbild mit eigener Sidebar |
| 5 | Chat | Vollbild mit eigener Sidebar (NEU v2.0.0) |

---

## Neue Features in v1.1.4 (App-Schliess-Schutz)

### Schliess-Schutz bei laufenden Operationen
- **Blockierende Worker**: `ProcessingWorker` (KI-Verarbeitung), `DelayedCostWorker` (Kosten-Ermittlung), `SmartScanWorker` (E-Mail-Versand)
- **Mechanismus**: `ArchiveBoxesView.get_blocking_operations()` liefert Liste blockierender Operationen
- **MainHub**: `closeEvent()` prueft vor allen anderen Checks (GDV-Aenderungen etc.)
- **UX**: `event.ignore()` + Toast-Warnung (kein modaler Dialog, kein "Trotzdem beenden?")
- **Sicherheit**: `_is_worker_running()` faengt `RuntimeError` bei geloeschten C++-Objekten ab

## Neue Features in v2.0.2 (Leere-Seiten-Erkennung)

### 4-Stufen PDF-Leerseiten-Erkennung
- **Zweck**: PDFs auf komplett leere oder inhaltslose Seiten pruefen (rein informativ, blockiert nicht die Pipeline)
- **Algorithmus** (Performance-optimiert, ~5-20ms pro Seite bei 50 DPI):
  1. **Text-Pruefung**: `page.get_text("text")` - OCR-Rauschen (<30 Zeichen) wird toleriert
  2. **Vektor-Objekte**: `page.get_drawings()` - Linien, Rahmen, Tabellen erkennen
  3. **Bilder**: `page.get_images(full=True)` - Relevante Bilder erkennen
  4. **Pixel-Analyse**: `page.get_pixmap(dpi=50)` - Helligkeit (>250) + Varianz (<5.5) = leer
- **Integration**: Laeuft in `document_processor._check_and_log_empty_pages()` VOR KI-Klassifikation
- **DB**: `documents.empty_page_count` + `documents.total_page_count` (INT NULL)
- **UI**: Spalte 1 in DocumentTableModel mit Icon (Halb-Kreis teilweise, Kreis komplett leer)
- **History**: `empty_pages_detected` Eintrag in `activity_log` mit Seitenindizes
- **Dateien**: `empty_page_detector.py` (Erkennung), `document_processor.py` (Integration), `archive_boxes_view.py` (UI)

## Neue Features in v1.1.3 (PDF-Bearbeitung)

### PDF-Bearbeitung in der Vorschau
- **Funktionen**: Seiten drehen (CW/CCW, 90 Grad), Seiten loeschen, Speichern auf Server
- **Architektur**: QPdfView (Darstellung) + PyMuPDF (Manipulation) + Thumbnail-Sidebar
- **Server**: `POST /documents/{id}/replace` ersetzt Datei, berechnet content_hash/file_size neu
- **Cache**: Vorschau-Cache + Historie-Cache werden nach Speichern invalidiert
- **Dateien**: `archive_view.py` (PDFViewerDialog erweitert), `archive_boxes_view.py`, `documents.php`

## Neue Features in v1.1.2 (Dokument-Historie)

### Dokument-Historie als Seitenpanel
- **Trigger**: Klick auf Dokument in Tabelle (Debounce 300ms)
- **Panel**: QSplitter rechts, max 400px, scrollbare farbcodierte Eintraege
- **8 Aktionsfarben**: Blau (Verschieben), Gruen (Download), Grau (Upload), Rot (Loeschen), Orange (Archiv), Lila (Farbe), Indigo (Update), Cyan (KI)
- **Performance**: Client-Cache (60s TTL), Debounce-Timer, async DocumentHistoryWorker
- **Berechtigung**: Neue Permission `documents_history`
- **Datenquelle**: `GET /documents/{id}/history` aus activity_log-Tabelle

## Neue Features in v1.1.1 (Duplikat-Erkennung)

### Duplikat-Erkennung via SHA256-Pruefziffer
- **Server**: `uploadDocument()` berechnet `content_hash = hash_file('sha256', $path)` beim Upload
- **Vergleich**: Gegen ALLE Dokumente in der DB (inkl. archivierte), kein `is_archived`-Filter
- **Verhalten**: Duplikate werden trotzdem hochgeladen, aber als Version > 1 markiert
- **List-API**: `listDocuments()` liefert jetzt `content_hash`, `version`, `previous_version_id`, `duplicate_of_filename` (via LEFT JOIN)
- **UI**: Eigene Spalte (Index 0) in der Archiv-Tabelle mit Warn-Icon und Tooltip zum Original
- **Toast**: Info-Benachrichtigung bei Upload-Erkennung (MultiUploadWorker + DropUploadWorker)

## Neue Features in v0.9.4 (Stabilitaets-Upgrade + KI-Optimierung)

### Stabilitaets-Fixes
- DataCache Race Condition (`_pause_count` unter Lock)
- JWT 401 Auto-Refresh mit Deadlock-Schutz
- Retry auf alle APIClient-Methoden (exp. Backoff 1s/2s/4s)
- SharedTokenManager Double-Checked Locking
- File-Logging mit RotatingFileHandler
- 11 Smoke-Tests

### Zweistufige KI-Klassifikation
- Stufe 1: GPT-4o-mini (2 Seiten, Confidence-Scoring)
- Stufe 2: GPT-4o (5 Seiten) nur bei low Confidence
- Courtage-Definition verschaerft (Negativ-Beispiele)
- Dokumentnamen bei Sonstige (Stufe 2)

## Aeltere Features in v0.9.3 (KI-Klassifikation & Kosten-Tracking)

Diese Version erweitert die KI-Klassifikation und fügt Kosten-Tracking hinzu:

### 1. OpenRouter Kosten-Tracking
- **Guthaben-Abfrage**: Vor und nach der Batch-Verarbeitung
- **Differenz-Berechnung**: Automatische Berechnung der Verarbeitungskosten
- **Pro-Dokument-Kosten**: Durchschnittliche Kosten pro klassifiziertem Dokument
- **BatchProcessingResult**: Erweitert um `credits_before`, `credits_after`, `total_cost_usd`, `cost_per_document_usd`

### 2. Erweiterte Sach-Klassifikation
- **Erweiterte Keywords**: Privathaftpflicht, PHV, Tierhalterhaftpflicht, Hundehaftpflicht
- **Haus- und Grundbesitzerhaftpflicht**: Korrekt als Sach klassifiziert
- **Bauherrenhaftpflicht, Jagdhaftpflicht**: Zusätzliche Haftpflichtarten
- **Gewaesserschadenhaftpflicht**: Umwelthaftpflicht-Bereich

### 3. Courtage-Benennung
- **Format**: `VU_Name + Dokumentdatum`
- **Beispiel**: `Degenia_2026-02-05.pdf`
- **Token-Optimierung**: Sach-Dokumente nur mit `Sach` benannt (kein Datum)

### 4. Verbesserte Leben-Klassifikation
- **Pensionskasse**: Korrekt als Leben klassifiziert
- **Rentenanstalt**: Korrekt als Leben klassifiziert

---

## Neue Features in v0.9.0 (Pipeline Hardening)

Diese Version enthält umfassende Verbesserungen für Datensicherheit, Transaktionssicherheit und Audit-Funktionalität:

### 1. PDF-Validierung mit Reason-Codes
- **Erweiterte Validierung**: Prüft auf Verschlüsselung, XFA-Formulare, Seitenzahl, strukturelle Integrität
- **Reason-Codes**: `PDFValidationStatus` Enum (`OK`, `PDF_ENCRYPTED`, `PDF_CORRUPT`, `PDF_XFA`, etc.)
- **Automatische Reparatur**: PyMuPDF-basierte Reparatur für beschädigte PDFs
- **Routing**: Problematische PDFs landen in der Sonstige-Box mit dokumentiertem Status

### 2. FS/DB Transaktionssicherheit
- **Atomic Write Pattern**: Staging → Verify → DB-Insert → Atomic Move → Commit
- **Content-Hash**: SHA256-Hash für Integritätsprüfung und Deduplizierung
- **Versionierung**: Automatische Versionsnummerierung bei Duplikaten
- **Rollback-Fähigkeit**: Bei Fehlern automatische Bereinigung

### 3. Dokument-State-Machine
- **Granulare Stati**: `downloaded` → `validated` → `classified` → `renamed` → `archived`
- **Error-Handling**: Jeder Schritt kann in `error` übergehen
- **Legacy-Kompatibilität**: Alte Stati (`pending`, `processing`, `completed`) bleiben gültig

### 4. XML-Indexierung
- **Separate Tabelle**: `xml_index` für BiPRO-XML-Rohdaten
- **Metadaten**: Lieferungs-ID, Kategorie, VU-Name, Content-Hash
- **Dedizierte API**: `xml_index.php` / `xml_index.py`

### 5. Klassifikations-Audit
- **Quelle dokumentieren**: `classification_source` (ki_gpt4o, rule_bipro, fallback)
- **Konfidenz**: `classification_confidence` (high, medium, low)
- **Begründung**: `classification_reason` (max. 500 Zeichen)
- **Zeitstempel**: `classification_timestamp`

### 6. Processing-History (Audit-Trail)
- **Vollständiges Logging**: Jeder Verarbeitungsschritt wird aufgezeichnet
- **Performance-Metriken**: Dauer jeder Aktion
- **Fehler-Analyse**: Fehlerhafte Aktionen mit Details
- **API**: `processing_history.php` / `processing_history.py`

### Neue Datenbank-Migrationen
| Script | Beschreibung |
|--------|--------------|
| `007_add_validation_status.php` | PDF-Validierungsstatus |
| `008_add_content_hash.php` | SHA256-Hash für Deduplizierung |
| `009_add_xml_index_table.php` | XML-Index-Tabelle |
| `010_add_document_version.php` | Versionierung |
| `011_add_classification_audit.php` | Klassifikations-Audit-Felder |
| `012_add_processing_history.php` | Processing-History-Tabelle |
| `013_add_bipro_document_id.php` | BiPRO-Dokument-ID + XML-Index-Relation |

### State-Machine mit Transition-Erzwingung (v0.9.1)

Die Pipeline verwendet eine strikte State-Machine mit erzwungenen Übergängen:

```
           ┌─────────────┐
           │  downloaded │
           └──────┬──────┘
                  │
      ┌───────────┼───────────┐
      ▼           ▼           ▼
┌───────────┐ ┌───────────┐ ┌───────────┐
│ validated │ │quarantined│ │   error   │
└─────┬─────┘ └───────────┘ └───────────┘
      │
      ▼
┌───────────┐
│ classified│
└─────┬─────┘
      │
      ├───────────────────┐
      ▼                   ▼
┌───────────┐      ┌───────────┐
│  renamed  │      │ archived  │
└─────┬─────┘      └───────────┘
      │
      ▼
┌───────────┐
│ archived  │
└───────────┘
```

Ungültige Übergänge werden vom PHP-Backend mit HTTP 400 abgelehnt.

### KI-Pipeline Backpressure-Kontrolle (v0.9.1)

- **Semaphore**: Begrenzt parallele KI-Aufrufe auf 3 (konfigurierbar)
- **Queue-Monitoring**: `get_ai_queue_depth()` für Überwachung
- **Retry mit Backoff**: Automatische Wiederholung bei HTTP 429/503

## Uebersicht

ACENCIA ATLAS ist eine Desktop-Anwendung mit Server-Backend. Es folgt einer mehrschichtigen Architektur:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Desktop-App (PySide6/Qt)                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                           UI Layer                                          │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────────────────┐│
│  │ main_hub.py │ │bipro_view.py│ │archive_boxes│ │    admin_view.py        ││
│  │ Navigation  │ │ BiPRO-Abruf │ │ _view.py    │ │   11 Admin-Panels       ││
│  │ Drag&Drop   │ │ MailImport  │ │ Smart!Scan  │ │   Sidebar-Navigation    ││
│  │ NotiPoller  │ │ VU-Verwalt. │ │ PDF-Preview │ │                         ││
│  │ toast.py    │ │             │ │             │ │                         ││
│  └──────┬──────┘ └──────┬──────┘ └──────┬──────┘ └───────────┬─────────────┘│
│  ┌─────────────────┐ ┌─────────────┐                                        │
│  │message_center   │ │ chat_view   │   NEU v2.0.0                           │
│  │ _view.py        │ │ .py         │                                        │
│  │ Dashboard       │ │ 1:1 Chat    │                                        │
│  └──────┬──────────┘ └──────┬──────┘                                        │
│         │               │               │                     │              │
│         │    ┌──────────┘               │        ┌────────────┘              │
│         │    │  ┌───────────────────────┘        │                           │
│         │    │  │  ┌─────────────────────────────┘                           │
│         ▼    ▼  ▼  ▼                                                         │
│  ┌─────────────────────┐ ┌─────────────┐ ┌──────────────────┐               │
│  │   main_window.py    │ │partner_view │ │  gdv_editor_view │               │
│  │   GDV-Editor        │ │ .py         │ │  .py             │               │
│  └──────────┬──────────┘ └──────┬──────┘ └────────┬─────────┘               │

└─────────────┼───────────────────┼─────────────────┼──────────────────────────┘
              │                   │                  │
              ▼                   ▼                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Service Layer                                       │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌────────────────────┐  │
│  │  API Clients │ │ BiPRO Client │ │   Services   │ │   Parser Layer     │  │
│  │  (src/api/)  │ │ (src/bipro/) │ │              │ │   (src/parser/)    │  │
│  │  - client.py │ │ - transfer   │ │ - data_cache │ │   - gdv_parser.py  │  │
│  │  - documents │ │   _service   │ │ - doc_proc.  │ │                    │  │
│  │  - smartscan │ │ - rate_limit │ │ - pdf_unlock │ │   (src/layouts/)   │  │
│  │  - admin     │ │ - categories │ │ - zip_handler│ │   - gdv_layouts.py │  │
│  │  - passwords │ │              │ │ - msg_handler│ │                    │  │
│  │  - releases  │ │              │ │ - update_svc │ │                    │  │
│  │  - messages  │ │              │ │ - empty_page │ │                    │  │
│  │  - chat      │ │              │ │   _detector  │ │                    │  │
│  └──────┬───────┘ └──────┬───────┘ └──────┬───────┘ └────────┬───────────┘  │
└─────────┼────────────────┼────────────────┼──────────────────┼──────────────┘
          │                │                │                  │
          ▼                ▼                ▼                  ▼
┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐ ┌──────────────┐
│  Strato Webspace │ │  Versicherer     │ │ OpenRouter/OpenAI│ │  Lokales FS  │
│  PHP REST API    │ │  BiPRO Services  │ │  GPT-4o/4o-mini  │ │  GDV-Dateien │
│  MySQL + Files   │ │  (Degenia, VEMA) │ │  Klassifikation  │ │  Temp-Cache  │
│  ~25 Endpunkte   │ │                  │ │  (dynamisch)     │ │              │
└──────────────────┘ └──────────────────┘ └──────────────────┘ └──────────────┘
```

---

## Komponenten

### 1. UI Layer (`src/ui/`)

#### main_hub.py (~1324 Zeilen)
Zentrales Navigationselement:
- Sidebar mit Bereichen (Zentrale, BiPRO, Archiv, GDV-Editor, Admin)
- Benutzeranzeige und Logout
- Routing zwischen Views via QStackedWidget (6 Indizes: Zentrale, BiPRO, Archiv, GDV, Admin, Chat)
- **Globales Drag & Drop**: Dateien/Ordner/Outlook-Mails per Drag & Drop hochladen
- **DropUploadWorker**: QThread fuer nicht-blockierenden Upload
- **Admin-Modus**: Haupt-Sidebar ausblenden, Admin-Sidebar einblenden
- **Chat-Modus**: Haupt-Sidebar ausblenden (wie Admin), `_show_chat()` / `_leave_chat()`
- **NotificationPoller**: QTimer alle 30s, `GET /notifications/summary`, Badge + Toast (NEU v2.0.0)
- **Notification-Badge**: Roter Kreis auf "Zentrale"-Button mit Unread-Count
- **Permission Guards**: Buttons basierend auf Nutzerrechten aktivieren/deaktivieren
- **Periodischer UpdateCheckWorker** (30 Min Timer)
- **Schliess-Schutz**: `closeEvent()` prueft auf blockierende Operationen in ArchiveBoxesView vor dem Beenden

#### message_center_view.py (~639 Zeilen) - NEU v2.0.0
Mitteilungszentrale Dashboard:
- **3 Kacheln**: System-/Admin-Mitteilungen (gross), Release-Info (klein), Chats-Button (klein)
- **LoadMessagesWorker**: Laedt Mitteilungen im Hintergrund
- **LoadReleasesWorker**: Laedt Releases fuer Release-Kachel
- **Severity-Farben**: info/warning/error/critical mit passenden Hintergrundfarben
- **Read-Markierung**: Beim Oeffnen werden alle sichtbaren Mitteilungen als gelesen markiert
- **Signal `open_chat_requested`**: Verbindet "Chats oeffnen" Button mit MainHub

#### chat_view.py (~739 Zeilen) - NEU v2.0.0
Vollbild-Chat fuer 1:1 Nachrichten:
- **ConversationItem**: Custom QFrame fuer Chat-Liste (Avatar, Name, letzte Nachricht, Unread-Badge)
- **MessageBubble**: Custom QFrame fuer Nachrichten (eigene rechts/blau, fremde links/grau, Lesebestaetigung)
- **LoadConversationsWorker**: Laedt Chat-Liste
- **LoadChatMessagesWorker**: Laedt Nachrichten eines Chats
- **SendMessageWorker**: Sendet Nachricht asynchron
- **LoadUsersWorker**: Laedt verfuegbare Chat-Partner fuer "Neuer Chat"
- **Auto-Scroll**: Scrollt nach unten bei neuen Nachrichten
- **Signal `back_requested`**: Verbindet "Zurueck" Button mit MainHub

#### bipro_view.py (~4900 Zeilen)
BiPRO-Datenabruf UI:
- **VU-Verbindungsliste**: Alle konfigurierten Versicherer (Degenia, VEMA, ...)
- **Lieferungstabelle**: Verfuegbare Lieferungen mit Kategorien
- **ParallelDownloadManager**: Parallele Downloads (max. 10 Worker, auto-adjustiert)
- **MailImportWorker**: IMAP-Poll + Attachment-Pipeline (QThread)
- **"Mails abholen" Button**: IMAP-Mails abrufen und Anhaenge importieren
- **"Alle VUs abholen"**: Sequentielle Verarbeitung aller aktiven VU-Verbindungen
- **Log-Bereich**: Status und Fehler
- **VU-Dialog**: Verbindung erstellen/bearbeiten mit VU-spezifischen Feldern
- **Progress-Toast**: Zweiphasiger Fortschritt (IMAP-Poll + Attachment-Import)

**Signalfluesse**:
```
VU auswaehlen → STS-Token holen → listShipments → Tabelle fuellen
Download klicken → getShipment → MTOM parsen → Archiv-Upload
Mails abholen → IMAP-Poll → Attachments downloaden → Pipeline → Upload
```

#### archive_boxes_view.py (~6350 Zeilen)
Dokumentenarchiv mit Box-System + ATLAS Index:
- **BoxSidebar**: Navigation mit Live-Zaehlern + Kontextmenue (Download, SmartScan) + ATLAS Index Item
- **ATLAS Index**: Virtuelle Such-Box (AtlasIndexWidget) mit SearchWorker, SearchResultCard, 3 Checkboxen
- **8 Boxen**: GDV, Courtage, Sach, Leben, Kranken, Sonstige, Roh, Falsch
- **MultiUploadWorker/MultiDownloadWorker**: Parallele Operationen
- **BoxDownloadWorker**: Ganze Boxen als ZIP oder in Ordner herunterladen
- **SmartScanWorker**: Dokumente per E-Mail versenden
- **Smart!Scan-Toolbar-Button**: Gruener Button (sichtbar wenn aktiviert)
- **CreditsWorker / DelayedCostWorker**: OpenRouter-Guthaben + verzoegerter Kosten-Check
- **PDFViewerDialog / SpreadsheetViewerDialog**: Vorschau fuer PDFs, CSV, XLSX
- **Tastenkuerzel**: F2, Entf, Strg+A/D/F/U, Enter, Esc, F5
- **Farbmarkierung**: 8 Farben persistent ueber alle Operationen
- **Verarbeitungs-Ausschluss**: Manuell verschobene Dokumente ueberspringen
- **Dokument-Historie**: Seitenpanel mit farbcodierten Aenderungseintraegen (DocumentHistoryPanel)
- **Duplikat-Spalte**: Warn-Icon bei erkannten Duplikaten mit Tooltip zum Original
- **Leere-Seiten-Spalte**: Icon bei PDFs mit leeren Seiten (teilweise/komplett, Tooltip mit Details)
- **Schliess-Schutz**: `get_blocking_operations()` verhindert App-Schliessung bei laufenden kritischen Workern

#### admin_view.py (~5200+ Zeilen) - Redesign v1.0.9, erweitert v2.1.3
Administration mit vertikaler Sidebar:
- **AdminNavButton**: Custom-Styling, monochrome Icons, orangene Trennlinien
- **QStackedWidget**: 15 Panels in 5 Sektionen
  - VERWALTUNG: Nutzerverwaltung, Sessions, Passwoerter (0-2)
  - MONITORING: Aktivitaetslog, KI-Kosten, Releases (3-5)
  - VERARBEITUNG: KI-Klassifikation (6), KI-Provider (7), Modell-Preise (8), Dokumenten-Regeln (9) **NEU v2.1.3**
  - E-MAIL: E-Mail-Konten, SmartScan-Settings, SmartScan-Historie, IMAP Inbox (10-13)
  - KOMMUNIKATION: Mitteilungen (14) **NEU v2.0.0**
- **"Zurueck zur App" Button**: Verlassen des Admin-Bereichs

#### toast.py (~558 Zeilen)
Toast-Benachrichtigungssystem:
- **ToastWidget**: 4 Typen (success, error, warning, info) mit Auto-Dismiss
- **ProgressToastWidget**: Fortschritts-Toast mit Titel, Status, QProgressBar
- **ToastManager**: Globaler Manager oben rechts, Stacking, Hover-Pause

#### main_window.py (~1060 Zeilen)
GDV-Editor Hauptfenster:
- **GDVMainWindow**: Menues, Toolbar, Statusbar
- **RecordTableWidget**: Tabelle aller Records mit Filterung
- **ExpertDetailWidget**: Alle Felder editierbar

#### partner_view.py (~1138 Zeilen)
Partner-Uebersicht:
- **extract_partners_from_file()**: Extrahiert Arbeitgeber/Personen
- **PartnerView**: Tabs fuer "Arbeitgeber" und "Personen"
- **EmployerDetailWidget**: Details mit Vertraegen
- **PersonDetailWidget**: Details mit Arbeitgeber-Zuordnung

---

### 2. API Clients (`src/api/`)

#### client.py (~513 Zeilen)
Base-Client fuer Server-Kommunikation:
- JWT-Authentifizierung mit Auto-Token-Refresh
- `_request_with_retry()`: Zentrale Retry-Logik (exp. Backoff 1s/2s/4s)
- Deadlock-Schutz: `_try_auth_refresh()` mit non-blocking acquire
- Multipart-Upload fuer Dateien

#### documents.py (~900 Zeilen)
Dokumenten-Operationen mit Box-Support + ATLAS Index:
- `list()`, `upload()`, `download()`, `delete()`
- `move_documents()`: Zwischen Boxen verschieben
- `archive_documents()` / `unarchive_documents()`: Bulk-Archivierung
- `set_documents_color()`: Bulk-Farbmarkierung
- `get_document_history()`: Aenderungshistorie pro Dokument
- `replace_document_file()`: Datei ersetzen (PDF-Bearbeitung)
- `search_documents()`: ATLAS Index Volltextsuche (FULLTEXT/LIKE, include_raw, substring)

#### Weitere API-Clients
| Datei | Zweck | Zeilen |
|-------|-------|--------|
| `auth.py` | Login, User-Model mit Permissions | ~150 |
| `vu_connections.py` | VU-Verbindungsverwaltung | ~350 |
| `admin.py` | Nutzerverwaltung (Admin) | ~200 |
| `messages.py` | **Mitteilungen + Notification-Polling (NEU v2.0.0)** | ~143 |
| `chat.py` | **1:1 Chat-Nachrichten (NEU v2.0.0)** | ~153 |
| `smartscan.py` | SmartScan + EmailAccounts | ~350 |
| `openrouter.py` | KI-Klassifikation (zweistufig, Provider-aware) | ~900 |
| `ai_providers.py` | **KI-Provider-Verwaltung (CRUD, activate, test) NEU v2.1.2** | ~120 |
| `model_pricing.py` | **Modell-Preise + KI-Request-Historie NEU v2.1.2** | ~117 |
| `passwords.py` | Passwort-Verwaltung | ~80 |
| `releases.py` | Auto-Update | ~120 |
| `processing_history.py` | Audit-Trail | ~380 |
| `document_rules.py` | **Dokumenten-Regeln (Settings + API) NEU v2.1.3** | ~94 |
| `gdv_api.py` | GDV-Dateien server-seitig parsen | ~229 |
| `xml_index.py` | XML-Index fuer BiPRO-Rohdaten | ~259 |
| `smartadmin_auth.py` | SmartAdmin SAML-Auth (47 VUs) | ~640 |

---

### 3. BiPRO Client (`src/bipro/`)

#### bipro_connector.py (~397 Zeilen)
BiPRO-Verbindungsabstraktion:
- SmartAdmin-Flow vs. Standard-BiPRO-Flow
- Dispatch basierend auf VU-Konfiguration
- Nutzt `smartadmin_auth.py` fuer SmartAdmin-Authentifizierung

#### transfer_service.py (~1334 Zeilen)
BiPRO 410/430 SOAP-Client (Multi-VU-Support):

**Klassen**:
```python
@dataclass
class BiPROCredentials:
    username, password, endpoint_url, sts_endpoint_url

@dataclass
class ShipmentInfo:
    shipment_id, created_at, category, available_until, transfer_count

@dataclass
class ShipmentDocument:
    filename, content_type, content_bytes

@dataclass
class ShipmentContent:
    documents: List[ShipmentDocument]
    metadata: Dict
    raw_xml: str
```

**Hauptmethoden**:
```python
class BiPROTransferService:
    def _get_sts_token() -> str        # BiPRO 410: Security-Token holen
    def list_shipments() -> List[ShipmentInfo]  # BiPRO 430: Liste
    def get_shipment(id) -> ShipmentContent     # BiPRO 430: Download
    def acknowledge_shipment(id) -> bool        # BiPRO 430: Quittieren
```

**MTOM/XOP-Handling**:
```python
def _parse_mtom_response(raw_bytes) -> Tuple[List[ShipmentDocument], Dict]:
    # 1. Multipart-Parts splitten
    # 2. XML-Part finden und parsen
    # 3. xop:Include Referenzen auflösen
    # 4. Binärdaten aus Parts extrahieren
```

#### categories.py
Mapping BiPRO-Kategorien zu lesbaren Namen:

```python
CATEGORY_NAMES = {
    "100002000": "Vertragsänderung",
    "100007000": "Geschäftsvorfall",
    "110011000": "Vertragsdokumente",
}

def get_category_name(code: str) -> str
def get_category_short_name(code: str) -> str
def get_category_icon(code: str) -> str
```

---

### 4. Parser Layer (`src/parser/`, `src/layouts/`)

#### gdv_parser.py (~786 Zeilen)
Generischer Fixed-Width-Parser:

```python
@dataclass
class ParsedField:
    name, label, value, raw_value, start, length, field_type

@dataclass
class ParsedRecord:
    line_number, satzart, satzart_name, raw_line
    fields: Dict[str, ParsedField]

@dataclass
class ParsedFile:
    filepath, encoding
    records: List[ParsedRecord]
    errors: List[str]
```

#### gdv_layouts.py (~559 Zeilen)
Layout-Definitionen als Metadaten:

```python
LAYOUT_0100_TD1: LayoutDefinition = {
    "satzart": "0100",
    "teildatensatz": 1,
    "name": "Partnerdaten (Adresse)",
    "length": 256,
    "fields": [
        {"name": "satzart", "start": 1, "length": 4, "type": "N"},
        {"name": "vu_nummer", "start": 5, "length": 5, "type": "AN"},
        # ...
    ]
}

TEILDATENSATZ_LAYOUTS = {
    "0100": {"1": LAYOUT_0100_TD1, "2": LAYOUT_0100_TD2, ...},
    "0220": {"1": LAYOUT_0220_TD1, "6": LAYOUT_0220_TD6, ...}
}
```

---

### 5. Domain Layer (`src/domain/`)

#### models.py (~623 Zeilen)
Fachliche Datenklassen:

```python
@dataclass
class GDVData:
    file_meta: FileMeta
    customers: List[Customer]
    contracts: List[Contract]

@dataclass
class Contract:
    vu_nummer, versicherungsschein_nr, sparte
    risks: List[Risk]
    coverages: List[Coverage]
    customer: Optional[Customer]

@dataclass
class Customer:
    anrede: Anrede
    name1, name2, strasse, plz, ort
    # ...
```

#### mapper.py (~513 Zeilen)
Mapping ParsedRecord → Domain:

```python
def map_parsed_file_to_gdv_data(parsed_file: ParsedFile) -> GDVData:
    # 0001 → FileMeta
    # 0100 → Customer[]
    # 0200 → Contract[]
    # 0210 → Risk[]
    # 0220 → Coverage[]
```

---

## Datenflüsse

### 1. BiPRO-Abruf

```
[VU auswählen]
    │
    ▼ (automatisch)
[STS-Token holen]
    │ POST /410_STS/UserPasswordLogin
    │ UsernameToken → SecurityContextToken
    ▼
[listShipments]
    │ POST /430_Transfer/Service
    │ SecurityContextToken → XML mit Lieferungen
    ▼
[Tabelle aktualisieren]
    │
    ▼ (Download klicken)
[getShipment]
    │ POST /430_Transfer/Service
    │ SecurityContextToken → MTOM/XOP Response
    ▼
[MTOM parsen]
    │ Multipart → XML + Binary Parts
    │ xop:Include → Dokumente extrahieren
    ▼
[Archiv-Upload]
    │ POST /api/documents
    │ Multipart → Server speichert Datei
    ▼
[Fertig-Meldung]
```

### 2. Dokumentenarchiv

```
[Archive-View öffnen]
    │
    ▼ (automatisch)
[Dokumente laden]
    │ GET /api/documents
    │ JWT-Token → JSON mit Dokumenten-Liste
    ▼
[Tabelle füllen]
    │
    ▼ (Doppelklick auf PDF)
[PDF-Vorschau]
    │ GET /api/documents/{id}/download
    │ JWT-Token → PDF-Bytes
    │ Speichern in temp/
    ▼
[QPdfView anzeigen]
```

### 3. GDV-Editor

```
[GDV-Datei öffnen]
    │
    ▼ parse_file()
[ParsedFile]
    │
    ▼ map_parsed_file_to_gdv_data()
[GDVData]
    │
    ├──▶ [RecordTableWidget]
    ├──▶ [UserDetailWidget]
    └──▶ [PartnerView]
```

---

## Abhängigkeiten

```
UI Layer
    ├── main_hub.py ──────▶ api/messages.py (NotificationPoller)
    │               ──────▶ api/chat.py (Chat-Navigation)
    │
    ├── message_center_view.py ▶ api/messages.py, api/releases.py
    ├── chat_view.py ─────▶ api/chat.py
    │
    ├── bipro_view.py ────▶ api/vu_connections.py
    │                 ────▶ api/documents.py
    │                 ────▶ bipro/transfer_service.py
    │
    ├── archive_view.py ──▶ api/documents.py
    │
    └── main_window.py ───▶ parser/gdv_parser.py
                      ───▶ domain/mapper.py
                      ───▶ domain/models.py

Service Layer
    ├── api/client.py ────▶ Server REST API
    ├── bipro/*.py ───────▶ BiPRO SOAP Services
    └── parser/*.py ──────▶ Lokales Dateisystem

External
    ├── Strato Webspace (PHP API, MySQL, Files, ~23 Endpunkte)
    ├── BiPRO Services (Degenia, VEMA: 410 STS, 430 Transfer)
    ├── OpenRouter ODER OpenAI (GPT-4o/4o-mini, dynamisch umschaltbar v2.1.2)
    └── Lokale GDV-Dateien
```

---

## Server-Komponenten

### PHP REST API (`BiPro-Webspace Spiegelung Live/api/`)

| Bereich | Endpoint | Datei | Beschreibung |
|---------|----------|-------|--------------|
| **Auth** | POST /auth/login | auth.php | JWT-Login |
| | POST /auth/logout | auth.php | Logout + Session beenden |
| | GET /auth/me | auth.php | Aktueller Benutzer + Berechtigungen |
| **Dokumente** | GET /documents | documents.php | Alle Dokumente (Box-Filter optional) |
| | POST /documents | documents.php | Upload (Atomic Write, Deduplizierung) |
| | PUT /documents/{id} | documents.php | Update (Verschieben, Klassifikation) |
| | POST /documents/archive | documents.php | Bulk-Archivierung |
| | POST /documents/colors | documents.php | Bulk-Farbmarkierung |
| | GET /documents/{id}/download | documents.php | Download |
| | DELETE /documents/{id} | documents.php | Loeschen |
| | GET /documents/{id}/history | documents.php | Aenderungshistorie |
| | POST /documents/{id}/replace | documents.php | Datei ersetzen (PDF-Bearbeitung) |
| | GET /documents/search | documents.php | **ATLAS Index Volltextsuche (NEU v2.1.0)** |
| **VU** | GET /vu-connections | credentials.php | VU-Liste |
| | POST /vu-connections | credentials.php | VU erstellen |
| | GET /vu-connections/{id}/credentials | credentials.php | Credentials (entschluesselt) |
| **SmartScan** | POST /smartscan/send | smartscan.php | Dokumente per E-Mail senden |
| | GET /smartscan/settings | smartscan.php | Einstellungen lesen |
| | PUT /smartscan/settings | smartscan.php | Einstellungen speichern |
| | GET /smartscan/jobs | smartscan.php | Versandhistorie |
| **E-Mail** | GET /admin/email-accounts | email_accounts.php | E-Mail-Konten (Admin) |
| | POST /admin/email-accounts/{id}/poll | email_accounts.php | IMAP-Polling |
| | GET /email-inbox/attachments | email_accounts.php | Pending Attachments |
| **Admin** | GET /admin/users | admin.php | Nutzerverwaltung |
| | GET /admin/sessions | sessions.php | Session-Tracking |
| | GET /admin/activity | activity.php | Aktivitaetslog |
| | GET /admin/passwords | passwords.php | Passwort-CRUD |
| | GET /admin/releases | releases.php | Release-Verwaltung |
| **Mitteilungen** | GET /messages | messages.php | Alle Mitteilungen (paginiert, Read-Status) |
| | POST /messages | messages.php | Neue Mitteilung (API-Key oder Admin) |
| | PUT /messages/read | messages.php | Bulk-Read-Markierung |
| | DELETE /messages/{id} | messages.php | Admin-Loeschung |
| **Chat** | GET /chat/conversations | chat.php | Eigene Chats (Unread-Count) |
| | POST /chat/conversations | chat.php | Neuen 1:1 Chat starten |
| | GET/POST .../messages | chat.php | Nachrichten lesen/senden |
| | PUT .../read | chat.php | Als gelesen markieren |
| | GET /chat/users | chat.php | Verfuegbare Chat-Partner |
| **Notifications** | GET /notifications/summary | notifications.php | Polling (Unread-Counts + Toast) |
| **KI** | POST /ai/classify | ai.php | **KI-Klassifikation (dynamisches Routing) v2.1.2** |
| | GET /ai/credits | ai.php | **Provider-Credits/Usage v2.1.2** |
| | GET /ai/requests | ai.php | **Request-Historie (Admin) v2.1.2** |
| | GET /ai/key | ai.php | Legacy OpenRouter API-Key |
| | GET /ai/providers/active | ai_providers.php | **Aktiver Provider v2.1.2** |
| | POST/PUT/DELETE /admin/ai-providers | ai_providers.php | **Provider CRUD v2.1.2** |
| | GET /ai/pricing | model_pricing.php | **Modell-Preise v2.1.2** |
| | POST/PUT/DELETE /admin/model-pricing | model_pricing.php | **Pricing CRUD v2.1.2** |
| **System** | GET /updates/check | releases.php | Update-Check (Public) |
| | POST /incoming-scans | incoming_scans.php | Scan-Upload (API-Key) |
| **Regeln** | GET /document-rules | document_rules.php | **Dokumenten-Regeln laden (JWT) v2.1.3** |
| | PUT /admin/document-rules | document_rules.php | **Regeln speichern (Admin) v2.1.3** |
| | POST /processing_history/create | processing_history.php | Audit-Trail |
| | GET /processing_history/costs | processing_history.php | KI-Kosten |

### Datenbank-Schema

```sql
-- Benutzer
users (id, username, password_hash, role, created_at)

-- Dokumente (erweitert in v0.9.0)
documents (
    id, user_id, filename, original_filename, mime_type, file_size,
    source_type, vu_name, external_shipment_id, bipro_category,
    box_type,              -- eingang, verarbeitung, gdv, courtage, sach, leben, kranken, sonstige, roh
    processing_status,     -- downloaded, validated, classified, renamed, archived, error
    validation_status,     -- OK, PDF_ENCRYPTED, PDF_CORRUPT, PDF_XFA, etc. (v0.9.0)
    content_hash,          -- SHA256-Hash für Deduplizierung (v0.9.0)
    version,               -- Versionsnummer bei Duplikaten (v0.9.0)
    previous_version_id,   -- Referenz auf vorherige Version (v0.9.0)
    document_category,     -- Fachliche Kategorie
    classification_source,     -- ki_gpt4o, rule_bipro, fallback (v0.9.0)
    classification_confidence, -- high, medium, low (v0.9.0)
    classification_reason,     -- Begründung (v0.9.0)
    classification_timestamp,  -- Zeitpunkt (v0.9.0)
    ai_renamed, ai_processing_error,
    created_at, uploaded_by
)

-- VU-Verbindungen
vu_connections (id, user_id, name, vu_id, bipro_type, is_active)
vu_credentials (id, connection_id, username, password_encrypted)

-- XML-Index (v0.9.0)
xml_index (
    id, external_shipment_id, filename, raw_path, file_size,
    bipro_category, vu_name, content_hash, shipment_date, created_at
)

-- Processing-History (v0.9.0)
processing_history (
    id, document_id, previous_status, new_status,
    action, action_details, success, error_message,
    classification_source, classification_result,
    duration_ms, created_at, created_by
)

-- Audit-Log
audit_log (id, user_id, action, entity_type, entity_id, details, created_at)

-- Mitteilungszentrale (v2.0.0)
messages (
    id, title, description, severity,          -- info, warning, error, critical
    source, sender_name, created_at, expires_at
)
message_reads (message_id, user_id, read_at)   -- PK: (message_id, user_id)

-- Private Chat (v2.0.0)
private_conversations (
    id, user1_id, user2_id,                     -- UNIQUE (user1_id, user2_id), user1 < user2
    created_at, updated_at                      -- updated_at: serverseitig bei neuer Nachricht
)
private_messages (
    id, conversation_id, sender_id, receiver_id,
    content, created_at, read_at                -- read_at NULL = ungelesen
)

-- KI-Provider (v2.1.2)
ai_provider_keys (
    id, provider_type,              -- 'openrouter' oder 'openai'
    name, api_key_encrypted,        -- AES-256-GCM verschluesselt
    is_active,                      -- nur 1 gleichzeitig aktiv
    created_by, created_at, updated_at
)

-- Modell-Preise (v2.1.2)
model_pricing (
    id, provider, model_name,
    input_price_per_million,        -- $ pro 1M Input-Tokens
    output_price_per_million,       -- $ pro 1M Output-Tokens
    valid_from, is_active
)

-- KI-Request-Logging (v2.1.2)
ai_requests (
    id, user_id, provider, model,
    context, document_id,           -- context z.B. 'document_classification'
    prompt_tokens, completion_tokens, total_tokens,
    estimated_cost_usd, real_cost_usd,
    created_at
)

-- Dokumenten-Regeln (v2.1.3)
document_rules_settings (
    id INT PRIMARY KEY DEFAULT 1,   -- Single-Row-Tabelle
    file_dup_action,                -- none, color_both, color_new, delete_new, delete_old
    file_dup_color,                 -- VARCHAR(20), Farbe fuer Markierung
    content_dup_action,             -- analog file_dup
    content_dup_color,
    partial_empty_action,           -- none, remove_pages, color_file
    partial_empty_color,
    full_empty_action,              -- none, delete, color_file
    full_empty_color,
    updated_at, updated_by
)
```

---

## Erweiterungspunkte

### Neuen Versicherer anbinden

1. **Endpoint-URLs ermitteln** (STS, Transfer)
2. **Authentifizierungsflow testen** (STS-Token, Bearer, Basic?)
3. **Bei Bedarf**: transfer_service.py erweitern für VU-spezifische Logik
4. **VU-Verbindung anlegen** (in App oder Datenbank)

### Neue Kategorie hinzufügen

1. **Code ermitteln** (aus BiPRO-Response)
2. **In categories.py eintragen**:
```python
CATEGORY_NAMES["123456789"] = "Neue Kategorie"
```

### Neue Satzart (GDV)

1. Layout in `gdv_layouts.py` definieren
2. Zu `RECORD_LAYOUTS` hinzufügen
3. Optional: Domain-Klasse in `models.py`
4. Optional: Mapping in `mapper.py`

---

## Bekannte Einschraenkungen

- **Multi-User**: Archiv ist fuer Team (2-5 Personen) ausgelegt, kein Echtzeit-Sync
- **Kein Offline-Mode**: Server-Verbindung erforderlich
- **UI-Texte**: Groesstenteils in i18n/de.py, einige Hardcoded Strings verbleiben
- **Speicherverbrauch**: Alle Records/Dokumente im Speicher (kein Lazy Loading)
- **VU-spezifisch**: BiPRO-Flow variiert je VU (Degenia, VEMA haben eigene Logik)
- **Grosse Dateien**: bipro_view.py (~4900), archive_boxes_view.py (~6350), admin_view.py (~5200), main_hub.py (~1324) → Aufteilen geplant

## Unterstützte VUs

| VU | Status | Anmerkungen |
|----|--------|-------------|
| Degenia | ✅ | Standard BiPRO |
| VEMA | ✅ | VEMA-spezifisches Format |
| Weitere | 🔜 | Je nach VU anzupassen |
