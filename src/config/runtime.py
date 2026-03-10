"""
Laufzeit-Konfiguration: Dev-Modus (python run.py) vs. EXE-Build.
"""

import sys


def is_dev_mode() -> bool:
    """
    Erkennt ob die App im Entwicklungsmodus laeuft (python run.py statt EXE).
    
    Im Dev-Modus:
    - Single-Instance-Check wird uebersprungen
    - Update-Check wird uebersprungen
    - Session-Token vom EXE-Client wird weder gelesen noch gespeichert noch geloescht
    """
    return not getattr(sys, 'frozen', False)
