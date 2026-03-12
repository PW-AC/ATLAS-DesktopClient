# -*- coding: utf-8 -*-
"""
ACENCIA ATLAS – Self-Service Passwort-Ändern-Dialog

Zweistufiger modaler Dialog:
  Schritt 1: Aktuelles Passwort eingeben und serverseitig verifizieren
  Schritt 2: Neues Passwort + Bestätigung eingeben

Erst wenn Schritt 1 vom Server bestätigt wurde, wird Schritt 2 freigeschaltet.
Nach erfolgreicher Änderung wird das Signal ``password_changed`` emittiert,
damit der Aufrufer die aktive Session invalidiert und den Nutzer abmeldet.
"""

import logging

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QStackedWidget, QWidget, QFrame,
)
from PySide6.QtCore import Signal, Qt, QThread

from i18n import de as texts
import ui.styles.tokens as _tokens
from ui.styles.tokens import (
    PRIMARY_900, PRIMARY_0,
    ACCENT_500,
    TEXT_SECONDARY,
    BORDER_DEFAULT,
    ERROR, ERROR_LIGHT,
    RADIUS_MD,
    FONT_SIZE_H2, FONT_SIZE_H3, FONT_SIZE_BODY, FONT_SIZE_CAPTION,
    FONT_WEIGHT_BOLD, FONT_WEIGHT_MEDIUM,
    get_button_primary_style, get_button_secondary_style,
)
from api.client import APIError

logger = logging.getLogger(__name__)

_STEP_CURRENT = 0
_STEP_NEW = 1


class _VerifyPasswordWorker(QThread):
    """Ruft POST /auth/verify-password auf um das aktuelle Passwort zu prüfen."""

    succeeded = Signal()
    failed = Signal(str, int)

    def __init__(self, auth_api, current_password: str, parent=None):
        super().__init__(parent)
        self._auth_api = auth_api
        self._current = current_password

    def run(self):
        try:
            self._auth_api.verify_current_password(self._current)
            self.succeeded.emit()
        except APIError as exc:
            self.failed.emit(str(exc), exc.status_code)
        except Exception as exc:
            logger.exception("Unerwarteter Fehler bei Passwort-Verifikation")
            self.failed.emit(str(exc), 0)


class _ChangePasswordWorker(QThread):
    """Sendet PUT /auth/change-password in einem eigenen Thread."""

    succeeded = Signal()
    failed = Signal(str, int)

    def __init__(self, auth_api, current_password: str, new_password: str, parent=None):
        super().__init__(parent)
        self._auth_api = auth_api
        self._current = current_password
        self._new = new_password

    def run(self):
        try:
            self._auth_api.change_password(self._current, self._new)
            self.succeeded.emit()
        except APIError as exc:
            self.failed.emit(str(exc), exc.status_code)
        except Exception as exc:
            logger.exception("Unerwarteter Fehler bei Passwort-Änderung")
            self.failed.emit(str(exc), 0)


_MAX_ATTEMPTS = 4


