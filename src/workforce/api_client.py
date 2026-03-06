"""
Workforce API Client - Kommunikation mit dem PHP-Backend.

Alle HR-Endpoints unter /hr/* werden ueber diesen Client aufgerufen.
Folgt dem ATLAS-Pattern (wie AdminAPI, ProvisionAPI).
"""

import logging
from typing import Optional

from api.client import APIClient, APIError

logger = logging.getLogger(__name__)


class WorkforceApiClient:
    """API-Client fuer das Workforce-Modul (PHP-Backend /hr/*)."""

    def __init__(self, client: APIClient):
        self.client = client

    # ── Employers ──────────────────────────────────────────────

    def get_employers(self) -> list[dict]:
        """Alle Arbeitgeber auflisten."""
        try:
            response = self.client.get('/hr/employers')
            if response.get('success'):
                return response.get('data', {}).get('employers', [])
        except APIError as e:
            logger.error(f"Fehler beim Laden der Arbeitgeber: {e}")
            raise
        return []

    def get_employer(self, employer_id: int) -> dict:
        """Einzelnen Arbeitgeber laden."""
        try:
            response = self.client.get(f'/hr/employers/{employer_id}')
            if response.get('success'):
                data = response.get('data', {})
                return data if 'name' in data else data
        except APIError as e:
            logger.error(f"Fehler beim Laden des Arbeitgebers {employer_id}: {e}")
            raise
        return {}

    def create_employer(self, data: dict) -> dict:
        """Neuen Arbeitgeber anlegen."""
        try:
            response = self.client.post('/hr/employers', json_data=data)
            if response.get('success'):
                return response.get('data', {})
        except APIError as e:
            logger.error(f"Fehler beim Erstellen des Arbeitgebers: {e}")
            raise
        return {}

    def update_employer(self, employer_id: int, data: dict) -> dict:
        """Arbeitgeber aktualisieren."""
        try:
            response = self.client.put(f'/hr/employers/{employer_id}', json_data=data)
            if response.get('success'):
                return response.get('data', {})
        except APIError as e:
            logger.error(f"Fehler beim Aktualisieren des Arbeitgebers {employer_id}: {e}")
            raise
        return {}

    def delete_employer(self, employer_id: int) -> bool:
        """Arbeitgeber loeschen (Soft-Delete)."""
        try:
            response = self.client.delete(f'/hr/employers/{employer_id}')
            return response.get('success', False)
        except APIError as e:
            logger.error(f"Fehler beim Loeschen des Arbeitgebers {employer_id}: {e}")
            raise

    # ── Credentials ────────────────────────────────────────────

    def save_credentials(self, employer_id: int, credentials: dict) -> dict:
        """Provider-Credentials speichern (PHP verschluesselt)."""
        try:
            response = self.client.post(
                f'/hr/employers/{employer_id}/credentials',
                json_data=credentials
            )
            if response.get('success'):
                return response.get('data', {})
        except APIError as e:
            logger.error(f"Fehler beim Speichern der Credentials: {e}")
            raise
        return {}

    def get_credentials(self, employer_id: int) -> dict:
        """Provider-Credentials laden (PHP entschluesselt)."""
        try:
            response = self.client.get(f'/hr/employers/{employer_id}/credentials')
            if response.get('success'):
                return response.get('data', {}).get('credentials', {})
        except APIError as e:
            logger.error(f"Fehler beim Laden der Credentials: {e}")
            raise
        return {}

    def get_credentials_status(self, employer_id: int) -> dict:
        """Credentials-Status pruefen (ohne Klartext)."""
        try:
            response = self.client.get(f'/hr/employers/{employer_id}/credentials/status')
            if response.get('success'):
                return response.get('data', {})
        except APIError as e:
            logger.error(f"Fehler beim Laden des Credentials-Status: {e}")
            raise
        return {}

    # ── Employees ──────────────────────────────────────────────

    def bulk_sync_employees(self, employer_id: int, employees: list) -> dict:
        """Mitarbeiter per Bulk-Upsert synchronisieren."""
        try:
            response = self.client.post('/hr/employees/bulk', json_data={
                'employer_id': employer_id,
                'employees': employees,
            })
            if response.get('success'):
                return response.get('data', {})
        except APIError as e:
            logger.error(f"Fehler beim Bulk-Sync: {e}")
            raise
        return {}

    def get_employees(self, employer_id: int, page: int = 1,
                      per_page: int = 50, status: str = None,
                      search: str = None) -> dict:
        """Mitarbeiter paginiert laden."""
        try:
            params = {'page': page, 'per_page': per_page}
            if status:
                params['status'] = status
            if search:
                params['search'] = search
            response = self.client.get(
                f'/hr/employers/{employer_id}/employees',
                params=params
            )
            if response.get('success'):
                return response.get('data', {})
        except APIError as e:
            logger.error(f"Fehler beim Laden der Mitarbeiter: {e}")
            raise
        return {}

    def get_employee(self, employer_id: int, employee_id: int) -> dict:
        """Einzelnen Mitarbeiter laden."""
        try:
            response = self.client.get(
                f'/hr/employers/{employer_id}/employees/{employee_id}'
            )
            if response.get('success'):
                return response.get('data', {})
        except APIError as e:
            logger.error(f"Fehler beim Laden des Mitarbeiters: {e}")
            raise
        return {}

    # ── Snapshots ──────────────────────────────────────────────

    def save_snapshot(self, employer_id: int, snapshot_ts: str,
                      employees: dict) -> dict:
        """Neuen Snapshot speichern."""
        try:
            response = self.client.post('/hr/snapshots', json_data={
                'employer_id': employer_id,
                'snapshot_ts': snapshot_ts,
                'employees': employees,
            })
            if response.get('success'):
                return response.get('data', {})
        except APIError as e:
            logger.error(f"Fehler beim Speichern des Snapshots: {e}")
            raise
        return {}

    def get_snapshots(self, employer_id: int) -> list[dict]:
        """Snapshot-Liste laden."""
        try:
            response = self.client.get(f'/hr/employers/{employer_id}/snapshots')
            if response.get('success'):
                return response.get('data', {}).get('snapshots', [])
        except APIError as e:
            logger.error(f"Fehler beim Laden der Snapshots: {e}")
            raise
        return []

    def get_snapshot(self, snapshot_id: int) -> dict:
        """Einzelnen Snapshot mit Daten laden."""
        try:
            response = self.client.get(f'/hr/snapshots/{snapshot_id}')
            if response.get('success'):
                return response.get('data', {})
        except APIError as e:
            logger.error(f"Fehler beim Laden des Snapshots {snapshot_id}: {e}")
            raise
        return {}

    def get_latest_snapshot(self, employer_id: int) -> Optional[dict]:
        """Aktuellsten Snapshot laden."""
        try:
            response = self.client.get(f'/hr/employers/{employer_id}/snapshots/latest')
            if response.get('success'):
                return response.get('data', {}).get('snapshot')
        except APIError as e:
            logger.error(f"Fehler beim Laden des letzten Snapshots: {e}")
            raise
        return None

    def delete_snapshot(self, snapshot_id: int) -> bool:
        """Snapshot loeschen."""
        try:
            response = self.client.delete(f'/hr/snapshots/{snapshot_id}')
            return response.get('success', False)
        except APIError as e:
            logger.error(f"Fehler beim Loeschen des Snapshots: {e}")
            raise

    # ── Exports ────────────────────────────────────────────────

    def upload_export(self, employer_id: int, file_path: str,
                      metadata: dict = None) -> dict:
        """Export-Datei hochladen (Multipart)."""
        try:
            additional_data = {'employer_id': str(employer_id)}
            if metadata:
                for k, v in metadata.items():
                    additional_data[k] = str(v) if v is not None else ''
            response = self.client.upload_file(
                '/hr/exports',
                file_path,
                additional_data=additional_data
            )
            if response.get('success'):
                return response.get('data', {})
        except APIError as e:
            logger.error(f"Fehler beim Upload des Exports: {e}")
            raise
        return {}

    def get_exports(self, employer_id: int) -> list[dict]:
        """Export-Liste laden."""
        try:
            response = self.client.get(f'/hr/employers/{employer_id}/exports')
            if response.get('success'):
                return response.get('data', {}).get('exports', [])
        except APIError as e:
            logger.error(f"Fehler beim Laden der Exporte: {e}")
            raise
        return []

    def download_export(self, export_id: int, save_path: str) -> str:
        """Export-Datei herunterladen."""
        try:
            self.client.download_file(f'/hr/exports/{export_id}/download', save_path)
            return save_path
        except APIError as e:
            logger.error(f"Fehler beim Download des Exports: {e}")
            raise

    # ── Triggers ───────────────────────────────────────────────

    def get_triggers(self) -> list[dict]:
        """Alle Trigger laden."""
        try:
            response = self.client.get('/hr/triggers')
            if response.get('success'):
                return response.get('data', {}).get('triggers', [])
        except APIError as e:
            logger.error(f"Fehler beim Laden der Trigger: {e}")
            raise
        return []

    def create_trigger(self, data: dict) -> dict:
        """Neuen Trigger erstellen."""
        try:
            response = self.client.post('/hr/triggers', json_data=data)
            if response.get('success'):
                return response.get('data', {})
        except APIError as e:
            logger.error(f"Fehler beim Erstellen des Triggers: {e}")
            raise
        return {}

    def update_trigger(self, trigger_id: int, data: dict) -> dict:
        """Trigger aktualisieren."""
        try:
            response = self.client.put(f'/hr/triggers/{trigger_id}', json_data=data)
            if response.get('success'):
                return response.get('data', {})
        except APIError as e:
            logger.error(f"Fehler beim Aktualisieren des Triggers: {e}")
            raise
        return {}

    def delete_trigger(self, trigger_id: int) -> bool:
        """Trigger loeschen."""
        try:
            response = self.client.delete(f'/hr/triggers/{trigger_id}')
            return response.get('success', False)
        except APIError as e:
            logger.error(f"Fehler beim Loeschen des Triggers: {e}")
            raise

    def toggle_trigger(self, trigger_id: int) -> dict:
        """Trigger aktivieren/deaktivieren."""
        try:
            response = self.client.post(f'/hr/triggers/{trigger_id}/toggle', json_data={})
            if response.get('success'):
                return response.get('data', {})
        except APIError as e:
            logger.error(f"Fehler beim Umschalten des Triggers: {e}")
            raise
        return {}

    def exclude_employer(self, trigger_id: int, employer_id: int,
                         exclude: bool) -> dict:
        """Arbeitgeber von Trigger ausschliessen/einschliessen."""
        try:
            response = self.client.post(
                f'/hr/triggers/{trigger_id}/exclude-employer',
                json_data={'employer_id': employer_id, 'exclude': exclude}
            )
            if response.get('success'):
                return response.get('data', {})
        except APIError as e:
            logger.error(f"Fehler beim Aendern des Trigger-Ausschlusses: {e}")
            raise
        return {}

    # ── Trigger-Runs ───────────────────────────────────────────

    def log_trigger_run(self, data: dict) -> dict:
        """Trigger-Ausfuehrung loggen."""
        try:
            response = self.client.post('/hr/trigger-runs', json_data=data)
            if response.get('success'):
                return response.get('data', {})
        except APIError as e:
            logger.error(f"Fehler beim Loggen der Trigger-Ausfuehrung: {e}")
            raise
        return {}

    def get_trigger_runs(self, page: int = 1, per_page: int = 25,
                         trigger_id: int = None, employer_id: int = None,
                         status: str = None) -> dict:
        """Trigger-Ausfuehrungslog laden."""
        try:
            params = {'page': page, 'per_page': per_page}
            if trigger_id:
                params['trigger_id'] = trigger_id
            if employer_id:
                params['employer_id'] = employer_id
            if status:
                params['status'] = status
            response = self.client.get('/hr/trigger-runs', params=params)
            if response.get('success'):
                return response.get('data', {})
        except APIError as e:
            logger.error(f"Fehler beim Laden der Trigger-Runs: {e}")
            raise
        return {}

    # ── SMTP Config ────────────────────────────────────────────

    def get_smtp_config(self) -> dict:
        """SMTP-Konfiguration laden (ohne Klartext-Passwort)."""
        try:
            response = self.client.get('/hr/smtp-config')
            if response.get('success'):
                return response.get('data', {}).get('smtp_config', {})
        except APIError as e:
            logger.error(f"Fehler beim Laden der SMTP-Config: {e}")
            raise
        return {}

    def update_smtp_config(self, data: dict) -> dict:
        """SMTP-Konfiguration speichern."""
        try:
            response = self.client.put('/hr/smtp-config', json_data=data)
            if response.get('success'):
                return response.get('data', {})
        except APIError as e:
            logger.error(f"Fehler beim Aktualisieren der SMTP-Config: {e}")
            raise
        return {}

    def get_smtp_config_decrypted(self) -> dict:
        """SMTP-Konfiguration mit Klartext-Passwort laden."""
        try:
            response = self.client.get('/hr/smtp-config/decrypted')
            if response.get('success'):
                return response.get('data', {}).get('smtp_config', {})
        except APIError as e:
            logger.error(f"Fehler beim Laden der entschluesselten SMTP-Config: {e}")
            raise
        return {}
