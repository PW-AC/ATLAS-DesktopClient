# ACENCIA ATLAS - Projektuebersicht

**Letzte Aktualisierung:** 24. Februar 2026
**Aktuelle Version:** 2.2.6 (VERSION-Datei)
**Projektname:** ACENCIA ATLAS ("Der Datenkern.")

---

## Was ist ACENCIA ATLAS?

ACENCIA ATLAS ist eine **Windows-Desktop-Anwendung** (Python/PySide6) mit einem **PHP-Server-Backend** (Strato Webspace), entwickelt fuer ein Versicherungsmakler-Buero mit 2-5 Nutzern.

Die App loest drei Kernprobleme:

1. **BiPRO-Datenabruf**: Automatisierter Download von Dokumenten (Policen, Abrechnungen, Schaeden) von Versicherungsunternehmen ueber das BiPRO-Protokoll (SOAP/XML)
2. **Dokumentenarchiv**: Zentrales, KI-gestuetztes Archiv fuer alle Versicherungsdokumente mit automatischer Klassifikation, Benennung und Duplikat-Erkennung
3. **Provisionsmanagement**: Geschaeftsfuehrer-Modul fuer Provisionsabrechnung, Berater-Verwaltung und Monatsabrechnungen

Zusaetzlich:
- **GDV-Editor**: Visualisierung und Bearbeitung von GDV-Datensaetzen (branchenspezifisches Fixed-Width-Format fuer Versicherungsdaten)
- **Kommunikation**: Mitteilungszentrale mit System-Meldungen und 1:1-Chat zwischen Nutzern
- **Auto-Update**: Automatische Software-Aktualisierung mit Admin-Verwaltung

---

## Zielgruppe und Nutzer

| Rolle | Anzahl | Zugang |
|-------|--------|--------|
| Administrator / Geschaeftsfuehrer | 1-2 | Voller Zugriff inkl. Admin-Bereich und Provisionsmanagement |
| Berater / Consulter | 2-3 | Dokumentenarchiv, BiPRO-Abruf, GDV-Editor, Chat |
| Teamleiter | 0-1 | Wie Berater + sieht Team-Provisionen |

**Rechte-System**: 12 granulare Berechtigungen (z.B. `documents_upload`, `bipro_fetch`, `smartscan_send`, `provision_access`, `provision_manage`)

---

## Tech-Stack

### Desktop-App (Client)

| Komponente | Technologie | Version |
|------------|-------------|---------|
| Sprache | Python | 3.10+ |
| UI-Framework | PySide6 (Qt6) | 6.6.0+ |
| PDF-Viewer | PySide6.QtPdf (QPdfView) | 6.6.0+ |
| PDF-Manipulation | PyMuPDF (fitz) | 1.23+ |
| Excel-Handling | openpyxl | 3.1+ |
| HTTP Client | requests | 2.31+ |
| BiPRO SOAP | requests (raw XML, kein zeep) | 2.31+ |
| Token-Zaehlung | tiktoken | 0.5+ |
| MSG-Parsing | extract-msg | 0.50+ |
| ZIP (AES-256) | pyzipper | 0.3.6+ |
| Outlook COM | pywin32 | 306+ |
| Installer/Build | PyInstaller + Inno Setup | 6.0+ |

### Server-Backend

| Komponente | Technologie | Version |
|------------|-------------|---------|
| API-Sprache | PHP | 7.4+ |
| Datenbank | MySQL | 8.0 |
| Hosting | Strato Webspace | Shared |
| Domain | acencia.info | HTTPS |
| E-Mail | PHPMailer | 6.9.3 |
| Verschluesselung | AES-256-GCM (fuer Credentials) | OpenSSL |

### KI-Integration

| Aspekt | Details |
|--------|---------|
| Provider | OpenRouter ODER OpenAI (umschaltbar im Admin) |
| Modelle | GPT-4o-mini (Stufe 1), GPT-4o-mini (Stufe 2) |
| Zweck | PDF-Klassifikation (Courtage/Sach/Leben/Kranken/Sonstige), Benennung, OCR |
| Kosten-Tracking | Exakte Kosten pro Request via model_pricing Tabelle |
| PII-Redaktion | E-Mail, IBAN, Telefon werden vor KI-Weiterleitung entfernt |

---

## Projektstruktur (Ueberblick)

