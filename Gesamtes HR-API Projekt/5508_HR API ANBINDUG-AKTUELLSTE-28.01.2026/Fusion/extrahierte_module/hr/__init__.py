"""
HR-Modul für ATLAS Desktop.

Extrahiert aus ACENCIA HR-Hub (app.py) für die Integration in die
ATLAS PySide6-Anwendung. Enthält Provider-Klassen, Export-Logik,
Trigger-System und Statistik-Berechnung.

Struktur:
    hr.providers    - HR-API-Anbindungen (Personio, HRworks, SageHR)
    hr.services     - Geschäftslogik (Delta, Export, Trigger, Stats)
    hr.constants    - Konfigurationskonstanten
    hr.helpers      - Utility-Funktionen

Quelle: ACENCIA_API_Hub/acencia_hub/app.py (v1.1.0, 28.01.2026)
"""

__version__ = "1.0.0"
__source__ = "ACENCIA HR-Hub v1.1.0"
