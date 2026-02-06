# 03 - Domain und Begriffe

**Version:** 0.9.3  
**Analyse-Datum:** 2026-02-05

---

## Domänen-Überblick

Das Projekt operiert in zwei Domänen:

1. **GDV (Gesamtverband der Deutschen Versicherungswirtschaft)** - Branchenstandard für Datenaustausch
2. **BiPRO (Brancheninstitut für Prozessoptimierung)** - Schnittstellen-Standard für Versicherer

---

## GDV-Domäne

### GDV-Format

Das GDV-Format ist ein **Fixed-Width-Format** für den Datenaustausch zwischen Versicherungsunternehmen und Vermittlern.

| Merkmal | Wert |
|---------|------|
| Zeilenbreite | 256 Bytes |
| Encoding | CP1252 (Windows-1252) |
| Satzart | Position 1-4 (4 Zeichen) |
| Teildatensatz | Position 256 (1 Zeichen) |

### Satzarten (Implementiert)

| Satzart | Name | Teildatensätze | Beschreibung |
|---------|------|----------------|--------------|
| 0001 | Vorsatz | 1 | Datei-Header (VU, Datum, Release) |
| 0100 | Partnerdaten | 1-5 | Kunden, Adressen, Bankdaten |
| 0200 | Vertragsteil | 1 | Grunddaten (Laufzeit, Beitrag, Sparte) |
| 0210 | Spartenspezifisch | 1+ | Wagnisse, Risiken |
| 0220 | Deckungsteil | 1, 6+ | Versicherte Personen, Leistungen |
| 0230 | Fondsanlage | 1+ | Fondsdaten (ISIN, Anteile) |
| 9999 | Nachsatz | 1 | Prüfsummen |

**Quelle:** `src/layouts/gdv_layouts.py`

### Teildatensätze (Wichtig!)

Manche Satzarten haben mehrere Teildatensätze:

| Satzart | TD | Inhalt |
|---------|-----|--------|
| 0100 | TD1 | Adressdaten |
| 0100 | TD2 | Kundennummern, Referenznummern |
| 0100 | TD3 | Kommunikationsdaten |
| 0100 | TD4 | Bankverbindung (BIC, IBAN) |
| 0100 | TD5 | Zusatzdaten |
| 0220 | TD1 | Versicherte Person |
| 0220 | TD6 | Bezugsberechtigte Person |

### Sparten

| Code | Bezeichnung | Kategorie |
|------|-------------|-----------|
| 010 | Leben | Leben |
| 020 | Kranken | Kranken |
| 030 | Unfall | Sach |
| 040 | Haftpflicht | Sach |
| 050 | Kraftfahrt | Sach |
| 060 | Rechtsschutz | Sach |
| 070 | Hausrat | Sach |
| 080 | Wohngebäude | Sach |
| 090 | Transport/Reise | Sach |

**Quelle:** `docs/DOMAIN.md`

---

## Domain-Modell (GDV)

```
┌─────────────────────────────────────────────────────────────────────┐
│                           GDVData                                    │
│  (Container für alle geladenen Daten)                               │
├─────────────────────────────────────────────────────────────────────┤
│  file_meta: FileMeta         (aus 0001)                             │
│  customers: List[Customer]   (aus 0100)                             │
│  contracts: List[Contract]   (aus 0200)                             │
└───────────────────────────────────────┬─────────────────────────────┘
                                        │
                    ┌───────────────────┼───────────────────┐
                    │                   │                   │
                    ▼                   ▼                   ▼
            ┌───────────────┐  ┌───────────────┐  ┌───────────────┐
            │   Customer    │  │   Contract    │  │   FileMeta    │
            │   (0100)      │  │   (0200)      │  │   (0001)      │
            └───────┬───────┘  └───────┬───────┘  └───────────────┘
                    │                  │
                    │          ┌───────┴───────┐
                    │          │               │
                    │          ▼               ▼
                    │  ┌───────────────┐ ┌───────────────┐
                    │  │     Risk      │ │   Coverage    │
                    │  │    (0210)     │ │    (0220)     │
                    │  └───────────────┘ └───────────────┘
                    │
                    ▼
            [Verknüpfung via VSNR]
```

**Quelle:** `src/domain/models.py`

---

## BiPRO-Domäne

### BiPRO-Normen

| Norm | Name | Beschreibung |
|------|------|--------------|
| 410 | STS (Security Token Service) | Authentifizierung, Token-Ausstellung |
| 420 | TAA (Tarif-Auskunft, Angebot, Antrag) | Nicht aktiv bei Degenia |
| 430 | Transfer-Service | Datentransfer |
| 430.1 | Transfer allgemein | Basis-Operationen |
| 430.2 | Lieferungen | listShipments, getShipment |
| 430.4 | GDV-Daten | (Laut Degenia unterstützt, keine Daten) |
| 430.5 | Dokumente | PDFs, Policen |

### BiPRO-Operationen (Implementiert)

