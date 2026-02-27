# -*- coding: utf-8 -*-
"""
QThread-Worker fuer das Provisionsmanagement.

KOMPATIBILITAETS-MODUL: Neue Worker sind in
infrastructure/threading/provision_workers.py.
Bestehende Imports funktionieren weiterhin.
"""

from PySide6.QtCore import QThread, Signal
from typing import List, Dict, Optional

from api.provision import ProvisionAPI
from domain.provision.entities import ImportResult
from i18n import de as texts
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# Dashboard
# =============================================================================


class DashboardLoadWorker(QThread):
    finished = Signal(object, object)
    error = Signal(str)

    def __init__(self, api: ProvisionAPI, von: str = None, bis: str = None):
        super().__init__()
        self._api = api
        self._von = von
        self._bis = bis

    def run(self):
        try:
            logger.debug(f"Dashboard-Load: von={self._von}, bis={self._bis}")
            summary = self._api.get_dashboard_summary(
                von=self._von, bis=self._bis)
            clearance = self._api.get_clearance_counts(von=self._von, bis=self._bis)
            self.finished.emit(summary, clearance)
        except Exception as e:
            self.error.emit(str(e))


class BeraterDetailWorker(QThread):
    finished = Signal(int, str, dict, object)
    error = Signal(str)

    def __init__(self, api: ProvisionAPI, berater_id: int, berater_name: str,
                 row_data: dict, von: str = None, bis: str = None):
        super().__init__()
        self._api = api
        self._berater_id = berater_id
        self._berater_name = berater_name
        self._row_data = row_data
        self._von = von
        self._bis = bis

    def run(self):
        try:
            detail = self._api.get_berater_detail(self._berater_id, von=self._von, bis=self._bis)
            self.finished.emit(self._berater_id, self._berater_name, self._row_data, detail)
        except Exception as e:
            self.error.emit(str(e))


# =============================================================================
# Abrechnungslaeufe (VU-Import)
# =============================================================================


class VuBatchesLoadWorker(QThread):
    finished = Signal(object)
    error = Signal(str)

    def __init__(self, api: ProvisionAPI):
        super().__init__()
        self._api = api

    def run(self):
        try:
            batches = self._api.get_import_batches()
            self.finished.emit(batches)
        except Exception as e:
            self.error.emit(str(e))


class VuParseFileWorker(QThread):
    """Parst VU-Provisionslisten im Hintergrund (blockiert nicht die UI)."""
    finished = Signal(object, str, str, str)  # rows, vu_name, sheet_name, log_text
    error = Signal(str)

    def __init__(self, path: str):
        super().__init__()
        self._path = path

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

    def __init__(self, api: ProvisionAPI, rows: List[Dict], filename: str,
                 sheet_name: str, vu_name: str, file_hash: str):
        super().__init__()
        self._api = api
        self._rows = rows
        self._filename = filename
        self._sheet_name = sheet_name
        self._vu_name = vu_name
        self._file_hash = file_hash

    def run(self):
        try:
            from domain.provision.entities import ImportResult
            from collections import defaultdict

            vu_groups = defaultdict(list)
            for row in self._rows:
                vu = row.pop('_vu_name', self._vu_name)
                sheet = row.pop('_sheet_name', self._sheet_name)
                vu_groups[(vu, sheet)].append(row)

            accumulated = ImportResult()
            chunk_size = 2000

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
                    result = self._api.import_vu_liste(
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
            self.finished.emit(accumulated)
        except Exception as e:
            self.error.emit(str(e))


# =============================================================================
# Provisionspositionen
# =============================================================================


class PositionsLoadWorker(QThread):
    finished = Signal(object)
    error = Signal(str)

    def __init__(self, api: ProvisionAPI, **kwargs):
        super().__init__()
        self._api = api
        self._kwargs = kwargs

    def run(self):
        try:
            data, _ = self._api.get_commissions(**self._kwargs)
            self.finished.emit(data)
        except Exception as e:
            self.error.emit(str(e))


class AuditLoadWorker(QThread):
    finished = Signal(int, list)
    error = Signal(str)

    def __init__(self, api: ProvisionAPI, comm_id: int):
        super().__init__()
        self._api = api
        self._comm_id = comm_id

    def run(self):
        try:
            entries = self._api.get_audit_log(entity_type='commission', entity_id=self._comm_id, limit=10)
            self.finished.emit(self._comm_id, entries)
        except Exception as e:
            self.error.emit(str(e))


class IgnoreWorker(QThread):
    finished = Signal(bool)
    error = Signal(str)

    def __init__(self, api: ProvisionAPI, comm_id: int):
        super().__init__()
        self._api = api
        self._comm_id = comm_id

    def run(self):
        try:
            ok = self._api.ignore_commission(self._comm_id)
            self.finished.emit(ok)
        except Exception as e:
            self.error.emit(str(e))


class MappingCreateWorker(QThread):
    finished = Signal()
    error = Signal(str)

    def __init__(self, api: ProvisionAPI, name: str, berater_id: int):
        super().__init__()
        self._api = api
        self._name = name
        self._berater_id = berater_id

    def run(self):
        try:
            self._api.create_mapping(self._name, self._berater_id)
            self._api.trigger_auto_match()
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))


# =============================================================================
# Zuordnung & Klaerfaelle
# =============================================================================


