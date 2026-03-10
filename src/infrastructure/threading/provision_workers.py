"""
QThread-Worker für das Provisionsmanagement.

Infrastructure Layer: Asynchrone Operationen mit Repository-Zugriff.
Worker kennen nur Repository-Interfaces, nicht die API direkt.
"""

from PySide6.QtCore import QThread, Signal
from typing import List, Dict, Optional

from infrastructure.api.provision_repository import ProvisionRepository
from domain.provision.entities import ImportResult, PaginationInfo
from i18n import de as texts
import logging

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════
# Dashboard
# ═══════════════════════════════════════════════════════


class DashboardLoadWorker(QThread):
    finished = Signal(object, object)
    error = Signal(str)

    def __init__(self, repo: ProvisionRepository, von: str = None, bis: str = None):
        super().__init__()
        self._repo = repo
        self._von = von
        self._bis = bis

    def run(self):
        try:
            summary = self._repo.get_dashboard_summary(von=self._von, bis=self._bis)
            clearance = self._repo.get_clearance_counts(von=self._von, bis=self._bis)
            self.finished.emit(summary, clearance)
        except Exception as e:
            self.error.emit(str(e))


class PerformanceLoadWorker(QThread):
    """Laedt die Erfolgsauswertung (3 Ebenen) im Hintergrund."""
    finished = Signal(object)
    error = Signal(str)

    def __init__(self, repo: ProvisionRepository, von: str = None, bis: str = None):
        super().__init__()
        self._repo = repo
        self._von = von
        self._bis = bis

    def run(self):
        try:
            data = self._repo.get_performance(von=self._von, bis=self._bis)
            self.finished.emit(data)
        except Exception as e:
            self.error.emit(str(e))


class BeraterDetailWorker(QThread):
    finished = Signal(int, str, dict, object)
    error = Signal(str)

    def __init__(self, repo: ProvisionRepository, berater_id: int, berater_name: str,
                 row_data: dict, von: str = None, bis: str = None):
        super().__init__()
        self._repo = repo
        self._berater_id = berater_id
        self._berater_name = berater_name
        self._row_data = row_data
        self._von = von
        self._bis = bis

    def run(self):
        try:
            detail = self._repo.get_berater_detail(self._berater_id, von=self._von, bis=self._bis)
            self.finished.emit(self._berater_id, self._berater_name, self._row_data, detail)
        except Exception as e:
            self.error.emit(str(e))


# ═══════════════════════════════════════════════════════
# Abrechnungsläufe (VU-Import)
# ═══════════════════════════════════════════════════════


class VuBatchesLoadWorker(QThread):
    finished = Signal(object)
    error = Signal(str)

    def __init__(self, repo: ProvisionRepository):
        super().__init__()
        self._repo = repo

    def run(self):
        try:
            batches = self._repo.get_import_batches()
            self.finished.emit(batches)
        except Exception as e:
            self.error.emit(str(e))


