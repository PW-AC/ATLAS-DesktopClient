# ACENCIA Hub - Multi-HR Integrator

Eine moderne Flask-basierte Web-Anwendung, die verschiedene HR-Provider APIs (Personio, HRworks, SageHR) verbindet und als zentrales Dashboard für Mitarbeiterdaten, Statistiken und Exporte fungiert.

## 🚀 Features

### Arbeitgeber-Verwaltung
- **Multi-Mandanten-System**: Verwalten Sie mehrere Arbeitgeber mit individuellen Provider-Konfigurationen
- **Dynamische Formulare**: Automatische Anpassung der Eingabefelder je nach Provider-Typ
- **Provider-Unterstützung**: Personio, HRworks, SageHR (Mock)

### Mitarbeiter-Management
- **Übersichtliche Mitarbeiterliste**: Durchsuchbar und filterbar nach Status (Aktiv, Ehemalig, Alle)
- **Detaillierte Mitarbeiteransicht**: Vollständige Anzeige aller normalisierten Daten aus dem Quellsystem
- **Echtzeitdaten**: Direkte Verbindung zu den HR-Provider APIs

### Datenanalyse & Statistiken
- **Standard-Statistiken**: KPIs zu Altersstruktur, Geschlechterverteilung, Fluktuation
- **Langzeit-Analyse**: Historische Trends basierend auf Snapshots
- **Interaktive Diagramme**: Visualisierung wichtiger Kennzahlen
- **Export-Funktionen**: TXT-Export für beide Statistik-Modi

### Export-System
- **Standard-Export**: Vollumfänglicher XLSX-Export aller Mitarbeiterdaten
- **Delta-SCS-Export**: Spezieller Export nur für neue und geänderte Mitarbeiter
- **Snapshot-System**: Robuste Verfolgung von Datenänderungen über Zeit
- **Vergangene Exporte**: Zugriff auf alle zuvor generierten Exporte

### Snapshot-Management
- **Automatische Snapshots**: Erstellung bei jedem Delta-Export
- **Snapshot-Vergleich**: Detaillierter Vergleich zwischen verschiedenen Zeitpunkten
- **Änderungsverfolgung**: Identifikation von hinzugefügten, entfernten und geänderten Mitarbeitern

### Benutzerverwaltung
- **Multi-User-System**: Unterstützung mehrerer Benutzer mit individuellen Einstellungen
- **Master-Benutzer**: Erweiterte Rechte für Benutzer- und Systemverwaltung
- **Theme-Unterstützung**: Hell- und Dunkelmodus
- **Sicherheit**: Passwort-Hashing und Session-Management

### Trigger-System (NEU)
- **Automatisierte Aktionen**: E-Mails und API-Aufrufe bei Datenänderungen
- **Flexible Bedingungen**: Status-Änderungen, Feldänderungen, neue/entfernte Mitarbeiter
- **Dynamische Templates**: Mustache-Syntax für personalisierte Inhalte
- **Protokollierung**: Vollständiges Ausführungsprotokoll mit Retry-Funktion
- **Arbeitgeber-Ausschlüsse**: Trigger pro Arbeitgeber aktivieren/deaktivieren

### System-Features
- **Automatische Updates**: GitHub-Integration für Updates
- **Logging-System**: Umfassende Protokollierung aller Aktionen
- **Responsive Design**: Moderne UI mit Design-Token-System
- **API-Endpunkte**: RESTful APIs für Frontend-Integration

## 📋 Voraussetzungen

- **Python**: 3.8 oder höher
- **pip**: Paketmanager für Python
- **venv**: Virtuelle Umgebung (empfohlen)

## 🛠️ Installation

### 1. Repository klonen
```bash
git clone <repository-url>
cd <repository-ordner>
```

### 2. Virtuelle Umgebung erstellen und aktivieren
```bash
# Virtuelle Umgebung erstellen
python -m venv venv

# Aktivieren (Windows)
venv\Scripts\activate

# Aktivieren (macOS / Linux)
source venv/bin/activate
```

