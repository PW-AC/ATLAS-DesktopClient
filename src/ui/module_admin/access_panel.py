"""
ACENCIA ATLAS - Modul-Admin: Zugriff-Tab

Zeigt User mit Modul-Zugriff, Rollen-Zuweisung pro User.
"""

import logging
from typing import List, Dict

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QHeaderView, QAbstractItemView, QComboBox,
    QMessageBox, QDialog, QListWidget, QListWidgetItem, QDialogButtonBox,
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor, QFont

from api.client import APIClient, APIError
from api.auth import AuthAPI
from api.admin_modules import AdminModulesAPI
from i18n import de as texts
from ui.styles.tokens import (
    PRIMARY_900, PRIMARY_500, PRIMARY_100, PRIMARY_0,
    ACCENT_500, ACCENT_100,
    SUCCESS, ERROR, WARNING,
    FONT_HEADLINE, FONT_BODY,
    FONT_SIZE_H3, FONT_SIZE_BODY, FONT_SIZE_CAPTION,
    RADIUS_MD,
    get_button_primary_style, get_button_secondary_style, get_button_danger_style,
)

logger = logging.getLogger(__name__)


class _LoadDataWorker(QThread):
    finished = Signal(list, list)

    def __init__(self, api: AdminModulesAPI, module_key: str, parent=None):
        super().__init__(parent)
        self._api = api
        self._key = module_key

    def run(self):
        try:
            users = self._api.get_module_users(self._key)
            roles = self._api.get_module_roles(self._key)
            self.finished.emit(users, roles)
        except Exception:
            self.finished.emit([], [])


class _AssignRolesDialog(QDialog):
    """Dialog zum Zuweisen von Rollen an einen User fuer dieses Modul."""

    def __init__(self, username: str, available_roles: List[Dict],
                 current_role_ids: List[int], parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"{texts.USER_ROLES_HEADER}: {username}")
        self.setMinimumWidth(450)
        self.setMinimumHeight(350)

        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        info = QLabel(f"{texts.USER_ROLES_HEADER} fuer <b>{username}</b>:")
        info.setStyleSheet(f"font-family: {FONT_HEADLINE}; font-size: {FONT_SIZE_BODY}; color: {PRIMARY_900};")
        layout.addWidget(info)

        if not available_roles:
            hint = QLabel(texts.ROLE_CREATE + " -- Es sind noch keine Rollen vorhanden.")
            hint.setStyleSheet(f"color: {WARNING}; font-style: italic; padding: 16px 0;")
            hint.setWordWrap(True)
            layout.addWidget(hint)

        self._role_list = QListWidget()
        self._role_list.setStyleSheet(f"""
            QListWidget {{
                border: 1px solid {PRIMARY_100};
                border-radius: {RADIUS_MD};
                padding: 8px;
                font-family: {FONT_BODY};
                font-size: {FONT_SIZE_BODY};
            }}
            QListWidget::item {{
                padding: 8px 4px;
                border-bottom: 1px solid {PRIMARY_100};
            }}
            QListWidget::item:hover {{
                background-color: {ACCENT_100};
            }}
        """)
        for role in available_roles:
            perms = role.get('permissions', [])
            perm_hint = f"  ({len(perms)} Rechte)" if perms else ""
            item = QListWidgetItem(f"{role.get('name', '')}  [{role.get('role_key', '')}]{perm_hint}")
            item.setData(Qt.UserRole, role['id'])
            item.setCheckState(Qt.Checked if role['id'] in current_role_ids else Qt.Unchecked)
            self._role_list.addItem(item)
        layout.addWidget(self._role_list)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel_btn = QPushButton(texts.CANCEL if hasattr(texts, 'CANCEL') else "Abbrechen")
        cancel_btn.setStyleSheet(get_button_secondary_style())
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        save_btn = QPushButton(texts.SAVE if hasattr(texts, 'SAVE') else "Speichern")
        save_btn.setStyleSheet(get_button_primary_style())
        save_btn.clicked.connect(self.accept)
        btn_row.addWidget(save_btn)

        layout.addLayout(btn_row)

    def get_selected_role_ids(self) -> List[int]:
        result = []
        for i in range(self._role_list.count()):
            item = self._role_list.item(i)
            if item.checkState() == Qt.Checked:
                result.append(item.data(Qt.UserRole))
        return result


