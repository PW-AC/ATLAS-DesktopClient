"""
ACENCIA ATLAS - Nutzerverwaltung Panel

Standalone QWidget fuer die Nutzerverwaltung im Admin-Bereich.
Extrahiert aus admin_view.py (Schritt 5 Refactoring).
"""

from typing import Optional, Dict

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QDialog, QMessageBox, QHeaderView, QAbstractItemView,
)
from PySide6.QtGui import QFont, QColor

from api.client import APIClient, APIError
from api.auth import AuthAPI
from api.admin import AdminAPI
from i18n import de as texts

from ui.styles.tokens import (
    PRIMARY_900, PRIMARY_500,
    ACCENT_500,
    FONT_HEADLINE, FONT_BODY,
    RADIUS_MD,
)
from ui.admin.workers import LoadUsersWorker, AdminWriteWorker
from ui.admin.dialogs import UserEditDialog, ChangePasswordDialog


class UserManagementPanel(QWidget):
    """Nutzerverwaltung: Erstellen, Bearbeiten, Sperren, Passwort aendern, Deaktivieren."""

    def __init__(self, api_client: APIClient, auth_api: AuthAPI,
                 toast_manager, admin_api: AdminAPI, **kwargs):
        super().__init__()
        self._api_client = api_client
        self._auth_api = auth_api
        self._toast_manager = toast_manager
        self._admin_api = admin_api
        self._users_data = []
        self._active_workers = []
        self._create_ui()

    def load_data(self):
        """Oeffentliche Methode zum Laden der Nutzerdaten."""
        self._load_users()

    # ----------------------------------------------------------------
    # UI
    # ----------------------------------------------------------------

    def _create_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)

        # Toolbar
        toolbar = QHBoxLayout()

        title = QLabel(texts.ADMIN_USERS_TITLE)
        title.setFont(QFont(FONT_HEADLINE, 18))
        title.setStyleSheet(f"color: {PRIMARY_900};")
        toolbar.addWidget(title)
        toolbar.addStretch()

        self._btn_new_user = QPushButton(f"+ {texts.ADMIN_USERS_NEW}")
        self._btn_new_user.setStyleSheet(f"""
            QPushButton {{
                background-color: {ACCENT_500};
                color: white;
                border: none;
                border-radius: {RADIUS_MD};
                padding: 8px 20px;
                font-weight: bold;
                font-family: {FONT_BODY};
            }}
            QPushButton:hover {{ background-color: #e88a2d; }}
        """)
        self._btn_new_user.clicked.connect(self._on_new_user)
        toolbar.addWidget(self._btn_new_user)

        refresh_btn = QPushButton("↻")
        refresh_btn.setFixedSize(36, 36)
        refresh_btn.setStyleSheet(f"border: 1px solid {PRIMARY_500}; border-radius: {RADIUS_MD}; color: {PRIMARY_500};")
        refresh_btn.clicked.connect(self._load_users)
        toolbar.addWidget(refresh_btn)

        layout.addLayout(toolbar)

        # Tabelle
        self._users_table = QTableWidget()
        self._users_table.setColumnCount(7)
        self._users_table.setHorizontalHeaderLabels([
            texts.ADMIN_COL_USERNAME, texts.ADMIN_COL_EMAIL, texts.ADMIN_COL_TYPE,
            texts.ADMIN_COL_STATUS, texts.ADMIN_COL_PERMISSIONS,
            texts.ADMIN_COL_LAST_ACTIVITY, texts.ADMIN_COL_CREATED
        ])
        self._users_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._users_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._users_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._users_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._users_table.setAlternatingRowColors(True)
        self._users_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._users_table.verticalHeader().setVisible(False)
        layout.addWidget(self._users_table)

        # Action-Buttons
        action_bar = QHBoxLayout()
        action_bar.addStretch()

        self._btn_edit_user = QPushButton(texts.EDIT)
        self._btn_edit_user.clicked.connect(self._on_edit_user)
        action_bar.addWidget(self._btn_edit_user)

        self._btn_change_pw = QPushButton(texts.ADMIN_USERS_CHANGE_PW)
        self._btn_change_pw.clicked.connect(self._on_change_password)
        action_bar.addWidget(self._btn_change_pw)

        self._btn_lock_user = QPushButton(texts.ADMIN_USERS_LOCK)
        self._btn_lock_user.setStyleSheet("color: #f39c12;")
        self._btn_lock_user.clicked.connect(self._on_lock_user)
        action_bar.addWidget(self._btn_lock_user)

        self._btn_delete_user = QPushButton(texts.ADMIN_USERS_DELETE)
        self._btn_delete_user.setStyleSheet("color: #e74c3c;")
        self._btn_delete_user.clicked.connect(self._on_delete_user)
        action_bar.addWidget(self._btn_delete_user)

        layout.addLayout(action_bar)

    # ----------------------------------------------------------------
    # Data loading
    # ----------------------------------------------------------------

    def _load_users(self):
        """Laedt alle Nutzer."""
        worker = LoadUsersWorker(self._admin_api)
        worker.finished.connect(self._on_users_loaded)
        worker.error.connect(lambda e: self._toast_manager.show_error(texts.ADMIN_USERS_LOAD_ERROR.format(error=e)) if hasattr(self, '_toast_manager') else None)
        worker.finished.connect(lambda: self._active_workers.remove(worker) if worker in self._active_workers else None)
        worker.error.connect(lambda: self._active_workers.remove(worker) if worker in self._active_workers else None)
        self._active_workers.append(worker)
        worker.start()

    def _on_users_loaded(self, users: list):
        """Callback wenn Nutzer geladen wurden."""
        self._users_data = users
        self._users_table.setRowCount(len(users))

        for row, user in enumerate(users):
            # Username
            self._users_table.setItem(row, 0, QTableWidgetItem(user.get('username', '')))

            # E-Mail
            self._users_table.setItem(row, 1, QTableWidgetItem(user.get('email', '')))

            # Kontotyp
            type_text = texts.ADMIN_TYPE_ADMIN if user.get('account_type') == 'admin' else texts.ADMIN_TYPE_USER
            type_item = QTableWidgetItem(type_text)
            if user.get('account_type') == 'admin':
                type_item.setForeground(QColor(ACCENT_500))
            self._users_table.setItem(row, 2, type_item)

            # Status
            if not user.get('is_active', True):
                status = texts.ADMIN_STATUS_INACTIVE
                color = '#e74c3c'
            elif user.get('is_locked', False):
                status = texts.ADMIN_STATUS_LOCKED
                color = '#f39c12'
            else:
                status = texts.ADMIN_STATUS_ACTIVE
                color = '#27ae60'
            status_item = QTableWidgetItem(status)
            status_item.setForeground(QColor(color))
            self._users_table.setItem(row, 3, status_item)

            # Permissions
            perms = user.get('permissions', [])
            perm_names = [texts.PERMISSION_NAMES.get(p, p) for p in perms]
            perm_text = ', '.join(perm_names) if perm_names else '-'
            if user.get('account_type') == 'admin':
                perm_text = texts.ADMIN_DIALOG_PERMISSIONS_HINT
            self._users_table.setItem(row, 4, QTableWidgetItem(perm_text))

            # Letzte Aktivitaet
            last_activity = user.get('last_activity') or user.get('last_login_at') or '-'
            if last_activity and last_activity != '-':
                last_activity = last_activity[:16].replace('T', ' ')
            self._users_table.setItem(row, 5, QTableWidgetItem(str(last_activity)))

            # Erstellt am
            created = user.get('created_at', '-')
            if created and created != '-':
                created = created[:10]
            self._users_table.setItem(row, 6, QTableWidgetItem(str(created)))

    # ----------------------------------------------------------------
    # Actions
    # ----------------------------------------------------------------

    def _get_selected_user(self) -> Optional[Dict]:
        """Gibt den ausgewaehlten User zurueck."""
        row = self._users_table.currentRow()
        if row < 0 or row >= len(self._users_data):
            return None
        return self._users_data[row]

    def _can_manage_provision(self) -> bool:
        user = self._auth_api.current_user
        return bool(user and user.has_permission('provision_manage'))

    def _on_new_user(self):
        dialog = UserEditDialog(self, is_new=True,
                                can_manage_provision=self._can_manage_provision())
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            try:
                self._admin_api.create_user(
                    username=data['username'],
                    password=data['password'],
                    email=data['email'],
                    account_type=data['account_type'],
                    permissions=data['permissions']
                )
                self._toast_manager.show_success(texts.ADMIN_USERS_CREATED.format(username=data['username']))
                self._load_users()
            except APIError as e:
                self._toast_manager.show_error(str(e))

    def _on_edit_user(self):
        user = self._get_selected_user()
        if not user:
            return
        dialog = UserEditDialog(self, user_data=user, is_new=False,
                                can_manage_provision=self._can_manage_provision())
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            username = user['username']
            worker = AdminWriteWorker(
                self._admin_api.update_user,
                user_id=user['id'],
                email=data['email'],
                account_type=data['account_type'],
                permissions=data['permissions']
            )
            worker.finished.connect(lambda _: (
                self._toast_manager.show_success(texts.ADMIN_USERS_UPDATED.format(username=username)),
                self._load_users()
            ))
            worker.error.connect(lambda e: self._toast_manager.show_error(str(e)))
            worker.finished.connect(lambda: self._active_workers.remove(worker) if worker in self._active_workers else None)
            worker.error.connect(lambda: self._active_workers.remove(worker) if worker in self._active_workers else None)
            self._active_workers.append(worker)
            worker.start()

    def _on_change_password(self):
        user = self._get_selected_user()
        if not user:
            return
        dialog = ChangePasswordDialog(self, username=user['username'])
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                self._admin_api.change_password(user['id'], dialog.get_password())
                self._toast_manager.show_success(texts.ADMIN_USERS_PW_SUCCESS)
                self._load_users()
            except APIError as e:
                self._toast_manager.show_error(str(e))

    def _on_lock_user(self):
        user = self._get_selected_user()
        if not user:
            return

        current_user = self._auth_api.current_user
        if current_user and user['id'] == current_user.id:
            self._toast_manager.show_warning(texts.ADMIN_USERS_SELF_LOCK)
            return

        if user.get('is_locked'):
            # Entsperren
            try:
                self._admin_api.unlock_user(user['id'])
                self._toast_manager.show_success(texts.ADMIN_USERS_UNLOCKED.format(username=user['username']))
                self._load_users()
            except APIError as e:
                self._toast_manager.show_error(str(e))
        else:
            # Sperren
            reply = QMessageBox.question(
                self, texts.WARNING, texts.ADMIN_USERS_LOCK_CONFIRM.format(username=user['username']),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                try:
                    self._admin_api.lock_user(user['id'])
                    self._toast_manager.show_success(texts.ADMIN_USERS_LOCKED.format(username=user['username']))
                    self._load_users()
                except APIError as e:
                    self._toast_manager.show_error(str(e))

    def _on_delete_user(self):
        user = self._get_selected_user()
        if not user:
            return

        current_user = self._auth_api.current_user
        if current_user and user['id'] == current_user.id:
            self._toast_manager.show_warning(texts.ADMIN_USERS_SELF_DELETE)
            return

        reply = QMessageBox.question(
            self, texts.WARNING, texts.ADMIN_USERS_DELETE_CONFIRM.format(username=user['username']),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self._admin_api.delete_user(user['id'])
                self._toast_manager.show_success(texts.ADMIN_USERS_DELETED.format(username=user['username']))
                self._load_users()
            except APIError as e:
                self._toast_manager.show_error(str(e))
