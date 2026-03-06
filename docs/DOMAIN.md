# DOMAIN.md - ACENCIA ATLAS Fachdomaene

> **Stand**: 05.03.2026 | **Version**: 2.3.1

---

## Ueberblick

ACENCIA ATLAS ist eine Fachanwendung fuer **Versicherungsvermittler**. Die Kerndomaene umfasst:

1. **BiPRO-Datenabruf** - Automatisierter Dokumentenabruf von Versicherungsunternehmen
2. **Dokumentenarchiv** - Verwaltung und KI-Klassifikation von Versicherungsdokumenten
3. **Provisionsmanagement** - Verwaltung von Vermittlerprovisionen und Abrechnungen
4. **GDV-Datensaetze** - Branchenstandard-Datenformat fuer Versicherungsdaten
5. **Workforce / HR** - Mitarbeiterverwaltung und HR-Provider-Integration

---

## Begriffe / Glossar

### Allgemein

| Begriff | Bedeutung |
|---------|-----------|
| **VU** | Versicherungsunternehmen (z.B. Allianz, SwissLife) |
| **Vermittler** | Person/Firma die Versicherungen vermittelt |
| **VSNR** | Versicherungsscheinnummer (eindeutige Vertragsnummer) |
| **Courtage** | Provision die ein Vermittler fuer den Abschluss erhaelt |
| **Sparte** | Versicherungsbereich (Sach, Leben, Kranken, etc.) |

### BiPRO

| Begriff | Bedeutung |
|---------|-----------|
| **BiPRO** | Brancheninitiative Prozessoptimierung (Datenstandard der Versicherungsbranche) |
| **Norm 410 (STS)** | Security Token Service - Authentifizierung beim VU |
| **Norm 430 (Transfer)** | Datentransfer-Service - Lieferungen abrufen |
| **Lieferung (Shipment)** | Ein Dokumentenpaket vom VU (PDF, XML, GDV) |
| **MTOM/XOP** | Message Transmission Optimization Mechanism (Binaerdaten in SOAP) |
| **SmartAdmin** | Alternative BiPRO-Anbindung ueber SmartAdmin-Plattform |

### GDV

| Begriff | Bedeutung |
|---------|-----------|
| **GDV** | Gesamtverband der Deutschen Versicherungswirtschaft |
| **GDV-Datensatz** | Fixed-Width-Format (256 Bytes/Zeile), Branchenstandard |
| **Satzart** | 4-stellige Kennung des Datensatztyps (0001, 0100, 0200, ...) |
| **CP1252** | Windows-Encoding fuer deutsche Umlaute in GDV |
| **Vorsatz (0001)** | Datei-Header mit Metadaten |
| **Nachsatz (9999)** | Datei-Footer mit Pruefsummen |

### Dokumentenarchiv

| Begriff | Bedeutung |
|---------|-----------|
| **Box** | Kategorie-Ordner im Archiv (GDV, Courtage, Sach, Leben, Kranken, Sonstige, Roh, Falsch) |
| **KI-Klassifikation** | Automatische Einordnung von Dokumenten in Boxen per OpenRouter/OpenAI |
| **Confidence** | Sicherheitswert der KI-Klassifikation (0.0-1.0) |
| **Smart!Scan** | Funktion zum E-Mail-Versand von Dokumenten an Scanner/Empfaenger |
| **Duplikat-Erkennung** | SHA256-basierte Pruefung auf doppelte Dokumente |
| **Content-Duplikat** | Dokument mit identischem Text (auch bei verschiedener Datei) |

### Provisionsmanagement

| Begriff | Bedeutung |
|---------|-----------|
| **Provision (Commission)** | Verguetung fuer einen vermittelten Versicherungsvertrag |
| **VU-Provisionsliste** | Excel-Datei vom VU mit allen Provisionszeilen eines Monats |
| **Xempus** | Plattform fuer betriebliche Altersvorsorge (bAV) |
| **Consulter** | Berater/Vermittler-Rolle im Team |
| **Teamleiter (TL)** | Fuehrungskraft mit Provisions-Override |
| **Backoffice** | Verwaltungsrolle (keine Provision) |
| **Split-Berechnung** | Aufteilung der Provision: Berater-Anteil, TL-Abzug, AG-Anteil |
| **Matching** | Zuordnung von VU-Provisionszeilen zu internen Beratern (VSNR-basiert) |
| **Abrechnung** | Monatsabrechnung fuer einen Berater (berechnet → ausgezahlt) |
| **Rueckbelastung** | Negative Provision (Storno, Rueckbuchung) |

### Workforce / HR

