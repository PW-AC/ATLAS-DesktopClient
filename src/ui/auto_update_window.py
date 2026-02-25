"""
ACENCIA ATLAS - Automatisches Update-Fenster

Nicht-interaktives Fenster fuer Pflicht-Updates.
Download startet sofort, Installation + Neustart passiert automatisch.
Einzige Nutzerinteraktion: Retry-Button bei Fehler.
"""

import sys
import logging
from typing import Optional
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QFrame, QSizePolicy
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QFont, QIcon

from services.update_service import UpdateInfo, UpdateService, UpdateDownloadError
from i18n import de as texts

from ui.styles.tokens import (
    PRIMARY_900, PRIMARY_500, PRIMARY_100, PRIMARY_0,
    ACCENT_500,
    FONT_HEADLINE, FONT_BODY,
    FONT_SIZE_BODY, FONT_SIZE_CAPTION,
    RADIUS_MD
)

logger = logging.getLogger(__name__)


def _format_file_size(size_bytes: int) -> str:
    """Formatiert Bytes in lesbare Groesse."""
    if size_bytes <= 0:
        return "Unbekannt"
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


class _DownloadWorker(QThread):
    """Worker-Thread fuer den Download des Installers."""
    progress = Signal(int, int)
    finished = Signal(str)
    error = Signal(str)

    def __init__(self, update_service: UpdateService, update_info: UpdateInfo):
        super().__init__()
        self._service = update_service
        self._info = update_info

    def run(self):
        try:
            path = self._service.download_update(
                self._info,
                progress_callback=self._on_progress
            )
            self.finished.emit(str(path))
        except UpdateDownloadError as e:
            self.error.emit(str(e))
        except Exception as e:
            self.error.emit(str(e))

    def _on_progress(self, downloaded: int, total: int):
        self.progress.emit(downloaded, total)


