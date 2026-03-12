# -*- coding: utf-8 -*-
"""
Screenshot-Upload-Widget mit Drag-and-Drop-Dropzone und Vorschau-Karte.

Akzeptiert PNG/JPG/JPEG bis 8 MB. Bietet Drag-and-Drop sowie Dateiauswahl
per Klick. Nach Auswahl wird eine kompakte Vorschau mit Dateiname, Groesse
und Entfernen-Button angezeigt.

Signals:
    screenshot_selected(str)  – Pfad der ausgewaehlten Datei
    screenshot_removed()      – Datei wurde entfernt
"""

import os
import logging

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QFileDialog,
)
from PySide6.QtCore import Signal, Qt, QMimeData
from PySide6.QtGui import QPixmap, QDragEnterEvent, QDropEvent

from i18n import de as texts
import ui.styles.tokens as tok

logger = logging.getLogger(__name__)

_MAX_FILE_SIZE = 8 * 1024 * 1024
_ALLOWED_EXTENSIONS = {'.png', '.jpg', '.jpeg'}


class _Dropzone(QFrame):
    """Klickbare und Drag-fähige Upload-Fläche."""

    file_dropped = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(130)
        self._is_drag_over = False
        self._apply_style(False)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(4)

        icon_lbl = QLabel("\U0001F5BC")
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setStyleSheet(
            f"font-size: 24pt; color: {tok.PRIMARY_500}; "
            f"background: transparent; border: none;"
        )
        icon_lbl.setAttribute(Qt.WA_TransparentForMouseEvents)
        layout.addWidget(icon_lbl)

        drop_lbl = QLabel(texts.FEEDBACK_SCREENSHOT_DROP)
        drop_lbl.setAlignment(Qt.AlignCenter)
        drop_lbl.setStyleSheet(
            f"font-family: {tok.FONT_BODY}; font-size: {tok.FONT_SIZE_BODY}; "
            f"font-weight: {tok.FONT_WEIGHT_MEDIUM}; color: {tok.TEXT_PRIMARY}; "
            f"background: transparent; border: none;"
        )
        drop_lbl.setAttribute(Qt.WA_TransparentForMouseEvents)
        layout.addWidget(drop_lbl)

        browse_lbl = QLabel(texts.FEEDBACK_SCREENSHOT_BROWSE)
        browse_lbl.setAlignment(Qt.AlignCenter)
        browse_lbl.setStyleSheet(
            f"font-family: {tok.FONT_BODY}; font-size: {tok.FONT_SIZE_CAPTION}; "
            f"color: {tok.TEXT_SECONDARY}; background: transparent; border: none;"
        )
        browse_lbl.setAttribute(Qt.WA_TransparentForMouseEvents)
        layout.addWidget(browse_lbl)

        fmt_lbl = QLabel(texts.FEEDBACK_SCREENSHOT_FORMATS)
        fmt_lbl.setAlignment(Qt.AlignCenter)
        fmt_lbl.setStyleSheet(
            f"font-family: {tok.FONT_BODY}; font-size: 7pt; "
            f"color: {tok.TEXT_DISABLED}; background: transparent; border: none;"
        )
        fmt_lbl.setAttribute(Qt.WA_TransparentForMouseEvents)
        layout.addWidget(fmt_lbl)

    def _apply_style(self, drag_over: bool):
        if drag_over:
            border_color = tok.ACCENT_500
            bg = "rgba(250, 153, 57, 0.06)"
        else:
            border_color = tok.BORDER_DEFAULT
            bg = tok.BG_TERTIARY
        self.setStyleSheet(f"""
            _Dropzone {{
                background-color: {bg};
                border: 2px dashed {border_color};
                border-radius: {tok.RADIUS_XL};
            }}
            _Dropzone:hover {{
                border-color: {tok.PRIMARY_500};
            }}
        """)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            path, _ = QFileDialog.getOpenFileName(
                self,
                texts.FEEDBACK_SCREENSHOT_TITLE,
                "",
                "Images (*.png *.jpg *.jpeg)",
            )
            if path:
                self.file_dropped.emit(path)
        super().mousePressEvent(event)

    def dragEnterEvent(self, event: QDragEnterEvent):
        mime: QMimeData = event.mimeData()
        if mime.hasUrls() and len(mime.urls()) == 1:
            url = mime.urls()[0]
            if url.isLocalFile():
                ext = os.path.splitext(url.toLocalFile())[1].lower()
                if ext in _ALLOWED_EXTENSIONS:
                    event.acceptProposedAction()
                    self._is_drag_over = True
                    self._apply_style(True)
                    return
        event.ignore()

    def dragLeaveEvent(self, event):
        self._is_drag_over = False
        self._apply_style(False)

    def dropEvent(self, event: QDropEvent):
        self._is_drag_over = False
        self._apply_style(False)
        mime: QMimeData = event.mimeData()
        if mime.hasUrls() and len(mime.urls()) == 1:
            path = mime.urls()[0].toLocalFile()
            event.acceptProposedAction()
            self.file_dropped.emit(path)


