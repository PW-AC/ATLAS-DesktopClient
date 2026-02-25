# ACENCIA ATLAS - API-Endpunkte und Datenbank

**Letzte Aktualisierung:** 24. Februar 2026
**API-Base-URL:** `https://acencia.info/api/`

---

## Authentifizierung

- **JWT-Token**: 30 Tage gueltig, im Header als `Authorization: Bearer <token>`
- **Single-Session**: Pro Nutzer nur eine aktive Session, bei Neuanmeldung werden alte beendet
- **API-Key**: Fuer externe Systeme (Power Automate Scans), im Header `X-API-Key`
- **Auto-Refresh**: Bei HTTP 401 wird Token automatisch erneuert (1x Retry)

---

## Alle API-Endpunkte (nach Bereich)

### Authentifizierung (`auth.php`, 279 Zeilen)

| Methode | Endpunkt | Auth | Beschreibung |
|---------|----------|------|--------------|
| POST | `/auth/login` | Nein | Login → JWT-Token + User-Daten + Permissions |
| POST | `/auth/logout` | JWT | Logout + Session beenden |
| GET | `/auth/verify` | JWT | Token verifizieren + User-Daten zurueckgeben |

### Dokumentenarchiv (`documents.php`, 1.748 Zeilen)

| Methode | Endpunkt | Auth | Beschreibung |
|---------|----------|------|--------------|
| GET | `/documents` | JWT | Alle Dokumente (mit Box-Filter, Duplikat-Metadaten, ?limit=10000) |
| GET | `/documents/{id}` | JWT | Einzelnes Dokument |
| GET | `/documents/{id}/history` | JWT + documents_history | Aenderungshistorie |
| GET | `/documents/{id}/ai-data` | JWT | Volltext + KI-Rohantwort |
| POST | `/documents/{id}/ai-data` | JWT | Volltext + KI-Daten speichern (Upsert) |
| POST | `/documents/{id}/replace` | JWT + documents_manage | PDF ersetzen (nach Bearbeitung) |
| GET | `/documents/search` | JWT | Volltextsuche (FULLTEXT + LIKE, include_raw, substring) |
| GET | `/documents/stats` | JWT | Box-Statistiken |
| GET | `/documents/missing-ai-data` | JWT | Dokumente ohne Text-Extraktion |
| POST | `/documents` | JWT + documents_upload | Dokument hochladen |
| PUT | `/documents/{id}` | JWT | Dokument aktualisieren (Name, Box, Farbe) |
| DELETE | `/documents/{id}` | JWT + documents_delete | Dokument loeschen |
| POST | `/documents/archive` | JWT | Bulk-Archivierung (IDs-Array) |
| POST | `/documents/unarchive` | JWT | Bulk-Entarchivierung |
| POST | `/documents/colors` | JWT | Bulk-Farbmarkierung |
| GET | `/documents/{id}/download` | JWT + documents_download | Datei herunterladen |

### BiPRO / VU-Verbindungen (`credentials.php`, 318 Zeilen)

| Methode | Endpunkt | Auth | Beschreibung |
|---------|----------|------|--------------|
| GET | `/credentials` | JWT + vu_connections_manage | Alle VU-Verbindungen |
| GET | `/credentials/{id}` | JWT | Einzelne Verbindung (inkl. Credentials) |
| POST | `/credentials` | JWT + vu_connections_manage | Neue VU-Verbindung |
| PUT | `/credentials/{id}` | JWT + vu_connections_manage | Verbindung aktualisieren |
| DELETE | `/credentials/{id}` | JWT + vu_connections_manage | Verbindung loeschen |

### KI-Proxy (`ai.php`, 427 Zeilen)

| Methode | Endpunkt | Auth | Beschreibung |
|---------|----------|------|--------------|
| POST | `/ai/classify` | JWT | KI-Klassifikation (Routing zu OpenRouter/OpenAI) |
| GET | `/ai/key` | JWT | API-Key fuer direkten OpenRouter-Zugriff (Legacy) |
| GET | `/ai/credits` | JWT | Provider-Guthaben (OpenRouter Balance / OpenAI Usage) |

