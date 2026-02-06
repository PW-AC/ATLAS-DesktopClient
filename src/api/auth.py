"""
BiPro API - Authentifizierung

Login, Logout, Token-Verwaltung.
"""

from typing import Optional, Dict, Any
from dataclasses import dataclass
import logging
import json
import os
from pathlib import Path

from .client import APIClient, APIError

logger = logging.getLogger(__name__)


@dataclass
class User:
    """Angemeldeter Benutzer"""
    id: int
    username: str
    email: Optional[str] = None


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
                
                # User-Objekt erstellen
                self._current_user = User(
                    id=user_data['id'],
                    username=user_data['username'],
                    email=user_data.get('email')
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
        
        # Token setzen und validieren
        self.client.set_token(token)
        
        if self.verify_token():
            self._current_user = User(
                id=user_data['id'],
                username=user_data['username'],
                email=user_data.get('email')
            )
            logger.info(f"Auto-Login erfolgreich: {self._current_user.username}")
            return AuthState(
                is_authenticated=True,
                user=self._current_user,
                token=token
            )
        else:
            # Token ungültig, aufräumen
            self.client.clear_token()
            self._delete_saved_token()
            logger.info("Auto-Login fehlgeschlagen: Token abgelaufen")
            return AuthState(is_authenticated=False)
    
    def re_authenticate(self) -> bool:
        """
        Versucht automatische Re-Authentifizierung.
        
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
        
        # Neuen Token setzen und pruefen
        self.client.set_token(token)
        
        if self.verify_token():
            self._current_user = User(
                id=user_data['id'],
                username=user_data['username'],
                email=user_data.get('email')
            )
            logger.info(f"Re-Authentifizierung erfolgreich: {self._current_user.username}")
            return True
        
        # Token ungueltig
        self.client.clear_token()
        logger.warning("Re-Authentifizierung fehlgeschlagen: Token ungueltig")
        return False
    
    def _save_token(self, token: str, user_data: Dict) -> None:
        """Speichert Token lokal."""
        try:
            data = {
                'token': token,
                'user': user_data
            }
            self.TOKEN_FILE.write_text(json.dumps(data))
            logger.debug("Token gespeichert")
        except Exception as e:
            logger.warning(f"Token speichern fehlgeschlagen: {e}")
    
    def _load_saved_token(self) -> Optional[Dict]:
        """Lädt gespeicherten Token."""
        try:
            if self.TOKEN_FILE.exists():
                return json.loads(self.TOKEN_FILE.read_text())
        except Exception as e:
            logger.warning(f"Token laden fehlgeschlagen: {e}")
        return None
    
    def _delete_saved_token(self) -> None:
        """Löscht gespeicherten Token."""
        try:
            if self.TOKEN_FILE.exists():
                self.TOKEN_FILE.unlink()
                logger.debug("Gespeicherter Token gelöscht")
        except Exception as e:
            logger.warning(f"Token löschen fehlgeschlagen: {e}")
