"""
ATLAS Wartungsmodus-UI

MaintenanceOverlay:  Widget das ueber dem MainHub eingeblendet wird (Betrieb-Sperre).
MaintenanceWindow:   Eigenstaendiges Fenster fuer den Fall dass der Hub gar nicht geoeffnet wird.
SystemStatusChecker: QThread-Worker fuer nicht-blockierende Status-Abfragen.

SICHERHEIT: Wenn kein Zugang besteht, darf der Nutzer UNTER KEINEN UMSTAENDEN
auf die App zugreifen koennen. Der Schliessen-Button beendet die gesamte App.
"""

import logging
import os

from PySide6.QtCore import Qt, QTimer, Signal, QThread
from PySide6.QtGui import QPainter, QColor, QPixmap
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QFrame, QMainWindow,
    QHBoxLayout, QApplication, QSpacerItem, QSizePolicy
)

from i18n import de as texts
from ui.styles.tokens import (
    PRIMARY_900, PRIMARY_500, PRIMARY_100, PRIMARY_0,
    ACCENT_500, FONT_HEADLINE, FONT_BODY,
    FONT_SIZE_H1, FONT_SIZE_BODY, FONT_SIZE_CAPTION,
    FONT_WEIGHT_MEDIUM, RADIUS_LG, RADIUS_MD,
    MAINTENANCE_CARD_BG,
)

logger = logging.getLogger(__name__)

RECHECK_INTERVAL_MS = 60_000

_CARD_BG = MAINTENANCE_CARD_BG
_CARD_BORDER = "rgba(136, 169, 195, 0.15)"


def _get_assets_dir() -> str:
    src_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(src_dir, "ui", "assets")


def _get_close_button_style() -> str:
    return f"""
        QPushButton {{
            background-color: transparent;
            color: {PRIMARY_500};
            border: 1px solid {PRIMARY_500};
            border-radius: {RADIUS_MD};
            padding: 8px 24px;
            font-family: {FONT_BODY};
            font-size: {FONT_SIZE_BODY};
            font-weight: {FONT_WEIGHT_MEDIUM};
        }}
        QPushButton:hover {{
            background-color: rgba(136, 169, 195, 0.12);
            color: {PRIMARY_0};
            border-color: {PRIMARY_0};
        }}
        QPushButton:pressed {{
            background-color: rgba(136, 169, 195, 0.2);
        }}
    """


class SystemStatusCheckWorker(QThread):
    """Fragt /system/status in einem Hintergrund-Thread ab.

    FAIL-CLOSED: Bei Fehler wird check_failed emittiert (NICHT 'public').
    Der aufrufende Code behaelt dann den aktuellen Sperr-Zustand bei.
    """
    status_received = Signal(str, str)
    check_failed = Signal()

    def __init__(self, api_client, parent=None):
        super().__init__(parent)
        self._api_client = api_client

    def run(self):
        try:
            from api.client import APIClient
            from api.system_status import SystemStatusAPI
            bg_client = APIClient(self._api_client.config)
            bg_client.set_token(self._api_client._token)
            api = SystemStatusAPI(bg_client)
            result = api.get_status()
            if result.status in ('public', 'closed', 'locked'):
                self.status_received.emit(result.status, result.message or '')
            else:
                logger.warning(f"Unbekannter System-Status: {result.status} - Fail-Closed")
                self.check_failed.emit()
        except Exception as e:
            logger.warning(f"System-Status Check fehlgeschlagen: {e} - Fail-Closed")
            self.check_failed.emit()