### KI-Provider (`ai_providers.php`, 298 Zeilen)

| Methode | Endpunkt | Auth | Beschreibung |
|---------|----------|------|--------------|
| GET | `/ai-providers` | JWT | Alle Provider-Keys (maskiert) |
| GET | `/ai-providers/active` | JWT | Aktuell aktiver Provider |
| POST | `/admin/ai-providers` | JWT + Admin | Neuen Key erstellen |
| PUT | `/admin/ai-providers/{id}` | JWT + Admin | Key aktualisieren |
| PUT | `/admin/ai-providers/{id}/activate` | JWT + Admin | Key aktivieren |
| DELETE | `/admin/ai-providers/{id}` | JWT + Admin | Key loeschen |
| POST | `/admin/ai-providers/{id}/test` | JWT + Admin | Verbindungstest |

### Modell-Preise (`model_pricing.php`, 298 Zeilen)

| Methode | Endpunkt | Auth | Beschreibung |
|---------|----------|------|--------------|
| GET | `/model-pricing` | JWT | Aktive Preise |
| GET | `/admin/model-pricing` | JWT + Admin | Alle Preise |
| POST | `/admin/model-pricing` | JWT + Admin | Preis erstellen |
| PUT | `/admin/model-pricing/{id}` | JWT + Admin | Preis aktualisieren |
| GET | `/admin/ai-requests` | JWT + Admin | KI-Request-Historie |

### Verarbeitungs-Settings (`processing_settings.php`, 384 Zeilen)

| Methode | Endpunkt | Auth | Beschreibung |
|---------|----------|------|--------------|
| GET | `/processing-settings` | JWT | Aktuelle KI-Settings (Modell, Prompt, Stufen) |
| PUT | `/admin/processing-settings` | JWT + Admin | Settings speichern |
| GET | `/admin/prompt-versions` | JWT + Admin | Prompt-Versionshistorie |
| PUT | `/admin/prompt-versions/{id}/activate` | JWT + Admin | Version aktivieren |

### Dokumenten-Regeln (`document_rules.php`, 210 Zeilen)

| Methode | Endpunkt | Auth | Beschreibung |
|---------|----------|------|--------------|
| GET | `/document-rules` | JWT | Aktuelle Regeln |
| PUT | `/admin/document-rules` | JWT + Admin | Regeln speichern |

### Scan-Upload (`incoming_scans.php`, 425 Zeilen)

| Methode | Endpunkt | Auth | Beschreibung |
|---------|----------|------|--------------|
| POST | `/incoming-scans` | API-Key | Scan-Dokument empfangen (Base64, fuer Power Automate) |

### SmartScan (`smartscan.php`, 1.229 Zeilen)

| Methode | Endpunkt | Auth | Beschreibung |
|---------|----------|------|--------------|
| GET | `/smartscan/settings` | JWT | SmartScan-Einstellungen laden |
| PUT | `/admin/smartscan/settings` | JWT + Admin | Einstellungen speichern |
| POST | `/smartscan/send` | JWT + smartscan_send | Dokumente versenden |
| POST | `/smartscan/send-chunk` | JWT + smartscan_send | Chunk-Versand (max 10 Docs) |
| GET | `/smartscan/history` | JWT | Versandhistorie |
| GET | `/smartscan/history/{id}` | JWT | Job-Details |

### E-Mail-Konten (`email_accounts.php`, 1.028 Zeilen)

