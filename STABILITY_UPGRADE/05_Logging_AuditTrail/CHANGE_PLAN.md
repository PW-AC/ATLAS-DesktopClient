# Change Plan: Task 05 - Logging & Audit Trail

## Betroffene Dateien

| Datei | Änderung |
|-------|----------|
| `src/main.py` | Logging-Konfiguration erweitern (FileHandler + Rotation) |
| `.gitignore` | `logs/` Ordner aufnehmen |

## Geänderte Logik

### `src/main.py` Zeile 18-22

Vorher:
```python
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
```

Nachher:
```python
import os
from logging.handlers import RotatingFileHandler

LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logs")
LOG_FILE = os.path.join(LOG_DIR, "bipro_gdv.log")

def setup_logging():
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    formatter = logging.Formatter(LOG_FORMAT)
    
    # Console Handler (wie bisher)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # File Handler mit Rotation
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        file_handler = RotatingFileHandler(
            LOG_FILE, maxBytes=5*1024*1024, backupCount=3, encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    except (OSError, PermissionError) as e:
        root_logger.warning(f"File-Logging nicht möglich: {e}")

setup_logging()
```

### `.gitignore`
Ergänzen:
```
# Logs
logs/
```

## Risikoanalyse

- **Kein Risiko**: Logging-Änderung hat keine Auswirkung auf Funktionalität
- **Fallback**: Wenn `logs/` nicht erstellt werden kann, läuft die App weiter (Console-only)
- **Encoding**: `utf-8` explizit gesetzt (wichtig für deutsche Umlaute in Logs)

## Validierung

- App starten → `logs/bipro_gdv.log` wird erstellt
- Console-Output bleibt erhalten
- Nach 5 MB wird rotiert
