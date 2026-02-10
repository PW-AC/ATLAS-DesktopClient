# Architektur - ACENCIA ATLAS v1.6.0

**Stand:** 10. Februar 2026

**Primaere Referenz: `AGENTS.md`** - Dieses Dokument enthaelt ergaenzende Architektur-Details. Fuer den aktuellen Feature-Stand und Debugging-Tipps siehe `AGENTS.md`.

## Neue Features in v1.1.4 (App-Schliess-Schutz)

### Schliess-Schutz bei laufenden Operationen
- **Blockierende Worker**: `ProcessingWorker` (KI-Verarbeitung), `DelayedCostWorker` (Kosten-Ermittlung), `SmartScanWorker` (E-Mail-Versand)
- **Mechanismus**: `ArchiveBoxesView.get_blocking_operations()` liefert Liste blockierender Operationen
- **MainHub**: `closeEvent()` prueft vor allen anderen Checks (GDV-Aenderungen etc.)
- **UX**: `event.ignore()` + Toast-Warnung (kein modaler Dialog, kein "Trotzdem beenden?")
- **Sicherheit**: `_is_worker_running()` faengt `RuntimeError` bei geloeschten C++-Objekten ab

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
│  │ Navigation  │ │ BiPRO-Abruf │ │ _view.py    │ │   10 Admin-Panels       ││
│  │ Drag&Drop   │ │ MailImport  │ │ Smart!Scan  │ │   Sidebar-Navigation    ││
│  │ toast.py    │ │ VU-Verwalt. │ │ PDF-Preview │ │                         ││
│  └──────┬──────┘ └──────┬──────┘ └──────┬──────┘ └───────────┬─────────────┘│
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
│  └──────┬───────┘ └──────┬───────┘ └──────┬───────┘ └────────┬───────────┘  │
└─────────┼────────────────┼────────────────┼──────────────────┼──────────────┘
          │                │                │                  │
          ▼                ▼                ▼                  ▼
┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐ ┌──────────────┐
│  Strato Webspace │ │  Versicherer     │ │  OpenRouter KI   │ │  Lokales FS  │
│  PHP REST API    │ │  BiPRO Services  │ │  GPT-4o/4o-mini  │ │  GDV-Dateien │
│  MySQL + Files   │ │  (Degenia, VEMA) │ │  Klassifikation  │ │  Temp-Cache  │
│  ~20 Endpunkte   │ │                  │ │                  │ │              │
└──────────────────┘ └──────────────────┘ └──────────────────┘ └──────────────┘
```

---

## Komponenten

### 1. UI Layer (`src/ui/`)

#### main_hub.py (~1145 Zeilen)
Zentrales Navigationselement:
- Sidebar mit Bereichen (BiPRO, Archiv, GDV-Editor, Admin)
- Benutzeranzeige und Logout
- Routing zwischen Views
- **Globales Drag & Drop**: Dateien/Ordner/Outlook-Mails per Drag & Drop hochladen
- **DropUploadWorker**: QThread fuer nicht-blockierenden Upload
- **Admin-Modus**: Haupt-Sidebar ausblenden, Admin-Sidebar einblenden
- **Permission Guards**: Buttons basierend auf Nutzerrechten aktivieren/deaktivieren
- **Periodischer UpdateCheckWorker** (30 Min Timer)
- **Schliess-Schutz**: `closeEvent()` prueft auf blockierende Operationen in ArchiveBoxesView vor dem Beenden

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

#### archive_boxes_view.py (~5380 Zeilen)
Dokumentenarchiv mit Box-System:
- **BoxSidebar**: Navigation mit Live-Zaehlern + Kontextmenue (Download, SmartScan)
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
- **Schliess-Schutz**: `get_blocking_operations()` verhindert App-Schliessung bei laufenden kritischen Workern

#### admin_view.py (~4000 Zeilen) - Redesign v1.0.9
Administration mit vertikaler Sidebar:
- **AdminNavButton**: Custom-Styling, monochrome Icons, orangene Trennlinien
- **QStackedWidget**: 10 Panels in 3 Sektionen
  - VERWALTUNG: Nutzerverwaltung, Sessions, Passwoerter (0-2)
  - MONITORING: Aktivitaetslog, KI-Kosten, Releases (3-5)
  - E-MAIL: E-Mail-Konten, SmartScan-Settings, SmartScan-Historie, IMAP Inbox (6-9)
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

#### documents.py (~864 Zeilen)
Dokumenten-Operationen mit Box-Support:
- `list()`, `upload()`, `download()`, `delete()`
- `move_documents()`: Zwischen Boxen verschieben
- `archive_documents()` / `unarchive_documents()`: Bulk-Archivierung
- `set_documents_color()`: Bulk-Farbmarkierung
- `get_document_history()`: Aenderungshistorie pro Dokument
- `replace_document_file()`: Datei ersetzen (PDF-Bearbeitung)

#### Weitere API-Clients
| Datei | Zweck | Zeilen |
|-------|-------|--------|
| `auth.py` | Login, User-Model mit Permissions | ~150 |
| `vu_connections.py` | VU-Verbindungsverwaltung | ~350 |
| `admin.py` | Nutzerverwaltung (Admin) | ~200 |
| `smartscan.py` | SmartScan + EmailAccounts | ~350 |
| `openrouter.py` | KI-Klassifikation (zweistufig) | ~900 |
| `passwords.py` | Passwort-Verwaltung | ~80 |
| `releases.py` | Auto-Update | ~120 |
| `processing_history.py` | Audit-Trail | ~380 |
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
    ├── Strato Webspace (PHP API, MySQL, Files)
    ├── BiPRO Services (Degenia: 410 STS, 430 Transfer)
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
| **System** | GET /updates/check | releases.php | Update-Check (Public) |
| | POST /incoming-scans | incoming_scans.php | Scan-Upload (API-Key) |
| | GET /ai/key | ai.php | OpenRouter API-Key |
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
- **Grosse Dateien**: bipro_view.py (~4950), archive_boxes_view.py (~5380), admin_view.py (~4000) → Aufteilen geplant

## Unterstützte VUs

| VU | Status | Anmerkungen |
|----|--------|-------------|
| Degenia | ✅ | Standard BiPRO |
| VEMA | ✅ | VEMA-spezifisches Format |
| Weitere | 🔜 | Je nach VU anzupassen |
