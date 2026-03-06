"""
ACENCIA ATLAS - Internationalisierung

Unterstuetzte Sprachen: Deutsch (de), English (en), Russkij (ru).

Mechanismus:
  Das Modul `de` dient als aktiver Textkatalog. Bei Sprachwechsel werden
  alle Attribute von `de` mit den Werten der Zielsprache ueberschrieben.
  Da saemtlicher Code `from i18n import de as texts` nutzt und Attribute
  erst zur Laufzeit aufloest, wirkt der Wechsel sofort fuer neu erstellte
  UI-Elemente.
"""

import importlib

from . import de

AVAILABLE_LANGUAGES = {
    'de': 'Deutsch',
    'en': 'English',
    'ru': '\u0420\u0443\u0441\u0441\u043a\u0438\u0439',
}

_current_lang = 'de'
_de_originals: dict = {}


def _backup_de():
    """Sichert die originalen deutschen Texte (einmalig beim Import)."""
    global _de_originals
    if not _de_originals:
        _de_originals = {
            k: v for k, v in vars(de).items() if not k.startswith('_')
        }


_backup_de()


def _apply_language(lang_code: str):
    """Patcht das de-Modul mit den Texten der Zielsprache."""
    global _current_lang

    for k, v in _de_originals.items():
        setattr(de, k, v)

    if lang_code == 'de':
        _current_lang = 'de'
        return

    try:
        lang_module = importlib.import_module(f'.{lang_code}', package='i18n')
    except ImportError:
        _current_lang = 'de'
        return

    for attr in dir(lang_module):
        if not attr.startswith('_'):
            setattr(de, attr, getattr(lang_module, attr))

    _current_lang = lang_code


def set_language(lang_code: str):
    """Setzt die aktive Sprache und persistiert die Wahl."""
    from PySide6.QtCore import QSettings
    if lang_code not in AVAILABLE_LANGUAGES:
        lang_code = 'de'
    QSettings("ACENCIA GmbH", "ACENCIA ATLAS").setValue(
        "appearance/language", lang_code,
    )
    _apply_language(lang_code)


def get_language() -> str:
    """Gibt den aktuellen Sprachcode zurueck."""
    return _current_lang


def _init_language():
    """Laedt die gespeicherte Sprache beim ersten Import."""
    try:
        from PySide6.QtCore import QSettings
        lang = QSettings(
            "ACENCIA GmbH", "ACENCIA ATLAS",
        ).value("appearance/language", "de")
        if lang and lang != 'de' and lang in AVAILABLE_LANGUAGES:
            _apply_language(lang)
    except Exception:
        pass


_init_language()
