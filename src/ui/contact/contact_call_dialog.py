# -*- coding: utf-8 -*-
"""
Contact Call Dialog - Dialog zum Anlegen eines neuen Telefonat-Eintrags.
"""

import logging

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QComboBox, QLineEdit,
    QTextEdit, QCheckBox, QDateEdit, QTimeEdit, QPushButton,
    QHBoxLayout, QLabel, QFrame,
)
from PySide6.QtCore import Signal, Qt, QDate, QTime

from contact.api_client import ContactApiClient
from ui.styles.tokens import (
    FONT_BODY, FONT_SIZE_BODY,
    BG_PRIMARY, BG_SECONDARY, BORDER_DEFAULT, RADIUS_MD,
    PRIMARY_900, PRIMARY_500, TEXT_SECONDARY,
    get_button_primary_style, get_button_secondary_style,
)
from i18n import de as texts

logger = logging.getLogger(__name__)


def _build_caller_display(contact_data: dict | None) -> str:
    """Gibt 'Vorname Nachname' oder 'Unbekannter Anrufer' zurueck."""
    if not contact_data:
        return texts.CONTACT_UNKNOWN_CALLER
    name = (
        contact_data.get("display_name")
        or (
            f"{contact_data.get('first_name', '') or ''} "
            f"{contact_data.get('last_name', '') or ''}"
        ).strip()
    )
    return name or texts.CONTACT_UNKNOWN_CALLER


def _build_dob_display(contact_data: dict | None) -> str:
    """Gibt '*TT.MM.JJJJ' zurueck oder leer wenn kein Datum vorhanden."""
    if not contact_data:
        return ""
    dob = contact_data.get("date_of_birth") or contact_data.get("birth_date")
    if not dob:
        return ""
    try:
        parts = str(dob)[:10].split("-")
        if len(parts) == 3:
            return f"\u2217 {parts[2]}.{parts[1]}.{parts[0]}"
    except Exception:
        pass
    return ""


_INPUT = (
    f"background-color: {BG_PRIMARY}; border: 1px solid {BORDER_DEFAULT}; "
    f"border-radius: {RADIUS_MD}; padding: 8px 12px; "
    f"font-family: {FONT_BODY}; font-size: {FONT_SIZE_BODY};"
)


