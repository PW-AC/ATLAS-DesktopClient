"""
ACENCIA ATLAS - Modul-Admin: Rollen-Tab

CRUD fuer Rollen + Rechte-Katalog des Moduls.
"""

import logging
from typing import List, Dict, Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QHeaderView, QAbstractItemView, QMessageBox,
    QDialog, QFormLayout, QLineEdit, QTextEdit, QListWidget, QListWidgetItem,
    QDialogButtonBox,
)
from PySide6.QtCore import Qt, QThread, Signal

from api.client import APIClient, APIError
from api.admin_modules import AdminModulesAPI
from i18n import de as texts
from ui.styles.tokens import (
    PRIMARY_900, PRIMARY_500, PRIMARY_100, ACCENT_500, ERROR,
    FONT_HEADLINE, FONT_BODY,
    FONT_SIZE_H3, FONT_SIZE_BODY, FONT_SIZE_CAPTION,
    RADIUS_MD,
)

logger = logging.getLogger(__name__)


class _LoadRolesWorker(QThread):
    finished = Signal(list, list)

    def __init__(self, api: AdminModulesAPI, module_key: str, parent=None):
        super().__init__(parent)
        self._api = api
        self._key = module_key

    def run(self):
        try:
            roles = self._api.get_module_roles(self._key)
            perms = self._api.get_module_permissions(self._key)
            self.finished.emit(roles, perms)
        except Exception:
            self.finished.emit([], [])


class RoleEditDialog(QDialog):
    """Dialog zum Erstellen/Bearbeiten einer Rolle."""

    def __init__(self, available_permissions: List[Dict],
                 role: Optional[Dict] = None, parent=None):
        super().__init__(parent)
        self._role = role
        self.setWindowTitle(texts.ROLE_EDIT if role else texts.ROLE_CREATE)
        self.setMinimumWidth(480)

        layout = QFormLayout(self)

        self._key_input = QLineEdit()
        if role:
            self._key_input.setText(role.get('role_key', ''))
            self._key_input.setReadOnly(True)
        layout.addRow(texts.ROLE_KEY, self._key_input)

        self._name_input = QLineEdit()
        if role:
            self._name_input.setText(role.get('name', ''))
        layout.addRow(texts.ROLE_NAME, self._name_input)

        self._desc_input = QTextEdit()
        self._desc_input.setMaximumHeight(80)
        if role:
            self._desc_input.setPlainText(role.get('description', '') or '')
        layout.addRow("Beschreibung", self._desc_input)

        layout.addRow(QLabel(texts.ROLE_PERMISSIONS))
        self._perm_list = QListWidget()
        current_perms = set(role.get('permissions', [])) if role else set()
        for p in available_permissions:
            item = QListWidgetItem(f"{p['permission_key']} - {p.get('name', '')}")
            item.setData(Qt.UserRole, p['permission_key'])
            item.setCheckState(Qt.Checked if p['permission_key'] in current_perms else Qt.Unchecked)
            self._perm_list.addItem(item)
        layout.addWidget(self._perm_list)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_data(self) -> Dict:
        perms = []
        for i in range(self._perm_list.count()):
            item = self._perm_list.item(i)
            if item.checkState() == Qt.Checked:
                perms.append(item.data(Qt.UserRole))
        return {
            'role_key': self._key_input.text().strip(),
            'name': self._name_input.text().strip(),
            'description': self._desc_input.toPlainText().strip(),
            'permissions': perms,
        }