class AutoUpdateWindow(QWidget):
    """
    Nicht-interaktives Update-Fenster fuer Pflicht-Updates.

    Startet Download automatisch, installiert und beendet die App.
    Kein Close-Button, kein Escape - der Nutzer muss nicht interagieren.
    Einzige Ausnahme: Retry-Button bei Download-Fehler.
    """

    def __init__(self, update_info: UpdateInfo, update_service: UpdateService,
                 parent=None):
        super().__init__(parent)
        self._update_info = update_info
        self._update_service = update_service
        self._download_worker: Optional[_DownloadWorker] = None
        self._is_downloading = False
        self._download_started = False
        self._installation_started = False

        self.setWindowFlags(
            Qt.Window
            | Qt.CustomizeWindowHint
            | Qt.WindowTitleHint
            | Qt.WindowStaysOnTopHint
        )
        self.setWindowTitle(texts.AUTO_UPDATE_TITLE)
        self.setFixedSize(480, 320)
        self._setup_ui()

    def _setup_ui(self):
        """Baut die UI auf."""
        self.setStyleSheet(f"background-color: {PRIMARY_0};")

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(32, 32, 32, 32)

        layout.addStretch(1)

        # Titel
        title = QLabel(texts.AUTO_UPDATE_TITLE)
        title.setFont(QFont(FONT_HEADLINE, 18, QFont.Bold))
        title.setStyleSheet(f"color: {PRIMARY_900};")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # Versionsinfo
        version_text = texts.AUTO_UPDATE_VERSION_INFO.format(
            current=self._update_info.current_version,
            new=self._update_info.latest_version,
        )
        version_label = QLabel(version_text)
        version_label.setFont(QFont(FONT_BODY, 12))
        version_label.setStyleSheet(f"color: {PRIMARY_500};")
        version_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(version_label)

        layout.addSpacing(16)

        # Status-Text
        self._status_label = QLabel(texts.AUTO_UPDATE_DOWNLOADING)
        self._status_label.setFont(QFont(FONT_BODY, 11))
        self._status_label.setStyleSheet(f"color: {PRIMARY_900};")
        self._status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._status_label)

        # Progress-Bar
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setFixedHeight(8)
        self._progress_bar.setStyleSheet(f"""
            QProgressBar {{
                border: none;
                border-radius: 4px;
                background-color: {PRIMARY_100};
            }}
            QProgressBar::chunk {{
                background-color: {ACCENT_500};
                border-radius: 4px;
            }}
        """)
        layout.addWidget(self._progress_bar)

        # Detail-Zeile (z.B. "12.3 MB / 45.0 MB")
        self._detail_label = QLabel("")
        self._detail_label.setStyleSheet(
            f"color: {PRIMARY_500}; font-size: {FONT_SIZE_CAPTION};"
        )
        self._detail_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._detail_label)

        # Fehler-Bereich (anfangs versteckt)
        self._error_frame = QFrame()
        error_layout = QVBoxLayout(self._error_frame)
        error_layout.setContentsMargins(0, 8, 0, 0)

        self._error_label = QLabel()
        self._error_label.setStyleSheet("color: #dc2626; font-weight: bold;")
        self._error_label.setAlignment(Qt.AlignCenter)
        self._error_label.setWordWrap(True)
        error_layout.addWidget(self._error_label)

        retry_layout = QHBoxLayout()
        retry_layout.addStretch()
        self._retry_btn = QPushButton(texts.AUTO_UPDATE_RETRY)
        self._retry_btn.setMinimumWidth(160)
        self._retry_btn.setMinimumHeight(36)
        self._retry_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ACCENT_500};
                color: {PRIMARY_0};
                border: none;
                border-radius: {RADIUS_MD};
                padding: 8px 20px;
                font-family: {FONT_BODY};
                font-size: {FONT_SIZE_BODY};
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #e0872f;
            }}
        """)
        self._retry_btn.clicked.connect(self._start_download)
        retry_layout.addWidget(self._retry_btn)
        retry_layout.addStretch()
        error_layout.addLayout(retry_layout)

        self._error_frame.setVisible(False)
        layout.addWidget(self._error_frame)

        layout.addStretch(1)

    def showEvent(self, event):
        """Startet den Download automatisch beim ersten Anzeigen."""
        super().showEvent(event)
        if not self._download_started:
            self._download_started = True
            QTimer.singleShot(100, self._start_download)

    def _start_download(self):
        """Startet den Download des Updates."""
        if self._is_downloading:
            return

        self._is_downloading = True
        self._error_frame.setVisible(False)
        self._progress_bar.setVisible(True)
        self._progress_bar.setValue(0)
        self._detail_label.setVisible(True)
        self._status_label.setText(texts.AUTO_UPDATE_DOWNLOADING)
        self._status_label.setStyleSheet(f"color: {PRIMARY_900};")

        self._download_worker = _DownloadWorker(self._update_service, self._update_info)
        self._download_worker.progress.connect(self._on_progress)
        self._download_worker.finished.connect(self._on_download_finished)
        self._download_worker.error.connect(self._on_download_error)
        self._download_worker.start()

    def _on_progress(self, downloaded: int, total: int):
        """Aktualisiert den Fortschritt."""
        if total > 0:
            percent = int(downloaded / total * 100)
            self._progress_bar.setValue(percent)
            self._detail_label.setText(
                texts.UPDATE_DOWNLOAD_PROGRESS.format(
                    downloaded=_format_file_size(downloaded),
                    total=_format_file_size(total),
                )
            )
        else:
            self._detail_label.setText(_format_file_size(downloaded))

    def _on_download_finished(self, path: str):
        """Download abgeschlossen - Mutex freigeben, dann Installation starten."""
        self._progress_bar.setValue(100)
        self._status_label.setText(texts.AUTO_UPDATE_INSTALLING)
        self._detail_label.setText("")

        try:
            from main import release_single_instance_mutex
            release_single_instance_mutex()

            self._update_service.install_update(Path(path))
            self._installation_started = True
            self._status_label.setText(texts.AUTO_UPDATE_RESTARTING)
            from PySide6.QtWidgets import QApplication
            QTimer.singleShot(3000, QApplication.instance().quit)
        except UpdateDownloadError as e:
            self._on_download_error(str(e))

    def _on_download_error(self, error_msg: str):
        """Download fehlgeschlagen - Retry-Button anzeigen."""
        self._is_downloading = False
        self._progress_bar.setVisible(False)
        self._detail_label.setVisible(False)
        self._status_label.setText("")

        self._error_label.setText(
            texts.AUTO_UPDATE_ERROR.format(error=error_msg)
        )
        self._error_frame.setVisible(True)

        logger.error(f"Auto-Update fehlgeschlagen: {error_msg}")

    def closeEvent(self, event):
        """Verhindert Schliessen waehrend Download, erlaubt nach Installations-Start."""
        if self._installation_started:
            if self._download_worker and self._download_worker.isRunning():
                self._download_worker.quit()
                self._download_worker.wait(3000)
            event.accept()
        else:
            event.ignore()

    def keyPressEvent(self, event):
        """Verhindert Escape."""
        if event.key() == Qt.Key_Escape:
            return
        super().keyPressEvent(event)
