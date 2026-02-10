# 09 - Offene Fragen und Unklarheiten

**Version:** 1.6.0
**Analyse-Datum:** 2026-02-10

---

## UNVERSTANDEN

### 1. acknowledgeShipment (BiPRO 430)

| Aspekt | Details |
|--------|---------|
| Was | BiPRO-Operation zum Quittieren von Lieferungen |
| Status | Code vorhanden in `transfer_service.py`, aber UNVERIFIZIERT |
| Frage | Wird acknowledgeShipment in der Produktion aufgerufen? Verhalten bei Fehler? |
| Hinweis | Degenia erfordert `BestaetigeLieferungen=true` in getShipment, VEMA NICHT |

### 2. Datenbank-Schema (vollstaendig)

| Aspekt | Details |
|--------|---------|
| Was | Vollstaendiges MySQL-Schema ist nicht dokumentiert |
| Status | Migrations-Skripte geben Hinweise, aber kein vollstaendiges CREATE-Script |
| Frage | Welche Tabellen existieren genau? Welche Indizes? |
| Bekannte Tabellen | users, sessions, activity_log, documents, processing_history, releases, known_passwords, email_accounts, smartscan_settings, smartscan_jobs, smartscan_job_items, smartscan_emails, email_inbox, email_inbox_attachments, vu_connections, permissions |

### 3. SmartAdmin-Integration

| Aspekt | Details |
|--------|---------|
| Was | `src/api/smartadmin_auth.py` (~640 Zeilen), `src/config/smartadmin_endpoints.py` (~490 Zeilen), `src/bipro/bipro_connector.py` (~397 Zeilen) |
| Status | Code vorhanden, jetzt in AGENTS.md Dateipfade dokumentiert. 47 VU-Endpunkte definiert. |
| Frage | Welche der 47 VUs sind produktiv getestet? Nur Degenia + VEMA sind als "funktioniert" markiert. |

---

## UNVERIFIZIERT

### 1. OpenRouter Rate-Limits

| Aspekt | Details |
|--------|---------|
| Was | OpenRouter hat Rate-Limits, die nicht dokumentiert sind |
| Status | Retry-Logik vorhanden, aber maximale Anfragen/Min unbekannt |
| Risiko | Bei grossen Batches koennten Rate-Limits greifen |

### 2. Server-Performance unter Last

| Aspekt | Details |
|--------|---------|
| Was | Strato Shared Hosting Performance bei vielen Anfragen |
| Status | Optimierungen vorhanden (Cache, Bulk-Ops), aber Limits unbekannt |
| Hinweis | SmartScan Chunking (max 10 Docs) deutet auf PHP-Timeout-Bewusstsein |

### 3. BiPRO Rate-Limiting pro VU

| Aspekt | Details |
|--------|---------|
| Was | Jede VU hat eigene Rate-Limits, die variieren koennen |
| Status | AdaptiveRateLimiter reagiert auf 429/503, aber keine VU-spezifischen Limits bekannt |
| Hinweis | `vu_max_workers_overrides` in processing_rules.py existiert, aber leer |

### 4. IMAP-Polling Intervall

| Aspekt | Details |
|--------|---------|
| Was | Wie oft wird IMAP gepollt? Nur manuell oder automatisch? |
| Status | Manueller Trigger ("Mails abholen" Button), kein automatischer Cron-Job |
| Frage | Soll automatisches Polling implementiert werden? |

---

## Fehlende Dokumentation

| Was fehlt | Auswirkung |
|-----------|------------|
| Vollstaendiges DB-Schema | Erschwert Backend-Aenderungen |
| BiPRO-Spezifika pro VU | Nur Degenia + VEMA dokumentiert, ~38 weitere undokumentiert |
| OpenRouter-Prompts (vollstaendig) | Prompts nur in Code, nicht separat dokumentiert |
| Testabdeckung-Uebersicht | Unklar welche Pfade getestet sind |
| Deployment-Prozess (vollstaendig) | Kein CI/CD, nur manuelles build.bat + WinSCP |
| DSGVO-Dokumentation | Technische Massnahmen erkennbar, aber keine formale DSGVO-Doku |

---

## Widersprueche / Legacy

### 1. Legacy archive_view.py vs. archive_boxes_view.py

| Aspekt | Details |
|--------|---------|
| Problem | Zwei Archiv-Views existieren parallel |
| `archive_view.py` | Aeltere Version (~1957 Z.), enthaelt PDFViewerDialog + SpreadsheetViewerDialog |
| `archive_boxes_view.py` | Aktuelle Version (~5380 Z.), importiert PDFViewerDialog aus archive_view |
| Status | archive_view.py ist keine vollstaendige Legacy-Datei, sondern enthaelt weiterhin aktiv genutzte Komponenten |

