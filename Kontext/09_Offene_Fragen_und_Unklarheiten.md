# 09 - Offene Fragen und Unklarheiten

**Version:** 0.9.3  
**Analyse-Datum:** 2026-02-05

---

## UNVERSTANDEN

Bereiche, die aus dem Code nicht vollständig erschlossen werden konnten:

### 1. JWT-Token-Gültigkeit

| Frage | Status |
|-------|--------|
| Wie lange ist ein JWT-Token gültig? | UNVERSTANDEN |
| Gibt es einen Refresh-Mechanismus? | UNVERSTANDEN |
| Was passiert bei abgelaufenem Token? | App zeigt "Unauthorized", Neustart nötig |

**Quelle:** Server-seitige Logik in `api/auth.php` nicht vollständig einsehbar.

### 2. BiPRO acknowledgeShipment

| Frage | Status |
|-------|--------|
| Wird acknowledgeShipment automatisch aufgerufen? | UNVERSTANDEN |
| Was passiert mit nicht-quittierten Lieferungen? | UNVERSTANDEN |

**Quelle:** `src/bipro/transfer_service.py` hat die Methode, aber Verwendung in UI unklar.

### 3. Datenbank-Schema

| Frage | Status |
|-------|--------|
| Vollständiges Schema der MySQL-Datenbank? | UNVERSTANDEN |
| Welche Constraints existieren? | UNVERSTANDEN |

**Quelle:** Kein Schema-Export im Projekt, nur Setup-Skripte.

---

## UNVERIFIZIERT

Annahmen, die nicht durch Code bestätigt werden konnten:

### 1. BiPRO-Token-Erneuerung

| Annahme | Status |
|---------|--------|
| STS-Token wird bei Ablauf automatisch erneuert | ✅ **VERIFIZIERT (v0.9.2)** |

**Update v0.9.1:** `SharedTokenManager.get_valid_token()` prüft Token-Gültigkeit mit 1-Minute-Buffer und erneuert bei Bedarf. Thread-sicher implementiert.

**Update v0.9.2:** Token-Vergleich ist jetzt timezone-aware (`datetime.now(timezone.utc)`), da Degenia UTC-Zeitstempel zurückgibt. Ohne diesen Fix kam es zu "can't compare offset-naive and offset-aware datetimes" Fehlern.

### 2. OpenRouter Rate-Limits

| Annahme | Status |
|---------|--------|
| OpenRouter hat Rate-Limits | ✅ **VERIFIZIERT** (Retry bei 429 implementiert) |
| Aktuelle Credits reichen für Betrieb | UNVERIFIZIERT (Credits-Anzeige vorhanden) |

### 3. Server-Performance

| Annahme | Status |
|---------|--------|
| Server kann parallele Uploads verarbeiten | UNVERIFIZIERT |
| Keine Timeout-Probleme bei großen Dateien | UNVERIFIZIERT |

### 4. Encoding-Erkennung

| Annahme | Status |
|---------|--------|
| Alle GDV-Dateien sind CP1252 | UNVERIFIZIERT |
| Fallback-Kette funktioniert immer | UNVERIFIZIERT |

### 5. BiPRO Rate-Limiting (NEU v0.9.1)

| Annahme | Status |
|---------|--------|
| AdaptiveRateLimiter passt bei 429/503 korrekt an | UNVERIFIZIERT (Implementierung vorhanden) |
| Alle Lieferungen werden trotz Rate-Limiting abgerufen | UNVERIFIZIERT |

---

## Fehlende Dokumentation

### 1. API-Dokumentation

| Fehlt | Beschreibung |
|-------|--------------|
| OpenAPI/Swagger-Spec | Keine formale API-Dokumentation |
| Request/Response-Beispiele | Nur aus Code ableitbar |
| Fehler-Codes | Nicht dokumentiert |

### 2. BiPRO-Spezifika

| Fehlt | Beschreibung |
|-------|--------------|
| Vollständige WSDL-Analyse | Nur `degenia_wsdl.xml` vorhanden |
| VU-spezifische Unterschiede | Nur Degenia implementiert |
| Kategorie-Vollständigkeit | Nur 3 Kategorien bekannt |

### 3. Testabdeckung

| Fehlt | Beschreibung |
|-------|--------------|
| Unit-Tests | Keine automatisierten Tests |
| Integrationstests | Keine automatisierten Tests |
| Test-Coverage-Report | Nicht vorhanden |

---

## Widersprüchliche Implementierungen

### 1. Legacy-Archiv-View

| Beobachtung | Dateien |
|-------------|---------|
| `archive_view.py` (Legacy) existiert neben `archive_boxes_view.py` | Beide vorhanden |
| MainHub verwendet nur `archive_boxes_view.py` | `archive_view.py` nicht eingebunden |

