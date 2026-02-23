"""
ACENCIA ATLAS - Admin Dialog-Klassen

7 Dialog-Klassen fuer Admin-Operationen.
Extrahiert aus admin_view.py (Schritt 4 Refactoring).
"""

from typing import Dict, Set

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit, QComboBox,
    QCheckBox, QGroupBox, QPushButton, QLabel, QTextEdit, QFileDialog,
    QSpinBox,
)
from PySide6.QtCore import Qt

from i18n import de as texts
from ui.styles.tokens import (
    PRIMARY_900, PRIMARY_500, PRIMARY_100, PRIMARY_0,
    ACCENT_500,
    FONT_BODY, FONT_SIZE_CAPTION, FONT_SIZE_BODY,
    RADIUS_MD,
    get_button_primary_style, get_button_secondary_style,
)


class ReleaseUploadDialog(QDialog):
    """Dialog zum Hochladen eines neuen Releases."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(texts.RELEASES_UPLOAD_TITLE)
        self.setMinimumWidth(500)
        self._file_path = ''
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        
        form = QFormLayout()
        form.setSpacing(8)
        
        # Datei-Auswahl
        file_layout = QHBoxLayout()
        self._file_label = QLabel(texts.RELEASES_SELECT_FILE)
        self._file_label.setStyleSheet(f"color: {PRIMARY_500};")
        file_layout.addWidget(self._file_label, 1)
        
        browse_btn = QPushButton("...")
        browse_btn.setFixedWidth(40)
        browse_btn.clicked.connect(self._browse_file)
        file_layout.addWidget(browse_btn)
        form.addRow("Datei:", file_layout)
        
        # Version
        self.version_edit = QLineEdit()
        self.version_edit.setPlaceholderText("z.B. 1.0.0")
        form.addRow(texts.RELEASES_VERSION + ":", self.version_edit)
        
        # Channel
        self.channel_combo = QComboBox()
        self.channel_combo.addItem(texts.RELEASES_CHANNEL_STABLE, 'stable')
        self.channel_combo.addItem(texts.RELEASES_CHANNEL_BETA, 'beta')
        self.channel_combo.addItem(texts.RELEASES_CHANNEL_INTERNAL, 'internal')
        form.addRow(texts.RELEASES_CHANNEL + ":", self.channel_combo)
        
        # Min-Version (optional)
        self.min_version_edit = QLineEdit()
        self.min_version_edit.setPlaceholderText("z.B. 0.8.0 (optional)")
        form.addRow(texts.RELEASES_MIN_VERSION + ":", self.min_version_edit)
        
        layout.addLayout(form)
        
        # Release Notes
        notes_label = QLabel(texts.RELEASES_NOTES + ":")
        layout.addWidget(notes_label)
        
        self.notes_edit = QTextEdit()
        self.notes_edit.setPlaceholderText("Aenderungen in dieser Version...")
        self.notes_edit.setMaximumHeight(150)
        layout.addWidget(self.notes_edit)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        cancel_btn = QPushButton(texts.CANCEL)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        upload_btn = QPushButton(texts.RELEASES_NEW)
        upload_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ACCENT_500};
                color: white;
                border: none;
                border-radius: {RADIUS_MD};
                padding: 8px 24px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background-color: #e88a2d; }}
        """)
        upload_btn.clicked.connect(self._on_upload)
        btn_layout.addWidget(upload_btn)
        
        layout.addLayout(btn_layout)
    
    def _browse_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, texts.RELEASES_SELECT_FILE, "",
            "Installer (*.exe *.msi);;Alle Dateien (*)"
        )
        if path:
            self._file_path = path
            self._file_label.setText(path.split('/')[-1].split('\\')[-1])
            self._file_label.setStyleSheet(f"color: {PRIMARY_900};")
    
    def _on_upload(self):
        if not self._file_path:
            if hasattr(self.parent(), '_toast_manager'):
                self.parent()._toast_manager.show_warning(texts.RELEASES_SELECT_FILE)
            return
        version = self.version_edit.text().strip()
        if not version:
            if hasattr(self.parent(), '_toast_manager'):
                self.parent()._toast_manager.show_warning(texts.RELEASES_VERSION + " erforderlich")
            return
        import re
        if not re.match(r'^\d+\.\d+\.\d+(-[a-zA-Z0-9.]+)?$', version):
            if hasattr(self.parent(), '_toast_manager'):
                self.parent()._toast_manager.show_warning("Version muss dem Format X.Y.Z entsprechen")
            return
        self.accept()
    
    def get_data(self) -> dict:
        return {
            'file_path': self._file_path,
            'version': self.version_edit.text().strip(),
            'channel': self.channel_combo.currentData(),
            'release_notes': self.notes_edit.toPlainText(),
            'min_version': self.min_version_edit.text().strip(),
        }


