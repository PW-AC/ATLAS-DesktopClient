"""
Provisions-Einstellungen Panel - Gefahrenzone mit Reset-Funktion.

Ermoeglicht das Zuruecksetzen aller Import-Daten fuer einen kompletten Neuimport.
Mitarbeiter, Modelle und Vermittler-Zuordnungen bleiben erhalten.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QDialog, QProgressBar, QSizePolicy,
)
from PySide6.QtCore import Signal, Qt, QTimer, QThread

from api.provision import ProvisionAPI
from ui.styles.tokens import (
    PRIMARY_0, PRIMARY_500, PRIMARY_900, ACCENT_500,
    FONT_BODY, FONT_HEADLINE, FONT_SIZE_H2, FONT_SIZE_BODY, FONT_SIZE_CAPTION,
    DANGER_500, SUCCESS_500,
)
from i18n import de as texts

import logging

logger = logging.getLogger(__name__)


class _ResetWorker(QThread):
    """Worker fuer den Datenbank-Reset (async)."""
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, api: ProvisionAPI):
        super().__init__()
        self._api = api

    def run(self):
        try:
            result = self._api.reset_provision_data()
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class ResetConfirmDialog(QDialog):
    """Bestaetigungsdialog mit 3-Sekunden-Countdown."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(texts.PROVISION_SETTINGS_RESET_CONFIRM_TITLE)
        self.setFixedSize(480, 320)
        self.setModal(True)

        self._countdown = 3
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)

        icon_lbl = QLabel("\u26A0\uFE0F")
        icon_lbl.setStyleSheet("font-size: 48pt;")
        icon_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(icon_lbl)

        title = QLabel(texts.PROVISION_SETTINGS_RESET_CONFIRM_TITLE)
        title.setStyleSheet(f"""
            font-family: {FONT_HEADLINE};
            font-size: {FONT_SIZE_H2};
            font-weight: 700;
            color: {DANGER_500};
        """)
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        desc = QLabel(texts.PROVISION_SETTINGS_RESET_CONFIRM_DESC)
        desc.setWordWrap(True)
        desc.setStyleSheet(f"""
            font-family: {FONT_BODY};
            font-size: {FONT_SIZE_BODY};
            color: {PRIMARY_500};
            line-height: 1.5;
        """)
        desc.setAlignment(Qt.AlignCenter)
        layout.addWidget(desc)

        layout.addStretch()

        self._countdown_lbl = QLabel(texts.PROVISION_SETTINGS_RESET_COUNTDOWN.format(seconds=self._countdown))
        self._countdown_lbl.setStyleSheet(f"""
            font-family: {FONT_BODY};
            font-size: {FONT_SIZE_BODY};
            color: {ACCENT_500};
            font-weight: 600;
        """)
        self._countdown_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._countdown_lbl)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(16)

        self._cancel_btn = QPushButton(texts.PROVISION_SETTINGS_RESET_CANCEL)
        self._cancel_btn.setMinimumHeight(44)
        self._cancel_btn.setCursor(Qt.PointingHandCursor)
        self._cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {PRIMARY_0};
                border: 1px solid {PRIMARY_500};
                border-radius: 6px;
                padding: 10px 24px;
                font-family: {FONT_BODY};
                font-size: {FONT_SIZE_BODY};
                color: {PRIMARY_500};
            }}
            QPushButton:hover {{
                background-color: rgba(0,0,0,0.05);
            }}
        """)
        self._cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self._cancel_btn)

        self._confirm_btn = QPushButton(texts.PROVISION_SETTINGS_RESET_CONFIRM_BTN.format(seconds=self._countdown))
        self._confirm_btn.setMinimumHeight(44)
        self._confirm_btn.setCursor(Qt.PointingHandCursor)
        self._confirm_btn.setEnabled(False)
        self._confirm_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {DANGER_500};
                border: none;
                border-radius: 6px;
                padding: 10px 24px;
                font-family: {FONT_BODY};
                font-size: {FONT_SIZE_BODY};
                font-weight: 600;
                color: white;
            }}
            QPushButton:hover {{
                background-color: #b91c1c;
            }}
            QPushButton:disabled {{
                background-color: #fca5a5;
                color: #fef2f2;
            }}
        """)
        self._confirm_btn.clicked.connect(self.accept)
        btn_row.addWidget(self._confirm_btn)

        layout.addLayout(btn_row)

    def showEvent(self, event):
        super().showEvent(event)
        self._countdown = 3
        self._update_ui()
        self._timer.start(1000)

    def _tick(self):
        self._countdown -= 1
        self._update_ui()
        if self._countdown <= 0:
            self._timer.stop()
            self._confirm_btn.setEnabled(True)
            self._confirm_btn.setText(texts.PROVISION_SETTINGS_RESET_CONFIRM_NOW)
            self._countdown_lbl.setText(texts.PROVISION_SETTINGS_RESET_READY)

    def _update_ui(self):
        if self._countdown > 0:
            self._countdown_lbl.setText(texts.PROVISION_SETTINGS_RESET_COUNTDOWN.format(seconds=self._countdown))
            self._confirm_btn.setText(texts.PROVISION_SETTINGS_RESET_CONFIRM_BTN.format(seconds=self._countdown))