### 2. GDV-Editor Views

| Aspekt | Details |
|--------|---------|
| Problem | Mehrere GDV-bezogene UI-Dateien |
| `gdv_editor_view.py` | Wrapper/Container fuer den GDV-Editor |
| `main_window.py` | Enthaelt RecordTableWidget + ExpertDetailWidget |
| Status | Aufgabenteilung ist klar, aber Beziehung koennte besser dokumentiert sein |

### 3. MTOM-Parser Duplikat

| Aspekt | Details |
|--------|---------|
| Problem | MTOM-Parsing existiert in `transfer_service.py` UND `bipro_view.py` |
| Status | Beide haben PDF-Magic-Byte-Validierung + CRLF-Stripping (v1.1.0) |
| Risiko | Aenderungen muessen an zwei Stellen vorgenommen werden |

### 4. UI-Texte teilweise hardcoded

| Aspekt | Details |
|--------|---------|
| Problem | ~910 Keys in i18n/de.py, aber einige Texte noch direkt im Code |
| Status | Meiste Texte zentralisiert, aber nicht 100% |
| Beispiel | Manche QMessageBox.question()-Texte |

---

## Tech Debt (aus AGENTS.md)

| Datei | Problem | Groesse |
|-------|---------|---------|
| `bipro_view.py` | Zu gross, ParallelDownloadManager + MailImportWorker auslagern | ~4950 Z. |
| `archive_boxes_view.py` | Zu gross, SmartScanWorker + BoxDownloadWorker auslagern | ~5380 Z. |
| `admin_view.py` | Zu gross, 10 Panels in separate Dateien aufteilen | ~4000 Z. |
| `main_window.py` | Zu gross | ~1060 Z. |
| `openrouter.py` | Zu gross, Triage/Klassifikation separieren | ~1878 Z. |
| `partner_view.py` | Datenextraktion gehoert in domain/ | ~1138 Z. |
| MTOM-Parser | Duplikat in bipro_view.py und transfer_service.py | - |
| Qt Inline-Styles | Gegen User-Rule, CSS-Module einfuehren | - |
| QFont Warnings | `setPointSize: Point size <= 0 (-1)` beim Start | - |

---

## Offene TODOs (aus Code)

| Ort | TODO |
|-----|------|
| AGENTS.md | Lazy Loading fuer grosse Dateien (>10.000 Zeilen) |
| AGENTS.md | Unit-Tests einfuehren |
| AGENTS.md | Linter/Formatter konfigurieren (ruff) |
| AGENTS.md | i18n fuer alle UI-Texte vervollstaendigen |
| AGENTS.md | Weitere VUs anbinden (Signal Iduna, Nuernberger) |
| AGENTS.md | Logging-Konfiguration verbessern |

---

## Architektur-Entscheidungen (beschrieben, nicht bewertet)

### Raw XML statt zeep

| Aspekt | Details |
|--------|---------|
| Entscheidung | BiPRO SOAP via `requests` + Raw XML (nicht `zeep`) |
| Grund (dokumentiert) | zeep ist zu strikt fuer VU-spezifische BiPRO-Implementierungen |
| Auswirkung | Mehr manuelles XML-Parsing, dafuer VU-spezifische Anpassungen moeglich |

### ThreadPoolExecutor statt asyncio

| Aspekt | Details |
|--------|---------|
| Entscheidung | Threading + QThread statt asyncio |
| Grund (erkennbar) | Qt Event Loop und asyncio vertragen sich schlecht, QThread ist Qt-nativ |
| Auswirkung | Viele Worker-Klassen, aber nahtlose Qt-Signal/Slot-Integration |

### Server-seitiges IMAP statt Client-seitig

| Aspekt | Details |
|--------|---------|
| Entscheidung | PHP pollt IMAP, Python verarbeitet Attachments |
| Grund (erkennbar) | Shared Hosting hat keinen Cron, aber Python hat bessere File-Pipeline |
| Auswirkung | Hybridansatz: PHP fuer Netzwerk-IO, Python fuer Verarbeitung |

### Kein Offline-Modus

| Aspekt | Details |
|--------|---------|
| Entscheidung | Server muss erreichbar sein, kein lokaler Fallback |
| Grund (erkennbar) | Team arbeitet immer online, Server ist "Single Source of Truth" |
| Auswirkung | App blockiert bei Server-Ausfall (Login unmoeglich) |