def _build_maintenance_content(parent_layout: QVBoxLayout) -> dict:
    """Erzeugt den Wartungsmodus-Inhalt im dunklen ACENCIA-Design."""

    container = QFrame()
    container.setObjectName("maintenanceCard")
    container.setFixedWidth(480)
    container.setStyleSheet(f"""
        QFrame#maintenanceCard {{
            background-color: {_CARD_BG};
            border-radius: {RADIUS_LG};
            border: 1px solid {_CARD_BORDER};
        }}
        QFrame#maintenanceCard QLabel {{
            background: transparent;
            border: none;
        }}
    """)
    card = QVBoxLayout(container)
    card.setContentsMargins(36, 32, 36, 28)
    card.setSpacing(0)

    # Wartungs-Illustration
    img_path = os.path.join(_get_assets_dir(), "maintenance.gif")
    if os.path.exists(img_path):
        img_label = QLabel()
        pixmap = QPixmap(img_path).scaled(
            140, 140,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        img_label.setPixmap(pixmap)
        img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card.addWidget(img_label)
        card.addSpacing(20)

    headline = QLabel(texts.MAINTENANCE_HEADLINE)
    headline.setAlignment(Qt.AlignmentFlag.AlignCenter)
    headline.setWordWrap(True)
    headline.setStyleSheet(f"""
        font-family: {FONT_HEADLINE};
        font-size: {FONT_SIZE_H1};
        color: {ACCENT_500};
        font-weight: 700;
    """)
    card.addWidget(headline)
    card.addSpacing(12)

    body = QLabel(texts.MAINTENANCE_BODY)
    body.setAlignment(Qt.AlignmentFlag.AlignCenter)
    body.setWordWrap(True)
    body.setStyleSheet(f"""
        font-family: {FONT_BODY};
        font-size: {FONT_SIZE_BODY};
        color: {PRIMARY_500};
        line-height: 1.5;
    """)
    card.addWidget(body)
    card.addSpacing(14)

    # Server-Nachricht (optional, initial versteckt)
    server_msg_label = QLabel("")
    server_msg_label.setObjectName("serverMsgLabel")
    server_msg_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    server_msg_label.setWordWrap(True)
    server_msg_label.setVisible(False)
    server_msg_label.setStyleSheet(f"""
        font-family: {FONT_BODY};
        font-size: {FONT_SIZE_BODY};
        color: {ACCENT_500};
        padding: 10px;
        background-color: rgba(250, 153, 57, 0.1) !important;
        border-radius: 6px;
    """)
    card.addWidget(server_msg_label)

    # Trennlinie (dezent)
    separator = QFrame()
    separator.setFixedHeight(1)
    separator.setStyleSheet(f"background-color: {_CARD_BORDER}; border: none;")
    card.addSpacing(14)
    card.addWidget(separator)
    card.addSpacing(14)

    contact = QLabel(texts.MAINTENANCE_CONTACT)
    contact.setAlignment(Qt.AlignmentFlag.AlignCenter)
    contact.setWordWrap(True)
    contact.setStyleSheet(f"""
        font-family: {FONT_BODY};
        font-size: {FONT_SIZE_CAPTION};
        color: rgba(136, 169, 195, 0.7);
    """)
    card.addWidget(contact)
    card.addSpacing(4)

    recheck = QLabel(texts.MAINTENANCE_RECHECK_INFO)
    recheck.setAlignment(Qt.AlignmentFlag.AlignCenter)
    recheck.setStyleSheet(f"""
        font-family: {FONT_BODY};
        font-size: {FONT_SIZE_CAPTION};
        color: rgba(136, 169, 195, 0.5);
    """)
    card.addWidget(recheck)

    parent_layout.addWidget(container, alignment=Qt.AlignmentFlag.AlignCenter)

    return {'server_msg_label': server_msg_label, 'container': container}


class MaintenanceOverlay(QWidget):
    """Overlay ueber dem MainHub wenn waehrend des Betriebs der Zugang gesperrt wird.

    SICHERHEIT: Das Overlay blockiert ALLE Interaktion mit der darunterliegenden App.
    Der Schliessen-Button beendet die GESAMTE Applikation (QApplication.quit()).
    """

    access_restored = Signal()

    def __init__(self, api_client, user, parent=None):
        super().__init__(parent)
        self._api_client = api_client
        self._user = user
        self._worker = None

        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setVisible(False)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        refs = _build_maintenance_content(layout)
        self._server_msg_label = refs['server_msg_label']

        layout.addSpacing(16)

        close_btn = QPushButton(texts.MAINTENANCE_CLOSE_BTN)
        close_btn.setFixedWidth(180)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(_get_close_button_style())
        close_btn.clicked.connect(self._quit_app)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        self._recheck_timer = QTimer(self)
        self._recheck_timer.timeout.connect(self._check_status)

    @property
    def is_blocking(self) -> bool:
        """True wenn das Overlay aktiv den Zugang blockiert."""
        return self.isVisible()

    def show_overlay(self, server_message: str = ''):
        """Overlay einblenden -- blockiert ab sofort jede Interaktion."""
        self._update_server_message(server_message)
        if self.parent():
            self.setGeometry(self.parent().rect())
        self.setVisible(True)
        self.raise_()
        self.setFocus()
        self._recheck_timer.start(RECHECK_INTERVAL_MS)
        logger.info("Maintenance-Overlay eingeblendet - App gesperrt")

    def hide_overlay(self):
        """Overlay ausblenden (nur wenn Zugang wiederhergestellt)."""
        self._recheck_timer.stop()
        self.setVisible(False)
        logger.info("Maintenance-Overlay ausgeblendet - Zugang wiederhergestellt")

    def _quit_app(self):
        """Gesamte Applikation sofort beenden."""
        logger.info("Maintenance: Nutzer hat App geschlossen")
        QApplication.quit()

    def _check_status(self):
        if self._worker and self._worker.isRunning():
            return
        self._worker = SystemStatusCheckWorker(self._api_client, self)
        self._worker.status_received.connect(self._on_status_received)
        self._worker.check_failed.connect(self._on_check_failed)
        self._worker.start()

    def _on_status_received(self, status: str, message: str):
        from api.system_status import has_access
        from config.runtime import is_dev_mode

        if has_access(status, self._user.is_admin, is_dev_mode()):
            self.hide_overlay()
            self.access_restored.emit()
        else:
            self._update_server_message(message)

    def _on_check_failed(self):
        """Fail-Closed: Bei Fehler bleibt Overlay aktiv."""
        logger.warning("Overlay Status-Check fehlgeschlagen - Sperre bleibt bestehen")

    def _update_server_message(self, message: str):
        if message:
            self._server_msg_label.setText(f"{texts.MAINTENANCE_SERVER_MSG}\n{message}")
            self._server_msg_label.setVisible(True)
        else:
            self._server_msg_label.setVisible(False)

    def paintEvent(self, event):
        """Halbtransparenter dunkler Hintergrund -- blockiert alles darunter."""
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 15, 35, 200))
        super().paintEvent(event)

    def mousePressEvent(self, event):
        """Alle Mausklicks abfangen -- nichts darf durchkommen."""
        event.accept()

    def mouseReleaseEvent(self, event):
        event.accept()

    def mouseDoubleClickEvent(self, event):
        event.accept()

    def keyPressEvent(self, event):
        """Alle Tastendruecke abfangen (inkl. Escape, Tab etc.)."""
        event.accept()


