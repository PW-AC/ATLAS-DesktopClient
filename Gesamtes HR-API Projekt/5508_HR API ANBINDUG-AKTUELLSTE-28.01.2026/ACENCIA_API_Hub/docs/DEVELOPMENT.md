# ACENCIA Hub - Entwicklungs-Dokumentation

## Voraussetzungen

- **Python**: 3.8 oder höher (getestet mit 3.13)
- **pip**: Python-Paketmanager
- **Git**: Für Versionskontrolle (optional)

## Lokales Setup

### 1. Repository klonen (oder Ordner kopieren)

```bash
git clone <repository-url>
cd ACENCIA_API_Hub
```

### 2. Virtuelle Umgebung erstellen

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. Abhängigkeiten installieren

```bash
pip install -r requirements.txt
```

### 4. Anwendung starten

```bash
# Entwicklungsmodus (mit Auto-Reload)
python acencia_hub/app.py

# Produktionsmodus mit Waitress
python run.py

# Windows: One-Click Start
start.bat
```

Die Anwendung ist erreichbar unter: `http://127.0.0.1:5001`

## Projektstruktur

```
ACENCIA_API_Hub/
├── acencia_hub/           # Hauptanwendung
│   ├── __init__.py        # Modul-Metadaten
│   ├── app.py             # Flask-App, Routen, Provider
│   ├── updater.py         # Auto-Update Funktionalität
│   ├── data/              # Persistente Daten
│   ├── static/css/        # Stylesheets
│   ├── templates/         # Jinja2 Templates
│   ├── _snapshots/        # Generierte Snapshots
│   ├── _history/          # API-Response-Backup
│   └── exports/           # Generierte Exports
├── docs/                  # Dokumentation
├── venv/                  # Virtuelle Umgebung (nicht committen!)
├── requirements.txt       # Python-Abhängigkeiten
├── run.py                 # Produktions-Entry-Point
├── start.bat              # Windows-Starter
├── server.log             # Log-Datei
├── AGENTS.md              # KI-Agent-Dokumentation
├── README.md              # Projekt-README
└── README_DESIGN.md       # Design-System-Dokumentation
```

## Entwicklungsworkflow

### Code-Änderungen

1. **Änderungen in `app.py`**: Server neu starten
2. **Änderungen in Templates**: Browser aktualisieren (F5)
3. **Änderungen in CSS**: Browser aktualisieren (F5)

### Neue Provider hinzufügen

1. Neue Klasse erstellen, die von `BaseProvider` erbt:

```python
class NeuerProvider(BaseProvider):
    def __init__(self, api_config: dict):
        super().__init__(api_config)
        # Provider-spezifische Initialisierung
    
    def list_employees(self) -> tuple[list[dict], Any]:
        # Implementierung
        pass
    
    def get_employee_details(self, employee_id: str) -> tuple[dict, Any]:
        # Implementierung
        pass
    
    def normalize_employee(self, data: dict) -> dict:
        # Daten in einheitliches Format transformieren
        pass
```

2. Provider in `ProviderFactory` registrieren:

```python
class ProviderFactory:
    @staticmethod
    def create(employer_cfg: dict) -> BaseProvider:
        # ...
        elif pk == "neuer_provider":
            return NeuerProvider(ac)
```

3. Formular in `add_employer.html` anpassen

### Neue Routen hinzufügen

```python
@app.route('/neue/route', methods=['GET', 'POST'])
def neue_route():
    """
    Beschreibung der Route.
    
    Returns:
        Response: HTML-Template oder JSON
    """
    # Login-Check
    if 'username' not in session:
        return redirect(url_for('login'))
    
    # Logik hier
    return render_template('template.html')
```

## Debugging

### Logs lesen

```bash
# Live-Logs anzeigen (PowerShell)
Get-Content server.log -Wait

# Oder in der App als Master-User: Einstellungen → Logs
```

### Häufige Probleme

#### Provider-Verbindungsfehler

```python
# In app.py nach custom_log suchen für Debug-Output
custom_log(session.get('kuerzel', 'SYSTEM'), f"API Error: {e}", "red")
```

#### Template nicht gefunden

- Pfad prüfen: `acencia_hub/templates/`
- Template-Name in `render_template()` prüfen

#### Session-Probleme

```python
# Secret Key in app.py prüfen
app.secret_key = 'your-secret-key'
```

### Debug-Modus aktivieren

In `app.py` am Ende:

```python
if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5001)
```

**Achtung**: Debug-Modus nicht in Produktion verwenden!

## Code-Standards

### Docstrings (Google-Style, Deutsch)

```python
def funktion(param1: str, param2: int) -> dict:
    """
    Kurze Beschreibung der Funktion.
    
    Args:
        param1 (str): Beschreibung des ersten Parameters
        param2 (int): Beschreibung des zweiten Parameters
    
    Returns:
        dict: Beschreibung des Rückgabewerts
    
    Raises:
        ValueError: Beschreibung wann dieser Fehler auftritt
    """
```

### Namenskonventionen

- **Funktionen/Variablen**: `snake_case`
- **Klassen**: `PascalCase`
- **Konstanten**: `UPPER_SNAKE_CASE`
- **Private Funktionen**: `_leading_underscore`

### CSS (Design-Token verwenden)

```css
/* RICHTIG */
.button {
    background-color: var(--color-accent);
    padding: var(--space-3) var(--space-4);
    border-radius: var(--radius-base);
}

/* FALSCH - Keine Hardcoded-Werte! */
.button {
    background-color: #fa9939;
    padding: 12px 16px;
    border-radius: 8px;
}
```

## Tests ausführen

**Hinweis**: Aktuell sind keine automatisierten Tests implementiert.

Geplante Test-Struktur:

```
tests/
├── __init__.py
├── test_providers.py      # Provider-Unit-Tests
├── test_exports.py        # Export-Funktions-Tests
├── test_routes.py         # Route-Integration-Tests
└── conftest.py            # Pytest-Fixtures
```

## Build & Deployment

### Lokales Deployment

```bash
# Mit start.bat (Windows)
start.bat

# Manuell mit Waitress
python run.py
```

### Netzwerkzugriff

Der Server bindet auf `0.0.0.0:5001` und ist von anderen Geräten im LAN erreichbar.
`start.bat` zeigt die verfügbaren IP-Adressen an.

### Updates verteilen

1. Änderungen auf GitHub pushen
2. Benutzer ruft Update in Master-Einstellungen auf
3. `updater.py` lädt automatisch die neueste Version

## Hilfreiche Befehle

```bash
# Abhängigkeiten aktualisieren
pip install --upgrade -r requirements.txt

# Neue Abhängigkeit hinzufügen
pip install <paket>
pip freeze > requirements.txt  # Nicht empfohlen, manuell editieren!

# Port prüfen (Windows)
netstat -an | findstr 5001

# Prozess beenden (Windows)
taskkill /F /IM python.exe
```

---

**Letzte Aktualisierung:** 28.01.2026