| Begriff | Bedeutung |
|---------|-----------|
| **Arbeitgeber (Employer)** | Firma deren Mitarbeiter verwaltet werden |
| **HR-Provider** | Externer Dienst fuer Mitarbeiterdaten (Personio, HRworks, SageHR) |
| **Snapshot** | Zeitpunktbezogene Kopie aller Mitarbeiterdaten eines Arbeitgebers |
| **Delta** | Differenz zwischen zwei Snapshots (Aenderungen) |
| **SCS-Export** | Standardisierter Export im SCS-Format (XLSX) |
| **Trigger** | Automatisierte Aktion bei Mitarbeiterdaten-Aenderung (E-Mail, API) |
| **Trigger-Run** | Protokollierter Ausfuehrungslauf eines Triggers |
| **Credentials** | Verschluesselte Zugangsdaten fuer HR-Provider (AES-256-GCM) |

---

## Entitaeten

### User (Benutzer)

```
User
├── id: int
├── username: str
├── email: str (optional)
├── account_type: 'user' | 'admin' | 'super_admin'
├── update_channel: 'stable' | 'beta'
├── permissions: List[str]
├── modules: List[UserModule]    -- freigeschaltete Module mit Zugangslevel
├── is_locked: bool
└── last_login_at: str (optional)
```

**Account-Typen**:
- `user`: Standard-Nutzer, nur freigeschaltete Module
- `admin`: Admin-Rechte + alle Standard-Panels
- `super_admin`: Alles inkl. Server-Management-Panels

**Berechtigungen**:
- Standard: Admins haben alle (ausser Provision/HR)
- Provision: `provision_access`, `provision_manage` (explizit)
- HR: `hr.view`, `hr.sync`, `hr.export`, `hr.triggers`, `hr.admin` (explizit)
- Modul-spezifisch: Ueber Rollen konfigurierbar (role_permissions)

### Document (Dokument)

```
Document
├── id: int
├── filename: str
├── box: str (GDV | Courtage | Sach | Leben | Kranken | Sonstige | Roh | Falsch)
├── mime_type: str
├── size: int
├── checksum: str (SHA256)
├── color: str (optional, 8 Farben)
├── ai_category: str (optional)
├── ai_confidence: float (optional)
├── ai_name: str (optional, automatisch generierter Name)
├── empty_page_count: int
├── total_page_count: int
├── duplicate_of_id: int (optional)
├── content_duplicate_of_id: int (optional)
├── is_archived: bool
├── created_at: datetime
└── updated_at: datetime
```

### Commission (Provision)

```
Commission
├── id: int
├── contract_id: int (FK)
├── employee_id: int (FK, optional)
├── amount: Decimal
├── commission_type: str
├── period: str (YYYY-MM)
├── vu_name: str
├── vsnr: str
├── sparte: str
├── is_matched: bool
├── split_berater: Decimal (optional)
├── split_tl: Decimal (optional)
├── split_ag: Decimal (optional)
└── created_at: datetime
```

### Module (Modul)

```
Module
├── id: int
├── module_key: str ('core' | 'provision' | 'workforce')
├── name: str
├── description: str (optional)
├── is_active: bool
├── created_at: datetime
└── updated_at: datetime
```

### UserModule (Modul-Zugriff pro User)

```
UserModule
├── id: int
├── user_id: int (FK → users)
├── module_key: str (FK → modules)
├── is_enabled: bool
├── access_level: 'user' | 'admin'
├── created_at: datetime
└── updated_at: datetime
```

### Role (Modul-Rolle)

```
Role
├── id: int
├── module_key: str (FK → modules)
├── role_key: str (z.B. 'provision.manager', 'hr.admin')
├── name: str
├── description: str (optional)
├── permissions: List[Permission]
├── created_at: datetime
└── updated_at: datetime
```

### HR Employer (Arbeitgeber)

```
Employer
├── id: int
├── name: str
├── provider: 'hrworks' | 'personio' | 'sagehr'
├── has_credentials: bool
├── employee_count: int
├── last_sync_at: datetime (optional)
├── is_active: bool
├── created_at: datetime
└── updated_at: datetime
```

### HR Employee (Mitarbeiter)

```
Employee
├── id: int
├── employer_id: int (FK)
├── external_id: str (Provider-ID)
├── first_name: str
├── last_name: str
├── email: str (optional)
├── status: str (active, inactive, terminated)
├── department: str (optional)
├── position: str (optional)
├── hire_date: date (optional)
├── termination_date: date (optional)
├── data_hash: str (fuer Delta-Erkennung)
├── created_at: datetime
└── updated_at: datetime
```

