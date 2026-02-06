# 01 - Projektüberblick

**Version:** 0.9.3  
**Analyse-Datum:** 2026-02-05

---

## Was ist das Projekt?

Das **BiPRO-GDV Tool** ist eine Desktop-Anwendung mit Server-Backend für Versicherungsvermittler. Es kombiniert drei Hauptfunktionen:

1. **BiPRO Datenabruf** - Automatisierter Abruf von Lieferungen (Dokumente, GDV-Daten) von Versicherungsunternehmen über BiPRO-Schnittstellen
2. **Dokumentenarchiv mit Box-System** - Zentrales Archiv mit KI-gestützter Klassifikation und automatischer Verarbeitung
3. **GDV-Editor** - Erstellen, Anzeigen und Bearbeiten von GDV-Datensätzen (Branchenstandard-Format)

---

## Zweck

| Ziel | Beschreibung | Status |
|------|--------------|--------|
| **Primär** | BiPRO-Daten automatisiert von Versicherern abrufen | ✅ Funktioniert (Degenia) |
| **Sekundär** | Zentrales Dokumentenarchiv für Team (2-5 Personen) | ✅ Funktioniert |
| **Tertiär** | GDV-Dateien visualisieren und bearbeiten | ✅ Funktioniert |

---

## Zielgruppe

- **Primär:** Versicherungsvermittler der ACENCIA GmbH
- **Team-Größe:** 2-5 Personen
- **Technisches Niveau:** Endanwender (keine IT-Kenntnisse erforderlich)

---

## Explizit NICHT Ziel

| Nicht-Ziel | Begründung |
|------------|------------|
| Web-Oberfläche | Desktop-App mit Server-Backend ist gewählt |
| XML/JSON-GDV-Varianten | Nur klassisches Fixed-Width-Format (256 Bytes/Zeile) |
| Automatische Abrufe ohne Benutzer | Zunächst nur manuelle Auslösung |
| Multi-Mandanten | Einzelne Firma (ACENCIA GmbH) |

---

## Technische Eckdaten

| Aspekt | Details |
|--------|---------|
| **Plattform** | Windows 10/11 (Desktop) |
| **Sprache** | Python 3.10+ |
| **GUI Framework** | PySide6 (Qt 6) |
| **Backend** | PHP 7.4+ REST API auf Strato Webspace |
| **Datenbank** | MySQL 8.0 |
| **KI** | OpenRouter API (GPT-4o für PDF-Klassifikation) |
| **BiPRO** | Raw XML mit requests (kein zeep) |

---

## Versionsverlauf

| Version | Datum | Meilensteine |
|---------|-------|--------------|
| v0.1.0 | - | Initiale Version, GDV-Dateien öffnen |
| v0.2.0 | - | Benutzer- und Experten-Ansicht, Speichern |
| v0.3.0 | Jan 2025 | Partner-Ansicht, Teildatensatz-Unterstützung |
| v0.4.0 | Jan 2026 | BiPRO-Client Grundgerüst, Server-API |
| v0.5.0 | Feb 2026 | BiPRO funktioniert (Degenia), Dokumentenarchiv |
| v0.6.0 | Feb 2026 | KI-basierte PDF-Analyse (OpenRouter) |
| v0.7.0 | Feb 2026 | Box-System (7 Boxen), automatische Klassifikation |
| v0.8.0 | Feb 2026 | Kranken-Box, Multi-Upload, parallele Verarbeitung |
| v0.9.0 | Feb 2026 | BiPRO-Code-Vorsortierung, Token-optimierte KI |
| v0.9.1 | 04.02.2026 | Parallele BiPRO-Downloads, Rate Limiting, Auto-Refresh-Kontrolle |
| v0.9.2 | 05.02.2026 | Timezone-aware Token-Validierung, MIME-Type Fixes |
| **v0.9.3** | **05.02.2026** | **Kosten-Tracking, erweiterte Sach-Keywords, Courtage-Benennung** |

---

## Scope der Analyse

Diese Dokumentation umfasst:

- Desktop-Anwendung (`src/`)
- Server-API (`BiPro-Webspace Spiegelung Live/api/`)
- Konfiguration und Abhängigkeiten
- Testdaten (`testdata/`)

**Nicht analysiert:**
- Inhalte von `Projekt Ziel/` (Konzepte, E-Mail-Verkehr)
- Echte Produktionsdaten