class ContactCallDialog(QDialog):
    """Dialog zum Anlegen eines neuen Telefonat-Eintrags."""

    call_saved = Signal()

    def __init__(
        self,
        contact_api: ContactApiClient,
        contact_id: int,
        parent=None,
        contact_data: dict | None = None,
    ):
        super().__init__(parent)
        self._api = contact_api
        self._cid = contact_id

        self.setWindowTitle(texts.CONTACT_CALL_NEW)
        self.setMinimumWidth(460)
        self.setStyleSheet(f"""
            QDialog {{ background-color: {BG_PRIMARY}; }}
            QLabel {{ font-family: {FONT_BODY}; font-size: {FONT_SIZE_BODY}; color: {PRIMARY_900}; }}
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 24, 24, 24)

        # Caller-Info-Header
        caller_frame = QFrame()
        caller_frame.setStyleSheet(
            f"QFrame {{ background-color: {BG_SECONDARY}; border: 1px solid {BORDER_DEFAULT}; "
            f"border-radius: {RADIUS_MD}; }}"
        )
        caller_layout = QVBoxLayout(caller_frame)
        caller_layout.setContentsMargins(16, 12, 16, 12)
        caller_layout.setSpacing(2)

        caption = QLabel(texts.CONTACT_CALL_CALLER)
        caption.setStyleSheet(
            f"font-family: {FONT_BODY}; font-size: 10pt; color: {TEXT_SECONDARY}; "
            f"border: none; background: transparent;"
        )
        caller_layout.addWidget(caption)

        name_lbl = QLabel(_build_caller_display(contact_data))
        name_lbl.setStyleSheet(
            f"font-family: {FONT_BODY}; font-size: 13pt; font-weight: bold; "
            f"color: {PRIMARY_900}; border: none; background: transparent;"
        )
        name_lbl.setWordWrap(True)
        caller_layout.addWidget(name_lbl)

        dob = _build_dob_display(contact_data)
        if dob:
            dob_lbl = QLabel(dob)
            dob_lbl.setStyleSheet(
                f"font-family: {FONT_BODY}; font-size: {FONT_SIZE_BODY}; "
                f"color: {TEXT_SECONDARY}; border: none; background: transparent;"
            )
            caller_layout.addWidget(dob_lbl)

        layout.addWidget(caller_frame)

        form = QFormLayout()
        form.setSpacing(8)

        self._combo_dir = QComboBox()
        self._combo_dir.addItem(texts.CONTACT_CALL_INBOUND, "inbound")
        self._combo_dir.addItem(texts.CONTACT_CALL_OUTBOUND, "outbound")
        self._combo_dir.setStyleSheet(f"QComboBox {{ {_INPUT} }}")
        form.addRow(texts.CONTACT_CALL_DIRECTION + ":", self._combo_dir)

        self._edit_subject = QLineEdit()
        self._edit_subject.setPlaceholderText(texts.CONTACT_CALL_SUBJECT)
        self._edit_subject.setStyleSheet(f"QLineEdit {{ {_INPUT} }}")
        form.addRow(texts.CONTACT_CALL_SUBJECT + ":", self._edit_subject)

        self._edit_note = QTextEdit()
        self._edit_note.setPlaceholderText(texts.CONTACT_CALL_NOTE)
        self._edit_note.setMaximumHeight(80)
        self._edit_note.setStyleSheet(f"QTextEdit {{ {_INPUT} }}")
        form.addRow(texts.CONTACT_CALL_NOTE + ":", self._edit_note)

        self._chk_cb = QCheckBox(texts.CONTACT_CALL_CALLBACK_NEEDED)
        self._chk_cb.setStyleSheet(
            f"QCheckBox {{ font-family: {FONT_BODY}; font-size: {FONT_SIZE_BODY}; color: {PRIMARY_900}; }}"
        )
        self._chk_cb.toggled.connect(self._toggle_cb_fields)
        form.addRow(self._chk_cb)

        self._de = QDateEdit()
        self._de.setCalendarPopup(True)
        self._de.setDate(QDate.currentDate())
        self._de.setDisplayFormat("dd.MM.yyyy")
        self._de.setStyleSheet(f"QDateEdit {{ {_INPUT} }}")
        self._de.setVisible(False)
        form.addRow(texts.CONTACT_CALL_CALLBACK_DATE + ":", self._de)

        self._te = QTimeEdit()
        self._te.setTime(QTime(9, 0))
        self._te.setDisplayFormat("HH:mm")
        self._te.setStyleSheet(f"QTimeEdit {{ {_INPUT} }}")
        self._te.setVisible(False)
        form.addRow(texts.CONTACT_CALL_CALLBACK_TIME + ":", self._te)

        layout.addLayout(form)
        layout.addStretch()

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton(texts.CANCEL)
        cancel_btn.setStyleSheet(get_button_secondary_style())
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        self._save_btn = QPushButton(texts.SAVE)
        self._save_btn.setStyleSheet(get_button_primary_style())
        self._save_btn.setCursor(Qt.PointingHandCursor)
        self._save_btn.clicked.connect(self._save)
        btn_row.addWidget(self._save_btn)
        layout.addLayout(btn_row)

    def _toggle_cb_fields(self, checked: bool):
        self._de.setVisible(checked)
        self._te.setVisible(checked)

    def _save(self):
        self._save_btn.setEnabled(False)
        self._save_btn.setText("...")

        data = {
            "direction": self._combo_dir.currentData() or "inbound",
            "subject": self._edit_subject.text().strip(),
            "note": self._edit_note.toPlainText().strip(),
            "callback_needed": 1 if self._chk_cb.isChecked() else 0,
            "status": "open",
        }

        if self._chk_cb.isChecked():
            d = self._de.date().toString("yyyy-MM-dd")
            t = self._te.time().toString("HH:mm")
            data["callback_at"] = f"{d} {t}:00"

        try:
            self._api.create_call(self._cid, data)
            self.call_saved.emit()
            self.accept()
        except Exception as e:
            logger.error("Telefonat speichern: %s", e)
            self._save_btn.setEnabled(True)
            self._save_btn.setText(texts.SAVE)
