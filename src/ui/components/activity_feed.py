# -*- coding: utf-8 -*-
"""
ACENCIA ATLAS - Aktivitaets-Feed fuer das Dashboard

Zeigt die letzten Aktivitaeten an, gefiltert nach Modul-Berechtigungen.
Aktivitaeten aus Modulen ohne Zugriff werden ausgeblendet.
"""

import logging
from datetime import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QSizePolicy,
)
from PySide6.QtCore import Signal, Qt

from i18n import de as texts
from api.auth import User
import ui.styles.tokens as _tok

logger = logging.getLogger(__name__)

_DOT_COLORS = {
    "core": _tok.SUCCESS,
    "provision": _tok.INDIGO,
    "workforce": _tok.ACCENT_500,
    "contact": _tok.CYAN,
    "system": _tok.PRIMARY_500,
}


class _ActivityItem(QFrame):
    """Einzelner Eintrag im Aktivitaets-Feed."""

    def __init__(self, text: str, time_str: str, module: str = "", parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QFrame {{
                border-bottom: 1px solid {_tok.BORDER_DEFAULT};
                background: transparent;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(12)

        dot = QFrame()
        dot.setFixedSize(8, 8)
        dot_color = _DOT_COLORS.get(module, _tok.PRIMARY_500)
        dot.setStyleSheet(
            f"background-color: {dot_color}; border-radius: 4px; border: none;"
        )
        layout.addWidget(dot, alignment=Qt.AlignTop)

        content = QVBoxLayout()
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(2)

        text_lbl = QLabel(text)
        text_lbl.setWordWrap(True)
        text_lbl.setStyleSheet(
            f"font-family: {_tok.FONT_BODY}; font-size: {_tok.FONT_SIZE_BODY}; "
            f"color: {_tok.PRIMARY_900}; background: transparent; border: none;"
        )
        content.addWidget(text_lbl)

        time_lbl = QLabel(time_str)
        time_lbl.setStyleSheet(
            f"font-family: {_tok.FONT_BODY}; font-size: {_tok.FONT_SIZE_CAPTION}; "
            f"color: {_tok.TEXT_SECONDARY}; background: transparent; border: none;"
        )
        content.addWidget(time_lbl)

        layout.addLayout(content, 1)


class ActivityFeedWidget(QWidget):
    """Aktivitaets-Feed-Card mit Modul-Filterung."""

    show_all_requested = Signal()

    def __init__(self, user: User, parent=None):
        super().__init__(parent)
        self._user = user

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

        title = QLabel(texts.ACTIVITY_FEED_TITLE)
        title.setStyleSheet(
            f"font-family: {_tok.FONT_BODY}; font-size: {_tok.FONT_SIZE_BODY}; "
            f"font-weight: {_tok.FONT_WEIGHT_BOLD}; color: {_tok.PRIMARY_900}; "
            f"background: transparent; border: none;"
        )
        h_layout.addWidget(title)
        h_layout.addStretch()

        all_link = QLabel(texts.ACTIVITY_FEED_ALL)
        all_link.setCursor(Qt.PointingHandCursor)
        all_link.setStyleSheet(
            f"font-size: {_tok.FONT_SIZE_CAPTION}; color: {_tok.ACCENT_500}; "
            f"background: transparent; border: none;"
        )
        h_layout.addWidget(all_link)
        card_layout.addWidget(header)

        self._body = QVBoxLayout()
        self._body.setContentsMargins(20, 8, 20, 16)
        self._body.setSpacing(0)
        card_layout.addLayout(self._body)

        self._empty_label = QLabel(texts.ACTIVITY_FEED_EMPTY)
        self._empty_label.setStyleSheet(
            f"font-family: {_tok.FONT_BODY}; font-size: {_tok.FONT_SIZE_BODY}; "
            f"color: {_tok.TEXT_SECONDARY}; background: transparent; border: none;"
        )
        self._body.addWidget(self._empty_label)

        outer.addWidget(self._card)

    def set_activities(self, activities: list):
        """Aktualisiert den Feed mit neuen Aktivitaeten (gefiltert nach Berechtigungen)."""
        self._clear()
        filtered = self._filter_activities(activities)

        if not filtered:
            self._empty_label.show()
            return

        self._empty_label.hide()
        for act in filtered[:6]:
            item = _ActivityItem(
                text=act.get("text", ""),
                time_str=act.get("time", ""),
                module=act.get("module", ""),
            )
            self._body.addWidget(item)

    def _filter_activities(self, activities: list) -> list:
        filtered = []
        for activity in activities:
            module = activity.get("module")
            if not module or module == "system":
                filtered.append(activity)
                continue
            if self._user.has_module(module):
                filtered.append(activity)
        return filtered

    def _clear(self):
        while self._body.count() > 1:
            item = self._body.takeAt(1)
            w = item.widget()
            if w and w is not self._empty_label:
                w.deleteLater()
