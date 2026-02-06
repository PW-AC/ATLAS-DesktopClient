# Plan-zu-Code Mapping

Dieses Dokument mappt jede Plananforderung auf die entsprechende Implementierung.

## Statistik

| Status | Anzahl | Prozent |
|--------|--------|---------|
| ✅ Vollständig | 26 | 96.3% |
| ⚠️ Teilweise | 1 | 3.7% |
| ❌ Falsch | 0 | 0% |
| 🚫 Fehlt | 0 | 0% |
| ❓ Unklar | 0 | 0% |

---

## Phase 1: PDF-Validierung mit Reason-Codes (KRITISCH)

| ID | Anforderung | Status | Code-Fundstelle | Bewertung |
|----|-------------|--------|-----------------|-----------|
| F01 | PDF encrypted erkennen | ✅ | `bipro_view.py:1056-1059` | `doc.is_encrypted` Prüfung vorhanden |
| F02 | PDF strukturell defekt erkennen | ✅ | `bipro_view.py:1073-1081` | Seiten-Ladung mit Fallback auf Reparatur |
| F03 | PDF unvollständig erkennen | ✅ | `bipro_view.py:1034-1041` | Content-Length vs Dateigröße Vergleich |
| F04 | PDF XFA erkennen | ✅ | `bipro_view.py:1061-1066, 1084-1088` | `doc.xfa` Prüfung mit Warnung |
| F05 | Reason-Codes definieren | ✅ | `processing_rules.py:26-50` | `PDFValidationStatus` Enum mit allen Codes |
| F06 | DB-Feld `validation_status` | ✅ | `documents.php:332-338, 548` | VARCHAR(50) NULLABLE, API-Update unterstützt |
| F07 | Problem → Sonstige-Box + Reason | ✅ | `bipro_view.py:848-862` | `validation_status` wird bei Upload übergeben |

### Detailanalyse F01: PDF encrypted erkennen

**Plan-Anforderung:**
> PyMuPDF `.is_encrypted` prüfen → `PDF_ENCRYPTED`

**Implementierung:**
- Datei: `src/ui/bipro_view.py`
- Funktion: `_validate_pdf`
- Zeilen: 1056-1059

**Code-Auszug:**
```python
# 4. Pruefe auf Verschluesselung
if doc.is_encrypted:
    doc.close()
    logger.warning(f"PDF ist verschluesselt: {filepath}")
    return (False, PDFValidationStatus.PDF_ENCRYPTED)
```

**Bewertung:** ✅ Vollständig

---

## Phase 2: GDV-Fallback-Benennung (MITTEL)

| ID | Anforderung | Status | Code-Fundstelle | Bewertung |
|----|-------------|--------|-----------------|-----------|
| F08 | Fallback-Konstanten definieren | ✅ | `processing_rules.py:80-82` | `GDV_FALLBACK_VU = "Xvu"`, `GDV_FALLBACK_DATE = "kDatum"` |
| F09 | Fallback bei GDV-Parsing-Fehler | ✅ | `document_processor.py:924-945` | Fallback-Werte werden bei Fehler verwendet |

### Detailanalyse F08: Fallback-Konstanten

**Plan-Anforderung:**
> Fallback-Konstanten: `FALLBACK_VU = "Xvu"`, `FALLBACK_DATE = "kDatum"`

**Implementierung:**
- Datei: `src/config/processing_rules.py`
- Zeilen: 80-82

**Code-Auszug:**
```python
# Fallback-Werte fuer GDV-Metadaten wenn Parsing fehlschlaegt
GDV_FALLBACK_VU = "Xvu"      # Unbekannter Versicherer
GDV_FALLBACK_DATE = "kDatum"  # Kein Datum gefunden
```

**Bewertung:** ✅ Vollständig

---

## Phase 3: Atomic File Operations (MITTEL)

| ID | Anforderung | Status | Code-Fundstelle | Bewertung |
|----|-------------|--------|-----------------|-----------|
| F10 | `safe_atomic_write()` Utility | ✅ | `atomic_ops.py:69-128` | Vollständige Implementierung |
| F11 | Staging → Verify → Atomic rename | ✅ | `atomic_ops.py:97-115`, `documents.php:288-403` | Pattern in Python und PHP implementiert |
| F12 | Fehler: temp-Datei löschen | ✅ | `atomic_ops.py:122-126`, `documents.php:446-452` | Cleanup bei Fehler |

### Detailanalyse F11: Atomic Write Pattern

**Plan-Anforderung:**
> 1. Schreibe in `.tmp`-Datei
> 2. Verifiziere Größe/Hash
> 3. Atomic rename via `os.replace()`

