"""
Workforce Hub - Hauptansicht mit eigener Sidebar.

Eigener Hub analog ProvisionHub mit 7 Panels in 2 Sektionen
(DATEN / VERWALTUNG). Lazy-Loading aller Panels.
"""

import json
import hashlib
import logging

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QFrame, QPushButton,
    QLabel,
)
from ui.components.fade_stacked_widget import FadeStackedWidget
from PySide6.QtCore import Signal, Qt, QTimer, QThreadPool, QObject, QRunnable

from api.client import APIClient
from api.auth import AuthAPI
from workforce.api_client import WorkforceApiClient
from ui.components.module_sidebar import ModuleSidebar, ModuleNavButton
from ui.styles.tokens import (
    SIDEBAR_BG, SIDEBAR_TEXT, SIDEBAR_HOVER, SIDEBAR_WIDTH_INT,
    ACCENT_500, PRIMARY_500, PRIMARY_0, PRIMARY_900,
    FONT_BODY, FONT_SIZE_BODY, FONT_SIZE_CAPTION,
)
from i18n import de as texts

logger = logging.getLogger(__name__)
hb_logger = logging.getLogger('heartbeat.workforce')


class _FingerprintSignals(QObject):
    result = Signal(str)


class _DataFingerprintWorker(QRunnable):
    """Holt im Hintergrund einen Fingerprint der Workforce-Daten."""

    def __init__(self, wf_api):
        super().__init__()
        self.signals = _FingerprintSignals()
        self._wf_api = wf_api
        self.setAutoDelete(True)

    def run(self):
        try:
            employers = self._wf_api.get_employers()
            if not employers:
                self.signals.result.emit("empty")
                return
            raw = json.dumps(
                sorted(employers, key=lambda e: e.get('id', 0)),
                sort_keys=True, default=str,
            )
            fp = hashlib.sha256(raw.encode()).hexdigest()
            self.signals.result.emit(fp)
        except Exception:
            self.signals.result.emit("")


_WfNavButton = ModuleNavButton


