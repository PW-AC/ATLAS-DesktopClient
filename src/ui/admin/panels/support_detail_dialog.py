# -*- coding: utf-8 -*-
"""
ACENCIA ATLAS - Support Feedback Detail-Dialog (Admin)

2-Spalten-Layout mit vollstaendiger Feedback-Ansicht,
Admin-Notizen, Status-/Prioritaets-Aenderung, Screenshot-Preview und Logs-Download.
"""

import logging
import os
import tempfile
from datetime import datetime
from typing import Dict, Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QTextEdit, QFrame, QScrollArea, QWidget,
    QFileDialog,
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont, QPixmap

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

_PRIORITY_LABELS = {
    "low": texts.ADMIN_SUPPORT_PRIORITY_LOW,
    "medium": texts.ADMIN_SUPPORT_PRIORITY_MEDIUM,
    "high": texts.ADMIN_SUPPORT_PRIORITY_HIGH,
}

_PRIORITY_COLORS = {
    "low": SUCCESS,
    "medium": WARNING,
    "high": ERROR,
}


class _LoadDetailWorker(QThread):
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, api_client, feedback_id: int, parent=None):
        super().__init__(parent)
        self._api_client = api_client
        self._feedback_id = feedback_id

    def run(self):
        try:
            api = SupportAPI(self._api_client)
            result = api.get_feedback_detail(self._feedback_id)
            data = result.get("data", result)
            logger.debug(
                "Detail geladen #%s: has_screenshot=%s, has_logs=%s, keys=%s",
                self._feedback_id,
                data.get("has_screenshot"),
                data.get("has_logs"),
                list(data.keys()),
            )
            self.finished.emit(data)
        except Exception as e:
            self.error.emit(str(e))


class _ScreenshotWorker(QThread):
    finished = Signal(bytes)
    error = Signal(str)

    def __init__(self, api_client, feedback_id: int, parent=None):
        super().__init__(parent)
        self._api_client = api_client
        self._feedback_id = feedback_id

    def run(self):
        try:
            api = SupportAPI(self._api_client)
            data = api.get_screenshot(self._feedback_id)
            logger.debug(
                "Screenshot geladen #%s: %d bytes",
                self._feedback_id, len(data) if data else 0,
            )
            self.finished.emit(data)
        except Exception as e:
            logger.error("Screenshot-Worker Fehler #%s: %s", self._feedback_id, e)
            self.error.emit(str(e))


