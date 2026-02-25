# Repo-Trennungsplan

> Status: **Vorbereitet** | Ausfuehrung: Spaeter manuell
> Stand: 25.02.2026

## Ziel

Das aktuelle Mono-Repo wird in zwei separate Repositories aufgeteilt:

1. **acencia-atlas-desktop** -- Python Desktop-App
2. **acencia-atlas-api** -- PHP REST-API

## Warum Trennung?

- `BiPro-Webspace Spiegelung Live/` ist **LIVE synchronisiert** mit dem Strato-Server
- Desktop-Code und API-Code haben unterschiedliche Deployment-Zyklen
- Vermeidung von versehentlichen API-Aenderungen durch Desktop-Commits
- Separate Berechtigungen und CI/CD moeglich

## Ausfuehrungsschritte

### Schritt 1: Desktop-Repo bereinigen

Das aktuelle Repo (`ATLAS-DesktopClient`) wird zum reinen Desktop-Repo:

```bash
# BiPro-Webspace Spiegelung Live/ aus Git-Tracking entfernen (NICHT vom Dateisystem!)
git rm -r --cached "BiPro-Webspace Spiegelung Live/"
# .gitignore ergaenzen
echo "BiPro-Webspace Spiegelung Live/" >> .gitignore
git commit -m "chore: API-Code aus Desktop-Repo entfernen (bleibt lokal fuer Sync)"
```

**VORSICHT**: Die Dateien bleiben auf der Festplatte und im Strato-Sync!

### Schritt 2: API-Repo erstellen

Neues GitHub-Repo: `acencia-atlas-api` (private)

```
acencia-atlas-api/
  api/              # <- Inhalt von BiPro-Webspace Spiegelung Live/api/
  setup/            # <- Migrationen (Kopie)
  config.example.php
  .gitignore
  README.md
```

**.gitignore fuer API-Repo:**

```gitignore
config.php
dokumente/
releases/
*.log
```

### Schritt 3: Strato-Sync umkonfigurieren

- Aktuell: `BiPro-Webspace Spiegelung Live/` synchronisiert direkt
- Neu: API-Repo wird separat synchronisiert
- Methode: FileZilla / rsync / Strato WebFTP

### Schritt 4: CI/CD fuer API-Repo

- Optional: Eigene GitHub Actions fuer PHP-Linting
- Deployment via Strato-Sync (manuell oder automatisiert)

## Risiken

| Risiko | Mitigation |
|--------|------------|
| Setup-Dateien (Migrationen) muessen in beiden Repos konsistent sein | Migrationen leben im API-Repo, Desktop-Repo hat Kopie |
| Strato-Sync-Unterbrechung | Umstellung schrittweise, erst testen |
| Bestehende Git-History geht fuer API-Dateien verloren | `git filter-branch` oder `git subtree split` verwenden |

## Voraussetzungen vor Ausfuehrung

- [x] Alle Governance-Aenderungen committed und gepushed
- [x] config.example.php vorhanden
- [x] .gitignore gehaertet
- [ ] Backup des gesamten Repos
- [ ] Strato-Sync getestet (manueller Upload eines Testfiles)
- [ ] API-Repo auf GitHub erstellt

## Zeitplan

Dieser Schritt wird **nicht automatisch** ausgefuehrt. Er erfordert:
1. Manuelle Vorbereitung und Backup
2. Testlauf mit einem kleinen Datei-Sync
3. Koordination mit dem Strato-Sync-Mechanismus
