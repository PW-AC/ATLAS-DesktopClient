# Gefundene Schwachstellen

## Übersicht

| ID | Schwachstelle | Schweregrad | Kategorie | Fundstelle |
|----|---------------|-------------|-----------|------------|
| SW01 | XML-Indexierung nicht automatisch bei Download | Niedrig | Logiklücke | `bipro_view.py` |

---

## Detailbeschreibungen

### SW01: XML-Indexierung nicht automatisch bei Download

**Schweregrad:** Niedrig
**Kategorie:** Logiklücke / Unvollständige Integration
**Fundstelle:** `src/ui/bipro_view.py` - `_save_shipment_documents()`

#### Technische Beschreibung

Der Plan fordert in Phase 4 eine XML-Metadaten-Indexierung für Suche. Die API ist vollständig implementiert:
- Python-Client: `src/api/xml_index.py` mit `XmlIndexAPI.index_xml_file()`
- PHP-Backend: `BiPro-Webspace Spiegelung Live/api/xml_index.php`
- DB-Tabelle: `xml_index`

Allerdings wird die Indexierung **nicht automatisch** beim BiPRO-Download aufgerufen. In `bipro_view.py` werden XML-Rohdateien zwar erkannt und ins Roh-Archiv geroutet, aber die `XmlIndexAPI.create()` Methode wird nicht aufgerufen.

#### Betroffener Code

```python
# bipro_view.py:864 - hier fehlt der XML-Index-Aufruf
return saved_docs, raw_xml_path
```

Die Funktion `_save_shipment_documents()` speichert die XML-Rohdatei, ruft aber nicht `XmlIndexAPI.index_xml_file()` auf.

#### Risikoauswirkungen

- **Auswirkung 1:** XML-Rohdateien sind nicht über die Such-API auffindbar
- **Auswirkung 2:** Keine automatische Verknüpfung zwischen Dokumenten und ihrer Quell-XML
- **Auswirkung 3:** Das Feld `source_xml_index_id` in `documents` bleibt leer

#### Reproduzierbarkeit

- Szenario 1: BiPRO-Download durchführen mit XML-Rohdatei
- Szenario 2: Prüfen ob Eintrag in `xml_index` Tabelle existiert → existiert NICHT

#### Zusammenhängende Befunde

- Verknüpft mit: [EMP01] in Empfehlungen
