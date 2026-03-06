"""
Workforce-Modul fuer ATLAS Desktop.

Extrahiert aus ACENCIA HR-Hub (app.py) fuer die Integration in die
ATLAS PySide6-Anwendung. Enthaelt Provider-Klassen, Export-Logik,
Trigger-System und Statistik-Berechnung.

Struktur:
    workforce.providers    - HR-API-Anbindungen (Personio, HRworks, SageHR)
    workforce.services     - Geschaeftslogik (Delta, Export, Trigger, Stats)
    workforce.constants    - Konfigurationskonstanten
    workforce.helpers      - Utility-Funktionen
    workforce.api_client   - PHP-Backend-Kommunikation
    workforce.workers      - QThread-Worker fuer nicht-blockierende Ops

Quelle: ACENCIA HR-Hub v1.1.0 -> ATLAS Workforce
"""

__version__ = "1.0.0"
