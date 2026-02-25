"""
Xempus-Beratungen Panel: Listenansicht aller Xempus-Vertraege
mit Status-Anzeige, Filtern und Detail-Splitter.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableView,
    QHeaderView, QSplitter, QFrame, QScrollArea, QComboBox,
    QLineEdit, QPushButton, QSizePolicy,
)
from PySide6.QtCore import (
    Qt, Signal, QSortFilterProxyModel, QTimer, QModelIndex,
)
from PySide6.QtGui import QColor
from typing import List, Optional

from api.provision import ProvisionAPI, Contract, Commission, Employee
from api.client import APIError
from ui.styles.tokens import (
    PRIMARY_100, PRIMARY_500, PRIMARY_900, ACCENT_500,
    BG_PRIMARY, BG_SECONDARY, BG_TERTIARY, BORDER_DEFAULT,
    SUCCESS, ERROR, WARNING,
    FONT_BODY, FONT_SIZE_BODY, FONT_SIZE_CAPTION,
    PILL_COLORS, get_provision_table_style,
)
from ui.provision.widgets import (
    PillBadgeDelegate, FilterChipBar, SectionHeader,
    PaginationBar, ProvisionLoadingOverlay,
    format_eur, get_search_field_style, get_secondary_button_style,
)
from ui.provision.workers import XempusContractsLoadWorker, XempusDetailLoadWorker
from ui.provision.models import XempusContractsModel, xempus_status_label
from i18n import de as texts
import logging

logger = logging.getLogger(__name__)


class XempusPanel(QWidget):
    """Listenansicht aller Xempus-Beratungen mit Detail-Splitter."""

    navigate_to_panel = Signal(int)

    def __init__(self, api: ProvisionAPI):
        super().__init__()
        self._api = api
        self._all_data: List[Contract] = []
        self._employees: List[Employee] = []
        self._worker = None
        self._detail_worker = None
        self._setup_ui()
        QTimer.singleShot(100, self.refresh)

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 16)
        root.setSpacing(12)

        header = SectionHeader(texts.PROVISION_XEMPUS_TITLE)
        root.addWidget(header)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self._search = QLineEdit()
        self._search.setPlaceholderText(texts.PROVISION_SEARCH)
        self._search.setStyleSheet(get_search_field_style())
        self._search.setFixedWidth(260)
        self._search.textChanged.connect(self._apply_filters)
        toolbar.addWidget(self._search)

        self._filter_status = QComboBox()
        self._filter_status.addItem(texts.PROVISION_XEMPUS_FILTER_ALL, 'all')
        self._filter_status.addItem(texts.PROVISION_XEMPUS_FILTER_PAID, 'paid')
        self._filter_status.addItem(texts.PROVISION_XEMPUS_FILTER_OPEN, 'open')
        self._filter_status.addItem(texts.PROVISION_XEMPUS_FILTER_APPLIED, 'applied')
        self._filter_status.setFixedWidth(140)
        self._filter_status.currentIndexChanged.connect(self._apply_filters)
        toolbar.addWidget(self._filter_status)

        self._filter_berater = QComboBox()
        self._filter_berater.addItem(texts.PROVISION_POS_FILTER_ALL, 0)
        self._filter_berater.setFixedWidth(180)
        self._filter_berater.currentIndexChanged.connect(self._apply_filters)
        toolbar.addWidget(self._filter_berater)

        toolbar.addStretch()

        self._count_label = QLabel()
        self._count_label.setStyleSheet(f"color: {PRIMARY_500}; font-size: {FONT_SIZE_CAPTION};")
        toolbar.addWidget(self._count_label)

        root.addLayout(toolbar)

        self._splitter = QSplitter(Qt.Horizontal)

        self._model = XempusContractsModel()
        self._proxy = QSortFilterProxyModel()
        self._proxy.setSourceModel(self._model)
        self._proxy.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self._proxy.setFilterKeyColumn(-1)

        self._table = QTableView()
        self._table.setModel(self._proxy)
        self._table.setSelectionBehavior(QTableView.SelectRows)
        self._table.setSelectionMode(QTableView.SingleSelection)
        self._table.setAlternatingRowColors(True)
        self._table.setSortingEnabled(True)
        self._table.setStyleSheet(get_provision_table_style())
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self._table.setItemDelegateForColumn(
            XempusContractsModel.COL_STATUS,
            PillBadgeDelegate(PILL_COLORS, parent=self._table)
        )
        self._table.selectionModel().currentRowChanged.connect(self._on_row_selected)

        self._splitter.addWidget(self._table)

        self._detail_frame = QFrame()
        self._detail_frame.setFixedWidth(360)
        self._detail_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {BG_SECONDARY};
                border-left: 1px solid {BORDER_DEFAULT};
                border-radius: 0px;
            }}
        """)
        self._detail_layout = QVBoxLayout(self._detail_frame)
        self._detail_layout.setContentsMargins(16, 16, 16, 16)
        self._detail_layout.setSpacing(8)
        self._detail_placeholder = QLabel(texts.PROVISION_XEMPUS_DETAIL_TITLE)
        self._detail_placeholder.setStyleSheet(f"color: {PRIMARY_500}; font-size: {FONT_SIZE_BODY};")
        self._detail_placeholder.setAlignment(Qt.AlignCenter)
        self._detail_layout.addWidget(self._detail_placeholder)
        self._detail_layout.addStretch()

        self._splitter.addWidget(self._detail_frame)
        self._splitter.setStretchFactor(0, 3)
        self._splitter.setStretchFactor(1, 1)

        root.addWidget(self._splitter, 1)

        self._loading = ProvisionLoadingOverlay(self)
        self._loading.hide()

    def refresh(self):
        if self._worker and self._worker.isRunning():
            return
        self._loading.show()
        self._worker = XempusContractsLoadWorker(self._api, limit=5000)
        self._worker.finished.connect(self._on_data_loaded)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_data_loaded(self, contracts, employees):
        self._loading.hide()
        self._all_data = contracts if isinstance(contracts, list) else []
        self._employees = employees if isinstance(employees, list) else []

        old_berater = self._filter_berater.currentData()
        self._filter_berater.blockSignals(True)
        self._filter_berater.clear()
        self._filter_berater.addItem(texts.PROVISION_POS_FILTER_ALL, 0)
        for emp in sorted(self._employees, key=lambda e: e.name):
            if emp.is_active and emp.role in ('consulter', 'teamleiter'):
                self._filter_berater.addItem(emp.name, emp.id)
        if old_berater:
            idx = self._filter_berater.findData(old_berater)
            if idx >= 0:
                self._filter_berater.setCurrentIndex(idx)
        self._filter_berater.blockSignals(False)

        self._apply_filters()

    def _on_error(self, msg: str):
        self._loading.hide()
        logger.error(f"Xempus-Ladefehler: {msg}")

    def _apply_filters(self):
        status_filter = self._filter_status.currentData()
        berater_filter = self._filter_berater.currentData()
        search = self._search.text().strip().lower()

        filtered = self._all_data
        if status_filter == 'paid':
            filtered = [c for c in filtered if c.provision_count and c.provision_count > 0]
        elif status_filter == 'open':
            filtered = [c for c in filtered
                        if (not c.provision_count or c.provision_count == 0) and c.status != 'beantragt']
        elif status_filter == 'applied':
            filtered = [c for c in filtered if c.status == 'beantragt']

        if berater_filter:
            filtered = [c for c in filtered if c.berater_id == berater_filter]

        if search:
            filtered = [c for c in filtered if
                        search in (c.vsnr or '').lower() or
                        search in (c.versicherungsnehmer or '').lower() or
                        search in (c.versicherer or '').lower() or
                        search in (c.berater_name or '').lower() or
                        search in (c.sparte or '').lower()]

        self._model.set_data(filtered, self._employees)
        self._count_label.setText(texts.PROVISION_XEMPUS_COUNT.format(count=len(filtered)))

        if self._table.model().rowCount() > 0:
            self._table.resizeColumnsToContents()
            h = self._table.horizontalHeader()
            for col in range(self._model.columnCount()):
                if h.sectionSize(col) > 200:
                    h.resizeSection(col, 200)

    def _on_row_selected(self, current: QModelIndex, previous: QModelIndex):
        if not current.isValid():
            return
        source_idx = self._proxy.mapToSource(current)
        contract = self._model.get_contract(source_idx.row())
        if not contract:
            return
        self._show_detail(contract)

    def _show_detail(self, contract: Contract):
        while self._detail_layout.count():
            item = self._detail_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        title = QLabel(texts.PROVISION_XEMPUS_DETAIL_TITLE)
        title.setStyleSheet(f"font-weight: 700; font-size: 12pt; color: {PRIMARY_900};")
        self._detail_layout.addWidget(title)

        fields = [
            (texts.PROVISION_XEMPUS_COL_VSNR, contract.vsnr or ''),
            (texts.PROVISION_XEMPUS_COL_PERSON, contract.versicherungsnehmer or ''),
            (texts.PROVISION_XEMPUS_COL_VU, contract.versicherer or ''),
            (texts.PROVISION_XEMPUS_COL_SPARTE, contract.sparte or ''),
            (texts.PROVISION_XEMPUS_COL_BERATER, contract.berater_name or ''),
            (texts.PROVISION_XEMPUS_COL_BEITRAG, format_eur(contract.beitrag) if contract.beitrag else ''),
            (texts.PROVISION_XEMPUS_COL_BEGINN, self._format_date(contract.beginn)),
            (texts.PROVISION_XEMPUS_COL_STATUS, xempus_status_label(contract)),
        ]

        for label, value in fields:
            row = QHBoxLayout()
            lbl = QLabel(f"{label}:")
            lbl.setFixedWidth(110)
            lbl.setStyleSheet(f"color: {PRIMARY_500}; font-size: {FONT_SIZE_CAPTION};")
            val = QLabel(str(value))
            val.setStyleSheet(f"color: {PRIMARY_900}; font-size: {FONT_SIZE_BODY}; font-weight: 500;")
            val.setWordWrap(True)
            row.addWidget(lbl)
            row.addWidget(val, 1)
            self._detail_layout.addLayout(row)

        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background-color: {BORDER_DEFAULT}; margin: 8px 0;")
        self._detail_layout.addWidget(sep)

        prov_title = QLabel(texts.PROVISION_XEMPUS_DETAIL_VU_PROVS)
        prov_title.setStyleSheet(f"font-weight: 600; font-size: 11pt; color: {PRIMARY_900}; margin-top: 4px;")
        self._detail_layout.addWidget(prov_title)

        if contract.provision_count and contract.provision_count > 0:
            prov_sum = QLabel(f"{contract.provision_count}x = {format_eur(contract.provision_summe)}")
            prov_sum.setStyleSheet(f"color: {SUCCESS}; font-weight: 600; font-size: {FONT_SIZE_BODY};")
            self._detail_layout.addWidget(prov_sum)

            self._load_commissions_for(contract.vsnr)
        else:
            no_prov = QLabel(texts.PROVISION_XEMPUS_DETAIL_NO_PROVS)
            no_prov.setStyleSheet(f"color: {WARNING}; font-size: {FONT_SIZE_CAPTION};")
            self._detail_layout.addWidget(no_prov)

        self._detail_layout.addStretch()

    def _load_commissions_for(self, vsnr: str):
        if self._detail_worker and self._detail_worker.isRunning():
            return
        self._detail_worker = XempusDetailLoadWorker(self._api, vsnr)
        self._detail_worker.finished.connect(self._on_detail_loaded)
        self._detail_worker.start()

    def _on_detail_loaded(self, commissions):
        if not isinstance(commissions, list):
            return
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        container = QWidget()
        cl = QVBoxLayout(container)
        cl.setContentsMargins(0, 4, 0, 0)
        cl.setSpacing(4)

        for comm in commissions[:20]:
            datum = ''
            if comm.auszahlungsdatum:
                try:
                    from datetime import datetime
                    dt = datetime.strptime(comm.auszahlungsdatum[:10], '%Y-%m-%d')
                    datum = dt.strftime('%d.%m.%Y')
                except (ValueError, TypeError):
                    datum = comm.auszahlungsdatum or ''

            line = QLabel(f"{datum}  {comm.versicherer or ''}  {format_eur(comm.betrag)}")
            line.setStyleSheet(f"color: {PRIMARY_900}; font-size: {FONT_SIZE_CAPTION}; padding: 2px 0;")
            cl.addWidget(line)

        cl.addStretch()
        scroll.setWidget(container)

        idx = self._detail_layout.count() - 1
        self._detail_layout.insertWidget(idx, scroll, 1)

    @staticmethod
    def _format_date(val: Optional[str]) -> str:
        if not val:
            return ''
        try:
            from datetime import datetime
            dt = datetime.strptime(val[:10], '%Y-%m-%d')
            return dt.strftime('%d.%m.%Y')
        except (ValueError, TypeError):
            return val

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, '_loading'):
            self._loading.resize(self.size())
