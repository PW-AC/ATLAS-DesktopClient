# 06 - Konfiguration und Abhängigkeiten

**Version:** 0.9.3  
**Analyse-Datum:** 2026-02-05

---

## Python-Abhängigkeiten

**Quelle:** `requirements.txt`

| Paket | Version | Zweck |
|-------|---------|-------|
| PySide6 | ≥6.6.0 | GUI Framework (Qt 6) |
| requests | ≥2.31.0 | HTTP Client für API-Kommunikation |
| cryptography | ≥41.0.0 | PFX-Zertifikate (easy Login) |
| PyMuPDF | ≥1.23.0 | PDF-Verarbeitung für KI-Benennung |
| pyjks | ≥20.0.0 | JKS-Zertifikate (Java KeyStore) |
| pyinstaller | ≥6.0.0 | Packaging (optional) |

**Nicht aktiv genutzt (auskommentiert):**
- `zeep` - SOAP Client (zu strikt für Degenia)
- `openpyxl` - Excel-Export

---

## Server-Konfiguration

### PHP API (Strato Webspace)

**Quelle:** `BiPro-Webspace Spiegelung Live/api/config.php`

| Konfiguration | Wert | Beschreibung |
|---------------|------|--------------|
| DB Server | `database-5019508812.webspace-host.com` | MySQL Server |
| DB Name | `dbs15252975` | Datenbank |
| DB User | (in config.php) | SENSIBEL |
| DB Password | (in config.php) | SENSIBEL |
| Master Key | (in config.php) | Für Verschlüsselung |
| JWT Secret | (in config.php) | Für Token-Signierung |

**WICHTIG:** `config.php` ist per `.htaccess` geschützt und nicht über HTTP aufrufbar!

### API-Endpunkte

| Endpunkt | Methode | Beschreibung |
|----------|---------|--------------|
| `/auth/login` | POST | Login, JWT-Token erhalten |
| `/auth/logout` | POST | Logout |
| `/documents` | GET | Alle Dokumente (mit Box-Filter) |
| `/documents` | POST | Dokument hochladen |
| `/documents/{id}` | GET | Dokument herunterladen |
| `/documents/{id}` | PUT | Metadaten aktualisieren |
| `/documents/{id}` | DELETE | Dokument löschen |
| `/documents/stats` | GET | Box-Statistiken |
| `/documents/move` | POST | Dokumente verschieben |
| `/vu-connections` | GET/POST/DELETE | VU-Verbindungen |
| `/vu-connections/{id}/credentials` | GET | Zugangsdaten (verschlüsselt) |
| `/ai/key` | GET | OpenRouter API-Key |

---

## Dokumenten-Verarbeitungsregeln

**Quelle:** `src/config/processing_rules.py`

### GDV-Dateiendungen

```python
"gdv_extensions": [".gdv", ".txt", ""]
```

### XML-Rohdateien-Patterns

```python
"raw_xml_patterns": [
    "Lieferung_Roh_*.xml",
    "*_Roh_*.xml",
    "BiPRO_Raw_*.xml"
]
```

### Courtage-Schlüsselwörter (Auszug)

```python
"courtage_keywords": [
    "Provisionsabrechnung",
    "Courtage",
    "Courtageabrechnung",
    "Vermittlervergütung",
    ...
]
```

### Leben/Sach/Kranken-Schlüsselwörter

```python
"leben_keywords": ["leben", "lebensversicherung", "rente", "bu", 
                   "pensionskasse", "rentenanstalt", ...]  # v0.9.3 erweitert
"sach_keywords": ["haftpflicht", "hausrat", "kfz", "unfall",
                  "privathaftpflicht", "phv", "tierhalterhaftpflicht",
                  "hundehaftpflicht", "bauherrenhaftpflicht",
                  "jagdhaftpflicht", "gewaesserschadenhaftpflicht", ...]  # v0.9.3 erweitert
"kranken_keywords": ["kranken", "pkv", "zahnzusatz", "pflege", ...]
```

**Neu in v0.9.3 - Erweiterte Sach-Klassifikation:**
- Alle Haftpflichtversicherungen werden korrekt als "Sach" erkannt
- Pensionskasse/Rentenanstalt werden als "Leben" klassifiziert

### Weitere Regeln

| Regel | Wert | Beschreibung |
|-------|------|--------------|
| `max_file_size` | 50 MB | Maximale Dateigröße für Verarbeitung |
| `max_pdf_pages` | 10 | Maximale Seiten für OCR |
| `auto_processing_enabled` | true | Automatische Verarbeitung aktiv |
| `processing_delay` | 1.0s | Verzögerung zwischen Dokumenten |

