"""
Workforce SMTP View - SMTP-Konfiguration fuer Trigger-E-Mails.

Erlaubt das Konfigurieren der SMTP-Verbindung, Speichern und
Senden einer Test-E-Mail zur Verifikation.
"""

import logging

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QFormLayout, QFrame, QCheckBox, QSpinBox,
)
from PySide6.QtCore import Qt, QThread, Signal

from workforce.api_client import WorkforceApiClient
from ui.styles.tokens import (
    PRIMARY_500, PRIMARY_900, ACCENT_500, FONT_BODY,
    FONT_SIZE_BODY, FONT_SIZE_CAPTION, FONT_SIZE_H2,
    BG_PRIMARY, BG_SECONDARY, BORDER_DEFAULT, RADIUS_MD,
    SUCCESS, ERROR as ERROR_COLOR,
    get_button_primary_style, get_button_secondary_style,
)
from i18n import de as texts

logger = logging.getLogger(__name__)


class _SmtpLoadThread(QThread):
    """Laedt die SMTP-Konfiguration (entschluesselt)."""
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, api: WorkforceApiClient):
        super().__init__()
        self._api = api

    def run(self):
        try:
            result = self._api.get_smtp_config_decrypted()
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class _SmtpSaveThread(QThread):
    """Speichert die SMTP-Konfiguration."""
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, api: WorkforceApiClient, data: dict):
        super().__init__()
        self._api = api
        self._data = data

    def run(self):
        try:
            result = self._api.update_smtp_config(self._data)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class _SmtpTestThread(QThread):
    """Sendet eine Test-E-Mail ueber die gespeicherte SMTP-Config."""
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, api: WorkforceApiClient, data: dict):
        super().__init__()
        self._api = api
        self._data = data

    def run(self):
        try:
            result = self._api.update_smtp_config({**self._data, '_test': True})
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class SmtpView(QWidget):
    """SMTP-Konfigurationspanel fuer das Workforce-Modul."""

    def __init__(self, wf_api: WorkforceApiClient):
        super().__init__()
        self._wf_api = wf_api
        self._toast_manager = None
        self._load_thread = None
        self._action_thread = None
        self._dirty = False

        self._setup_ui()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(20)

        title = QLabel(texts.WF_SMTP_TITLE)
        title.setStyleSheet(f"""
            font-family: {FONT_BODY}; font-size: {FONT_SIZE_H2};
            color: {PRIMARY_900}; font-weight: 600;
        """)
        root.addWidget(title)

        desc = QLabel(texts.WF_SMTP_DESCRIPTION)
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {PRIMARY_500}; font-size: {FONT_SIZE_BODY}; font-family: {FONT_BODY};")
        root.addWidget(desc)

        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {BG_PRIMARY};
                border: 1px solid {BORDER_DEFAULT};
                border-radius: {RADIUS_MD};
            }}
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 20, 24, 20)
        card_layout.setSpacing(16)

        form = QFormLayout()
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self._host_input = QLineEdit()
        self._host_input.setPlaceholderText(texts.WF_SMTP_HOST_PLACEHOLDER)
        self._host_input.textChanged.connect(self._mark_dirty)
        form.addRow(texts.WF_SMTP_HOST, self._host_input)

        self._port_input = QSpinBox()
        self._port_input.setRange(1, 65535)
        self._port_input.setValue(587)
        self._port_input.valueChanged.connect(self._mark_dirty)
        form.addRow(texts.WF_SMTP_PORT, self._port_input)

        self._username_input = QLineEdit()
        self._username_input.setPlaceholderText(texts.WF_SMTP_USERNAME_PLACEHOLDER)
        self._username_input.textChanged.connect(self._mark_dirty)
        form.addRow(texts.WF_SMTP_USERNAME, self._username_input)

        self._password_input = QLineEdit()
        self._password_input.setEchoMode(QLineEdit.Password)
        self._password_input.setPlaceholderText(texts.WF_SMTP_PASSWORD_PLACEHOLDER)
        self._password_input.textChanged.connect(self._mark_dirty)
        form.addRow(texts.WF_SMTP_PASSWORD, self._password_input)

        self._from_email_input = QLineEdit()
        self._from_email_input.setPlaceholderText(texts.WF_SMTP_FROM_EMAIL_PLACEHOLDER)
        self._from_email_input.textChanged.connect(self._mark_dirty)
        form.addRow(texts.WF_SMTP_FROM_EMAIL, self._from_email_input)

        self._from_name_input = QLineEdit()
        self._from_name_input.setPlaceholderText(texts.WF_SMTP_FROM_NAME_PLACEHOLDER)
        self._from_name_input.textChanged.connect(self._mark_dirty)
        form.addRow(texts.WF_SMTP_FROM_NAME, self._from_name_input)

        self._tls_checkbox = QCheckBox(texts.WF_SMTP_USE_TLS)
        self._tls_checkbox.setChecked(True)
        self._tls_checkbox.stateChanged.connect(self._mark_dirty)
        form.addRow("", self._tls_checkbox)

        card_layout.addLayout(form)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"color: {BORDER_DEFAULT};")
        card_layout.addWidget(sep)

        btns = QHBoxLayout()
        btns.setSpacing(12)

        self._test_btn = QPushButton(texts.WF_SMTP_TEST)
        self._test_btn.setStyleSheet(get_button_secondary_style())
        self._test_btn.setCursor(Qt.PointingHandCursor)
        self._test_btn.clicked.connect(self._test_connection)
        btns.addWidget(self._test_btn)

        btns.addStretch()

        self._save_btn = QPushButton(texts.SAVE)
        self._save_btn.setStyleSheet(get_button_primary_style())
        self._save_btn.setCursor(Qt.PointingHandCursor)
        self._save_btn.clicked.connect(self._save_config)
        btns.addWidget(self._save_btn)

        card_layout.addLayout(btns)
        root.addWidget(card)

        self._status_frame = QFrame()
        self._status_frame.setVisible(False)
        self._status_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {BG_SECONDARY};
                border: 1px solid {BORDER_DEFAULT};
                border-radius: {RADIUS_MD};
                padding: 12px 16px;
            }}
        """)
        status_layout = QHBoxLayout(self._status_frame)
        status_layout.setContentsMargins(16, 12, 16, 12)
        self._status_icon = QLabel()
        self._status_icon.setFixedWidth(24)
        self._status_icon.setAlignment(Qt.AlignCenter)
        status_layout.addWidget(self._status_icon)
        self._status_label = QLabel()
        self._status_label.setWordWrap(True)
        self._status_label.setStyleSheet(f"font-family: {FONT_BODY}; font-size: {FONT_SIZE_BODY};")
        status_layout.addWidget(self._status_label, 1)
        root.addWidget(self._status_frame)

        root.addStretch()

    def _mark_dirty(self):
        self._dirty = True

    def _load_config(self):
        if self._load_thread and self._load_thread.isRunning():
            return
        self._set_loading(True)
        thread = _SmtpLoadThread(self._wf_api)
        thread.finished.connect(self._on_config_loaded)
        thread.error.connect(self._on_load_error)
        self._load_thread = thread
        thread.start()

    def _on_config_loaded(self, config: dict):
        self._set_loading(False)
        if not config:
            self._show_status(texts.WF_SMTP_NOT_CONFIGURED, is_error=False)
            self._dirty = False
            return

        self._host_input.setText(config.get('host', ''))
        self._port_input.setValue(config.get('port', 587))
        self._username_input.setText(config.get('username', ''))
        self._password_input.setText(config.get('password', ''))
        self._from_email_input.setText(config.get('from_email', ''))
        self._from_name_input.setText(config.get('from_name', ''))
        self._tls_checkbox.setChecked(config.get('use_tls', True))
        self._dirty = False
        self._status_frame.setVisible(False)

    def _on_load_error(self, error: str):
        self._set_loading(False)
        logger.error(f"SMTP-Config Ladefehler: {error}")
        self._show_status(f"{texts.WF_SMTP_LOAD_ERROR}: {error}", is_error=True)

    def _get_form_data(self) -> dict:
        return {
            'host': self._host_input.text().strip(),
            'port': self._port_input.value(),
            'username': self._username_input.text().strip(),
            'password': self._password_input.text(),
            'from_email': self._from_email_input.text().strip(),
            'from_name': self._from_name_input.text().strip(),
            'use_tls': self._tls_checkbox.isChecked(),
        }

    def _validate(self) -> bool:
        data = self._get_form_data()
        if not data['host']:
            if self._toast_manager:
                self._toast_manager.show_warning(texts.WF_SMTP_HOST_REQUIRED)
            return False
        if not data['from_email']:
            if self._toast_manager:
                self._toast_manager.show_warning(texts.WF_SMTP_FROM_REQUIRED)
            return False
        return True

    def _save_config(self):
        if not self._validate():
            return
        self._set_loading(True)
        data = self._get_form_data()
        thread = _SmtpSaveThread(self._wf_api, data)
        thread.finished.connect(self._on_save_done)
        thread.error.connect(self._on_save_error)
        self._action_thread = thread
        thread.start()

    def _on_save_done(self, _result: dict):
        self._set_loading(False)
        self._dirty = False
        self._show_status(texts.WF_SMTP_SAVED, is_error=False)
        if self._toast_manager:
            self._toast_manager.show_success(texts.WF_SMTP_SAVED)

    def _on_save_error(self, error: str):
        self._set_loading(False)
        logger.error(f"SMTP-Config Speicherfehler: {error}")
        self._show_status(f"{texts.WF_SMTP_SAVE_ERROR}: {error}", is_error=True)
        if self._toast_manager:
            self._toast_manager.show_error(f"{texts.WF_SMTP_SAVE_ERROR}: {error}")

    def _test_connection(self):
        if not self._validate():
            return
        self._set_loading(True)
        self._show_status(texts.WF_SMTP_TESTING, is_error=False)
        data = self._get_form_data()
        thread = _SmtpTestThread(self._wf_api, data)
        thread.finished.connect(self._on_test_done)
        thread.error.connect(self._on_test_error)
        self._action_thread = thread
        thread.start()

    def _on_test_done(self, result: dict):
        self._set_loading(False)
        self._show_status(texts.WF_SMTP_TEST_SUCCESS, is_error=False)
        if self._toast_manager:
            self._toast_manager.show_success(texts.WF_SMTP_TEST_SUCCESS)

    def _on_test_error(self, error: str):
        self._set_loading(False)
        self._show_status(f"{texts.WF_SMTP_TEST_FAILED}: {error}", is_error=True)
        if self._toast_manager:
            self._toast_manager.show_error(f"{texts.WF_SMTP_TEST_FAILED}: {error}")

    def _set_loading(self, loading: bool):
        self._save_btn.setEnabled(not loading)
        self._test_btn.setEnabled(not loading)

    def _show_status(self, message: str, is_error: bool):
        self._status_frame.setVisible(True)
        color = ERROR_COLOR if is_error else SUCCESS
        self._status_icon.setText("\u2717" if is_error else "\u2713")
        self._status_icon.setStyleSheet(f"font-size: 16pt; color: {color};")
        self._status_label.setText(message)
        self._status_label.setStyleSheet(
            f"color: {color}; font-family: {FONT_BODY}; font-size: {FONT_SIZE_BODY};"
        )

    def refresh(self):
        self._load_config()
