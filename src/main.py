#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BiPRO-GDV Tool - Haupteinstiegspunkt

Ein Desktop-Tool für BiPRO-Datenabruf und GDV-Bearbeitung.
Visuelles Design basiert auf ACENCIA Corporate Identity.
"""

import sys
import os
import logging
from logging.handlers import RotatingFileHandler

from PySide6.QtWidgets import QApplication, QDialog, QMessageBox
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QFontDatabase, QIcon

LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

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

from ui.login_dialog import LoginDialog
from ui.main_hub import MainHub
from ui.styles.tokens import get_application_stylesheet, FONT_BODY


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


def main():
    """Hauptfunktion zum Starten der Anwendung."""
    app = QApplication(sys.argv)
    
    # Anwendungsweite Einstellungen
    app.setApplicationName("BiPRO-GDV Tool")
    app.setApplicationVersion("0.8.0")
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
        
        sys.exit(app.exec())
    else:
        # Login abgebrochen
        logger.info("Login abgebrochen")
        sys.exit(0)


if __name__ == "__main__":
    main()
