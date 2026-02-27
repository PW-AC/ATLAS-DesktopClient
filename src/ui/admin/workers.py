"""
ACENCIA ATLAS - Admin Worker-Klassen

8 QThread-Worker fuer asynchrone Admin-Operationen.
Extrahiert aus admin_view.py (Schritt 4 Refactoring).
"""

from typing import Dict

from PySide6.QtCore import QThread, Signal

from api.client import APIClient
from api.admin import AdminAPI
from api.releases import ReleasesAPI


class AdminWriteWorker(QThread):
    """Fuehrt Admin-Schreiboperationen im Hintergrund aus."""
    finished = Signal(object)  # Ergebnis oder None
    error = Signal(str)
    
    def __init__(self, func, *args, **kwargs):
        super().__init__()
        self._func = func
        self._args = args
        self._kwargs = kwargs
    
    def run(self):
        try:
            result = self._func(*self._args, **self._kwargs)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class LoadUsersWorker(QThread):
    """Laedt Nutzer im Hintergrund."""
    finished = Signal(list)
    error = Signal(str)
    
    def __init__(self, admin_api: AdminAPI):
        super().__init__()
        self._admin_api = admin_api
    
    def run(self):
        try:
            users = self._admin_api.get_users()
            self.finished.emit(users)
        except Exception as e:
            self.error.emit(str(e))


class LoadSessionsWorker(QThread):
    """Laedt Sessions im Hintergrund."""
    finished = Signal(list)
    error = Signal(str)
    
    def __init__(self, admin_api: AdminAPI, user_id: int = None):
        super().__init__()
        self._admin_api = admin_api
        self._user_id = user_id
    
    def run(self):
        try:
            sessions = self._admin_api.get_sessions(self._user_id)
            self.finished.emit(sessions)
        except Exception as e:
            self.error.emit(str(e))


class LoadActivityWorker(QThread):
    """Laedt Aktivitaetslog im Hintergrund."""
    finished = Signal(dict)
    error = Signal(str)
    
    def __init__(self, admin_api: AdminAPI, filters: Dict):
        super().__init__()
        self._admin_api = admin_api
        self._filters = filters
    
    def run(self):
        try:
            result = self._admin_api.get_activity_log(**self._filters)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class LoadCostDataWorker(QThread):
    """Laedt Kosten-Historie und Statistiken im Hintergrund."""
    finished = Signal(dict)  # {'history': [...], 'stats': {...}}
    error = Signal(str)
    
    def __init__(self, api_client: APIClient, from_date: str = None, to_date: str = None):
        super().__init__()
        self._api_client = api_client
        self._from_date = from_date
        self._to_date = to_date
    
    def run(self):
        try:
            from api.processing_history import ProcessingHistoryAPI
            
            history_api = ProcessingHistoryAPI(self._api_client)
            
            # Kosten-Historie laden
            entries, total = history_api.get_cost_history(
                from_date=self._from_date,
                to_date=self._to_date,
                limit=500
            )
            
            # Kosten-Statistiken laden
            stats = history_api.get_cost_stats(
                from_date=self._from_date,
                to_date=self._to_date
            )
            
            self.finished.emit({
                'history': entries,
                'total': total,
                'stats': stats or {}
            })
        except Exception as e:
            self.error.emit(str(e))


class LoadReleasesWorker(QThread):
    """Laedt Releases im Hintergrund."""
    finished = Signal(list)
    error = Signal(str)
    
    def __init__(self, releases_api: ReleasesAPI):
        super().__init__()
        self._releases_api = releases_api
    
    def run(self):
        try:
            releases = self._releases_api.get_releases()
            self.finished.emit(releases)
        except Exception as e:
            self.error.emit(str(e))


class UploadReleaseWorker(QThread):
    """Laedt ein Release hoch."""
    finished = Signal(dict)
    error = Signal(str)
    
    def __init__(self, releases_api: ReleasesAPI, file_path: str, version: str,
                 channel: str, release_notes: str, min_version: str):
        super().__init__()
        self._releases_api = releases_api
        self._file_path = file_path
        self._version = version
        self._channel = channel
        self._release_notes = release_notes
        self._min_version = min_version
    
    def run(self):
        try:
            result = self._releases_api.create_release(
                file_path=self._file_path,
                version=self._version,
                channel=self._channel,
                release_notes=self._release_notes,
                min_version=self._min_version
            )
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class RunHealthCheckWorker(QThread):
    """Fuehrt den Server-Health-Check im Hintergrund aus."""
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, admin_api: AdminAPI):
        super().__init__()
        self._admin_api = admin_api

    def run(self):
        try:
            result = self._admin_api.run_health_check()
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class LoadHealthHistoryWorker(QThread):
    """Laedt Health-Check-Historie im Hintergrund."""
    finished = Signal(list)
    error = Signal(str)

    def __init__(self, admin_api: AdminAPI, limit: int = 20):
        super().__init__()
        self._admin_api = admin_api
        self._limit = limit

    def run(self):
        try:
            runs = self._admin_api.get_health_history(self._limit)
            self.finished.emit(runs)
        except Exception as e:
            self.error.emit(str(e))


class LoadMigrationsWorker(QThread):
    """Laedt verfuegbare Migrationsdateien im Hintergrund."""
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, admin_api: AdminAPI):
        super().__init__()
        self._admin_api = admin_api

    def run(self):
        try:
            result = self._admin_api.get_migrations()
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class ExecuteMigrationWorker(QThread):
    """Fuehrt eine Migrationsdatei im Hintergrund aus."""
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, admin_api: AdminAPI, filename: str):
        super().__init__()
        self._admin_api = admin_api
        self._filename = filename

    def run(self):
        try:
            result = self._admin_api.execute_migration(self._filename)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class ImapPollWorker(QThread):
    """Ruft IMAP-Postfach im Hintergrund ab (verhindert UI-Freeze)."""
    finished = Signal(dict)
    error = Signal(str)
    
    def __init__(self, email_accounts_api, account_id: int):
        super().__init__()
        self._api = email_accounts_api
        self._account_id = account_id
    
    def run(self):
        try:
            result = self._api.poll_inbox(self._account_id)
            self.finished.emit(result if result else {})
        except Exception as e:
            self.error.emit(str(e))
