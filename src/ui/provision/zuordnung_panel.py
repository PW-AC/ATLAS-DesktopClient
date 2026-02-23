"""
Zuordnung & Klaerfaelle-Panel: Klaerfall-Typen, Vermittler-Zuordnungen.

Ersetzt: mappings_panel.py
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableView,
    QHeaderView, QFrame, QPushButton, QDialog, QComboBox,
    QLineEdit, QScrollArea, QSizePolicy, QMenu,
    QFormLayout, QDialogButtonBox, QCheckBox, QMessageBox,
)
from PySide6.QtCore import (
    Qt, Signal, QAbstractTableModel, QModelIndex, QThread, QTimer,
)
from typing import List, Dict, Optional

from api.provision import (
    ProvisionAPI, Commission, VermittlerMapping, Employee,
    ContractSearchResult, Contract, PaginationInfo,
)
from api.client import APIError
from ui.styles.tokens import (
    PRIMARY_100, PRIMARY_500, PRIMARY_900, ACCENT_500,
    BG_PRIMARY, BG_SECONDARY, BORDER_DEFAULT,
    SUCCESS, ERROR, WARNING,
    FONT_BODY, FONT_SIZE_BODY, FONT_SIZE_CAPTION,
    PILL_COLORS, build_rich_tooltip, get_provision_table_style,
)
from ui.provision.widgets import (
    FilterChipBar, SectionHeader, KpiCard, PillBadgeDelegate, ProvisionLoadingOverlay,
    PaginationBar, format_eur, get_secondary_button_style, get_search_field_style,
)
from i18n import de as texts
import logging

logger = logging.getLogger(__name__)


def _clearance_type(c) -> str:
    """Bestimmt den Klaerfall-Typ anhand von match_status und berater_id."""
    if c.match_status == 'unmatched':
        return texts.PROVISION_CLEAR_TYPE_NO_CONTRACT
    if c.match_status in ('auto_matched', 'manual_matched') and not c.berater_id:
        return texts.PROVISION_CLEAR_TYPE_NO_BERATER
    return texts.PROVISION_CLEAR_TYPE_NO_CONTRACT


class _ClearanceLoadWorker(QThread):
    finished = Signal(object, object)
    error = Signal(str)

    def __init__(self, api: ProvisionAPI):
        super().__init__()
        self._api = api

    def run(self):
        try:
            unmatched, _ = self._api.get_commissions(match_status='unmatched', limit=1000)
            all_matched, _ = self._api.get_commissions(limit=5000)
            berater_missing = [c for c in all_matched
                               if c.match_status in ('auto_matched', 'manual_matched') and not c.berater_id]
            commissions = unmatched + berater_missing
            mappings_data = self._api.get_mappings(include_unmapped=True)
            self.finished.emit(commissions, mappings_data)
        except Exception as e:
            self.error.emit(str(e))


class _UnmatchedModel(QAbstractTableModel):
    COL_VU = 0
    COL_VSNR = 1
    COL_KUNDE = 2
    COL_BETRAG = 3
    COL_XEMPUS_BERATER = 4
    COL_SOURCE = 5
    COL_PROBLEM = 6

    COLUMNS = [
        texts.PROVISION_POS_COL_VU,
        texts.PROVISION_POS_COL_VSNR,
        texts.PROVISION_POS_COL_KUNDE,
        texts.PROVISION_POS_COL_BETRAG,
        texts.PROVISION_POS_COL_XEMPUS_BERATER,
        texts.PROVISION_POS_COL_SOURCE,
        texts.PROVISION_CLEAR_PROBLEM,
    ]

    def __init__(self):
        super().__init__()
        self._data: List[Commission] = []

    def set_data(self, data: List[Commission]):
        self.beginResetModel()
        self._data = data
        self.endResetModel()

    def get_item(self, row: int) -> Optional[Commission]:
        if 0 <= row < len(self._data):
            return self._data[row]
        return None

    def rowCount(self, parent=QModelIndex()):
        return len(self._data)

    def columnCount(self, parent=QModelIndex()):
        return len(self.COLUMNS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self.COLUMNS[section]
        return None

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        c = self._data[index.row()]
        col = index.column()

        if role == Qt.DisplayRole:
            if col == self.COL_VU:
                return c.versicherer or ""
            elif col == self.COL_VSNR:
                return c.vsnr or ""
            elif col == self.COL_KUNDE:
                return c.versicherungsnehmer or ""
            elif col == self.COL_BETRAG:
                return format_eur(c.betrag)
            elif col == self.COL_XEMPUS_BERATER:
                return c.xempus_berater_name or "\u2014"
            elif col == self.COL_SOURCE:
                return c.source_label
            elif col == self.COL_PROBLEM:
                return _clearance_type(c)

        if role == Qt.TextAlignmentRole and col == self.COL_BETRAG:
            return Qt.AlignRight | Qt.AlignVCenter

        return None


class _MappingsModel(QAbstractTableModel):
    COLUMNS = [
        texts.PROVISION_MAP_COL_VU_NAME,
        texts.PROVISION_MAP_COL_BERATER,
    ]

    def __init__(self):
        super().__init__()
        self._data: List[VermittlerMapping] = []

    def set_data(self, data: List[VermittlerMapping]):
        self.beginResetModel()
        self._data = data
        self.endResetModel()

    def get_item(self, row: int) -> Optional[VermittlerMapping]:
        if 0 <= row < len(self._data):
            return self._data[row]
        return None

    def rowCount(self, parent=QModelIndex()):
        return len(self._data)

    def columnCount(self, parent=QModelIndex()):
        return len(self.COLUMNS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self.COLUMNS[section]
        return None

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        m = self._data[index.row()]
        col = index.column()
        if role == Qt.DisplayRole:
            if col == 0:
                return m.vermittler_name
            elif col == 1:
                return m.berater_name or f"ID {m.berater_id}"
        return None


class ZuordnungPanel(QWidget):
    """Zuordnung & Klaerfaelle: Offene Positionen und Vermittler-Mappings."""

    navigate_to_panel = Signal(int)

    def __init__(self, api: ProvisionAPI):
        super().__init__()
        self._api = api
        self._worker = None
        self._toast_manager = None
        self._all_unmatched: list = []
        self._setup_ui()
        QTimer.singleShot(100, self._load_data)

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
            QPushButton:hover {{ background-color: #e88a2d; }}
        """)
        auto_btn.clicked.connect(self._trigger_auto_match)
        header.add_action(auto_btn)
        layout.addWidget(header)

        # Klaerfall-Chips
        self._chips = FilterChipBar()
        self._chips.filter_changed.connect(self._filter_clearance)
        layout.addWidget(self._chips)

        # Klaerfall-Tabelle
        self._unmatched_model = _UnmatchedModel()
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
                "vermittler_unbekannt": {"bg": "#fee2e2", "text": "#991b1b"},
                "berater-mapping_fehlt": PILL_COLORS.get("vertrag_gefunden", {"bg": "#fef3c7", "text": "#92400e"}),
            }
        )
        self._unmatched_table.setItemDelegateForColumn(
            _UnmatchedModel.COL_PROBLEM, problem_delegate)
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

        self._mappings_model = _MappingsModel()
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

    def _load_data(self):
        self._status.setText("")
        self._loading_overlay.setGeometry(self.rect())
        self._loading_overlay.setVisible(True)
        if self._worker:
            if self._worker.isRunning():
                return
            try:
                self._worker.finished.disconnect()
                self._worker.error.disconnect()
            except RuntimeError:
                pass
        self._worker = _ClearanceLoadWorker(self._api)
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
        stats = self._api.trigger_auto_match()
        if stats:
            matched = stats.get('matched', 0)
            still_open = stats.get('still_unmatched', 0)
            if self._toast_manager:
                self._toast_manager.show_success(
                    texts.PROVISION_TOAST_AUTOMATCH_DONE.format(matched=matched, open=still_open)
                )
            self._load_data()

    def _add_mapping(self):
        dlg = QDialog(self)
        dlg.setWindowTitle(texts.PROVISION_MAP_DLG_TITLE)
        dlg.setMinimumWidth(400)
        form = QFormLayout(dlg)

        name_edit = QLineEdit()
        name_edit.setPlaceholderText(texts.PROVISION_MAP_DLG_NAME)
        form.addRow(texts.PROVISION_MAP_DLG_NAME, name_edit)

        berater_combo = QComboBox()
        employees = self._api.get_employees()
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
                self._api.create_mapping(name, berater_id)
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
        dlg = QDialog(self)
        dlg.setWindowTitle(texts.PROVISION_MENU_EDIT)
        dlg.setMinimumWidth(400)
        form = QFormLayout(dlg)

        name_lbl = QLabel(mapping.vermittler_name)
        name_lbl.setStyleSheet(f"font-weight: 500; color: {PRIMARY_900};")
        form.addRow(texts.PROVISION_MAP_DLG_NAME, name_lbl)

        berater_combo = QComboBox()
        employees = self._api.get_employees()
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
                self._api.delete_mapping(mapping.id)
                self._api.create_mapping(mapping.vermittler_name, new_berater_id)
                if self._toast_manager:
                    self._toast_manager.show_success(texts.PROVISION_TOAST_SAVED)
                self._load_data()

    def _delete_mapping(self, mapping: VermittlerMapping):
        if self._api.delete_mapping(mapping.id):
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
        dlg = MatchContractDialog(self._api, comm, parent=self)
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

        dlg = QDialog(self)
        dlg.setWindowTitle(texts.PROVISION_MAP_DLG_CREATE_TITLE)
        dlg.setMinimumWidth(420)
        form = QFormLayout(dlg)

        if vu_name:
            vu_lbl = QLabel(texts.PROVISION_MAPPING_DLG_VU_NAME.format(name=vu_name))
            vu_lbl.setStyleSheet(f"color: {PRIMARY_500}; font-size: {FONT_SIZE_CAPTION};")
            vu_lbl.setWordWrap(True)
            form.addRow(vu_lbl)

        if xempus_name:
            xempus_lbl = QLabel(texts.PROVISION_MAPPING_DLG_XEMPUS_NAME.format(name=xempus_name))
            xempus_lbl.setStyleSheet(f"font-weight: 600; color: {PRIMARY_900}; font-size: 11pt;")
            xempus_lbl.setWordWrap(True)
            form.addRow(xempus_lbl)

        berater_combo = QComboBox()
        berater_combo.addItem("\u2014", None)
        employees = self._api.get_employees()
        for emp in employees:
            if emp.is_active and emp.role in ('consulter', 'teamleiter'):
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
                self._mapping_worker = _MappingSyncWorker(
                    self._api, primary_name, berater_id, also_name)
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


