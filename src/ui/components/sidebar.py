# -*- coding: utf-8 -*-
"""
ACENCIA ATLAS - App-Sidebar

Persistente Sidebar-Navigation mit dynamischem Modul-Loading.
Module werden nur angezeigt, wenn der Nutzer die entsprechende Berechtigung hat.
Das Zahnrad-Icon fuer die Modul-Verwaltung erscheint nur bei Admin-Zugriff.

Collapse-Verhalten:
  - Im Dashboard: Sidebar ist ausgeklappt (260px) mit Icons + Labels
  - In jedem Modul: Sidebar klappt ein (~56px) und zeigt nur Icons
"""

import logging
from typing import Optional

from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QLabel, QPushButton,
    QSizePolicy, QWidget, QGraphicsOpacityEffect,
)
from PySide6.QtCore import (
    Signal, Qt, Property, QPropertyAnimation, QEasingCurve,
    QParallelAnimationGroup, QSequentialAnimationGroup, QPauseAnimation,
)

from i18n import de as texts
from api.auth import User
import ui.styles.tokens as _tok

logger = logging.getLogger(__name__)

_MODULE_META = {
    "core": {"icon": "\U0001F4C1", "label_attr": "DASHBOARD_TILE_CORE"},
    "provision": {"icon": "\U0001F4B0", "label_attr": "DASHBOARD_TILE_LEDGER"},
    "workforce": {"icon": "\U0001F465", "label_attr": "WF_DASHBOARD_TILE"},
    "contact": {"icon": "\U0001F4DE", "label_attr": "CONTACT_DASHBOARD_TILE"},
}

_W_EXPANDED = _tok.APP_SIDEBAR_WIDTH_EXPANDED
_W_COLLAPSED = _tok.APP_SIDEBAR_WIDTH_COLLAPSED


class _SidebarNavItem(QPushButton):
    """Einzelner Navigations-Eintrag in der Sidebar."""

    admin_clicked = Signal(str)

    def __init__(self, icon: str, label: str, item_id: str,
                 show_admin: bool = False, parent=None):
        super().__init__(parent)
        self._item_id = item_id
        self._icon = icon
        self._label = label
        self._collapsed = False
        self._set_text_for_state(False)
        self.setCheckable(True)
        self.setMinimumHeight(_tok.APP_SIDEBAR_NAV_HEIGHT)
        self.setCursor(Qt.PointingHandCursor)
        self._apply_style()

        if show_admin:
            self._admin_btn = QPushButton("\u2699", self)
            self._admin_btn.setFixedSize(26, 26)
            self._admin_btn.setCursor(Qt.PointingHandCursor)
            self._admin_btn.setToolTip(texts.SIDEBAR_ADMIN_TOOLTIP)
            self._admin_btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent; border: none;
                    font-size: 13px; color: {_tok.SIDEBAR_TEXT};
                    border-radius: 4px; opacity: 0.5;
                }}
                QPushButton:hover {{
                    background: rgba(250, 153, 57, 0.2); opacity: 1;
                }}
            """)
            self._admin_btn.clicked.connect(
                lambda: self.admin_clicked.emit(self._item_id)
            )
        else:
            self._admin_btn = None

    def set_collapsed(self, collapsed: bool):
        self._collapsed = collapsed
        self._set_text_for_state(collapsed)
        if self._admin_btn:
            self._admin_btn.setVisible(not collapsed)

    def _set_text_for_state(self, collapsed: bool):
        if collapsed:
            self.setText(self._icon)
            self.setToolTip(self._label)
        else:
            self.setText(f"  {self._icon}  {self._label}")
            self.setToolTip("")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._admin_btn and not self._collapsed:
            y = (self.height() - self._admin_btn.height()) // 2
            x = self.width() - self._admin_btn.width() - 12
            self._admin_btn.move(x, y)

    def _apply_style(self):
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                border-left: 3px solid transparent;
                border-radius: 0px;
                padding: 12px 16px;
                text-align: left;
                font-family: {_tok.FONT_BODY};
                font-size: {_tok.FONT_SIZE_BODY};
                color: {_tok.SIDEBAR_TEXT};
            }}
            QPushButton:hover {{
                background-color: {_tok.SIDEBAR_HOVER};
            }}
            QPushButton:checked {{
                background-color: {_tok.SIDEBAR_HOVER};
                border-left: 3px solid {_tok.ACCENT_500};
                color: {_tok.SIDEBAR_TEXT};
                font-weight: 500;
            }}
        """)


