# -*- coding: utf-8 -*-
"""
ACENCIA ATLAS - Dashboard / Startseite

Informatives Dashboard mit KPI-Karten, Schnellaktionen und kompakten
System-Mitteilungen. Module werden nicht mehr hier angezeigt sondern
in der persistenten App-Sidebar.
"""

import logging
from datetime import datetime
from typing import List, Dict, Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSizePolicy, QFrame, QScrollArea,
    QGraphicsBlurEffect, QGraphicsOpacityEffect,
    QTabWidget, QRadioButton, QButtonGroup,
    QGraphicsDropShadowEffect,
)
from PySide6.QtCore import Signal, Qt, QTimer, QThread, QPropertyAnimation, QEasingCurve, QSettings
from PySide6.QtGui import QPainter, QColor

from i18n import de as texts
import ui.styles.tokens as _tokens
from ui.styles.tokens import (
    FONT_SIZE_H1, FONT_SIZE_H2, FONT_SIZE_H3, FONT_SIZE_BODY, FONT_SIZE_CAPTION,
    FONT_WEIGHT_BOLD, FONT_WEIGHT_MEDIUM,
    PRIMARY_900, PRIMARY_500, PRIMARY_100, PRIMARY_0,
    ACCENT_500, ACCENT_100, ACCENT_HOVER,
    TEXT_INVERSE, TEXT_SECONDARY,
    BG_PRIMARY, BG_TERTIARY,
    BORDER_DEFAULT,
    RADIUS_LG, RADIUS_MD,
    SHADOW_SM,
    WARNING, WARNING_LIGHT,
    ERROR, ERROR_LIGHT,
    INFO, INFO_LIGHT,
    CRITICAL, CRITICAL_LIGHT,
    INDIGO,
)
from api.auth import User
from ui.components.kpi_card import KpiCardsWidget
from ui.components.quick_actions import QuickActionsWidget

logger = logging.getLogger(__name__)

_SEVERITY_COLORS = {
    'info': (INFO, INFO_LIGHT),
    'warning': (WARNING, WARNING_LIGHT),
    'error': (ERROR, ERROR_LIGHT),
    'critical': (CRITICAL, CRITICAL_LIGHT),
}

_SEVERITY_LABELS = {
    'info': 'MSG_CENTER_SEVERITY_INFO',
    'warning': 'MSG_CENTER_SEVERITY_WARNING',
    'error': 'MSG_CENTER_SEVERITY_ERROR',
    'critical': 'MSG_CENTER_SEVERITY_CRITICAL',
}


def _time_greeting() -> str:
    hour = datetime.now().hour
    if 5 <= hour < 12:
        return texts.DASHBOARD_GREETING_MORNING
    elif 12 <= hour < 18:
        return texts.DASHBOARD_GREETING_DAY
    return texts.DASHBOARD_GREETING_EVENING


# ======================================================================
# Background worker
# ======================================================================

class _LoadMessagesWorker(QThread):
    finished = Signal(list)

    def __init__(self, messages_api, parent=None):
        super().__init__(parent)
        self._api = messages_api

    def run(self):
        try:
            result = self._api.get_messages(page=1, per_page=10)
            self.finished.emit(result.get('data', []))
        except Exception:
            self.finished.emit([])


# ======================================================================
# Clickable frame helper
# ======================================================================

class _ClickableFrame(QFrame):
    """QFrame das bei Klick ein zugeordnetes QRadioButton aktiviert."""

    clicked = Signal()

    def mousePressEvent(self, event):
        self.clicked.emit()
        super().mousePressEvent(event)


# ======================================================================
# Settings Overlay
# ======================================================================

