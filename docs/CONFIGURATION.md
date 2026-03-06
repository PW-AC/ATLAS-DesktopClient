# CONFIGURATION.md - ACENCIA ATLAS Desktop Client

> **Stand**: 05.03.2026 | **Version**: 2.3.1

---

## Ueberblick

ATLAS verwendet **keine `.env`-Dateien**. Die Konfiguration erfolgt ueber:

1. **Hardcoded Defaults** in Python-Modulen (API-URL, Timeouts)
2. **QSettings** fuer persistente Benutzereinstellungen (Registry/INI)
3. **Server-seitige Konfiguration** (DB-Credentials, API-Keys nur auf dem Server)
4. **Lokale Konfigurationsdateien** (VU-Connections, Zertifikate)

---

## API-Konfiguration

### Basis-URL

| Parameter | Wert | Datei |
|-----------|------|-------|
| `base_url` | `https://acencia.info/api` | `src/api/client.py` → `APIConfig` |
| `timeout` | 30 Sekunden | `src/api/client.py` → `APIConfig` |
| `verify_ssl` | `True` | `src/api/client.py` → `APIConfig` |

### Retry-Konfiguration

| Parameter | Wert | Datei |
|-----------|------|-------|
| `MAX_RETRIES` | 3 | `src/api/client.py` |
| `RETRY_STATUS_CODES` | `{429, 500, 502, 503, 504}` | `src/api/client.py` |
| `RETRY_BACKOFF_FACTOR` | 1.0 | `src/api/client.py` |

---

## QSettings (Persistente Einstellungen)

**Organisation**: `ACENCIA GmbH`
**Applikation**: `ACENCIA ATLAS`

Windows: Gespeichert in der Registry unter `HKCU\Software\ACENCIA GmbH\ACENCIA ATLAS`

| Key | Typ | Default | Beschreibung | Verwendung |
|-----|-----|---------|-------------|------------|
| `appearance/font_preset` | string | `classic` | Font-Preset (classic, compact, ...) | `src/main.py` |
| `appearance/language` | string | `de` | UI-Sprache (de, en, ru) | `src/i18n/__init__.py` |
| `bipro/last_fetch_*` | string | - | Letzter BiPRO-Abruf-Zeitpunkt pro VU | `src/ui/bipro_view.py` |
| `provision/last_path` | string | - | Letzter Import-Pfad | `src/infrastructure/storage/local_storage.py` |

---

## Token-Persistenz

### Bevorzugt: Keyring (Windows Credential Manager)

```python
# Verwendet DPAPI (Data Protection API) unter Windows
import keyring
keyring.set_password("ACENCIA_ATLAS", "auth_token", token)
```

### Fallback: Token-Datei

| Parameter | Wert |
|-----------|------|
| **Pfad** | `~/.bipro_gdv_token.json` |
| **Berechtigung** | `chmod 0600` |
| **Format** | `{ "token": "jwt...", "username": "..." }` |

Definiert in: `src/api/auth.py` → `AuthAPI.TOKEN_FILE`

---

## Lokale Konfigurationsdateien

### VU-Verbindungen

| Parameter | Wert |
|-----------|------|
| **Pfad** | `<config_dir>/vu_connections.json` |
| **Zweck** | BiPRO VU-Verbindungsdaten (URLs, Benutzer) |
| **Format** | JSON-Array mit VU-Objekten |

Definiert in: `src/config/vu_endpoints.py` → `get_config_dir()`

### Zertifikate

| Parameter | Wert |
|-----------|------|
| **Pfad** | `<certificates_dir>/index.json` |
| **Zweck** | BiPRO-Zertifikate (JKS, PEM) fuer SOAP-Verbindungen |
| **Format** | JSON-Index mit Zertifikat-Metadaten |

Definiert in: `src/config/certificates.py` → `get_certificates_dir()`

---

## Logging

### Konsole

```python
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
```

### Datei

| Parameter | Wert |
|-----------|------|
| **Pfad** | `logs/bipro_gdv.log` |
| **Handler** | `RotatingFileHandler` |
| **Max-Groesse** | 5 MB |
| **Backups** | 3 |
| **Encoding** | UTF-8 |

Definiert in: `src/main.py` → `_setup_logging()`

### Log-Level aendern

Standard-Level ist `INFO`. Fuer Debug-Logging:
```python
import logging
logging.getLogger().setLevel(logging.DEBUG)
```

---

## KI-Konfiguration

KI-Provider und Modelle werden ueber das Admin-Panel konfiguriert (DB-basiert).

| Parameter | Konfigurationsort | Beschreibung |
|-----------|------------------|-------------|
| **Active Provider** | DB: `ai_provider_keys` | OpenRouter oder OpenAI |
| **API-Keys** | DB: `ai_provider_keys` (AES-256-GCM verschluesselt) | Provider-API-Schluessel |
| **Modell-Preise** | DB: `model_pricing` | Input/Output-Preis pro 1M Tokens |
| **Klassifikations-Modell** | DB: `processing_settings` | Aktuell verwendetes KI-Modell |
| **Klassifikations-Prompt** | DB: `processing_settings` | System-Prompt fuer Klassifikation |
| **Fallback-Modell** | `src/config/ai_models.py` | GPT-4o als Fallback bei niedriger Confidence |

### Lokale Fallback-Konfiguration

