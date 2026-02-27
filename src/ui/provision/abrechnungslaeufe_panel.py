"""
Abrechnungslaeufe-Panel: Import-Rework mit GF-Sprache.

Ersetzt: import_panel.py
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableView,
    QHeaderView, QFrame, QPushButton, QFileDialog,
    QComboBox, QTextEdit, QProgressBar, QSizePolicy,
)
from PySide6.QtCore import (
    Qt, Signal, QTimer,
)
from typing import List, Optional, Dict
from datetime import datetime
import os
import hashlib

from api.provision import ProvisionAPI
from domain.provision.entities import ImportBatch, ImportResult
from ui.styles.tokens import (
    PRIMARY_100, PRIMARY_500, PRIMARY_900, ACCENT_500,
    BG_PRIMARY, BG_SECONDARY, BORDER_DEFAULT,
    SUCCESS, ERROR, WARNING,
    FONT_BODY, FONT_SIZE_BODY, FONT_SIZE_CAPTION,
    PILL_COLORS, get_provision_table_style,
)
from ui.provision.widgets import (
    SectionHeader, PillBadgeDelegate, PaginationBar, ProvisionLoadingOverlay,
    format_eur, get_secondary_button_style,
)
from ui.provision.workers import VuBatchesLoadWorker, VuParseFileWorker, VuImportWorker
from ui.provision.models import VuBatchesModel
from i18n import de as texts
import logging

logger = logging.getLogger(__name__)


class AbrechnungslaeufPanel(QWidget):
    """Abrechnungslaeufe: Import mit GF-Sprache und Batch-Historie.

    Implementiert IImportView fuer den ImportPresenter.
    """

    navigate_to_panel = Signal(int)

    def __init__(self, api: ProvisionAPI = None):
        super().__init__()
        self._api = api
        self._presenter = None
        self._batches_worker = None
        self._import_worker = None
        self._parse_worker = None
        self._toast_manager = None
        self._parsed_rows = []
        self._setup_ui()
        if api:
            QTimer.singleShot(100, self._load_batches)

    def set_presenter(self, presenter) -> None:
        """Verbindet dieses Panel mit dem ImportPresenter."""
        self._presenter = presenter
        presenter.set_view(self)
        self._presenter.load_batches()

    # ── IImportView ──

    def show_batches(self, batches: list) -> None:
        """View-Interface: Batch-Historie anzeigen."""
        self._batches_model.set_data(batches)

    def show_import_result(self, result: ImportResult) -> None:
        """View-Interface: Import-Ergebnis anzeigen."""
        self._on_import_done(result)

    def show_parse_progress(self, message: str) -> None:
        """View-Interface: Parse-Fortschritt anzeigen."""
        if hasattr(self, '_log'):
            self._log.append(message)

    def show_loading(self, loading: bool) -> None:
        """View-Interface: Ladezustand."""
        pass

    def show_error(self, message: str) -> None:
        """View-Interface: Fehler anzeigen."""
        logger.error(f"Import-Fehler: {message}")

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)

        header = SectionHeader(texts.PROVISION_RUN_TITLE, texts.PROVISION_RUN_DESC)
        layout.addWidget(header)

        # Import-Bereich
        import_frame = QFrame()
        import_frame.setStyleSheet(f"background: white; border: 1.5px solid #b0c4d8; border-radius: 8px;")
        import_layout = QVBoxLayout(import_frame)
        import_layout.setContentsMargins(20, 16, 20, 16)
        import_layout.setSpacing(10)

        import_header = QLabel(texts.PROVISION_RUN_IMPORT_BTN)
        import_header.setStyleSheet(f"font-weight: 600; font-size: 12pt; color: {PRIMARY_900}; border: none;")
        import_layout.addWidget(import_header)

        import_sub = QLabel(texts.PROVISION_RUN_IMPORT_SUB)
        import_sub.setStyleSheet(f"color: {PRIMARY_500}; font-size: {FONT_SIZE_BODY}; border: none;")
        import_layout.addWidget(import_sub)

        type_row = QHBoxLayout()
        type_lbl = QLabel(texts.PROVISION_IMPORT_TYPE_LABEL)
        type_lbl.setStyleSheet(f"font-weight: 500; color: {PRIMARY_900}; border: none;")
        type_row.addWidget(type_lbl)
        self._type_combo = QComboBox()
        self._type_combo.addItem(texts.PROVISION_IMPORT_TYPE_VU, 'vu')
        self._type_combo.setStyleSheet(
            f"QComboBox {{ padding: 6px 10px; border: 1.5px solid {BORDER_DEFAULT}; "
            f"border-radius: 6px; font-size: {FONT_SIZE_BODY}; min-width: 200px; background: white; }}"
        )
        self._type_combo.currentIndexChanged.connect(self._on_type_changed)
        type_row.addWidget(self._type_combo)
        type_row.addStretch()
        import_layout.addLayout(type_row)

        btn_row = QHBoxLayout()
        self._file_btn = QPushButton(texts.PROVISION_IMPORT_SELECT_FILE)
        self._file_btn.setStyleSheet(get_secondary_button_style())
        self._file_btn.clicked.connect(self._select_file)
        btn_row.addWidget(self._file_btn)

        self._file_label = QLabel("")
        self._file_label.setStyleSheet(f"color: {PRIMARY_500}; font-size: {FONT_SIZE_CAPTION}; border: none;")
        btn_row.addWidget(self._file_label)
        btn_row.addStretch()

        self._import_btn = QPushButton(texts.PROVISION_IMPORT_START)
        self._import_btn.setEnabled(False)
        self._import_btn.setStyleSheet(f"""
            QPushButton {{ background-color: {ACCENT_500}; color: white; border: none;
                border-radius: 6px; padding: 8px 16px; font-weight: 500; }}
            QPushButton:hover {{ background-color: #e88a2d; }}
            QPushButton:disabled {{ background-color: {PRIMARY_100}; color: #a0a0a0; }}
        """)
        self._import_btn.clicked.connect(self._start_import)
        btn_row.addWidget(self._import_btn)
        import_layout.addLayout(btn_row)

        self._progress = QProgressBar()
        self._progress.setVisible(False)
        self._progress.setMaximum(0)
        import_layout.addWidget(self._progress)

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumHeight(120)
        self._log.setVisible(False)
        self._log.setStyleSheet(f"border: 1px solid {BORDER_DEFAULT}; border-radius: 4px; font-size: {FONT_SIZE_CAPTION};")
        import_layout.addWidget(self._log)

        layout.addWidget(import_frame)

        # Historie
        hist_header = SectionHeader(texts.PROVISION_IMPORT_HISTORY_TITLE)
        layout.addWidget(hist_header)

        self._batches_model = VuBatchesModel()
        self._batches_table = QTableView()
        self._batches_table.setModel(self._batches_model)
        self._batches_table.setAlternatingRowColors(True)
        self._batches_table.setSelectionBehavior(QTableView.SelectRows)
        self._batches_table.verticalHeader().setVisible(False)
        self._batches_table.verticalHeader().setDefaultSectionSize(52)
        self._batches_table.horizontalHeader().setStretchLastSection(True)
        self._batches_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._batches_table.setStyleSheet(get_provision_table_style())
        self._batches_table.setMinimumHeight(250)

        status_del = PillBadgeDelegate(PILL_COLORS, label_map={
            'entwurf': texts.PROVISION_RUN_STATUS_ENTWURF,
            'in_pruefung': texts.PROVISION_RUN_STATUS_PRUEFUNG,
            'abgeschlossen': texts.PROVISION_RUN_STATUS_DONE,
        })
        self._batches_table.setItemDelegateForColumn(6, status_del)
        self._status_del = status_del

        layout.addWidget(self._batches_table)

        self._status = QLabel("")
        self._status.setStyleSheet(f"color: {ERROR}; font-size: {FONT_SIZE_CAPTION};")
        layout.addWidget(self._status)
        self._loading_overlay = ProvisionLoadingOverlay(self)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._loading_overlay.setGeometry(self.rect())

    def refresh(self):
        self._load_batches()

    def _load_batches(self):
        self._status.setText("")
        self._loading_overlay.setGeometry(self.rect())
        self._loading_overlay.setVisible(True)

        if self._presenter:
            self._presenter.load_batches()
            return

        if self._batches_worker and self._batches_worker.isRunning():
            return
        self._batches_worker = VuBatchesLoadWorker(self._api)
        self._batches_worker.finished.connect(self._on_batches_loaded)
        self._batches_worker.error.connect(self._on_error)
        self._batches_worker.start()

    def _on_batches_loaded(self, batches: List[ImportBatch]):
        self._loading_overlay.setVisible(False)
        self._batches_model.set_data(batches)
        self._status.setText("")

    def _on_error(self, msg: str):
        self._loading_overlay.setVisible(False)
        self._status.setText(texts.PROVISION_DASH_ERROR)

    def _on_type_changed(self, _index: int):
        self._parsed_rows = []
        self._import_btn.setEnabled(False)
        self._file_label.setText("")
        self._log.setVisible(False)
        self._log.clear()

    def _select_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, texts.PROVISION_IMPORT_SELECT_FILE, "",
            "Excel (*.xlsx *.xls);;CSV (*.csv);;Alle (*.*)"
        )
        if not path:
            return
        self._selected_path = path
        self._file_label.setText(texts.PROVISION_IMPORT_SELECTED.format(filename=os.path.basename(path)))
        self._start_parse(path)

    def _start_parse(self, path: str):
        from services.provision_import import compute_file_hash
        self._parsed_hash = compute_file_hash(path)
        self._log.setVisible(True)
        self._log.setText(texts.PROVISION_IMPORT_PROGRESS_PARSING)
        self._file_btn.setEnabled(False)
        self._import_btn.setEnabled(False)

        if self._parse_worker and self._parse_worker.isRunning():
            self._parse_worker.quit()
            self._parse_worker.wait(2000)

        self._parse_worker = VuParseFileWorker(path)
        self._parse_worker.finished.connect(self._on_parse_done)
        self._parse_worker.error.connect(self._on_parse_error)
        self._parse_worker.start()

    def _on_parse_done(self, rows, vu_name, sheet_name, log_text):
        self._file_btn.setEnabled(True)
        self._parsed_rows = rows
        self._parsed_vu = vu_name
        self._parsed_sheet = sheet_name
        self._log.setText(log_text)
        self._import_btn.setEnabled(len(rows) > 0)

    def _on_parse_error(self, msg: str):
        self._file_btn.setEnabled(True)
        self._log.setText(texts.PROVISION_IMPORT_PARSE_ERROR.format(msg=msg))
        self._import_btn.setEnabled(False)
        logger.error(f"Parse-Fehler: {msg}")

    def _start_import(self):
        if not self._parsed_rows:
            return
        self._import_btn.setEnabled(False)
        self._progress.setVisible(True)

        if self._presenter:
            self._presenter.start_import(
                rows=self._parsed_rows,
                filename=os.path.basename(self._selected_path),
                sheet_name=self._parsed_sheet,
                vu_name=self._parsed_vu,
                file_hash=self._parsed_hash,
            )
        elif self._api:
            self._import_worker = VuImportWorker(
                self._api, self._parsed_rows, os.path.basename(self._selected_path),
                self._parsed_sheet, self._parsed_vu, self._parsed_hash,
            )
            self._import_worker.progress.connect(lambda msg: self._log.append(msg))
            self._import_worker.finished.connect(self._on_import_done)
            self._import_worker.error.connect(self._on_import_error)
            self._import_worker.start()

    def _on_import_done(self, result: Optional[ImportResult]):
        self._progress.setVisible(False)
        self._import_btn.setEnabled(True)
        if result:
            summary = texts.PROVISION_IMPORT_SUCCESS.format(
                imported=result.imported, skipped=result.skipped, errors=result.errors,
            )
            self._log.append(summary)
            matched = getattr(result, 'matched', 0) or 0
            still_open = getattr(result, 'still_unmatched', 0) or 0
            if matched > 0 or still_open > 0:
                self._log.append(texts.PROVISION_TOAST_AUTOMATCH_DONE.format(
                    matched=matched, open=still_open))
            if self._toast_manager:
                self._toast_manager.show_success(
                    texts.PROVISION_TOAST_IMPORT_SUCCESS.format(count=result.imported)
                )
        self._load_batches()
        self.navigate_to_panel.emit(2)

    def _on_import_error(self, msg: str):
        self._progress.setVisible(False)
        self._import_btn.setEnabled(True)
        self._log.append(f"{texts.PROVISION_ERROR_PREFIX}: {msg}")