**Frage:** Soll `archive_view.py` entfernt werden?

### 2. GDV-Editor-Views

| Beobachtung | Dateien |
|-------------|---------|
| `gdv_editor_view.py` und `main_window.py` | Beide vorhanden |
| Unterschiedliche Funktionalität | UNVERSTANDEN |

### 3. UI-Texte

| Beobachtung | Status |
|-------------|--------|
| AGENTS.md sagt "UI-Texte SOLLTEN in zentraler Datei sein" | Nicht implementiert |
| User-Rule verlangt i18n-Datei | Hardcoded Strings im Code |

---

## Offene TODOs (aus Code/Doku)

### Aus AGENTS.md

| TODO | Status |
|------|--------|
| Weitere VUs anbinden (Signal Iduna, Nürnberger) | ❌ |
| i18n für UI-Texte | ❌ |
| Unit-Tests | ❌ |
| Linter/Formatter einrichten (ruff) | ❌ |
| Logging-Konfiguration verbessern | ❌ |
| acknowledgeShipment testen | ❌ |

### Aus DEVELOPMENT.md

| TODO | Status |
|------|--------|
| PyInstaller konfigurieren | ❌ |
| Unit-Tests mit pytest | ❌ |
| Linter mit ruff | ❌ |

### Tech Debt (aus AGENTS.md)

| Issue | Beschreibung |
|-------|--------------|
| `bipro_view.py` sehr groß | **~3900+ Zeilen (v0.9.2)**, ParallelDownloadManager sollte ausgelagert werden |
| `main_window.py` zu groß | ~914 Zeilen, sollte aufgeteilt werden |
| `openrouter.py` groß | ~1500+ Zeilen, Triage/Klassifikation separieren |
| `partner_view.py` enthält Datenextraktion | Sollte nach `domain/` |
| Inline-Styles in Qt | Gegen User-Rule, CSS-Module einführen |
| **MTOM-Parser Duplikat** | `bipro_view.py` und `transfer_service.py` haben ähnlichen Code |

### Gelöste Issues (v0.9.2)

| Issue | Lösung |
|-------|--------|
| BiPRO-Downloads schlagen fehl bei Degenia | Timezone-aware datetime Vergleiche in `transfer_service.py` |
| Dateien haben .bin Endung statt .pdf | `mime_to_extension()` Funktion mappt MIME-Type auf Endung |

---

## Unklare Architektur-Entscheidungen

### 1. Warum Raw XML statt zeep?

**Beobachtung:** `transfer_service.py` verwendet `requests` mit handgeschriebenem XML.

**Kommentar aus Code:**
> "zeep ist zu strikt für Degenia"

**Frage:** Was genau hat zeep nicht akzeptiert?

### 2. ~~Warum kein Token-Refresh?~~ (GEKLÄRT v0.9.1)

**Update v0.9.1:** `SharedTokenManager` implementiert automatische Token-Erneuerung mit 1-Minute-Buffer vor Ablauf. Thread-sicher für parallele Downloads.

### 3. Warum parallele Verarbeitung mit ThreadPoolExecutor statt asyncio?

**Beobachtung:** `document_processor.py` und `ParallelDownloadManager` verwenden Threads.

**Vermutete Antwort:** 
- Qt-Kompatibilität (QThread-basierte Worker, Signale)
- Blockierende I/O-Operationen (requests, Datei-Operationen)
- `asyncio` würde komplettes Redesign erfordern

### 4. Warum MTOM-Parser in bipro_view.py dupliziert? (NEU v0.9.1)

**Beobachtung:** `ParallelDownloadManager` hat eigene `_parse_mtom_response()` und `_split_multipart()`.

**Frage:** Konsolidieren mit `transfer_service.py`?

---

## Empfohlene Klärungen

| Priorität | Frage | Ansprechpartner |
|-----------|-------|-----------------|
| Hoch | JWT-Token-Gültigkeit und Refresh | Backend-Entwickler |
| Hoch | acknowledgeShipment-Workflow | Viktor Kerber (Degenia) |
| Mittel | Legacy-Views entfernen? | Projektleitung |
| Mittel | i18n-Strategie | Projektleitung |
| Niedrig | zeep-Probleme dokumentieren | - |

---

## Anmerkungen zur Analyse

Diese Dokumentation basiert auf:
- Statischer Code-Analyse
- Vorhandener Dokumentation (README, AGENTS.md, docs/)
- Strukturanalyse der Dateien

**Nicht durchgeführt:**
- Ausführung der Anwendung
- Netzwerk-Analyse
- Datenbank-Inspektion
- Penetrationstests
