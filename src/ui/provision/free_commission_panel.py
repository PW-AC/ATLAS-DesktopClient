"""
Panel: Freie Provisionen / Sonderzahlungen.

Ermoeglicht dem GF das Erfassen, Bearbeiten und Loeschen von
Sonderzahlungen mit freier Verteilung an Berater.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableView,
    QHeaderView, QPushButton, QAbstractItemView,
    QMessageBox,
)
from PySide6.QtCore import Qt, Signal, QTimer, QObject
from PySide6.QtGui import QColor
from typing import List, Optional

from domain.provision.entities import FreeCommission
from infrastructure.threading.worker_utils import run_worker
from ui.styles.tokens import (
    PRIMARY_100, PRIMARY_500, PRIMARY_900, ACCENT_500,
    BG_PRIMARY, BG_SECONDARY, BORDER_DEFAULT,
    TEXT_DISABLED,
    SUCCESS, ERROR, ERROR_LIGHT,
    FONT_BODY, FONT_SIZE_BODY, FONT_SIZE_CAPTION,
    get_provision_table_style,
)
from ui.provision.widgets import (
    SectionHeader, ProvisionLoadingOverlay,
    format_eur, get_secondary_button_style,
)
from ui.provision.models import FreeCommissionModel
from i18n import de as texts
import logging

logger = logging.getLogger(__name__)


class FreeCommissionPanel(QWidget):
    """Freie Provisionen / Sonderzahlungen - Uebersicht und CRUD.

    Implementiert IFreeCommissionView fuer den FreeCommissionPresenter.
    """

    navigate_to_panel = Signal(int)
    data_changed = Signal()

    def __init__(self):
        super().__init__()
        self._presenter = None
        self._toast_manager = None
        self._items: List[FreeCommission] = []
        self._dialog_ctx = QObject(self)
        self._setup_ui()

    def set_presenter(self, presenter) -> None:
        self._presenter = presenter
        presenter.set_view(self)
        QTimer.singleShot(100, self._load_data)

    # ── IFreeCommissionView ──

    def show_free_commissions(self, items: List[FreeCommission]) -> None:
        self._items = items
        self._populate_table()

    def show_loading(self, loading: bool) -> None:
        self._loading_overlay.setVisible(loading)
        if loading:
            self._loading_overlay.raise_()

    def show_error(self, message: str) -> None:
        if self._toast_manager:
            self._toast_manager.show_error(message)

    def show_success(self, message: str) -> None:
        if self._toast_manager:
            self._toast_manager.show_success(message)
        self.data_changed.emit()

    def refresh(self) -> None:
        self._load_data()

    # ── UI-Setup ──

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        header = SectionHeader(texts.PM_FREE_PANEL_TITLE, texts.PM_FREE_PANEL_DESC)
        self._create_btn = QPushButton(f"  +  {texts.PM_FREE_BTN_CREATE}")
        self._create_btn.setCursor(Qt.PointingHandCursor)
        self._create_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ACCENT_500};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 20px;
                font-family: {FONT_BODY};
                font-size: {FONT_SIZE_BODY};
                font-weight: 600;
            }}
            QPushButton:hover {{ background-color: {PRIMARY_500}; }}
            QPushButton:pressed {{ background-color: {PRIMARY_900}; }}
        """)
        self._create_btn.clicked.connect(self._on_create)
        header._action_area.addWidget(self._create_btn)

        self._edit_btn = QPushButton(texts.PM_FREE_DIALOG_TITLE_EDIT.split()[0])
        self._edit_btn.setCursor(Qt.PointingHandCursor)
        self._edit_btn.setStyleSheet(get_secondary_button_style())
        self._edit_btn.setEnabled(False)
        self._edit_btn.clicked.connect(self._on_edit_selected)
        header._action_area.addWidget(self._edit_btn)

        self._del_btn = QPushButton("\u2716")
        self._del_btn.setCursor(Qt.PointingHandCursor)
        self._del_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent; color: {ERROR};
                border: 1px solid {ERROR}; border-radius: 4px;
                padding: 4px 12px; font-size: {FONT_SIZE_CAPTION};
            }}
            QPushButton:hover {{ background-color: {ERROR_LIGHT}; }}
            QPushButton:disabled {{ color: {TEXT_DISABLED}; border-color: {TEXT_DISABLED}; }}
        """)
        self._del_btn.setEnabled(False)
        self._del_btn.clicked.connect(self._on_delete_selected)
        header._action_area.addWidget(self._del_btn)

        layout.addWidget(header)

        self._fc_model = FreeCommissionModel()
        self._table = QTableView()
        self._table.setModel(self._fc_model)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.setStyleSheet(get_provision_table_style())
        self._table.doubleClicked.connect(lambda idx: self._on_edit(idx.row()))
        self._table.setContextMenuPolicy(Qt.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._show_context_menu)

        hh = self._table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.Stretch)
        hh.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(4, QHeaderView.Stretch)
        hh.setSectionResizeMode(5, QHeaderView.ResizeToContents)

        self._table.selectionModel().selectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self._table)

        self._empty_label = QLabel(texts.PM_FREE_EMPTY)
        self._empty_label.setAlignment(Qt.AlignCenter)
        self._empty_label.setStyleSheet(
            f"color: {PRIMARY_500}; font-size: 12pt; font-family: {FONT_BODY}; padding: 40px;"
        )
        self._empty_label.setVisible(False)
        layout.addWidget(self._empty_label)

        self._loading_overlay = ProvisionLoadingOverlay(self)
        self._loading_overlay.setVisible(False)

    def _populate_table(self):
        has_data = bool(self._items)
        self._table.setVisible(has_data)
        self._empty_label.setVisible(not has_data)
        self._fc_model.set_data(self._items if has_data else [])

    # ── Selection & Context Menu ──

    def _on_selection_changed(self):
        row = self._get_selected_row()
        if row < 0 or row >= len(self._items):
            self._edit_btn.setEnabled(False)
            self._del_btn.setEnabled(False)
            return
        fc = self._items[row]
        self._edit_btn.setEnabled(fc.can_edit)
        self._del_btn.setEnabled(fc.can_edit)

    def _get_selected_row(self) -> int:
        indexes = self._table.selectionModel().selectedRows()
        if indexes:
            return indexes[0].row()
        return -1

    def _on_edit_selected(self):
        row = self._get_selected_row()
        if row >= 0:
            self._on_edit(row)

    def _on_delete_selected(self):
        row = self._get_selected_row()
        if row >= 0:
            self._on_delete(row)

    def _show_context_menu(self, pos):
        from PySide6.QtWidgets import QMenu
        idx = self._table.indexAt(pos)
        if not idx.isValid():
            return
        row = idx.row()
        if row < 0 or row >= len(self._items):
            return
        fc = self._items[row]
        menu = QMenu(self)
        if fc.can_edit:
            menu.addAction(texts.PM_FREE_DIALOG_TITLE_EDIT.split()[0],
                           lambda: self._on_edit(row))
            menu.addAction(texts.PM_FREE_BTN_DELETE if hasattr(texts, 'PM_FREE_BTN_DELETE') else "\u2716",
                           lambda: self._on_delete(row))
        menu.exec(self._table.viewport().mapToGlobal(pos))

    # ── Actions ──

    def _load_data(self):
        if self._presenter:
            self._presenter.load_free_commissions()

    def _on_create(self):
        if not self._presenter:
            return
        self.show_loading(True)
        run_worker(
            self._dialog_ctx,
            lambda w: self._presenter._repo.get_employees(),
            self._open_create_dialog,
            on_error=self._on_dialog_load_error,
        )

    def _open_create_dialog(self, employees):
        self.show_loading(False)
        from ui.provision.free_commission_dialog import FreeCommissionDialog
        dlg = FreeCommissionDialog(employees, parent=self)
        if dlg.exec():
            data = dlg.get_data()
            if self._presenter:
                self._presenter.save_free_commission(data)

    def _on_edit(self, row: int):
        if row < 0 or row >= len(self._items):
            return
        fc = self._items[row]
        if not fc.can_edit:
            if self._toast_manager:
                self._toast_manager.show_error(texts.PM_FREE_EDIT_LOCKED)
            return
        if not self._presenter:
            return

        self.show_loading(True)
        fc_id = fc.id
        run_worker(
            self._dialog_ctx,
            lambda w: {
                'employees': self._presenter._repo.get_employees(),
                'detail': self._presenter._repo.get_free_commission(fc_id),
            },
            lambda result: self._open_edit_dialog(result, fc),
            on_error=self._on_dialog_load_error,
        )

    def _open_edit_dialog(self, result, fc):
        self.show_loading(False)
        from ui.provision.free_commission_dialog import FreeCommissionDialog
        employees = result.get('employees', [])
        detail = result.get('detail', {})
        fc_detail = FreeCommission.from_dict(detail) if detail else fc
        dlg = FreeCommissionDialog(employees, fc=fc_detail, parent=self)
        if dlg.exec():
            data = dlg.get_data()
            if self._presenter:
                self._presenter.save_free_commission(data, fc_id=fc.id)

    def _on_dialog_load_error(self, msg: str):
        self.show_loading(False)
        if self._toast_manager:
            self._toast_manager.show_error(msg)

    def _on_delete(self, row: int):
        if row < 0 or row >= len(self._items):
            return
        fc = self._items[row]
        if not fc.can_edit:
            if self._toast_manager:
                self._toast_manager.show_error(texts.PM_FREE_DELETE_LOCKED)
            return

        msg = texts.PM_FREE_DELETE_CONFIRM.format(beschreibung=fc.beschreibung)
        reply = QMessageBox.question(self, texts.PM_FREE_PANEL_TITLE, msg,
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes and self._presenter:
            self._presenter.delete_free_commission(fc.id)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._loading_overlay.setGeometry(self.rect())
