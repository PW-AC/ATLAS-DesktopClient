"""
Processing History API Client

Client fuer die Processing-History API zur Verwaltung des Audit-Trails.
Jeder Verarbeitungsschritt eines Dokuments wird protokolliert.
"""

import logging
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from contextlib import contextmanager

from api.client import APIClient

logger = logging.getLogger(__name__)


@dataclass
class HistoryEntry:
    """Einzelner Eintrag in der Processing-History."""
    id: int
    document_id: int
    previous_status: Optional[str]
    new_status: str
    action: str
    action_details: Optional[Dict]
    success: bool
    error_message: Optional[str]
    classification_source: Optional[str]
    classification_result: Optional[str]
    duration_ms: Optional[int]
    created_at: str
    created_by: Optional[str]
    # Optional: Dokument-Infos (wenn mit Join geladen)
    document_filename: Optional[str] = None
    document_original_filename: Optional[str] = None
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'HistoryEntry':
        return cls(
            id=data['id'],
            document_id=data['document_id'],
            previous_status=data.get('previous_status'),
            new_status=data['new_status'],
            action=data['action'],
            action_details=data.get('action_details'),
            success=bool(data.get('success', True)),
            error_message=data.get('error_message'),
            classification_source=data.get('classification_source'),
            classification_result=data.get('classification_result'),
            duration_ms=data.get('duration_ms'),
            created_at=data.get('created_at', ''),
            created_by=data.get('created_by'),
            document_filename=data.get('document_filename'),
            document_original_filename=data.get('document_original_filename')
        )


class ProcessingHistoryAPI:
    """API Client fuer Processing-History."""
    
    def __init__(self, client: APIClient):
        self.client = client
        self._endpoint = 'processing_history'
    
    def list(self, 
             document_id: Optional[int] = None,
             action: Optional[str] = None,
             status: Optional[str] = None,
             success: Optional[bool] = None,
             from_date: Optional[str] = None,
             to_date: Optional[str] = None,
             limit: int = 100,
             offset: int = 0) -> tuple[List[HistoryEntry], int]:
        """
        Listet History-Eintraege mit optionalen Filtern.
        
        Returns:
            Tuple aus (Liste von HistoryEntry, Gesamtzahl)
        """
        params = {'limit': limit, 'offset': offset}
        
        if document_id is not None:
            params['document_id'] = document_id
        if action:
            params['action'] = action
        if status:
            params['status'] = status
        if success is not None:
            params['success'] = '1' if success else '0'
        if from_date:
            params['from'] = from_date
        if to_date:
            params['to'] = to_date
        
        response = self.client.get(f'{self._endpoint}/list', params=params)
        
        if response and response.get('success'):
            data = response.get('data', {})
            entries = [HistoryEntry.from_dict(e) for e in data.get('entries', [])]
            total = data.get('total', len(entries))
            return entries, total
        
        return [], 0
    
    def get_document_history(self, document_id: int) -> tuple[Optional[Dict], List[HistoryEntry], Dict]:
        """
        Holt die komplette History eines Dokuments.
        
        Returns:
            Tuple aus (Dokument-Dict, Liste von HistoryEntry, Stats-Dict)
        """
        response = self.client.get(f'{self._endpoint}/{document_id}')
        
        if response and response.get('success'):
            data = response.get('data', {})
            document = data.get('document')
            history = [HistoryEntry.from_dict(e) for e in data.get('history', [])]
            stats = data.get('stats', {})
            return document, history, stats
        
        return None, [], {}
    
    def create(self,
               document_id: Optional[int],
               action: str,
               new_status: str,
               previous_status: Optional[str] = None,
               action_details: Optional[Dict] = None,
               success: bool = True,
               error_message: Optional[str] = None,
               classification_source: Optional[str] = None,
               classification_result: Optional[str] = None,
               duration_ms: Optional[int] = None) -> Optional[int]:
        """
        Erstellt einen neuen History-Eintrag.
        
        Returns:
            ID des neuen Eintrags oder None bei Fehler
        """
        payload = {
            'document_id': document_id,
            'action': action,
            'new_status': new_status,
            'success': success
        }
        
        if previous_status:
            payload['previous_status'] = previous_status
        if action_details:
            payload['action_details'] = action_details
        if error_message:
            payload['error_message'] = error_message[:500]  # DB-Limit
        if classification_source:
            payload['classification_source'] = classification_source
        if classification_result:
            payload['classification_result'] = classification_result
        if duration_ms is not None:
            payload['duration_ms'] = duration_ms
        
        response = self.client.post(f'{self._endpoint}/create', json_data=payload)
        
        if response and response.get('success'):
            return response.get('data', {}).get('id')
        
        return None
    
    def get_stats(self, 
                  from_date: Optional[str] = None,
                  to_date: Optional[str] = None) -> Optional[Dict]:
        """
        Holt Statistiken ueber die Verarbeitung.
        
        Returns:
            Dict mit Statistiken oder None bei Fehler
        """
        params = {}
        if from_date:
            params['from'] = from_date
        if to_date:
            params['to'] = to_date
        
        response = self.client.get(f'{self._endpoint}/stats', params=params)
        
        if response and response.get('success'):
            return response.get('data')
        
        return None
    
    def get_recent_errors(self, limit: int = 20) -> List[HistoryEntry]:
        """
        Holt die letzten Fehler.
        
        Returns:
            Liste von HistoryEntry mit success=False
        """
        response = self.client.get(f'{self._endpoint}/errors', params={'limit': limit})
        
        if response and response.get('success'):
            data = response.get('data', {})
            return [HistoryEntry.from_dict(e) for e in data.get('errors', [])]
        
        return []
    
    @contextmanager
    def track_action(self, 
                     document_id: int,
                     action: str,
                     new_status: str,
                     previous_status: Optional[str] = None,
                     classification_source: Optional[str] = None):
        """
        Context-Manager zum automatischen Tracking einer Aktion.
        
        Misst automatisch die Dauer und protokolliert Erfolg/Fehler.
        
        Usage:
            with history_api.track_action(doc.id, 'classify', 'classified') as tracker:
                # Klassifikation durchfuehren
                tracker.set_result('ki_gpt4o', 'sparte_sach')
        
        Yields:
            ActionTracker-Objekt zum Setzen zusaetzlicher Informationen
        """
        tracker = ActionTracker(
            history_api=self,
            document_id=document_id,
            action=action,
            new_status=new_status,
            previous_status=previous_status,
            classification_source=classification_source
        )
        
        try:
            yield tracker
            tracker.finish_success()
        except Exception as e:
            tracker.finish_error(str(e))
            raise


