"""
Zuordnung & Klaerfaelle-Panel: Klaerfall-Typen, Vermittler-Zuordnungen.

Ersetzt: mappings_panel.py
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableView,
    QHeaderView, QPushButton, QDialog, QComboBox, QDateEdit,
    QLineEdit, QMenu, QFormLayout, QDialogButtonBox, QCheckBox,
)
from PySide6.QtCore import (
    Qt, Signal, QModelIndex, QTimer, QDate,
)
from typing import List, Dict, Optional
from datetime import date
import calendar

from api.provision import ProvisionAPI
from domain.provision.entities import Commission, VermittlerMapping, Employee
from ui.styles.tokens import (
    PRIMARY_500, PRIMARY_900, ACCENT_500, ACCENT_HOVER,
    ERROR, ERROR_LIGHT, FONT_SIZE_BODY, FONT_SIZE_CAPTION,
    PILL_COLORS, get_provision_table_style,
)
from ui.provision.widgets import (
    FilterChipBar, SectionHeader, PillBadgeDelegate, ProvisionLoadingOverlay,
    format_eur, get_secondary_button_style,
)
from ui.provision.workers import ClearanceLoadWorker, MappingSyncWorker
from ui.provision.models import UnmatchedModel, MappingsModel, clearance_type
from ui.provision.dialogs import MatchContractDialog
from infrastructure.threading.worker_utils import run_worker
from i18n import de as texts
import logging

logger = logging.getLogger(__name__)


class ZuordnungPanel(QWidget):
    """Zuordnung & Klaerfaelle: Offene Positionen und Vermittler-Mappings.

    Implementiert IClearanceView fuer den ClearancePresenter.
    """

    navigate_to_panel = Signal(int)

    def __init__(self, api: ProvisionAPI = None):
        super().__init__()
        self._api = api
        self._presenter = None
        self._worker = None
        self._toast_manager = None
        self._all_unmatched: list = []
        self._setup_ui()

    @property
    def _backend(self):
        """Presenter bevorzugen, API als Fallback."""
        return self._presenter or self._api

    def set_presenter(self, presenter) -> None:
        """Verbindet dieses Panel mit dem ClearancePresenter."""
        self._presenter = presenter
        presenter.set_view(self)
        self._load_data()

    # ── IClearanceView ──

    def show_commissions(self, commissions: list) -> None:
        """View-Interface: Klaerfaelle anzeigen."""
        self._all_unmatched = commissions
        self._unmatched_model.set_data(commissions)
        self._filter_clearance("alle")

    def show_mappings(self, mappings: list, unmapped: list = None) -> None:
        """View-Interface: Vermittler-Mappings anzeigen."""
        self._mappings_model.set_data(mappings)

    def show_loading(self, loading: bool) -> None:
        """View-Interface: Ladezustand."""
        overlay = getattr(self, '_loading_overlay', None)
        if overlay:
            overlay.setVisible(loading)

    def show_error(self, message: str) -> None:
        """View-Interface: Fehler anzeigen."""
        logger.error(f"Klaerfaelle-Fehler: {message}")

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)

        # Header
        header = SectionHeader(
            texts.PROVISION_CLEAR_TITLE,
            texts.PROVISION_CLEAR_DESC,
        )
        auto_btn = QPushButton(texts.PROVISION_ACT_AUTO_MATCH)
        auto_btn.setToolTip(texts.PROVISION_ACT_AUTO_MATCH_TIP)
        auto_btn.setStyleSheet(f"""
            QPushButton {{ background-color: {ACCENT_500}; color: white; border: none;
                border-radius: 6px; padding: 8px 16px; font-weight: 500; }}
            QPushButton:hover {{ background-color: {ACCENT_HOVER}; }}
        """)
        auto_btn.clicked.connect(self._trigger_auto_match)
        header.add_action(auto_btn)
        layout.addWidget(header)

        # Zeitraumfilter
        date_row = QHBoxLayout()
        date_row.setSpacing(10)

        self._mode_combo = QComboBox()
        self._mode_combo.setFixedWidth(170)
        self._mode_combo.setFixedHeight(32)
        self._mode_combo.addItem(texts.PROVISION_FILTER_MODE_MONTH, "month")
        self._mode_combo.addItem(texts.PROVISION_FILTER_LAST_3, "last_3")
        self._mode_combo.addItem(texts.PROVISION_FILTER_LAST_6, "last_6")
        self._mode_combo.addItem(texts.PROVISION_FILTER_LAST_12, "last_12")
        self._mode_combo.addItem(texts.PROVISION_FILTER_MODE_RANGE, "range")
        self._mode_combo.addItem(texts.PROVISION_FILTER_ALL_TIME, "all")
        self._mode_combo.currentIndexChanged.connect(self._on_date_mode_changed)
        date_row.addWidget(self._mode_combo)

        self._month_combo = QComboBox()
        self._month_combo.setFixedWidth(130)
        self._month_combo.setFixedHeight(32)
        today = date.today()
        for offset in range(24):
            y = today.year
            m = today.month - offset
            while m < 1:
                m += 12
                y -= 1
            self._month_combo.addItem(f"{m:02d}/{y}", f"{y}-{m:02d}")
        self._month_combo.currentIndexChanged.connect(self._on_date_filter_changed)
        date_row.addWidget(self._month_combo)

        self._von_label = QLabel(texts.PROVISION_FILTER_FROM)
        self._von_label.setStyleSheet(f"color: {PRIMARY_500};")
        self._von_label.setVisible(False)
        date_row.addWidget(self._von_label)
        self._date_from = QDateEdit()
        self._date_from.setCalendarPopup(True)
        self._date_from.setDisplayFormat("dd.MM.yyyy")
        self._date_from.setDate(QDate(today.year, today.month, 1).addMonths(-3))
        self._date_from.setFixedHeight(32)
        self._date_from.setVisible(False)
        self._date_from.dateChanged.connect(self._on_date_filter_changed)
        date_row.addWidget(self._date_from)

        self._bis_label = QLabel(texts.PROVISION_FILTER_TO)
        self._bis_label.setStyleSheet(f"color: {PRIMARY_500};")
        self._bis_label.setVisible(False)
        date_row.addWidget(self._bis_label)
        self._date_to = QDateEdit()
        self._date_to.setCalendarPopup(True)
        self._date_to.setDisplayFormat("dd.MM.yyyy")
        self._date_to.setDate(QDate.currentDate())
        self._date_to.setFixedHeight(32)
        self._date_to.setVisible(False)
        self._date_to.dateChanged.connect(self._on_date_filter_changed)
        date_row.addWidget(self._date_to)

        date_row.addStretch()
        layout.addLayout(date_row)

        # Klaerfall-Chips
        self._chips = FilterChipBar()
        self._chips.filter_changed.connect(self._filter_clearance)
        layout.addWidget(self._chips)

        # Klaerfall-Tabelle
        self._unmatched_model = UnmatchedModel()
        self._unmatched_table = QTableView()
        self._unmatched_table.setModel(self._unmatched_model)
        self._unmatched_table.setAlternatingRowColors(True)
        self._unmatched_table.setSelectionBehavior(QTableView.SelectRows)
        self._unmatched_table.verticalHeader().setVisible(False)
        self._unmatched_table.verticalHeader().setDefaultSectionSize(52)
        self._unmatched_table.horizontalHeader().setStretchLastSection(True)
        self._unmatched_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._unmatched_table.setStyleSheet(get_provision_table_style())
        self._unmatched_table.setMinimumHeight(300)

        problem_delegate = PillBadgeDelegate(
            {
                "kein_passender_vertrag_gefunden": PILL_COLORS["offen"],
                "vermittler_unbekannt": {"bg": ERROR_LIGHT, "text": ERROR},
                "berater-mapping_fehlt": PILL_COLORS.get("vertrag_gefunden", {"bg": "#fef3c7", "text": "#92400e"}),
            }
        )
        self._unmatched_table.setItemDelegateForColumn(
            UnmatchedModel.COL_PROBLEM, problem_delegate)
        self._problem_delegate = problem_delegate

        self._unmatched_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self._unmatched_table.customContextMenuRequested.connect(self._clearance_context_menu)
        self._unmatched_table.doubleClicked.connect(self._on_clearance_double_click)

        layout.addWidget(self._unmatched_table, 2)

        # Vermittler-Zuordnungen
        mapping_header = SectionHeader(
            texts.PROVISION_CLEAR_MAPPING_TITLE,
            texts.PROVISION_CLEAR_MAPPING_DESC,
        )
        add_btn = QPushButton(texts.PROVISION_CLEAR_MAPPING_ADD)
        add_btn.setStyleSheet(get_secondary_button_style())
        add_btn.clicked.connect(self._add_mapping)
        mapping_header.add_action(add_btn)
        layout.addWidget(mapping_header)

        self._mappings_model = MappingsModel()
        self._mappings_table = QTableView()
        self._mappings_table.setModel(self._mappings_model)
        self._mappings_table.setAlternatingRowColors(True)
        self._mappings_table.setSelectionBehavior(QTableView.SelectRows)
        self._mappings_table.verticalHeader().setVisible(False)
        self._mappings_table.verticalHeader().setDefaultSectionSize(52)
        self._mappings_table.horizontalHeader().setStretchLastSection(True)
        self._mappings_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._mappings_table.setStyleSheet(get_provision_table_style())
        self._mappings_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self._mappings_table.customContextMenuRequested.connect(self._mapping_context_menu)
        layout.addWidget(self._mappings_table, 1)

        self._status = QLabel("")
        self._status.setStyleSheet(f"color: {ERROR}; font-size: {FONT_SIZE_CAPTION};")
        layout.addWidget(self._status)
        self._loading_overlay = ProvisionLoadingOverlay(self)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._loading_overlay.setGeometry(self.rect())

    def refresh(self):
        self._load_data()

    def _get_date_range(self):
        mode = self._mode_combo.currentData()
        if mode == "month":
            val = self._month_combo.currentData()
            if val:
                y, m = val.split('-')
                y, m = int(y), int(m)
                last_day = calendar.monthrange(y, m)[1]
                return f"{y}-{m:02d}-01", f"{y}-{m:02d}-{last_day:02d}"
        elif mode == "range":
            von = self._date_from.date().toString("yyyy-MM-dd")
            bis = self._date_to.date().toString("yyyy-MM-dd")
            return von, bis
        elif mode == "last_3":
            bis = date.today().strftime("%Y-%m-%d")
            von = QDate.currentDate().addMonths(-3).toString("yyyy-MM-dd")
            return von, bis
        elif mode == "last_6":
            bis = date.today().strftime("%Y-%m-%d")
            von = QDate.currentDate().addMonths(-6).toString("yyyy-MM-dd")
            return von, bis
        elif mode == "last_12":
            bis = date.today().strftime("%Y-%m-%d")
            von = QDate.currentDate().addMonths(-12).toString("yyyy-MM-dd")
            return von, bis
        elif mode == "all":
            return None, None
        return None, None

    def _on_date_mode_changed(self, *args):
        mode = self._mode_combo.currentData()
        is_month = mode == "month"
        is_range = mode == "range"
        self._month_combo.setVisible(is_month)
        self._von_label.setVisible(is_range)
        self._date_from.setVisible(is_range)
        self._bis_label.setVisible(is_range)
        self._date_to.setVisible(is_range)
        self._load_data()

    def _on_date_filter_changed(self, *args):
        self._load_data()

    def _load_data(self):
        self._status.setText("")
        self._loading_overlay.setGeometry(self.rect())
        self._loading_overlay.setVisible(True)

        von, bis = self._get_date_range()

        if self._presenter:
            self._presenter.load_clearance(von=von, bis=bis)
            return

        if self._worker:
            if self._worker.isRunning():
                return
            try:
                self._worker.finished.disconnect()
                self._worker.error.disconnect()
            except RuntimeError:
                pass
        self._worker = ClearanceLoadWorker(self._backend, von=von, bis=bis)
        self._worker.finished.connect(self._on_loaded)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_loaded(self, commissions: List[Commission], mappings_data: Dict):
        self._all_unmatched = commissions
        self._unmatched_model.set_data(commissions)

        no_contract = sum(1 for c in commissions
                          if c.match_status == 'unmatched')
        no_berater = sum(1 for c in commissions
                         if c.match_status in ('auto_matched', 'manual_matched') and not c.berater_id)
        total = len(commissions)

        self._chips.set_chips([
            ("alle", texts.PROVISION_POS_FILTER_ALL, total),
            ("no_contract", texts.PROVISION_CLEAR_TYPE_NO_CONTRACT, no_contract),
            ("no_berater", texts.PROVISION_CLEAR_TYPE_NO_BERATER, no_berater),
        ])

        mappings = mappings_data.get('mappings', [])
        self._mappings_model.set_data(mappings)

        self._loading_overlay.setVisible(False)
        self._status.setText("")

    def _on_error(self, msg: str):
        self._loading_overlay.setVisible(False)
        self._status.setText(texts.PROVISION_DASH_ERROR)
        logger.error(f"Klaerfaelle-Ladefehler: {msg}")

    def _filter_clearance(self, key: str):
        if key == "alle":
            self._unmatched_model.set_data(self._all_unmatched)
        elif key == "no_contract":
            self._unmatched_model.set_data([c for c in self._all_unmatched
                                            if c.match_status == 'unmatched'])
        elif key == "no_berater":
            self._unmatched_model.set_data([c for c in self._all_unmatched
                                            if c.match_status in ('auto_matched', 'manual_matched') and not c.berater_id])

    def _trigger_auto_match(self):
        run_worker(
            self, lambda w: self._backend.trigger_auto_match(),
            self._on_auto_match_done,
        )

    def _on_auto_match_done(self, stats):
        if stats:
            matched = stats.get('matched', 0)
            still_open = stats.get('still_unmatched', 0)
            if self._toast_manager:
                self._toast_manager.show_success(
                    texts.PROVISION_TOAST_AUTOMATCH_DONE.format(matched=matched, open=still_open)
                )
            self._load_data()

    def _add_mapping(self):
        run_worker(
            self, lambda w: self._backend.get_employees(),
            self._show_add_mapping_dialog,
        )

    def _show_add_mapping_dialog(self, employees):
        dlg = QDialog(self)
        dlg.setWindowTitle(texts.PROVISION_MAP_DLG_TITLE)
        dlg.setMinimumWidth(400)
        form = QFormLayout(dlg)

        name_edit = QLineEdit()
        name_edit.setPlaceholderText(texts.PROVISION_MAP_DLG_NAME)
        form.addRow(texts.PROVISION_MAP_DLG_NAME, name_edit)

        berater_combo = QComboBox()
        for emp in employees:
            if emp.is_active:
                berater_combo.addItem(emp.name, emp.id)
        form.addRow(texts.PROVISION_MAP_DLG_BERATER, berater_combo)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        form.addRow(buttons)

        if dlg.exec() == QDialog.Accepted:
            name = name_edit.text().strip()
            berater_id = berater_combo.currentData()
            if name and berater_id:
                run_worker(
                    self,
                    lambda w, n=name, b=berater_id: self._backend.create_mapping(n, b),
                    lambda _: self._on_mapping_write_done(),
                )

    def _on_mapping_write_done(self):
        if self._toast_manager:
            self._toast_manager.show_success(texts.PROVISION_TOAST_SAVED)
        self._load_data()

    def _mapping_context_menu(self, pos):
        idx = self._mappings_table.indexAt(pos)
        if not idx.isValid():
            return
        mapping = self._mappings_model.get_item(idx.row())
        if not mapping:
            return
        menu = QMenu(self)
        menu.addAction(texts.PROVISION_MENU_EDIT, lambda: self._edit_mapping(mapping))
        menu.addAction(texts.PROVISION_MENU_DELETE, lambda: self._delete_mapping(mapping))
        menu.exec(self._mappings_table.viewport().mapToGlobal(pos))

    def _edit_mapping(self, mapping: VermittlerMapping):
        run_worker(
            self, lambda w: self._backend.get_employees(),
            lambda employees, m=mapping: self._show_edit_mapping_dialog(m, employees),
        )

    def _show_edit_mapping_dialog(self, mapping: VermittlerMapping, employees):
        dlg = QDialog(self)
        dlg.setWindowTitle(texts.PROVISION_MENU_EDIT)
        dlg.setMinimumWidth(400)
        form = QFormLayout(dlg)

        name_lbl = QLabel(mapping.vermittler_name)
        name_lbl.setStyleSheet(f"font-weight: 500; color: {PRIMARY_900};")
        form.addRow(texts.PROVISION_MAP_DLG_NAME, name_lbl)

        berater_combo = QComboBox()
        for emp in employees:
            if emp.is_active:
                berater_combo.addItem(emp.name, emp.id)
                if emp.id == mapping.berater_id:
                    berater_combo.setCurrentIndex(berater_combo.count() - 1)
        form.addRow(texts.PROVISION_MAP_DLG_BERATER, berater_combo)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        form.addRow(buttons)

        if dlg.exec() == QDialog.Accepted:
            new_berater_id = berater_combo.currentData()
            if new_berater_id and new_berater_id != mapping.berater_id:
                def _update(w, mid=mapping.id, name=mapping.vermittler_name, bid=new_berater_id):
                    self._backend.delete_mapping(mid)
                    self._backend.create_mapping(name, bid)
                run_worker(self, _update, lambda _: self._on_mapping_write_done())

    def _delete_mapping(self, mapping: VermittlerMapping):
        run_worker(
            self,
            lambda w, mid=mapping.id: self._backend.delete_mapping(mid),
            self._on_mapping_deleted,
        )

    def _on_mapping_deleted(self, success):
        if success:
            if self._toast_manager:
                self._toast_manager.show_success(texts.PROVISION_TOAST_DELETED)
            self._load_data()

    def _clearance_context_menu(self, pos):
        idx = self._unmatched_table.indexAt(pos)
        if not idx.isValid():
            return
        comm = self._unmatched_model.get_item(idx.row())
        if not comm:
            return
        menu = QMenu(self)
        if comm.match_status == 'unmatched':
            menu.addAction(texts.PROVISION_MATCH_DLG_ASSIGN, lambda: self._open_match_dialog(comm))
        mappable_name = comm.xempus_berater_name or comm.vermittler_name
        if not comm.berater_id and mappable_name:
            menu.addAction(texts.PROVISION_MAP_DLG_CREATE_TITLE, lambda: self._create_mapping_for(comm))
        if comm.contract_id:
            menu.addAction(texts.PROVISION_MATCH_DLG_REASSIGN, lambda: self._open_match_dialog(comm))
        menu.addAction(texts.PROVISION_MENU_DETAILS, lambda: self.navigate_to_panel.emit(2))
        menu.exec(self._unmatched_table.viewport().mapToGlobal(pos))

    def _on_clearance_double_click(self, index: QModelIndex):
        comm = self._unmatched_model.get_item(index.row())
        if not comm:
            return
        if comm.match_status == 'unmatched':
            self._open_match_dialog(comm)
        else:
            mappable_name = comm.xempus_berater_name or comm.vermittler_name
            if not comm.berater_id and mappable_name:
                self._create_mapping_for(comm)

    def _open_match_dialog(self, comm: Commission):
        """Oeffnet den MatchContractDialog fuer manuelle Vertragszuordnung."""
        dlg = MatchContractDialog(self._backend, comm, parent=self)
        if dlg.exec() == QDialog.Accepted:
            if self._toast_manager:
                self._toast_manager.show_success(texts.PROVISION_TOAST_ASSIGN_SUCCESS)
            self._load_data()

    def _create_mapping_for(self, comm: Commission):
        xempus_name = comm.xempus_berater_name or ""
        vu_name = comm.vermittler_name or ""
        primary_name = xempus_name or vu_name
        if not primary_name:
            return
        run_worker(
            self, lambda w: self._backend.get_employees(),
            lambda employees, c=comm: self._show_create_mapping_dialog(c, employees),
        )

    def _show_create_mapping_dialog(self, comm: Commission, employees):
        xempus_name = comm.xempus_berater_name or ""
        vu_name = comm.vermittler_name or ""
        primary_name = xempus_name or vu_name

        dlg = QDialog(self)
        dlg.setWindowTitle(texts.PROVISION_MAP_DLG_CREATE_TITLE)
        dlg.setMinimumWidth(420)
        form = QFormLayout(dlg)

        if vu_name:
            vu_lbl = QLabel(texts.PROVISION_MAPPING_DLG_VU_NAME.format(name=vu_name))
            vu_lbl.setStyleSheet(f"font-size: {FONT_SIZE_CAPTION};")
            vu_lbl.setWordWrap(True)
            form.addRow(vu_lbl)

        if xempus_name:
            xempus_lbl = QLabel(texts.PROVISION_MAPPING_DLG_XEMPUS_NAME.format(name=xempus_name))
            xempus_lbl.setStyleSheet(f"font-weight: 600; color: {PRIMARY_900}; font-size: 11pt;")
            xempus_lbl.setWordWrap(True)
            form.addRow(xempus_lbl)

        berater_combo = QComboBox()
        berater_combo.addItem("\u2014", None)
        for emp in employees:
            if emp.is_active and emp.role in ('consulter', 'teamleiter', 'geschaeftsfuehrer'):
                berater_combo.addItem(emp.name, emp.id)
        form.addRow(texts.PROVISION_MAPPING_DLG_SELECT, berater_combo)

        also_vu_cb = None
        if vu_name and xempus_name and vu_name.lower() != xempus_name.lower():
            also_vu_cb = QCheckBox(texts.PROVISION_MAPPING_DLG_BOTH)
            also_vu_cb.setChecked(True)
            form.addRow(also_vu_cb)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        form.addRow(buttons)

        if dlg.exec() == QDialog.Accepted:
            berater_id = berater_combo.currentData()
            if berater_id:
                also_name = None
                if also_vu_cb and also_vu_cb.isChecked() and vu_name != primary_name:
                    also_name = vu_name
                self._mapping_worker = MappingSyncWorker(
                    self._backend, primary_name, berater_id, also_name)
                self._mapping_worker.finished.connect(self._on_mapping_sync_done)
                self._mapping_worker.error.connect(self._on_mapping_sync_error)
                self._loading_overlay.setVisible(True)
                self._mapping_worker.start()

    def _on_mapping_sync_done(self, stats):
        self._loading_overlay.setVisible(False)
        if self._toast_manager:
            self._toast_manager.show_success(texts.PROVISION_TOAST_MAPPING_CREATED)
        self._load_data()

    def _on_mapping_sync_error(self, msg: str):
        self._loading_overlay.setVisible(False)
        logger.error(f"Mapping-Sync-Fehler: {msg}")
        if self._toast_manager:
            self._toast_manager.show_error(texts.PROVISION_DASH_ERROR)