| Methode | Endpunkt | Auth | Beschreibung |
|---------|----------|------|--------------|
| GET | `/admin/email-accounts` | JWT + Admin | Alle Konten |
| POST | `/admin/email-accounts` | JWT + Admin | Konto erstellen |
| PUT | `/admin/email-accounts/{id}` | JWT + Admin | Konto aktualisieren |
| DELETE | `/admin/email-accounts/{id}` | JWT + Admin | Konto loeschen |
| POST | `/admin/email-accounts/{id}/test` | JWT + Admin | SMTP-Verbindungstest |
| POST | `/email/poll` | JWT | IMAP-Polling (neue Mails abrufen) |
| GET | `/email/inbox` | JWT | Inbox-Eintraege |
| GET | `/email/inbox/{id}/attachments` | JWT | Anhaenge eines Inbox-Eintrags |
| GET | `/email/attachments/pending` | JWT | Unverarbeitete Anhaenge |
| PUT | `/email/attachments/{id}/imported` | JWT | Anhang als importiert markieren |
| GET | `/email/attachments/{id}/download` | JWT | Anhang herunterladen |

### Passwoerter (`passwords.php`, 298 Zeilen)

| Methode | Endpunkt | Auth | Beschreibung |
|---------|----------|------|--------------|
| GET | `/passwords` | JWT | Aktive Passwoerter (Typ: pdf/zip) |
| GET | `/admin/passwords` | JWT + Admin | Alle Passwoerter |
| POST | `/admin/passwords` | JWT + Admin | Passwort erstellen |
| PUT | `/admin/passwords/{id}` | JWT + Admin | Passwort aktualisieren |
| DELETE | `/admin/passwords/{id}` | JWT + Admin | Passwort deaktivieren |

### Mitteilungen (`messages.php`, 252 Zeilen)

| Methode | Endpunkt | Auth | Beschreibung |
|---------|----------|------|--------------|
| GET | `/messages` | JWT | Alle Mitteilungen (mit Read-Status) |
| POST | `/messages/{id}/read` | JWT | Als gelesen markieren |
| POST | `/admin/messages` | JWT + Admin | Mitteilung erstellen |
| DELETE | `/admin/messages/{id}` | JWT + Admin | Mitteilung loeschen |

### Chat (`chat.php`, 400 Zeilen)

| Methode | Endpunkt | Auth | Beschreibung |
|---------|----------|------|--------------|
| GET | `/chat/conversations` | JWT | Alle Conversations |
| POST | `/chat/conversations` | JWT | Neue Conversation starten |
| GET | `/chat/conversations/{id}/messages` | JWT | Nachrichten laden |
| POST | `/chat/conversations/{id}/messages` | JWT | Nachricht senden |
| POST | `/chat/conversations/{id}/read` | JWT | Als gelesen markieren |

### Notifications (`notifications.php`, 109 Zeilen)

| Methode | Endpunkt | Auth | Beschreibung |
|---------|----------|------|--------------|
| GET | `/notifications/summary` | JWT | Unread-Counts + neueste Toast-Nachricht |

### Admin (`admin.php`, 407 Zeilen)

| Methode | Endpunkt | Auth | Beschreibung |
|---------|----------|------|--------------|
| GET | `/admin/users` | JWT + Admin | Alle Nutzer |
| POST | `/admin/users` | JWT + Admin | Nutzer erstellen |
| PUT | `/admin/users/{id}` | JWT + Admin | Nutzer aktualisieren (Name, Rechte, Status, update_channel) |
| PUT | `/admin/users/{id}/password` | JWT + Admin | Passwort aendern |

### Sessions (`sessions.php`, 174 Zeilen)

| Methode | Endpunkt | Auth | Beschreibung |
|---------|----------|------|--------------|
| GET | `/admin/sessions` | JWT + Admin | Alle aktiven Sessions |
| DELETE | `/admin/sessions/{id}` | JWT + Admin | Session beenden |
| DELETE | `/admin/sessions/user/{id}` | JWT + Admin | Alle Sessions eines Nutzers |

### Aktivitaetslog (`activity.php`, 227 Zeilen)

| Methode | Endpunkt | Auth | Beschreibung |
|---------|----------|------|--------------|
| GET | `/admin/activity` | JWT + Admin | Aktivitaetslog (Filter: User, Action, Zeitraum) |

### Releases (`releases.php`, ~850 Zeilen, inkl. Gate Engine)

