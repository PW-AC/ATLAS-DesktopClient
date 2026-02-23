"""
BiPro API - Basis HTTP Client

Zentrale Klasse für alle API-Anfragen.
"""

import os
import requests
import time
import threading
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

# Retry-Konfiguration
MAX_RETRIES = 3
RETRY_STATUS_CODES = {429, 500, 502, 503, 504}
RETRY_BACKOFF_FACTOR = 1.0


@dataclass
class APIConfig:
    """API-Konfiguration"""
    base_url: str = "https://acencia.info/api"
    timeout: int = 30
    verify_ssl: bool = True


class APIError(Exception):
    """Fehler bei API-Anfragen"""
    def __init__(self, message: str, status_code: int = 0, details: Dict = None):
        super().__init__(message)
        self.status_code = status_code
        self.details = details or {}


class APIClient:
    """
    Basis-Client für API-Kommunikation.
    
    Verwendung:
        client = APIClient()
        client.set_token("jwt_token_here")
        response = client.get("/documents")
    """
    
    def __init__(self, config: APIConfig = None):
        self.config = config or APIConfig()
        self._token: Optional[str] = None
        self._session = requests.Session()
        self._auth_refresh_callback: Optional[Callable[[], bool]] = None
        self._forced_logout_callback: Optional[Callable[[str], None]] = None
        self._auth_refresh_lock = threading.Lock()
        
    @property
    def base_url(self) -> str:
        return self.config.base_url.rstrip('/')
    
    def set_token(self, token: str) -> None:
        """Setzt den JWT-Token für authentifizierte Anfragen."""
        self._token = token
        logger.debug("Token gesetzt")
        
    def clear_token(self) -> None:
        """Entfernt den Token (Logout)."""
        self._token = None
        logger.debug("Token entfernt")
        
    def is_authenticated(self) -> bool:
        """Prüft ob ein Token gesetzt ist."""
        return self._token is not None
    
    def _get_headers(self) -> Dict[str, str]:
        """Erstellt die HTTP-Header für Anfragen."""
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }
        if self._token:
            headers['Authorization'] = f'Bearer {self._token}'
        return headers
    
    def set_auth_refresh_callback(self, callback: Callable[[], bool]) -> None:
        """
        Registriert einen Callback fuer automatischen Token-Refresh bei 401.
        
        Args:
            callback: Funktion die True zurueckgibt wenn Token erfolgreich erneuert
        """
        self._auth_refresh_callback = callback
    
    def set_forced_logout_callback(self, callback: Callable[[str], None]) -> None:
        """
        Registriert einen Callback fuer erzwungenen Logout.
        
        Wird aufgerufen wenn eine Session server-seitig ungueltig wurde
        (Session beendet, User gesperrt, User deaktiviert) und kein
        Token-Refresh moeglich ist.
        
        Args:
            callback: Funktion mit Grund-String als Parameter
        """
        self._forced_logout_callback = callback
    
    def _try_auth_refresh(self, error_message: str = '') -> bool:
        """
        Versucht Token-Refresh (thread-safe, max 1 gleichzeitig).
        
        Verwendet non-blocking Lock um Deadlocks zu verhindern:
        - Wenn der Lock bereits gehalten wird (z.B. durch rekursiven Aufruf
          aus re_authenticate() -> verify_token() -> get() -> 401), wird
          sofort False zurueckgegeben statt zu blockieren.
        - threading.Lock() ist NICHT reentrant, daher wuerde 'with self._lock'
          bei Rekursion den gleichen Thread blockieren (Deadlock).
        
        Wenn der Refresh fehlschlaegt, wird der forced_logout_callback
        aufgerufen (Session ungueltig).
        """
        if not self._auth_refresh_callback:
            self._trigger_forced_logout(error_message)
            return False
        
        # Non-blocking acquire verhindert Deadlock bei Rekursion
        acquired = self._auth_refresh_lock.acquire(blocking=False)
        if not acquired:
            return False  # Lock gehalten (Rekursion oder paralleler Refresh)
        
        try:
            success = self._auth_refresh_callback()
            if not success:
                self._trigger_forced_logout(error_message)
            return success
        except Exception:
            self._trigger_forced_logout(error_message)
            return False
        finally:
            self._auth_refresh_lock.release()
    
    def _trigger_forced_logout(self, reason: str = '') -> None:
        """
        Loest einen erzwungenen Logout aus.
        
        Wird aufgerufen wenn die Session server-seitig ungueltig ist
        und kein Re-Auth moeglich war.
        """
        if self._forced_logout_callback:
            logger.warning(f"Erzwungener Logout: {reason}")
            self.clear_token()
            try:
                self._forced_logout_callback(reason)
            except Exception as e:
                logger.error(f"Fehler im Forced-Logout-Callback: {e}")
    
    def _handle_response(self, response: requests.Response) -> Dict[str, Any]:
        """Verarbeitet die API-Response."""
        try:
            data = response.json()
        except ValueError:
            if response.status_code >= 400:
                raise APIError(
                    f"Server-Fehler: {response.status_code}",
                    status_code=response.status_code
                )
            return {'raw': response.text}
        
        # Fehler prüfen
        if response.status_code >= 400:
            error_msg = data.get('error', f'HTTP {response.status_code}')
            raise APIError(
                error_msg,
                status_code=response.status_code,
                details=data.get('details', {})
            )
        
        return data
    
    def _request_with_retry(self, method: str, url: str, max_retries: int = None, **kwargs) -> requests.Response:
        """
        Fuehrt einen HTTP-Request mit Retry-Logik aus.
        
        Retries bei: RETRY_STATUS_CODES + Timeout + ConnectionError
        Kein Retry bei: 401 (wird von 401-Retry-Logik behandelt), andere 4xx
        
        Args:
            method: HTTP-Methode ('GET', 'POST', 'PUT', 'DELETE')
            url: Vollstaendige URL
            max_retries: Maximale Anzahl Versuche (None = globaler Default)
            **kwargs: Werden an requests.Session.request() weitergegeben
            
        Returns:
            requests.Response
            
        Raises:
            requests.RequestException nach allen fehlgeschlagenen Retries
        """
        retries = max_retries if max_retries is not None else MAX_RETRIES
        last_error = None
        
        for attempt in range(retries):
            try:
                response = self._session.request(method, url, **kwargs)
                
                # Retryable Status Codes
                if response.status_code in RETRY_STATUS_CODES and attempt < retries - 1:
                    wait_time = RETRY_BACKOFF_FACTOR * (2 ** attempt)
                    logger.warning(
                        f"{method} {url} HTTP {response.status_code}, "
                        f"Retry {attempt + 1}/{retries} in {wait_time:.1f}s"
                    )
                    time.sleep(wait_time)
                    continue
                
                return response
                
            except requests.Timeout as e:
                last_error = e
                if attempt < retries - 1:
                    wait_time = RETRY_BACKOFF_FACTOR * (2 ** attempt)
                    logger.warning(
                        f"{method} {url} Timeout, "
                        f"Retry {attempt + 1}/{retries} in {wait_time:.1f}s"
                    )
                    time.sleep(wait_time)
                else:
                    raise
                    
            except requests.ConnectionError as e:
                last_error = e
                if attempt < retries - 1:
                    wait_time = RETRY_BACKOFF_FACTOR * (2 ** attempt)
                    logger.warning(
                        f"{method} {url} Verbindungsfehler, "
                        f"Retry {attempt + 1}/{retries} in {wait_time:.1f}s"
                    )
                    time.sleep(wait_time)
                else:
                    raise
        
        # Sollte nicht erreicht werden, aber Sicherheit
        raise requests.RequestException(f"Request fehlgeschlagen nach {retries} Versuchen: {last_error}")
    
    def get(self, endpoint: str, params: Dict = None) -> Dict[str, Any]:
        """GET-Anfrage an die API."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        logger.debug(f"GET {url}")
        
        try:
            response = self._request_with_retry(
                'GET', url,
                headers=self._get_headers(),
                params=params,
                timeout=self.config.timeout,
                verify=self.config.verify_ssl
            )
            return self._handle_response(response)
        except APIError as e:
            # Bei 401: Token-Refresh versuchen und Retry
            if e.status_code == 401 and self._try_auth_refresh(str(e)):
                logger.info(f"Token erneuert, wiederhole GET {endpoint}")
                try:
                    response = self._request_with_retry(
                        'GET', url,
                        headers=self._get_headers(),
                        params=params,
                        timeout=self.config.timeout,
                        verify=self.config.verify_ssl
                    )
                    return self._handle_response(response)
                except APIError:
                    raise  # Retry auch fehlgeschlagen
            raise  # Kein Refresh moeglich oder kein 401
        except requests.RequestException as e:
            logger.error(f"Netzwerkfehler: {e}")
            raise APIError(f"Netzwerkfehler: {e}")
    
    def post(self, endpoint: str, data: Dict = None, json_data: Dict = None,
             timeout: int = None, retries: int = None) -> Dict[str, Any]:
        """POST-Anfrage an die API.
        
        Args:
            retries: Max Versuche (1 = kein Retry). None = globaler Default.
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        logger.debug(f"POST {url}")
        req_timeout = timeout or self.config.timeout
        
        try:
            response = self._request_with_retry(
                'POST', url,
                max_retries=retries,
                headers=self._get_headers(),
                data=data,
                json=json_data,
                timeout=req_timeout,
                verify=self.config.verify_ssl
            )
            return self._handle_response(response)
        except APIError as e:
            # Bei 401: Token-Refresh versuchen und Retry
            if e.status_code == 401 and self._try_auth_refresh(str(e)):
                logger.info(f"Token erneuert, wiederhole POST {endpoint}")
                try:
                    response = self._request_with_retry(
                        'POST', url,
                        max_retries=retries,
                        headers=self._get_headers(),
                        data=data,
                        json=json_data,
                        timeout=req_timeout,
                        verify=self.config.verify_ssl
                    )
                    return self._handle_response(response)
                except APIError:
                    raise  # Retry auch fehlgeschlagen
            raise  # Kein Refresh moeglich oder kein 401
        except requests.RequestException as e:
            logger.error(f"Netzwerkfehler: {e}")
            raise APIError(f"Netzwerkfehler: {e}")
    
    def put(self, endpoint: str, json_data: Dict = None) -> Dict[str, Any]:
        """PUT-Anfrage an die API."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        logger.debug(f"PUT {url}")
        
        try:
            response = self._request_with_retry(
                'PUT', url,
                headers=self._get_headers(),
                json=json_data,
                timeout=self.config.timeout,
                verify=self.config.verify_ssl
            )
            return self._handle_response(response)
        except APIError as e:
            # Bei 401: Token-Refresh versuchen und Retry
            if e.status_code == 401 and self._try_auth_refresh(str(e)):
                logger.info(f"Token erneuert, wiederhole PUT {endpoint}")
                try:
                    response = self._request_with_retry(
                        'PUT', url,
                        headers=self._get_headers(),
                        json=json_data,
                        timeout=self.config.timeout,
                        verify=self.config.verify_ssl
                    )
                    return self._handle_response(response)
                except APIError:
                    raise  # Retry auch fehlgeschlagen
            raise  # Kein Refresh moeglich oder kein 401
        except requests.RequestException as e:
            logger.error(f"Netzwerkfehler: {e}")
            raise APIError(f"Netzwerkfehler: {e}")
    
    def delete(self, endpoint: str) -> Dict[str, Any]:
        """DELETE-Anfrage an die API."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        logger.debug(f"DELETE {url}")
        
        try:
            response = self._request_with_retry(
                'DELETE', url,
                headers=self._get_headers(),
                timeout=self.config.timeout,
                verify=self.config.verify_ssl
            )
            return self._handle_response(response)
        except APIError as e:
            # Bei 401: Token-Refresh versuchen und Retry
            if e.status_code == 401 and self._try_auth_refresh(str(e)):
                logger.info(f"Token erneuert, wiederhole DELETE {endpoint}")
                try:
                    response = self._request_with_retry(
                        'DELETE', url,
                        headers=self._get_headers(),
                        timeout=self.config.timeout,
                        verify=self.config.verify_ssl
                    )
                    return self._handle_response(response)
                except APIError:
                    raise  # Retry auch fehlgeschlagen
            raise  # Kein Refresh moeglich oder kein 401
        except requests.RequestException as e:
            logger.error(f"Netzwerkfehler: {e}")
            raise APIError(f"Netzwerkfehler: {e}")
    
    def upload_file(self, endpoint: str, file_path: str, 
                    additional_data: Dict = None) -> Dict[str, Any]:
        """Datei an die API hochladen."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        logger.debug(f"UPLOAD {url} <- {file_path}")
        
        headers = {}
        if self._token:
            headers['Authorization'] = f'Bearer {self._token}'
        
        try:
            # Datei einmal in Speicher lesen, damit Retries funktionieren
            filename = os.path.basename(file_path)
            with open(file_path, 'rb') as f:
                file_content = f.read()
            
            response = self._request_with_retry(
                'POST', url,
                headers=headers,
                files={'file': (filename, file_content)},
                data=additional_data or {},
                timeout=self.config.timeout * 2,  # Laengerer Timeout fuer Uploads
                verify=self.config.verify_ssl
            )
            return self._handle_response(response)
        except APIError as e:
            # Bei 401: Token-Refresh versuchen und Retry
            if e.status_code == 401 and self._try_auth_refresh(str(e)):
                logger.info(f"Token erneuert, wiederhole UPLOAD {endpoint}")
                headers = {}
                if self._token:
                    headers['Authorization'] = f'Bearer {self._token}'
                try:
                    response = self._request_with_retry(
                        'POST', url,
                        headers=headers,
                        files={'file': (filename, file_content)},
                        data=additional_data or {},
                        timeout=self.config.timeout * 2,
                        verify=self.config.verify_ssl
                    )
                    return self._handle_response(response)
                except APIError:
                    raise  # Retry auch fehlgeschlagen
            raise  # Kein Refresh moeglich oder kein 401
        except FileNotFoundError:
            raise APIError(f"Datei nicht gefunden: {file_path}")
        except requests.RequestException as e:
            logger.error(f"Upload-Fehler: {e}")
            raise APIError(f"Upload-Fehler: {e}")
    
    def download_file(self, endpoint: str, target_path: str, 
                       max_retries: int = MAX_RETRIES) -> str:
        """
        Datei von der API herunterladen mit Retry-Logik.
        
        Args:
            endpoint: API-Endpunkt
            target_path: Zielpfad fuer die Datei
            max_retries: Maximale Anzahl Versuche (veraltet, zentral konfiguriert)
            
        Returns:
            Pfad zur heruntergeladenen Datei
            
        Raises:
            APIError: Nach allen fehlgeschlagenen Versuchen
        """
        try:
            return self._download_file_inner(endpoint, target_path)
        except APIError as e:
            # Bei 401: Token-Refresh versuchen und Retry
            if e.status_code == 401 and self._try_auth_refresh(str(e)):
                logger.info(f"Token erneuert, wiederhole DOWNLOAD {endpoint}")
                try:
                    return self._download_file_inner(endpoint, target_path)
                except APIError:
                    raise  # Retry auch fehlgeschlagen
            raise  # Kein Refresh moeglich oder kein 401
    
    def _download_file_inner(self, endpoint: str, target_path: str) -> str:
        """Innere Download-Logik (ohne 401-Retry)."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        logger.debug(f"DOWNLOAD {url} -> {target_path}")
        
        headers = {}
        if self._token:
            headers['Authorization'] = f'Bearer {self._token}'
        
        try:
            response = self._request_with_retry(
                'GET', url,
                headers=headers,
                timeout=self.config.timeout * 3,  # Laengerer Timeout fuer Downloads
                verify=self.config.verify_ssl,
                stream=True
            )
            
            # 401 sofort als APIError werfen (wird von download_file behandelt)
            if response.status_code == 401:
                raise APIError(
                    f"Download fehlgeschlagen: {response.status_code}",
                    status_code=response.status_code
                )
            
            # Nicht-retryable Fehler (alles was _request_with_retry nicht retried hat)
            if response.status_code >= 400:
                raise APIError(
                    f"Download fehlgeschlagen: {response.status_code}",
                    status_code=response.status_code
                )
            
            # Erfolg - Datei schreiben
            bytes_written = 0
            with open(target_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        bytes_written += len(chunk)
            
            logger.debug(f"Download erfolgreich: {bytes_written} bytes -> {target_path}")
            return target_path
            
        except requests.RequestException as e:
            # Timeout/ConnectionError kommen hier an wenn alle Retries in
            # _request_with_retry erschoepft sind
            logger.error(f"Download-Fehler: {e}")
            raise APIError(f"Download-Fehler: {e}")
    
    def check_connection(self) -> bool:
        """Prüft ob die API erreichbar ist."""
        try:
            response = self.get("/")
            return response.get('status') == 'ok'
        except APIError:
            return False