class ReleaseEditDialog(QDialog):
    """Dialog zum Bearbeiten eines bestehenden Releases."""
    
    # Status-Mapping
    STATUS_OPTIONS = [
        ('active', texts.RELEASES_STATUS_ACTIVE),
        ('mandatory', texts.RELEASES_STATUS_MANDATORY),
        ('deprecated', texts.RELEASES_STATUS_DEPRECATED),
        ('withdrawn', texts.RELEASES_STATUS_WITHDRAWN),
    ]
    
    CHANNEL_OPTIONS = [
        ('stable', texts.RELEASES_CHANNEL_STABLE),
        ('beta', texts.RELEASES_CHANNEL_BETA),
        ('internal', texts.RELEASES_CHANNEL_INTERNAL),
    ]
    
    def __init__(self, release_data: dict, parent=None):
        super().__init__(parent)
        self._data = release_data
        self.setWindowTitle(texts.RELEASES_EDIT_TITLE + f" - v{release_data.get('version', '')}")
        self.setMinimumWidth(500)
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        
        form = QFormLayout()
        form.setSpacing(8)
        
        # Version (readonly)
        version_label = QLabel(self._data.get('version', ''))
        version_label.setStyleSheet(f"font-weight: bold; color: {PRIMARY_900};")
        form.addRow(texts.RELEASES_VERSION + ":", version_label)
        
        # SHA256 (readonly, abgekuerzt)
        sha = self._data.get('sha256', '')
        sha_label = QLabel(sha[:16] + '...' if len(sha) > 16 else sha)
        sha_label.setStyleSheet(f"color: {PRIMARY_500}; font-size: {FONT_SIZE_CAPTION};")
        form.addRow(texts.RELEASES_SHA256 + ":", sha_label)
        
        # Status
        self.status_combo = QComboBox()
        for value, label in self.STATUS_OPTIONS:
            self.status_combo.addItem(label, value)
        current_status = self._data.get('status', 'active')
        idx = self.status_combo.findData(current_status)
        if idx >= 0:
            self.status_combo.setCurrentIndex(idx)
        form.addRow(texts.RELEASES_STATUS + ":", self.status_combo)
        
        # Channel
        self.channel_combo = QComboBox()
        for value, label in self.CHANNEL_OPTIONS:
            self.channel_combo.addItem(label, value)
        current_channel = self._data.get('channel', 'stable')
        idx = self.channel_combo.findData(current_channel)
        if idx >= 0:
            self.channel_combo.setCurrentIndex(idx)
        form.addRow(texts.RELEASES_CHANNEL + ":", self.channel_combo)
        
        # Min-Version
        self.min_version_edit = QLineEdit(self._data.get('min_version', '') or '')
        self.min_version_edit.setPlaceholderText("z.B. 0.8.0 (optional)")
        form.addRow(texts.RELEASES_MIN_VERSION + ":", self.min_version_edit)
        
        layout.addLayout(form)
        
        # Release Notes
        notes_label = QLabel(texts.RELEASES_NOTES + ":")
        layout.addWidget(notes_label)
        
        self.notes_edit = QTextEdit()
        self.notes_edit.setPlainText(self._data.get('release_notes', '') or '')
        self.notes_edit.setMaximumHeight(150)
        layout.addWidget(self.notes_edit)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        cancel_btn = QPushButton(texts.CANCEL)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        save_btn = QPushButton(texts.SAVE)
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ACCENT_500};
                color: white;
                border: none;
                border-radius: {RADIUS_MD};
                padding: 8px 24px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background-color: #e88a2d; }}
        """)
        save_btn.clicked.connect(self.accept)
        btn_layout.addWidget(save_btn)
        
        layout.addLayout(btn_layout)
    
    def get_changes(self) -> dict:
        """Gibt nur die geaenderten Felder zurueck."""
        changes = {}
        new_status = self.status_combo.currentData()
        if new_status != self._data.get('status'):
            changes['status'] = new_status
        new_channel = self.channel_combo.currentData()
        if new_channel != self._data.get('channel'):
            changes['channel'] = new_channel
        new_notes = self.notes_edit.toPlainText()
        if new_notes != (self._data.get('release_notes', '') or ''):
            changes['release_notes'] = new_notes
        new_min = self.min_version_edit.text().strip()
        old_min = self._data.get('min_version', '') or ''
        if new_min != old_min:
            changes['min_version'] = new_min if new_min else None
        return changes


class UserEditDialog(QDialog):
    """Dialog zum Erstellen/Bearbeiten eines Nutzers."""

    PROVISION_PERM_KEYS: Set[str] = {'provision_access', 'provision_manage'}

    def __init__(self, parent=None, user_data: Dict = None, is_new: bool = True,
                 can_manage_provision: bool = False):
        super().__init__(parent)
        self._user_data = user_data or {}
        self._is_new = is_new
        self._can_manage_provision = can_manage_provision
        self.setWindowTitle(texts.ADMIN_USERS_NEW if is_new else texts.ADMIN_USERS_EDIT)
        self.setMinimumWidth(450)
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        
        form = QFormLayout()
        form.setSpacing(8)
        
        # Benutzername
        self.username_edit = QLineEdit(self._user_data.get('username', ''))
        self.username_edit.setPlaceholderText(texts.ADMIN_DIALOG_USERNAME)
        if not self._is_new:
            self.username_edit.setReadOnly(True)
            self.username_edit.setStyleSheet("background-color: #f0f0f0;")
        form.addRow(texts.ADMIN_DIALOG_USERNAME + ":", self.username_edit)
        
        # E-Mail
        self.email_edit = QLineEdit(self._user_data.get('email', ''))
        self.email_edit.setPlaceholderText(texts.ADMIN_DIALOG_EMAIL)
        form.addRow(texts.ADMIN_DIALOG_EMAIL + ":", self.email_edit)
        
        # Passwort (nur bei Neuanlage)
        if self._is_new:
            self.password_edit = QLineEdit()
            self.password_edit.setPlaceholderText(texts.ADMIN_DIALOG_PASSWORD)
            self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
            form.addRow(texts.ADMIN_DIALOG_PASSWORD + ":", self.password_edit)
        
        # Kontotyp
        self.type_combo = QComboBox()
        self.type_combo.addItem(texts.ADMIN_TYPE_USER, 'user')
        self.type_combo.addItem(texts.ADMIN_TYPE_ADMIN, 'admin')
        current_type = self._user_data.get('account_type', 'user')
        idx = self.type_combo.findData(current_type)
        if idx >= 0:
            self.type_combo.setCurrentIndex(idx)
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)
        form.addRow(texts.ADMIN_DIALOG_TYPE + ":", self.type_combo)
        
        layout.addLayout(form)
        
        # Berechtigungen
        perm_group = QGroupBox(texts.ADMIN_DIALOG_PERMISSIONS)
        perm_layout = QVBoxLayout(perm_group)
        perm_layout.setSpacing(4)
        
        self._perm_hint = QLabel(texts.ADMIN_DIALOG_PERMISSIONS_HINT)
        self._perm_hint.setStyleSheet(f"color: {PRIMARY_500}; font-size: {FONT_SIZE_CAPTION};")
        self._perm_hint.setVisible(current_type == 'admin')
        perm_layout.addWidget(self._perm_hint)
        
        current_perms = self._user_data.get('permissions', [])
        self._perm_checkboxes = {}
        for perm_key, perm_name in texts.PERMISSION_NAMES.items():
            is_provision_perm = perm_key in self.PROVISION_PERM_KEYS
            if is_provision_perm and not self._can_manage_provision:
                continue
            cb = QCheckBox(perm_name)
            cb.setChecked(perm_key in current_perms)
            if is_provision_perm:
                cb.setEnabled(True)
            else:
                cb.setEnabled(current_type != 'admin')
            self._perm_checkboxes[perm_key] = cb
            perm_layout.addWidget(cb)
        
        layout.addWidget(perm_group)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        cancel_btn = QPushButton(texts.CANCEL)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        save_btn = QPushButton(texts.SAVE)
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ACCENT_500};
                color: white;
                border: none;
                border-radius: {RADIUS_MD};
                padding: 8px 24px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background-color: #e88a2d; }}
        """)
        save_btn.clicked.connect(self._on_save)
        btn_layout.addWidget(save_btn)
        
        layout.addLayout(btn_layout)
    
    def _on_type_changed(self, index: int):
        is_admin = self.type_combo.currentData() == 'admin'
        self._perm_hint.setVisible(is_admin)
        for perm_key, cb in self._perm_checkboxes.items():
            if perm_key in self.PROVISION_PERM_KEYS:
                cb.setEnabled(True)
            else:
                cb.setEnabled(not is_admin)
    
    def _on_save(self):
        if self._is_new:
            username = self.username_edit.text().strip()
            if len(username) < 3:
                if hasattr(self.parent(), '_toast_manager'):
                    self.parent()._toast_manager.show_warning(texts.ADMIN_USERS_NAME_TOO_SHORT)
                return
            password = self.password_edit.text()
            if len(password) < 8:
                if hasattr(self.parent(), '_toast_manager'):
                    self.parent()._toast_manager.show_warning(texts.ADMIN_USERS_PW_TOO_SHORT)
                return
        self.accept()
    
    def get_data(self) -> Dict:
        """Gibt die eingegebenen Daten zurueck."""
        data = {
            'email': self.email_edit.text().strip(),
            'account_type': self.type_combo.currentData(),
            'permissions': [k for k, cb in self._perm_checkboxes.items() if cb.isChecked()]
        }
        if self._is_new:
            data['username'] = self.username_edit.text().strip()
            data['password'] = self.password_edit.text()
        return data