class ActionTracker:
    """Helper-Klasse fuer track_action Context-Manager."""
    
    def __init__(self, 
                 history_api: ProcessingHistoryAPI,
                 document_id: int,
                 action: str,
                 new_status: str,
                 previous_status: Optional[str] = None,
                 classification_source: Optional[str] = None):
        self.history_api = history_api
        self.document_id = document_id
        self.action = action
        self.new_status = new_status
        self.previous_status = previous_status
        self.classification_source = classification_source
        self.classification_result: Optional[str] = None
        self.action_details: Optional[Dict] = None
        self.start_time = time.time()
        self._finished = False
    
    def set_result(self, source: str, result: str):
        """Setzt Klassifikationsquelle und -ergebnis."""
        self.classification_source = source
        self.classification_result = result
    
    def set_details(self, details: Dict):
        """Setzt zusaetzliche Aktionsdetails."""
        self.action_details = details
    
    def _calculate_duration(self) -> int:
        """Berechnet die Dauer in Millisekunden."""
        return int((time.time() - self.start_time) * 1000)
    
    def finish_success(self):
        """Schließt die Aktion erfolgreich ab."""
        if self._finished:
            return
        self._finished = True
        
        self.history_api.create(
            document_id=self.document_id,
            action=self.action,
            new_status=self.new_status,
            previous_status=self.previous_status,
            action_details=self.action_details,
            success=True,
            classification_source=self.classification_source,
            classification_result=self.classification_result,
            duration_ms=self._calculate_duration()
        )
    
    def finish_error(self, error_message: str):
        """Schließt die Aktion mit Fehler ab."""
        if self._finished:
            return
        self._finished = True
        
        self.history_api.create(
            document_id=self.document_id,
            action=self.action,
            new_status='error',
            previous_status=self.previous_status,
            action_details=self.action_details,
            success=False,
            error_message=error_message,
            classification_source=self.classification_source,
            duration_ms=self._calculate_duration()
        )
