"""
BiPro API - Dokumenten-Regeln Einstellungen

Konfigurierbare Aktionen fuer Datei-Duplikate, Inhaltsduplikate,
teilweise leere PDFs und komplett leere Dateien.
"""

from dataclasses import dataclass
from typing import Optional, Dict
import logging

from .client import APIClient, APIError

logger = logging.getLogger(__name__)


@dataclass
class DocumentRulesSettings:
    """Konfigurierbare Regeln fuer automatische Dokumentenbehandlung."""
    file_dup_action: str = 'none'
    file_dup_color: Optional[str] = None
    content_dup_action: str = 'none'
    content_dup_color: Optional[str] = None
    partial_empty_action: str = 'none'
    partial_empty_color: Optional[str] = None
    full_empty_action: str = 'none'
    full_empty_color: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict) -> 'DocumentRulesSettings':
        return cls(
            file_dup_action=data.get('file_dup_action', 'none'),
            file_dup_color=data.get('file_dup_color'),
            content_dup_action=data.get('content_dup_action', 'none'),
            content_dup_color=data.get('content_dup_color'),
            partial_empty_action=data.get('partial_empty_action', 'none'),
            partial_empty_color=data.get('partial_empty_color'),
            full_empty_action=data.get('full_empty_action', 'none'),
            full_empty_color=data.get('full_empty_color'),
        )

    def has_any_rule(self) -> bool:
        """Prueft ob mindestens eine Regel aktiv ist (nicht 'none')."""
        return any([
            self.file_dup_action != 'none',
            self.content_dup_action != 'none',
            self.partial_empty_action != 'none',
            self.full_empty_action != 'none',
        ])

    def to_dict(self) -> Dict:
        return {
            'file_dup_action': self.file_dup_action,
            'file_dup_color': self.file_dup_color,
            'content_dup_action': self.content_dup_action,
            'content_dup_color': self.content_dup_color,
            'partial_empty_action': self.partial_empty_action,
            'partial_empty_color': self.partial_empty_color,
            'full_empty_action': self.full_empty_action,
            'full_empty_color': self.full_empty_color,
        }


class DocumentRulesAPI:
    """API-Client fuer Dokumenten-Regeln Einstellungen."""

    def __init__(self, client: APIClient):
        self.client = client

    def get_rules(self) -> DocumentRulesSettings:
        """Aktive Dokumenten-Regeln laden."""
        try:
            response = self.client.get('/document-rules')
            if response.get('success'):
                return DocumentRulesSettings.from_dict(
                    response['data'].get('settings', {}))
        except APIError as e:
            logger.error(f"Fehler beim Laden der Dokumenten-Regeln: {e}")
        return DocumentRulesSettings()

    def save_rules(self, settings: DocumentRulesSettings) -> bool:
        """Dokumenten-Regeln speichern (Admin-only)."""
        try:
            response = self.client.put(
                '/admin/document-rules',
                json_data=settings.to_dict()
            )
            if response.get('success'):
                logger.info("Dokumenten-Regeln gespeichert")
                return True
        except APIError as e:
            logger.error(f"Fehler beim Speichern der Dokumenten-Regeln: {e}")
        return False
