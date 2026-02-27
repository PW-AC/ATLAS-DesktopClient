"""
Domain-Entitäten für das Provisionsmanagement.

Reine Datenklassen ohne externe Abhängigkeiten.
Migriert aus api/provision.py in den Domain Layer.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict


@dataclass
class CommissionModel:
    """Provisionssatzmodell."""
    id: int = 0
    name: str = ''
    description: Optional[str] = None
    commission_rate: float = 0.0
    tl_rate: Optional[float] = None
    tl_basis: Optional[str] = None
    is_active: bool = True

    @classmethod
    def from_dict(cls, d: Dict) -> 'CommissionModel':
        tl_rate_raw = d.get('tl_rate')
        return cls(
            id=int(d.get('id', 0)),
            name=d.get('name', ''),
            description=d.get('description'),
            commission_rate=float(d.get('commission_rate', 0)),
            tl_rate=float(tl_rate_raw) if tl_rate_raw is not None else None,
            tl_basis=d.get('tl_basis'),
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
class RecalcSummary:
    """Zusammenfassung einer Neuberechnung nach Ratenänderung."""
    splits_recalculated: int = 0
    abrechnungen_regenerated: int = 0
    affected_employees: int = 0
    from_date: Optional[str] = None

    @classmethod
    def from_dict(cls, d: Optional[Dict]) -> Optional['RecalcSummary']:
        if not d:
            return None
        return cls(
            splits_recalculated=int(d.get('splits_recalculated', 0)),
            abrechnungen_regenerated=int(d.get('abrechnungen_regenerated', 0)),
            affected_employees=int(d.get('affected_employees', 0)),
            from_date=d.get('from_date'),
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
    import_sheet_name: Optional[str] = None
    is_relevant: bool = True
    source_row: Optional[int] = None
    buchungsart_raw: Optional[str] = None
    konditionssatz: Optional[str] = None
    courtage_rate: Optional[float] = None

    @property
    def source_label(self) -> str:
        if self.import_source_type == 'xempus':
            return "Xempus"
        if self.import_source_type == 'vu_liste':
            name = self.import_sheet_name or self.import_vu_name
            if name:
                return f"VU-Liste {name}"
        if self.import_sheet_name:
            return self.import_sheet_name
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
            import_sheet_name=d.get('import_sheet_name'),
            is_relevant=bool(int(d.get('is_relevant', 1))),
            source_row=int(d['source_row']) if d.get('source_row') else None,
            buchungsart_raw=d.get('buchungsart_raw'),
            konditionssatz=d.get('konditionssatz'),
            courtage_rate=float(d['courtage_rate']) if d.get('courtage_rate') is not None else None,
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
