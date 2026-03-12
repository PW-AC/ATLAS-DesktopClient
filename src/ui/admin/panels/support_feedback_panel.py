# -*- coding: utf-8 -*-
"""
ACENCIA ATLAS - Support & Feedback Panel (Admin)

Zeigt eingereichte Feedbacks mit Filtern, Tabelle und Detail-Dialog.
Nur fuer Super-Admins sichtbar.
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QComboBox, QHeaderView, QAbstractItemView,
    QMessageBox, QDialog, QTextEdit, QScrollArea, QFrame,
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont, QPixmap, QColor

from i18n import de as texts
from api.support import SupportAPI
from ui.styles.tokens import (
    PRIMARY_900, PRIMARY_500, PRIMARY_100, PRIMARY_0,
    ACCENT_500, ACCENT_HOVER,
    FONT_HEADLINE, FONT_BODY,
    FONT_SIZE_H2, FONT_SIZE_H3, FONT_SIZE_BODY, FONT_SIZE_CAPTION,
    FONT_WEIGHT_BOLD, FONT_WEIGHT_MEDIUM,
    RADIUS_MD, RADIUS_LG,
    BG_PRIMARY, BG_SECONDARY, BG_TERTIARY,
    BORDER_DEFAULT,
    TEXT_INVERSE, TEXT_SECONDARY, TEXT_DISABLED,
    SUCCESS, SUCCESS_LIGHT,
    WARNING, WARNING_LIGHT,
    ERROR, ERROR_LIGHT,
    INFO, INFO_LIGHT,
)

logger = logging.getLogger(__name__)

_TYPE_LABELS = {
    "feedback": texts.ADMIN_SUPPORT_TYPE_FEEDBACK,
    "feature": texts.ADMIN_SUPPORT_TYPE_FEATURE,
    "bug": texts.ADMIN_SUPPORT_TYPE_BUG,
}

_TYPE_COLORS = {
    "feedback": (INFO, INFO_LIGHT),
    "feature": (SUCCESS, SUCCESS_LIGHT),
    "bug": (ERROR, ERROR_LIGHT),
}

_STATUS_LABELS = {
    "open": texts.ADMIN_SUPPORT_STATUS_OPEN,
    "review": texts.ADMIN_SUPPORT_STATUS_REVIEW,
    "closed": texts.ADMIN_SUPPORT_STATUS_CLOSED,
}

_STATUS_ICONS = {
    "open": "\U0001F7E2",
    "review": "\U0001F7E1",
    "closed": "\u26AA",
}

_PRIORITY_LABELS = {
    "low": texts.ADMIN_SUPPORT_PRIORITY_LOW,
    "medium": texts.ADMIN_SUPPORT_PRIORITY_MEDIUM,
    "high": texts.ADMIN_SUPPORT_PRIORITY_HIGH,
}

_PRIORITY_COLORS = {
    "low": (SUCCESS, SUCCESS_LIGHT),
    "medium": (WARNING, WARNING_LIGHT),
    "high": (ERROR, ERROR_LIGHT),
}


class _LoadWorker(QThread):
    finished = Signal(list, dict)
    error = Signal(str)

    def __init__(self, api_client, filters: Dict, parent=None):
        super().__init__(parent)
        self._api_client = api_client
        self._filters = filters

    def run(self):
        try:
            api = SupportAPI(self._api_client)
            result = api.get_all_feedback(**self._filters)
            data = result.get("data", [])
            pagination = result.get("pagination", {})
            self.finished.emit(data, pagination)
        except Exception as e:
            self.error.emit(str(e))


class SupportFeedbackPanel(QWidget):
    """Admin-Panel fuer Support & Feedback Management."""

    def __init__(self, api_client, toast_manager=None, parent=None):
        super().__init__(parent)
        self._api_client = api_client
        self._toast_manager = toast_manager
        self._data: List[Dict] = []
        self._worker: Optional[_LoadWorker] = None
        self._exclude_closed: bool = True
        self._create_ui()

    def load_data(self):
        self._load_feedbacks()

    def _create_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Header
        header = QHBoxLayout()
        header.setSpacing(16)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        title = QLabel(texts.ADMIN_SUPPORT_TITLE)
        title.setFont(QFont(FONT_HEADLINE, 18))
        title.setStyleSheet(f"color: {PRIMARY_900};")
        title_col.addWidget(title)

        subtitle = QLabel(texts.ADMIN_SUPPORT_SUBTITLE)
        subtitle.setStyleSheet(
            f"font-family: {FONT_BODY}; font-size: {FONT_SIZE_BODY}; "
            f"color: {TEXT_SECONDARY};"
        )
        title_col.addWidget(subtitle)
        header.addLayout(title_col, 1)

        self._count_label = QLabel("")
        self._count_label.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: {FONT_SIZE_BODY};"
        )
        header.addWidget(self._count_label)

        refresh_btn = QPushButton(f"\u21BB  {texts.ADMIN_SUPPORT_REFRESH}")
        refresh_btn.setCursor(Qt.PointingHandCursor)
        refresh_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: 1px solid {PRIMARY_500};
                border-radius: {RADIUS_MD};
                padding: 8px 16px;
                font-size: {FONT_SIZE_BODY};
                color: {PRIMARY_500};
            }}
            QPushButton:hover {{
                color: {PRIMARY_900}; border-color: {PRIMARY_900};
            }}
        """)
        refresh_btn.clicked.connect(self._load_feedbacks)
        header.addWidget(refresh_btn)
        layout.addLayout(header)

        # Filters
        filter_row = QHBoxLayout()
        filter_row.setSpacing(12)

        type_label = QLabel(f"{texts.ADMIN_SUPPORT_COL_TYPE}:")
        type_label.setStyleSheet(f"font-size: {FONT_SIZE_BODY}; color: {PRIMARY_900};")
        filter_row.addWidget(type_label)

        self._type_filter = QComboBox()
        self._type_filter.addItem(texts.ADMIN_SUPPORT_FILTER_ALL, "")
        self._type_filter.addItem(texts.ADMIN_SUPPORT_FILTER_FEEDBACK, "feedback")
        self._type_filter.addItem(texts.ADMIN_SUPPORT_FILTER_FEATURE, "feature")
        self._type_filter.addItem(texts.ADMIN_SUPPORT_FILTER_BUG, "bug")
        self._type_filter.setStyleSheet(self._combo_style())
        self._type_filter.currentIndexChanged.connect(self._load_feedbacks)
        filter_row.addWidget(self._type_filter)

        prio_label = QLabel(f"{texts.ADMIN_SUPPORT_FILTER_PRIORITY}:")
        prio_label.setStyleSheet(f"font-size: {FONT_SIZE_BODY}; color: {PRIMARY_900};")
        filter_row.addWidget(prio_label)

        self._prio_filter = QComboBox()
        self._prio_filter.addItem(texts.ADMIN_SUPPORT_FILTER_ALL, "")
        self._prio_filter.addItem(texts.ADMIN_SUPPORT_PRIORITY_LOW, "low")
        self._prio_filter.addItem(texts.ADMIN_SUPPORT_PRIORITY_MEDIUM, "medium")
        self._prio_filter.addItem(texts.ADMIN_SUPPORT_PRIORITY_HIGH, "high")
        self._prio_filter.setStyleSheet(self._combo_style())
        self._prio_filter.currentIndexChanged.connect(self._load_feedbacks)
        filter_row.addWidget(self._prio_filter)

        status_label = QLabel(f"{texts.ADMIN_SUPPORT_FILTER_STATUS}:")
        status_label.setStyleSheet(f"font-size: {FONT_SIZE_BODY}; color: {PRIMARY_900};")
        filter_row.addWidget(status_label)

        self._status_filter = QComboBox()
        self._status_filter.addItem(texts.ADMIN_SUPPORT_FILTER_ACTIVE, "active")
        self._status_filter.addItem(texts.ADMIN_SUPPORT_FILTER_ALL, "")
        self._status_filter.addItem(texts.ADMIN_SUPPORT_STATUS_OPEN, "open")
        self._status_filter.addItem(texts.ADMIN_SUPPORT_STATUS_REVIEW, "review")
        self._status_filter.addItem(texts.ADMIN_SUPPORT_STATUS_CLOSED, "closed")
        self._status_filter.setStyleSheet(self._combo_style())
        self._status_filter.currentIndexChanged.connect(self._load_feedbacks)
        filter_row.addWidget(self._status_filter)

        filter_row.addStretch()
        layout.addLayout(filter_row)

        # Table
        self._table = QTableWidget()
        self._table.setColumnCount(8)
        self._table.setHorizontalHeaderLabels([
            texts.ADMIN_SUPPORT_COL_STATUS,
            texts.ADMIN_SUPPORT_COL_PRIORITY,
            texts.ADMIN_SUPPORT_COL_TYPE,
            texts.ADMIN_SUPPORT_COL_SUBJECT,
            texts.ADMIN_SUPPORT_COL_USER,
            texts.ADMIN_SUPPORT_COL_VERSION,
            texts.ADMIN_SUPPORT_COL_DATE,
            texts.ADMIN_SUPPORT_COL_ACTIONS,
        ])
        self._table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.Stretch
        )
        self._table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Fixed
        )
        self._table.setColumnWidth(0, 140)
        self._table.horizontalHeader().setSectionResizeMode(
            7, QHeaderView.ResizeMode.Fixed
        )
        self._table.setColumnWidth(7, 220)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.setAlternatingRowColors(True)
        self._table.setStyleSheet(f"""
            QTableWidget {{
                border: 1px solid {PRIMARY_100};
                border-radius: {RADIUS_MD};
                gridline-color: {PRIMARY_100};
                font-size: {FONT_SIZE_BODY};
            }}
            QTableWidget::item {{
                padding: 6px 8px;
            }}
        """)
        self._table.doubleClicked.connect(self._on_row_double_clicked)
        layout.addWidget(self._table)

    def _combo_style(self) -> str:
        return f"""
            QComboBox {{
                border: 1px solid {PRIMARY_100};
                border-radius: {RADIUS_MD};
                padding: 6px 10px;
                font-size: {FONT_SIZE_BODY};
                min-width: 100px;
            }}
        """

    def _load_feedbacks(self):
        if self._worker and self._worker.isRunning():
            return

        status_val = self._status_filter.currentData()
        self._exclude_closed = (status_val == "active")

        filters = {
            "feedback_type": self._type_filter.currentData() or None,
            "priority": self._prio_filter.currentData() or None,
            "status": None if status_val in ("", "active") else status_val,
            "page": 1,
            "per_page": 100,
        }
        filters = {k: v for k, v in filters.items() if v is not None}

        self._worker = _LoadWorker(self._api_client, filters, parent=self)
        self._worker.finished.connect(self._on_data_loaded)
        self._worker.error.connect(self._on_load_error)
        self._worker.start()

    def _on_data_loaded(self, data: list, pagination: dict):
        if self._exclude_closed:
            data = [fb for fb in data if fb.get("status") != "closed"]
        self._data = data
        self._count_label.setText(texts.ADMIN_SUPPORT_COUNT.format(count=len(data)))
        self._populate_table()

    def _on_load_error(self, msg: str):
        logger.error("Support-Feedbacks laden: %s", msg)
        if self._toast_manager:
            self._toast_manager.show_error(texts.ADMIN_SUPPORT_LOAD_ERROR)

    def _populate_table(self):
        self._table.setRowCount(len(self._data))

        for row, fb in enumerate(self._data):
            self._table.setRowHeight(row, 44)

            # Status
            status = fb.get("status", "open")
            icon = _STATUS_ICONS.get(status, "")
            label = _STATUS_LABELS.get(status, status)
            item = QTableWidgetItem(f"{icon} {label}")
            self._table.setItem(row, 0, item)

            # Priority
            prio = fb.get("priority", "low")
            prio_fg, prio_bg = _PRIORITY_COLORS.get(prio, (INFO, INFO_LIGHT))
            prio_item = QTableWidgetItem(_PRIORITY_LABELS.get(prio, prio))
            prio_item.setForeground(QColor(prio_fg))
            self._table.setItem(row, 1, prio_item)

            # Type
            ftype = fb.get("feedback_type", "feedback")
            type_fg, type_bg = _TYPE_COLORS.get(ftype, (INFO, INFO_LIGHT))
            type_item = QTableWidgetItem(_TYPE_LABELS.get(ftype, ftype))
            type_item.setForeground(QColor(type_fg))
            self._table.setItem(row, 2, type_item)

            # Subject
            subject = fb.get("subject") or texts.ADMIN_SUPPORT_NO_SUBJECT
            has_screenshot = fb.get("has_screenshot", False)
            if has_screenshot:
                subject = f"\U0001F4F7 {subject}"
            self._table.setItem(row, 3, QTableWidgetItem(subject))

            # User
            username = fb.get("username", "")
            self._table.setItem(row, 4, QTableWidgetItem(username))

            # Version
            version = fb.get("client_version", "")
            self._table.setItem(row, 5, QTableWidgetItem(version or "-"))

            # Date
            created = fb.get("created_at", "")
            date_str = self._format_date(created)
            date_item = QTableWidgetItem(date_str)
            date_item.setToolTip(created)
            self._table.setItem(row, 6, date_item)

            # Actions
            actions = QWidget()
            actions_layout = QHBoxLayout(actions)
            actions_layout.setContentsMargins(6, 6, 6, 6)
            actions_layout.setSpacing(8)

            detail_btn = QPushButton(texts.ADMIN_SUPPORT_DETAIL_BTN)
            detail_btn.setCursor(Qt.PointingHandCursor)
            detail_btn.setFixedHeight(28)
            detail_btn.setStyleSheet(self._action_btn_style(ACCENT_500))
            detail_btn.clicked.connect(
                lambda checked, fid=fb.get("id"): self._open_detail(fid)
            )
            actions_layout.addWidget(detail_btn)

            del_btn = QPushButton(texts.ADMIN_SUPPORT_DELETE_BTN)
            del_btn.setCursor(Qt.PointingHandCursor)
            del_btn.setFixedHeight(28)
            del_btn.setStyleSheet(self._action_btn_style(ERROR))
            del_btn.clicked.connect(
                lambda checked, fid=fb.get("id"): self._delete_feedback(fid)
            )
            actions_layout.addWidget(del_btn)

            self._table.setCellWidget(row, 7, actions)

    def _action_btn_style(self, color: str) -> str:
        return f"""
            QPushButton {{
                color: {color};
                background: transparent;
                border: 1px solid {color};
                border-radius: 4px;
                padding: 5px 14px;
                font-size: {FONT_SIZE_CAPTION};
                font-weight: 500;
                min-width: 80px;
            }}
            QPushButton:hover {{
                background-color: rgba({self._hex_to_rgb(color)}, 0.08);
            }}
        """

    @staticmethod
    def _hex_to_rgb(hex_color: str) -> str:
        h = hex_color.lstrip("#")
        return f"{int(h[:2], 16)}, {int(h[2:4], 16)}, {int(h[4:6], 16)}"

    @staticmethod
    def _format_date(iso_str: str) -> str:
        try:
            dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
            now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
            diff = now - dt
            if diff.total_seconds() < 3600:
                mins = max(1, int(diff.total_seconds() / 60))
                return f"vor {mins} Min"
            elif diff.total_seconds() < 86400:
                hours = int(diff.total_seconds() / 3600)
                return f"vor {hours} Std"
            elif diff.days < 7:
                return f"vor {diff.days} Tagen"
            else:
                return dt.strftime("%d.%m.%Y")
        except (ValueError, AttributeError):
            return iso_str[:10] if len(iso_str) >= 10 else iso_str

    def _on_row_double_clicked(self, index):
        row = index.row()
        if 0 <= row < len(self._data):
            fb_id = self._data[row].get("id")
            if fb_id:
                self._open_detail(fb_id)

    def _open_detail(self, feedback_id: int):
        from ui.admin.panels.support_detail_dialog import SupportDetailDialog
        dialog = SupportDetailDialog(
            self._api_client, feedback_id,
            toast_manager=self._toast_manager, parent=self
        )
        dialog.data_changed.connect(self._load_feedbacks)
        dialog.exec()

    def _delete_feedback(self, feedback_id: int):
        reply = QMessageBox.question(
            self,
            texts.ADMIN_SUPPORT_DELETE_BTN,
            texts.ADMIN_SUPPORT_DELETE_CONFIRM.format(id=feedback_id),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        from ui.async_worker import AsyncWorker
        self._del_fb_worker = AsyncWorker(
            lambda: SupportAPI(self._api_client).delete_feedback(feedback_id),
            parent=self,
        )

        def _on_ok(_):
            if self._toast_manager:
                self._toast_manager.show_success(texts.ADMIN_SUPPORT_DELETED)
            self._load_feedbacks()

        def _on_err(msg):
            logger.error("Feedback loeschen: %s", msg)
            if self._toast_manager:
                self._toast_manager.show_error(texts.ADMIN_SUPPORT_DELETE_ERROR)

        self._del_fb_worker.finished.connect(_on_ok)
        self._del_fb_worker.error.connect(_on_err)
        self._del_fb_worker.start()