class VuParseFileWorker(QThread):
    """Parst VU-Provisionslisten im Hintergrund."""
    finished = Signal(object, str, str, str)
    error = Signal(str)

    def __init__(self, path: str):
        super().__init__()
        self._path = path
        self.raw_data_map: Dict = {}

    @staticmethod
    def _build_raw_data_map(results) -> Dict:
        raw_map = {}
        for pr in results:
            if pr.raw_headers or pr.raw_rows:
                raw_map[pr.sheet_name or pr.vu_name] = {
                    'headers': pr.raw_headers,
                    'rows': pr.raw_rows,
                    'total_rows': pr.total_rows,
                    'skipped_rows': pr.skipped_rows,
                }
        return raw_map

    def run(self):
        try:
            from services.provision_import import (
                get_available_vu_sheets, parse_vu_liste, detect_vu_format,
            )

            known_sheets = get_available_vu_sheets(self._path)
            if known_sheets:
                log = texts.PROVISION_IMPORT_DETECTED.format(sheets=', '.join(known_sheets))
                results = parse_vu_liste(self._path, selected_sheets=known_sheets)
                all_rows = []
                vu_names = []
                for pr in results:
                    for row in pr.rows:
                        row['_vu_name'] = pr.vu_name
                        row['_sheet_name'] = pr.sheet_name
                    all_rows.extend(pr.rows)
                    if pr.rows:
                        vu_names.append(pr.vu_name)
                self.raw_data_map = self._build_raw_data_map(results)
                vu = ', '.join(vu_names) if vu_names else (known_sheets[0] if known_sheets else '')
                sheet = known_sheets[0] if len(known_sheets) == 1 else None
                log += f"\n{len(all_rows)} {texts.PROVISION_IMPORT_ROWS_FOUND}"
                self.finished.emit(all_rows, vu, sheet, log)
            else:
                detected = detect_vu_format(self._path)
                if detected:
                    vu_name, confidence = detected[0]
                    log = texts.PROVISION_IMPORT_AUTODETECT.format(
                        vu=vu_name, confidence=f"{confidence*100:.0f}%")
                    results = parse_vu_liste(self._path, selected_sheets=[vu_name])
                    all_rows = []
                    for pr in results:
                        all_rows.extend(pr.rows)
                    self.raw_data_map = self._build_raw_data_map(results)
                    log += f"\n{len(all_rows)} {texts.PROVISION_IMPORT_ROWS_FOUND}"
                    self.finished.emit(all_rows, vu_name, vu_name, log)
                else:
                    self.finished.emit([], '', None,
                                       texts.PROVISION_IMPORT_NO_FORMAT)
        except Exception as e:
            self.error.emit(str(e))


class VuImportWorker(QThread):
    finished = Signal(object)
    error = Signal(str)
    progress = Signal(str)

    def __init__(self, repo: ProvisionRepository, rows: List[Dict], filename: str,
                 sheet_name: str, vu_name: str, file_hash: str,
                 raw_data_map: Dict = None):
        super().__init__()
        self._repo = repo
        self._rows = rows
        self._filename = filename
        self._sheet_name = sheet_name
        self._vu_name = vu_name
        self._file_hash = file_hash
        self._raw_data_map = raw_data_map or {}

    def run(self):
        try:
            from collections import defaultdict

            vu_groups = defaultdict(list)
            for row in self._rows:
                vu = row.get('_vu_name', self._vu_name)
                sheet = row.get('_sheet_name', self._sheet_name)
                clean_row = {k: v for k, v in row.items()
                             if k not in ('_vu_name', '_sheet_name')}
                vu_groups[(vu, sheet)].append(clean_row)

            accumulated = ImportResult()
            chunk_size = 2000
            batch_map = {}

            for (vu_name, sheet_name), vu_rows in vu_groups.items():
                chunks = [vu_rows[i:i+chunk_size] for i in range(0, len(vu_rows), chunk_size)]
                for idx, chunk in enumerate(chunks):
                    self.progress.emit(
                        texts.PROVISION_IMPORT_PROGRESS_CHUNK.format(
                            sheet=sheet_name or vu_name or self._filename,
                            current=idx + 1,
                            total=len(chunks),
                        )
                    )
                    is_last_chunk_of_last_vu = (
                        (vu_name, sheet_name) == list(vu_groups.keys())[-1]
                        and idx == len(chunks) - 1
                    )
                    result = self._repo.import_vu_liste(
                        rows=chunk,
                        filename=self._filename,
                        sheet_name=sheet_name or vu_name,
                        vu_name=vu_name,
                        file_hash=self._file_hash,
                        skip_match=not is_last_chunk_of_last_vu,
                    )
                    if result:
                        accumulated.imported += result.imported
                        accumulated.updated += result.updated
                        accumulated.skipped += result.skipped
                        accumulated.errors += result.errors
                        accumulated.batch_id = result.batch_id
                        if result.matching:
                            accumulated.matching = result.matching
                        batch_map[sheet_name or vu_name] = result.batch_id

            if batch_map and self._raw_data_map:
                self._upload_raw_data(batch_map)

            self.finished.emit(accumulated)
        except Exception as e:
            self.error.emit(str(e))

    def _upload_raw_data(self, batch_map: dict) -> None:
        logger.info(f"Rohdaten-Upload: batch_map={batch_map}, raw_sheets={list(self._raw_data_map.keys())}")
        for sheet_key, raw_info in self._raw_data_map.items():
            batch_id = batch_map.get(sheet_key)
            if not batch_id:
                logger.warning(f"  Sheet '{sheet_key}': Kein Batch-ID gefunden, uebersprungen")
                continue
            try:
                n_rows = len(raw_info.get('rows', []))
                n_headers = len(raw_info.get('headers', []))
                logger.info(f"  Upload Sheet '{sheet_key}' -> batch={batch_id}: {n_headers} headers, {n_rows} rows")
                ok = self._repo.upload_raw_data(
                    batch_id=batch_id,
                    headers=raw_info['headers'],
                    rows=raw_info['rows'],
                    sheet_name=sheet_key,
                    total_rows=raw_info.get('total_rows', len(raw_info['rows'])),
                    skipped_rows=raw_info.get('skipped_rows', 0),
                )
                if ok:
                    logger.info(f"  Sheet '{sheet_key}' (batch={batch_id}): Upload OK")
                else:
                    logger.error(f"  Sheet '{sheet_key}' (batch={batch_id}): Upload FEHLGESCHLAGEN (success=false)")
            except Exception as e:
                logger.error(f"  Sheet '{sheet_key}' (batch={batch_id}): Upload EXCEPTION: {e}")


