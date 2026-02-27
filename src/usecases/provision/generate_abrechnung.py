"""
UseCase: Monatsabrechnung generieren.
"""

from typing import Dict

from domain.provision.interfaces import IAbrechnungRepository


class GenerateAbrechnung:
    """Generiert eine Monatsabrechnung fuer alle Berater."""

    def __init__(self, repository: IAbrechnungRepository):
        self._repo = repository

    def execute(self, *, monat: str) -> Dict:
        return self._repo.generate_abrechnung(monat=monat)