class ChangePasswordDialog(QDialog):
    """Dialog zum Aendern eines Passworts."""
    
    def __init__(self, parent=None, username: str = ''):
        super().__init__(parent)
        self.setWindowTitle(texts.ADMIN_USERS_CHANGE_PW_TITLE.format(username=username))
        self.setMinimumWidth(350)
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        form = QFormLayout()
        self.pw_edit = QLineEdit()
        self.pw_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.pw_edit.setPlaceholderText(texts.ADMIN_USERS_PW_NEW)
        form.addRow(texts.ADMIN_USERS_PW_NEW + ":", self.pw_edit)
        
        self.pw_confirm = QLineEdit()
        self.pw_confirm.setEchoMode(QLineEdit.EchoMode.Password)
        self.pw_confirm.setPlaceholderText(texts.ADMIN_USERS_PW_CONFIRM)
        form.addRow(texts.ADMIN_USERS_PW_CONFIRM + ":", self.pw_confirm)
        layout.addLayout(form)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = QPushButton(texts.CANCEL)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        save_btn = QPushButton(texts.SAVE)
        save_btn.setStyleSheet(f"background-color: {ACCENT_500}; color: white; border: none; border-radius: {RADIUS_MD}; padding: 8px 24px; font-weight: bold;")
        save_btn.clicked.connect(self._on_save)
        btn_layout.addWidget(save_btn)
        layout.addLayout(btn_layout)
    
    def _on_save(self):
        if self.pw_edit.text() != self.pw_confirm.text():
            if hasattr(self.parent(), '_toast_manager'):
                self.parent()._toast_manager.show_warning(texts.ADMIN_USERS_PW_MISMATCH)
            return
        if len(self.pw_edit.text()) < 8:
            if hasattr(self.parent(), '_toast_manager'):
                self.parent()._toast_manager.show_warning(texts.ADMIN_USERS_PW_TOO_SHORT)
            return
        self.accept()
    
    def get_password(self) -> str:
        return self.pw_edit.text()