# ═══════════════════════════════════════════════════════
# Provisionspositionen
# ═══════════════════════════════════════════════════════


class PositionsLoadWorker(QThread):
    """Laedt Provisionspositionen mit automatischem Chunking bei grossen Datenmengen."""
    finished = Signal(object, object)
    error = Signal(str)

    def __init__(self, repo: ProvisionRepository, **kwargs):
        super().__init__()
        self._repo = repo
        self._kwargs = kwargs

    def run(self):
        try:
            data, pagination = self._repo.get_commissions(**self._kwargs)
            total = pagination.total if pagination else len(data)

            while len(data) < total:
                chunk_kwargs = {**self._kwargs, 'offset': len(data)}
                next_data, _ = self._repo.get_commissions(**chunk_kwargs)
                if not next_data:
                    break
                data.extend(next_data)
                logger.debug(f"Chunk geladen: {len(data)}/{total}")

            final_pagination = PaginationInfo(total=total) if total > 0 else None
            self.finished.emit(data, final_pagination)
        except Exception as e:
            self.error.emit(str(e))


class AuditLoadWorker(QThread):
    finished = Signal(int, list)
    error = Signal(str)

    def __init__(self, repo: ProvisionRepository, comm_id: int):
        super().__init__()
        self._repo = repo
        self._comm_id = comm_id

    def run(self):
        try:
            entries = self._repo.get_audit_log(entity_type='commission', entity_id=self._comm_id, limit=10)
            self.finished.emit(self._comm_id, entries)
        except Exception as e:
            self.error.emit(str(e))


class IgnoreWorker(QThread):
    finished = Signal(bool)
    error = Signal(str)

    def __init__(self, repo: ProvisionRepository, comm_id: int):
        super().__init__()
        self._repo = repo
        self._comm_id = comm_id

    def run(self):
        try:
            ok = self._repo.ignore_commission(self._comm_id)
            self.finished.emit(ok)
        except Exception as e:
            self.error.emit(str(e))


class RawDataLoadWorker(QThread):
    finished = Signal(int, dict)
    error = Signal(str)

    def __init__(self, repo: ProvisionRepository, batch_id: int):
        super().__init__()
        self._repo = repo
        self._batch_id = batch_id

    def run(self):
        try:
            data = self._repo.get_raw_data(self._batch_id)
            self.finished.emit(self._batch_id, data)
        except Exception as e:
            self.error.emit(str(e))


# ═══════════════════════════════════════════════════════
# Zuordnung & Klärfälle
# ═══════════════════════════════════════════════════════


class ClearanceLoadWorker(QThread):
    finished = Signal(object, object)
    error = Signal(str)

    def __init__(self, repo: ProvisionRepository, von: str = None, bis: str = None):
        super().__init__()
        self._repo = repo
        self._von = von
        self._bis = bis

    def run(self):
        try:
            date_kwargs = {}
            if self._von:
                date_kwargs['von'] = self._von
            if self._bis:
                date_kwargs['bis'] = self._bis
            unmatched, _ = self._repo.get_commissions(
                match_status='unmatched', is_relevant=True, limit=50000, **date_kwargs)
            all_matched, _ = self._repo.get_commissions(
                is_relevant=True, limit=50000, **date_kwargs)
            berater_missing = [c for c in all_matched
                               if c.match_status in ('auto_matched', 'manual_matched') and not c.berater_id]
            commissions = unmatched + berater_missing
            mappings_data = self._repo.get_mappings(include_unmapped=True)
            self.finished.emit(commissions, mappings_data)
        except Exception as e:
            self.error.emit(str(e))


