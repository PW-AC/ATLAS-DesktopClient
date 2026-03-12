# -*- coding: utf-8 -*-
"""
ACENCIA ATLAS - Schnellaktionen-Widget

Zeigt kontextbasierte Schnellaktionen an, gefiltert nach Modul-Berechtigungen.
Aktionen, die Admin-Rechte erfordern, werden nur bei entsprechendem Zugriff angezeigt.
"""

import logging

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QSizePolicy,
)
from PySide6.QtCore import Signal, Qt

from i18n import de as texts
from api.auth import User
import ui.styles.tokens as _tok

logger = logging.getLogger(__name__)


class _ActionRow(QFrame):
    """Einzelne Schnellaktion als klickbare Zeile."""

    clicked = Signal(str)

    def __init__(self, action_id: str, icon: str, label: str, parent=None):
        super().__init__(parent)
        self._action_id = action_id
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(f"""
            QFrame {{
                background: transparent; border: none;
                border-radius: {_tok.RADIUS_MD};
            }}
            QFrame:hover {{
                background-color: {_tok.BG_TERTIARY};
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 6, 0, 6)
        layout.setSpacing(12)

        icon_box = QFrame()
        icon_box.setFixedSize(32, 32)
        icon_box.setStyleSheet(f"""
            QFrame {{
                background-color: {_tok.PRIMARY_100};
                border-radius: {_tok.RADIUS_MD};
                border: none;
            }}
        """)
        icon_lbl = QLabel(icon)
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setStyleSheet(
            f"font-size: 14px; background: transparent; border: none;"
        )
        icon_lbl.setAttribute(Qt.WA_TransparentForMouseEvents)
        ib_layout = QVBoxLayout(icon_box)
        ib_layout.setContentsMargins(0, 0, 0, 0)
        ib_layout.addWidget(icon_lbl)
        icon_box.setAttribute(Qt.WA_TransparentForMouseEvents)
        layout.addWidget(icon_box)

        text_lbl = QLabel(label)
        text_lbl.setStyleSheet(
            f"font-family: {_tok.FONT_BODY}; font-size: {_tok.FONT_SIZE_BODY}; "
            f"font-weight: {_tok.FONT_WEIGHT_MEDIUM}; color: {_tok.PRIMARY_900}; "
            f"background: transparent; border: none;"
        )
        text_lbl.setAttribute(Qt.WA_TransparentForMouseEvents)
        layout.addWidget(text_lbl, 1)

    def mousePressEvent(self, event):
        self.clicked.emit(self._action_id)
        super().mousePressEvent(event)

    def enterEvent(self, event):
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {_tok.BG_TERTIARY};
                border: none; border-radius: {_tok.RADIUS_MD};
            }}
        """)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.setStyleSheet(f"""
            QFrame {{
                background: transparent; border: none;
                border-radius: {_tok.RADIUS_MD};
            }}
        """)
        super().leaveEvent(event)


class QuickActionsWidget(QWidget):
    """Schnellaktionen-Card, gefiltert nach User-Berechtigungen."""

    action_requested = Signal(str)

    def __init__(self, user: User, parent=None):
        super().__init__(parent)
        self._user = user
        self._actions: list[_ActionRow] = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._card = QFrame()
        self._card.setStyleSheet(f"""
            QFrame {{
                background-color: {_tok.PRIMARY_0};
                border: 1px solid {_tok.BORDER_DEFAULT};
                border-radius: {_tok.RADIUS_LG};
            }}
        """)
        card_layout = QVBoxLayout(self._card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        header = QFrame()
        header.setStyleSheet(
            f"border-bottom: 1px solid {_tok.BORDER_DEFAULT}; "
            f"background: transparent;"
        )
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(20, 14, 20, 14)
        title = QLabel(texts.QUICK_ACTIONS_TITLE)
        title.setStyleSheet(
            f"font-family: {_tok.FONT_BODY}; font-size: {_tok.FONT_SIZE_BODY}; "
            f"font-weight: {_tok.FONT_WEIGHT_BOLD}; color: {_tok.PRIMARY_900}; "
            f"background: transparent; border: none;"
        )
        h_layout.addWidget(title)
        h_layout.addStretch()
        card_layout.addWidget(header)

        self._body = QVBoxLayout()
        self._body.setContentsMargins(20, 10, 20, 16)
        self._body.setSpacing(2)
        card_layout.addLayout(self._body)

        outer.addWidget(self._card)

        self._build_actions()

    def _build_actions(self):
        if self._user.has_module("core"):
            self._add_action("open_inbox", "\U0001F4E5", texts.QA_OPEN_INBOX)
            self._add_action("upload_doc", "\U0001F4E4", texts.QA_UPLOAD_DOC)
            if self._user.is_module_admin("core"):
                self._add_action("bipro_fetch", "\U0001F504", texts.QA_BIPRO_FETCH)

        if self._user.has_module("contact"):
            self._add_action("search_phone", "\U0001F50D", texts.QA_SEARCH_PHONE)
            self._add_action("new_call_note", "\U0001F4DD", texts.QA_NEW_CALL_NOTE)

        if self._user.has_module("workforce"):
            self._add_action("search_employee", "\U0001F464", texts.QA_SEARCH_EMPLOYEE)

        if self._user.has_module("provision"):
            self._add_action("check_provision", "\U0001F4B0", texts.QA_CHECK_PROVISION)

        if not self._actions:
            self.hide()

    def _add_action(self, action_id: str, icon: str, label: str):
        row = _ActionRow(action_id, icon, label)
        row.clicked.connect(self.action_requested.emit)
        self._actions.append(row)
        self._body.addWidget(row)

    def has_actions(self) -> bool:
        return len(self._actions) > 0
