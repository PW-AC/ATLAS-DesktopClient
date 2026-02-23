"""
Provisionspositionen-Panel: Tabelle mit Pill-Badges, FilterChips,
Detail-Panel rechts (QSplitter) mit Zuordnung/Verteilung/Audit.

Ersetzt: commissions_panel.py + contracts_panel.py
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableView,
    QHeaderView, QSplitter, QFrame, QScrollArea, QMenu,
    QComboBox, QLineEdit, QPushButton, QSizePolicy,
    QDialog, QFormLayout, QDialogButtonBox, QDateEdit,
)
from PySide6.QtCore import (
    Qt, Signal, QAbstractTableModel, QModelIndex, QThread,
    QSortFilterProxyModel, QTimer, QDate,
)
from PySide6.QtGui import QColor
from typing import List, Optional
from datetime import datetime, date
import calendar

from api.provision import ProvisionAPI, Commission, Employee, ContractSearchResult
from api.client import APIError
from ui.styles.tokens import (
    PRIMARY_100, PRIMARY_500, PRIMARY_900, ACCENT_500,
    BG_PRIMARY, BG_SECONDARY, BG_TERTIARY, BORDER_DEFAULT,
    SUCCESS, ERROR, WARNING,
    FONT_BODY, FONT_SIZE_BODY, FONT_SIZE_CAPTION,
    PILL_COLORS, ROLE_BADGE_COLORS, ART_BADGE_COLORS,
    build_rich_tooltip, get_provision_table_style,
)
from ui.provision.widgets import (
    PillBadgeDelegate, FilterChipBar, SectionHeader, ThreeDotMenuDelegate,
    PaginationBar, ActivityFeedWidget, ProvisionLoadingOverlay,
    format_eur, get_search_field_style,
)
from i18n import de as texts
import logging

logger = logging.getLogger(__name__)

def _status_label(c) -> str:
    """Differenzierter Status-Text basierend auf match_status + berater_id."""
    if c.match_status in ('auto_matched', 'manual_matched', 'matched'):
        if c.berater_id:
            return texts.PROVISION_STATUS_ZUGEORDNET
        return texts.PROVISION_STATUS_VERTRAG_GEFUNDEN
    if c.match_status == 'unmatched':
        return texts.PROVISION_STATUS_OFFEN
    if c.match_status == 'ignored':
        return texts.PROVISION_STATUS_IGNORIERT
    if c.match_status == 'gesperrt':
        return texts.PROVISION_STATUS_GESPERRT
    return c.match_status


def _status_pill_key(c) -> str:
    """Pill-Color-Key basierend auf match_status + berater_id."""
    if c.match_status in ('auto_matched', 'manual_matched', 'matched'):
        if c.berater_id:
            return 'zugeordnet'
        return 'vertrag_gefunden'
    if c.match_status == 'unmatched':
        return 'offen'
    if c.match_status == 'ignored':
        return 'ignoriert'
    if c.match_status == 'gesperrt':
        return 'gesperrt'
    return c.match_status

ART_LABELS = {
    'ap': texts.PROVISION_COMM_ART_AP,
    'bp': texts.PROVISION_COMM_ART_BP,
    'rueckbelastung': texts.PROVISION_COMM_ART_RUECK,
    'nullmeldung': texts.PROVISION_COMM_ART_NULL,
    'sonstige': texts.PROVISION_COMM_ART_SONSTIGE,
}


class _LoadWorker(QThread):
    finished = Signal(object)
    error = Signal(str)

    def __init__(self, api: ProvisionAPI, **kwargs):
        super().__init__()
        self._api = api
        self._kwargs = kwargs

    def run(self):
        try:
            data, _ = self._api.get_commissions(**self._kwargs)
            self.finished.emit(data)
        except Exception as e:
            self.error.emit(str(e))


class _AuditLoadWorker(QThread):
    finished = Signal(int, list)
    error = Signal(str)

    def __init__(self, api: ProvisionAPI, comm_id: int):
        super().__init__()
        self._api = api
        self._comm_id = comm_id

    def run(self):
        try:
            entries = self._api.get_audit_log(entity_type='commission', entity_id=self._comm_id, limit=10)
            self.finished.emit(self._comm_id, entries)
        except Exception as e:
            self.error.emit(str(e))


class _IgnoreWorker(QThread):
    finished = Signal(bool)
    error = Signal(str)

    def __init__(self, api: ProvisionAPI, comm_id: int):
        super().__init__()
        self._api = api
        self._comm_id = comm_id

    def run(self):
        try:
            ok = self._api.ignore_commission(self._comm_id)
            self.finished.emit(ok)
        except Exception as e:
            self.error.emit(str(e))


class _MappingWorker(QThread):
    finished = Signal()
    error = Signal(str)

    def __init__(self, api: ProvisionAPI, name: str, berater_id: int):
        super().__init__()
        self._api = api
        self._name = name
        self._berater_id = berater_id

    def run(self):
        try:
            self._api.create_mapping(self._name, self._berater_id)
            self._api.trigger_auto_match()
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))


class _PositionsModel(QAbstractTableModel):
    COL_DATUM = 0
    COL_VU = 1
    COL_VSNR = 2
    COL_KUNDE = 3
    COL_BETRAG = 4
    COL_XEMPUS_BERATER = 5
    COL_BERATER = 6
    COL_STATUS = 7
    COL_BERATER_ANTEIL = 8
    COL_SOURCE = 9
    COL_MENU = 10

    COLUMNS = [
        texts.PROVISION_POS_COL_DATUM,
        texts.PROVISION_POS_COL_VU,
        texts.PROVISION_POS_COL_VSNR,
        texts.PROVISION_POS_COL_KUNDE,
        texts.PROVISION_POS_COL_BETRAG,
        texts.PROVISION_POS_COL_XEMPUS_BERATER,
        texts.PROVISION_POS_COL_BERATER,
        texts.PROVISION_POS_COL_STATUS,
        texts.PROVISION_POS_COL_BERATER_ANTEIL,
        texts.PROVISION_POS_COL_SOURCE,
        "",
    ]

    TOOLTIPS = [
        texts.PROVISION_TIP_COL_DATUM,
        texts.PROVISION_TIP_COL_VERSICHERER,
        texts.PROVISION_TIP_COL_VSNR,
        texts.PROVISION_TIP_COL_KUNDE,
        build_rich_tooltip(texts.PROVISION_TIP_COL_BETRAG),
        texts.PROVISION_TIP_COL_XEMPUS_BERATER,
        texts.PROVISION_TIP_COL_BERATER,
        build_rich_tooltip(
            texts.PROVISION_TIP_COL_STATUS,
            hinweis=texts.PROVISION_TIP_STATUS_HINT,
        ),
        build_rich_tooltip(texts.PROVISION_TIP_COL_BERATER_ANTEIL),
        texts.PROVISION_TIP_COL_SOURCE,
        "",
    ]

    def __init__(self):
        super().__init__()
        self._data: List[Commission] = []

    def set_data(self, data: List[Commission]):
        self.beginResetModel()
        self._data = data
        self.endResetModel()

    def get_commission(self, row: int) -> Optional[Commission]:
        if 0 <= row < len(self._data):
            return self._data[row]
        return None

    def rowCount(self, parent=QModelIndex()):
        return len(self._data)

    def columnCount(self, parent=QModelIndex()):
        return len(self.COLUMNS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal:
            if role == Qt.DisplayRole:
                return self.COLUMNS[section]
            if role == Qt.ToolTipRole and section < len(self.TOOLTIPS):
                return self.TOOLTIPS[section] or None
        return None

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        c = self._data[index.row()]
        col = index.column()

        if role == Qt.DisplayRole:
            if col == self.COL_VU:
                return c.versicherer or c.vu_name or ""
            elif col == self.COL_DATUM:
                d = c.auszahlungsdatum or ""
                if len(d) >= 10:
                    try:
                        dt = datetime.strptime(d[:10], "%Y-%m-%d")
                        return dt.strftime("%d.%m.%Y")
                    except ValueError:
                        pass
                return d
            elif col == self.COL_KUNDE:
                return c.versicherungsnehmer or ""
            elif col == self.COL_VSNR:
                return c.vsnr or ""
            elif col == self.COL_BETRAG:
                return format_eur(c.betrag)
            elif col == self.COL_BERATER_ANTEIL:
                return format_eur(c.berater_anteil) if c.berater_anteil is not None else ""
            elif col == self.COL_STATUS:
                return _status_label(c)
            elif col == self.COL_BERATER:
                return c.berater_name or "\u2014"
            elif col == self.COL_XEMPUS_BERATER:
                return c.xempus_berater_name or "\u2014"
            elif col == self.COL_SOURCE:
                return c.source_label
            elif col == self.COL_MENU:
                return ""

        if role == Qt.TextAlignmentRole:
            if col in (self.COL_BETRAG, self.COL_BERATER_ANTEIL):
                return Qt.AlignRight | Qt.AlignVCenter

        if role == Qt.ForegroundRole and col == self.COL_BETRAG:
            if c.betrag < 0:
                return QColor(ERROR)

        if role == Qt.UserRole:
            return c

        return None


class ProvisionspositionenPanel(QWidget):
    """Provisionspositionen mit FilterChips, Pill-Badges und Detail-Panel."""

    navigate_to_panel = Signal(int)

    def __init__(self, api: ProvisionAPI):
        super().__init__()
        self._api = api
        self._worker = None
        self._all_data: List[Commission] = []
        self._filtered_data: List[Commission] = []
        self._toast_manager = None
        self._current_detail_comm: Optional[Commission] = None
        self._employees_cache: List[Employee] = []
        self._setup_ui()
        QTimer.singleShot(100, self._load_data)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        header = SectionHeader(
            texts.PROVISION_POS_TITLE,
            texts.PROVISION_POS_DESC,
        )
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

        # FilterChips + Suche
        filter_row = QHBoxLayout()
        self._chips = FilterChipBar()
        self._chips.filter_changed.connect(self._apply_filter)
        filter_row.addWidget(self._chips)

        self._search = QLineEdit()
        self._search.setPlaceholderText(texts.PROVISION_SEARCH)
        self._search.setFixedWidth(220)
        self._search.setFixedHeight(32)
        self._search.setStyleSheet(get_search_field_style())
        self._search.textChanged.connect(self._apply_filter)
        filter_row.addWidget(self._search)

        layout.addLayout(filter_row)

        # Splitter: Tabelle links, Detail rechts
        self._splitter = QSplitter(Qt.Horizontal)

        # Tabelle
        table_widget = QWidget()
        table_layout = QVBoxLayout(table_widget)
        table_layout.setContentsMargins(0, 0, 0, 0)

        self._model = _PositionsModel()
        self._proxy = QSortFilterProxyModel()
        self._proxy.setSourceModel(self._model)
        self._proxy.setFilterCaseSensitivity(Qt.CaseInsensitive)

        self._table = QTableView()
        self._table.setModel(self._proxy)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QTableView.SelectRows)
        self._table.setSelectionMode(QTableView.SingleSelection)
        self._table.verticalHeader().setVisible(False)
        self._table.verticalHeader().setDefaultSectionSize(52)
        self._table.horizontalHeader().setDefaultSectionSize(52)
        self._table.horizontalHeader().setStretchLastSection(False)
        self._table.horizontalHeader().setMinimumSectionSize(50)
        self._table.setStyleSheet(get_provision_table_style())
        self._table.setMinimumHeight(400)
        self._table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._table.selectionModel().selectionChanged.connect(self._on_selection_changed)

        status_delegate = PillBadgeDelegate(PILL_COLORS)
        self._table.setItemDelegateForColumn(_PositionsModel.COL_STATUS, status_delegate)
        self._status_delegate = status_delegate

        menu_delegate = ThreeDotMenuDelegate(self._build_row_menu)
        self._table.setItemDelegateForColumn(_PositionsModel.COL_MENU, menu_delegate)
        self._menu_delegate = menu_delegate

        table_layout.addWidget(self._table)

        self._pagination = PaginationBar(page_size=50)
        self._pagination.page_changed.connect(self._on_page_changed)
        table_layout.addWidget(self._pagination)

        self._splitter.addWidget(table_widget)

        # Detail-Panel
        self._detail_panel = self._create_detail_panel()
        self._detail_panel.setVisible(False)
        self._splitter.addWidget(self._detail_panel)

        self._splitter.setStretchFactor(0, 3)
        self._splitter.setStretchFactor(1, 1)
        layout.addWidget(self._splitter, 1)

        self._status = QLabel("")
        self._status.setStyleSheet(f"color: {ERROR}; font-size: {FONT_SIZE_CAPTION};")
        layout.addWidget(self._status)

        self._loading_overlay = ProvisionLoadingOverlay(self)

    def _create_detail_panel(self) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background-color: white;
                border: 1px solid {BORDER_DEFAULT};
                border-radius: 8px;
            }}
        """)
        frame.setMinimumWidth(320)
        frame.setMaximumWidth(420)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")

        content = QWidget()
        self._detail_layout = QVBoxLayout(content)
        self._detail_layout.setContentsMargins(16, 16, 16, 16)
        self._detail_layout.setSpacing(12)

        self._det_close = QPushButton("\u2715")
        self._det_close.setFixedSize(28, 28)
        self._det_close.setStyleSheet(f"""
            QPushButton {{ border: none; color: {PRIMARY_500}; font-size: 14pt; background: transparent; }}
            QPushButton:hover {{ color: {PRIMARY_900}; }}
        """)
        self._det_close.clicked.connect(lambda: self._detail_panel.setVisible(False))
        close_row = QHBoxLayout()
        close_row.addStretch()
        close_row.addWidget(self._det_close)
        self._detail_layout.addLayout(close_row)

        # Originaldaten
        self._det_section_orig = QLabel(texts.PROVISION_POS_DETAIL_ORIGINAL)
        self._det_section_orig.setStyleSheet(f"font-weight: 600; font-size: 11pt; color: {PRIMARY_900};")
        self._detail_layout.addWidget(self._det_section_orig)
        self._det_vu = self._add_detail_field(texts.PROVISION_POS_COL_VU)
        self._det_vsnr = self._add_detail_field(texts.PROVISION_POS_COL_VSNR)
        self._det_betrag = self._add_detail_field(texts.PROVISION_POS_COL_BETRAG)
        self._det_art = self._add_detail_field(texts.PROVISION_POS_DETAIL_ART)
        self._det_datum = self._add_detail_field(texts.PROVISION_POS_COL_DATUM)
        self._det_kunde = self._add_detail_field(texts.PROVISION_POS_COL_KUNDE)

        # Zuordnung
        self._det_section_match = QLabel(texts.PROVISION_POS_DETAIL_MATCHING)
        self._det_section_match.setStyleSheet(f"font-weight: 600; font-size: 11pt; color: {PRIMARY_900}; margin-top: 8px;")
        self._detail_layout.addWidget(self._det_section_match)
        self._det_status = self._add_detail_field(texts.PROVISION_POS_COL_STATUS)
        self._det_method = self._add_detail_field(texts.PROVISION_POS_DETAIL_MATCHING_METHOD)
        self._det_xempus_berater = self._add_detail_field(texts.PROVISION_POS_COL_XEMPUS_BERATER)
        self._det_berater = self._add_detail_field(texts.PROVISION_POS_COL_BERATER)

        # Verteilung
        self._det_section_dist = QLabel(texts.PROVISION_POS_DETAIL_DISTRIBUTION)
        self._det_section_dist.setStyleSheet(f"font-weight: 600; font-size: 11pt; color: {PRIMARY_900}; margin-top: 8px;")
        self._detail_layout.addWidget(self._det_section_dist)
        self._det_ag = self._add_detail_field(texts.PROVISION_TIP_COL_AG_ANTEIL[:20])
        self._det_berater_ant = self._add_detail_field(texts.PROVISION_POS_DETAIL_BERATER_ANTEIL)
        self._det_tl = self._add_detail_field(texts.PROVISION_POS_DETAIL_TEAMLEITER)

        # Audit-Log
        self._det_section_audit = QLabel(texts.PROVISION_POS_DETAIL_AUDIT)
        self._det_section_audit.setStyleSheet(f"font-weight: 600; font-size: 11pt; color: {PRIMARY_900}; margin-top: 8px;")
        self._detail_layout.addWidget(self._det_section_audit)
        self._activity_feed = ActivityFeedWidget()
        self._activity_feed.setMaximumHeight(200)
        self._detail_layout.addWidget(self._activity_feed)

        self._detail_layout.addStretch()

        # Aktionen
        self._det_btn_assign = QPushButton(texts.PROVISION_ACT_MANUAL_MATCH)
        self._det_btn_assign.setToolTip(texts.PROVISION_ACT_MANUAL_MATCH_TIP)
        self._det_btn_assign.setStyleSheet(f"""
            QPushButton {{ background-color: {ACCENT_500}; color: white; border: none;
                border-radius: 6px; padding: 8px 16px; font-weight: 500; }}
            QPushButton:hover {{ background-color: #e88a2d; }}
        """)
        self._det_btn_assign.clicked.connect(self._on_detail_assign)
        self._detail_layout.addWidget(self._det_btn_assign)

        self._det_btn_ignore = QPushButton(texts.PROVISION_ACT_IGNORE)
        self._det_btn_ignore.setToolTip(texts.PROVISION_ACT_IGNORE_TIP)
        self._det_btn_ignore.clicked.connect(self._on_detail_ignore)
        self._detail_layout.addWidget(self._det_btn_ignore)

        scroll.setWidget(content)
        outer = QVBoxLayout(frame)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)
        return frame

    def _add_detail_field(self, label: str) -> QLabel:
        row = QHBoxLayout()
        lbl = QLabel(f"{label}:")
        lbl.setStyleSheet(f"color: {PRIMARY_500}; font-size: {FONT_SIZE_CAPTION};")
        lbl.setFixedWidth(120)
        row.addWidget(lbl)
        val = QLabel("")
        val.setStyleSheet(f"color: {PRIMARY_900}; font-size: {FONT_SIZE_BODY}; font-weight: 500;")
        val.setWordWrap(True)
        row.addWidget(val)
        self._detail_layout.addLayout(row)
        return val

    def _build_row_menu(self, index: QModelIndex) -> Optional[QMenu]:
        source_idx = self._proxy.mapToSource(index)
        comm = self._model.get_commission(source_idx.row())
        if not comm:
            return None
        menu = QMenu(self)
        menu.addAction(texts.PROVISION_MENU_DETAILS, lambda: self._show_detail(comm))
        if comm.match_status == 'unmatched':
            menu.addAction(texts.PROVISION_MATCH_DLG_ASSIGN, lambda: self._manual_match(comm))
        if comm.contract_id:
            menu.addAction(texts.PROVISION_MATCH_DLG_REASSIGN, lambda: self._manual_match(comm))
        mappable_name = comm.xempus_berater_name or comm.vermittler_name
        if not comm.berater_id and mappable_name:
            menu.addAction(texts.PROVISION_MAP_DLG_CREATE_TITLE, lambda: self._create_mapping_for(comm))
        menu.addAction(texts.PROVISION_MENU_IGNORE, lambda: self._ignore_commission(comm))
        return menu

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
        if self._worker:
            if self._worker.isRunning():
                return
            try:
                self._worker.finished.disconnect()
                self._worker.error.disconnect()
            except RuntimeError:
                pass
        von, bis = self._get_date_range()
        logger.debug(f"Positionen _load_data: von={von}, bis={bis}")
        kwargs = dict(limit=5000)
        if von:
            kwargs['von'] = von
        if bis:
            kwargs['bis'] = bis
        self._worker = _LoadWorker(self._api, **kwargs)
        self._worker.finished.connect(self._on_loaded)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_loaded(self, data: List[Commission]):
        self._loading_overlay.setVisible(False)
        self._all_data = data
        self._update_chips()
        self._apply_filter()
        self._resize_columns()
        self._status.setText("")

    def _on_error(self, msg: str):
        self._loading_overlay.setVisible(False)
        self._status.setText(texts.PROVISION_DASH_ERROR)
        logger.error(f"Positionen-Ladefehler: {msg}")

    def _update_chips(self):
        total = len(self._all_data)
        zugeordnet = sum(1 for c in self._all_data
                         if c.match_status in ('auto_matched', 'manual_matched', 'matched') and c.berater_id)
        vertrag_gef = sum(1 for c in self._all_data
                          if c.match_status in ('auto_matched', 'manual_matched', 'matched') and not c.berater_id)
        unmatched = sum(1 for c in self._all_data if c.match_status == 'unmatched')
        locked = sum(1 for c in self._all_data if c.match_status in ('gesperrt', 'ignored'))
        self._chips.set_chips([
            ("alle", texts.PROVISION_POS_FILTER_ALL, total),
            ("zugeordnet", texts.PROVISION_POS_FILTER_MATCHED, zugeordnet),
            ("vertrag_gefunden", texts.PROVISION_STATUS_VERTRAG_GEFUNDEN, vertrag_gef),
            ("offen", texts.PROVISION_POS_FILTER_UNMATCHED, unmatched),
            ("gesperrt", texts.PROVISION_POS_FILTER_LOCKED, locked),
        ])

    def _apply_filter(self, *args):
        key = self._chips.active_key()
        search = self._search.text().strip().lower()

        filtered = self._all_data
        if key == "zugeordnet":
            filtered = [c for c in filtered
                        if c.match_status in ('auto_matched', 'manual_matched', 'matched') and c.berater_id]
        elif key == "vertrag_gefunden":
            filtered = [c for c in filtered
                        if c.match_status in ('auto_matched', 'manual_matched', 'matched') and not c.berater_id]
        elif key == "offen":
            filtered = [c for c in filtered if c.match_status == 'unmatched']
        elif key == "gesperrt":
            filtered = [c for c in filtered if c.match_status in ('gesperrt', 'ignored')]

        if search:
            filtered = [c for c in filtered if
                        search in (c.versicherer or "").lower() or
                        search in (c.vsnr or "").lower() or
                        search in (c.versicherungsnehmer or "").lower() or
                        search in (c.berater_name or "").lower() or
                        search in (c.xempus_berater_name or "").lower()]

        self._filtered_data = filtered
        self._pagination.set_total(len(filtered))
        self._paginate()

    def _on_page_changed(self, page: int):
        self._paginate()

    def _paginate(self):
        page = self._pagination.current_page
        ps = self._pagination._page_size
        start = page * ps
        end = start + ps
        self._model.set_data(self._filtered_data[start:end])

    def _resize_columns(self):
        header = self._table.horizontalHeader()
        for i in range(self._model.columnCount()):
            if i == _PositionsModel.COL_MENU:
                header.setSectionResizeMode(i, QHeaderView.Fixed)
                self._table.setColumnWidth(i, 48)
            elif i == _PositionsModel.COL_STATUS:
                header.setSectionResizeMode(i, QHeaderView.Fixed)
                self._table.setColumnWidth(i, 170)
            else:
                header.setSectionResizeMode(i, QHeaderView.Stretch)

    def _on_selection_changed(self, selected, deselected):
        indexes = self._table.selectionModel().selectedRows()
        if not indexes:
            return
        source_idx = self._proxy.mapToSource(indexes[0])
        comm = self._model.get_commission(source_idx.row())
        if comm:
            self._show_detail(comm)

    def _show_detail(self, comm: Commission):
        self._current_detail_comm = comm
        show_assign = comm.match_status == 'unmatched' or comm.contract_id is not None
        self._det_btn_assign.setVisible(show_assign)
        if comm.contract_id:
            self._det_btn_assign.setText(texts.PROVISION_MATCH_DLG_REASSIGN)
        else:
            self._det_btn_assign.setText(texts.PROVISION_ACT_MANUAL_MATCH)
        self._det_btn_ignore.setVisible(comm.match_status not in ('ignored', 'gesperrt'))
        self._det_vu.setText(comm.versicherer or comm.vu_name or "")
        self._det_vsnr.setText(comm.vsnr or "")
        self._det_betrag.setText(format_eur(comm.betrag))
        self._det_art.setText(ART_LABELS.get(comm.art, comm.art))
        d = comm.auszahlungsdatum or ""
        if len(d) >= 10:
            try:
                dt = datetime.strptime(d[:10], "%Y-%m-%d")
                d = dt.strftime("%d.%m.%Y")
            except ValueError:
                pass
        self._det_datum.setText(d)
        self._det_kunde.setText(comm.versicherungsnehmer or "")

        self._det_status.setText(_status_label(comm))

        if comm.match_status == 'auto_matched':
            method = texts.PROVISION_TIP_MATCHING_NORMALIZED
        elif comm.match_status == 'manual_matched':
            method = texts.PROVISION_TIP_MATCHING_MANUAL
        elif comm.match_status in ('matched',):
            method = texts.PROVISION_TIP_MATCHING_EXACT
        else:
            method = "\u2014"
        self._det_method.setText(method)
        self._det_xempus_berater.setText(comm.xempus_berater_name or "\u2014")
        self._det_berater.setText(comm.berater_name or "\u2014")

        self._det_ag.setText(format_eur(comm.ag_anteil) if comm.ag_anteil is not None else "\u2014")
        self._det_berater_ant.setText(format_eur(comm.berater_anteil) if comm.berater_anteil is not None else "\u2014")
        self._det_tl.setText(format_eur(comm.tl_anteil) if comm.tl_anteil is not None else "\u2014")

        self._detail_panel.setVisible(True)
        self._load_audit(comm)

    def _load_audit(self, comm: Commission):
        if hasattr(self, '_audit_worker') and self._audit_worker and self._audit_worker.isRunning():
            return
        self._audit_worker = _AuditLoadWorker(self._api, comm.id)
        self._audit_worker.finished.connect(self._on_audit_loaded)
        self._audit_worker.error.connect(lambda msg: self._activity_feed.set_items([]))
        self._audit_worker.start()

    def _on_audit_loaded(self, comm_id: int, entries: list):
        if self._current_detail_comm and self._current_detail_comm.id != comm_id:
            return
        feed_items = []
        for e in entries:
            action = e.get('action', '')
            action_type = 'default'
            if 'match' in action:
                action_type = 'matched'
            elif 'import' in action:
                action_type = 'import'
            elif 'status' in action:
                action_type = 'status'
            elif 'create' in action:
                action_type = 'created'
            elif 'delete' in action:
                action_type = 'deleted'
            feed_items.append({
                'type': action_type,
                'text': e.get('description', action),
                'time': e.get('created_at', '')[:16].replace('T', ' ') if e.get('created_at') else '',
            })
        self._activity_feed.set_items(feed_items)

    def _ignore_commission(self, comm: Commission):
        if hasattr(self, '_ignore_worker') and self._ignore_worker and self._ignore_worker.isRunning():
            return
        self._ignore_worker = _IgnoreWorker(self._api, comm.id)
        self._ignore_worker.finished.connect(self._on_ignore_finished)
        self._ignore_worker.error.connect(lambda msg: logger.warning(f"Ignore fehlgeschlagen: {msg}"))
        self._ignore_worker.start()

    def _on_ignore_finished(self, ok: bool):
        if ok:
            if self._toast_manager:
                self._toast_manager.show_success(texts.PROVISION_TOAST_IGNORED)
            self._load_data()

    def _on_detail_assign(self):
        if self._current_detail_comm:
            self._manual_match(self._current_detail_comm)

    def _on_detail_ignore(self):
        if self._current_detail_comm:
            self._ignore_commission(self._current_detail_comm)

    def _manual_match(self, comm: Commission):
        from ui.provision.zuordnung_panel import MatchContractDialog
        dlg = MatchContractDialog(self._api, comm, parent=self)
        if dlg.exec() == QDialog.Accepted:
            if self._toast_manager:
                self._toast_manager.show_success(texts.PROVISION_TOAST_ASSIGN_SUCCESS)
            self._load_data()

    def _create_mapping_for(self, comm: Commission):
        from ui.provision.zuordnung_panel import ZuordnungPanel
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
        if not self._employees_cache:
            self._employees_cache = self._api.get_employees()
        for emp in self._employees_cache:
            if emp.is_active and emp.role in ('consulter', 'teamleiter'):
                berater_combo.addItem(emp.name, emp.id)
        form.addRow(texts.PROVISION_MAPPING_DLG_SELECT, berater_combo)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        form.addRow(buttons)

        if dlg.exec() == QDialog.Accepted:
            berater_id = berater_combo.currentData()
            if berater_id:
                self._start_mapping_worker(primary_name, berater_id)

    def _start_mapping_worker(self, name: str, berater_id: int):
        if hasattr(self, '_mapping_worker') and self._mapping_worker and self._mapping_worker.isRunning():
            return
        self._mapping_worker = _MappingWorker(self._api, name, berater_id)
        self._mapping_worker.finished.connect(self._on_mapping_finished)
        self._mapping_worker.error.connect(lambda msg: logger.warning(f"Mapping fehlgeschlagen: {msg}"))
        self._mapping_worker.start()

    def _on_mapping_finished(self):
        if self._toast_manager:
            self._toast_manager.show_success(texts.PROVISION_TOAST_MAPPING_CREATED)
        self._load_data()