```
X:\projekte\5510_GDV Tool V1\
├── src/                          # Python Desktop-App (~119 Dateien, ~48.000+ Zeilen)
│   ├── main.py                   # App-Einstiegspunkt
│   ├── api/                      # API-Clients (22 Dateien, ~6.900 Zeilen)
│   ├── bipro/                    # BiPRO SOAP-Client (7 Dateien, ~3.860 Zeilen)
│   ├── config/                   # Konfiguration (6 Dateien, ~2.120 Zeilen)
│   ├── domain/                   # Datenmodelle (4 Dateien, ~1.510 Zeilen)
│   ├── i18n/                     # Uebersetzungen (2 Dateien, ~2.130 Zeilen, ~1.400 Keys)
│   ├── layouts/                  # GDV-Satzart-Definitionen (2 Dateien)
│   ├── parser/                   # GDV-Parser (2 Dateien)
│   ├── services/                 # Business-Logik (13 Dateien, ~5.120 Zeilen)
│   ├── tests/                    # Smoke-Tests (2 Dateien)
│   └── ui/                       # Benutzeroberflaeche (~45 Dateien, ~28.000+ Zeilen)
│       ├── admin/                # Admin-Bereich (21 Dateien, ~5.700 Zeilen)
│       ├── archive/              # Dokumentenarchiv (4 Dateien, ~9.200 Zeilen)
│       ├── provision/            # Provisionsmanagement (14 Dateien, ~8.800 Zeilen)
│       └── styles/               # Design-Tokens (2 Dateien, ~1.100 Zeilen)
│
├── BiPro-Webspace Spiegelung Live/  # ⚠️ LIVE-SYNCHRONISIERT mit Strato!
│   └── api/                      # PHP REST API (27 Dateien, ~15.300 Zeilen)
│       ├── lib/                  # Hilfsbibliotheken (permissions, activity_logger, PHPMailer)
│       └── config.php            # DB-Credentials (SENSIBEL!)
│
├── run.py                        # Start-Script
├── VERSION                       # Versionsdatei (Single Source of Truth)
├── requirements.txt              # Python-Abhaengigkeiten
├── docs/                         # Technische Dokumentation
├── ChatGPT-Kontext/              # Diese Dokumentation
├── testdata/                     # GDV-Testdateien
└── logs/                         # Laufzeit-Logs (Rotation)
```

---

## Codebasis-Kennzahlen

| Metrik | Wert |
|--------|------|
| Python-Dateien | ~119 |
| Python-Codezeilen | ~48.000+ |
| PHP-Dateien (API) | 27 |
| PHP-Codezeilen | ~15.300 |
| i18n-Schluessel | ~1.400 |
| DB-Migrationen | 21 Skripte |
| DB-Tabellen (geschaetzt) | ~42+ |
| API-Endpunkte | ~150+ |
| Groesste Python-Datei | archive_boxes_view.py (~5.645 Zeilen) |
| Groesste PHP-Datei | provision.php (~2.480 Zeilen) |

---

## Kommunikation Desktop ↔ Server

```
Desktop-App (Python)                    Strato Webspace
┌─────────────────┐                    ┌──────────────────┐
│ requests (HTTP)  │ ──── HTTPS ────▶  │ PHP REST API     │
│ JWT-Token Auth   │ ◀───────────────  │ MySQL Datenbank  │
│                  │                    │ Datei-Storage    │
│ BiPRO SOAP       │ ──── HTTPS ────▶  │ (Versicherer)    │
│ (direkt zu VU)   │ ◀───────────────  │                  │
└─────────────────┘                    └──────────────────┘

Authentifizierung: JWT-Token (30 Tage gueltig)
Session: Single-Session pro Nutzer (neue Session beendet alte)
Auto-Refresh: JWT wird bei 401 automatisch erneuert
```

---

## Wichtige Prinzipien

1. **Desktop-First**: Keine Web-Oberflaeche, die App laeuft nur auf Windows
2. **Server = Datenbank + Storage**: PHP-API ist reine REST-Schicht, keine Rendering-Logik
3. **KI-Klassifikation ist optional**: Dokumente funktionieren auch ohne KI (landen in "Sonstige")
4. **Keine modalen Popups**: Alle Benachrichtigungen als Toast (nicht-blockierend)
5. **Live-Sync**: Der Ordner `BiPro-Webspace Spiegelung Live/` wird direkt auf den Server synchronisiert
6. **Deutsche UI**: Alle Texte auf Deutsch, aus zentraler i18n-Datei (`src/i18n/de.py`)
7. **Encoding**: GDV-Dateien nutzen CP1252, Daten im deutschen Format (DD.MM.YYYY)