### HR Trigger

```
Trigger
├── id: int
├── name: str
├── event: str (employee.created | employee.updated | employee.terminated | ...)
├── action_type: 'email' | 'api'
├── action_config: dict (SMTP-Daten / API-URL)
├── conditions: List[Condition] (Feld, Operator, Wert)
├── is_active: bool
├── excluded_employers: List[int]
├── created_at: datetime
└── updated_at: datetime
```

---

## Workflows

### Dokumenten-Upload-Workflow

```
Benutzer waehlt Dateien → Upload → Server speichert in "Eingang" (Roh-Box)
                                    │
                                    ├── ZIP? → Entpacken (rekursiv, AES-256)
                                    ├── MSG? → Anhaenge extrahieren (COM/pywin32)
                                    ├── PDF geschuetzt? → Passwort-Entsperrung
                                    │
                                    ▼
                              Text-Extraktion (PyMuPDF)
                                    │
                                    ▼
                              Duplikat-Pruefung (SHA256 + Content)
                                    │
                                    ├── Duplikat → Markierung + Regel (skip/archive/move)
                                    │
                                    ▼
                              KI-Klassifikation (Stufe 1: GPT-4o-mini)
                                    │
                                    ├── Confidence < Schwellwert → Stufe 2: GPT-4o
                                    │
                                    ▼
                              Verschieben in Ziel-Box + AI-Umbenennung
                                    │
                                    ▼
                              Leere-Seiten-Pruefung → ggf. automatisches Entfernen
```

### Provisions-Matching-Workflow

```
VU-Provisionsliste (Excel) → Parser (Column-Mapping, Normalisierung)
                                    │
                                    ▼
                              Import in DB (pm_commissions)
                                    │
                                    ▼
                              Auto-Matching (5-Schritt Batch-JOIN):
                              1. VSNR direkt → pm_contracts
                              2. Vertragsnr-Matching
                              3. Vermittler-Zuordnung (pm_vu_mappings)
                              4. Berater-Zuweisung (pm_employees)
                              5. Split-Berechnung:
                                 - Rueckbelastung: 100% Berater
                                 - Positiv ohne TL: Berater-Satz + AG-Rest
                                 - Positiv mit TL: Berater-Satz + TL-Override + AG-Rest
                                    │
                                    ▼
                              Dashboard-Aktualisierung (KPIs, Ranking)
```

### HR-Sync-Workflow

```
Arbeitgeber auswaehlen → Credentials laden (PHP, entschluesselt)
                                    │
                                    ▼
                              Provider-API aufrufen (Personio/HRworks direkt)
                                    │
                                    ▼
                              Mitarbeiter-Daten empfangen
                                    │
                                    ▼
                              Letzten Snapshot laden (PHP)
                                    │
                                    ▼
                              Delta berechnen (Hash-Vergleich):
                              - Neue Mitarbeiter (added)
                              - Geaenderte Mitarbeiter (changed, mit Feldliste)
                              - Entfernte Mitarbeiter (removed)
                                    │
                                    ▼
                              XLSX generieren (Delta-SCS-Format)
                                    │
                                    ▼
                              Neuen Snapshot speichern (PHP)
                              Export hochladen (PHP/Volume)
                                    │
                                    ▼
                              Trigger auswerten:
                              - Event matchen (employee.created, .updated, .terminated)
                              - Bedingungen pruefen (Feld + Operator + Wert)
                              - Aktion ausfuehren (E-Mail via smtplib / API via requests)
                              - Trigger-Run loggen (PHP)
```

### BiPRO-Abruf-Workflow

```
VU-Verbindung waehlen → STS-Authentifizierung (Norm 410)
                                    │
                                    ▼
                              listShipments (Norm 430) → Lieferungsliste
                                    │
                                    ▼
                              getShipment pro Lieferung (MTOM/XOP):
                              - PDF-Validierung + Reparatur
                              - Magic-Byte-Pruefung
                                    │
                                    ▼
                              Upload ins Dokumentenarchiv → KI-Pipeline
```

---

## Datenbank-Tabellen (Uebersicht)

### Kern-Tabellen

| Tabelle | Beschreibung |
|---------|-------------|
| `users` | Benutzer mit account_type (user/admin/super_admin), permissions |
| `sessions` | Aktive JWT-Sessions |
| `documents` | Dokumente im Archiv (Box-System) |
| `document_ai_data` | KI-Daten zu Dokumenten (1:1) |
| `document_history` | Aenderungshistorie pro Dokument |
| `messages` | System-/Admin-Mitteilungen |
| `message_reads` | Per-User Lese-Status |
| `private_conversations` | 1:1 Chat-Konversationen |
| `private_messages` | Chat-Nachrichten |
| `activity_log` | API-Aktivitaetsprotokoll |