class MappingSyncWorker(QThread):
    finished = Signal(object)
    error = Signal(str)

    def __init__(self, repo: ProvisionRepository, primary_name: str, berater_id: int,
                 also_vu_name: str = None):
        super().__init__()
        self._repo = repo
        self._primary_name = primary_name
        self._berater_id = berater_id
        self._also_vu_name = also_vu_name

    def run(self):
        try:
            self._repo.create_mapping(self._primary_name, self._berater_id)
            if self._also_vu_name:
                try:
                    self._repo.create_mapping(self._also_vu_name, self._berater_id)
                except Exception:
                    pass
            stats = self._repo.trigger_auto_match()
            self.finished.emit(stats or {})
        except Exception as e:
            self.error.emit(str(e))


class MatchSearchWorker(QThread):
    finished = Signal(object, object)
    error = Signal(str)

    def __init__(self, repo: ProvisionRepository, commission_id: int, q: str = None):
        super().__init__()
        self._repo = repo
        self._commission_id = commission_id
        self._q = q

    def run(self):
        try:
            result = self._repo.get_match_suggestions(
                commission_id=self._commission_id,
                direction='forward',
                q=self._q,
                limit=50,
            )
            suggestions = result.get('suggestions', [])
            commission = result.get('commission', {})
            self.finished.emit(suggestions, commission)
        except Exception as e:
            self.error.emit(str(e))


# ═══════════════════════════════════════════════════════
# Verteilschlüssel & Rollen
# ═══════════════════════════════════════════════════════


class VerteilschluesselLoadWorker(QThread):
    finished = Signal(object, object, object)
    error = Signal(str)

    def __init__(self, repo: ProvisionRepository):
        super().__init__()
        self._repo = repo

    def run(self):
        try:
            models = self._repo.get_models()
            employees = self._repo.get_employees()
            settings = self._repo.get_pm_settings()
            self.finished.emit(models, employees, settings)
        except Exception as e:
            self.error.emit(str(e))


class SaveEmployeeWorker(QThread):
    finished = Signal(bool, object)
    error = Signal(str)

    def __init__(self, repo: ProvisionRepository, emp_id: int, data: Dict):
        super().__init__()
        self._repo = repo
        self._emp_id = emp_id
        self._data = data

    def run(self):
        try:
            success, summary = self._repo.update_employee(self._emp_id, self._data)
            self.finished.emit(success, summary)
        except Exception as e:
            self.error.emit(str(e))


class SaveModelWorker(QThread):
    finished = Signal(bool, object)
    error = Signal(str)

    def __init__(self, repo: ProvisionRepository, model_id: int, data: Dict):
        super().__init__()
        self._repo = repo
        self._model_id = model_id
        self._data = data

    def run(self):
        try:
            success, summary = self._repo.update_model(self._model_id, self._data)
            self.finished.emit(success, summary)
        except Exception as e:
            self.error.emit(str(e))


# ═══════════════════════════════════════════════════════
# Auszahlungen & Reports
# ═══════════════════════════════════════════════════════


class AuszahlungenLoadWorker(QThread):
    finished = Signal(object)
    error = Signal(str)

    def __init__(self, repo: ProvisionRepository, monat: str):
        super().__init__()
        self._repo = repo
        self._monat = monat

    def run(self):
        try:
            data = self._repo.get_abrechnungen(self._monat)
            self.finished.emit(data)
        except Exception as e:
            self.error.emit(str(e))


class AuszahlungenPositionenWorker(QThread):
    finished = Signal(int, list)
    error = Signal(str)

    def __init__(self, repo: ProvisionRepository, berater_id: int, von: str, bis: str):
        super().__init__()
        self._repo = repo
        self._berater_id = berater_id
        self._von = von
        self._bis = bis

    def run(self):
        try:
            comms, _ = self._repo.get_commissions(
                berater_id=self._berater_id, von=self._von, bis=self._bis, limit=200
            )
            self.finished.emit(self._berater_id, comms)
        except Exception as e:
            self.error.emit(str(e))


