"""
Contact Hub - Hauptansicht mit eigener Sidebar.

Eigener Hub analog WorkforceHub mit 6 Panels in 2 Sektionen
(KONTAKTE / WEITERES). Lazy-Loading aller Panels.
"""

import json
import hashlib
import logging

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QFrame, QPushButton,
    QLabel, QApplication,
)
from ui.components.fade_stacked_widget import FadeStackedWidget
from PySide6.QtCore import Signal, Qt, QTimer, QThreadPool, QObject, QRunnable

from api.client import APIClient
from api.auth import AuthAPI
from contact.api_client import ContactApiClient
from ui.components.module_sidebar import ModuleSidebar, ModuleNavButton
from ui.styles.tokens import (
    SIDEBAR_BG, SIDEBAR_TEXT, SIDEBAR_HOVER, SIDEBAR_WIDTH_INT,
    ACCENT_500, PRIMARY_500, PRIMARY_0, PRIMARY_900,
    FONT_BODY, FONT_SIZE_BODY, FONT_SIZE_CAPTION,
    BORDER_SUBTLE,
)
from i18n import de as texts

logger = logging.getLogger(__name__)
hb_logger = logging.getLogger('heartbeat.contact')


class _ContactFingerprintSignals(QObject):
    result = Signal(str)


class _ContactDataFingerprintWorker(QRunnable):
    """Holt im Hintergrund einen Fingerprint der Contact-Daten."""

    def __init__(self, contact_api: ContactApiClient):
        super().__init__()
        self.signals = _ContactFingerprintSignals()
        self._contact_api = contact_api
        self.setAutoDelete(True)

    def run(self):
        try:
            data = self._contact_api.list_contacts(page=1, per_page=50)
            contacts = data.get('contacts', [])
            if not contacts:
                self.signals.result.emit("empty")
                return
            raw = json.dumps(
                sorted(contacts, key=lambda c: c.get('id', 0)),
                sort_keys=True, default=str,
            )
            fp = hashlib.sha256(raw.encode()).hexdigest()
            self.signals.result.emit(fp)
        except Exception:
            self.signals.result.emit("")


_ContactNavButton = ModuleNavButton