class EmailAccountDialog(QDialog):
    """Dialog zum Hinzufuegen/Bearbeiten von E-Mail-Konten."""
    
    def __init__(self, parent=None, existing_data: Dict = None):
        super().__init__(parent)
        self._existing = existing_data
        self._is_edit = existing_data is not None
        
        self.setWindowTitle(
            texts.EMAIL_ACCOUNT_DIALOG_TITLE_EDIT if self._is_edit
            else texts.EMAIL_ACCOUNT_DIALOG_TITLE_ADD
        )
        self.setMinimumWidth(500)
        self.setModal(True)
        
        layout = QFormLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Name
        self._name = QLineEdit()
        self._name.setPlaceholderText("z.B. SCS SmartScan Versand")
        layout.addRow(texts.EMAIL_ACCOUNT_NAME, self._name)
        
        # Typ
        self._type = QComboBox()
        self._type.addItem(texts.EMAIL_ACCOUNT_TYPE_SMTP, "smtp")
        self._type.addItem(texts.EMAIL_ACCOUNT_TYPE_IMAP, "imap")
        self._type.addItem(texts.EMAIL_ACCOUNT_TYPE_BOTH, "both")
        self._type.currentIndexChanged.connect(self._on_type_changed)
        layout.addRow(texts.EMAIL_ACCOUNT_TYPE, self._type)
        
        # SMTP
        self._smtp_host = QLineEdit()
        self._smtp_host.setPlaceholderText("smtp.web.de")
        layout.addRow(texts.EMAIL_ACCOUNT_SMTP_HOST, self._smtp_host)
        
        self._smtp_port = QSpinBox()
        self._smtp_port.setRange(1, 65535)
        self._smtp_port.setValue(587)
        layout.addRow(texts.EMAIL_ACCOUNT_SMTP_PORT, self._smtp_port)
        
        self._smtp_enc = QComboBox()
        self._smtp_enc.addItem(texts.EMAIL_ACCOUNT_ENCRYPTION_TLS, "tls")
        self._smtp_enc.addItem(texts.EMAIL_ACCOUNT_ENCRYPTION_SSL, "ssl")
        self._smtp_enc.addItem(texts.EMAIL_ACCOUNT_ENCRYPTION_NONE, "none")
        layout.addRow(texts.EMAIL_ACCOUNT_ENCRYPTION + " (SMTP)", self._smtp_enc)
        
        # IMAP
        self._imap_host = QLineEdit()
        self._imap_host.setPlaceholderText("imap.web.de")
        layout.addRow(texts.EMAIL_ACCOUNT_IMAP_HOST, self._imap_host)
        
        self._imap_port = QSpinBox()
        self._imap_port.setRange(1, 65535)
        self._imap_port.setValue(993)
        layout.addRow(texts.EMAIL_ACCOUNT_IMAP_PORT, self._imap_port)
        
        self._imap_enc = QComboBox()
        self._imap_enc.addItem(texts.EMAIL_ACCOUNT_ENCRYPTION_SSL, "ssl")
        self._imap_enc.addItem(texts.EMAIL_ACCOUNT_ENCRYPTION_TLS, "tls")
        self._imap_enc.addItem(texts.EMAIL_ACCOUNT_ENCRYPTION_NONE, "none")
        layout.addRow(texts.EMAIL_ACCOUNT_ENCRYPTION + " (IMAP)", self._imap_enc)
        
        # Credentials
        self._username = QLineEdit()
        self._username.setPlaceholderText("user@web.de")
        layout.addRow(texts.EMAIL_ACCOUNT_USERNAME, self._username)
        
        self._password = QLineEdit()
        self._password.setEchoMode(QLineEdit.EchoMode.Password)
        self._password.setPlaceholderText("Leer lassen = unveraendert" if self._is_edit else "")
        layout.addRow(texts.EMAIL_ACCOUNT_PASSWORD, self._password)
        
        # From
        self._from_address = QLineEdit()
        self._from_address.setPlaceholderText("scan@example.com")
        layout.addRow(texts.EMAIL_ACCOUNT_FROM_ADDRESS, self._from_address)
        
        self._from_name = QLineEdit()
        self._from_name.setPlaceholderText("ACENCIA ATLAS")
        layout.addRow(texts.EMAIL_ACCOUNT_FROM_NAME, self._from_name)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        cancel_btn = QPushButton(texts.SMARTSCAN_SEND_CANCEL)
        cancel_btn.setStyleSheet(get_button_secondary_style())
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        save_btn = QPushButton("Speichern")
        save_btn.setStyleSheet(get_button_primary_style())
        save_btn.clicked.connect(self.accept)
        btn_layout.addWidget(save_btn)
        
        layout.addRow(btn_layout)
        
        # Bestehende Daten laden
        if self._existing:
            self._name.setText(self._existing.get('account_name', self._existing.get('name', '')))
            idx = self._type.findData(self._existing.get('account_type', 'smtp'))
            if idx >= 0:
                self._type.setCurrentIndex(idx)
            self._smtp_host.setText(self._existing.get('smtp_host', '') or '')
            self._smtp_port.setValue(int(self._existing.get('smtp_port', 587) or 587))
            enc_idx = self._smtp_enc.findData(self._existing.get('smtp_encryption', 'tls'))
            if enc_idx >= 0:
                self._smtp_enc.setCurrentIndex(enc_idx)
            self._imap_host.setText(self._existing.get('imap_host', '') or '')
            imap_port = int(self._existing.get('imap_port', 993) or 993)
            self._imap_port.setValue(imap_port)
            imap_enc = self._existing.get('imap_encryption', 'ssl') or 'ssl'
            if imap_port == 993:
                imap_enc = 'ssl'
            elif imap_port == 143:
                imap_enc = 'tls'
            ienc_idx = self._imap_enc.findData(imap_enc)
            if ienc_idx >= 0:
                self._imap_enc.setCurrentIndex(ienc_idx)
            self._username.setText(self._existing.get('username', '') or '')
            self._from_address.setText(self._existing.get('from_address', '') or '')
            self._from_name.setText(self._existing.get('from_name', '') or '')
        
        self._on_type_changed()
    
    def _on_type_changed(self):
        """Zeigt/versteckt SMTP/IMAP-Felder basierend auf Typ."""
        acc_type = self._type.currentData()
        show_smtp = acc_type in ('smtp', 'both')
        show_imap = acc_type in ('imap', 'both')
        self._smtp_host.setEnabled(show_smtp)
        self._smtp_port.setEnabled(show_smtp)
        self._smtp_enc.setEnabled(show_smtp)
        self._imap_host.setEnabled(show_imap)
        self._imap_port.setEnabled(show_imap)
        self._imap_enc.setEnabled(show_imap)
    
    def get_data(self) -> Dict:
        """Gibt die eingegebenen Daten zurueck."""
        email_address = self._username.text().strip()
        data = {
            'account_name': self._name.text().strip(),
            'email_address': email_address,
            'account_type': self._type.currentData(),
            'smtp_host': self._smtp_host.text().strip(),
            'smtp_port': self._smtp_port.value(),
            'smtp_encryption': self._smtp_enc.currentData(),
            'imap_host': self._imap_host.text().strip(),
            'imap_port': self._imap_port.value(),
            'imap_encryption': self._imap_enc.currentData(),
            'username': email_address,
            'from_address': self._from_address.text().strip() or email_address,
            'from_name': self._from_name.text().strip(),
        }
        pw = self._password.text()
        if pw:
            data['password'] = pw
        return data


