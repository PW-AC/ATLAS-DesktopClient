"""
ACENCIA ATLAS - Releases Panel

Standalone QWidget fuer die Release-Verwaltung im Admin-Bereich.
Extrahiert aus admin_view.py (Schritt 5 Refactoring).
"""

import logging

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QComboBox, QDialog, QMessageBox,
    QHeaderView, QAbstractItemView,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor

from api.client import APIClient, APIError
from api.releases import ReleasesAPI
from i18n import de as texts

from ui.styles.tokens import (
    PRIMARY_900, PRIMARY_500,
    ACCENT_500, ACCENT_100, SUCCESS,
    FONT_HEADLINE, FONT_BODY,
    FONT_SIZE_H2,
    RADIUS_MD, RADIUS_SM,
)
from ui.admin.workers import LoadReleasesWorker, UploadReleaseWorker
from ui.admin.dialogs import ReleaseUploadDialog, ReleaseEditDialog

logger = logging.getLogger(__name__)


RELEASE_STATUS_COLORS = {
    'pending': '#95a5a6',
    'validated': '#3498db',
    'blocked': '#e74c3c',
    'active': SUCCESS,
    'mandatory': '#e74c3c',
    'deprecated': '#f39c12',
    'withdrawn': '#95a5a6',
}

RELEASE_STATUS_NAMES = {
    'pending': texts.RELEASES_STATUS_PENDING,
    'validated': texts.RELEASES_STATUS_VALIDATED,
    'blocked': texts.RELEASES_STATUS_BLOCKED,
    'active': texts.RELEASES_STATUS_ACTIVE,
    'mandatory': texts.RELEASES_STATUS_MANDATORY,
    'deprecated': texts.RELEASES_STATUS_DEPRECATED,
    'withdrawn': texts.RELEASES_STATUS_WITHDRAWN,
}

RELEASE_CHANNEL_NAMES = {
    'stable': texts.RELEASES_CHANNEL_STABLE,
    'beta': texts.RELEASES_CHANNEL_BETA,
    'dev': texts.RELEASES_CHANNEL_DEV,
}


