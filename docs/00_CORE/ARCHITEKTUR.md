# ACENCIA ATLAS - Architektur und Dateistruktur

**Letzte Aktualisierung:** 24. Februar 2026

---

## Systemarchitektur

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ ACENCIA ATLAS                                                               │
├─────────────────────────────────────────────────────────────────────────────┤
│ Desktop-App (PySide6/Qt)              Strato Webspace                       │
│ ├── UI Layer                          ├── PHP REST API (27 Dateien)         │
│ │   ├── main_hub.py (Navigation)      │   ├── auth.php (JWT)               │
│ │   ├── message_center_view.py        │   ├── documents.php (Archiv)       │
│ │   ├── chat_view.py                  │   ├── provision.php (GF-Bereich)   │
│ │   ├── bipro_view.py                 │   ├── bipro_events.php (Events)    │
│ │   ├── archive_boxes_view.py         │   ├── xempus.php (Insight Engine)  │
│ │   ├── gdv_editor_view.py            │   ├── ai.php (KI-Proxy)           │
│ │   ├── admin/ (15 Panels)            │   └── ... (20 weitere)            │
│ │   ├── provision/ (8 Panels)         │                                     │
│ │   └── toast.py                      ├── MySQL Datenbank (~42 Tabellen)   │
│ ├── API Clients                       ├── Dokumente-Storage (/dokumente/)  │
│ │   ├── client.py (Base)              └── Releases-Storage (/releases/)    │
│ │   ├── documents.py                                                        │
│ │   ├── provision.py                                                        │
│ │   └── ... (18 weitere)                                                    │
│ ├── BiPRO SOAP Client                                                       │
│ │   ├── transfer_service.py                                                 │
│ │   └── workers.py                                                          │
│ ├── Services Layer                                                           │
│ │   ├── document_processor.py                                               │
│ │   ├── provision_import.py                                                 │
│ │   └── ... (11 weitere)                                                    │
│ └── Parser Layer                                                             │
│     ├── gdv_parser.py                                                       │
│     └── gdv_layouts.py                                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│ Datenfluesse:                                                                │
│ 1. Desktop ←→ PHP-API ←→ MySQL/Dateien (Archiv, Auth, Provisionen)         │
│ 2. Desktop → BiPRO SOAP → Versicherer (STS-Token + Transfer)               │
│ 3. Desktop ←→ PHP-API → OpenRouter/OpenAI (KI-Proxy)                       │
│ 4. SharePoint → PHP-API → MySQL (Power Automate Scans)                     │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Python-Dateien (Desktop-App) - Vollstaendige Liste

### `src/` (Root)

| Datei | Zeilen | Zweck |
|-------|--------|-------|
| `__init__.py` | 18 | Package-Init |
| `main.py` | ~365 | Qt-App Initialisierung, asynchroner Update-Check, APP_VERSION aus VERSION, Mutex-Release fuer Updates |
| `background_updater.py` | ~260 | Headless Hintergrund-Updater (kein Qt), Scheduled Task / Autostart |

### `src/api/` (API-Clients, 21 Dateien)

| Datei | Zeilen | Zweck |
|-------|--------|-------|
| `client.py` | 523 | Base-Client mit JWT, Retry, Auto-Refresh |
| `documents.py` | 1.111 | Document-Modell, Upload/Download, Bulk-Ops, ATLAS-Suche, Duplikate |
| `provision.py` | 859 | ProvisionAPI (40+ Methoden), 11 Dataclasses (Employee, Contract, Commission...) |
| `auth.py` | 390 | Login/Logout, User-Model mit Permissions |
| `smartadmin_auth.py` | 640 | SmartAdmin-SAML-Auth fuer 47 VUs |
| `smartscan.py` | 502 | SmartScan + EmailAccounts API |
| `vu_connections.py` | 427 | VU-Verbindungen CRUD |
| `xempus.py` | 377 | Xempus Insight Engine API (Chunked Import, CRUD, Stats, Diff) |
| `processing_history.py` | 371 | Verarbeitungs-Audit-Trail |
| `xml_index.py` | 259 | XML-Rohdaten-Index |
| `admin.py` | 241 | Admin-Nutzerverwaltung |
| `gdv_api.py` | 229 | GDV-Dateien server-seitig parsen/speichern |
| `releases.py` | 171 | Release-Verwaltung + Update-Check |
| `chat.py` | 152 | 1:1 Chat-Nachrichten |
| `messages.py` | 143 | System-/Admin-Mitteilungen |
| `processing_settings.py` | 133 | KI-Klassifikations-Einstellungen |
| `ai_providers.py` | 120 | KI-Provider-Verwaltung (OpenRouter/OpenAI) |
| `model_pricing.py` | 117 | Modell-Preise + Request-Historie |
| `document_rules.py` | 94 | Dokumenten-Regeln (Duplikate, leere Seiten) |
| `bipro_events.py` | 135 | BiPRO-Events API (CRUD, Summary, Bulk-Read) |
| `passwords.py` | ~100 | PDF/ZIP-Passwoerter aus DB |