### 3. Abhängigkeiten installieren
```bash
pip install -r requirements.txt
```

## 🚀 Anwendung starten

### Entwicklungsserver
```bash
python acencia_hub/app.py
```

Die Anwendung ist anschließend erreichbar unter: **http://127.0.0.1:5001**

### Produktionsserver (Windows)
Für eine robustere Ausführung mit Netzwerkzugriff:

```bash
start.bat
```

Dieses Skript:
- Aktiviert automatisch die virtuelle Umgebung
- Installiert/aktualisiert alle Abhängigkeiten
- Zeigt lokale IP-Adressen für Netzwerkzugriff an
- Startet den Server mit Waitress (produktionsreif)

## 📁 Projektstruktur

```
acencia_hub/
├── __init__.py          # Modul-Dokumentation
├── app.py              # Hauptanwendung mit allen Routen und Klassen
├── updater.py          # Automatische Update-Funktionalität
├── data/               # Benutzer- und Konfigurationsdaten
│   ├── users.json      # Benutzerdatenbank
│   ├── secrets.json    # Geheimnisse (GitHub PAT, etc.)
│   └── force_logout.txt # Erzwungenes Abmelden
├── static/             # Statische Dateien
│   └── css/           # Stylesheets mit Design-Token-System
├── templates/          # Jinja2-Templates
│   ├── base.html      # Basis-Template
│   ├── index.html     # Hauptseite
│   ├── login.html     # Anmeldeseite
│   └── ...            # Weitere Templates
├── _snapshots/        # Automatisch erstellte Datensnapshots
├── _history/          # Rohdaten-Backup der API-Antworten
└── exports/           # Generierte Export-Dateien
```

## 🔧 Konfiguration

### Arbeitgeber hinzufügen
1. Navigieren Sie zur Hauptseite
2. Klicken Sie auf "Arbeitgeber hinzufügen"
3. Wählen Sie den Provider-Typ (Personio, HRworks, SageHR)
4. Geben Sie die entsprechenden Zugangsdaten ein
5. Speichern Sie die Konfiguration

### Provider-spezifische Einstellungen

#### Personio
- **Client ID**: Ihre Personio Client ID
- **Client Secret**: Ihr Personio Client Secret

#### HRworks
- **Access Key**: Ihr HRworks Access Key
- **Secret Key**: Ihr HRworks Secret Key
- **Demo-Modus**: Aktivieren für Testumgebung

#### SageHR (Mock)
- **Access Key**: Beliebiger Wert (wird ignoriert)
- **Slug**: Beliebiger Wert (wird ignoriert)

## 📊 Verwendung

### Mitarbeiter anzeigen
1. Wählen Sie einen Arbeitgeber aus der Hauptseite
2. Die Mitarbeiterliste wird automatisch geladen
3. Verwenden Sie Filter für Status (Aktiv/Ehemalig/Alle)
4. Klicken Sie auf einen Mitarbeiter für Details

### Statistiken analysieren
1. Navigieren Sie zum "Statistiken"-Tab
2. Wechseln Sie zwischen "Standard" und "Langzeit"-Ansicht
3. Exportieren Sie Statistiken als TXT-Datei

### Exporte generieren
1. Gehen Sie zum "Exporte"-Tab
2. **Standard-Export**: Vollständige Excel-Datei aller Daten
3. **Delta-SCS-Export**: Nur neue/geänderte Mitarbeiter
4. **Vergangene Exporte**: Zugriff auf alle zuvor generierten Exporte

### Snapshots vergleichen
1. Navigieren Sie zum "Snapshots"-Tab
2. Wählen Sie zwei Snapshots zum Vergleichen aus
3. Sehen Sie detaillierte Änderungen zwischen den Zeitpunkten