Datei: `src/config/ai_models.py`
- Modell-Listen (verfuegbare OpenRouter/OpenAI-Modelle)
- Fallback-Werte wenn DB-Konfiguration fehlt

---

## BiPRO-Konfiguration

| Parameter | Wert | Datei |
|-----------|------|-------|
| **Max Worker** | 10 | `src/bipro/workers.py` |
| **Rate Limit** | Adaptiv (429/503 → dynamisch) | `src/bipro/rate_limiter.py` |
| **MTOM/XOP** | Aktiviert | `src/bipro/transfer_service.py` |
| **Timeout** | 30s (STS), 60s (Transfer) | `src/bipro/transfer_service.py` |

### VU-Endpoints (vorkonfiguriert)

Datei: `src/config/vu_endpoints.py`

| VU | STS-URL | Transfer-URL |
|----|---------|-------------|
| Degenia | `https://bipro.degenia.de/...` | `https://bipro.degenia.de/...` |
| VEMA | `https://bipro.vema-eg.de/...` | `https://bipro.vema-eg.de/...` |

---

## Build-Konfiguration

### PyInstaller (`build_config.spec`)

| Parameter | Wert |
|-----------|------|
| **Entry** | `run.py` |
| **Name** | `ACENCIA-ATLAS` |
| **Icon** | `src/ui/assets/icon.ico` |
| **Version-Info** | `version_info.txt` |
| **Hidden Imports** | PySide6, tiktoken, certifi, keyring |
| **Daten** | `VERSION`, `src/ui/assets/fonts/` |

### Inno Setup (`installer.iss`)

| Parameter | Wert |
|-----------|------|
| **App-Name** | `ACENCIA ATLAS` |
| **Version** | Dynamisch aus `VERSION`-Datei |
| **Publisher** | `ACENCIA GmbH` |
| **Lizenz** | `LICENSE.txt` |
| **Mutex** | `ACENCIA_ATLAS_SINGLE_INSTANCE` |
| **Autostart** | Scheduled Task fuer Hintergrund-Updater |

---

## Server-Konfiguration (Referenz)

Diese Werte liegen **NUR auf dem Server** (nicht im Repo):

| Parameter | Ort | Beschreibung |
|-----------|-----|-------------|
| **DB-Credentials** | `/var/www/atlas/api/config.php` | MySQL Host, User, Password, DB |
| **JWT-Secret** | `/var/www/atlas/api/config.php` | JWT-Signatur-Schluessel |
| **Crypto-Key** | `/var/www/atlas/api/config.php` | AES-256-GCM Master-Key |
| **SMTP-Credentials** | DB (verschluesselt) | E-Mail-Versand |
| **API-Provider-Keys** | DB (verschluesselt) | OpenRouter/OpenAI |
| **HR-Provider-Credentials** | DB (verschluesselt) | Personio/HRworks |

Details: `ATLAS_private - Doku - Backend/hetzner-migration/INFRASTRUKTUR_DATEN.md`

---

## Umgebungsvariablen

ATLAS verwendet **keine Umgebungsvariablen**. Alle Konfiguration ist entweder:
- Hardcoded (API-URL, Timeouts)
- Persistiert (QSettings, Token-File)
- Server-seitig (DB, config.php)

Die `.gitignore` ignoriert `.env` und `.env.*` praeventiv.

---

## Modul-Konfiguration

### Modul-Zugriffssteuerung (Migrationen 045-050)

Die Module (Core, Provision, Workforce) werden serverseitig verwaltet:

| Parameter | Konfigurationsort | Beschreibung |
|-----------|------------------|-------------|
| **Module** | DB: `modules` | Registrierte Module (core, provision, workforce) |
| **User-Module** | DB: `user_modules` | Modul-Freischaltung pro User |
| **Rollen** | DB: `roles` | Modul-spezifische Rollen |
| **Berechtigungen** | DB: `role_permissions` | Rechte pro Rolle |
| **Account-Typ** | DB: `users.account_type` | user, admin, super_admin |

### Zugangslevel

| Level | Beschreibung |
|-------|-------------|
| `user` | Standard-Zugriff auf das Modul |
| `admin` | Modul-Admin: Kann Zugriff, Rollen und Konfiguration verwalten |

Die Modul-Verwaltung erfolgt ueber:
- Desktop: ModuleAdminShell (`src/ui/module_admin/`)
- API: AdminModulesAPI (`src/api/admin_modules.py`)
- PHP: `admin_modules.php` (Endpoints unter `/admin/modules`)

---

## Internationalisierung (i18n)

| Parameter | Wert |
|-----------|------|
| **Sprachen** | `de` (Deutsch), `en` (English), `ru` (Russisch) |
| **Dateien** | `src/i18n/de.py`, `src/i18n/en.py`, `src/i18n/ru.py` |
| **Keys** | ~2600 (Deutsch als Hauptkatalog) |
| **Persistenz** | QSettings `appearance/language` |
| **Mechanismus** | Module-basiertes Patching zur Laufzeit |
| **Neue Prefixe** | `MODULE_ADMIN_*`, `ACCOUNT_TYPE_*`, `ACCESS_LEVEL_*`, `ROLE_*` |

### Verwendung

```python
from i18n import de as texts

label = texts.ARCHIVE_UPLOAD_SUCCESS  # "Dokument erfolgreich hochgeladen"
```

### Sprache wechseln

```python
import i18n
i18n.set_language('en')  # Patcht de-Modul mit englischen Texten
```
