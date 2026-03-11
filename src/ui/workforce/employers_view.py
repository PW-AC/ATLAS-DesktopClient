"""
ACENCIA ATLAS - Workforce Employers View

CRUD-Panel fuer Arbeitgeber-Verwaltung im Workforce-Modul.
Tabelle mit Anlegen/Bearbeiten/Loeschen und Credentials-Dialog.
"""

import logging

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QComboBox, QLineEdit, QHeaderView,
    QDialog, QFormLayout, QFrame, QCheckBox, QAbstractItemView, QMessageBox,
)
from PySide6.QtCore import Qt, QRunnable, QObject, Signal, QThreadPool
from PySide6.QtGui import QFont, QColor

from api.auth import AuthAPI
from workforce.api_client import WorkforceApiClient
from ui.workforce.utils import format_date_de
from ui.styles.tokens import (
    PRIMARY_500, PRIMARY_900, ACCENT_500, ACCENT_100,
    FONT_HEADLINE, FONT_BODY, FONT_SIZE_H2, FONT_SIZE_BODY, FONT_SIZE_CAPTION,
    BG_PRIMARY, BORDER_DEFAULT, RADIUS_MD, RADIUS_SM,
    SUCCESS, ERROR, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_INVERSE, TEXT_DISABLED,
    BG_SECONDARY,
    get_button_primary_style, get_button_secondary_style, get_button_danger_style,
    get_input_style, get_dialog_style,
)
from i18n import de as texts

logger = logging.getLogger(__name__)

PROVIDER_OPTIONS = [
    ("personio", "Personio"),
    ("hrworks", "HRworks"),
    ("sagehr", "Sage HR"),
]


class _LoadEmployersSignals(QObject):
    finished = Signal(list)
    error = Signal(str)


class _LoadEmployersWorker(QRunnable):
    def __init__(self, wf_api: WorkforceApiClient):
        super().__init__()
        self.signals = _LoadEmployersSignals()
        self._api = wf_api

    def run(self):
        try:
            employers = self._api.get_employers()
            self.signals.finished.emit(employers)
        except Exception as e:
            logger.error(f"Arbeitgeber laden fehlgeschlagen: {e}")
            self.signals.error.emit(str(e))


class EmployerDialog(QDialog):
    """Dialog zum Anlegen/Bearbeiten eines Arbeitgebers."""

    def __init__(self, parent=None, employer: dict = None):
        super().__init__(parent)
        self._employer = employer or {}
        self._is_edit = bool(employer)
        self._address = self._employer.get('address_json') or {}
        title = texts.WF_EMPLOYER_EDIT_TITLE if self._is_edit else texts.WF_EMPLOYER_ADD_TITLE
        self.setWindowTitle(title)
        self.setMinimumWidth(420)
        self.setStyleSheet(get_dialog_style())
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        title_lbl = QLabel(
            texts.WF_EMPLOYER_EDIT_TITLE if self._is_edit else texts.WF_EMPLOYER_ADD_TITLE
        )
        title_lbl.setObjectName("dialogTitle")
        layout.addWidget(title_lbl)

        form = QFormLayout()
        form.setSpacing(12)

        self._name_input = QLineEdit(self._employer.get('name', ''))
        self._name_input.setPlaceholderText(texts.WF_EMPLOYER_NAME_PLACEHOLDER)
        self._name_input.setStyleSheet(get_input_style())
        form.addRow(QLabel(texts.WF_EMPLOYER_NAME), self._name_input)

        self._provider_combo = QComboBox()
        for key, label in PROVIDER_OPTIONS:
            self._provider_combo.addItem(label, key)
        current_key = self._employer.get('provider_key', '')
        idx = next((i for i, (k, _) in enumerate(PROVIDER_OPTIONS) if k == current_key), 0)
        self._provider_combo.setCurrentIndex(idx)
        if self._is_edit:
            self._provider_combo.setEnabled(False)
        form.addRow(QLabel(texts.WF_EMPLOYER_PROVIDER), self._provider_combo)

        self._street_input = QLineEdit(self._address.get('street', ''))
        self._street_input.setPlaceholderText(texts.WF_EMPLOYER_STREET_PLACEHOLDER)
        form.addRow(QLabel(texts.WF_EMPLOYER_STREET), self._street_input)

        addr_row = QHBoxLayout()
        self._zip_input = QLineEdit(self._address.get('zip_code', ''))
        self._zip_input.setPlaceholderText(texts.WF_EMPLOYER_ZIP_PLACEHOLDER)
        self._zip_input.setMaximumWidth(100)
        addr_row.addWidget(self._zip_input)

        self._city_input = QLineEdit(self._address.get('city', ''))
        self._city_input.setPlaceholderText(texts.WF_EMPLOYER_CITY_PLACEHOLDER)
        addr_row.addWidget(self._city_input)

        addr_widget = QWidget()
        addr_widget.setLayout(addr_row)
        form.addRow(QLabel(texts.WF_EMPLOYER_LOCATION), addr_widget)

        layout.addLayout(form)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel_btn = QPushButton(texts.CANCEL)
        cancel_btn.setStyleSheet(get_button_secondary_style())
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        save_btn = QPushButton(texts.SAVE)
        save_btn.setStyleSheet(get_button_primary_style())
        save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(save_btn)

        layout.addLayout(btn_row)

    def _on_save(self):
        name = self._name_input.text().strip()
        if not name:
            return
        self.accept()

    def get_data(self) -> dict:
        return {
            'name': self._name_input.text().strip(),
            'provider_key': self._provider_combo.currentData(),
            'address': {
                'street': self._street_input.text().strip(),
                'zip_code': self._zip_input.text().strip(),
                'city': self._city_input.text().strip(),
            },
        }


