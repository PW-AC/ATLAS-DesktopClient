# -*- coding: utf-8 -*-
"""
Excel-Rohdaten-Viewer Dialog.

Zeigt den Inhalt einer Original-Excel-Datei in einer QTableView an
und springt optional zu einer bestimmten Zeile (source_row).
"""

import logging
from typing import Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableView,
    QPushButton, QLabel, QLineEdit, QHeaderView,
    QFileDialog, QAbstractItemView, QFrame,
)
from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex, QThread, Signal
from PySide6.QtGui import QColor

from ui.styles.tokens import (
    PRIMARY_0, PRIMARY_500, PRIMARY_900, ACCENT_500,
    FONT_BODY, FONT_SIZE_BODY, FONT_SIZE_CAPTION,
    SUCCESS, WARNING,
)
from i18n import de as texts

logger = logging.getLogger(__name__)


class _ExcelLoadWorker(QThread):
    """Lädt Excel-Daten im Hintergrund."""
    finished = Signal(list, list)
    error = Signal(str)

    def __init__(self, filepath: str, sheet_name: str = None):
        super().__init__()
        self._filepath = filepath
        self._sheet_name = sheet_name

    def run(self):
        try:
            import openpyxl
            wb = openpyxl.load_workbook(self._filepath, read_only=True, data_only=True)
            if self._sheet_name and self._sheet_name in wb.sheetnames:
                ws = wb[self._sheet_name]
            else:
                ws = wb.active

            headers = []
            rows_data = []
            for row_idx, row in enumerate(ws.iter_rows(values_only=True)):
                str_row = [str(v) if v is not None else '' for v in row]
                if row_idx == 0:
                    headers = str_row
                else:
                    rows_data.append(str_row)

            wb.close()
            self.finished.emit(headers, rows_data)
        except Exception as e:
            self.error.emit(str(e))


class _ExcelTableModel(QAbstractTableModel):
    """Einfaches Model für Excel-Rohdaten."""

    def __init__(self):
        super().__init__()
        self._headers = []
        self._rows = []
        self._highlight_row = -1

    def set_data(self, headers: list, rows: list):
        self.beginResetModel()
        self._headers = headers
        self._rows = rows
        self.endResetModel()

    def set_highlight_row(self, row: int):
        self._highlight_row = row
        self.dataChanged.emit(
            self.index(0, 0),
            self.index(self.rowCount() - 1, self.columnCount() - 1),
        )

    def rowCount(self, parent=QModelIndex()):
        return len(self._rows)

    def columnCount(self, parent=QModelIndex()):
        return len(self._headers) if self._headers else 0

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            if section < len(self._headers):
                return self._headers[section]
        if orientation == Qt.Vertical and role == Qt.DisplayRole:
            return str(section + 2)
        return None

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        row_data = self._rows[index.row()]
        col = index.column()

        if role == Qt.DisplayRole:
            if col < len(row_data):
                return row_data[col]
            return ''

        if role == Qt.BackgroundRole:
            if index.row() == self._highlight_row:
                return QColor(ACCENT_500 + '40')

        return None


class RawDataViewerDialog(QDialog):
    """In-App Excel-Rohdaten-Viewer mit Zeilen-Navigation."""

    def __init__(self, parent=None, filepath: str = None,
                 sheet_name: str = None, target_row: int = None):
        super().__init__(parent)
        self._filepath = filepath
        self._sheet_name = sheet_name
        self._target_row = target_row
        self._load_worker = None
        self._model = _ExcelTableModel()

        self.setWindowTitle(texts.PROVISION_RAW_VIEWER_TITLE.format(
            filename=filepath.split('\\')[-1].split('/')[-1] if filepath else ''))
        self.setMinimumSize(1000, 600)
        self._setup_ui()

        if filepath:
            self._load_file(filepath, sheet_name)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self._file_btn = QPushButton(texts.PROVISION_RAW_VIEWER_FILE_SELECT)
        self._file_btn.setCursor(Qt.PointingHandCursor)
        self._file_btn.clicked.connect(self._on_select_file)
        toolbar.addWidget(self._file_btn)

        if self._sheet_name:
            sheet_lbl = QLabel(texts.PROVISION_RAW_VIEWER_SHEET.format(sheet=self._sheet_name))
            sheet_lbl.setStyleSheet(f"color: {PRIMARY_500}; font-size: {FONT_SIZE_CAPTION};")
            toolbar.addWidget(sheet_lbl)

        toolbar.addStretch()

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText(texts.PROVISION_RAW_VIEWER_SEARCH)
        self._search_input.setMaximumWidth(250)
        self._search_input.textChanged.connect(self._on_search)
        toolbar.addWidget(self._search_input)

        if self._target_row is not None:
            self._jump_btn = QPushButton(
                texts.PROVISION_RAW_VIEWER_ROW.format(row=self._target_row))
            self._jump_btn.setCursor(Qt.PointingHandCursor)
            self._jump_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {ACCENT_500}; color: white;
                    border: none; border-radius: 4px;
                    padding: 6px 12px; font-weight: 600;
                }}
                QPushButton:hover {{ background: {SUCCESS}; }}
            """)
            self._jump_btn.clicked.connect(self._jump_to_target)
            toolbar.addWidget(self._jump_btn)

        layout.addLayout(toolbar)

        self._status_label = QLabel(texts.PROVISION_RAW_VIEWER_LOADING)
        self._status_label.setStyleSheet(f"color: {PRIMARY_500}; font-size: {FONT_SIZE_CAPTION};")
        layout.addWidget(self._status_label)

        self._table = QTableView()
        self._table.setModel(self._model)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self._table.verticalHeader().setDefaultSectionSize(28)
        layout.addWidget(self._table)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton(texts.CLOSE)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(self.close)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def _load_file(self, filepath: str, sheet_name: str = None):
        self._status_label.setText(texts.PROVISION_RAW_VIEWER_LOADING)
        self._load_worker = _ExcelLoadWorker(filepath, sheet_name)
        self._load_worker.finished.connect(self._on_data_loaded)
        self._load_worker.error.connect(self._on_load_error)
        self._load_worker.start()

    def _on_data_loaded(self, headers: list, rows: list):
        self._model.set_data(headers, rows)
        self._status_label.setText(f"{len(rows)} Zeilen")
        if self._target_row is not None:
            self._jump_to_target()

    def _on_load_error(self, error: str):
        self._status_label.setText(
            texts.PROVISION_RAW_VIEWER_ERROR.format(error=error))

    def _jump_to_target(self):
        if self._target_row is None:
            return
        model_row = self._target_row - 2
        if 0 <= model_row < self._model.rowCount():
            self._model.set_highlight_row(model_row)
            idx = self._model.index(model_row, 0)
            self._table.scrollTo(idx, QAbstractItemView.PositionAtCenter)
            self._table.selectRow(model_row)

    def _on_select_file(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            texts.PROVISION_RAW_VIEWER_FILE_SELECT,
            '',
            texts.PROVISION_RAW_VIEWER_FILE_FILTER,
        )
        if filepath:
            self._filepath = filepath
            self._load_file(filepath)

    def _on_search(self, text: str):
        if not text:
            return
        text_lower = text.lower()
        for row_idx in range(self._model.rowCount()):
            for col_idx in range(self._model.columnCount()):
                val = self._model.data(self._model.index(row_idx, col_idx))
                if val and text_lower in str(val).lower():
                    self._model.set_highlight_row(row_idx)
                    idx = self._model.index(row_idx, col_idx)
                    self._table.scrollTo(idx, QAbstractItemView.PositionAtCenter)
                    self._table.selectRow(row_idx)
                    return