class SettingsPanel(QWidget):
    """Einstellungen-Panel mit Gefahrenzone fuer Daten-Reset."""

    def __init__(self, api: ProvisionAPI):
        super().__init__()
        self._api = api
        self._presenter = None
        self._toast_manager = None
        self._reset_worker = None
        self._setup_ui()

    @property
    def _backend(self):
        return self._presenter or self._api

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(24)

        title = QLabel(texts.PROVISION_SETTINGS_TITLE)
        title.setStyleSheet(f"""
            font-family: {FONT_HEADLINE};
            font-size: {FONT_SIZE_H2};
            font-weight: 700;
            color: {PRIMARY_900};
        """)
        layout.addWidget(title)

        layout.addStretch()

        danger_frame = QFrame()
        danger_frame.setStyleSheet(f"""
            QFrame {{
                background-color: #fef2f2;
                border: 2px solid {DANGER_500};
                border-radius: 12px;
            }}
        """)

        danger_layout = QVBoxLayout(danger_frame)
        danger_layout.setContentsMargins(24, 24, 24, 24)
        danger_layout.setSpacing(16)

        danger_title = QLabel(f"\u26A0\uFE0F  {texts.PROVISION_SETTINGS_DANGER_ZONE}")
        danger_title.setStyleSheet(f"""
            font-family: {FONT_HEADLINE};
            font-size: 14pt;
            font-weight: 700;
            color: {DANGER_500};
        """)
        danger_layout.addWidget(danger_title)

        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background-color: {DANGER_500}; opacity: 0.3;")
        danger_layout.addWidget(sep)

        reset_row = QHBoxLayout()
        reset_row.setSpacing(16)

        reset_info = QVBoxLayout()
        reset_info.setSpacing(4)

        reset_title = QLabel(texts.PROVISION_SETTINGS_RESET_TITLE)
        reset_title.setStyleSheet(f"""
            font-family: {FONT_BODY};
            font-size: {FONT_SIZE_BODY};
            font-weight: 600;
            color: {PRIMARY_900};
        """)
        reset_info.addWidget(reset_title)

        reset_desc = QLabel(texts.PROVISION_SETTINGS_RESET_DESC)
        reset_desc.setWordWrap(True)
        reset_desc.setStyleSheet(f"""
            font-family: {FONT_BODY};
            font-size: {FONT_SIZE_CAPTION};
            color: {PRIMARY_500};
            line-height: 1.4;
        """)
        reset_info.addWidget(reset_desc)

        deleted_lbl = QLabel(texts.PROVISION_SETTINGS_RESET_DELETED)
        deleted_lbl.setStyleSheet(f"""
            font-family: {FONT_BODY};
            font-size: {FONT_SIZE_CAPTION};
            color: {DANGER_500};
            margin-top: 8px;
        """)
        reset_info.addWidget(deleted_lbl)

        kept_lbl = QLabel(texts.PROVISION_SETTINGS_RESET_KEPT)
        kept_lbl.setStyleSheet(f"""
            font-family: {FONT_BODY};
            font-size: {FONT_SIZE_CAPTION};
            color: {SUCCESS_500};
        """)
        reset_info.addWidget(kept_lbl)

        reset_row.addLayout(reset_info, 1)

        self._reset_btn = QPushButton(texts.PROVISION_SETTINGS_RESET_BTN)
        self._reset_btn.setMinimumSize(180, 48)
        self._reset_btn.setCursor(Qt.PointingHandCursor)
        self._reset_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {DANGER_500};
                border: none;
                border-radius: 8px;
                padding: 12px 24px;
                font-family: {FONT_BODY};
                font-size: {FONT_SIZE_BODY};
                font-weight: 700;
                color: white;
            }}
            QPushButton:hover {{
                background-color: #b91c1c;
            }}
            QPushButton:pressed {{
                background-color: #991b1b;
            }}
            QPushButton:disabled {{
                background-color: #fca5a5;
            }}
        """)
        self._reset_btn.clicked.connect(self._on_reset_clicked)
        reset_row.addWidget(self._reset_btn, 0, Qt.AlignTop)

        danger_layout.addLayout(reset_row)
        layout.addWidget(danger_frame)

        layout.addStretch()

    def _on_reset_clicked(self):
        dialog = ResetConfirmDialog(self)
        if dialog.exec() == QDialog.Accepted:
            self._execute_reset()

    def _execute_reset(self):
        self._reset_btn.setEnabled(False)
        self._reset_btn.setText(texts.PROVISION_SETTINGS_RESET_RUNNING)

        self._reset_worker = _ResetWorker(self._backend)
        self._reset_worker.finished.connect(self._on_reset_finished)
        self._reset_worker.error.connect(self._on_reset_error)
        self._reset_worker.start()

    def _on_reset_finished(self, result: dict):
        self._reset_btn.setEnabled(True)
        self._reset_btn.setText(texts.PROVISION_SETTINGS_RESET_BTN)

        deleted = result.get('deleted', {})
        msg = texts.PROVISION_SETTINGS_RESET_SUCCESS.format(
            commissions=deleted.get('pm_commissions', 0),
            contracts=deleted.get('pm_contracts', 0),
            batches=deleted.get('pm_import_batches', 0),
        )
        if self._toast_manager:
            self._toast_manager.show_success(msg)
        logger.info(f"Provision-Reset erfolgreich: {result}")

    def _on_reset_error(self, error: str):
        self._reset_btn.setEnabled(True)
        self._reset_btn.setText(texts.PROVISION_SETTINGS_RESET_BTN)

        if self._toast_manager:
            self._toast_manager.show_error(texts.PROVISION_SETTINGS_RESET_ERROR.format(error=error))
        logger.error(f"Provision-Reset Fehler: {error}")

    def refresh(self):
        pass