| Methode | Endpunkt | Auth | Beschreibung |
|---------|----------|------|--------------|
| GET | `/updates/check` | Nein | Update-Check (Version vergleichen, Channel-Parameter) |
| GET | `/releases/latest` | Nein | Neueste Version herunterladen (fuer neue Nutzer) |
| GET | `/releases/download/{id}` | Nein | Installer nach ID herunterladen |
| GET | `/admin/releases` | JWT + Admin | Alle Releases |
| POST | `/admin/releases` | JWT + Admin | Release hochladen (Status = `pending`) |
| POST | `/admin/releases/{id}/validate` | JWT + Admin | Gate-Validierung (7 Gates) |
| POST | `/admin/releases/{id}/withdraw` | JWT + Admin | Release zurueckziehen + Auto-Fallback |
| GET | `/admin/releases/schema-snapshot` | JWT + Admin | DB-Schema-Hash + Tabellen-Inventar |
| PUT | `/admin/releases/{id}` | JWT + Admin | Release aktualisieren (Status-Uebergaenge erzwungen) |
| DELETE | `/admin/releases/{id}` | JWT + Admin | Release loeschen |

### Processing History (`processing_history.php`, 589 Zeilen)

| Methode | Endpunkt | Auth | Beschreibung |
|---------|----------|------|--------------|
| POST | `/processing_history/create` | JWT | Verarbeitungslog erstellen |
| PUT | `/processing_history/{id}` | JWT | Log aktualisieren |
| GET | `/processing_history/costs` | JWT + Admin | Kosten-Historie |
| GET | `/processing_history/cost_stats` | JWT + Admin | Aggregierte Kosten |

### BiPRO-Events (`bipro_events.php`, 278 Zeilen)

| Methode | Endpunkt | Auth | Beschreibung |
|---------|----------|------|--------------|
| GET | `/bipro-events` | JWT | Paginierte Liste (Filter: event_type, vu_name, is_read) |
| GET | `/bipro-events/summary` | JWT | Leichtgewichtig fuer Polling (unread_count, latest_event) |
| POST | `/bipro-events` | JWT | Neuen Event erstellen |
| PUT | `/bipro-events/read` | JWT | Bulk-Read-Markierung (IDs-Array) |
| PUT | `/bipro-events/read-all` | JWT | Alle als gelesen markieren |
| DELETE | `/bipro-events/{id}` | JWT + Admin | Einzelnen Event loeschen |
| DELETE | `/bipro-events/all` | JWT + Admin | Alle Events loeschen |

### Provisionsmanagement (`provision.php`, ~2.480 Zeilen)

