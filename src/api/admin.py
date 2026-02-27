"""
BiPro API - Administration

Nutzerverwaltung, Session-Management und Aktivitaetslog.
Nur fuer Administratoren zugaenglich.
"""

from typing import Optional, Dict, Any, List
import logging

from .client import APIClient, APIError

logger = logging.getLogger(__name__)


class AdminAPI:
    """
    API-Client fuer Administrations-Endpunkte.
    
    Verwendung:
        admin = AdminAPI(client)
        users = admin.get_users()
        admin.lock_user(user_id=5)
    """
    
    def __init__(self, client: APIClient):
        self.client = client
    
    # ================================================================
    # Nutzerverwaltung
    # ================================================================
    
    def get_users(self) -> List[Dict]:
        """Alle Nutzer auflisten (mit Permissions und letzter Aktivitaet)."""
        try:
            response = self.client.get('/admin/users')
            if response.get('success'):
                return response['data'].get('users', [])
        except APIError as e:
            logger.error(f"Fehler beim Laden der Nutzer: {e}")
            raise
        return []
    
    def get_user(self, user_id: int) -> Optional[Dict]:
        """Einzelnen Nutzer mit Details abrufen."""
        try:
            response = self.client.get(f'/admin/users/{user_id}')
            if response.get('success'):
                return response['data'].get('user')
        except APIError as e:
            logger.error(f"Fehler beim Laden des Nutzers {user_id}: {e}")
            raise
        return None
    
    def create_user(self, username: str, password: str, email: str = '',
                    account_type: str = 'user', permissions: List[str] = None) -> Dict:
        """
        Neuen Nutzer erstellen.
        
        Args:
            username: Benutzername (min. 3 Zeichen)
            password: Passwort (min. 8 Zeichen)
            email: E-Mail-Adresse
            account_type: 'admin' oder 'user'
            permissions: Liste von Permission-Keys
        """
        data = {
            'username': username,
            'password': password,
            'email': email,
            'account_type': account_type,
            'permissions': permissions or []
        }
        try:
            response = self.client.post('/admin/users', json_data=data)
            if response.get('success'):
                return response['data'].get('user', {})
        except APIError as e:
            logger.error(f"Fehler beim Erstellen des Nutzers: {e}")
            raise
        return {}
    
    def update_user(self, user_id: int, email: str = None,
                    account_type: str = None, permissions: List[str] = None) -> Dict:
        """Nutzer bearbeiten (nur geaenderte Felder senden)."""
        data = {}
        if email is not None:
            data['email'] = email
        if account_type is not None:
            data['account_type'] = account_type
        if permissions is not None:
            data['permissions'] = permissions
        
        try:
            response = self.client.put(f'/admin/users/{user_id}', json_data=data)
            if response.get('success'):
                return response['data'].get('user', {})
        except APIError as e:
            logger.error(f"Fehler beim Aktualisieren des Nutzers {user_id}: {e}")
            raise
        return {}
    
    def change_password(self, user_id: int, new_password: str) -> bool:
        """Passwort eines Nutzers aendern (invalidiert alle Sessions)."""
        try:
            response = self.client.put(f'/admin/users/{user_id}/password', json_data={
                'new_password': new_password
            })
            return response.get('success', False)
        except APIError as e:
            logger.error(f"Fehler beim Passwort-Aendern fuer Nutzer {user_id}: {e}")
            raise
    
    def lock_user(self, user_id: int) -> bool:
        """Nutzer sperren (invalidiert alle Sessions)."""
        try:
            response = self.client.put(f'/admin/users/{user_id}/lock')
            return response.get('success', False)
        except APIError as e:
            logger.error(f"Fehler beim Sperren des Nutzers {user_id}: {e}")
            raise
    
    def unlock_user(self, user_id: int) -> bool:
        """Nutzer entsperren."""
        try:
            response = self.client.put(f'/admin/users/{user_id}/unlock')
            return response.get('success', False)
        except APIError as e:
            logger.error(f"Fehler beim Entsperren des Nutzers {user_id}: {e}")
            raise
    
    def delete_user(self, user_id: int) -> bool:
        """Nutzer deaktivieren (Soft-Delete)."""
        try:
            response = self.client.delete(f'/admin/users/{user_id}')
            return response.get('success', False)
        except APIError as e:
            logger.error(f"Fehler beim Deaktivieren des Nutzers {user_id}: {e}")
            raise
    
    def get_permissions(self) -> List[Dict]:
        """Alle verfuegbaren Rechte auflisten."""
        try:
            response = self.client.get('/admin/permissions')
            if response.get('success'):
                return response['data'].get('permissions', [])
        except APIError as e:
            logger.error(f"Fehler beim Laden der Rechte: {e}")
            raise
        return []
    
    # ================================================================
    # Session-Verwaltung
    # ================================================================
    
    def get_sessions(self, user_id: int = None) -> List[Dict]:
        """
        Aktive Sessions auflisten.
        
        Args:
            user_id: Optional - nur Sessions dieses Users
        """
        try:
            if user_id:
                response = self.client.get(f'/sessions/user/{user_id}')
            else:
                response = self.client.get('/sessions')
            if response.get('success'):
                return response['data'].get('sessions', [])
        except APIError as e:
            logger.error(f"Fehler beim Laden der Sessions: {e}")
            raise
        return []
    
    def kill_session(self, session_id: int) -> bool:
        """Einzelne Session beenden."""
        try:
            response = self.client.delete(f'/sessions/{session_id}')
            return response.get('success', False)
        except APIError as e:
            logger.error(f"Fehler beim Beenden der Session {session_id}: {e}")
            raise
    
    def kill_user_sessions(self, user_id: int) -> bool:
        """Alle Sessions eines Users beenden."""
        try:
            response = self.client.delete(f'/sessions/user/{user_id}')
            return response.get('success', False)
        except APIError as e:
            logger.error(f"Fehler beim Beenden aller Sessions fuer User {user_id}: {e}")
            raise
    
    # ================================================================
    # Aktivitaetslog
    # ================================================================
    
    def get_activity_log(self, user_id: int = None, action_category: str = None,
                         status: str = None, from_date: str = None, to_date: str = None,
                         search: str = None, page: int = 1, per_page: int = 50) -> Dict:
        """
        Aktivitaetslog mit Filtern abrufen.
        
        Returns:
            Dict mit 'items', 'total', 'page', 'per_page', 'total_pages'
        """
        params = {'page': str(page), 'per_page': str(per_page)}
        if user_id:
            params['user_id'] = str(user_id)
        if action_category:
            params['action_category'] = action_category
        if status:
            params['status'] = status
        if from_date:
            params['from'] = from_date
        if to_date:
            params['to'] = to_date
        if search:
            params['search'] = search
        
        # Query-String bauen
        query = '&'.join(f'{k}={v}' for k, v in params.items())
        
        try:
            response = self.client.get(f'/activity?{query}')
            if response.get('success'):
                return response['data']
        except APIError as e:
            logger.error(f"Fehler beim Laden des Aktivitaetslogs: {e}")
            raise
        return {'items': [], 'total': 0, 'page': 1, 'per_page': per_page, 'total_pages': 0}
    
    def get_activity_stats(self) -> Dict:
        """Aktivitaets-Statistiken abrufen."""
        try:
            response = self.client.get('/activity/stats')
            if response.get('success'):
                return response['data']
        except APIError as e:
            logger.error(f"Fehler beim Laden der Aktivitaets-Statistiken: {e}")
            raise
        return {}

    # ================================================================
    # Server-Diagnostik
    # ================================================================

    def run_health_check(self) -> Dict:
        """Vollstaendigen Server-Health-Check ausfuehren."""
        try:
            response = self.client.get('/admin/diagnostics')
            if response.get('success'):
                return response['data']
        except APIError as e:
            logger.error(f"Fehler beim Health-Check: {e}")
            raise
        return {}

    def get_health_history(self, limit: int = 20) -> List[Dict]:
        """Vergangene Health-Check-Laeufe abrufen."""
        try:
            response = self.client.get(f'/admin/diagnostics/history?limit={limit}')
            if response.get('success'):
                return response['data'].get('runs', [])
        except APIError as e:
            logger.error(f"Fehler beim Laden der Health-History: {e}")
            raise
        return []

    # ================================================================
    # Migrations-Verwaltung
    # ================================================================

    def get_migrations(self) -> Dict:
        """Alle verfuegbaren Migrationsdateien aus setup/ auflisten."""
        try:
            response = self.client.get('/admin/migrations')
            if response.get('success'):
                return response['data']
        except APIError as e:
            logger.error(f"Fehler beim Laden der Migrationen: {e}")
            raise
        return {'migrations': [], 'total': 0, 'pending': 0, 'applied': 0, 'manual': 0}

    def execute_migration(self, filename: str) -> Dict:
        """Eine Migrationsdatei ausfuehren."""
        try:
            response = self.client.post('/admin/migrations/execute',
                                        json_data={'filename': filename})
            return {
                'success': response.get('success', False),
                'output': response.get('data', {}).get('output', ''),
                'filename': filename,
            }
        except APIError as e:
            logger.error(f"Fehler beim Ausfuehren der Migration {filename}: {e}")
            raise
