"""
Workforce QThread-Worker fuer nicht-blockierende IO-Operationen.

Alle Provider-Calls, API-Calls und Export-Generierung laufen in Worker-Threads.
"""

import json
import os
import logging
import tempfile
from datetime import datetime

from PySide6.QtCore import QRunnable, QObject, Signal

logger = logging.getLogger(__name__)


class WorkforceSignals(QObject):
    """Signals fuer alle Workforce-Worker."""
    finished = Signal(dict)
    error = Signal(str)
    progress = Signal(str)


class SyncWorker(QRunnable):
    """Worker fuer die Mitarbeiter-Synchronisierung."""

    def __init__(self, api_client, employer_id: int, only_active: bool = False):
        super().__init__()
        self.signals = WorkforceSignals()
        self.api = api_client
        self.employer_id = employer_id
        self.only_active = only_active

    def run(self):
        try:
            from workforce.services.sync_service import SyncService
            service = SyncService(self.api)
            self.signals.progress.emit("Synchronisierung laeuft...")
            result = service.sync_employer(self.employer_id, self.only_active)
            self.signals.finished.emit(result)
        except Exception as e:
            logger.error(f"SyncWorker Fehler: {e}", exc_info=True)
            self.signals.error.emit(str(e))


class DeltaExportWorker(QRunnable):
    """Worker fuer den Delta-SCS-Export (kompletter Ablauf)."""

    def __init__(self, api_client, employer_id: int, username: str = 'system'):
        super().__init__()
        self.signals = WorkforceSignals()
        self.api = api_client
        self.employer_id = employer_id
        self.username = username

    def run(self):
        try:
            from workforce.providers import ProviderFactory
            from workforce.services.delta_service import generate_delta_export
            from workforce.services.trigger_service import TriggerEngine

            self.signals.progress.emit("Credentials laden...")
            employer = self.api.get_employer(self.employer_id)
            credentials = self.api.get_credentials(self.employer_id)

            self.signals.progress.emit("Mitarbeiterdaten abrufen...")
            provider = ProviderFactory.create(employer['provider_key'], credentials)
            employees, raw_responses = provider.list_employees(only_active=False)

            self.signals.progress.emit("Letzten Snapshot laden...")
            prev_snapshot = self.api.get_latest_snapshot(self.employer_id)
            prev_data = prev_snapshot.get('data', {}) if prev_snapshot else {}

            exports_dir = os.path.join(tempfile.gettempdir(), 'atlas_workforce_exports')
            self.signals.progress.emit("Delta berechnen und Export generieren...")
            result = generate_delta_export(
                employees, employer, prev_data, exports_dir
            )

            snapshot_ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            self.signals.progress.emit("Snapshot speichern...")
            snapshot_result = self.api.save_snapshot(
                self.employer_id, snapshot_ts, result['current_snapshot']
            )

            if result['filepath']:
                self.signals.progress.emit("Export hochladen...")
                export_meta = {
                    'export_type': 'delta_scs',
                    'filename': os.path.basename(result['filepath']),
                    'diff_summary': json.dumps(result.get('diff', {}), ensure_ascii=False, default=str),
                }
                self.api.upload_export(self.employer_id, result['filepath'], export_meta)

            self.signals.progress.emit("Trigger auswerten...")
            triggers = self.api.get_triggers()
            active_triggers = [
                t for t in triggers
                if t.get('enabled') and self.employer_id not in (t.get('excluded_employers') or [])
            ]

            trigger_results = []
            if active_triggers and (result['added_pids'] or result['changed_pids']):
                smtp_config = None
                if any(t.get('action_type') == 'email' for t in active_triggers):
                    try:
                        smtp_config = self.api.get_smtp_config_decrypted()
                    except Exception:
                        logger.warning("SMTP-Config konnte nicht geladen werden")

                engine = TriggerEngine()
                trigger_results = engine.evaluate_and_execute(
                    employer, result['diff'], result['current_snapshot'],
                    active_triggers, smtp_config, self.username
                )

                for tr in trigger_results:
                    try:
                        self.api.log_trigger_run({
                            'trigger_id': tr['trigger_id'],
                            'employer_id': self.employer_id,
                            'employee_pid': tr.get('employee_pid'),
                            'employee_name': tr.get('employee_name'),
                            'event': tr['event'],
                            'status': tr['status'],
                            'action_type': tr['action_type'],
                            'request_json': tr.get('action_details'),
                            'response_json': {'error': tr.get('error_message')} if tr.get('error_message') else None,
                            'can_retry': 1 if tr['status'] == 'error' else 0,
                            'executed_by': self.username,
                        })
                    except Exception as e:
                        logger.error(f"Trigger-Run-Log fehlgeschlagen: {e}")

            self.signals.finished.emit({
                'diff': result['diff'],
                'filepath': result['filepath'],
                'added_count': len(result['added_pids']),
                'changed_count': len(result['changed_pids']),
                'trigger_results': trigger_results,
                'snapshot_id': snapshot_result.get('snapshot_id'),
            })

        except Exception as e:
            logger.error(f"DeltaExportWorker Fehler: {e}", exc_info=True)
            self.signals.error.emit(str(e))


