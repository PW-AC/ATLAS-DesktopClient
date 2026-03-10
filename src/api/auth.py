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
from config.server_config import CONTROL_API_URL, API_VERIFY_SSL
from config.runtime import is_dev_mode

logger = logging.getLogger(__name__)

@dataclass
class UserModule:
    """Modul-Freischaltung eines Benutzers."""
    module_key: str
    group_key: str
    name: str
    is_enabled: bool
    access_level: str  # 'user' | 'admin'


@dataclass
class UserRole:
    """Rollenzuweisung eines Benutzers."""
    role_id: int
    role_key: str
    module_key: str


@dataclass
class User:
    """Angemeldeter Benutzer mit Kontotyp, Modulen, Rollen und Rechten."""
    id: int
    username: str
    email: Optional[str] = None
    account_type: str = 'user'
    update_channel: str = 'stable'
    permissions: List[str] = field(default_factory=list)
    modules: List[UserModule] = field(default_factory=list)
    roles: List[UserRole] = field(default_factory=list)
    is_locked: bool = False
    last_login_at: Optional[str] = None

    @property
    def is_admin(self) -> bool:
        return self.account_type in ('admin', 'super_admin')

    @property
    def is_super_admin(self) -> bool:
        return self.account_type == 'super_admin'

    def has_module(self, module_key: str) -> bool:
        return any(m.module_key == module_key and m.is_enabled for m in self.modules)

    def is_module_admin(self, module_key: str) -> bool:
        return any(
            m.module_key == module_key and m.is_enabled and m.access_level == 'admin'
            for m in self.modules
        )

    def has_permission(self, perm: str) -> bool:
        return perm in self.permissions


@dataclass
class TenantInfo:
    """Informationen ueber ein verfuegbares Universe."""
    tenant_id: int
    tenant_key: str
    tenant_name: str
    role: str
    status: str
    schema_version: int = 0


@dataclass  
class AuthState:
    """Authentifizierungs-Status"""
    is_authenticated: bool
    user: Optional[User] = None
    token: Optional[str] = None
    expires_in: int = 0
    tenants: List[TenantInfo] = field(default_factory=list)
    selected_tenant: Optional[TenantInfo] = None