| Methode | Endpunkt | Auth | Beschreibung |
|---------|----------|------|--------------|
| GET | `/pm/employees` | JWT + provision_access | Alle Mitarbeiter |
| GET | `/pm/employees/{id}` | JWT + provision_access | Einzelner Mitarbeiter |
| POST | `/pm/employees` | JWT + provision_access | Mitarbeiter erstellen |
| PUT | `/pm/employees/{id}` | JWT + provision_access | Mitarbeiter aktualisieren |
| DELETE | `/pm/employees/{id}` | JWT + provision_access | Mitarbeiter loeschen |
| GET | `/pm/contracts` | JWT + provision_access | Vertraege (Pagination) |
| GET | `/pm/contracts/{id}` | JWT + provision_access | Einzelner Vertrag |
| PUT | `/pm/contracts/{id}` | JWT + provision_access | Vertrag aktualisieren |
| GET | `/pm/contracts/unmatched` | JWT + provision_access | Ungematchte Xempus-Vertraege |
| GET | `/pm/commissions` | JWT + provision_access | Provisionen (Filter + Pagination) |
| PUT | `/pm/commissions/{id}/match` | JWT + provision_access | Manuelles Matching |
| PUT | `/pm/commissions/{id}/ignore` | JWT + provision_access | Provision ignorieren |
| POST | `/pm/commissions/recalculate` | JWT + provision_access | Splits neu berechnen |
| POST | `/pm/import/vu-liste` | JWT + provision_access | VU-Provisionsliste importieren |
| POST | `/pm/import/xempus` | JWT + provision_access | Xempus-Beratungen importieren (Legacy) |
| POST | `/pm/import/match` | JWT + provision_access | Auto-Matching ausloesen |
| GET | `/pm/import/batches` | JWT + provision_access | Import-Historie |
| GET | `/pm/dashboard/summary` | JWT + provision_access | Dashboard KPI-Daten |
| GET | `/pm/dashboard/berater/{id}` | JWT + provision_access | Berater-Detail |
| GET | `/pm/mappings` | JWT + provision_access | Vermittler-Mappings |
| POST | `/pm/mappings` | JWT + provision_access | Mapping erstellen |
| DELETE | `/pm/mappings/{id}` | JWT + provision_access | Mapping loeschen |
| GET | `/pm/abrechnungen` | JWT + provision_access | Alle Abrechnungen |
| GET | `/pm/abrechnungen/{id}` | JWT + provision_access | Einzelne Abrechnung |
| POST | `/pm/abrechnungen` | JWT + provision_access | Abrechnung generieren |
| PUT | `/pm/abrechnungen/{id}` | JWT + provision_access | Status aendern |
| GET | `/pm/models` | JWT + provision_access | Provisionsmodelle |
| POST | `/pm/models` | JWT + provision_access | Modell erstellen |
| PUT | `/pm/models/{id}` | JWT + provision_access | Modell aktualisieren |
| GET | `/pm/clearance` | JWT + provision_access | Klaerfall-Counts |
| GET | `/pm/audit` | JWT + provision_access | PM-Aktivitaetshistorie |
| GET | `/pm/match-suggestions` | JWT + provision_access | Multi-Level-Matching-Vorschlaege |
| PUT | `/pm/assign` | JWT + provision_access | Transaktionale Zuordnung |
| POST | `/pm/reset` | JWT + provision_manage | Gefahrenzone: Daten loeschen |

### Xempus Insight Engine (`xempus.php`, 1.360 Zeilen)

| Methode | Endpunkt | Auth | Beschreibung |
|---------|----------|------|--------------|
| POST | `/pm/xempus/import` | JWT + provision_access | RAW Ingest (chunked) |
| POST | `/pm/xempus/parse` | JWT + provision_access | Normalize + Parse |
| POST | `/pm/xempus/finalize` | JWT + provision_access | Finalize (Hash, Status) |
| GET | `/pm/xempus/batches` | JWT + provision_access | Import-Batches |
| GET | `/pm/xempus/employers` | JWT + provision_access | Arbeitgeber |
| GET | `/pm/xempus/employers/{id}` | JWT + provision_access | Arbeitgeber-Detail |
| GET | `/pm/xempus/employees` | JWT + provision_access | Arbeitnehmer |
| GET | `/pm/xempus/employees/{id}` | JWT + provision_access | Arbeitnehmer-Detail |
| GET | `/pm/xempus/consultations` | JWT + provision_access | Beratungen |
| GET | `/pm/xempus/stats` | JWT + provision_access | Statistiken |
| GET | `/pm/xempus/diff/{batch_id}` | JWT + provision_access | Snapshot-Diff |
| GET | `/pm/xempus/status-mapping` | JWT + provision_access | Status-Mappings laden |
| POST | `/pm/xempus/status-mapping` | JWT + provision_access | Status-Mapping speichern |
| POST | `/pm/xempus/sync/{batch_id}` | JWT + provision_access | Sync → pm_contracts |

---

## Datenbank-Tabellen (Uebersicht)

### Kern-Tabellen

| Tabelle | Zweck |
|---------|-------|
| `users` | Benutzer (Name, Passwort-Hash, account_type, update_channel, permissions JSON) |
| `sessions` | Aktive Sessions (Token-Hash, IP, Ablauf) |
| `activity_log` | Alle API-Aktionen (User, Aktion, Details, Zeitstempel) |

### Dokumentenarchiv

