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
    Qt, Signal, QTimer, QDate, QModelIndex, QObject,
)
from PySide6.QtGui import QColor
from typing import List, Optional
from datetime import datetime, date
import calendar

from api.provision import ProvisionAPI
from domain.provision.entities import Commission, Employee, ContractSearchResult, PaginationInfo
from ui.styles.tokens import (
    PRIMARY_100, PRIMARY_500, PRIMARY_900, ACCENT_500, ACCENT_HOVER,
    BG_PRIMARY, BG_SECONDARY, BG_TERTIARY, BORDER_DEFAULT,
    SUCCESS, ERROR, WARNING,
    FONT_BODY, FONT_SIZE_BODY, FONT_SIZE_CAPTION,
    PILL_COLORS, ROLE_BADGE_COLORS, ART_BADGE_COLORS,
    get_provision_table_style,
)
from ui.provision.widgets import (
    PillBadgeDelegate, FilterChipBar, SectionHeader, ThreeDotMenuDelegate,
    ActivityFeedWidget, ProvisionLoadingOverlay, ColumnFilterRow,
    format_eur, get_search_field_style,
)
from ui.provision.workers import (
    PositionsLoadWorker, AuditLoadWorker, IgnoreWorker, MappingCreateWorker,
    OverrideWorker, OverrideResetWorker, NoteWorker, RawDataLoadWorker,
)
from ui.provision.models import PositionsModel, PositionsFilterProxy, status_label, status_pill_key, ART_LABELS, build_positions_cache
from ui.provision.dialogs import MatchContractDialog, OverrideDialog, NoteDialog
from infrastructure.threading.worker_utils import run_worker
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
        self._filter_ctx = QObject(self)
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
        self._schedule_filter(debounce_ms=0)
        self._resize_columns()
        total = pagination.total if pagination else len(commissions)
        if total > 50000 and self._toast_manager:
            self._toast_manager.show_info(
                texts.PM_POSITIONS_LOADED_CHUNKED.format(count=len(commissions)))

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
        self._chips.filter_changed.connect(lambda: self._schedule_filter(debounce_ms=300))
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
        filter_row.addWidget(self._search)

        self._clear_filter_btn = QPushButton(texts.PM_FILTER_CLEAR_ALL)
        self._clear_filter_btn.setFixedHeight(32)
        self._clear_filter_btn.setCursor(Qt.PointingHandCursor)
        self._clear_filter_btn.setStyleSheet(
            f"color: {PRIMARY_500}; background: transparent; border: none; "
            f"font-size: {FONT_SIZE_CAPTION}; font-family: {FONT_BODY};")
        self._clear_filter_btn.clicked.connect(self._clear_all_filters)
        self._clear_filter_btn.setVisible(False)
        filter_row.addWidget(self._clear_filter_btn)

        layout.addLayout(filter_row)

        # Splitter: Tabelle links, Detail rechts
        self._splitter = QSplitter(Qt.Horizontal)

        # Tabelle
        table_widget = QWidget()
        table_layout = QVBoxLayout(table_widget)
        table_layout.setContentsMargins(0, 0, 0, 0)

        self._model = PositionsModel()
        self._proxy = PositionsFilterProxy()
        self._proxy.setSourceModel(self._model)

        self._search.textChanged.connect(self._on_search_changed)

        self._table = QTableView()
        self._table.setModel(self._proxy)
        self._table.setSortingEnabled(True)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QTableView.SelectRows)
        self._table.setSelectionMode(QTableView.SingleSelection)
        self._table.verticalHeader().setVisible(False)
        self._table.verticalHeader().setDefaultSectionSize(38)
        self._table.horizontalHeader().setDefaultSectionSize(100)
        self._table.horizontalHeader().setStretchLastSection(False)
        self._table.horizontalHeader().setMinimumSectionSize(40)
        self._table.setStyleSheet(get_provision_table_style())
        self._table.setMinimumHeight(400)
        self._table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._table.setContextMenuPolicy(Qt.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._on_context_menu)
        self._table.selectionModel().selectionChanged.connect(self._on_selection_changed)

        status_delegate = PillBadgeDelegate(PILL_COLORS)
        self._table.setItemDelegateForColumn(PositionsModel.COL_STATUS, status_delegate)
        self._status_delegate = status_delegate

        menu_delegate = ThreeDotMenuDelegate(self._build_row_menu)
        self._table.setItemDelegateForColumn(PositionsModel.COL_MENU, menu_delegate)
        self._menu_delegate = menu_delegate

        # Spaltenfilter-Zeile (Excel-Stil)
        status_options = [
            texts.PROVISION_STATUS_ZUGEORDNET,
            texts.PROVISION_STATUS_VERTRAG_GEFUNDEN,
            texts.PROVISION_STATUS_OFFEN,
            texts.PROVISION_STATUS_GESPERRT,
            texts.PROVISION_STATUS_IGNORIERT,
        ]
        self._col_filter_row = ColumnFilterRow(
            column_count=self._model.columnCount(),
            combo_options={
                PositionsModel.COL_STATUS: status_options,
            },
            skip_columns={PositionsModel.COL_MENU},
        )
        self._col_filter_row.column_filter_changed.connect(self._on_column_filter_changed)
        table_layout.addWidget(self._col_filter_row)

        table_layout.addWidget(self._table)

        self._filter_info = QLabel("")
        self._filter_info.setStyleSheet(
            f"color: {PRIMARY_500}; font-size: {FONT_SIZE_CAPTION}; font-family: {FONT_BODY};")
        table_layout.addWidget(self._filter_info)

        self._total_info = QLabel("")
        self._total_info.setStyleSheet(
            f"color: {PRIMARY_500}; font-size: {FONT_SIZE_CAPTION}; font-family: {FONT_BODY};")
        table_layout.addWidget(self._total_info)

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

        self._det_raw_btn = QPushButton(texts.PM_RAW_BTN_SHOW)
        self._det_raw_btn.setCursor(Qt.PointingHandCursor)
        self._det_raw_btn.clicked.connect(self._show_raw_data)
        self._detail_layout.addWidget(self._det_raw_btn)

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

        # Override-Info
        self._det_section_override = QLabel(texts.PM_OVERRIDE_TITLE)
        self._det_section_override.setStyleSheet(f"font-weight: 600; font-size: 11pt; color: {PRIMARY_900}; margin-top: 8px;")
        self._detail_layout.addWidget(self._det_section_override)
        self._det_override_original = self._add_detail_field(texts.PM_OVERRIDE_ORIGINAL)
        self._det_override_settled = self._add_detail_field(texts.PM_OVERRIDE_SETTLED)
        self._det_override_reason = self._add_detail_field(texts.PM_OVERRIDE_REASON)
        self._det_override_by = self._add_detail_field(texts.PM_OVERRIDE_BY)

        # Notiz
        self._det_section_note = QLabel(texts.PM_NOTE_TITLE)
        self._det_section_note.setStyleSheet(f"font-weight: 600; font-size: 11pt; color: {PRIMARY_900}; margin-top: 8px;")
        self._detail_layout.addWidget(self._det_section_note)
        self._det_note_text = QLabel("")
        self._det_note_text.setWordWrap(True)
        self._det_note_text.setStyleSheet(f"color: {PRIMARY_900}; font-size: {FONT_SIZE_BODY};")
        self._detail_layout.addWidget(self._det_note_text)
        self._det_note_meta = QLabel("")
        self._det_note_meta.setStyleSheet(f"color: {PRIMARY_500}; font-size: {FONT_SIZE_CAPTION}; font-style: italic;")
        self._detail_layout.addWidget(self._det_note_meta)

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
            QPushButton:hover {{ background-color: {ACCENT_HOVER}; }}
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
        return self._build_menu_for_commission(comm)

    def _build_menu_for_commission(self, comm: Commission) -> QMenu:
        menu = QMenu(self)
        menu.addAction(texts.PROVISION_MENU_DETAILS, lambda: self._show_detail(comm))
        if comm.import_batch_id:
            menu.addAction(texts.PM_RAW_BTN_SHOW, lambda: self._show_raw_data_for(comm))
        if comm.match_status == 'unmatched':
            menu.addAction(texts.PROVISION_MATCH_DLG_ASSIGN, lambda: self._manual_match(comm))
        if comm.contract_id:
            menu.addAction(texts.PROVISION_MATCH_DLG_REASSIGN, lambda: self._manual_match(comm))
        mappable_name = comm.xempus_berater_name or comm.vermittler_name
        if not comm.berater_id and mappable_name:
            menu.addAction(texts.PROVISION_MAP_DLG_CREATE_TITLE, lambda: self._create_mapping_for(comm))
        menu.addSeparator()
        menu.addAction(texts.PM_OVERRIDE_TITLE, lambda: self._open_override_dialog(comm))
        if comm.is_overridden:
            menu.addAction(texts.PM_OVERRIDE_RESET, lambda: self._reset_override(comm))
        menu.addAction(texts.PM_NOTE_TITLE, lambda: self._open_note_dialog(comm))
        menu.addSeparator()
        menu.addAction(texts.PROVISION_MENU_IGNORE, lambda: self._ignore_commission(comm))
        return menu

    def _on_context_menu(self, pos):
        index = self._table.indexAt(pos)
        if not index.isValid():
            return
        source_idx = self._proxy.mapToSource(index)
        comm = self._model.get_commission(source_idx.row())
        if not comm:
            return
        menu = self._build_menu_for_commission(comm)
        menu.exec(self._table.viewport().mapToGlobal(pos))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._loading_overlay.setGeometry(self.rect())
        if hasattr(self, '_col_filter_row'):
            self._col_filter_row.sync_widths(self._table.horizontalHeader())

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
            kwargs = dict(limit=50000)
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
        kwargs = dict(limit=50000)
        if von:
            kwargs['von'] = von
        if bis:
            kwargs['bis'] = bis
        self._worker = PositionsLoadWorker(self._backend, **kwargs)
        self._worker.finished.connect(self._on_loaded)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_loaded(self, data: List[Commission], pagination=None):
        self._loading_overlay.setVisible(False)
        self._all_data = data
        self._schedule_filter(debounce_ms=0)
        self._resize_columns()
        self._status.setText("")
        total = pagination.total if pagination else len(data)
        if total > 50000 and self._toast_manager:
            self._toast_manager.show_info(
                texts.PM_POSITIONS_LOADED_CHUNKED.format(count=len(data)))

    def _on_error(self, msg: str):
        self._loading_overlay.setVisible(False)
        self._status.setText(texts.PROVISION_DASH_ERROR)
        logger.error(f"Positionen-Ladefehler: {msg}")

    def _schedule_filter(self, debounce_ms: int = 0):
        """Chip-Zaehler, Statusfilter und Display-Cache im Background-Worker."""
        chip_key = self._chips.active_key()
        all_data = self._all_data

        def compute(worker):
            if worker.is_cancelled():
                return None
            total = len(all_data)
            zugeordnet = sum(1 for c in all_data
                             if c.match_status in ('auto_matched', 'manual_matched', 'matched') and c.berater_id)
            vertrag_gef = sum(1 for c in all_data
                              if c.match_status in ('auto_matched', 'manual_matched', 'matched') and not c.berater_id)
            unmatched = sum(1 for c in all_data if c.match_status == 'unmatched')
            locked = sum(1 for c in all_data if c.match_status in ('gesperrt', 'ignored'))
            if worker.is_cancelled():
                return None
            filtered = all_data
            if chip_key == "zugeordnet":
                filtered = [c for c in filtered
                            if c.match_status in ('auto_matched', 'manual_matched', 'matched') and c.berater_id]
            elif chip_key == "vertrag_gefunden":
                filtered = [c for c in filtered
                            if c.match_status in ('auto_matched', 'manual_matched', 'matched') and not c.berater_id]
            elif chip_key == "offen":
                filtered = [c for c in filtered if c.match_status == 'unmatched']
            elif chip_key == "gesperrt":
                filtered = [c for c in filtered if c.match_status in ('gesperrt', 'ignored')]
            if worker.is_cancelled():
                return None
            display_cache, tooltip_cache = build_positions_cache(filtered)
            return ([total, zugeordnet, vertrag_gef, unmatched, locked],
                    filtered, display_cache, tooltip_cache)

        run_worker(
            self._filter_ctx, compute, self._on_filter_computed,
            debounce_ms=debounce_ms,
        )

    def _on_filter_computed(self, result):
        if result is None:
            return
        counts, filtered, display_cache, tooltip_cache = result
        total, zugeordnet, vertrag_gef, unmatched, locked = counts
        self._chips.blockSignals(True)
        self._chips.set_chips([
            ("alle", texts.PROVISION_POS_FILTER_ALL, total),
            ("zugeordnet", texts.PROVISION_POS_FILTER_MATCHED, zugeordnet),
            ("vertrag_gefunden", texts.PROVISION_STATUS_VERTRAG_GEFUNDEN, vertrag_gef),
            ("offen", texts.PROVISION_POS_FILTER_UNMATCHED, unmatched),
            ("gesperrt", texts.PROVISION_POS_FILTER_LOCKED, locked),
        ])
        self._chips.blockSignals(False)
        self._filtered_data = filtered
        self._model.set_data_with_cache(filtered, display_cache, tooltip_cache)
        self._update_total_info(len(filtered))
        self._update_filter_info()

    def _update_total_info(self, count: int):
        if count > 0:
            self._total_info.setText(texts.PM_POSITIONS_TOTAL.format(count=count))
            self._total_info.setVisible(True)
        else:
            self._total_info.setVisible(False)

    def _on_search_changed(self, text: str) -> None:
        self._proxy.set_global_filter(text)
        self._update_filter_info()
        self._clear_filter_btn.setVisible(bool(text.strip()))

    def _on_column_filter_changed(self, column: int, text: str) -> None:
        self._proxy.set_column_filter(column, text)
        self._update_filter_info()
        has_any = bool(self._proxy._column_filters) or bool(self._search.text().strip())
        self._clear_filter_btn.setVisible(has_any)

    def _clear_all_filters(self) -> None:
        self._search.clear()
        self._col_filter_row.clear_all()
        self._proxy.clear_all_filters()
        self._update_filter_info()
        self._clear_filter_btn.setVisible(False)

    def _update_filter_info(self) -> None:
        visible = self._proxy.rowCount()
        total = self._model.rowCount()
        if visible < total:
            self._filter_info.setText(
                texts.PM_FILTER_SHOWING.format(visible=visible, total=total))
            self._filter_info.setVisible(True)
        else:
            self._filter_info.setVisible(False)

    def _resize_columns(self):
        header = self._table.horizontalHeader()
        col_widths = {
            PositionsModel.COL_DATUM: 90,
            PositionsModel.COL_VU: 100,
            PositionsModel.COL_VSNR: 140,
            PositionsModel.COL_BETRAG: 120,
            PositionsModel.COL_BUCHUNGSART: 110,
            PositionsModel.COL_XEMPUS_BERATER: 150,
            PositionsModel.COL_BERATER: 140,
            PositionsModel.COL_STATUS: 150,
            PositionsModel.COL_BERATER_ANTEIL: 120,
            PositionsModel.COL_MENU: 36,
        }
        stretch_col = PositionsModel.COL_KUNDE
        for i in range(self._model.columnCount()):
            if i == stretch_col:
                header.setSectionResizeMode(i, QHeaderView.Stretch)
            elif i in col_widths:
                header.setSectionResizeMode(i, QHeaderView.Interactive)
                self._table.setColumnWidth(i, col_widths[i])
            else:
                header.setSectionResizeMode(i, QHeaderView.Interactive)
        self._col_filter_row.sync_widths(header)

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
        self._det_raw_btn.setVisible(bool(comm.import_batch_id))

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

        has_override = comm.is_overridden
        self._det_section_override.setVisible(has_override)
        if has_override:
            self._det_override_original.setText(format_eur(comm.betrag))
            self._det_override_settled.setText(format_eur(comm.amount_settled))
            self._det_override_reason.setText(comm.amount_override_reason or "\u2014")
            override_info = comm.overrider_name or "\u2014"
            if comm.amount_overridden_at:
                override_info += f" ({comm.amount_overridden_at[:16]})"
            self._det_override_by.setText(override_info)
        else:
            self._det_override_original.setText("")
            self._det_override_settled.setText("")
            self._det_override_reason.setText("")
            self._det_override_by.setText("")

        has_note = comm.has_note
        self._det_section_note.setVisible(True)
        if has_note:
            self._det_note_text.setText(comm.note)
            self._det_note_text.setVisible(True)
            if comm.note_updater_name and comm.note_updated_at:
                self._det_note_meta.setText(texts.PM_NOTE_UPDATED_BY.format(
                    name=comm.note_updater_name, date=comm.note_updated_at[:16]))
                self._det_note_meta.setVisible(True)
            else:
                self._det_note_meta.setVisible(False)
        else:
            self._det_note_text.setText(texts.PM_NOTE_EMPTY)
            self._det_note_text.setVisible(True)
            self._det_note_meta.setVisible(False)

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

    def _show_raw_data_for(self, comm: Commission):
        """Originaldaten fuer eine beliebige Commission laden (aus Kontextmenue)."""
        if not comm or not comm.import_batch_id:
            return
        self._raw_comm = comm
        if hasattr(self, '_raw_worker') and self._raw_worker and self._raw_worker.isRunning():
            return
        logger.info(f"Rohdaten laden: batch_id={comm.import_batch_id}, sheet={comm.import_sheet_name}, vu={comm.import_vu_name}")
        self._raw_worker = RawDataLoadWorker(self._backend, comm.import_batch_id)
        self._raw_worker.finished.connect(self._on_raw_data_loaded)
        self._raw_worker.error.connect(self._on_raw_data_error)
        self._raw_worker.start()

    def _show_raw_data(self):
        comm = self._current_detail_comm
        if not comm or not comm.import_batch_id:
            return

        if hasattr(self, '_raw_worker') and self._raw_worker and self._raw_worker.isRunning():
            return

        self._det_raw_btn.setEnabled(False)
        self._det_raw_btn.setText(texts.PM_RAW_LOADING)

        self._raw_comm = comm
        logger.info(f"Rohdaten laden: batch_id={comm.import_batch_id}, sheet={comm.import_sheet_name}, vu={comm.import_vu_name}")
        self._raw_worker = RawDataLoadWorker(self._backend, comm.import_batch_id)
        self._raw_worker.finished.connect(self._on_raw_data_loaded)
        self._raw_worker.error.connect(self._on_raw_data_error)
        self._raw_worker.start()

    def _on_raw_data_loaded(self, batch_id: int, raw: dict):
        self._det_raw_btn.setEnabled(True)
        self._det_raw_btn.setText(texts.PM_RAW_BTN_SHOW)

        logger.info(f"Rohdaten GET batch={batch_id}: keys={list(raw.keys()) if raw else 'None'}, "
                     f"sheets={len(raw.get('sheets', []))} entries" if raw else "raw=None")
        sheets = raw.get('sheets', []) if raw else []
        if not sheets:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(self, texts.PM_RAW_BTN_SHOW, texts.PM_RAW_NO_DATA)
            return

        comm = self._raw_comm
        sheet_key = (comm.import_sheet_name or comm.import_vu_name) if comm else None
        sheet = None
        if sheet_key:
            sheet = next((s for s in sheets if s.get('sheet_name') == sheet_key), None)
        if not sheet and len(sheets) == 1:
            sheet = sheets[0]
        if not sheet:
            sheet = sheets[0]

        logger.info(f"Rohdaten-Viewer: sheet_key='{sheet_key}', "
                     f"gewaehlt='{sheet.get('sheet_name')}', "
                     f"source_row={comm.source_row if comm else None}, "
                     f"rows={len(sheet.get('rows', []))}")

        from ui.provision.raw_data_viewer import RawDataViewerDialog
        dlg = RawDataViewerDialog(
            parent=self,
            headers=sheet.get('headers', []),
            rows_data=sheet.get('rows', []),
            target_row=comm.source_row if comm else None,
            sheet_name=sheet.get('sheet_name'),
            title=texts.PM_RAW_TITLE_JSON.format(batch_id=batch_id),
        )
        dlg.exec()

    def _on_raw_data_error(self, error: str):
        self._det_raw_btn.setEnabled(True)
        self._det_raw_btn.setText(texts.PM_RAW_BTN_SHOW)
        logger.error(f"Rohdaten-Laden fehlgeschlagen: {error}")
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.warning(self, texts.PM_RAW_BTN_SHOW, texts.PM_RAW_LOAD_ERROR)

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

    def _open_override_dialog(self, comm: Commission):
        dlg = OverrideDialog(comm, parent=self)
        if dlg.exec() == QDialog.Accepted and dlg.amount is not None:
            self._override_worker = OverrideWorker(
                self._backend, comm.id, dlg.amount, dlg.reason)
            self._override_worker.finished.connect(self._on_override_finished)
            self._override_worker.error.connect(
                lambda msg: self._show_toast_error(texts.PM_OVERRIDE_TOAST_ERROR, msg))
            self._override_worker.start()

    def _on_override_finished(self, result):
        success = result.get('success', False) if isinstance(result, dict) else result
        if success:
            abr = result.get('abrechnungen') if isinstance(result, dict) else None
            count = abr.get('abrechnungen_regenerated', 0) if abr else 0
            if self._toast_manager:
                if count > 0:
                    self._toast_manager.show_success(
                        texts.PM_OVERRIDE_TOAST_SET_WITH_ABRECHNUNGEN.format(count=count))
                else:
                    self._toast_manager.show_success(texts.PM_OVERRIDE_TOAST_SET)
            self._load_data()
        else:
            if self._toast_manager:
                self._toast_manager.show_error(texts.PM_OVERRIDE_TOAST_ERROR)

    def _reset_override(self, comm: Commission):
        from PySide6.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self, texts.PM_OVERRIDE_RESET, texts.PM_OVERRIDE_RESET_CONFIRM,
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        self._override_reset_worker = OverrideResetWorker(self._backend, comm.id)
        self._override_reset_worker.finished.connect(self._on_override_reset_finished)
        self._override_reset_worker.error.connect(
            lambda msg: self._show_toast_error(texts.PM_OVERRIDE_TOAST_ERROR, msg))
        self._override_reset_worker.start()

    def _on_override_reset_finished(self, result):
        success = result.get('success', False) if isinstance(result, dict) else result
        if success:
            abr = result.get('abrechnungen') if isinstance(result, dict) else None
            count = abr.get('abrechnungen_regenerated', 0) if abr else 0
            if self._toast_manager:
                if count > 0:
                    self._toast_manager.show_success(
                        texts.PM_OVERRIDE_TOAST_RESET_WITH_ABRECHNUNGEN.format(count=count))
                else:
                    self._toast_manager.show_success(texts.PM_OVERRIDE_TOAST_RESET)
            self._load_data()
        else:
            if self._toast_manager:
                self._toast_manager.show_error(texts.PM_OVERRIDE_TOAST_ERROR)

    def _open_note_dialog(self, comm: Commission):
        dlg = NoteDialog(comm, parent=self)
        if dlg.exec() == QDialog.Accepted and dlg.note is not None:
            self._note_worker = NoteWorker(self._backend, comm.id, dlg.note)
            self._note_worker.finished.connect(self._on_note_finished)
            self._note_worker.error.connect(
                lambda msg: self._show_toast_error(texts.PM_NOTE_TOAST_ERROR, msg))
            self._note_worker.start()

    def _on_note_finished(self, ok: bool):
        if ok:
            if self._toast_manager:
                self._toast_manager.show_success(texts.PM_NOTE_TOAST_SAVED)
            self._load_data()
        else:
            if self._toast_manager:
                self._toast_manager.show_error(texts.PM_NOTE_TOAST_ERROR)

    def _show_toast_error(self, title: str, detail: str):
        logger.warning(f"{title}: {detail}")
        if self._toast_manager:
            self._toast_manager.show_error(f"{title}: {detail}")

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
        xempus_name = comm.xempus_berater_name or ""
        vu_name = comm.vermittler_name or ""
        primary_name = xempus_name or vu_name
        if not primary_name:
            return
        run_worker(
            self, lambda w: self._backend.get_employees(),
            lambda employees, c=comm: self._show_mapping_dialog(c, employees),
        )

    def _show_mapping_dialog(self, comm: Commission, employees):
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
        self._employees_cache = employees
        for emp in employees:
            if emp.is_active and emp.role in ('consulter', 'teamleiter', 'geschaeftsfuehrer'):
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
