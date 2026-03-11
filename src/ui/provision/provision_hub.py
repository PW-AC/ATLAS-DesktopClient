"""
Provisionsmanagement Hub - Hauptansicht mit eigener Sidebar.

UX-Redesign v3.2: 10 Panels in 2 Sektionen (DATEN / VERWALTUNG),
Workflow-orientierte Reihenfolge, klare Benennung.
"""

import json
import hashlib

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QFrame, QPushButton,
    QStackedWidget, QLabel, QSizePolicy,
)
from PySide6.QtCore import Signal, Qt, QTimer, QObject, QRunnable, QThreadPool

from api.client import APIClient
from api.auth import AuthAPI
from api.provision import ProvisionAPI
from infrastructure.api.provision_repository import ProvisionRepository
from infrastructure.cache.provision_cache import ProvisionCache
from infrastructure.threading.freeze_detector import FreezeDetector
from presenters.provision.positions_presenter import PositionsPresenter
from presenters.provision.dashboard_presenter import DashboardPresenter
from presenters.provision.import_presenter import ImportPresenter
from presenters.provision.clearance_presenter import ClearancePresenter
from presenters.provision.distribution_presenter import DistributionPresenter
from presenters.provision.payouts_presenter import PayoutsPresenter
from presenters.provision.free_commission_presenter import FreeCommissionPresenter
from presenters.provision.performance_presenter import PerformancePresenter
from ui.styles.tokens import (
    SIDEBAR_BG, SIDEBAR_TEXT, SIDEBAR_HOVER, SIDEBAR_WIDTH_INT,
    ACCENT_500, PRIMARY_500, PRIMARY_0, PRIMARY_900,
    FONT_BODY, FONT_SIZE_BODY, FONT_SIZE_CAPTION,
    BORDER_SUBTLE,
)
from i18n import de as texts

import logging

logger = logging.getLogger(__name__)
hb_logger = logging.getLogger('heartbeat.ledger')


class _ProvFingerprintSignals(QObject):
    result = Signal(str)


class _ProvDataFingerprintWorker(QRunnable):
    """Holt im Hintergrund einen Fingerprint der Provisions-Daten."""

    def __init__(self, provision_api):
        super().__init__()
        self.signals = _ProvFingerprintSignals()
        self._api = provision_api
        self.setAutoDelete(True)

    def run(self):
        try:
            batches = self._api.get_import_batches()
            raw = json.dumps(
                [{'id': b.id, 'status': b.status, 'row_count': b.row_count}
                 for b in batches] if batches else [],
                sort_keys=True, default=str,
            )
            fp = hashlib.md5(raw.encode()).hexdigest()
            self.signals.result.emit(fp)
        except RuntimeError:
            pass
        except Exception:
            try:
                self.signals.result.emit("")
            except RuntimeError:
                pass


class ProvisionNavButton(QPushButton):
    """Navigations-Button mit optionalem Subtext fuer die Provisions-Sidebar."""

    def __init__(self, icon: str, text: str, subtitle: str = "", parent=None):
        super().__init__(parent)
        self._title = text
        self._subtitle = subtitle
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)

        if subtitle:
            display = f"   {icon}  {text}\n        {subtitle}"
            self.setMinimumHeight(56)
        else:
            display = f"   {icon}  {text}"
            self.setMinimumHeight(40)

        self.setText(display)
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                border-left: 3px solid transparent;
                border-radius: 0px;
                padding: 8px 20px;
                text-align: left;
                font-family: {FONT_BODY};
                font-size: {FONT_SIZE_CAPTION};
                color: {PRIMARY_500};
                line-height: 1.4;
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


