# Task 02: JWT 401 Auto-Refresh (P0)

## Problem

Wenn der JWT-Token während einer laufenden Operation abläuft, wirft `APIClient._handle_response()` sofort `APIError(status_code=401)`. Es gibt keinen Token-Refresh-Mechanismus. Der User muss die App neu starten und sich erneut einloggen.

## Root Cause

- `APIClient` in `src/api/client.py` hat keine Referenz zu `AuthAPI` 
- `_handle_response()` (Zeile 80-101) wirft bei 401 sofort eine Exception
- `AuthAPI` in `src/api/auth.py` hat keine `refresh_token()` Methode
- Das PHP-Backend hat keinen Token-Refresh-Endpoint (nur `/auth/login` und `/auth/verify`)

## Technische Analyse

- JWT-Token hat `expires_in` (Default 1800s = 30 Minuten)
- Langlaufende Operationen (Batch-Processing, Multi-Download mit KI-Klassifikation) können >30 Minuten dauern
- `AuthAPI.verify_token()` existiert (prüft via `/auth/verify`), hat aber keinen Refresh

Da kein Server-seitiger Refresh-Endpoint existiert, implementieren wir:
1. **Proaktive Token-Validierung**: Vor kritischen Operationen Token prüfen
2. **401-Retry mit Re-Login**: Bei 401 automatisch Token erneuern via gespeichertem Credential

## Zielzustand

- `APIClient` kann bei 401 automatisch einen neuen Token holen
- Token wird proaktiv geprüft vor langlaufenden Operationen
- Transparenter Retry: Caller bemerkt nichts vom Token-Refresh
- Kein gespeichertes Passwort im Speicher nötig (nutze Token-File wenn vorhanden)

## Randbedingungen

- PHP-Backend hat KEINEN `/auth/refresh` Endpoint → wir können nur via `/auth/verify` prüfen und bei Bedarf Re-Login vorschlagen
- **Realistischer Ansatz**: Da kein Refresh-Endpoint existiert, implementieren wir einen **proaktiven Expiry-Check** + einen **einmaligen automatischen Re-Login mit gespeichertem Token**
- Thread-Safety: `APIClient` kann von mehreren Threads genutzt werden → Token-Refresh darf kein Race verursachen

## Performance-Vorgaben

- Proaktiver Check: max. 1 zusätzlicher HTTP-Call alle 5 Minuten
- 401-Retry: max. 1 Retry pro Request

## Thread-Safety-Vorgaben

- Token-Refresh muss atomar sein (nur ein Thread refreshed gleichzeitig)
- Andere Threads warten auf neuen Token (nicht parallel refreshen)

## Nicht-Ziele

- Kein neuer PHP-Endpoint (Backend bleibt unverändert)
- Kein Passwort-Speicher im RAM
- Keine UI-Änderungen (kein Popup "Session abgelaufen")