class PasswordDialog(QDialog):
    """Dialog zum Hinzufuegen/Bearbeiten von Passwoertern."""
    
    def __init__(self, parent=None, existing_data: Dict = None):
        super().__init__(parent)
        self._existing = existing_data
        self._is_edit = existing_data is not None
        
        self.setWindowTitle(
            texts.PASSWORD_DIALOG_TITLE_EDIT if self._is_edit
            else texts.PASSWORD_DIALOG_TITLE_ADD
        )
        self.setMinimumWidth(400)
        self.setModal(True)
        
        layout = QFormLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Typ-Auswahl (bei Edit nicht aenderbar)
        self._type_combo = QComboBox()
        self._type_combo.addItem(texts.PASSWORD_TYPE_PDF, "pdf")
        self._type_combo.addItem(texts.PASSWORD_TYPE_ZIP, "zip")
        self._type_combo.setStyleSheet(f"font-family: {FONT_BODY}; padding: 4px;")
        if self._is_edit:
            idx = 0 if existing_data.get('password_type') == 'pdf' else 1
            self._type_combo.setCurrentIndex(idx)
            self._type_combo.setEnabled(False)
        layout.addRow(texts.PASSWORD_TYPE + ":", self._type_combo)
        
        # Passwort-Wert
        self._value_input = QLineEdit()
        self._value_input.setStyleSheet(f"font-family: Consolas; padding: 4px;")
        self._value_input.setPlaceholderText("Passwort eingeben...")
        if self._is_edit:
            self._value_input.setText(existing_data.get('password_value', ''))
        layout.addRow(texts.PASSWORD_VALUE + ":", self._value_input)
        
        # Beschreibung
        self._desc_input = QLineEdit()
        self._desc_input.setStyleSheet(f"font-family: {FONT_BODY}; padding: 4px;")
        self._desc_input.setPlaceholderText("Optionale Beschreibung...")
        if self._is_edit:
            self._desc_input.setText(existing_data.get('description') or '')
        layout.addRow(texts.PASSWORD_DESCRIPTION + ":", self._desc_input)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        cancel_btn = QPushButton(texts.CANCEL if hasattr(texts, 'CANCEL') else "Abbrechen")
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                padding: 8px 20px;
                font-family: {FONT_BODY};
                background-color: {PRIMARY_100};
                color: {PRIMARY_900};
                border: none;
                border-radius: {RADIUS_MD};
            }}
            QPushButton:hover {{ background-color: {PRIMARY_500}; color: white; }}
        """)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        save_btn = QPushButton(texts.PASSWORD_EDIT if self._is_edit else texts.PASSWORD_ADD)
        save_btn.setStyleSheet(f"""
            QPushButton {{
                padding: 8px 20px;
                font-family: {FONT_BODY};
                background-color: {ACCENT_500};
                color: white;
                border: none;
                border-radius: {RADIUS_MD};
                font-weight: bold;
            }}
            QPushButton:hover {{ background-color: #e88a2d; }}
        """)
        save_btn.clicked.connect(self._on_save)
        btn_layout.addWidget(save_btn)
        
        layout.addRow(btn_layout)
    
    def _on_save(self):
        """Validiert und akzeptiert den Dialog."""
        value = self._value_input.text().strip()
        if not value:
            if hasattr(self.parent(), '_toast_manager'):
                self.parent()._toast_manager.show_warning(texts.PASSWORD_ERROR_EMPTY)
            return
        self.accept()
    
    def get_data(self) -> Dict:
        """Gibt die eingegebenen Daten zurueck."""
        return {
            'password_type': self._type_combo.currentData(),
            'password_value': self._value_input.text().strip(),
            'description': self._desc_input.text().strip()
        }
