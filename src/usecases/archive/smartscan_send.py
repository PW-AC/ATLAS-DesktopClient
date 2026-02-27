"""
UseCase: SmartScan-Versand.
"""

from typing import List, Optional

from api.client import APIClient
from domain.archive.entities import SmartScanResult


class SmartScanSend:
    """Sendet Dokumente an den SmartScan-Service."""

    def __init__(self, api_client: APIClient):
        self._api_client = api_client

    def execute(
        self, document_ids: List[int], *,
        mode: str = 'selected',
        box_type: Optional[str] = None,
        client_request_id: Optional[str] = None,
        archive_after: bool = False,
        recolor_after: bool = False,
        recolor_color: Optional[str] = None,
    ) -> SmartScanResult:
        """Startet einen SmartScan-Job. Gibt das initiale Ergebnis zurueck."""
        from api.smartscan import SmartScanAPI
        api = SmartScanAPI(self._api_client)
        kwargs = dict(
            mode=mode,
            document_ids=document_ids,
            box_type=box_type,
            archive_after_send=archive_after if archive_after else None,
            recolor_after_send=recolor_after if recolor_after else None,
            recolor_color=recolor_color,
        )
        if client_request_id:
            kwargs['client_request_id'] = client_request_id
        result = api.send(**kwargs) or {}
        return SmartScanResult(
            success=bool(result.get('success', True)),
            job_id=result.get('job_id'),
            document_count=len(document_ids),
            raw_response=result,
        )
