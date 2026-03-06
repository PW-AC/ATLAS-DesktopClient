"""
ACENCIA ATLAS - Admin Modul- und Rollenverwaltung API
"""

import logging
from typing import List, Dict, Any, Optional

from .client import APIClient, APIError

logger = logging.getLogger(__name__)


class AdminModulesAPI:
    """API-Client fuer Modul- und Rollenverwaltung."""

    def __init__(self, client: APIClient):
        self.client = client

    def get_modules(self) -> List[Dict]:
        resp = self.client.get('/admin/modules')
        if resp.get('success'):
            return resp['data'].get('modules', [])
        return []

    def get_user_modules(self, user_id: int) -> List[Dict]:
        resp = self.client.get(f'/admin/users/{user_id}/modules')
        if resp.get('success'):
            return resp['data'].get('modules', [])
        return []

    def update_user_modules(self, user_id: int, modules: List[Dict]) -> Dict:
        return self.client.put(f'/admin/users/{user_id}/modules', json_data={
            'modules': modules
        })

    def get_module_roles(self, module_key: str) -> List[Dict]:
        resp = self.client.get(f'/admin/modules/{module_key}/roles')
        if resp.get('success'):
            return resp['data'].get('roles', [])
        return []

    def create_role(self, module_key: str, role_key: str, name: str,
                    description: str = '', permissions: Optional[List[str]] = None) -> Dict:
        data: Dict[str, Any] = {
            'role_key': role_key,
            'name': name,
            'description': description,
        }
        if permissions:
            data['permissions'] = permissions
        return self.client.post(f'/admin/modules/{module_key}/roles', json_data=data)

    def update_role(self, module_key: str, role_id: int, data: Dict) -> Dict:
        return self.client.put(f'/admin/modules/{module_key}/roles/{role_id}', json_data=data)

    def delete_role(self, module_key: str, role_id: int) -> Dict:
        return self.client.delete(f'/admin/modules/{module_key}/roles/{role_id}')

    def get_module_permissions(self, module_key: str) -> List[Dict]:
        resp = self.client.get(f'/admin/modules/{module_key}/permissions')
        if resp.get('success'):
            return resp['data'].get('permissions', [])
        return []

    def get_module_users(self, module_key: str) -> List[Dict]:
        resp = self.client.get(f'/admin/modules/{module_key}/users')
        if resp.get('success'):
            return resp['data'].get('users', [])
        return []

    def assign_user_roles(self, module_key: str, user_id: int, role_ids: List[int]) -> Dict:
        return self.client.put(
            f'/admin/modules/{module_key}/users/{user_id}/roles',
            json_data={'role_ids': role_ids}
        )