### `src/api/openrouter/` (KI-Integration, 6 Dateien)

| Datei | Zeilen | Zweck |
|-------|--------|-------|
| `classification.py` | 749 | Zweistufige KI-Klassifikation (Triage + Detail) |
| `client.py` | 253 | HTTP-Client mit Semaphore fuer Rate-Limiting |
| `ocr.py` | 244 | Vision-OCR fuer Bild-PDFs |
| `utils.py` | 188 | Keyword-Hints, Text-Aufbereitung |
| `models.py` | 170 | Dataclasses (ClassificationResult, etc.) |
| `__init__.py` | 49 | Package-Exports |

### `src/bipro/` (BiPRO SOAP, 7 Dateien)

| Datei | Zeilen | Zweck |
|-------|--------|-------|
| `transfer_service.py` | 1.330 | BiPRO 410 STS + 430 Transfer, SharedTokenManager |
| `workers.py` | 1.699 | 6 QThread-Worker (Fetch, Download, Ack, MailImport, ParallelDL, Events) |
| `bipro_connector.py` | 397 | SmartAdmin vs. Standard Verbindungsabstraktion |
| `rate_limiter.py` | 343 | AdaptiveRateLimiter (HTTP 429/503) |
| `mtom_parser.py` | 283 | MTOM/XOP-Response-Parser (Multipart-MIME) |
| `categories.py` | 155 | BiPRO-Kategorie-Code zu Name Mapping |

### `src/config/` (Konfiguration, 6 Dateien)

| Datei | Zeilen | Zweck |
|-------|--------|-------|
| `vu_endpoints.py` | 641 | VU-spezifische BiPRO-Endpunkte |
| `processing_rules.py` | ~604 | BiPRO-Code → Box-Mapping, Verarbeitungsregeln, PDFValidationStatus |
| `smartadmin_endpoints.py` | 490 | SmartAdmin VU-Endpunkte (47 Versicherer) |
| `certificates.py` | 298 | PFX/P12 Zertifikat-Manager |
| `ai_models.py` | 58 | Modell-Definitionen pro Provider |

### `src/domain/` (Datenmodelle, 4 Dateien)

| Datei | Zeilen | Zweck |
|-------|--------|-------|
| `models.py` | 623 | GDV-Domain (ParsedFile, ParsedRecord, GDVField) |
| `mapper.py` | 513 | GDV-Feldwert-Zuordnungen (Anrede, Sparte, etc.) |
| `xempus_models.py` | 375 | 9 Xempus-Dataclasses (Employer, Consultation, etc.) |

### `src/i18n/` (Uebersetzungen)

| Datei | Zeilen | Zweck |
|-------|--------|-------|
| `de.py` | ~2.179 | ~1.400+ deutsche UI-Texte (alle GROSSBUCHSTABEN_KEYS) |

### `src/services/` (Business-Logik, 13 Dateien)

