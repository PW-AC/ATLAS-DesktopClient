# Architektur - BiPRO-GDV Tool v0.9.3

**Stand:** 05. Februar 2026

## Neue Features in v0.9.3 (KI-Klassifikation & Kosten-Tracking)

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

## Übersicht

Das BiPRO-GDV Tool ist eine Desktop-Anwendung mit Server-Backend. Es folgt einer mehrschichtigen Architektur:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Desktop-App (PySide6/Qt)                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                           UI Layer                                          │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────────────────┐│
│  │ main_hub.py │ │bipro_view.py│ │archive_view │ │    main_window.py       ││
│  │ Navigation  │ │ BiPRO-Abruf │ │ Dok-Archiv  │ │     GDV-Editor          ││
│  │             │ │ VU-Verwalt. │ │ PDF-Preview │ │    partner_view.py      ││
│  └──────┬──────┘ └──────┬──────┘ └──────┬──────┘ └───────────┬─────────────┘│
└─────────┼───────────────┼───────────────┼───────────────────┼──────────────┘
          │               │               │                   │
          ▼               ▼               ▼                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Service Layer                                       │
│  ┌─────────────────────┐ ┌─────────────────────┐ ┌────────────────────────┐ │
│  │   API Client        │ │   BiPRO Client      │ │    Parser Layer        │ │
│  │   (src/api/)        │ │   (src/bipro/)      │ │    (src/parser/)       │ │
│  │   - client.py       │ │   - transfer_svc.py │ │    - gdv_parser.py     │ │
│  │   - documents.py    │ │   - categories.py   │ │                        │ │
│  │   - vu_connections  │ │                     │ │    (src/layouts/)      │ │
│  │   - auth.py         │ │                     │ │    - gdv_layouts.py    │ │
│  └──────────┬──────────┘ └──────────┬──────────┘ └───────────┬────────────┘ │
└─────────────┼───────────────────────┼───────────────────────┼──────────────┘
              │                       │                       │
              ▼                       ▼                       ▼
┌─────────────────────────┐ ┌─────────────────────┐ ┌─────────────────────────┐
│   Strato Webspace       │ │   Versicherer       │ │   Lokales Dateisystem   │
│   PHP REST API          │ │   BiPRO Services    │ │   GDV-Dateien           │
│   MySQL Datenbank       │ │   (z.B. Degenia)    │ │   *.gdv, *.txt, etc.    │
│   Dokumente-Storage     │ │                     │ │                         │
└─────────────────────────┘ └─────────────────────┘ └─────────────────────────┘
```

---

## Komponenten

### 1. UI Layer (`src/ui/`)

#### main_hub.py
Zentrales Navigationselement:
- Sidebar mit Bereichen (BiPRO, Archiv, GDV-Editor)
- Benutzeranzeige und Logout
- Routing zwischen Views

#### bipro_view.py (~2466 Zeilen)
BiPRO-Datenabruf UI:
- **VU-Verbindungsliste**: Alle konfigurierten Versicherer (Degenia, VEMA, ...)
- **Lieferungstabelle**: Verfügbare Lieferungen mit Kategorien
- **Download-Worker**: Hintergrund-Download (QThread)
- **Log-Bereich**: Status und Fehler
- **VU-Dialog**: Verbindung erstellen/bearbeiten mit VU-spezifischen Feldern

**Signalfluss**:
```
VU auswählen → STS-Token holen → listShipments → Tabelle füllen
Download klicken → getShipment → MTOM parsen → Archiv-Upload
```

**VU-spezifisches Verhalten**:
- Degenia: Standard BiPRO, BestaetigeLieferungen=true
- VEMA: VEMA-Format, Consumer-ID erforderlich

#### archive_boxes_view.py (~1400 Zeilen) - NEU v0.8.0
Dokumentenarchiv mit Box-System:
- **BoxSidebar**: Navigation mit Live-Zaehlern
- **7 Boxen**: GDV, Courtage, Sach, Leben, Kranken, Sonstige, Roh
- **MultiUploadWorker/MultiDownloadWorker**: Parallele Operationen
- **CreditsWorker**: OpenRouter-Guthaben im Header
- **Thread-Cleanup**: closeEvent wartet auf Worker
- **PDFViewerDialog**: Integrierte PDF-Vorschau (QPdfView)

**Neue Features v0.8.0**:
- Parallele Verarbeitung (ThreadPoolExecutor)
- Robuster Download mit Retry
- OpenRouter Credits-Anzeige
- Multi-Upload

#### main_window.py (~914 Zeilen)
GDV-Editor Hauptfenster:
- **GDVMainWindow**: Menüs, Toolbar, Statusbar
- **RecordTableWidget**: Tabelle aller Records mit Filterung
- **ExpertDetailWidget**: Alle Felder editierbar

#### partner_view.py (~1165 Zeilen)
Partner-Übersicht:
- **extract_partners_from_file()**: Extrahiert Arbeitgeber/Personen
- **PartnerView**: Tabs für "Arbeitgeber" und "Personen"
- **EmployerDetailWidget**: Details mit Verträgen
- **PersonDetailWidget**: Details mit Arbeitgeber-Zuordnung

---

### 2. API Client (`src/api/`)

#### client.py
Base-Client für Server-Kommunikation:
- JWT-Authentifizierung
- Auto-Token-Refresh
- Multipart-Upload für Dateien

```python
class APIClient:
    def __init__(self, base_url: str)
    def login(username, password) -> bool
    def request(method, endpoint, data) -> Response
    def upload_file(endpoint, file_path) -> Response
    def download_file(endpoint, target_path) -> str