class _ScreenshotFullDialog(QDialog):
    """Vollbild-Ansicht eines Screenshots mit Download-Button."""

    def __init__(self, pixmap: QPixmap, feedback_id: int,
                 raw_bytes: bytes, toast_manager=None, parent=None):
        super().__init__(parent)
        self._pixmap = pixmap
        self._feedback_id = feedback_id
        self._raw_bytes = raw_bytes
        self._toast_manager = toast_manager

        self.setWindowTitle(
            f"{texts.ADMIN_SUPPORT_DETAIL_SCREENSHOT_FULLVIEW_TITLE} – #{feedback_id}"
        )
        self.setMinimumSize(700, 500)
        self.resize(
            min(pixmap.width() + 64, 1200),
            min(pixmap.height() + 120, 900),
        )
        self.setStyleSheet(f"background-color: {PRIMARY_900};")
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setAlignment(Qt.AlignCenter)
        scroll.setStyleSheet(f"""
            QScrollArea {{
                border: none; background-color: {PRIMARY_900};
            }}
            QScrollBar:vertical, QScrollBar:horizontal {{
                background: {PRIMARY_900}; width: 8px; height: 8px;
            }}
            QScrollBar::handle:vertical, QScrollBar::handle:horizontal {{
                background: {PRIMARY_500}; border-radius: 4px;
            }}
        """)

        img_label = QLabel()
        img_label.setAlignment(Qt.AlignCenter)
        img_label.setStyleSheet(f"background: {PRIMARY_900}; padding: 16px;")

        avail_w = min(self._pixmap.width(), 1100)
        avail_h = min(self._pixmap.height(), 780)
        scaled = self._pixmap.scaled(
            avail_w, avail_h, Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        img_label.setPixmap(scaled)
        scroll.setWidget(img_label)
        root.addWidget(scroll, 1)

        footer = QWidget()
        footer.setStyleSheet(f"background-color: {BG_PRIMARY};")
        f_layout = QHBoxLayout(footer)
        f_layout.setContentsMargins(16, 10, 16, 10)

        size_kb = round(len(self._raw_bytes) / 1024, 1)
        info = QLabel(
            f"{self._pixmap.width()} \u00d7 {self._pixmap.height()} px  \u2502  {size_kb} KB"
        )
        info.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: {FONT_SIZE_CAPTION};"
        )
        f_layout.addWidget(info)
        f_layout.addStretch()

        dl_btn = QPushButton(f"\u2B07  {texts.ADMIN_SUPPORT_DETAIL_SCREENSHOT_DOWNLOAD}")
        dl_btn.setCursor(Qt.PointingHandCursor)
        dl_btn.setFixedHeight(34)
        dl_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ACCENT_500}; color: {TEXT_INVERSE};
                border: none; border-radius: {RADIUS_MD}; padding: 0 20px;
                font-size: {FONT_SIZE_BODY}; font-weight: {FONT_WEIGHT_MEDIUM};
            }}
            QPushButton:hover {{ background-color: {ACCENT_HOVER}; }}
        """)
        dl_btn.clicked.connect(self._download)
        f_layout.addWidget(dl_btn)

        close_btn = QPushButton(texts.ADMIN_SUPPORT_DETAIL_CLOSE)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setFixedHeight(34)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: 1px solid {PRIMARY_500};
                border-radius: {RADIUS_MD}; padding: 0 20px;
                font-size: {FONT_SIZE_BODY}; color: {PRIMARY_500};
            }}
            QPushButton:hover {{ color: {PRIMARY_900}; border-color: {PRIMARY_900}; }}
        """)
        close_btn.clicked.connect(self.accept)
        f_layout.addWidget(close_btn)

        root.addWidget(footer)

    def _download(self):
        path, _ = QFileDialog.getSaveFileName(
            self,
            texts.ADMIN_SUPPORT_DETAIL_SCREENSHOT_DOWNLOAD,
            f"screenshot_{self._feedback_id}.png",
            "Images (*.png *.jpg *.jpeg)",
        )
        if not path:
            return
        try:
            with open(path, "wb") as f:
                f.write(self._raw_bytes)
            if self._toast_manager:
                self._toast_manager.show_success(
                    f"{texts.ADMIN_SUPPORT_DETAIL_SCREENSHOT_SAVE_SUCCESS}: "
                    f"{os.path.basename(path)}"
                )
        except Exception as e:
            logger.error("Screenshot save: %s", e)
            if self._toast_manager:
                self._toast_manager.show_error(
                    texts.ADMIN_SUPPORT_DETAIL_SCREENSHOT_SAVE_ERROR
                )


