# 02 – Modul-Mapping: app.py → Neue Dateien

## Übersicht

Die monolithische `app.py` (~5326 Zeilen) wird in eigenständige Module aufgeteilt.
Dieses Dokument zeigt die **exakte Zuordnung** jeder Sektion.

---

## Mapping-Tabelle

### Übernommene Logik (→ neue Dateien)

| app.py Zeilen | Funktion/Klasse | Neue Datei | Anpassungen nötig |
|---------------|-----------------|------------|-------------------|
| 306-313 | `SCS_HEADERS` (Konstante) | `hr/constants.py` | Keine |
| 315-343 | `_get_from_path()` | `hr/helpers.py` | Keine |
| 345-364 | `_getv()` | `hr/helpers.py` | Keine |
| 366-376 | `_get_safe_employer_name()` | `hr/helpers.py` | Keine |
| 378-395 | `_get_value_from_details()` | `hr/helpers.py` | Keine |
| 397-413 | `_parse_date()` | `hr/helpers.py` | Keine |
| 415-426 | `_format_date_for_display()` | `hr/helpers.py` | Keine |
| 1837-1887 | `BaseProvider` (ABC) | `hr/providers/base.py` | Keine |
| 1889-2141 | `HRworksProvider` | `hr/providers/hrworks.py` | Import-Pfade |
| 2142-2185 | `SageHrProvider` | `hr/providers/sagehr.py` | Keine |
| 2186-2362 | `PersonioProvider` | `hr/providers/personio.py` | Import-Pfade |
| 2363-2390 | `ProviderFactory` | `hr/providers/__init__.py` | Import-Pfade |
| 2394-2471 | `_map_to_scs_schema()` | `hr/services/export_service.py` | Import von helpers |
| 2473-2507 | `generate_standard_export()` | `hr/services/export_service.py` | Kein app.config |
| 2509-2520 | `_json_hash()` | `hr/helpers.py` | Keine |
| 2522-2542 | `_flatten_record()` | `hr/helpers.py` | Keine |
| 2544-2555 | `_person_key()` | `hr/helpers.py` | Keine |
| 2557-2675 | `generate_delta_scs_export()` | `hr/services/delta_service.py` | API statt Dateisystem |
| 2676-2778 | `_get_employee_history_from_snapshots()` | `hr/services/snapshot_service.py` | API statt Dateisystem |
| 2779-2829 | `calculate_statistics()` | `hr/services/stats_service.py` | Import von helpers |
| 2830-2905 | `calculate_long_term_statistics()` | `hr/services/stats_service.py` | Keine |
| 2907-2965 | `_format_stats_for_export()` | `hr/services/stats_service.py` | Keine |
| 4712-4762 | `_compare_snapshots()` | `hr/services/snapshot_service.py` | Keine |
| 1164-1600 | `TriggerEngine` | `hr/services/trigger_service.py` | API statt JSON-Store |
| 1602-1740 | `EmailAction` | `hr/services/trigger_service.py` | Keine |
| 1742-1835 | `APIAction` | `hr/services/trigger_service.py` | Keine |

### NICHT übernommene Logik (Flask-spezifisch / durch ATLAS ersetzt)

| app.py Zeilen | Funktion/Klasse | Grund | Ersatz in ATLAS |
|---------------|-----------------|-------|-----------------|
| 1-17 | Imports (Flask etc.) | Framework-spezifisch | PySide6-Imports |
| 18-127 | Credential-Encryption (Fernet) | ATLAS hat eigene Verschlüsselung | AES-256-GCM via PHP |
| 130-298 | Logging-Setup, custom_log() | ATLAS hat eigenes Logging | ATLAS Logger |
| 428-455 | `save_history_entry()` | JSON-Dateisystem | API: POST /hr/history |
| 460-615 | `EmployerStore` | JSON-Dateisystem | API: /hr/employers |
| 624-973 | `TriggerStore` | JSON-Dateisystem | API: /hr/triggers |
| 975-1156 | `TriggerLogStore` | JSON-Dateisystem | API: /hr/trigger-runs |
| 2966-3055 | Flask-App-Init | Flask-spezifisch | Entfällt |
| 3057-3075 | Security Headers | Flask-spezifisch | PHP-Backend |
| 3084-3162 | Zugriffskontrolle | Flask-Sessions | JWT Permissions |
| 3164-3355 | User-Management | users.json | ATLAS Auth-System |
| 3357-3450 | Login/Logout | Flask-Sessions | ATLAS Login |
| 3454-3560 | Settings-Routen | Flask + Jinja2 | PySide6 Views |
| 3570-3990 | Trigger-Routen | Flask + Jinja2 | PySide6 Views |
| 4095-4170 | User-Settings | Flask + Jinja2 | ATLAS Settings |
| 4300-4965 | Alle @app.route() | Flask-Routing | PySide6 Signals |
| 4967-5295 | API-Endpunkte | Flask-Routing | Direkte Aufrufe |
| 5312-5326 | `__main__` Block | Flask-Server | Entfällt |
| templates/* | 18 Jinja2-Templates | Web-UI | PySide6 Views |
| static/css/* | CSS-Dateien | Web-UI | QSS-Styles |

---

## Dateistruktur nach Extraktion

```
hr/
├── __init__.py              # HR-Modul-Registrierung
├── constants.py             # SCS_HEADERS + Konfiguration (15 Zeilen)
├── helpers.py               # Utility-Funktionen (180 Zeilen)
├── api_client.py            # PHP-Backend-Kommunikation (NEU, ~200 Zeilen)
├── providers/
│   ├── __init__.py          # ProviderFactory + Registry (40 Zeilen)
│   ├── base.py              # BaseProvider ABC (55 Zeilen)
│   ├── hrworks.py           # HRworksProvider (260 Zeilen)
│   ├── personio.py          # PersonioProvider (180 Zeilen)
│   └── sagehr.py            # SageHrProvider Mock (45 Zeilen)
└── services/
    ├── __init__.py
    ├── sync_service.py      # Mitarbeiterdaten holen + speichern (NEU, ~100 Zeilen)
    ├── delta_service.py     # Diff + Delta-Export-Orchestrierung (170 Zeilen)
    ├── export_service.py    # Excel-Generierung (120 Zeilen)
    ├── snapshot_service.py  # Snapshot-Vergleich + Historie (160 Zeilen)
    ├── trigger_service.py   # TriggerEngine + Actions (700 Zeilen)
    └── stats_service.py     # Statistik-Berechnung (200 Zeilen)
```

**Geschätzter Gesamtumfang:** ~2.425 Zeilen (vs. 5.326 in app.py)
- Davon ~1.900 Zeilen 1:1 übernommen
- Davon ~525 Zeilen neu (API-Client, Sync-Service, Adapter)

---

## Import-Änderungen

### Vorher (app.py – alles in einer Datei)
```python
# Direkter Zugriff auf alles
SCS_HEADERS = [...]
def _getv(...): ...
class BaseProvider: ...
class HRworksProvider(BaseProvider): ...
```

### Nachher (modulare Struktur)
```python
# In hr/providers/hrworks.py:
from hr.providers.base import BaseProvider
from hr.helpers import _format_date_for_display

# In hr/services/delta_service.py:
from hr.helpers import _json_hash, _flatten_record, _person_key, _getv, _get_safe_employer_name
from hr.services.export_service import map_to_scs_schema
from hr.services.snapshot_service import compare_snapshots

# In hr/services/export_service.py:
from hr.constants import SCS_HEADERS
from hr.helpers import _getv, _get_from_path, _get_safe_employer_name
```

---

**Erstellt:** 19.02.2026
