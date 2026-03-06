"""
ACENCIA ATLAS - Generische Modul-Admin-Shell

Tabs: Zugriff | Rollen | Konfiguration
Wird pro Modul instanziiert (module_key als Parameter).
"""

import logging
from typing import Optional, Dict, List, Callable

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QLabel, QPushButton,
)
from PySide6.QtCore import Signal, Qt

from api.client import APIClient
from api.auth import AuthAPI
from api.admin_modules import AdminModulesAPI
from i18n import de as texts
from ui.styles.tokens import (
    PRIMARY_900, PRIMARY_500, PRIMARY_0, ACCENT_500,
    FONT_HEADLINE, FONT_BODY,
    FONT_SIZE_H2, FONT_SIZE_BODY,
)

logger = logging.getLogger(__name__)


class ModuleAdminShell(QWidget):
    """Generische Modul-Verwaltung mit Tabs fuer Zugriff, Rollen und Konfiguration."""

    back_requested = Signal()

    def __init__(self, module_key: str, module_name: str,
                 api_client: APIClient, auth_api: AuthAPI,
                 config_panels: Optional[List] = None,
                 parent=None):
        super().__init__(parent)
        self._module_key = module_key
        self._module_name = module_name
        self._api_client = api_client
        self._auth_api = auth_api
        self._modules_api = AdminModulesAPI(api_client)
        self._config_panel_factories = config_panels or []

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QHBoxLayout()
        header.setContentsMargins(24, 16, 24, 8)

        back_btn = QPushButton(f"\u2190  {texts.DASHBOARD_BACK}")
        back_btn.setCursor(Qt.PointingHandCursor)
        back_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: none;
                font-family: {FONT_BODY}; font-size: {FONT_SIZE_BODY};
                color: {ACCENT_500}; font-weight: 600; padding: 8px 12px;
            }}
            QPushButton:hover {{ text-decoration: underline; }}
        """)
        back_btn.clicked.connect(self.back_requested.emit)
        header.addWidget(back_btn)

        title = QLabel(texts.MODULE_ADMIN_TITLE.format(module=self._module_name))
        title.setStyleSheet(f"""
            font-family: {FONT_HEADLINE}; font-size: {FONT_SIZE_H2};
            font-weight: 700; color: {PRIMARY_900}; padding: 8px 0;
        """)
        header.addWidget(title)
        header.addStretch()

        layout.addLayout(header)

        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(f"""
            QTabWidget::pane {{ border: none; background: {PRIMARY_0}; }}
            QTabBar::tab {{
                padding: 10px 24px;
                font-family: {FONT_BODY}; font-size: {FONT_SIZE_BODY};
                color: {PRIMARY_500}; border: none;
                border-bottom: 2px solid transparent;
            }}
            QTabBar::tab:selected {{
                color: {PRIMARY_900}; font-weight: 600;
                border-bottom: 2px solid {ACCENT_500};
            }}
        """)

        from ui.module_admin.access_panel import ModuleAccessPanel
        self._access_panel = ModuleAccessPanel(
            self._module_key, self._api_client, self._auth_api, self._modules_api
        )
        self._tabs.addTab(self._access_panel, texts.MODULE_ADMIN_TAB_ACCESS)

        from ui.module_admin.roles_panel import ModuleRolesPanel
        self._roles_panel = ModuleRolesPanel(
            self._module_key, self._api_client, self._modules_api
        )
        self._tabs.addTab(self._roles_panel, texts.MODULE_ADMIN_TAB_ROLES)

        if self._config_panel_factories:
            from ui.module_admin.config_panel import ModuleConfigPanel
            self._config_panel = ModuleConfigPanel(
                self._module_key, self._api_client, self._auth_api,
                self._config_panel_factories
            )
            self._tabs.addTab(self._config_panel, texts.MODULE_ADMIN_TAB_CONFIG)

        self._tabs.currentChanged.connect(self._on_tab_changed)
        layout.addWidget(self._tabs)

    def _on_tab_changed(self, index: int):
        w = self._tabs.widget(index)
        if hasattr(w, 'load_data'):
            w.load_data()

    def load_data(self):
        idx = self._tabs.currentIndex()
        w = self._tabs.widget(idx)
        if hasattr(w, 'load_data'):
            w.load_data()
