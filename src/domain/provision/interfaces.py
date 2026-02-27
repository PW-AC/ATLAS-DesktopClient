"""
Interfaces (Protocols) für das Provisionsmanagement.

Definiert die Verträge zwischen Schichten.
Domain und UseCases hängen nur von diesen Interfaces ab,
nie von konkreten Implementierungen.
"""

from typing import Protocol, Optional, List, Dict, Tuple, runtime_checkable

from .entities import (
    Commission, Contract, Employee, CommissionModel,
    DashboardSummary, ImportResult, ImportBatch,
    BeraterAbrechnung, VermittlerMapping, ContractSearchResult,
    PaginationInfo, RecalcSummary,
)


# ═══════════════════════════════════════════════════════════
# Repository Interfaces (implementiert in Infrastructure)
# ═══════════════════════════════════════════════════════════


@runtime_checkable
class IProvisionRepository(Protocol):
    """Zugriff auf Provisionsdaten (API/DB)."""

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
    ) -> Tuple[List[Commission], Optional[PaginationInfo]]: ...

    def match_commission(self, commission_id: int, contract_id: int = None,
                         berater_id: int = None) -> bool: ...

    def ignore_commission(self, commission_id: int) -> bool: ...

    def recalculate_splits(self) -> int: ...

    def get_dashboard_summary(self, von: str = None,
                              bis: str = None) -> Optional[DashboardSummary]: ...

    def get_clearance_counts(self, von: str = None, bis: str = None) -> Dict: ...

    def get_match_suggestions(self, commission_id: int = None,
                              contract_id: int = None,
                              direction: str = 'forward',
                              q: str = None,
                              limit: int = 50) -> Dict: ...

    def assign_contract(self, commission_id: int, contract_id: int,
                        force_override: bool = False) -> Dict: ...


@runtime_checkable
class IImportRepository(Protocol):
    """Import von VU-Listen und Xempus-Daten."""

    def import_vu_liste(self, rows: List[Dict], filename: str,
                        sheet_name: str = None, vu_name: str = None,
                        file_hash: str = None,
                        skip_match: bool = False) -> Optional[ImportResult]: ...

    def import_xempus(self, rows: List[Dict], filename: str,
                      file_hash: str = None) -> Optional[ImportResult]: ...

    def trigger_auto_match(self, batch_id: int = None) -> Dict: ...

    def get_import_batches(self) -> List[ImportBatch]: ...


@runtime_checkable
class IEmployeeRepository(Protocol):
    """Zugriff auf Mitarbeiterdaten."""

    def get_employees(self) -> List[Employee]: ...
    def get_employee(self, emp_id: int) -> Optional[Employee]: ...
    def create_employee(self, data: Dict) -> Optional[Employee]: ...
    def update_employee(self, emp_id: int, data: Dict) -> Tuple[bool, Optional[RecalcSummary]]: ...
    def delete_employee(self, emp_id: int, hard: bool = False) -> bool: ...


@runtime_checkable
class IContractRepository(Protocol):
    """Zugriff auf Vertragsdaten."""

    def get_contracts(self, berater_id: int = None, status: str = None,
                      q: str = None, limit: int = 500) -> List[Contract]: ...
    def get_unmatched_contracts(self, von: str = None, bis: str = None,
                                q: str = None,
                                page: int = 1, per_page: int = 50) -> Tuple[List[Contract], Optional[PaginationInfo]]: ...
    def assign_berater_to_contract(self, contract_id: int, berater_id: int) -> bool: ...


@runtime_checkable
class IMappingRepository(Protocol):
    """Zugriff auf Vermittler-Mappings."""

    def get_mappings(self, include_unmapped: bool = False) -> Dict: ...
    def create_mapping(self, vermittler_name: str, berater_id: int) -> Optional[int]: ...
    def delete_mapping(self, mapping_id: int) -> bool: ...


@runtime_checkable
class IModelRepository(Protocol):
    """Zugriff auf Provisionsmodelle."""

    def get_models(self) -> List[CommissionModel]: ...
    def create_model(self, data: Dict) -> Optional[CommissionModel]: ...
    def update_model(self, model_id: int, data: Dict) -> Tuple[bool, Optional[RecalcSummary]]: ...
    def delete_model(self, model_id: int) -> bool: ...


@runtime_checkable
class IAbrechnungRepository(Protocol):
    """Zugriff auf Abrechnungen."""

    def get_abrechnungen(self, monat: str = None) -> List[BeraterAbrechnung]: ...
    def generate_abrechnung(self, monat: str) -> Dict: ...
    def update_abrechnung_status(self, abrechnung_id: int, status: str) -> bool: ...


@runtime_checkable
class IAuditRepository(Protocol):
    """Zugriff auf Audit-Logs."""

    def get_audit_log(self, entity_type: str = None, entity_id: int = None,
                      limit: int = 100) -> List[Dict]: ...


# ═══════════════════════════════════════════════════════════
# View Interfaces (implementiert in UI-Panels)
# ═══════════════════════════════════════════════════════════


@runtime_checkable
class IPositionsView(Protocol):
    """Interface für das Provisionspositionen-Panel."""

    def show_commissions(self, commissions: List[Commission],
                         pagination: Optional[PaginationInfo] = None) -> None: ...
    def show_loading(self, loading: bool) -> None: ...
    def show_error(self, message: str) -> None: ...
    def show_detail(self, commission: Commission) -> None: ...
    def update_filter_counts(self, total: int, filtered: int) -> None: ...


@runtime_checkable
class IDashboardView(Protocol):
    """Interface für das Dashboard-Panel."""

    def show_summary(self, summary: DashboardSummary) -> None: ...
    def show_clearance_counts(self, counts: Dict) -> None: ...
    def show_loading(self, loading: bool) -> None: ...
    def show_error(self, message: str) -> None: ...


@runtime_checkable
class IClearanceView(Protocol):
    """Interface für das Zuordnung/Klärfälle-Panel."""

    def show_commissions(self, commissions: List[Commission]) -> None: ...
    def show_mappings(self, mappings: List[VermittlerMapping],
                      unmapped: List[str]) -> None: ...
    def show_loading(self, loading: bool) -> None: ...
    def show_error(self, message: str) -> None: ...


@runtime_checkable
class IImportView(Protocol):
    """Interface für das Import/Abrechnungsläufe-Panel."""

    def show_batches(self, batches: List[ImportBatch]) -> None: ...
    def show_import_result(self, result: ImportResult) -> None: ...
    def show_parse_progress(self, message: str) -> None: ...
    def show_loading(self, loading: bool) -> None: ...
    def show_error(self, message: str) -> None: ...


@runtime_checkable
class IDistributionView(Protocol):
    """Interface für das Verteilschlüssel-Panel."""

    def show_employees(self, employees: List[Employee]) -> None: ...
    def show_models(self, models: List[CommissionModel]) -> None: ...
    def show_loading(self, loading: bool) -> None: ...
    def show_error(self, message: str) -> None: ...


@runtime_checkable
class IPayoutsView(Protocol):
    """Interface für das Auszahlungen-Panel."""

    def show_abrechnungen(self, abrechnungen: List[BeraterAbrechnung]) -> None: ...
    def show_loading(self, loading: bool) -> None: ...
    def show_error(self, message: str) -> None: ...
