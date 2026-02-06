# Architekturabweichungen

## Übersicht

| ID | Planvorgabe | Tatsächliche Umsetzung | Bewertung |
|----|-------------|------------------------|-----------|
| AA01 | Tabelle `document_processing_log` | Tabelle `processing_history` | Akzeptabel |
| AA02 | XML-Indexierung automatisch bei Download | XML-Index API vorhanden, aber manuell | Problematisch |

---

## Detailbeschreibungen

### AA01: Tabellenname processing_history statt document_processing_log

**Bewertung:** Akzeptabel

#### Planvorgabe
> Neue Tabelle `document_processing_log`:
> - `id`, `document_id`, `timestamp`
> - `status_from`, `status_to`
> - `reason_code`
> - `worker_id` / `process_id`
> - `details` (JSON)

#### Tatsächliche Umsetzung

Tabelle heißt `processing_history` mit folgenden Feldern:
- `id`, `document_id`, `created_at` (statt timestamp)
- `previous_status`, `new_status` (statt status_from/to)
- `action` (statt reason_code, flexibler)
- `created_by` (statt worker_id, besser lesbar)
- `action_details` (JSON, wie geplant)
- **Zusätzlich:** `success`, `error_message`, `classification_source`, `classification_result`, `duration_ms`

#### Code-Referenz
- Datei: `BiPro-Webspace Spiegelung Live/api/processing_history.php`
- Migration: `012_add_processing_history.php`

#### Analyse

Die Abweichung ist eine **Verbesserung** gegenüber dem Plan:
- Mehr Felder für besseres Debugging
- Konsistentere Namenskonventionen
- Integration von Klassifikations-Metadaten

#### Auswirkungen
- **Positiv:** Umfassenderer Audit-Trail
- **Negativ:** Keine

#### Empfehlung
Abweichung akzeptieren - die Implementierung ist besser als der Plan.

---

### AA02: XML-Indexierung nicht automatisch bei Download

**Bewertung:** Problematisch

#### Planvorgabe
> Bei XML-Upload im Ingress-Gate:
> - Metadaten aus Dateinamen/Response extrahieren
> - In separate Struktur schreiben

#### Tatsächliche Umsetzung

Die XML-Index-API ist vollständig implementiert, aber:
- Wird **nicht automatisch** beim BiPRO-Download aufgerufen
- Muss manuell oder via separatem Prozess befüllt werden

#### Code-Referenz
- API: `src/api/xml_index.py`, `BiPro-Webspace Spiegelung Live/api/xml_index.php`
- **Fehlt in:** `src/ui/bipro_view.py:_save_shipment_documents()`

```python
# bipro_view.py:864 - hier SOLLTE stehen:
# xml_index_api.index_xml_file(raw_xml_path, ...)
return saved_docs, raw_xml_path  # XML wird nicht indexiert
```

#### Analyse

Die API-Infrastruktur ist komplett, nur die Integration in den Download-Flow fehlt. Dies ist ein Versäumnis bei der Integration, keine Architekturentscheidung.

#### Auswirkungen
- **Negativ:** XML-Rohdateien nicht durchsuchbar
- **Negativ:** Keine automatische Verknüpfung zu Dokumenten

#### Empfehlung
Integration in `_save_shipment_documents()` nachholen:
```python
if raw_xml_path:
    xml_index_api.index_xml_file(
        filepath=raw_xml_path,
        raw_path=relative_path,
        shipment_id=shipment_id,
        bipro_category=category,
        vu_name=vu_name
    )
```
