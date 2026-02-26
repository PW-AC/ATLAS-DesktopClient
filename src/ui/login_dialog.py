"""
ACENCIA ATLAS - Login Dialog

Dialog für Benutzer-Anmeldung.
"""

import os
import logging

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QPushButton, QLabel, QCheckBox,
    QProgressBar
)
from PySide6.QtCore import Qt, QThread, Signal, QEvent, QPropertyAnimation, QEasingCurve, QPoint, QAbstractAnimation
from PySide6.QtGui import QFont, QPixmap, QAction, QIcon, QPainter, QColor, QPen

from ui.styles.tokens import TEXT_SECONDARY, ERROR
from i18n.de import PASSWORD_SHOW, PASSWORD_HIDE, LOGIN_CAPS_LOCK_WARNING

from api.client import APIClient
from api.auth import AuthAPI, AuthState

logger = logging.getLogger(__name__)


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
    Login-Dialog für ACENCIA ATLAS.
    
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
        
        self.setWindowTitle("ACENCIA ATLAS - Anmeldung")
        self.setFixedSize(400, 420)
        self.setModal(True)
        
        self._setup_ui()
        self.password_input.installEventFilter(self)
        self._check_connection()

    def eventFilter(self, source, event):
        """Event-Filter zur Erkennung von Caps Lock."""
        if source == self.password_input and event.type() == QEvent.KeyPress:
            text = event.text()
            if text and text.isalpha():
                is_upper = text.isupper()
                modifiers = event.modifiers()
                shift_pressed = bool(modifiers & Qt.ShiftModifier)

                # Logic: Upper without Shift OR Lower with Shift => Caps Lock ON
                if (is_upper and not shift_pressed) or (not is_upper and shift_pressed):
                    self.caps_lock_label.show()
                else:
                    self.caps_lock_label.hide()

        return super().eventFilter(source, event)
    
    def shake_window(self):
        """Wackelt das Fenster bei Fehler (Feedback)."""
        if hasattr(self, '_shake_animation') and self._shake_animation.state() == QAbstractAnimation.State.Running:
            return

        animation = QPropertyAnimation(self, b"pos", self)
        animation.setDuration(400)
        animation.setLoopCount(1)
        animation.setEasingCurve(QEasingCurve.Type.InOutQuad)

        pos = self.pos()
        x = pos.x()
        y = pos.y()

        # Shake Keyframes
        animation.setKeyValueAt(0, QPoint(x, y))
        animation.setKeyValueAt(0.1, QPoint(x + 5, y))
        animation.setKeyValueAt(0.2, QPoint(x - 5, y))
        animation.setKeyValueAt(0.3, QPoint(x + 5, y))
        animation.setKeyValueAt(0.4, QPoint(x - 5, y))
        animation.setKeyValueAt(0.5, QPoint(x + 3, y))
        animation.setKeyValueAt(0.6, QPoint(x - 3, y))
        animation.setKeyValueAt(0.7, QPoint(x + 2, y))
        animation.setKeyValueAt(0.8, QPoint(x - 2, y))
        animation.setKeyValueAt(1, QPoint(x, y))

        animation.start()
        self._shake_animation = animation

    def _generate_eye_icon(self, crossed=False):
        """Generiert ein Augen-Icon (optional durchgestrichen) mit Primitiven."""
        pixmap = QPixmap(20, 20)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        color = QColor(TEXT_SECONDARY)
        pen = QPen(color)
        pen.setWidth(2)
        painter.setPen(pen)

        # Auge zeichnen (Ellipse)
        # rect(x, y, w, h) -> Mitte ist 10,10
        painter.drawEllipse(2, 5, 16, 10)

        # Pupille (Kreis)
        painter.setBrush(color)
        painter.drawEllipse(8, 8, 4, 4)

        if crossed:
            # Diagonale Linie
            pen.setWidth(2)
            # Etwas Abstand lassen (Outline) - optional
            painter.setPen(pen)
            painter.drawLine(3, 3, 17, 17)

        painter.end()
        return QIcon(pixmap)

    def _toggle_password_visibility(self):
        """Schaltet Passwort-Sichtbarkeit um."""
        if self.password_input.echoMode() == QLineEdit.Password:
            self.password_input.setEchoMode(QLineEdit.Normal)
            self.toggle_password_action.setIcon(self._icon_hide)
            self.toggle_password_action.setToolTip(PASSWORD_HIDE)
        else:
            self.password_input.setEchoMode(QLineEdit.Password)
            self.toggle_password_action.setIcon(self._icon_show)
            self.toggle_password_action.setToolTip(PASSWORD_SHOW)

    def _setup_ui(self):
        """UI aufbauen."""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(30, 30, 30, 30)
        
        # App-Logo
        logo_label = QLabel()
        logo_label.setAlignment(Qt.AlignCenter)
        logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "logo.png")
        if os.path.exists(logo_path):
            pixmap = QPixmap(logo_path)
            scaled = pixmap.scaled(100, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            logo_label.setPixmap(scaled)
        layout.addWidget(logo_label)
        
        # Titel
        title = QLabel("ACENCIA ATLAS")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # Tagline
        tagline = QLabel("Der Datenkern.")
        tagline.setAlignment(Qt.AlignCenter)
        tagline.setStyleSheet("color: #6B7280; font-size: 11px;")
        layout.addWidget(tagline)
        
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

        # Passwort-Toggle Action
        self._icon_show = self._generate_eye_icon(crossed=False)
        self._icon_hide = self._generate_eye_icon(crossed=True)

        self.toggle_password_action = QAction(self)
        self.toggle_password_action.setIcon(self._icon_show)
        self.toggle_password_action.setToolTip(PASSWORD_SHOW)
        self.toggle_password_action.triggered.connect(self._toggle_password_visibility)
        self.password_input.addAction(self.toggle_password_action, QLineEdit.ActionPosition.TrailingPosition)

        form_layout.addRow("Passwort:", self.password_input)
        
        # Caps Lock Warning (hidden by default)
        self.caps_lock_label = QLabel(LOGIN_CAPS_LOCK_WARNING)
        self.caps_lock_label.setStyleSheet(f"color: {ERROR}; font-size: 11px; margin-top: -5px;")
        self.caps_lock_label.hide()
        form_layout.addRow("", self.caps_lock_label)

        layout.addLayout(form_layout)
        
        # Angemeldet bleiben
        self.remember_check = QCheckBox("Angemeldet bleiben (30 Tage)")
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
        else:
            self._clear_local_caches()
    
    def _clear_local_caches(self):
        """Loescht alle lokalen Caches wenn keine gueltige Session vorhanden ist."""
        import shutil
        import tempfile
        
        cache_dir = os.path.join(tempfile.gettempdir(), 'bipro_preview_cache')
        if os.path.isdir(cache_dir):
            try:
                shutil.rmtree(cache_dir)
                logger.info(f"Vorschau-Cache geloescht: {cache_dir}")
            except Exception as e:
                logger.debug(f"Cache-Bereinigung fehlgeschlagen: {e}")
    
    def _do_login(self):
        """Login durchführen."""
        username = self.username_input.text().strip()
        password = self.password_input.text()
        
        if not username:
            self.status_label.setText("Bitte Benutzername eingeben.")
            self.status_label.setStyleSheet("color: #dc2626;")
            self.username_input.setFocus()
            self.shake_window()
            return
        
        if not password:
            self.status_label.setText("Bitte Passwort eingeben.")
            self.status_label.setStyleSheet("color: #dc2626;")
            self.password_input.setFocus()
            self.shake_window()
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
            self.shake_window()
    
    def _on_login_error(self, error_msg: str):
        """Callback bei Login-Fehler."""
        self.progress.hide()
        self.status_label.setText("Verbindungsfehler")
        self.status_label.setStyleSheet("color: red;")
        self._enable_inputs()
        self.shake_window()
        
        # Fehler wird ueber status_label angezeigt (inline, nicht modal)
    
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
