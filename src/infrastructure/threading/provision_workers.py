"""
QThread-Worker für das Provisionsmanagement.

Infrastructure Layer: Asynchrone Operationen mit Repository-Zugriff.
Worker kennen nur Repository-Interfaces, nicht die API direkt.
"""

from PySide6.QtCore import QThread, Signal
from typing import List, Dict, Optional

from infrastructure.api.provision_repository import ProvisionRepository
from domain.provision.entities import ImportResult
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

    def __init__(self, repo: ProvisionRepository, rows: List[Dict], filename: str,
                 sheet_name: str, vu_name: str, file_hash: str):
        super().__init__()
        self._repo = repo
        self._rows = rows
        self._filename = filename
        self._sheet_name = sheet_name
        self._vu_name = vu_name
        self._file_hash = file_hash

    def run(self):
        try:
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
            self.finished.emit(accumulated)
        except Exception as e:
            self.error.emit(str(e))


# ═══════════════════════════════════════════════════════
# Provisionspositionen
# ═══════════════════════════════════════════════════════


class PositionsLoadWorker(QThread):
    finished = Signal(object, object)
    error = Signal(str)

    def __init__(self, repo: ProvisionRepository, **kwargs):
        super().__init__()
        self._repo = repo
        self._kwargs = kwargs

    def run(self):
        try:
            data, pagination = self._repo.get_commissions(**self._kwargs)
            self.finished.emit(data, pagination)
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


# ═══════════════════════════════════════════════════════
# Zuordnung & Klärfälle
# ═══════════════════════════════════════════════════════


class ClearanceLoadWorker(QThread):
    finished = Signal(object, object)
    error = Signal(str)

    def __init__(self, repo: ProvisionRepository):
        super().__init__()
        self._repo = repo

    def run(self):
        try:
            unmatched, _ = self._repo.get_commissions(match_status='unmatched', is_relevant=True, limit=1000)
            all_matched, _ = self._repo.get_commissions(is_relevant=True, limit=5000)
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
    finished = Signal(object, object)
    error = Signal(str)

    def __init__(self, repo: ProvisionRepository):
        super().__init__()
        self._repo = repo

    def run(self):
        try:
            models = self._repo.get_models()
            employees = self._repo.get_employees()
            self.finished.emit(models, employees)
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
