"""
ACENCIA ATLAS - Workforce Exports View

Export-Management mit Standard- und Delta-SCS-Export,
Export-Historie und Download-Funktion.
"""

import os
import logging

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QComboBox, QHeaderView,
    QFrame, QAbstractItemView, QProgressBar, QFileDialog,
)
from PySide6.QtCore import Qt, QThreadPool
from PySide6.QtGui import QFont, QColor

from workforce.api_client import WorkforceApiClient
from workforce.workers import SyncWorker, DeltaExportWorker, StandardExportWorker
from ui.styles.tokens import (
    PRIMARY_500, PRIMARY_900, ACCENT_500, ACCENT_100,
    FONT_HEADLINE, FONT_BODY, FONT_SIZE_H2, FONT_SIZE_BODY, FONT_SIZE_CAPTION,
    BG_PRIMARY, BG_SECONDARY, BORDER_DEFAULT, RADIUS_MD, RADIUS_SM,
    SUCCESS, ERROR, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_DISABLED, TEXT_INVERSE,
    get_button_primary_style, get_button_secondary_style,
)
from i18n import de as texts

logger = logging.getLogger(__name__)


class ExportsView(QWidget):
    """Export-Management: Standard/Delta-Export, Historie, Download."""

    def __init__(self, wf_api: WorkforceApiClient, thread_pool: QThreadPool):
        super().__init__()
        self._wf_api = wf_api
        self._thread_pool = thread_pool
        self._toast_manager = None
        self._employers: list[dict] = []
        self._exports_data: list[dict] = []
        self._exporting = False
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        header = QHBoxLayout()
        title = QLabel(texts.WF_EXPORTS_TITLE)
        title.setStyleSheet(f"""
            font-family: {FONT_HEADLINE}; font-size: {FONT_SIZE_H2};
            color: {PRIMARY_900}; font-weight: bold;
        """)
        header.addWidget(title)
        header.addStretch()
        layout.addLayout(header)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(12)

        emp_label = QLabel(texts.WF_EMPLOYER_SELECT)
        emp_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-family: {FONT_BODY};")
        toolbar.addWidget(emp_label)

        self._employer_combo = QComboBox()
        self._employer_combo.setMinimumWidth(220)
        self._employer_combo.currentIndexChanged.connect(self._on_employer_changed)
        toolbar.addWidget(self._employer_combo)

        toolbar.addStretch()
        layout.addLayout(toolbar)

        actions_frame = QFrame()
        actions_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {BG_SECONDARY};
                border: 1px solid {BORDER_DEFAULT};
                border-radius: {RADIUS_MD};
            }}
        """)
        af_layout = QHBoxLayout(actions_frame)
        af_layout.setContentsMargins(16, 16, 16, 16)
        af_layout.setSpacing(16)

        std_section = QVBoxLayout()
        std_title = QLabel(texts.WF_EXPORT_STANDARD_TITLE)
        std_title.setStyleSheet(f"font-family: {FONT_BODY}; font-weight: bold; color: {TEXT_PRIMARY};")
        std_section.addWidget(std_title)
        std_desc = QLabel(texts.WF_EXPORT_STANDARD_DESC)
        std_desc.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: {FONT_SIZE_CAPTION};")
        std_desc.setWordWrap(True)
        std_section.addWidget(std_desc)

        self._std_export_btn = QPushButton(texts.WF_EXPORT_STANDARD_BTN)
        self._std_export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._std_export_btn.setStyleSheet(get_button_secondary_style())
        self._std_export_btn.clicked.connect(self._on_standard_export)
        std_section.addWidget(self._std_export_btn)
        af_layout.addLayout(std_section)

        sep = QFrame()
        sep.setFixedWidth(1)
        sep.setStyleSheet(f"background-color: {BORDER_DEFAULT};")
        af_layout.addWidget(sep)

        delta_section = QVBoxLayout()
        delta_title = QLabel(texts.WF_EXPORT_DELTA_TITLE)
        delta_title.setStyleSheet(f"font-family: {FONT_BODY}; font-weight: bold; color: {TEXT_PRIMARY};")
        delta_section.addWidget(delta_title)
        delta_desc = QLabel(texts.WF_EXPORT_DELTA_DESC)
        delta_desc.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: {FONT_SIZE_CAPTION};")
        delta_desc.setWordWrap(True)
        delta_section.addWidget(delta_desc)

        self._delta_export_btn = QPushButton(texts.WF_EXPORT_DELTA_BTN)
        self._delta_export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._delta_export_btn.setStyleSheet(f"""
            QPushButton {{
                padding: 6px 16px; font-family: {FONT_BODY};
                background-color: {ACCENT_500}; color: white;
                border: none; border-radius: {RADIUS_MD}; font-weight: bold;
            }}
            QPushButton:hover {{ background-color: #e88a2d; }}
            QPushButton:disabled {{ background-color: {BG_SECONDARY}; color: {TEXT_DISABLED}; }}
        """)
        self._delta_export_btn.clicked.connect(self._on_delta_export)
        delta_section.addWidget(self._delta_export_btn)
        af_layout.addLayout(delta_section)

        layout.addWidget(actions_frame)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 0)
        self._progress_bar.setVisible(False)
        self._progress_bar.setFixedHeight(20)
        layout.addWidget(self._progress_bar)

        self._progress_label = QLabel("")
        self._progress_label.setStyleSheet(f"color: {ACCENT_500}; font-size: {FONT_SIZE_CAPTION};")
        layout.addWidget(self._progress_label)

        self._diff_frame = QFrame()
        self._diff_frame.setVisible(False)
        self._diff_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {BG_SECONDARY};
                border: 1px solid {BORDER_DEFAULT};
                border-radius: {RADIUS_MD};
            }}
        """)
        diff_layout = QVBoxLayout(self._diff_frame)
        diff_layout.setContentsMargins(16, 12, 16, 12)
        self._diff_title = QLabel(texts.WF_EXPORT_DIFF_TITLE)
        self._diff_title.setStyleSheet(f"font-weight: bold; color: {TEXT_PRIMARY};")
        diff_layout.addWidget(self._diff_title)
        self._diff_content = QLabel("")
        self._diff_content.setWordWrap(True)
        self._diff_content.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: {FONT_SIZE_BODY};")
        diff_layout.addWidget(self._diff_content)
        layout.addWidget(self._diff_frame)

        hist_header = QHBoxLayout()
        hist_title = QLabel(texts.WF_EXPORT_HISTORY_TITLE)
        hist_title.setStyleSheet(f"""
            font-family: {FONT_BODY}; font-size: 11pt;
            color: {PRIMARY_900}; font-weight: bold;
        """)
        hist_header.addWidget(hist_title)
        hist_header.addStretch()

        refresh_btn = QPushButton(texts.WF_REFRESH)
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_btn.setStyleSheet(f"""
            QPushButton {{
                padding: 4px 12px; font-family: {FONT_BODY};
                background-color: {ACCENT_100}; color: {PRIMARY_900};
                border: 1px solid {ACCENT_500}; border-radius: {RADIUS_SM};
            }}
            QPushButton:hover {{ background-color: {ACCENT_500}; color: white; }}
        """)
        refresh_btn.clicked.connect(self._load_exports)
        hist_header.addWidget(refresh_btn)
        layout.addLayout(hist_header)

        self._history_table = QTableWidget()
        self._history_table.setColumnCount(5)
        self._history_table.setHorizontalHeaderLabels([
            texts.WF_COL_FILENAME, texts.WF_COL_EXPORT_TYPE,
            texts.WF_COL_SIZE, texts.WF_COL_DATE, texts.WF_COL_ACTIONS,
        ])
        self._history_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._history_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._history_table.setAlternatingRowColors(True)
        self._history_table.verticalHeader().setVisible(False)
        self._history_table.verticalHeader().setDefaultSectionSize(44)

        h = self._history_table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self._history_table.setColumnWidth(4, 160)

        layout.addWidget(self._history_table)

    # ── Data ───────────────────────────────────────────────────

    def refresh(self):
        self._load_employers()

    def _load_employers(self):
        try:
            self._employers = self._wf_api.get_employers()
            current_data = self._employer_combo.currentData()
            self._employer_combo.blockSignals(True)
            self._employer_combo.clear()
            if not self._employers:
                self._employer_combo.addItem(texts.WF_NO_EMPLOYERS, None)
            else:
                for emp in self._employers:
                    self._employer_combo.addItem(emp.get('name', '?'), emp.get('id'))
                if current_data:
                    idx = next(
                        (i for i, e in enumerate(self._employers) if e.get('id') == current_data), 0
                    )
                    self._employer_combo.setCurrentIndex(idx)
            self._employer_combo.blockSignals(False)
            self._load_exports()
        except Exception as e:
            logger.error(f"Arbeitgeber laden: {e}")

    def _on_employer_changed(self):
        self._load_exports()

    def _load_exports(self):
        employer_id = self._employer_combo.currentData()
        if not employer_id:
            self._history_table.setRowCount(0)
            return
        try:
            self._exports_data = self._wf_api.get_exports(employer_id)
            self._populate_history(self._exports_data)
        except Exception as e:
            logger.error(f"Exporte laden: {e}")
            if self._toast_manager:
                self._toast_manager.show_error(texts.WF_EXPORTS_LOAD_ERROR.format(error=str(e)))

    def _populate_history(self, exports: list):
        self._history_table.setSortingEnabled(False)
        self._history_table.setRowCount(len(exports))

        for row, exp in enumerate(exports):
            self._history_table.setItem(row, 0, QTableWidgetItem(exp.get('filename', '-')))

            export_type = exp.get('export_type', '-')
            type_display = texts.WF_EXPORT_TYPE_STANDARD if export_type == 'standard' else texts.WF_EXPORT_TYPE_DELTA
            type_item = QTableWidgetItem(type_display)
            type_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._history_table.setItem(row, 1, type_item)

            file_size = int(exp.get('file_size', 0))
            if file_size >= 1024 * 1024:
                size_str = f"{file_size / 1024 / 1024:.1f} MB"
            elif file_size >= 1024:
                size_str = f"{file_size / 1024:.1f} KB"
            elif file_size > 0:
                size_str = f"{file_size} B"
            else:
                size_str = "-"
            size_item = QTableWidgetItem(size_str)
            size_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._history_table.setItem(row, 2, size_item)

            created = exp.get('created_at', '-') or '-'
            if created != '-':
                created = created[:19].replace('T', ' ')
            self._history_table.setItem(row, 3, QTableWidgetItem(created))

            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(4, 2, 4, 2)
            actions_layout.setSpacing(4)

            dl_btn = QPushButton(texts.WF_EXPORT_DOWNLOAD_BTN)
            dl_btn.setFixedHeight(26)
            dl_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            dl_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent; color: #3498db;
                    border: 1px solid #3498db; border-radius: {RADIUS_SM};
                    padding: 2px 10px; font-family: {FONT_BODY}; font-size: 12px;
                }}
                QPushButton:hover {{ background-color: #3498db; color: white; }}
            """)
            dl_btn.clicked.connect(lambda checked, e=exp: self._on_download(e))
            actions_layout.addWidget(dl_btn)
            actions_layout.addStretch()

            self._history_table.setCellWidget(row, 4, actions_widget)

        self._history_table.setSortingEnabled(True)

    # ── Export Actions ─────────────────────────────────────────

    def _set_exporting(self, active: bool):
        self._exporting = active
        self._std_export_btn.setEnabled(not active)
        self._delta_export_btn.setEnabled(not active)
        self._progress_bar.setVisible(active)
        if not active:
            self._progress_label.setText("")

    def _on_standard_export(self):
        employer_id = self._employer_combo.currentData()
        if not employer_id or self._exporting:
            return
        self._set_exporting(True)
        self._diff_frame.setVisible(False)

        worker = StandardExportWorker(self._wf_api, employer_id)
        worker.signals.finished.connect(self._on_standard_done)
        worker.signals.error.connect(self._on_export_error)
        worker.signals.progress.connect(self._on_export_progress)
        self._thread_pool.start(worker)

    def _on_standard_done(self, result: dict):
        self._set_exporting(False)
        count = result.get('employee_count', 0)
        filepath = result.get('filepath', '')
        if self._toast_manager:
            self._toast_manager.show_success(
                texts.WF_EXPORT_STANDARD_SUCCESS.format(count=count)
            )
        self._load_exports()

    def _on_delta_export(self):
        employer_id = self._employer_combo.currentData()
        if not employer_id or self._exporting:
            return
        self._set_exporting(True)
        self._diff_frame.setVisible(False)

        worker = DeltaExportWorker(self._wf_api, employer_id)
        worker.signals.finished.connect(self._on_delta_done)
        worker.signals.error.connect(self._on_export_error)
        worker.signals.progress.connect(self._on_export_progress)
        self._thread_pool.start(worker)

    def _on_delta_done(self, result: dict):
        self._set_exporting(False)
        added = result.get('added_count', 0)
        changed = result.get('changed_count', 0)
        diff = result.get('diff', {})

        self._diff_frame.setVisible(True)
        removed = len(diff.get('removed', []))
        summary_lines = [
            texts.WF_EXPORT_DIFF_ADDED.format(count=added),
            texts.WF_EXPORT_DIFF_CHANGED.format(count=changed),
            texts.WF_EXPORT_DIFF_REMOVED.format(count=removed),
        ]
        self._diff_content.setText("\n".join(summary_lines))

        trigger_results = result.get('trigger_results', [])
        if trigger_results:
            executed = sum(1 for t in trigger_results if t.get('status') == 'success')
            failed = sum(1 for t in trigger_results if t.get('status') == 'error')
            summary_lines.append(
                texts.WF_EXPORT_TRIGGERS_SUMMARY.format(executed=executed, failed=failed)
            )
            self._diff_content.setText("\n".join(summary_lines))

        if self._toast_manager:
            self._toast_manager.show_success(
                texts.WF_EXPORT_DELTA_SUCCESS.format(added=added, changed=changed)
            )
        self._load_exports()

    def _on_export_progress(self, msg: str):
        self._progress_label.setText(msg)

    def _on_export_error(self, error: str):
        self._set_exporting(False)
        logger.error(f"Export fehlgeschlagen: {error}")
        if self._toast_manager:
            self._toast_manager.show_error(texts.WF_EXPORT_ERROR.format(error=error))

    # ── Download ───────────────────────────────────────────────

    def _on_download(self, export_item: dict):
        export_id = export_item.get('id')
        filename = export_item.get('filename', 'export.csv')

        save_path, _ = QFileDialog.getSaveFileName(
            self, texts.WF_EXPORT_SAVE_DIALOG, filename,
        )
        if not save_path:
            return

        try:
            self._wf_api.download_export(export_id, save_path)
            if self._toast_manager:
                self._toast_manager.show_success(
                    texts.WF_EXPORT_DOWNLOADED.format(filename=os.path.basename(save_path))
                )
        except Exception as e:
            logger.error(f"Download fehlgeschlagen: {e}")
            if self._toast_manager:
                self._toast_manager.show_error(str(e))
