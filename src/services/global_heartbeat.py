"""
Globaler Heartbeat-Service

Laeuft kontinuierlich nach Login, unabhaengig vom aktiven Modul.
Prueft alle 5 Sekunden:
- Session-Gueltigkeit (GET /auth/verify)
- Nutzerrechte (Permissions aus verify-Response)
- Notification-Summary (GET /notifications/summary)
- System-Status (GET /system/status)
"""

import logging
from typing import Optional

from PySide6.QtCore import QObject, QTimer, QThread, Signal

logger = logging.getLogger(__name__)
hb_logger = logging.getLogger('heartbeat.global')

HEARTBEAT_INTERVAL_MS = 5_000


class _HeartbeatWorker(QThread):
    """Fuehrt alle Heartbeat-API-Calls in einem Hintergrund-Thread aus."""

    result_ready = Signal(dict)

    def __init__(self, api_client, auth_api, last_message_ts: Optional[str] = None,
                 parent=None):
        super().__init__(parent)
        self._api_client = api_client
        self._auth_api = auth_api
        self._last_message_ts = last_message_ts

    def run(self):
        result = {
            'session_valid': False,
            'permissions': [],
            'notifications': {},
            'system_status': None,
            'system_message': '',
        }

        if not self._api_client.is_authenticated():
            self.result_ready.emit(result)
            return

        try:
            verify_resp = self._api_client.get('/auth/verify')
            if verify_resp.get('valid', False):
                result['session_valid'] = True
                result['permissions'] = verify_resp.get('permissions', [])
                result['account_type'] = verify_resp.get('account_type', 'user')
                result['update_channel'] = verify_resp.get('update_channel', 'stable')
                result['username'] = verify_resp.get('username', '')
                result['modules'] = verify_resp.get('modules', [])
                result['roles'] = verify_resp.get('roles', [])
            else:
                self.result_ready.emit(result)
                return
        except Exception as e:
            logger.debug(f"Heartbeat session-check fehlgeschlagen: {e}")
            self.result_ready.emit(result)
            return

        try:
            from api.messages import MessagesAPI
            messages_api = MessagesAPI(self._api_client)
            notif = messages_api.get_notifications_summary(
                last_message_ts=self._last_message_ts
            )
            try:
                from api.bipro_events import BiproEventsAPI
                bipro_api = BiproEventsAPI(self._api_client)
                ev_summary = bipro_api.get_summary()
                notif['unread_bipro_events'] = ev_summary.get('unread_count', 0)
            except Exception:
                notif['unread_bipro_events'] = 0
            result['notifications'] = notif
        except Exception as e:
            logger.debug(f"Heartbeat notifications fehlgeschlagen: {e}")

        try:
            from api.system_status import SystemStatusAPI
            status_api = SystemStatusAPI(self._api_client)
            status_result = status_api.get_status()
            result['system_status'] = status_result.status
            result['system_message'] = status_result.message or ''
        except Exception as e:
            logger.debug(f"Heartbeat system-status fehlgeschlagen: {e}")

        self.result_ready.emit(result)


class GlobalHeartbeat(QObject):
    """
    Globaler Heartbeat -- laeuft dauerhaft nach Login.

    Signale:
        session_invalid: Session abgelaufen, Forced-Logout noetig
        permissions_updated(list): Nutzerrechte haben sich geaendert
        notifications_updated(dict): Notification-Summary (unread_chats, etc.)
        system_status_changed(str, str): (status, message) fuer Maintenance-Check
    """

    session_invalid = Signal()
    permissions_updated = Signal(list)
    modules_updated = Signal()
    notifications_updated = Signal(dict)
    system_status_changed = Signal(str, str)

    def __init__(self, api_client, auth_api, parent=None):
        super().__init__(parent)
        self._api_client = api_client
        self._auth_api = auth_api
        self._worker: Optional[_HeartbeatWorker] = None
        self._last_message_ts: Optional[str] = None
        self._prev_permissions: list = []
        self._prev_module_keys: list = []
        self._running = False

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    def start(self):
        """Startet den Heartbeat."""
        if self._running:
            return
        self._running = True
        self._prev_permissions = list(
            self._auth_api.current_user.permissions
        ) if self._auth_api.current_user else []
        self._timer.start(HEARTBEAT_INTERVAL_MS)
        QTimer.singleShot(1_000, self._tick)
        hb_logger.info(f"[GLOBAL] START (Intervall={HEARTBEAT_INTERVAL_MS}ms)")

    def stop(self):
        """Stoppt den Heartbeat."""
        self._running = False
        self._timer.stop()
        hb_logger.info("[GLOBAL] STOP")

    def force_check(self):
        """Einmaliger sofortiger Check."""
        self._tick()

    def _tick(self):
        if not self._running:
            return
        if self._worker and self._worker.isRunning():
            return
        hb_logger.info("[GLOBAL] TICK")

        self._worker = _HeartbeatWorker(
            self._api_client, self._auth_api,
            last_message_ts=self._last_message_ts,
            parent=self,
        )
        self._worker.result_ready.connect(self._on_result)
        self._worker.start()

    def _on_result(self, data: dict):
        if not data.get('session_valid'):
            logger.warning("GlobalHeartbeat: Session ungueltig")
            self.session_invalid.emit()
            return

        user = self._auth_api.current_user
        new_perms = data.get('permissions', [])
        perms_changed = sorted(new_perms) != sorted(self._prev_permissions)

        from api.auth import UserModule, UserRole
        raw_modules = data.get('modules', [])
        new_module_keys = sorted(
            m.get('module_key', '') for m in raw_modules if m.get('is_enabled')
        )
        modules_changed = new_module_keys != self._prev_module_keys

        if user:
            user.permissions = new_perms
            user.account_type = data.get('account_type', user.account_type)
            user.update_channel = data.get('update_channel', user.update_channel)
            if raw_modules:
                user.modules = [
                    UserModule(
                        module_key=m.get('module_key', ''),
                        group_key=m.get('group_key', ''),
                        name=m.get('name', ''),
                        is_enabled=bool(m.get('is_enabled', False)),
                        access_level=m.get('access_level', 'user')
                    ) for m in raw_modules
                ]
            raw_roles = data.get('roles', [])
            if raw_roles:
                user.roles = [
                    UserRole(
                        role_id=int(r.get('role_id', 0)),
                        role_key=r.get('role_key', ''),
                        module_key=r.get('module_key', '')
                    ) for r in raw_roles
                ]

        if perms_changed:
            self._prev_permissions = list(new_perms)
            self.permissions_updated.emit(new_perms)

        if modules_changed:
            self._prev_module_keys = new_module_keys
            self.modules_updated.emit()

        notif = data.get('notifications', {})
        if notif:
            latest = notif.get('latest_chat_message')
            if latest and latest.get('created_at'):
                self._last_message_ts = latest['created_at']
            self.notifications_updated.emit(notif)

        status = data.get('system_status')
        if status:
            self.system_status_changed.emit(status, data.get('system_message', ''))
