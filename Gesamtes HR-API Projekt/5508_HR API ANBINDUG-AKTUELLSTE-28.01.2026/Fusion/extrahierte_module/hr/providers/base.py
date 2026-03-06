"""
Abstrakte Basisklasse für alle HR-Provider.

Quelle: app.py Zeilen 1837-1887
"""

from abc import ABC, abstractmethod


class BaseProvider(ABC):
    """
    Abstrakte Basisklasse für alle HR-Datenprovider.

    Definiert die gemeinsame Schnittstelle für alle HR-Provider
    und stellt sicher, dass alle Provider die erforderlichen Methoden implementieren.

    Implementierungen:
        - HRworksProvider (hr/providers/hrworks.py)
        - PersonioProvider (hr/providers/personio.py)
        - SageHrProvider (hr/providers/sagehr.py)
    """

    def __init__(self, access_key: str, secret_key: str = None, slug: str = None, **kwargs):
        """
        Initialisiert einen HR-Provider.

        Args:
            access_key: Zugangsschlüssel für den Provider
            secret_key: Geheimer Schlüssel (optional)
            slug: Provider-Slug (optional, für SageHR)
            **kwargs: Weitere Provider-spezifische Parameter
        """
        self.access_key = access_key
        self.secret_key = secret_key
        self.slug = slug

    @abstractmethod
    def list_employees(self, only_active: bool = True) -> tuple[list[dict], list]:
        """
        Ruft eine Liste aller Mitarbeiter ab.

        Args:
            only_active: Ob nur aktive Mitarbeiter zurückgegeben werden

        Returns:
            Tupel aus (normalisierte Mitarbeiterdaten, rohe API-Antworten)
        """
        pass

    @abstractmethod
    def get_employee_details(self, employee_id: str, return_history: bool = True) -> tuple[dict, dict | list]:
        """
        Ruft detaillierte Informationen für einen einzelnen Mitarbeiter ab.

        Args:
            employee_id: Die ID des Mitarbeiters
            return_history: Ob die rohe API-Antwort zurückgegeben werden soll

        Returns:
            Tupel aus (normalisierte Daten, rohe API-Antwort)
        """
        pass

    def __repr__(self):
        return f"<{self.__class__.__name__}>"
