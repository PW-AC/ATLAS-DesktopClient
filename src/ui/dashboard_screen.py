# -*- coding: utf-8 -*-
"""
ACENCIA ATLAS - Dashboard / Startseite

Tageszeitabhaengige Begruessung, System-Mitteilungen, Modul-Tiles (am unteren Rand),
Uhrzeit und Abmelden.
"""

import logging
from datetime import datetime
from typing import List, Dict

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSizePolicy, QFrame, QScrollArea,
    QGraphicsBlurEffect, QGraphicsOpacityEffect,
    QTabWidget, QRadioButton, QButtonGroup,
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

logger = logging.getLogger(__name__)

_TILE_LABEL = "ATLAS"

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
# Tile
# ======================================================================

class _ModuleTile(QPushButton):

    def __init__(self, title: str, description: str,
                 accent_color: str, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setFixedSize(200, 160)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 20)
        layout.setSpacing(4)

        accent_line = QFrame()
        accent_line.setFixedSize(32, 3)
        accent_line.setStyleSheet(f"background-color: {accent_color}; border: none;")
        accent_line.setAttribute(Qt.WA_TransparentForMouseEvents)
        layout.addWidget(accent_line)

        atlas_label = QLabel(_TILE_LABEL)
        atlas_label.setStyleSheet(
            f"font-family: {_tokens.FONT_HEADLINE}; font-size: {FONT_SIZE_CAPTION}; "
            f"letter-spacing: 2px; color: {PRIMARY_500}; background: transparent;"
        )
        atlas_label.setAttribute(Qt.WA_TransparentForMouseEvents)
        layout.addWidget(atlas_label)

        layout.addSpacing(2)

        title_label = QLabel(title)
        title_label.setStyleSheet(
            f"font-family: {_tokens.FONT_HEADLINE}; font-size: {FONT_SIZE_H3}; "
            f"font-weight: {FONT_WEIGHT_BOLD}; color: {PRIMARY_900}; background: transparent;"
        )
        title_label.setAttribute(Qt.WA_TransparentForMouseEvents)
        layout.addWidget(title_label)

        desc_label = QLabel(description)
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet(
            f"font-family: {_tokens.FONT_BODY}; font-size: {FONT_SIZE_CAPTION}; "
            f"color: {PRIMARY_500}; background: transparent;"
        )
        desc_label.setAttribute(Qt.WA_TransparentForMouseEvents)
        layout.addWidget(desc_label)

        layout.addStretch()

        self.setStyleSheet(f"""
            _ModuleTile {{
                background-color: {PRIMARY_0};
                border: 1px solid {BORDER_DEFAULT};
                border-radius: {RADIUS_LG};
                text-align: left;
            }}
            _ModuleTile:hover {{
                border-color: {accent_color};
            }}
        """)


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

    def __init__(self, parent=None):
        super().__init__(parent)
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

        # ── Tab Widget ──────────────────────────────────────────────
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

        # ── Tab: Darstellung ────────────────────────────────────────
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

        # ── Theme (Dark/Light) ─────────────────────────────────────
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
        p_layout.addWidget(tabs, 1)

        outer.addWidget(self._panel)

        self._opacity = QGraphicsOpacityEffect(self)
        self._opacity.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity)
        self._anim = None

    # -- Font preset handling --------------------------------------------

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
        """Setzt die Radio-Buttons auf den aktuell gespeicherten Wert."""
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

    # -- Animation -------------------------------------------------------

    def show_animated(self):
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
        self._anim = QPropertyAnimation(self._opacity, b"opacity")
        self._anim.setDuration(150)
        self._anim.setStartValue(1.0)
        self._anim.setEndValue(0.0)
        self._anim.setEasingCurve(QEasingCurve.InCubic)
        self._anim.finished.connect(self.hide)
        if callback:
            self._anim.finished.connect(callback)
        self._anim.start()

    # -- Events ----------------------------------------------------------

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
    """Startseite nach Login."""

    module_requested = Signal(str)
    logout_requested = Signal()

    def __init__(self, username: str = "", app_version: str = "",
                 api_client=None, tenant_name: str = "", parent=None):
        super().__init__(parent)
        self._username = username
        self._app_version = app_version
        self._api_client = api_client
        self._tenant_name = tenant_name
        self._tiles: dict[str, _ModuleTile] = {}
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

        # ── Header ────────────────────────────────────────────────────
        header = QWidget()
        header.setStyleSheet(f"background-color: {BG_TERTIARY};")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(48, 32, 48, 16)
        h_layout.setSpacing(0)

        greeting_col = QVBoxLayout()
        greeting_col.setSpacing(2)

        self._greeting_label = QLabel()
        self._greeting_label.setStyleSheet(
            f"font-family: {_tokens.FONT_HEADLINE}; font-size: 20pt; "
            f"color: {PRIMARY_900}; background: transparent;"
        )
        greeting_col.addWidget(self._greeting_label)

        self._tenant_label = QLabel()
        self._tenant_label.setStyleSheet(
            f"font-family: {_tokens.FONT_BODY}; font-size: 10pt; "
            f"color: {TEXT_SECONDARY}; background: transparent;"
        )
        if self._tenant_name:
            self._tenant_label.setText(self._tenant_name)
        else:
            self._tenant_label.hide()
        greeting_col.addWidget(self._tenant_label)

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
            f"font-family: {_tokens.FONT_BODY}; font-size: {FONT_SIZE_BODY}; "
            f"color: {PRIMARY_500}; background: transparent;"
        )
        datetime_col.addWidget(self._date_label)

        self._time_label = QLabel()
        self._time_label.setAlignment(Qt.AlignRight)
        self._time_label.setStyleSheet(
            f"font-family: {_tokens.FONT_HEADLINE}; font-size: {FONT_SIZE_H1}; "
            f"color: {PRIMARY_900}; background: transparent;"
        )
        datetime_col.addWidget(self._time_label)

        right_area.addLayout(datetime_col)

        settings_btn = QPushButton(f"\u2699  {texts.NAV_EINSTELLUNGEN}")
        settings_btn.setCursor(Qt.PointingHandCursor)
        settings_btn.setStyleSheet(f"""
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
        settings_btn.clicked.connect(self._open_settings)
        right_area.addWidget(settings_btn, alignment=Qt.AlignVCenter)

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

        # ── Divider ───────────────────────────────────────────────────
        div1 = QFrame()
        div1.setFrameShape(QFrame.HLine)
        div1.setStyleSheet(
            f"color: {BORDER_DEFAULT}; background: {BORDER_DEFAULT}; max-height: 1px;"
        )
        root.addWidget(div1)

        # ── System-Mitteilungen ───────────────────────────────────────
        msg_section = QWidget()
        msg_section.setStyleSheet(f"background-color: {BG_TERTIARY};")
        msg_layout = QVBoxLayout(msg_section)
        msg_layout.setContentsMargins(48, 24, 48, 0)
        msg_layout.setSpacing(8)

        msg_header = QLabel(texts.DASHBOARD_MESSAGES_HEADER)
        msg_header.setStyleSheet(
            f"font-family: {_tokens.FONT_HEADLINE}; font-size: {FONT_SIZE_H2}; "
            f"font-weight: {FONT_WEIGHT_BOLD}; color: {PRIMARY_900}; background: transparent;"
        )
        msg_layout.addWidget(msg_header)

        msg_div = QFrame()
        msg_div.setFrameShape(QFrame.HLine)
        msg_div.setStyleSheet(
            f"color: {BORDER_DEFAULT}; background: {BORDER_DEFAULT}; max-height: 1px;"
        )
        msg_layout.addWidget(msg_div)

        # Scrollbare Nachrichten-Card
        self._msg_card = QFrame()
        self._msg_card.setStyleSheet(f"""
            QFrame {{
                background-color: {PRIMARY_0};
                border: 1px solid {BORDER_DEFAULT};
                border-radius: {RADIUS_LG};
            }}
        """)
        card_layout = QVBoxLayout(self._msg_card)
        card_layout.setContentsMargins(20, 16, 20, 16)
        card_layout.setSpacing(10)

        self._msg_placeholder = QLabel(texts.DASHBOARD_MESSAGES_LOADING)
        self._msg_placeholder.setStyleSheet(
            f"font-family: {_tokens.FONT_BODY}; font-size: {FONT_SIZE_BODY}; "
            f"color: {PRIMARY_500}; background: transparent; border: none;"
        )
        card_layout.addWidget(self._msg_placeholder)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self._msg_card)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        msg_layout.addWidget(scroll, stretch=1)

        root.addWidget(msg_section, stretch=1)

        # ── Module (am unteren Rand fixiert) ──────────────────────────
        bottom = QWidget()
        bottom.setStyleSheet(f"background-color: {BG_TERTIARY};")
        b_layout = QVBoxLayout(bottom)
        b_layout.setContentsMargins(48, 16, 48, 16)
        b_layout.setSpacing(8)

        mod_header = QLabel(texts.DASHBOARD_MODULES_HEADER)
        mod_header.setStyleSheet(
            f"font-family: {_tokens.FONT_HEADLINE}; font-size: {FONT_SIZE_H2}; "
            f"font-weight: {FONT_WEIGHT_BOLD}; color: {PRIMARY_900}; background: transparent;"
        )
        b_layout.addWidget(mod_header)

        mod_div = QFrame()
        mod_div.setFrameShape(QFrame.HLine)
        mod_div.setStyleSheet(
            f"color: {BORDER_DEFAULT}; background: {BORDER_DEFAULT}; max-height: 1px;"
        )
        b_layout.addWidget(mod_div)
        b_layout.addSpacing(12)

        tiles_row = QHBoxLayout()
        tiles_row.setSpacing(16)
        tiles_row.setAlignment(Qt.AlignLeft)

        _ma_btn_style = f"""
            QPushButton {{
                background-color: {PRIMARY_0};
                border: 1px solid {BORDER_DEFAULT};
                border-radius: {RADIUS_MD};
                padding: 5px 14px;
                text-align: left;
                font-family: {_tokens.FONT_BODY}; font-size: {FONT_SIZE_CAPTION};
                color: {PRIMARY_500};
            }}
            QPushButton:hover {{
                border-color: {ACCENT_500}; color: {ACCENT_500};
            }}
        """

        # -- Core --
        core_group = QVBoxLayout()
        core_group.setSpacing(6)
        tile_core = _ModuleTile(
            texts.DASHBOARD_TILE_CORE, texts.DASHBOARD_TILE_CORE_DESC, PRIMARY_900,
        )
        tile_core.clicked.connect(lambda: self.module_requested.emit("core"))
        core_group.addWidget(tile_core)
        self._tiles["core"] = tile_core

        self._core_admin_btn = QPushButton(f"  \U0001F6E0  {texts.MODULE_ADMIN_BTN}")
        self._core_admin_btn.setCursor(Qt.PointingHandCursor)
        self._core_admin_btn.setFixedWidth(200)
        self._core_admin_btn.setStyleSheet(_ma_btn_style)
        self._core_admin_btn.clicked.connect(lambda: self.module_requested.emit("core_admin"))
        self._core_admin_btn.setVisible(False)
        core_group.addWidget(self._core_admin_btn)
        self._tiles["core_admin"] = self._core_admin_btn

        tiles_row.addLayout(core_group)

        # -- Ledger --
        ledger_group = QVBoxLayout()
        ledger_group.setSpacing(6)
        tile_ledger = _ModuleTile(
            texts.DASHBOARD_TILE_LEDGER, texts.DASHBOARD_TILE_LEDGER_DESC, ACCENT_500,
        )
        tile_ledger.clicked.connect(lambda: self.module_requested.emit("ledger"))
        ledger_group.addWidget(tile_ledger)
        self._tiles["ledger"] = tile_ledger

        self._ledger_admin_btn = QPushButton(f"  \U0001F6E0  {texts.MODULE_ADMIN_BTN}")
        self._ledger_admin_btn.setCursor(Qt.PointingHandCursor)
        self._ledger_admin_btn.setFixedWidth(200)
        self._ledger_admin_btn.setStyleSheet(_ma_btn_style)
        self._ledger_admin_btn.clicked.connect(lambda: self.module_requested.emit("ledger_admin"))
        self._ledger_admin_btn.setVisible(False)
        ledger_group.addWidget(self._ledger_admin_btn)
        self._tiles["ledger_admin"] = self._ledger_admin_btn

        tiles_row.addLayout(ledger_group)

        # -- Workforce --
        wf_group = QVBoxLayout()
        wf_group.setSpacing(6)
        tile_workforce = _ModuleTile(
            texts.WF_DASHBOARD_TILE, texts.WF_DASHBOARD_TILE_DESC, _tokens.SUCCESS,
        )
        tile_workforce.clicked.connect(lambda: self.module_requested.emit("workforce"))
        wf_group.addWidget(tile_workforce)
        self._tiles["workforce"] = tile_workforce

        self._wf_admin_btn = QPushButton(f"  \U0001F6E0  {texts.MODULE_ADMIN_BTN}")
        self._wf_admin_btn.setCursor(Qt.PointingHandCursor)
        self._wf_admin_btn.setFixedWidth(200)
        self._wf_admin_btn.setStyleSheet(_ma_btn_style)
        self._wf_admin_btn.clicked.connect(lambda: self.module_requested.emit("workforce_admin"))
        self._wf_admin_btn.setVisible(False)
        wf_group.addWidget(self._wf_admin_btn)
        self._tiles["workforce_admin"] = self._wf_admin_btn

        tiles_row.addLayout(wf_group)

        # -- Contact (Telefonbuch) --
        contact_group = QVBoxLayout()
        contact_group.setSpacing(6)
        tile_contact = _ModuleTile(
            texts.CONTACT_DASHBOARD_TILE, texts.CONTACT_DASHBOARD_TILE_DESC, INDIGO,
        )
        tile_contact.clicked.connect(lambda: self.module_requested.emit("contact"))
        contact_group.addWidget(tile_contact)
        self._tiles["contact"] = tile_contact

        self._contact_admin_btn = QPushButton(f"  \U0001F6E0  {texts.MODULE_ADMIN_BTN}")
        self._contact_admin_btn.setCursor(Qt.PointingHandCursor)
        self._contact_admin_btn.setFixedWidth(200)
        self._contact_admin_btn.setStyleSheet(_ma_btn_style)
        self._contact_admin_btn.clicked.connect(lambda: self.module_requested.emit("contact_admin"))
        self._contact_admin_btn.setVisible(False)
        contact_group.addWidget(self._contact_admin_btn)
        self._tiles["contact_admin"] = self._contact_admin_btn

        tiles_row.addLayout(contact_group)

        b_layout.addLayout(tiles_row)
        b_layout.addSpacing(4)

        version_text = f"ATLAS v{self._app_version}" if self._app_version else "ATLAS"
        version_label = QLabel(version_text)
        version_label.setAlignment(Qt.AlignRight)
        version_label.setStyleSheet(
            f"font-family: {_tokens.FONT_BODY}; font-size: {FONT_SIZE_CAPTION}; "
            f"color: {ACCENT_500}; background: transparent;"
        )
        b_layout.addWidget(version_label)

        root.addWidget(bottom)

        self._update_clock()

        self._settings_overlay = _SettingsOverlay(self)
        self._settings_overlay.hide()
        self._settings_overlay.close_requested.connect(self._close_settings)
        self._settings_overlay.save_requested.connect(self._on_settings_saved)

    # ------------------------------------------------------------------
    # Settings overlay
    # ------------------------------------------------------------------

    def _open_settings(self):
        if self._settings_overlay.isVisible():
            return
        self._settings_overlay.reset_to_current()
        blur = QGraphicsBlurEffect()
        blur.setBlurRadius(8)
        self._content.setGraphicsEffect(blur)
        self._settings_overlay.setGeometry(self.rect())
        self._settings_overlay.show_animated()

    def _close_settings(self):
        if not self._settings_overlay.isVisible():
            return
        self._settings_overlay.close_animated(
            callback=lambda: self._content.setGraphicsEffect(None)
        )

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
        _tok.apply_font_preset(preset_id)
        _tok.apply_theme(theme_id)
        _i18n_mod.set_language(lang_code)

        app = QApplication.instance()
        app.setStyleSheet(_tok.get_application_stylesheet())

        _body = _tok.FONT_BODY.split(",")[0].strip().strip('"')
        if QFontDatabase.hasFamily(_body):
            app.setFont(QFont(_body, 10))

        QTimer.singleShot(0, self._rebuild_ui)

    def _rebuild_ui(self):
        """Baut die gesamte Dashboard-UI neu auf."""
        self._clock_timer.stop()

        if self._messages_worker and self._messages_worker.isRunning():
            try:
                self._messages_worker.finished.disconnect()
            except RuntimeError:
                pass
        self._messages_worker = None

        old_content = self._content
        old_overlay = self._settings_overlay

        old_content.setGraphicsEffect(None)
        old_content.hide()
        old_overlay.hide()

        self._setup_ui()
        self._content.setGeometry(self.rect())
        self._content.show()

        old_content.deleteLater()
        old_overlay.deleteLater()

        self._clock_timer.start(1_000)

        if self._api_client:
            self.load_messages(self._api_client)

    # ------------------------------------------------------------------
    # Resize
    # ------------------------------------------------------------------

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, '_content'):
            self._content.setGeometry(self.rect())
        if hasattr(self, '_settings_overlay') and self._settings_overlay.isVisible():
            self._settings_overlay.setGeometry(self.rect())

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_modules(self, visible_modules: list[str]):
        for module_id, tile in self._tiles.items():
            tile.setVisible(module_id in visible_modules)
        if hasattr(self, '_admin_header_btn'):
            self._admin_header_btn.setVisible('admin' in visible_modules)

    def load_messages(self, api_client):
        """Startet asynchrones Laden der System-Mitteilungen."""
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

    def on_notifications_updated(self, summary: dict):
        """Empfaengt Notification-Summary vom GlobalHeartbeat.

        Aktualisiert die System-Mitteilungen auf dem Dashboard neu,
        wenn sich die Anzahl ungelesener System-Nachrichten aendert.
        """
        unread_system = summary.get('unread_system_messages', 0)
        prev = getattr(self, '_prev_unread_system', -1)
        if unread_system != prev:
            self._prev_unread_system = unread_system
            if hasattr(self, '_api_client') and self._api_client:
                self._reload_messages()

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _reload_messages(self):
        """Laedt System-Mitteilungen erneut (z.B. bei Heartbeat-Update)."""
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
        """Callback fuer Heartbeat-getriebenes Nachladen der Mitteilungen."""
        layout = self._msg_card.layout()
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        if not messages:
            self._msg_placeholder.setText(texts.DASHBOARD_MESSAGES_EMPTY)
            self._msg_placeholder.show()
            return

        self._msg_placeholder.hide()
        for msg in messages:
            card = self._build_message_card(msg)
            layout.addWidget(card)
        layout.addStretch()

    def _on_messages_loaded(self, messages: list):
        layout = self._msg_card.layout()

        self._msg_placeholder.hide()

        if not messages:
            self._msg_placeholder.setText(texts.DASHBOARD_MESSAGES_EMPTY)
            self._msg_placeholder.show()
            return

        for msg in messages:
            card = self._build_message_card(msg)
            layout.addWidget(card)

        layout.addStretch()

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
                margin-bottom: 2px;
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