**Implementierung PHP (documents.php:288-403):**
```php
// SCHRITT 1: Datei als .tmp in Staging schreiben
$stagingPath = $stagingDir . '/.tmp_' . $uniqueFilename;

// SCHRITT 2: Hash/Size verifizieren
$actualSize = filesize($stagingPath);
$contentHash = hash_file('sha256', $stagingPath);

// SCHRITT 3-6: Transaction + Atomic move
Database::beginTransaction();
$docId = Database::insert(...);
if (!rename($stagingPath, $targetPath)) {
    throw new Exception("Atomic move fehlgeschlagen");
}
Database::commit();
```

**Bewertung:** ✅ Vollständig

---

## Phase 4: XML-Indexierung (MITTEL)

| ID | Anforderung | Status | Code-Fundstelle | Bewertung |
|----|-------------|--------|-----------------|-----------|
| F13 | Separate XML-Metadaten-Indexierung | ⚠️ | `xml_index.php`, `xml_index.py` | API vorhanden, aber nicht automatisch bei Download aufgerufen |
| F14 | Felder: shipment_id, bipro_category, raw_path, content_hash | ✅ | `xml_index.php:196-209` | Alle Felder in DB-Insert vorhanden |

### Detailanalyse F13: XML-Indexierung

**Plan-Anforderung:**
> Eigene Tabelle `xml_index` ODER separate Felder in `documents`

**Implementierung:**
- Tabelle: `xml_index` (eigene Tabelle)
- Python-Client: `src/api/xml_index.py`
- PHP-Backend: `BiPro-Webspace Spiegelung Live/api/xml_index.php`
- Migration: `009_add_xml_index_table.php`

**Bewertung:** ⚠️ Teilweise

**Abweichung:** Die XML-Indexierung ist als API vollständig implementiert, wird aber nicht automatisch beim BiPRO-Download aufgerufen. Die Funktion `index_xml_file()` existiert, muss aber manuell oder via separatem Prozess aufgerufen werden.

---

## Phase 5: Dokument-State-Machine (HOCH)

| ID | Anforderung | Status | Code-Fundstelle | Bewertung |
|----|-------------|--------|-----------------|-----------|
| F15 | Neue Stati: downloaded, validated, classified, renamed, archived | ✅ | `processing_rules.py:102-128` | `DocumentProcessingStatus` Enum |
| F16 | Statusübergänge atomar und geloggt | ✅ | `documents.php:656-730`, `document_processor.py:181-182, 448-458` | Transition-Validierung + History-Logging |

### Detailanalyse F15: State-Machine

**Plan-Anforderung:**
> Vollständige Zustandsmaschine: downloaded → validated → classified → renamed → archived

**Implementierung:**
- Datei: `src/config/processing_rules.py`
- Klasse: `DocumentProcessingStatus`
- Zeilen: 102-191

**Code-Auszug:**
```python
class DocumentProcessingStatus(Enum):
    # Neue granulare Status
    DOWNLOADED = "downloaded"      # Datei vom BiPRO heruntergeladen
    VALIDATED = "validated"        # PDF-Validierung durchgefuehrt
    CLASSIFIED = "classified"      # KI/Regel-Klassifikation abgeschlossen
    RENAMED = "renamed"            # Dateiname angepasst
    ARCHIVED = "archived"          # In Ziel-Box verschoben
    QUARANTINED = "quarantined"    # In Quarantaene
    ERROR = "error"                # Fehler aufgetreten

    # Legacy-Status (abwaertskompatibel)
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
```

**Bewertung:** ✅ Vollständig - inkl. Transition-Validierung via `is_valid_transition()`

---

## Phase 6: Idempotenz + Versionierung (MITTEL)

| ID | Anforderung | Status | Code-Fundstelle | Bewertung |
|----|-------------|--------|-----------------|-----------|
| F17 | content_hash (SHA256) bei Upload | ✅ | `documents.php:305`, `atomic_ops.py:107-108` | Hash-Berechnung vorhanden |
| F18 | Duplikat-Erkennung vor Speicherung | ✅ | `documents.php:347-371` | Hash-Vergleich mit existierenden Dokumenten |
| F19 | version INT DEFAULT 1 | ✅ | `documents.php:348, 376` | Version wird gespeichert und erhöht |
| F20 | Mehrfachlieferung: Version erhöhen | ✅ | `documents.php:364-370` | `$version = $existing['version'] + 1` |

### Detailanalyse F18: Duplikat-Erkennung

**Plan-Anforderung:**
> Duplikat-Erkennung vor Speicherung via content_hash