class SupportDetailDialog(QDialog):
    """Detail-Dialog fuer ein einzelnes Support-Feedback."""

    data_changed = Signal()

    def __init__(self, api_client, feedback_id: int,
                 toast_manager=None, parent=None):
        super().__init__(parent)
        self._api_client = api_client
        self._feedback_id = feedback_id
        self._toast_manager = toast_manager
        self._feedback_data: Dict = {}
        self._worker: Optional[_LoadDetailWorker] = None
        self._screenshot_worker: Optional[_ScreenshotWorker] = None
        self._screenshot_bytes: Optional[bytes] = None
        self._screenshot_pixmap: Optional[QPixmap] = None

        self.setWindowTitle(f"{texts.ADMIN_SUPPORT_DETAIL_TITLE} #{feedback_id}")
        self.setMinimumSize(900, 650)
        self.setStyleSheet(f"background-color: {BG_PRIMARY};")

        self._setup_ui()
        self._load_detail()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        header = QWidget()
        header.setStyleSheet(f"background-color: {BG_PRIMARY};")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(24, 20, 24, 16)

        self._header_title = QLabel(texts.ADMIN_SUPPORT_DETAIL_TITLE)
        self._header_title.setFont(QFont(FONT_HEADLINE, 16))
        self._header_title.setStyleSheet(f"color: {PRIMARY_900};")
        h_layout.addWidget(self._header_title, 1)

        self._badges_layout = QHBoxLayout()
        self._badges_layout.setSpacing(8)
        h_layout.addLayout(self._badges_layout)

        root.addWidget(header)

        div = QFrame()
        div.setFrameShape(QFrame.HLine)
        div.setStyleSheet(f"color: {BORDER_DEFAULT}; background: {BORDER_DEFAULT}; max-height: 1px;")
        root.addWidget(div)

        # Two-column body
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        # Left column (60%)
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QFrame.NoFrame)
        left_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        left_widget = QWidget()
        left_widget.setStyleSheet("background: transparent;")
        self._left_layout = QVBoxLayout(left_widget)
        self._left_layout.setContentsMargins(24, 20, 16, 20)
        self._left_layout.setSpacing(16)

        self._subject_label = QLabel("")
        self._subject_label.setFont(QFont(FONT_HEADLINE, 14))
        self._subject_label.setStyleSheet(f"color: {PRIMARY_900};")
        self._subject_label.setWordWrap(True)
        self._left_layout.addWidget(self._subject_label)

        # Description
        desc_lbl = QLabel(texts.ADMIN_SUPPORT_DETAIL_DESCRIPTION)
        desc_lbl.setStyleSheet(
            f"font-family: {FONT_BODY}; font-size: {FONT_SIZE_BODY}; "
            f"font-weight: {FONT_WEIGHT_MEDIUM}; color: {PRIMARY_900};"
        )
        self._left_layout.addWidget(desc_lbl)

        self._desc_text = QTextEdit()
        self._desc_text.setReadOnly(True)
        self._desc_text.setMinimumHeight(160)
        self._desc_text.setMaximumHeight(220)
        self._desc_text.setStyleSheet(self._text_area_style())
        self._left_layout.addWidget(self._desc_text)

        # Reproduction steps
        self._repro_section = QWidget()
        self._repro_section.setVisible(False)
        repro_layout = QVBoxLayout(self._repro_section)
        repro_layout.setContentsMargins(0, 0, 0, 0)
        repro_layout.setSpacing(6)

        repro_lbl = QLabel(texts.ADMIN_SUPPORT_DETAIL_REPRO)
        repro_lbl.setStyleSheet(
            f"font-family: {FONT_BODY}; font-size: {FONT_SIZE_BODY}; "
            f"font-weight: {FONT_WEIGHT_MEDIUM}; color: {PRIMARY_900};"
        )
        repro_layout.addWidget(repro_lbl)

        self._repro_text = QTextEdit()
        self._repro_text.setReadOnly(True)
        self._repro_text.setMinimumHeight(100)
        self._repro_text.setMaximumHeight(160)
        self._repro_text.setStyleSheet(self._text_area_style())
        repro_layout.addWidget(self._repro_text)
        self._left_layout.addWidget(self._repro_section)

        # Admin notes
        notes_lbl = QLabel(texts.ADMIN_SUPPORT_DETAIL_ADMIN_NOTES)
        notes_lbl.setStyleSheet(
            f"font-family: {FONT_BODY}; font-size: {FONT_SIZE_BODY}; "
            f"font-weight: {FONT_WEIGHT_MEDIUM}; color: {PRIMARY_900};"
        )
        self._left_layout.addWidget(notes_lbl)

        self._notes_display = QTextEdit()
        self._notes_display.setReadOnly(True)
        self._notes_display.setMinimumHeight(80)
        self._notes_display.setMaximumHeight(140)
        self._notes_display.setStyleSheet(self._text_area_style())
        self._notes_display.setPlaceholderText("-")
        self._left_layout.addWidget(self._notes_display)

        note_input_row = QHBoxLayout()
        note_input_row.setSpacing(8)

        self._note_input = QTextEdit()
        self._note_input.setPlaceholderText(texts.ADMIN_SUPPORT_DETAIL_NOTE_PLACEHOLDER)
        self._note_input.setMaximumHeight(60)
        self._note_input.setStyleSheet(self._text_area_style())
        note_input_row.addWidget(self._note_input, 1)

        save_note_btn = QPushButton(texts.ADMIN_SUPPORT_DETAIL_SAVE_NOTE)
        save_note_btn.setCursor(Qt.PointingHandCursor)
        save_note_btn.setFixedHeight(40)
        save_note_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ACCENT_500}; color: {TEXT_INVERSE};
                border: none; border-radius: {RADIUS_MD}; padding: 0 16px;
                font-size: {FONT_SIZE_BODY}; font-weight: {FONT_WEIGHT_MEDIUM};
            }}
            QPushButton:hover {{ background-color: {ACCENT_HOVER}; }}
        """)
        save_note_btn.clicked.connect(self._save_note)
        note_input_row.addWidget(save_note_btn)
        self._left_layout.addLayout(note_input_row)

        self._left_layout.addStretch()
        left_scroll.setWidget(left_widget)
        body.addWidget(left_scroll, 6)

        # Vertical divider
        v_div = QFrame()
        v_div.setFrameShape(QFrame.VLine)
        v_div.setStyleSheet(f"color: {BORDER_DEFAULT}; background: {BORDER_DEFAULT}; max-width: 1px;")
        body.addWidget(v_div)

        # Right column (40%)
        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setFrameShape(QFrame.NoFrame)
        right_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        right_widget = QWidget()
        right_widget.setStyleSheet(f"background-color: {BG_TERTIARY};")
        self._right_layout = QVBoxLayout(right_widget)
        self._right_layout.setContentsMargins(16, 20, 24, 20)
        self._right_layout.setSpacing(14)

        # Meta
        self._meta_labels: Dict[str, QLabel] = {}
        meta_fields = [
            ("user", texts.ADMIN_SUPPORT_DETAIL_META_USER),
            ("date", texts.ADMIN_SUPPORT_DETAIL_META_DATE),
            ("version", texts.ADMIN_SUPPORT_DETAIL_META_VERSION),
            ("os", texts.ADMIN_SUPPORT_DETAIL_META_OS),
            ("ram", texts.ADMIN_SUPPORT_DETAIL_META_RAM),
            ("cpu", texts.ADMIN_SUPPORT_DETAIL_META_CPU),
        ]

        for key, label_text in meta_fields:
            row = QHBoxLayout()
            lbl = QLabel(label_text)
            lbl.setStyleSheet(
                f"font-size: {FONT_SIZE_CAPTION}; color: {TEXT_SECONDARY};"
            )
            lbl.setFixedWidth(110)
            row.addWidget(lbl)

            val = QLabel("-")
            val.setStyleSheet(
                f"font-size: {FONT_SIZE_BODY}; color: {PRIMARY_900}; font-weight: {FONT_WEIGHT_MEDIUM};"
            )
            val.setWordWrap(True)
            self._meta_labels[key] = val
            row.addWidget(val, 1)
            self._right_layout.addLayout(row)

        # Screenshot (vor Status/Prioritaet, damit sofort sichtbar)
        self._screenshot_separator = self._build_separator()
        self._screenshot_separator.setVisible(False)
        self._right_layout.addWidget(self._screenshot_separator)

        self._screenshot_section = QWidget()
        self._screenshot_section.setVisible(False)
        ss_layout = QVBoxLayout(self._screenshot_section)
        ss_layout.setContentsMargins(0, 0, 0, 0)
        ss_layout.setSpacing(8)

        ss_lbl = QLabel(texts.ADMIN_SUPPORT_DETAIL_SCREENSHOT_LABEL)
        ss_lbl.setStyleSheet(
            f"font-size: {FONT_SIZE_BODY}; font-weight: {FONT_WEIGHT_MEDIUM}; color: {PRIMARY_900};"
        )
        ss_layout.addWidget(ss_lbl)

        self._screenshot_preview = QLabel()
        self._screenshot_preview.setMinimumSize(280, 200)
        self._screenshot_preview.setMaximumHeight(260)
        self._screenshot_preview.setAlignment(Qt.AlignCenter)
        self._screenshot_preview.setCursor(Qt.PointingHandCursor)
        self._screenshot_preview.setStyleSheet(f"""
            QLabel {{
                background-color: {PRIMARY_100};
                border: 1px solid {BORDER_DEFAULT};
                border-radius: {RADIUS_MD};
            }}
            QLabel:hover {{
                border-color: {ACCENT_500};
                border-width: 2px;
            }}
        """)
        self._screenshot_preview.setText(texts.ADMIN_SUPPORT_DETAIL_SCREENSHOT_LOADING)
        self._screenshot_preview.mousePressEvent = self._on_screenshot_clicked
        ss_layout.addWidget(self._screenshot_preview)

        hint = QLabel(texts.ADMIN_SUPPORT_DETAIL_SCREENSHOT_CLICK_HINT)
        hint.setAlignment(Qt.AlignCenter)
        hint.setStyleSheet(
            f"font-size: {FONT_SIZE_CAPTION}; color: {TEXT_SECONDARY}; font-style: italic;"
        )
        ss_layout.addWidget(hint)

        ss_btn_row = QHBoxLayout()
        ss_btn_row.setSpacing(8)

        ss_download_btn = QPushButton(f"\u2B07  {texts.ADMIN_SUPPORT_DETAIL_SCREENSHOT_DOWNLOAD}")
        ss_download_btn.setCursor(Qt.PointingHandCursor)
        ss_download_btn.setFixedHeight(32)
        ss_download_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ACCENT_500}; color: {TEXT_INVERSE};
                border: none; border-radius: {RADIUS_MD}; padding: 0 14px;
                font-size: {FONT_SIZE_CAPTION}; font-weight: {FONT_WEIGHT_MEDIUM};
            }}
            QPushButton:hover {{ background-color: {ACCENT_HOVER}; }}
        """)
        ss_download_btn.clicked.connect(self._download_screenshot)
        ss_btn_row.addWidget(ss_download_btn)
        ss_btn_row.addStretch()
        ss_layout.addLayout(ss_btn_row)

        self._right_layout.addWidget(self._screenshot_section)

        # Logs
        self._logs_section = QWidget()
        self._logs_section.setVisible(False)
        logs_layout = QVBoxLayout(self._logs_section)
        logs_layout.setContentsMargins(0, 0, 0, 0)
        logs_layout.setSpacing(8)

        logs_lbl = QLabel(texts.ADMIN_SUPPORT_DETAIL_LOGS_LABEL)
        logs_lbl.setStyleSheet(
            f"font-size: {FONT_SIZE_BODY}; font-weight: {FONT_WEIGHT_MEDIUM}; color: {PRIMARY_900};"
        )
        logs_layout.addWidget(logs_lbl)

        self._logs_info = QLabel("")
        self._logs_info.setStyleSheet(f"font-size: {FONT_SIZE_CAPTION}; color: {TEXT_SECONDARY};")
        logs_layout.addWidget(self._logs_info)

        logs_dl_btn = QPushButton(texts.ADMIN_SUPPORT_DETAIL_LOGS_DOWNLOAD)
        logs_dl_btn.setCursor(Qt.PointingHandCursor)
        logs_dl_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: 1px solid {PRIMARY_500};
                border-radius: {RADIUS_MD}; padding: 6px 12px;
                font-size: {FONT_SIZE_CAPTION}; color: {PRIMARY_500};
            }}
            QPushButton:hover {{ color: {PRIMARY_900}; border-color: {PRIMARY_900}; }}
        """)
        logs_dl_btn.clicked.connect(self._download_logs)
        logs_layout.addWidget(logs_dl_btn)
        self._right_layout.addWidget(self._logs_section)

        # Status dropdown
        self._right_layout.addWidget(self._build_separator())

        status_lbl = QLabel(texts.ADMIN_SUPPORT_DETAIL_STATUS_LABEL)
        status_lbl.setStyleSheet(
            f"font-size: {FONT_SIZE_BODY}; font-weight: {FONT_WEIGHT_MEDIUM}; color: {PRIMARY_900};"
        )
        self._right_layout.addWidget(status_lbl)

        self._status_combo = QComboBox()
        self._status_combo.addItem(texts.ADMIN_SUPPORT_STATUS_OPEN, "open")
        self._status_combo.addItem(texts.ADMIN_SUPPORT_STATUS_REVIEW, "review")
        self._status_combo.addItem(texts.ADMIN_SUPPORT_STATUS_CLOSED, "closed")
        self._status_combo.setStyleSheet(self._combo_style())
        self._status_combo.currentIndexChanged.connect(self._on_status_changed)
        self._right_layout.addWidget(self._status_combo)

        # Priority dropdown
        prio_lbl = QLabel(texts.ADMIN_SUPPORT_DETAIL_PRIORITY_LABEL)
        prio_lbl.setStyleSheet(
            f"font-size: {FONT_SIZE_BODY}; font-weight: {FONT_WEIGHT_MEDIUM}; color: {PRIMARY_900};"
        )
        self._right_layout.addWidget(prio_lbl)

        self._prio_combo = QComboBox()
        self._prio_combo.addItem(texts.ADMIN_SUPPORT_PRIORITY_LOW, "low")
        self._prio_combo.addItem(texts.ADMIN_SUPPORT_PRIORITY_MEDIUM, "medium")
        self._prio_combo.addItem(texts.ADMIN_SUPPORT_PRIORITY_HIGH, "high")
        self._prio_combo.setStyleSheet(self._combo_style())
        self._prio_combo.currentIndexChanged.connect(self._on_priority_changed)
        self._right_layout.addWidget(self._prio_combo)

        self._right_layout.addStretch()
        right_scroll.setWidget(right_widget)
        body.addWidget(right_scroll, 4)

        body_widget = QWidget()
        body_widget.setLayout(body)
        root.addWidget(body_widget, 1)

        # Footer
        footer_div = QFrame()
        footer_div.setFrameShape(QFrame.HLine)
        footer_div.setStyleSheet(f"color: {BORDER_DEFAULT}; background: {BORDER_DEFAULT}; max-height: 1px;")
        root.addWidget(footer_div)

        footer = QWidget()
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(24, 12, 24, 16)
        footer_layout.addStretch()

        close_btn = QPushButton(texts.ADMIN_SUPPORT_DETAIL_CLOSE)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setFixedHeight(38)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: 1px solid {PRIMARY_900};
                border-radius: {RADIUS_MD}; padding: 0 24px;
                font-size: {FONT_SIZE_BODY}; color: {PRIMARY_900};
                font-weight: {FONT_WEIGHT_MEDIUM};
            }}
            QPushButton:hover {{ background-color: {PRIMARY_100}; }}
        """)
        close_btn.clicked.connect(self.accept)
        footer_layout.addWidget(close_btn)
        root.addWidget(footer)

    def _text_area_style(self) -> str:
        return f"""
            QTextEdit {{
                border: 1px solid {PRIMARY_100};
                border-radius: {RADIUS_MD};
                padding: 10px;
                font-size: {FONT_SIZE_BODY};
                font-family: {FONT_BODY};
                background-color: {BG_PRIMARY};
            }}
        """

    def _combo_style(self) -> str:
        return f"""
            QComboBox {{
                border: 1px solid {PRIMARY_100};
                border-radius: {RADIUS_MD};
                padding: 6px 10px;
                font-size: {FONT_SIZE_BODY};
            }}
        """

    def _build_separator(self) -> QFrame:
        div = QFrame()
        div.setFrameShape(QFrame.HLine)
        div.setStyleSheet(f"color: {BORDER_DEFAULT}; background: {BORDER_DEFAULT}; max-height: 1px;")
        return div

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def _load_detail(self):
        self._worker = _LoadDetailWorker(self._api_client, self._feedback_id, parent=self)
        self._worker.finished.connect(self._on_detail_loaded)
        self._worker.error.connect(self._on_detail_error)
        self._worker.start()

    def _on_detail_loaded(self, data: dict):
        self._feedback_data = data
        self._populate(data)

    def _on_detail_error(self, msg: str):
        logger.error("Detail laden: %s", msg)
        self._subject_label.setText(texts.ADMIN_SUPPORT_LOAD_ERROR)

    def _populate(self, fb: dict):
        subject = fb.get("subject") or texts.ADMIN_SUPPORT_NO_SUBJECT
        ftype = fb.get("feedback_type", "feedback")
        self._subject_label.setText(subject)
        self._header_title.setText(
            f"{texts.ADMIN_SUPPORT_DETAIL_TITLE} #{fb.get('id', '?')}"
        )

        # Badges
        while self._badges_layout.count():
            item = self._badges_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        type_fg, type_bg = _TYPE_COLORS.get(ftype, (INFO, INFO_LIGHT))
        self._badges_layout.addWidget(
            self._make_badge(_TYPE_LABELS.get(ftype, ftype), type_fg, type_bg)
        )

        prio = fb.get("priority", "low")
        prio_color = _PRIORITY_COLORS.get(prio, INFO)
        self._badges_layout.addWidget(
            self._make_badge(_PRIORITY_LABELS.get(prio, prio), prio_color, f"{prio_color}22")
        )

        status = fb.get("status", "open")
        self._badges_layout.addWidget(
            self._make_badge(_STATUS_LABELS.get(status, status), PRIMARY_500, PRIMARY_100)
        )

        # Description
        self._desc_text.setPlainText(fb.get("content", ""))

        # Repro
        repro = fb.get("reproduction_steps", "")
        if repro:
            self._repro_section.setVisible(True)
            self._repro_text.setPlainText(repro)
        else:
            self._repro_section.setVisible(False)

        # Admin notes
        notes = fb.get("admin_notes", "")
        self._notes_display.setPlainText(notes or "")

        # Meta
        self._meta_labels["user"].setText(fb.get("username", "-"))
        self._meta_labels["user"].setToolTip(
            f"ID: {fb.get('user_id', '?')}, E-Mail: {fb.get('email', '?')}"
        )

        created = fb.get("created_at", "")
        try:
            dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
            self._meta_labels["date"].setText(dt.strftime("%d.%m.%Y %H:%M"))
        except (ValueError, AttributeError):
            self._meta_labels["date"].setText(created)

        self._meta_labels["version"].setText(fb.get("client_version", "-") or "-")
        self._meta_labels["os"].setText(fb.get("os_info", "-") or "-")

        sys_info = fb.get("system_info")
        if isinstance(sys_info, dict):
            ram_total = sys_info.get("ram_total_gb", "-")
            ram_avail = sys_info.get("ram_available_gb", "")
            ram_text = f"{ram_total} GB"
            if ram_avail:
                ram_text += f" ({ram_avail} GB frei)"
            self._meta_labels["ram"].setText(ram_text)

            cpu_count = sys_info.get("cpu_count", "-")
            cpu_phys = sys_info.get("cpu_physical", "")
            cpu_text = f"{cpu_count} Kerne"
            if cpu_phys:
                cpu_text += f" ({cpu_phys} physisch)"
            self._meta_labels["cpu"].setText(cpu_text)
        else:
            self._meta_labels["ram"].setText("-")
            self._meta_labels["cpu"].setText("-")

        # Dropdowns (blockSignals to avoid triggering update)
        self._status_combo.blockSignals(True)
        idx = self._status_combo.findData(status)
        if idx >= 0:
            self._status_combo.setCurrentIndex(idx)
        self._status_combo.blockSignals(False)

        self._prio_combo.blockSignals(True)
        idx = self._prio_combo.findData(prio)
        if idx >= 0:
            self._prio_combo.setCurrentIndex(idx)
        self._prio_combo.blockSignals(False)

        # Screenshot
        raw_ss = fb.get("has_screenshot")
        has_ss = bool(raw_ss) and raw_ss not in (0, "0", "false", False, None)
        logger.info(
            "Feedback #%s: has_screenshot raw=%r -> bool=%s, screenshot_path=%s",
            fb.get("id"), raw_ss, has_ss, fb.get("screenshot_path", "N/A"),
        )
        self._screenshot_section.setVisible(has_ss)
        self._screenshot_separator.setVisible(has_ss)
        if has_ss:
            self._load_screenshot_preview()

        # Logs
        log_files = fb.get("log_files", [])
        if fb.get("has_logs") and log_files:
            self._logs_section.setVisible(True)
            names = [f.get("name", "?") for f in log_files]
            self._logs_info.setText(", ".join(names))
        else:
            self._logs_section.setVisible(fb.get("has_logs", False))

    def _make_badge(self, text: str, fg: str, bg: str) -> QLabel:
        badge = QLabel(text)
        badge.setStyleSheet(f"""
            QLabel {{
                background-color: {bg}; color: {fg};
                border-radius: 4px; padding: 3px 10px;
                font-size: {FONT_SIZE_CAPTION}; font-weight: {FONT_WEIGHT_BOLD};
            }}
        """)
        badge.setFixedHeight(22)
        return badge

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _on_status_changed(self):
        new_status = self._status_combo.currentData()
        if not new_status or new_status == self._feedback_data.get("status"):
            return
        self._update_field(status=new_status)

    def _on_priority_changed(self):
        new_prio = self._prio_combo.currentData()
        if not new_prio or new_prio == self._feedback_data.get("priority"):
            return
        self._update_field(priority=new_prio)

    def _save_note(self):
        note = self._note_input.toPlainText().strip()
        if not note:
            return
        self._update_field(admin_notes=note)
        self._note_input.clear()

    def _update_field(self, **kwargs):
        has_notes = "admin_notes" in kwargs
        fid = self._feedback_id

        class _W(QThread):
            ok = Signal()
            failed = Signal(str)
            def __init__(self, api_client, feedback_id, kw, parent=None):
                super().__init__(parent)
                self._api_client = api_client
                self._fid = feedback_id
                self._kw = kw
            def run(self):
                try:
                    SupportAPI(self._api_client).update_feedback(self._fid, **self._kw)
                    self.ok.emit()
                except Exception as e:
                    self.failed.emit(str(e))

        def _on_ok():
            if has_notes:
                if self._toast_manager:
                    self._toast_manager.show_success(texts.ADMIN_SUPPORT_DETAIL_NOTE_SAVED)
            else:
                if self._toast_manager:
                    self._toast_manager.show_success(texts.ADMIN_SUPPORT_DETAIL_UPDATED)
            self.data_changed.emit()
            self._load_detail()

        def _on_fail(msg):
            logger.error("Feedback-Update: %s", msg)
            if self._toast_manager:
                self._toast_manager.show_error(texts.ADMIN_SUPPORT_DETAIL_UPDATE_ERROR)

        self._update_worker = _W(self._api_client, fid, kwargs, parent=self)
        self._update_worker.ok.connect(_on_ok)
        self._update_worker.failed.connect(_on_fail)
        self._update_worker.start()

    def _load_screenshot_preview(self):
        logger.info("Starte Screenshot-Download fuer Feedback #%s", self._feedback_id)
        self._screenshot_worker = _ScreenshotWorker(
            self._api_client, self._feedback_id, parent=self
        )
        self._screenshot_worker.finished.connect(self._on_screenshot_loaded)
        self._screenshot_worker.error.connect(self._on_screenshot_error)
        self._screenshot_worker.start()

    def _on_screenshot_error(self, msg: str):
        logger.error("Screenshot-Laden fehlgeschlagen #%s: %s", self._feedback_id, msg)
        self._screenshot_preview.setText(
            f"{texts.ADMIN_SUPPORT_DETAIL_SCREENSHOT_NO_PREVIEW}\n({msg[:80]})"
        )

    def _on_screenshot_loaded(self, data: bytes):
        logger.info(
            "Screenshot empfangen #%s: %d bytes", self._feedback_id, len(data) if data else 0
        )
        self._screenshot_bytes = data
        if not data:
            self._screenshot_preview.setText(texts.ADMIN_SUPPORT_DETAIL_SCREENSHOT_NO_PREVIEW)
            return
        pixmap = QPixmap()
        loaded = pixmap.loadFromData(data)
        logger.debug("Pixmap loadFromData: success=%s, isNull=%s", loaded, pixmap.isNull())
        if not pixmap.isNull():
            self._screenshot_pixmap = pixmap
            preview_w = self._screenshot_preview.width() - 8
            preview_h = self._screenshot_preview.maximumHeight() - 8
            scaled = pixmap.scaled(
                max(preview_w, 260), max(preview_h, 190),
                Qt.KeepAspectRatio, Qt.SmoothTransformation,
            )
            self._screenshot_preview.setPixmap(scaled)
        else:
            logger.warning(
                "Screenshot #%s: Pixmap konnte nicht geladen werden (bytes=%d, first_4=%r)",
                self._feedback_id, len(data), data[:4] if data else b"",
            )
            self._screenshot_preview.setText(
                texts.ADMIN_SUPPORT_DETAIL_SCREENSHOT_NO_PREVIEW
            )

    def _on_screenshot_clicked(self, _event):
        if self._screenshot_pixmap is None or self._screenshot_bytes is None:
            return
        dlg = _ScreenshotFullDialog(
            self._screenshot_pixmap,
            self._feedback_id,
            self._screenshot_bytes,
            toast_manager=self._toast_manager,
            parent=self,
        )
        dlg.exec()

    def _download_screenshot(self):
        path, _ = QFileDialog.getSaveFileName(
            self,
            texts.ADMIN_SUPPORT_DETAIL_SCREENSHOT_DOWNLOAD,
            f"screenshot_{self._feedback_id}.png",
            "Images (*.png *.jpg *.jpeg)",
        )
        if not path:
            return

        cached = self._screenshot_bytes

        class _W(QThread):
            ok = Signal(str)
            failed = Signal(str)
            def __init__(self, api_client, fid, dest, data, parent=None):
                super().__init__(parent)
                self._api_client = api_client
                self._fid = fid
                self._dest = dest
                self._data = data
            def run(self):
                try:
                    raw = self._data
                    if not raw:
                        raw = SupportAPI(self._api_client).get_screenshot(self._fid)
                    with open(self._dest, "wb") as f:
                        f.write(raw)
                    self.ok.emit(os.path.basename(self._dest))
                except Exception as e:
                    self.failed.emit(str(e))

        def _on_ok(name):
            if self._toast_manager:
                self._toast_manager.show_success(
                    f"{texts.ADMIN_SUPPORT_DETAIL_SCREENSHOT_SAVE_SUCCESS}: {name}"
                )

        def _on_fail(msg):
            logger.error("Screenshot save: %s", msg)
            if self._toast_manager:
                self._toast_manager.show_error(
                    texts.ADMIN_SUPPORT_DETAIL_SCREENSHOT_SAVE_ERROR
                )

        self._dl_screenshot_worker = _W(
            self._api_client, self._feedback_id, path, cached, parent=self
        )
        self._dl_screenshot_worker.ok.connect(_on_ok)
        self._dl_screenshot_worker.failed.connect(_on_fail)
        self._dl_screenshot_worker.start()

    def _download_logs(self):
        path, _ = QFileDialog.getSaveFileName(
            self,
            texts.ADMIN_SUPPORT_DETAIL_LOGS_DOWNLOAD,
            f"feedback_{self._feedback_id}_logs.zip",
            "ZIP (*.zip)",
        )
        if not path:
            return

        class _W(QThread):
            ok = Signal(str)
            failed = Signal(str)
            def __init__(self, api_client, fid, dest, parent=None):
                super().__init__(parent)
                self._api_client = api_client
                self._fid = fid
                self._dest = dest
            def run(self):
                try:
                    SupportAPI(self._api_client).get_logs_zip(self._fid, self._dest)
                    self.ok.emit(os.path.basename(self._dest))
                except Exception as e:
                    self.failed.emit(str(e))

        def _on_ok(name):
            if self._toast_manager:
                self._toast_manager.show_success(f"Logs gespeichert: {name}")

        def _on_fail(msg):
            logger.error("Logs download: %s", msg)
            if self._toast_manager:
                self._toast_manager.show_error("Logs konnten nicht gespeichert werden")

        self._dl_logs_worker = _W(self._api_client, self._feedback_id, path, parent=self)
        self._dl_logs_worker.ok.connect(_on_ok)
        self._dl_logs_worker.failed.connect(_on_fail)
        self._dl_logs_worker.start()
