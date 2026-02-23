"""
BiPro API - Provisionsmanagement

Geschaeftsfuehrer-Ebene: Mitarbeiter, Provisionen, Vertraege,
Importe, Abrechnungen, Vermittler-Mappings.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import date
import logging

from .client import APIClient, APIError

logger = logging.getLogger(__name__)


@dataclass
class CommissionModel:
    """Provisionssatzmodell."""
    id: int = 0
    name: str = ''
    description: Optional[str] = None
    commission_rate: float = 0.0
    is_active: bool = True

    @classmethod
    def from_dict(cls, d: Dict) -> 'CommissionModel':
        return cls(
            id=int(d.get('id', 0)),
            name=d.get('name', ''),
            description=d.get('description'),
            commission_rate=float(d.get('commission_rate', 0)),
            is_active=bool(int(d.get('is_active', 1))),
        )


@dataclass
class Employee:
    """Berater/Teamleiter/Backoffice."""
    id: int = 0
    user_id: Optional[int] = None
    name: str = ''
    role: str = 'consulter'
    commission_model_id: Optional[int] = None
    commission_rate_override: Optional[float] = None
    tl_override_rate: float = 0.0
    tl_override_basis: str = 'berater_anteil'
    teamleiter_id: Optional[int] = None
    is_active: bool = True
    notes: Optional[str] = None
    model_name: Optional[str] = None
    model_rate: Optional[float] = None
    teamleiter_name: Optional[str] = None

    @property
    def effective_rate(self) -> float:
        if self.commission_rate_override is not None:
            return self.commission_rate_override
        return self.model_rate or 0.0

    @classmethod
    def from_dict(cls, d: Dict) -> 'Employee':
        return cls(
            id=int(d.get('id', 0)),
            user_id=int(d['user_id']) if d.get('user_id') else None,
            name=d.get('name', ''),
            role=d.get('role', 'consulter'),
            commission_model_id=int(d['commission_model_id']) if d.get('commission_model_id') else None,
            commission_rate_override=float(d['commission_rate_override']) if d.get('commission_rate_override') is not None else None,
            tl_override_rate=float(d.get('tl_override_rate', 0)),
            tl_override_basis=d.get('tl_override_basis', 'berater_anteil'),
            teamleiter_id=int(d['teamleiter_id']) if d.get('teamleiter_id') else None,
            is_active=bool(int(d.get('is_active', 1))),
            notes=d.get('notes'),
            model_name=d.get('model_name'),
            model_rate=float(d['model_rate']) if d.get('model_rate') is not None else None,
            teamleiter_name=d.get('teamleiter_name'),
        )


@dataclass
class Contract:
    """Vertrag aus Xempus/VU."""
    id: int = 0
    vsnr: str = ''
    vsnr_normalized: str = ''
    versicherer: Optional[str] = None
    versicherungsnehmer: Optional[str] = None
    sparte: Optional[str] = None
    tarif: Optional[str] = None
    beitrag: Optional[float] = None
    beginn: Optional[str] = None
    berater_id: Optional[int] = None
    berater_name: Optional[str] = None
    status: str = 'offen'
    source: str = 'manuell'
    xempus_id: Optional[str] = None
    provision_count: int = 0
    provision_summe: float = 0.0

    @classmethod
    def from_dict(cls, d: Dict) -> 'Contract':
        return cls(
            id=int(d.get('id', 0)),
            vsnr=d.get('vsnr', '') or '',
            vsnr_normalized=d.get('vsnr_normalized', '') or '',
            versicherer=d.get('versicherer'),
            versicherungsnehmer=d.get('versicherungsnehmer'),
            sparte=d.get('sparte'),
            tarif=d.get('tarif'),
            beitrag=float(d['beitrag']) if d.get('beitrag') is not None else None,
            beginn=d.get('beginn'),
            berater_id=int(d['berater_id']) if d.get('berater_id') else None,
            berater_name=d.get('berater_name'),
            status=d.get('status', 'offen'),
            source=d.get('source', 'manuell'),
            xempus_id=d.get('xempus_id'),
            provision_count=int(d.get('provision_count', 0)),
            provision_summe=float(d.get('provision_summe', 0)),
        )


@dataclass
class ContractSearchResult:
    """Vertrag mit Match-Score aus match-suggestions Endpoint."""
    contract: Contract = None
    match_score: int = 0
    match_reason: str = ''
    source_type: Optional[str] = None
    vu_name: Optional[str] = None

    @classmethod
    def from_dict(cls, d: Dict) -> 'ContractSearchResult':
        return cls(
            contract=Contract.from_dict(d),
            match_score=int(d.get('match_score', 0)),
            match_reason=d.get('match_reason', ''),
            source_type=d.get('source_type'),
            vu_name=d.get('vu_name'),
        )


@dataclass
class PaginationInfo:
    """Server-seitige Pagination-Metadaten."""
    page: int = 1
    per_page: int = 50
    total: int = 0
    total_pages: int = 0

    @classmethod
    def from_dict(cls, d: Dict) -> 'PaginationInfo':
        return cls(
            page=int(d.get('page', 1)),
            per_page=int(d.get('per_page', 50)),
            total=int(d.get('total', 0)),
            total_pages=int(d.get('total_pages', 0)),
        )


@dataclass
class Commission:
    """Einzelne Provisionsbuchung."""
    id: int = 0
    contract_id: Optional[int] = None
    vsnr: str = ''
    vsnr_normalized: str = ''
    betrag: float = 0.0
    art: str = 'ap'
    auszahlungsdatum: Optional[str] = None
    versicherer: Optional[str] = None
    vu_name: Optional[str] = None
    versicherungsnehmer: Optional[str] = None
    vermittler_name: Optional[str] = None
    berater_id: Optional[int] = None
    berater_name: Optional[str] = None
    xempus_berater_name: Optional[str] = None
    xempus_consultation_id: Optional[str] = None
    match_status: str = 'unmatched'
    match_confidence: Optional[float] = None
    berater_anteil: Optional[float] = None
    tl_anteil: Optional[float] = None
    ag_anteil: Optional[float] = None
    import_batch_id: Optional[int] = None
    import_source_type: Optional[str] = None
    import_vu_name: Optional[str] = None

    @property
    def source_label(self) -> str:
        if self.import_source_type == 'xempus':
            return "Xempus"
        if self.import_source_type and self.import_vu_name:
            return f"VU-Liste {self.import_vu_name}"
        if self.import_vu_name:
            return self.import_vu_name
        return "\u2014"

    @classmethod
    def from_dict(cls, d: Dict) -> 'Commission':
        return cls(
            id=int(d.get('id', 0)),
            contract_id=int(d['contract_id']) if d.get('contract_id') else None,
            vsnr=d.get('vsnr', ''),
            vsnr_normalized=d.get('vsnr_normalized', ''),
            betrag=float(d.get('betrag', 0)),
            art=d.get('art', 'ap'),
            auszahlungsdatum=d.get('auszahlungsdatum'),
            versicherer=d.get('versicherer'),
            vu_name=d.get('vu_name') or d.get('versicherer'),
            versicherungsnehmer=d.get('versicherungsnehmer'),
            vermittler_name=d.get('vermittler_name'),
            berater_id=int(d['berater_id']) if d.get('berater_id') else None,
            berater_name=d.get('berater_name'),
            xempus_berater_name=d.get('xempus_berater_name'),
            xempus_consultation_id=d.get('xempus_consultation_id'),
            match_status=d.get('match_status', 'unmatched'),
            match_confidence=float(d['match_confidence']) if d.get('match_confidence') is not None else None,
            berater_anteil=float(d['berater_anteil']) if d.get('berater_anteil') is not None else None,
            tl_anteil=float(d['tl_anteil']) if d.get('tl_anteil') is not None else None,
            ag_anteil=float(d['ag_anteil']) if d.get('ag_anteil') is not None else None,
            import_batch_id=int(d['import_batch_id']) if d.get('import_batch_id') else None,
            import_source_type=d.get('import_source_type'),
            import_vu_name=d.get('import_vu_name'),
        )


@dataclass
class DashboardSummary:
    """Dashboard-KPIs."""
    monat: str = ''
    eingang_monat: float = 0.0
    rueckbelastung_monat: float = 0.0
    ag_monat: float = 0.0
    berater_monat: float = 0.0
    tl_monat: float = 0.0
    eingang_ytd: float = 0.0
    rueckbelastung_ytd: float = 0.0
    unmatched_count: int = 0
    total_positions: int = 0
    matched_positions: int = 0
    per_berater: List[Dict] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: Dict) -> 'DashboardSummary':
        return cls(
            monat=d.get('monat', ''),
            eingang_monat=float(d.get('eingang_monat', 0)),
            rueckbelastung_monat=float(d.get('rueckbelastung_monat', 0)),
            ag_monat=float(d.get('ag_monat', 0)),
            berater_monat=float(d.get('berater_monat', 0)),
            tl_monat=float(d.get('tl_monat', 0)),
            eingang_ytd=float(d.get('eingang_ytd', 0)),
            rueckbelastung_ytd=float(d.get('rueckbelastung_ytd', 0)),
            unmatched_count=int(d.get('unmatched_count', 0)),
            total_positions=int(d.get('total_positions', 0)),
            matched_positions=int(d.get('matched_positions', 0)),
            per_berater=d.get('per_berater', []),
        )


@dataclass
class ImportResult:
    """Ergebnis eines Import-Vorgangs."""
    batch_id: int = 0
    imported: int = 0
    updated: int = 0
    skipped: int = 0
    errors: int = 0
    matching: Optional[Dict] = None

    @classmethod
    def from_dict(cls, d: Dict) -> 'ImportResult':
        return cls(
            batch_id=int(d.get('batch_id', 0)),
            imported=int(d.get('imported', 0)),
            updated=int(d.get('updated', 0)),
            skipped=int(d.get('skipped', 0)),
            errors=int(d.get('errors', 0)),
            matching=d.get('matching'),
        )


@dataclass
class ImportBatch:
    """Import-Historie-Eintrag."""
    id: int = 0
    source_type: str = ''
    vu_name: Optional[str] = None
    filename: str = ''
    sheet_name: Optional[str] = None
    total_rows: int = 0
    imported_rows: int = 0
    matched_rows: int = 0
    skipped_rows: int = 0
    error_rows: int = 0
    imported_by_name: Optional[str] = None
    created_at: Optional[str] = None

    @classmethod
    def from_dict(cls, d: Dict) -> 'ImportBatch':
        return cls(
            id=int(d.get('id', 0)),
            source_type=d.get('source_type', ''),
            vu_name=d.get('vu_name'),
            filename=d.get('filename', ''),
            sheet_name=d.get('sheet_name'),
            total_rows=int(d.get('total_rows', 0)),
            imported_rows=int(d.get('imported_rows', 0)),
            matched_rows=int(d.get('matched_rows', 0)),
            skipped_rows=int(d.get('skipped_rows', 0)),
            error_rows=int(d.get('error_rows', 0)),
            imported_by_name=d.get('imported_by_name'),
            created_at=d.get('created_at'),
        )


@dataclass
class BeraterAbrechnung:
    """Monatsabrechnung pro Berater (Snapshot)."""
    id: int = 0
    abrechnungsmonat: str = ''
    berater_id: int = 0
    berater_name: str = ''
    berater_role: str = ''
    revision: int = 1
    brutto_provision: float = 0.0
    tl_abzug: float = 0.0
    netto_provision: float = 0.0
    rueckbelastungen: float = 0.0
    auszahlung: float = 0.0
    anzahl_provisionen: int = 0
    status: str = 'berechnet'
    is_locked: bool = False

    @classmethod
    def from_dict(cls, d: Dict) -> 'BeraterAbrechnung':
        return cls(
            id=int(d.get('id', 0)),
            abrechnungsmonat=d.get('abrechnungsmonat', ''),
            berater_id=int(d.get('berater_id', 0)),
            berater_name=d.get('berater_name', ''),
            berater_role=d.get('berater_role', ''),
            revision=int(d.get('revision', 1)),
            brutto_provision=float(d.get('brutto_provision', 0)),
            tl_abzug=float(d.get('tl_abzug', 0)),
            netto_provision=float(d.get('netto_provision', 0)),
            rueckbelastungen=float(d.get('rueckbelastungen', 0)),
            auszahlung=float(d.get('auszahlung', 0)),
            anzahl_provisionen=int(d.get('anzahl_provisionen', 0)),
            status=d.get('status', 'berechnet'),
            is_locked=bool(int(d.get('is_locked', 0))),
        )


@dataclass
class VermittlerMapping:
    """VU-Vermittlername → interner Berater."""
    id: int = 0
    vermittler_name: str = ''
    vermittler_name_normalized: str = ''
    berater_id: int = 0
    berater_name: Optional[str] = None
    created_at: Optional[str] = None

    @classmethod
    def from_dict(cls, d: Dict) -> 'VermittlerMapping':
        return cls(
            id=int(d.get('id', 0)),
            vermittler_name=d.get('vermittler_name', ''),
            vermittler_name_normalized=d.get('vermittler_name_normalized', ''),
            berater_id=int(d.get('berater_id', 0)),
            berater_name=d.get('berater_name'),
            created_at=d.get('created_at'),
        )


class ProvisionAPI:
    """API-Client fuer Provisionsmanagement."""

    def __init__(self, client: APIClient):
        self.client = client

    # ── Employees ──

    def get_employees(self) -> List[Employee]:
        try:
            resp = self.client.get('/pm/employees')
            if resp.get('success'):
                return [Employee.from_dict(e) for e in resp.get('data', {}).get('employees', [])]
        except APIError as e:
            logger.error(f"Fehler beim Laden der Mitarbeiter: {e}")
        return []

    def get_employee(self, emp_id: int) -> Optional[Employee]:
        try:
            resp = self.client.get(f'/pm/employees/{emp_id}')
            if resp.get('success'):
                return Employee.from_dict(resp.get('data', {}).get('employee', {}))
        except APIError as e:
            logger.error(f"Fehler beim Laden des Mitarbeiters {emp_id}: {e}")
        return None

    def create_employee(self, data: Dict) -> Optional[Employee]:
        try:
            resp = self.client.post('/pm/employees', json_data=data)
            if resp.get('success'):
                return Employee.from_dict(resp.get('data', {}).get('employee', {}))
        except APIError as e:
            logger.error(f"Fehler beim Erstellen des Mitarbeiters: {e}")
        return None

    def update_employee(self, emp_id: int, data: Dict) -> bool:
        try:
            resp = self.client.put(f'/pm/employees/{emp_id}', json_data=data)
            return resp.get('success', False)
        except APIError as e:
            logger.error(f"Fehler beim Aktualisieren des Mitarbeiters {emp_id}: {e}")
        return False

    def delete_employee(self, emp_id: int, hard: bool = False) -> bool:
        """Mitarbeiter deaktivieren (soft) oder loeschen (hard).

        Bei hard=True gibt der Server 409 zurueck wenn noch Commissions zugeordnet sind.
        """
        try:
            url = f'/pm/employees/{emp_id}'
            if hard:
                url += '?hard=1'
            resp = self.client.delete(url)
            return resp.get('success', False)
        except APIError as e:
            logger.error(f"Fehler beim {'Loeschen' if hard else 'Deaktivieren'} des Mitarbeiters {emp_id}: {e}")
            raise

    # ── Contracts ──

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
            resp = self.client.get('/pm/contracts', params=params)
            if resp.get('success'):
                return [Contract.from_dict(c) for c in resp.get('data', {}).get('contracts', [])]
        except APIError as e:
            logger.error(f"Fehler beim Laden der Vertraege: {e}")
        return []

    def assign_berater_to_contract(self, contract_id: int, berater_id: int) -> bool:
        return self.update_contract(contract_id, {'berater_id': berater_id})

    def update_contract(self, contract_id: int, data: Dict) -> bool:
        try:
            resp = self.client.put(f'/pm/contracts/{contract_id}', json_data=data)
            return resp.get('success', False)
        except APIError as e:
            logger.error(f"Fehler beim Aktualisieren des Vertrags {contract_id}: {e}")
        return False

    # ── Commissions ──

    def get_commissions(self, berater_id: int = None, match_status: str = None,
                        von: str = None, bis: str = None, versicherer: str = None,
                        q: str = None,
                        page: int = None, per_page: int = None,
                        limit: int = 500) -> tuple:
        """Provisionen laden. Mit page/per_page: gibt (list, PaginationInfo) zurueck.
        Ohne page: gibt (list, None) zurueck (Legacy-Modus).
        """
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
        try:
            resp = self.client.get('/pm/commissions', params=params)
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
            resp = self.client.put(
                f'/pm/commissions/{commission_id}/match',
                json_data={'contract_id': contract_id, 'berater_id': berater_id}
            )
            return resp.get('success', False)
        except APIError as e:
            logger.error(f"Fehler beim manuellen Matching {commission_id}: {e}")
        return False

    def ignore_commission(self, commission_id: int) -> bool:
        try:
            resp = self.client.put(f'/pm/commissions/{commission_id}/ignore', json_data={})
            return resp.get('success', False)
        except APIError as e:
            logger.error(f"Fehler beim Ignorieren der Provision {commission_id}: {e}")
        return False

    def recalculate_splits(self) -> int:
        try:
            resp = self.client.post('/pm/commissions/recalculate', json_data={})
            if resp.get('success'):
                return resp.get('data', {}).get('recalculated', 0)
        except APIError as e:
            logger.error(f"Fehler bei Split-Neuberechnung: {e}")
        return 0

    # ── Import ──

    def import_vu_liste(self, rows: List[Dict], filename: str,
                        sheet_name: str = None, vu_name: str = None,
                        file_hash: str = None,
                        skip_match: bool = False,
                        retries: int = None) -> Optional[ImportResult]:
        try:
            resp = self.client.post('/pm/import/vu-liste', json_data={
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
            resp = self.client.post('/pm/import/xempus', json_data={
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
            resp = self.client.post('/pm/import/match', json_data=data, timeout=120)
            if resp.get('success'):
                return resp.get('data', {}).get('stats', {})
        except APIError as e:
            logger.error(f"Fehler beim Auto-Matching: {e}")
        return {}

    def get_import_batches(self) -> List[ImportBatch]:
        try:
            resp = self.client.get('/pm/import/batches')
            if resp.get('success'):
                return [ImportBatch.from_dict(b) for b in resp.get('data', {}).get('batches', [])]
        except APIError as e:
            logger.error(f"Fehler beim Laden der Import-Historie: {e}")
        return []

    # ── Dashboard ──

    def get_dashboard_summary(self, von: str = None,
                             bis: str = None) -> Optional[DashboardSummary]:
        params = {}
        if von and bis:
            params['von'] = von
            params['bis'] = bis
        logger.debug(f"get_dashboard_summary params={params}")
        try:
            resp = self.client.get('/pm/dashboard/summary', params=params)
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
            resp = self.client.get(f'/pm/dashboard/berater/{berater_id}', params=params)
            if resp.get('success'):
                return resp.get('data', {})
        except APIError as e:
            logger.error(f"Fehler beim Laden der Berater-Details {berater_id}: {e}")
        return None

    # ── Mappings ──

    def get_mappings(self, include_unmapped: bool = False) -> Dict:
        params = {}
        if include_unmapped:
            params['include_unmapped'] = '1'
        try:
            resp = self.client.get('/pm/mappings', params=params)
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
            resp = self.client.post('/pm/mappings', json_data={
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
            resp = self.client.delete(f'/pm/mappings/{mapping_id}')
            return resp.get('success', False)
        except APIError as e:
            logger.error(f"Fehler beim Loeschen des Mappings {mapping_id}: {e}")
        return False

    # ── Abrechnungen ──

    def get_abrechnungen(self, monat: str = None) -> List[BeraterAbrechnung]:
        params = {}
        if monat:
            params['monat'] = monat
        try:
            resp = self.client.get('/pm/abrechnungen', params=params)
            if resp.get('success'):
                return [BeraterAbrechnung.from_dict(a) for a in resp.get('data', {}).get('abrechnungen', [])]
        except APIError as e:
            logger.error(f"Fehler beim Laden der Abrechnungen: {e}")
        return []

    def generate_abrechnung(self, monat: str) -> Dict:
        try:
            resp = self.client.post('/pm/abrechnungen', json_data={'monat': monat})
            if resp.get('success'):
                return resp.get('data', {})
        except APIError as e:
            logger.error(f"Fehler beim Generieren der Abrechnung: {e}")
        return {}

    def update_abrechnung_status(self, abrechnung_id: int, status: str) -> bool:
        try:
            resp = self.client.put(
                f'/pm/abrechnungen/{abrechnung_id}',
                json_data={'status': status}
            )
            return resp.get('success', False)
        except APIError as e:
            logger.error(f"Fehler beim Aktualisieren der Abrechnung {abrechnung_id}: {e}")
        return False

    # ── Models ──

    def get_models(self) -> List[CommissionModel]:
        try:
            resp = self.client.get('/pm/models')
            if resp.get('success'):
                return [CommissionModel.from_dict(m) for m in resp.get('data', {}).get('models', [])]
        except APIError as e:
            logger.error(f"Fehler beim Laden der Provisionsmodelle: {e}")
        return []

    def create_model(self, data: Dict) -> Optional[CommissionModel]:
        try:
            resp = self.client.post('/pm/models', json_data=data)
            if resp.get('success'):
                return CommissionModel.from_dict(resp.get('data', {}).get('model', {}))
        except APIError as e:
            logger.error(f"Fehler beim Erstellen des Provisionsmodells: {e}")
        return None

    def update_model(self, model_id: int, data: Dict) -> bool:
        try:
            resp = self.client.put(f'/pm/models/{model_id}', json_data=data)
            return resp.get('success', False)
        except APIError as e:
            logger.error(f"Fehler beim Aktualisieren des Provisionsmodells {model_id}: {e}")
        return False

    def delete_model(self, model_id: int) -> bool:
        try:
            resp = self.client.delete(f'/pm/models/{model_id}')
            return resp.get('success', False)
        except APIError as e:
            logger.error(f"Fehler beim Deaktivieren des Provisionsmodells {model_id}: {e}")
        return False

    # ── Match-Suggestions (Phase 2) ──

    def get_match_suggestions(self, commission_id: int = None,
                              contract_id: int = None,
                              direction: str = 'forward',
                              q: str = None,
                              limit: int = 50) -> Dict:
        """Match-Vorschlaege vom Server holen.

        Returns dict with 'suggestions' (list of ContractSearchResult or Commission dicts)
        and 'commission' or 'contract' (source record).
        """
        params = {'direction': direction, 'limit': limit}
        if commission_id:
            params['commission_id'] = commission_id
        if contract_id:
            params['contract_id'] = contract_id
        if q:
            params['q'] = q
        try:
            resp = self.client.get('/pm/match-suggestions', params=params)
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
        """Provision einem Vertrag transaktional zuordnen (Phase 4).

        Returns dict with 'commission' (updated) and 'message' on success.
        Raises APIError on conflict (409) or other errors.
        """
        try:
            resp = self.client.put('/pm/assign', json_data={
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

    def get_unmatched_contracts(self, von: str = None, bis: str = None,
                                q: str = None,
                                page: int = 1, per_page: int = 50) -> tuple:
        """Xempus-Vertraege ohne VU-Provision (Phase 5b).

        Returns (list[Contract], PaginationInfo).
        """
        params = {'page': page, 'per_page': per_page}
        if von:
            params['von'] = von
        if bis:
            params['bis'] = bis
        if q:
            params['q'] = q
        try:
            resp = self.client.get('/pm/contracts/unmatched', params=params)
            if resp.get('success'):
                data = resp.get('data', {})
                contracts = [Contract.from_dict(c) for c in data.get('contracts', [])]
                pagination = PaginationInfo.from_dict(data['pagination']) if data.get('pagination') else None
                return contracts, pagination
        except APIError as e:
            logger.error(f"Fehler beim Laden ungematchter Vertraege: {e}")
        return [], None

    # ── Clearance (Klaerfall-Counts) ──

    def get_clearance_counts(self) -> Dict:
        try:
            resp = self.client.get('/pm/clearance')
            if resp.get('success'):
                return resp.get('data', {})
        except APIError as e:
            logger.error(f"Fehler beim Laden der Klaerfall-Counts: {e}")
        return {'total': 0, 'no_contract': 0, 'no_berater': 0,
                'no_model': 0, 'no_split': 0}

    # ── Audit ──

    def get_audit_log(self, entity_type: str = None, entity_id: int = None,
                      limit: int = 100) -> List[Dict]:
        path = '/pm/audit'
        if entity_type and entity_id:
            path = f'/pm/audit/{entity_type}/{entity_id}'
        try:
            resp = self.client.get(path, params={'limit': limit})
            if resp.get('success'):
                return resp.get('data', {}).get('entries', [])
        except APIError as e:
            logger.error(f"Fehler beim Laden des PM-Audit-Logs: {e}")
        return []

    # ── Reset (Gefahrenzone) ──

    def reset_provision_data(self) -> Dict:
        """Loescht alle Import-Daten (Commissions, Contracts, Batches, Abrechnungen).

        Mitarbeiter, Modelle und Vermittler-Mappings bleiben erhalten.

        Returns:
            Dict mit 'deleted' (Anzahl geloeschter Zeilen pro Tabelle) und 'kept' (erhaltene Zeilen).
        """
        try:
            resp = self.client.post('/pm/reset', {})
            if resp.get('success'):
                return resp.get('data', {})
            raise APIError(resp.get('message', 'Reset fehlgeschlagen'))
        except APIError as e:
            logger.error(f"Fehler beim Reset der Provision-Daten: {e}")
            raise
