"""
Log-Kategorie-System fuer ATLAS Desktop Client.

Gruppiert alle ~125 Logger-Module in 5 thematische Kategorien.
Jede Kategorie kann per Config-Dict oder Umgebungsvariable
ATLAS_LOG_SILENT auf silent gestellt werden.

Der CategoryFilter wird NUR auf den Console-Handler angewendet --
das File-Log behaelt immer alle Meldungen.

Steuerung:
    1) Direkt hier: LOG_CATEGORIES[<name>]['enabled'] = False
    2) Umgebungsvariable (ueberschreibt Config):
       set ATLAS_LOG_SILENT=ui_log,parser_log
"""

import os
import logging

LOG_CATEGORIES: dict[str, dict] = {
    'ui_log': {
        'prefixes': ['ui.'],
        'enabled': False,
    },
    'backend_log': {
        'prefixes': ['api.', 'bipro.', 'workforce.api_client'],
        'enabled': False,
    },
    'logic_log': {
        'prefixes': [
            'services.', 'domain.', 'usecases.', 'infrastructure.',
            'presenters.', 'workforce.services.', 'workforce.providers.',
            'workforce.workers',
        ],
        'enabled': False,
    },
    'parser_log': {
        'prefixes': ['parser.'],
        'enabled': False,
    },
    'system_log': {
        'prefixes': ['main', 'config.', 'qt', 'background_updater', 'provision.performance'],
        'enabled': False,
    },
    'heartbeat_log': {
        'prefixes': ['heartbeat.'],
        'enabled': False,
    },
}


def _matches_prefix(logger_name: str, prefix: str) -> bool:
    """Prueft ob ein Logger-Name zu einem Prefix gehoert."""
    if prefix.endswith('.'):
        return logger_name.startswith(prefix) or logger_name == prefix.rstrip('.')
    return logger_name == prefix or logger_name.startswith(prefix + '.')


class CategoryFilter(logging.Filter):
    """Filtert LogRecords anhand deaktivierter Kategorien aus LOG_CATEGORIES."""

    def __init__(self, categories: dict[str, dict]):
        super().__init__()
        self._categories = categories

    def filter(self, record: logging.LogRecord) -> bool:
        name = record.name
        for cat_config in self._categories.values():
            if not cat_config['enabled']:
                for prefix in cat_config['prefixes']:
                    if _matches_prefix(name, prefix):
                        return False
        return True


def apply_env_overrides() -> None:
    """Liest ATLAS_LOG_SILENT und deaktiviert genannte Kategorien.

    Format: ATLAS_LOG_SILENT=ui_log,parser_log
    """
    silent_env = os.environ.get('ATLAS_LOG_SILENT', '').strip()
    if not silent_env:
        return
    for cat_name in silent_env.split(','):
        cat_name = cat_name.strip()
        if cat_name in LOG_CATEGORIES:
            LOG_CATEGORIES[cat_name]['enabled'] = False


def get_console_filter() -> CategoryFilter:
    """Gibt einen konfigurierten CategoryFilter zurueck.

    Wendet vorher Umgebungsvariablen-Overrides an.
    """
    apply_env_overrides()
    return CategoryFilter(LOG_CATEGORIES)


def get_status_summary() -> str:
    """Gibt eine einzeilige Zusammenfassung der Kategorie-Status zurueck."""
    parts = []
    for name, cfg in LOG_CATEGORIES.items():
        label = name.replace('_log', '').upper()
        status = 'ON' if cfg['enabled'] else 'SILENT'
        parts.append(f"{label}={status}")
    return ' | '.join(parts)
