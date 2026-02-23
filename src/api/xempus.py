"""
API-Client fuer Xempus Insight Engine.

Kommuniziert mit den /pm/xempus/* Endpoints.
4-Phasen-Import, CRUD fuer Entities, Stats, Diff, Status-Mapping.
"""

import logging
from typing import Optional, List, Dict

from .client import APIClient, APIError

logger = logging.getLogger(__name__)

# Domain-Imports werden spaet geladen um zirkulaere Imports zu vermeiden
_models = None


def _get_models():
    global _models
    if _models is None:
        from domain import xempus_models as m
        _models = m
    return _models


class XempusAPI:
    """API-Client fuer alle /pm/xempus/* Endpoints."""

    def __init__(self, client: APIClient):
        self.client = client

    CHUNK_SIZE = 2000

    # ── Phase 1: RAW Ingest (chunked) ──

    def import_raw(self, filename: str, sheets: List[Dict],
                   timeout: int = 120,
                   on_progress=None) -> Dict:
        """Phase 1: RAW-Ingest aller Sheets mit automatischem Chunking.

        Große Sheets werden in Chunks von CHUNK_SIZE Zeilen aufgeteilt.
        Der erste Request erstellt den Batch, Folge-Requests hängen Daten an.

        Args:
            filename: Original-Dateiname
            sheets: Liste von {sheet_name: str, rows: List[Dict]}
            on_progress: Optional callback(sent_rows, total_rows)
        Returns:
            Dict mit batch_id, total_rows, sheet_counts
        """
        total_rows = sum(len(s.get('rows', [])) for s in sheets)
        sent_rows = 0
        batch_id = None
        last_result = {}

        chunks = self._build_chunks(sheets)
        for chunk_sheets in chunks:
            try:
                payload = {'filename': filename, 'sheets': chunk_sheets}
                if batch_id:
                    payload['batch_id'] = batch_id
                resp = self.client.post('/pm/xempus/import',
                                        json_data=payload, timeout=timeout)
                if resp.get('success'):
                    last_result = resp.get('data', {})
                    if not batch_id:
                        batch_id = last_result.get('batch_id')
                    sent_rows += sum(len(s.get('rows', [])) for s in chunk_sheets)
                    if on_progress and total_rows > 0:
                        on_progress(sent_rows, total_rows)
                else:
                    raise APIError(resp.get('error', 'Unbekannter Fehler'))
            except APIError as e:
                logger.error(f"Xempus RAW-Ingest Chunk fehlgeschlagen: {e}")
                raise

        return last_result

    def _build_chunks(self, sheets: List[Dict]) -> List[List[Dict]]:
        """Teilt große Sheets in Chunks auf (max CHUNK_SIZE Rows pro Request)."""
        chunks = []
        current_chunk = []
        current_size = 0

        for sheet in sheets:
            name = sheet.get('sheet_name', '')
            rows = sheet.get('rows', [])

            if not rows:
                continue

            if len(rows) <= self.CHUNK_SIZE and current_size + len(rows) <= self.CHUNK_SIZE:
                current_chunk.append(sheet)
                current_size += len(rows)
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                    current_chunk = []
                    current_size = 0

                for i in range(0, len(rows), self.CHUNK_SIZE):
                    sub = rows[i:i + self.CHUNK_SIZE]
                    chunks.append([{'sheet_name': name, 'rows': sub}])

        if current_chunk:
            chunks.append(current_chunk)

        return chunks

    PARSE_CHUNK_SIZE = 1000

    # ── Phase 2: Parse (chunked) ──

    def parse_batch(self, batch_id: int, timeout: int = 300,
                    on_progress=None) -> Dict:
        """Phase 2: Normalize + Parse in Chunks (Server-seitig limitiert).

        Ruft den Parse-Endpunkt wiederholt auf bis done=True.

        Args:
            batch_id: ID des Import-Batches
            timeout: Timeout pro Chunk-Request
            on_progress: Optional callback(parsed_rows, total_rows)
        Returns:
            Dict mit batch_id und aggregierten parsed-Stats
        """
        total_stats = {'ok': 0, 'warning': 0, 'error': 0}
        total_parsed = 0
        total_rows = None

        while True:
            try:
                resp = self.client.post(
                    f'/pm/xempus/parse/{batch_id}',
                    json_data={'limit': self.PARSE_CHUNK_SIZE},
                    timeout=timeout
                )
                if not resp.get('success'):
                    raise APIError(resp.get('error', 'Parse fehlgeschlagen'))

                data = resp.get('data', {})
                chunk_stats = data.get('parsed', {})
                remaining = data.get('remaining', 0)
                done = data.get('done', True)

                for k in ('ok', 'warning', 'error'):
                    total_stats[k] += chunk_stats.get(k, 0)

                chunk_count = sum(chunk_stats.get(k, 0) for k in ('ok', 'warning', 'error'))
                total_parsed += chunk_count

                if total_rows is None:
                    total_rows = total_parsed + remaining

                if on_progress and total_rows > 0:
                    on_progress(total_parsed, total_rows)

                if done:
                    break

            except APIError as e:
                logger.error(f"Xempus Parse fehlgeschlagen fuer Batch {batch_id}: {e}")
                raise

        return {'batch_id': batch_id, 'parsed': total_stats}

    # ── Phase 3+4: Finalize ──

    def finalize_batch(self, batch_id: int, timeout: int = 120) -> Dict:
        """Phase 3+4: Snapshot Update + Finalize.

        Returns:
            Dict mit batch_id, snapshot_hash, diff, record_counts
        """
        try:
            resp = self.client.post(f'/pm/xempus/finalize/{batch_id}', json_data={},
                                    timeout=timeout)
            if resp.get('success'):
                return resp.get('data', {})
        except APIError as e:
            logger.error(f"Xempus Finalize fehlgeschlagen fuer Batch {batch_id}: {e}")
            raise
        return {}

    # ── Sync xempus_consultations → pm_contracts ──

    def sync_to_pm(self, batch_id: Optional[int] = None, timeout: int = 120) -> Dict:
        """Sync Xempus-Beratungen in pm_contracts + Auto-Matching."""
        url = f'/pm/xempus/sync/{batch_id}' if batch_id else '/pm/xempus/sync'
        try:
            resp = self.client.post(url, json_data={}, timeout=timeout)
            if resp.get('success'):
                return resp.get('data', {})
        except APIError as e:
            logger.error(f"Xempus Sync fehlgeschlagen: {e}")
            raise
        return {}

    # ── Batches (Import-Historie) ──

    def get_batches(self) -> List:
        """Import-Historie mit Phase-Status laden."""
        m = _get_models()
        try:
            resp = self.client.get('/pm/xempus/batches')
            if resp.get('success'):
                return [m.XempusImportBatch.from_dict(b)
                        for b in resp.get('data', {}).get('batches', [])]
        except APIError as e:
            logger.error(f"Xempus Batches laden fehlgeschlagen: {e}")
        return []

    # ── Employers ──

    def get_employers(self) -> List:
        """Alle aktiven Arbeitgeber mit Counts laden."""
        m = _get_models()
        try:
            resp = self.client.get('/pm/xempus/employers')
            if resp.get('success'):
                return [m.XempusEmployer.from_dict(e)
                        for e in resp.get('data', {}).get('employers', [])]
        except APIError as e:
            logger.error(f"Xempus Employers laden fehlgeschlagen: {e}")
        return []

    def get_employer_detail(self, employer_id: str) -> Optional[Dict]:
        """Arbeitgeber-Detail mit Tarifen, Zueschuessen, MA-Stats."""
        m = _get_models()
        try:
            resp = self.client.get(f'/pm/xempus/employers/{employer_id}')
            if resp.get('success'):
                data = resp.get('data', {})
                employer = m.XempusEmployer.from_dict(data.get('employer', {}))
                employer.employee_count = int(data.get('employee_count', 0))
                return {
                    'employer': employer,
                    'tariffs': [m.XempusTariff.from_dict(t) for t in data.get('tariffs', [])],
                    'subsidies': [m.XempusSubsidy.from_dict(s) for s in data.get('subsidies', [])],
                    'employee_count': employer.employee_count,
                    'status_distribution': data.get('status_distribution', []),
                }
        except APIError as e:
            logger.error(f"Xempus Employer Detail {employer_id} fehlgeschlagen: {e}")
        return None

    # ── Employees ──

    def get_employees(self, employer_id: str = None, status: str = None,
                      q: str = None, page: int = 1, per_page: int = 50) -> tuple:
        """Arbeitnehmer-Liste (paginiert).

        Returns: (List[XempusEmployee], PaginationInfo-Dict)
        """
        m = _get_models()
        params = {'page': page, 'per_page': per_page}
        if employer_id:
            params['employer_id'] = employer_id
        if status:
            params['status'] = status
        if q:
            params['q'] = q
        try:
            resp = self.client.get('/pm/xempus/employees', params=params)
            if resp.get('success'):
                data = resp.get('data', {})
                employees = [m.XempusEmployee.from_dict(e) for e in data.get('employees', [])]
                pagination = data.get('pagination', {})
                return employees, pagination
        except APIError as e:
            logger.error(f"Xempus Employees laden fehlgeschlagen: {e}")
        return [], {}

    def get_employee_detail(self, employee_id: str) -> Optional[Dict]:
        """Arbeitnehmer-Detail mit Beratungen."""
        m = _get_models()
        try:
            resp = self.client.get(f'/pm/xempus/employees/{employee_id}')
            if resp.get('success'):
                data = resp.get('data', {})
                return {
                    'employee': m.XempusEmployee.from_dict(data.get('employee', {})),
                    'consultations': [m.XempusConsultation.from_dict(c)
                                      for c in data.get('consultations', [])],
                }
        except APIError as e:
            logger.error(f"Xempus Employee Detail {employee_id} fehlgeschlagen: {e}")
        return None

    # ── Consultations ──

    def get_consultations(self, employer_id: str = None, status: str = None,
                          q: str = None, page: int = 1, per_page: int = 50) -> tuple:
        """Beratungen-Liste (paginiert).

        Returns: (List[XempusConsultation], PaginationInfo-Dict)
        """
        m = _get_models()
        params = {'page': page, 'per_page': per_page}
        if employer_id:
            params['employer_id'] = employer_id
        if status:
            params['status'] = status
        if q:
            params['q'] = q
        try:
            resp = self.client.get('/pm/xempus/consultations', params=params)
            if resp.get('success'):
                data = resp.get('data', {})
                consultations = [m.XempusConsultation.from_dict(c)
                                 for c in data.get('consultations', [])]
                pagination = data.get('pagination', {})
                return consultations, pagination
        except APIError as e:
            logger.error(f"Xempus Consultations laden fehlgeschlagen: {e}")
        return [], {}

    # ── Stats ──

    def get_stats(self):
        """Aggregierte KPI-Statistiken."""
        m = _get_models()
        try:
            resp = self.client.get('/pm/xempus/stats')
            if resp.get('success'):
                data = resp.get('data', {})
                debug = data.get('_debug', {})
                if debug:
                    logger.info(f"Xempus Stats _debug from server: {debug}")
                return m.XempusStats.from_dict(data)
        except APIError as e:
            logger.error(f"Xempus Stats laden fehlgeschlagen: {e}")
        return _get_models().XempusStats()

    # ── Diff ──

    def get_diff(self, batch_id: int):
        """Snapshot-Diff zwischen Batch und vorherigem Snapshot."""
        m = _get_models()
        try:
            resp = self.client.get(f'/pm/xempus/diff/{batch_id}')
            if resp.get('success'):
                return m.XempusDiff.from_dict(resp.get('data', {}))
        except APIError as e:
            logger.error(f"Xempus Diff fuer Batch {batch_id} fehlgeschlagen: {e}")
        return None

    # ── Status-Mapping ──

    def get_status_mappings(self) -> List:
        """Alle Status-Mappings laden."""
        m = _get_models()
        try:
            resp = self.client.get('/pm/xempus/status-mapping')
            if resp.get('success'):
                return [m.XempusStatusMapping.from_dict(sm)
                        for sm in resp.get('data', {}).get('mappings', [])]
        except APIError as e:
            logger.error(f"Xempus Status-Mappings laden fehlgeschlagen: {e}")
        return []

    def save_status_mapping(self, raw_status: str, category: str,
                            display_label: str = '', color: str = '#9e9e9e') -> bool:
        """Status-Mapping erstellen oder aktualisieren."""
        try:
            resp = self.client.post('/pm/xempus/status-mapping', json_data={
                'raw_status': raw_status,
                'category': category,
                'display_label': display_label,
                'color': color,
            })
            return resp.get('success', False)
        except APIError as e:
            logger.error(f"Xempus Status-Mapping speichern fehlgeschlagen: {e}")
        return False
