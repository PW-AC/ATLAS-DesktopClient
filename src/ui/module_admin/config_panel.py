"""
ACENCIA ATLAS - Modul-Admin: Konfiguration-Tab

Hostet modulspezifische Config-Panels (migriert aus admin_shell.py).
"""

import logging
from typing import List, Callable, Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget, QPushButton,
    QLabel, QFrame,
)
from PySide6.QtCore import Qt

from api.client import APIClient
from api.auth import AuthAPI
from i18n import de as texts
from ui.styles.tokens import (
    PRIMARY_900, PRIMARY_500, PRIMARY_0, ACCENT_500,
    FONT_BODY, FONT_SIZE_BODY, FONT_SIZE_CAPTION,
    SIDEBAR_BG, SIDEBAR_TEXT, SIDEBAR_HOVER,
)

logger = logging.getLogger(__name__)


class _ConfigNavButton(QPushButton):
    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        self.setText(f"   ›  {text}")
        self.setCheckable(True)
        self.setMinimumHeight(36)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent; border: none;
                border-left: 2px solid transparent;
                padding: 6px 16px; text-align: left;
                font-family: {FONT_BODY}; font-size: {FONT_SIZE_BODY};
                color: {PRIMARY_500};
            }}
            QPushButton:hover {{ background-color: rgba(136, 169, 195, 0.08); color: {PRIMARY_900}; }}
            QPushButton:checked {{
                background-color: rgba(136, 169, 195, 0.08);
                border-left: 2px solid {ACCENT_500}; color: {PRIMARY_900}; font-weight: 500;
            }}
        """)


class ModuleConfigPanel(QWidget):
    """Konfiguration-Tab: Sidebar-Navigation + Sub-Panels."""

    def __init__(self, module_key: str, api_client: APIClient, auth_api: AuthAPI,
                 panel_factories: List, parent=None):
        """
        panel_factories: List von (label: str, factory: Callable) Tupeln.
        factory erhaelt (api_client, toast_manager) und gibt QWidget zurueck.
        """
        super().__init__(parent)
        self._module_key = module_key
        self._api_client = api_client
        self._auth_api = auth_api
        self._factories = panel_factories
        self._panels: List[Optional[QWidget]] = [None] * len(panel_factories)
        self._nav_buttons: List[_ConfigNavButton] = []
        self._setup_ui()

    def _setup_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        nav_frame = QFrame()
        nav_frame.setFixedWidth(220)
        nav_frame.setStyleSheet(f"background-color: {PRIMARY_0}; border-right: 1px solid rgba(0,0,0,0.06);")
        nav_layout = QVBoxLayout(nav_frame)
        nav_layout.setContentsMargins(0, 8, 0, 8)
        nav_layout.setSpacing(2)

        for i, (label, _factory) in enumerate(self._factories):
            btn = _ConfigNavButton(label)
            btn.clicked.connect(lambda checked, idx=i: self._navigate_to(idx))
            nav_layout.addWidget(btn)
            self._nav_buttons.append(btn)

        nav_layout.addStretch()
        root.addWidget(nav_frame)

        self._stack = QStackedWidget()
        for _ in self._factories:
            self._stack.addWidget(QWidget())
        root.addWidget(self._stack)

        if self._nav_buttons:
            self._navigate_to(0)

    def _navigate_to(self, index: int):
        for i, btn in enumerate(self._nav_buttons):
            btn.setChecked(i == index)

        if self._panels[index] is None:
            _label, factory = self._factories[index]
            tm = getattr(self, '_toast_manager', None)
            try:
                panel = factory(self._api_client, tm)
                panel._toast_manager = tm
            except Exception:
                logger.exception(f"Config-Panel {index} konnte nicht erstellt werden")
                panel = QWidget()
            self._panels[index] = panel
            old = self._stack.widget(index)
            self._stack.removeWidget(old)
            old.deleteLater()
            self._stack.insertWidget(index, panel)

        self._stack.setCurrentIndex(index)
        panel = self._panels[index]
        if panel and hasattr(panel, 'load_data'):
            panel.load_data()

    def load_data(self):
        idx = self._stack.currentIndex()
        panel = self._panels[idx] if 0 <= idx < len(self._panels) else None
        if panel and hasattr(panel, 'load_data'):
            panel.load_data()
