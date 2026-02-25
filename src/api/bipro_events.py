"""
ACENCIA ATLAS - BiPRO Events API Client

Zugriff auf die bipro_events-Tabelle: strukturierte Metadaten
aus 0-Dokument-Lieferungen (Vertragsdaten-XML, Statusmeldungen,
GDV-Ankuendigungen).
"""

import logging
from dataclasses import dataclass
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)


@dataclass
class BiproEvent:
    """Einzelner BiPRO-Event-Eintrag."""
    id: int
    shipment_id: str
    vu_name: Optional[str]
    vu_bafin_nr: Optional[str]
    bipro_category: Optional[str]
    category_name: Optional[str]
    event_type: str
    vsnr: Optional[str]
    vn_name: Optional[str]
    vn_address: Optional[str]
    sparte: Optional[str]
    vermittler_nr: Optional[str]
    freitext: Optional[str]
    kurzbeschreibung: Optional[str]
    referenced_filename: Optional[str]
    shipment_date: Optional[str]
    raw_document_id: Optional[int]
    is_read: bool
    created_at: str

    @classmethod
    def from_dict(cls, d: Dict) -> 'BiproEvent':
        return cls(
            id=int(d['id']),
            shipment_id=d['shipment_id'],
            vu_name=d.get('vu_name'),
            vu_bafin_nr=d.get('vu_bafin_nr'),
            bipro_category=d.get('bipro_category'),
            category_name=d.get('category_name'),
            event_type=d['event_type'],
            vsnr=d.get('vsnr'),
            vn_name=d.get('vn_name'),
            vn_address=d.get('vn_address'),
            sparte=d.get('sparte'),
            vermittler_nr=d.get('vermittler_nr'),
            freitext=d.get('freitext'),
            kurzbeschreibung=d.get('kurzbeschreibung'),
            referenced_filename=d.get('referenced_filename'),
            shipment_date=d.get('shipment_date'),
            raw_document_id=int(d['raw_document_id']) if d.get('raw_document_id') else None,
            is_read=bool(int(d.get('is_read', 0))),
            created_at=d.get('created_at', ''),
        )


class BiproEventsAPI:
    """API-Client fuer BiPRO-Events."""

    def __init__(self, client):
        self.client = client

    def get_events(self, page: int = 1, per_page: int = 20,
                   event_type: str = None, is_read: int = None) -> Dict:
        params = {'page': page, 'per_page': per_page}
        if event_type:
            params['event_type'] = event_type
        if is_read is not None:
            params['is_read'] = is_read
        try:
            resp = self.client.get('/bipro-events', params=params)
            events = [BiproEvent.from_dict(e) for e in resp.get('data', [])]
            return {'data': events, 'pagination': resp.get('pagination', {})}
        except Exception as e:
            logger.error(f"Fehler beim Laden der BiPRO-Events: {e}")
            return {'data': [], 'pagination': {}}

    def get_summary(self) -> Dict:
        try:
            return self.client.get('/bipro-events/summary')
        except Exception as e:
            logger.debug(f"BiPRO-Events Summary Fehler: {e}")
            return {'unread_count': 0, 'latest_event': None}

    def create_event(self, data: Dict) -> Optional[int]:
        try:
            resp = self.client.post('/bipro-events', json_data=data)
            if resp.get('success'):
                return resp.get('id')
        except Exception as e:
            logger.warning(f"BiPRO-Event erstellen fehlgeschlagen: {e}")
        return None

    def mark_as_read(self, ids: List[int]) -> None:
        if not ids:
            return
        try:
            self.client.put('/bipro-events/read', json_data={'ids': ids})
        except Exception as e:
            logger.warning(f"BiPRO-Events als gelesen markieren fehlgeschlagen: {e}")

    def mark_all_read(self) -> int:
        """Markiert alle Events als gelesen. Gibt Anzahl aktualisierter Events zurueck."""
        try:
            resp = self.client.put('/bipro-events/read-all', json_data={})
            return resp.get('updated', 0)
        except Exception as e:
            logger.warning(f"Alle BiPRO-Events als gelesen markieren fehlgeschlagen: {e}")
            return 0

    def delete_event(self, event_id: int) -> bool:
        """Loescht einen einzelnen Event (Admin)."""
        try:
            resp = self.client.delete(f'/bipro-events/{event_id}')
            return resp.get('success', False)
        except Exception as e:
            logger.warning(f"BiPRO-Event {event_id} loeschen fehlgeschlagen: {e}")
            return False

    def delete_all_events(self) -> int:
        """Loescht alle Events (Admin). Gibt Anzahl geloeschter Events zurueck."""
        try:
            resp = self.client.delete('/bipro-events/all')
            return resp.get('deleted', 0)
        except Exception as e:
            logger.warning(f"Alle BiPRO-Events loeschen fehlgeschlagen: {e}")
            return 0