class ClearanceLoadWorker(QThread):
    finished = Signal(object, object)
    error = Signal(str)

    def __init__(self, api: ProvisionAPI):
        super().__init__()
        self._api = api

    def run(self):
        try:
            unmatched, _ = self._api.get_commissions(match_status='unmatched', limit=1000)
            all_matched, _ = self._api.get_commissions(limit=5000)
            berater_missing = [c for c in all_matched
                               if c.match_status in ('auto_matched', 'manual_matched') and not c.berater_id]
            commissions = unmatched + berater_missing
            mappings_data = self._api.get_mappings(include_unmapped=True)
            self.finished.emit(commissions, mappings_data)
        except Exception as e:
            self.error.emit(str(e))


class MappingSyncWorker(QThread):
    """Erstellt Mapping(s) und fuehrt Auto-Match im Hintergrund aus."""
    finished = Signal(object)
    error = Signal(str)

    def __init__(self, api: ProvisionAPI, primary_name: str, berater_id: int,
                 also_vu_name: str = None):
        super().__init__()
        self._api = api
        self._primary_name = primary_name
        self._berater_id = berater_id
        self._also_vu_name = also_vu_name

    def run(self):
        try:
            self._api.create_mapping(self._primary_name, self._berater_id)
            if self._also_vu_name:
                try:
                    self._api.create_mapping(self._also_vu_name, self._berater_id)
                except Exception:
                    pass
            stats = self._api.trigger_auto_match()
            self.finished.emit(stats or {})
        except Exception as e:
            self.error.emit(str(e))


class MatchSearchWorker(QThread):
    finished = Signal(object, object)
    error = Signal(str)

    def __init__(self, api: ProvisionAPI, commission_id: int, q: str = None):
        super().__init__()
        self._api = api
        self._commission_id = commission_id
        self._q = q

    def run(self):
        try:
            result = self._api.get_match_suggestions(
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


# =============================================================================
# Verteilschluessel & Rollen
# =============================================================================


class VerteilschluesselLoadWorker(QThread):
    finished = Signal(object, object)
    error = Signal(str)

    def __init__(self, api: ProvisionAPI):
        super().__init__()
        self._api = api

    def run(self):
        try:
            models = self._api.get_models()
            employees = self._api.get_employees()
            self.finished.emit(models, employees)
        except Exception as e:
            self.error.emit(str(e))


# =============================================================================
# Auszahlungen & Reports
# =============================================================================


class AuszahlungenLoadWorker(QThread):
    finished = Signal(object)
    error = Signal(str)

    def __init__(self, api: ProvisionAPI, monat: str):
        super().__init__()
        self._api = api
        self._monat = monat

    def run(self):
        try:
            data = self._api.get_abrechnungen(self._monat)
            self.finished.emit(data)
        except Exception as e:
            self.error.emit(str(e))


class AuszahlungenPositionenWorker(QThread):
    finished = Signal(int, list)
    error = Signal(str)

    def __init__(self, api: ProvisionAPI, berater_id: int, von: str, bis: str):
        super().__init__()
        self._api = api
        self._berater_id = berater_id
        self._von = von
        self._bis = bis

    def run(self):
        try:
            comms, _ = self._api.get_commissions(
                berater_id=self._berater_id, von=self._von, bis=self._bis, limit=200
            )
            self.finished.emit(self._berater_id, comms)
        except Exception as e:
            self.error.emit(str(e))


# =============================================================================
# Xempus-Beratungen (xempus_panel)
# =============================================================================


class XempusContractsLoadWorker(QThread):
    finished = Signal(object, object)
    error = Signal(str)

    def __init__(self, api: ProvisionAPI, **kwargs):
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
    """Laedt VU-Provisionen fuer einen einzelnen Vertrag."""
    finished = Signal(object)
    error = Signal(str)

    def __init__(self, api: ProvisionAPI, vsnr: str):
        super().__init__()
        self._api = api
        self._vsnr = vsnr

    def run(self):
        try:
            comms, _ = self._api.get_commissions(q=self._vsnr, limit=200)
            self.finished.emit(comms)
        except Exception as e:
            self.error.emit(str(e))


# =============================================================================
# Xempus Insight (xempus_insight_panel)
# =============================================================================


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
    """4-Phasen-Import-Worker: raw_ingest (chunked) -> parse -> finalize."""
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
            total_rows = sum(len(s.get('rows', [])) for s in self._sheets)
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


# =============================================================================
# Verteilschluessel - Save Workers
# =============================================================================


class SaveEmployeeWorker(QThread):
    """Async-Worker fuer Mitarbeiter-Update (kann Neuberechnung ausloesen)."""
    finished = Signal(bool, object)
    error = Signal(str)

    def __init__(self, api: ProvisionAPI, emp_id: int, data: Dict):
        super().__init__()
        self._api = api
        self._emp_id = emp_id
        self._data = data

    def run(self):
        try:
            success, summary = self._api.update_employee(self._emp_id, self._data)
            self.finished.emit(success, summary)
        except Exception as e:
            self.error.emit(str(e))


class SaveModelWorker(QThread):
    """Async-Worker fuer Modell-Update (kann Neuberechnung ausloesen)."""
    finished = Signal(bool, object)
    error = Signal(str)

    def __init__(self, api: ProvisionAPI, model_id: int, data: Dict):
        super().__init__()
        self._api = api
        self._model_id = model_id
        self._data = data

    def run(self):
        try:
            success, summary = self._api.update_model(self._model_id, self._data)
            self.finished.emit(success, summary)
        except Exception as e:
            self.error.emit(str(e))