class CredentialsDialog(QDialog):
    """Dialog fuer Provider-Credentials."""

    def __init__(self, parent=None, provider_key: str = '', credentials: dict = None):
        super().__init__(parent)
        self._provider_key = provider_key
        self._credentials = credentials or {}
        self.setWindowTitle(texts.WF_CREDENTIALS_TITLE)
        self.setMinimumWidth(420)
        self.setStyleSheet(get_dialog_style())
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        title_lbl = QLabel(texts.WF_CREDENTIALS_TITLE)
        title_lbl.setObjectName("dialogTitle")
        layout.addWidget(title_lbl)

        form = QFormLayout()
        form.setSpacing(12)

        self._access_key_input = QLineEdit(self._credentials.get('access_key', ''))
        self._access_key_input.setPlaceholderText(texts.WF_CREDENTIALS_ACCESS_KEY_PLACEHOLDER)
        form.addRow(QLabel(texts.WF_CREDENTIALS_ACCESS_KEY), self._access_key_input)

        self._secret_key_input = QLineEdit(self._credentials.get('secret_key', ''))
        self._secret_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._secret_key_input.setPlaceholderText(texts.WF_CREDENTIALS_SECRET_KEY_PLACEHOLDER)
        form.addRow(QLabel(texts.WF_CREDENTIALS_SECRET_KEY), self._secret_key_input)

        self._demo_checkbox = QCheckBox(texts.WF_CREDENTIALS_IS_DEMO)
        self._demo_checkbox.setChecked(self._credentials.get('is_demo', False))
        if self._provider_key != 'hrworks':
            self._demo_checkbox.setVisible(False)
        form.addRow(QLabel(""), self._demo_checkbox)

        layout.addLayout(form)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel_btn = QPushButton(texts.CANCEL)
        cancel_btn.setStyleSheet(get_button_secondary_style())
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        save_btn = QPushButton(texts.SAVE)
        save_btn.setStyleSheet(get_button_primary_style())
        save_btn.clicked.connect(self.accept)
        btn_row.addWidget(save_btn)

        layout.addLayout(btn_row)

    def get_data(self) -> dict:
        data = {
            'access_key': self._access_key_input.text().strip(),
            'secret_key': self._secret_key_input.text().strip(),
        }
        if self._provider_key == 'hrworks':
            data['is_demo'] = self._demo_checkbox.isChecked()
        return data


