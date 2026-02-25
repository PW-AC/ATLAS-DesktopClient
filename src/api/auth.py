"""
BiPro API - Authentifizierung

Login, Logout, Token-Verwaltung.
"""

from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
import logging
import json
import os
from pathlib import Path

from .client import APIClient, APIError

logger = logging.getLogger(__name__)

PROVISION_PERMISSIONS = frozenset({'provision_access', 'provision_manage'})


@dataclass
class User:
    """Angemeldeter Benutzer mit Kontotyp und Rechten."""
    id: int
    username: str
    email: Optional[str] = None
    account_type: str = 'user'
    update_channel: str = 'stable'
    permissions: List[str] = field(default_factory=list)
    is_locked: bool = False
    last_login_at: Optional[str] = None

    @property
    def is_admin(self) -> bool:
        """Ist der Benutzer ein Administrator?"""
        return self.account_type == 'admin'

    def has_permission(self, perm: str) -> bool:
        """Prueft ob der Benutzer ein bestimmtes Recht hat.
        Admins haben alle Standard-Rechte. Provision-Rechte muessen explizit vergeben werden."""
        if perm in PROVISION_PERMISSIONS:
            return perm in self.permissions
        return self.is_admin or perm in self.permissions


@dataclass  
class AuthState:
    """Authentifizierungs-Status"""
    is_authenticated: bool
    user: Optional[User] = None
    token: Optional[str] = None
    expires_in: int = 0