| Tabelle | Zweck |
|---------|-------|
| `documents` | Haupttabelle (Dateiname, Box, Farbe, Hash, Duplikat-Info, Seiten-Info) |
| `document_ai_data` | Volltext + KI-Daten (1:1 zu documents, CASCADE-Delete) |
| `document_rules_settings` | Single-Row Regelkonfiguration |
| `processing_history` | Verarbeitungs-Audit-Trail |
| `processing_ai_settings` | KI-Klassifikations-Konfiguration (Single-Row) |
| `prompt_versions` | Prompt-Versionierung |

### KI-System

| Tabelle | Zweck |
|---------|-------|
| `ai_provider_keys` | API-Keys (AES-256-GCM verschluesselt) |
| `model_pricing` | Input/Output-Preis pro 1M Tokens |
| `ai_requests` | Jeder KI-Call geloggt (Tokens, Kosten) |

### BiPRO / VU

| Tabelle | Zweck |
|---------|-------|
| `vu_connections` | VU-Verbindungen (Credentials verschluesselt) |
| `shipments` | BiPRO-Lieferungen |
| `bipro_events` | Strukturierte Metadaten aus 0-Dokument-Lieferungen (FK → documents) |

### E-Mail-System

| Tabelle | Zweck |
|---------|-------|
| `email_accounts` | SMTP/IMAP-Konten (AES-256-GCM) |
| `smartscan_settings` | SmartScan-Konfiguration |
| `smartscan_jobs` | Versand-Jobs |
| `smartscan_job_items` | Einzelne Dokumente pro Job |
| `smartscan_emails` | Gesendete E-Mails mit Message-IDs |
| `email_inbox` | IMAP-Import Eintraege |
| `email_inbox_attachments` | IMAP-Anhaenge (mit import_status) |

### Kommunikation

| Tabelle | Zweck |
|---------|-------|
| `messages` | System-/Admin-Mitteilungen |
| `message_reads` | Per-User Read-Status |
| `private_conversations` | Chat-Conversations |
| `private_messages` | Chat-Nachrichten |

### Passwoerter

| Tabelle | Zweck |
|---------|-------|
| `known_passwords` | PDF/ZIP-Passwoerter (Typ, Wert, Aktiv) |

### Releases

| Tabelle | Zweck |
|---------|-------|
| `releases` | Versionen (SHA256, Channel, Status, Downloads, gate_report, smoke_test_report) |
| `schema_migrations` | Tracking aller ausgefuehrten DB-Migrationen |

### Provisionsmanagement (pm_*)

| Tabelle | Zweck |
|---------|-------|
| `pm_commission_models` | Provisionssatzmodelle (Name, Rate) |
| `pm_employees` | Mitarbeiter (Rolle, Modell, TL-Override) |
| `pm_contracts` | Vertraege (VSNR, VU, Berater, Status) |
| `pm_commissions` | Provisionsbuchungen (Betrag, Splits, Match-Status) |
| `pm_vermittler_mapping` | VU-Vermittler → Berater (UNIQUE) |
| `pm_berater_abrechnungen` | Monats-Snapshots (UNIQUE monat+berater+revision) |
| `pm_import_batches` | Import-Historie |

### Xempus Insight Engine (xempus_*)

| Tabelle | Zweck |
|---------|-------|
| `xempus_employers` | Arbeitgeber (Name, Adresse, Tarif-Info) |
| `xempus_tariffs` | Tarife pro Arbeitgeber |
| `xempus_subsidies` | AG-Zuschuesse |
| `xempus_employees` | Arbeitnehmer (Name, Status) |
| `xempus_consultations` | Beratungen (VSNR, VU, Sparte, Berater) |
| `xempus_raw_rows` | Rohdaten (Sheet, JSON, row_hash) |
| `xempus_import_batches` | Import-Tracking (4 Phasen) |
| `xempus_commission_matches` | Consultation → Commission Matches |
| `xempus_status_mappings` | Xempus-Status → interner Status |

---

## Berechtigungssystem

> **Detaillierte Dokumentation**: Siehe `docs/02_SECURITY/PERMISSIONS.md`
> 14 Berechtigungen, 2 Kontotypen (Admin/Benutzer), Provisions-Sonderregel.