class EmployersView(QWidget):
    """Arbeitgeber-Verwaltung: Tabelle, CRUD, Credentials."""

    def __init__(self, wf_api: WorkforceApiClient, auth_api: AuthAPI):
        super().__init__()
        self._wf_api = wf_api
        self._auth_api = auth_api
        self._toast_manager = None
        self._employers_data: list[dict] = []
        self._thread_pool = QThreadPool.globalInstance()
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        header = QHBoxLayout()
        title = QLabel(texts.WF_EMPLOYERS_TITLE)
        title.setStyleSheet(f"""
            font-family: {FONT_HEADLINE}; font-size: {FONT_SIZE_H2};
            color: {PRIMARY_900}; font-weight: bold;
        """)
        header.addWidget(title)
        header.addStretch()

        add_btn = QPushButton(f"+ {texts.WF_EMPLOYER_ADD_BTN}")
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.setStyleSheet(f"""
            QPushButton {{
                padding: 6px 16px; font-family: {FONT_BODY};
                background-color: {ACCENT_500}; color: white;
                border: none; border-radius: {RADIUS_MD}; font-weight: bold;
            }}
            QPushButton:hover {{ background-color: #e88a2d; }}
        """)
        add_btn.clicked.connect(self._on_add_employer)
        header.addWidget(add_btn)

        refresh_btn = QPushButton(texts.WF_REFRESH)
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_btn.setStyleSheet(f"""
            QPushButton {{
                padding: 6px 16px; font-family: {FONT_BODY};
                background-color: {ACCENT_100}; color: {PRIMARY_900};
                border: 1px solid {ACCENT_500}; border-radius: {RADIUS_MD};
            }}
            QPushButton:hover {{ background-color: {ACCENT_500}; color: white; }}
        """)
        refresh_btn.clicked.connect(self.refresh)
        header.addWidget(refresh_btn)

        layout.addLayout(header)

        self._table = QTableWidget()
        self._table.setColumnCount(6)
        self._table.setHorizontalHeaderLabels([
            texts.WF_COL_NAME, texts.WF_COL_PROVIDER, texts.WF_COL_STATUS,
            texts.WF_COL_CREDENTIALS, texts.WF_COL_LAST_SYNC, texts.WF_COL_ACTIONS,
        ])
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.verticalHeader().setDefaultSectionSize(52)

        h = self._table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(5, 260)

        layout.addWidget(self._table)

        self._count_label = QLabel("")
        self._count_label.setStyleSheet(f"color: {PRIMARY_500}; font-size: {FONT_SIZE_CAPTION};")
        layout.addWidget(self._count_label)

    def refresh(self):
        worker = _LoadEmployersWorker(self._wf_api)
        worker.signals.finished.connect(self._on_employers_loaded)
        worker.signals.error.connect(self._on_load_error)
        self._thread_pool.start(worker)

    def _on_employers_loaded(self, employers: list):
        self._employers_data = employers
        self._populate_table(employers)

    def _on_load_error(self, error: str):
        logger.error(f"Arbeitgeber laden: {error}")
        if self._toast_manager:
            self._toast_manager.show_error(texts.WF_EMPLOYERS_LOAD_ERROR.format(error=error))

    def _populate_table(self, employers: list):
        self._table.setSortingEnabled(False)
        self._table.setRowCount(len(employers))
        self._count_label.setText(
            texts.WF_EMPLOYERS_COUNT.format(count=len(employers))
        )

        for row, emp in enumerate(employers):
            name_item = QTableWidgetItem(emp.get('name', ''))
            name_item.setFont(QFont(FONT_BODY))
            name_item.setData(Qt.ItemDataRole.UserRole, emp)
            self._table.setItem(row, 0, name_item)

            provider = emp.get('provider_key', '')
            provider_display = dict(PROVIDER_OPTIONS).get(provider, provider)
            self._table.setItem(row, 1, QTableWidgetItem(provider_display))

            status = emp.get('status', 'active')
            status_item = QTableWidgetItem(f"● {status}")
            color = SUCCESS if status == 'active' else TEXT_DISABLED
            status_item.setForeground(QColor(color))
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row, 2, status_item)

            has_creds = emp.get('has_credentials', False)
            cred_label = texts.WF_CREDENTIALS_OK if has_creds else texts.WF_CREDENTIALS_MISSING
            cred_item = QTableWidgetItem(cred_label)
            cred_color = SUCCESS if has_creds else ERROR
            cred_item.setForeground(QColor(cred_color))
            cred_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row, 3, cred_item)

            last_sync = format_date_de(emp.get('last_sync_at', '-') or '-')
            self._table.setItem(row, 4, QTableWidgetItem(last_sync))

            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(4, 2, 4, 2)
            actions_layout.setSpacing(6)

            cred_btn = QPushButton(texts.WF_CREDENTIALS_BTN)
            cred_btn.setFixedHeight(26)
            cred_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            cred_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent; color: #3498db;
                    border: 1px solid #3498db; border-radius: {RADIUS_SM};
                    padding: 2px 10px; font-family: {FONT_BODY}; font-size: 12px;
                }}
                QPushButton:hover {{ background-color: #3498db; color: white; }}
            """)
            cred_btn.clicked.connect(lambda checked, e=emp: self._on_credentials(e))
            actions_layout.addWidget(cred_btn)

            edit_btn = QPushButton(texts.EDIT)
            edit_btn.setFixedHeight(26)
            edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            edit_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {ACCENT_500}; color: white; border: none;
                    border-radius: {RADIUS_SM}; padding: 2px 10px;
                    font-family: {FONT_BODY}; font-size: 12px; font-weight: bold;
                }}
                QPushButton:hover {{ background-color: #e88a2d; }}
            """)
            edit_btn.clicked.connect(lambda checked, e=emp: self._on_edit_employer(e))
            actions_layout.addWidget(edit_btn)

            del_btn = QPushButton(texts.DELETE)
            del_btn.setFixedHeight(26)
            del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            del_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent; color: #e74c3c;
                    border: 1px solid #e74c3c; border-radius: {RADIUS_SM};
                    padding: 2px 10px; font-family: {FONT_BODY}; font-size: 12px;
                }}
                QPushButton:hover {{ background-color: #e74c3c; color: white; }}
            """)
            del_btn.clicked.connect(lambda checked, e=emp: self._on_delete_employer(e))
            actions_layout.addWidget(del_btn)

            actions_layout.addStretch()
            self._table.setCellWidget(row, 5, actions_widget)

        self._table.setSortingEnabled(True)

    # ── Actions ────────────────────────────────────────────────

    def _on_add_employer(self):
        dialog = EmployerDialog(parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        data = dialog.get_data()
        try:
            self._wf_api.create_employer(data)
            if self._toast_manager:
                self._toast_manager.show_success(texts.WF_EMPLOYER_CREATED)
            self.refresh()
        except Exception as e:
            if self._toast_manager:
                self._toast_manager.show_error(str(e))

    def _on_edit_employer(self, employer: dict):
        dialog = EmployerDialog(parent=self, employer=employer)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        data = dialog.get_data()
        try:
            self._wf_api.update_employer(employer['id'], data)
            if self._toast_manager:
                self._toast_manager.show_success(texts.WF_EMPLOYER_UPDATED)
            self.refresh()
        except Exception as e:
            if self._toast_manager:
                self._toast_manager.show_error(str(e))

    def _on_delete_employer(self, employer: dict):
        name = employer.get('name', '?')
        reply = QMessageBox.question(
            self, texts.WARNING,
            texts.WF_EMPLOYER_DELETE_CONFIRM.format(name=name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            self._wf_api.delete_employer(employer['id'])
            if self._toast_manager:
                self._toast_manager.show_success(texts.WF_EMPLOYER_DELETED.format(name=name))
            self.refresh()
        except Exception as e:
            if self._toast_manager:
                self._toast_manager.show_error(str(e))

    def _on_credentials(self, employer: dict):
        provider_key = employer.get('provider_key', '')
        employer_id = employer.get('id')
        existing = {}
        try:
            existing = self._wf_api.get_credentials(employer_id)
        except Exception:
            pass

        dialog = CredentialsDialog(
            parent=self, provider_key=provider_key, credentials=existing,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        cred_data = dialog.get_data()
        try:
            self._wf_api.save_credentials(employer_id, cred_data)
            if self._toast_manager:
                self._toast_manager.show_success(texts.WF_CREDENTIALS_SAVED)
            self.refresh()
        except Exception as e:
            if self._toast_manager:
                self._toast_manager.show_error(str(e))