class _PreviewCard(QFrame):
    """Kompakte Vorschau-Karte mit Thumbnail, Dateiname, Groesse und Entfernen."""

    remove_requested = Signal()

    def __init__(self, file_path: str, parent=None):
        super().__init__(parent)
        self._path = file_path
        self.setFixedHeight(80)
        self.setStyleSheet(f"""
            _PreviewCard {{
                background-color: {tok.BG_PRIMARY};
                border: 1px solid {tok.BORDER_DEFAULT};
                border-radius: {tok.RADIUS_LG};
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(12)

        thumb_lbl = QLabel()
        thumb_lbl.setFixedSize(60, 60)
        thumb_lbl.setStyleSheet(
            f"border-radius: {tok.RADIUS_MD}; border: 1px solid {tok.BORDER_DEFAULT}; "
            f"background: {tok.BG_TERTIARY};"
        )
        pix = QPixmap(file_path)
        if not pix.isNull():
            thumb_lbl.setPixmap(
                pix.scaled(60, 60, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
            thumb_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(thumb_lbl)

        info_col = QVBoxLayout()
        info_col.setSpacing(2)

        name_lbl = QLabel(os.path.basename(file_path))
        name_lbl.setStyleSheet(
            f"font-family: {tok.FONT_BODY}; font-size: {tok.FONT_SIZE_BODY}; "
            f"font-weight: {tok.FONT_WEIGHT_MEDIUM}; color: {tok.TEXT_PRIMARY}; "
            f"border: none; background: transparent;"
        )
        info_col.addWidget(name_lbl)

        try:
            size_bytes = os.path.getsize(file_path)
            if size_bytes >= 1024 * 1024:
                size_str = f"{size_bytes / (1024 * 1024):.1f} MB"
            else:
                size_str = f"{size_bytes / 1024:.0f} KB"
        except OSError:
            size_str = "–"

        size_lbl = QLabel(size_str)
        size_lbl.setStyleSheet(
            f"font-family: {tok.FONT_BODY}; font-size: {tok.FONT_SIZE_CAPTION}; "
            f"color: {tok.TEXT_SECONDARY}; border: none; background: transparent;"
        )
        info_col.addWidget(size_lbl)

        layout.addLayout(info_col, 1)

        remove_btn = QPushButton(texts.FEEDBACK_SCREENSHOT_REMOVE)
        remove_btn.setCursor(Qt.PointingHandCursor)
        remove_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: 1px solid {tok.BORDER_DEFAULT};
                border-radius: {tok.RADIUS_MD}; padding: 4px 12px;
                font-family: {tok.FONT_BODY}; font-size: {tok.FONT_SIZE_CAPTION};
                color: {tok.ERROR};
            }}
            QPushButton:hover {{
                background-color: {tok.ERROR_LIGHT}; border-color: {tok.ERROR};
            }}
        """)
        remove_btn.clicked.connect(self.remove_requested.emit)
        layout.addWidget(remove_btn, alignment=Qt.AlignVCenter)


class ScreenshotUploadWidget(QWidget):
    """Hochwertige Screenshot-Upload-Komponente mit Dropzone und Preview."""

    screenshot_selected = Signal(str)
    screenshot_removed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._file_path: str | None = None
        self._error_label: QLabel | None = None
        self._setup_ui()

    @property
    def file_path(self) -> str | None:
        return self._file_path

    def _setup_ui(self):
        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(0, 0, 0, 0)
        self._root.setSpacing(6)

        title = QLabel(texts.FEEDBACK_SCREENSHOT_TITLE)
        title.setStyleSheet(
            f"font-family: {tok.FONT_BODY}; font-size: {tok.FONT_SIZE_BODY}; "
            f"font-weight: {tok.FONT_WEIGHT_MEDIUM}; color: {tok.TEXT_PRIMARY};"
        )
        self._root.addWidget(title)

        desc = QLabel(texts.FEEDBACK_SCREENSHOT_DESC)
        desc.setWordWrap(True)
        desc.setStyleSheet(
            f"font-family: {tok.FONT_BODY}; font-size: {tok.FONT_SIZE_CAPTION}; "
            f"color: {tok.TEXT_SECONDARY};"
        )
        self._root.addWidget(desc)

        self._dropzone = _Dropzone()
        self._dropzone.file_dropped.connect(self._on_file_selected)
        self._root.addWidget(self._dropzone)

        self._error_label = QLabel()
        self._error_label.setWordWrap(True)
        self._error_label.setStyleSheet(
            f"font-family: {tok.FONT_BODY}; font-size: {tok.FONT_SIZE_CAPTION}; "
            f"color: {tok.ERROR};"
        )
        self._error_label.hide()
        self._root.addWidget(self._error_label)

        self._preview: _PreviewCard | None = None

    def _on_file_selected(self, path: str):
        ext = os.path.splitext(path)[1].lower()
        if ext not in _ALLOWED_EXTENSIONS:
            self._show_error(texts.FEEDBACK_SCREENSHOT_INVALID_TYPE)
            return

        try:
            size = os.path.getsize(path)
        except OSError:
            return
        if size > _MAX_FILE_SIZE:
            self._show_error(texts.FEEDBACK_SCREENSHOT_TOO_LARGE)
            return

        self._clear_error()
        self._set_file(path)

    def _set_file(self, path: str):
        self._file_path = path
        self._dropzone.hide()

        if self._preview:
            self._preview.deleteLater()

        self._preview = _PreviewCard(path)
        self._preview.remove_requested.connect(self._on_remove)
        self._root.addWidget(self._preview)

        self.screenshot_selected.emit(path)

    def _on_remove(self):
        self._file_path = None
        if self._preview:
            self._preview.deleteLater()
            self._preview = None
        self._dropzone.show()
        self.screenshot_removed.emit()

    def _show_error(self, message: str):
        self._error_label.setText(message)
        self._error_label.show()

    def _clear_error(self):
        self._error_label.setText("")
        self._error_label.hide()

    def reset(self):
        """Setzt das Widget in den Ausgangszustand zurueck."""
        self._on_remove()
        self._clear_error()
