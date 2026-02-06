"""
BiPRO-GDV Tool - Login Dialog

Dialog für Benutzer-Anmeldung.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QPushButton, QLabel, QCheckBox,
    QMessageBox, QProgressBar
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont

from api.client import APIClient, APIError
from api.auth import AuthAPI, AuthState


class LoginWorker(QThread):
    """Worker-Thread für Login (blockiert nicht die UI)."""
    
    finished = Signal(object)  # AuthState
    error = Signal(str)
    
    def __init__(self, auth_api: AuthAPI, username: str, password: str, remember: bool):
        super().__init__()
        self.auth_api = auth_api
        self.username = username
        self.password = password
        self.remember = remember
    
    def run(self):
        try:
            state = self.auth_api.login(self.username, self.password, self.remember)
            self.finished.emit(state)
        except Exception as e:
            self.error.emit(str(e))


class ConnectionCheckWorker(QThread):
    """Worker-Thread für Verbindungstest."""
    
    finished = Signal(bool)
    
    def __init__(self, client: APIClient):
        super().__init__()
        self.client = client
    
    def run(self):
        result = self.client.check_connection()
        self.finished.emit(result)


class LoginDialog(QDialog):
    """
    Login-Dialog für BiPRO-GDV Tool.
    
    Verwendung:
        dialog = LoginDialog()
        if dialog.exec() == QDialog.Accepted:
            client = dialog.get_client()
            auth = dialog.get_auth()
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.client = APIClient()
        self.auth_api = AuthAPI(self.client)
        self._login_worker = None
        self._check_worker = None
        
        self.setWindowTitle("BiPRO-GDV Tool - Anmeldung")
        self.setFixedSize(400, 300)
        self.setModal(True)
        
        self._setup_ui()
        self._check_connection()
    
    def _setup_ui(self):
        """UI aufbauen."""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(30, 30, 30, 30)
        
        # Titel
        title = QLabel("BiPRO-GDV Tool")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # Status-Label
        self.status_label = QLabel("Verbindung wird geprüft...")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("color: gray;")
        layout.addWidget(self.status_label)
        
        # Formular
        form_layout = QFormLayout()
        form_layout.setSpacing(10)
        
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Benutzername")
        self.username_input.returnPressed.connect(self._focus_password)
        form_layout.addRow("Benutzer:", self.username_input)
        
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Passwort")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.returnPressed.connect(self._do_login)
        form_layout.addRow("Passwort:", self.password_input)
        
        layout.addLayout(form_layout)
        
        # Angemeldet bleiben
        self.remember_check = QCheckBox("Angemeldet bleiben (8 Stunden)")
        layout.addWidget(self.remember_check)
        
        # Progress Bar (versteckt)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)  # Indeterminate
        self.progress.hide()
        layout.addWidget(self.progress)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.login_button = QPushButton("Anmelden")
        self.login_button.setDefault(True)
        self.login_button.clicked.connect(self._do_login)
        self.login_button.setEnabled(False)  # Aktiviert nach Verbindungscheck
        button_layout.addWidget(self.login_button)
        
        cancel_button = QPushButton("Abbrechen")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)
        
        layout.addLayout(button_layout)
        
        # Stretch am Ende
        layout.addStretch()
    
    def _focus_password(self):
        """Fokus auf Passwort-Feld."""
        self.password_input.setFocus()
    
    def _check_connection(self):
        """Prüft Verbindung zum Server."""
        self._check_worker = ConnectionCheckWorker(self.client)
        self._check_worker.finished.connect(self._on_connection_checked)
        self._check_worker.start()
    
    def _on_connection_checked(self, connected: bool):
        """Callback nach Verbindungscheck."""
        if connected:
            self.status_label.setText("Verbunden mit Server")
            self.status_label.setStyleSheet("color: green;")
            self.login_button.setEnabled(True)
            self.username_input.setFocus()
            
            # Auto-Login versuchen
            self._try_auto_login()
        else:
            self.status_label.setText("Server nicht erreichbar")
            self.status_label.setStyleSheet("color: red;")
            self.login_button.setEnabled(False)
    
    def _try_auto_login(self):
        """Versucht Auto-Login mit gespeichertem Token."""
        state = self.auth_api.try_auto_login()
        if state.is_authenticated:
            self.status_label.setText(f"Willkommen zurück, {state.user.username}!")
            self.status_label.setStyleSheet("color: green;")
            self.accept()
    
    def _do_login(self):
        """Login durchführen."""
        username = self.username_input.text().strip()
        password = self.password_input.text()
        
        if not username:
            QMessageBox.warning(self, "Fehler", "Bitte Benutzername eingeben.")
            self.username_input.setFocus()
            return
        
        if not password:
            QMessageBox.warning(self, "Fehler", "Bitte Passwort eingeben.")
            self.password_input.setFocus()
            return
        
        # UI deaktivieren
        self.login_button.setEnabled(False)
        self.username_input.setEnabled(False)
        self.password_input.setEnabled(False)
        self.progress.show()
        self.status_label.setText("Anmeldung läuft...")
        self.status_label.setStyleSheet("color: gray;")
        
        # Login im Hintergrund
        self._login_worker = LoginWorker(
            self.auth_api,
            username,
            password,
            self.remember_check.isChecked()
        )
        self._login_worker.finished.connect(self._on_login_finished)
        self._login_worker.error.connect(self._on_login_error)
        self._login_worker.start()
    
    def _on_login_finished(self, state: AuthState):
        """Callback nach Login."""
        self.progress.hide()
        
        if state.is_authenticated:
            self.status_label.setText(f"Willkommen, {state.user.username}!")
            self.status_label.setStyleSheet("color: green;")
            self.accept()
        else:
            self.status_label.setText("Anmeldung fehlgeschlagen")
            self.status_label.setStyleSheet("color: red;")
            self.password_input.clear()
            self.password_input.setFocus()
            self._enable_inputs()
            
            QMessageBox.warning(
                self,
                "Anmeldung fehlgeschlagen",
                "Benutzername oder Passwort falsch."
            )
    
    def _on_login_error(self, error_msg: str):
        """Callback bei Login-Fehler."""
        self.progress.hide()
        self.status_label.setText("Verbindungsfehler")
        self.status_label.setStyleSheet("color: red;")
        self._enable_inputs()
        
        QMessageBox.critical(
            self,
            "Fehler",
            f"Anmeldung fehlgeschlagen:\n{error_msg}"
        )
    
    def _enable_inputs(self):
        """Eingabefelder wieder aktivieren."""
        self.login_button.setEnabled(True)
        self.username_input.setEnabled(True)
        self.password_input.setEnabled(True)
    
    def get_client(self) -> APIClient:
        """Gibt den authentifizierten API-Client zurück."""
        return self.client
    
    def get_auth(self) -> AuthAPI:
        """Gibt die Auth-API zurück."""
        return self.auth_api
