# Kontext-Dokumentation - ACENCIA Hub

**Projekt:** ACENCIA Hub - Multi-HR Integrator  
**Erstellungsdatum:** 28.01.2026  
**Letzte Aktualisierung:** 29.01.2026  
**Agent:** Kontext-Agent (Read-Only, Analyse, Synthese)  
**Zweck:** Vollständiges Verständnis des Projekts für nachfolgende Agenten  
**Version:** 1.1.0 (Trigger-System)

---

## Dokumentenübersicht

| Nr. | Dokument | Inhalt |
|-----|----------|--------|
| 00 | **INDEX.md** (dieses Dokument) | Navigation und Übersicht |
| 01 | [Projektueberblick.md](01_Projektueberblick.md) | Was ist das Projekt? Zielgruppe, Einsatzzweck |
| 02 | [System_und_Architektur.md](02_System_und_Architektur.md) | Komponenten, Datenflüsse, Tech-Stack |
| 03 | [Domain_und_Begriffe.md](03_Domain_und_Begriffe.md) | Fachbegriffe, Definitionen aus dem Code |
| 04 | [Code_Struktur_und_Moduluebersicht.md](04_Code_Struktur_und_Moduluebersicht.md) | Dateien, Module, Klassen, Verantwortlichkeiten |
| 05 | [Laufzeit_und_Flows.md](05_Laufzeit_und_Flows.md) | Typische Abläufe, Start bis Shutdown |
| 06 | [Konfiguration_und_Abhaengigkeiten.md](06_Konfiguration_und_Abhaengigkeiten.md) | Konfigurations-Dateien, externe Dependencies |
| 07 | [Build_Run_Test_Deployment.md](07_Build_Run_Test_Deployment.md) | Befehle, Artefakte, Umgebungen |
| 08 | [Sicherheits_und_Randannahmen.md](08_Sicherheits_und_Randannahmen.md) | Security-Mechanismen, implizite Annahmen |
| 09 | [Offene_Fragen_und_Unklarheiten.md](09_Offene_Fragen_und_Unklarheiten.md) | Ungeklärtes, UNVERIFIZIERT-Markierungen |

---

## Schnellzugriff

### Projekttyp
Flask-basierte **Web-Anwendung** (Single-Page-Application mit Server-Side-Rendering)

### Hauptfunktion
Zentrales Dashboard zur Verbindung mehrerer HR-Provider-APIs (Personio, HRworks, SageHR) für Mitarbeiterdatenverwaltung, Statistiken, Exporte und **automatisierte Trigger-Aktionen** bei Datenänderungen.

### Tech-Stack
- Python 3.8+ / Flask 3.0.3
- Jinja2 Templates
- Waitress WSGI-Server
- JSON-Datenspeicherung
- requests für API-Kommunikation
- openpyxl für Excel-Exporte
- smtplib für E-Mail-Versand (Trigger)

### Entry Points
| Entry Point | Beschreibung |
|-------------|-------------|
| `run.py` | Produktions-Entry-Point mit Waitress |
| `start.bat` | Windows-Starter (Batch-Skript) |
| `acencia_hub/app.py` | Direkter Flask-Start (Entwicklung) |

### Wichtigste Dateien
| Datei | Zeilen | Zweck |
|-------|--------|-------|
| `app.py` | ~5326 | Gesamte Anwendungslogik, Routen, Provider, Trigger-System |
| `updater.py` | ~165 | Automatische Updates von GitHub |
| `employers.json` | dynamisch | Arbeitgeber-Konfiguration |
| `users.json` | dynamisch | Benutzerdatenbank |
| `triggers.json` | dynamisch | Trigger-Konfiguration und SMTP |
| `trigger_log.json` | dynamisch | Trigger-Ausführungsprotokoll |

### Haupt-Klassen (app.py)
| Klasse | Zeile | Zweck |
|--------|-------|-------|
| `EmployerStore` | 460 | Arbeitgeber-Persistenz (Singleton) |
| `TriggerStore` | 624 | Trigger-Konfiguration (Singleton) |
| `TriggerLogStore` | 975 | Trigger-Protokollierung (Singleton) |
| `TriggerEngine` | 1164 | Trigger-Auswertung und -Ausführung |
| `EmailAction` | 1602 | E-Mail-Versand via SMTP |
| `APIAction` | 1742 | HTTP-Requests an externe APIs |
| `BaseProvider` | 1837 | Abstrakte Provider-Basisklasse |
| `HRworksProvider` | 1889 | HRworks API-Integration |
| `SageHrProvider` | 2142 | Mock-Provider |
| `PersonioProvider` | 2186 | Personio API-Integration |
| `ProviderFactory` | 2363 | Provider-Instanziierung |

---

## Leseanleitung

1. **Für Überblick:** Dokumente 01 und 02 lesen
2. **Für Entwicklung:** Dokumente 04, 05 und 07 lesen
3. **Für Audit/Security:** Dokumente 08 und 09 lesen
4. **Für Domain-Verständnis:** Dokument 03 lesen
5. **Für Trigger-System:** docs/TRIGGERS.md und AGENTS.md Sektion 16 lesen

---

## Hinweise

- Diese Dokumentation ist **deskriptiv**, nicht evaluierend
- Alle Aussagen basieren auf **statischer Code-Analyse**
- **UNVERIFIZIERT**: Aussagen, die nicht durch Code belegt werden konnten
- Keine Empfehlungen oder Bewertungen enthalten

---

## Änderungshistorie

| Datum | Änderung |
|-------|----------|
| 28.01.2026 | Initiale Erstellung |
| 29.01.2026 | Zeilenzahlen aktualisiert (~5326 statt ~3400), Trigger-Klassen dokumentiert |

---

**Letzte Aktualisierung:** 29.01.2026
