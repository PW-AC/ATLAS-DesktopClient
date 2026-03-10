# Dev-Auth: Automatischer Admin-Login im Entwicklungsmodus

Ermoeglicht passwortlosen Login als Admin, wenn der Client mit `python run.py` gestartet wird.
Funktioniert wie SSH-Pubkey-Auth: Challenge-Response mit RSA-Signatur, gegen jeden Server (lokal oder live).

## Sicherheitsmodell (identisch mit SSH)

| Eigenschaft | Beschreibung |
|-------------|-------------|
| **Private Key** | Verlaesst nie den Entwicklungsrechner |
| **Public Key** | Muss explizit auf dem Server eingetragen sein |
| **Challenge-Response** | Beweist Besitz des Private Key, kein Replay moeglich |
| **Challenge-Ablauf** | 60 Sekunden |
| **Logging** | Jeder Versuch (Erfolg + Ablehnung) im Activity-Log mit IP |
| **Kein Passwort** | Wird nie uebertragen |

## Einmaliges Setup (pro Entwicklungsrechner)

### 1. Schluesselpaar erzeugen

```powershell
cd ATLAS-DesktopClient
python setup_dev_auth.py
```

Erzeugt:
- `dev_keys/atlas_dev.key` (privat, bleibt auf diesem Rechner, nie committen)
- `dev_keys/atlas_dev.pub` (oeffentlich)

### 2. Public Key auf dem Server eintragen

#### Lokaler Dev-Server

Public Key nach `Local_dev_Backend/config/dev_auth_keys.txt` kopieren:

```powershell
Get-Content dev_keys\atlas_dev.pub | Set-Content "..\Local_dev_Backend\config\dev_auth_keys.txt" -Encoding UTF8
```

#### Live-Server (acencia.info)

1. Per SSH auf den Server verbinden
2. Datei `/var/www/atlas/config/dev_auth_keys.txt` anlegen
3. Inhalt von `dev_keys/atlas_dev.pub` einfuegen

Mehrere Entwickler: Mehrere Public Keys untereinander in die gleiche Datei.

### 3. Testen

```powershell
python run.py
```

## Ablauf

1. `python run.py` starten
2. Client erkennt Dev-Modus (nicht gefrorene EXE)
3. `dev_keys/atlas_dev.key` wird gelesen
4. Challenge vom Server holen, mit Private Key signieren, zuruecksenden
5. Server prueft: Key autorisiert? Signatur gueltig? Challenge noch frisch?
6. Bei Erfolg: JWT fuer Admin-User, automatischer Login ohne Dialog

## Wann funktioniert Dev-Auth NICHT?

- **EXE-Build** (sys.frozen = True) → nur normaler Login
- **Kein Private Key** (dev_keys/atlas_dev.key fehlt) → normaler Login
- **Key nicht autorisiert** (Public Key nicht auf Server) → normaler Login
- **Server nicht erreichbar** → Login-Dialog zeigt Fehler

## Reproduzierbarkeit

- **Neuer Rechner**: Schritte 1–2 wiederholen (ca. 2 Minuten)
- **Neuer Entwickler**: Eigenes Keypair erzeugen, eigenen Public Key auf Server eintragen
- **Bestehender Rechner**: Kein erneutes Setup noetig