# ═══════════════════════════════════════════════════════
# Freie Provisionen / Sonderzahlungen
# ═══════════════════════════════════════════════════════

class FreeCommissionLoadWorker(QThread):
    finished = Signal(list)
    error = Signal(str)

    def __init__(self, repo: ProvisionRepository, von: str = None, bis: str = None):
        super().__init__()
        self._repo = repo
        self._von = von
        self._bis = bis

    def run(self):
        try:
            data = self._repo.get_free_commissions(von=self._von, bis=self._bis)
            self.finished.emit(data)
        except Exception as e:
            self.error.emit(str(e))


class FreeCommissionSaveWorker(QThread):
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, repo: ProvisionRepository, data: dict, fc_id: int = None):
        super().__init__()
        self._repo = repo
        self._data = data
        self._fc_id = fc_id

    def run(self):
        try:
            if self._fc_id:
                result = self._repo.update_free_commission(self._fc_id, self._data)
            else:
                result = self._repo.create_free_commission(self._data)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class FreeCommissionDeleteWorker(QThread):
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, repo: ProvisionRepository, fc_id: int):
        super().__init__()
        self._repo = repo
        self._fc_id = fc_id

    def run(self):
        try:
            result = self._repo.delete_free_commission(self._fc_id)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


# ═══════════════════════════════════════════════════════
# Provisions-Detail-Aktionen (Override, Note, Mapping)
# ═══════════════════════════════════════════════════════


class OverrideWorker(QThread):
    finished = Signal(object)
    error = Signal(str)

    def __init__(self, repo, comm_id: int, amount_settled: float,
                 reason: str = None):
        super().__init__()
        self._repo = repo
        self._comm_id = comm_id
        self._amount_settled = amount_settled
        self._reason = reason

    def run(self):
        try:
            result = self._repo.set_commission_override(
                self._comm_id, self._amount_settled, self._reason)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class OverrideResetWorker(QThread):
    finished = Signal(object)
    error = Signal(str)

    def __init__(self, repo, comm_id: int):
        super().__init__()
        self._repo = repo
        self._comm_id = comm_id

    def run(self):
        try:
            result = self._repo.reset_commission_override(self._comm_id)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class NoteWorker(QThread):
    finished = Signal(bool)
    error = Signal(str)

    def __init__(self, repo, comm_id: int, note: str):
        super().__init__()
        self._repo = repo
        self._comm_id = comm_id
        self._note = note

    def run(self):
        try:
            ok = self._repo.save_commission_note(self._comm_id, self._note)
            self.finished.emit(ok)
        except Exception as e:
            self.error.emit(str(e))


class MappingCreateWorker(QThread):
    finished = Signal()
    error = Signal(str)

    def __init__(self, repo, name: str, berater_id: int):
        super().__init__()
        self._repo = repo
        self._name = name
        self._berater_id = berater_id

    def run(self):
        try:
            self._repo.create_mapping(self._name, self._berater_id)
            self._repo.trigger_auto_match()
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))


# ═══════════════════════════════════════════════════════
# Abrechnungen generieren / Status
# ═══════════════════════════════════════════════════════


class AbrechnungGenerateWorker(QThread):
    finished = Signal(object, str)

    def __init__(self, repo, monat: str, parent=None):
        super().__init__(parent)
        self._repo = repo
        self._monat = monat

    def run(self):
        try:
            resp = self._repo.generate_abrechnung(self._monat)
            self.finished.emit(resp, "")
        except Exception as e:
            self.finished.emit(None, str(e))


class AbrechnungStatusWorker(QThread):
    finished = Signal(bool, str, str)
    error = Signal(str)

    def __init__(self, repo, abrechnung_id: int, status: str, parent=None):
        super().__init__(parent)
        self._repo = repo
        self._abrechnung_id = abrechnung_id
        self._status = status

    def run(self):
        try:
            ok = self._repo.update_abrechnung_status(self._abrechnung_id, self._status)
            self.finished.emit(ok, self._status, "")
        except Exception as e:
            self.finished.emit(False, self._status, str(e))