class ProvisionHub(QWidget):
    """Provisionsmanagement-Hauptansicht mit eigener Sidebar und 10 Panels."""

    back_requested = Signal()

    PANEL_OVERVIEW = 0
    PANEL_PERFORMANCE = 1
    PANEL_IMPORT = 2
    PANEL_VU = 3
    PANEL_XEMPUS = 4
    PANEL_FREE = 5
    PANEL_CLEARANCE = 6
    PANEL_DISTRIBUTION = 7
    PANEL_PAYOUTS = 8
    PANEL_SETTINGS = 9

    PANEL_RUNS = PANEL_IMPORT
    PANEL_POSITIONS = PANEL_VU
    _TOTAL_PANELS = 10

    _MODULE_HEARTBEAT_INTERVAL = 15_000

    def __init__(self, api_client: APIClient, auth_api: AuthAPI):
        super().__init__()
        self._api_client = api_client
        self._auth_api = auth_api
        self._provision_api = ProvisionAPI(api_client)
        self._toast_manager = None
        self._nav_buttons = []
        self._panels_loaded = set()
        self._initial_loaded = False
        self._last_data_fingerprint = ""
        self._fingerprint_check_running = False
        self._thread_pool = QThreadPool.globalInstance()

        self._freeze_detector = FreezeDetector(self)
        self._refresh_guard = False

        self._module_heartbeat_timer = QTimer(self)
        self._module_heartbeat_timer.timeout.connect(self._on_module_heartbeat_tick)

        self._repository = ProvisionRepository(api_client)
        self._presenters = {
            'positions': PositionsPresenter(self._repository),
            'dashboard': DashboardPresenter(self._repository),
            'import': ImportPresenter(self._repository),
            'clearance': ClearancePresenter(self._repository),
            'distribution': DistributionPresenter(self._repository),
            'payouts': PayoutsPresenter(self._repository),
            'free_commission': FreeCommissionPresenter(self._repository),
            'performance': PerformancePresenter(self._repository),
        }

        user = self._auth_api.current_user
        if not user or not user.has_module('provision'):
            logger.warning("ProvisionHub ohne Modul-Freischaltung geladen")
            return

        self._setup_ui()
        self._freeze_detector.start()
        self._freeze_detector.set_context("provision_hub:init")

    def _setup_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("provision_sidebar")
        sidebar.setFixedWidth(SIDEBAR_WIDTH_INT)
        sidebar.setStyleSheet(f"""
            QFrame#provision_sidebar {{
                background-color: {SIDEBAR_BG};
                border-right: 1px solid {BORDER_SUBTLE};
            }}
        """)

        sb_layout = QVBoxLayout(sidebar)
        sb_layout.setContentsMargins(0, 8, 0, 8)
        sb_layout.setSpacing(0)

        back_btn = QPushButton(f"  \u2190  {texts.DASHBOARD_BACK}")
        back_btn.setCursor(Qt.PointingHandCursor)
        back_btn.setMinimumHeight(44)
        back_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                border-bottom: 1px solid {BORDER_SUBTLE};
                padding: 10px 16px;
                text-align: left;
                font-family: {FONT_BODY};
                font-size: {FONT_SIZE_BODY};
                color: {ACCENT_500};
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {SIDEBAR_HOVER};
            }}
        """)
        back_btn.clicked.connect(self.back_requested.emit)
        sb_layout.addWidget(back_btn)
        sb_layout.addSpacing(12)

        def add_nav(icon: str, title: str, subtitle: str, index: int) -> ProvisionNavButton:
            btn = ProvisionNavButton(icon, title, subtitle)
            btn.clicked.connect(lambda checked, i=index: self._navigate_to(i))
            sb_layout.addWidget(btn)
            self._nav_buttons.append(btn)
            return btn

        add_nav("\u203A", texts.PROVISION_PANEL_OVERVIEW, texts.PROVISION_PANEL_OVERVIEW_DESC, self.PANEL_OVERVIEW)
        add_nav("\u203A", texts.PM_PERF_PANEL_TITLE, texts.PM_PERF_PANEL_DESC, self.PANEL_PERFORMANCE)

        section_daten = QLabel(f"  {texts.PROVISION_SECTION_DATA}")
        section_daten.setStyleSheet(f"""
            color: {ACCENT_500}; font-family: {FONT_BODY};
            font-size: 9pt; font-weight: 700; letter-spacing: 1px;
            padding: 12px 16px 4px 16px;
        """)
        sb_layout.addWidget(section_daten)

        add_nav("\u203A", texts.PROVISION_PANEL_IMPORT, texts.PROVISION_PANEL_IMPORT_DESC, self.PANEL_IMPORT)
        add_nav("\u203A", texts.PROVISION_PANEL_VU, texts.PROVISION_PANEL_VU_DESC, self.PANEL_VU)
        add_nav("\u203A", texts.PROVISION_PANEL_XEMPUS, texts.PROVISION_PANEL_XEMPUS_DESC, self.PANEL_XEMPUS)
        add_nav("\u203A", texts.PM_FREE_PANEL_TITLE, texts.PM_FREE_PANEL_DESC, self.PANEL_FREE)

        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background-color: {ACCENT_500}; margin: 8px 16px;")
        sb_layout.addWidget(sep)

        section_admin = QLabel(f"  {texts.PROVISION_SECTION_ADMIN}")
        section_admin.setStyleSheet(f"""
            color: {ACCENT_500}; font-family: {FONT_BODY};
            font-size: 9pt; font-weight: 700; letter-spacing: 1px;
            padding: 8px 16px 4px 16px;
        """)
        sb_layout.addWidget(section_admin)

        add_nav("\u203A", texts.PROVISION_PANEL_CLEARANCE, texts.PROVISION_PANEL_CLEARANCE_DESC, self.PANEL_CLEARANCE)
        add_nav("\u203A", texts.PROVISION_PANEL_DISTRIBUTION, texts.PROVISION_PANEL_DISTRIBUTION_DESC, self.PANEL_DISTRIBUTION)
        add_nav("\u203A", texts.PROVISION_PANEL_PAYOUTS, texts.PROVISION_PANEL_PAYOUTS_DESC, self.PANEL_PAYOUTS)

        sep2 = QFrame()
        sep2.setFixedHeight(1)
        sep2.setStyleSheet(f"background-color: {ACCENT_500}; margin: 8px 16px;")
        sb_layout.addWidget(sep2)

        add_nav("\u26A0\uFE0F", texts.PROVISION_PANEL_SETTINGS, texts.PROVISION_PANEL_SETTINGS_DESC, self.PANEL_SETTINGS)

        user_pm = self._auth_api.current_user
        if user_pm and user_pm.is_module_admin('provision'):
            sep_admin = QFrame()
            sep_admin.setFixedHeight(1)
            sep_admin.setStyleSheet(f"background-color: {ACCENT_500}; margin: 8px 16px;")
            sb_layout.addWidget(sep_admin)

            admin_btn = ProvisionNavButton("\U0001F6E0", texts.MODULE_ADMIN_BTN, "")
            admin_btn.clicked.connect(self._show_provision_module_admin)
            sb_layout.addWidget(admin_btn)

        sb_layout.addStretch()

        refresh_btn = QPushButton(f"  \u21BB  {texts.PROVISION_HUB_REFRESH}")
        refresh_btn.setToolTip(texts.PROVISION_HUB_REFRESH_TIP)
        refresh_btn.setCursor(Qt.PointingHandCursor)
        refresh_btn.setMinimumHeight(44)
        refresh_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                border-top: 1px solid {BORDER_SUBTLE};
                padding: 10px 16px;
                text-align: left;
                font-family: {FONT_BODY};
                font-size: {FONT_SIZE_CAPTION};
                color: {ACCENT_500};
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {SIDEBAR_HOVER};
            }}
        """)
        refresh_btn.clicked.connect(lambda: self._refresh_all(show_toast=True))
        sb_layout.addWidget(refresh_btn)

        root.addWidget(sidebar)

        self._content_stack = QStackedWidget()
        for i in range(self._TOTAL_PANELS):
            self._content_stack.addWidget(self._create_panel_placeholder(i))
        root.addWidget(self._content_stack)

        self._nav_buttons[0].setChecked(True)

    def _create_panel_placeholder(self, index: int) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setAlignment(Qt.AlignCenter)
        lbl = QLabel(texts.PROVISION_LOADING)
        lbl.setStyleSheet(f"color: {PRIMARY_500}; font-size: 14pt; font-family: {FONT_BODY};")
        lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl)
        return w

    _PANEL_NAMES = {
        0: "overview", 1: "performance", 2: "import", 3: "positions",
        4: "xempus", 5: "free_commission", 6: "clearance",
        7: "distribution", 8: "payouts", 9: "settings",
    }

    def _navigate_to(self, index: int):
        for i, btn in enumerate(self._nav_buttons):
            btn.setChecked(i == index)
        panel_name = self._PANEL_NAMES.get(index, f"panel_{index}")
        self._freeze_detector.set_context(f"provision:{panel_name}")
        self._ensure_panel_loaded(index)
        self._content_stack.setCurrentIndex(index)

    def _ensure_panel_loaded(self, index: int):
        if index in self._panels_loaded:
            return
        self._panels_loaded.add(index)

        panel = None
        try:
            if index == self.PANEL_OVERVIEW:
                from ui.provision.dashboard_panel import DashboardPanel
                panel = DashboardPanel()
                panel.set_presenter(self._presenters['dashboard'])
            elif index == self.PANEL_PERFORMANCE:
                from ui.provision.performance_panel import PerformancePanel
                panel = PerformancePanel()
                panel.set_presenter(self._presenters['performance'])
            elif index == self.PANEL_IMPORT:
                from ui.provision.abrechnungslaeufe_panel import AbrechnungslaeufPanel
                panel = AbrechnungslaeufPanel()
                panel.set_presenter(self._presenters['import'])
            elif index == self.PANEL_VU:
                from ui.provision.provisionspositionen_panel import ProvisionspositionenPanel
                panel = ProvisionspositionenPanel()
                panel.set_presenter(self._presenters['positions'])
            elif index == self.PANEL_XEMPUS:
                from ui.provision.xempus_insight_panel import XempusInsightPanel
                panel = XempusInsightPanel(self._provision_api)
            elif index == self.PANEL_FREE:
                from ui.provision.free_commission_panel import FreeCommissionPanel
                panel = FreeCommissionPanel()
                panel.set_presenter(self._presenters['free_commission'])
            elif index == self.PANEL_CLEARANCE:
                from ui.provision.zuordnung_panel import ZuordnungPanel
                panel = ZuordnungPanel()
                panel.set_presenter(self._presenters['clearance'])
            elif index == self.PANEL_DISTRIBUTION:
                from ui.provision.verteilschluessel_panel import VerteilschluesselPanel
                panel = VerteilschluesselPanel(api_client=self._api_client)
                panel.set_presenter(self._presenters['distribution'])
            elif index == self.PANEL_PAYOUTS:
                from ui.provision.auszahlungen_panel import AuszahlungenPanel
                panel = AuszahlungenPanel()
                panel.set_presenter(self._presenters['payouts'])
            elif index == self.PANEL_SETTINGS:
                from ui.provision.settings_panel import SettingsPanel
                panel = SettingsPanel(self._provision_api)
        except Exception as e:
            logger.error(f"Fehler beim Laden von Panel {index}: {e}")
            self._panels_loaded.discard(index)
            return

        if panel:
            if self._toast_manager and hasattr(panel, '_toast_manager'):
                panel._toast_manager = self._toast_manager
            if hasattr(panel, 'navigate_to_panel'):
                panel.navigate_to_panel.connect(self._navigate_to)
            if hasattr(panel, 'data_changed'):
                panel.data_changed.connect(self._on_panel_data_changed)
            old = self._content_stack.widget(index)
            self._content_stack.removeWidget(old)
            old.deleteLater()
            self._content_stack.insertWidget(index, panel)
            self._content_stack.setCurrentIndex(index)

    def _on_panel_data_changed(self):
        """Daten in einem Panel haben sich geaendert - alle anderen Panels aktualisieren."""
        ProvisionCache.instance().invalidate_all()
        for index in list(self._panels_loaded):
            panel = self._content_stack.widget(index)
            if panel and hasattr(panel, 'refresh'):
                try:
                    panel.refresh()
                except Exception as e:
                    logger.debug(f"Refresh Panel {index} nach data_changed: {e}")

    def _refresh_all(self, show_toast: bool = True):
        """Alle geladenen Panels neu laden (mit Guard gegen Rapid-Fire)."""
        if self._refresh_guard:
            return
        self._refresh_guard = True
        QTimer.singleShot(1500, self._release_refresh_guard)

        ProvisionCache.instance().invalidate_all()
        for index in list(self._panels_loaded):
            panel = self._content_stack.widget(index)
            if panel and hasattr(panel, 'refresh'):
                try:
                    panel.refresh()
                except Exception as e:
                    logger.debug(f"Refresh Panel {index}: {e}")
        if show_toast and self._toast_manager:
            self._toast_manager.show_success(texts.PROVISION_HUB_REFRESH_DONE)

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
            hb_logger.info(f"[LEDGER] START (Intervall={self._MODULE_HEARTBEAT_INTERVAL}ms)")

    def stop_module_heartbeat(self):
        """Stoppt den periodischen Heartbeat."""
        self._module_heartbeat_timer.stop()
        hb_logger.info("[LEDGER] STOP")

    def _initial_load_all_panels(self):
        """Laedt ALLE Panels sofort beim ersten Oeffnen des Moduls."""
        for i in range(self._TOTAL_PANELS):
            self._ensure_panel_loaded(i)
            panel = self._content_stack.widget(i)
            if panel and hasattr(panel, 'refresh'):
                try:
                    panel.refresh()
                except Exception as e:
                    logger.debug(f"Initial refresh Panel {i}: {e}")
        self._navigate_to(self.PANEL_OVERVIEW)

    def _on_module_heartbeat_tick(self):
        """Prueft im Hintergrund ob sich Daten geaendert haben."""
        hb_logger.info("[LEDGER] TICK")
        if self._fingerprint_check_running:
            return
        self._fingerprint_check_running = True
        worker = _ProvDataFingerprintWorker(self._provision_api)
        worker.signals.result.connect(self._on_fingerprint_result)
        self._thread_pool.start(worker)

    def _on_fingerprint_result(self, fingerprint: str):
        self._fingerprint_check_running = False
        if not fingerprint:
            return
        if fingerprint != self._last_data_fingerprint:
            self._last_data_fingerprint = fingerprint
            ProvisionCache.instance().invalidate_all()
            self._refresh_all(show_toast=False)

    def get_blocking_operations(self) -> list:
        """Laufende Operationen die das Schliessen blockieren."""
        ops = []

        for name, presenter in self._presenters.items():
            if presenter and hasattr(presenter, 'has_running_workers'):
                if presenter.has_running_workers():
                    ops.append(texts.PROVISION_BLOCKING_IMPORT if name == 'import'
                               else texts.PROVISION_BLOCKING_WORKER)

        for index in list(self._panels_loaded):
            panel = self._content_stack.widget(index)
            if not panel:
                continue
            for attr in ('_import_worker', '_parse_worker', '_load_worker',
                         '_worker', '_detail_worker', '_audit_worker',
                         '_ignore_worker', '_mapping_worker', '_pos_worker',
                         '_generate_worker', '_save_worker', '_raw_worker'):
                w = getattr(panel, attr, None)
                if w and w.isRunning():
                    ops.append(texts.PROVISION_BLOCKING_WORKER)
                    break
        return ops

    def _show_provision_module_admin(self):
        """Oeffnet die Provision-Modul-Verwaltung."""
        if not hasattr(self, '_module_admin_view') or self._module_admin_view is None:
            from ui.module_admin import ModuleAdminShell
            self._module_admin_view = ModuleAdminShell(
                module_key='provision', module_name='Provision',
                api_client=self._api_client, auth_api=self._auth_api,
            )
            self._module_admin_view._toast_manager = getattr(self, '_toast_manager', None)
            self._module_admin_view.back_requested.connect(self._leave_provision_module_admin)
            self._content_stack.addWidget(self._module_admin_view)
        idx = self._content_stack.indexOf(self._module_admin_view)
        self._content_stack.setCurrentIndex(idx)
        self._module_admin_view.load_data()

    def _leave_provision_module_admin(self):
        self._navigate_to(self.PANEL_OVERVIEW)

    def cleanup(self) -> None:
        """Alle laufenden Worker sicher beenden."""
        self._freeze_detector.stop()
        for presenter in self._presenters.values():
            if presenter and hasattr(presenter, 'cleanup'):
                presenter.cleanup()