**Implementierung (documents.php:352-371):**
```php
if ($contentHash) {
    $existing = Database::queryOne(
        "SELECT id, version, original_filename 
         FROM documents 
         WHERE content_hash = ? 
         ORDER BY version DESC 
         LIMIT 1",
        [$contentHash]
    );
    
    if ($existing) {
        $isDuplicate = true;
        $previousVersionId = $existing['id'];
        $version = $existing['version'] + 1;
    }
}
```

**Bewertung:** ✅ Vollständig

---

## Phase 7: KI/GDV Audit-Metadaten (MITTEL)

| ID | Anforderung | Status | Code-Fundstelle | Bewertung |
|----|-------------|--------|-----------------|-----------|
| F21 | classification_source speichern | ✅ | `document_processor.py:190, 424-425`, `documents.php:549` | Feld vorhanden und befüllt |
| F22 | classification_confidence speichern | ✅ | `document_processor.py:191, 426-427`, `documents.php:550` | Feld vorhanden und befüllt |
| F23 | classification_reason speichern | ✅ | `document_processor.py:192, 428-430`, `documents.php:551` | Max 500 Zeichen, trunciert |
| F24 | classification_timestamp speichern | ✅ | `document_processor.py:432`, `documents.php:552` | Timestamp wird gesetzt |

### Detailanalyse F21-F24: Audit-Metadaten

**Plan-Anforderung:**
> Speicherung von: classification_source, classification_confidence, classification_reason, classification_timestamp

**Implementierung (document_processor.py:189-192, 424-432):**
```python
# Audit-Metadaten fuer Klassifikation
classification_source = None      # ki_gpt4o, rule_bipro, fallback, etc.
classification_confidence = None  # high, medium, low
classification_reason = None      # Begruendung

# Beim Update speichern:
if classification_source:
    update_kwargs['classification_source'] = classification_source
if classification_confidence:
    update_kwargs['classification_confidence'] = classification_confidence
if classification_reason:
    update_kwargs['classification_reason'] = classification_reason[:500]
update_kwargs['classification_timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
```

**Bewertung:** ✅ Vollständig

---

## Phase 8: Processing-History Tabelle (MITTEL)

| ID | Anforderung | Status | Code-Fundstelle | Bewertung |
|----|-------------|--------|-----------------|-----------|
| F25 | Neue Tabelle processing_history | ✅ | `processing_history.php`, `processing_history.py` | Vollständige API |
| F26 | Felder: document_id, status_from/to, action, details, duration_ms | ✅ | `processing_history.php:230-246` | Alle Felder im INSERT |

### Detailanalyse F25: Processing-History

**Plan-Anforderung:**
> Neue Tabelle `document_processing_log` mit Feldern für vollständigen Audit-Trail

**Implementierung:**
- Tabelle: `processing_history`
- Python-Client: `src/api/processing_history.py`
- PHP-Backend: `BiPro-Webspace Spiegelung Live/api/processing_history.php`
- Migration: `012_add_processing_history.php`

**Felder (processing_history.php:230-246):**
```php
INSERT INTO processing_history 
(document_id, previous_status, new_status, action, action_details, 
 success, error_message, classification_source, classification_result, 
 duration_ms, created_by)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
```

**Bewertung:** ✅ Vollständig

---

## Architektonische Anforderungen

| ID | Anforderung | Status | Code-Fundstelle | Bewertung |
|----|-------------|--------|-----------------|-----------|
| A01 | Trennung Dokument-Index vs Rohdaten-Index | ✅ | `xml_index.php/py` vs `documents.php/py` | Eigene Tabelle `xml_index` |
| A02 | Abwärtskompatibilität | ✅ | `processing_rules.py:124-127` | Legacy-Status bleiben gültig |
| A03 | Migrationsfähigkeit | ✅ | `setup/005-013_*.php` | Einzelne Migrations-Scripts |
| A04 | Atomic Write Pattern | ✅ | `documents.php:237-244` | Dokumentiert und implementiert |

---

## Sicherheitsanforderungen

| ID | Anforderung | Status | Code-Fundstelle | Bewertung |
|----|-------------|--------|-----------------|-----------|
| S01 | FS/DB Transaktionssicherheit | ✅ | `documents.php:344-456` | Transaction mit Rollback bei Fehler |
| S02 | Rollbackfähigkeit | ✅ | Alle Migrations-Scripts | Neue Spalten sind NULLABLE |
| S03 | Keine Spalten löschen/umbenennen | ✅ | Keine DELETE/RENAME in Migrations | Nur ADD COLUMN |
| S04 | Keine nicht-nullable ohne Default | ✅ | Alle neuen Spalten | NULLABLE oder mit DEFAULT |
