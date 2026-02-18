"""
ACENCIA ATLAS - Administrations-Ansicht

Vollbild-Layout mit eigener Sidebar-Navigation (14 Bereiche):

VERWALTUNG:
1. Nutzerverwaltung (CRUD)
2. Sessions (Einsicht + Kill)
3. Passwoerter (PDF/ZIP Passwort-Verwaltung)

MONITORING:
4. Aktivitaetslog (Filter + Pagination)
5. KI-Kosten (Verarbeitungshistorie + Kosten-Statistiken + Request-Details)
6. Releases (Auto-Update Verwaltung)

VERARBEITUNG:
7. KI-Klassifikation (Prompts, Modelle, Pipeline-Visualisierung)
8. KI-Provider (API-Key-Verwaltung OpenRouter/OpenAI)
9. Modell-Preise (Kostenberechnung pro Modell)

E-MAIL:
10. E-Mail-Konten (SMTP/IMAP Verwaltung)
11. Smart!Scan (Einstellungen)
12. Smart!Scan Historie
13. E-Mail Posteingang

KOMMUNIKATION:
14. Mitteilungen (System + Admin-Mitteilungen verwalten)
"""

from typing import Optional, List, Dict
import logging

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QComboBox, QCheckBox,
    QGroupBox, QMessageBox, QHeaderView, QAbstractItemView, QFrame, QDateEdit,
    QSizePolicy, QSpacerItem, QTextEdit, QPlainTextEdit, QFileDialog, QProgressBar,
    QSpinBox, QMenu, QRadioButton, QButtonGroup, QScrollArea, QStackedWidget
)
from PySide6.QtCore import Qt, QThread, Signal, QDate, QTimer
from PySide6.QtGui import QFont, QColor, QAction

from api.client import APIClient, APIError
from api.auth import AuthAPI
from api.admin import AdminAPI
from api.releases import ReleasesAPI
from api.passwords import PasswordsAPI
from api.processing_settings import ProcessingSettingsAPI
from api.ai_providers import AIProvidersAPI
from api.model_pricing import ModelPricingAPI
from i18n import de as texts

from ui.styles.tokens import (
    PRIMARY_900, PRIMARY_500, PRIMARY_100, PRIMARY_0,
    ACCENT_500, ACCENT_100, SUCCESS, TEXT_SECONDARY,
    SIDEBAR_BG, SIDEBAR_TEXT, SIDEBAR_HOVER, SIDEBAR_WIDTH_INT,
    FONT_HEADLINE, FONT_BODY,
    FONT_SIZE_H1, FONT_SIZE_H2, FONT_SIZE_BODY, FONT_SIZE_CAPTION,
    RADIUS_MD, RADIUS_SM,
    get_button_primary_style, get_button_secondary_style, get_button_ghost_style,
)

# Integer-Werte fuer Margins/Spacing (tokens.py hat nur Strings)
SPACING_SM = 8
SPACING_MD = 16
SPACING_LG = 24

logger = logging.getLogger(__name__)

# Farbkodierung fuer Status
STATUS_COLORS = {
    'success': '#27ae60',
    'error': '#e74c3c',
    'denied': '#f39c12',
}

CATEGORY_NAMES = {
    'auth': texts.ACTIVITY_CAT_AUTH,
    'document': texts.ACTIVITY_CAT_DOCUMENT,
    'bipro': texts.ACTIVITY_CAT_BIPRO,
    'vu_connection': texts.ACTIVITY_CAT_VU_CONNECTION,
    'gdv': texts.ACTIVITY_CAT_GDV,
    'admin': texts.ACTIVITY_CAT_ADMIN,
    'system': texts.ACTIVITY_CAT_SYSTEM,
    'ai': texts.ACTIVITY_CAT_AI,
}


# ================================================================
# Worker-Threads
# ================================================================

class AdminWriteWorker(QThread):
    """Fuehrt Admin-Schreiboperationen im Hintergrund aus."""
    finished = Signal(object)  # Ergebnis oder None
    error = Signal(str)
    
    def __init__(self, func, *args, **kwargs):
        super().__init__()
        self._func = func
        self._args = args
        self._kwargs = kwargs
    
    def run(self):
        try:
            result = self._func(*self._args, **self._kwargs)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class LoadUsersWorker(QThread):
    """Laedt Nutzer im Hintergrund."""
    finished = Signal(list)
    error = Signal(str)
    
    def __init__(self, admin_api: AdminAPI):
        super().__init__()
        self._admin_api = admin_api
    
    def run(self):
        try:
            users = self._admin_api.get_users()
            self.finished.emit(users)
        except Exception as e:
            self.error.emit(str(e))


class LoadSessionsWorker(QThread):
    """Laedt Sessions im Hintergrund."""
    finished = Signal(list)
    error = Signal(str)
    
    def __init__(self, admin_api: AdminAPI, user_id: int = None):
        super().__init__()
        self._admin_api = admin_api
        self._user_id = user_id
    
    def run(self):
        try:
            sessions = self._admin_api.get_sessions(self._user_id)
            self.finished.emit(sessions)
        except Exception as e:
            self.error.emit(str(e))


class LoadActivityWorker(QThread):
    """Laedt Aktivitaetslog im Hintergrund."""
    finished = Signal(dict)
    error = Signal(str)
    
    def __init__(self, admin_api: AdminAPI, filters: Dict):
        super().__init__()
        self._admin_api = admin_api
        self._filters = filters
    
    def run(self):
        try:
            result = self._admin_api.get_activity_log(**self._filters)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class LoadCostDataWorker(QThread):
    """Laedt Kosten-Historie und Statistiken im Hintergrund."""
    finished = Signal(dict)  # {'history': [...], 'stats': {...}}
    error = Signal(str)
    
    def __init__(self, api_client: APIClient, from_date: str = None, to_date: str = None):
        super().__init__()
        self._api_client = api_client
        self._from_date = from_date
        self._to_date = to_date
    
    def run(self):
        try:
            from api.processing_history import ProcessingHistoryAPI
            
            history_api = ProcessingHistoryAPI(self._api_client)
            
            # Kosten-Historie laden
            entries, total = history_api.get_cost_history(
                from_date=self._from_date,
                to_date=self._to_date,
                limit=500
            )
            
            # Kosten-Statistiken laden
            stats = history_api.get_cost_stats(
                from_date=self._from_date,
                to_date=self._to_date
            )
            
            self.finished.emit({
                'history': entries,
                'total': total,
                'stats': stats or {}
            })
        except Exception as e:
            self.error.emit(str(e))


class LoadReleasesWorker(QThread):
    """Laedt Releases im Hintergrund."""
    finished = Signal(list)
    error = Signal(str)
    
    def __init__(self, releases_api: ReleasesAPI):
        super().__init__()
        self._releases_api = releases_api
    
    def run(self):
        try:
            releases = self._releases_api.get_releases()
            self.finished.emit(releases)
        except Exception as e:
            self.error.emit(str(e))


class UploadReleaseWorker(QThread):
    """Laedt ein Release hoch."""
    finished = Signal(dict)
    error = Signal(str)
    
    def __init__(self, releases_api: ReleasesAPI, file_path: str, version: str,
                 channel: str, release_notes: str, min_version: str):
        super().__init__()
        self._releases_api = releases_api
        self._file_path = file_path
        self._version = version
        self._channel = channel
        self._release_notes = release_notes
        self._min_version = min_version
    
    def run(self):
        try:
            result = self._releases_api.create_release(
                file_path=self._file_path,
                version=self._version,
                channel=self._channel,
                release_notes=self._release_notes,
                min_version=self._min_version
            )
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class ImapPollWorker(QThread):
    """Ruft IMAP-Postfach im Hintergrund ab (verhindert UI-Freeze)."""
    finished = Signal(dict)
    error = Signal(str)
    
    def __init__(self, email_accounts_api, account_id: int):
        super().__init__()
        self._api = email_accounts_api
        self._account_id = account_id
    
    def run(self):
        try:
            result = self._api.poll_inbox(self._account_id)
            self.finished.emit(result if result else {})
        except Exception as e:
            self.error.emit(str(e))


# ================================================================
# Dialoge
# ================================================================

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
    
    def __init__(self, parent=None, user_data: Dict = None, is_new: bool = True):
        super().__init__(parent)
        self._user_data = user_data or {}
        self._is_new = is_new
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
            cb = QCheckBox(perm_name)
            cb.setChecked(perm_key in current_perms)
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
        for cb in self._perm_checkboxes.values():
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


# ================================================================
# Admin NavButton (Sidebar-Navigation)
# ================================================================

