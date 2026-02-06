# BiPro-Webspace Spiegelung Live

## WICHTIGER HINWEIS

**Dieser Ordner ist LIVE mit dem Strato Webspace synchronisiert!**

Alle Änderungen in diesem Ordner werden in Echtzeit auf den Webspace übertragen.

| Lokal | Webspace |
|-------|----------|
| `BiPro-Webspace Spiegelung Live/` | `BiPro/` |
| Domain: | `https://acencia.info/` |

## Synchronisierung

- Tool: WinSCP (oder ähnlich)
- Richtung: Lokal → Webspace (Echtzeit)
- **VORSICHT:** Gelöschte Dateien werden auch auf dem Server gelöscht!

## Sicherheitsrelevante Dateien

Die folgenden Dateien enthalten sensible Daten und sind per `.htaccess` geschützt:

- `api/config.php` - Datenbank-Credentials, Master-Key
- `api/lib/` - Interne PHP-Bibliotheken

**Diese Dateien sind NICHT direkt über HTTP aufrufbar.**

## Datenbank

- Server: `database-5019508812.webspace-host.com`
- Datenbank: `dbs15252975`
- Typ: MySQL 8

## API-Endpunkte

Base-URL: `https://acencia.info/api/`

| Endpunkt | Beschreibung |
|----------|--------------|
| `/api/auth/login` | Login |
| `/api/documents` | Dokumente |
| `/api/gdv/` | GDV-Operationen |
| `/api/shipments` | Lieferungen |

## Ordnerstruktur

```
BiPro-Webspace Spiegelung Live/
├── api/
│   ├── .htaccess          # URL-Rewriting, Schutz
│   ├── index.php          # API-Router
│   ├── config.php         # Credentials (GESCHÜTZT!)
│   ├── auth.php           # Auth-Endpunkte
│   ├── documents.php      # Dokument-Endpunkte
│   ├── gdv.php            # GDV-Endpunkte
│   ├── credentials.php    # VU-Credentials
│   ├── shipments.php      # Lieferungen
│   └── lib/
│       ├── db.php         # Datenbank-Wrapper
│       ├── jwt.php        # Token-Handling
│       └── crypto.php     # Verschlüsselung
├── dokumente/             # Datei-Storage
│   └── .htaccess          # Deny all (nicht web-zugänglich!)
├── setup/                 # DB-Setup-Skripte (temporär)
│   └── *.php              # Nach Ausführung löschen!
└── .htaccess              # Haupt-Config
```
