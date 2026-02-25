#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ACENCIA ATLAS - Haupteinstiegspunkt

Der Datenkern. Desktop-App für BiPRO-Datenabruf und GDV-Bearbeitung.
Visuelles Design basiert auf ACENCIA Corporate Identity.
"""

import sys
import os
import logging
import ctypes
from logging.handlers import RotatingFileHandler

from PySide6.QtWidgets import QApplication, QDialog, QMessageBox
from PySide6.QtCore import Qt, QtMsgType, qInstallMessageHandler, QThread, Signal
from PySide6.QtGui import QFont, QFontDatabase, QIcon

LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Bekannte Qt-Warnungen die unterdrueckt werden sollen
_SUPPRESSED_QT_WARNINGS = [
    "QFont::setPointSize: Point size <= 0",  # QPdfView setzt intern pointSize(-1)
]

def _qt_message_handler(mode, context, message):
    """Custom Qt Message Handler: Unterdrueckt bekannte harmlose Warnungen."""
    if mode == QtMsgType.QtWarningMsg:
        for pattern in _SUPPRESSED_QT_WARNINGS:
            if pattern in message:
                return  # Bekannte harmlose Warnung unterdruecken
    # Alle anderen Meldungen normal ausgeben
    if mode == QtMsgType.QtWarningMsg:
        logging.getLogger('qt').warning(message)
    elif mode == QtMsgType.QtCriticalMsg:
        logging.getLogger('qt').error(message)
    elif mode == QtMsgType.QtFatalMsg:
        logging.getLogger('qt').critical(message)


def _read_app_version() -> str:
    """Liest die App-Version aus der VERSION-Datei (zentrale Versionsquelle)."""
    # In PyInstaller-Bundle: VERSION liegt neben der EXE im _MEIPASS oder Arbeitsverzeichnis
    candidates = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "VERSION"),
        os.path.join(os.path.dirname(sys.executable), "VERSION"),
        os.path.join(getattr(sys, '_MEIPASS', ''), "VERSION"),
    ]
    for path in candidates:
        try:
            with open(path, 'r', encoding='utf-8-sig') as f:
                version = f.read().strip()
                if version:
                    return version
        except (FileNotFoundError, OSError):
            continue
    return "0.0.0"  # Fallback


def is_dev_mode() -> bool:
    """Erkennt ob die App im Entwicklungsmodus laeuft (python run.py statt EXE)."""
    return not getattr(sys, 'frozen', False)


APP_VERSION = _read_app_version()

def setup_logging():
    """Konfiguriert Logging mit Console + File Output."""
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logs")
    log_file = os.path.join(log_dir, "bipro_gdv.log")
    
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    formatter = logging.Formatter(LOG_FORMAT)
    
    # Console Handler (wie bisher)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # File Handler mit Rotation (5 MB, 3 Backups)
    try:
        os.makedirs(log_dir, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_file, 
            maxBytes=5 * 1024 * 1024,  # 5 MB
            backupCount=3, 
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
        root_logger.info(f"File-Logging aktiviert: {log_file}")
    except (OSError, PermissionError) as e:
        root_logger.warning(f"File-Logging nicht moeglich, nur Console: {e}")

setup_logging()

logger = logging.getLogger(__name__)

# Pfad zum src-Verzeichnis
_src_dir = os.path.dirname(os.path.abspath(__file__))
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from PySide6.QtCore import QObject, Signal as QtSignal

from ui.login_dialog import LoginDialog
from ui.main_hub import MainHub
from ui.styles.tokens import get_application_stylesheet, FONT_BODY
from i18n import de as texts


class ForcedLogoutHandler(QObject):
    """
    Vermittler fuer erzwungenen Logout aus beliebigen Threads.
    
    Der APIClient kann den forced_logout_callback aus Worker-Threads aufrufen.
    Qt-UI-Operationen (MessageBox, close) muessen aber im Main-Thread laufen.
    Dieses Signal stellt die Thread-Sicherheit sicher.
    """
    logout_requested = QtSignal(str)
    
    def __init__(self, window: MainHub, auth_api):
        super().__init__()
        self._window = window
        self._auth_api = auth_api
        self._triggered = False
        self.logout_requested.connect(self._do_forced_logout)
    
    def trigger(self, reason: str) -> None:
        """Wird vom APIClient (ggf. aus Worker-Thread) aufgerufen."""
        if not self._triggered:
            self._triggered = True
            self.logout_requested.emit(reason)
    
    def _do_forced_logout(self, reason: str) -> None:
        """Wird im Main-Thread ausgefuehrt."""
        logger.warning(f"Erzwungener Logout durchgefuehrt: {reason}")
        
        # Auth-State bereinigen
        try:
            self._auth_api.logout()
        except Exception:
            pass
        
        # Meldung anzeigen
        QMessageBox.warning(
            self._window,
            texts.FORCED_LOGOUT_TITLE,
            texts.FORCED_LOGOUT_MESSAGE
        )
        
        # Fenster schliessen
        self._window.close()


class _UpdateCheckWorker(QThread):
    """Asynchroner Update-Check im Hintergrund, blockiert nicht den Main-Thread."""
    update_found = Signal(object, object)  # (update_info, update_service)
    
    def __init__(self, api_client, current_version: str, channel: str = 'stable'):
        super().__init__()
        self._api_client = api_client
        self._current_version = current_version
        self._channel = channel
    
    def run(self):
        try:
            from services.update_service import UpdateService
            update_service = UpdateService(self._api_client, channel=self._channel)
            update_info = update_service.check_for_update(self._current_version)
            if update_info:
                self.update_found.emit(update_info, update_service)
        except Exception as e:
            logger.warning(f"Update-Check fehlgeschlagen: {e}")


def load_embedded_fonts():
    """Lädt eingebettete Schriftarten aus dem assets/fonts/ Ordner."""
    fonts_dir = os.path.join(_src_dir, "ui", "assets", "fonts")
    loaded_fonts = []
    
    if not os.path.exists(fonts_dir):
        logger.debug(f"Fonts-Ordner nicht gefunden: {fonts_dir}")
        return loaded_fonts
    
    # Alle TTF/OTF Dateien im fonts-Ordner laden
    for filename in os.listdir(fonts_dir):
        if filename.lower().endswith(('.ttf', '.otf')):
            font_path = os.path.join(fonts_dir, filename)
            font_id = QFontDatabase.addApplicationFont(font_path)
            if font_id != -1:
                families = QFontDatabase.applicationFontFamilies(font_id)
                loaded_fonts.extend(families)
                logger.info(f"Schriftart geladen: {filename} -> {', '.join(families)}")
            else:
                logger.warning(f"Schriftart konnte nicht geladen werden: {filename}")
    
    return loaded_fonts


# Single-Instance Mutex (global, damit der Handle nicht garbage-collected wird)
_instance_mutex = None

SINGLE_INSTANCE_MUTEX_NAME = "ACENCIA_ATLAS_SINGLE_INSTANCE"


def _acquire_single_instance() -> bool:
    """
    Erstellt einen Windows Named Mutex fuer Single-Instance-Schutz.
    
    Der gleiche Mutex-Name wird in installer.iss (AppMutex) verwendet,
    damit der Installer wartet bis die App geschlossen ist.
    
    Returns:
        True wenn diese Instanz die einzige ist, False wenn bereits eine laeuft.
    """
    global _instance_mutex
    
    if sys.platform != 'win32':
        return True  # Nur Windows
    
    try:
        kernel32 = ctypes.windll.kernel32
        _instance_mutex = kernel32.CreateMutexW(None, False, SINGLE_INSTANCE_MUTEX_NAME)
        last_error = kernel32.GetLastError()
        
        # ERROR_ALREADY_EXISTS = 183
        if last_error == 183:
            logger.warning("Andere Instanz laeuft bereits (Mutex existiert)")
            return False
        
        logger.info("Single-Instance Mutex erstellt")
        return True
    except Exception as e:
        logger.warning(f"Single-Instance Check fehlgeschlagen: {e}")
        return True  # Im Zweifel starten


def release_single_instance_mutex():
    """
    Gibt den Single-Instance-Mutex explizit frei.
    
    Wird vor dem Installer-Start aufgerufen, damit der Inno-Setup-Installer
    keinen Mutex-Konflikt sieht und sofort installieren kann (kein CloseApplications-Warten).
    """
    global _instance_mutex
    if _instance_mutex and sys.platform == 'win32':
        try:
            kernel32 = ctypes.windll.kernel32
            kernel32.ReleaseMutex(_instance_mutex)
            kernel32.CloseHandle(_instance_mutex)
            _instance_mutex = None
            logger.info("Single-Instance Mutex freigegeben (fuer Update)")
        except Exception as e:
            logger.warning(f"Mutex-Freigabe fehlgeschlagen: {e}")


def main():
    """Hauptfunktion zum Starten der Anwendung."""
    # Qt Message Handler installieren (vor QApplication, um alle Warnungen abzufangen)
    qInstallMessageHandler(_qt_message_handler)
    
    app = QApplication(sys.argv)
    
    # Single-Instance Check
    if not _acquire_single_instance():
        from i18n import de as _texts
        QMessageBox.warning(
            None,
            _texts.SINGLE_INSTANCE_TITLE,
            _texts.SINGLE_INSTANCE_MSG
        )
        sys.exit(0)
    
    # Anwendungsweite Einstellungen
    app.setApplicationName("ACENCIA ATLAS")
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName("ACENCIA GmbH")
    
    # App-Icon setzen (falls vorhanden)
    icon_path = os.path.join(_src_dir, "ui", "assets", "icon.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
        logger.info(f"App-Icon geladen: {icon_path}")
    
    # Eingebettete Schriftarten laden (aus assets/fonts/)
    loaded_fonts = load_embedded_fonts()
    if loaded_fonts:
        logger.info(f"Eingebettete Schriftarten: {', '.join(set(loaded_fonts))}")
    
    # Standard-Font setzen (Open Sans mit Fallback)
    if QFontDatabase.hasFamily("Open Sans"):
        default_font = QFont("Open Sans", 10)
        logger.info("Verwende Open Sans")
    else:
        default_font = QFont("Segoe UI", 10)
        logger.info("Open Sans nicht verfuegbar, verwende Segoe UI")
    app.setFont(default_font)
    
    # ACENCIA Corporate Design Stylesheet
    app.setStyleSheet(get_application_stylesheet())
    
    # Login-Dialog anzeigen
    login_dialog = LoginDialog()
    
    if login_dialog.exec() == QDialog.Accepted:
        # Login erfolgreich - Hauptfenster mit API-Client starten
        api_client = login_dialog.get_client()
        auth_api = login_dialog.get_auth()
        
        # Auth-Refresh-Callback registrieren fuer automatischen 401-Retry
        api_client.set_auth_refresh_callback(auth_api.re_authenticate)
        
        logger.info(f"Angemeldet als: {auth_api.current_user.username}")
        
        # Neues Hub-Hauptfenster erstellen und anzeigen
        window = MainHub(api_client=api_client, auth_api=auth_api)
        window.show()
        
        # === Update-Check nach Login (asynchron, blockiert UI nicht) ===
        if not is_dev_mode():
            def _on_update_found(update_info, update_service):
                try:
                    if update_info.mandatory:
                        logger.info(f"Pflicht-Update erforderlich: {update_info.latest_version}")
                        from ui.auto_update_window import AutoUpdateWindow
                        auto_update = AutoUpdateWindow(update_info, update_service)
                        auto_update.show()
                        window.close()
                    elif update_info.deprecated and not update_info.update_available:
                        window._toast_manager.show_warning(
                            texts.UPDATE_DEPRECATED_MSG.format(version=APP_VERSION),
                            duration_ms=12000
                        )
                    elif update_info.update_available:
                        from ui.update_dialog import UpdateDialog
                        dialog = UpdateDialog(update_info, update_service, mode='optional')
                        if dialog.exec() == QDialog.Accepted:
                            release_single_instance_mutex()
                            sys.exit(0)
                except Exception as e:
                    logger.warning(f"Update-Verarbeitung fehlgeschlagen: {e}")
            
            _user_channel = auth_api.current_user.update_channel if auth_api.current_user else 'stable'
            window._update_check_bg_worker = _UpdateCheckWorker(api_client, APP_VERSION, channel=_user_channel)
            window._update_check_bg_worker.update_found.connect(_on_update_found)
            window._update_check_bg_worker.start()
        else:
            logger.info("Dev-Modus erkannt (python run.py) - Update-Check uebersprungen")
        
        # Forced-Logout-Handler registrieren (Session-Invalidierung)
        forced_logout_handler = ForcedLogoutHandler(window, auth_api)
        api_client.set_forced_logout_callback(forced_logout_handler.trigger)
        
        sys.exit(app.exec())
    else:
        # Login abgebrochen
        logger.info("Login abgebrochen")
        sys.exit(0)


if __name__ == "__main__":
    main()
