"""
ATLAS API - Support & Feedback

API-Client fuer das Enterprise Support-System.
Sammelt System-Info automatisch und versendet Feedback inkl. Screenshot und Logs.
"""

import json
import logging
import os
import platform
from typing import Dict, List, Optional

from .client import APIClient, APIError

logger = logging.getLogger(__name__)


def collect_system_info() -> Dict:
    """
    Sammelt System-Informationen fuer Bug-Reports.
    Nicht-blockierend: fehlende Werte werden mit Defaults befuellt.
    """
    info: Dict = {
        "os": platform.system(),
        "os_version": platform.version(),
        "os_release": platform.release(),
        "architecture": platform.machine(),
        "python_version": platform.python_version(),
    }

    try:
        import psutil
        mem = psutil.virtual_memory()
        info["ram_total_gb"] = round(mem.total / (1024 ** 3), 2)
        info["ram_available_gb"] = round(mem.available / (1024 ** 3), 2)
        info["cpu_count"] = psutil.cpu_count(logical=True)
        info["cpu_physical"] = psutil.cpu_count(logical=False)
    except ImportError:
        info["ram_total_gb"] = None
        info["cpu_count"] = os.cpu_count()
    except Exception as e:
        logger.debug(f"psutil-Fehler: {e}")
        info["cpu_count"] = os.cpu_count()

    try:
        from main import APP_VERSION
        info["client_version"] = APP_VERSION
    except ImportError:
        info["client_version"] = "unknown"

    return info


def get_client_version() -> str:
    try:
        from main import APP_VERSION
        return APP_VERSION
    except ImportError:
        return "unknown"


def get_log_file_paths() -> Dict[str, str]:
    """
    Ermittelt die Pfade zu den relevanten Log-Dateien.
    """
    base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "logs")
    base = os.path.normpath(base)

    candidates = {
        "log_main": "bipro_gdv.log",
        "log_updater": "background_updater.log",
        "log_performance": "provision_performance.log",
    }

    result = {}
    for field, filename in candidates.items():
        path = os.path.join(base, filename)
        if os.path.isfile(path):
            result[field] = path

    return result


class SupportAPI:
    """
    API-Client fuer Support & Feedback.

    Verwendung:
        support = SupportAPI(client)
        result = support.submit_feedback(
            feedback_type='bug',
            priority='high',
            content='...',
            screenshot_path='/tmp/screenshot.png',
            include_logs=True
        )
    """

    def __init__(self, client: APIClient):
        self.client = client

    def submit_feedback(
        self,
        feedback_type: str,
        priority: str,
        content: str,
        subject: str = "",
        reproduction_steps: str = "",
        screenshot_path: Optional[str] = None,
        include_logs: bool = False,
    ) -> Dict:
        """
        Feedback an das Backend senden (multipart).

        Args:
            feedback_type: 'feedback', 'feature', 'bug'
            priority: 'low', 'medium', 'high'
            content: Beschreibung (Pflicht)
            subject: Betreff (optional)
            reproduction_steps: Reproduktionsschritte (nur bug)
            screenshot_path: Pfad zum Screenshot (optional)
            include_logs: Log-Dateien mitsenden (nur bei bug)

        Returns:
            Dict mit Backend-Response (id, feedback_type, ...)
        """
        sys_info = collect_system_info()
        version = get_client_version()
        os_info = f"{platform.system()} {platform.release()}"

        fields = {
            "feedback_type": feedback_type,
            "priority": priority,
            "content": content,
            "client_version": version,
            "os_info": os_info,
            "system_info": json.dumps(sys_info),
            "include_logs": "1" if include_logs else "0",
        }

        if subject:
            fields["subject"] = subject
        if reproduction_steps and feedback_type == "bug":
            fields["reproduction_steps"] = reproduction_steps

        files: Dict[str, str] = {}

        if screenshot_path and os.path.isfile(screenshot_path):
            files["screenshot"] = screenshot_path

        if include_logs and feedback_type == "bug":
            log_paths = get_log_file_paths()
            files.update(log_paths)

        try:
            response = self.client.upload_multipart(
                "/support/feedback",
                fields=fields,
                files=files,
                timeout=60,
            )
            if response.get("success"):
                logger.info(f"Feedback eingereicht: ID {response.get('data', {}).get('id')}")
            return response
        except APIError as e:
            logger.error(f"Fehler beim Feedback-Submit: {e}")
            raise

    def get_all_feedback(
        self,
        feedback_type: Optional[str] = None,
        priority: Optional[str] = None,
        status: Optional[str] = None,
        page: int = 1,
        per_page: int = 50,
    ) -> Dict:
        """
        Alle Feedbacks abrufen (nur Super-Admin).
        """
        params: Dict = {"page": page, "per_page": per_page}
        if feedback_type:
            params["type"] = feedback_type
        if priority:
            params["priority"] = priority
        if status:
            params["status"] = status

        try:
            return self.client.get("/support/feedback", params=params)
        except APIError as e:
            logger.error(f"Fehler beim Laden der Feedbacks: {e}")
            raise

    def get_feedback_detail(self, feedback_id: int) -> Dict:
        """
        Einzelnes Feedback mit allen Details abrufen (Super-Admin).
        """
        try:
            return self.client.get(f"/support/feedback/{feedback_id}")
        except APIError as e:
            logger.error(f"Fehler beim Laden von Feedback #{feedback_id}: {e}")
            raise

    def update_feedback(
        self,
        feedback_id: int,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        admin_notes: Optional[str] = None,
    ) -> Dict:
        """
        Feedback aktualisieren (Status, Prioritaet, Notizen).
        """
        data: Dict = {}
        if status:
            data["status"] = status
        if priority:
            data["priority"] = priority
        if admin_notes is not None:
            data["admin_notes"] = admin_notes

        try:
            return self.client.patch(f"/support/feedback/{feedback_id}", json_data=data)
        except APIError as e:
            logger.error(f"Fehler beim Update von Feedback #{feedback_id}: {e}")
            raise

    def get_screenshot(self, feedback_id: int) -> bytes:
        """
        Screenshot als Bilddaten herunterladen (Super-Admin).
        """
        try:
            return self.client.get_binary(f"/support/feedback/{feedback_id}/screenshot")
        except APIError as e:
            logger.error(f"Fehler beim Screenshot-Download #{feedback_id}: {e}")
            raise

    def get_logs_zip(self, feedback_id: int, target_path: str) -> str:
        """
        Log-Archiv herunterladen (Super-Admin).
        """
        try:
            return self.client.download_file(
                f"/support/feedback/{feedback_id}/logs",
                target_path
            )
        except APIError as e:
            logger.error(f"Fehler beim Logs-Download #{feedback_id}: {e}")
            raise

    def delete_feedback(self, feedback_id: int) -> bool:
        """
        Feedback loeschen (Super-Admin).
        """
        try:
            response = self.client.delete(f"/support/feedback/{feedback_id}")
            return response.get("success", False)
        except APIError as e:
            logger.error(f"Fehler beim Loeschen von Feedback #{feedback_id}: {e}")
            raise