class ContactHub(QWidget):
    """Contact-Hauptansicht mit eigener Sidebar und 6 Panels."""

    back_requested = Signal()

    PANEL_ALL = 0
    PANEL_FAVORITES = 1
    PANEL_RECENT_VIEWED = 2
    PANEL_RECENT_CALLED = 3
    PANEL_CALLBACKS = 4
    PANEL_COMPANIES = 5
    _TOTAL_PANELS = 6

    _PANEL_NAMES = {
        0: "all", 1: "favorites", 2: "recent_viewed",
        3: "recent_called", 4: "callbacks", 5: "companies",
    }

    _MODULE_HEARTBEAT_INTERVAL = 15_000

    def open_quick_call_note(self):
        """Oeffentliche Methode: Schnelle Gespraechsnotiz-Dialog oeffnen."""
        self._on_quick_call_note()

    def __init__(self, api_client: APIClient, auth_api: AuthAPI):
        super().__init__()
        self._api_client = api_client
        self._auth_api = auth_api
        self._contact_api = ContactApiClient(api_client)
        self._toast_manager = None
        self._nav_buttons: list[_ContactNavButton] = []
        self._panels_loaded: set[int] = set()
        self._thread_pool = QThreadPool.globalInstance()
        self._refresh_guard = False
        self._initial_loaded = False
        self._last_data_fingerprint = ""
        self._fingerprint_check_running = False

        self._module_heartbeat_timer = QTimer(self)
        self._module_heartbeat_timer.timeout.connect(self._on_module_heartbeat_tick)

        self._content_stack = None

        user = self._auth_api.current_user
        if not user or not user.has_module('contact'):
            logger.warning("ContactHub ohne Modul-Freischaltung geladen")
            return

        self._setup_ui()

    def _setup_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._sidebar = ModuleSidebar("contact_sidebar", parent=self)
        self._sidebar.back_requested.connect(self.back_requested.emit)

        self._sidebar.add_section_label(texts.CONTACT_SECTION_CONTACTS)

        self._sidebar.add_nav("\u203A", texts.CONTACT_NAV_ALL, "", self.PANEL_ALL, self._navigate_to)
        self._sidebar.add_nav("\u203A", texts.CONTACT_NAV_FAVORITES, "", self.PANEL_FAVORITES, self._navigate_to)
        self._sidebar.add_nav("\u203A", texts.CONTACT_NAV_RECENT_VIEWED, "", self.PANEL_RECENT_VIEWED, self._navigate_to)
        self._sidebar.add_nav("\u203A", texts.CONTACT_NAV_RECENT_CALLED, "", self.PANEL_RECENT_CALLED, self._navigate_to)
        self._sidebar.add_nav("\u203A", texts.CONTACT_NAV_CALLBACKS, "", self.PANEL_CALLBACKS, self._navigate_to)

        self._sidebar.add_separator()

        self._sidebar.add_section_label(texts.CONTACT_SECTION_EXTRA)

        self._sidebar.add_nav("\u203A", texts.CONTACT_NAV_COMPANIES, "", self.PANEL_COMPANIES, self._navigate_to)

        user = self._auth_api.current_user
        if user and user.is_module_admin('contact'):
            self._sidebar.add_separator()
            ma_btn = ModuleNavButton("\U0001F6E0", texts.MODULE_ADMIN_BTN, "")
            ma_btn.clicked.connect(self._show_contact_module_admin)
            self._sidebar.add_widget(ma_btn)

        self._sidebar.add_stretch()
        self._sidebar.add_refresh_button(texts.CONTACT_REFRESH, lambda: self._refresh_all(show_toast=True))

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
            if index == self.PANEL_ALL:
                from ui.contact.contacts_view import ContactsView
                panel = ContactsView(self._contact_api, self._auth_api, 'all', parent=self)
            elif index == self.PANEL_FAVORITES:
                from ui.contact.contacts_view import ContactsView
                panel = ContactsView(self._contact_api, self._auth_api, 'favorites', parent=self)
            elif index == self.PANEL_RECENT_VIEWED:
                from ui.contact.contacts_view import ContactsView
                panel = ContactsView(self._contact_api, self._auth_api, 'recent_viewed', parent=self)
            elif index == self.PANEL_RECENT_CALLED:
                from ui.contact.contacts_view import ContactsView
                panel = ContactsView(self._contact_api, self._auth_api, 'recent_called', parent=self)
            elif index == self.PANEL_CALLBACKS:
                from ui.contact.contacts_view import ContactsView
                panel = ContactsView(self._contact_api, self._auth_api, 'callbacks', parent=self)
            elif index == self.PANEL_COMPANIES:
                from ui.contact.contact_company_view import ContactCompanyView
                panel = ContactCompanyView(self._contact_api, self._auth_api, parent=self)
        except Exception as e:
            logger.error("Fehler beim Laden eines Contact-Panels: %s", e)
            self._panels_loaded.discard(index)
            return

        if panel:
            if self._toast_manager and hasattr(panel, '_toast_manager'):
                panel._toast_manager = self._toast_manager
            if hasattr(panel, 'contact_selected'):
                panel.contact_selected.connect(self._on_contact_selected)
            if hasattr(panel, 'create_person_requested'):
                panel.create_person_requested.connect(self._on_create_person)
            if hasattr(panel, 'create_company_requested'):
                panel.create_company_requested.connect(self._on_create_company)
            if hasattr(panel, 'create_temp_note_requested'):
                panel.create_temp_note_requested.connect(self._on_create_temp_note)
            if hasattr(panel, 'quick_call_note_requested'):
                panel.quick_call_note_requested.connect(self._on_quick_call_note)
            old = self._content_stack.widget(index)
            self._content_stack.removeWidget(old)
            old.deleteLater()
            self._content_stack.insertWidget(index, panel)

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
                    logger.debug("Refresh Panel %s: %s", index, e)
        if show_toast and self._toast_manager:
            self._toast_manager.show_success(texts.CONTACT_REFRESH_DONE)

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
            hb_logger.info("[CONTACT] START (Intervall=%sms)", self._MODULE_HEARTBEAT_INTERVAL)

    def stop_module_heartbeat(self):
        """Stoppt den periodischen Heartbeat."""
        self._module_heartbeat_timer.stop()
        hb_logger.info("[CONTACT] STOP")

    def _initial_load_all_panels(self):
        """Laedt das Default-Panel sofort, Rest gestaffelt (1 pro Frame)."""
        if not self._content_stack:
            return
        default_idx = self.PANEL_ALL
        self._ensure_panel_loaded(default_idx)
        panel = self._content_stack.widget(default_idx)
        if panel and hasattr(panel, 'refresh'):
            try:
                panel.refresh()
            except Exception as e:
                logger.debug("Initial refresh Panel %s: %s", default_idx, e)
        self._navigate_to(default_idx)
        remaining = [i for i in range(self._TOTAL_PANELS) if i != default_idx]
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
                logger.debug("Staggered refresh Panel %s: %s", idx, e)
        QTimer.singleShot(0, lambda: self._load_panels_staggered(indices, pos + 1))

    def _on_module_heartbeat_tick(self):
        """Prueft im Hintergrund ob sich Daten geaendert haben."""
        hb_logger.info("[CONTACT] TICK")
        if self._fingerprint_check_running:
            return
        self._fingerprint_check_running = True
        worker = _ContactDataFingerprintWorker(self._contact_api)
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

    def _show_contact_module_admin(self):
        """Oeffnet die Contact-Modul-Verwaltung."""
        if not hasattr(self, '_module_admin_view') or self._module_admin_view is None:
            from ui.module_admin import ModuleAdminShell
            self._module_admin_view = ModuleAdminShell(
                module_key='contact', module_name='Contact',
                api_client=self._api_client, auth_api=self._auth_api,
            )
            self._module_admin_view._toast_manager = getattr(self, '_toast_manager', None)
            self._module_admin_view.back_requested.connect(self._leave_contact_module_admin)
            self._content_stack.addWidget(self._module_admin_view)
        idx = self._content_stack.indexOf(self._module_admin_view)
        self._content_stack.setCurrentIndex(idx)
        self._module_admin_view.load_data()

    def _leave_contact_module_admin(self):
        self._navigate_to(self.PANEL_ALL)

    # ------------------------------------------------------------------
    # Contact Actions (Overlay, Anlegen)
    # ------------------------------------------------------------------

    def _get_or_create_overlay(self):
        if not hasattr(self, '_detail_overlay') or self._detail_overlay is None:
            from ui.contact.contact_detail_overlay import ContactDetailOverlay
            self._detail_overlay = ContactDetailOverlay(
                self._contact_api, self._auth_api, parent=self,
            )
            self._detail_overlay.contact_updated.connect(self._refresh_all_silent)
            self._detail_overlay.close_requested.connect(self._on_overlay_closed)
        return self._detail_overlay

    def _on_contact_selected(self, contact_id: int):
        if contact_id == 0:
            self._on_create_person('')
            return
        overlay = self._get_or_create_overlay()
        overlay.show_contact(contact_id)

    def _on_create_person(self, query: str):
        overlay = self._get_or_create_overlay()
        overlay.show_new_contact(prefill_phone=query if query and query[0].isdigit() else '',
                                 prefill_name=query if query and not query[0].isdigit() else '')

    def _on_quick_call_note(self):
        overlay = self._get_or_create_overlay()
        overlay.show_new_contact(open_call_dialog_immediately=True)

    def _on_create_company(self, query: str):
        self._navigate_to(self.PANEL_COMPANIES)
        panel = self._content_stack.widget(self.PANEL_COMPANIES) if self._content_stack else None
        if panel and hasattr(panel, 'open_create_dialog'):
            panel.open_create_dialog(query)
        elif panel and hasattr(panel, '_on_create_company'):
            panel._on_create_company()

    def _on_create_temp_note(self, query: str):
        try:
            data = {
                'contact_type': 'temporary',
                'first_name': query if query and not query[0].isdigit() else None,
                'last_name': None,
            }
            if query and query[0].isdigit():
                data['phones'] = [{'phone_raw': query, 'phone_type': 'other'}]
            result = self._contact_api.create_contact(data)
            new_id = result.get('id')
            if new_id:
                overlay = self._get_or_create_overlay()
                overlay.contact_updated.emit()
                overlay.show_contact(new_id)
            if self._toast_manager:
                self._toast_manager.show_success(texts.CONTACT_SAVED)
        except Exception as e:
            logger.error("Temporaeren Kontakt erstellen fehlgeschlagen: %s", e)
            if self._toast_manager:
                self._toast_manager.show_error(str(e))

    def _on_overlay_closed(self):
        pass

    # ------------------------------------------------------------------
    # Call-Pop (Teams PSTN Screen-Pop)
    # ------------------------------------------------------------------

    def handle_call_pop(self, phone: str):
        """Eingehender PSTN-Anruf: Kontakt suchen, Overlay oeffnen, Anruf-Dialog."""
        logger.info("[CALL-POP] handle_call_pop: %s", phone)
        try:
            result = self._contact_api.find_contact_by_phone(phone)
        except Exception as e:
            logger.error("[CALL-POP] Suche fehlgeschlagen: %s", e)
            result = None

        overlay = self._get_or_create_overlay()
        if result and result.get('id'):
            cid = result['id']
            name = result.get('display_name', '')
            logger.info("[CALL-POP] Kontakt gefunden: id=%s name=%s", cid, name)
            overlay.show_contact(cid, open_call_dialog_immediately=True)
        else:
            logger.info("[CALL-POP] Kein Kontakt fuer %s → neuer Kontakt", phone)
            overlay.show_new_contact(prefill_phone=phone, open_call_dialog_immediately=True)

    def handle_call_pop_refocus(self):
        """Duplikat-Anruf: nur Fenster nach vorne holen."""
        logger.info("[CALL-POP] Refocus (Duplikat)")
        self._bring_window_to_front()

    def _bring_window_to_front(self):
        """Bringt das Hauptfenster zuverlaessig in den Vordergrund (Windows-robust)."""
        win = self.window()
        if not win:
            return
        if win.isMinimized():
            win.setWindowState(win.windowState() & ~Qt.WindowMinimized)
        win.raise_()
        win.activateWindow()
        QApplication.alert(win, 5000)

    def _refresh_all_silent(self):
        self._refresh_all(show_toast=False)
