"""
Provisionspositionen-Panel: Tabelle mit Pill-Badges, FilterChips,
Detail-Panel rechts (QSplitter) mit Zuordnung/Verteilung/Audit.

Ersetzt: commissions_panel.py + contracts_panel.py
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableView,
    QHeaderView, QSplitter, QFrame, QScrollArea, QMenu,
    QComboBox, QLineEdit, QPushButton, QSizePolicy, QCheckBox,
    QDialog, QFormLayout, QDialogButtonBox, QDateEdit,
)
from PySide6.QtCore import (
    Qt, Signal, QSortFilterProxyModel, QTimer, QDate, QModelIndex,
)
from PySide6.QtGui import QColor
from typing import List, Optional
from datetime import datetime, date
import calendar

from api.provision import ProvisionAPI
from domain.provision.entities import Commission, Employee, ContractSearchResult, PaginationInfo
from api.client import APIError
from ui.styles.tokens import (
    PRIMARY_100, PRIMARY_500, PRIMARY_900, ACCENT_500,
    BG_PRIMARY, BG_SECONDARY, BG_TERTIARY, BORDER_DEFAULT,
    SUCCESS, ERROR, WARNING,
    FONT_BODY, FONT_SIZE_BODY, FONT_SIZE_CAPTION,
    PILL_COLORS, ROLE_BADGE_COLORS, ART_BADGE_COLORS,
    get_provision_table_style,
)
from ui.provision.widgets import (
    PillBadgeDelegate, FilterChipBar, SectionHeader, ThreeDotMenuDelegate,
    PaginationBar, ActivityFeedWidget, ProvisionLoadingOverlay,
    format_eur, get_search_field_style,
)
from ui.provision.workers import (
    PositionsLoadWorker, AuditLoadWorker, IgnoreWorker, MappingCreateWorker,
)
from ui.provision.models import PositionsModel, status_label, status_pill_key, ART_LABELS
from ui.provision.dialogs import MatchContractDialog
from i18n import de as texts
import logging

logger = logging.getLogger(__name__)


class ProvisionspositionenPanel(QWidget):
    """Provisionspositionen mit FilterChips, Pill-Badges und Detail-Panel.

    Implementiert IPositionsView fuer den PositionsPresenter.
    """

    navigate_to_panel = Signal(int)

    def __init__(self, api: ProvisionAPI = None):
        super().__init__()
        self._api = api
        self._presenter = None
        self._worker = None
        self._all_data: List[Commission] = []
        self._filtered_data: List[Commission] = []
        self._toast_manager = None
        self._current_detail_comm: Optional[Commission] = None
        self._employees_cache: List[Employee] = []
        self._setup_ui()
        if api:
            QTimer.singleShot(100, self._load_data)

    @property
    def _backend(self):
        return self._presenter or self._api

    def set_presenter(self, presenter) -> None:
        """Verbindet dieses Panel mit dem PositionsPresenter."""
        self._presenter = presenter
        presenter.set_view(self)
        self._load_data()

    # ── IPositionsView ──

    def show_commissions(self, commissions: List[Commission],
                         pagination: Optional[PaginationInfo] = None) -> None:
        """View-Interface: Provisionen anzeigen."""
        self._loading_overlay.setVisible(False)
        self._all_data = commissions
        self._update_chips()
        self._apply_filter()
        self._resize_columns()

    def show_loading(self, loading: bool) -> None:
        """View-Interface: Ladezustand."""
        overlay = getattr(self, '_loading_overlay', None)
        if overlay:
            overlay.setVisible(loading)

    def show_error(self, message: str) -> None:
        """View-Interface: Fehler anzeigen."""
        logger.error(f"Positionen-Fehler: {message}")

    def show_detail(self, commission: Commission) -> None:
        """View-Interface: Detail-Panel aktualisieren."""
        self._show_detail(commission)

    def update_filter_counts(self, total: int, filtered: int) -> None:
        """View-Interface: Filterzaehler aktualisieren."""
        pass

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

        self._relevance_cb = QCheckBox(texts.PROVISION_RELEVANCE_TOGGLE)
        self._relevance_cb.setChecked(True)
        self._relevance_cb.setToolTip(texts.PROVISION_RELEVANCE_TOGGLE_TIP)
        self._relevance_cb.setStyleSheet(
            f"color: {PRIMARY_500}; font-size: {FONT_SIZE_CAPTION}; font-family: {FONT_BODY};")
        self._relevance_cb.stateChanged.connect(self._on_relevance_changed)
        filter_row.addWidget(self._relevance_cb)

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

        self._model = PositionsModel()
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
        self._table.horizontalHeader().setDefaultSectionSize(100)
        self._table.horizontalHeader().setStretchLastSection(False)
        self._table.horizontalHeader().setMinimumSectionSize(40)
        self._table.setStyleSheet(get_provision_table_style())
        self._table.setMinimumHeight(400)
        self._table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._table.selectionModel().selectionChanged.connect(self._on_selection_changed)

        status_delegate = PillBadgeDelegate(PILL_COLORS)
        self._table.setItemDelegateForColumn(PositionsModel.COL_STATUS, status_delegate)
        self._status_delegate = status_delegate

        menu_delegate = ThreeDotMenuDelegate(self._build_row_menu)
        self._table.setItemDelegateForColumn(PositionsModel.COL_MENU, menu_delegate)
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

    def _on_relevance_changed(self, state):
        """Relevanz-Filter umgeschaltet: Daten neu laden."""
        if self._presenter:
            self._presenter.only_relevant = self._relevance_cb.isChecked()
            self._presenter.refresh()
        else:
            self._load_data()

    def _load_data(self):
        self._status.setText("")
        self._loading_overlay.setGeometry(self.rect())
        self._loading_overlay.setVisible(True)

        von, bis = self._get_date_range()
        logger.debug(f"Positionen _load_data: von={von}, bis={bis}")

        if self._presenter:
            kwargs = dict(limit=5000)
            if von:
                kwargs['von'] = von
            if bis:
                kwargs['bis'] = bis
            self._presenter.load_positions(**kwargs)
            return

        if self._worker:
            if self._worker.isRunning():
                return
            try:
                self._worker.finished.disconnect()
                self._worker.error.disconnect()
            except RuntimeError:
                pass
        kwargs = dict(limit=5000)
        if von:
            kwargs['von'] = von
        if bis:
            kwargs['bis'] = bis
        self._worker = PositionsLoadWorker(self._backend, **kwargs)
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
        col_widths = {
            PositionsModel.COL_DATUM: 85,
            PositionsModel.COL_VU: 80,
            PositionsModel.COL_VSNR: 120,
            PositionsModel.COL_BETRAG: 90,
            PositionsModel.COL_BUCHUNGSART: 70,
            PositionsModel.COL_XEMPUS_BERATER: 120,
            PositionsModel.COL_BERATER: 110,
            PositionsModel.COL_STATUS: 110,
            PositionsModel.COL_BERATER_ANTEIL: 80,
            PositionsModel.COL_SOURCE: 60,
            PositionsModel.COL_MENU: 36,
        }
        stretch_col = PositionsModel.COL_KUNDE
        for i in range(self._model.columnCount()):
            if i == stretch_col:
                header.setSectionResizeMode(i, QHeaderView.Stretch)
            elif i == PositionsModel.COL_MENU:
                header.setSectionResizeMode(i, QHeaderView.Fixed)
                self._table.setColumnWidth(i, 36)
            elif i in col_widths:
                header.setSectionResizeMode(i, QHeaderView.ResizeToContents)
            else:
                header.setSectionResizeMode(i, QHeaderView.ResizeToContents)

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
        self._det_art.setText(comm.buchungsart_raw or ART_LABELS.get(comm.art, comm.art))
        d = comm.auszahlungsdatum or ""
        if len(d) >= 10:
            try:
                dt = datetime.strptime(d[:10], "%Y-%m-%d")
                d = dt.strftime("%d.%m.%Y")
            except ValueError:
                pass
        self._det_datum.setText(d)
        self._det_kunde.setText(comm.versicherungsnehmer or "")

        self._det_status.setText(status_label(comm))

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
        self._audit_worker = AuditLoadWorker(self._backend, comm.id)
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
        self._ignore_worker = IgnoreWorker(self._backend, comm.id)
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
        # MatchContractDialog importiert ueber dialogs.py (top-level)
        dlg = MatchContractDialog(self._backend, comm, parent=self)
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
        self._employees_cache = self._backend.get_employees()
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
        self._mapping_worker = MappingCreateWorker(self._backend, name, berater_id)
        self._mapping_worker.finished.connect(self._on_mapping_finished)
        self._mapping_worker.error.connect(lambda msg: logger.warning(f"Mapping fehlgeschlagen: {msg}"))
        self._mapping_worker.start()

    def _on_mapping_finished(self):
        if self._toast_manager:
            self._toast_manager.show_success(texts.PROVISION_TOAST_MAPPING_CREATED)
        self._load_data()
