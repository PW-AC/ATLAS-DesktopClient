"""
ACENCIA ATLAS - Server-Management API Client

Endpunkte unter /admin/server/* (nur super_admin).
"""

import logging
from typing import List, Dict, Optional

from .client import APIClient, APIError

logger = logging.getLogger(__name__)


class ServerManagementAPI:
    """API-Client fuer Server-Management (super_admin only)."""

    def __init__(self, client: APIClient):
        self.client = client

    def get_connections(self) -> List[Dict]:
        resp = self.client.get('/admin/server/connections')
        if resp.get('success'):
            return resp['data'].get('connections', [])
        return []

    def kill_connection(self, pid: int) -> Dict:
        return self.client.post('/admin/server/connections/kill', json_data={'pid': pid})

    def get_fail2ban_status(self) -> List[Dict]:
        resp = self.client.get('/admin/server/fail2ban')
        if resp.get('success'):
            return resp['data'].get('jails', [])
        return []

    def unban_ip(self, ip: str, jail: str) -> Dict:
        return self.client.post('/admin/server/fail2ban/unban', json_data={'ip': ip, 'jail': jail})

    def get_fail2ban_history(self, limit: int = 100) -> List[Dict]:
        resp = self.client.get(f'/admin/server/fail2ban/history?limit={limit}')
        if resp.get('success'):
            return resp['data'].get('bans', [])
        return []

    def get_firewall_status(self) -> Dict:
        resp = self.client.get('/admin/server/firewall')
        if resp.get('success'):
            return resp.get('data', {})
        return {}

    def reload_firewall(self) -> Dict:
        return self.client.post('/admin/server/firewall/reload')

    def get_services(self) -> List[Dict]:
        resp = self.client.get('/admin/server/services')
        if resp.get('success'):
            return resp['data'].get('services', [])
        return []

    def restart_service(self, service: str) -> Dict:
        return self.client.post('/admin/server/services/restart', json_data={'service': service})

    def get_system_info(self) -> Dict:
        resp = self.client.get('/admin/server/system')
        if resp.get('success'):
            return resp.get('data', {})
        return {}

    def reboot_server(self) -> Dict:
        return self.client.post('/admin/server/reboot', json_data={'confirm': 'REBOOT'})

    def exec_command(self, command: str) -> Dict:
        resp = self.client.post('/admin/server/exec', json_data={'command': command})
        if resp.get('success'):
            return resp.get('data', {})
        return {'output': resp.get('error', 'Fehler'), 'duration_ms': 0}