| Datei | Zeilen | Zweck |
|-------|--------|-------|
| `document_processor.py` | ~2.300 | KI-Klassifikation, Verarbeitung, Regeln, Kosten |
| `provision_import.py` | 738 | VU/Xempus Excel-Parser, Normalisierung |
| `xempus_parser.py` | 404 | Xempus 5-Sheet Excel-Parser |
| `zip_handler.py` | 320 | ZIP-Entpackung (AES-256, rekursiv) |
| `update_service.py` | ~260 | Auto-Update (Check, Download, Verify, Install, /norun-Support) |
| `atomic_ops.py` | 214 | SHA256, Staging, Safe-Write |
| `empty_page_detector.py` | 191 | 4-Stufen Leere-Seiten-Erkennung |
| `pdf_unlock.py` | 169 | PDF-Passwort-Entsperrung (dynamisch aus DB) |
| `cost_calculator.py` | 164 | tiktoken Token-Zaehlung + Kostenberechnung |
| `msg_handler.py` | 155 | Outlook .msg Anhaenge extrahieren |
| `early_text_extract.py` | 149 | Text sofort nach Upload extrahieren |
| `image_converter.py` | 73 | Bild → PDF Konvertierung (PyMuPDF) |
| `data_cache.py` | ~340 | DataCacheService (Auto-Refresh, Thread-safe, separate Session fuer BG-Thread) |

### `src/ui/` (Hauptfenster, ~13 Dateien)

| Datei | Zeilen | Zweck |
|-------|--------|-------|
| `bipro_view.py` | ~3.530 | BiPRO-UI, VU-Verwaltung, Signal-Handling |
| `main_hub.py` | 1.529 | Haupt-Navigation, Drag&Drop, NotificationPoller, Schliess-Schutz |
| `partner_view.py` | 1.165 | Partner-Uebersicht (Firmen/Personen) |
| `main_window.py` | 1.072 | GDV-Editor Hauptfenster |
| `chat_view.py` | 876 | Vollbild-Chat (Conversation-Liste + Nachrichten) |
| `message_center_view.py` | ~1.077 | Mitteilungszentrale (3 Kacheln + BiPRO-Events) |
| `gdv_editor_view.py` | 598 | GDV-Editor View (RecordTable + Editor) |
| `toast.py` | 598 | ToastManager + ToastWidget + ProgressToast |
| `user_detail_view.py` | 515 | Benutzerfreundliche GDV-Detail-Ansicht |
| `settings_dialog.py` | 417 | Einstellungen (Zertifikate) |
| `update_dialog.py` | 361 | Update-Dialog (optional/deprecated Modi) |
| `auto_update_window.py` | ~250 | Zero-Interaction Pflicht-Update (automatischer Download + Install) |
| `login_dialog.py` | 288 | Login mit Auto-Login + Cache-Wipe |

### `src/ui/admin/` (Admin-Bereich, 21 Dateien)

| Datei | Zeilen | Zweck |
|-------|--------|-------|
| `admin_shell.py` | 390 | Shell mit Sidebar + QStackedWidget + Lazy Loading |
| `dialogs.py` | 723 | 6 Dialog-Klassen + AdminNavButton |
| `workers.py` | 190 | 8 Admin-Worker-Klassen |
| `panels/user_management.py` | 323 | Nutzerverwaltung |
| `panels/sessions.py` | 216 | Session-Management |
| `panels/passwords.py` | 414 | Passwort-Verwaltung |
| `panels/activity_log.py` | 286 | Aktivitaetslog |
| `panels/ai_costs.py` | 578 | KI-Kosten + Einzelne Requests |
| `panels/releases.py` | 455 | Release-Verwaltung |
| `panels/ai_classification.py` | 654 | KI-Pipeline + Prompt-Editor |
| `panels/ai_providers.py` | 335 | KI-Provider (OpenRouter/OpenAI) |
| `panels/model_pricing.py` | 308 | Modell-Preise |
| `panels/document_rules.py` | 274 | Dokumenten-Regeln |
| `panels/email_accounts.py` | 237 | E-Mail-Konten |
| `panels/smartscan_settings.py` | 321 | SmartScan-Einstellungen |
| `panels/smartscan_history.py` | 251 | SmartScan-Historie |
| `panels/email_inbox.py` | 322 | E-Mail-Posteingang |
| `panels/messages.py` | 286 | Admin-Mitteilungen |

### `src/ui/archive/` (Dokumentenarchiv, 4 Dateien)

