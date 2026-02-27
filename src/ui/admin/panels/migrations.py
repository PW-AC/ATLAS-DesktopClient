"""
ACENCIA ATLAS - Migrations-Verwaltung Panel

Eigenstaendiges Admin-Panel zum Anzeigen und Ausfuehren von
Datenbank-Migrationen aus dem setup/-Verzeichnis des Backends.

- Automatische Erkennung aller .php und .sql Dateien
- Status-Anzeige: angewendet / ausstehend / manuell
- Ausfuehren mit Sicherheitsabfrage + Output-Anzeige
"""

import logging
from typing import Dict, List, Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QMessageBox, QPlainTextEdit,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from api.client import APIClient
from api.admin import AdminAPI
from i18n import de as texts

from ui.styles.tokens import (
    PRIMARY_900, PRIMARY_500, PRIMARY_0,
    ACCENT_500,
    SUCCESS, SUCCESS_LIGHT, WARNING, WARNING_LIGHT,
    ERROR, ERROR_LIGHT,
    BG_PRIMARY, BG_SECONDARY,
    BORDER_DEFAULT,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_DISABLED,
    FONT_HEADLINE, FONT_BODY, FONT_MONO,
    FONT_SIZE_BODY, FONT_SIZE_CAPTION, FONT_SIZE_H3,
    RADIUS_SM, RADIUS_MD, RADIUS_LG,
    get_button_primary_style, get_button_secondary_style,
)
from ui.admin.workers import LoadMigrationsWorker, ExecuteMigrationWorker

logger = logging.getLogger(__name__)

STATUS_COLORS = {
    'applied': SUCCESS,
    'pending': WARNING,
    'manual': ACCENT_500,
    'unknown': TEXT_DISABLED,
}

STATUS_BG = {
    'applied': SUCCESS_LIGHT,
    'pending': WARNING_LIGHT,
    'manual': f"{ACCENT_500}22",
    'unknown': BG_SECONDARY,
}


