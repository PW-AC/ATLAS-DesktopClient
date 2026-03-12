# -*- coding: utf-8 -*-
"""
ACENCIA ATLAS - KPI-Karten fuer das Dashboard

Zeigt kompakte Kennzahlen-Karten an. Jede Karte wird nur dargestellt,
wenn der Nutzer die entsprechende Modul-Berechtigung hat.
Daten werden asynchron geladen; waehrend des Ladens wird ein Skeleton angezeigt.
"""

import logging
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QFrame,
    QSizePolicy, QGraphicsDropShadowEffect,
)
from PySide6.QtCore import Signal, Qt, QThread, QTimer
from PySide6.QtGui import QColor

from i18n import de as texts
from api.auth import User
import ui.styles.tokens as _tok

logger = logging.getLogger(__name__)


class _SingleKpiCard(QFrame):
    """Einzelne KPI-Karte mit Wert und Beschriftung."""

    clicked = Signal(str)

    def __init__(self, card_id: str, label: str, parent=None):
        super().__init__(parent)
        self._card_id = card_id
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(_tok.KPI_CARD_MIN_HEIGHT)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self._apply_style(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(4)

        self._value_label = QLabel(texts.KPI_LOADING)
        self._value_label.setStyleSheet(
            f"font-family: {_tok.FONT_HEADLINE}; font-size: 22pt; "
            f"font-weight: {_tok.FONT_WEIGHT_BOLD}; color: {_tok.PRIMARY_900}; "
            f"background: transparent; border: none;"
        )
        layout.addWidget(self._value_label)

        self._desc_label = QLabel(label)
        self._desc_label.setStyleSheet(
            f"font-family: {_tok.FONT_BODY}; font-size: {_tok.FONT_SIZE_CAPTION}; "
            f"color: {_tok.TEXT_SECONDARY}; background: transparent; border: none;"
        )
        layout.addWidget(self._desc_label)

    def set_value(self, value: int, highlight: bool = False):
        self._value_label.setText(str(value))
        color = _tok.ACCENT_500 if highlight and value > 0 else _tok.PRIMARY_900
        self._value_label.setStyleSheet(
            f"font-family: {_tok.FONT_HEADLINE}; font-size: 22pt; "
            f"font-weight: {_tok.FONT_WEIGHT_BOLD}; color: {color}; "
            f"background: transparent; border: none;"
        )

    def set_loading(self):
        self._value_label.setText(texts.KPI_LOADING)

    def mousePressEvent(self, event):
        self.clicked.emit(self._card_id)
        super().mousePressEvent(event)

    def enterEvent(self, event):
        self._apply_style(True)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._apply_style(False)
        super().leaveEvent(event)

    def _apply_style(self, hovered: bool):
        border_color = _tok.ACCENT_500 if hovered else _tok.BORDER_DEFAULT
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {_tok.PRIMARY_0};
                border: 1px solid {border_color};
                border-radius: {_tok.RADIUS_LG};
            }}
        """)


class _KpiLoadWorker(QThread):
    """Laedt KPI-Werte asynchron."""

    finished = Signal(dict)

    def __init__(self, api_client, user: User, parent=None):
        super().__init__(parent)
        self._api_client = api_client
        self._user = user

    def run(self):
        results = {}
        try:
            if self._user.has_module("core"):
                results.update(self._load_core_kpis())
            results.update(self._load_message_kpis())
        except Exception:
            logger.exception("KPI-Daten konnten nicht geladen werden")
        self.finished.emit(results)

    def _load_core_kpis(self) -> dict:
        data = {}
        try:
            from api.documents import DocumentsAPI
            doc_api = DocumentsAPI(self._api_client)
            stats = doc_api.get_box_stats()
            data["inbox"] = stats.eingang
        except Exception:
            data["inbox"] = 0
        return data

    def _load_message_kpis(self) -> dict:
        data = {}
        try:
            from api.messages import MessagesAPI
            msg_api = MessagesAPI(self._api_client)
            result = msg_api.get_messages(page=1, per_page=1)
            data["messages"] = result.get("pagination", {}).get("total", 0)
        except Exception:
            data["messages"] = 0
        return data


class KpiCardsWidget(QWidget):
    """Zeile von KPI-Karten, gefiltert nach Modul-Berechtigungen."""

    card_clicked = Signal(str)

    def __init__(self, user: User, api_client=None, parent=None):
        super().__init__(parent)
        self._user = user
        self._api_client = api_client
        self._cards: dict[str, _SingleKpiCard] = {}
        self._worker: Optional[_KpiLoadWorker] = None

        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(16)

        self._build_cards()

    def _build_cards(self):
        if self._user.has_module("core"):
            self._add_card("inbox", texts.KPI_INBOX, True)

        self._add_card("messages", texts.KPI_MESSAGES, True)

    def _add_card(self, card_id: str, label: str, highlight: bool):
        card = _SingleKpiCard(card_id, label)
        card._highlight = highlight
        card.clicked.connect(self.card_clicked.emit)
        self._cards[card_id] = card
        self._layout.addWidget(card)

    def load_data(self, api_client=None):
        if api_client:
            self._api_client = api_client
        if not self._api_client:
            return
        if self._worker and self._worker.isRunning():
            return

        for card in self._cards.values():
            card.set_loading()

        self._worker = _KpiLoadWorker(self._api_client, self._user, parent=self)
        self._worker.finished.connect(self._on_data_loaded)
        self._worker.start()

    def _on_data_loaded(self, data: dict):
        for card_id, card in self._cards.items():
            value = data.get(card_id, 0)
            card.set_value(value, highlight=getattr(card, '_highlight', False))