class AdminNavButton(QPushButton):
    """Navigations-Button fuer die Admin-Sidebar (ACENCIA CI-konform)."""
    
    def __init__(self, icon: str, text: str, parent=None):
        super().__init__(parent)
        self.setText(f"   {icon}  {text}")
        self.setCheckable(True)
        self.setMinimumHeight(40)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                border-left: 3px solid transparent;
                border-radius: 0px;
                padding: 8px 20px;
                text-align: left;
                font-family: {FONT_BODY};
                font-size: {FONT_SIZE_BODY};
                color: {PRIMARY_500};
            }}
            QPushButton:hover {{
                background-color: {SIDEBAR_HOVER};
                color: {SIDEBAR_TEXT};
            }}
            QPushButton:checked {{
                background-color: {SIDEBAR_HOVER};
                border-left: 3px solid {ACCENT_500};
                color: {SIDEBAR_TEXT};
                font-weight: 500;
            }}
        """)


# ================================================================
# Admin-View (Vollbild mit eigener Sidebar)
# ================================================================

class AdminView(QWidget):
    """
    Administrations-Ansicht mit eigener Sidebar-Navigation.
    Ersetzt die horizontalen Tabs durch eine vertikale Sidebar
    (gleicher Style wie die Haupt-App-Sidebar).
    
    10 Bereiche in 3 Sektionen:
    - VERWALTUNG: Nutzerverwaltung, Sessions, Passwoerter
    - MONITORING: Aktivitaetslog, KI-Kosten, Releases
    - E-MAIL: E-Mail-Konten, Smart!Scan, Smart!Scan Historie, E-Mail Posteingang
    """
    
    # Signal: Zurueck zur Hauptapp
    back_requested = Signal()
    
    def __init__(self, api_client: APIClient, auth_api: AuthAPI):
        super().__init__()
        self._api_client = api_client
        self._auth_api = auth_api
        self._admin_api = AdminAPI(api_client)
        self._releases_api = ReleasesAPI(api_client)
        
        # SmartScan APIs
        from api.smartscan import SmartScanAPI, EmailAccountsAPI as EmailAccAPI
        self._smartscan_api = SmartScanAPI(api_client)
        self._email_accounts_api = EmailAccAPI(api_client)
        
        # Processing Settings API
        self._processing_settings_api = ProcessingSettingsAPI(api_client)
        
        # KI-Provider + Modell-Preise APIs
        self._ai_providers_api = AIProvidersAPI(api_client)
        self._model_pricing_api = ModelPricingAPI(api_client)
        
        # Worker-Referenzen (fuer Cleanup)
        self._active_workers = []
        
        # Daten-Cache
        self._users_data: List[Dict] = []
        self._sessions_data: List[Dict] = []
        self._releases_data: List[Dict] = []
        
        # Aktivitaetslog State
        self._activity_page = 1
        self._activity_per_page = 50
        
        self._setup_ui()
        
        # Initial laden
        QTimer.singleShot(100, self._load_users)
    
    def _setup_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        
        # === Admin-Sidebar (gleicher Style wie Haupt-Sidebar) ===
        admin_sidebar = QFrame()
        admin_sidebar.setObjectName("admin_sidebar")
        admin_sidebar.setFixedWidth(SIDEBAR_WIDTH_INT)
        admin_sidebar.setStyleSheet(f"""
            QFrame#admin_sidebar {{
                background-color: {SIDEBAR_BG};
                border: none;
            }}
        """)
        
        sb_layout = QVBoxLayout(admin_sidebar)
        sb_layout.setContentsMargins(0, 8, 0, 20)
        sb_layout.setSpacing(2)
        
        # Zurueck-Button
        back_btn = QPushButton(texts.ADMIN_BACK_TO_APP)
        back_btn.setCursor(Qt.PointingHandCursor)
        back_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: 1px solid {PRIMARY_500};
                border-radius: {RADIUS_MD};
                padding: 8px 16px;
                margin: 0 16px 4px 16px;
                color: {PRIMARY_500};
                font-family: {FONT_BODY};
                font-size: {FONT_SIZE_BODY};
                text-align: center;
            }}
            QPushButton:hover {{
                background-color: {SIDEBAR_HOVER};
                border-color: {SIDEBAR_TEXT};
                color: {SIDEBAR_TEXT};
            }}
        """)
        back_btn.clicked.connect(self.back_requested.emit)
        sb_layout.addWidget(back_btn)
        
        # --- Alle NavButtons sammeln (fuer checked-State) ---
        self._nav_buttons: list[AdminNavButton] = []
        
        # Hilfsfunktion: Sektion mit orangener Trennlinie
        def add_section(label_text: str):
            # Trennlinie (Sekundaerfarbe 1 - Orange)
            line = QFrame()
            line.setFixedHeight(1)
            line.setStyleSheet(f"background-color: {ACCENT_500}; border: none; margin: 0;")
            sb_layout.addWidget(line)
            
            lbl = QLabel(label_text)
            lbl.setStyleSheet(f"""
                background-color: transparent;
                color: {PRIMARY_500};
                font-size: {FONT_SIZE_CAPTION};
                padding: 10px 20px 4px 20px;
                letter-spacing: 1px;
            """)
            sb_layout.addWidget(lbl)
        
        # Hilfsfunktion: NavButton erstellen + verbinden
        def add_nav(icon: str, text: str, index: int) -> AdminNavButton:
            btn = AdminNavButton(icon, text)
            btn.clicked.connect(lambda checked, i=index: self._navigate_to(i))
            sb_layout.addWidget(btn)
            self._nav_buttons.append(btn)
            return btn
        
        # Trennlinie oben (nach Zurueck-Button)
        top_line = QFrame()
        top_line.setFixedHeight(1)
        top_line.setStyleSheet(f"background-color: {ACCENT_500}; border: none; margin: 0;")
        sb_layout.addWidget(top_line)
        
        # === VERWALTUNG ===
        lbl_verwaltung = QLabel(texts.ADMIN_SECTION_MANAGEMENT)
        lbl_verwaltung.setStyleSheet(f"""
            background-color: transparent;
            color: {PRIMARY_500};
            font-size: {FONT_SIZE_CAPTION};
            padding: 8px 20px 4px 20px;
            letter-spacing: 1px;
        """)
        sb_layout.addWidget(lbl_verwaltung)
        self._btn_users     = add_nav("›", texts.ADMIN_TAB_USERS, 0)
        self._btn_sessions  = add_nav("›", texts.ADMIN_TAB_SESSIONS, 1)
        self._btn_passwords = add_nav("›", texts.ADMIN_TAB_PASSWORDS, 2)
        
        # === MONITORING ===
        add_section(texts.ADMIN_SECTION_MONITORING)
        self._btn_activity = add_nav("›", texts.ADMIN_TAB_ACTIVITY, 3)
        self._btn_costs    = add_nav("›", texts.ADMIN_TAB_COSTS, 4)
        self._btn_releases = add_nav("›", texts.ADMIN_TAB_RELEASES, 5)
        
        # === VERARBEITUNG ===
        add_section(texts.ADMIN_SECTION_PROCESSING)
        self._btn_ai_classification = add_nav("›", texts.ADMIN_TAB_AI_CLASSIFICATION, 6)
        self._btn_ai_providers      = add_nav("›", texts.ADMIN_TAB_AI_PROVIDERS, 7)
        self._btn_model_pricing     = add_nav("›", texts.ADMIN_TAB_MODEL_PRICING, 8)
        self._btn_document_rules    = add_nav("›", texts.ADMIN_TAB_DOCUMENT_RULES, 9)
        
        # === E-MAIL ===
        add_section(texts.ADMIN_SECTION_EMAIL)
        self._btn_email_accounts     = add_nav("›", texts.ADMIN_TAB_EMAIL_ACCOUNTS, 10)
        self._btn_smartscan_settings = add_nav("›", texts.ADMIN_TAB_SMARTSCAN_SETTINGS, 11)
        self._btn_smartscan_history  = add_nav("›", texts.ADMIN_TAB_SMARTSCAN_HISTORY, 12)
        self._btn_email_inbox        = add_nav("›", texts.ADMIN_TAB_EMAIL_INBOX, 13)
        
        # === KOMMUNIKATION ===
        add_section("KOMMUNIKATION")
        self._btn_messages           = add_nav("›", texts.ADMIN_MSG_TAB, 14)
        
        sb_layout.addStretch()
        root.addWidget(admin_sidebar)
        
        # === Content-Bereich (QStackedWidget) ===
        self._content_stack = QStackedWidget()
        self._content_stack.setStyleSheet(f"background-color: {PRIMARY_0};")
        
        # Panels in der neuen Reihenfolge erstellen
        # VERWALTUNG
        self._users_tab = self._create_users_tab()
        self._content_stack.addWidget(self._users_tab)              # 0
        
        self._sessions_tab = self._create_sessions_tab()
        self._content_stack.addWidget(self._sessions_tab)           # 1
        
        self._passwords_tab = self._create_passwords_tab()
        self._content_stack.addWidget(self._passwords_tab)          # 2
        
        # MONITORING
        self._activity_tab = self._create_activity_tab()
        self._content_stack.addWidget(self._activity_tab)           # 3
        
        self._costs_tab = self._create_costs_tab()
        self._content_stack.addWidget(self._costs_tab)              # 4
        
        self._releases_tab = self._create_releases_tab()
        self._content_stack.addWidget(self._releases_tab)           # 5
        
        # VERARBEITUNG
        self._ai_classification_tab = self._create_ai_classification_tab()
        self._content_stack.addWidget(self._ai_classification_tab)  # 6
        
        self._ai_providers_tab = self._create_ai_providers_tab()
        self._content_stack.addWidget(self._ai_providers_tab)       # 7
        
        self._model_pricing_tab = self._create_model_pricing_tab()
        self._content_stack.addWidget(self._model_pricing_tab)      # 8
        
        self._document_rules_tab = self._create_document_rules_tab()
        self._content_stack.addWidget(self._document_rules_tab)     # 9
        
        # E-MAIL
        self._email_accounts_tab = self._create_email_accounts_tab()
        self._content_stack.addWidget(self._email_accounts_tab)     # 10
        
        self._smartscan_settings_tab = self._create_smartscan_settings_tab()
        self._content_stack.addWidget(self._smartscan_settings_tab)  # 11
        
        self._smartscan_history_tab = self._create_smartscan_history_tab()
        self._content_stack.addWidget(self._smartscan_history_tab)   # 12
        
        self._email_inbox_tab = self._create_email_inbox_tab()
        self._content_stack.addWidget(self._email_inbox_tab)         # 13
        
        # KOMMUNIKATION
        self._messages_tab = self._create_messages_tab()
        self._content_stack.addWidget(self._messages_tab)            # 14
        
        root.addWidget(self._content_stack)
        
        # Erster Bereich aktiv
        self._btn_users.setChecked(True)
    
    # ================================================================
    # Tab 1: Nutzerverwaltung
    # ================================================================
    
    def _create_users_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
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
        
        return widget
    
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
    
    def _get_selected_user(self) -> Optional[Dict]:
        """Gibt den ausgewaehlten User zurueck."""
        row = self._users_table.currentRow()
        if row < 0 or row >= len(self._users_data):
            return None
        return self._users_data[row]
    
    def _on_new_user(self):
        dialog = UserEditDialog(self, is_new=True)
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
        dialog = UserEditDialog(self, user_data=user, is_new=False)
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
    
    # ================================================================
    # Tab 2: Sessions
    # ================================================================
    
    def _create_sessions_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(24, 24, 24, 24)
        
        # Toolbar
        toolbar = QHBoxLayout()
        
        title = QLabel(texts.ADMIN_SESSIONS_TITLE)
        title.setFont(QFont(FONT_HEADLINE, 18))
        title.setStyleSheet(f"color: {PRIMARY_900};")
        toolbar.addWidget(title)
        
        toolbar.addStretch()
        
        # Filter: Nutzer
        self._sessions_filter_combo = QComboBox()
        self._sessions_filter_combo.setMinimumWidth(200)
        self._sessions_filter_combo.addItem(texts.ADMIN_SESSIONS_FILTER_ALL, None)
        self._sessions_filter_combo.currentIndexChanged.connect(self._load_sessions)
        toolbar.addWidget(self._sessions_filter_combo)
        
        refresh_btn = QPushButton("↻")
        refresh_btn.setFixedSize(36, 36)
        refresh_btn.setStyleSheet(f"border: 1px solid {PRIMARY_500}; border-radius: {RADIUS_MD}; color: {PRIMARY_500};")
        refresh_btn.clicked.connect(self._load_sessions)
        toolbar.addWidget(refresh_btn)
        
        layout.addLayout(toolbar)
        
        # Tabelle
        self._sessions_table = QTableWidget()
        self._sessions_table.setColumnCount(6)
        self._sessions_table.setHorizontalHeaderLabels([
            texts.ADMIN_COL_USER, texts.ADMIN_COL_IP, texts.ADMIN_COL_CLIENT,
            texts.ADMIN_COL_LAST_ACTIVE, texts.ADMIN_COL_CREATED, texts.ADMIN_COL_EXPIRES
        ])
        self._sessions_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._sessions_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._sessions_table.setAlternatingRowColors(True)
        self._sessions_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._sessions_table.verticalHeader().setVisible(False)
        layout.addWidget(self._sessions_table)
        
        # Action-Buttons
        action_bar = QHBoxLayout()
        
        self._sessions_count_label = QLabel("")
        self._sessions_count_label.setStyleSheet(f"color: {PRIMARY_500};")
        action_bar.addWidget(self._sessions_count_label)
        action_bar.addStretch()
        
        self._btn_kill_session = QPushButton(texts.ADMIN_SESSIONS_KILL)
        self._btn_kill_session.setStyleSheet("color: #e74c3c;")
        self._btn_kill_session.clicked.connect(self._on_kill_session)
        action_bar.addWidget(self._btn_kill_session)
        
        self._btn_kill_all = QPushButton(texts.ADMIN_SESSIONS_KILL_ALL)
        self._btn_kill_all.setStyleSheet("color: #e74c3c;")
        self._btn_kill_all.clicked.connect(self._on_kill_all_sessions)
        action_bar.addWidget(self._btn_kill_all)
        
        layout.addLayout(action_bar)
        
        # Auto-Refresh Timer
        self._session_timer = QTimer()
        self._session_timer.setInterval(30000)  # 30 Sekunden
        self._session_timer.timeout.connect(self._load_sessions)
        
        return widget
    
    def _load_sessions(self):
        """Laedt Sessions."""
        user_id = self._sessions_filter_combo.currentData()
        worker = LoadSessionsWorker(self._admin_api, user_id)
        worker.finished.connect(self._on_sessions_loaded)
        worker.error.connect(lambda e: self._toast_manager.show_error(texts.ADMIN_SESSIONS_LOAD_ERROR.format(error=e)) if hasattr(self, '_toast_manager') else None)
        worker.finished.connect(lambda: self._active_workers.remove(worker) if worker in self._active_workers else None)
        worker.error.connect(lambda: self._active_workers.remove(worker) if worker in self._active_workers else None)
        self._active_workers.append(worker)
        worker.start()
    
    def _on_sessions_loaded(self, sessions: list):
        """Callback wenn Sessions geladen wurden."""
        self._sessions_data = sessions
        self._sessions_table.setRowCount(len(sessions))
        self._sessions_count_label.setText(f"{len(sessions)} Session(s)")
        
        for row, session in enumerate(sessions):
            self._sessions_table.setItem(row, 0, QTableWidgetItem(session.get('username', '')))
            self._sessions_table.setItem(row, 1, QTableWidgetItem(session.get('ip_address', '')))
            self._sessions_table.setItem(row, 2, QTableWidgetItem(session.get('user_agent_short', '')))
            
            last_active = session.get('last_activity_at', '-')
            if last_active and last_active != '-':
                last_active = last_active[:19].replace('T', ' ')
            self._sessions_table.setItem(row, 3, QTableWidgetItem(str(last_active)))
            
            created = session.get('created_at', '-')
            if created and created != '-':
                created = created[:19].replace('T', ' ')
            self._sessions_table.setItem(row, 4, QTableWidgetItem(str(created)))
            
            expires = session.get('expires_at', '-')
            if expires and expires != '-':
                expires = expires[:19].replace('T', ' ')
            self._sessions_table.setItem(row, 5, QTableWidgetItem(str(expires)))
        
        # User-Filter aktualisieren (nur einmalig)
        if self._sessions_filter_combo.count() <= 1:
            usernames = sorted(set(s.get('username', '') for s in sessions))
            for username in usernames:
                user_id = next((s.get('user_id') for s in sessions if s.get('username') == username), None)
                if user_id:
                    self._sessions_filter_combo.addItem(username, user_id)
    
    def _get_selected_session(self) -> Optional[Dict]:
        row = self._sessions_table.currentRow()
        if row < 0 or row >= len(self._sessions_data):
            return None
        return self._sessions_data[row]
    
    def _on_kill_session(self):
        session = self._get_selected_session()
        if not session:
            return
        reply = QMessageBox.question(self, texts.WARNING, texts.ADMIN_SESSIONS_KILL_CONFIRM,
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self._admin_api.kill_session(session['id'])
                self._toast_manager.show_success(texts.ADMIN_SESSIONS_KILLED)
                self._load_sessions()
            except APIError as e:
                self._toast_manager.show_error(str(e))
    
    def _on_kill_all_sessions(self):
        session = self._get_selected_session()
        if not session:
            return
        username = session.get('username', '')
        user_id = session.get('user_id')
        if not user_id:
            return
        reply = QMessageBox.question(self, texts.WARNING, texts.ADMIN_SESSIONS_KILL_ALL_CONFIRM.format(username=username),
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self._admin_api.kill_user_sessions(user_id)
                self._toast_manager.show_success(texts.ADMIN_SESSIONS_ALL_KILLED.format(count='?'))
                self._load_sessions()
            except APIError as e:
                self._toast_manager.show_error(str(e))
    
    # ================================================================
    # Tab 3: Aktivitaetslog
    # ================================================================
    
    def _create_activity_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(24, 24, 24, 24)
        
        # Toolbar
        toolbar = QHBoxLayout()
        
        title = QLabel(texts.ADMIN_ACTIVITY_TITLE)
        title.setFont(QFont(FONT_HEADLINE, 18))
        title.setStyleSheet(f"color: {PRIMARY_900};")
        toolbar.addWidget(title)
        toolbar.addStretch()
        
        refresh_btn = QPushButton("↻")
        refresh_btn.setFixedSize(36, 36)
        refresh_btn.setStyleSheet(f"border: 1px solid {PRIMARY_500}; border-radius: {RADIUS_MD}; color: {PRIMARY_500};")
        refresh_btn.clicked.connect(self._load_activity)
        toolbar.addWidget(refresh_btn)
        
        layout.addLayout(toolbar)
        
        # Filter-Leiste
        filter_bar = QHBoxLayout()
        
        # Kategorie
        filter_bar.addWidget(QLabel(texts.ADMIN_ACTIVITY_FILTER_CATEGORY + ":"))
        self._activity_category_combo = QComboBox()
        self._activity_category_combo.setMinimumWidth(150)
        self._activity_category_combo.addItem(texts.ADMIN_ACTIVITY_FILTER_ALL, '')
        for cat_key, cat_name in CATEGORY_NAMES.items():
            self._activity_category_combo.addItem(cat_name, cat_key)
        filter_bar.addWidget(self._activity_category_combo)
        
        # Status
        filter_bar.addWidget(QLabel(texts.ADMIN_ACTIVITY_FILTER_STATUS + ":"))
        self._activity_status_combo = QComboBox()
        self._activity_status_combo.addItem(texts.ADMIN_ACTIVITY_FILTER_ALL, '')
        self._activity_status_combo.addItem(texts.ACTIVITY_STATUS_SUCCESS, 'success')
        self._activity_status_combo.addItem(texts.ACTIVITY_STATUS_ERROR, 'error')
        self._activity_status_combo.addItem(texts.ACTIVITY_STATUS_DENIED, 'denied')
        filter_bar.addWidget(self._activity_status_combo)
        
        # Von/Bis
        filter_bar.addWidget(QLabel(texts.ADMIN_ACTIVITY_FILTER_FROM + ":"))
        self._activity_from_date = QDateEdit()
        self._activity_from_date.setCalendarPopup(True)
        self._activity_from_date.setDate(QDate.currentDate().addDays(-7))
        self._activity_from_date.setDisplayFormat("dd.MM.yyyy")
        filter_bar.addWidget(self._activity_from_date)
        
        filter_bar.addWidget(QLabel(texts.ADMIN_ACTIVITY_FILTER_TO + ":"))
        self._activity_to_date = QDateEdit()
        self._activity_to_date.setCalendarPopup(True)
        self._activity_to_date.setDate(QDate.currentDate())
        self._activity_to_date.setDisplayFormat("dd.MM.yyyy")
        filter_bar.addWidget(self._activity_to_date)
        
        # Suche
        self._activity_search = QLineEdit()
        self._activity_search.setPlaceholderText(texts.ADMIN_ACTIVITY_FILTER_SEARCH)
        self._activity_search.setMinimumWidth(180)
        self._activity_search.returnPressed.connect(self._load_activity)
        filter_bar.addWidget(self._activity_search)
        
        # Filter-Button
        filter_btn = QPushButton(texts.ADMIN_ACTIVITY_FILTER_SEARCH.replace('...', ''))
        filter_btn.setStyleSheet(f"background-color: {ACCENT_500}; color: white; border: none; border-radius: {RADIUS_MD}; padding: 6px 16px;")
        filter_btn.clicked.connect(self._load_activity)
        filter_bar.addWidget(filter_btn)
        
        layout.addLayout(filter_bar)
        
        # Tabelle
        self._activity_table = QTableWidget()
        self._activity_table.setColumnCount(7)
        self._activity_table.setHorizontalHeaderLabels([
            texts.ADMIN_COL_TIMESTAMP, texts.ADMIN_COL_USER, texts.ADMIN_COL_CATEGORY,
            texts.ADMIN_COL_ACTION, texts.ADMIN_COL_DESCRIPTION, texts.ADMIN_COL_IP,
            texts.ADMIN_COL_STATUS
        ])
        self._activity_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._activity_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._activity_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self._activity_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        self._activity_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._activity_table.setAlternatingRowColors(True)
        self._activity_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._activity_table.verticalHeader().setVisible(False)
        layout.addWidget(self._activity_table)
        
        # Pagination
        pagination_bar = QHBoxLayout()
        
        self._activity_total_label = QLabel("")
        self._activity_total_label.setStyleSheet(f"color: {PRIMARY_500};")
        pagination_bar.addWidget(self._activity_total_label)
        pagination_bar.addStretch()
        
        self._btn_prev_page = QPushButton("← Vorherige")
        self._btn_prev_page.setEnabled(False)
        self._btn_prev_page.clicked.connect(self._activity_prev_page)
        pagination_bar.addWidget(self._btn_prev_page)
        
        self._activity_page_label = QLabel("")
        pagination_bar.addWidget(self._activity_page_label)
        
        self._btn_next_page = QPushButton("Naechste →")
        self._btn_next_page.setEnabled(False)
        self._btn_next_page.clicked.connect(self._activity_next_page)
        pagination_bar.addWidget(self._btn_next_page)
        
        layout.addLayout(pagination_bar)
        
        return widget
    
    def _load_activity(self):
        """Laedt Aktivitaetslog mit aktuellen Filtern."""
        filters = {
            'page': self._activity_page,
            'per_page': self._activity_per_page,
        }
        
        category = self._activity_category_combo.currentData()
        if category:
            filters['action_category'] = category
        
        status = self._activity_status_combo.currentData()
        if status:
            filters['status'] = status
        
        from_date = self._activity_from_date.date().toString('yyyy-MM-dd')
        filters['from_date'] = from_date
        
        to_date = self._activity_to_date.date().toString('yyyy-MM-dd')
        filters['to_date'] = to_date
        
        search = self._activity_search.text().strip()
        if search:
            filters['search'] = search
        
        worker = LoadActivityWorker(self._admin_api, filters)
        worker.finished.connect(self._on_activity_loaded)
        worker.error.connect(lambda e: self._toast_manager.show_error(texts.ADMIN_ACTIVITY_LOAD_ERROR.format(error=e)) if hasattr(self, '_toast_manager') else None)
        worker.finished.connect(lambda: self._active_workers.remove(worker) if worker in self._active_workers else None)
        worker.error.connect(lambda: self._active_workers.remove(worker) if worker in self._active_workers else None)
        self._active_workers.append(worker)
        worker.start()
    
    def _on_activity_loaded(self, result: dict):
        """Callback wenn Log geladen wurde."""
        items = result.get('items', [])
        total = result.get('total', 0)
        page = result.get('page', 1)
        total_pages = result.get('total_pages', 0)
        
        self._activity_table.setRowCount(len(items))
        
        for row, item in enumerate(items):
            # Zeitpunkt
            ts = item.get('created_at', '-')
            if ts and ts != '-':
                ts = ts[:19].replace('T', ' ')
            self._activity_table.setItem(row, 0, QTableWidgetItem(str(ts)))
            
            # Nutzer
            self._activity_table.setItem(row, 1, QTableWidgetItem(item.get('username', '-')))
            
            # Kategorie
            cat_key = item.get('action_category', '')
            cat_name = CATEGORY_NAMES.get(cat_key, cat_key)
            self._activity_table.setItem(row, 2, QTableWidgetItem(cat_name))
            
            # Aktion
            self._activity_table.setItem(row, 3, QTableWidgetItem(item.get('action', '')))
            
            # Beschreibung
            self._activity_table.setItem(row, 4, QTableWidgetItem(item.get('description', '')))
            
            # IP
            self._activity_table.setItem(row, 5, QTableWidgetItem(item.get('ip_address', '')))
            
            # Status (farbkodiert)
            status = item.get('status', 'success')
            status_text = {
                'success': texts.ACTIVITY_STATUS_SUCCESS,
                'error': texts.ACTIVITY_STATUS_ERROR,
                'denied': texts.ACTIVITY_STATUS_DENIED
            }.get(status, status)
            status_item = QTableWidgetItem(status_text)
            color = STATUS_COLORS.get(status, PRIMARY_500)
            status_item.setForeground(QColor(color))
            self._activity_table.setItem(row, 6, status_item)
        
        # Pagination aktualisieren
        self._activity_total_label.setText(texts.ADMIN_ACTIVITY_TOTAL.format(total=total))
        self._activity_page_label.setText(texts.ADMIN_ACTIVITY_PAGE.format(page=page, total_pages=max(total_pages, 1)))
        self._btn_prev_page.setEnabled(page > 1)
        self._btn_next_page.setEnabled(page < total_pages)
    
    def _activity_prev_page(self):
        if self._activity_page > 1:
            self._activity_page -= 1
            self._load_activity()
    
    def _activity_next_page(self):
        self._activity_page += 1
        self._load_activity()
    
    # ================================================================
    # Tab 4: KI-Kosten
    # ================================================================
    
    def _create_costs_tab(self) -> QWidget:
        """Erstellt den KI-Kosten-Tab mit Statistiken und Historie."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        
        # --- Header mit Titel und Aktionen ---
        header_layout = QHBoxLayout()
        
        title = QLabel(texts.COSTS_TITLE)
        title.setStyleSheet(f"""
            font-family: {FONT_HEADLINE};
            font-size: {FONT_SIZE_H2};
            color: {PRIMARY_900};
            font-weight: bold;
        """)
        header_layout.addWidget(title)
        header_layout.addStretch()
        
        # Zeitraum-Filter
        period_label = QLabel(texts.COSTS_PERIOD_LABEL)
        period_label.setStyleSheet(f"font-family: {FONT_BODY}; color: {PRIMARY_500};")
        header_layout.addWidget(period_label)
        
        self._costs_period_combo = QComboBox()
        self._costs_period_combo.addItem(texts.COSTS_PERIOD_ALL, "all")
        self._costs_period_combo.addItem(texts.COSTS_PERIOD_7D, "7d")
        self._costs_period_combo.addItem(texts.COSTS_PERIOD_30D, "30d")
        self._costs_period_combo.addItem(texts.COSTS_PERIOD_90D, "90d")
        self._costs_period_combo.setCurrentIndex(0)
        self._costs_period_combo.currentIndexChanged.connect(self._load_cost_data)
        self._costs_period_combo.setStyleSheet(f"font-family: {FONT_BODY};")
        header_layout.addWidget(self._costs_period_combo)
        
        # Aktualisieren-Button
        refresh_btn = QPushButton(texts.COSTS_REFRESH)
        refresh_btn.setStyleSheet(f"""
            QPushButton {{
                padding: 6px 16px;
                font-family: {FONT_BODY};
                background-color: {ACCENT_100};
                color: {PRIMARY_900};
                border: 1px solid {ACCENT_500};
                border-radius: {RADIUS_MD};
            }}
            QPushButton:hover {{
                background-color: {ACCENT_500};
                color: white;
            }}
        """)
        refresh_btn.clicked.connect(self._load_cost_data)
        header_layout.addWidget(refresh_btn)
        
        layout.addLayout(header_layout)
        
        # --- Statistik-Karten ---
        stats_frame = QFrame()
        stats_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {PRIMARY_100};
                border: 1px solid {ACCENT_100};
                border-radius: {RADIUS_MD};
                padding: 16px;
            }}
        """)
        stats_layout = QHBoxLayout(stats_frame)
        stats_layout.setSpacing(24)
        
        # Statistik-Labels erstellen
        self._stat_labels = {}
        stat_items = [
            ('runs', texts.COSTS_TOTAL_RUNS, '0'),
            ('docs', texts.COSTS_TOTAL_DOCS, '0'),
            ('cost', texts.COSTS_TOTAL_COST, '$0.00'),
            ('avg_doc', texts.COSTS_AVG_COST_PER_DOC, '$0.00'),
            ('avg_run', texts.COSTS_AVG_COST_PER_RUN, '$0.00'),
            ('duration', texts.COSTS_TOTAL_DURATION, '0s'),
            ('rate', texts.COSTS_SUCCESS_RATE, '0%'),
        ]
        
        for key, label_text, default_val in stat_items:
            stat_widget = QVBoxLayout()
            
            value_label = QLabel(default_val)
            value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            value_label.setStyleSheet(f"""
                font-family: {FONT_HEADLINE};
                font-size: 18px;
                color: {PRIMARY_900};
                font-weight: bold;
                background: transparent;
                border: none;
            """)
            
            desc_label = QLabel(label_text)
            desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            desc_label.setStyleSheet(f"""
                font-family: {FONT_BODY};
                font-size: {FONT_SIZE_CAPTION};
                color: {PRIMARY_500};
                background: transparent;
                border: none;
            """)
            
            stat_widget.addWidget(value_label)
            stat_widget.addWidget(desc_label)
            stats_layout.addLayout(stat_widget)
            
            self._stat_labels[key] = value_label
        
        layout.addWidget(stats_frame)
        
        # --- Historie-Tabelle ---
        history_label = QLabel(texts.COSTS_HISTORY_TITLE)
        history_label.setStyleSheet(f"""
            font-family: {FONT_HEADLINE};
            font-size: 14px;
            color: {PRIMARY_900};
            font-weight: bold;
        """)
        layout.addWidget(history_label)
        
        self._costs_table = QTableWidget()
        self._costs_table.setColumnCount(8)
        self._costs_table.setHorizontalHeaderLabels([
            texts.COSTS_COL_DATE,
            texts.COSTS_COL_TOTAL_COST,
            texts.COSTS_COL_COST_PER_DOC,
            texts.COSTS_COL_DOC_COUNT,
            texts.COSTS_COL_SUCCESS,
            texts.COSTS_COL_FAILED,
            texts.COSTS_COL_DURATION,
            texts.COSTS_COL_USER,
        ])
        
        self._costs_table.setAlternatingRowColors(True)
        self._costs_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._costs_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._costs_table.verticalHeader().setVisible(False)
        self._costs_table.setStyleSheet(f"""
            QTableWidget {{
                font-family: {FONT_BODY};
                font-size: {FONT_SIZE_BODY};
                background-color: white;
                border: 1px solid {PRIMARY_100};
                border-radius: {RADIUS_MD};
                gridline-color: {PRIMARY_100};
            }}
            QTableWidget::item {{
                padding: 6px 10px;
            }}
            QTableWidget::item:alternate {{
                background-color: #FAFAFA;
            }}
            QHeaderView::section {{
                background-color: {PRIMARY_100};
                color: {PRIMARY_900};
                font-weight: bold;
                padding: 8px 10px;
                border: none;
                border-bottom: 2px solid {ACCENT_500};
            }}
        """)
        
        header = self._costs_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # Datum
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)             # Kosten
        header.resizeSection(1, 80)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)             # $/Dok
        header.resizeSection(2, 95)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)             # Doks
        header.resizeSection(3, 55)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)             # OK
        header.resizeSection(4, 45)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)             # Fehler
        header.resizeSection(5, 65)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)             # Dauer
        header.resizeSection(6, 60)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)           # Nutzer
        
        layout.addWidget(self._costs_table, stretch=1)
        
        # Status-Label
        self._costs_status = QLabel("")
        self._costs_status.setStyleSheet(f"""
            font-family: {FONT_BODY};
            font-size: {FONT_SIZE_CAPTION};
            color: {PRIMARY_500};
        """)
        layout.addWidget(self._costs_status)
        
        # --- Einzelne Requests (NEU) ---
        requests_header = QHBoxLayout()
        requests_label = QLabel(texts.AI_COSTS_REQUESTS_TITLE)
        requests_label.setStyleSheet(f"""
            font-family: {FONT_HEADLINE};
            font-size: 14px;
            color: {PRIMARY_900};
            font-weight: bold;
        """)
        requests_header.addWidget(requests_label)
        requests_header.addStretch()
        
        export_btn = QPushButton(texts.AI_COSTS_REQUESTS_EXPORT)
        export_btn.setStyleSheet(get_button_secondary_style())
        export_btn.setCursor(Qt.PointingHandCursor)
        export_btn.clicked.connect(self._export_ai_requests_csv)
        requests_header.addWidget(export_btn)
        layout.addLayout(requests_header)
        
        self._ai_requests_table = QTableWidget()
        self._ai_requests_table.setColumnCount(8)
        self._ai_requests_table.setHorizontalHeaderLabels([
            texts.AI_COSTS_REQUESTS_TIME, texts.AI_COSTS_REQUESTS_USER,
            texts.AI_COSTS_REQUESTS_PROVIDER, texts.AI_COSTS_REQUESTS_MODEL,
            texts.AI_COSTS_REQUESTS_PROMPT_TOKENS, texts.AI_COSTS_REQUESTS_COMPLETION_TOKENS,
            texts.AI_COSTS_REQUESTS_ESTIMATED, texts.AI_COSTS_REQUESTS_COST
        ])
        self._ai_requests_table.setAlternatingRowColors(True)
        self._ai_requests_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._ai_requests_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._ai_requests_table.verticalHeader().setVisible(False)
        self._ai_requests_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self._ai_requests_table.setColumnWidth(0, 130)   # Zeit
        self._ai_requests_table.setColumnWidth(4, 110)   # Prompt Tokens
        self._ai_requests_table.setColumnWidth(5, 130)   # Completion Tokens
        self._ai_requests_table.setColumnWidth(6, 110)   # Geschaetzt
        self._ai_requests_table.setColumnWidth(7, 110)   # Echte Kosten
        layout.addWidget(self._ai_requests_table, stretch=1)
        
        self._ai_requests_status = QLabel("")
        self._ai_requests_status.setStyleSheet(f"font-size: {FONT_SIZE_CAPTION}; color: {PRIMARY_500};")
        layout.addWidget(self._ai_requests_status)
        
        return widget
    
    def _load_cost_data(self):
        """Laedt Kosten-Daten basierend auf dem Zeitraum-Filter."""
        from datetime import datetime, timedelta
        
        self._costs_status.setText(texts.LOADING)
        
        # Zeitraum bestimmen
        period = self._costs_period_combo.currentData()
        from_date = None
        to_date = None
        
        if period == '7d':
            from_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        elif period == '30d':
            from_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        elif period == '90d':
            from_date = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
        # 'all' -> kein Filter
        
        self._cost_worker = LoadCostDataWorker(
            self._api_client, from_date, to_date
        )
        self._cost_worker.finished.connect(self._on_cost_data_loaded)
        self._cost_worker.error.connect(self._on_cost_data_error)
        self._active_workers.append(self._cost_worker)
        self._cost_worker.start()
    
    def _on_cost_data_loaded(self, result: Dict):
        """Callback wenn Kosten-Daten geladen."""
        history = result.get('history', [])
        stats = result.get('stats', {})
        
        # Statistik-Karten aktualisieren
        self._update_cost_stats(stats)
        
        # Tabelle befuellen
        self._populate_cost_table(history)
        
        count = len(history)
        if count == 0:
            self._costs_status.setText(texts.COSTS_NO_DATA)
        else:
            self._costs_status.setText(f"{count} Verarbeitungslauf/-laeufe")
        
        # Einzelne Requests laden
        self._load_ai_requests()
    
    def _on_cost_data_error(self, error: str):
        """Callback bei Kosten-Daten Fehler."""
        self._costs_status.setText(texts.COSTS_LOAD_ERROR.format(error=error))
        logger.error(f"Kosten-Daten Fehler: {error}")
    
    def _update_cost_stats(self, stats: Dict):
        """Aktualisiert die Statistik-Karten."""
        if not stats:
            return
        
        self._stat_labels['runs'].setText(str(stats.get('total_runs', 0)))
        self._stat_labels['docs'].setText(str(stats.get('total_documents', 0)))
        
        total_cost = stats.get('total_cost_usd', 0)
        self._stat_labels['cost'].setText(f"${total_cost:.4f}")
        
        avg_doc = stats.get('avg_cost_per_document_usd', 0)
        self._stat_labels['avg_doc'].setText(f"${avg_doc:.6f}")
        
        avg_run = stats.get('avg_cost_per_run_usd', 0)
        self._stat_labels['avg_run'].setText(f"${avg_run:.4f}")
        
        duration_s = stats.get('total_duration_seconds', 0)
        if duration_s >= 60:
            minutes = int(duration_s // 60)
            seconds = int(duration_s % 60)
            self._stat_labels['duration'].setText(f"{minutes}m {seconds}s")
        else:
            self._stat_labels['duration'].setText(f"{duration_s:.1f}s")
        
        rate = stats.get('success_rate_percent', 0)
        self._stat_labels['rate'].setText(f"{rate:.1f}%")
        
        # Farbkodierung fuer Erfolgsrate
        if rate >= 95:
            color = STATUS_COLORS['success']
        elif rate >= 80:
            color = STATUS_COLORS['denied']
        else:
            color = STATUS_COLORS['error']
        
        self._stat_labels['rate'].setStyleSheet(f"""
            font-family: {FONT_HEADLINE};
            font-size: 18px;
            color: {color};
            font-weight: bold;
            background: transparent;
            border: none;
        """)
    
    def _populate_cost_table(self, history: list):
        """Befuellt die Kosten-Tabelle."""
        self._costs_table.setRowCount(0)
        self._costs_table.setSortingEnabled(False)
        
        for entry in history:
            row = self._costs_table.rowCount()
            self._costs_table.insertRow(row)
            
            # Datum formatieren (YYYY-MM-DD HH:MM:SS -> DD.MM.YYYY HH:MM)
            date_str = entry.get('date', '')
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(date_str.replace('Z', '+00:00') if 'Z' in date_str else date_str)
                formatted_date = dt.strftime('%d.%m.%Y %H:%M')
            except (ValueError, TypeError):
                formatted_date = date_str[:16] if date_str else '-'
            
            # Datum
            date_item = QTableWidgetItem(formatted_date)
            date_item.setData(Qt.ItemDataRole.UserRole, date_str)  # Fuer Sortierung
            self._costs_table.setItem(row, 0, date_item)
            
            # Gesamtkosten
            total_cost = entry.get('total_cost_usd', 0)
            cost_item = QTableWidgetItem(f"${total_cost:.4f}")
            cost_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            cost_item.setData(Qt.ItemDataRole.UserRole, total_cost)
            self._costs_table.setItem(row, 1, cost_item)
            
            # Kosten pro Dokument
            cost_per_doc = entry.get('cost_per_document_usd', 0)
            cpd_item = QTableWidgetItem(f"${cost_per_doc:.6f}")
            cpd_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            cpd_item.setData(Qt.ItemDataRole.UserRole, cost_per_doc)
            self._costs_table.setItem(row, 2, cpd_item)
            
            # Dokumente
            total_docs = entry.get('total_documents', 0)
            docs_item = QTableWidgetItem(str(total_docs))
            docs_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            docs_item.setData(Qt.ItemDataRole.UserRole, total_docs)
            self._costs_table.setItem(row, 3, docs_item)
            
            # Erfolgreich
            success = entry.get('successful_documents', 0)
            success_item = QTableWidgetItem(str(success))
            success_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            success_item.setForeground(QColor(STATUS_COLORS['success']))
            self._costs_table.setItem(row, 4, success_item)
            
            # Fehlgeschlagen
            failed = entry.get('failed_documents', 0)
            failed_item = QTableWidgetItem(str(failed))
            failed_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if failed > 0:
                failed_item.setForeground(QColor(STATUS_COLORS['error']))
            self._costs_table.setItem(row, 5, failed_item)
            
            # Dauer
            duration_s = entry.get('duration_seconds', 0)
            if duration_s >= 60:
                minutes = int(duration_s // 60)
                seconds = int(duration_s % 60)
                duration_str = f"{minutes}m {seconds}s"
            else:
                duration_str = f"{duration_s:.1f}s"
            duration_item = QTableWidgetItem(duration_str)
            duration_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            duration_item.setData(Qt.ItemDataRole.UserRole, duration_s)
            self._costs_table.setItem(row, 6, duration_item)
            
            # User
            user = entry.get('user', '-')
            self._costs_table.setItem(row, 7, QTableWidgetItem(user))
        
        self._costs_table.setSortingEnabled(True)
    
    def _load_ai_requests(self):
        """Laedt die einzelnen KI-Requests."""
        period = self._costs_period_combo.currentData() or 'all'
        
        def _do_load():
            return self._model_pricing_api.get_ai_requests(limit=200, period=period)
        
        worker = AdminWriteWorker(_do_load)
        worker.finished.connect(self._on_ai_requests_loaded)
        worker.error.connect(lambda e: (
            self._ai_requests_status.setText(texts.AI_COSTS_REQUESTS_LOAD_ERROR),
            logger.error(f"AI-Requests laden: {e}")
        ))
        self._active_workers.append(worker)
        worker.start()
    
    def _on_ai_requests_loaded(self, result):
        """Befuellt die AI-Requests Tabelle."""
        if not result:
            return
        requests = result if isinstance(result, list) else result.get('requests', [])
        table = self._ai_requests_table
        table.setRowCount(len(requests))
        
        for row, req in enumerate(requests):
            # Zeit
            created = req.get('created_at', '')
            try:
                from datetime import datetime as dt_cls
                dt = dt_cls.fromisoformat(created.replace('Z', '+00:00') if 'Z' in created else created)
                time_str = dt.strftime('%d.%m. %H:%M:%S')
            except (ValueError, TypeError):
                time_str = created[:19] if created else '-'
            table.setItem(row, 0, QTableWidgetItem(time_str))
            
            # User
            table.setItem(row, 1, QTableWidgetItem(req.get('username', '-')))
            
            # Provider
            table.setItem(row, 2, QTableWidgetItem(req.get('provider', '-')))
            
            # Modell
            table.setItem(row, 3, QTableWidgetItem(req.get('model', '-')))
            
            # Prompt Tokens
            pt = QTableWidgetItem(str(req.get('prompt_tokens', 0)))
            pt.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            table.setItem(row, 4, pt)
            
            # Completion Tokens
            ct = QTableWidgetItem(str(req.get('completion_tokens', 0)))
            ct.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            table.setItem(row, 5, ct)
            
            # Geschaetzte Kosten
            est = req.get('estimated_cost_usd')
            est_str = f"${float(est):.6f}" if est is not None else "-"
            est_item = QTableWidgetItem(est_str)
            est_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            table.setItem(row, 6, est_item)
            
            # Echte Kosten
            real = float(req.get('real_cost_usd', 0))
            real_item = QTableWidgetItem(f"${real:.6f}")
            real_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            table.setItem(row, 7, real_item)
        
        total_count = len(requests)
        total_cost = sum(float(r.get('real_cost_usd', 0)) for r in requests)
        self._ai_requests_status.setText(
            texts.AI_COSTS_REQUESTS_TOTAL.format(count=total_count, cost=f"{total_cost:.4f}")
        )
    
    def _export_ai_requests_csv(self):
        """Exportiert die AI-Requests als CSV."""
        from ui.toast import ToastManager
        path, _ = QFileDialog.getSaveFileName(
            self, texts.AI_COSTS_REQUESTS_EXPORT, "ai_requests.csv", "CSV (*.csv)"
        )
        if not path:
            return
        
        try:
            table = self._ai_requests_table
            with open(path, 'w', encoding='utf-8-sig') as f:
                headers = []
                for col in range(table.columnCount()):
                    headers.append(table.horizontalHeaderItem(col).text())
                f.write(';'.join(headers) + '\n')
                
                for row in range(table.rowCount()):
                    cells = []
                    for col in range(table.columnCount()):
                        item = table.item(row, col)
                        cells.append(item.text() if item else '')
                    f.write(';'.join(cells) + '\n')
            
            ToastManager.instance().show_success(f"CSV exportiert: {path}")
        except Exception as e:
            ToastManager.instance().show_error(f"Export fehlgeschlagen: {e}")
    
    # ================================================================
    # Tab 5: Releases
    # ================================================================
    
    # Status-Farben fuer Releases
    RELEASE_STATUS_COLORS = {
        'active': SUCCESS,
        'mandatory': '#e74c3c',
        'deprecated': '#f39c12',
        'withdrawn': '#95a5a6',
    }
    
    RELEASE_STATUS_NAMES = {
        'active': texts.RELEASES_STATUS_ACTIVE,
        'mandatory': texts.RELEASES_STATUS_MANDATORY,
        'deprecated': texts.RELEASES_STATUS_DEPRECATED,
        'withdrawn': texts.RELEASES_STATUS_WITHDRAWN,
    }
    
    RELEASE_CHANNEL_NAMES = {
        'stable': texts.RELEASES_CHANNEL_STABLE,
        'beta': texts.RELEASES_CHANNEL_BETA,
        'internal': texts.RELEASES_CHANNEL_INTERNAL,
    }
    
    def _create_releases_tab(self) -> QWidget:
        """Erstellt den Releases-Tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        
        # --- Header mit Titel und Aktionen ---
        header_layout = QHBoxLayout()
        
        title = QLabel(texts.RELEASES_TITLE)
        title.setStyleSheet(f"""
            font-family: {FONT_HEADLINE};
            font-size: {FONT_SIZE_H2};
            color: {PRIMARY_900};
            font-weight: bold;
        """)
        header_layout.addWidget(title)
        header_layout.addStretch()
        
        # Filter: Channel
        channel_label = QLabel(texts.RELEASES_FILTER_CHANNEL)
        channel_label.setStyleSheet(f"font-family: {FONT_BODY}; color: {PRIMARY_500};")
        header_layout.addWidget(channel_label)
        
        self._releases_channel_filter = QComboBox()
        self._releases_channel_filter.addItem(texts.RELEASES_FILTER_ALL, "all")
        self._releases_channel_filter.addItem(texts.RELEASES_CHANNEL_STABLE, "stable")
        self._releases_channel_filter.addItem(texts.RELEASES_CHANNEL_BETA, "beta")
        self._releases_channel_filter.addItem(texts.RELEASES_CHANNEL_INTERNAL, "internal")
        self._releases_channel_filter.setStyleSheet(f"font-family: {FONT_BODY};")
        self._releases_channel_filter.currentIndexChanged.connect(self._apply_releases_filter)
        header_layout.addWidget(self._releases_channel_filter)
        
        # Filter: Status
        status_label = QLabel(texts.RELEASES_FILTER_STATUS)
        status_label.setStyleSheet(f"font-family: {FONT_BODY}; color: {PRIMARY_500};")
        header_layout.addWidget(status_label)
        
        self._releases_status_filter = QComboBox()
        self._releases_status_filter.addItem(texts.RELEASES_FILTER_ALL, "all")
        self._releases_status_filter.addItem(texts.RELEASES_STATUS_ACTIVE, "active")
        self._releases_status_filter.addItem(texts.RELEASES_STATUS_MANDATORY, "mandatory")
        self._releases_status_filter.addItem(texts.RELEASES_STATUS_DEPRECATED, "deprecated")
        self._releases_status_filter.addItem(texts.RELEASES_STATUS_WITHDRAWN, "withdrawn")
        self._releases_status_filter.setStyleSheet(f"font-family: {FONT_BODY};")
        self._releases_status_filter.currentIndexChanged.connect(self._apply_releases_filter)
        header_layout.addWidget(self._releases_status_filter)
        
        # Neues Release Button
        new_btn = QPushButton(f"+ {texts.RELEASES_NEW}")
        new_btn.setStyleSheet(f"""
            QPushButton {{
                padding: 6px 16px;
                font-family: {FONT_BODY};
                background-color: {ACCENT_500};
                color: white;
                border: none;
                border-radius: {RADIUS_MD};
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #e88a2d;
            }}
        """)
        new_btn.clicked.connect(self._new_release)
        header_layout.addWidget(new_btn)
        
        # Aktualisieren Button
        refresh_btn = QPushButton(texts.COSTS_REFRESH)
        refresh_btn.setStyleSheet(f"""
            QPushButton {{
                padding: 6px 16px;
                font-family: {FONT_BODY};
                background-color: {ACCENT_100};
                color: {PRIMARY_900};
                border: 1px solid {ACCENT_500};
                border-radius: {RADIUS_MD};
            }}
            QPushButton:hover {{
                background-color: {ACCENT_500};
                color: white;
            }}
        """)
        refresh_btn.clicked.connect(self._load_releases)
        header_layout.addWidget(refresh_btn)
        
        layout.addLayout(header_layout)
        
        # --- Releases-Tabelle ---
        self._releases_table = QTableWidget()
        self._releases_table.setColumnCount(8)
        self._releases_table.setHorizontalHeaderLabels([
            texts.RELEASES_VERSION,
            texts.RELEASES_CHANNEL,
            texts.RELEASES_STATUS,
            texts.RELEASES_DOWNLOADS,
            texts.RELEASES_SIZE,
            texts.RELEASES_DATE,
            texts.RELEASES_RELEASED_BY,
            texts.RELEASES_ACTIONS,
        ])
        self._releases_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._releases_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._releases_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._releases_table.setAlternatingRowColors(True)
        self._releases_table.setSortingEnabled(True)
        self._releases_table.verticalHeader().setVisible(False)
        self._releases_table.verticalHeader().setDefaultSectionSize(70)
        
        header = self._releases_table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Fixed)
        self._releases_table.setColumnWidth(7, 180)
        
        layout.addWidget(self._releases_table)
        
        return widget
    
    def _load_releases(self):
        """Laedt alle Releases vom Server."""
        worker = LoadReleasesWorker(self._releases_api)
        worker.finished.connect(self._on_releases_loaded)
        worker.error.connect(self._on_releases_error)
        self._active_workers.append(worker)
        worker.start()
    
    def _on_releases_loaded(self, releases: list):
        """Releases geladen, Tabelle fuellen."""
        self._releases_data = releases
        self._apply_releases_filter()
    
    def _on_releases_error(self, error: str):
        """Fehler beim Laden der Releases."""
        logger.error(f"Releases laden fehlgeschlagen: {error}")
        self._toast_manager.show_error(texts.RELEASES_LOAD_ERROR.format(error=error))
    
    def _apply_releases_filter(self):
        """Wendet die aktuellen Filter auf die Releases-Tabelle an."""
        channel_filter = self._releases_channel_filter.currentData()
        status_filter = self._releases_status_filter.currentData()
        
        filtered = self._releases_data
        if channel_filter != 'all':
            filtered = [r for r in filtered if r.get('channel') == channel_filter]
        if status_filter != 'all':
            filtered = [r for r in filtered if r.get('status') == status_filter]
        
        self._populate_releases_table(filtered)
    
    def _populate_releases_table(self, releases: list):
        """Fuellt die Releases-Tabelle."""
        self._releases_table.setSortingEnabled(False)
        self._releases_table.setRowCount(len(releases))
        
        for row, release in enumerate(releases):
            # Version
            version_item = QTableWidgetItem(release.get('version', ''))
            font = QFont(FONT_BODY)
            font.setBold(True)
            version_item.setFont(font)
            version_item.setData(Qt.ItemDataRole.UserRole, release)
            self._releases_table.setItem(row, 0, version_item)
            
            # Channel
            channel = release.get('channel', 'stable')
            channel_name = self.RELEASE_CHANNEL_NAMES.get(channel, channel)
            channel_item = QTableWidgetItem(channel_name)
            channel_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._releases_table.setItem(row, 1, channel_item)
            
            # Status (farbkodiert)
            status = release.get('status', 'active')
            status_name = self.RELEASE_STATUS_NAMES.get(status, status)
            status_item = QTableWidgetItem(f"● {status_name}")
            status_color = self.RELEASE_STATUS_COLORS.get(status, PRIMARY_500)
            status_item.setForeground(QColor(status_color))
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._releases_table.setItem(row, 2, status_item)
            
            # Downloads
            downloads = release.get('download_count', 0)
            downloads_item = QTableWidgetItem(str(downloads))
            downloads_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            downloads_item.setData(Qt.ItemDataRole.UserRole, downloads)
            self._releases_table.setItem(row, 3, downloads_item)
            
            # Groesse
            file_size = int(release.get('file_size', 0))
            if file_size > 0:
                if file_size >= 1024 * 1024:
                    size_str = f"{file_size / 1024 / 1024:.1f} MB"
                elif file_size >= 1024:
                    size_str = f"{file_size / 1024:.1f} KB"
                else:
                    size_str = f"{file_size} B"
            else:
                size_str = "-"
            size_item = QTableWidgetItem(size_str)
            size_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            size_item.setData(Qt.ItemDataRole.UserRole, file_size)
            self._releases_table.setItem(row, 4, size_item)
            
            # Datum
            released_at = release.get('released_at', '')
            if released_at:
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(released_at.replace('Z', '+00:00'))
                    date_str = dt.strftime('%d.%m.%Y %H:%M')
                except (ValueError, TypeError):
                    date_str = released_at[:10] if len(released_at) >= 10 else released_at
            else:
                date_str = '-'
            date_item = QTableWidgetItem(date_str)
            date_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._releases_table.setItem(row, 5, date_item)
            
            # Erstellt von
            released_by = release.get('released_by_name', '-') or '-'
            self._releases_table.setItem(row, 6, QTableWidgetItem(released_by))
            
            # Aktionen
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(4, 2, 4, 2)
            actions_layout.setSpacing(6)
            
            edit_btn = QPushButton(texts.RELEASES_EDIT_BTN)
            edit_btn.setFixedHeight(26)
            edit_btn.setToolTip(texts.RELEASES_EDIT_TITLE)
            edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            edit_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {ACCENT_500};
                    color: white;
                    border: none;
                    border-radius: {RADIUS_SM};
                    padding: 2px 10px;
                    font-family: {FONT_BODY};
                    font-size: 12px;
                    font-weight: bold;
                }}
                QPushButton:hover {{ background-color: #e88a2d; }}
            """)
            edit_btn.clicked.connect(lambda checked, r=release: self._edit_release(r))
            actions_layout.addWidget(edit_btn)
            
            del_btn = QPushButton(texts.RELEASES_DELETE_BTN)
            del_btn.setFixedHeight(26)
            del_btn.setToolTip(texts.RELEASES_DELETE_CONFIRM)
            del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            del_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    color: #e74c3c;
                    border: 1px solid #e74c3c;
                    border-radius: {RADIUS_SM};
                    padding: 2px 10px;
                    font-family: {FONT_BODY};
                    font-size: 12px;
                }}
                QPushButton:hover {{
                    background-color: #e74c3c;
                    color: white;
                }}
            """)
            del_btn.clicked.connect(lambda checked, r=release: self._delete_release(r))
            actions_layout.addWidget(del_btn)
            
            actions_layout.addStretch()
            self._releases_table.setCellWidget(row, 7, actions_widget)
        
        self._releases_table.setSortingEnabled(True)
    
    def _new_release(self):
        """Oeffnet Dialog zum Hochladen eines neuen Releases."""
        dialog = ReleaseUploadDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        
        data = dialog.get_data()
        
        # Upload im Worker-Thread
        worker = UploadReleaseWorker(
            self._releases_api,
            file_path=data['file_path'],
            version=data['version'],
            channel=data['channel'],
            release_notes=data['release_notes'],
            min_version=data['min_version']
        )
        worker.finished.connect(self._on_release_uploaded)
        worker.error.connect(self._on_release_upload_error)
        self._active_workers.append(worker)
        
        # Einfacher "Wird hochgeladen..." Hinweis
        self._toast_manager.show_info(texts.RELEASES_UPLOADING)
        worker.start()
    
    def _on_release_uploaded(self, release: dict):
        """Release erfolgreich hochgeladen."""
        version = release.get('version', '?')
        self._toast_manager.show_success(texts.RELEASES_UPLOAD_SUCCESS.format(version=version))
        self._load_releases()
    
    def _on_release_upload_error(self, error: str):
        """Fehler beim Upload."""
        self._toast_manager.show_error(error)
    
    def _edit_release(self, release: dict):
        """Oeffnet Dialog zum Bearbeiten eines Releases."""
        dialog = ReleaseEditDialog(release, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        
        changes = dialog.get_changes()
        if not changes:
            return  # Nichts geaendert
        
        release_id = release.get('id')
        version = release.get('version', '?')
        
        try:
            self._releases_api.update_release(release_id, **changes)
            self._toast_manager.show_success(texts.RELEASES_UPDATE_SUCCESS.format(version=version))
            self._load_releases()
        except APIError as e:
            self._toast_manager.show_error(str(e))
    
    def _delete_release(self, release: dict):
        """Loescht ein Release oder setzt Status auf withdrawn."""
        release_id = release.get('id')
        version = release.get('version', '?')
        downloads = int(release.get('download_count', 0))
        
        if downloads > 0:
            # Kann nicht geloescht werden - auf withdrawn setzen?
            reply = QMessageBox.question(
                self, texts.WARNING,
                texts.RELEASES_DELETE_HAS_DOWNLOADS.format(version=version, count=downloads),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                try:
                    self._releases_api.update_release(release_id, status='withdrawn')
                    self._load_releases()
                except APIError as e:
                    self._toast_manager.show_error(str(e))
            return
        
        # Wirklich loeschen
        reply = QMessageBox.question(
            self, texts.WARNING,
            texts.RELEASES_DELETE_CONFIRM.format(version=version),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        try:
            self._releases_api.delete_release(release_id)
            self._toast_manager.show_success(texts.RELEASES_DELETE_SUCCESS.format(version=version))
            self._load_releases()
        except APIError as e:
            self._toast_manager.show_error(str(e))
    
    # ================================================================
    # Tab 6: Passwoerter
    # ================================================================
    
    def _create_passwords_tab(self) -> QWidget:
        """Erstellt den Passwoerter-Tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        
        # --- Header mit Titel und Aktionen ---
        header_layout = QHBoxLayout()
        
        title = QLabel(texts.PASSWORDS_TITLE)
        title.setStyleSheet(f"""
            font-family: {FONT_HEADLINE};
            font-size: {FONT_SIZE_H2};
            color: {PRIMARY_900};
            font-weight: bold;
        """)
        header_layout.addWidget(title)
        
        subtitle = QLabel(texts.PASSWORDS_SUBTITLE)
        subtitle.setStyleSheet(f"font-family: {FONT_BODY}; color: {PRIMARY_500}; margin-left: 12px;")
        header_layout.addWidget(subtitle)
        
        header_layout.addStretch()
        
        # Filter: Typ
        type_label = QLabel(texts.PASSWORD_TYPE)
        type_label.setStyleSheet(f"font-family: {FONT_BODY}; color: {PRIMARY_500};")
        header_layout.addWidget(type_label)
        
        self._pw_type_filter = QComboBox()
        self._pw_type_filter.addItem(texts.PASSWORDS_ALL, "all")
        self._pw_type_filter.addItem(texts.PASSWORDS_PDF, "pdf")
        self._pw_type_filter.addItem(texts.PASSWORDS_ZIP, "zip")
        self._pw_type_filter.setStyleSheet(f"font-family: {FONT_BODY};")
        self._pw_type_filter.currentIndexChanged.connect(self._apply_passwords_filter)
        header_layout.addWidget(self._pw_type_filter)
        
        # Hinzufuegen Button
        add_btn = QPushButton(f"+ {texts.PASSWORD_ADD}")
        add_btn.setStyleSheet(f"""
            QPushButton {{
                padding: 6px 16px;
                font-family: {FONT_BODY};
                background-color: {ACCENT_500};
                color: white;
                border: none;
                border-radius: {RADIUS_MD};
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #e88a2d;
            }}
        """)
        add_btn.clicked.connect(self._add_password)
        header_layout.addWidget(add_btn)
        
        # Aktualisieren Button
        refresh_btn = QPushButton(texts.COSTS_REFRESH)
        refresh_btn.setStyleSheet(f"""
            QPushButton {{
                padding: 6px 16px;
                font-family: {FONT_BODY};
                background-color: {ACCENT_100};
                color: {PRIMARY_900};
                border: 1px solid {ACCENT_500};
                border-radius: {RADIUS_MD};
            }}
            QPushButton:hover {{
                background-color: {ACCENT_500};
                color: white;
            }}
        """)
        refresh_btn.clicked.connect(self._load_passwords)
        header_layout.addWidget(refresh_btn)
        
        layout.addLayout(header_layout)
        
        # --- Passwoerter-Tabelle ---
        self._pw_table = QTableWidget()
        self._pw_table.setColumnCount(6)
        self._pw_table.setHorizontalHeaderLabels([
            texts.PASSWORD_TYPE,
            texts.PASSWORD_VALUE,
            texts.PASSWORD_DESCRIPTION,
            texts.PASSWORD_CREATED_AT,
            texts.PASSWORD_IS_ACTIVE,
            ""  # Aktionen
        ])
        self._pw_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._pw_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._pw_table.setAlternatingRowColors(True)
        self._pw_table.verticalHeader().setVisible(False)
        self._pw_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        
        # Spaltenbreiten
        header = self._pw_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(0, 60)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(3, 140)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(4, 60)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(5, 420)
        
        self._pw_table.setStyleSheet(f"""
            QTableWidget {{
                background-color: white;
                border: 1px solid {PRIMARY_100};
                border-radius: {RADIUS_SM};
                font-family: {FONT_BODY};
            }}
            QTableWidget::item {{
                padding: 6px;
            }}
            QHeaderView::section {{
                background-color: {PRIMARY_100};
                padding: 8px;
                border: none;
                font-family: {FONT_BODY};
                font-weight: bold;
                color: {PRIMARY_900};
            }}
        """)
        
        layout.addWidget(self._pw_table)
        
        # Interner State
        self._pw_data: List[Dict] = []
        self._pw_show_values: bool = False
        self._passwords_api = PasswordsAPI(self._api_client)
        
        return widget
    
    def _load_passwords(self):
        """Laedt alle Passwoerter vom Server."""
        try:
            pw_type = self._pw_type_filter.currentData()
            if pw_type == "all":
                self._pw_data = self._passwords_api.get_all_passwords()
            else:
                self._pw_data = self._passwords_api.get_all_passwords(pw_type)
            self._populate_pw_table()
        except APIError as e:
            logger.error(f"Fehler beim Laden der Passwoerter: {e}")
            self._toast_manager.show_error(texts.PASSWORD_ERROR_LOAD.format(error=str(e)))
    
    def _apply_passwords_filter(self):
        """Wendet den Typ-Filter an."""
        self._load_passwords()
    
    def _populate_pw_table(self):
        """Fuellt die Passwoerter-Tabelle."""
        self._pw_table.setRowCount(len(self._pw_data))
        self._pw_table.verticalHeader().setDefaultSectionSize(48)
        
        for row, pw in enumerate(self._pw_data):
            # Typ
            type_item = QTableWidgetItem(
                texts.PASSWORD_TYPE_PDF if pw.get('password_type') == 'pdf' else texts.PASSWORD_TYPE_ZIP
            )
            type_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            type_bg = QColor('#e8f5e9') if pw.get('password_type') == 'pdf' else QColor('#e3f2fd')
            type_item.setBackground(type_bg)
            self._pw_table.setItem(row, 0, type_item)
            
            # Passwort-Wert (maskiert oder angezeigt)
            value = pw.get('password_value', '')
            display_value = value if self._pw_show_values else '*' * min(len(value), 12)
            value_item = QTableWidgetItem(display_value)
            value_item.setFont(QFont("Consolas", 10))
            self._pw_table.setItem(row, 1, value_item)
            
            # Beschreibung
            desc_item = QTableWidgetItem(pw.get('description') or '-')
            self._pw_table.setItem(row, 2, desc_item)
            
            # Erstellt am
            created = pw.get('created_at', '')
            if created:
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(created)
                    created = dt.strftime('%d.%m.%Y %H:%M')
                except Exception:
                    pass
            created_item = QTableWidgetItem(created)
            created_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._pw_table.setItem(row, 3, created_item)
            
            # Aktiv
            active = pw.get('is_active')
            active_text = "Ja" if active and str(active) == '1' else "Nein"
            active_item = QTableWidgetItem(active_text)
            active_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if not (active and str(active) == '1'):
                active_item.setForeground(QColor('#e74c3c'))
            else:
                active_item.setForeground(QColor('#27ae60'))
            self._pw_table.setItem(row, 4, active_item)
            
            # Aktionen-Buttons
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(4, 2, 4, 2)
            actions_layout.setSpacing(4)
            
            # Anzeigen/Verbergen Toggle
            toggle_btn = QPushButton(texts.PASSWORD_SHOW if not self._pw_show_values else texts.PASSWORD_HIDE)
            toggle_btn.setFixedHeight(26)
            toggle_btn.setStyleSheet(f"""
                QPushButton {{
                    padding: 2px 8px;
                    font-family: {FONT_BODY};
                    font-size: {FONT_SIZE_CAPTION};
                    background-color: {PRIMARY_100};
                    color: {PRIMARY_900};
                    border: none;
                    border-radius: {RADIUS_SM};
                }}
                QPushButton:hover {{ background-color: {PRIMARY_500}; color: white; }}
            """)
            toggle_btn.clicked.connect(self._toggle_pw_visibility)
            actions_layout.addWidget(toggle_btn)
            
            # Bearbeiten
            edit_btn = QPushButton(texts.PASSWORD_EDIT)
            edit_btn.setFixedHeight(26)
            edit_btn.setStyleSheet(f"""
                QPushButton {{
                    padding: 2px 8px;
                    font-family: {FONT_BODY};
                    font-size: {FONT_SIZE_CAPTION};
                    background-color: {ACCENT_100};
                    color: {PRIMARY_900};
                    border: none;
                    border-radius: {RADIUS_SM};
                }}
                QPushButton:hover {{ background-color: {ACCENT_500}; color: white; }}
            """)
            pw_id = pw.get('id')
            edit_btn.clicked.connect(lambda checked=False, pid=pw_id: self._edit_password(pid))
            actions_layout.addWidget(edit_btn)
            
            # Loeschen/Reaktivieren
            is_active = active and str(active) == '1'
            if is_active:
                del_btn = QPushButton(texts.PASSWORD_DELETE)
                del_btn.setFixedHeight(26)
                del_btn.setStyleSheet(f"""
                    QPushButton {{
                        padding: 2px 8px;
                        font-family: {FONT_BODY};
                        font-size: {FONT_SIZE_CAPTION};
                        background-color: #ffebee;
                        color: #c62828;
                        border: none;
                        border-radius: {RADIUS_SM};
                    }}
                    QPushButton:hover {{ background-color: #e74c3c; color: white; }}
                """)
                del_btn.clicked.connect(lambda checked=False, pid=pw_id: self._delete_password(pid))
                actions_layout.addWidget(del_btn)
            else:
                react_btn = QPushButton(texts.PASSWORD_REACTIVATE)
                react_btn.setFixedHeight(26)
                react_btn.setStyleSheet(f"""
                    QPushButton {{
                        padding: 2px 8px;
                        font-family: {FONT_BODY};
                        font-size: {FONT_SIZE_CAPTION};
                        background-color: #e8f5e9;
                        color: #2e7d32;
                        border: none;
                        border-radius: {RADIUS_SM};
                    }}
                    QPushButton:hover {{ background-color: #27ae60; color: white; }}
                """)
                react_btn.clicked.connect(lambda checked=False, pid=pw_id: self._reactivate_password(pid))
                actions_layout.addWidget(react_btn)
            
            self._pw_table.setCellWidget(row, 5, actions_widget)
    
    def _toggle_pw_visibility(self):
        """Schaltet die Sichtbarkeit der Passwort-Werte um."""
        self._pw_show_values = not self._pw_show_values
        self._populate_pw_table()
    
    def _add_password(self):
        """Oeffnet Dialog zum Hinzufuegen eines neuen Passworts."""
        dialog = _PasswordDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            try:
                self._passwords_api.create_password(
                    data['password_type'],
                    data['password_value'],
                    data.get('description', '')
                )
                # Cache leeren damit neue Passwoerter verwendet werden
                from services.pdf_unlock import clear_password_cache
                clear_password_cache()
                self._load_passwords()
            except APIError as e:
                self._toast_manager.show_error(texts.PASSWORD_ERROR_SAVE.format(error=str(e)))
    
    def _edit_password(self, password_id: int):
        """Oeffnet Dialog zum Bearbeiten eines Passworts."""
        pw_data = None
        for pw in self._pw_data:
            if pw.get('id') == password_id:
                pw_data = pw
                break
        
        if not pw_data:
            return
        
        dialog = _PasswordDialog(self, pw_data)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            try:
                self._passwords_api.update_password(
                    password_id,
                    password_value=data.get('password_value'),
                    description=data.get('description')
                )
                from services.pdf_unlock import clear_password_cache
                clear_password_cache()
                self._load_passwords()
            except APIError as e:
                self._toast_manager.show_error(texts.PASSWORD_ERROR_SAVE.format(error=str(e)))
    
    def _delete_password(self, password_id: int):
        """Deaktiviert ein Passwort (Soft-Delete)."""
        pw_data = None
        for pw in self._pw_data:
            if pw.get('id') == password_id:
                pw_data = pw
                break
        
        if not pw_data:
            return
        
        reply = QMessageBox.question(
            self,
            texts.PASSWORD_CONFIRM_DELETE_TITLE,
            texts.PASSWORD_CONFIRM_DELETE.format(value=pw_data.get('password_value', '???')),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self._passwords_api.delete_password(password_id)
                from services.pdf_unlock import clear_password_cache
                clear_password_cache()
                self._load_passwords()
            except APIError as e:
                self._toast_manager.show_error(texts.PASSWORD_ERROR_SAVE.format(error=str(e)))
    
    def _reactivate_password(self, password_id: int):
        """Reaktiviert ein deaktiviertes Passwort."""
        try:
            self._passwords_api.update_password(password_id, is_active=True)
            from services.pdf_unlock import clear_password_cache
            clear_password_cache()
            self._load_passwords()
        except APIError as e:
            self._toast_manager.show_error(texts.PASSWORD_ERROR_SAVE.format(error=str(e)))
    
    # ================================================================
    # Tab-Wechsel
    # ================================================================
    
    def _navigate_to(self, index: int):
        """Navigiert zu einem Admin-Bereich (Sidebar-Klick)."""
        # NavButtons aktualisieren
        for i, btn in enumerate(self._nav_buttons):
            btn.setChecked(i == index)
        
        # Content anzeigen
        self._content_stack.setCurrentIndex(index)
        
        # Daten laden
        self._on_panel_changed(index)
    
    def _on_panel_changed(self, index: int):
        """Laedt Daten beim Panel-Wechsel.
        
        Index-Zuordnung (nach Sidebar-Reihenfolge):
        0 = Nutzerverwaltung
        1 = Sessions
        2 = Passwoerter
        3 = Aktivitaetslog
        4 = KI-Kosten
        5 = Releases
        6 = KI-Klassifikation (Verarbeitung)
        7 = KI-Provider
        8 = Modell-Preise
        9 = Dokumenten-Regeln
        10 = E-Mail-Konten
        11 = SmartScan Einstellungen
        12 = SmartScan Historie
        13 = E-Mail Posteingang
        14 = Mitteilungen
        """
        # Sessions-Timer nur wenn Sessions aktiv
        if index == 1:
            self._load_sessions()
            self._session_timer.start()
        else:
            self._session_timer.stop()
        
        if index == 2:
            self._load_passwords()
        
        if index == 3:
            self._activity_page = 1
            self._load_activity()
        
        if index == 4:
            self._load_cost_data()
        
        if index == 5:
            self._load_releases()
        
        if index == 6:
            self._load_ai_classification_settings()
        
        if index == 7:
            self._load_ai_providers()
        
        if index == 8:
            self._load_model_pricing()
        
        if index == 9:
            self._load_document_rules()
        
        if index == 10:
            self._load_email_accounts()
        
        if index == 11:
            self._load_smartscan_settings()
        
        if index == 12:
            self._load_smartscan_history()
        
        if index == 13:
            self._load_email_inbox()
        
        if index == 14:
            self._load_admin_messages()

    # ================================================================
    # Tab: Dokumenten-Regeln (Verarbeitung)
    # ================================================================
    
    def _create_document_rules_tab(self) -> QWidget:
        """Erstellt das Dokumenten-Regeln Panel mit 4 Regel-Sektionen."""
        from i18n import de as texts
        from ui.styles.tokens import ACCENT_500
        
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        
        # Titel
        title = QLabel(texts.DOC_RULES_TITLE)
        title.setFont(QFont("Open Sans", 16, QFont.Weight.Bold))
        layout.addWidget(title)
        
        desc = QLabel(texts.DOC_RULES_DESCRIPTION)
        desc.setFont(QFont("Open Sans", 10))
        desc.setStyleSheet(f"color: #64748b;")
        desc.setWordWrap(True)
        layout.addWidget(desc)
        
        # Scroll-Bereich fuer die 4 Sektionen
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setSpacing(16)
        
        # Farb-Optionen fuer Dropdowns
        color_items = [
            ('green', texts.DOC_RULES_COLOR_GREEN),
            ('red', texts.DOC_RULES_COLOR_RED),
            ('blue', texts.DOC_RULES_COLOR_BLUE),
            ('orange', texts.DOC_RULES_COLOR_ORANGE),
            ('purple', texts.DOC_RULES_COLOR_PURPLE),
            ('pink', texts.DOC_RULES_COLOR_PINK),
            ('cyan', texts.DOC_RULES_COLOR_CYAN),
            ('yellow', texts.DOC_RULES_COLOR_YELLOW),
        ]
        
        def create_rule_section(title_text: str, desc_text: str,
                                action_items: list, color_items_list: list):
            """Erstellt eine Regel-Sektion mit Aktion-Dropdown + Farb-Dropdown."""
            group = QGroupBox(title_text)
            group.setFont(QFont("Open Sans", 11, QFont.Weight.DemiBold))
            group.setStyleSheet(f"""
                QGroupBox {{
                    border: 1px solid #e2e8f0;
                    border-radius: 8px;
                    margin-top: 12px;
                    padding: 16px 12px 12px 12px;
                    background: white;
                }}
                QGroupBox::title {{
                    subcontrol-origin: margin;
                    left: 12px;
                    padding: 0 6px;
                }}
            """)
            g_layout = QVBoxLayout(group)
            g_layout.setSpacing(8)
            
            desc_label = QLabel(desc_text)
            desc_label.setFont(QFont("Open Sans", 9))
            desc_label.setStyleSheet("color: #64748b; border: none;")
            desc_label.setWordWrap(True)
            g_layout.addWidget(desc_label)
            
            # Aktion
            action_row = QHBoxLayout()
            action_label = QLabel(texts.DOC_RULES_ACTION_LABEL)
            action_label.setFixedWidth(80)
            action_label.setStyleSheet("border: none;")
            action_combo = QComboBox()
            for value, display in action_items:
                action_combo.addItem(display, value)
            action_combo.setMinimumWidth(250)
            action_row.addWidget(action_label)
            action_row.addWidget(action_combo)
            action_row.addStretch()
            g_layout.addLayout(action_row)
            
            # Farbe (initial versteckt)
            color_row = QHBoxLayout()
            color_label = QLabel(texts.DOC_RULES_COLOR_LABEL)
            color_label.setFixedWidth(80)
            color_label.setStyleSheet("border: none;")
            color_combo = QComboBox()
            for value, display in color_items_list:
                color_combo.addItem(display, value)
            color_combo.setMinimumWidth(250)
            color_row.addWidget(color_label)
            color_row.addWidget(color_combo)
            color_row.addStretch()
            
            color_container = QWidget()
            color_container.setLayout(color_row)
            color_container.setStyleSheet("border: none;")
            color_container.setVisible(False)
            g_layout.addWidget(color_container)
            
            def on_action_changed(idx):
                val = action_combo.itemData(idx)
                needs_color = val in ('color_both', 'color_new', 'color_file')
                color_container.setVisible(needs_color)
            
            action_combo.currentIndexChanged.connect(on_action_changed)
            
            return group, action_combo, color_combo, color_container
        
        # 1. Datei-Duplikate
        dup_actions = [
            ('none', texts.DOC_RULES_ACTION_NONE),
            ('color_both', texts.DOC_RULES_ACTION_COLOR_BOTH),
            ('color_new', texts.DOC_RULES_ACTION_COLOR_NEW),
            ('delete_new', texts.DOC_RULES_ACTION_DELETE_NEW),
            ('delete_old', texts.DOC_RULES_ACTION_DELETE_OLD),
        ]
        
        grp1, self._dr_file_dup_action, self._dr_file_dup_color, _ = create_rule_section(
            texts.DOC_RULES_FILE_DUP_TITLE, texts.DOC_RULES_FILE_DUP_DESC,
            dup_actions, color_items)
        scroll_layout.addWidget(grp1)
        
        # 2. Inhaltsduplikate
        grp2, self._dr_content_dup_action, self._dr_content_dup_color, _ = create_rule_section(
            texts.DOC_RULES_CONTENT_DUP_TITLE, texts.DOC_RULES_CONTENT_DUP_DESC,
            dup_actions, color_items)
        scroll_layout.addWidget(grp2)
        
        # 3. Teilweise leere Seiten
        partial_actions = [
            ('none', texts.DOC_RULES_ACTION_NONE),
            ('remove_pages', texts.DOC_RULES_ACTION_REMOVE_PAGES),
            ('color_file', texts.DOC_RULES_ACTION_COLOR_FILE),
        ]
        
        grp3, self._dr_partial_empty_action, self._dr_partial_empty_color, _ = create_rule_section(
            texts.DOC_RULES_PARTIAL_EMPTY_TITLE, texts.DOC_RULES_PARTIAL_EMPTY_DESC,
            partial_actions, color_items)
        scroll_layout.addWidget(grp3)
        
        # 4. Komplett leere Dateien
        full_actions = [
            ('none', texts.DOC_RULES_ACTION_NONE),
            ('delete', texts.DOC_RULES_ACTION_DELETE),
            ('color_file', texts.DOC_RULES_ACTION_COLOR_FILE),
        ]
        
        grp4, self._dr_full_empty_action, self._dr_full_empty_color, _ = create_rule_section(
            texts.DOC_RULES_FULL_EMPTY_TITLE, texts.DOC_RULES_FULL_EMPTY_DESC,
            full_actions, color_items)
        scroll_layout.addWidget(grp4)
        
        scroll_layout.addStretch()
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)
        
        # Speichern-Button
        save_btn = QPushButton(texts.DOC_RULES_SAVE)
        save_btn.setMinimumHeight(36)
        save_btn.setMaximumWidth(200)
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ACCENT_500};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 600;
            }}
            QPushButton:hover {{ background-color: #e67e22; }}
        """)
        save_btn.clicked.connect(self._save_document_rules)
        layout.addWidget(save_btn)
        
        # Status-Label
        self._dr_status = QLabel("")
        self._dr_status.setVisible(False)
        self._dr_status.setWordWrap(True)
        layout.addWidget(self._dr_status)
        
        return widget
    
    def _load_document_rules(self):
        """Laedt die Dokumenten-Regeln vom Server und setzt die UI-Werte."""
        from api.document_rules import DocumentRulesAPI
        try:
            api = DocumentRulesAPI(self._api_client)
            settings = api.get_rules()
            
            self._set_combo_by_data(self._dr_file_dup_action, settings.file_dup_action)
            self._set_combo_by_data(self._dr_file_dup_color, settings.file_dup_color or 'green')
            self._set_combo_by_data(self._dr_content_dup_action, settings.content_dup_action)
            self._set_combo_by_data(self._dr_content_dup_color, settings.content_dup_color or 'green')
            self._set_combo_by_data(self._dr_partial_empty_action, settings.partial_empty_action)
            self._set_combo_by_data(self._dr_partial_empty_color, settings.partial_empty_color or 'orange')
            self._set_combo_by_data(self._dr_full_empty_action, settings.full_empty_action)
            self._set_combo_by_data(self._dr_full_empty_color, settings.full_empty_color or 'red')
        except Exception as e:
            from i18n.de import DOC_RULES_LOAD_ERROR
            logger.error(f"Dokumenten-Regeln laden fehlgeschlagen: {e}")
            self._dr_status.setText(DOC_RULES_LOAD_ERROR)
            self._dr_status.setStyleSheet(
                "color: #dc2626; background: #fef2f2; padding: 6px 12px; border-radius: 4px;")
            self._dr_status.setVisible(True)
    
    def _set_combo_by_data(self, combo: QComboBox, value: str):
        """Setzt eine QComboBox auf den Eintrag mit dem gegebenen Data-Wert."""
        for i in range(combo.count()):
            if combo.itemData(i) == value:
                combo.setCurrentIndex(i)
                return
    
    def _save_document_rules(self):
        """Speichert die Dokumenten-Regeln auf dem Server."""
        from api.document_rules import DocumentRulesAPI, DocumentRulesSettings
        from i18n.de import DOC_RULES_SAVE_SUCCESS, DOC_RULES_SAVE_ERROR
        
        settings = DocumentRulesSettings(
            file_dup_action=self._dr_file_dup_action.currentData() or 'none',
            file_dup_color=self._dr_file_dup_color.currentData() if self._dr_file_dup_action.currentData() in ('color_both', 'color_new') else None,
            content_dup_action=self._dr_content_dup_action.currentData() or 'none',
            content_dup_color=self._dr_content_dup_color.currentData() if self._dr_content_dup_action.currentData() in ('color_both', 'color_new') else None,
            partial_empty_action=self._dr_partial_empty_action.currentData() or 'none',
            partial_empty_color=self._dr_partial_empty_color.currentData() if self._dr_partial_empty_action.currentData() == 'color_file' else None,
            full_empty_action=self._dr_full_empty_action.currentData() or 'none',
            full_empty_color=self._dr_full_empty_color.currentData() if self._dr_full_empty_action.currentData() == 'color_file' else None,
        )
        
        try:
            api = DocumentRulesAPI(self._api_client)
            success = api.save_rules(settings)
            if success:
                self._dr_status.setText(DOC_RULES_SAVE_SUCCESS)
                self._dr_status.setStyleSheet(
                    "color: #059669; background: #ecfdf5; padding: 6px 12px; border-radius: 4px;")
            else:
                self._dr_status.setText(DOC_RULES_SAVE_ERROR.format(error="Server-Fehler"))
                self._dr_status.setStyleSheet(
                    "color: #dc2626; background: #fef2f2; padding: 6px 12px; border-radius: 4px;")
        except Exception as e:
            self._dr_status.setText(DOC_RULES_SAVE_ERROR.format(error=str(e)))
            self._dr_status.setStyleSheet(
                "color: #dc2626; background: #fef2f2; padding: 6px 12px; border-radius: 4px;")
        self._dr_status.setVisible(True)

    # ================================================================
    # Tab: KI-Klassifikation (Verarbeitung)
    # ================================================================
    
    def _create_ai_classification_tab(self) -> QWidget:
        """Erstellt das KI-Klassifikation Panel mit Pipeline-Visualisierung + Prompt-Editor."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(SPACING_MD)
        
        # Toolbar
        toolbar = QHBoxLayout()
        title = QLabel(texts.PROCESSING_AI_TITLE)
        title.setFont(QFont(FONT_HEADLINE, 18))
        title.setStyleSheet(f"color: {PRIMARY_900};")
        toolbar.addWidget(title)
        toolbar.addStretch()
        
        self._btn_ai_save = QPushButton(texts.PROCESSING_AI_SAVE)
        self._btn_ai_save.setStyleSheet(get_button_primary_style())
        self._btn_ai_save.setCursor(Qt.PointingHandCursor)
        self._btn_ai_save.clicked.connect(self._save_ai_classification_settings)
        toolbar.addWidget(self._btn_ai_save)
        
        layout.addLayout(toolbar)
        
        subtitle = QLabel(texts.PROCESSING_AI_SUBTITLE)
        subtitle.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: {FONT_SIZE_BODY};")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)
        
        # Provider-Info-Banner
        self._ai_provider_banner = QLabel(texts.AI_CLASSIFICATION_NO_PROVIDER)
        self._ai_provider_banner.setWordWrap(True)
        self._ai_provider_banner.setStyleSheet(f"""
            QLabel {{
                background-color: {ACCENT_100};
                border: 1px solid {ACCENT_500};
                border-radius: {RADIUS_SM};
                padding: 8px 12px;
                color: {PRIMARY_900};
                font-size: {FONT_SIZE_BODY};
            }}
        """)
        layout.addWidget(self._ai_provider_banner)
        
        # Scrollbarer Inhalt
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(SPACING_MD)
        
        # ---- Bereich A: Statische Pipeline-Visualisierung ----
        pipeline_group = QFrame()
        pipeline_group.setStyleSheet(f"""
            QFrame {{
                background-color: {PRIMARY_100};
                border-radius: {RADIUS_MD};
                padding: 16px;
            }}
        """)
        pipeline_layout = QVBoxLayout(pipeline_group)
        pipeline_layout.setSpacing(SPACING_SM)
        
        pipeline_title = QLabel(texts.PROCESSING_AI_PIPELINE_TITLE)
        pipeline_title.setFont(QFont(FONT_HEADLINE, 14))
        pipeline_title.setStyleSheet(f"color: {PRIMARY_900}; background: transparent;")
        pipeline_layout.addWidget(pipeline_title)
        
        # Pipeline-Schritte als Flow-Karten
        steps = [
            (texts.PROCESSING_AI_STEP_XML, texts.PROCESSING_AI_STEP_XML_DESC, "Roh-Archiv"),
            (texts.PROCESSING_AI_STEP_GDV_BIPRO, texts.PROCESSING_AI_STEP_GDV_BIPRO_DESC, "GDV-Box"),
            (texts.PROCESSING_AI_STEP_GDV_EXT, texts.PROCESSING_AI_STEP_GDV_EXT_DESC, "GDV-Box"),
            (texts.PROCESSING_AI_STEP_PDF_VALIDATE, texts.PROCESSING_AI_STEP_PDF_VALIDATE_DESC, None),
            (texts.PROCESSING_AI_STEP_COURTAGE, texts.PROCESSING_AI_STEP_COURTAGE_DESC, "Courtage-Box"),
        ]
        
        for step_title, step_desc, target in steps:
            step_frame = QFrame()
            step_frame.setStyleSheet(f"""
                QFrame {{
                    background-color: {PRIMARY_0};
                    border: 1px solid {PRIMARY_500};
                    border-radius: {RADIUS_SM};
                    padding: 8px 12px;
                }}
            """)
            step_row = QHBoxLayout(step_frame)
            step_row.setContentsMargins(8, 4, 8, 4)
            
            step_lbl = QLabel(f"<b>{step_title}</b>")
            step_lbl.setStyleSheet(f"color: {PRIMARY_900}; background: transparent; border: none;")
            step_row.addWidget(step_lbl)
            
            desc_lbl = QLabel(step_desc)
            desc_lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; background: transparent; border: none;")
            step_row.addWidget(desc_lbl)
            step_row.addStretch()
            
            if target:
                target_lbl = QLabel(f"→ {target}")
                target_lbl.setStyleSheet(f"color: {ACCENT_500}; font-weight: bold; background: transparent; border: none;")
                step_row.addWidget(target_lbl)
            
            pipeline_layout.addWidget(step_frame)
        
        # Uebergangs-Pfeil
        transition = QLabel(f"▼  {texts.PROCESSING_AI_STEP_KI_TRANSITION} → {texts.PROCESSING_AI_ARROW_LABEL}")
        transition.setAlignment(Qt.AlignCenter)
        transition.setStyleSheet(f"color: {ACCENT_500}; font-size: 14px; font-weight: bold; padding: 8px; background: transparent;")
        pipeline_layout.addWidget(transition)
        
        scroll_layout.addWidget(pipeline_group)
        
        # ---- Bereich B: Stufe 1 ----
        stage1_group = QFrame()
        stage1_group.setStyleSheet(f"""
            QFrame {{
                background-color: {PRIMARY_0};
                border: 2px solid {ACCENT_500};
                border-radius: {RADIUS_MD};
                padding: 16px;
            }}
        """)
        stage1_layout = QVBoxLayout(stage1_group)
        stage1_layout.setSpacing(SPACING_SM)
        
        s1_header = QHBoxLayout()
        s1_title = QLabel(texts.PROCESSING_AI_STAGE1_TITLE)
        s1_title.setFont(QFont(FONT_HEADLINE, 14))
        s1_title.setStyleSheet(f"color: {PRIMARY_900}; border: none;")
        s1_header.addWidget(s1_title)
        s1_header.addStretch()
        s1_badge = QLabel(texts.PROCESSING_AI_STAGE1_ALWAYS_ACTIVE)
        s1_badge.setStyleSheet(f"color: {SUCCESS}; font-size: {FONT_SIZE_CAPTION}; border: none;")
        s1_header.addWidget(s1_badge)
        stage1_layout.addLayout(s1_header)
        
        s1_desc = QLabel(texts.PROCESSING_AI_STAGE1_DESC)
        s1_desc.setStyleSheet(f"color: {TEXT_SECONDARY}; border: none;")
        stage1_layout.addWidget(s1_desc)
        
        # Model + Max Tokens
        s1_row = QHBoxLayout()
        s1_row.addWidget(QLabel(texts.PROCESSING_AI_STAGE_MODEL))
        self._ai_s1_model = QComboBox()
        self._ai_s1_model.setMinimumWidth(250)
        self._ai_s1_model.setStyleSheet("border: 1px solid #ccc; padding: 4px;")
        s1_row.addWidget(self._ai_s1_model)
        s1_row.addSpacing(20)
        s1_row.addWidget(QLabel(texts.PROCESSING_AI_STAGE_MAX_TOKENS))
        self._ai_s1_max_tokens = QSpinBox()
        self._ai_s1_max_tokens.setRange(50, 4096)
        self._ai_s1_max_tokens.setValue(150)
        self._ai_s1_max_tokens.setStyleSheet("border: 1px solid #ccc; padding: 4px;")
        s1_row.addWidget(self._ai_s1_max_tokens)
        s1_row.addStretch()
        stage1_layout.addLayout(s1_row)
        
        # Version Dropdown + Save As
        s1_version_row = QHBoxLayout()
        s1_version_row.addWidget(QLabel(texts.PROCESSING_AI_STAGE_VERSION))
        self._ai_s1_version = QComboBox()
        self._ai_s1_version.setMinimumWidth(300)
        self._ai_s1_version.setStyleSheet("border: 1px solid #ccc; padding: 4px;")
        self._ai_s1_version.currentIndexChanged.connect(self._on_s1_version_changed)
        s1_version_row.addWidget(self._ai_s1_version)
        self._btn_s1_save_version = QPushButton(texts.PROCESSING_AI_VERSION_SAVE_AS)
        self._btn_s1_save_version.setStyleSheet(get_button_secondary_style())
        self._btn_s1_save_version.setCursor(Qt.PointingHandCursor)
        self._btn_s1_save_version.clicked.connect(lambda: self._save_prompt_version('stage1'))
        s1_version_row.addWidget(self._btn_s1_save_version)
        s1_version_row.addStretch()
        stage1_layout.addLayout(s1_version_row)
        
        # Prompt Editor
        prompt_label = QLabel(texts.PROCESSING_AI_STAGE_PROMPT)
        prompt_label.setStyleSheet("border: none;")
        stage1_layout.addWidget(prompt_label)
        self._ai_s1_prompt = QPlainTextEdit()
        self._ai_s1_prompt.setMinimumHeight(200)
        self._ai_s1_prompt.setMaximumHeight(400)
        self._ai_s1_prompt.setFont(QFont("Consolas", 10))
        self._ai_s1_prompt.setStyleSheet(f"border: 1px solid #ccc; border-radius: {RADIUS_SM}; padding: 8px;")
        stage1_layout.addWidget(self._ai_s1_prompt)
        
        scroll_layout.addWidget(stage1_group)
        
        # ---- Uebergang: Confidence -> Stufe 2 ----
        transition2 = QLabel(f"▼  {texts.PROCESSING_AI_TRANSITION_LABEL.format(trigger='low')}")
        transition2.setAlignment(Qt.AlignCenter)
        transition2.setStyleSheet(f"color: {ACCENT_500}; font-size: 14px; font-weight: bold; padding: 8px;")
        self._ai_transition_label = transition2
        scroll_layout.addWidget(transition2)
        
        # ---- Bereich C: Stufe 2 ----
        stage2_group = QFrame()
        stage2_group.setStyleSheet(f"""
            QFrame {{
                background-color: {PRIMARY_0};
                border: 2px solid {PRIMARY_500};
                border-radius: {RADIUS_MD};
                padding: 16px;
            }}
        """)
        self._ai_stage2_group = stage2_group
        stage2_layout = QVBoxLayout(stage2_group)
        stage2_layout.setSpacing(SPACING_SM)
        
        s2_header = QHBoxLayout()
        s2_title = QLabel(texts.PROCESSING_AI_STAGE2_TITLE)
        s2_title.setFont(QFont(FONT_HEADLINE, 14))
        s2_title.setStyleSheet(f"color: {PRIMARY_900}; border: none;")
        s2_header.addWidget(s2_title)
        s2_header.addStretch()
        self._ai_s2_enabled = QCheckBox(texts.PROCESSING_AI_STAGE2_ENABLED)
        self._ai_s2_enabled.setChecked(True)
        self._ai_s2_enabled.setStyleSheet("border: none;")
        self._ai_s2_enabled.toggled.connect(self._on_s2_enabled_toggled)
        s2_header.addWidget(self._ai_s2_enabled)
        stage2_layout.addLayout(s2_header)
        
        s2_desc = QLabel(texts.PROCESSING_AI_STAGE2_DESC)
        s2_desc.setStyleSheet(f"color: {TEXT_SECONDARY}; border: none;")
        stage2_layout.addWidget(s2_desc)
        
        # Disabled-Info (nur sichtbar wenn deaktiviert)
        self._ai_s2_disabled_info = QLabel(texts.PROCESSING_AI_STAGE2_DISABLED_INFO)
        self._ai_s2_disabled_info.setStyleSheet(f"color: {STATUS_COLORS['denied']}; font-style: italic; padding: 8px; border: none;")
        self._ai_s2_disabled_info.setWordWrap(True)
        self._ai_s2_disabled_info.setVisible(False)
        stage2_layout.addWidget(self._ai_s2_disabled_info)
        
        # Container fuer editierbare Felder (ein/ausblendbar)
        self._ai_s2_fields = QWidget()
        s2_fields_layout = QVBoxLayout(self._ai_s2_fields)
        s2_fields_layout.setContentsMargins(0, 0, 0, 0)
        s2_fields_layout.setSpacing(SPACING_SM)
        
        # Trigger
        s2_trigger_row = QHBoxLayout()
        s2_trigger_row.addWidget(QLabel(texts.PROCESSING_AI_STAGE2_TRIGGER))
        self._ai_s2_trigger = QComboBox()
        self._ai_s2_trigger.addItem(texts.PROCESSING_AI_STAGE2_TRIGGER_LOW, "low")
        self._ai_s2_trigger.addItem(texts.PROCESSING_AI_STAGE2_TRIGGER_LOW_MEDIUM, "low_medium")
        self._ai_s2_trigger.setStyleSheet("border: 1px solid #ccc; padding: 4px;")
        self._ai_s2_trigger.currentIndexChanged.connect(self._on_s2_trigger_changed)
        s2_trigger_row.addWidget(self._ai_s2_trigger)
        s2_trigger_row.addStretch()
        s2_fields_layout.addLayout(s2_trigger_row)
        
        # Model + Max Tokens
        s2_row = QHBoxLayout()
        s2_row.addWidget(QLabel(texts.PROCESSING_AI_STAGE_MODEL))
        self._ai_s2_model = QComboBox()
        self._ai_s2_model.setMinimumWidth(250)
        self._ai_s2_model.setStyleSheet("border: 1px solid #ccc; padding: 4px;")
        s2_row.addWidget(self._ai_s2_model)
        s2_row.addSpacing(20)
        s2_row.addWidget(QLabel(texts.PROCESSING_AI_STAGE_MAX_TOKENS))
        self._ai_s2_max_tokens = QSpinBox()
        self._ai_s2_max_tokens.setRange(50, 4096)
        self._ai_s2_max_tokens.setValue(200)
        self._ai_s2_max_tokens.setStyleSheet("border: 1px solid #ccc; padding: 4px;")
        s2_row.addWidget(self._ai_s2_max_tokens)
        s2_row.addStretch()
        s2_fields_layout.addLayout(s2_row)
        
        # Version Dropdown + Save As
        s2_version_row = QHBoxLayout()
        s2_version_row.addWidget(QLabel(texts.PROCESSING_AI_STAGE_VERSION))
        self._ai_s2_version = QComboBox()
        self._ai_s2_version.setMinimumWidth(300)
        self._ai_s2_version.setStyleSheet("border: 1px solid #ccc; padding: 4px;")
        self._ai_s2_version.currentIndexChanged.connect(self._on_s2_version_changed)
        s2_version_row.addWidget(self._ai_s2_version)
        self._btn_s2_save_version = QPushButton(texts.PROCESSING_AI_VERSION_SAVE_AS)
        self._btn_s2_save_version.setStyleSheet(get_button_secondary_style())
        self._btn_s2_save_version.setCursor(Qt.PointingHandCursor)
        self._btn_s2_save_version.clicked.connect(lambda: self._save_prompt_version('stage2'))
        s2_version_row.addWidget(self._btn_s2_save_version)
        s2_version_row.addStretch()
        s2_fields_layout.addLayout(s2_version_row)
        
        # Prompt Editor
        prompt2_label = QLabel(texts.PROCESSING_AI_STAGE_PROMPT)
        prompt2_label.setStyleSheet("border: none;")
        s2_fields_layout.addWidget(prompt2_label)
        self._ai_s2_prompt = QPlainTextEdit()
        self._ai_s2_prompt.setMinimumHeight(200)
        self._ai_s2_prompt.setMaximumHeight(400)
        self._ai_s2_prompt.setFont(QFont("Consolas", 10))
        self._ai_s2_prompt.setStyleSheet(f"border: 1px solid #ccc; border-radius: {RADIUS_SM}; padding: 8px;")
        s2_fields_layout.addWidget(self._ai_s2_prompt)
        
        stage2_layout.addWidget(self._ai_s2_fields)
        
        scroll_layout.addWidget(stage2_group)
        
        # ---- Bereich D: Ergebnis ----
        result_label = QLabel(f"▼  {texts.PROCESSING_AI_RESULT_TITLE}: {texts.PROCESSING_AI_RESULT_DESC}")
        result_label.setAlignment(Qt.AlignCenter)
        result_label.setStyleSheet(f"color: {SUCCESS}; font-size: 13px; padding: 12px;")
        result_label.setWordWrap(True)
        scroll_layout.addWidget(result_label)
        
        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)
        
        # Prompt-Versionen Cache
        self._ai_s1_versions: List[Dict] = []
        self._ai_s2_versions: List[Dict] = []
        
        return widget
    
    def _on_s2_enabled_toggled(self, checked: bool):
        """Toggle Stufe 2 aktiv/deaktiviert."""
        self._ai_s2_fields.setVisible(checked)
        self._ai_s2_disabled_info.setVisible(not checked)
        # Border-Farbe aendern
        if checked:
            self._ai_stage2_group.setStyleSheet(f"""
                QFrame {{
                    background-color: {PRIMARY_0};
                    border: 2px solid {PRIMARY_500};
                    border-radius: {RADIUS_MD};
                    padding: 16px;
                }}
            """)
        else:
            self._ai_stage2_group.setStyleSheet(f"""
                QFrame {{
                    background-color: {PRIMARY_100};
                    border: 2px dashed {PRIMARY_500};
                    border-radius: {RADIUS_MD};
                    padding: 16px;
                }}
            """)
    
    def _on_s2_trigger_changed(self, index: int):
        """Aktualisiert das Transition-Label wenn der Trigger geaendert wird."""
        trigger = self._ai_s2_trigger.currentData()
        if trigger == 'low_medium':
            self._ai_transition_label.setText(
                f"▼  {texts.PROCESSING_AI_TRANSITION_LABEL.format(trigger='low oder medium')}")
        else:
            self._ai_transition_label.setText(
                f"▼  {texts.PROCESSING_AI_TRANSITION_LABEL.format(trigger='low')}")
    
    def _on_s1_version_changed(self, index: int):
        """Laedt einen Stufe-1-Prompt aus der Version."""
        if index <= 0 or index > len(self._ai_s1_versions):
            return
        version = self._ai_s1_versions[index - 1]  # -1 wegen "Aktuell" Eintrag
        self._ai_s1_prompt.setPlainText(version.get('prompt_text', ''))
        model = version.get('model', '')
        idx = self._ai_s1_model.findText(model)
        if idx >= 0:
            self._ai_s1_model.setCurrentIndex(idx)
        mt = version.get('max_tokens', 150)
        self._ai_s1_max_tokens.setValue(int(mt))
    
    def _on_s2_version_changed(self, index: int):
        """Laedt einen Stufe-2-Prompt aus der Version."""
        if index <= 0 or index > len(self._ai_s2_versions):
            return
        version = self._ai_s2_versions[index - 1]
        self._ai_s2_prompt.setPlainText(version.get('prompt_text', ''))
        model = version.get('model', '')
        idx = self._ai_s2_model.findText(model)
        if idx >= 0:
            self._ai_s2_model.setCurrentIndex(idx)
        mt = version.get('max_tokens', 200)
        self._ai_s2_max_tokens.setValue(int(mt))
    
    def _load_ai_classification_settings(self):
        """Laedt KI-Einstellungen und Prompt-Versionen vom Server."""
        # Zuerst Provider-Info laden und Modell-Dropdowns aktualisieren
        self._refresh_ai_classification_provider_info()
        
        try:
            data = self._processing_settings_api.get_ai_settings_admin()
            settings = data.get('settings', {})
            
            if not settings:
                return
            
            # Stufe 1 befuellen
            s1_model = settings.get('stage1_model', 'openai/gpt-4o-mini')
            self._restore_model_selection(self._ai_s1_model, s1_model)
            
            self._ai_s1_max_tokens.setValue(int(settings.get('stage1_max_tokens', 150)))
            self._ai_s1_prompt.setPlainText(settings.get('stage1_prompt', ''))
            
            # Stufe 2 befuellen
            s2_enabled = settings.get('stage2_enabled')
            if isinstance(s2_enabled, str):
                s2_enabled = s2_enabled == '1'
            self._ai_s2_enabled.setChecked(bool(s2_enabled))
            
            s2_model = settings.get('stage2_model', 'openai/gpt-4o-mini')
            self._restore_model_selection(self._ai_s2_model, s2_model)
            
            self._ai_s2_max_tokens.setValue(int(settings.get('stage2_max_tokens', 200)))
            self._ai_s2_prompt.setPlainText(settings.get('stage2_prompt', ''))
            
            trigger = settings.get('stage2_trigger', 'low')
            trigger_idx = self._ai_s2_trigger.findData(trigger)
            if trigger_idx >= 0:
                self._ai_s2_trigger.setCurrentIndex(trigger_idx)
            
            # Versionen laden
            self._load_prompt_versions()
            
        except Exception as e:
            logger.error(f"KI-Settings laden fehlgeschlagen: {e}")
            from ui.toast import ToastManager
            ToastManager.instance().show_error(texts.PROCESSING_AI_LOAD_ERROR)
    
    def _refresh_ai_classification_provider_info(self):
        """Laedt aktiven Provider und aktualisiert Banner + Modell-Dropdowns."""
        try:
            provider_info = self._ai_providers_api.get_active_provider()
            if provider_info and provider_info.get('provider'):
                provider = provider_info['provider']
                name = provider_info.get('name', '')
                
                banner_text = texts.AI_CLASSIFICATION_PROVIDER_INFO.format(
                    provider=provider.capitalize(), name=name
                )
                if provider == 'openrouter':
                    banner_text += "\n" + texts.AI_CLASSIFICATION_PROVIDER_ALL_MODELS
                else:
                    banner_text += "\n" + texts.AI_CLASSIFICATION_PROVIDER_OPENAI_ONLY
                self._ai_provider_banner.setText(banner_text)
                
                self._update_model_dropdowns(provider)
            else:
                self._ai_provider_banner.setText(texts.AI_CLASSIFICATION_NO_PROVIDER)
                self._update_model_dropdowns('openrouter')
        except Exception as e:
            logger.warning(f"Provider-Info laden fehlgeschlagen: {e}")
            self._update_model_dropdowns('openrouter')
    
    def _update_model_dropdowns(self, provider: str):
        """Aktualisiert Modell-Auswahl basierend auf Provider."""
        from config.ai_models import get_models_for_provider
        
        models = get_models_for_provider(provider)
        
        current_s1 = self._ai_s1_model.currentText()
        current_s2 = self._ai_s2_model.currentText()
        
        for combo in [self._ai_s1_model, self._ai_s2_model]:
            combo.blockSignals(True)
            combo.clear()
            for m in models:
                combo.addItem(m["name"], m["id"])
            combo.blockSignals(False)
        
        if current_s1:
            self._restore_model_selection(self._ai_s1_model, current_s1)
        if current_s2:
            self._restore_model_selection(self._ai_s2_model, current_s2)
    
    def _restore_model_selection(self, combo: QComboBox, model_id: str):
        """Stellt Modell-Auswahl wieder her oder mappt auf Aequivalent."""
        from config.ai_models import find_equivalent_model
        
        # Direkte Uebereinstimmung nach data (id)
        idx = combo.findData(model_id)
        if idx >= 0:
            combo.setCurrentIndex(idx)
            return
        
        # Direkte Uebereinstimmung nach Text (name)
        idx = combo.findText(model_id)
        if idx >= 0:
            combo.setCurrentIndex(idx)
            return
        
        # Aequivalent suchen
        provider = 'openrouter'
        if combo.count() > 0:
            first_id = combo.itemData(0) or ''
            if '/' not in str(first_id):
                provider = 'openai'
        
        equivalent = find_equivalent_model(model_id, provider)
        idx = combo.findData(equivalent)
        if idx >= 0:
            combo.setCurrentIndex(idx)
            return
        
        # Fallback: Modell hinzufuegen falls es ein Custom-Modell ist
        if model_id:
            combo.addItem(model_id, model_id)
            combo.setCurrentIndex(combo.count() - 1)
    
    def _load_prompt_versions(self):
        """Laedt Prompt-Versionen fuer beide Stufen."""
        try:
            # Stage 1
            self._ai_s1_versions = self._processing_settings_api.get_prompt_versions('stage1')
            self._ai_s1_version.blockSignals(True)
            self._ai_s1_version.clear()
            self._ai_s1_version.addItem(texts.PROCESSING_AI_VERSION_CURRENT)
            for v in self._ai_s1_versions:
                label = v.get('label') or f"v{v.get('version_number', '?')}"
                is_default = v.get('is_default')
                if is_default:
                    label = f"{label} ({texts.PROCESSING_AI_VERSION_SYSTEM_DEFAULT})"
                self._ai_s1_version.addItem(label)
            self._ai_s1_version.setCurrentIndex(0)
            self._ai_s1_version.blockSignals(False)
            
            # Stage 2
            self._ai_s2_versions = self._processing_settings_api.get_prompt_versions('stage2')
            self._ai_s2_version.blockSignals(True)
            self._ai_s2_version.clear()
            self._ai_s2_version.addItem(texts.PROCESSING_AI_VERSION_CURRENT)
            for v in self._ai_s2_versions:
                label = v.get('label') or f"v{v.get('version_number', '?')}"
                is_default = v.get('is_default')
                if is_default:
                    label = f"{label} ({texts.PROCESSING_AI_VERSION_SYSTEM_DEFAULT})"
                self._ai_s2_version.addItem(label)
            self._ai_s2_version.setCurrentIndex(0)
            self._ai_s2_version.blockSignals(False)
            
        except Exception as e:
            logger.error(f"Prompt-Versionen laden fehlgeschlagen: {e}")
    
    def _save_ai_classification_settings(self):
        """Speichert KI-Einstellungen auf dem Server."""
        try:
            s1_model = self._ai_s1_model.currentData() or self._ai_s1_model.currentText()
            s2_model = self._ai_s2_model.currentData() or self._ai_s2_model.currentText()
            data = {
                'stage1_model': s1_model,
                'stage1_prompt': self._ai_s1_prompt.toPlainText(),
                'stage1_max_tokens': self._ai_s1_max_tokens.value(),
                'stage2_enabled': self._ai_s2_enabled.isChecked(),
                'stage2_model': s2_model,
                'stage2_prompt': self._ai_s2_prompt.toPlainText(),
                'stage2_max_tokens': self._ai_s2_max_tokens.value(),
                'stage2_trigger': self._ai_s2_trigger.currentData() or 'low',
            }
            
            self._processing_settings_api.save_ai_settings(data)
            
            from ui.toast import ToastManager
            ToastManager.instance().show_success(texts.PROCESSING_AI_SAVE_SUCCESS)
            
            # Versionen neu laden (neue Version koennte erstellt worden sein)
            self._load_prompt_versions()
            
        except Exception as e:
            logger.error(f"KI-Settings speichern fehlgeschlagen: {e}")
            from ui.toast import ToastManager
            ToastManager.instance().show_error(texts.PROCESSING_AI_SAVE_ERROR)
    
    def _save_prompt_version(self, stage: str):
        """Speichert den aktuellen Prompt als benannte Version."""
        from PySide6.QtWidgets import QInputDialog
        label, ok = QInputDialog.getText(
            self,
            texts.PROCESSING_AI_VERSION_SAVE_AS,
            texts.PROCESSING_AI_VERSION_LABEL,
        )
        if not ok:
            return
        
        try:
            if stage == 'stage1':
                prompt = self._ai_s1_prompt.toPlainText()
                model = self._ai_s1_model.currentData() or self._ai_s1_model.currentText()
                max_tokens = self._ai_s1_max_tokens.value()
            else:
                prompt = self._ai_s2_prompt.toPlainText()
                model = self._ai_s2_model.currentData() or self._ai_s2_model.currentText()
                max_tokens = self._ai_s2_max_tokens.value()
            
            # Speichern mit optionalem Label
            data = {
                f'{stage}_prompt': prompt,
                f'{stage}_model': model,
                f'{stage}_max_tokens': max_tokens,
                f'{stage}_version_label': label.strip() if label.strip() else None,
            }
            
            self._processing_settings_api.save_ai_settings(data)
            
            from ui.toast import ToastManager
            ToastManager.instance().show_success(texts.PROCESSING_AI_SAVE_SUCCESS)
            
            self._load_prompt_versions()
            
        except Exception as e:
            logger.error(f"Prompt-Version speichern fehlgeschlagen: {e}")
            from ui.toast import ToastManager
            ToastManager.instance().show_error(texts.PROCESSING_AI_SAVE_ERROR)
    
    # ================================================================
    # Tab 7: KI-Provider
    # ================================================================
    
    def _create_ai_providers_tab(self) -> QWidget:
        """Erstellt das KI-Provider-Panel (API-Key-Verwaltung)."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
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
        
        return widget
    
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
        for p in getattr(self, '_providers_data', []):
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
    
    # ================================================================
    # Tab 8: Modell-Preise
    # ================================================================
    
    def _create_model_pricing_tab(self) -> QWidget:
        """Erstellt das Modell-Preise-Panel."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(SPACING_LG, SPACING_LG, SPACING_LG, SPACING_LG)
        layout.setSpacing(SPACING_MD)
        
        # Header
        header = QHBoxLayout()
        title = QLabel(texts.MODEL_PRICING_TITLE)
        title.setFont(QFont(FONT_HEADLINE, 18))
        header.addWidget(title)
        header.addStretch()
        
        add_btn = QPushButton(texts.MODEL_PRICING_ADD)
        add_btn.setStyleSheet(get_button_primary_style())
        add_btn.setCursor(Qt.PointingHandCursor)
        add_btn.clicked.connect(self._show_add_pricing_dialog)
        header.addWidget(add_btn)
        layout.addLayout(header)
        
        # Hint
        hint_label = QLabel(texts.MODEL_PRICING_HINT)
        hint_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: {FONT_SIZE_CAPTION}; padding: 4px 0;")
        hint_label.setOpenExternalLinks(True)
        layout.addWidget(hint_label)
        
        # Tabelle
        self._pricing_table = QTableWidget()
        self._pricing_table.setColumnCount(7)
        self._pricing_table.setHorizontalHeaderLabels([
            texts.MODEL_PRICING_PROVIDER, texts.MODEL_PRICING_MODEL,
            texts.MODEL_PRICING_INPUT, texts.MODEL_PRICING_OUTPUT,
            texts.MODEL_PRICING_VALID_FROM, texts.MODEL_PRICING_IS_ACTIVE,
            texts.MODEL_PRICING_ACTIONS
        ])
        self._pricing_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._pricing_table.setColumnWidth(6, 220)
        self._pricing_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._pricing_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._pricing_table.verticalHeader().setVisible(False)
        self._pricing_table.setAlternatingRowColors(True)
        layout.addWidget(self._pricing_table)
        
        return widget
    
    def _load_model_pricing(self):
        """Laedt alle Modell-Preise vom Server."""
        def _do_load():
            return self._model_pricing_api.list_prices_admin()
        
        worker = AdminWriteWorker(_do_load)
        worker.finished.connect(self._on_pricing_loaded)
        worker.error.connect(lambda e: self._show_toast_error(f"Modell-Preise laden: {e}"))
        self._active_workers.append(worker)
        worker.start()
    
    def _on_pricing_loaded(self, prices):
        """Aktualisiert die Preise-Tabelle."""
        self._pricing_data = prices if prices else []
        table = self._pricing_table
        table.setRowCount(len(self._pricing_data))
        
        for row, p in enumerate(self._pricing_data):
            type_label = texts.AI_PROVIDER_OPENROUTER if p.provider == 'openrouter' else texts.AI_PROVIDER_OPENAI
            table.setItem(row, 0, QTableWidgetItem(type_label))
            table.setItem(row, 1, QTableWidgetItem(p.model_name))
            table.setItem(row, 2, QTableWidgetItem(f"${p.input_price_per_million:.4f}"))
            table.setItem(row, 3, QTableWidgetItem(f"${p.output_price_per_million:.4f}"))
            table.setItem(row, 4, QTableWidgetItem(p.valid_from))
            
            active_text = texts.AI_PROVIDER_ACTIVE if p.is_active else texts.AI_PROVIDER_INACTIVE
            active_item = QTableWidgetItem(active_text)
            if p.is_active:
                active_item.setForeground(QColor(STATUS_COLORS['success']))
            else:
                active_item.setForeground(QColor(STATUS_COLORS['error']))
            table.setItem(row, 5, active_item)
            
            # Aktions-Buttons
            actions = QWidget()
            actions_layout = QHBoxLayout(actions)
            actions_layout.setContentsMargins(4, 2, 4, 2)
            actions_layout.setSpacing(4)
            
            edit_btn = QPushButton(texts.MODEL_PRICING_EDIT)
            edit_btn.setStyleSheet(get_button_ghost_style())
            edit_btn.setCursor(Qt.PointingHandCursor)
            edit_btn.setFixedHeight(28)
            edit_btn.clicked.connect(lambda _, pid=p.id: self._show_edit_pricing_dialog(pid))
            actions_layout.addWidget(edit_btn)
            
            if p.is_active:
                deact_btn = QPushButton(texts.MODEL_PRICING_DEACTIVATE)
                deact_btn.setStyleSheet(get_button_ghost_style())
                deact_btn.setCursor(Qt.PointingHandCursor)
                deact_btn.setFixedHeight(28)
                deact_btn.clicked.connect(lambda _, pid=p.id, pmodel=p.model_name: self._deactivate_pricing(pid, pmodel))
                actions_layout.addWidget(deact_btn)
            
            table.setCellWidget(row, 6, actions)
        
        table.resizeRowsToContents()
    
    def _show_add_pricing_dialog(self):
        """Dialog zum Anlegen eines neuen Modell-Preises."""
        dialog = QDialog(self)
        dialog.setWindowTitle(texts.MODEL_PRICING_DIALOG_TITLE_NEW)
        dialog.setMinimumWidth(450)
        form = QFormLayout(dialog)
        
        provider_combo = QComboBox()
        provider_combo.addItem(texts.AI_PROVIDER_OPENROUTER, "openrouter")
        provider_combo.addItem(texts.AI_PROVIDER_OPENAI, "openai")
        form.addRow(texts.MODEL_PRICING_PROVIDER + ":", provider_combo)
        
        model_edit = QLineEdit()
        model_edit.setPlaceholderText("z.B. gpt-4o oder openai/gpt-4o")
        form.addRow(texts.MODEL_PRICING_MODEL + ":", model_edit)
        
        input_spin = QLineEdit()
        input_spin.setPlaceholderText("z.B. 2.50")
        form.addRow(texts.MODEL_PRICING_INPUT + ":", input_spin)
        
        output_spin = QLineEdit()
        output_spin.setPlaceholderText("z.B. 10.00")
        form.addRow(texts.MODEL_PRICING_OUTPUT + ":", output_spin)
        
        date_edit = QDateEdit()
        date_edit.setDate(QDate.currentDate())
        date_edit.setCalendarPopup(True)
        form.addRow(texts.MODEL_PRICING_VALID_FROM + ":", date_edit)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)
        
        if dialog.exec() == QDialog.Accepted:
            from ui.toast import ToastManager
            provider = provider_combo.currentData()
            model_name = model_edit.text().strip()
            try:
                input_price = float(input_spin.text().replace(',', '.'))
                output_price = float(output_spin.text().replace(',', '.'))
            except ValueError:
                ToastManager.instance().show_error("Ungueltige Preiseingabe")
                return
            valid_from = date_edit.date().toString("yyyy-MM-dd")
            
            if not model_name:
                return
            
            def _do_create():
                return self._model_pricing_api.create_price(
                    provider, model_name, input_price, output_price, valid_from
                )
            
            worker = AdminWriteWorker(_do_create)
            worker.finished.connect(lambda _: (
                ToastManager.instance().show_success(texts.MODEL_PRICING_CREATED.format(model=model_name)),
                self._load_model_pricing()
            ))
            worker.error.connect(lambda e: ToastManager.instance().show_error(str(e)))
            self._active_workers.append(worker)
            worker.start()
    
    def _show_edit_pricing_dialog(self, price_id: int):
        """Dialog zum Bearbeiten eines Modell-Preises."""
        price = None
        for p in getattr(self, '_pricing_data', []):
            if p.id == price_id:
                price = p
                break
        if not price:
            return
        
        dialog = QDialog(self)
        dialog.setWindowTitle(texts.MODEL_PRICING_DIALOG_TITLE_EDIT)
        dialog.setMinimumWidth(450)
        form = QFormLayout(dialog)
        
        model_edit = QLineEdit(price.model_name)
        form.addRow(texts.MODEL_PRICING_MODEL + ":", model_edit)
        
        input_edit = QLineEdit(str(price.input_price_per_million))
        form.addRow(texts.MODEL_PRICING_INPUT + ":", input_edit)
        
        output_edit = QLineEdit(str(price.output_price_per_million))
        form.addRow(texts.MODEL_PRICING_OUTPUT + ":", output_edit)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)
        
        if dialog.exec() == QDialog.Accepted:
            from ui.toast import ToastManager
            data = {}
            new_model = model_edit.text().strip()
            if new_model and new_model != price.model_name:
                data['model_name'] = new_model
            try:
                new_input = float(input_edit.text().replace(',', '.'))
                if new_input != price.input_price_per_million:
                    data['input_price_per_million'] = new_input
                new_output = float(output_edit.text().replace(',', '.'))
                if new_output != price.output_price_per_million:
                    data['output_price_per_million'] = new_output
            except ValueError:
                ToastManager.instance().show_error("Ungueltige Preiseingabe")
                return
            
            if not data:
                return
            
            def _do_update():
                return self._model_pricing_api.update_price(price_id, **data)
            
            worker = AdminWriteWorker(_do_update)
            worker.finished.connect(lambda _: (
                ToastManager.instance().show_success(texts.MODEL_PRICING_UPDATED),
                self._load_model_pricing()
            ))
            worker.error.connect(lambda e: ToastManager.instance().show_error(str(e)))
            self._active_workers.append(worker)
            worker.start()
    
    def _deactivate_pricing(self, price_id: int, model_name: str):
        """Modell-Preis deaktivieren nach Bestaetigung."""
        from ui.toast import ToastManager
        reply = QMessageBox.question(
            self, texts.MODEL_PRICING_DEACTIVATE,
            texts.MODEL_PRICING_CONFIRM_DELETE.format(model=model_name),
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return
        
        def _do_deactivate():
            return self._model_pricing_api.delete_price(price_id)
        
        worker = AdminWriteWorker(_do_deactivate)
        worker.finished.connect(lambda _: (
            ToastManager.instance().show_success(texts.MODEL_PRICING_DEACTIVATED),
            self._load_model_pricing()
        ))
        worker.error.connect(lambda e: ToastManager.instance().show_error(str(e)))
        self._active_workers.append(worker)
        worker.start()
    
    def _show_toast_error(self, msg: str):
        """Zeigt eine Fehler-Toast-Benachrichtigung."""
        from ui.toast import ToastManager
        ToastManager.instance().show_error(msg)
    
    # ================================================================
    # Tab 9: E-Mail-Konten (war Tab 8)
    # ================================================================
    
    def _create_email_accounts_tab(self) -> QWidget:
        """Erstellt den E-Mail-Konten-Tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
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
        ea_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)          # Kontoname
        self._ea_table.setColumnWidth(0, 160)
        ea_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)          # Typ
        self._ea_table.setColumnWidth(1, 80)
        ea_header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)  # SMTP-Server
        ea_header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # Absender
        ea_header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)          # Aktiv
        self._ea_table.setColumnWidth(4, 70)
        ea_header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)        # Aktionen
        self._ea_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._ea_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._ea_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._ea_table.verticalHeader().setVisible(False)
        self._ea_table.verticalHeader().setDefaultSectionSize(50)
        layout.addWidget(self._ea_table)
        
        self._ea_data: List[Dict] = []
        return widget
    
    def _load_email_accounts(self):
        """Laedt E-Mail-Konten vom Server."""
        try:
            self._ea_data = self._email_accounts_api.get_accounts()
            self._populate_email_accounts_table()
        except Exception as e:
            logger.error(f"Fehler beim Laden der E-Mail-Konten: {e}")
    
    def _derive_account_type(self, acc: Dict) -> str:
        """Leitet den Kontotyp aus vorhandenen Daten ab."""
        # Expliziter Typ vorhanden?
        if acc.get('account_type'):
            return acc['account_type']
        # Ableiten aus Host-Feldern
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
        dialog = _EmailAccountDialog(self)
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
        acc = dict(self._ea_data[row])  # Kopie um Original nicht zu veraendern
        # account_type ableiten wenn nicht in DB vorhanden
        if not acc.get('account_type'):
            acc['account_type'] = self._derive_account_type(acc)
        dialog = _EmailAccountDialog(self, existing_data=acc)
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

    # ================================================================
    # Tab 8: Smart!Scan Einstellungen
    # ================================================================
    
    def _create_smartscan_settings_tab(self) -> QWidget:
        """Erstellt den SmartScan-Einstellungen-Tab."""
        from PySide6.QtWidgets import QScrollArea, QSpinBox, QTextEdit, QCheckBox, QRadioButton, QButtonGroup
        
        widget = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        
        # === Versand-Sektion ===
        title = QLabel(texts.SMARTSCAN_SETTINGS_TITLE)
        title.setFont(QFont(FONT_HEADLINE, 18))
        title.setStyleSheet(f"color: {PRIMARY_900};")
        layout.addWidget(title)
        
        form = QFormLayout()
        form.setSpacing(10)
        
        # SmartScan aktiviert
        self._ss_enabled = QCheckBox(texts.SMARTSCAN_ENABLED)
        form.addRow("", self._ss_enabled)
        
        # E-Mail-Konto
        self._ss_email_account = QComboBox()
        form.addRow(texts.SMARTSCAN_EMAIL_ACCOUNT, self._ss_email_account)
        
        # Zieladresse
        self._ss_target = QLineEdit()
        self._ss_target.setPlaceholderText("scan@scs-smartscan.de")
        form.addRow(texts.SMARTSCAN_TARGET_ADDRESS, self._ss_target)
        
        # Betreff-Vorlage
        self._ss_subject = QLineEdit()
        self._ss_subject.setPlaceholderText("SmartScan - {box} - {date}")
        subject_help = QLabel(texts.SMARTSCAN_SUBJECT_HELP)
        subject_help.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: {FONT_SIZE_CAPTION};")
        form.addRow(texts.SMARTSCAN_SUBJECT_TEMPLATE, self._ss_subject)
        form.addRow("", subject_help)
        
        # Body-Vorlage
        self._ss_body = QTextEdit()
        self._ss_body.setMaximumHeight(100)
        self._ss_body.setPlaceholderText("Smart!Scan Versand - {count} Dokument(e)")
        form.addRow(texts.SMARTSCAN_BODY_TEMPLATE, self._ss_body)
        
        # Versandmodus
        mode_group = QButtonGroup(content)
        self._ss_mode_single = QRadioButton(texts.SMARTSCAN_MODE_SINGLE)
        self._ss_mode_batch = QRadioButton(texts.SMARTSCAN_MODE_BATCH)
        mode_group.addButton(self._ss_mode_single)
        mode_group.addButton(self._ss_mode_batch)
        self._ss_mode_single.setChecked(True)
        mode_widget = QWidget()
        mode_layout = QVBoxLayout(mode_widget)
        mode_layout.setContentsMargins(0, 0, 0, 0)
        mode_layout.addWidget(self._ss_mode_single)
        mode_layout.addWidget(self._ss_mode_batch)
        form.addRow(texts.SMARTSCAN_SEND_MODE, mode_widget)
        
        # Batch-Limits
        self._ss_max_attachments = QSpinBox()
        self._ss_max_attachments.setRange(1, 100)
        self._ss_max_attachments.setValue(20)
        form.addRow(texts.SMARTSCAN_BATCH_MAX_ATTACHMENTS, self._ss_max_attachments)
        
        self._ss_max_mb = QSpinBox()
        self._ss_max_mb.setRange(1, 100)
        self._ss_max_mb.setValue(25)
        form.addRow(texts.SMARTSCAN_BATCH_MAX_MB, self._ss_max_mb)
        
        # Post-Send Aktionen
        self._ss_archive = QCheckBox(texts.SMARTSCAN_ARCHIVE_AFTER_SEND)
        form.addRow("", self._ss_archive)
        
        recolor_widget = QWidget()
        recolor_layout = QHBoxLayout(recolor_widget)
        recolor_layout.setContentsMargins(0, 0, 0, 0)
        self._ss_recolor = QCheckBox(texts.SMARTSCAN_RECOLOR_AFTER_SEND)
        recolor_layout.addWidget(self._ss_recolor)
        self._ss_recolor_combo = QComboBox()
        from ui.styles.tokens import DOCUMENT_DISPLAY_COLORS
        for key, hex_color in DOCUMENT_DISPLAY_COLORS.items():
            self._ss_recolor_combo.addItem(key.capitalize(), key)
        recolor_layout.addWidget(self._ss_recolor_combo)
        recolor_layout.addStretch()
        form.addRow("", recolor_widget)
        
        layout.addLayout(form)
        
        # === IMAP-Import Sektion ===
        layout.addSpacing(20)
        imap_title = QLabel(texts.SMARTSCAN_IMAP_SECTION)
        imap_title.setFont(QFont(FONT_HEADLINE, 16))
        imap_title.setStyleSheet(f"color: {PRIMARY_900};")
        layout.addWidget(imap_title)
        
        imap_form = QFormLayout()
        imap_form.setSpacing(10)
        
        self._ss_imap_auto = QCheckBox(texts.SMARTSCAN_IMAP_AUTO_IMPORT)
        imap_form.addRow("", self._ss_imap_auto)
        
        self._ss_imap_account = QComboBox()
        imap_form.addRow(texts.SMARTSCAN_IMAP_ACCOUNT, self._ss_imap_account)
        
        # Filter-Modus
        filter_group = QButtonGroup(content)
        self._ss_imap_filter_all = QRadioButton(texts.SMARTSCAN_IMAP_FILTER_ALL)
        self._ss_imap_filter_keyword = QRadioButton(texts.SMARTSCAN_IMAP_FILTER_KEYWORD)
        filter_group.addButton(self._ss_imap_filter_all)
        filter_group.addButton(self._ss_imap_filter_keyword)
        self._ss_imap_filter_all.setChecked(True)
        filter_widget = QWidget()
        filter_layout = QVBoxLayout(filter_widget)
        filter_layout.setContentsMargins(0, 0, 0, 0)
        filter_layout.addWidget(self._ss_imap_filter_all)
        filter_layout.addWidget(self._ss_imap_filter_keyword)
        imap_form.addRow(texts.SMARTSCAN_IMAP_FILTER_MODE, filter_widget)
        
        self._ss_imap_keyword = QLineEdit()
        self._ss_imap_keyword.setText("ATLASabruf")
        imap_form.addRow(texts.SMARTSCAN_IMAP_KEYWORD, self._ss_imap_keyword)
        
        # Absender-Filter
        sender_group = QButtonGroup(content)
        self._ss_imap_sender_all = QRadioButton(texts.SMARTSCAN_IMAP_SENDER_ALL)
        self._ss_imap_sender_whitelist = QRadioButton(texts.SMARTSCAN_IMAP_SENDER_WHITELIST)
        sender_group.addButton(self._ss_imap_sender_all)
        sender_group.addButton(self._ss_imap_sender_whitelist)
        self._ss_imap_sender_all.setChecked(True)
        sender_widget = QWidget()
        sender_layout = QVBoxLayout(sender_widget)
        sender_layout.setContentsMargins(0, 0, 0, 0)
        sender_layout.addWidget(self._ss_imap_sender_all)
        sender_layout.addWidget(self._ss_imap_sender_whitelist)
        imap_form.addRow(texts.SMARTSCAN_IMAP_SENDER_MODE, sender_widget)
        
        self._ss_imap_senders = QTextEdit()
        self._ss_imap_senders.setMaximumHeight(80)
        self._ss_imap_senders.setPlaceholderText("info@example.com\nscanner@firma.de")
        imap_form.addRow(texts.SMARTSCAN_IMAP_ALLOWED_SENDERS, self._ss_imap_senders)
        
        # Info-Text
        info_label = QLabel(texts.SMARTSCAN_IMAP_INFO)
        info_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: {FONT_SIZE_CAPTION};")
        info_label.setWordWrap(True)
        imap_form.addRow("", info_label)
        
        layout.addLayout(imap_form)
        
        # Speichern-Button
        layout.addSpacing(20)
        save_btn = QPushButton(texts.SMARTSCAN_SETTINGS_SAVED.split('.')[0])
        save_btn.setText("Einstellungen speichern")
        save_btn.setStyleSheet(get_button_primary_style())
        save_btn.clicked.connect(self._save_smartscan_settings)
        layout.addWidget(save_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        
        layout.addStretch()
        
        scroll.setWidget(content)
        outer = QVBoxLayout(widget)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)
        
        return widget
    
    def _load_smartscan_settings(self):
        """Laedt SmartScan-Einstellungen vom Server."""
        try:
            # E-Mail-Konten fuer Dropdowns laden
            accounts = self._email_accounts_api.get_accounts()
            self._ss_email_account.clear()
            self._ss_imap_account.clear()
            self._ss_email_account.addItem("-- Kein Konto --", None)
            self._ss_imap_account.addItem("-- Kein Konto --", None)
            for acc in accounts:
                label = f"{acc.get('account_name', acc.get('name', ''))} ({acc.get('from_address', '')})"
                # ID immer als int speichern (PHP kann string oder int liefern)
                acc_id_int = int(acc['id']) if acc.get('id') is not None else None
                self._ss_email_account.addItem(label, acc_id_int)
                self._ss_imap_account.addItem(label, acc_id_int)
            
            # Einstellungen laden
            settings = self._smartscan_api.get_settings()
            if not settings:
                return
            
            # enabled kann int (0/1) oder bool sein
            self._ss_enabled.setChecked(bool(int(settings.get('enabled', 0))))
            
            # E-Mail-Konto auswaehlen (ID als int normalisieren)
            acc_id = settings.get('email_account_id')
            if acc_id is not None:
                acc_id = int(acc_id)
                idx = self._ss_email_account.findData(acc_id)
                if idx >= 0:
                    self._ss_email_account.setCurrentIndex(idx)
            
            self._ss_target.setText(settings.get('target_address', '') or '')
            self._ss_subject.setText(settings.get('subject_template', '') or '')
            self._ss_body.setPlainText(settings.get('body_template', '') or '')
            
            if settings.get('send_mode_default') == 'batch':
                self._ss_mode_batch.setChecked(True)
            else:
                self._ss_mode_single.setChecked(True)
            
            self._ss_max_attachments.setValue(int(settings.get('batch_max_attachments', 20) or 20))
            self._ss_max_mb.setValue(int(settings.get('batch_max_total_mb', 25) or 25))
            self._ss_archive.setChecked(bool(int(settings.get('archive_after_send', 0) or 0)))
            self._ss_recolor.setChecked(bool(int(settings.get('recolor_after_send', 0) or 0)))
            
            color = settings.get('recolor_color')
            if color:
                idx = self._ss_recolor_combo.findData(color)
                if idx >= 0:
                    self._ss_recolor_combo.setCurrentIndex(idx)
            
            # IMAP Settings
            self._ss_imap_auto.setChecked(bool(int(settings.get('imap_auto_import', 0) or 0)))
            
            imap_acc_id = settings.get('imap_poll_account_id')
            if imap_acc_id is not None:
                imap_acc_id = int(imap_acc_id)
                idx = self._ss_imap_account.findData(imap_acc_id)
                if idx >= 0:
                    self._ss_imap_account.setCurrentIndex(idx)
            
            if settings.get('imap_filter_mode') == 'keyword':
                self._ss_imap_filter_keyword.setChecked(True)
            else:
                self._ss_imap_filter_all.setChecked(True)
            
            self._ss_imap_keyword.setText(settings.get('imap_filter_keyword', 'ATLASabruf') or 'ATLASabruf')
            
            if settings.get('imap_sender_mode') == 'whitelist':
                self._ss_imap_sender_whitelist.setChecked(True)
            else:
                self._ss_imap_sender_all.setChecked(True)
            
            senders = settings.get('imap_allowed_senders', '')
            if senders:
                self._ss_imap_senders.setPlainText(senders.replace(',', '\n'))
            
        except Exception as e:
            logger.error(f"Fehler beim Laden der SmartScan-Einstellungen: {e}")
    
    def _save_smartscan_settings(self):
        """Speichert SmartScan-Einstellungen."""
        # Boolean-Werte als int (0/1) senden - PHP erwartet das fuer TINYINT-Spalten
        data = {
            'enabled': 1 if self._ss_enabled.isChecked() else 0,
            'email_account_id': self._ss_email_account.currentData(),
            'target_address': self._ss_target.text().strip(),
            'subject_template': self._ss_subject.text().strip(),
            'body_template': self._ss_body.toPlainText().strip(),
            'send_mode_default': 'batch' if self._ss_mode_batch.isChecked() else 'single',
            'batch_max_attachments': self._ss_max_attachments.value(),
            'batch_max_total_mb': self._ss_max_mb.value(),
            'archive_after_send': 1 if self._ss_archive.isChecked() else 0,
            'recolor_after_send': 1 if self._ss_recolor.isChecked() else 0,
            'recolor_color': self._ss_recolor_combo.currentData() if self._ss_recolor.isChecked() else None,
            'imap_auto_import': 1 if self._ss_imap_auto.isChecked() else 0,
            'imap_poll_account_id': self._ss_imap_account.currentData(),
            'imap_filter_mode': 'keyword' if self._ss_imap_filter_keyword.isChecked() else 'all',
            'imap_filter_keyword': self._ss_imap_keyword.text().strip(),
            'imap_sender_mode': 'whitelist' if self._ss_imap_sender_whitelist.isChecked() else 'all',
            'imap_allowed_senders': ','.join(
                line.strip() for line in self._ss_imap_senders.toPlainText().split('\n') if line.strip()
            ),
        }
        try:
            result = self._smartscan_api.update_settings(data)
            if result is not None:
                self._toast_manager.show_success(texts.SMARTSCAN_SETTINGS_SAVED)
            else:
                self._toast_manager.show_error(texts.SMARTSCAN_SETTINGS_ERROR.format(error="Keine Antwort vom Server"))
        except Exception as e:
            self._toast_manager.show_error(texts.SMARTSCAN_SETTINGS_ERROR.format(error=str(e)))

    # ================================================================
    # Tab 9: Smart!Scan Historie
    # ================================================================
    
    def _create_smartscan_history_tab(self) -> QWidget:
        """Erstellt den SmartScan-Historie-Tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(24, 24, 24, 24)
        
        # Toolbar
        toolbar = QHBoxLayout()
        title = QLabel(texts.SMARTSCAN_HISTORY_TITLE)
        title.setFont(QFont(FONT_HEADLINE, 18))
        title.setStyleSheet(f"color: {PRIMARY_900};")
        toolbar.addWidget(title)
        toolbar.addStretch()
        
        # Zeitraum-Filter
        self._ss_hist_filter = QComboBox()
        self._ss_hist_filter.addItem(texts.SMARTSCAN_HISTORY_FILTER_ALL, "all")
        self._ss_hist_filter.addItem(texts.SMARTSCAN_HISTORY_FILTER_7D, "7")
        self._ss_hist_filter.addItem(texts.SMARTSCAN_HISTORY_FILTER_30D, "30")
        self._ss_hist_filter.addItem(texts.SMARTSCAN_HISTORY_FILTER_90D, "90")
        self._ss_hist_filter.currentIndexChanged.connect(lambda: self._load_smartscan_history())
        toolbar.addWidget(self._ss_hist_filter)
        
        refresh_btn = QPushButton("Aktualisieren")
        refresh_btn.setStyleSheet(get_button_secondary_style())
        refresh_btn.clicked.connect(self._load_smartscan_history)
        toolbar.addWidget(refresh_btn)
        
        layout.addLayout(toolbar)
        
        # Tabelle
        self._ss_hist_table = QTableWidget()
        self._ss_hist_table.setColumnCount(9)
        self._ss_hist_table.setHorizontalHeaderLabels([
            texts.SMARTSCAN_HISTORY_DATE, texts.SMARTSCAN_HISTORY_USER,
            texts.SMARTSCAN_HISTORY_MODE, texts.SMARTSCAN_HISTORY_DOCUMENTS,
            texts.SMARTSCAN_HISTORY_SENT, texts.SMARTSCAN_HISTORY_FAILED,
            texts.SMARTSCAN_HISTORY_ARCHIVED, texts.SMARTSCAN_HISTORY_STATUS,
            texts.SMARTSCAN_HISTORY_DETAILS
        ])
        ss_hist_header = self._ss_hist_table.horizontalHeader()
        ss_hist_header.setStretchLastSection(True)
        for col in range(8):
            ss_hist_header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        self._ss_hist_table.setColumnWidth(8, 120)
        self._ss_hist_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._ss_hist_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._ss_hist_table.verticalHeader().setVisible(False)
        self._ss_hist_table.verticalHeader().setDefaultSectionSize(40)
        layout.addWidget(self._ss_hist_table)
        
        self._ss_hist_data: List[Dict] = []
        return widget
    
    def _load_smartscan_history(self):
        """Laedt SmartScan-Historie."""
        try:
            jobs = self._smartscan_api.get_jobs(limit=100)
            self._ss_hist_data = jobs
            self._populate_smartscan_history()
        except Exception as e:
            logger.error(f"Fehler beim Laden der SmartScan-Historie: {e}")
    
    def _populate_smartscan_history(self):
        """Fuellt die SmartScan-Historie-Tabelle."""
        status_labels = {
            'queued': texts.SMARTSCAN_STATUS_QUEUED,
            'sending': texts.SMARTSCAN_STATUS_SENDING,
            'sent': texts.SMARTSCAN_STATUS_SENT,
            'partial': texts.SMARTSCAN_STATUS_PARTIAL,
            'failed': texts.SMARTSCAN_STATUS_FAILED,
        }
        mode_labels = {
            'single': texts.SMARTSCAN_MODE_SINGLE.split('(')[0].strip(),
            'batch': texts.SMARTSCAN_MODE_BATCH.split('(')[0].strip(),
        }
        
        self._ss_hist_table.setRowCount(len(self._ss_hist_data))
        for row, job in enumerate(self._ss_hist_data):
            # Datum formatieren (MySQL: "2026-02-10 11:55:15" oder ISO: "2026-02-10T11:55:15")
            created = job.get('created_at', '')
            if created:
                try:
                    from datetime import datetime
                    # Sowohl MySQL- als auch ISO-Format unterstuetzen
                    dt_str = created.replace('T', ' ').replace('Z', '')
                    if '+' in dt_str:
                        dt_str = dt_str[:dt_str.index('+')]
                    dt = datetime.strptime(dt_str.strip(), '%Y-%m-%d %H:%M:%S')
                    created = dt.strftime('%d.%m.%Y %H:%M')
                except Exception:
                    pass  # Original-String beibehalten
            
            # Felder aus PHP-API: username, total_items, processed_items, sent_emails, failed_emails
            total_items = int(job.get('total_items', 0) or 0)
            processed = int(job.get('processed_items', 0) or 0)
            sent = int(job.get('sent_emails', 0) or 0)
            failed = int(job.get('failed_emails', 0) or 0)
            
            self._ss_hist_table.setItem(row, 0, QTableWidgetItem(created))
            self._ss_hist_table.setItem(row, 1, QTableWidgetItem(job.get('username', '')))
            self._ss_hist_table.setItem(row, 2, QTableWidgetItem(
                mode_labels.get(job.get('mode', ''), job.get('mode', ''))
            ))
            self._ss_hist_table.setItem(row, 3, QTableWidgetItem(str(total_items)))
            self._ss_hist_table.setItem(row, 4, QTableWidgetItem(str(sent)))
            self._ss_hist_table.setItem(row, 5, QTableWidgetItem(str(failed)))
            # Archiviert: Zeige processed_items > 0 als Hinweis (kein separates Feld)
            self._ss_hist_table.setItem(row, 6, QTableWidgetItem(
                "Ja" if processed > 0 else "-"
            ))
            self._ss_hist_table.setItem(row, 7, QTableWidgetItem(
                status_labels.get(job.get('status', ''), job.get('status', ''))
            ))
            
            detail_btn = QPushButton(texts.SMARTSCAN_HISTORY_DETAILS)
            detail_btn.setFixedHeight(28)
            detail_btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: {ACCENT_500};
                    border: 1px solid {ACCENT_500};
                    border-radius: 4px;
                    padding: 2px 10px;
                    font-size: 12px;
                }}
                QPushButton:hover {{
                    background: {ACCENT_500};
                    color: white;
                }}
            """)
            detail_btn.clicked.connect(lambda checked, r=row: self._show_smartscan_job_details(r))
            self._ss_hist_table.setCellWidget(row, 8, detail_btn)
        
        self._ss_hist_table.resizeColumnsToContents()
    
    def _show_smartscan_job_details(self, row: int):
        """Zeigt Job-Details an."""
        if row < 0 or row >= len(self._ss_hist_data):
            return
        job = self._ss_hist_data[row]
        try:
            details = self._smartscan_api.get_job_details(job['id'])
            if not details:
                return
            
            dialog = QDialog(self)
            dialog.setWindowTitle(texts.SMARTSCAN_DETAIL_TITLE)
            dialog.setMinimumSize(700, 500)
            layout = QVBoxLayout(dialog)
            
            # Items-Tabelle
            items_label = QLabel(texts.SMARTSCAN_DETAIL_DOCUMENTS)
            items_label.setFont(QFont(FONT_HEADLINE, 14))
            layout.addWidget(items_label)
            
            items_table = QTableWidget()
            items = details.get('items', [])
            items_table.setRowCount(len(items))
            items_table.setColumnCount(3)
            items_table.setHorizontalHeaderLabels([
                texts.SMARTSCAN_DETAIL_DOC_NAME,
                texts.SMARTSCAN_DETAIL_DOC_STATUS,
                texts.SMARTSCAN_DETAIL_DOC_ERROR
            ])
            items_table.horizontalHeader().setStretchLastSection(True)
            items_table.verticalHeader().setDefaultSectionSize(34)
            for i, item in enumerate(items):
                # PHP-Feld: original_filename (nicht document_name_snapshot)
                items_table.setItem(i, 0, QTableWidgetItem(item.get('original_filename', '') or ''))
                items_table.setItem(i, 1, QTableWidgetItem(item.get('status', '')))
                items_table.setItem(i, 2, QTableWidgetItem(item.get('error_message', '') or ''))
            items_table.resizeColumnsToContents()
            layout.addWidget(items_table)
            
            # Emails-Tabelle
            emails_label = QLabel(texts.SMARTSCAN_DETAIL_EMAILS)
            emails_label.setFont(QFont(FONT_HEADLINE, 14))
            layout.addWidget(emails_label)
            
            emails_table = QTableWidget()
            emails = details.get('emails', [])
            emails_table.setRowCount(len(emails))
            emails_table.setColumnCount(4)
            emails_table.setHorizontalHeaderLabels([
                texts.SMARTSCAN_DETAIL_EMAIL_SUBJECT,
                texts.SMARTSCAN_DETAIL_EMAIL_ATTACHMENTS,
                texts.SMARTSCAN_DETAIL_EMAIL_MESSAGE_ID,
                texts.SMARTSCAN_DETAIL_EMAIL_SENT_AT
            ])
            emails_table.horizontalHeader().setStretchLastSection(True)
            emails_table.verticalHeader().setDefaultSectionSize(34)
            for i, email in enumerate(emails):
                emails_table.setItem(i, 0, QTableWidgetItem(email.get('subject', '') or ''))
                emails_table.setItem(i, 1, QTableWidgetItem(str(email.get('attachment_count', 0))))
                # PHP-Feld: message_id (nicht smtp_message_id)
                emails_table.setItem(i, 2, QTableWidgetItem(email.get('message_id', '') or ''))
                # PHP-Feld: created_at (nicht sent_at)
                created = email.get('created_at', '') or ''
                if created:
                    try:
                        from datetime import datetime
                        dt = datetime.strptime(created.replace('T', ' ')[:19], '%Y-%m-%d %H:%M:%S')
                        created = dt.strftime('%d.%m.%Y %H:%M')
                    except Exception:
                        pass
                emails_table.setItem(i, 3, QTableWidgetItem(created))
            emails_table.resizeColumnsToContents()
            layout.addWidget(emails_table)
            
            close_btn = QPushButton("Schliessen")
            close_btn.setStyleSheet(get_button_secondary_style())
            close_btn.clicked.connect(dialog.accept)
            layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)
            
            dialog.exec()
        except Exception as e:
            logger.error(f"Fehler beim Laden der Job-Details: {e}")

    # ================================================================
    # Tab 10: E-Mail Posteingang (IMAP Inbox)
    # ================================================================
    
    def _create_email_inbox_tab(self) -> QWidget:
        """Erstellt den E-Mail-Posteingang-Tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(24, 24, 24, 24)
        
        # Toolbar
        toolbar = QHBoxLayout()
        title = QLabel(texts.EMAIL_INBOX_TITLE)
        title.setFont(QFont(FONT_HEADLINE, 18))
        title.setStyleSheet(f"color: {PRIMARY_900};")
        toolbar.addWidget(title)
        
        self._inbox_last_poll = QLabel("")
        self._inbox_last_poll.setStyleSheet(f"color: {TEXT_SECONDARY};")
        toolbar.addWidget(self._inbox_last_poll)
        toolbar.addStretch()
        
        # Status-Filter
        self._inbox_filter = QComboBox()
        self._inbox_filter.addItem(texts.EMAIL_INBOX_FILTER_ALL, "")
        self._inbox_filter.addItem(texts.EMAIL_INBOX_FILTER_NEW, "new")
        self._inbox_filter.addItem(texts.EMAIL_INBOX_FILTER_PROCESSED, "processed")
        self._inbox_filter.addItem(texts.EMAIL_INBOX_FILTER_IGNORED, "ignored")
        self._inbox_filter.currentIndexChanged.connect(lambda: self._load_email_inbox())
        toolbar.addWidget(self._inbox_filter)
        
        poll_btn = QPushButton(texts.EMAIL_INBOX_POLL)
        poll_btn.setStyleSheet(get_button_primary_style())
        poll_btn.clicked.connect(self._poll_email_inbox)
        toolbar.addWidget(poll_btn)
        
        layout.addLayout(toolbar)
        
        # Tabelle
        self._inbox_table = QTableWidget()
        self._inbox_table.setColumnCount(6)
        self._inbox_table.setHorizontalHeaderLabels([
            texts.EMAIL_INBOX_DATE, texts.EMAIL_INBOX_FROM,
            texts.EMAIL_INBOX_SUBJECT, texts.EMAIL_INBOX_ATTACHMENTS,
            texts.EMAIL_INBOX_STATUS, ""
        ])
        self._inbox_table.horizontalHeader().setStretchLastSection(True)
        self._inbox_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._inbox_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._inbox_table.verticalHeader().setVisible(False)
        self._inbox_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._inbox_table.customContextMenuRequested.connect(self._show_inbox_context_menu)
        layout.addWidget(self._inbox_table)
        
        self._inbox_data: List[Dict] = []
        self._inbox_page = 1
        return widget
    
    def _load_email_inbox(self):
        """Laedt E-Mail-Posteingang."""
        try:
            status_filter = self._inbox_filter.currentData()
            result = self._email_accounts_api.get_inbox(
                page=self._inbox_page, limit=50, status=status_filter or None
            )
            self._inbox_data = result.get('mails', []) if isinstance(result, dict) else []
            self._populate_inbox_table()
        except Exception as e:
            logger.error(f"Fehler beim Laden des Posteingangs: {e}")
    
    def _populate_inbox_table(self):
        """Fuellt die Posteingang-Tabelle."""
        status_labels = {
            'new': texts.EMAIL_INBOX_STATUS_NEW,
            'processed': texts.EMAIL_INBOX_STATUS_PROCESSED,
            'ignored': texts.EMAIL_INBOX_STATUS_IGNORED,
        }
        
        self._inbox_table.setRowCount(len(self._inbox_data))
        for row, mail in enumerate(self._inbox_data):
            received = mail.get('received_at', '')
            if received and 'T' in str(received):
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(str(received).replace('Z', '+00:00'))
                    received = dt.strftime('%d.%m.%Y %H:%M')
                except Exception:
                    pass
            
            self._inbox_table.setItem(row, 0, QTableWidgetItem(str(received)))
            
            from_str = mail.get('from_name', '') or mail.get('from_address', '')
            self._inbox_table.setItem(row, 1, QTableWidgetItem(from_str))
            self._inbox_table.setItem(row, 2, QTableWidgetItem(mail.get('subject', '')))
            self._inbox_table.setItem(row, 3, QTableWidgetItem(str(mail.get('attachment_count', 0))))
            self._inbox_table.setItem(row, 4, QTableWidgetItem(
                status_labels.get(mail.get('processing_status', ''), mail.get('processing_status', ''))
            ))
            
            detail_btn = QPushButton(texts.EMAIL_INBOX_DETAILS)
            detail_btn.setStyleSheet(get_button_ghost_style())
            detail_btn.clicked.connect(lambda checked, r=row: self._show_inbox_detail(r))
            self._inbox_table.setCellWidget(row, 5, detail_btn)
        
        self._inbox_table.resizeColumnsToContents()
    
    def _poll_email_inbox(self):
        """IMAP-Postfach im Hintergrund abrufen (verhindert UI-Freeze)."""
        # Bereits laufender Poll?
        if getattr(self, '_imap_poll_worker', None) and self._imap_poll_worker.isRunning():
            self._toast_manager.show_info(texts.EMAIL_INBOX_POLL_RUNNING)
            return
        
        # Account-ID ermitteln (schnelle lokale Checks, kein Netzwerk)
        acc_id = None
        
        # 1. Versuche imap_poll_account_id aus SmartScan-Einstellungen
        try:
            settings = self._smartscan_api.get_settings()
            if settings:
                raw_id = settings.get('imap_poll_account_id')
                if raw_id is not None and str(raw_id).strip():
                    acc_id = int(raw_id)
        except Exception as e:
            logger.debug(f"SmartScan-Settings Fehler (ignoriert): {e}")
        
        # 2. Fallback: Erstes E-Mail-Konto mit IMAP-Host verwenden
        if not acc_id and self._ea_data:
            for acc in self._ea_data:
                imap_host = acc.get('imap_host', '').strip() if acc.get('imap_host') else ''
                is_active = acc.get('is_active')
                # is_active kann int (1/0), string ("1"/"0"), oder bool sein
                if imap_host and (is_active == 1 or is_active == '1' or is_active is True):
                    acc_id = int(acc['id'])
                    break
        
        # 3. Noch kein Konto? Konten nachladen und erneut suchen
        if not acc_id:
            try:
                accounts = self._email_accounts_api.get_accounts()
                for acc in accounts:
                    imap_host = acc.get('imap_host', '').strip() if acc.get('imap_host') else ''
                    is_active = acc.get('is_active')
                    if imap_host and (is_active == 1 or is_active == '1' or is_active is True):
                        acc_id = int(acc['id'])
                        break
            except Exception:
                pass
        
        if not acc_id:
            self._toast_manager.show_warning(texts.EMAIL_INBOX_NO_IMAP_ACCOUNT)
            return
        
        logger.info(f"IMAP-Poll gestartet fuer Konto-ID {acc_id}")
        
        # Worker starten (Hintergrund-Thread, UI bleibt responsiv)
        self._toast_manager.show_info(texts.EMAIL_INBOX_POLL_RUNNING)
        self._imap_poll_worker = ImapPollWorker(self._email_accounts_api, acc_id)
        self._imap_poll_worker.finished.connect(self._on_imap_poll_finished)
        self._imap_poll_worker.error.connect(self._on_imap_poll_error)
        self._active_workers.append(self._imap_poll_worker)
        self._imap_poll_worker.start()
    
    def _on_imap_poll_finished(self, result: dict):
        """Callback wenn IMAP-Poll abgeschlossen."""
        new_mails = result.get('new_mails', 0)
        new_atts = result.get('new_attachments', 0)
        
        if new_mails > 0:
            self._toast_manager.show_success(texts.EMAIL_INBOX_POLL_SUCCESS.format(
                new_mails=new_mails, new_attachments=new_atts))
        else:
            self._toast_manager.show_info(texts.EMAIL_INBOX_POLL_NO_NEW)
        
        self._load_email_inbox()
    
    def _on_imap_poll_error(self, error: str):
        """Callback wenn IMAP-Poll fehlgeschlagen."""
        self._toast_manager.show_error(texts.EMAIL_INBOX_POLL_ERROR.format(error=error))
    
    def _show_inbox_context_menu(self, position):
        """Kontextmenue fuer Posteingang-Tabelle."""
        row = self._inbox_table.rowAt(position.y())
        if row < 0 or row >= len(self._inbox_data):
            return
        
        mail = self._inbox_data[row]
        menu = QMenu(self)
        
        if mail.get('has_attachments') and mail.get('processing_status') == 'new':
            import_action = QAction(texts.EMAIL_INBOX_IMPORT, self)
            import_action.triggered.connect(lambda: self._import_inbox_attachments(row))
            menu.addAction(import_action)
        
        ignore_action = QAction(texts.EMAIL_INBOX_IGNORE, self)
        ignore_action.triggered.connect(lambda: self._ignore_inbox_mail(row))
        menu.addAction(ignore_action)
        
        detail_action = QAction(texts.EMAIL_INBOX_DETAILS, self)
        detail_action.triggered.connect(lambda: self._show_inbox_detail(row))
        menu.addAction(detail_action)
        
        menu.exec(self._inbox_table.viewport().mapToGlobal(position))
    
    def _show_inbox_detail(self, row: int):
        """Zeigt Mail-Details an."""
        if row < 0 or row >= len(self._inbox_data):
            return
        mail = self._inbox_data[row]
        try:
            detail = self._email_accounts_api.get_inbox_mail(mail['id'])
            if not detail:
                return
            
            dialog = QDialog(self)
            dialog.setWindowTitle(f"Mail: {detail.get('subject', '')}")
            dialog.setMinimumSize(600, 400)
            layout = QVBoxLayout(dialog)
            
            # Header
            header_text = f"Von: {detail.get('from_name', '')} <{detail.get('from_address', '')}>\n"
            header_text += f"Betreff: {detail.get('subject', '')}\n"
            header_text += f"Datum: {detail.get('received_at', '')}"
            header_label = QLabel(header_text)
            header_label.setWordWrap(True)
            layout.addWidget(header_label)
            
            # Body
            body = detail.get('body_preview', '')
            if body:
                body_edit = QTextEdit()
                body_edit.setPlainText(body)
                body_edit.setReadOnly(True)
                body_edit.setMaximumHeight(150)
                layout.addWidget(body_edit)
            
            # Anhaenge
            attachments = detail.get('attachments', [])
            if attachments:
                att_label = QLabel(f"Anhaenge ({len(attachments)}):")
                att_label.setFont(QFont(FONT_HEADLINE, 12))
                layout.addWidget(att_label)
                
                att_table = QTableWidget()
                att_table.setRowCount(len(attachments))
                att_table.setColumnCount(4)
                att_table.setHorizontalHeaderLabels(["Dateiname", "Groesse", "MIME", "Status"])
                att_table.horizontalHeader().setStretchLastSection(True)
                for i, att in enumerate(attachments):
                    att_table.setItem(i, 0, QTableWidgetItem(att.get('filename', '')))
                    size_bytes = att.get('file_size_bytes', 0)
                    size_str = f"{size_bytes / 1024:.1f} KB" if size_bytes else "?"
                    att_table.setItem(i, 1, QTableWidgetItem(size_str))
                    att_table.setItem(i, 2, QTableWidgetItem(att.get('mime_type', '')))
                    att_table.setItem(i, 3, QTableWidgetItem(att.get('import_status', '')))
                layout.addWidget(att_table)
            
            close_btn = QPushButton("Schliessen")
            close_btn.setStyleSheet(get_button_secondary_style())
            close_btn.clicked.connect(dialog.accept)
            layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)
            
            dialog.exec()
        except Exception as e:
            logger.error(f"Fehler beim Laden der Mail-Details: {e}")
    
    def _import_inbox_attachments(self, row: int):
        """Importiert Anhaenge einer Mail (Stub - wird vom ImapImportWorker erledigt)."""
        self._toast_manager.show_info(
            "Der Import wird ueber den IMAP-Import-Worker ausgefuehrt. "
            "Verwenden Sie den 'Postfach abrufen' Button.")
    
    def _ignore_inbox_mail(self, row: int):
        """Markiert eine Mail als ignoriert."""
        if row < 0 or row >= len(self._inbox_data):
            return
        # TODO: API-Call zum Ignorieren
        self._load_email_inbox()
    
    # ================================================================
    # Tab 11: Mitteilungen (Admin-Verwaltung)
    # ================================================================
    
    def _create_messages_tab(self) -> QWidget:
        """Erstellt das Admin-Panel fuer Mitteilungen (System + Admin)."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(24, 24, 24, 24)
        
        # Toolbar
        toolbar = QHBoxLayout()
        
        title = QLabel(texts.ADMIN_MSG_TITLE)
        title.setFont(QFont(FONT_HEADLINE, 18))
        title.setStyleSheet(f"color: {PRIMARY_900};")
        toolbar.addWidget(title)
        toolbar.addStretch()
        
        new_msg_btn = QPushButton(f"+ {texts.ADMIN_MSG_NEW}")
        new_msg_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ACCENT_500};
                color: white;
                border: none;
                border-radius: {RADIUS_MD};
                padding: 8px 20px;
                font-size: {FONT_SIZE_BODY};
            }}
            QPushButton:hover {{
                background-color: #e8882e;
            }}
        """)
        new_msg_btn.clicked.connect(self._show_new_message_dialog)
        toolbar.addWidget(new_msg_btn)
        
        layout.addLayout(toolbar)
        
        # Tabelle
        self._msg_table = QTableWidget()
        self._msg_table.setColumnCount(6)
        self._msg_table.setHorizontalHeaderLabels([
            texts.ADMIN_MSG_COL_DATE,
            texts.ADMIN_MSG_COL_TITLE,
            texts.ADMIN_MSG_COL_SEVERITY,
            texts.ADMIN_MSG_COL_SOURCE,
            texts.ADMIN_MSG_COL_SENDER,
            texts.ADMIN_MSG_COL_ACTIONS,
        ])
        self._msg_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self._msg_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self._msg_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self._msg_table.verticalHeader().setVisible(False)
        self._msg_table.setAlternatingRowColors(True)
        self._msg_table.setStyleSheet(f"""
            QTableWidget {{
                border: 1px solid {PRIMARY_100};
                border-radius: {RADIUS_MD};
                gridline-color: {PRIMARY_100};
                font-size: {FONT_SIZE_BODY};
            }}
            QTableWidget::item {{
                padding: 6px 8px;
            }}
        """)
        layout.addWidget(self._msg_table)
        
        self._msg_data = []
        return widget
    
    def _load_admin_messages(self):
        """Laedt alle Mitteilungen fuer die Admin-Tabelle."""
        try:
            from api.messages import MessagesAPI
            api = MessagesAPI(self._api_client)
            result = api.get_messages(page=1, per_page=100)
            self._msg_data = result.get('data', [])
            self._populate_msg_table()
        except Exception as e:
            logger.error(f"Admin-Mitteilungen laden: {e}")
            if hasattr(self, '_toast_manager') and self._toast_manager:
                self._toast_manager.show_error(texts.ADMIN_MSG_LOAD_ERROR)
    
    def _populate_msg_table(self):
        """Fuellt die Mitteilungen-Tabelle."""
        self._msg_table.setRowCount(len(self._msg_data))
        
        severity_labels = {
            'info': texts.MSG_CENTER_SEVERITY_INFO,
            'warning': texts.MSG_CENTER_SEVERITY_WARNING,
            'error': texts.MSG_CENTER_SEVERITY_ERROR,
            'critical': texts.MSG_CENTER_SEVERITY_CRITICAL,
        }
        
        for row, msg in enumerate(self._msg_data):
            # Datum
            created = msg.get('created_at', '')
            from datetime import datetime
            try:
                dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
                date_str = dt.strftime('%d.%m.%Y %H:%M')
            except (ValueError, AttributeError):
                date_str = created
            self._msg_table.setItem(row, 0, QTableWidgetItem(date_str))
            
            # Titel
            self._msg_table.setItem(row, 1, QTableWidgetItem(msg.get('title', '')))
            
            # Severity
            sev = msg.get('severity', 'info')
            self._msg_table.setItem(row, 2, QTableWidgetItem(
                severity_labels.get(sev, sev)
            ))
            
            # Quelle
            self._msg_table.setItem(row, 3, QTableWidgetItem(msg.get('source', '')))
            
            # Absender
            self._msg_table.setItem(row, 4, QTableWidgetItem(msg.get('sender_name', '')))
            
            # Aktionen
            delete_btn = QPushButton(texts.ADMIN_MSG_DELETE)
            delete_btn.setStyleSheet(f"""
                QPushButton {{
                    color: #dc2626;
                    background: transparent;
                    border: 1px solid #dc2626;
                    border-radius: 4px;
                    padding: 3px 10px;
                    font-size: 11px;
                }}
                QPushButton:hover {{
                    background-color: #fee2e2;
                }}
            """)
            msg_id = msg.get('id', 0)
            msg_title = msg.get('title', '')
            delete_btn.clicked.connect(
                lambda checked, mid=msg_id, mt=msg_title: self._delete_admin_message(mid, mt)
            )
            self._msg_table.setCellWidget(row, 5, delete_btn)
    
    def _show_new_message_dialog(self):
        """Zeigt den Dialog zum Erstellen einer neuen Mitteilung."""
        dialog = QDialog(self)
        dialog.setWindowTitle(texts.ADMIN_MSG_DIALOG_TITLE)
        dialog.setMinimumWidth(450)
        dialog.setStyleSheet(f"background-color: {PRIMARY_0};")
        
        layout = QFormLayout(dialog)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)
        
        title_input = QLineEdit()
        title_input.setMaxLength(500)
        title_input.setPlaceholderText(texts.ADMIN_MSG_DIALOG_TITLE_LABEL)
        title_input.setStyleSheet(f"""
            QLineEdit {{
                border: 1px solid {PRIMARY_100};
                border-radius: {RADIUS_MD};
                padding: 8px;
                font-size: {FONT_SIZE_BODY};
            }}
        """)
        layout.addRow(texts.ADMIN_MSG_DIALOG_TITLE_LABEL, title_input)
        
        desc_input = QTextEdit()
        desc_input.setMaximumHeight(100)
        desc_input.setStyleSheet(f"""
            QTextEdit {{
                border: 1px solid {PRIMARY_100};
                border-radius: {RADIUS_MD};
                padding: 8px;
                font-size: {FONT_SIZE_BODY};
            }}
        """)
        layout.addRow(texts.ADMIN_MSG_DIALOG_DESC_LABEL, desc_input)
        
        severity_combo = QComboBox()
        severity_combo.addItem(texts.MSG_CENTER_SEVERITY_INFO, 'info')
        severity_combo.addItem(texts.MSG_CENTER_SEVERITY_WARNING, 'warning')
        severity_combo.addItem(texts.MSG_CENTER_SEVERITY_ERROR, 'error')
        severity_combo.addItem(texts.MSG_CENTER_SEVERITY_CRITICAL, 'critical')
        severity_combo.setStyleSheet(f"""
            QComboBox {{
                border: 1px solid {PRIMARY_100};
                border-radius: {RADIUS_MD};
                padding: 6px 8px;
                font-size: {FONT_SIZE_BODY};
            }}
        """)
        layout.addRow(texts.ADMIN_MSG_DIALOG_SEVERITY_LABEL, severity_combo)
        
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            title_text = title_input.text().strip()
            if not title_text:
                return
            
            desc_text = desc_input.toPlainText().strip() or None
            severity = severity_combo.currentData()
            
            try:
                from api.messages import MessagesAPI
                api = MessagesAPI(self._api_client)
                api.create_message(
                    title=title_text,
                    description=desc_text,
                    severity=severity
                )
                if hasattr(self, '_toast_manager') and self._toast_manager:
                    self._toast_manager.show_success(texts.ADMIN_MSG_CREATED)
                self._load_admin_messages()
            except Exception as e:
                logger.error(f"Mitteilung erstellen: {e}")
                if hasattr(self, '_toast_manager') and self._toast_manager:
                    self._toast_manager.show_error(texts.ADMIN_MSG_CREATE_ERROR)
    
    def _delete_admin_message(self, message_id: int, title: str):
        """Loescht eine Mitteilung nach Bestaetigung."""
        reply = QMessageBox.question(
            self,
            texts.ADMIN_MSG_DELETE,
            texts.ADMIN_MSG_DELETE_CONFIRM.format(title=title[:50]),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        try:
            from api.messages import MessagesAPI
            api = MessagesAPI(self._api_client)
            api.delete_message(message_id)
            if hasattr(self, '_toast_manager') and self._toast_manager:
                self._toast_manager.show_success(texts.ADMIN_MSG_DELETED)
            self._load_admin_messages()
        except Exception as e:
            logger.error(f"Mitteilung loeschen: {e}")
            if hasattr(self, '_toast_manager') and self._toast_manager:
                self._toast_manager.show_error(texts.ADMIN_MSG_DELETE_ERROR)


class _EmailAccountDialog(QDialog):
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
            # IMAP-Verschluesselung: Auto-Korrektur Port 993 → SSL, Port 143 → TLS
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


class _PasswordDialog(QDialog):
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