class ModuleAccessPanel(QWidget):
    """Zeigt und verwaltet User-Zugriff + Rollen-Zuweisung fuer ein Modul."""

    def __init__(self, module_key: str, api_client: APIClient,
                 auth_api: AuthAPI, modules_api: AdminModulesAPI, parent=None):
        super().__init__(parent)
        self._module_key = module_key
        self._api_client = api_client
        self._auth_api = auth_api
        self._modules_api = modules_api
        self._users_data: List[Dict] = []
        self._roles_data: List[Dict] = []
        self._worker = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel(texts.MODULE_USERS_WITH_ACCESS)
        title.setStyleSheet(
            f"font-family: {FONT_HEADLINE}; font-size: {FONT_SIZE_H3}; "
            f"font-weight: 700; color: {PRIMARY_900};"
        )
        header.addWidget(title)
        header.addStretch()

        refresh_btn = QPushButton(f"\u21BB  {texts.SRVMGMT_REFRESH}")
        refresh_btn.setCursor(Qt.PointingHandCursor)
        refresh_btn.setStyleSheet(get_button_secondary_style())
        refresh_btn.clicked.connect(self.load_data)
        header.addWidget(refresh_btn)
        layout.addLayout(header)

        self._table = QTableWidget()
        self._table.setColumnCount(6)
        self._table.setHorizontalHeaderLabels([
            "Username", "Kontotyp",
            "Freigeschaltet", "Zugangslevel",
            "Rollen", "Aktionen"
        ])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Fixed)
        self._table.setColumnWidth(5, 200)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setDefaultSectionSize(44)
        layout.addWidget(self._table)

        hint = QLabel(texts.MODULE_ENABLE_FIRST)
        hint.setStyleSheet(
            f"font-size: {FONT_SIZE_CAPTION}; color: {PRIMARY_500}; "
            f"padding: 8px 12px; background: {PRIMARY_100}; border-radius: {RADIUS_MD};"
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

    def load_data(self):
        if self._worker and self._worker.isRunning():
            return
        self._worker = _LoadDataWorker(self._modules_api, self._module_key, self)
        self._worker.finished.connect(self._on_data_loaded)
        self._worker.start()

    def _on_data_loaded(self, users: List[Dict], roles: List[Dict]):
        self._users_data = users
        self._roles_data = roles
        self._table.setRowCount(len(users))

        for row, u in enumerate(users):
            # Username
            name_item = QTableWidgetItem(u.get('username', ''))
            name_item.setFont(QFont(FONT_BODY, weight=QFont.Weight.Bold))
            self._table.setItem(row, 0, name_item)

            # Kontotyp
            at = u.get('account_type', 'user')
            type_labels = {
                'super_admin': texts.ACCOUNT_TYPE_SUPER_ADMIN,
                'admin': texts.ACCOUNT_TYPE_ADMIN,
                'user': texts.ACCOUNT_TYPE_USER,
            }
            type_item = QTableWidgetItem(type_labels.get(at, at))
            if at == 'super_admin':
                type_item.setForeground(QColor('#dc2626'))
            elif at == 'admin':
                type_item.setForeground(QColor(ACCENT_500))
            self._table.setItem(row, 1, type_item)

            # Freigeschaltet
            enabled = u.get('is_enabled', False)
            en_item = QTableWidgetItem("  Ja" if enabled else "  Nein")
            en_item.setForeground(QColor(SUCCESS) if enabled else QColor(ERROR))
            en_item.setFont(QFont(FONT_BODY, weight=QFont.Weight.Bold))
            self._table.setItem(row, 2, en_item)

            # Zugangslevel
            al = u.get('access_level') or '-'
            level_labels = {'user': texts.ACCESS_LEVEL_USER, 'admin': texts.ACCESS_LEVEL_ADMIN}
            al_item = QTableWidgetItem(level_labels.get(al, al))
            if al == 'admin':
                al_item.setForeground(QColor(ACCENT_500))
                al_item.setFont(QFont(FONT_BODY, weight=QFont.Weight.Bold))
            self._table.setItem(row, 3, al_item)

            # Rollen
            user_roles = u.get('roles', [])
            role_names = ', '.join(r.get('name', r.get('role_key', '')) for r in user_roles)
            roles_item = QTableWidgetItem(role_names or '-')
            if role_names:
                roles_item.setForeground(QColor(PRIMARY_900))
            else:
                roles_item.setForeground(QColor(PRIMARY_500))
            self._table.setItem(row, 4, roles_item)

            # Aktionen
            actions = QWidget()
            actions_layout = QHBoxLayout(actions)
            actions_layout.setContentsMargins(4, 4, 4, 4)
            actions_layout.setSpacing(6)

            if enabled:
                roles_btn = QPushButton(f"\u270E {texts.USER_ROLES_HEADER}")
                roles_btn.setCursor(Qt.PointingHandCursor)
                roles_btn.setFixedHeight(26)
                roles_btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {ACCENT_500};
                        color: white;
                        border: none;
                        border-radius: 4px;
                        padding: 2px 10px;
                        font-family: {FONT_BODY};
                        font-size: 11px;
                        font-weight: 700;
                    }}
                    QPushButton:hover {{ background-color: #e88a2d; }}
                """)
                roles_btn.clicked.connect(
                    lambda _, uid=u['id'], uname=u['username'], uroles=user_roles:
                        self._assign_roles(uid, uname, uroles)
                )
                actions_layout.addWidget(roles_btn)
            else:
                no_label = QLabel(texts.MODULE_NOT_ENABLED)
                no_label.setStyleSheet(
                    f"color: {ERROR}; font-size: {FONT_SIZE_CAPTION}; font-style: italic;"
                )
                actions_layout.addWidget(no_label)

            actions_layout.addStretch()
            self._table.setCellWidget(row, 5, actions)

    def _assign_roles(self, user_id: int, username: str, current_roles: List[Dict]):
        current_ids = [r.get('role_id', r.get('id', 0)) for r in current_roles]
        dlg = _AssignRolesDialog(username, self._roles_data, current_ids, parent=self)
        if dlg.exec() == QDialog.Accepted:
            selected = dlg.get_selected_role_ids()
            try:
                self._modules_api.assign_user_roles(self._module_key, user_id, selected)
                tm = getattr(self, '_toast_manager', None)
                if tm:
                    tm.show_success(texts.USER_ROLES_ASSIGNED)
                self.load_data()
            except APIError as e:
                tm = getattr(self, '_toast_manager', None)
                if tm:
                    tm.show_error(str(e))
