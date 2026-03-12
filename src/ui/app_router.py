# -*- coding: utf-8 -*-
"""
ACENCIA ATLAS - App Router

Shell-Fenster mit persistenter Sidebar links und QStackedWidget rechts.
Die Sidebar zeigt Module dynamisch basierend auf User-Berechtigungen an.
"""

import os
import logging
import warnings

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QMessageBox, QApplication, QSystemTrayIcon, QMenu,
)
from PySide6.QtGui import QIcon, QAction, QCloseEvent
from PySide6.QtCore import Qt, QTimer

from api.client import APIClient
from api.auth import AuthAPI
from i18n import de as texts
from ui.dashboard_screen import DashboardScreen
from ui.components.sidebar import AppSidebar
from ui.components.module_sidebar import ModuleSidebar
from ui.components.fade_stacked_widget import FadeStackedWidget
from ui.toast import ToastManager
from services.global_heartbeat import GlobalHeartbeat
from services.contact.call_runtime_service import CallRuntimeService
from domain.contact.runtime_models import CallValidationStatus
from ui.styles.tokens import (
    FONT_BODY, FONT_SIZE_BODY, PRIMARY_500, BG_PRIMARY,
)

APP_VERSION_FILE = "VERSION"

logger = logging.getLogger(__name__)
hb_logger = logging.getLogger('heartbeat.router')

_IDX_DASHBOARD = 0
_IDX_CORE = 1
_IDX_LEDGER = 2
_IDX_WORKFORCE = 3
_IDX_CONTACT = 4

# Verzoegerung zwischen Modul-Preloads (ms). Ermoeglicht UI-Thread-Atmung:
# ensure_fn() kann Widget-Erstellung/Stylesheet-Parsing machen; mit 0ms
# blockiert der naechste Event-Loop-Tick. 75–100ms lassen Frames rendern.
_PRELOAD_DELAY_MS = 75