class _SettingsOverlay(QWidget):
    """Modales Einstellungs-Overlay mit Backdrop und Fade-Animation."""

    close_requested = Signal()
    save_requested = Signal(str, str, str)
    change_password_requested = Signal()

    def __init__(self, parent=None, username: str = "", email: str = "", account_type: str = "user"):
        super().__init__(parent)
        self._username = username
        self._email = email
        self._account_type = account_type
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFocusPolicy(Qt.StrongFocus)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setAlignment(Qt.AlignCenter)

        self._panel = QFrame()
        self._panel.setFixedSize(560, 820)
        self._panel.setStyleSheet(f"""
            QFrame {{
                background-color: {PRIMARY_0};
                border-radius: {RADIUS_LG};
                border: 1px solid {BORDER_DEFAULT};
            }}
        """)

        p_layout = QVBoxLayout(self._panel)
        p_layout.setContentsMargins(28, 24, 28, 24)
        p_layout.setSpacing(16)

        hdr = QHBoxLayout()
        title_lbl = QLabel(texts.NAV_EINSTELLUNGEN)
        title_lbl.setStyleSheet(
            f"font-family: {_tokens.FONT_HEADLINE}; font-size: {FONT_SIZE_H2}; "
            f"font-weight: {FONT_WEIGHT_BOLD}; color: {PRIMARY_900}; "
            f"background: transparent; border: none;"
        )
        hdr.addWidget(title_lbl)
        hdr.addStretch()

        close_btn = QPushButton("\u2715")
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setFixedSize(32, 32)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: none;
                font-size: 14pt; color: {PRIMARY_500};
                border-radius: 16px;
            }}
            QPushButton:hover {{
                background-color: {PRIMARY_100}; color: {PRIMARY_900};
            }}
        """)
        close_btn.clicked.connect(self.close_requested.emit)
        hdr.addWidget(close_btn)
        p_layout.addLayout(hdr)

        div = QFrame()
        div.setFrameShape(QFrame.HLine)
        div.setStyleSheet(
            f"color: {BORDER_DEFAULT}; background: {BORDER_DEFAULT}; "
            f"max-height: 1px; border: none;"
        )
        p_layout.addWidget(div)

        tabs = QTabWidget()
        tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: none; background: transparent;
            }}
            QTabBar::tab {{
                background: transparent; border: none;
                border-bottom: 2px solid transparent;
                padding: 8px 16px;
                font-family: {_tokens.FONT_BODY}; font-size: {FONT_SIZE_BODY};
                color: {PRIMARY_500};
            }}
            QTabBar::tab:selected {{
                color: {PRIMARY_900}; border-bottom-color: {ACCENT_500};
            }}
            QTabBar::tab:hover:!selected {{
                color: {PRIMARY_900};
            }}
        """)

        # Tab: Darstellung
        appearance = QWidget()
        appearance.setStyleSheet("background: transparent;")
        a_layout = QVBoxLayout(appearance)
        a_layout.setContentsMargins(4, 16, 4, 4)
        a_layout.setSpacing(12)

        font_header = QLabel(texts.SETTINGS_FONT_SECTION)
        font_header.setStyleSheet(
            f"font-family: {_tokens.FONT_HEADLINE}; font-size: {FONT_SIZE_H3}; "
            f"font-weight: {FONT_WEIGHT_BOLD}; color: {PRIMARY_900}; border: none;"
        )
        a_layout.addWidget(font_header)

        current_preset = QSettings(
            "ACENCIA GmbH", "ACENCIA ATLAS"
        ).value("appearance/font_preset", "classic")

        self._font_group = QButtonGroup(self)
        self._font_cards: dict[str, tuple[QFrame, QRadioButton]] = {}

        _presets = [
            ("modern", texts.SETTINGS_FONT_MODERN, texts.SETTINGS_FONT_MODERN_FONTS),
            ("classic", texts.SETTINGS_FONT_CLASSIC, texts.SETTINGS_FONT_CLASSIC_FONTS),
        ]

        for preset_id, title, fonts_desc in _presets:
            card = _ClickableFrame()
            card.setCursor(Qt.PointingHandCursor)
            c_lay = QHBoxLayout(card)
            c_lay.setContentsMargins(16, 12, 16, 12)
            c_lay.setSpacing(12)

            radio = QRadioButton()
            radio.setChecked(preset_id == current_preset)
            radio.setProperty("preset_id", preset_id)
            radio.setStyleSheet("QRadioButton { border: none; }")
            card.clicked.connect(lambda r=radio: r.setChecked(True))
            c_lay.addWidget(radio)

            text_col = QVBoxLayout()
            text_col.setSpacing(2)
            name_lbl = QLabel(title)
            name_lbl.setStyleSheet(
                f"font-family: {_tokens.FONT_BODY}; font-weight: {FONT_WEIGHT_BOLD}; "
                f"color: {PRIMARY_900}; border: none;"
            )
            name_lbl.setAttribute(Qt.WA_TransparentForMouseEvents)
            text_col.addWidget(name_lbl)

            desc_lbl = QLabel(fonts_desc)
            desc_lbl.setStyleSheet(
                f"font-family: {_tokens.FONT_BODY}; font-size: {FONT_SIZE_CAPTION}; "
                f"color: {PRIMARY_500}; border: none;"
            )
            desc_lbl.setAttribute(Qt.WA_TransparentForMouseEvents)
            text_col.addWidget(desc_lbl)

            c_lay.addLayout(text_col, 1)

            self._font_group.addButton(radio)
            self._font_cards[preset_id] = (card, radio)
            a_layout.addWidget(card)

        self._update_font_card_styles()
        self._font_group.buttonClicked.connect(self._on_font_preset_changed)

        a_layout.addSpacing(8)

        # Theme (Dark/Light)
        theme_header = QLabel(texts.SETTINGS_THEME_SECTION)
        theme_header.setStyleSheet(
            f"font-family: {_tokens.FONT_HEADLINE}; font-size: {FONT_SIZE_H3}; "
            f"font-weight: {FONT_WEIGHT_BOLD}; color: {PRIMARY_900}; border: none;"
        )
        a_layout.addWidget(theme_header)

        current_theme = _tokens.get_current_theme()
        self._theme_group = QButtonGroup(self)
        self._theme_cards: dict[str, tuple[QFrame, QRadioButton]] = {}

        _themes = [
            ("light", texts.SETTINGS_THEME_LIGHT, texts.SETTINGS_THEME_LIGHT_DESC),
            ("dark", texts.SETTINGS_THEME_DARK, texts.SETTINGS_THEME_DARK_DESC),
        ]

        for theme_id, title, desc in _themes:
            tcard = _ClickableFrame()
            tcard.setCursor(Qt.PointingHandCursor)
            tc_lay = QHBoxLayout(tcard)
            tc_lay.setContentsMargins(16, 10, 16, 10)
            tc_lay.setSpacing(12)

            tradio = QRadioButton()
            tradio.setChecked(theme_id == current_theme)
            tradio.setProperty("theme_id", theme_id)
            tradio.setStyleSheet("QRadioButton { border: none; }")
            tcard.clicked.connect(lambda r=tradio: r.setChecked(True))
            tc_lay.addWidget(tradio)

            t_text_col = QVBoxLayout()
            t_text_col.setSpacing(2)
            t_name = QLabel(title)
            t_name.setStyleSheet(
                f"font-family: {_tokens.FONT_BODY}; font-weight: {FONT_WEIGHT_BOLD}; "
                f"color: {PRIMARY_900}; border: none;"
            )
            t_name.setAttribute(Qt.WA_TransparentForMouseEvents)
            t_text_col.addWidget(t_name)

            t_desc = QLabel(desc)
            t_desc.setStyleSheet(
                f"font-family: {_tokens.FONT_BODY}; font-size: {FONT_SIZE_CAPTION}; "
                f"color: {PRIMARY_500}; border: none;"
            )
            t_desc.setAttribute(Qt.WA_TransparentForMouseEvents)
            t_text_col.addWidget(t_desc)

            tc_lay.addLayout(t_text_col, 1)

            self._theme_group.addButton(tradio)
            self._theme_cards[theme_id] = (tcard, tradio)
            a_layout.addWidget(tcard)

        self._update_theme_card_styles()
        self._theme_group.buttonClicked.connect(self._on_theme_changed)

        a_layout.addSpacing(8)

        import i18n as _i18n_mod
        lang_header = QLabel(texts.SETTINGS_LANGUAGE_SECTION)
        lang_header.setStyleSheet(
            f"font-family: {_tokens.FONT_HEADLINE}; font-size: {FONT_SIZE_H3}; "
            f"font-weight: {FONT_WEIGHT_BOLD}; color: {PRIMARY_900}; border: none;"
        )
        a_layout.addWidget(lang_header)

        current_lang = _i18n_mod.get_language()
        self._lang_group = QButtonGroup(self)
        self._lang_cards: dict[str, tuple[QFrame, QRadioButton]] = {}

        for lang_code, lang_name in _i18n_mod.AVAILABLE_LANGUAGES.items():
            lcard = _ClickableFrame()
            lcard.setCursor(Qt.PointingHandCursor)
            lc_lay = QHBoxLayout(lcard)
            lc_lay.setContentsMargins(16, 10, 16, 10)
            lc_lay.setSpacing(12)

            lradio = QRadioButton()
            lradio.setChecked(lang_code == current_lang)
            lradio.setProperty("lang_code", lang_code)
            lradio.setStyleSheet("QRadioButton { border: none; }")
            lcard.clicked.connect(lambda r=lradio: r.setChecked(True))
            lc_lay.addWidget(lradio)

            lname = QLabel(lang_name)
            lname.setStyleSheet(
                f"font-family: {_tokens.FONT_BODY}; font-weight: {FONT_WEIGHT_BOLD}; "
                f"color: {PRIMARY_900}; border: none;"
            )
            lname.setAttribute(Qt.WA_TransparentForMouseEvents)
            lc_lay.addWidget(lname, 1)

            self._lang_group.addButton(lradio)
            self._lang_cards[lang_code] = (lcard, lradio)
            a_layout.addWidget(lcard)

        self._update_lang_card_styles()
        self._lang_group.buttonClicked.connect(self._on_lang_changed)

        a_layout.addStretch()

        save_btn = QPushButton(texts.SAVE)
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ACCENT_500};
                color: {TEXT_INVERSE};
                border: none;
                border-radius: {RADIUS_MD};
                padding: 10px 32px;
                font-family: {_tokens.FONT_BODY}; font-size: {FONT_SIZE_BODY};
                font-weight: {FONT_WEIGHT_MEDIUM};
            }}
            QPushButton:hover {{
                background-color: {ACCENT_HOVER};
            }}
        """)
        save_btn.clicked.connect(self._on_save)
        a_layout.addWidget(save_btn, alignment=Qt.AlignRight)

        tabs.addTab(appearance, texts.SETTINGS_TAB_APPEARANCE)
        tabs.addTab(self._build_account_tab(), texts.SETTINGS_TAB_ACCOUNT)
        p_layout.addWidget(tabs, 1)

        outer.addWidget(self._panel)

        self._opacity = QGraphicsOpacityEffect(self)
        self._opacity.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity)
        self._anim = None

    def _build_account_tab(self) -> QWidget:
        tab = QWidget()
        tab.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(4, 16, 4, 4)
        layout.setSpacing(12)

        def _section_header(text: str) -> QLabel:
            lbl = QLabel(text)
            lbl.setStyleSheet(
                f"font-family: {_tokens.FONT_HEADLINE}; font-size: {FONT_SIZE_H3}; "
                f"font-weight: {FONT_WEIGHT_BOLD}; color: {PRIMARY_900}; border: none;"
            )
            return lbl

        def _info_row(label_text: str, value_text: str) -> QWidget:
            row = QWidget()
            row.setStyleSheet("background: transparent;")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 4, 0, 4)
            row_layout.setSpacing(8)

            lbl = QLabel(label_text)
            lbl.setFixedWidth(130)
            lbl.setStyleSheet(
                f"font-family: {_tokens.FONT_BODY}; font-size: {FONT_SIZE_BODY}; "
                f"color: {TEXT_SECONDARY}; border: none;"
            )
            row_layout.addWidget(lbl)

            val = QLabel(value_text if value_text else "\u2014")
            val.setStyleSheet(
                f"font-family: {_tokens.FONT_BODY}; font-size: {FONT_SIZE_BODY}; "
                f"font-weight: {FONT_WEIGHT_MEDIUM}; color: {PRIMARY_900}; border: none;"
            )
            row_layout.addWidget(val, 1)
            return row

        _account_type_labels = {
            "super_admin": texts.SETTINGS_ACCOUNT_TYPE_SUPER_ADMIN,
            "admin": texts.SETTINGS_ACCOUNT_TYPE_ADMIN,
            "user": texts.SETTINGS_ACCOUNT_TYPE_USER,
        }
        account_type_display = _account_type_labels.get(
            self._account_type, texts.SETTINGS_ACCOUNT_TYPE_USER
        )

        layout.addWidget(_section_header(texts.SETTINGS_ACCOUNT_SECTION_PROFILE))
        layout.addWidget(_info_row(texts.SETTINGS_ACCOUNT_USERNAME, self._username))
        layout.addWidget(_info_row(texts.SETTINGS_ACCOUNT_EMAIL, self._email))
        layout.addWidget(_info_row(texts.SETTINGS_ACCOUNT_TYPE, account_type_display))

        div = QFrame()
        div.setFrameShape(QFrame.HLine)
        div.setStyleSheet(
            f"color: {BORDER_DEFAULT}; background: {BORDER_DEFAULT}; "
            f"max-height: 1px; border: none;"
        )
        layout.addWidget(div)

        layout.addWidget(_section_header(texts.SETTINGS_ACCOUNT_SECTION_SECURITY))

        change_pw_btn = QPushButton(texts.SETTINGS_ACCOUNT_CHANGE_PW_BTN)
        change_pw_btn.setCursor(Qt.PointingHandCursor)
        change_pw_btn.setStyleSheet(
            f"QPushButton {{"
            f"  background-color: {PRIMARY_0}; color: {PRIMARY_900}; "
            f"  border: 1px solid {BORDER_DEFAULT}; border-radius: {RADIUS_MD}; "
            f"  padding: 8px 20px; "
            f"  font-family: {_tokens.FONT_BODY}; font-size: {FONT_SIZE_BODY}; "
            f"  font-weight: {FONT_WEIGHT_MEDIUM}; "
            f"}}"
            f"QPushButton:hover {{"
            f"  background-color: {PRIMARY_100}; border-color: {ACCENT_500}; "
            f"}}"
        )
        change_pw_btn.clicked.connect(self.change_password_requested.emit)
        layout.addWidget(change_pw_btn, alignment=Qt.AlignLeft)

        layout.addStretch()
        return tab

    def _on_font_preset_changed(self, _button):
        self._update_font_card_styles()

    def _on_lang_changed(self, _button):
        self._update_lang_card_styles()

    def _on_theme_changed(self, _button):
        self._update_theme_card_styles()

    def _on_save(self):
        font_btn = self._font_group.checkedButton()
        lang_btn = self._lang_group.checkedButton()
        theme_btn = self._theme_group.checkedButton()
        font_preset = font_btn.property("preset_id") if font_btn else "classic"
        lang_code = lang_btn.property("lang_code") if lang_btn else "de"
        theme_id = theme_btn.property("theme_id") if theme_btn else "light"
        self.save_requested.emit(font_preset, lang_code, theme_id)

    def reset_to_current(self):
        current = QSettings(
            "ACENCIA GmbH", "ACENCIA ATLAS"
        ).value("appearance/font_preset", "classic")
        for _pid, (card, radio) in self._font_cards.items():
            radio.setChecked(_pid == current)
        self._update_font_card_styles()

        current_theme = _tokens.get_current_theme()
        for _tid, (card, radio) in self._theme_cards.items():
            radio.setChecked(_tid == current_theme)
        self._update_theme_card_styles()

        import i18n as _i18n_mod
        current_lang = _i18n_mod.get_language()
        for _lid, (card, radio) in self._lang_cards.items():
            radio.setChecked(_lid == current_lang)
        self._update_lang_card_styles()

    def _update_font_card_styles(self):
        for pid, (card, radio) in self._font_cards.items():
            if radio.isChecked():
                card.setStyleSheet(f"""
                    QFrame {{
                        background-color: {PRIMARY_0};
                        border: 2px solid {ACCENT_500};
                        border-radius: {RADIUS_LG};
                    }}
                """)
            else:
                card.setStyleSheet(f"""
                    QFrame {{
                        background-color: {PRIMARY_0};
                        border: 1px solid {BORDER_DEFAULT};
                        border-radius: {RADIUS_LG};
                    }}
                """)

    def _update_lang_card_styles(self):
        for lid, (card, radio) in self._lang_cards.items():
            if radio.isChecked():
                card.setStyleSheet(f"""
                    QFrame {{
                        background-color: {PRIMARY_0};
                        border: 2px solid {ACCENT_500};
                        border-radius: {RADIUS_LG};
                    }}
                """)
            else:
                card.setStyleSheet(f"""
                    QFrame {{
                        background-color: {PRIMARY_0};
                        border: 1px solid {BORDER_DEFAULT};
                        border-radius: {RADIUS_LG};
                    }}
                """)

    def _update_theme_card_styles(self):
        for tid, (card, radio) in self._theme_cards.items():
            if radio.isChecked():
                card.setStyleSheet(f"""
                    QFrame {{
                        background-color: {PRIMARY_0};
                        border: 2px solid {ACCENT_500};
                        border-radius: {RADIUS_LG};
                    }}
                """)
            else:
                card.setStyleSheet(f"""
                    QFrame {{
                        background-color: {PRIMARY_0};
                        border: 1px solid {BORDER_DEFAULT};
                        border-radius: {RADIUS_LG};
                    }}
                """)

    def _ensure_opacity_effect(self):
        try:
            self._opacity.opacity()
        except (RuntimeError, AttributeError):
            self._opacity = QGraphicsOpacityEffect(self)
            self._opacity.setOpacity(0.0)
            self.setGraphicsEffect(self._opacity)

    def show_animated(self):
        self._ensure_opacity_effect()
        if hasattr(self, '_anim') and self._anim is not None:
            self._anim.stop()
        self._opacity.setOpacity(0.0)
        self.show()
        self.raise_()
        self.setFocus()
        self._anim = QPropertyAnimation(self._opacity, b"opacity")
        self._anim.setDuration(200)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.start()

    def close_animated(self, callback=None):
        self._ensure_opacity_effect()
        if hasattr(self, '_anim') and self._anim is not None:
            self._anim.stop()
        self._anim = QPropertyAnimation(self._opacity, b"opacity")
        self._anim.setDuration(150)
        self._anim.setStartValue(1.0)
        self._anim.setEndValue(0.0)
        self._anim.setEasingCurve(QEasingCurve.InCubic)
        self._anim.finished.connect(self.hide)
        if callback:
            self._anim.finished.connect(callback)
        self._anim.start()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 15, 30, 100))

    def mousePressEvent(self, event):
        if not self._panel.geometry().contains(event.pos()):
            self.close_requested.emit()
        else:
            super().mousePressEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close_requested.emit()
        else:
            super().keyPressEvent(event)


# ======================================================================
# Dashboard
# ======================================================================

class DashboardScreen(QWidget):
    """Startseite nach Login - informatives Dashboard ohne Modul-Tiles."""

    module_requested = Signal(str)
    quick_action_requested = Signal(str, str)
    logout_requested = Signal()
    forced_logout_requested = Signal()
    settings_requested = Signal()

    def __init__(self, username: str = "", app_version: str = "",
                 api_client=None, auth_api=None, tenant_name: str = "",
                 user_email: str = "", user_account_type: str = "user",
                 user: Optional[User] = None,
                 parent=None):
        super().__init__(parent)
        self._username = username
        self._app_version = app_version
        self._api_client = api_client
        self._auth_api = auth_api
        self._tenant_name = tenant_name
        self._user_email = user_email
        self._user_account_type = user_account_type
        self._user = user
        self._messages_worker = None

        self._setup_ui()

        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self._update_clock)
        self._clock_timer.start(1_000)

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _setup_ui(self):
        self.setStyleSheet(f"background-color: {BG_TERTIARY};")

        self._content = QWidget(self)
        self._content.setStyleSheet(f"background-color: {BG_TERTIARY};")

        root = QVBoxLayout(self._content)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # -- Header --
        header = QWidget()
        header.setStyleSheet(f"background-color: {PRIMARY_0}; border-bottom: 1px solid {BORDER_DEFAULT};")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(32, 20, 32, 20)
        h_layout.setSpacing(0)

        greeting_col = QVBoxLayout()
        greeting_col.setSpacing(2)

        self._greeting_label = QLabel()
        self._greeting_label.setStyleSheet(
            f"font-family: {_tokens.FONT_HEADLINE}; font-size: 18pt; "
            f"color: {PRIMARY_900}; background: transparent; border: none;"
        )
        greeting_col.addWidget(self._greeting_label)

        role_map = {
            "super_admin": texts.DASHBOARD_ROLE_SUPER_ADMIN,
            "admin": texts.DASHBOARD_ROLE_ADMIN,
            "user": texts.DASHBOARD_ROLE_USER,
        }
        role_text = role_map.get(self._user_account_type, texts.DASHBOARD_ROLE_USER)
        meta_parts = [role_text]
        if self._tenant_name:
            meta_parts.append(self._tenant_name)

        self._meta_label = QLabel(" \u00B7 ".join(meta_parts))
        self._meta_label.setStyleSheet(
            f"font-family: {_tokens.FONT_BODY}; font-size: {FONT_SIZE_CAPTION}; "
            f"color: {TEXT_SECONDARY}; background: transparent; border: none;"
        )
        greeting_col.addWidget(self._meta_label)

        h_layout.addLayout(greeting_col)
        h_layout.addStretch()

        right_area = QHBoxLayout()
        right_area.setSpacing(16)
        right_area.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        datetime_col = QVBoxLayout()
        datetime_col.setSpacing(0)

        self._date_label = QLabel()
        self._date_label.setAlignment(Qt.AlignRight)
        self._date_label.setStyleSheet(
            f"font-family: {_tokens.FONT_BODY}; font-size: {FONT_SIZE_CAPTION}; "
            f"color: {PRIMARY_500}; background: transparent; border: none;"
        )
        datetime_col.addWidget(self._date_label)

        self._time_label = QLabel()
        self._time_label.setAlignment(Qt.AlignRight)
        self._time_label.setStyleSheet(
            f"font-family: {_tokens.FONT_HEADLINE}; font-size: 16pt; "
            f"color: {PRIMARY_900}; background: transparent; border: none;"
        )
        datetime_col.addWidget(self._time_label)

        right_area.addLayout(datetime_col)

        self._admin_header_btn = QPushButton(f"\U0001F6E0  {texts.DASHBOARD_TILE_ADMIN}")
        self._admin_header_btn.setCursor(Qt.PointingHandCursor)
        self._admin_header_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: 1px solid {ACCENT_500};
                border-radius: {RADIUS_LG};
                font-family: {_tokens.FONT_BODY}; font-size: {FONT_SIZE_BODY};
                color: {ACCENT_500}; padding: 8px 24px; font-weight: 600;
            }}
            QPushButton:hover {{
                color: {PRIMARY_0}; background: {ACCENT_500};
            }}
        """)
        self._admin_header_btn.clicked.connect(lambda: self.module_requested.emit("admin"))
        self._admin_header_btn.setVisible(False)
        right_area.addWidget(self._admin_header_btn, alignment=Qt.AlignVCenter)

        logout_btn = QPushButton(texts.NAV_ABMELDEN)
        logout_btn.setCursor(Qt.PointingHandCursor)
        logout_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: 1px solid {PRIMARY_500};
                border-radius: {RADIUS_LG};
                font-family: {_tokens.FONT_BODY}; font-size: {FONT_SIZE_BODY};
                color: {PRIMARY_500}; padding: 8px 24px;
            }}
            QPushButton:hover {{
                color: {PRIMARY_900}; border-color: {PRIMARY_900};
            }}
        """)
        logout_btn.clicked.connect(self.logout_requested.emit)
        right_area.addWidget(logout_btn, alignment=Qt.AlignVCenter)

        h_layout.addLayout(right_area)
        root.addWidget(header)

        # -- Scrollable dashboard content --
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        dashboard_content = QWidget()
        dashboard_content.setStyleSheet(f"background-color: {BG_TERTIARY};")
        dc_layout = QVBoxLayout(dashboard_content)
        dc_layout.setContentsMargins(32, 24, 32, 24)
        dc_layout.setSpacing(24)

        has_any_module = self._user and any([
            self._user.has_module("core"),
            self._user.has_module("provision"),
            self._user.has_module("workforce"),
            self._user.has_module("contact"),
        ])

        # -- KPI Cards --
        if self._user and has_any_module:
            self._kpi_widget = KpiCardsWidget(self._user, self._api_client)
            self._kpi_widget.card_clicked.connect(self._on_kpi_clicked)
            dc_layout.addWidget(self._kpi_widget)
        else:
            self._kpi_widget = None

        # -- Quick Actions --
        if self._user and has_any_module:
            self._quick_actions = QuickActionsWidget(self._user)
            self._quick_actions.action_requested.connect(self._on_quick_action)
            if self._quick_actions.has_actions():
                dc_layout.addWidget(self._quick_actions)
        else:
            self._quick_actions = None

        # -- Compact Messages Section --
        msg_section = QVBoxLayout()
        msg_section.setSpacing(12)

        msg_header_row = QHBoxLayout()
        msg_title = QLabel(texts.DASHBOARD_MESSAGES_HEADER)
        msg_title.setStyleSheet(
            f"font-family: {_tokens.FONT_BODY}; font-size: {FONT_SIZE_BODY}; "
            f"font-weight: {FONT_WEIGHT_BOLD}; color: {PRIMARY_900}; "
            f"background: transparent; border: none;"
        )
        msg_header_row.addWidget(msg_title)
        msg_header_row.addStretch()

        self._msg_count_label = QLabel("")
        self._msg_count_label.setCursor(Qt.PointingHandCursor)
        self._msg_count_label.setStyleSheet(
            f"font-size: {FONT_SIZE_CAPTION}; color: {ACCENT_500}; "
            f"background: transparent; border: none;"
        )
        msg_header_row.addWidget(self._msg_count_label)
        msg_section.addLayout(msg_header_row)

        self._msg_container = QVBoxLayout()
        self._msg_container.setSpacing(10)

        self._msg_placeholder = QLabel(texts.DASHBOARD_MESSAGES_LOADING)
        self._msg_placeholder.setStyleSheet(
            f"font-family: {_tokens.FONT_BODY}; font-size: {FONT_SIZE_BODY}; "
            f"color: {PRIMARY_500}; background: transparent; border: none;"
        )
        self._msg_container.addWidget(self._msg_placeholder)

        msg_section.addLayout(self._msg_container)
        dc_layout.addLayout(msg_section)

        if not has_any_module and self._user:
            hint = QLabel(texts.DASHBOARD_NO_MODULES_HINT)
            hint.setWordWrap(True)
            hint.setStyleSheet(
                f"font-family: {_tokens.FONT_BODY}; font-size: {FONT_SIZE_BODY}; "
                f"color: {TEXT_SECONDARY}; padding: 24px; "
                f"background-color: {PRIMARY_0}; border: 1px solid {BORDER_DEFAULT}; "
                f"border-radius: {RADIUS_LG};"
            )
            dc_layout.addWidget(hint)

        dc_layout.addStretch()

        scroll.setWidget(dashboard_content)
        root.addWidget(scroll, stretch=1)

        self._update_clock()

        self._settings_overlay = _SettingsOverlay(
            self,
            username=self._username,
            email=getattr(self, '_user_email', ''),
            account_type=getattr(self, '_user_account_type', 'user'),
        )
        self._settings_overlay.hide()
        self._settings_overlay.close_requested.connect(self._close_settings)
        self._settings_overlay.save_requested.connect(self._on_settings_saved)
        self._settings_overlay.change_password_requested.connect(self._on_change_password_requested)

        self._build_feedback_pill()
        self._build_feedback_overlay()

    # ------------------------------------------------------------------
    # KPI / Quick Action handlers
    # ------------------------------------------------------------------

    def _on_kpi_clicked(self, card_id: str):
        mapping = {
            "inbox": "core",
            "messages": None,
        }
        module_id = mapping.get(card_id)
        if module_id:
            self.module_requested.emit(module_id)

    def _on_quick_action(self, action_id: str):
        mapping = {
            "open_inbox": "core",
            "upload_doc": "core",
            "bipro_fetch": "core",
            "search_phone": "contact",
            "new_call_note": "contact",
            "search_employee": "workforce",
            "check_provision": "ledger",
        }
        module_id = mapping.get(action_id)
        if module_id:
            self.quick_action_requested.emit(module_id, action_id)

    # ------------------------------------------------------------------
    # Feedback pill button + overlay
    # ------------------------------------------------------------------

    def _build_feedback_pill(self):
        self._feedback_btn = QPushButton(f"\U0001F4AC  {texts.FEEDBACK_BTN_TEXT}")
        self._feedback_btn.setParent(self)
        self._feedback_btn.setCursor(Qt.PointingHandCursor)
        self._feedback_btn.setToolTip(texts.FEEDBACK_BTN_TOOLTIP)
        self._feedback_btn.setFixedHeight(44)
        self._feedback_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {PRIMARY_900};
                color: {TEXT_INVERSE};
                border: 1px solid {PRIMARY_500};
                border-radius: 22px;
                padding: 0 20px;
                font-family: {_tokens.FONT_BODY};
                font-size: {FONT_SIZE_BODY};
                font-weight: {FONT_WEIGHT_MEDIUM};
            }}
            QPushButton:hover {{
                background-color: rgba(0, 31, 61, 0.85);
                border-color: {ACCENT_500};
            }}
            QPushButton:pressed {{
                background-color: rgba(0, 31, 61, 0.95);
            }}
        """)
        shadow = QGraphicsDropShadowEffect(self._feedback_btn)
        shadow.setBlurRadius(16)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 31, 61, 50))
        self._feedback_btn.setGraphicsEffect(shadow)
        self._feedback_btn.clicked.connect(self._open_feedback)
        self._feedback_btn.show()
        self._feedback_btn.raise_()

    def _build_feedback_overlay(self):
        from ui.feedback_overlay import FeedbackOverlay

        self._feedback_overlay = FeedbackOverlay(self)
        self._feedback_overlay.hide()
        self._feedback_overlay.close_requested.connect(self._close_feedback)
        self._feedback_overlay.submit_requested.connect(self._on_feedback_submitted)

    def _position_feedback_pill(self):
        if not hasattr(self, '_feedback_btn'):
            return
        btn = self._feedback_btn
        btn.adjustSize()
        x = self.width() - btn.width() - 24
        y = self.height() - btn.height() - 56
        btn.move(x, y)
        btn.raise_()

    def _open_feedback(self):
        try:
            if self._feedback_overlay.isVisible():
                return
            self._feedback_overlay.reset()
            self._content.setGraphicsEffect(None)
            self._feedback_btn.setEnabled(False)
            self._feedback_overlay.setGeometry(self.rect())
            self._feedback_overlay.show_animated()
        except RuntimeError as e:
            logger.error("Feedback-Overlay konnte nicht geoeffnet werden: %s", e)
            self._rebuild_feedback_overlay()

    def _close_feedback(self):
        try:
            if not self._feedback_overlay.isVisible():
                return
            self._feedback_overlay.close_animated(
                callback=self._on_feedback_close_done
            )
        except RuntimeError as e:
            logger.error("Feedback-Overlay konnte nicht geschlossen werden: %s", e)
            self._content.setGraphicsEffect(None)
            self._feedback_btn.setEnabled(True)

    def _on_feedback_close_done(self):
        try:
            self._content.setGraphicsEffect(None)
        except RuntimeError:
            pass
        try:
            self._feedback_btn.setEnabled(True)
        except RuntimeError:
            pass

    def _rebuild_feedback_overlay(self):
        try:
            old = getattr(self, '_feedback_overlay', None)
            if old:
                old.hide()
                old.deleteLater()
        except RuntimeError:
            pass
        self._build_feedback_overlay()
        logger.info("Feedback-Overlay wurde neu erstellt")

    def _on_feedback_submitted(self, payload: dict):
        logger.info("Feedback payload collected: type=%s, prio=%s",
                     payload.get('feedback_type'), payload.get('priority'))
        self._close_feedback()

        if hasattr(self, '_api_client') and self._api_client:
            self._submit_feedback_async(payload)
        else:
            self._show_feedback_toast(True)

    def _submit_feedback_async(self, payload: dict):
        from api.support import SupportAPI

        class _Worker(QThread):
            finished = Signal(bool, str)

            def __init__(self, api_client, data, parent=None):
                super().__init__(parent)
                self._api_client = api_client
                self._data = data

            def run(self):
                try:
                    support_api = SupportAPI(self._api_client)
                    support_api.submit_feedback(
                        feedback_type=self._data.get("feedback_type", "feedback"),
                        priority=self._data.get("priority", "low"),
                        content=self._data.get("content", ""),
                        subject=self._data.get("subject", ""),
                        reproduction_steps=self._data.get("reproduction_steps", ""),
                        screenshot_path=self._data.get("screenshot_path"),
                        include_logs=self._data.get("include_logs", False),
                    )
                    self.finished.emit(True, "")
                except Exception as e:
                    self.finished.emit(False, str(e))

        self._feedback_worker = _Worker(self._api_client, payload, parent=self)
        self._feedback_worker.finished.connect(self._on_feedback_api_done)
        self._feedback_worker.start()

    def _on_feedback_api_done(self, success: bool, error_msg: str):
        self._show_feedback_toast(success)
        if not success:
            logger.warning("Feedback-Submit fehlgeschlagen: %s", error_msg)

    def _show_feedback_toast(self, success: bool):
        try:
            tm = self._find_toast_manager()
            if tm:
                if success:
                    tm.show_success(texts.FEEDBACK_SUCCESS)
                else:
                    tm.show_error(texts.FEEDBACK_ERROR)
        except Exception:
            logger.debug("Toast not available for feedback confirmation")

    def _find_toast_manager(self):
        widget = self.parent()
        while widget:
            if hasattr(widget, '_toast_manager'):
                return widget._toast_manager
            widget = widget.parent()
        return None

    # ------------------------------------------------------------------
    # Settings overlay
    # ------------------------------------------------------------------

    def _open_settings(self):
        if self._settings_overlay.isVisible():
            return
        self._settings_overlay.reset_to_current()
        self._content.setGraphicsEffect(None)
        self._settings_overlay.setGeometry(self.rect())
        self._settings_overlay.show_animated()

    def _close_settings(self):
        if not self._settings_overlay.isVisible():
            return
        self._settings_overlay.close_animated()

    def _on_change_password_requested(self):
        from ui.change_password_dialog import ChangeOwnPasswordDialog

        if not hasattr(self, '_auth_api') or self._auth_api is None:
            return

        dlg = ChangeOwnPasswordDialog(self._auth_api, parent=self)
        dlg.password_changed.connect(self._on_password_changed_successfully)
        dlg.max_attempts_reached.connect(self._on_max_attempts_logout)
        dlg.exec()

    def _on_password_changed_successfully(self):
        QTimer.singleShot(200, self.logout_requested.emit)

    def _on_max_attempts_logout(self):
        QTimer.singleShot(200, self.forced_logout_requested.emit)

    def _on_settings_saved(self, preset_id: str, lang_code: str, theme_id: str):
        from PySide6.QtWidgets import QApplication
        from PySide6.QtGui import QFont, QFontDatabase
        import ui.styles.tokens as _tok
        import i18n as _i18n_mod

        QSettings("ACENCIA GmbH", "ACENCIA ATLAS").setValue(
            "appearance/font_preset", preset_id
        )
        QSettings("ACENCIA GmbH", "ACENCIA ATLAS").setValue(
            "appearance/theme", theme_id
        )

        app = QApplication.instance()
        # Repaints unterdruecken waehrend globale Styles angewendet werden
        app.setUpdatesEnabled(False)
        try:
            _tok.apply_font_preset(preset_id)
            _tok.apply_theme(theme_id)
            _i18n_mod.set_language(lang_code)

            app.setStyleSheet(_tok.get_application_stylesheet())

            _body = _tok.FONT_BODY.split(",")[0].strip().strip('"')
            if QFontDatabase.hasFamily(_body):
                app.setFont(QFont(_body, 10))
        finally:
            app.setUpdatesEnabled(True)

        QTimer.singleShot(0, self._rebuild_ui)

    def _rebuild_ui(self):
        self._clock_timer.stop()

        if self._messages_worker and self._messages_worker.isRunning():
            try:
                self._messages_worker.finished.disconnect()
            except RuntimeError:
                pass
        self._messages_worker = None

        old_content = self._content
        old_overlay = self._settings_overlay
        old_feedback_overlay = getattr(self, '_feedback_overlay', None)
        old_feedback_btn = getattr(self, '_feedback_btn', None)

        old_content.setGraphicsEffect(None)

        # Repaints unterdruecken waehrend des kompletten Rebuilds
        self.setUpdatesEnabled(False)
        try:
            old_content.hide()
            old_overlay.hide()
            if old_feedback_overlay:
                old_feedback_overlay.hide()

            self._setup_ui()
            self._content.setGeometry(self.rect())
        finally:
            self.setUpdatesEnabled(True)

        self._content.show()

        old_content.deleteLater()
        old_overlay.deleteLater()
        if old_feedback_overlay:
            old_feedback_overlay.deleteLater()
        if old_feedback_btn:
            old_feedback_btn.deleteLater()

        self._clock_timer.start(1_000)

        if self._api_client:
            QTimer.singleShot(0, lambda: self._deferred_reload_data())

    def _deferred_reload_data(self):
        """Laedt Daten erst im naechsten Event-Loop-Zyklus nach dem UI-Rebuild."""
        if self._api_client:
            self.load_messages(self._api_client)
            if self._kpi_widget:
                self._kpi_widget.load_data(self._api_client)

    # ------------------------------------------------------------------
    # Resize
    # ------------------------------------------------------------------

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, '_content'):
            self._content.setGeometry(self.rect())
        if hasattr(self, '_settings_overlay') and self._settings_overlay.isVisible():
            self._settings_overlay.setGeometry(self.rect())
        if hasattr(self, '_feedback_overlay') and self._feedback_overlay.isVisible():
            self._feedback_overlay.setGeometry(self.rect())
        self._position_feedback_pill()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_modules(self, visible_modules: list[str]):
        """Kompatibilitaets-Methode: Steuert Admin-Button Sichtbarkeit."""
        if hasattr(self, '_admin_header_btn'):
            self._admin_header_btn.setVisible('admin' in visible_modules)

    def load_messages(self, api_client):
        if self._messages_worker and self._messages_worker.isRunning():
            return
        self._api_client = api_client
        try:
            from api.messages import MessagesAPI
            messages_api = MessagesAPI(api_client)
            self._messages_worker = _LoadMessagesWorker(messages_api, parent=self)
            self._messages_worker.finished.connect(self._on_messages_loaded)
            self._messages_worker.start()
        except Exception:
            logger.exception("Mitteilungen konnten nicht geladen werden")
            self._msg_placeholder.setText(texts.DASHBOARD_MESSAGES_EMPTY)

    def load_kpi_data(self):
        if self._kpi_widget and self._api_client:
            self._kpi_widget.load_data(self._api_client)

    def on_notifications_updated(self, summary: dict):
        unread_system = summary.get('unread_system_messages', 0)
        prev = getattr(self, '_prev_unread_system', -1)
        if unread_system != prev:
            self._prev_unread_system = unread_system
            if self.isVisible() and hasattr(self, '_api_client') and self._api_client:
                self._reload_messages()

    def open_settings_overlay(self):
        """Wird vom AppRouter aufgerufen wenn in der Sidebar auf Einstellungen geklickt wird."""
        self._open_settings()

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _reload_messages(self):
        if not hasattr(self, '_api_client') or not self._api_client:
            return
        if self._messages_worker and self._messages_worker.isRunning():
            return
        try:
            from api.messages import MessagesAPI
            messages_api = MessagesAPI(self._api_client)
            self._messages_worker = _LoadMessagesWorker(messages_api, parent=self)
            self._messages_worker.finished.connect(self._on_messages_reloaded)
            self._messages_worker.start()
        except Exception:
            logger.debug("Mitteilungen-Reload fehlgeschlagen")

    def _on_messages_reloaded(self, messages: list):
        self._render_messages(messages)

    def _on_messages_loaded(self, messages: list):
        self._render_messages(messages)

    def _render_messages(self, messages: list):
        # Diff-Guard: Nur aktualisieren wenn sich Daten tatsaechlich geaendert haben
        msg_fingerprint = tuple((m.get('id'), m.get('is_read')) for m in messages) if messages else ()
        if getattr(self, '_last_msg_fingerprint', None) == msg_fingerprint:
            return
        self._last_msg_fingerprint = msg_fingerprint

        while self._msg_container.count():
            item = self._msg_container.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        if not messages:
            self._msg_placeholder = QLabel(texts.DASHBOARD_MESSAGES_EMPTY)
            self._msg_placeholder.setStyleSheet(
                f"font-family: {_tokens.FONT_BODY}; font-size: {FONT_SIZE_BODY}; "
                f"color: {PRIMARY_500}; background: transparent; border: none;"
            )
            self._msg_container.addWidget(self._msg_placeholder)
            self._msg_count_label.setText("")
            return

        display_msgs = messages[:3]
        total = len(messages)
        self._msg_count_label.setText(
            texts.DASHBOARD_MESSAGES_ALL.format(count=total)
        )

        for msg in display_msgs:
            card = self._build_message_card(msg)
            self._msg_container.addWidget(card)

    def _build_message_card(self, msg: dict) -> QFrame:
        severity = msg.get('severity', 'info')
        fg_color, bg_color = _SEVERITY_COLORS.get(severity, _SEVERITY_COLORS['info'])
        is_read = msg.get('is_read', False)

        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {bg_color if not is_read else BG_TERTIARY};
                border: 1px solid {BORDER_DEFAULT};
                border-left: 4px solid {fg_color};
                border-radius: {RADIUS_MD};
            }}
        """)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(3)

        top_row = QHBoxLayout()
        sev_label_key = _SEVERITY_LABELS.get(severity, '')
        sev_text = getattr(texts, sev_label_key, severity) if sev_label_key else severity
        badge = QLabel(sev_text)
        badge.setStyleSheet(f"""
            QLabel {{
                background-color: {fg_color}; color: {TEXT_INVERSE};
                border-radius: 3px; padding: 1px 6px; border: none;
                font-size: {FONT_SIZE_CAPTION}; font-weight: {FONT_WEIGHT_BOLD};
            }}
        """)
        badge.setFixedHeight(18)
        top_row.addWidget(badge)

        title = QLabel(msg.get('title', ''))
        title.setWordWrap(True)
        title.setStyleSheet(
            f"font-family: {_tokens.FONT_BODY}; font-size: {FONT_SIZE_H3}; "
            f"font-weight: {FONT_WEIGHT_BOLD}; color: {PRIMARY_900}; "
            f"background: transparent; border: none;"
        )
        top_row.addWidget(title, 1)
        layout.addLayout(top_row)

        description = msg.get('description', '')
        if description:
            desc = QLabel(description)
            desc.setWordWrap(True)
            desc.setStyleSheet(
                f"font-family: {_tokens.FONT_BODY}; font-size: {FONT_SIZE_BODY}; "
                f"color: {PRIMARY_900}; background: transparent; border: none;"
            )
            layout.addWidget(desc)

        sender = msg.get('sender_name', '')
        created = msg.get('created_at', '')
        try:
            dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
            date_str = dt.strftime("%d.%m.%Y %H:%M")
        except (ValueError, AttributeError):
            date_str = created[:10] if len(created) >= 10 else created

        meta_parts = []
        if sender:
            meta_parts.append(texts.MSG_CENTER_FROM.format(sender=sender))
        if date_str:
            meta_parts.append(date_str)
        if meta_parts:
            meta = QLabel("  \u00B7  ".join(meta_parts))
            meta.setStyleSheet(
                f"font-family: {_tokens.FONT_BODY}; font-size: {FONT_SIZE_CAPTION}; "
                f"color: {PRIMARY_500}; background: transparent; border: none;"
            )
            layout.addWidget(meta)

        return card

    def _update_clock(self):
        now = datetime.now()
        greeting = _time_greeting()
        name = self._username or ""

        self._greeting_label.setText(
            f"{greeting}, {name}" if name else greeting
        )
        self._date_label.setText(now.strftime("%d.%m.%Y"))
        self._time_label.setText(now.strftime("%H:%M:%S"))
