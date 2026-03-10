"""
ACENCIA ATLAS - Dev-Modus Pubkey-Authentifizierung

Ermoeglicht automatischen Login als Admin im Dev-Modus (python run.py)
ohne Passwort-Eingabe. Nutzt Challenge-Response mit RSA-Signatur.

Geht ueber die Control Plane (wie normaler Login), damit bei
mehreren Universes der Benutzer gefragt wird, welches er verwenden moechte.

Setup:
  1. python setup_dev_auth.py
  2. Inhalt von atlas_dev.pub auf dem Server in config/dev_auth_keys.txt eintragen
"""

import base64
import logging
from pathlib import Path
from typing import Optional, Tuple, List

import requests as req

from api.client import APIClient, APIError
from api.auth import AuthAPI, AuthState, TenantInfo, _build_user
from config.runtime import is_dev_mode
from config.server_config import CONTROL_API_URL, API_VERIFY_SSL

logger = logging.getLogger(__name__)

DEFAULT_KEY_PATH = Path("dev_keys") / "atlas_dev.key"


def _get_key_path() -> Optional[Path]:
    candidates = [
        Path(__file__).resolve().parent.parent / DEFAULT_KEY_PATH,
        Path.cwd() / DEFAULT_KEY_PATH,
    ]
    for p in candidates:
        if p.exists() and p.is_file():
            return p
    return None


def _load_private_key(path: Path) -> Optional["object"]:
    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.backends import default_backend
        key_data = path.read_bytes()
        return serialization.load_pem_private_key(
            key_data, password=None, backend=default_backend()
        )
    except Exception as e:
        logger.debug(f"Dev-Auth: Schluessel konnte nicht geladen werden: {e}")
        return None


def _get_public_key_pem(private_key) -> str:
    from cryptography.hazmat.primitives import serialization
    pub = private_key.public_key()
    return pub.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode("ascii")


def _sign_challenge(private_key, challenge_b64: str) -> Optional[str]:
    try:
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding
        challenge = base64.b64decode(challenge_b64)
        signature = private_key.sign(challenge, padding.PKCS1v15(), hashes.SHA256())
        return base64.b64encode(signature).decode("ascii")
    except Exception as e:
        logger.debug(f"Dev-Auth: Signatur fehlgeschlagen: {e}")
        return None


def try_dev_login(api_client: APIClient, auth_api: AuthAPI) -> Optional[AuthState]:
    """
    Versucht Dev-Login per Pubkey ueber die Control Plane.

    Gibt ein AuthState zurueck:
    - is_authenticated=True + token: Direkt eingeloggt (1 Universe, auto-selected)
    - is_authenticated=False + tenants: Mehrere Universes, Benutzer muss waehlen
    - None: Dev-Auth nicht verfuegbar, Fallback auf normalen Login
    """
    if not is_dev_mode():
        return None

    key_path = _get_key_path()
    if not key_path:
        logger.debug("Dev-Auth: Kein Schluessel unter dev_keys/atlas_dev.key")
        return None

    private_key = _load_private_key(key_path)
    if not private_key:
        return None

    try:
        # 1. Challenge von Control Plane holen
        challenge_resp = req.get(
            f"{CONTROL_API_URL}/auth/dev-challenge",
            verify=API_VERIFY_SSL,
            timeout=10,
        )
        challenge_data = challenge_resp.json() if challenge_resp.ok else {}
        if not challenge_data.get("success"):
            logger.debug("Dev-Auth: Challenge-Endpoint nicht verfuegbar")
            return None

        cdata = challenge_data.get("data", {})
        challenge_id = cdata.get("challenge_id")
        challenge = cdata.get("challenge")
        if not challenge_id or not challenge:
            return None

        # 2. Challenge signieren
        signature = _sign_challenge(private_key, challenge)
        if not signature:
            return None

        public_key_pem = _get_public_key_pem(private_key)

        # 3. Dev-Login an Control Plane senden
        login_resp = req.post(
            f"{CONTROL_API_URL}/auth/dev-login",
            json={
                "challenge_id": challenge_id,
                "public_key": public_key_pem,
                "signature": signature,
            },
            verify=API_VERIFY_SSL,
            timeout=10,
        )
        login_data = login_resp.json() if login_resp.ok else {}
        if not login_data.get("success"):
            error_msg = login_data.get("error", f"HTTP {login_resp.status_code}")
            logger.debug(f"Dev-Auth Login fehlgeschlagen: {error_msg}")
            return None

        control_token = login_data.get("control_token")
        if not control_token:
            return None

        auth_api._control_token = control_token

        tenants = [
            TenantInfo(
                tenant_id=t["tenant_id"],
                tenant_key=t["tenant_key"],
                tenant_name=t["tenant_name"],
                role=t["role"],
                status=t["status"],
                schema_version=t.get("schema_version", 0),
            )
            for t in login_data.get("tenants", [])
        ]

        # Auto-Select: Genau 1 Universe, Server hat Tenant-JWT mitgegeben
        if "tenant_token" in login_data and login_data.get("selected_tenant"):
            token = login_data["tenant_token"]
            api_client.set_token(token)

            st = login_data["selected_tenant"]
            selected = TenantInfo(
                tenant_id=st["tenant_id"],
                tenant_key=st["tenant_key"],
                tenant_name=st["tenant_name"],
                role=st["role"],
                status="active",
                schema_version=st.get("schema_version", 0),
            )
            auth_api._active_tenant = selected

            user_info = auth_api._fetch_user_info()
            if user_info:
                auth_api._current_user = _build_user(user_info)
            else:
                auth_api._current_user = _build_user(login_data.get("user", {}))

            logger.info(f"Dev-Auth: Angemeldet als {auth_api._current_user.username} -> {selected.tenant_key}")
            return AuthState(
                is_authenticated=True,
                user=auth_api._current_user,
                token=token,
                tenants=tenants,
                selected_tenant=selected,
            )

        # Mehrere Universes: Benutzer muss waehlen
        logger.info(f"Dev-Auth: Identitaet bestaetigt, {len(tenants)} Universe(s) verfuegbar")
        return AuthState(
            is_authenticated=False,
            tenants=tenants,
        )

    except (req.ConnectionError, req.Timeout) as e:
        logger.debug(f"Dev-Auth: Control Plane nicht erreichbar: {e}")
        return None
    except Exception as e:
        logger.debug(f"Dev-Auth Fehler: {e}")
        return None


def generate_keypair() -> Tuple[Path, Path]:
    """
    Erzeugt ein neues RSA-Keypair fuer Dev-Auth.
    Gibt (path_private, path_public) zurueck.
    """
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.backends import default_backend

    key_dir = Path(__file__).resolve().parent.parent / "dev_keys"
    key_dir.mkdir(exist_ok=True)
    priv_path = key_dir / "atlas_dev.key"
    pub_path = key_dir / "atlas_dev.pub"

    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend(),
    )

    priv_path.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )

    pub = private_key.public_key()
    pub_path.write_bytes(
        pub.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )

    print(f"Keypair erstellt:")
    print(f"  Privat: {priv_path}")
    print(f"  Oeffentl.: {pub_path}")
    print(f"\nNaechster Schritt: Inhalt von {pub_path.name} in")
    print(f"  Local_dev_Backend/config/dev_auth_keys.txt eintragen.")
    return priv_path, pub_path