class _MappingSyncWorker(QThread):
    """Erstellt Mapping(s) und fuehrt Auto-Match im Hintergrund aus."""
    finished = Signal(object)
    error = Signal(str)

    def __init__(self, api: ProvisionAPI, primary_name: str, berater_id: int,
                 also_vu_name: str = None):
        super().__init__()
        self._api = api
        self._primary_name = primary_name
        self._berater_id = berater_id
        self._also_vu_name = also_vu_name

    def run(self):
        try:
            self._api.create_mapping(self._primary_name, self._berater_id)
            if self._also_vu_name:
                try:
                    self._api.create_mapping(self._also_vu_name, self._berater_id)
                except Exception:
                    pass
            stats = self._api.trigger_auto_match()
            self.finished.emit(stats or {})
        except Exception as e:
            self.error.emit(str(e))


# =============================================================================
# MatchContractDialog – Vertragszuordnung mit Suche
# =============================================================================

MATCH_REASON_LABELS = {
    'vsnr_exact': texts.PROVISION_MATCH_DLG_SCORE_VSNR_EXACT,
    'vsnr_alt': texts.PROVISION_MATCH_DLG_SCORE_VSNR_ALT,
    'name_exact': texts.PROVISION_MATCH_DLG_SCORE_NAME_EXACT,
    'name_partial': texts.PROVISION_MATCH_DLG_SCORE_NAME_PARTIAL,
}