| Operation | Norm | Beschreibung |
|-----------|------|--------------|
| `RequestSecurityToken` | 410 | STS-Token holen (UsernameToken → SecurityContextToken) |
| `listShipments` | 430 | Bereitstehende Lieferungen auflisten |
| `getShipment` | 430 | Lieferung abrufen (MTOM/XOP) |
| `acknowledgeShipment` | 430 | Empfang quittieren |

**Quelle:** `src/bipro/transfer_service.py`

### Lieferungs-Kategorien

| Code | Bezeichnung |
|------|-------------|
| 100002000 | Vertragsänderung |
| 100007000 | Geschäftsvorfall |
| 110011000 | Vertragsdokumente |

**Quelle:** `src/bipro/categories.py`

---

## Box-System (Dokumentenarchiv)

### Box-Typen

| Box | Farbe | Beschreibung | Klassifikation |
|-----|-------|--------------|----------------|
| Eingang | Amber | Neue Dokumente | - |
| Verarbeitung | Orange | In Verarbeitung | - |
| GDV | Grün | GDV-Dateien | Dateiendung |
| Courtage | Indigo | Provisionsabrechnungen | KI |
| Sach | Blau | Sachversicherungen | KI |
| Leben | Violett | Lebensversicherungen | KI |
| Kranken | Cyan | Krankenversicherungen | KI |
| Sonstige | Grau | Nicht zugeordnet | Fallback |
| Roh | Steingrau | XML-Rohdateien | Dateiname |

**Quelle:** `src/api/documents.py`

### Klassifikations-Workflow

1. **Eingang** - Dokument wird hochgeladen (manuell oder BiPRO)
2. **Verarbeitung** - Automatische Verarbeitung läuft
3. **Klassifikation:**
   - XML mit "Roh" im Namen → **Roh Archiv**
   - `.gdv`, `.txt` ohne Inhalt → **GDV Box**
   - PDF → **KI-Klassifikation** (OpenRouter)
4. **Ziel-Box** - Basierend auf KI-Entscheidung

**Quelle:** `src/services/document_processor.py`

---

## KI-Klassifikation

### Klassifikations-Logik

Die KI analysiert den **HAUPTZWECK** des Dokuments:

| Hauptzweck | Ziel-Box |
|------------|----------|
| Provisionsabrechnung, Courtage-Abrechnung | **courtage** |
| Versicherungsschein Haftpflicht, Hausrat, KFZ... | **sach** |
| Versicherungsschein Leben, Rente, BU... | **leben** |
| Versicherungsschein PKV, Krankenzusatz... | **kranken** |
| Unklar | **sonstige** |

**Wichtig:** Keywords in Fußnoten/AGB werden ignoriert. Nur der Hauptinhalt zählt.

### Erweiterte Keywords (v0.9.3)

| Kategorie | Neue Keywords |
|-----------|---------------|
| **Sach** | Privathaftpflicht, PHV, Tierhalterhaftpflicht, Hundehaftpflicht, Bauherrenhaftpflicht, Jagdhaftpflicht, Gewaesserschadenhaftpflicht |
| **Leben** | Pensionskasse, Rentenanstalt |

### Benennungs-Schema

| Box | Schema | Beispiel |
|-----|--------|----------|
| Courtage | `VU_Name_Datum.pdf` (v0.9.3) | `Degenia_2025-01-15.pdf` |
| Sach | `Sach.pdf` (Token-Optimierung) | `Sach.pdf` |
| Andere | `Versicherer_Dokumenttyp_Datum.pdf` | `Allianz_Privathaftpflicht_2025-01-15.pdf` |

**Quelle:** `src/api/openrouter.py`

### Kosten-Tracking (v0.9.3)

| Metrik | Beschreibung |
|--------|--------------|
| `credits_before` | OpenRouter-Guthaben vor Verarbeitung |
| `credits_after` | OpenRouter-Guthaben nach Verarbeitung |
| `total_cost_usd` | Gesamtkosten in USD |
| `cost_per_document_usd` | Durchschnittskosten pro Dokument |

**Quelle:** `src/services/document_processor.py` (BatchProcessingResult)

---

## Glossar

| Begriff | Erklärung | Kontext |
|---------|-----------|---------|
| **VU** | Versicherungsunternehmen | Versicherer wie Allianz, Degenia |
| **VSNR** | Versicherungsscheinnummer | Eindeutige Vertragsnummer |
| **Sparte** | Versicherungszweig | Leben, Kranken, Sach |
| **Satzart** | Datensatztyp im GDV-Format | 0001, 0100, 0200, etc. |
| **TD** | Teildatensatz | Unterstruktur einer Satzart |
| **STS** | Security Token Service | BiPRO-Authentifizierung |
| **MTOM** | Message Transmission Optimization | Binärdaten in SOAP |
| **XOP** | XML-binary Optimized Packaging | Referenz auf Binärteil |
| **Courtage** | Provision/Vergütung | Vermittlergebühr |
| **Box** | Kategorie im Dokumentenarchiv | Container für Dokumente |
