"""
HR-Provider-Registry und Factory.

Quelle: app.py Zeilen 2363-2390
"""

from hr.providers.base import BaseProvider
from hr.providers.hrworks import HRworksProvider
from hr.providers.personio import PersonioProvider
from hr.providers.sagehr import SageHrProvider


PROVIDER_MAP = {
    "hrworks": HRworksProvider,
    "personio": PersonioProvider,
    "sagehr": SageHrProvider,
}


class ProviderFactory:
    """Factory zum Erstellen von Provider-Instanzen basierend auf der Konfiguration."""

    @staticmethod
    def create(provider_key: str, credentials: dict) -> BaseProvider:
        """
        Erstellt eine Provider-Instanz.

        Args:
            provider_key: Provider-Typ ('personio', 'hrworks', 'sagehr')
            credentials: Dict mit access_key, secret_key, is_demo etc.

        Returns:
            BaseProvider-Instanz

        Raises:
            ValueError: Bei unbekanntem provider_key
        """
        provider_class = PROVIDER_MAP.get(provider_key)
        if not provider_class:
            raise ValueError(f"Unbekannter Provider: {provider_key}")
        return provider_class(**credentials)
