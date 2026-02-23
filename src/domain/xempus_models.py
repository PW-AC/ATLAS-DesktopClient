"""
Domain-Modelle fuer Xempus Insight Engine.

Dataclasses fuer alle Xempus-Entitaeten: Arbeitgeber, Tarife, Zuschuesse,
Arbeitnehmer, Beratungen, Import-Batches und Status-Mappings.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import date, datetime


@dataclass
class XempusEmployer:
    """Arbeitgeber aus Xempus."""
    id: str = ''
    name: str = ''
    street: Optional[str] = None
    plz: Optional[str] = None
    city: Optional[str] = None
    iban: Optional[str] = None
    bic: Optional[str] = None
    tarif_info: Optional[str] = None
    zuschuss_info: Optional[str] = None
    first_seen_batch_id: Optional[int] = None
    last_seen_batch_id: Optional[int] = None
    is_active: bool = True
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    employee_count: int = 0
    tariff_count: int = 0
    subsidy_count: int = 0

    @classmethod
    def from_dict(cls, d: Dict) -> 'XempusEmployer':
        return cls(
            id=d.get('id', ''),
            name=d.get('name', ''),
            street=d.get('street'),
            plz=d.get('plz'),
            city=d.get('city'),
            iban=d.get('iban'),
            bic=d.get('bic'),
            tarif_info=d.get('tarif_info'),
            zuschuss_info=d.get('zuschuss_info'),
            first_seen_batch_id=int(d['first_seen_batch_id']) if d.get('first_seen_batch_id') else None,
            last_seen_batch_id=int(d['last_seen_batch_id']) if d.get('last_seen_batch_id') else None,
            is_active=bool(int(d.get('is_active', 1))),
            created_at=d.get('created_at'),
            updated_at=d.get('updated_at'),
            employee_count=int(d.get('employee_count', 0)),
            tariff_count=int(d.get('tariff_count', 0)),
            subsidy_count=int(d.get('subsidy_count', 0)),
        )


@dataclass
class XempusTariff:
    """Tarif eines Arbeitgebers."""
    id: str = ''
    employer_id: Optional[str] = None
    versicherer: Optional[str] = None
    typ: Optional[str] = None
    durchfuehrungsweg: Optional[str] = None
    tarif: Optional[str] = None
    beantragung: Optional[str] = None
    gruppenrahmenkollektiv: Optional[str] = None
    gruppennummer: Optional[str] = None
    is_active: bool = True

    @classmethod
    def from_dict(cls, d: Dict) -> 'XempusTariff':
        return cls(
            id=d.get('id', ''),
            employer_id=d.get('employer_id'),
            versicherer=d.get('versicherer'),
            typ=d.get('typ'),
            durchfuehrungsweg=d.get('durchfuehrungsweg'),
            tarif=d.get('tarif'),
            beantragung=d.get('beantragung'),
            gruppenrahmenkollektiv=d.get('gruppenrahmenkollektiv'),
            gruppennummer=d.get('gruppennummer'),
            is_active=bool(int(d.get('is_active', 1))),
        )


@dataclass
class XempusSubsidy:
    """Zuschuss eines Arbeitgebers."""
    id: str = ''
    employer_id: Optional[str] = None
    bezeichnung: Optional[str] = None
    art_vl_umwandlung: Optional[str] = None
    zuschuss_vl_alternativ: Optional[float] = None
    prozent_auf_vl: Optional[bool] = None
    zuschuss_prozentual_leq_bbg: Optional[float] = None
    zuschuss_prozentual_gt_bbg: Optional[float] = None
    begrenzung_prozentual: Optional[str] = None
    fester_zuschuss: Optional[float] = None
    fester_arbg_beitrag: Optional[float] = None
    gestaffelter_zuschuss_aktiv: Optional[bool] = None
    gestaffelter_zuschuss: Optional[str] = None
    begrenzung_gestaffelt: Optional[str] = None
    is_active: bool = True

    @classmethod
    def from_dict(cls, d: Dict) -> 'XempusSubsidy':
        return cls(
            id=d.get('id', ''),
            employer_id=d.get('employer_id'),
            bezeichnung=d.get('bezeichnung'),
            art_vl_umwandlung=d.get('art_vl_umwandlung'),
            zuschuss_vl_alternativ=float(d['zuschuss_vl_alternativ']) if d.get('zuschuss_vl_alternativ') is not None else None,
            prozent_auf_vl=bool(int(d['prozent_auf_vl'])) if d.get('prozent_auf_vl') is not None else None,
            zuschuss_prozentual_leq_bbg=float(d['zuschuss_prozentual_leq_bbg']) if d.get('zuschuss_prozentual_leq_bbg') is not None else None,
            zuschuss_prozentual_gt_bbg=float(d['zuschuss_prozentual_gt_bbg']) if d.get('zuschuss_prozentual_gt_bbg') is not None else None,
            begrenzung_prozentual=d.get('begrenzung_prozentual'),
            fester_zuschuss=float(d['fester_zuschuss']) if d.get('fester_zuschuss') is not None else None,
            fester_arbg_beitrag=float(d['fester_arbg_beitrag']) if d.get('fester_arbg_beitrag') is not None else None,
            gestaffelter_zuschuss_aktiv=bool(int(d['gestaffelter_zuschuss_aktiv'])) if d.get('gestaffelter_zuschuss_aktiv') is not None else None,
            gestaffelter_zuschuss=d.get('gestaffelter_zuschuss'),
            begrenzung_gestaffelt=d.get('begrenzung_gestaffelt'),
            is_active=bool(int(d.get('is_active', 1))),
        )


@dataclass
class XempusEmployee:
    """Arbeitnehmer aus Xempus."""
    id: str = ''
    employer_id: Optional[str] = None
    employer_name: Optional[str] = None
    zuschuss_id: Optional[str] = None
    anrede: Optional[str] = None
    titel: Optional[str] = None
    name: str = ''
    vorname: str = ''
    beratungsstatus: Optional[str] = None
    status_category: Optional[str] = None
    status_label: Optional[str] = None
    status_color: Optional[str] = None
    street: Optional[str] = None
    plz: Optional[str] = None
    city: Optional[str] = None
    bundesland: Optional[str] = None
    land: Optional[str] = None
    geburtsdatum: Optional[str] = None
    telefon: Optional[str] = None
    mobiltelefon: Optional[str] = None
    email: Optional[str] = None
    diensteintritt: Optional[str] = None
    krankenversicherung: Optional[str] = None
    bruttolohn: Optional[float] = None
    steuerklasse: Optional[str] = None
    berufsstellung: Optional[str] = None
    berufsbezeichnung: Optional[str] = None
    personalnummer: Optional[str] = None
    is_active: bool = True

    @property
    def full_name(self) -> str:
        return f"{self.name} {self.vorname}".strip()

    @classmethod
    def from_dict(cls, d: Dict) -> 'XempusEmployee':
        return cls(
            id=d.get('id', ''),
            employer_id=d.get('employer_id'),
            employer_name=d.get('employer_name'),
            zuschuss_id=d.get('zuschuss_id'),
            anrede=d.get('anrede'),
            titel=d.get('titel'),
            name=d.get('name', ''),
            vorname=d.get('vorname', ''),
            beratungsstatus=d.get('beratungsstatus'),
            status_category=d.get('status_category'),
            status_label=d.get('status_label'),
            status_color=d.get('status_color'),
            street=d.get('street'),
            plz=d.get('plz'),
            city=d.get('city'),
            bundesland=d.get('bundesland'),
            land=d.get('land'),
            geburtsdatum=d.get('geburtsdatum'),
            telefon=d.get('telefon'),
            mobiltelefon=d.get('mobiltelefon'),
            email=d.get('email'),
            diensteintritt=d.get('diensteintritt'),
            krankenversicherung=d.get('krankenversicherung'),
            bruttolohn=float(d['bruttolohn']) if d.get('bruttolohn') is not None else None,
            steuerklasse=d.get('steuerklasse'),
            berufsstellung=d.get('berufsstellung'),
            berufsbezeichnung=d.get('berufsbezeichnung'),
            personalnummer=d.get('personalnummer'),
            is_active=bool(int(d.get('is_active', 1))),
        )


@dataclass
class XempusConsultation:
    """Beratung aus Xempus (alle Spalten)."""
    id: str = ''
    employee_id: Optional[str] = None
    employer_id: Optional[str] = None
    arbg_name: Optional[str] = None
    arbn_name: Optional[str] = None
    arbn_vorname: Optional[str] = None
    geburtsdatum: Optional[str] = None
    status: Optional[str] = None
    status_category: Optional[str] = None
    status_label: Optional[str] = None
    status_color: Optional[str] = None
    beratungsdatum: Optional[str] = None
    beginn: Optional[str] = None
    ende: Optional[str] = None
    arbn_anteil: Optional[float] = None
    arbg_anteil: Optional[float] = None
    gesamtbeitrag: Optional[float] = None
    versicherungsscheinnummer: Optional[str] = None
    versicherer: Optional[str] = None
    typ: Optional[str] = None
    durchfuehrungsweg: Optional[str] = None
    tarif: Optional[str] = None
    berater: Optional[str] = None
    beratungstyp: Optional[str] = None
    is_active: bool = True

    @property
    def full_name(self) -> str:
        return f"{self.arbn_name or ''} {self.arbn_vorname or ''}".strip()

    @classmethod
    def from_dict(cls, d: Dict) -> 'XempusConsultation':
        return cls(
            id=d.get('id', ''),
            employee_id=d.get('employee_id'),
            employer_id=d.get('employer_id'),
            arbg_name=d.get('arbg_name'),
            arbn_name=d.get('arbn_name'),
            arbn_vorname=d.get('arbn_vorname'),
            geburtsdatum=d.get('geburtsdatum'),
            status=d.get('status'),
            status_category=d.get('status_category'),
            status_label=d.get('status_label'),
            status_color=d.get('status_color'),
            beratungsdatum=d.get('beratungsdatum'),
            beginn=d.get('beginn'),
            ende=d.get('ende'),
            arbn_anteil=float(d['arbn_anteil']) if d.get('arbn_anteil') is not None else None,
            arbg_anteil=float(d['arbg_anteil']) if d.get('arbg_anteil') is not None else None,
            gesamtbeitrag=float(d['gesamtbeitrag']) if d.get('gesamtbeitrag') is not None else None,
            versicherungsscheinnummer=d.get('versicherungsscheinnummer'),
            versicherer=d.get('versicherer'),
            typ=d.get('typ'),
            durchfuehrungsweg=d.get('durchfuehrungsweg'),
            tarif=d.get('tarif'),
            berater=d.get('berater'),
            beratungstyp=d.get('beratungstyp'),
            is_active=bool(int(d.get('is_active', 1))),
        )


@dataclass
class XempusImportBatch:
    """Import-Batch mit Phase-Status und Parse-Statistiken."""
    id: int = 0
    filename: str = ''
    imported_at: Optional[str] = None
    imported_by: Optional[int] = None
    imported_by_name: Optional[str] = None
    record_counts: Optional[Dict] = None
    snapshot_hash: Optional[str] = None
    is_active_snapshot: bool = False
    import_phase: str = 'raw_ingest'
    previous_batch_id: Optional[int] = None
    notes: Optional[str] = None
    parse_stats: Optional[Dict] = None

    @classmethod
    def from_dict(cls, d: Dict) -> 'XempusImportBatch':
        rc = d.get('record_counts')
        if isinstance(rc, str):
            import json
            try:
                rc = json.loads(rc)
            except (ValueError, TypeError):
                rc = None

        return cls(
            id=int(d.get('id', 0)),
            filename=d.get('filename', ''),
            imported_at=d.get('imported_at'),
            imported_by=int(d['imported_by']) if d.get('imported_by') else None,
            imported_by_name=d.get('imported_by_name'),
            record_counts=rc,
            snapshot_hash=d.get('snapshot_hash'),
            is_active_snapshot=bool(int(d.get('is_active_snapshot', 0))),
            import_phase=d.get('import_phase', 'raw_ingest'),
            previous_batch_id=int(d['previous_batch_id']) if d.get('previous_batch_id') else None,
            notes=d.get('notes'),
            parse_stats=d.get('parse_stats'),
        )


@dataclass
class XempusStatusMapping:
    """Status-Text zu Kategorie Mapping."""
    id: int = 0
    raw_status: str = ''
    category: str = ''
    display_label: str = ''
    color: str = '#9e9e9e'
    is_active: bool = True

    @classmethod
    def from_dict(cls, d: Dict) -> 'XempusStatusMapping':
        return cls(
            id=int(d.get('id', 0)),
            raw_status=d.get('raw_status', ''),
            category=d.get('category', ''),
            display_label=d.get('display_label', ''),
            color=d.get('color', '#9e9e9e'),
            is_active=bool(int(d.get('is_active', 1))),
        )


@dataclass
class XempusStats:
    """Aggregierte Xempus-Statistiken."""
    total_employers: int = 0
    total_employees: int = 0
    total_consultations: int = 0
    ansprache_quote: float = 0.0
    abschluss_quote: float = 0.0
    erfolgs_quote: float = 0.0
    status_distribution: List[Dict] = field(default_factory=list)
    per_employer: List[Dict] = field(default_factory=list)
    unmapped_statuses: List[Dict] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: Dict) -> 'XempusStats':
        return cls(
            total_employers=int(d.get('total_employers', 0)),
            total_employees=int(d.get('total_employees', 0)),
            total_consultations=int(d.get('total_consultations', 0)),
            ansprache_quote=float(d.get('ansprache_quote', 0)),
            abschluss_quote=float(d.get('abschluss_quote', 0)),
            erfolgs_quote=float(d.get('erfolgs_quote', 0)),
            status_distribution=d.get('status_distribution', []),
            per_employer=d.get('per_employer', []),
            unmapped_statuses=d.get('unmapped_statuses', []),
        )


@dataclass
class XempusDiff:
    """Snapshot-Diff zwischen zwei Imports."""
    batch_id: int = 0
    previous_batch_id: Optional[int] = None
    employers: Optional[Dict] = None
    employees: Optional[Dict] = None
    consultations: Optional[Dict] = None
    status_changes: List[Dict] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: Dict) -> 'XempusDiff':
        diff = d.get('diff') or {}
        return cls(
            batch_id=int(d.get('batch_id', 0)),
            previous_batch_id=int(d['previous_batch_id']) if d.get('previous_batch_id') else None,
            employers=diff.get('employers'),
            employees=diff.get('employees'),
            consultations=diff.get('consultations'),
            status_changes=diff.get('status_changes', []),
        )
