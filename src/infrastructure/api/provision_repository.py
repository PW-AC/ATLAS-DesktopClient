"""
Infrastructure-Adapter: Provision API → Domain Repository Interfaces.

Wrappt die bestehende ProvisionAPI-Klasse und implementiert
die Domain-Interfaces. Konvertiert zwischen API-Datenformaten
und Domain-Entitäten.
"""

import logging
from typing import Optional, List, Dict, Tuple

from api.client import APIClient, APIError
from domain.provision.entities import (
    Commission, Contract, Employee, CommissionModel,
    DashboardSummary, ImportResult, ImportBatch,
    BeraterAbrechnung, VermittlerMapping, ContractSearchResult,
    PaginationInfo, RecalcSummary,
)

logger = logging.getLogger(__name__)


class ProvisionRepository:
    """Implementiert IProvisionRepository, IImportRepository, IEmployeeRepository,
    IContractRepository, IMappingRepository, IModelRepository,
    IAbrechnungRepository, IAuditRepository.

    Einzelne Klasse als Fassade für den bestehenden REST-API-Client.
    """

    def __init__(self, client: APIClient):
        self._client = client

    # ── Commissions (IProvisionRepository) ──

    def get_commissions(
        self, *,
        berater_id: int = None,
        match_status: str = None,
        von: str = None,
        bis: str = None,
        versicherer: str = None,
        q: str = None,
        is_relevant: Optional[bool] = None,
        page: int = None,
        per_page: int = None,
        limit: int = 500,
    ) -> Tuple[List[Commission], Optional[PaginationInfo]]:
        params = {}
        if page is not None:
            params['page'] = page
            params['per_page'] = per_page or 50
        else:
            params['limit'] = limit
        if berater_id:
            params['berater_id'] = berater_id
        if match_status:
            params['match_status'] = match_status
        if von:
            params['von'] = von
        if bis:
            params['bis'] = bis
        if versicherer:
            params['versicherer'] = versicherer
        if q:
            params['q'] = q
        if is_relevant is not None:
            params['is_relevant'] = '1' if is_relevant else '0'
        try:
            resp = self._client.get('/pm/commissions', params=params)
            if resp.get('success'):
                data = resp.get('data', {})
                commissions = [Commission.from_dict(c) for c in data.get('commissions', [])]
                pagination_data = data.get('pagination')
                pagination = PaginationInfo.from_dict(pagination_data) if pagination_data else None
                return commissions, pagination
        except APIError as e:
            logger.error(f"Fehler beim Laden der Provisionen: {e}")
        return [], None

    def match_commission(self, commission_id: int, contract_id: int = None,
                         berater_id: int = None) -> bool:
        try:
            resp = self._client.put(
                f'/pm/commissions/{commission_id}/match',
                json_data={'contract_id': contract_id, 'berater_id': berater_id}
            )
            return resp.get('success', False)
        except APIError as e:
            logger.error(f"Fehler beim manuellen Matching {commission_id}: {e}")
        return False

    def ignore_commission(self, commission_id: int) -> bool:
        try:
            resp = self._client.put(f'/pm/commissions/{commission_id}/ignore', json_data={})
            return resp.get('success', False)
        except APIError as e:
            logger.error(f"Fehler beim Ignorieren der Provision {commission_id}: {e}")
        return False

    def recalculate_splits(self) -> int:
        try:
            resp = self._client.post('/pm/commissions/recalculate', json_data={})
            if resp.get('success'):
                return resp.get('data', {}).get('recalculated', 0)
        except APIError as e:
            logger.error(f"Fehler bei Split-Neuberechnung: {e}")
        return 0

    # ── Dashboard ──

    def get_dashboard_summary(self, von: str = None,
                              bis: str = None) -> Optional[DashboardSummary]:
        params = {}
        if von and bis:
            params['von'] = von
            params['bis'] = bis
        try:
            resp = self._client.get('/pm/dashboard/summary', params=params)
            if resp.get('success'):
                return DashboardSummary.from_dict(resp.get('data', {}))
        except APIError as e:
            logger.error(f"Fehler beim Laden des Dashboards: {e}")
        return None

    def get_berater_detail(self, berater_id: int,
                           von: str = None, bis: str = None) -> Optional[Dict]:
        params = {}
        if von and bis:
            params['von'] = von
            params['bis'] = bis
        try:
            resp = self._client.get(f'/pm/dashboard/berater/{berater_id}', params=params)
            if resp.get('success'):
                return resp.get('data', {})
        except APIError as e:
            logger.error(f"Fehler beim Laden der Berater-Details {berater_id}: {e}")
        return None

    def get_clearance_counts(self, von: str = None, bis: str = None) -> Dict:
        try:
            params = {}
            if von:
                params['von'] = von
            if bis:
                params['bis'] = bis
            resp = self._client.get('/pm/clearance', params=params)
            if resp.get('success'):
                return resp.get('data', {})
        except APIError as e:
            logger.error(f"Fehler beim Laden der Klärfall-Counts: {e}")
        return {'total': 0, 'no_contract': 0, 'no_berater': 0,
                'no_model': 0, 'no_split': 0}

    # ── Match-Suggestions ──

    def get_match_suggestions(self, commission_id: int = None,
                              contract_id: int = None,
                              direction: str = 'forward',
                              q: str = None,
                              limit: int = 50) -> Dict:
        params = {'direction': direction, 'limit': limit}
        if commission_id:
            params['commission_id'] = commission_id
        if contract_id:
            params['contract_id'] = contract_id
        if q:
            params['q'] = q
        try:
            resp = self._client.get('/pm/match-suggestions', params=params)
            if resp.get('success'):
                data = resp.get('data', {})
                if direction == 'forward':
                    return {
                        'suggestions': [ContractSearchResult.from_dict(s) for s in data.get('suggestions', [])],
                        'commission': Commission.from_dict(data['commission']) if data.get('commission') else None,
                    }
                else:
                    return {
                        'suggestions': data.get('suggestions', []),
                        'contract': Contract.from_dict(data['contract']) if data.get('contract') else None,
                    }
        except APIError as e:
            logger.error(f"Fehler bei Match-Suggestions: {e}")
        return {'suggestions': [], 'commission': None, 'contract': None}

    def assign_contract(self, commission_id: int, contract_id: int,
                        force_override: bool = False) -> Dict:
        try:
            resp = self._client.put('/pm/assign', json_data={
                'commission_id': commission_id,
                'contract_id': contract_id,
                'force_override': force_override,
            })
            if resp.get('success'):
                return resp.get('data', {})
        except APIError as e:
            logger.error(f"Fehler bei Zuordnung commission={commission_id} → contract={contract_id}: {e}")
            raise
        return {}

    # ── Import (IImportRepository) ──

    def import_vu_liste(self, rows: List[Dict], filename: str,
                        sheet_name: str = None, vu_name: str = None,
                        file_hash: str = None,
                        skip_match: bool = False,
                        retries: int = None) -> Optional[ImportResult]:
        try:
            resp = self._client.post('/pm/import/vu-liste', json_data={
                'rows': rows,
                'filename': filename,
                'sheet_name': sheet_name,
                'vu_name': vu_name,
                'file_hash': file_hash,
                'skip_match': skip_match,
            }, timeout=120, retries=retries)
            if resp.get('success'):
                return ImportResult.from_dict(resp.get('data', {}))
        except APIError as e:
            logger.error(f"Fehler beim VU-Import: {e}")
            raise
        return None

    def import_xempus(self, rows: List[Dict], filename: str,
                      file_hash: str = None) -> Optional[ImportResult]:
        try:
            resp = self._client.post('/pm/import/xempus', json_data={
                'rows': rows,
                'filename': filename,
                'file_hash': file_hash,
            }, timeout=120)
            if resp.get('success'):
                return ImportResult.from_dict(resp.get('data', {}))
        except APIError as e:
            logger.error(f"Fehler beim Xempus-Import: {e}")
            raise
        return None

    def trigger_auto_match(self, batch_id: int = None) -> Dict:
        try:
            data = {}
            if batch_id:
                data['batch_id'] = batch_id
            resp = self._client.post('/pm/import/match', json_data=data, timeout=120)
            if resp.get('success'):
                return resp.get('data', {}).get('stats', {})
        except APIError as e:
            logger.error(f"Fehler beim Auto-Matching: {e}")
        return {}

    def get_import_batches(self) -> List[ImportBatch]:
        try:
            resp = self._client.get('/pm/import/batches')
            if resp.get('success'):
                return [ImportBatch.from_dict(b) for b in resp.get('data', {}).get('batches', [])]
        except APIError as e:
            logger.error(f"Fehler beim Laden der Import-Historie: {e}")
        return []

    # ── Employees (IEmployeeRepository) ──

    def get_employees(self) -> List[Employee]:
        try:
            resp = self._client.get('/pm/employees')
            if resp.get('success'):
                return [Employee.from_dict(e) for e in resp.get('data', {}).get('employees', [])]
        except APIError as e:
            logger.error(f"Fehler beim Laden der Mitarbeiter: {e}")
        return []

    def get_employee(self, emp_id: int) -> Optional[Employee]:
        try:
            resp = self._client.get(f'/pm/employees/{emp_id}')
            if resp.get('success'):
                return Employee.from_dict(resp.get('data', {}).get('employee', {}))
        except APIError as e:
            logger.error(f"Fehler beim Laden des Mitarbeiters {emp_id}: {e}")
        return None

    def create_employee(self, data: Dict) -> Optional[Employee]:
        try:
            resp = self._client.post('/pm/employees', json_data=data)
            if resp.get('success'):
                return Employee.from_dict(resp.get('data', {}).get('employee', {}))
        except APIError as e:
            logger.error(f"Fehler beim Erstellen des Mitarbeiters: {e}")
        return None

    def update_employee(self, emp_id: int, data: Dict) -> Tuple[bool, Optional[RecalcSummary]]:
        try:
            resp = self._client.put(f'/pm/employees/{emp_id}', json_data=data)
            success = resp.get('success', False)
            summary = RecalcSummary.from_dict(resp.get('data', {}).get('recalc_summary'))
            return success, summary
        except APIError as e:
            logger.error(f"Fehler beim Aktualisieren des Mitarbeiters {emp_id}: {e}")
        return False, None

    def delete_employee(self, emp_id: int, hard: bool = False) -> bool:
        try:
            url = f'/pm/employees/{emp_id}'
            if hard:
                url += '?hard=1'
            resp = self._client.delete(url)
            return resp.get('success', False)
        except APIError as e:
            logger.error(f"Fehler beim Deaktivieren des Mitarbeiters {emp_id}: {e}")
            raise

    # ── Contracts (IContractRepository) ──

    def get_contracts(self, berater_id: int = None, status: str = None,
                      q: str = None, limit: int = 500) -> List[Contract]:
        params = {'limit': limit}
        if berater_id:
            params['berater_id'] = berater_id
        if status:
            params['status'] = status
        if q:
            params['q'] = q
        try:
            resp = self._client.get('/pm/contracts', params=params)
            if resp.get('success'):
                return [Contract.from_dict(c) for c in resp.get('data', {}).get('contracts', [])]
        except APIError as e:
            logger.error(f"Fehler beim Laden der Verträge: {e}")
        return []

    def get_unmatched_contracts(self, von: str = None, bis: str = None,
                                q: str = None,
                                page: int = 1, per_page: int = 50) -> Tuple[List[Contract], Optional[PaginationInfo]]:
        params = {'page': page, 'per_page': per_page}
        if von:
            params['von'] = von
        if bis:
            params['bis'] = bis
        if q:
            params['q'] = q
        try:
            resp = self._client.get('/pm/contracts/unmatched', params=params)
            if resp.get('success'):
                data = resp.get('data', {})
                contracts = [Contract.from_dict(c) for c in data.get('contracts', [])]
                pagination = PaginationInfo.from_dict(data['pagination']) if data.get('pagination') else None
                return contracts, pagination
        except APIError as e:
            logger.error(f"Fehler beim Laden ungematchter Verträge: {e}")
        return [], None

    def assign_berater_to_contract(self, contract_id: int, berater_id: int) -> bool:
        try:
            resp = self._client.put(f'/pm/contracts/{contract_id}', json_data={'berater_id': berater_id})
            return resp.get('success', False)
        except APIError as e:
            logger.error(f"Fehler beim Zuordnen von Berater {berater_id} zu Vertrag {contract_id}: {e}")
        return False

    # ── Mappings (IMappingRepository) ──

    def get_mappings(self, include_unmapped: bool = False) -> Dict:
        params = {}
        if include_unmapped:
            params['include_unmapped'] = '1'
        try:
            resp = self._client.get('/pm/mappings', params=params)
            if resp.get('success'):
                return {
                    'mappings': [VermittlerMapping.from_dict(m) for m in resp.get('data', {}).get('mappings', [])],
                    'unmapped': resp.get('data', {}).get('unmapped', []),
                }
        except APIError as e:
            logger.error(f"Fehler beim Laden der Vermittler-Mappings: {e}")
        return {'mappings': [], 'unmapped': []}

    def create_mapping(self, vermittler_name: str, berater_id: int) -> Optional[int]:
        try:
            resp = self._client.post('/pm/mappings', json_data={
                'vermittler_name': vermittler_name,
                'berater_id': berater_id,
            })
            if resp.get('success'):
                return resp.get('data', {}).get('id')
        except APIError as e:
            logger.error(f"Fehler beim Erstellen des Mappings: {e}")
        return None

    def delete_mapping(self, mapping_id: int) -> bool:
        try:
            resp = self._client.delete(f'/pm/mappings/{mapping_id}')
            return resp.get('success', False)
        except APIError as e:
            logger.error(f"Fehler beim Löschen des Mappings {mapping_id}: {e}")
        return False

    # ── Models (IModelRepository) ──

    def get_models(self) -> List[CommissionModel]:
        try:
            resp = self._client.get('/pm/models')
            if resp.get('success'):
                return [CommissionModel.from_dict(m) for m in resp.get('data', {}).get('models', [])]
        except APIError as e:
            logger.error(f"Fehler beim Laden der Provisionsmodelle: {e}")
        return []

    def create_model(self, data: Dict) -> Optional[CommissionModel]:
        try:
            resp = self._client.post('/pm/models', json_data=data)
            if resp.get('success'):
                return CommissionModel.from_dict(resp.get('data', {}).get('model', {}))
        except APIError as e:
            logger.error(f"Fehler beim Erstellen des Provisionsmodells: {e}")
        return None

    def update_model(self, model_id: int, data: Dict) -> Tuple[bool, Optional[RecalcSummary]]:
        try:
            resp = self._client.put(f'/pm/models/{model_id}', json_data=data)
            success = resp.get('success', False)
            summary = RecalcSummary.from_dict(resp.get('data', {}).get('recalc_summary'))
            return success, summary
        except APIError as e:
            logger.error(f"Fehler beim Aktualisieren des Provisionsmodells {model_id}: {e}")
        return False, None

    def delete_model(self, model_id: int) -> bool:
        try:
            resp = self._client.delete(f'/pm/models/{model_id}')
            return resp.get('success', False)
        except APIError as e:
            logger.error(f"Fehler beim Deaktivieren des Provisionsmodells {model_id}: {e}")
        return False

    # ── Abrechnungen (IAbrechnungRepository) ──

    def get_abrechnungen(self, monat: str = None) -> List[BeraterAbrechnung]:
        params = {}
        if monat:
            params['monat'] = monat
        try:
            resp = self._client.get('/pm/abrechnungen', params=params)
            if resp.get('success'):
                return [BeraterAbrechnung.from_dict(a) for a in resp.get('data', {}).get('abrechnungen', [])]
        except APIError as e:
            logger.error(f"Fehler beim Laden der Abrechnungen: {e}")
        return []

    def generate_abrechnung(self, monat: str) -> Dict:
        try:
            resp = self._client.post('/pm/abrechnungen', json_data={'monat': monat})
            if resp.get('success'):
                return resp.get('data', {})
        except APIError as e:
            logger.error(f"Fehler beim Generieren der Abrechnung: {e}")
        return {}

    def update_abrechnung_status(self, abrechnung_id: int, status: str) -> bool:
        try:
            resp = self._client.put(
                f'/pm/abrechnungen/{abrechnung_id}',
                json_data={'status': status}
            )
            return resp.get('success', False)
        except APIError as e:
            logger.error(f"Fehler beim Aktualisieren der Abrechnung {abrechnung_id}: {e}")
        return False

    # ── Audit (IAuditRepository) ──

    def get_audit_log(self, entity_type: str = None, entity_id: int = None,
                      limit: int = 100) -> List[Dict]:
        path = '/pm/audit'
        if entity_type and entity_id:
            path = f'/pm/audit/{entity_type}/{entity_id}'
        try:
            resp = self._client.get(path, params={'limit': limit})
            if resp.get('success'):
                return resp.get('data', {}).get('entries', [])
        except APIError as e:
            logger.error(f"Fehler beim Laden des PM-Audit-Logs: {e}")
        return []

    # ── Reset ──

    def reset_provision_data(self) -> Dict:
        try:
            resp = self._client.post('/pm/reset', {})
            if resp.get('success'):
                return resp.get('data', {})
            raise APIError(resp.get('message', 'Reset fehlgeschlagen'))
        except APIError as e:
            logger.error(f"Fehler beim Reset der Provision-Daten: {e}")
            raise