| Datei | Zeilen | Zweck |
|-------|--------|-------|
| `archive_boxes_view.py` | ~5.645 | Box-UI, QTableView/Model, SmartScan, Duplikate, ATLAS Index, Historie |
| `archive_view.py` | ~2.674 | Legacy-View + PDFViewerDialog + DuplicateCompareDialog |
| `workers.py` | 901 | 16 QThread-Worker (Cache, Upload, Download, Processing, etc.) |

### `src/ui/provision/` (Provisionsmanagement, 14 Dateien)

| Datei | Zeilen | Zweck |
|-------|--------|-------|
| `models.py` | ~1.179 | **12 QAbstractTableModel-Klassen + Helper (Refactoring v3.4.0)** |
| `xempus_insight_panel.py` | ~784 | 4-Tab Xempus-Analyse (Arbeitgeber, Stats, Import, Status-Mapping) |
| `widgets.py` | 821 | 9 Shared Widgets (PillBadge, DonutChart, KpiCard, etc.) |
| `provisionspositionen_panel.py` | ~657 | Master-Detail mit FilterChips, PillBadges, VU-Vermittler |
| `verteilschluessel_panel.py` | ~648 | Modell-Karten + Mitarbeiter-Tabelle |
| `workers.py` | ~640 | **24 QThread-Worker fuer PM (Refactoring v3.4.0)** |
| `auszahlungen_panel.py` | ~491 | StatementCards, Status-Workflow, Export |
| `dashboard_panel.py` | ~436 | 4 KPI-Karten, DonutChart, Berater-Ranking |
| `zuordnung_panel.py` | ~398 | Klaerfaelle + Reverse-Matching |
| `dialogs.py` | ~348 | **MatchContractDialog + DiffDialog (Refactoring v3.4.0)** |
| `provision_hub.py` | ~340 | Hub mit Sidebar + 8 Panels |
| `settings_panel.py` | 341 | Gefahrenzone (Reset mit 3s-Countdown) |
| `xempus_panel.py` | ~333 | Xempus-Beratungen-Liste |
| `abrechnungslaeufe_panel.py` | ~276 | Import + Batch-Historie |

### `src/ui/styles/` (Design)

| Datei | Zeilen | Zweck |
|-------|--------|-------|
| `tokens.py` | 1.090 | ACENCIA Design-Tokens, Farben, Fonts, Pill-Colors, Rich-Tooltips |

---

## PHP-Dateien (Server-Backend) - Vollstaendige Liste

### `BiPro-Webspace Spiegelung Live/api/`

| Datei | Zeilen | Zweck |
|-------|--------|-------|
| `provision.php` | ~2.480 | Provisionsmanagement (Split-Engine, Auto-Matching, 32+ Routes) |
| `documents.php` | 1.748 | Dokumentenarchiv (CRUD, Bulk-Ops, Suche, Duplikate, Historie) |
| `xempus.php` | 1.360 | Xempus Insight Engine (4-Phasen-Import, CRUD, Stats, Diff) |
| `smartscan.php` | 1.229 | SmartScan (Settings, Send, Chunk, Historie) |
| `email_accounts.php` | 1.028 | E-Mail-Konten (SMTP/IMAP, Polling, Inbox) |
| `processing_history.php` | 589 | Verarbeitungs-Audit-Trail + Kosten-Historie |
| `releases.php` | 514 | Release-Verwaltung + Update-Check |
| `incoming_scans.php` | 425 | Scan-Upload (Power Automate, API-Key-Auth) |
| `ai.php` | 427 | KI-Proxy (OpenRouter/OpenAI Routing, PII-Redaktion, Kosten) |
| `admin.php` | 407 | Nutzerverwaltung (nur Admins) |
| `chat.php` | 400 | 1:1 Chat (Conversations, Messages, Read) |
| `gdv.php` | 399 | GDV-Operationen |
| `processing_settings.php` | 384 | KI-Klassifikations-Einstellungen |
| `credentials.php` | 318 | VU-Verbindungen (Credentials verschluesselt) |
| `ai_providers.php` | 298 | KI-Provider-Keys (AES-256-GCM) |
| `model_pricing.php` | 298 | Modell-Preise + Request-Logging |
| `passwords.php` | 298 | PDF/ZIP-Passwoerter |
| `index.php` | 297 | API-Router (alle Routes) |
| `auth.php` | 279 | Login/Logout/JWT-Token |
| `messages.php` | 252 | System-/Admin-Mitteilungen |
| `xml_index.php` | 247 | XML-Rohdaten-Index |
| `activity.php` | 227 | Aktivitaetslog-Endpunkte |
| `shipments.php` | 229 | BiPRO-Lieferungen |
| `document_rules.php` | 210 | Dokumenten-Regeln Settings |
| `sessions.php` | 174 | Session-Management |
| `bipro_events.php` | 278 | BiPRO-Events (Structured Metadata, CRUD, Bulk-Read) |
| `notifications.php` | 109 | Polling-Endpoint (Unread-Counts) |

