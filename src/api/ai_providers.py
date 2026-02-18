"""
Python API Client fuer KI-Provider-Verwaltung.

Kommuniziert mit ai_providers.php auf dem Server.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class AIProviderKey:
    """Repraesentiert einen KI-Provider-Key."""
    id: int
    provider_type: str
    name: str
    api_key_masked: str
    is_active: bool
    created_at: Optional[datetime] = None

    @staticmethod
    def from_dict(d: dict) -> 'AIProviderKey':
        created = None
        if d.get('created_at'):
            try:
                created = datetime.fromisoformat(d['created_at'].replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                pass
        return AIProviderKey(
            id=int(d.get('id', 0)),
            provider_type=d.get('provider_type', ''),
            name=d.get('name', ''),
            api_key_masked=d.get('api_key_masked', ''),
            is_active=bool(d.get('is_active', False)),
            created_at=created,
        )


class AIProvidersAPI:
    """API Client fuer KI-Provider-Verwaltung."""

    def __init__(self, api_client):
        self._api = api_client

    def get_active_provider(self) -> Optional[dict]:
        """Gibt den aktiven Provider-Typ zurueck (ohne Key)."""
        try:
            resp = self._api.get("/ai/provider")
            if resp and resp.get('success'):
                return resp.get('data')
            return resp.get('data') if resp else None
        except Exception as e:
            logger.warning(f"Aktiven Provider laden fehlgeschlagen: {e}")
            return None

    def list_keys(self) -> List[AIProviderKey]:
        """Listet alle Provider-Keys auf (Admin)."""
        try:
            resp = self._api.get("/admin/ai-providers")
            data = resp.get('data', resp) if isinstance(resp, dict) else {}
            keys = data if isinstance(data, list) else data.get('providers', [])
            return [AIProviderKey.from_dict(k) for k in keys]
        except Exception as e:
            logger.error(f"Provider-Keys laden fehlgeschlagen: {e}")
            return []

    def create_key(self, provider_type: str, name: str, api_key: str) -> Optional[AIProviderKey]:
        """Erstellt einen neuen Provider-Key."""
        try:
            resp = self._api.post("/admin/ai-providers", json_data={
                'provider_type': provider_type,
                'name': name,
                'api_key': api_key,
            })
            data = resp.get('data', resp) if isinstance(resp, dict) else {}
            return AIProviderKey.from_dict(data) if data else None
        except Exception as e:
            logger.error(f"Provider-Key erstellen fehlgeschlagen: {e}")
            return None

    def update_key(self, key_id: int, **kwargs) -> bool:
        """Aktualisiert einen Provider-Key."""
        try:
            self._api.put(f"/admin/ai-providers/{key_id}", json_data=kwargs)
            return True
        except Exception as e:
            logger.error(f"Provider-Key aktualisieren fehlgeschlagen: {e}")
            return False

    def delete_key(self, key_id: int) -> bool:
        """Loescht einen Provider-Key."""
        try:
            self._api.delete(f"/admin/ai-providers/{key_id}")
            return True
        except Exception as e:
            logger.error(f"Provider-Key loeschen fehlgeschlagen: {e}")
            return False

    def activate_key(self, key_id: int) -> bool:
        """Aktiviert einen Provider-Key (deaktiviert alle anderen)."""
        try:
            self._api.post(f"/admin/ai-providers/{key_id}/activate")
            return True
        except Exception as e:
            logger.error(f"Provider-Key aktivieren fehlgeschlagen: {e}")
            return False

    def test_key(self, key_id: int) -> dict:
        """Testet einen Provider-Key."""
        try:
            resp = self._api.post(f"/admin/ai-providers/{key_id}/test")
            return resp.get('data', resp) if isinstance(resp, dict) else {}
        except Exception as e:
            logger.error(f"Provider-Key testen fehlgeschlagen: {e}")
            return {'success': False, 'error': str(e)}