class ModuleRolesPanel(QWidget):
    """Rollen-Verwaltung fuer ein Modul."""

    def __init__(self, module_key: str, api_client: APIClient,
                 modules_api: AdminModulesAPI, parent=None):
        super().__init__(parent)
        self._module_key = module_key
        self._api_client = api_client
        self._modules_api = modules_api
        self._roles_data: List[Dict] = []
        self._perms_data: List[Dict] = []
        self._worker = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)

        header = QHBoxLayout()
        title = QLabel(texts.MODULE_ADMIN_TAB_ROLES)
        title.setStyleSheet(f"font-family: {FONT_HEADLINE}; font-size: {FONT_SIZE_H3}; font-weight: 700; color: {PRIMARY_900};")
        header.addWidget(title)
        header.addStretch()

        self._create_btn = QPushButton(f"+  {texts.ROLE_CREATE}")
        self._create_btn.setCursor(Qt.PointingHandCursor)
        self._create_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ACCENT_500};
                color: white;
                border: none;
                border-radius: {RADIUS_MD};
                padding: 8px 20px;
                font-family: {FONT_BODY};
                font-weight: 700;
            }}
            QPushButton:hover {{ background-color: #e88a2d; }}
        """)
        self._create_btn.clicked.connect(self._on_create)
        header.addWidget(self._create_btn)
        layout.addLayout(header)

        self._table = QTableWidget()
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels([
            texts.ROLE_KEY, texts.ROLE_NAME, texts.ROLE_PERMISSIONS, "System", ""
        ])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Fixed)
        self._table.setColumnWidth(4, 300)
        self._table.verticalHeader().setDefaultSectionSize(44)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        layout.addWidget(self._table)

    def load_data(self):
        if self._worker and self._worker.isRunning():
            return
        self._worker = _LoadRolesWorker(self._modules_api, self._module_key, self)
        self._worker.finished.connect(self._on_loaded)
        self._worker.start()

    def _on_loaded(self, roles: List[Dict], perms: List[Dict]):
        self._roles_data = roles
        self._perms_data = perms
        self._table.setRowCount(len(roles))
        for row, role in enumerate(roles):
            self._table.setItem(row, 0, QTableWidgetItem(role.get('role_key', '')))
            self._table.setItem(row, 1, QTableWidgetItem(role.get('name', '')))
            perm_keys = role.get('permissions', [])
            self._table.setItem(row, 2, QTableWidgetItem(', '.join(perm_keys) if perm_keys else '-'))
            self._table.setItem(row, 3, QTableWidgetItem("Ja" if role.get('is_system') else "Nein"))

            actions = QWidget()
            actions_layout = QHBoxLayout(actions)
            actions_layout.setContentsMargins(4, 2, 4, 2)
            actions_layout.setSpacing(4)

            edit_btn = QPushButton(texts.ROLE_EDIT)
            edit_btn.setCursor(Qt.PointingHandCursor)
            edit_btn.setFixedHeight(32)
            edit_btn.setMinimumWidth(100)
            edit_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {PRIMARY_900};
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 4px 16px;
                    font-family: {FONT_BODY};
                    font-size: 12px;
                    font-weight: 700;
                }}
                QPushButton:hover {{ background-color: {PRIMARY_500}; }}
            """)
            edit_btn.clicked.connect(lambda _, r=role: self._on_edit(r))
            actions_layout.addWidget(edit_btn)

            del_btn = QPushButton(texts.ROLE_DELETE)
            del_btn.setCursor(Qt.PointingHandCursor)
            del_btn.setFixedHeight(32)
            del_btn.setMinimumWidth(100)
            is_system = bool(role.get('is_system'))
            del_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    color: {ERROR};
                    border: 1px solid {ERROR};
                    border-radius: 4px;
                    padding: 4px 16px;
                    font-family: {FONT_BODY};
                    font-size: 12px;
                    font-weight: 700;
                }}
                QPushButton:hover {{ background-color: {ERROR}; color: white; }}
                QPushButton:disabled {{ color: {PRIMARY_500}; border-color: {PRIMARY_100}; }}
            """)
            if is_system:
                del_btn.setEnabled(False)
                del_btn.setToolTip(texts.ROLE_SYSTEM_LOCKED)
            del_btn.clicked.connect(lambda _, r=role: self._on_delete(r))
            actions_layout.addWidget(del_btn)

            self._table.setCellWidget(row, 4, actions)

    def _on_create(self):
        dlg = RoleEditDialog(self._perms_data, parent=self)
        if dlg.exec() == QDialog.Accepted:
            data = dlg.get_data()
            if not data['role_key'] or not data['name']:
                return
            try:
                self._modules_api.create_role(
                    self._module_key, data['role_key'], data['name'],
                    data['description'], data['permissions']
                )
                self.load_data()
            except APIError as e:
                QMessageBox.warning(self, texts.WARNING, str(e))

    def _on_edit(self, role: Dict):
        dlg = RoleEditDialog(self._perms_data, role=role, parent=self)
        if dlg.exec() == QDialog.Accepted:
            data = dlg.get_data()
            try:
                self._modules_api.update_role(self._module_key, role['id'], data)
                self.load_data()
            except APIError as e:
                QMessageBox.warning(self, texts.WARNING, str(e))

    def _on_delete(self, role: Dict):
        if role.get('is_system'):
            return
        reply = QMessageBox.question(
            self, texts.ROLE_DELETE,
            texts.ROLE_DELETE_CONFIRM.format(name=role.get('name', '')),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self._modules_api.delete_role(self._module_key, role['id'])
                self.load_data()
            except APIError as e:
                QMessageBox.warning(self, texts.WARNING, str(e))
