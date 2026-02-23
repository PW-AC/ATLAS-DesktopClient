"""
ACENCIA ATLAS - Admin Panel: KI-Provider-Verwaltung

Extrahiert aus admin_view.py (Zeilen 3845-4122).
"""

import logging

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QComboBox, QHeaderView, QAbstractItemView,
    QMessageBox, QDialog, QDialogButtonBox, QFormLayout, QLineEdit,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor

from api.client import APIClient
from i18n import de as texts
from ui.styles.tokens import (
    PRIMARY_900, TEXT_SECONDARY,
    FONT_HEADLINE,
    FONT_SIZE_CAPTION,
    get_button_primary_style, get_button_secondary_style, get_button_ghost_style,
)
from ui.admin.workers import AdminWriteWorker

logger = logging.getLogger(__name__)

SPACING_MD = 16
SPACING_LG = 24

STATUS_COLORS = {
    'success': '#27ae60',
    'error': '#e74c3c',
    'denied': '#f39c12',
}


class AiProvidersPanel(QWidget):
    """Admin-Panel fuer KI-Provider (API-Key-Verwaltung OpenRouter/OpenAI)."""

    def __init__(self, api_client: APIClient, toast_manager, ai_providers_api, parent=None):
        super().__init__(parent)
        self._api_client = api_client
        self._toast_manager = toast_manager
        self._ai_providers_api = ai_providers_api
        self._active_workers: list = []
        self._providers_data = []
        self._create_ui()

    def load_data(self):
        """Oeffentliche Methode zum Laden der Daten."""
        self._load_ai_providers()

    def _create_ui(self):
        """Erstellt das KI-Provider-Panel (API-Key-Verwaltung)."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING_LG, SPACING_LG, SPACING_LG, SPACING_LG)
        layout.setSpacing(SPACING_MD)

        # Header
        header = QHBoxLayout()
        title = QLabel(texts.AI_PROVIDER_TITLE)
        title.setFont(QFont(FONT_HEADLINE, 18))
        header.addWidget(title)
        header.addStretch()

        add_btn = QPushButton(texts.AI_PROVIDER_ADD)
        add_btn.setStyleSheet(get_button_primary_style())
        add_btn.setCursor(Qt.PointingHandCursor)
        add_btn.clicked.connect(self._show_add_provider_dialog)
        header.addWidget(add_btn)
        layout.addLayout(header)

        # Hint
        hint_label = QLabel(texts.AI_PROVIDER_HINT)
        hint_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: {FONT_SIZE_CAPTION}; padding: 4px 0;")
        layout.addWidget(hint_label)

        # Tabelle
        self._providers_table = QTableWidget()
        self._providers_table.setColumnCount(6)
        self._providers_table.setHorizontalHeaderLabels([
            texts.AI_PROVIDER_NAME, texts.AI_PROVIDER_TYPE, texts.AI_PROVIDER_KEY,
            texts.AI_PROVIDER_STATUS, "", texts.AI_PROVIDER_ACTIONS
        ])
        self._providers_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._providers_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self._providers_table.setColumnWidth(4, 10)
        self._providers_table.setColumnWidth(5, 340)
        self._providers_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._providers_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._providers_table.verticalHeader().setVisible(False)
        self._providers_table.setAlternatingRowColors(True)
        layout.addWidget(self._providers_table)

    def _load_ai_providers(self):
        """Laedt alle Provider-Keys vom Server."""
        def _do_load():
            return self._ai_providers_api.list_keys()

        worker = AdminWriteWorker(_do_load)
        worker.finished.connect(self._on_providers_loaded)
        worker.error.connect(lambda e: self._show_toast_error(f"Provider laden: {e}"))
        self._active_workers.append(worker)
        worker.start()

    def _on_providers_loaded(self, providers):
        """Aktualisiert die Provider-Tabelle."""
        from ui.toast import ToastManager
        self._providers_data = providers if providers else []
        table = self._providers_table
        table.setRowCount(len(self._providers_data))

        for row, p in enumerate(self._providers_data):
            table.setItem(row, 0, QTableWidgetItem(p.name))

            type_label = texts.AI_PROVIDER_OPENROUTER if p.provider_type == 'openrouter' else texts.AI_PROVIDER_OPENAI
            table.setItem(row, 1, QTableWidgetItem(type_label))

            table.setItem(row, 2, QTableWidgetItem(p.api_key_masked))

            status_text = texts.AI_PROVIDER_ACTIVE if p.is_active else texts.AI_PROVIDER_INACTIVE
            status_item = QTableWidgetItem(status_text)
            if p.is_active:
                status_item.setForeground(QColor(STATUS_COLORS['success']))
            table.setItem(row, 3, status_item)

            # Leer-Spalte (Platz fuer Test)
            table.setItem(row, 4, QTableWidgetItem(""))

            # Aktions-Buttons
            actions = QWidget()
            actions_layout = QHBoxLayout(actions)
            actions_layout.setContentsMargins(4, 2, 4, 2)
            actions_layout.setSpacing(4)

            if not p.is_active:
                activate_btn = QPushButton(texts.AI_PROVIDER_ACTIVATE)
                activate_btn.setStyleSheet(get_button_primary_style())
                activate_btn.setCursor(Qt.PointingHandCursor)
                activate_btn.setFixedHeight(28)
                activate_btn.clicked.connect(lambda _, pid=p.id, pname=p.name: self._activate_provider(pid, pname))
                actions_layout.addWidget(activate_btn)

            test_btn = QPushButton(texts.AI_PROVIDER_TEST)
            test_btn.setStyleSheet(get_button_secondary_style())
            test_btn.setCursor(Qt.PointingHandCursor)
            test_btn.setFixedHeight(28)
            test_btn.clicked.connect(lambda _, pid=p.id: self._test_provider(pid))
            actions_layout.addWidget(test_btn)

            edit_btn = QPushButton(texts.AI_PROVIDER_EDIT)
            edit_btn.setStyleSheet(get_button_ghost_style())
            edit_btn.setCursor(Qt.PointingHandCursor)
            edit_btn.setFixedHeight(28)
            edit_btn.clicked.connect(lambda _, pid=p.id: self._show_edit_provider_dialog(pid))
            actions_layout.addWidget(edit_btn)

            if not p.is_active:
                del_btn = QPushButton(texts.AI_PROVIDER_DELETE)
                del_btn.setStyleSheet(get_button_ghost_style())
                del_btn.setCursor(Qt.PointingHandCursor)
                del_btn.setFixedHeight(28)
                del_btn.clicked.connect(lambda _, pid=p.id, pname=p.name: self._delete_provider(pid, pname))
                actions_layout.addWidget(del_btn)

            table.setCellWidget(row, 5, actions)

        table.resizeRowsToContents()

    def _show_add_provider_dialog(self):
        """Dialog zum Anlegen eines neuen Providers."""
        dialog = QDialog(self)
        dialog.setWindowTitle(texts.AI_PROVIDER_DIALOG_TITLE_NEW)
        dialog.setMinimumWidth(450)
        form = QFormLayout(dialog)

        name_edit = QLineEdit()
        name_edit.setPlaceholderText(texts.AI_PROVIDER_NAME)
        form.addRow(texts.AI_PROVIDER_NAME + ":", name_edit)

        type_combo = QComboBox()
        type_combo.addItem(texts.AI_PROVIDER_OPENROUTER, "openrouter")
        type_combo.addItem(texts.AI_PROVIDER_OPENAI, "openai")
        form.addRow(texts.AI_PROVIDER_TYPE + ":", type_combo)

        key_edit = QLineEdit()
        key_edit.setPlaceholderText(texts.AI_PROVIDER_KEY_PLACEHOLDER)
        key_edit.setEchoMode(QLineEdit.Password)
        form.addRow(texts.AI_PROVIDER_KEY + ":", key_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)

        if dialog.exec() == QDialog.Accepted:
            from ui.toast import ToastManager
            name = name_edit.text().strip()
            provider_type = type_combo.currentData()
            api_key = key_edit.text().strip()

            if not name or not api_key:
                return

            def _do_create():
                return self._ai_providers_api.create_key(provider_type, name, api_key)

            worker = AdminWriteWorker(_do_create)
            worker.finished.connect(lambda _: (
                ToastManager.instance().show_success(texts.AI_PROVIDER_CREATED.format(name=name)),
                self._load_ai_providers()
            ))
            worker.error.connect(lambda e: ToastManager.instance().show_error(str(e)))
            self._active_workers.append(worker)
            worker.start()

    def _show_edit_provider_dialog(self, provider_id: int):
        """Dialog zum Bearbeiten eines Providers."""
        provider = None
        for p in self._providers_data:
            if p.id == provider_id:
                provider = p
                break
        if not provider:
            return

        dialog = QDialog(self)
        dialog.setWindowTitle(texts.AI_PROVIDER_DIALOG_TITLE_EDIT)
        dialog.setMinimumWidth(450)
        form = QFormLayout(dialog)

        name_edit = QLineEdit(provider.name)
        form.addRow(texts.AI_PROVIDER_NAME + ":", name_edit)

        key_edit = QLineEdit()
        key_edit.setPlaceholderText(texts.AI_PROVIDER_KEY_UNCHANGED)
        key_edit.setEchoMode(QLineEdit.Password)
        form.addRow(texts.AI_PROVIDER_KEY + ":", key_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)

        if dialog.exec() == QDialog.Accepted:
            from ui.toast import ToastManager
            name = name_edit.text().strip()
            api_key = key_edit.text().strip() or None

            def _do_update():
                return self._ai_providers_api.update_key(provider_id, name=name, api_key=api_key)

            worker = AdminWriteWorker(_do_update)
            worker.finished.connect(lambda _: (
                ToastManager.instance().show_success(texts.AI_PROVIDER_UPDATED),
                self._load_ai_providers()
            ))
            worker.error.connect(lambda e: ToastManager.instance().show_error(str(e)))
            self._active_workers.append(worker)
            worker.start()

    def _activate_provider(self, provider_id: int, name: str):
        """Provider aktivieren nach Bestaetigung."""
        from ui.toast import ToastManager
        reply = QMessageBox.question(
            self, texts.AI_PROVIDER_ACTIVATE,
            texts.AI_PROVIDER_CONFIRM_ACTIVATE.format(name=name),
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        def _do_activate():
            return self._ai_providers_api.activate_key(provider_id)

        worker = AdminWriteWorker(_do_activate)
        worker.finished.connect(lambda _: (
            ToastManager.instance().show_success(texts.AI_PROVIDER_ACTIVATED.format(name=name)),
            self._load_ai_providers()
        ))
        worker.error.connect(lambda e: ToastManager.instance().show_error(str(e)))
        self._active_workers.append(worker)
        worker.start()

    def _test_provider(self, provider_id: int):
        """Provider-Key testen."""
        from ui.toast import ToastManager

        def _do_test():
            return self._ai_providers_api.test_key(provider_id)

        worker = AdminWriteWorker(_do_test)
        worker.finished.connect(lambda result: (
            ToastManager.instance().show_success(texts.AI_PROVIDER_TEST_SUCCESS)
            if result and result.get('success')
            else ToastManager.instance().show_error(
                texts.AI_PROVIDER_TEST_FAILED.format(error=result.get('error', ''))
            )
        ))
        worker.error.connect(lambda e: ToastManager.instance().show_error(
            texts.AI_PROVIDER_TEST_FAILED.format(error=e)
        ))
        self._active_workers.append(worker)
        worker.start()

    def _delete_provider(self, provider_id: int, name: str):
        """Provider loeschen nach Bestaetigung."""
        from ui.toast import ToastManager
        reply = QMessageBox.question(
            self, texts.AI_PROVIDER_DELETE,
            texts.AI_PROVIDER_CONFIRM_DELETE.format(name=name),
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        def _do_delete():
            return self._ai_providers_api.delete_key(provider_id)

        worker = AdminWriteWorker(_do_delete)
        worker.finished.connect(lambda _: (
            ToastManager.instance().show_success(texts.AI_PROVIDER_DELETED),
            self._load_ai_providers()
        ))
        worker.error.connect(lambda e: ToastManager.instance().show_error(str(e)))
        self._active_workers.append(worker)
        worker.start()

    def _show_toast_error(self, msg: str):
        """Zeigt eine Fehler-Toast-Benachrichtigung."""
        from ui.toast import ToastManager
        ToastManager.instance().show_error(msg)