MATCH_SCORE_COLORS = {
    100: {"bg": "#dcfce7", "text": "#166534"},
    90: {"bg": "#dbeafe", "text": "#1e40af"},
    70: {"bg": "#fef9c3", "text": "#854d0e"},
    40: {"bg": "#fee2e2", "text": "#991b1b"},
}


class _MatchSearchWorker(QThread):
    finished = Signal(object, object)
    error = Signal(str)

    def __init__(self, api: ProvisionAPI, commission_id: int, q: str = None):
        super().__init__()
        self._api = api
        self._commission_id = commission_id
        self._q = q

    def run(self):
        try:
            result = self._api.get_match_suggestions(
                commission_id=self._commission_id,
                direction='forward',
                q=self._q,
                limit=50,
            )
            suggestions = result.get('suggestions', [])
            commission = result.get('commission', {})
            self.finished.emit(suggestions, commission)
        except Exception as e:
            self.error.emit(str(e))


class _SuggestionsModel(QAbstractTableModel):
    COL_SCORE = 0
    COL_VSNR = 1
    COL_KUNDE = 2
    COL_VU = 3
    COL_SPARTE = 4
    COL_BERATER = 5
    COL_REASON = 6

    COLUMNS = [
        texts.PROVISION_MATCH_DLG_SCORE_LABEL,
        texts.PROVISION_POS_COL_VSNR,
        texts.PROVISION_POS_COL_KUNDE,
        texts.PROVISION_POS_COL_VU,
        texts.PROVISION_MATCH_DLG_COL_SPARTE,
        texts.PROVISION_POS_COL_BERATER,
        texts.PROVISION_MATCH_DLG_COL_REASON,
    ]

    def __init__(self):
        super().__init__()
        self._data: List[ContractSearchResult] = []

    def set_data(self, data: List[ContractSearchResult]):
        self.beginResetModel()
        self._data = data
        self.endResetModel()

    def get_item(self, row: int) -> Optional[ContractSearchResult]:
        if 0 <= row < len(self._data):
            return self._data[row]
        return None

    def rowCount(self, parent=QModelIndex()):
        return len(self._data)

    def columnCount(self, parent=QModelIndex()):
        return len(self.COLUMNS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self.COLUMNS[section]
        return None

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        item = self._data[index.row()]
        ct = item.contract
        col = index.column()

        if role == Qt.DisplayRole:
            if col == self.COL_SCORE:
                return str(item.match_score)
            elif col == self.COL_VSNR:
                return ct.vsnr or "\u2014"
            elif col == self.COL_KUNDE:
                return ct.versicherungsnehmer or ""
            elif col == self.COL_VU:
                return ct.versicherer or ""
            elif col == self.COL_SPARTE:
                return ct.sparte or ""
            elif col == self.COL_BERATER:
                return ct.berater_name or "\u2014"
            elif col == self.COL_REASON:
                return item.match_reason or ''

        if role == Qt.TextAlignmentRole and col == self.COL_SCORE:
            return Qt.AlignCenter

        return None


class MatchContractDialog(QDialog):
    """Dialog fuer manuelle Vertragszuordnung mit Multi-Level-Matching."""

    def __init__(self, api: ProvisionAPI, commission: Commission, parent=None):
        super().__init__(parent)
        self._api = api
        self._comm = commission
        self._worker: Optional[_MatchSearchWorker] = None
        self._selected_contract: Optional[ContractSearchResult] = None
        self.setWindowTitle(texts.PROVISION_MATCH_DLG_TITLE)
        self.setMinimumSize(780, 550)
        self._setup_ui()
        QTimer.singleShot(100, self._auto_search)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # Original VU-Datensatz
        orig_frame = QFrame()
        orig_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {BG_SECONDARY};
                border: 1px solid {BORDER_DEFAULT};
                border-radius: 8px;
                padding: 12px;
            }}
        """)
        orig_layout = QVBoxLayout(orig_frame)
        orig_layout.setSpacing(6)

        orig_title = QLabel(texts.PROVISION_MATCH_DLG_ORIGINAL)
        orig_title.setStyleSheet(f"font-weight: 600; color: {PRIMARY_900}; border: none;")
        orig_layout.addWidget(orig_title)

        details = QHBoxLayout()
        for label, value in [
            (texts.PROVISION_POS_COL_VU, self._comm.versicherer or self._comm.vu_name or "\u2014"),
            (texts.PROVISION_POS_COL_VSNR, self._comm.vsnr or "\u2014"),
            (texts.PROVISION_POS_COL_KUNDE, self._comm.versicherungsnehmer or "\u2014"),
            (texts.PROVISION_POS_COL_BETRAG, format_eur(self._comm.betrag)),
            (texts.PROVISION_POS_COL_XEMPUS_BERATER, self._comm.xempus_berater_name or "\u2014"),
        ]:
            item = QLabel(f"<b>{label}:</b> {value}")
            item.setStyleSheet(f"color: {PRIMARY_900}; font-size: {FONT_SIZE_CAPTION}; border: none;")
            details.addWidget(item)
        details.addStretch()
        orig_layout.addLayout(details)

        source_lbl = QLabel(f"{texts.PROVISION_POS_COL_SOURCE}: {self._comm.source_label}")
        source_lbl.setStyleSheet(f"color: {PRIMARY_500}; font-size: {FONT_SIZE_CAPTION}; border: none;")
        orig_layout.addWidget(source_lbl)

        layout.addWidget(orig_frame)

        # Suchzeile
        search_row = QHBoxLayout()
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText(texts.PROVISION_MATCH_DLG_SEARCH)
        self._search_edit.setFixedHeight(34)
        self._search_edit.setStyleSheet(get_search_field_style())
        self._search_edit.returnPressed.connect(self._do_search)
        search_row.addWidget(self._search_edit)

        search_btn = QPushButton(texts.PROVISION_MATCH_DLG_SEARCH_BTN)
        search_btn.setFixedHeight(34)
        search_btn.setStyleSheet(f"""
            QPushButton {{ background-color: {ACCENT_500}; color: white; border: none;
                border-radius: 6px; padding: 4px 16px; font-weight: 500; }}
            QPushButton:hover {{ background-color: #e88a2d; }}
        """)
        search_btn.clicked.connect(self._do_search)
        search_row.addWidget(search_btn)
        layout.addLayout(search_row)

        # Ergebnis-Titel
        self._results_title = QLabel(texts.PROVISION_MATCH_DLG_RESULTS)
        self._results_title.setStyleSheet(f"font-weight: 600; font-size: 11pt; color: {PRIMARY_900};")
        layout.addWidget(self._results_title)

        # Ergebnistabelle
        self._suggestions_model = _SuggestionsModel()
        self._table = QTableView()
        self._table.setModel(self._suggestions_model)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QTableView.SelectRows)
        self._table.setSelectionMode(QTableView.SingleSelection)
        self._table.verticalHeader().setVisible(False)
        self._table.verticalHeader().setDefaultSectionSize(42)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._table.setStyleSheet(get_provision_table_style())
        self._table.setMinimumHeight(200)
        self._table.selectionModel().selectionChanged.connect(self._on_selection)

        score_delegate = PillBadgeDelegate(
            {str(k): v for k, v in MATCH_SCORE_COLORS.items()},
        )
        self._table.setItemDelegateForColumn(_SuggestionsModel.COL_SCORE, score_delegate)

        reason_delegate = PillBadgeDelegate({
            'vsnr_exact': {"bg": "#dcfce7", "text": "#166534"},
            'vsnr_alt': {"bg": "#dbeafe", "text": "#1e40af"},
            'name_exact': {"bg": "#fef9c3", "text": "#854d0e"},
            'name_partial': {"bg": "#fee2e2", "text": "#991b1b"},
        }, label_map={
            'vsnr_exact': texts.PROVISION_MATCH_DLG_SCORE_VSNR_EXACT,
            'vsnr_alt': texts.PROVISION_MATCH_DLG_SCORE_VSNR_ALT,
            'name_exact': texts.PROVISION_MATCH_DLG_SCORE_NAME_EXACT,
            'name_partial': texts.PROVISION_MATCH_DLG_SCORE_NAME_PARTIAL,
        })
        self._table.setItemDelegateForColumn(_SuggestionsModel.COL_REASON, reason_delegate)

        layout.addWidget(self._table, 1)

        # Status
        self._status_label = QLabel("")
        self._status_label.setStyleSheet(f"color: {PRIMARY_500}; font-size: {FONT_SIZE_CAPTION};")
        layout.addWidget(self._status_label)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self._assign_btn = QPushButton(texts.PROVISION_MATCH_DLG_ASSIGN)
        self._assign_btn.setEnabled(False)
        self._assign_btn.setFixedHeight(36)
        self._assign_btn.setStyleSheet(f"""
            QPushButton {{ background-color: {ACCENT_500}; color: white; border: none;
                border-radius: 6px; padding: 8px 24px; font-weight: 600; }}
            QPushButton:hover {{ background-color: #e88a2d; }}
            QPushButton:disabled {{ background-color: {BORDER_DEFAULT}; color: {PRIMARY_500}; }}
        """)
        self._assign_btn.clicked.connect(self._do_assign)
        btn_row.addWidget(self._assign_btn)

        cancel_btn = QPushButton(texts.PROVISION_MATCH_DLG_CANCEL)
        cancel_btn.setFixedHeight(36)
        cancel_btn.setStyleSheet(get_secondary_button_style())
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        layout.addLayout(btn_row)

    def _auto_search(self):
        """Automatische Server-Suche beim Oeffnen."""
        self._status_label.setText(texts.PROVISION_MATCH_DLG_LOADING)
        self._suggestions_model.set_data([])
        self._run_search(q=None)

    def _do_search(self):
        q = self._search_edit.text().strip()
        self._status_label.setText(texts.PROVISION_MATCH_DLG_LOADING)
        self._suggestions_model.set_data([])
        self._run_search(q=q if q else None)

    def _run_search(self, q: str = None):
        if self._worker and self._worker.isRunning():
            return
        self._worker = _MatchSearchWorker(self._api, self._comm.id, q=q)
        self._worker.finished.connect(self._on_results)
        self._worker.error.connect(self._on_search_error)
        self._worker.start()

    def _on_results(self, suggestions: list, commission: dict):
        results = []
        for s in suggestions:
            if isinstance(s, ContractSearchResult):
                results.append(s)
            elif isinstance(s, dict):
                results.append(ContractSearchResult.from_dict(s))
            else:
                results.append(s)
        self._suggestions_model.set_data(results)
        if results:
            count = len(results)
            self._status_label.setText(
                texts.PROVISION_MATCH_RESULTS_COUNT.format(count=count)
            )
        else:
            self._status_label.setText(texts.PROVISION_MATCH_DLG_NO_RESULTS)

    def _on_search_error(self, msg: str):
        self._status_label.setText(f"{texts.PROVISION_ERROR_PREFIX}: {msg}")
        logger.error(f"Match-Suche fehlgeschlagen: {msg}")

    def _on_selection(self, selected, deselected):
        indexes = self._table.selectionModel().selectedRows()
        if indexes:
            item = self._suggestions_model.get_item(indexes[0].row())
            self._selected_contract = item
            self._assign_btn.setEnabled(item is not None)
        else:
            self._selected_contract = None
            self._assign_btn.setEnabled(False)

    def _do_assign(self):
        if not self._selected_contract:
            return
        contract = self._selected_contract.contract
        force = bool(self._comm.contract_id)

        if force:
            reply = QMessageBox.question(
                self,
                texts.PROVISION_MATCH_DLG_REASSIGN,
                texts.PROVISION_MATCH_DLG_FORCE,
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return

        try:
            self._api.assign_contract(
                commission_id=self._comm.id,
                contract_id=contract.id,
                force_override=force,
            )
            self.accept()
        except APIError as e:
            self._status_label.setText(
                texts.PROVISION_TOAST_ASSIGN_CONFLICT.format(msg=str(e))
            )
            self._status_label.setStyleSheet(f"color: {ERROR}; font-size: {FONT_SIZE_CAPTION};")