class MigrationsPanel(QWidget):
    """Admin-Panel fuer Datenbank-Migrationen."""

    def __init__(self, api_client: APIClient, toast_manager,
                 admin_api: AdminAPI, **kwargs):
        super().__init__()
        self._api_client = api_client
        self._toast_manager = toast_manager
        self._admin_api = admin_api
        self._active_workers: list = []
        self._migrations: List[Dict] = []
        self._create_ui()

    def load_data(self):
        """Wird beim Panel-Wechsel aufgerufen."""
        self._load_migrations()

    # ================================================================
    #  UI-Aufbau
    # ================================================================

    def _create_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # --- Header ---
        header = QHBoxLayout()

        title = QLabel(texts.MIGRATIONS_TITLE)
        title.setFont(QFont(FONT_HEADLINE, 18))
        title.setStyleSheet(f"color: {PRIMARY_900};")
        header.addWidget(title)

        header.addStretch()

        self._summary_label = QLabel("")
        self._summary_label.setStyleSheet(f"""
            color: {TEXT_SECONDARY};
            font-size: {FONT_SIZE_BODY};
        """)
        header.addWidget(self._summary_label)

        self._refresh_btn = QPushButton(texts.MIGRATIONS_REFRESH)
        self._refresh_btn.setStyleSheet(get_button_primary_style())
        self._refresh_btn.setMinimumWidth(160)
        self._refresh_btn.setCursor(Qt.PointingHandCursor)
        self._refresh_btn.clicked.connect(self._load_migrations)
        header.addWidget(self._refresh_btn)

        layout.addLayout(header)

        # --- Scroll-Bereich ---
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self._list_container = QWidget()
        self._list_container.setStyleSheet("background: transparent;")
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(8)

        self._empty_label = QLabel(texts.MIGRATIONS_EMPTY)
        self._empty_label.setStyleSheet(f"""
            color: {TEXT_DISABLED};
            font-size: {FONT_SIZE_BODY};
            padding: 40px;
        """)
        self._empty_label.setAlignment(Qt.AlignCenter)
        self._list_layout.addWidget(self._empty_label)

        self._list_layout.addStretch()

        scroll.setWidget(self._list_container)
        layout.addWidget(scroll)

    # ================================================================
    #  Laden
    # ================================================================

    def _load_migrations(self):
        self._refresh_btn.setEnabled(False)
        self._refresh_btn.setText(texts.MIGRATIONS_LOADING)

        worker = LoadMigrationsWorker(self._admin_api)
        worker.finished.connect(self._on_loaded)
        worker.error.connect(self._on_load_error)
        worker.finished.connect(lambda: self._cleanup_worker(worker))
        worker.error.connect(lambda: self._cleanup_worker(worker))
        self._active_workers.append(worker)
        worker.start()

    def _on_loaded(self, data: dict):
        self._refresh_btn.setEnabled(True)
        self._refresh_btn.setText(texts.MIGRATIONS_REFRESH)

        self._migrations = data.get('migrations', [])
        total = data.get('total', 0)
        applied = data.get('applied', 0)
        pending = data.get('pending', 0)
        manual = data.get('manual', 0)

        self._summary_label.setText(
            texts.MIGRATIONS_SUMMARY.format(
                total=total, applied=applied, pending=pending, manual=manual
            )
        )
        self._render_list()

    def _on_load_error(self, error: str):
        self._refresh_btn.setEnabled(True)
        self._refresh_btn.setText(texts.MIGRATIONS_REFRESH)
        logger.error(f"Migrationen laden fehlgeschlagen: {error}")
        if self._toast_manager:
            self._toast_manager.show_error(
                texts.MIGRATIONS_ERROR.format(error=error)
            )

    # ================================================================
    #  Rendering
    # ================================================================

    def _render_list(self):
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        if not self._migrations:
            empty = QLabel(texts.MIGRATIONS_EMPTY)
            empty.setStyleSheet(f"""
                color: {TEXT_DISABLED};
                font-size: {FONT_SIZE_BODY};
                padding: 40px;
            """)
            empty.setAlignment(Qt.AlignCenter)
            self._list_layout.addWidget(empty)
            self._list_layout.addStretch()
            return

        for mig in self._migrations:
            card = self._build_card(mig)
            self._list_layout.addWidget(card)

        self._list_layout.addStretch()

    def _build_card(self, mig: dict) -> QFrame:
        status = mig.get('status', 'unknown')
        mig_type = mig.get('type', '?')
        filename = mig.get('filename', '')
        modified = mig.get('modified', '')
        size_bytes = mig.get('size_bytes', 0)
        applied_at = mig.get('applied_at')
        preview = mig.get('preview', '')

        color = STATUS_COLORS.get(status, TEXT_DISABLED)
        bg = STATUS_BG.get(status, BG_SECONDARY)

        status_labels = {
            'applied': texts.MIGRATIONS_STATUS_APPLIED,
            'pending': texts.MIGRATIONS_STATUS_PENDING,
            'manual': texts.MIGRATIONS_STATUS_MANUAL,
            'unknown': texts.MIGRATIONS_STATUS_UNKNOWN,
        }

        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {BG_PRIMARY};
                border: 1px solid {BORDER_DEFAULT};
                border-radius: {RADIUS_MD};
            }}
            QFrame:hover {{
                border-color: {PRIMARY_500};
            }}
        """)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 12, 16, 12)
        card_layout.setSpacing(6)

        # --- Zeile 1: Status + Typ + Dateiname + Button ---
        row1 = QHBoxLayout()
        row1.setSpacing(12)

        status_pill = QLabel(status_labels.get(status, status))
        status_pill.setFixedHeight(24)
        status_pill.setMinimumWidth(90)
        status_pill.setMaximumWidth(90)
        status_pill.setAlignment(Qt.AlignCenter)
        status_pill.setStyleSheet(f"""
            color: {color};
            background-color: {bg};
            border-radius: 12px;
            font-size: {FONT_SIZE_CAPTION};
            font-weight: bold;
            padding: 2px 10px;
            border: none;
        """)
        row1.addWidget(status_pill)

        type_color = PRIMARY_500 if mig_type == 'php' else ACCENT_500
        type_label = QLabel(mig_type.upper())
        type_label.setFixedWidth(36)
        type_label.setAlignment(Qt.AlignCenter)
        type_label.setStyleSheet(f"""
            color: {type_color};
            font-size: {FONT_SIZE_CAPTION};
            font-family: {FONT_MONO};
            font-weight: bold;
            border: none;
            background: transparent;
        """)
        row1.addWidget(type_label)

        name_label = QLabel(filename)
        name_label.setStyleSheet(f"""
            color: {TEXT_PRIMARY};
            font-size: {FONT_SIZE_BODY};
            font-family: {FONT_MONO};
            font-weight: 500;
            border: none;
            background: transparent;
        """)
        row1.addWidget(name_label, 1)

        exec_btn = QPushButton(texts.MIGRATIONS_EXECUTE)
        exec_btn.setFixedWidth(120)
        exec_btn.setFixedHeight(30)
        exec_btn.setCursor(Qt.PointingHandCursor)
        if status == 'pending' or status == 'manual':
            exec_btn.setStyleSheet(get_button_primary_style())
        else:
            exec_btn.setStyleSheet(get_button_secondary_style())
        exec_btn.clicked.connect(lambda _, f=filename: self._confirm_execute(f))
        row1.addWidget(exec_btn)

        card_layout.addLayout(row1)

        # --- Zeile 2: Meta-Infos ---
        row2 = QHBoxLayout()
        row2.setSpacing(20)

        size_kb = round(size_bytes / 1024, 1) if size_bytes else 0
        meta_parts = [f"{size_kb} KB"]
        if modified:
            meta_parts.append(modified)
        if applied_at:
            meta_parts.append(f"{texts.MIGRATIONS_STATUS_APPLIED}: {applied_at}")

        meta_label = QLabel("  \u2502  ".join(meta_parts))
        meta_label.setStyleSheet(f"""
            color: {TEXT_SECONDARY};
            font-size: {FONT_SIZE_CAPTION};
            font-family: {FONT_MONO};
            border: none;
            background: transparent;
        """)
        row2.addWidget(meta_label)
        row2.addStretch()

        card_layout.addLayout(row2)

        # --- Zeile 3: Vorschau (gekuerzt) ---
        if preview:
            lines = preview.strip().split('\n')
            short = '\n'.join(lines[:4])
            if len(lines) > 4:
                short += '\n...'

            preview_label = QLabel(short)
            preview_label.setWordWrap(True)
            preview_label.setStyleSheet(f"""
                color: {TEXT_DISABLED};
                font-size: {FONT_SIZE_CAPTION};
                font-family: {FONT_MONO};
                padding: 6px 8px;
                background-color: {BG_SECONDARY};
                border: none;
                border-radius: {RADIUS_SM};
            """)
            card_layout.addWidget(preview_label)

        return card

    # ================================================================
    #  Ausfuehren
    # ================================================================

    def _confirm_execute(self, filename: str):
        reply = QMessageBox.warning(
            self,
            texts.MIGRATIONS_CONFIRM_TITLE,
            texts.MIGRATIONS_CONFIRM_TEXT.format(filename=filename),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self._execute(filename)

    def _execute(self, filename: str):
        worker = ExecuteMigrationWorker(self._admin_api, filename)
        worker.finished.connect(self._on_executed)
        worker.error.connect(self._on_exec_error)
        worker.finished.connect(lambda: self._cleanup_worker(worker))
        worker.error.connect(lambda: self._cleanup_worker(worker))
        self._active_workers.append(worker)
        worker.start()

    def _on_executed(self, result: dict):
        success = result.get('success', False)
        output = result.get('output', '')
        filename = result.get('filename', '')

        if success and self._toast_manager:
            self._toast_manager.show_success(
                f"{texts.MIGRATIONS_SUCCESS}: {filename}"
            )
        elif not success and self._toast_manager:
            self._toast_manager.show_error(
                texts.MIGRATIONS_ERROR.format(error=output[:200])
            )

        if output:
            self._show_output(filename, output, success)

        self._load_migrations()

    def _on_exec_error(self, error: str):
        logger.error(f"Migration fehlgeschlagen: {error}")
        if self._toast_manager:
            self._toast_manager.show_error(
                texts.MIGRATIONS_ERROR.format(error=error)
            )

    def _show_output(self, filename: str, output: str, success: bool):
        dlg = QMessageBox(self)
        dlg.setWindowTitle(f"{texts.MIGRATIONS_OUTPUT_TITLE}: {filename}")
        dlg.setIcon(QMessageBox.Information if success else QMessageBox.Warning)
        dlg.setText(
            texts.MIGRATIONS_SUCCESS if success
            else texts.MIGRATIONS_ERROR.format(error="Siehe Details")
        )
        dlg.setDetailedText(output)
        dlg.exec()

    # ================================================================
    #  Helpers
    # ================================================================

    def _cleanup_worker(self, worker):
        if worker in self._active_workers:
            self._active_workers.remove(worker)