class MaintenanceWindow(QMainWindow):
    """Eigenstaendiges Fenster wenn beim Login kein Zugang besteht.

    SICHERHEIT: Dieses Fenster ist die EINZIGE UI wenn kein Zugang besteht.
    Das Schliessen (X-Button, Close-Button, Alt+F4) beendet die gesamte App
    ueber QApplication.quit(). Es gibt KEINEN Weg zur normalen App.
    """

    access_granted = Signal()

    def __init__(self, api_client, user, server_message: str = '', parent=None):
        super().__init__(parent)
        self._api_client = api_client
        self._user = user
        self._worker = None
        self._access_restored = False

        self.setWindowTitle(texts.MAINTENANCE_TITLE)
        self.setMinimumSize(560, 620)
        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: {PRIMARY_900};
            }}
        """)

        central = QWidget()
        central.setStyleSheet("background: transparent;")
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        refs = _build_maintenance_content(layout)
        self._server_msg_label = refs['server_msg_label']

        if server_message:
            self._server_msg_label.setText(f"{texts.MAINTENANCE_SERVER_MSG}\n{server_message}")
            self._server_msg_label.setVisible(True)

        layout.addSpacing(20)

        close_btn = QPushButton(texts.MAINTENANCE_CLOSE_BTN)
        close_btn.setFixedWidth(180)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(_get_close_button_style())
        close_btn.clicked.connect(self._quit_app)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addSpacing(20)

        self._recheck_timer = QTimer(self)
        self._recheck_timer.timeout.connect(self._check_status)
        self._recheck_timer.start(RECHECK_INTERVAL_MS)

    def _quit_app(self):
        """Gesamte Applikation sofort beenden."""
        logger.info("Maintenance-Window: Nutzer hat App geschlossen")
        QApplication.quit()

    def closeEvent(self, event):
        """Schliessen beendet die App -- AUSSER Zugang wurde wiederhergestellt."""
        if self._access_restored:
            logger.info("Maintenance-Window: Zugang wiederhergestellt, Fenster schliesst normal")
            event.accept()
            return
        logger.info("Maintenance-Window closeEvent: App wird beendet")
        event.accept()
        QApplication.quit()

    def _check_status(self):
        if self._worker and self._worker.isRunning():
            return
        self._worker = SystemStatusCheckWorker(self._api_client, self)
        self._worker.status_received.connect(self._on_status_received)
        self._worker.check_failed.connect(self._on_check_failed)
        self._worker.start()

    def _on_status_received(self, status: str, message: str):
        from api.system_status import has_access
        from config.runtime import is_dev_mode

        if has_access(status, self._user.is_admin, is_dev_mode()):
            self._recheck_timer.stop()
            self._access_restored = True
            self.access_granted.emit()
        else:
            if message:
                self._server_msg_label.setText(f"{texts.MAINTENANCE_SERVER_MSG}\n{message}")
                self._server_msg_label.setVisible(True)
            else:
                self._server_msg_label.setVisible(False)

    def _on_check_failed(self):
        """Fail-Closed: Bei Fehler bleibt Wartungsfenster aktiv."""
        logger.warning("MaintenanceWindow Status-Check fehlgeschlagen - Sperre bleibt bestehen")
