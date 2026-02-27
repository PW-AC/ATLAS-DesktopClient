"""
ACENCIA ATLAS - Admin-Shell (Sidebar + Panel-Wechsel mit Lazy Loading)

Vollbild-Layout mit eigener Sidebar-Navigation (16 Bereiche):

VERWALTUNG:
0. Nutzerverwaltung (CRUD)
1. Sessions (Einsicht + Kill)
2. Passwoerter (PDF/ZIP Passwort-Verwaltung)

MONITORING:
3. Aktivitaetslog (Filter + Pagination)
4. KI-Kosten (Verarbeitungshistorie + Kosten-Statistiken + Request-Details)
5. Releases (Auto-Update Verwaltung)

VERARBEITUNG:
6. KI-Klassifikation (Prompts, Modelle, Pipeline-Visualisierung)
7. KI-Provider (API-Key-Verwaltung OpenRouter/OpenAI)
8. Modell-Preise (Kostenberechnung pro Modell)
9. Dokumenten-Regeln (Automatische Aktionen bei Duplikaten/leeren Seiten)

E-MAIL:
10. E-Mail-Konten (SMTP/IMAP Verwaltung)
11. Smart!Scan (Einstellungen)
12. Smart!Scan Historie
13. E-Mail Posteingang

KOMMUNIKATION:
14. Mitteilungen (System + Admin-Mitteilungen verwalten)

SYSTEM:
15. Server-Gesundheit (Health-Check mit ~35 Einzel-Checks + Trend-Vergleich)
16. Migrationen (DB-Migrationen aus setup/ anzeigen + ausfuehren)

Extrahiert aus admin_view.py (Schritt 4 Refactoring).
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
from api.processing_settings import ProcessingSettingsAPI
from api.ai_providers import AIProvidersAPI
from api.model_pricing import ModelPricingAPI
from i18n import de as texts

from ui.styles.tokens import (
    PRIMARY_900, PRIMARY_500, PRIMARY_0,
    ACCENT_500,
    SIDEBAR_BG, SIDEBAR_TEXT, SIDEBAR_HOVER, SIDEBAR_WIDTH_INT,
    FONT_BODY,
    FONT_SIZE_BODY, FONT_SIZE_CAPTION,
    RADIUS_MD,
)

logger = logging.getLogger(__name__)

NUM_PANELS = 17


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
        
        from api.smartscan import SmartScanAPI, EmailAccountsAPI as EmailAccAPI
        self._smartscan_api = SmartScanAPI(api_client)
        self._email_accounts_api = EmailAccAPI(api_client)
        
        self._processing_settings_api = ProcessingSettingsAPI(api_client)
        self._ai_providers_api = AIProvidersAPI(api_client)
        self._model_pricing_api = ModelPricingAPI(api_client)
        
        self._panels: List[Optional[QWidget]] = [None] * NUM_PANELS
        self._placeholders: List[QWidget] = []
        
        self._setup_ui()
        
        QTimer.singleShot(100, lambda: self._navigate_to(0))
    
    def _setup_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        
        # === Admin-Sidebar ===
        admin_sidebar = QFrame()
        admin_sidebar.setObjectName("admin_sidebar")
        admin_sidebar.setFixedWidth(SIDEBAR_WIDTH_INT)
        admin_sidebar.setStyleSheet(f"""
            QFrame#admin_sidebar {{
                background-color: {SIDEBAR_BG};
                border: none;
            }}
        """)
        
        sb_layout = QVBoxLayout(admin_sidebar)
        sb_layout.setContentsMargins(0, 8, 0, 20)
        sb_layout.setSpacing(2)
        
        # Zurueck-Button
        back_btn = QPushButton(texts.ADMIN_BACK_TO_APP)
        back_btn.setCursor(Qt.PointingHandCursor)
        back_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: 1px solid {PRIMARY_500};
                border-radius: {RADIUS_MD};
                padding: 8px 16px;
                margin: 0 16px 4px 16px;
                color: {PRIMARY_500};
                font-family: {FONT_BODY};
                font-size: {FONT_SIZE_BODY};
                text-align: center;
            }}
            QPushButton:hover {{
                background-color: {SIDEBAR_HOVER};
                border-color: {SIDEBAR_TEXT};
                color: {SIDEBAR_TEXT};
            }}
        """)
        back_btn.clicked.connect(self.back_requested.emit)
        sb_layout.addWidget(back_btn)
        
        self._nav_buttons: list[AdminNavButton] = []
        
        def add_section(label_text: str):
            line = QFrame()
            line.setFixedHeight(1)
            line.setStyleSheet(f"background-color: {ACCENT_500}; border: none; margin: 0;")
            sb_layout.addWidget(line)
            
            lbl = QLabel(label_text)
            lbl.setStyleSheet(f"""
                background-color: transparent;
                color: {PRIMARY_500};
                font-size: {FONT_SIZE_CAPTION};
                padding: 10px 20px 4px 20px;
                letter-spacing: 1px;
            """)
            sb_layout.addWidget(lbl)
        
        def add_nav(icon: str, text: str, index: int) -> AdminNavButton:
            btn = AdminNavButton(icon, text)
            btn.clicked.connect(lambda checked, i=index: self._navigate_to(i))
            sb_layout.addWidget(btn)
            self._nav_buttons.append(btn)
            return btn
        
        # Trennlinie oben
        top_line = QFrame()
        top_line.setFixedHeight(1)
        top_line.setStyleSheet(f"background-color: {ACCENT_500}; border: none; margin: 0;")
        sb_layout.addWidget(top_line)
        
        # === VERWALTUNG ===
        lbl_verwaltung = QLabel(texts.ADMIN_SECTION_MANAGEMENT)
        lbl_verwaltung.setStyleSheet(f"""
            background-color: transparent;
            color: {PRIMARY_500};
            font-size: {FONT_SIZE_CAPTION};
            padding: 8px 20px 4px 20px;
            letter-spacing: 1px;
        """)
        sb_layout.addWidget(lbl_verwaltung)
        self._btn_users     = add_nav("›", texts.ADMIN_TAB_USERS, 0)
        self._btn_sessions  = add_nav("›", texts.ADMIN_TAB_SESSIONS, 1)
        self._btn_passwords = add_nav("›", texts.ADMIN_TAB_PASSWORDS, 2)
        
        # === MONITORING ===
        add_section(texts.ADMIN_SECTION_MONITORING)
        self._btn_activity = add_nav("›", texts.ADMIN_TAB_ACTIVITY, 3)
        self._btn_costs    = add_nav("›", texts.ADMIN_TAB_COSTS, 4)
        self._btn_releases = add_nav("›", texts.ADMIN_TAB_RELEASES, 5)
        
        # === VERARBEITUNG ===
        add_section(texts.ADMIN_SECTION_PROCESSING)
        self._btn_ai_classification = add_nav("›", texts.ADMIN_TAB_AI_CLASSIFICATION, 6)
        self._btn_ai_providers      = add_nav("›", texts.ADMIN_TAB_AI_PROVIDERS, 7)
        self._btn_model_pricing     = add_nav("›", texts.ADMIN_TAB_MODEL_PRICING, 8)
        self._btn_document_rules    = add_nav("›", texts.ADMIN_TAB_DOCUMENT_RULES, 9)
        
        # === E-MAIL ===
        add_section(texts.ADMIN_SECTION_EMAIL)
        self._btn_email_accounts     = add_nav("›", texts.ADMIN_TAB_EMAIL_ACCOUNTS, 10)
        self._btn_smartscan_settings = add_nav("›", texts.ADMIN_TAB_SMARTSCAN_SETTINGS, 11)
        self._btn_smartscan_history  = add_nav("›", texts.ADMIN_TAB_SMARTSCAN_HISTORY, 12)
        self._btn_email_inbox        = add_nav("›", texts.ADMIN_TAB_EMAIL_INBOX, 13)
        
        # === KOMMUNIKATION ===
        add_section("KOMMUNIKATION")
        self._btn_messages           = add_nav("›", texts.ADMIN_MSG_TAB, 14)
        
        # === SYSTEM ===
        add_section(texts.ADMIN_SECTION_SYSTEM)
        self._btn_server_health      = add_nav("›", texts.ADMIN_TAB_SERVER_HEALTH, 15)
        self._btn_migrations         = add_nav("›", texts.ADMIN_TAB_MIGRATIONS, 16)
        
        sb_layout.addStretch()
        root.addWidget(admin_sidebar)
        
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
        """Erstellt das Panel fuer den gegebenen Index."""
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
                api_client=ac, toast_manager=tm, admin_api=self._admin_api
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
            from ui.admin.panels.ai_classification import AiClassificationPanel
            return AiClassificationPanel(
                api_client=ac, toast_manager=tm,
                processing_settings_api=self._processing_settings_api,
                ai_providers_api=self._ai_providers_api
            )
        elif index == 7:
            from ui.admin.panels.ai_providers import AiProvidersPanel
            return AiProvidersPanel(
                api_client=ac, toast_manager=tm,
                ai_providers_api=self._ai_providers_api
            )
        elif index == 8:
            from ui.admin.panels.model_pricing import ModelPricingPanel
            return ModelPricingPanel(
                api_client=ac, toast_manager=tm,
                model_pricing_api=self._model_pricing_api
            )
        elif index == 9:
            from ui.admin.panels.document_rules import DocumentRulesPanel
            return DocumentRulesPanel(api_client=ac, toast_manager=tm)
        elif index == 10:
            from ui.admin.panels.email_accounts import EmailAccountsPanel
            return EmailAccountsPanel(
                api_client=ac, toast_manager=tm,
                email_accounts_api=self._email_accounts_api
            )
        elif index == 11:
            from ui.admin.panels.smartscan_settings import SmartScanSettingsPanel
            return SmartScanSettingsPanel(
                api_client=ac, toast_manager=tm,
                smartscan_api=self._smartscan_api,
                email_accounts_api=self._email_accounts_api
            )
        elif index == 12:
            from ui.admin.panels.smartscan_history import SmartScanHistoryPanel
            return SmartScanHistoryPanel(
                api_client=ac, toast_manager=tm,
                smartscan_api=self._smartscan_api
            )
        elif index == 13:
            from ui.admin.panels.email_inbox import EmailInboxPanel
            return EmailInboxPanel(
                api_client=ac, toast_manager=tm,
                email_accounts_api=self._email_accounts_api
            )
        elif index == 14:
            from ui.admin.panels.messages import MessagesPanel
            return MessagesPanel(api_client=ac, toast_manager=tm)
        elif index == 15:
            from ui.admin.panels.server_health import ServerHealthPanel
            return ServerHealthPanel(
                api_client=ac, toast_manager=tm, admin_api=self._admin_api
            )
        elif index == 16:
            from ui.admin.panels.migrations import MigrationsPanel
            return MigrationsPanel(
                api_client=ac, toast_manager=tm, admin_api=self._admin_api
            )
        
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