def _build_user(data: Dict) -> User:
    """Erstellt ein User-Objekt aus API-Response-Daten."""
    modules = []
    for m in data.get('modules', []):
        try:
            modules.append(UserModule(
                module_key=m.get('module_key', ''),
                group_key=m.get('group_key', ''),
                name=m.get('name', ''),
                is_enabled=bool(m.get('is_enabled', False)),
                access_level=m.get('access_level', 'user')
            ))
        except Exception:
            continue
    roles = []
    for r in data.get('roles', []):
        try:
            roles.append(UserRole(
                role_id=int(r.get('role_id', 0)),
                role_key=r.get('role_key', ''),
                module_key=r.get('module_key', '')
            ))
        except Exception:
            continue
    return User(
        id=data.get('id', data.get('user_id', 0)),
        username=data.get('username', ''),
        email=data.get('email'),
        account_type=data.get('account_type', 'user'),
        update_channel=data.get('update_channel', 'stable'),
        permissions=data.get('permissions', []),
        modules=modules,
        roles=roles,
        is_locked=bool(data.get('is_locked', False)),
        last_login_at=data.get('last_login_at')
    )


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
        self._control_token: Optional[str] = None
        self._active_tenant: Optional[TenantInfo] = None
        
    @property
    def current_user(self) -> Optional[User]:
        """Aktuell angemeldeter Benutzer."""
        return self._current_user
    
    @property
    def is_authenticated(self) -> bool:
        """Ist ein Benutzer angemeldet?"""
        return self.client.is_authenticated() and self._current_user is not None

    @property
    def active_tenant(self) -> Optional[TenantInfo]:
        """Aktuell ausgewaehltes Universe."""
        return self._active_tenant
    
    def login(self, username: str, password: str, remember: bool = False) -> AuthState:
        """
        Benutzer anmelden (zweistufig ueber Control Plane).

        Flow:
        1. POST /control/api/auth/login -> Control-JWT + Tenant-Liste
        2. Bei genau 1 Universe: automatisch Tenant-JWT (im Response enthalten)
        3. Bei mehreren: tenants-Liste zurueckgeben, Client ruft select_tenant() auf
        4. Fallback auf /api/auth/login wenn Control Plane nicht erreichbar
        """
        # Schritt 1: Control Plane Login versuchen
        control_state = self._try_control_login(username, password, remember)
        if control_state is not None:
            return control_state

        # Fallback: Alt-Login direkt gegen Tenant-API
        logger.info("Control Plane nicht erreichbar, Fallback auf Tenant-API Login")
        return self._legacy_login(username, password, remember)

    def _try_control_login(self, username: str, password: str, remember: bool) -> Optional[AuthState]:
        """Login ueber Control Plane API. Gibt None zurueck wenn nicht erreichbar."""
        import requests as req

        try:
            resp = req.post(
                f"{CONTROL_API_URL}/auth/login",
                json={'username': username, 'password': password},
                verify=API_VERIFY_SSL,
                timeout=10,
            )
        except (req.ConnectionError, req.Timeout) as e:
            logger.warning(f"Control Plane nicht erreichbar: {e}")
            return None

        data = resp.json() if resp.headers.get('content-type', '').startswith('application/json') else {}

        if resp.status_code == 401:
            # User nicht in control_users -- Fallback auf Tenant-API
            # (wo der Reverse-Sync den User automatisch hochsynchronisiert)
            logger.info("Control Plane: 401 -- Fallback auf Tenant-API fuer Reverse-Sync")
            return None
        if resp.status_code == 403:
            raise APIError(data.get('error', 'Zugriff verweigert'), 403)
        if resp.status_code == 429:
            raise APIError(data.get('error', 'Zu viele Versuche'), 429)
        if not data.get('success'):
            raise APIError(data.get('error', 'Login fehlgeschlagen'), resp.status_code)

        self._control_token = data.get('control_token')

        tenants = [
            TenantInfo(
                tenant_id=t['tenant_id'],
                tenant_key=t['tenant_key'],
                tenant_name=t['tenant_name'],
                role=t['role'],
                status=t['status'],
                schema_version=t.get('schema_version', 0),
            )
            for t in data.get('tenants', [])
        ]

        # Auto-selected (genau 1 Universe, Server hat Tenant-JWT mitgegeben)
        if 'tenant_token' in data and data.get('selected_tenant'):
            token = data['tenant_token']
            self.client.set_token(token)

            st = data['selected_tenant']
            selected = TenantInfo(
                tenant_id=st['tenant_id'],
                tenant_key=st['tenant_key'],
                tenant_name=st['tenant_name'],
                role=st['role'],
                status='active',
                schema_version=st.get('schema_version', 0),
            )
            self._active_tenant = selected

            user_info = self._fetch_user_info()
            if user_info:
                self._current_user = _build_user(user_info)
            else:
                user_data = data.get('user', {})
                self._current_user = _build_user(user_data)

            if remember and not is_dev_mode():
                self._save_token(token, self._serialize_user(self._current_user))

            logger.info(f"Login erfolgreich (Control Plane, auto-select): {username} -> {selected.tenant_key}")

            return AuthState(
                is_authenticated=True,
                user=self._current_user,
                token=token,
                tenants=tenants,
                selected_tenant=selected,
            )

        # Mehrere Universes: Noch nicht eingeloggt, Client muss waehlen
        logger.info(f"Login erfolgreich, {len(tenants)} Universe(s) verfuegbar")
        return AuthState(
            is_authenticated=False,
            tenants=tenants,
        )

    def select_tenant(self, tenant_id: int, remember: bool = False) -> AuthState:
        """
        Universe auswaehlen (Schritt 2 des zweistufigen Logins).
        Erfordert vorherigen erfolgreichen Control-Login.
        """
        import requests as req

        if not self._control_token:
            raise APIError("Kein Control-Token vorhanden. Zuerst login() aufrufen.", 401)

        try:
            resp = req.post(
                f"{CONTROL_API_URL}/auth/select-tenant",
                json={'tenant_id': tenant_id},
                headers={'Authorization': f'Bearer {self._control_token}'},
                verify=API_VERIFY_SSL,
                timeout=10,
            )
        except (req.ConnectionError, req.Timeout) as e:
            raise APIError(f"Control Plane nicht erreichbar: {e}", 0)

        data = resp.json() if resp.headers.get('content-type', '').startswith('application/json') else {}

        if not data.get('success'):
            raise APIError(data.get('error', 'Tenant-Auswahl fehlgeschlagen'), resp.status_code)

        token = data['tenant_token']
        self.client.set_token(token)

        t = data['tenant']
        selected = TenantInfo(
            tenant_id=t['tenant_id'],
            tenant_key=t['tenant_key'],
            tenant_name=t['tenant_name'],
            role=t['role'],
            status='active',
            schema_version=t.get('schema_version', 0),
        )
        self._active_tenant = selected

        user_info = self._fetch_user_info()
        if user_info:
            self._current_user = _build_user(user_info)

        if remember and self._current_user and not is_dev_mode():
            self._save_token(token, self._serialize_user(self._current_user))

        logger.info(f"Universe ausgewaehlt: {selected.tenant_key}")

        return AuthState(
            is_authenticated=True,
            user=self._current_user,
            token=token,
            selected_tenant=selected,
        )

    def _fetch_user_info(self) -> Optional[Dict]:
        """Laedt User-Info inkl. Permissions von /auth/me."""
        try:
            response = self.client.get('/auth/me')
            if response.get('success'):
                return response['data']['user']
        except APIError:
            pass
        return None

    def _serialize_user(self, user: User) -> Dict:
        """Serialisiert User-Objekt fuer Token-Persistenz."""
        return {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'account_type': user.account_type,
            'update_channel': user.update_channel,
            'permissions': user.permissions,
        }

    def _legacy_login(self, username: str, password: str, remember: bool) -> AuthState:
        """Fallback: Login direkt gegen Tenant-API (Alt-Endpoint)."""
        try:
            response = self.client.post('/auth/login', json_data={
                'username': username,
                'password': password
            })

            if response.get('success'):
                token = response['data']['token']
                user_data = response['data']['user']
                expires_in = response['data'].get('expires_in', 1800)

                self.client.set_token(token)
                self._current_user = _build_user(user_data)

                tenant_data = response['data'].get('tenant')
                if tenant_data:
                    self._active_tenant = TenantInfo(
                        tenant_id=tenant_data.get('tenant_id', 0),
                        tenant_key=tenant_data.get('tenant_key', ''),
                        tenant_name=tenant_data.get('tenant_name', ''),
                        role='tenant_user',
                        status='active',
                    )
                else:
                    self._extract_tenant_from_token(token)

                if remember and not is_dev_mode():
                    self._save_token(token, user_data)

                logger.info(f"Login erfolgreich (Legacy): {username}")

                return AuthState(
                    is_authenticated=True,
                    user=self._current_user,
                    token=token,
                    expires_in=expires_in,
                    selected_tenant=self._active_tenant,
                )
            else:
                raise APIError(response.get('error', 'Login fehlgeschlagen'))

        except APIError as e:
            logger.error(f"Login-Fehler: {e}")
            raise

    def _extract_tenant_from_token(self, token: str) -> None:
        """Extrahiert Tenant-Info aus dem JWT-Payload (Base64-Decode, keine Signaturpruefung)."""
        import base64
        try:
            parts = token.split('.')
            if len(parts) != 3:
                return
            padding = '=' * (4 - len(parts[1]) % 4)
            payload_json = base64.urlsafe_b64decode(parts[1] + padding)
            payload = json.loads(payload_json)

            tenant_key = payload.get('tenant_key')
            tenant_id = payload.get('tenant_id')
            if tenant_key and tenant_id:
                self._active_tenant = TenantInfo(
                    tenant_id=int(tenant_id),
                    tenant_key=tenant_key,
                    tenant_name=tenant_key.replace('_', ' ').title(),
                    role=payload.get('tenant_role', 'tenant_user'),
                    status='active',
                )
                logger.debug(f"Tenant aus Token extrahiert: {tenant_key}")
        except Exception as e:
            logger.debug(f"Tenant-Extraktion aus Token fehlgeschlagen: {e}")
    
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
        
        # Gespeicherten Token löschen (nur EXE: Im Dev-Modus EXE-Token unberuehrt lassen)
        if not is_dev_mode():
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
        
        Im Dev-Modus: Kein Auto-Login, EXE-Token bleibt unberuehrt.
        
        Returns:
            AuthState
        """
        if is_dev_mode():
            logger.debug("Dev-Modus: Auto-Login uebersprungen (EXE-Token wird nicht gelesen)")
            return AuthState(is_authenticated=False)
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
            merged = {**user_data, **verify_result}
            self._current_user = _build_user(merged)
            logger.info(f"Auto-Login erfolgreich: {self._current_user.username}")
            return AuthState(
                is_authenticated=True,
                user=self._current_user,
                token=token
            )
        else:
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
        if is_dev_mode():
            logger.debug("Dev-Modus: Re-Authentifizierung uebersprungen (EXE-Token wird nicht gelesen)")
            return False
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
            merged = {**user_data, **verify_result}
            self._current_user = _build_user(merged)
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
                    'id': response.get('user_id'),
                    'username': response.get('username'),
                    'account_type': response.get('account_type', 'user'),
                    'update_channel': response.get('update_channel', 'stable'),
                    'permissions': response.get('permissions', []),
                    'modules': response.get('modules', []),
                    'roles': response.get('roles', [])
                }
        except APIError:
            pass
        return None

    @staticmethod
    def _parse_modules(raw: list) -> List['UserModule']:
        result = []
        for m in raw:
            try:
                result.append(UserModule(
                    module_key=m.get('module_key', ''),
                    group_key=m.get('group_key', ''),
                    name=m.get('name', ''),
                    is_enabled=bool(m.get('is_enabled', False)),
                    access_level=m.get('access_level', 'user')
                ))
            except Exception:
                continue
        return result

    @staticmethod
    def _parse_roles(raw: list) -> List['UserRole']:
        result = []
        for r in raw:
            try:
                result.append(UserRole(
                    role_id=int(r.get('role_id', 0)),
                    role_key=r.get('role_key', ''),
                    module_key=r.get('module_key', '')
                ))
            except Exception:
                continue
        return result

    def _save_token(self, token: str, user_data: Dict) -> None:
        """
        SV-005 Fix: Speichert Token lokal mit OS-Schutz.
        Nutzt keyring (Windows Credential Manager/DPAPI) wenn verfuegbar,
        sonst Datei mit restriktiven Permissions.
        Im Dev-Modus: Kein Speichern, EXE-Token bleibt unberuehrt.
        """
        if is_dev_mode():
            logger.debug("Dev-Modus: Token wird nicht gespeichert (EXE-Token bleibt unberuehrt)")
            return
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
        Im Dev-Modus: Kein Lesen, EXE-Token bleibt unberuehrt.
        """
        if is_dev_mode():
            return None
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
        Im Dev-Modus: Kein Loeschen, EXE-Token bleibt unberuehrt.
        """
        if is_dev_mode():
            return
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