### `BiPro-Webspace Spiegelung Live/api/lib/`

| Datei | Zweck |
|-------|-------|
| `permissions.php` | Permission-Middleware (requirePermission, requireAdmin) |
| `activity_logger.php` | Zentrales Activity-Logging |
| `db.php` | Datenbank-Verbindung |
| `response.php` | JSON-Response-Helpers |
| `PHPMailer/` | PHPMailer v6.9.3 (3 Dateien: PHPMailer.php, SMTP.php, Exception.php) |

---

## DB-Migrationen (21 Skripte)

| Nr. | Datei | Zweck |
|-----|-------|-------|
| 005 | `add_box_columns.php` | Box-Spalten fuer Dokumentenarchiv |
| 006 | `add_bipro_category.php` | BiPRO-Kategorie-Spalte |
| 007 | `add_is_archived.php` | Archivierungs-Flag |
| 008 | `add_box_type_falsch.php` | Box "falsch" (Admin-Umlagerung) |
| 010 | `smartscan_email.php` | 7 Tabellen fuer E-Mail-System |
| 011 | `fix_smartscan_schema.php` | Schema-Fix SmartScan |
| 012 | `add_documents_history_permission.php` | documents_history Berechtigung |
| 013 | `rate_limits.php` | Rate-Limiting Tabelle |
| 014 | `encrypt_passwords.php` | Passwort-Verschluesselung |
| 015 | `message_center.php` | 4 Tabellen fuer Mitteilungen + Chat |
| 016 | `empty_page_detection.php` | empty_page_count Spalten |
| 017 | `document_ai_data.php` | document_ai_data Tabelle |
| 018 | `content_duplicate_detection.php` | content_duplicate_of_id |
| 024 | `provision_matching_v2.php` | VN-Normalisierung, Indizes, UNIQUE |
| 025 | `provision_indexes.php` | 8 operative Indizes |
| 026 | `vsnr_renormalize.php` | VSNR: Alle Nullen entfernen |
| 027 | `reset_provision_data.php` | Reset-Funktion fuer Gefahrenzone |
| 028 | `xempus_complete.php` | 9 neue xempus_* Tabellen |
| 029 | `provision_role_permissions.php` | provision_access + provision_manage |
| 030 | `bipro_events.php` | BiPRO-Events Tabelle (Metadaten aus 0-Dokument-Lieferungen) |
| 031 | `model_tl_fields.php` | TL-Rate + TL-Basis in pm_commission_models |

---

## Wichtige Sonstige Dateien

| Datei | Zweck |
|-------|-------|
| `run.py` | Start-Script (`python run.py` oder `--background-update` fuer Hintergrund-Updater) |
| `VERSION` | Zentrale Versionsdatei (aktuell: 2.2.0) |
| `requirements.txt` | 13 Python-Abhaengigkeiten |
| `AGENTS.md` | Agent-Dokumentation (Single Source of Truth) |
| `docs/ARCHITECTURE.md` | Architektur-Dokumentation |
| `docs/DOMAIN.md` | Datenmodell-Dokumentation |
| `docs/DEVELOPMENT.md` | Entwicklungs-Richtlinien |
| `docs/BIPRO_ENDPOINTS.md` | BiPRO VU-Endpunkte |
| `docs/ui/UX_RULES.md` | Verbindliche UI-Regeln (keine modalen Popups) |
| `testdata/sample.gdv` | GDV-Testdatei |
| `src/tests/run_smoke_tests.py` | 11 Smoke-Tests |
| `logs/bipro_gdv.log` | Laufzeit-Log (Rotation 5 MB, 3 Backups) |
| `installer.iss` | Inno Setup Installer-Script |