# ═══════════════════════════════════════════════════════
# Xempus Contracts (ProvisionAPI-kompatibel)
# ═══════════════════════════════════════════════════════


class XempusContractsLoadWorker(QThread):
    finished = Signal(object, object)
    error = Signal(str)

    def __init__(self, api, **kwargs):
        super().__init__()
        self._api = api
        self._kwargs = kwargs

    def run(self):
        try:
            contracts = self._api.get_contracts(**self._kwargs)
            employees = self._api.get_employees()
            self.finished.emit(contracts, employees)
        except Exception as e:
            self.error.emit(str(e))


class XempusDetailLoadWorker(QThread):
    finished = Signal(object)
    error = Signal(str)

    def __init__(self, api, vsnr: str):
        super().__init__()
        self._api = api
        self._vsnr = vsnr

    def run(self):
        try:
            comms, _ = self._api.get_commissions(q=self._vsnr, limit=200)
            self.finished.emit(comms)
        except Exception as e:
            self.error.emit(str(e))


# ═══════════════════════════════════════════════════════
# Xempus Insight (XempusAPI)
# ═══════════════════════════════════════════════════════


class EmployerLoadWorker(QThread):
    finished = Signal(list)
    error = Signal(str)

    def __init__(self, api):
        super().__init__()
        self._api = api

    def run(self):
        try:
            employers = self._api.get_employers()
            self.finished.emit(employers)
        except Exception as e:
            self.error.emit(str(e))


class EmployerDetailWorker(QThread):
    finished = Signal(object)
    error = Signal(str)

    def __init__(self, api, employer_id: str):
        super().__init__()
        self._api = api
        self._employer_id = employer_id

    def run(self):
        try:
            detail = self._api.get_employer_detail(self._employer_id)
            self.finished.emit(detail)
        except Exception as e:
            self.error.emit(str(e))


class XempusStatsLoadWorker(QThread):
    finished = Signal(object)
    error = Signal(str)

    def __init__(self, api):
        super().__init__()
        self._api = api

    def run(self):
        try:
            stats = self._api.get_stats()
            self.finished.emit(stats)
        except Exception as e:
            self.error.emit(str(e))


class EmployeePageLoadWorker(QThread):
    """Laedt eine einzelne Seite von Mitarbeitern (serverseitige Pagination)."""
    finished = Signal(list, dict)
    error = Signal(str)

    def __init__(self, api, page: int = 1, per_page: int = 48,
                 employer_id: str = None, q: str = None):
        super().__init__()
        self._api = api
        self._page = page
        self._per_page = per_page
        self._employer_id = employer_id
        self._q = q

    def run(self):
        try:
            employees, pagination = self._api.get_employees(
                employer_id=self._employer_id, q=self._q,
                page=self._page, per_page=self._per_page)
            if not isinstance(pagination, dict):
                pagination = {}
            self.finished.emit(employees or [], pagination)
        except Exception as e:
            self.error.emit(str(e))


class EmployeeDetailWorker(QThread):
    finished = Signal(object)
    error = Signal(str)

    def __init__(self, api, employee_id: str):
        super().__init__()
        self._api = api
        self._employee_id = employee_id

    def run(self):
        try:
            detail = self._api.get_employee_detail(self._employee_id)
            self.finished.emit(detail)
        except Exception as e:
            self.error.emit(str(e))


class XempusBatchesLoadWorker(QThread):
    finished = Signal(list)
    error = Signal(str)

    def __init__(self, api):
        super().__init__()
        self._api = api

    def run(self):
        try:
            batches = self._api.get_batches()
            self.finished.emit(batches)
        except Exception as e:
            self.error.emit(str(e))