### Provision-Tabellen (pm_*)

| Tabelle | Beschreibung |
|---------|-------------|
| `pm_employees` | Mitarbeiter (Berater, TL, Backoffice) |
| `pm_contracts` | Vertraege (VSNR, VU, Sparte) |
| `pm_commissions` | Provisionszeilen |
| `pm_vu_mappings` | VU-Vermittlername → interner Berater |
| `pm_import_batches` | Import-Batches (VU-Listen, Xempus) |
| `pm_abrechnungen` | Monatsabrechnungen |
| `pm_settings` | Provisions-Einstellungen |

### HR-Tabellen (hr_*)

| Tabelle | Beschreibung |
|---------|-------------|
| `hr_employers` | Arbeitgeber |
| `hr_employer_credentials` | Verschluesselte Provider-Credentials |
| `hr_employees` | Mitarbeiter |
| `hr_snapshots` | Zeitpunkt-Snapshots |
| `hr_exports` | Generierte Exporte |
| `hr_triggers` | Trigger-Definitionen |
| `hr_trigger_runs` | Trigger-Ausfuehrungsprotokoll |
| `hr_smtp_config` | SMTP-Konfiguration |
| `hr_excluded_employers` | Ausgeschlossene Arbeitgeber pro Trigger |

### KI-Tabellen

| Tabelle | Beschreibung |
|---------|-------------|
| `ai_provider_keys` | KI-Provider API-Keys (verschluesselt) |
| `model_pricing` | Modell-Preise (Input/Output pro 1M Tokens) |
| `ai_requests` | Einzelne KI-Requests (Kosten, Tokens, Modell) |
| `processing_settings` | KI-Klassifikation-Einstellungen |
| `document_rules_settings` | Regeln fuer Duplikate/leere Seiten |

### Modul-Tabellen (Migrationen 045-050)

| Tabelle | Migration | Beschreibung |
|---------|-----------|-------------|
| `modules` | 046 | Registrierte Module (core, provision, workforce) |
| `user_modules` | 047 | User ↔ Modul (is_enabled, access_level: user/admin) |
| `roles` | 048 | Modul-spezifische Rollen (role_key, name, description) |
| `permissions` | 048 | Erweitert um module_key-Zuordnung |
| `role_permissions` | 049 | Rolle ↔ Permission Mapping |
| `user_roles` | 049 | User ↔ Rolle Mapping pro Modul |

### System-Tabellen

| Tabelle | Beschreibung |
|---------|-------------|
| `passwords` | PDF/ZIP-Passwoerter (verschluesselt) |
| `email_accounts` | SMTP/IMAP-Konten (verschluesselt) |
| `smartscan_settings` | Smart!Scan-Konfiguration |
| `smartscan_history` | Smart!Scan-Versandhistorie |
| `releases` | Release-Versionen (Auto-Update) |
| `bipro_events` | BiPRO-Events |
| `notifications` | Benachrichtigungs-Summary |
| `server_audit_log` | Server-Audit-Log (Super-Admin) |
| `migrations` | Durchgefuehrte DB-Migrationen (005-050) |

---

## Validierungsregeln

### Dokumenten-Benennung

Schema: `Versicherer_Typ_Datum.pdf` (automatisch durch KI, manuell ueberschreibbar)

### VSNR (Versicherungsscheinnummer)

- Normalisierung: Leerzeichen, Punkte, Bindestriche entfernen
- Gross-/Kleinschreibung irrelevant
- Matching: Exakter Vergleich nach Normalisierung

### GDV-Felder

- Satzart: Immer 4-stellig mit fuehrenden Nullen ("0100", "0200")
- Zeilenlaenge: Exakt 256 Bytes
- Encoding: CP1252

### Berechtigungen

- **Account-Typen**: `user` → `admin` → `super_admin` (3-stufig, Migration 045)
- **Modul-Zugriff**: Pro User konfigurierbar (user_modules-Tabelle, Migration 047)
- **Modul-Rollen**: Pro Modul definierbare Rollen mit granularen Rechten (roles + role_permissions)
- **Zugangslevel**: `user` (Standard) oder `admin` (Modul-Verwaltungsrechte) pro Modul
- Provision/HR-Rechte: Muessen explizit vergeben werden (auch fuer Admins)
- Standard-Rechte: Admins erhalten automatisch alle (ausser Provision/HR)
- Super-Admin (`account_type = 'super_admin'`): Zugriff auf Server-Management-Panels