class ChangeOwnPasswordDialog(QDialog):
    """
    Zweistufiger Dialog für die Self-Service Passwort-Änderung.

    Schritt 1 verifiziert das aktuelle Passwort serverseitig bevor
    Schritt 2 (Neues Passwort eingeben) freigeschaltet wird.
    Nach 4 Fehlversuchen wird ``max_attempts_reached`` emittiert und
    der Dialog schließt sich – der Aufrufer soll die Session beenden.

    Signals:
        password_changed:    Wird nach erfolgreicher Änderung emittiert.
        max_attempts_reached: Wird nach 4 Fehlversuchen emittiert (→ Logout).
    """

    password_changed = Signal()
    max_attempts_reached = Signal()

    def __init__(self, auth_api, parent=None):
        super().__init__(parent)
        self._auth_api = auth_api
        self._failed_attempts = 0
        self._verify_worker: _VerifyPasswordWorker | None = None
        self._change_worker: _ChangePasswordWorker | None = None

        self.setWindowTitle(texts.CHANGE_PW_TITLE)
        self.setMinimumWidth(420)
        self.setModal(True)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self._setup_ui()

    # ------------------------------------------------------------------
    # UI-Aufbau
    # ------------------------------------------------------------------

    def _setup_ui(self):
        self.setStyleSheet(f"background-color: {PRIMARY_0};")

        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 28)
        root.setSpacing(0)

        title = QLabel(texts.CHANGE_PW_TITLE)
        title.setStyleSheet(
            f"font-family: {_tokens.FONT_HEADLINE}; font-size: {FONT_SIZE_H2}; "
            f"font-weight: {FONT_WEIGHT_BOLD}; color: {PRIMARY_900}; border: none;"
        )
        root.addWidget(title)
        root.addSpacing(4)

        div = QFrame()
        div.setFrameShape(QFrame.HLine)
        div.setFixedHeight(1)
        div.setStyleSheet(f"background: {BORDER_DEFAULT}; border: none;")
        root.addWidget(div)
        root.addSpacing(20)

        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_step1())
        self._stack.addWidget(self._build_step2())
        self._stack.setCurrentIndex(_STEP_CURRENT)
        root.addWidget(self._stack, 1)

        root.addSpacing(12)
        self._error_banner = QLabel()
        self._error_banner.setWordWrap(True)
        self._error_banner.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._error_banner.setStyleSheet(
            f"background: {ERROR_LIGHT}; color: {ERROR}; "
            f"border: 1px solid {ERROR}; border-radius: {RADIUS_MD}; "
            f"padding: 8px 12px; font-size: {FONT_SIZE_BODY}; "
            f"font-family: {_tokens.FONT_BODY};"
        )
        self._error_banner.hide()
        root.addWidget(self._error_banner)

    def _field_style(self) -> str:
        return (
            f"QLineEdit {{"
            f"  font-family: {_tokens.FONT_BODY}; font-size: {FONT_SIZE_BODY}; "
            f"  color: {PRIMARY_900}; background: {PRIMARY_0}; "
            f"  border: 1px solid {BORDER_DEFAULT}; border-radius: {RADIUS_MD}; "
            f"  padding: 8px 12px;"
            f"}}"
            f"QLineEdit:focus {{"
            f"  border-color: {ACCENT_500};"
            f"}}"
        )

    def _label_style(self) -> str:
        return (
            f"font-family: {_tokens.FONT_BODY}; font-size: {FONT_SIZE_BODY}; "
            f"color: {PRIMARY_900}; border: none;"
        )

    def _desc_style(self) -> str:
        return (
            f"font-family: {_tokens.FONT_BODY}; font-size: {FONT_SIZE_CAPTION}; "
            f"color: {TEXT_SECONDARY}; border: none;"
        )

    def _section_title_style(self) -> str:
        return (
            f"font-family: {_tokens.FONT_HEADLINE}; font-size: {FONT_SIZE_H3}; "
            f"font-weight: {FONT_WEIGHT_BOLD}; color: {PRIMARY_900}; border: none;"
        )

    def _build_step1(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        sec_title = QLabel(texts.CHANGE_PW_STEP1_TITLE)
        sec_title.setStyleSheet(self._section_title_style())
        layout.addWidget(sec_title)

        desc = QLabel(texts.CHANGE_PW_STEP1_DESC)
        desc.setWordWrap(True)
        desc.setStyleSheet(self._desc_style())
        layout.addWidget(desc)

        layout.addSpacing(16)

        lbl = QLabel(texts.CHANGE_PW_CURRENT_LABEL)
        lbl.setStyleSheet(self._label_style())
        layout.addWidget(lbl)

        self._current_pw_edit = QLineEdit()
        self._current_pw_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._current_pw_edit.setPlaceholderText(texts.CHANGE_PW_CURRENT_PLACEHOLDER)
        self._current_pw_edit.setStyleSheet(self._field_style())
        self._current_pw_edit.returnPressed.connect(self._on_step1_next)
        layout.addWidget(self._current_pw_edit)

        layout.addSpacing(20)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.addStretch()

        self._step1_cancel_btn = QPushButton(texts.CANCEL)
        self._step1_cancel_btn.setStyleSheet(get_button_secondary_style())
        self._step1_cancel_btn.setCursor(Qt.PointingHandCursor)
        self._step1_cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self._step1_cancel_btn)

        self._step1_next_btn = QPushButton(texts.CHANGE_PW_STEP1_BTN)
        self._step1_next_btn.setStyleSheet(get_button_primary_style())
        self._step1_next_btn.setCursor(Qt.PointingHandCursor)
        self._step1_next_btn.clicked.connect(self._on_step1_next)
        btn_row.addWidget(self._step1_next_btn)

        layout.addLayout(btn_row)
        layout.addStretch()
        return w

    def _build_step2(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        sec_title = QLabel(texts.CHANGE_PW_STEP2_TITLE)
        sec_title.setStyleSheet(self._section_title_style())
        layout.addWidget(sec_title)

        desc = QLabel(texts.CHANGE_PW_STEP2_DESC)
        desc.setWordWrap(True)
        desc.setStyleSheet(self._desc_style())
        layout.addWidget(desc)

        layout.addSpacing(16)

        lbl_new = QLabel(texts.CHANGE_PW_NEW_LABEL)
        lbl_new.setStyleSheet(self._label_style())
        layout.addWidget(lbl_new)

        self._new_pw_edit = QLineEdit()
        self._new_pw_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._new_pw_edit.setPlaceholderText(texts.CHANGE_PW_NEW_PLACEHOLDER)
        self._new_pw_edit.setStyleSheet(self._field_style())
        self._new_pw_edit.textChanged.connect(self._on_new_pw_changed)
        layout.addWidget(self._new_pw_edit)

        layout.addSpacing(12)

        lbl_confirm = QLabel(texts.CHANGE_PW_CONFIRM_LABEL)
        lbl_confirm.setStyleSheet(self._label_style())
        layout.addWidget(lbl_confirm)

        self._confirm_pw_edit = QLineEdit()
        self._confirm_pw_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._confirm_pw_edit.setPlaceholderText(texts.CHANGE_PW_CONFIRM_PLACEHOLDER)
        self._confirm_pw_edit.setStyleSheet(self._field_style())
        self._confirm_pw_edit.textChanged.connect(self._on_new_pw_changed)
        self._confirm_pw_edit.returnPressed.connect(self._on_step2_confirm)
        layout.addWidget(self._confirm_pw_edit)

        layout.addSpacing(12)
        hint = QLabel(texts.CHANGE_PW_LOGOUT_HINT)
        hint.setWordWrap(True)
        hint.setStyleSheet(
            f"font-family: {_tokens.FONT_BODY}; font-size: {FONT_SIZE_CAPTION}; "
            f"color: {TEXT_SECONDARY}; border: 1px solid {BORDER_DEFAULT}; "
            f"border-radius: {RADIUS_MD}; padding: 8px 10px; background: transparent;"
        )
        layout.addWidget(hint)

        layout.addSpacing(20)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self._back_btn = QPushButton(texts.CHANGE_PW_BACK_BTN)
        self._back_btn.setStyleSheet(get_button_secondary_style())
        self._back_btn.setCursor(Qt.PointingHandCursor)
        self._back_btn.clicked.connect(self._go_back)
        btn_row.addWidget(self._back_btn)

        btn_row.addStretch()

        self._step2_confirm_btn = QPushButton(texts.CHANGE_PW_CONFIRM_BTN)
        self._step2_confirm_btn.setStyleSheet(get_button_primary_style())
        self._step2_confirm_btn.setCursor(Qt.PointingHandCursor)
        self._step2_confirm_btn.setEnabled(False)
        self._step2_confirm_btn.clicked.connect(self._on_step2_confirm)
        btn_row.addWidget(self._step2_confirm_btn)

        layout.addLayout(btn_row)
        layout.addStretch()
        return w

    # ------------------------------------------------------------------
    # Hilfs-Methoden
    # ------------------------------------------------------------------

    def _show_error(self, message: str):
        self._error_banner.setText(message)
        self._error_banner.show()

    def _hide_error(self):
        self._error_banner.hide()
        self._error_banner.setText("")

    def _set_step1_busy(self, busy: bool):
        self._step1_next_btn.setEnabled(not busy)
        self._step1_cancel_btn.setEnabled(not busy)
        self._current_pw_edit.setEnabled(not busy)
        self._step1_next_btn.setText(
            texts.CHANGE_PW_VERIFYING if busy else texts.CHANGE_PW_STEP1_BTN
        )

    def _set_step2_busy(self, busy: bool):
        self._step2_confirm_btn.setEnabled(not busy)
        self._back_btn.setEnabled(not busy)
        self._new_pw_edit.setEnabled(not busy)
        self._confirm_pw_edit.setEnabled(not busy)
        self._step2_confirm_btn.setText(
            texts.CHANGE_PW_LOADING if busy else texts.CHANGE_PW_CONFIRM_BTN
        )

    # ------------------------------------------------------------------
    # Schritt 1 – Aktuelles Passwort verifizieren
    # ------------------------------------------------------------------

    def _on_step1_next(self):
        current_pw = self._current_pw_edit.text()
        if not current_pw:
            self._show_error(texts.CHANGE_PW_ERROR_WRONG_CURRENT)
            return

        self._hide_error()
        self._set_step1_busy(True)

        self._verify_worker = _VerifyPasswordWorker(self._auth_api, current_pw, parent=self)
        self._verify_worker.succeeded.connect(self._on_verify_success)
        self._verify_worker.failed.connect(self._on_verify_failure)
        self._verify_worker.start()

    def _on_verify_success(self):
        self._set_step1_busy(False)
        self._hide_error()
        self._stack.setCurrentIndex(_STEP_NEW)

    def _on_verify_failure(self, message: str, status_code: int):
        self._set_step1_busy(False)

        if status_code == 422:
            self._failed_attempts += 1
            remaining = _MAX_ATTEMPTS - self._failed_attempts

            if remaining <= 0:
                self._show_error(texts.CHANGE_PW_MAX_ATTEMPTS)
                self._step1_next_btn.setEnabled(False)
                self._current_pw_edit.setEnabled(False)
                from PySide6.QtCore import QTimer
                QTimer.singleShot(1500, self._on_max_attempts)
                return

            if remaining == 1:
                self._show_error(texts.CHANGE_PW_ATTEMPTS_REMAINING_SINGULAR)
            else:
                self._show_error(
                    texts.CHANGE_PW_ATTEMPTS_REMAINING_PLURAL.format(count=remaining)
                )
        else:
            self._show_error(texts.CHANGE_PW_ERROR_GENERIC.format(error=message))

        self._current_pw_edit.selectAll()
        self._current_pw_edit.setFocus()

    def _on_max_attempts(self):
        self.max_attempts_reached.emit()
        self.reject()

    # ------------------------------------------------------------------
    # Schritt 2 – Neues Passwort setzen
    # ------------------------------------------------------------------

    def _go_back(self):
        self._hide_error()
        self._new_pw_edit.clear()
        self._confirm_pw_edit.clear()
        self._step2_confirm_btn.setEnabled(False)
        self._stack.setCurrentIndex(_STEP_CURRENT)

    def _on_new_pw_changed(self):
        new_pw = self._new_pw_edit.text()
        confirm_pw = self._confirm_pw_edit.text()
        self._step2_confirm_btn.setEnabled(
            len(new_pw) >= 8 and new_pw == confirm_pw
        )
        self._hide_error()

    def _on_step2_confirm(self):
        new_pw = self._new_pw_edit.text()
        confirm_pw = self._confirm_pw_edit.text()

        if len(new_pw) < 8:
            self._show_error(texts.CHANGE_PW_ERROR_TOO_SHORT)
            return
        if new_pw != confirm_pw:
            self._show_error(texts.CHANGE_PW_ERROR_MISMATCH)
            return

        self._hide_error()
        self._set_step2_busy(True)

        current_pw = self._current_pw_edit.text()
        self._change_worker = _ChangePasswordWorker(
            self._auth_api, current_pw, new_pw, parent=self
        )
        self._change_worker.succeeded.connect(self._on_change_success)
        self._change_worker.failed.connect(self._on_change_failure)
        self._change_worker.start()

    def _on_change_success(self):
        self._set_step2_busy(False)
        self.password_changed.emit()
        self.accept()

    def _on_change_failure(self, message: str, status_code: int):
        self._set_step2_busy(False)
        if status_code == 401:
            self._show_error(texts.CHANGE_PW_ERROR_WRONG_CURRENT)
            self._go_back()
        else:
            self._show_error(texts.CHANGE_PW_ERROR_GENERIC.format(error=message))