class AuthAPI:
    """
    Authentifizierungs-API.
    
    Verwendung:
        auth = AuthAPI(client)
        state = auth.login("admin", "password")
        if state.is_authenticated:
            print(f"Eingeloggt als {state.user.username}")
    """
    
    # Pfad für Token-Persistenz (optional)
    TOKEN_FILE = Path.home() / '.bipro_gdv_token.json'
    
    def __init__(self, client: APIClient):
        self.client = client
        self._current_user: Optional[User] = None
        
    @property
    def current_user(self) -> Optional[User]:
        """Aktuell angemeldeter Benutzer."""
        return self._current_user
    
    @property
    def is_authenticated(self) -> bool:
        """Ist ein Benutzer angemeldet?"""
        return self.client.is_authenticated() and self._current_user is not None
    
    def login(self, username: str, password: str, remember: bool = False) -> AuthState:
        """
        Benutzer anmelden.
        
        Args:
            username: Benutzername
            password: Passwort
            remember: Token lokal speichern für Auto-Login
            
        Returns:
            AuthState mit Anmeldestatus
        """
        try:
            response = self.client.post('/auth/login', json_data={
                'username': username,
                'password': password
            })
            
            if response.get('success'):
                token = response['data']['token']
                user_data = response['data']['user']
                expires_in = response['data'].get('expires_in', 1800)
                
                # Token im Client setzen
                self.client.set_token(token)
                
                # User-Objekt erstellen (mit Kontotyp und Rechten)
                self._current_user = User(
                    id=user_data['id'],
                    username=user_data['username'],
                    email=user_data.get('email'),
                    account_type=user_data.get('account_type', 'user'),
                    update_channel=user_data.get('update_channel', 'stable'),
                    permissions=user_data.get('permissions', [])
                )

                # Token speichern falls gewünscht
                if remember:
                    self._save_token(token, user_data)
                
                logger.info(f"Login erfolgreich: {username}")
                
                return AuthState(
                    is_authenticated=True,
                    user=self._current_user,
                    token=token,
                    expires_in=expires_in
                )
            else:
                logger.warning(f"Login fehlgeschlagen: {response.get('error')}")
                return AuthState(is_authenticated=False)
                
        except APIError as e:
            logger.error(f"Login-Fehler: {e}")
            return AuthState(is_authenticated=False)
    
    def logout(self) -> bool:
        """
        Benutzer abmelden.
        
        Returns:
            True wenn erfolgreich
        """
        try:
            if self.is_authenticated:
                self.client.post('/auth/logout')
        except APIError:
            pass  # Logout-Fehler ignorieren
        
        # Lokalen State zurücksetzen
        self.client.clear_token()
        self._current_user = None
        
        # Gespeicherten Token löschen
        self._delete_saved_token()
        
        logger.info("Logout erfolgreich")
        return True
    
    def verify_token(self) -> bool:
        """
        Prüft ob der aktuelle Token noch gültig ist.
        
        Returns:
            True wenn Token gültig
        """
        if not self.client.is_authenticated():
            return False
            
        try:
            response = self.client.get('/auth/verify')
            return response.get('valid', False)
        except APIError:
            return False
    
    def get_current_user_info(self) -> Optional[Dict[str, Any]]:
        """Holt aktuelle Benutzer-Informationen vom Server."""
        if not self.is_authenticated:
            return None
            
        try:
            response = self.client.get('/auth/me')
            if response.get('success'):
                return response['data']['user']
        except APIError:
            pass
        return None
    
    def try_auto_login(self) -> AuthState:
        """
        Versucht automatischen Login mit gespeichertem Token.
        
        BUG-0014 Fix: Token wird erst nach erfolgreicher Validierung
        persistent gesetzt. Vorheriger Token wird bei Fehler zurueckgerollt.
        
        Returns:
            AuthState
        """
        saved = self._load_saved_token()
        if not saved:
            return AuthState(is_authenticated=False)
        
        token = saved.get('token')
        user_data = saved.get('user')
        
        if not token or not user_data:
            return AuthState(is_authenticated=False)
        
        # BUG-0014 Fix: Alten Token merken fuer Rollback bei Fehler
        old_token = getattr(self.client, '_token', None)
        
        # Token temporaer setzen fuer Validierung (benoetigt fuer API-Call)
        self.client.set_token(token)
        
        verify_result = self._verify_token_with_permissions()
        if verify_result:
            # Token ist gueltig - behalten
            self._current_user = User(
                id=verify_result.get('user_id', user_data['id']),
                username=verify_result.get('username', user_data['username']),
                email=user_data.get('email'),
                account_type=verify_result.get('account_type', user_data.get('account_type', 'user')),
                update_channel=verify_result.get('update_channel', user_data.get('update_channel', 'stable')),
                permissions=verify_result.get('permissions', user_data.get('permissions', []))
            )
            logger.info(f"Auto-Login erfolgreich: {self._current_user.username}")
            return AuthState(
                is_authenticated=True,
                user=self._current_user,
                token=token
            )
        else:
            # Token ungueltig - auf alten Zustand zurueckrollen
            if old_token:
                self.client.set_token(old_token)
            else:
                self.client.clear_token()
            self._delete_saved_token()
            logger.info("Auto-Login fehlgeschlagen: Token abgelaufen")
            return AuthState(is_authenticated=False)
    
    def re_authenticate(self) -> bool:
        """
        Versucht automatische Re-Authentifizierung.
        
        BUG-0014 Fix: Token wird erst nach erfolgreicher Validierung
        persistent gesetzt. Vorheriger Token wird bei Fehler zurueckgerollt.
        
        Strategie:
        1. Token aus gespeicherter Datei laden
        2. Token validieren
        3. Falls ungueltig: Kann nicht automatisch re-authentifizieren
        
        Returns:
            True wenn Token erfolgreich erneuert
        """
        logger.info("Versuche automatische Re-Authentifizierung...")
        
        saved = self._load_saved_token()
        if not saved:
            logger.warning("Kein gespeicherter Token vorhanden")
            return False
        
        token = saved.get('token')
        user_data = saved.get('user')
        
        if not token or not user_data:
            logger.warning("Gespeicherte Token-Daten unvollstaendig")
            return False
        
        # BUG-0014 Fix: Alten Token merken fuer Rollback bei Fehler
        old_token = getattr(self.client, '_token', None)
        
        # Token temporaer setzen fuer Validierung (benoetigt fuer API-Call)
        self.client.set_token(token)
        
        verify_result = self._verify_token_with_permissions()
        if verify_result:
            # Token ist gueltig - behalten
            self._current_user = User(
                id=verify_result.get('user_id', user_data['id']),
                username=verify_result.get('username', user_data['username']),
                email=user_data.get('email'),
                account_type=verify_result.get('account_type', user_data.get('account_type', 'user')),
                update_channel=verify_result.get('update_channel', user_data.get('update_channel', 'stable')),
                permissions=verify_result.get('permissions', user_data.get('permissions', []))
            )
            logger.info(f"Re-Authentifizierung erfolgreich: {self._current_user.username}")
            return True
        
        # Token ungueltig - auf alten Zustand zurueckrollen
        if old_token:
            self.client.set_token(old_token)
        else:
            self.client.clear_token()
        logger.warning("Re-Authentifizierung fehlgeschlagen: Token ungueltig")
        return False
    
    def _verify_token_with_permissions(self) -> Optional[Dict]:
        """
        Prueft Token und gibt erweiterte Daten (inkl. account_type, update_channel, permissions) zurueck.
        
        Returns:
            Dict mit user_id, username, account_type, update_channel, permissions oder None
        """
        if not self.client.is_authenticated():
            return None
            
        try:
            response = self.client.get('/auth/verify')
            if response.get('valid', False):
                return {
                    'user_id': response.get('user_id'),
                    'username': response.get('username'),
                    'account_type': response.get('account_type', 'user'),
                    'update_channel': response.get('update_channel', 'stable'),
                    'permissions': response.get('permissions', [])
                }
        except APIError:
            pass
        return None

    def _save_token(self, token: str, user_data: Dict) -> None:
        """
        SV-005 Fix: Speichert Token lokal mit OS-Schutz.
        Nutzt keyring (Windows Credential Manager/DPAPI) wenn verfuegbar,
        sonst Datei mit restriktiven Permissions.
        """
        data_json = json.dumps({'token': token, 'user': user_data})
        
        # Versuch 1: keyring (bevorzugt, DPAPI-geschuetzt)
        try:
            import keyring
            keyring.set_password("acencia_atlas", "jwt_token", data_json)
            logger.debug("Token in keyring gespeichert (SV-005)")
            # Alte Datei aufraeumen falls vorhanden
            if self.TOKEN_FILE.exists():
                self.TOKEN_FILE.unlink()
            return
        except Exception:
            pass
        
        # Versuch 2: Datei mit restriktiven Permissions (Fallback)
        try:
            self.TOKEN_FILE.write_text(data_json)
            # SV-005: Restriktive Permissions setzen (nur aktueller User)
            import stat
            self.TOKEN_FILE.chmod(stat.S_IRUSR | stat.S_IWUSR)
            logger.debug("Token in Datei gespeichert (SV-005 Fallback, chmod 0600)")
        except Exception as e:
            logger.warning(f"Token speichern fehlgeschlagen: {e}")
    
    def _load_saved_token(self) -> Optional[Dict]:
        """
        SV-005 Fix: Laedt Token aus keyring oder Datei.
        """
        # Versuch 1: keyring
        try:
            import keyring
            data = keyring.get_password("acencia_atlas", "jwt_token")
            if data:
                return json.loads(data)
        except Exception:
            pass
        
        # Versuch 2: Datei (Fallback / Migration)
        try:
            if self.TOKEN_FILE.exists():
                return json.loads(self.TOKEN_FILE.read_text())
        except Exception as e:
            logger.warning(f"Token laden fehlgeschlagen: {e}")
        return None
    
    def _delete_saved_token(self) -> None:
        """
        SV-005 Fix: Loescht Token aus keyring und Datei.
        """
        # keyring aufraeumen
        try:
            import keyring
            keyring.delete_password("acencia_atlas", "jwt_token")
            logger.debug("Token aus keyring geloescht (SV-005)")
        except Exception:
            pass
        
        # Datei aufraeumen
        try:
            if self.TOKEN_FILE.exists():
                self.TOKEN_FILE.unlink()
                logger.debug("Token-Datei geloescht")
        except Exception as e:
            logger.warning(f"Token loeschen fehlgeschlagen: {e}")
