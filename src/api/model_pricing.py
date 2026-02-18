"""
Python API Client fuer Modell-Preise und KI-Request-Historie.

Kommuniziert mit model_pricing.php auf dem Server.
"""

import logging
from dataclasses import dataclass
from datetime import date, datetime
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ModelPrice:
    """Repraesentiert einen Modell-Preis-Eintrag."""
    id: int
    provider: str
    model_name: str
    input_price_per_million: float
    output_price_per_million: float
    valid_from: Optional[str] = None
    is_active: bool = True

    @staticmethod
    def from_dict(d: dict) -> 'ModelPrice':
        return ModelPrice(
            id=int(d.get('id', 0)),
            provider=d.get('provider', ''),
            model_name=d.get('model_name', d.get('model', '')),
            input_price_per_million=float(d.get('input_price_per_million', 0)),
            output_price_per_million=float(d.get('output_price_per_million', 0)),
            valid_from=d.get('valid_from'),
            is_active=bool(d.get('is_active', True)),
        )


class ModelPricingAPI:
    """API Client fuer Modell-Preise."""

    def __init__(self, api_client):
        self._api = api_client

    def get_prices(self) -> List[ModelPrice]:
        """Gibt aktive Preise zurueck (oeffentlich, fuer Client-Schaetzung)."""
        try:
            resp = self._api.get("/ai/pricing")
            data = resp.get('data', resp) if isinstance(resp, dict) else {}
            prices = data.get('prices', [])
            return [ModelPrice.from_dict(p) for p in prices]
        except Exception as e:
            logger.warning(f"Preise laden fehlgeschlagen: {e}")
            return []

    def list_prices_admin(self) -> List[ModelPrice]:
        """Gibt alle Preise zurueck (Admin)."""
        try:
            resp = self._api.get("/admin/model-pricing")
            data = resp.get('data', resp) if isinstance(resp, dict) else {}
            prices = data if isinstance(data, list) else data.get('prices', [])
            return [ModelPrice.from_dict(p) for p in prices]
        except Exception as e:
            logger.error(f"Admin-Preise laden fehlgeschlagen: {e}")
            return []

    def create_price(self, provider: str, model_name: str,
                     input_price: float, output_price: float,
                     valid_from: str = None) -> Optional[ModelPrice]:
        """Erstellt einen neuen Modell-Preis."""
        try:
            payload = {
                'provider': provider,
                'model_name': model_name,
                'input_price_per_million': input_price,
                'output_price_per_million': output_price,
            }
            if valid_from:
                payload['valid_from'] = valid_from
            resp = self._api.post("/admin/model-pricing", json_data=payload)
            data = resp.get('data', resp) if isinstance(resp, dict) else {}
            return ModelPrice.from_dict(data) if data else None
        except Exception as e:
            logger.error(f"Preis erstellen fehlgeschlagen: {e}")
            return None

    def update_price(self, price_id: int, **kwargs) -> bool:
        """Aktualisiert einen Modell-Preis."""
        try:
            self._api.put(f"/admin/model-pricing/{price_id}", json_data=kwargs)
            return True
        except Exception as e:
            logger.error(f"Preis aktualisieren fehlgeschlagen: {e}")
            return False

    def delete_price(self, price_id: int) -> bool:
        """Deaktiviert einen Modell-Preis."""
        try:
            self._api.delete(f"/admin/model-pricing/{price_id}")
            return True
        except Exception as e:
            logger.error(f"Preis deaktivieren fehlgeschlagen: {e}")
            return False

    def get_ai_requests(self, limit: int = 200, period: str = 'all') -> list:
        """Gibt KI-Request-Historie zurueck (Admin)."""
        try:
            params = {'limit': limit}
            if period and period != 'all':
                params['period'] = period
            resp = self._api.get("/ai/requests", params=params)
            data = resp.get('data', resp) if isinstance(resp, dict) else {}
            return data if isinstance(data, list) else data.get('requests', [])
        except Exception as e:
            logger.error(f"AI-Requests laden fehlgeschlagen: {e}")
            return []