class AppSidebar(QFrame):
    """Persistente App-Sidebar mit Collapse/Expand-Verhalten."""

    dashboard_requested = Signal()
    module_requested = Signal(str)
    admin_requested = Signal(str)
    settings_requested = Signal()
    global_admin_requested = Signal()
    collapse_finished = Signal()

    def _get_sidebar_width(self) -> int:
        return self.width()

    def _set_sidebar_width(self, w: int):
        self.setFixedWidth(w)

    sidebarWidth = Property(int, _get_sidebar_width, _set_sidebar_width)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("appSidebar")
        self._is_expanded = True
        self.setFixedWidth(_W_EXPANDED)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)

        self._nav_items: dict[str, _SidebarNavItem] = {}
        self._module_container: Optional[QVBoxLayout] = None
        self._collapsible_labels: list[QWidget] = []

        self._anim_group: Optional[QParallelAnimationGroup] = None
        self._pending_collapse = False

        self._build_ui()

    # ------------------------------------------------------------------
    # Build UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        self.setStyleSheet(f"""
            QFrame#appSidebar {{
                background-color: {_tok.SIDEBAR_BG};
                border: none;
                border-right: 2px solid {_tok.ACCENT_500};
            }}
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addSpacing(16)

        # -- Dashboard-Link --
        nav_area = QVBoxLayout()
        nav_area.setContentsMargins(0, 0, 0, 0)
        nav_area.setSpacing(0)

        dash_item = _SidebarNavItem(
            "\U0001F3E0", texts.SIDEBAR_NAV_DASHBOARD, "dashboard",
        )
        dash_item.setChecked(True)
        dash_item.clicked.connect(self._on_dashboard_clicked)
        self._nav_items["dashboard"] = dash_item
        nav_area.addWidget(dash_item)

        nav_area.addSpacing(8)

        # -- Modul-Sektion --
        section_label = QLabel(texts.SIDEBAR_SECTION_MODULES)
        section_label.setStyleSheet(
            f"font-size: 9px; font-weight: 600; text-transform: uppercase; "
            f"letter-spacing: 1.5px; color: {_tok.PRIMARY_500}; "
            f"padding: 8px 20px; background: transparent; border: none;"
        )
        self._collapsible_labels.append(section_label)
        nav_area.addWidget(section_label)

        self._module_container = QVBoxLayout()
        self._module_container.setContentsMargins(0, 0, 0, 0)
        self._module_container.setSpacing(0)
        nav_area.addLayout(self._module_container)

        nav_area.addSpacing(16)

        # -- System-Sektion --
        sys_label = QLabel(texts.SIDEBAR_SECTION_SYSTEM)
        sys_label.setStyleSheet(
            f"font-size: 9px; font-weight: 600; text-transform: uppercase; "
            f"letter-spacing: 1.5px; color: {_tok.PRIMARY_500}; "
            f"padding: 8px 20px; background: transparent; border: none;"
        )
        self._collapsible_labels.append(sys_label)
        nav_area.addWidget(sys_label)

        settings_item = _SidebarNavItem(
            "\u2699\uFE0F", texts.SIDEBAR_NAV_SETTINGS, "settings",
        )
        settings_item.clicked.connect(self._on_settings_clicked)
        self._nav_items["settings"] = settings_item
        nav_area.addWidget(settings_item)

        self._admin_nav_item = _SidebarNavItem(
            "\U0001F6E0\uFE0F", texts.SIDEBAR_NAV_ADMIN, "admin",
        )
        self._admin_nav_item.clicked.connect(self._on_global_admin_clicked)
        self._admin_nav_item.setVisible(False)
        self._nav_items["admin"] = self._admin_nav_item
        nav_area.addWidget(self._admin_nav_item)

        root.addLayout(nav_area)
        root.addStretch()

        # -- Footer --
        footer = QFrame()
        footer.setStyleSheet(
            f"border-top: 1px solid {_tok.BORDER_SUBTLE};"
        )
        f_layout = QVBoxLayout(footer)
        f_layout.setContentsMargins(20, 12, 20, 12)

        self._version_label = QLabel("ATLAS")
        self._version_label.setStyleSheet(
            f"font-size: 10px; color: {_tok.PRIMARY_500}; "
            f"background: transparent; border: none;"
        )
        self._collapsible_labels.append(self._version_label)
        f_layout.addWidget(self._version_label)
        root.addWidget(footer)

    # ------------------------------------------------------------------
    # Collapse / Expand
    # ------------------------------------------------------------------

    _ANIM_DURATION = 420
    _FADE_DURATION = 180

    def set_expanded(self, expanded: bool):
        """Klappt die Sidebar animiert aus (True) oder ein (False)."""
        if expanded == self._is_expanded:
            return
        self._is_expanded = expanded

        if self._anim_group and self._anim_group.state() == QParallelAnimationGroup.Running:
            self._anim_group.stop()
            # Abgebrochene Collapse-Animation: Zustand sauber abschliessen und
            # collapse_finished emittieren, damit Downstream-Animationen nicht blockiert werden.
            if self._pending_collapse:
                self._pending_collapse = False
                end_w = _W_COLLAPSED
                self.setFixedWidth(end_w)
                for item in self._nav_items.values():
                    item.set_collapsed(True)
                for lbl in self._collapsible_labels:
                    lbl._expanded_text = lbl.text()
                    lbl.setText("")
                for lbl in self._collapsible_labels:
                    effect = lbl.graphicsEffect()
                    if isinstance(effect, QGraphicsOpacityEffect):
                        effect.setOpacity(1.0)
                self.collapse_finished.emit()

        self._pending_collapse = not expanded

        start_w = self.width()
        end_w = _W_EXPANDED if expanded else _W_COLLAPSED

        width_anim = QPropertyAnimation(self, b"sidebarWidth", self)
        width_anim.setDuration(self._ANIM_DURATION)
        width_anim.setStartValue(start_w)
        width_anim.setEndValue(end_w)
        width_anim.setEasingCurve(QEasingCurve.OutCubic)

        group = QParallelAnimationGroup(self)
        group.addAnimation(width_anim)

        if expanded:
            for item in self._nav_items.values():
                item.set_collapsed(False)
            for lbl in self._collapsible_labels:
                if hasattr(lbl, '_expanded_text'):
                    lbl.setText(lbl._expanded_text)
            self._add_fade_animations(group, 0.0, 1.0, delay=self._ANIM_DURATION // 3)
        else:
            self._add_fade_animations(group, 1.0, 0.0, delay=0)

        group.finished.connect(self._on_anim_finished)
        self._anim_group = group
        group.start()

    def _add_fade_animations(self, group: QParallelAnimationGroup,
                             start_opacity: float, end_opacity: float,
                             delay: int):
        """Erzeugt Opacity-Fade fuer Section-Labels (nicht fuer Nav-Icons)."""
        for widget in self._collapsible_labels:
            effect = widget.graphicsEffect()
            if not isinstance(effect, QGraphicsOpacityEffect):
                effect = QGraphicsOpacityEffect(widget)
                widget.setGraphicsEffect(effect)
            effect.setOpacity(start_opacity)

            fade = QPropertyAnimation(effect, b"opacity", group)
            fade.setDuration(self._FADE_DURATION)
            fade.setStartValue(start_opacity)
            fade.setEndValue(end_opacity)
            fade.setEasingCurve(QEasingCurve.InOutQuad)

            if delay > 0:
                seq = QSequentialAnimationGroup(group)
                seq.addPause(delay)
                seq.addAnimation(fade)
                group.addAnimation(seq)
            else:
                group.addAnimation(fade)

    def _on_anim_finished(self):
        # Kein setUpdatesEnabled-Guard: Unterdrueckt Repaints und kann waehrend/
        # nach der Animation zu sichtbarem Freeze-Frame fuehren. Die wenigen
        # State-Aenderungen (Nav-Items, Labels, Opacity) sind akzeptabel.
        if self._pending_collapse:
            self._pending_collapse = False
            for item in self._nav_items.values():
                item.set_collapsed(True)
            for lbl in self._collapsible_labels:
                lbl._expanded_text = lbl.text()
                lbl.setText("")

        for lbl in self._collapsible_labels:
            effect = lbl.graphicsEffect()
            if isinstance(effect, QGraphicsOpacityEffect):
                effect.setOpacity(1.0)

        if not self._is_expanded:
            self.collapse_finished.emit()

    @property
    def is_expanded(self) -> bool:
        return self._is_expanded

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_version(self, version: str):
        self._version_label.setText(f"ATLAS v{version}" if version else "ATLAS")

    def set_user(self, user: User):
        """Baut Modul-Navigation dynamisch basierend auf User-Berechtigungen auf."""
        self._clear_modules()

        if user.is_admin:
            self._admin_nav_item.setVisible(True)

        for module_key, meta in _MODULE_META.items():
            if not user.has_module(module_key):
                continue

            label = getattr(texts, meta["label_attr"], module_key.title())
            show_admin = user.is_module_admin(module_key)

            item = _SidebarNavItem(
                meta["icon"], label, module_key,
                show_admin=show_admin,
            )
            item.set_collapsed(not self._is_expanded)
            item.clicked.connect(lambda checked, mk=module_key: self._on_module_clicked(mk))
            if show_admin:
                item.admin_clicked.connect(self._on_admin_clicked)

            self._nav_items[module_key] = item
            self._module_container.addWidget(item)

    def set_active(self, item_id: str):
        """Setzt das aktive Element in der Navigation."""
        for key, item in self._nav_items.items():
            item.setChecked(key == item_id)

    def update_modules(self, user: User):
        """Aktualisiert die Module nach einem Heartbeat-Update.
        Diff-Vergleich: Nur bei tatsaechlicher Aenderung neu aufbauen."""
        new_keys = []
        for module_key in _MODULE_META:
            if user.has_module(module_key):
                new_keys.append(module_key)

        current_keys = [
            getattr(w, '_item_id', None)
            for w in (self._module_container.itemAt(i).widget()
                      for i in range(self._module_container.count()))
            if w is not None
        ] if self._module_container else []

        if new_keys == current_keys:
            return

        self.set_user(user)

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _clear_modules(self):
        if not self._module_container:
            return
        while self._module_container.count():
            item = self._module_container.takeAt(0)
            w = item.widget()
            if w:
                key = getattr(w, '_item_id', None)
                if key and key in self._nav_items:
                    del self._nav_items[key]
                w.deleteLater()

    def _on_dashboard_clicked(self):
        self.set_active("dashboard")
        self.dashboard_requested.emit()

    def _on_module_clicked(self, module_key: str):
        self.set_active(module_key)
        module_id = "ledger" if module_key == "provision" else module_key
        self.module_requested.emit(module_id)

    def _on_admin_clicked(self, module_key: str):
        module_id = "ledger" if module_key == "provision" else module_key
        self.admin_requested.emit(f"{module_id}_admin")

    def _on_settings_clicked(self):
        self.set_active("settings")
        self.settings_requested.emit()

    def _on_global_admin_clicked(self):
        self.set_active("admin")
        self.global_admin_requested.emit()