---

## OpenRouter-Konfiguration

**Quelle:** `src/api/openrouter.py`

| Konfiguration | Wert |
|---------------|------|
| Base URL | `https://openrouter.ai/api/v1` |
| Vision Model | `openai/gpt-4o` |
| Extract Model | `openai/gpt-4o` |
| Max Retries | 4 |
| Retry Status Codes | 429, 502, 503, 504 |
| Retry Backoff Factor | 1.5 |
| **Credits Endpoint** | `/api/v1/auth/key` (v0.9.3) |

**API-Key:** Wird vom Server abgerufen (`/api/ai/key`)

**Kosten-Tracking (v0.9.3):**
- Guthaben wird vor und nach Batch-Verarbeitung abgefragt
- Differenz wird als Gesamtkosten berechnet
- Pro-Dokument-Kosten = Gesamtkosten / Anzahl erfolgreicher Dokumente

---

## BiPRO-Konfiguration

**Quelle:** `src/bipro/transfer_service.py`

### Bekannte Endpoints

```python
KNOWN_ENDPOINTS = {
    'degenia': {
        'transfer': 'https://transfer.degenia.de/X4/httpstarter/ReST/BiPRO/430_Transfer/Service_2.6.1.1.0',
        'sts': 'https://transfer.degenia.de/X4/httpstarter/ReST/BiPRO/410_STS/UserPasswordLogin_2.6.1.1.0'
    }
}
```

### Authentifizierungs-Methoden

| Methode | Felder | Beschreibung |
|---------|--------|--------------|
| STS-Token | username, password, sts_endpoint_url | Standard (Degenia) |
| PFX-Zertifikat | pfx_path, pfx_password | easy Login |
| JKS-Zertifikat | jks_path, jks_password, jks_alias | Java KeyStore |
| PEM-Zertifikat | cert_path, key_path | Separate Dateien |

---

## Design-Tokens (ACENCIA CI)

**Quelle:** `src/ui/styles/tokens.py`

### Farben

| Token | Wert | Verwendung |
|-------|------|------------|
| `PRIMARY_900` | #001f3d | Sidebar, Titel, Primärtext |
| `PRIMARY_500` | #88a9c3 | Sekundärtext, Icons |
| `PRIMARY_100` | #e3ebf2 | Hover, Backgrounds |
| `PRIMARY_0` | #ffffff | Content-Hintergrund |
| `ACCENT_500` | #fa9939 | CTAs, Active States |
| `ACCENT_100` | #f8dcbf | Badges, Highlights |

### Typografie

| Token | Wert |
|-------|------|
| `FONT_HEADLINE` | "Tenor Sans", "Segoe UI", sans-serif |
| `FONT_BODY` | "Open Sans", "Segoe UI", sans-serif |
| `FONT_SIZE_H1` | 20px |
| `FONT_SIZE_BODY` | 13px |
| `FONT_SIZE_CAPTION` | 11px |

### Box-Farben

| Box | Farbe |
|-----|-------|
| eingang | #f59e0b (Amber) |
| verarbeitung | #f97316 (Orange) |
| gdv | #10b981 (Grün) |
| courtage | #6366f1 (Indigo) |
| sach | #3b82f6 (Blau) |
| leben | #8b5cf6 (Violett) |
| kranken | #06b6d4 (Cyan) |
| sonstige | #64748b (Grau) |
| roh | #78716c (Steingrau) |

---

## Umgebungsvariablen

| Variable | Verwendung | Notwendig |
|----------|------------|-----------|
| - | (Keine erforderlich) | - |

**Hinweis:** Alle Konfiguration ist in der App/Server fest definiert.

---

## Dateipfade

### Lokale Verzeichnisse

| Pfad | Beschreibung |
|------|--------------|
| `X:\projekte\5510_GDV Tool V1\` | Projekt-Root |
| `testdata/` | Testdaten |
| `docs/` | Dokumentation |
| `Kontext/` | Diese Dokumentation |

### Server-Verzeichnisse

| Pfad (Webspace) | Beschreibung |
|-----------------|--------------|
| `/BiPro/api/` | PHP REST API |
| `/BiPro/dokumente/` | Datei-Storage |

---

## Encoding-Konfiguration

### GDV-Dateien

| Aspekt | Wert |
|--------|------|
| Standard | CP1252 (Windows-1252) |
| Fallback 1 | Latin-1 (ISO-8859-1) |
| Fallback 2 | UTF-8 |
| Zeilenbreite | 256 Bytes |
| Zeilenende | Variabel (wird erkannt) |

**Quelle:** `src/parser/gdv_parser.py`