### Trigger einrichten (NEU)
1. Gehen Sie zu "Einstellungen" → "Trigger verwalten" (nur Master-Benutzer)
2. Konfigurieren Sie zuerst die SMTP-Einstellungen für E-Mail-Versand
3. Erstellen Sie einen neuen Trigger:
   - Name vergeben
   - Event wählen (z.B. "Mitarbeiter geändert")
   - Bedingungen definieren (z.B. "Status" ändert von "Aktiv" zu "Inaktiv")
   - Aktion konfigurieren (E-Mail oder API-Aufruf)
4. Trigger werden automatisch beim Delta-Export ausgewertet
5. Protokoll einsehen unter "Ausführungsprotokoll"

**Beispiel-Trigger:** E-Mail bei Mitarbeiter-Austritt
- Event: "Mitarbeiter geändert"
- Bedingung: Feld "Status", Operator "ändert von/zu", Von "Aktiv", Zu "Inaktiv"
- Aktion: E-Mail an hr@firma.de mit Betreff "{{Vorname}} {{Name}} ausgetreten"

## 🔐 Benutzerverwaltung

### Master-Benutzer erstellen
1. Melden Sie sich als Master-Benutzer an
2. Gehen Sie zu "Einstellungen"
3. Fügen Sie neue Benutzer hinzu
4. Verwalten Sie Benutzerrechte und -einstellungen

### Theme wechseln
- Verwenden Sie den Theme-Schalter in der Kopfzeile
- Einstellungen werden automatisch gespeichert

## 🔄 Updates

### Automatische Updates
1. Gehen Sie zu "Einstellungen" (als Master-Benutzer)
2. Fügen Sie Ihr GitHub Personal Access Token hinzu
3. Updates werden automatisch über GitHub bezogen

### Manuelle Updates
```bash
git pull origin main
pip install -r requirements.txt
```

## 🐛 Fehlerbehebung

### Häufige Probleme

#### Provider-Verbindungsfehler
- Überprüfen Sie Ihre Zugangsdaten
- Stellen Sie sicher, dass die API-Endpunkte erreichbar sind
- Prüfen Sie die Netzwerkverbindung

#### Authentifizierungsfehler
- Überprüfen Sie Benutzername und Passwort
- Stellen Sie sicher, dass der Benutzer aktiv ist
- Kontaktieren Sie einen Master-Benutzer

#### Export-Probleme
- Überprüfen Sie die Schreibberechtigungen im Export-Verzeichnis
- Stellen Sie sicher, dass genügend Speicherplatz vorhanden ist

### Logs anzeigen
- Master-Benutzer können System-Logs über die Einstellungen einsehen
- Log-Dateien werden in `server.log` gespeichert

## 🤝 Entwicklung

### Code-Standards
- Alle Funktionen und Klassen sind vollständig dokumentiert
- Verwendung von Type Hints für bessere Code-Qualität
- Konsistente Namenskonventionen

### Design-System
- Verwendung von CSS-Design-Tokens für konsistente UI
- Responsive Design für alle Bildschirmgrößen
- Unterstützung für Hell- und Dunkelmodus

### API-Dokumentation
- RESTful API-Endpunkte für Frontend-Integration
- JSON-Responses für alle API-Calls
- Umfassende Fehlerbehandlung

## 📝 Lizenz

Dieses Projekt ist proprietär und gehört Acencia.

## 👥 Support

Bei Fragen oder Problemen wenden Sie sich an das Acencia-Team.

## 📚 Weitere Dokumentation

- **[AGENTS.md](AGENTS.md)** - Detaillierte technische Dokumentation für KI-Agenten und Entwickler
- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** - Architektur-Übersicht und Komponenten
- **[docs/TRIGGERS.md](docs/TRIGGERS.md)** - Trigger-System Referenz (NEU)
- **[docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)** - Entwicklungs-Setup und Workflow
- **[docs/CONFIGURATION.md](docs/CONFIGURATION.md)** - Alle Konfigurationsoptionen
- **[README_DESIGN.md](README_DESIGN.md)** - Design-System-Dokumentation

---

**Version**: 1.1.0  
**Letzte Aktualisierung**: 28.01.2026 (Trigger-System)  
**Entwickelt von**: Acencia Team