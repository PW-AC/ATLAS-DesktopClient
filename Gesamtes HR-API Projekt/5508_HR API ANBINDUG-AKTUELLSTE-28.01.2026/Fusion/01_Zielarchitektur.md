# 01 – Zielarchitektur: HR-Hub → ATLAS

## Überblick

Das HR-Modul wird **direkt in die ATLAS Desktop-App (PySide6)** integriert. Die Python-Geschäftslogik (Provider, Delta-Export, Trigger, Statistiken) läuft lokal auf dem Desktop. Persistenz erfolgt über die bestehende PHP-REST-API auf Strato (MySQL).

---

## Architektur-Diagramm

```
┌──────────────────────────────────────────────────────────────────────────┐
│                     ATLAS Desktop (PySide6 / Python)                     │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │  Bestehende Module                                                  │ │
│  │  ├── BiPRO, Archiv, GDV, Admin                                     │ │
│  │  ├── src/api/* (bestehende API-Clients)                            │ │
│  │  └── Auth-System (JWT, Login, Permissions)                          │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │  NEUES HR-MODUL                                                     │ │
│  │                                                                      │ │
│  │  hr/providers/          hr/services/          hr/views/             │ │
│  │  ├── base.py            ├── sync_service.py   ├── employers_view   │ │
│  │  ├── hrworks.py         ├── delta_service.py  ├── employees_view   │ │
│  │  ├── personio.py        ├── export_service.py ├── exports_view     │ │
│  │  └── sagehr.py          ├── snapshot_service  ├── snapshots_view   │ │
│  │                         ├── trigger_service   ├── triggers_view    │ │
│  │  hr/api_client.py       └── stats_service.py  └── stats_view      │ │
│  │  (PHP-Backend-Komm.)                                                │ │
│  └─────────────┬───────────────────────────┬──────────────────────────┘ │
│                │                           │                            │
│       ┌────────┘                           └────────┐                   │
│       ▼                                             ▼                   │
│  ┌─────────────────┐                    ┌─────────────────────┐        │
│  │ HR-Provider APIs │                    │ PHP REST-API        │        │
│  │ (HTTPS direkt)   │                    │ (Strato, JWT)       │        │
│  │ ┌─────────────┐  │                    │ /hr/* Endpoints     │        │
│  │ │ Personio    │  │                    └──────────┬──────────┘        │
│  │ │ HRworks     │  │                               │                   │
│  │ │ SageHR      │  │                               ▼                   │
│  │ └─────────────┘  │                    ┌─────────────────────┐        │
│  └─────────────────┘                    │ MySQL (Strato)      │        │
│                                          │ hr_* Tabellen       │        │
│                                          └─────────────────────┘        │
│                                                     │                   │
│                                                     ▼                   │
│                                          ┌─────────────────────┐        │
│                                          │ Webspace (Strato)   │        │
│                                          │ /files/hr/exports/  │        │
│                                          └─────────────────────┘        │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## Verantwortlichkeiten

### Desktop (Python/PySide6)

| Aufgabe | Wo |
|---------|-----|
| Provider-API-Calls (Personio, HRworks) | `hr/providers/*` |
| Daten normalisieren | `hr/providers/*` (normalize-Methoden) |
| Delta berechnen (Hash-Vergleich) | `hr/services/delta_service.py` |
| Excel generieren (openpyxl) | `hr/services/export_service.py` |
| Trigger auswerten + ausführen | `hr/services/trigger_service.py` |
| Statistiken berechnen | `hr/services/stats_service.py` |
| E-Mail senden (smtplib) | `hr/services/trigger_service.py` |
| API-Aktionen ausführen (requests) | `hr/services/trigger_service.py` |
| UI rendern (PySide6 Views) | `hr/views/*` |
| Alles via QThread/ThreadPool | Non-blocking UI |

### PHP-Backend (Strato)

| Aufgabe | Wo |
|---------|-----|
| JWT-Auth prüfen | Wie bestehend |
| Permissions prüfen (hr.view, hr.sync, ...) | Wie bestehend |
| CRUD für hr_employers | `/hr/employers` |
| Credentials verschlüsselt speichern/liefern | `/hr/employers/{id}/credentials` |
| Mitarbeiter-Daten speichern (Bulk) | `/hr/employees/bulk` |
| Snapshots speichern/abrufen | `/hr/snapshots` |
| Export-Dateien speichern (Upload) | `/hr/exports` |
| Trigger-Config CRUD | `/hr/triggers` |
| Trigger-Runs loggen | `/hr/trigger-runs` |

---

## Datenfluss: Delta-Export (Kernprozess)

```
1. Nutzer klickt "Delta-Export" in ATLAS
   │
   ├── 2. QThread startet
   │      │
   │      ├── 3. hr_api_client.get_credentials(employer_id)
   │      │      └── GET /hr/employers/{id}/credentials → PHP entschlüsselt
   │      │
   │      ├── 4. Provider instanziieren + list_employees()
   │      │      └── HTTPS an Personio/HRworks direkt
   │      │
   │      ├── 5. hr_api_client.get_latest_snapshot(employer_id)
   │      │      └── GET /hr/snapshots/{employer_id}/latest → MySQL
   │      │
   │      ├── 6. delta_service.calculate_diff(current, previous)
   │      │      └── Lokal: Hash-Vergleich, added/changed/removed
   │      │
   │      ├── 7. export_service.generate_scs_excel(diff, employer)
   │      │      └── Lokal: openpyxl → XLSX
   │      │
   │      ├── 8. hr_api_client.save_snapshot(employer_id, current_hashes)
   │      │      └── POST /hr/snapshots → MySQL
   │      │
   │      ├── 9. hr_api_client.upload_export(employer_id, xlsx_bytes)
   │      │      └── POST /hr/exports → Webspace + MySQL
   │      │
   │      ├── 10. trigger_service.evaluate_and_execute(employer, diff, current)
   │      │       ├── E-Mail: smtplib vom Desktop
   │      │       └── API: requests vom Desktop
   │      │
   │      └── 11. hr_api_client.log_trigger_runs(results)
   │             └── POST /hr/trigger-runs → MySQL
   │
   └── 12. UI aktualisiert (Signal → Slot)
```

---

## Auth-Flow (SSO)

```
1. Nutzer startet ATLAS Desktop
2. Login → POST /auth/login → JWT
3. JWT wird in allen API-Calls verwendet
4. HR-Modul nutzt denselben JWT
5. PHP prüft hr.* Permissions:
   - hr.view       → Arbeitgeber/Mitarbeiter sehen
   - hr.sync       → Daten synchronisieren
   - hr.export     → Exporte generieren
   - hr.triggers   → Trigger verwalten (Master only)
   - hr.admin      → Arbeitgeber verwalten
```

Kein separates Login, kein separates Session-Management.

---

## Was NICHT übernommen wird

| Komponente aus HR-Hub | Grund |
|-----------------------|-------|
| Flask-App (`app = Flask(...)`) | Wird durch PySide6 ersetzt |
| Jinja2-Templates | Werden durch PySide6-Views ersetzt |
| Flask-Sessions | JWT aus ATLAS |
| users.json | ATLAS-Benutzerverwaltung |
| CSRF-Schutz (Flask-WTF) | Desktop-App braucht kein CSRF |
| Rate-Limiter | PHP-Backend hat eigenes Rate-Limiting |
| Werkzeug/Waitress | Kein Webserver nötig |
| updater.py | ATLAS hat eigenes Auto-Update |
| JSON-Dateipersistenz | → MySQL via PHP-API |

---

## Was 1:1 übernommen wird

| Komponente | Datei in HR-Hub (app.py) | Neue Datei |
|------------|-------------------------|------------|
| BaseProvider | Zeilen 1837-1887 | `hr/providers/base.py` |
| HRworksProvider | Zeilen 1889-2141 | `hr/providers/hrworks.py` |
| PersonioProvider | Zeilen 2186-2362 | `hr/providers/personio.py` |
| SageHrProvider | Zeilen 2142-2185 | `hr/providers/sagehr.py` |
| SCS_HEADERS | Zeilen 306-313 | `hr/constants.py` |
| Helper-Funktionen | Zeilen 315-455 | `hr/helpers.py` |
| _map_to_scs_schema | Zeilen 2394-2471 | `hr/services/export_service.py` |
| generate_standard_export | Zeilen 2473-2507 | `hr/services/export_service.py` |
| Delta-Export-Logik | Zeilen 2509-2675 | `hr/services/delta_service.py` |
| _compare_snapshots | Zeilen 4712-4762 | `hr/services/snapshot_service.py` |
| Snapshot-Historie | Zeilen 2676-2778 | `hr/services/snapshot_service.py` |
| calculate_statistics | Zeilen 2779-2829 | `hr/services/stats_service.py` |
| calculate_long_term | Zeilen 2830-2905 | `hr/services/stats_service.py` |
| _format_stats_for_export | Zeilen 2907-2965 | `hr/services/stats_service.py` |
| TriggerEngine | Zeilen 1164-1600 | `hr/services/trigger_service.py` |
| EmailAction | Zeilen 1602-1740 | `hr/services/trigger_service.py` |
| APIAction | Zeilen 1742-1835 | `hr/services/trigger_service.py` |

---

**Erstellt:** 19.02.2026