class AppRouter(QMainWindow):
    """Router-Shell: Sidebar links + Content-Stack rechts."""

    def __init__(self, api_client: APIClient, auth_api: AuthAPI):
        super().__init__()

        self.api_client = api_client
        self.auth_api = auth_api

        username = auth_api.current_user.username if auth_api.current_user else ""
        tenant_name = auth_api.active_tenant.tenant_name if auth_api.active_tenant else ""
        if tenant_name:
            self.setWindowTitle(f"ACENCIA ATLAS - {tenant_name} - {username}")
        else:
            self.setWindowTitle(f"ACENCIA ATLAS - {username}")
        self.setMinimumSize(1460, 900)

        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        # -- Central widget: Sidebar + Content Stack --
        central = QWidget()
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Sidebar
        self._sidebar = AppSidebar()
        self._sidebar.dashboard_requested.connect(self.show_dashboard)
        self._sidebar.module_requested.connect(self._open_module)
        self._sidebar.admin_requested.connect(self._open_module)
        self._sidebar.settings_requested.connect(self._on_settings_from_sidebar)
        self._sidebar.global_admin_requested.connect(
            lambda: self._open_module("admin")
        )
        main_layout.addWidget(self._sidebar)

        # Content Stack mit Fade-Through-Transition (250ms gesamt: 100ms out + 150ms in)
        self._stack = FadeStackedWidget(fade_out_ms=100, fade_in_ms=150)
        main_layout.addWidget(self._stack, 1)

        self.setCentralWidget(central)

        self._core_widget = None
        self._ledger_widget = None
        self._workforce_widget = None
        self._contact_widget = None

        self._pending_module_id: str | None = None
        self._pending_from_dashboard: bool = False
        self._pending_exit_sidebar: ModuleSidebar | None = None
        self._pending_action: str | None = None
        self._pending_reset_module: str | None = None

        app_version = self._read_version()

        user = auth_api.current_user
        visible = []
        if user:
            if user.has_module("core"):
                visible.append("core")
            if user.is_admin:
                visible.append("admin")
            if user.has_module("provision"):
                visible.append("ledger")
            if user.has_module("workforce"):
                visible.append("workforce")
            if user.has_module("contact"):
                visible.append("contact")
            if user.is_module_admin("core"):
                visible.append("core_admin")
            if user.is_module_admin("provision"):
                visible.append("ledger_admin")
            if user.is_module_admin("workforce"):
                visible.append("workforce_admin")

        user_email = user.email or "" if user else ""
        user_account_type = user.account_type if user else "user"
        self._dashboard = DashboardScreen(
            username=username, app_version=app_version,
            api_client=api_client, auth_api=auth_api, tenant_name=tenant_name,
            user_email=user_email, user_account_type=user_account_type,
            user=user,
        )
        self._dashboard.set_modules(visible)
        self._dashboard.module_requested.connect(self._open_module)
        self._dashboard.quick_action_requested.connect(self._on_quick_action)
        self._dashboard.logout_requested.connect(self._on_logout)
        self._dashboard.forced_logout_requested.connect(self._on_forced_logout)
        self._stack.addWidget(self._dashboard)  # Index 0

        self._dashboard.load_messages(api_client)
        self._dashboard.load_kpi_data()

        self._stack.addWidget(QWidget())  # Placeholder Index 1 (Core)
        self._stack.addWidget(QWidget())  # Placeholder Index 2 (Ledger)
        self._stack.addWidget(QWidget())  # Placeholder Index 3 (Workforce)
        self._stack.addWidget(QWidget())  # Placeholder Index 4 (Contact)

        # Sidebar mit User-Daten befuellen
        self._sidebar.set_version(app_version)
        if user:
            self._sidebar.set_user(user)
        self._sidebar.set_active("dashboard")

        self._toast_manager = ToastManager(self)
        self._active_module: str | None = None

        self._call_runtime = CallRuntimeService()

        self._heartbeat = GlobalHeartbeat(api_client, auth_api, parent=self)
        self._heartbeat.session_invalid.connect(self._on_session_invalid)
        self._heartbeat.notifications_updated.connect(self._on_notifications_updated)
        self._heartbeat.system_status_changed.connect(self._on_system_status_changed)
        self._heartbeat.modules_updated.connect(self._on_modules_updated)
        self._heartbeat.start()

        self._preload_queue = self._build_preload_queue(user)
        if self._preload_queue:
            QTimer.singleShot(_PRELOAD_DELAY_MS, self._preload_next_module)

    # ------------------------------------------------------------------
    # Boot-Preload
    # ------------------------------------------------------------------

    def _build_preload_queue(self, user) -> list:
        """Baut die Liste der vorab zu ladenden Module basierend auf Nutzerrechten."""
        queue = []
        if user and user.has_module("core"):
            queue.append(self._ensure_core)
        if user and user.has_module("provision"):
            queue.append(self._ensure_ledger)
        if user and user.has_module("workforce"):
            queue.append(self._ensure_workforce)
        if user and user.has_module("contact"):
            queue.append(self._ensure_contact)
        return queue

    def _preload_next_module(self):
        """Laedt das naechste Modul aus der Queue (1 pro Event-Loop-Durchlauf)."""
        if not self._preload_queue:
            return
        ensure_fn = self._preload_queue.pop(0)
        try:
            ensure_fn()
        except Exception:
            logger.exception("Modul-Preload fehlgeschlagen")
        if self._preload_queue:
            QTimer.singleShot(_PRELOAD_DELAY_MS, self._preload_next_module)

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def show_dashboard(self):
        """Zeigt das Dashboard (Index 0)."""
        old_sidebar = self._get_module_sidebar() if self._active_module else None
        leaving_module = self._active_module

        if old_sidebar:
            self._pending_exit_sidebar = old_sidebar
            self._pending_reset_module = leaving_module
            self._safe_connect_exit(old_sidebar, self._on_exit_finished_show_dashboard)
            old_sidebar.play_exit_animation()
            # Parallel: Dashboard-Wechsel sofort starten, aber den
            # reset_leaving_module verschieben bis Exit fertig ist –
            # _restore_sidebar() wuerde sonst die laufende Exit-Animation
            # abbrechen und einen sichtbaren Ruckler erzeugen.
            self._stop_active_module_heartbeat()
            self._active_module = None
            self._stack.setCurrentIndex(_IDX_DASHBOARD)
            self._sidebar.set_active("dashboard")
            QTimer.singleShot(0, lambda: self._sidebar.set_expanded(True))
            return

        self._do_show_dashboard()

    def _on_exit_finished_show_dashboard(self):
        """Callback nach Exit-Animation: raeume alte Sidebar auf und reset Modul."""
        if self._pending_exit_sidebar:
            self._safe_disconnect_exit(self._pending_exit_sidebar, self._on_exit_finished_show_dashboard)
            self._pending_exit_sidebar.reset_animation_state()
            self._pending_exit_sidebar = None

        self._deferred_reset_leaving_module()

    def _do_show_dashboard(self):
        """Fuehrt den eigentlichen Wechsel zum Dashboard durch (ohne Exit-Animation)."""
        self._stop_active_module_heartbeat()
        self._reset_leaving_module()
        self._active_module = None
        self._stack.setCurrentIndex(_IDX_DASHBOARD)
        self._sidebar.set_active("dashboard")
        QTimer.singleShot(0, lambda: self._sidebar.set_expanded(True))

    def _on_settings_from_sidebar(self):
        """Oeffnet die Einstellungen im Dashboard-Overlay."""
        self.show_dashboard()
        self._dashboard.open_settings_overlay()

    def _on_quick_action(self, module_id: str, action_id: str):
        """Schnellaktion vom Dashboard: Modul oeffnen + Sub-Aktion ausfuehren."""
        self._pending_action = action_id
        self._open_module(module_id)

    def _open_module(self, module_id: str):
        from_dashboard = self._active_module is None
        from_module = not from_dashboard
        leaving_module = self._active_module

        old_sidebar = self._get_module_sidebar() if from_module else None

        if old_sidebar:
            self._pending_module_id = module_id
            self._pending_from_dashboard = False
            self._pending_exit_sidebar = old_sidebar
            self._pending_reset_module = leaving_module
            self._safe_connect_exit(old_sidebar, self._on_exit_finished_open_module)
            old_sidebar.play_exit_animation()
            # Parallel: Fade-Transition + View-Switch sofort starten.
            # reset_leaving_module wird ins Exit-Cleanup verschoben,
            # damit _restore_sidebar() nicht die laufende Animation killt.
            self._do_open_module(module_id, False, skip_reset=True)
            return

        self._do_open_module(module_id, from_dashboard)

    def _on_exit_finished_open_module(self):
        """Callback nach Exit-Animation: raeume alte Sidebar auf und reset Modul."""
        if self._pending_exit_sidebar:
            self._safe_disconnect_exit(self._pending_exit_sidebar, self._on_exit_finished_open_module)
            self._pending_exit_sidebar.reset_animation_state()
            self._pending_exit_sidebar = None

        self._deferred_reset_leaving_module()

        self._pending_module_id = None
        self._pending_from_dashboard = False

    def _do_open_module(self, module_id: str, from_dashboard: bool,
                        skip_reset: bool = False):
        """Fuehrt den eigentlichen Modulwechsel durch."""
        self._stop_active_module_heartbeat()
        if not skip_reset:
            self._reset_leaving_module()

        action = getattr(self, '_pending_action', None)
        self._pending_action = None
        target_index: int | None = None

        if module_id == "core":
            self._ensure_core()
            target_index = _IDX_CORE
            self._stack.setCurrentIndex(target_index)
            QTimer.singleShot(0, lambda: self._start_module_heartbeat(self._core_widget, "core"))
            self._dispatch_core_action(action)
        elif module_id == "admin":
            user = self.auth_api.current_user
            if not user or not user.is_admin:
                logger.warning("Admin-Zugriff ohne Admin-Recht abgelehnt")
                return
            self._ensure_core()
            target_index = _IDX_CORE
            self._stack.setCurrentIndex(target_index)
            self._core_widget.navigate_to_admin()
            QTimer.singleShot(0, lambda: self._start_module_heartbeat(self._core_widget, "core"))
        elif module_id == "ledger":
            user = self.auth_api.current_user
            if not user or not user.has_module('provision'):
                logger.warning("Ledger-Zugriff ohne Modul-Freischaltung abgelehnt")
                return
            self._ensure_ledger()
            target_index = _IDX_LEDGER
            self._stack.setCurrentIndex(target_index)
            QTimer.singleShot(0, lambda: self._start_module_heartbeat(self._ledger_widget, "ledger"))
        elif module_id == "workforce":
            user = self.auth_api.current_user
            if not user or not user.has_module('workforce'):
                logger.warning("Workforce-Zugriff ohne Modul-Freischaltung abgelehnt")
                return
            self._ensure_workforce()
            target_index = _IDX_WORKFORCE
            self._stack.setCurrentIndex(target_index)
            QTimer.singleShot(0, lambda: self._start_module_heartbeat(self._workforce_widget, "workforce"))
        elif module_id == "contact":
            user = self.auth_api.current_user
            if not user or not user.has_module('contact'):
                logger.warning("Contact-Zugriff ohne Modul-Freischaltung abgelehnt")
                return
            self._ensure_contact()
            target_index = _IDX_CONTACT
            self._stack.setCurrentIndex(target_index)
            QTimer.singleShot(0, lambda: self._start_module_heartbeat(self._contact_widget, "contact"))
            self._dispatch_contact_action(action)
        elif module_id == "contact_admin":
            self._open_module_admin("contact", "Contact", from_dashboard)
            return
        elif module_id == "core_admin":
            self._open_module_admin("core", "Core", from_dashboard)
            return
        elif module_id == "ledger_admin":
            self._open_module_admin("provision", "Provision", from_dashboard)
            return
        elif module_id == "workforce_admin":
            self._open_module_admin("workforce", "Workforce", from_dashboard)
            return

        if target_index is not None:
            self._schedule_module_sidebar_enter(target_index)

    def _dispatch_core_action(self, action: str | None):
        """Fuehrt Sub-Aktionen im Core-Modul aus."""
        if not action or not self._core_widget:
            return
        if action == "open_inbox":
            self._core_widget.navigate_to_inbox()
        elif action == "upload_doc":
            self._core_widget.navigate_to_inbox()
            QTimer.singleShot(200, self._core_widget.open_upload_dialog)
        elif action == "bipro_fetch":
            self._core_widget.navigate_to_bipro()

    def _dispatch_contact_action(self, action: str | None):
        """Fuehrt Sub-Aktionen im Contact-Modul aus."""
        if not action or not self._contact_widget:
            return
        if action == "new_call_note":
            QTimer.singleShot(200, self._contact_widget.open_quick_call_note)

    @staticmethod
    def _safe_connect_exit(sidebar: 'ModuleSidebar', slot):
        """Verbindet exit_animation_finished sicher: erst alle vorherigen Verbindungen
        dieses Slots entfernen, dann genau einmal verbinden."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            try:
                sidebar.exit_animation_finished.disconnect(slot)
            except (RuntimeError, TypeError):
                pass
        sidebar.exit_animation_finished.connect(slot)

    @staticmethod
    def _safe_disconnect_exit(sidebar: 'ModuleSidebar', slot):
        """Trennt den Slot sicher von exit_animation_finished."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            try:
                sidebar.exit_animation_finished.disconnect(slot)
            except (RuntimeError, TypeError):
                pass

    def _get_module_sidebar(self, widget: QWidget | None = None) -> 'ModuleSidebar | None':
        """Findet die ModuleSidebar eines Widgets.

        Gibt nur eine Sidebar zurueck, die tatsaechlich sichtbar ist.
        Einige Views (z.B. MainHub im Admin-Modus) verstecken ihre
        eigene Sidebar per hide(), wenn ein Sub-View eine eigene hat.

        Wenn kein Widget angegeben wird, wird das aktuell sichtbare
        Widget im Stack verwendet.
        """
        if widget is None:
            widget = self._stack.currentWidget()
        if widget is None:
            return None
        sidebar = getattr(widget, '_sidebar', None) or getattr(widget, '_sidebar_frame', None)
        if isinstance(sidebar, ModuleSidebar) and not sidebar.isHidden():
            return sidebar
        return None

    def _get_sidebar_of_stack_index(self, index: int) -> 'ModuleSidebar | None':
        """Findet die ModuleSidebar des Widgets an einem bestimmten Stack-Index.

        Im Gegensatz zu _get_module_sidebar prueft diese Methode nicht isHidden,
        weil die Sidebar eines Ziel-Widgets vor der Transition im Default-Zustand
        sein kann (sichtbar aber visuell zurueckgesetzt).
        """
        widget = self._stack.widget(index)
        if widget is None:
            return None
        sidebar = getattr(widget, '_sidebar', None) or getattr(widget, '_sidebar_frame', None)
        if isinstance(sidebar, ModuleSidebar):
            return sidebar
        return None

    def _schedule_module_sidebar_enter(self, target_index: int):
        """Bereitet die ModuleSidebar-Enter-Animation vor.

        Die Sidebar des Ziel-Widgets wird sofort unsichtbar gemacht
        (reset_animation_state). Die Enter-Animation startet parallel
        zum Fade-In des Content-Stacks:
        - Wenn die AppSidebar noch expanded ist (Dashboard->Modul),
          wird sie collapsed. Collapse und Fade laufen parallel.
        - Enter-Animation startet sobald der Fade-Out des Overlays
          fertig ist (= View-Switch passiert), nicht erst nach Fade-In.
        """
        target_sidebar = self._get_sidebar_of_stack_index(target_index)
        if target_sidebar:
            target_sidebar.reset_animation_state()

        needs_collapse = self._sidebar._is_expanded
        if needs_collapse:
            self._sidebar.set_expanded(False)

        if self._stack.is_transitioning:
            self._stack.view_switched.connect(
                self._play_module_sidebar_enter, Qt.SingleShotConnection
            )
        else:
            self._play_module_sidebar_enter()

    def _play_module_sidebar_enter(self):
        """Spielt die Eingangsanimation der Modul-Sidebar des aktuellen Widgets ab."""
        sidebar = self._get_module_sidebar()
        if sidebar:
            sidebar.reset_animation_state()
            sidebar.play_enter_animation()

    def _open_module_admin(self, module_key: str, module_name: str,
                           from_dashboard: bool = False):
        """Oeffnet die Modul-Admin-Verwaltung als eigenstaendige Ansicht."""
        user = self.auth_api.current_user
        if not user or not user.is_module_admin(module_key):
            logger.warning(f"Modul-Admin-Zugriff fuer {module_key} abgelehnt")
            return
        attr = f'_module_admin_{module_key}'
        if not hasattr(self, attr) or getattr(self, attr) is None:
            from ui.module_admin import ModuleAdminShell
            config_panels = []
            if module_key == 'core':
                config_panels = self._get_core_admin_config_panels()
            shell = ModuleAdminShell(
                module_key=module_key, module_name=module_name,
                api_client=self.api_client, auth_api=self.auth_api,
                config_panels=config_panels,
            )
            shell._toast_manager = self._toast_manager
            shell.back_requested.connect(self.show_dashboard)
            setattr(self, attr, shell)
            self._stack.addWidget(shell)

        self._reset_leaving_module()

        widget = getattr(self, attr)
        idx = self._stack.indexOf(widget)
        self._stack.setCurrentIndex(idx)
        widget.load_data()

        self._schedule_module_sidebar_enter(idx)

    def _get_core_admin_config_panels(self):
        """Config-Panel-Factories fuer das Core-Modul."""
        from api.processing_settings import ProcessingSettingsAPI
        from api.ai_providers import AIProvidersAPI
        from api.model_pricing import ModelPricingAPI
        from api.smartscan import SmartScanAPI, EmailAccountsAPI as EmailAccAPI

        psa = ProcessingSettingsAPI(self.api_client)
        apa = AIProvidersAPI(self.api_client)
        mpa = ModelPricingAPI(self.api_client)
        ssa = SmartScanAPI(self.api_client)
        eaa = EmailAccAPI(self.api_client)

        def _ai_class(ac, tm):
            from ui.admin.panels.ai_classification import AiClassificationPanel
            return AiClassificationPanel(api_client=ac, toast_manager=tm, processing_settings_api=psa, ai_providers_api=apa)
        def _ai_prov(ac, tm):
            from ui.admin.panels.ai_providers import AiProvidersPanel
            return AiProvidersPanel(api_client=ac, toast_manager=tm, ai_providers_api=apa)
        def _model_price(ac, tm):
            from ui.admin.panels.model_pricing import ModelPricingPanel
            return ModelPricingPanel(api_client=ac, toast_manager=tm, model_pricing_api=mpa)
        def _doc_rules(ac, tm):
            from ui.admin.panels.document_rules import DocumentRulesPanel
            return DocumentRulesPanel(api_client=ac, toast_manager=tm)
        def _email_acc(ac, tm):
            from ui.admin.panels.email_accounts import EmailAccountsPanel
            return EmailAccountsPanel(api_client=ac, toast_manager=tm, email_accounts_api=eaa)
        def _ss_settings(ac, tm):
            from ui.admin.panels.smartscan_settings import SmartScanSettingsPanel
            return SmartScanSettingsPanel(api_client=ac, toast_manager=tm, smartscan_api=ssa, email_accounts_api=eaa)
        def _ss_history(ac, tm):
            from ui.admin.panels.smartscan_history import SmartScanHistoryPanel
            return SmartScanHistoryPanel(api_client=ac, toast_manager=tm, smartscan_api=ssa)
        def _email_inbox(ac, tm):
            from ui.admin.panels.email_inbox import EmailInboxPanel
            return EmailInboxPanel(api_client=ac, toast_manager=tm, email_accounts_api=eaa)

        return [
            ("KI-Klassifikation", _ai_class),
            ("KI-Provider", _ai_prov),
            ("Modell-Preise", _model_price),
            ("Dokumenten-Regeln", _doc_rules),
            ("E-Mail-Konten", _email_acc),
            ("Smart!Scan Einstellungen", _ss_settings),
            ("Smart!Scan Historie", _ss_history),
            ("E-Mail Posteingang", _email_inbox),
        ]

    _DEFERRED_RESET_DELAY_MS = 220

    def _reset_leaving_module(self):
        """Setzt den aktuell aktiven Hub in seinen Default-Zustand zurueck.

        Stellt sicher, dass versteckte Sidebars (z.B. wenn der User im
        Admin-Bereich innerhalb des Core-Moduls war) wieder sichtbar sind,
        damit beim naechsten Oeffnen des Moduls kein inkonsistenter Zustand
        entsteht.
        """
        if self._active_module == "core" and self._core_widget is not None:
            self._core_widget.reset_to_default_view()

    def _deferred_reset_leaving_module(self):
        """Fuehrt den Modul-Reset verzoegert aus.

        Wird nach der Exit-Animation aufgerufen. Die kurze Pause laesst
        laufende Fade-/Expand-Animationen sauber abklingen, bevor das
        (nicht mehr sichtbare) Modul-Widget umgebaut wird.
        """
        module = self._pending_reset_module
        self._pending_reset_module = None
        if module == "core" and self._core_widget is not None:
            QTimer.singleShot(
                self._DEFERRED_RESET_DELAY_MS,
                self._core_widget.reset_to_default_view,
            )

    # ------------------------------------------------------------------
    # Module Heartbeat Lifecycle
    # ------------------------------------------------------------------

    def _start_module_heartbeat(self, widget, module_id: str):
        self._active_module = module_id
        if widget and hasattr(widget, 'start_module_heartbeat'):
            hb_logger.info(f"[MODULE:{module_id.upper()}] START angefordert")
            widget.start_module_heartbeat()

    def _stop_active_module_heartbeat(self):
        if not self._active_module:
            return
        widget = self._get_active_module_widget()
        if widget and hasattr(widget, 'stop_module_heartbeat'):
            hb_logger.info(f"[MODULE:{self._active_module.upper()}] STOP angefordert")
            widget.stop_module_heartbeat()

    def _get_active_module_widget(self):
        if self._active_module == "core":
            return self._core_widget
        elif self._active_module == "ledger":
            return self._ledger_widget
        elif self._active_module == "workforce":
            return self._workforce_widget
        elif self._active_module == "contact":
            return self._contact_widget
        return None

    # ------------------------------------------------------------------
    # Global Heartbeat Callbacks
    # ------------------------------------------------------------------

    def _on_session_invalid(self):
        logger.warning("GlobalHeartbeat: Session ungueltig -- Forced Logout")
        self._heartbeat.stop()
        self._stop_active_module_heartbeat()
        if hasattr(self.api_client, '_trigger_forced_logout'):
            self.api_client._trigger_forced_logout("Session abgelaufen")
        else:
            self.auth_api.logout()
            self.close()

    def _on_notifications_updated(self, summary: dict):
        self._dashboard.on_notifications_updated(summary)
        if self._core_widget and hasattr(self._core_widget, 'on_notifications_updated'):
            self._core_widget.on_notifications_updated(summary)

    def _on_system_status_changed(self, status: str, message: str):
        if self._core_widget and hasattr(self._core_widget, 'on_system_status_changed'):
            self._core_widget.on_system_status_changed(status, message)

    def _on_modules_updated(self):
        """Reagiert auf Modul-Aenderungen: Sidebar + Dashboard aktualisieren, ggf. Modul schliessen."""
        user = self.auth_api.current_user
        if not user:
            return

        visible = []
        if user.has_module("core"):
            visible.append("core")
        if user.is_admin:
            visible.append("admin")
        if user.has_module("provision"):
            visible.append("ledger")
        if user.has_module("workforce"):
            visible.append("workforce")
        if user.has_module("contact"):
            visible.append("contact")
        if user.is_module_admin("core"):
            visible.append("core_admin")
        if user.is_module_admin("provision"):
            visible.append("ledger_admin")
        if user.is_module_admin("workforce"):
            visible.append("workforce_admin")
        if user.is_module_admin("contact"):
            visible.append("contact_admin")

        # Diff-Guard: Sidebar und Dashboard nur aktualisieren wenn sich Module tatsaechlich geaendert haben
        visible_hash = tuple(sorted(visible))
        prev_hash = getattr(self, '_prev_visible_modules_hash', None)
        if visible_hash != prev_hash:
            self._prev_visible_modules_hash = visible_hash
            self._dashboard.set_modules(visible)
            self._sidebar.update_modules(user)

        module_check = {
            "core": lambda: user.has_module("core"),
            "ledger": lambda: user.has_module("provision"),
            "workforce": lambda: user.has_module("workforce"),
            "contact": lambda: user.has_module("contact"),
        }

        if self._active_module and self._active_module in module_check:
            if not module_check[self._active_module]():
                logger.warning(f"Modul-Zugriff entzogen: {self._active_module} -- zurueck zum Dashboard")
                self.show_dashboard()
                if hasattr(self, '_toast_manager') and self._toast_manager:
                    from i18n import de as texts
                    self._toast_manager.show_warning(texts.MODULE_NOT_ENABLED)

    # ------------------------------------------------------------------
    # Lazy Init
    # ------------------------------------------------------------------

    def _ensure_core(self):
        if self._core_widget is not None:
            return
        from ui.main_hub import MainHub
        hub = MainHub(api_client=self.api_client, auth_api=self.auth_api)
        hub.back_to_dashboard_requested.connect(self.show_dashboard)
        self._core_widget = hub

        self._replace_stack_placeholder(_IDX_CORE, hub)

    def _ensure_ledger(self):
        if self._ledger_widget is not None:
            return
        try:
            from ui.provision.provision_hub import ProvisionHub
            widget = ProvisionHub(self.api_client, self.auth_api)
            widget._toast_manager = self._toast_manager
            widget.back_requested.connect(self.show_dashboard)
        except Exception:
            logger.exception("ProvisionHub konnte nicht geladen werden, zeige Placeholder")
            widget = self._create_ledger_placeholder()
        self._ledger_widget = widget

        self._replace_stack_placeholder(_IDX_LEDGER, widget)

    def _ensure_workforce(self):
        if self._workforce_widget is not None:
            return
        try:
            from ui.workforce.workforce_hub import WorkforceHub
            widget = WorkforceHub(self.api_client, self.auth_api)
            widget._toast_manager = self._toast_manager
            widget.back_requested.connect(self.show_dashboard)
        except Exception:
            logger.exception("WorkforceHub konnte nicht geladen werden, zeige Placeholder")
            widget = self._create_workforce_placeholder()
        self._workforce_widget = widget

        self._replace_stack_placeholder(_IDX_WORKFORCE, widget)

    # ------------------------------------------------------------------
    # Call-Pop (Teams PSTN Screen-Pop)
    # ------------------------------------------------------------------

    def handle_call_pop(self, phone: str):
        """Eingehender PSTN-Anruf: Contact-Modul oeffnen und Overlay triggern."""
        user = self.auth_api.current_user
        if not user or not user.has_module('contact'):
            logger.warning("[CALL-POP] Contact-Modul nicht freigeschaltet")
            return

        result = self._call_runtime.validate_call_pop(phone, source="core")
        if result.status != CallValidationStatus.OK:
            return

        self._stop_active_module_heartbeat()
        self._reset_leaving_module()
        self._ensure_contact()

        if self._contact_widget:
            cs = getattr(self._contact_widget, '_sidebar', None) or getattr(self._contact_widget, '_sidebar_frame', None)
            if isinstance(cs, ModuleSidebar):
                cs.reset_animation_state()

        self._stack.set_animated(False)
        self._stack.setCurrentIndex(_IDX_CONTACT)
        self._stack.set_animated(True)
        self._active_module = "contact"

        if self._sidebar._is_expanded:
            self._sidebar.set_expanded(False)

        self._play_module_sidebar_enter()

        QTimer.singleShot(0, lambda: self._start_module_heartbeat(self._contact_widget, "contact"))
        if hasattr(self._contact_widget, 'handle_call_pop'):
            self._contact_widget.handle_call_pop(result.phone_normalized or phone)
        self._bring_window_to_front()

    def handle_call_pop_refocus(self):
        """Duplikat-Anruf: nur Fenster nach vorne."""
        self._bring_window_to_front()

    def _bring_window_to_front(self):
        """Bringt das Hauptfenster zuverlaessig in den Vordergrund."""
        if self.isMinimized():
            self.setWindowState(self.windowState() & ~Qt.WindowMinimized)
        self.raise_()
        self.activateWindow()
        QApplication.alert(self, 5000)

    def _ensure_contact(self):
        if self._contact_widget is not None:
            return
        try:
            from ui.contact.contact_hub import ContactHub
            widget = ContactHub(self.api_client, self.auth_api)
            widget._toast_manager = self._toast_manager
            widget.back_requested.connect(self.show_dashboard)
        except Exception:
            logger.exception("ContactHub konnte nicht geladen werden, zeige Placeholder")
            widget = self._create_contact_placeholder()
        self._contact_widget = widget

        self._replace_stack_placeholder(_IDX_CONTACT, widget)

    def _replace_stack_placeholder(self, index: int, widget: QWidget):
        """Ersetzt einen Placeholder im Stack mit setUpdatesEnabled-Guard."""
        self._stack.setUpdatesEnabled(False)
        try:
            old = self._stack.widget(index)
            self._stack.removeWidget(old)
            old.deleteLater()
            self._stack.insertWidget(index, widget)
        finally:
            self._stack.setUpdatesEnabled(True)

    def _create_contact_placeholder(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setAlignment(Qt.AlignCenter)
        lbl = QLabel(texts.CONTACT_DASHBOARD_TILE)
        lbl.setStyleSheet(
            f"font-family: {FONT_BODY}; font-size: {FONT_SIZE_BODY}; color: {PRIMARY_500};"
        )
        layout.addWidget(lbl, alignment=Qt.AlignCenter)
        w.setStyleSheet(f"background-color: {BG_PRIMARY};")
        return w

    def _create_workforce_placeholder(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setAlignment(Qt.AlignCenter)
        lbl = QLabel(texts.WF_DASHBOARD_TILE)
        lbl.setStyleSheet(
            f"font-family: {FONT_BODY}; font-size: {FONT_SIZE_BODY}; color: {PRIMARY_500};"
        )
        layout.addWidget(lbl, alignment=Qt.AlignCenter)
        w.setStyleSheet(f"background-color: {BG_PRIMARY};")
        return w

    def _create_ledger_placeholder(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setAlignment(Qt.AlignCenter)
        lbl = QLabel(texts.DASHBOARD_TILE_LEDGER)
        lbl.setStyleSheet(
            f"font-family: {FONT_BODY}; font-size: {FONT_SIZE_BODY}; color: {PRIMARY_500};"
        )
        layout.addWidget(lbl, alignment=Qt.AlignCenter)
        w.setStyleSheet(f"background-color: {BG_PRIMARY};")
        return w

    # ------------------------------------------------------------------
    # System Tray
    # ------------------------------------------------------------------

    def setup_tray_icon(self):
        """Erstellt das System-Tray-Icon mit Kontextmenue."""
        icon_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "assets", "icon.ico"
        )
        icon = QIcon(icon_path) if os.path.exists(icon_path) else QIcon()

        self._tray_icon = QSystemTrayIcon(icon, self)
        self._tray_icon.setToolTip(texts.TRAY_TOOLTIP)

        tray_menu = QMenu()
        show_action = QAction(texts.TRAY_SHOW_WINDOW, self)
        show_action.triggered.connect(self._tray_show_window)
        tray_menu.addAction(show_action)

        tray_menu.addSeparator()

        quit_action = QAction(texts.TRAY_QUIT, self)
        quit_action.triggered.connect(self._tray_quit)
        tray_menu.addAction(quit_action)

        self._tray_icon.setContextMenu(tray_menu)
        self._tray_icon.activated.connect(self._on_tray_activated)
        self._tray_icon.show()

        self._force_quit = False

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._tray_show_window()

    def _tray_show_window(self):
        """Fenster aus dem Tray wiederherstellen."""
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _tray_quit(self):
        """App komplett beenden (ueber Tray-Menue)."""
        self._force_quit = True
        self.close()

    def closeEvent(self, event: QCloseEvent):
        """Fenster verstecken statt App beenden (Minimize-to-Tray)."""
        if getattr(self, '_force_quit', False):
            self._heartbeat.stop()
            self._stop_active_module_heartbeat()
            if hasattr(self, '_tray_icon'):
                self._tray_icon.hide()
            event.accept()
            QApplication.instance().quit()
            return

        if hasattr(self, '_tray_icon') and self._tray_icon.isVisible():
            self.hide()
            event.ignore()
            return

        event.accept()

    # ------------------------------------------------------------------
    # Logout
    # ------------------------------------------------------------------

    def _on_logout(self):
        reply = QMessageBox.question(
            self,
            texts.NAV_ABMELDEN,
            texts.LOGOUT_CONFIRM
            if hasattr(texts, "LOGOUT_CONFIRM")
            else "Wirklich abmelden?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._force_quit = True
            self._heartbeat.stop()
            self._stop_active_module_heartbeat()
            self.auth_api.logout()
            self.close()

    def _on_forced_logout(self):
        self._force_quit = True
        self._heartbeat.stop()
        self._stop_active_module_heartbeat()
        self.auth_api.logout()
        self.close()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _read_version() -> str:
        try:
            import main as _m
            return getattr(_m, "APP_VERSION", "")
        except Exception:
            return ""