class WorkforceHub(QWidget):
    """Workforce-Hauptansicht mit eigener Sidebar und 7 Panels."""

    back_requested = Signal()

    PANEL_EMPLOYERS = 0
    PANEL_EMPLOYEES = 1
    PANEL_EXPORTS = 2
    PANEL_SNAPSHOTS = 3
    PANEL_STATS = 4
    PANEL_TRIGGERS = 5
    PANEL_SMTP = 6
    _TOTAL_PANELS = 7

    _PANEL_NAMES = {
        0: "employers", 1: "employees", 2: "exports",
        3: "snapshots", 4: "stats", 5: "triggers", 6: "smtp",
    }

    _MODULE_HEARTBEAT_INTERVAL = 15_000

    def __init__(self, api_client: APIClient, auth_api: AuthAPI):
        super().__init__()
        self._api_client = api_client
        self._auth_api = auth_api
        self._wf_api = WorkforceApiClient(api_client)
        self._toast_manager = None
        self._nav_buttons: list[_WfNavButton] = []
        self._panels_loaded: set[int] = set()
        self._thread_pool = QThreadPool.globalInstance()
        self._refresh_guard = False
        self._initial_loaded = False
        self._last_data_fingerprint = ""
        self._fingerprint_check_running = False

        self._module_heartbeat_timer = QTimer(self)
        self._module_heartbeat_timer.timeout.connect(self._on_module_heartbeat_tick)

        user = self._auth_api.current_user
        if not user or not user.has_module('workforce'):
            logger.warning("WorkforceHub ohne Modul-Freischaltung geladen")
            return

        self._setup_ui()

    def _setup_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._sidebar = ModuleSidebar("wf_sidebar", parent=self)
        self._sidebar.back_requested.connect(self.back_requested.emit)

        self._sidebar.add_section_label(texts.WF_SECTION_DATA)

        self._sidebar.add_nav("\u203A", texts.WF_NAV_EMPLOYERS, texts.WF_NAV_EMPLOYERS_DESC, self.PANEL_EMPLOYERS, self._navigate_to)
        self._sidebar.add_nav("\u203A", texts.WF_NAV_EMPLOYEES, texts.WF_NAV_EMPLOYEES_DESC, self.PANEL_EMPLOYEES, self._navigate_to)
        self._sidebar.add_nav("\u203A", texts.WF_NAV_EXPORTS, texts.WF_NAV_EXPORTS_DESC, self.PANEL_EXPORTS, self._navigate_to)
        self._sidebar.add_nav("\u203A", texts.WF_NAV_SNAPSHOTS, texts.WF_NAV_SNAPSHOTS_DESC, self.PANEL_SNAPSHOTS, self._navigate_to)
        self._sidebar.add_nav("\u203A", texts.WF_NAV_STATS, texts.WF_NAV_STATS_DESC, self.PANEL_STATS, self._navigate_to)

        user = self._auth_api.current_user
        has_trigger_perm = user and (user.has_permission('hr.triggers') or user.is_module_admin('workforce'))

        if has_trigger_perm:
            self._sidebar.add_separator()
            self._sidebar.add_section_label(texts.WF_SECTION_ADMIN)
            self._sidebar.add_nav("\u203A", texts.WF_NAV_TRIGGERS, texts.WF_NAV_TRIGGERS_DESC, self.PANEL_TRIGGERS, self._navigate_to)
            self._sidebar.add_nav("\u203A", texts.WF_NAV_SMTP, texts.WF_NAV_SMTP_DESC, self.PANEL_SMTP, self._navigate_to)

        if user and user.is_module_admin('workforce'):
            self._sidebar.add_separator()
            ma_btn = ModuleNavButton("\U0001F6E0", texts.MODULE_ADMIN_BTN, "")
            ma_btn.clicked.connect(self._show_workforce_module_admin)
            self._sidebar.add_widget(ma_btn)

        self._sidebar.add_stretch()
        self._sidebar.add_refresh_button(texts.WF_REFRESH, lambda: self._refresh_all(show_toast=True))

        self._nav_buttons = self._sidebar.nav_buttons
        root.addWidget(self._sidebar)

        self._content_stack = FadeStackedWidget(fade_out_ms=80, fade_in_ms=120)
        for i in range(self._TOTAL_PANELS):
            self._content_stack.addWidget(self._create_placeholder())
        root.addWidget(self._content_stack)

        if self._nav_buttons:
            self._nav_buttons[0].setChecked(True)

    def _create_placeholder(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setAlignment(Qt.AlignCenter)
        lbl = QLabel(texts.LOADING)
        lbl.setStyleSheet(f"color: {PRIMARY_500}; font-size: 14pt; font-family: {FONT_BODY};")
        lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl)
        return w

    def _navigate_to(self, index: int):
        for i, btn in enumerate(self._nav_buttons):
            btn.setChecked(i == index)
        self._ensure_panel_loaded(index)
        self._content_stack.setCurrentIndex(index)

    def _ensure_panel_loaded(self, index: int):
        if index in self._panels_loaded:
            return
        self._panels_loaded.add(index)

        panel = None
        try:
            if index == self.PANEL_EMPLOYERS:
                from ui.workforce.employers_view import EmployersView
                panel = EmployersView(self._wf_api, self._auth_api)
            elif index == self.PANEL_EMPLOYEES:
                from ui.workforce.employees_view import EmployeesView
                panel = EmployeesView(self._wf_api, self._thread_pool)
            elif index == self.PANEL_EXPORTS:
                from ui.workforce.exports_view import ExportsView
                panel = ExportsView(self._wf_api, self._thread_pool)
            elif index == self.PANEL_SNAPSHOTS:
                from ui.workforce.snapshots_view import SnapshotsView
                panel = SnapshotsView(self._wf_api)
            elif index == self.PANEL_STATS:
                from ui.workforce.stats_view import StatsView
                panel = StatsView(self._wf_api, self._thread_pool)
            elif index == self.PANEL_TRIGGERS:
                from ui.workforce.triggers_view import TriggersView
                panel = TriggersView(self._wf_api)
            elif index == self.PANEL_SMTP:
                from ui.workforce.smtp_view import SmtpView
                panel = SmtpView(self._wf_api)
        except Exception as e:
            logger.error("Fehler beim Laden eines Workforce-Panels")
            self._panels_loaded.discard(index)
            return

        if panel:
            if self._toast_manager and hasattr(panel, '_toast_manager'):
                panel._toast_manager = self._toast_manager
            old = self._content_stack.widget(index)
            self._content_stack.removeWidget(old)
            old.deleteLater()
            self._content_stack.insertWidget(index, panel)
            self._content_stack.setCurrentIndex(index)

    def _refresh_all(self, show_toast: bool = True):
        if self._refresh_guard:
            return
        self._refresh_guard = True
        QTimer.singleShot(1500, self._release_refresh_guard)

        for index in list(self._panels_loaded):
            panel = self._content_stack.widget(index)
            if panel and hasattr(panel, 'refresh'):
                try:
                    panel.refresh()
                except Exception as e:
                    logger.debug(f"Refresh Panel {index}: {e}")
        if show_toast and self._toast_manager:
            self._toast_manager.show_success(texts.WF_REFRESH_DONE)

    def _release_refresh_guard(self):
        self._refresh_guard = False

    # ------------------------------------------------------------------
    # Module Heartbeat (gesteuert durch AppRouter)
    # ------------------------------------------------------------------

    def start_module_heartbeat(self):
        """Startet Initial-Load und periodischen Heartbeat (15s)."""
        if not self._initial_loaded:
            self._initial_load_all_panels()
            self._initial_loaded = True
        if not self._module_heartbeat_timer.isActive():
            self._module_heartbeat_timer.start(self._MODULE_HEARTBEAT_INTERVAL)
            hb_logger.info(f"[WORKFORCE] START (Intervall={self._MODULE_HEARTBEAT_INTERVAL}ms)")

    def stop_module_heartbeat(self):
        """Stoppt den periodischen Heartbeat."""
        self._module_heartbeat_timer.stop()
        hb_logger.info("[WORKFORCE] STOP")

    def _initial_load_all_panels(self):
        """Laedt das Default-Panel sofort, Rest gestaffelt (1 pro Frame)."""
        user = self._auth_api.current_user
        has_trigger_perm = user and (user.has_permission('hr.triggers') or user.is_module_admin('workforce'))
        max_panel = self._TOTAL_PANELS if has_trigger_perm else self.PANEL_STATS + 1

        default_idx = self.PANEL_EMPLOYERS
        self._ensure_panel_loaded(default_idx)
        panel = self._content_stack.widget(default_idx)
        if panel and hasattr(panel, 'refresh'):
            try:
                panel.refresh()
            except Exception as e:
                logger.debug(f"Initial refresh Panel {default_idx}: {e}")
        self._navigate_to(default_idx)
        remaining = [i for i in range(max_panel) if i != default_idx]
        self._load_panels_staggered(remaining, 0)

    def _load_panels_staggered(self, indices: list, pos: int):
        """Laedt jeweils ein Panel pro Event-Loop-Durchlauf."""
        if pos >= len(indices):
            return
        idx = indices[pos]
        self._ensure_panel_loaded(idx)
        panel = self._content_stack.widget(idx)
        if panel and hasattr(panel, 'refresh'):
            try:
                panel.refresh()
            except Exception as e:
                logger.debug(f"Staggered refresh Panel {idx}: {e}")
        QTimer.singleShot(0, lambda: self._load_panels_staggered(indices, pos + 1))

    def _on_module_heartbeat_tick(self):
        """Prueft im Hintergrund ob sich Daten geaendert haben."""
        hb_logger.info("[WORKFORCE] TICK")
        if self._fingerprint_check_running:
            return
        self._fingerprint_check_running = True
        worker = _DataFingerprintWorker(self._wf_api)
        worker.signals.result.connect(self._on_fingerprint_result)
        self._thread_pool.start(worker)

    def _on_fingerprint_result(self, fingerprint: str):
        self._fingerprint_check_running = False
        if not fingerprint:
            return
        if not self._last_data_fingerprint:
            self._last_data_fingerprint = fingerprint
            return
        if fingerprint != self._last_data_fingerprint:
            self._last_data_fingerprint = fingerprint
            self._refresh_all(show_toast=False)

    def _show_workforce_module_admin(self):
        """Oeffnet die Workforce-Modul-Verwaltung."""
        if not hasattr(self, '_module_admin_view') or self._module_admin_view is None:
            from ui.module_admin import ModuleAdminShell
            self._module_admin_view = ModuleAdminShell(
                module_key='workforce', module_name='Workforce',
                api_client=self._api_client, auth_api=self._auth_api,
            )
            self._module_admin_view._toast_manager = getattr(self, '_toast_manager', None)
            self._module_admin_view.back_requested.connect(self._leave_workforce_module_admin)
            self._content_stack.addWidget(self._module_admin_view)
        idx = self._content_stack.indexOf(self._module_admin_view)
        self._content_stack.setCurrentIndex(idx)
        self._module_admin_view.load_data()

    def _leave_workforce_module_admin(self):
        self._navigate_to(self.PANEL_EMPLOYERS)