class XempusImportWorker(QThread):
    phase_changed = Signal(int, str)
    finished = Signal(object)
    error = Signal(str)

    def __init__(self, api, filename: str, sheets: list):
        super().__init__()
        self._api = api
        self._filename = filename
        self._sheets = sheets

    def run(self):
        try:
            self.phase_changed.emit(1, texts.XEMPUS_IMPORT_PHASE_RAW)

            def on_progress(sent, total):
                pct = int(sent / total * 100) if total else 100
                self.phase_changed.emit(
                    1, f"{texts.XEMPUS_IMPORT_PHASE_RAW} ({pct}%)"
                )

            raw_result = self._api.import_raw(
                self._filename, self._sheets, on_progress=on_progress)
            batch_id = raw_result.get('batch_id')
            if not batch_id:
                self.error.emit(texts.XEMPUS_IMPORT_ERROR.format(error="No batch_id returned"))
                return

            self.phase_changed.emit(2, texts.XEMPUS_IMPORT_PHASE_PARSE)

            def on_parse_progress(parsed, total):
                pct = int(parsed / total * 100) if total else 100
                self.phase_changed.emit(
                    2, f"{texts.XEMPUS_IMPORT_PHASE_PARSE} ({pct}%)"
                )

            self._api.parse_batch(batch_id, timeout=300,
                                  on_progress=on_parse_progress)

            self.phase_changed.emit(3, texts.XEMPUS_IMPORT_PHASE_SNAPSHOT)
            finalize_result = self._api.finalize_batch(batch_id, timeout=300)

            self.phase_changed.emit(4, texts.XEMPUS_IMPORT_PHASE_FINALIZE)
            self.finished.emit(finalize_result)
        except Exception as e:
            self.error.emit(str(e))


class XempusDiffLoadWorker(QThread):
    finished = Signal(object)
    error = Signal(str)

    def __init__(self, api, batch_id: int):
        super().__init__()
        self._api = api
        self._batch_id = batch_id

    def run(self):
        try:
            diff = self._api.get_diff(self._batch_id)
            self.finished.emit(diff)
        except Exception as e:
            self.error.emit(str(e))


class StatusMappingLoadWorker(QThread):
    finished = Signal(list)
    error = Signal(str)

    def __init__(self, api):
        super().__init__()
        self._api = api

    def run(self):
        try:
            mappings = self._api.get_status_mappings()
            self.finished.emit(mappings)
        except Exception as e:
            self.error.emit(str(e))


# ═══════════════════════════════════════════════════════
# Statement Export & E-Mail (Presenter-basiert)
# ═══════════════════════════════════════════════════════


class StatementExportWorker(QThread):
    finished = Signal(str)
    error = Signal(str)

    def __init__(self, presenter, berater, fmt: str, path: str):
        super().__init__()
        self._presenter = presenter
        self._berater = berater
        self._fmt = fmt
        self._path = path

    def run(self):
        try:
            self._presenter.export_single_statement(
                self._berater, self._fmt, self._path)
            self.finished.emit(self._path)
        except Exception as e:
            self.error.emit(str(e))


class StatementBatchExportWorker(QThread):
    finished = Signal(int)
    progress = Signal(int, int)
    error = Signal(str)

    def __init__(self, presenter, abrechnungen: list, fmt: str, folder: str):
        super().__init__()
        self._presenter = presenter
        self._abrechnungen = abrechnungen
        self._fmt = fmt
        self._folder = folder

    def run(self):
        try:
            from services.statement_export import export_batch
            items = self._presenter.build_all_statements(self._abrechnungen)
            count = export_batch(
                items, self._fmt, self._folder,
                progress_callback=lambda c, t: self.progress.emit(c, t),
            )
            self.finished.emit(count)
        except Exception as e:
            self.error.emit(str(e))


class StatementEmailWorker(QThread):
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, presenter, berater):
        super().__init__()
        self._presenter = presenter
        self._berater = berater

    def run(self):
        try:
            result = self._presenter.send_statement_email(self._berater)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class StatementBatchEmailWorker(QThread):
    finished = Signal(int, int)
    progress = Signal(int, int)
    error = Signal(str)

    def __init__(self, presenter, abrechnungen: list):
        super().__init__()
        self._presenter = presenter
        self._abrechnungen = abrechnungen

    def run(self):
        try:
            eligible = [b for b in self._abrechnungen if b.has_email]
            sent = 0
            failed = 0
            for i, berater in enumerate(eligible):
                try:
                    result = self._presenter.send_statement_email(berater)
                    if result.get('success'):
                        sent += 1
                    else:
                        failed += 1
                except Exception:
                    failed += 1
                self.progress.emit(i + 1, len(eligible))
            self.finished.emit(sent, failed)
        except Exception as e:
            self.error.emit(str(e))
