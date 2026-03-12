"""
ACENCIA ATLAS - Admin-Shell (Sidebar + Panel-Wechsel mit Lazy Loading)

Vollbild-Layout mit eigener Sidebar-Navigation (11 Panels):

VERWALTUNG:
0. Nutzerverwaltung (CRUD)
1. Sessions (Einsicht + Kill)
2. Passwoerter (PDF/ZIP Passwort-Verwaltung)

MONITORING:
3. Aktivitaetslog (Filter + Pagination)
4. KI-Kosten (Verarbeitungshistorie + Kosten-Statistiken + Request-Details)
5. Releases (Auto-Update Verwaltung)

KOMMUNIKATION:
6. Mitteilungen (System + Admin-Mitteilungen verwalten)

SYSTEM:
7. Server-Gesundheit (Health-Check mit ~35 Einzel-Checks + Trend-Vergleich)
8. Migrationen (DB-Migrationen aus setup/ anzeigen + ausfuehren)

SUPPORT (Super-Admin):
9. Support & Feedback (Eingereichte Feedbacks, Feature-Wuensche, Bug-Reports)

SERVER (Super-Admin):
10. Server-Verwaltung (VPS-Steuerung)
"""

import logging
from typing import Optional, List, Dict

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFrame, QStackedWidget,
)
from PySide6.QtCore import Qt, Signal, QTimer

from api.client import APIClient
from api.auth import AuthAPI
from api.admin import AdminAPI
from api.releases import ReleasesAPI
from api.model_pricing import ModelPricingAPI
from i18n import de as texts

from ui.components.module_sidebar import ModuleSidebar
from ui.styles.tokens import (
    PRIMARY_900, PRIMARY_500, PRIMARY_0,
    ACCENT_500,
    SIDEBAR_BG, SIDEBAR_TEXT, SIDEBAR_HOVER, SIDEBAR_WIDTH_INT,
    FONT_BODY,
    FONT_SIZE_BODY, FONT_SIZE_CAPTION,
    RADIUS_MD,
)

logger = logging.getLogger(__name__)

NUM_PANELS = 11


