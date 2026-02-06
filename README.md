# BiPRO-GDV Tool v0.9.3

Ein Desktop-Tool für Versicherungsvermittler mit:
- **BiPRO-Datenabruf** - Automatisierter Abruf von Lieferungen von Versicherern
- **Dokumentenarchiv mit Box-System** - Zentrales Archiv mit KI-Klassifikation
- **GDV-Editor** - Erstellung, Ansicht und Bearbeitung von GDV-Datensätzen

![Python 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)
![PySide6](https://img.shields.io/badge/GUI-PySide6-green.svg)
![Status](https://img.shields.io/badge/BiPRO-Funktioniert-brightgreen.svg)
![KI](https://img.shields.io/badge/KI-OpenRouter-purple.svg)
![License](https://img.shields.io/badge/License-Proprietary-red.svg)

---

## Features

### BiPRO Datenabruf
- **Automatischer Abruf** von Lieferungen (Dokumente, Vertragsänderungen)
- **VU-Verbindungen verwalten** (Degenia, VEMA)
- **Kategorien-Anzeige** (Vertragsdokumente, Geschäftsvorfälle, etc.)
- **Download einzeln oder alle** mit automatischem Archiv-Upload
- **MTOM/XOP-Support** für Binärdaten (PDFs)
- **Parallele Downloads** (5 Worker, ~5x schneller) **NEU v0.9.1**
- **Adaptive Rate Limiting** (dynamische Anpassung bei 429/503) **NEU v0.9.1**
- **PDF-Validierung** mit automatischer Reparatur **NEU v0.9.1**

### Dokumentenarchiv mit Box-System (v0.8.0)
- **7 Boxen**: GDV, Courtage, Sach, Leben, Kranken, Sonstige, Roh
- **KI-Klassifikation**: Automatische Zuordnung via OpenRouter (GPT-4o)
- **Parallele Verarbeitung**: 4 Dokumente gleichzeitig (ThreadPoolExecutor)
- **KI-Benennung**: Automatische Umbenennung nach Schema `Versicherer_Typ_Datum.pdf`
- **Multi-Upload**: Mehrere Dateien gleichzeitig hochladen
- **PDF-Vorschau** direkt in der App (QPdfView)
- **OpenRouter Credits**: Guthaben-Anzeige im Header
- **Robuster Download**: Retry-Logik mit Backoff

### GDV-Editor
- **GDV-Dateien öffnen**: `.gdv`, `.txt`, `.dat`, `.vwb`
- **Drei Ansichtsmodi**:
  - 👥 **Partner-Ansicht**: Alle Arbeitgeber und Personen mit ihren Verträgen
  - 📋 **Benutzer-Ansicht**: Nur wichtige Felder, benutzerfreundlich
  - ⚙️ **Experten-Ansicht**: Alle Felder, volle Kontrolle
- **Daten bearbeiten und speichern**
- **Neue Sätze erstellen**: 0001, 0100, 0200, 0210, 0220, 0230, 9999

---

## Quickstart

### Voraussetzungen

- Python 3.10 oder höher
- Windows 10/11 (getestet)
- Internetzugang (für Server-API und BiPRO)

### Installation

```bash
# Repository klonen oder Ordner öffnen
cd "X:\projekte\5510_GDV Tool V1"

# Abhängigkeiten installieren
pip install -r requirements.txt
```

### Starten

```bash
python run.py
```

### Login

- **Benutzer**: `admin`
- **Passwort**: (vom Administrator)

---

## Verwendung

### BiPRO Datenabruf

1. **Navigation** → **BiPRO Datenabruf**
2. VU-Verbindung in der Liste auswählen (Lieferungen laden automatisch)
3. Lieferungen werden mit Kategorie und Datum angezeigt
4. **"Alle herunterladen"** oder einzeln auswählen und **"Ausgewählte herunterladen"**
5. Dokumente werden automatisch ins Archiv hochgeladen

### Dokumentenarchiv

1. **Navigation** → **Dokumentenarchiv**
2. Dokumente werden vom Server geladen
3. **PDF-Vorschau**: Doppelklick auf PDF oder "👁️ Vorschau" Button
4. **Download**: Rechtsklick → "Herunterladen" oder Toolbar-Button
5. **Upload**: "📤 Hochladen" Button

### GDV-Editor

1. **Navigation** → **GDV Editor**
2. **Menü** → **Datei** → **GDV-Datei öffnen** (Strg+O)
3. Sätze werden in der Tabelle angezeigt
4. Felder im rechten Panel bearbeiten
5. **Menü** → **Datei** → **Speichern** (Strg+S)

---

## Projektstruktur

```
5510_GDV Tool V1/
├── run.py                     # Entry Point
├── requirements.txt           # Python-Abhängigkeiten
├── AGENTS.md                  # Agent-Anweisungen (aktuell halten!)
├── BIPRO_STATUS.md            # BiPRO-Integrationsstatus
├── README.md                  # Diese Datei
│
├── src/                       # Quellcode
│   ├── main.py               # Qt-Anwendung
│   │
│   ├── api/                  # Server-API Clients
│   │   ├── client.py         # Base-Client mit JWT-Auth
│   │   ├── documents.py      # Dokumenten-Operationen
│   │   └── vu_connections.py # VU-Verbindungen
│   │
│   ├── bipro/                # BiPRO SOAP Client
│   │   ├── transfer_service.py  # BiPRO 410 + 430
│   │   └── categories.py     # Kategorie-Mapping
│   │
│   ├── domain/               # Datenmodelle
│   │   ├── models.py         # Contract, Customer, Risk, Coverage
│   │   └── mapper.py         # ParsedRecord → Domain-Objekt
│   │
│   ├── layouts/
│   │   └── gdv_layouts.py    # GDV-Satzart-Definitionen
│   │
│   ├── parser/
│   │   └── gdv_parser.py     # Fixed-Width Parser
│   │
│   └── ui/                   # Benutzeroberfläche
│       ├── main_hub.py       # Navigation
│       ├── bipro_view.py     # BiPRO Datenabruf
│       ├── archive_view.py   # Dokumentenarchiv
│       ├── main_window.py    # GDV-Editor
│       ├── user_detail_view.py
│       └── partner_view.py
│
├── BiPro-Webspace Spiegelung Live/  # Server-API (LIVE synchronisiert!)
│   └── api/                  # PHP REST API
│
├── testdata/                  # Testdaten
│   ├── sample.gdv
│   ├── create_testdata.py
│   └── test_roundtrip.py
│
└── docs/                      # Dokumentation
    ├── ARCHITECTURE.md
    ├── DEVELOPMENT.md
    └── DOMAIN.md
```

---

## BiPRO-Integration

### Unterstützte Versicherer

| Versicherer | Status | Normen |
|-------------|--------|--------|
| Degenia | ✅ Funktioniert | 410 STS, 430 Transfer |
| VEMA | ✅ Funktioniert | 410 STS, 430 Transfer |
| Weitere | 🔜 Geplant | - |

### Technischer Ablauf

1. **STS-Authentifizierung** (BiPRO 410): Holt Security-Token
2. **listShipments** (BiPRO 430): Listet verfügbare Lieferungen
3. **getShipment** (BiPRO 430): Lädt Lieferung herunter (MTOM/XOP)
4. **Archivierung**: Automatischer Upload ins Dokumentenarchiv

Siehe `BIPRO_STATUS.md` für Details.

---

## GDV-Format

Das GDV-Format ist ein Branchenstandard für den Datenaustausch zwischen Versicherungsunternehmen und Vermittlern.

### Merkmale

- **Fixed-Width**: 256 Bytes pro Zeile
- **Satzart**: Erste 4 Zeichen identifizieren den Satztyp
- **Encoding**: CP1252 (Windows-1252) für deutsche Umlaute

### Unterstützte Satzarten

| Satzart | Name | Beschreibung |
|---------|------|--------------|
| 0001 | Vorsatz | Datei-Header |
| 0100 | Partnerdaten | Adressen, Nummern, Bankdaten |
| 0200 | Vertragsteil | Grunddaten des Vertrags |
| 0210 | Spartenspezifisch | Wagnisse, Risiken |
| 0220 | Deckungsteil | Versicherte Personen, Leistungen |
| 0230 | Fondsanlage | ISIN, Fondsanteile |
| 9999 | Nachsatz | Prüfsummen |

---

## Konfiguration

### Server-API

Die Desktop-App verbindet sich mit:
- **API**: `https://acencia.info/api/`
- **Authentifizierung**: JWT-Token

### Umgebungsvariablen

Keine erforderlich (Konfiguration in App).

---

## Entwicklung

Siehe [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) für Setup und Workflow.

Siehe [AGENTS.md](AGENTS.md) für Agent-Anweisungen und aktuelle Architektur.

---

## Lizenz

Proprietär - Nur für internen Gebrauch bei ACENCIA GmbH.

---

## Changelog

### v0.9.3 (05. Februar 2026)
- **NEU**: Kosten-Tracking für OpenRouter-Verarbeitung
- **NEU**: BatchProcessingResult mit Kosten-Statistiken (Gesamt + pro Dokument)
- **NEU**: Erweiterte Sach-Keywords (Privathaftpflicht, PHV, Tierhalterhaftpflicht, etc.)
- **NEU**: Courtage-Benennung mit VU_Name + Datum
- **FIX**: Privathaftpflichtversicherung wird jetzt korrekt als Sach klassifiziert
- **FIX**: Pensionskasse wird jetzt korrekt als Leben klassifiziert

### v0.9.2 (05. Februar 2026)
- **FIX**: Timezone-aware Token-Validierung (Degenia-Fix)
- **FIX**: MIME-Type→Extension Mapping (.pdf statt .bin)
- **FIX**: Auto Worker-Anpassung bei wenigen Lieferungen

### v0.9.1 (04. Februar 2026)
- **NEU**: Parallele BiPRO-Downloads (5 Worker, ThreadPoolExecutor)
- **NEU**: SharedTokenManager für thread-sicheres STS-Token-Management
- **NEU**: AdaptiveRateLimiter bei HTTP 429/503 (dynamische Worker-Anpassung)
- **NEU**: PDF-Validierung und automatische Reparatur mit PyMuPDF
- **NEU**: Auto-Refresh-Kontrolle (pause/resume während Operationen)
- **NEU**: GDV-Erkennung über BiPRO-Code (999xxx)
- **FIX**: if/elif-Struktur in document_processor (XML→roh korrekt)
- **FIX**: MTOM-Parsing verbessert (keine korrupten PDFs mehr)

### v0.9.0 (Februar 2026)
- **NEU**: BiPRO-Code-basierte Vorsortierung
- **NEU**: Token-optimierte KI-Klassifikation (~90% Einsparung)
- **NEU**: GDV-Metadaten aus Datensatz (VU + Datum ohne KI)
- **NEU**: Einheitliche Fortschrittsanzeige (BiPRO + Verarbeitung)
- **NEU**: LoadingOverlay für async Box-Wechsel

### v0.8.0 (Februar 2026)
- **NEU**: Kranken-Box für Krankenversicherungs-Dokumente
- **NEU**: Multi-Upload (mehrere Dateien gleichzeitig)
- **NEU**: Parallele Dokumentenverarbeitung (ThreadPoolExecutor)
- **NEU**: Robuster Download mit Retry-Logik (3 Versuche, Backoff)
- **NEU**: OpenRouter Credits-Anzeige im Header
- **NEU**: Thread-sicheres Worker-Cleanup (kein Crash bei Schließen)
- **NEU**: Robustes JSON-Parsing (_safe_json_loads)
- **NEU**: Sichere Dateinamen-Generierung (slug_de)
- **NEU**: Verbesserter KI-Prompt (Kontext-Awareness)
- **NEU**: insurance_type bei Courtage (Leben/Sach/Kranken im Dateinamen)

### v0.7.0 (Februar 2026)
- Box-System für Dokumentenarchiv (7 Boxen)
- Automatische Dokumenten-Klassifikation
- KI-basierte PDF-Benennung via OpenRouter

### v0.6.0 (Februar 2026)
- KI-basierte PDF-Analyse und Umbenennung
- OpenRouter-Integration (GPT-4o Vision + Structured Output)

### v0.5.0 (Februar 2026)
- BiPRO-Integration vollständig funktionsfähig (Degenia)
- Dokumentenarchiv mit Server-Backend
- PDF-Vorschau (QPdfView)
- Multi-Download/Multi-Delete im Archiv
- Automatische Archivierung von BiPRO-Downloads

### v0.4.0 (Januar 2026)
- BiPRO-Client Grundgerüst
- VU-Verbindungsverwaltung
- Server-API Integration

### v0.3.0 (Januar 2025)
- Partner-Ansicht mit Firmen/Personen-Übersicht
- Teildatensatz-Unterstützung

### v0.2.0
- Benutzer- und Experten-Ansicht
- GDV-Dateien speichern

### v0.1.0
- Initiale Version
- GDV-Dateien öffnen und anzeigen