```

#### documents.py
Dokumenten-Operationen:
- `list()`: Alle Dokumente abrufen
- `upload(file_path, source_type)`: Dokument hochladen
- `download(doc_id, target_dir)`: Dokument herunterladen
- `delete(doc_id)`: Dokument löschen

#### vu_connections.py
VU-Verbindungsverwaltung:
- `list()`: Alle Verbindungen
- `create(name, vu_id, bipro_type)`: Neue Verbindung
- `get_credentials(connection_id)`: Zugangsdaten abrufen
- `delete(connection_id)`: Verbindung löschen

---

### 3. BiPRO Client (`src/bipro/`)

#### transfer_service.py (~1220 Zeilen)
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

| Endpoint | Datei | Beschreibung |
|----------|-------|--------------|
| POST /auth/login | auth.php | JWT-Login |
| POST /auth/logout | auth.php | Logout |
| GET /documents | documents.php | Liste Dokumente |
| POST /documents | documents.php | Upload (mit Atomic Write, Deduplizierung) |
| PUT /documents/{id} | documents.php | Update (inkl. Klassifikations-Audit) |
| GET /documents/{id}/download | documents.php | Download |
| DELETE /documents/{id} | documents.php | Löschen |
| GET /vu-connections | credentials.php | VU-Liste |
| POST /vu-connections | credentials.php | VU erstellen |
| GET /vu-connections/{id}/credentials | credentials.php | Credentials |
| **Neue Endpoints (v0.9.0)** | | |
| GET /xml_index/list | xml_index.php | XML-Index auflisten |
| GET /xml_index/{id} | xml_index.php | XML-Index-Eintrag abrufen |
| POST /xml_index/create | xml_index.php | XML-Index-Eintrag erstellen |
| DELETE /xml_index/{id} | xml_index.php | XML-Index-Eintrag löschen |
| GET /processing_history/list | processing_history.php | History auflisten |
| GET /processing_history/{doc_id} | processing_history.php | Dokument-History abrufen |
| POST /processing_history/create | processing_history.php | History-Eintrag erstellen |
| GET /processing_history/stats | processing_history.php | Statistiken |
| GET /processing_history/errors | processing_history.php | Letzte Fehler |

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

## Bekannte Einschränkungen

- **Single-User**: Keine gleichzeitige Bearbeitung
- **Kein Offline-Mode**: Server-Verbindung erforderlich
- **Hardcodierte UI-Texte**: Keine i18n-Unterstützung
- **Speicherverbrauch**: Alle Records/Dokumente im Speicher
- **VU-spezifisch**: BiPRO-Flow variiert je VU (Degenia, VEMA haben eigene Logik)

## Unterstützte VUs

| VU | Status | Anmerkungen |
|----|--------|-------------|
| Degenia | ✅ | Standard BiPRO |
| VEMA | ✅ | VEMA-spezifisches Format |
| Weitere | 🔜 | Je nach VU anzupassen |
