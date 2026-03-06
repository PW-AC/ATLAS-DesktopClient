# 01 - Projektüberblick

## Was ist ACENCIA Hub?

ACENCIA Hub ist eine **Flask-basierte Web-Anwendung**, die als zentrales Dashboard für HR-Daten aus verschiedenen Provider-Systemen dient. Die Anwendung verbindet sich mit HR-APIs (Personio, HRworks, SageHR), normalisiert die Mitarbeiterdaten und bietet Funktionen für Analyse, Export und Vergleich.

**Evidenz:** `README.md:1-4`, `AGENTS.md:9-11`

---

## Projekttyp

| Aspekt | Beschreibung |
|--------|-------------|
| **Typ** | Web-Anwendung |
| **Rendering** | Server-Side mit Jinja2 Templates |
| **API** | RESTful JSON-Endpoints für Frontend-Integration |
| **Architektur** | Monolithisch (alles in `app.py`) |

---

## Zielgruppe

| Benutzergruppe | Funktion |
|----------------|----------|
| **HR-Manager** | Mitarbeiterübersicht, Statistiken, Exporte erstellen |
| **Master-User** | Benutzerverwaltung, System-Einstellungen, Updates |
| **Normale Benutzer** | Zugewiesene Arbeitgeber einsehen, Exporte generieren |

**Evidenz:** `README.md:34-38`, `app.py:1836-1869` (Zugriffskontrolle)

---

## Einsatzzweck

### Primäre Use Cases

1. **Multi-Mandanten HR-Verwaltung**
   - Mehrere Arbeitgeber mit unterschiedlichen HR-Providern verwalten
   - Zentrales Dashboard für alle Mandanten
   - **Evidenz:** `README.md:8-10`

2. **Mitarbeiterdaten-Aggregation**
   - Daten aus verschiedenen HR-Systemen normalisieren
   - Einheitliche Darstellung unabhängig vom Provider
   - **Evidenz:** `app.py:616-666` (BaseProvider), `AGENTS.md:15-19`

3. **Statistik und Analyse**
   - KPIs zu Altersstruktur, Geschlechterverteilung, Fluktuation
   - Standard- und Langzeit-Analyse aus Snapshots
   - **Evidenz:** `app.py:1531-1579` (calculate_statistics), `README.md:17-21`

4. **Datenexport für Lohnabrechnung (SCS)**
   - Delta-Export nur für neue/geänderte Mitarbeiter
   - Spezielles SCS-Format mit festen Headern
   - **Evidenz:** `app.py:1229-1426` (generate_delta_scs_export), `AGENTS.md:39-49`

5. **Historische Datenvergleiche**
   - Snapshot-System zur Änderungsverfolgung
   - Vergleich zwischen Zeitpunkten
   - **Evidenz:** `README.md:29-33`

---

## Zielumgebung

| Aspekt | IST-Zustand | Evidenz |
|--------|-------------|---------|
| **Deployment-Typ** | Lokaler Windows-Server im LAN | `start.bat`, `run.py:57-58` |
| **Netzwerk** | 0.0.0.0:5001 (LAN-Zugriff) | `run.py:57-58` |
| **Betriebssystem** | Windows (primär) | `start.bat`, PowerShell-Befehle |
| **Reverse Proxy** | NICHT VORHANDEN | - |
| **HTTPS/TLS** | NICHT KONFIGURIERT | - |

**Hinweis:** Die Anwendung ist für den Einsatz in lokalen Netzwerken konzipiert, nicht für öffentliches Internet-Deployment.

---

## Eigentümer und Entwicklung

| Aspekt | Wert |
|--------|------|
| **Eigentümer** | Acencia GmbH |
| **Entwickler** | Paul Weimert / Acencia Team |
| **Version** | 1.1.0 (Trigger-System) |
| **Lizenz** | Proprietär |
| **Repository** | `paulweimert2006-commits/JULES_WEB4` (privat) |

**Evidenz:** `README.md:234-240`, `__init__.py:30-36`, `base.html:64`

---

## Feature-Übersicht

### Implementierte Features ✓

| Feature | Beschreibung | Evidenz |
|---------|-------------|---------|
| Arbeitgeber-Verwaltung | CRUD für Mandanten, Provider-Konfiguration | `app.py:4355-4406` |
| Personio-Integration | Vollständige API-Anbindung | `app.py:2186-2360` |
| HRworks-Integration | Vollständige API-Anbindung (Prod + Demo) | `app.py:1889-2141` |
| SageHR-Integration | Mock-Provider | `app.py:2142-2185` |
| Mitarbeiter-Dashboard | Liste, Filter, Detailansicht | Templates, `app.py:4406-4467` |
| Standard-Statistiken | KPIs, Diagramme | `app.py:2779-2829` |
| Langzeit-Analyse | Aus Snapshots berechnet | `app.py:2830-2905` |
| Standard-Export | XLSX mit allen Daten | `app.py:2473-2507` |
| Delta-SCS-Export | Nur Änderungen, SCS-Format | `app.py:2557-2675` |
| Snapshot-System | Automatische Erstellung, Vergleich | `app.py:2676-2778` |
| Benutzerverwaltung | Multi-User, Master-Rechte | `app.py:3164-3330` |
| Theme-System | Hell/Dunkel-Modus | `tokens.css:124-137`, `base.html:91-151` |
| Auto-Updates | GitHub-Integration | `updater.py` |
| Security-Fixes | 20 von 26 Befunden umgesetzt | `Sicherheit/Umsetzung/00_INDEX.md` |
| **Trigger-System** | Automatisierte E-Mail/API-Aktionen | `app.py:624-1600`, `docs/TRIGGERS.md` |

### Bekannte Einschränkungen

| Einschränkung | Beschreibung |
|---------------|-------------|
| Monolithische Codebasis | `app.py` hat ~5326 Zeilen |
| Kein HTTPS | Benötigt externen Reverse Proxy |
| SageHR nur Mock | Keine echte API-Anbindung |
| Keine automatische Snapshot-Bereinigung | Alte Snapshots werden nicht gelöscht |
| Trigger nur bei Delta-Export | Nicht bei normalem Datenabruf |

**Evidenz:** `AGENTS.md:423-427`, `Sicherheit/Umsetzung/00_INDEX.md:105-112`

---

## Beziehung zu anderen Systemen

```
┌─────────────────────────────────────────────────────────────────┐
│                         ACENCIA Hub                             │
│                    (diese Anwendung)                            │
└───────────────────────────┬─────────────────────────────────────┘
                            │
            ┌───────────────┼───────────────┐
            ▼               ▼               ▼
    ┌───────────────┐ ┌───────────────┐ ┌───────────────┐
    │   Personio    │ │    HRworks    │ │    SageHR     │
    │   API v1      │ │   API v2      │ │   (Mock)      │
    └───────────────┘ └───────────────┘ └───────────────┘
            │               │               │
            ▼               ▼               ▼
    ┌─────────────────────────────────────────────────────────────┐
    │              Externe HR-Datensysteme der Mandanten          │
    └─────────────────────────────────────────────────────────────┘
```

---

**Letzte Aktualisierung:** 29.01.2026