class AdminNavButton(QPushButton):
    """Navigations-Button fuer die Admin-Sidebar (ACENCIA CI-konform)."""
    
    def __init__(self, icon: str, text: str, parent=None):
        super().__init__(parent)
        self.setText(f"   {icon}  {text}")
        self.setCheckable(True)
        self.setMinimumHeight(40)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                border-left: 3px solid transparent;
                border-radius: 0px;
                padding: 8px 20px;
                text-align: left;
                font-family: {FONT_BODY};
                font-size: {FONT_SIZE_BODY};
                color: {PRIMARY_500};
            }}
            QPushButton:hover {{
                background-color: {SIDEBAR_HOVER};
                color: {SIDEBAR_TEXT};
            }}
            QPushButton:checked {{
                background-color: {SIDEBAR_HOVER};
                border-left: 3px solid {ACCENT_500};
                color: {SIDEBAR_TEXT};
                font-weight: 500;
            }}
        """)


class AdminView(QWidget):
    """
    Administrations-Ansicht mit eigener Sidebar-Navigation.
    16 Bereiche in 6 Sektionen, Panels werden per Lazy Loading instanziiert.
    """
    
    back_requested = Signal()
    
    def __init__(self, api_client: APIClient, auth_api: AuthAPI):
        super().__init__()
        self._api_client = api_client
        self._auth_api = auth_api
        self._admin_api = AdminAPI(api_client)
        self._releases_api = ReleasesAPI(api_client)
        
        self._model_pricing_api = ModelPricingAPI(api_client)
        
        self._panels: List[Optional[QWidget]] = [None] * NUM_PANELS
        self._placeholders: List[QWidget] = []
        
        self._setup_ui()
        
        QTimer.singleShot(100, lambda: self._navigate_to(0))
    
    def _setup_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._sidebar_frame = ModuleSidebar("admin_sidebar", parent=self)
        self._sidebar_frame.back_requested.connect(self.back_requested.emit)

        self._nav_buttons: list[AdminNavButton] = []

        def add_nav(icon: str, text: str, index: int) -> AdminNavButton:
            btn = AdminNavButton(icon, text)
            btn.clicked.connect(lambda checked, i=index: self._navigate_to(i))
            self._sidebar_frame.add_widget(btn)
            self._nav_buttons.append(btn)
            return btn

        self._sidebar_frame.add_admin_section(texts.ADMIN_SECTION_MANAGEMENT)
        self._btn_users     = add_nav("\u203A", texts.ADMIN_TAB_USERS, 0)
        self._btn_sessions  = add_nav("\u203A", texts.ADMIN_TAB_SESSIONS, 1)
        self._btn_passwords = add_nav("\u203A", texts.ADMIN_TAB_PASSWORDS, 2)

        self._sidebar_frame.add_admin_section(texts.ADMIN_SECTION_MONITORING)
        self._btn_activity = add_nav("\u203A", texts.ADMIN_TAB_ACTIVITY, 3)
        self._btn_costs    = add_nav("\u203A", texts.ADMIN_TAB_COSTS, 4)
        self._btn_releases = add_nav("\u203A", texts.ADMIN_TAB_RELEASES, 5)

        self._sidebar_frame.add_admin_section("KOMMUNIKATION")
        self._btn_messages = add_nav("\u203A", texts.ADMIN_MSG_TAB, 6)

        self._sidebar_frame.add_admin_section(texts.ADMIN_SECTION_SYSTEM)
        self._btn_server_health = add_nav("\u203A", texts.ADMIN_TAB_SERVER_HEALTH, 7)
        self._btn_migrations    = add_nav("\u203A", texts.ADMIN_TAB_MIGRATIONS, 8)

        user = self._auth_api.current_user if self._auth_api else None
        if user and user.is_super_admin:
            self._sidebar_frame.add_admin_section(texts.ADMIN_SUPPORT_SECTION)
            self._btn_support = add_nav("\u203A", texts.ADMIN_SUPPORT_NAV, 9)

            self._sidebar_frame.add_admin_section(texts.SRVMGMT_SECTION)
            self._btn_server_mgmt = add_nav("\u203A", texts.SRVMGMT_TITLE, 10)
        else:
            self._btn_support = None
            self._btn_server_mgmt = None

        self._sidebar_frame.add_stretch()
        root.addWidget(self._sidebar_frame)
        
        # === Content-Bereich (QStackedWidget mit Platzhaltern) ===
        self._content_stack = QStackedWidget()
        self._content_stack.setStyleSheet(f"background-color: {PRIMARY_0};")
        
        for i in range(NUM_PANELS):
            placeholder = QWidget()
            self._placeholders.append(placeholder)
            self._content_stack.addWidget(placeholder)
        
        root.addWidget(self._content_stack)
        
        self._btn_users.setChecked(True)
    
    def _navigate_to(self, index: int):
        """Navigiert zu einem Admin-Bereich (Sidebar-Klick)."""
        for i, btn in enumerate(self._nav_buttons):
            btn.setChecked(i == index)
        
        self._ensure_panel_loaded(index)
        self._content_stack.setCurrentIndex(index)
        self._on_panel_changed(index)
    
    def _ensure_panel_loaded(self, index: int):
        """Lazy Loading: Panel wird erst beim ersten Aufruf instanziiert."""
        if self._panels[index] is not None:
            return
        
        panel = self._create_panel(index)
        if panel is None:
            return
        
        panel._toast_manager = getattr(self, '_toast_manager', None)
        self._panels[index] = panel
        
        old_placeholder = self._placeholders[index]
        self._content_stack.removeWidget(old_placeholder)
        old_placeholder.deleteLater()
        self._content_stack.insertWidget(index, panel)
    
    def _create_panel(self, index: int) -> Optional[QWidget]:
        """Erstellt das Panel fuer den gegebenen Index (11 Panels)."""
        tm = getattr(self, '_toast_manager', None)
        ac = self._api_client

        if index == 0:
            from ui.admin.panels.user_management import UserManagementPanel
            return UserManagementPanel(
                api_client=ac, auth_api=self._auth_api,
                toast_manager=tm, admin_api=self._admin_api
            )
        elif index == 1:
            from ui.admin.panels.sessions import SessionsPanel
            return SessionsPanel(
                api_client=ac, toast_manager=tm, admin_api=self._admin_api,
                auth_api=self._auth_api
            )
        elif index == 2:
            from ui.admin.panels.passwords import PasswordsPanel
            return PasswordsPanel(api_client=ac, toast_manager=tm)
        elif index == 3:
            from ui.admin.panels.activity_log import ActivityLogPanel
            return ActivityLogPanel(
                api_client=ac, toast_manager=tm, admin_api=self._admin_api
            )
        elif index == 4:
            from ui.admin.panels.ai_costs import AiCostsPanel
            return AiCostsPanel(
                api_client=ac, toast_manager=tm,
                model_pricing_api=self._model_pricing_api
            )
        elif index == 5:
            from ui.admin.panels.releases import ReleasesPanel
            return ReleasesPanel(
                api_client=ac, toast_manager=tm,
                releases_api=self._releases_api
            )
        elif index == 6:
            from ui.admin.panels.messages import MessagesPanel
            return MessagesPanel(api_client=ac, toast_manager=tm)
        elif index == 7:
            from ui.admin.panels.server_health import ServerHealthPanel
            return ServerHealthPanel(
                api_client=ac, toast_manager=tm, admin_api=self._admin_api
            )
        elif index == 8:
            from ui.admin.panels.migrations import MigrationsPanel
            return MigrationsPanel(
                api_client=ac, toast_manager=tm, admin_api=self._admin_api
            )
        elif index == 9:
            from ui.admin.panels.support_feedback_panel import SupportFeedbackPanel
            return SupportFeedbackPanel(api_client=ac, toast_manager=tm)
        elif index == 10:
            from ui.admin.panels.server_mgmt_panel import ServerMgmtPanel
            return ServerMgmtPanel(api_client=ac, toast_manager=tm)

        return None
    
    def _on_panel_changed(self, index: int):
        """Laedt Daten beim Panel-Wechsel."""
        panel = self._panels[index]
        if panel is None:
            return
        
        # Sessions-Timer nur wenn Sessions aktiv
        sessions_panel = self._panels[1]
        if sessions_panel is not None and hasattr(sessions_panel, 'stop_timer'):
            if index == 1:
                sessions_panel.start_timer()
            else:
                sessions_panel.stop_timer()
        
        if hasattr(panel, 'load_data'):
            panel.load_data()
