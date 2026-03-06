# Aktuelle Risiken und Regressionen

## Bekannte Regressionen durch Fixes

| Befund-ID | Regression | Auswirkung | Mitigation |
|-----------|------------|------------|------------|
| SV-001 | Bestehende Sessions invalidiert | Benutzer müssen sich neu anmelden | Benutzer über Änderung informieren |
| SV-002 | employers.json Format ändert sich | Bestehende Daten werden automatisch migriert | Automatische Migration beim ersten Zugriff |
| SV-004 | API-Calls benötigen CSRF-Header | JavaScript fetch() muss angepasst werden | base.html enthält Beispiel-Code |
| SV-007 | secrets.json Format ändert sich | PAT wird automatisch migriert | Automatische Migration beim ersten Speichern |
| SV-012 | Passwort-Policy | Neue Passwörter müssen komplexer sein | Policy in UI dokumentieren |

## Offene Risiken (BLOCKED Befunde)

| Risiko | Schwere | Befund | Mitigation bis zur Behebung |
|--------|---------|--------|----------------------------|
| Unverschlüsselter Transport | KRITISCH | SV-003 | VPN verwenden, keine sensiblen Daten über öffentliche Netze |
| Externe JS ohne SRI | MITTEL | SV-019 | Google Fonts sind vertrauenswürdig, Risiko akzeptabel |
| Update ohne Signatur | MITTEL | SV-017 | Manuelles Update-Verfahren, keine Auto-Updates in Produktion |
| Keine CI/CD | NIEDRIG | SV-024 | Manuelle Tests vor Deployment |
| Monolithischer Code | NIEDRIG | SV-022 | Technische Schulden dokumentiert |
| Keine Lockfile | INFO | SV-026 | requirements.txt mit Versionen ausreichend |

## Empfehlungen für nächste Schritte

### Priorität 1: HTTPS einrichten
1. SSL-Zertifikat besorgen (Let's Encrypt)
2. nginx als Reverse Proxy konfigurieren
3. HTTP-zu-HTTPS-Redirect einrichten
4. `HTTPS_ENABLED=true` setzen

### Priorität 2: CI/CD Pipeline
1. GitHub Repository einrichten
2. GitHub Actions Workflow erstellen
3. Automatische Tests bei Push
4. Deployment-Pipeline konfigurieren

### Priorität 3: Code-Refactoring
1. `routes.py` für Flask-Routen erstellen
2. `providers.py` für API-Provider extrahieren
3. `utils.py` für Hilfsfunktionen
4. Tests erweitern

## Qualitäts-Gates (Alle erfüllt)

- [x] Kein SV bleibt unbehandelt ohne BLOCKED-Begründung
- [x] Kein Fix ohne dokumentierten Verifikationsversuch
- [x] Doku entspricht dem Code
- [x] Keine Secrets im Repo
- [x] .gitignore unverändert (keine neuen Artefakte die Ausschluss erfordern)

---

**Letzte Aktualisierung:** 28.01.2026