class ReleasesPanel(QWidget):
    """Release-Verwaltung: Upload, Status, Channel, Filter, Bearbeiten, Loeschen."""

    def __init__(self, api_client: APIClient, toast_manager,
                 releases_api: ReleasesAPI, **kwargs):
        super().__init__()
        self._api_client = api_client
        self._toast_manager = toast_manager
        self._releases_api = releases_api
        self._releases_data = []
        self._active_workers = []
        self._create_ui()

    def load_data(self):
        """Oeffentliche Methode zum Laden der Releases."""
        self._load_releases()

    # ----------------------------------------------------------------
    # UI
    # ----------------------------------------------------------------

    def _create_ui(self):
        layout = QVBoxLayout(self)
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
        self._releases_table.setColumnWidth(7, 280)

        layout.addWidget(self._releases_table)

    # ----------------------------------------------------------------
    # Data loading
    # ----------------------------------------------------------------

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

    # ----------------------------------------------------------------
    # Filtering
    # ----------------------------------------------------------------

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
            channel_name = RELEASE_CHANNEL_NAMES.get(channel, channel)
            channel_item = QTableWidgetItem(channel_name)
            channel_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._releases_table.setItem(row, 1, channel_item)

            # Status (farbkodiert)
            status = release.get('status', 'active')
            status_name = RELEASE_STATUS_NAMES.get(status, status)
            status_item = QTableWidgetItem(f"● {status_name}")
            status_color = RELEASE_STATUS_COLORS.get(status, PRIMARY_500)
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

            release_status = release.get('status', 'active')

            # Validieren-Button (nur bei pending/blocked)
            if release_status in ('pending', 'blocked'):
                validate_btn = QPushButton(texts.RELEASES_VALIDATE_BTN)
                validate_btn.setFixedHeight(26)
                validate_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                validate_btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: #3498db;
                        color: white;
                        border: none;
                        border-radius: {RADIUS_SM};
                        padding: 2px 10px;
                        font-family: {FONT_BODY};
                        font-size: 12px;
                        font-weight: bold;
                    }}
                    QPushButton:hover {{ background-color: #2980b9; }}
                """)
                validate_btn.clicked.connect(lambda checked, r=release: self._validate_release(r))
                actions_layout.addWidget(validate_btn)

            # Aktivieren-Button (nur bei validated)
            if release_status == 'validated':
                activate_btn = QPushButton(texts.RELEASES_ACTIVATE_BTN)
                activate_btn.setFixedHeight(26)
                activate_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                activate_btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {SUCCESS};
                        color: white;
                        border: none;
                        border-radius: {RADIUS_SM};
                        padding: 2px 10px;
                        font-family: {FONT_BODY};
                        font-size: 12px;
                        font-weight: bold;
                    }}
                    QPushButton:hover {{ background-color: #27ae60; }}
                """)
                activate_btn.clicked.connect(lambda checked, r=release: self._activate_release(r))
                actions_layout.addWidget(activate_btn)

            # Zurueckziehen-Button (nur bei active/mandatory)
            if release_status in ('active', 'mandatory'):
                withdraw_btn = QPushButton(texts.RELEASES_WITHDRAW_BTN)
                withdraw_btn.setFixedHeight(26)
                withdraw_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                withdraw_btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: transparent;
                        color: #e67e22;
                        border: 1px solid #e67e22;
                        border-radius: {RADIUS_SM};
                        padding: 2px 10px;
                        font-family: {FONT_BODY};
                        font-size: 12px;
                    }}
                    QPushButton:hover {{ background-color: #e67e22; color: white; }}
                """)
                withdraw_btn.clicked.connect(lambda checked, r=release: self._withdraw_release(r))
                actions_layout.addWidget(withdraw_btn)

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

            # Gate-Report-Button (wenn vorhanden)
            if release.get('gate_report'):
                report_btn = QPushButton(texts.RELEASES_GATE_REPORT_BTN)
                report_btn.setFixedHeight(26)
                report_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                report_btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: transparent;
                        color: #3498db;
                        border: 1px solid #3498db;
                        border-radius: {RADIUS_SM};
                        padding: 2px 8px;
                        font-family: {FONT_BODY};
                        font-size: 11px;
                    }}
                    QPushButton:hover {{ background-color: #3498db; color: white; }}
                """)
                report_btn.clicked.connect(lambda checked, r=release: self._show_gate_report(r))
                actions_layout.addWidget(report_btn)

            actions_layout.addStretch()
            self._releases_table.setCellWidget(row, 7, actions_widget)

        self._releases_table.setSortingEnabled(True)

    # ----------------------------------------------------------------
    # Actions
    # ----------------------------------------------------------------

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
            return

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

    def _validate_release(self, release: dict):
        """Fuehrt die Gate-Validierung fuer ein Release aus."""
        release_id = release.get('id')
        version = release.get('version', '?')

        try:
            result = self._releases_api.validate_release(release_id)
            gate_report = result.get('gate_report', {})
            overall = gate_report.get('overall', 'unknown')

            if overall == 'passed':
                self._toast_manager.show_success(
                    texts.RELEASES_GATE_ALL_PASSED.format(version=version))
            else:
                failed_gates = [g['name'] for g in gate_report.get('gates', []) if g.get('status') == 'failed']
                self._toast_manager.show_error(
                    texts.RELEASES_GATE_SOME_FAILED.format(version=version, gates=', '.join(failed_gates)))

            self._load_releases()
        except APIError as e:
            self._toast_manager.show_error(str(e))

    def _activate_release(self, release: dict):
        """Aktiviert ein validiertes Release."""
        release_id = release.get('id')
        version = release.get('version', '?')

        try:
            self._releases_api.update_release(release_id, status='active')
            self._toast_manager.show_success(
                texts.RELEASES_ACTIVATED.format(version=version))
            self._load_releases()
        except APIError as e:
            self._toast_manager.show_error(str(e))

    def _withdraw_release(self, release: dict):
        """Zieht ein aktives Release zurueck mit Bestaetigungs-Dialog."""
        version = release.get('version', '?')
        channel = release.get('channel', '?')

        reply = QMessageBox.question(
            self, texts.RELEASES_WITHDRAW_BTN,
            texts.RELEASES_WITHDRAW_CONFIRM.format(version=version),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            result = self._releases_api.withdraw_release(release.get('id'))
            fallback = result.get('fallback_release')
            if fallback:
                self._toast_manager.show_success(
                    texts.RELEASES_WITHDRAW_SUCCESS.format(version=version)
                    + " — " + texts.RELEASES_WITHDRAW_FALLBACK.format(
                        fallback_version=fallback.get('version', '?')))
            else:
                self._toast_manager.show_warning(
                    texts.RELEASES_WITHDRAW_SUCCESS.format(version=version)
                    + " — " + texts.RELEASES_WITHDRAW_NO_FALLBACK.format(channel=channel))
            self._load_releases()
        except APIError as e:
            self._toast_manager.show_error(str(e))

    def _show_gate_report(self, release: dict):
        """Zeigt den Gate-Report eines Releases an."""
        import json
        gate_report = release.get('gate_report')
        if isinstance(gate_report, str):
            gate_report = json.loads(gate_report)

        if not gate_report:
            self._toast_manager.show_warning(texts.RELEASES_NO_GATE_REPORT)
            return

        version = release.get('version', '?')
        overall = gate_report.get('overall', 'unknown')
        gates = gate_report.get('gates', [])

        lines = [f"{texts.RELEASES_GATE_REPORT_TITLE}: {version}", f"Ergebnis: {overall}", ""]
        for gate in gates:
            status_icon = {'passed': '✓', 'failed': '✗', 'skipped': '–'}.get(gate['status'], '?')
            lines.append(f"  {status_icon} {gate['name']}: {gate['details']}")

        from PySide6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QDialogButtonBox
        dlg = QDialog(self)
        dlg.setWindowTitle(texts.RELEASES_GATE_REPORT_TITLE)
        dlg.setMinimumSize(500, 400)
        layout = QVBoxLayout(dlg)
        text_widget = QTextEdit()
        text_widget.setReadOnly(True)
        text_widget.setPlainText('\n'.join(lines))
        text_widget.setStyleSheet(f"font-family: 'Consolas', monospace; font-size: 13px;")
        layout.addWidget(text_widget)
        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        btn_box.accepted.connect(dlg.accept)
        layout.addWidget(btn_box)
        dlg.exec()
