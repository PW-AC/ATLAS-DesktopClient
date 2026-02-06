# BiPRO Integration - Status

**Datum:** 05.02.2026  
**Status:** ✅ **FUNKTIONIERT (Multi-VU, v0.9.2)**  
**Bearbeiter:** ACENCIA GmbH

---

## 1. Zusammenfassung

Die BiPRO 430 Integration ist **vollständig funktionsfähig** mit mehreren VUs!

| VU | Status | Besonderheiten |
|----|--------|----------------|
| **Degenia** | ✅ Funktioniert | Standard BiPRO, BestaetigeLieferungen=true |
| **VEMA** | ✅ Funktioniert | VEMA-Format, Consumer-ID erforderlich |

| Funktion | Degenia | VEMA |
|----------|---------|------|
| STS-Authentifizierung (BiPRO 410) | ✅ | ✅ |
| listShipments | ✅ | ✅ |
| getShipment | ✅ | ✅ |
| acknowledgeShipment | ✅ | - |

---

## 2. Korrekte Zugangsdaten

### VEMA-API-Credentials (FUNKTIONIEREND)
```
Username: 00101375
Password: `r4U^u?<)U"FhM6w
```

**Wichtig:** Das Portal-Passwort (ACA555) funktioniert NICHT für die API!

---

## 3. Korrekter BiPRO-Flow

Der korrekte Ablauf für Degenia:

1. **STS-Token holen** (BiPRO 410)
   - Endpoint: `https://transfer.degenia.de/X4/httpstarter/ReST/BiPRO/410_STS/UserPasswordLogin_2.6.1.1.0`
   - Authentifizierung: WSSE UsernameToken mit VEMA-Credentials
   - Ergebnis: SecurityContextToken (gültig 10 Minuten)

2. **Mit Token Transfer-Service aufrufen** (BiPRO 430)
   - Endpoint: `https://transfer.degenia.de/X4/httpstarter/ReST/BiPRO/430_Transfer/Service_2.6.1.1.0`
   - Authentifizierung: SecurityContextToken im Header
   - Operationen: listShipments, getShipment, acknowledgeShipment

---

## 4. Unterstützte BiPRO-Normen (Degenia)

| Norm | Beschreibung | Status |
|------|--------------|--------|
| 430.1 | Transfer allgemein | ✅ Aktiv |
| 430.2 | Lieferungen | ✅ Aktiv |
| 430.4 | GDV-Daten | ⚠️ Laut Degenia unterstützt, aber keine GDV-Daten bereitgestellt |
| 430.5 | Dokumente | ✅ Aktiv |
| 410 | STS (Token) | ✅ Aktiv |
| 420 | TAA (Angebot/Antrag) | ❌ Nicht aktiv (HTTP 500) |

---

## 5. Lieferungs-Kategorien

| Kategorie-Code | Bedeutung |
|----------------|-----------|
| 100002000 | Vertragsänderung |
| 100007000 | Geschäftsvorfall |
| 110011000 | Vertragsdokumente |

---

## 6. Produktions-Code

### `src/bipro/transfer_service.py`
- Vollständige Implementierung mit STS-Token-Flow
- **SharedTokenManager**: Thread-sicheres Token-Management für parallele Downloads
- **Timezone-aware Token-Validierung** (v0.9.2): `datetime.now(timezone.utc)` für korrekten Vergleich
- Verwendet `requests` (nicht zeep) für Zuverlässigkeit

### `src/bipro/rate_limiter.py` **NEU v0.9.1**
- **AdaptiveRateLimiter**: Dynamische Worker-Anpassung bei Rate Limiting
- Erkennt HTTP 429/503 und reduziert Worker-Anzahl
- Exponentielles Backoff mit automatischer Recovery

### `src/ui/bipro_view.py`
- UI-Integration mit VU-Verbindungsverwaltung
- Lieferungsliste mit Kategorie-Anzeige
- **ParallelDownloadManager**: max. 10 Worker, auto-adjustiert auf Lieferungsanzahl (~10x schneller)
- **PDF-Validierung**: Automatische Reparatur korrupter PDFs mit PyMuPDF
- **Auto-Refresh-Pause**: Cache-Refresh wird während Downloads pausiert
- **MIME-Type→Extension Mapping** (v0.9.2): `mime_to_extension()` für korrekte Dateiendungen (.pdf statt .bin)

### `src/services/data_cache.py`
- **pause_auto_refresh()**: Pausiert Auto-Refresh während langen Operationen
- **resume_auto_refresh()**: Setzt Auto-Refresh fort (Counter-basiert für verschachtelte Aufrufe)

---

## 7. Bekannte Einschränkungen

1. **Kein GDV-Datenexport:** Viktor Kerber (Degenia) bestätigte, dass GDV-Daten nicht bereitgestellt werden
2. **Token-Gültigkeit:** STS-Token läuft nach 10 Minuten ab (SharedTokenManager erneuert automatisch)
3. **Keine Kategorie-Filterung:** Der `KategorieDerLieferung`-Parameter führt zu Schema-Fehlern
4. **Rate Limiting:** Bei vielen Downloads kann HTTP 429 auftreten (AdaptiveRateLimiter passt an)
5. **PDF-Korruption:** Einige PDFs können nach MTOM-Parsing korrupt sein (automatische Reparatur aktiv)

### Gelöste Probleme (v0.9.2)

| Problem | Lösung |
|---------|--------|
| "can't compare offset-naive and offset-aware datetimes" bei Degenia | `datetime.now(timezone.utc)` in transfer_service.py |
| Dateien mit .bin Endung statt .pdf | `mime_to_extension()` mappt MIME-Type auf Endung |

---

## 8. Kontakt Degenia

**Viktor Kerber**  
degenia Versicherungsdienst AG  
Fon: 0671 84003 140  
viktor.kerber@degenia.de

---

## Changelog

- **05.02.2026:** **v0.9.2 - Degenia-Fix!** Timezone-aware Token-Validierung (`datetime.now(timezone.utc)`)
- **05.02.2026:** **MIME-Type→Extension Mapping** - Dateien erhalten korrekte Endungen (.pdf statt .bin)
- **05.02.2026:** **Worker-Anpassung** - Automatische Reduktion auf Lieferungsanzahl (3 Lieferungen = 3 Worker)
- **04.02.2026:** **VEMA-Integration funktioniert!** Multi-VU-Support implementiert
- **04.02.2026:** VU-spezifische Logik in transfer_service.py (Degenia vs. VEMA)
- **02.02.2026:** PDF-Vorschau im Dokumentenarchiv (QPdfView)
- **02.02.2026:** Automatischer Download bei VU-Auswahl
- **02.02.2026:** MTOM/XOP-Support für Binärdokumente
- **02.02.2026:** Automatische Archivierung von BiPRO-Downloads
- **02.02.2026:** STS-Token-Flow implementiert - **DURCHBRUCH!**
- **02.02.2026:** 3 Lieferungen erfolgreich abgerufen
- **30.01.2026:** Erste Tests mit Portal-Credentials (fehlgeschlagen)
