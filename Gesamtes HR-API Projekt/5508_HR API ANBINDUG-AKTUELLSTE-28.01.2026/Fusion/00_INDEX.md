# Fusion: HR-Hub → ATLAS Integration

## Zweck dieses Ordners

Dieser Ordner enthält die **komplette Dokumentation und vorbereiteten Module** für die Integration des ACENCIA HR-Hub in die ATLAS Desktop-Anwendung (PySide6).

**WICHTIG FÜR AGENTEN:** Lies diesen Index zuerst, dann die einzelnen Dokumente in Reihenfolge.

---

## Dokumente (in Lesereihenfolge)

| Nr. | Datei | Inhalt |
|-----|-------|--------|
| 01 | [01_Zielarchitektur.md](01_Zielarchitektur.md) | Architektur-Diagramm, Datenflüsse, Designentscheidungen |
| 02 | [02_Modul_Mapping.md](02_Modul_Mapping.md) | Exakte Zuordnung: app.py Zeilen → neue Dateien |
| 03 | [03_Endpoint_Kontrakte.md](03_Endpoint_Kontrakte.md) | PHP-Backend-Endpoints (Strato) – Request/Response |
| 04 | [04_MySQL_Schema.md](04_MySQL_Schema.md) | Komplettes Datenbank-Schema mit Erklärungen |
| 05 | [05_API_Client_Spezifikation.md](05_API_Client_Spezifikation.md) | Python API-Client für Desktop ↔ PHP-Backend |
| 06 | [06_Migrations_Checkliste.md](06_Migrations_Checkliste.md) | Schritt-für-Schritt-Anleitung für die Umsetzung |

---

## Extrahierte Module

Unter `extrahierte_module/hr/` liegen die **fertig extrahierten Python-Module** aus HR-Hub `app.py`. Diese sind bereit zur Integration in ATLAS:

```
extrahierte_module/
└── hr/
    ├── __init__.py              # Modul-Initialisierung
    ├── constants.py             # SCS_HEADERS, Konfigurationskonstanten
    ├── helpers.py               # Utility-Funktionen (Datum, Pfade, Hashing)
    ├── providers/
    │   ├── __init__.py          # Provider-Registry
    │   ├── base.py              # BaseProvider (ABC)
    │   ├── hrworks.py           # HRworksProvider
    │   ├── personio.py          # PersonioProvider
    │   └── sagehr.py            # SageHrProvider (Mock)
    └── services/
        ├── __init__.py
        ├── sync_service.py      # Mitarbeiterdaten von Provider abrufen
        ├── delta_service.py     # Snapshot-Vergleich, Diff-Berechnung
        ├── export_service.py    # Excel-Generierung (Standard + Delta-SCS)
        ├── snapshot_service.py  # Snapshot-Management und Historie
        ├── trigger_service.py   # TriggerEngine, EmailAction, APIAction
        └── stats_service.py     # Standard- und Langzeit-Statistiken
```

---

## Entscheidungen

| Entscheidung | Begründung |
|-------------|-----------|
| **Kein VPS** | Alles in ATLAS integriert, Strato bleibt PHP+MySQL |
| **Provider-Calls vom Desktop** | Desktop ruft HR-APIs direkt (HTTPS), PHP speichert nur Daten |
| **Auth über ATLAS** | JWT + Permissions wie bestehend, kein eigenes Auth im HR-Modul |
| **JSON → MySQL** | EmployerStore, Snapshots, Triggers → MySQL via PHP-API |
| **Trigger vom Desktop** | Nutzer löst Delta-Export aus → Desktop führt Trigger aus |
| **Exports auf Webspace** | Excel-Dateien werden via PHP auf Strato gespeichert |

---

## Kontext aus HR-Hub

Die Kontextdokumentation des HR-Hub liegt in:
- `Kontext/` – Vollständige Projektanalyse
- `ACENCIA_API_Hub/AGENTS.md` – Technische KI-Agent-Dokumentation
- `ACENCIA_API_Hub/docs/` – Architektur, Triggers, Konfiguration

---

**Erstellt:** 19.02.2026
**Autor:** Fusions-Vorbereitung (automatisch)