---

## Performance- und Threading-Architektur

### Asynchrone Operationen (UI bleibt responsiv)

| Operation | Worker | Datei |
|-----------|--------|-------|
| Update-Check beim App-Start | `_UpdateCheckWorker` (QThread) | `src/main.py` |
| Outlook E-Mail-Extraktion (COM) | `_OutlookWorker` (QThread) | `src/ui/main_hub.py` |
| PDF-Thumbnail-Rendering | `_ThumbnailWorker` (QThread) | `src/ui/archive_view.py` |
| Cache-Refresh | `_refresh_all_background` (threading.Thread) | `src/services/data_cache.py` |
| BiPRO-Quittierung (>3 IDs) | `ThreadPoolExecutor` (max 4 parallel) | `src/bipro/workers.py` |

### Timeout-Konfiguration

| Endpoint | Client-Timeout | Server-Timeout | Datei |
|----------|---------------|----------------|-------|
| Standard-API | 30s | - | `src/api/client.py` |
| KI-Classify (`/ai/classify`) | 150s | 120s (cURL) | `src/api/openrouter/client.py` |
| SmartScan Process | 330s | 300s (PHP) | `src/api/smartscan.py` |
| SmartScan Send | 180s | - | `src/api/smartscan.py` |
| IMAP-Poll | 120s | - | `src/api/smartscan.py` |
| BiPRO SOAP | 30s | - | `src/bipro/transfer_service.py` |

### KI-Pipeline Backpressure

- Max parallele KI-Aufrufe: 8 (gesteuert via `threading.Semaphore`)
- Konfiguriert in: `src/api/openrouter/client.py` (`DEFAULT_MAX_CONCURRENT_AI_CALLS`)
- DocumentProcessor Worker-Pool: 8 Threads (`DEFAULT_MAX_WORKERS`)

---

## Release-Channel-System

### Channels (server-seitig pro User)

| Channel | Branch | Zielgruppe |
|---------|--------|------------|
| `stable` | `main` | Alle Berater |
| `beta` | `develop` | GF, Tester |
| `dev` | `dev` | Nur Entwickler |

- Feld `update_channel` in `users`-Tabelle (ENUM: stable/beta/dev, Default: stable)
- Client liest Channel bei Login/Verify und prueft Updates im zugewiesenen Channel
- Admin-Panel: Channel pro User einstellbar

### Release Gate Engine

Releases durchlaufen einen definierten Lebenszyklus mit server-seitigen Gate-Checks:

```
Upload -> pending -> [Validate] -> validated -> [Activate] -> active
                  -> blocked -> pending (retry)
                                                active -> [Withdraw] -> withdrawn (+ Auto-Fallback)
```

7 Gate-Checks:
1. Schema-Version -- erwartete Migration angewendet
2. Split-Invariante -- `berater_anteil + tl_anteil + ag_anteil == betrag`
3. Matching-Konsistenz -- keine verwaisten Matchings
4. Smoke-Test-Report -- Tests bestanden, Version korrekt
5. Versions-Konsistenz -- SemVer-Format pro Channel
6. Schema-Struktur -- kritische Tabellen, Indexes, Spalten vorhanden (+ Schema-Hash Audit)
7. Daten-Integritaet -- keine orphaned FKs, keine fehlenden Berater-Referenzen

Withdraw-Endpoint (`POST /admin/releases/{id}/withdraw`) zieht ein aktives Release zurueck und reaktiviert automatisch das vorherige Release im gleichen Channel.

Details: `docs/01_DEVELOPMENT/RELEASE_STRATEGY.md`

### Git-Governance

- Branch-Strategie: `main` (stable) / `develop` (beta) / `dev` (experimental)
- PR-Pflicht fuer `main` und `develop`
- CI: GitHub Actions Smoke Tests bei PRs
- Details: `docs/01_DEVELOPMENT/GIT_GOVERNANCE.md`