class StandardExportWorker(QRunnable):
    """Worker fuer den Standard-Export (alle Mitarbeiter)."""

    def __init__(self, api_client, employer_id: int):
        super().__init__()
        self.signals = WorkforceSignals()
        self.api = api_client
        self.employer_id = employer_id

    def run(self):
        try:
            from workforce.providers import ProviderFactory
            from workforce.services.export_service import generate_standard_export

            self.signals.progress.emit("Credentials laden...")
            employer = self.api.get_employer(self.employer_id)
            credentials = self.api.get_credentials(self.employer_id)

            self.signals.progress.emit("Mitarbeiterdaten abrufen...")
            provider = ProviderFactory.create(employer['provider_key'], credentials)
            employees, _ = provider.list_employees(only_active=False)

            exports_dir = os.path.join(tempfile.gettempdir(), 'atlas_workforce_exports')
            self.signals.progress.emit("Export generieren...")
            filepath = generate_standard_export(
                employees, employer['name'], employer['provider_key'], exports_dir,
                employer_cfg=employer
            )

            self.signals.progress.emit("Export hochladen...")
            self.api.upload_export(self.employer_id, filepath, {
                'export_type': 'standard',
                'filename': os.path.basename(filepath),
            })

            self.signals.finished.emit({
                'filepath': filepath,
                'employee_count': len(employees),
            })

        except Exception as e:
            logger.error(f"StandardExportWorker Fehler: {e}", exc_info=True)
            self.signals.error.emit(str(e))


class StatsWorker(QRunnable):
    """Worker fuer Statistik-Berechnung."""

    def __init__(self, api_client, employer_id: int, stats_type: str = 'standard'):
        super().__init__()
        self.signals = WorkforceSignals()
        self.api = api_client
        self.employer_id = employer_id
        self.stats_type = stats_type

    def run(self):
        try:
            from workforce.providers import ProviderFactory
            from workforce.services.stats_service import calculate_statistics, calculate_long_term_statistics
            from workforce.services.snapshot_service import build_employee_history

            if self.stats_type == 'standard':
                self.signals.progress.emit("Mitarbeiterdaten abrufen...")
                employer = self.api.get_employer(self.employer_id)
                credentials = self.api.get_credentials(self.employer_id)
                provider = ProviderFactory.create(employer['provider_key'], credentials)
                current, _ = provider.list_employees(only_active=False)

                self.signals.progress.emit("Statistiken berechnen...")
                stats = calculate_statistics(current)
                self.signals.finished.emit({'stats_type': 'standard', 'stats': stats})

            else:
                self.signals.progress.emit("Snapshots laden...")
                snapshots_list = self.api.get_snapshots(self.employer_id)

                full_snapshots = []
                for snap_meta in snapshots_list:
                    snap_full = self.api.get_snapshot(snap_meta['id'])
                    full_snapshots.append(snap_full)

                full_snapshots.sort(key=lambda s: s.get('snapshot_ts', ''))

                self.signals.progress.emit("Langzeit-Statistiken berechnen...")
                history = build_employee_history(full_snapshots)
                stats = calculate_long_term_statistics(history)
                self.signals.finished.emit({'stats_type': 'longterm', 'stats': stats})

        except Exception as e:
            logger.error(f"StatsWorker Fehler: {e}", exc_info=True)
            self.signals.error.emit(str(e))
