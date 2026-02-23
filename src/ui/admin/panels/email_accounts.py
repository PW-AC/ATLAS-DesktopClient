"""
ACENCIA ATLAS - E-Mail-Konten Panel

Extrahiert aus admin_view.py (Lines 4388-4587).
"""

from typing import List, Dict
import logging

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QHeaderView, QDialog, QMessageBox,
)
from PySide6.QtGui import QFont

from i18n import de as texts
from ui.styles.tokens import (
    PRIMARY_900, ACCENT_500, ACCENT_100,
    FONT_HEADLINE,
    get_button_primary_style, get_button_secondary_style,
)
from ui.admin.workers import AdminWriteWorker
from ui.admin.dialogs import EmailAccountDialog

logger = logging.getLogger(__name__)


class EmailAccountsPanel(QWidget):
    """E-Mail-Konten Verwaltung (SMTP/IMAP)."""

    def __init__(self, api_client, toast_manager, email_accounts_api, parent=None):
        super().__init__(parent)
        self._api_client = api_client
        self._toast_manager = toast_manager
        self._email_accounts_api = email_accounts_api
        self._ea_data: List[Dict] = []
        self._active_workers: List = []
        self._create_ui()

    def load_data(self):
        """Public entry point to load panel data."""
        self._load_email_accounts()

    def _create_ui(self):
        """Erstellt den E-Mail-Konten-Tab."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)

        # Toolbar
        toolbar = QHBoxLayout()
        title = QLabel(texts.EMAIL_ACCOUNT_TITLE)
        title.setFont(QFont(FONT_HEADLINE, 18))
        title.setStyleSheet(f"color: {PRIMARY_900};")
        toolbar.addWidget(title)
        toolbar.addStretch()

        add_btn = QPushButton(f"+ {texts.EMAIL_ACCOUNT_ADD}")
        add_btn.setStyleSheet(get_button_primary_style())
        add_btn.clicked.connect(self._add_email_account)
        toolbar.addWidget(add_btn)

        test_btn = QPushButton(texts.EMAIL_ACCOUNT_TEST)
        test_btn.setStyleSheet(get_button_secondary_style())
        test_btn.clicked.connect(self._test_email_account)
        toolbar.addWidget(test_btn)

        layout.addLayout(toolbar)

        # Tabelle
        self._ea_table = QTableWidget()
        self._ea_table.setColumnCount(6)
        self._ea_table.setHorizontalHeaderLabels([
            texts.EMAIL_ACCOUNT_NAME, texts.EMAIL_ACCOUNT_TYPE,
            texts.EMAIL_ACCOUNT_SMTP_HOST, texts.EMAIL_ACCOUNT_FROM_ADDRESS,
            texts.EMAIL_ACCOUNT_ACTIVE, ""
        ])
        ea_header = self._ea_table.horizontalHeader()
        ea_header.setStretchLastSection(False)
        ea_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self._ea_table.setColumnWidth(0, 160)
        ea_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self._ea_table.setColumnWidth(1, 80)
        ea_header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        ea_header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        ea_header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self._ea_table.setColumnWidth(4, 70)
        ea_header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self._ea_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._ea_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._ea_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._ea_table.verticalHeader().setVisible(False)
        self._ea_table.verticalHeader().setDefaultSectionSize(50)
        layout.addWidget(self._ea_table)

    def _load_email_accounts(self):
        """Laedt E-Mail-Konten vom Server."""
        try:
            self._ea_data = self._email_accounts_api.get_accounts()
            self._populate_email_accounts_table()
        except Exception as e:
            logger.error(f"Fehler beim Laden der E-Mail-Konten: {e}")

    def _derive_account_type(self, acc: Dict) -> str:
        """Leitet den Kontotyp aus vorhandenen Daten ab."""
        if acc.get('account_type'):
            return acc['account_type']
        has_smtp = bool(acc.get('smtp_host', '').strip())
        has_imap = bool(acc.get('imap_host', '').strip())
        if has_smtp and has_imap:
            return 'both'
        elif has_imap:
            return 'imap'
        return 'smtp'

    def _populate_email_accounts_table(self):
        """Fuellt die E-Mail-Konten-Tabelle."""
        self._ea_table.setRowCount(len(self._ea_data))
        type_labels = {'smtp': texts.EMAIL_ACCOUNT_TYPE_SMTP,
                       'imap': texts.EMAIL_ACCOUNT_TYPE_IMAP,
                       'both': texts.EMAIL_ACCOUNT_TYPE_BOTH}
        for row, acc in enumerate(self._ea_data):
            self._ea_table.setItem(row, 0, QTableWidgetItem(acc.get('account_name', acc.get('name', ''))))
            derived_type = self._derive_account_type(acc)
            self._ea_table.setItem(row, 1, QTableWidgetItem(
                type_labels.get(derived_type, derived_type)
            ))
            self._ea_table.setItem(row, 2, QTableWidgetItem(acc.get('smtp_host', '') or ''))
            self._ea_table.setItem(row, 3, QTableWidgetItem(acc.get('from_address', '')))
            active_item = QTableWidgetItem("Ja" if acc.get('is_active') else "Nein")
            self._ea_table.setItem(row, 4, active_item)

            # Aktions-Buttons
            btn_widget = QWidget()
            btn_layout = QHBoxLayout(btn_widget)
            btn_layout.setContentsMargins(2, 1, 2, 1)
            btn_layout.setSpacing(4)

            edit_btn = QPushButton(texts.EMAIL_ACCOUNT_EDIT)
            edit_btn.setFixedHeight(26)
            edit_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {ACCENT_100};
                    color: {PRIMARY_900};
                    border: 1px solid {ACCENT_500};
                    border-radius: 4px;
                    padding: 2px 10px;
                    font-size: 12px;
                }}
                QPushButton:hover {{ background-color: {ACCENT_500}; color: white; }}
            """)
            edit_btn.clicked.connect(lambda checked, r=row: self._edit_email_account(r))
            btn_layout.addWidget(edit_btn)

            del_btn = QPushButton(texts.EMAIL_ACCOUNT_DELETE)
            del_btn.setFixedHeight(26)
            del_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: #fff0f0;
                    color: #c0392b;
                    border: 1px solid #e74c3c;
                    border-radius: 4px;
                    padding: 2px 10px;
                    font-size: 12px;
                }}
                QPushButton:hover {{ background-color: #e74c3c; color: white; }}
            """)
            del_btn.clicked.connect(lambda checked, r=row: self._delete_email_account(r))
            btn_layout.addWidget(del_btn)

            self._ea_table.setCellWidget(row, 5, btn_widget)

    def _add_email_account(self):
        """Neues E-Mail-Konto anlegen."""
        dialog = EmailAccountDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            try:
                result = self._email_accounts_api.create_account(data)
                if result:
                    self._toast_manager.show_success(texts.EMAIL_ACCOUNT_CREATED)
                    self._load_email_accounts()
            except Exception as e:
                self._toast_manager.show_error(texts.EMAIL_ACCOUNT_ERROR_SAVE.format(error=str(e)))

    def _edit_email_account(self, row: int):
        """E-Mail-Konto bearbeiten."""
        if row < 0 or row >= len(self._ea_data):
            return
        acc = dict(self._ea_data[row])
        if not acc.get('account_type'):
            acc['account_type'] = self._derive_account_type(acc)
        dialog = EmailAccountDialog(self, existing_data=acc)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            try:
                result = self._email_accounts_api.update_account(acc['id'], data)
                if result:
                    self._toast_manager.show_success(texts.EMAIL_ACCOUNT_UPDATED)
                    self._load_email_accounts()
            except Exception as e:
                self._toast_manager.show_error(texts.EMAIL_ACCOUNT_ERROR_SAVE.format(error=str(e)))

    def _delete_email_account(self, row: int):
        """E-Mail-Konto deaktivieren."""
        if row < 0 or row >= len(self._ea_data):
            return
        acc = self._ea_data[row]
        reply = QMessageBox.question(
            self, texts.EMAIL_ACCOUNT_CONFIRM_DELETE_TITLE,
            texts.EMAIL_ACCOUNT_CONFIRM_DELETE.format(name=acc.get('account_name', acc.get('name', ''))),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                if self._email_accounts_api.delete_account(acc['id']):
                    self._toast_manager.show_success(texts.EMAIL_ACCOUNT_DELETED)
                    self._load_email_accounts()
            except Exception as e:
                self._toast_manager.show_error(texts.EMAIL_ACCOUNT_ERROR_SAVE.format(error=str(e)))

    def _test_email_account(self):
        """SMTP-Verbindung testen."""
        selected = self._ea_table.currentRow()
        if selected < 0 or selected >= len(self._ea_data):
            self._toast_manager.show_info(texts.EMAIL_ACCOUNT_NONE)
            return
        acc = self._ea_data[selected]
        self._toast_manager.show_info(texts.EMAIL_ACCOUNT_TEST_RUNNING)
        try:
            result = self._email_accounts_api.test_connection(acc['id'])
            if result and result.get('test_result') == 'success':
                self._toast_manager.show_success(texts.EMAIL_ACCOUNT_TEST_SUCCESS)
            else:
                self._toast_manager.show_error(texts.EMAIL_ACCOUNT_TEST_FAILED.format(error=result.get('message', 'Unbekannt')))
        except Exception as e:
            self._toast_manager.show_error(texts.EMAIL_ACCOUNT_TEST_FAILED.format(error=str(e)))
