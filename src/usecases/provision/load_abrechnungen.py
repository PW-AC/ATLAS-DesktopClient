"""
UseCase: Monatsabrechnungen laden.
"""

from typing import List, Optional

from domain.provision.entities import BeraterAbrechnung
from domain.provision.interfaces import IAbrechnungRepository


class LoadAbrechnungen:
    """Laedt Monatsabrechnungen fuer einen bestimmten Monat."""

    def __init__(self, repository: IAbrechnungRepository):
        self._repo = repository

    def execute(self, *, monat: str = None) -> List[BeraterAbrechnung]:
        return self._repo.get_abrechnungen(monat=monat)
