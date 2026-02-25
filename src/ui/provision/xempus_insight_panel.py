"""
Xempus Insight Panel: Tabbed-Ansicht mit Arbeitgeber-TreeView,
Statistik-Dashboard, Import-Management und Status-Mapping.

Ersetzt den alten xempus_panel.py mit einer vollstaendigen
Verwaltungsoberflaeche fuer Xempus-Daten.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableView,
    QHeaderView, QSplitter, QFrame, QScrollArea, QTabWidget,
    QLineEdit, QPushButton, QSizePolicy, QFileDialog,
    QComboBox, QDialog, QDialogButtonBox, QFormLayout,
    QAbstractItemView,
)
from PySide6.QtCore import (
    Qt, Signal, QSortFilterProxyModel, QTimer, QModelIndex,
)
from PySide6.QtGui import QColor

from typing import List, Optional, Dict

from api.provision import ProvisionAPI
from api.xempus import XempusAPI
from api.client import APIError
from domain.xempus_models import (
    XempusEmployer, XempusTariff, XempusSubsidy, XempusEmployee,
    XempusConsultation, XempusImportBatch, XempusStatusMapping,
    XempusStats, XempusDiff,
)
from services.xempus_parser import parse_xempus_complete, prepare_sheets_for_upload
from ui.styles.tokens import (
    PRIMARY_100, PRIMARY_500, PRIMARY_900, ACCENT_500,
    BG_PRIMARY, BG_SECONDARY, BG_TERTIARY, BORDER_DEFAULT,
    SUCCESS, ERROR, WARNING,
    FONT_BODY, FONT_SIZE_BODY, FONT_SIZE_CAPTION,
    PILL_COLORS, get_provision_table_style,
)
from ui.provision.widgets import (
    PillBadgeDelegate, DonutChartWidget, FilterChipBar, SectionHeader,
    KpiCard, PaginationBar, ProvisionLoadingOverlay,
    format_eur, get_search_field_style, get_secondary_button_style,
)
from ui.provision.workers import (
    EmployerLoadWorker, EmployerDetailWorker, XempusStatsLoadWorker,
    XempusBatchesLoadWorker, XempusImportWorker, XempusDiffLoadWorker,
    StatusMappingLoadWorker,
)
from ui.provision.models import (
    EmployerTableModel, XempusBatchTableModel, StatusMappingModel, fmt_date,
)
from ui.provision.dialogs import DiffDialog
from i18n import de as texts
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# Tabs
# =============================================================================


class _EmployersTab(QWidget):
    """Arbeitgeber-Tabelle mit Lazy-Loading Detail-Panel."""

    def __init__(self, xempus_api: XempusAPI, parent=None):
        super().__init__(parent)
        self._api = xempus_api
        self._worker = None
        self._detail_worker = None
        self._setup_ui()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 8)
        root.setSpacing(8)

        toolbar = QHBoxLayout()
        self._search = QLineEdit()
        self._search.setPlaceholderText(texts.XEMPUS_EMPLOYER_SEARCH)
        self._search.setStyleSheet(get_search_field_style())
        self._search.setFixedWidth(280)
        self._search.textChanged.connect(self._on_search)
        toolbar.addWidget(self._search)
        toolbar.addStretch()
        self._count_label = QLabel()
        self._count_label.setStyleSheet(f"color: {PRIMARY_500}; font-size: {FONT_SIZE_CAPTION};")
        toolbar.addWidget(self._count_label)
        root.addLayout(toolbar)

        self._splitter = QSplitter(Qt.Horizontal)

        self._model = EmployerTableModel()
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
        self._table.selectionModel().currentRowChanged.connect(self._on_row_selected)
        self._splitter.addWidget(self._table)

        self._detail_frame = QFrame()
        self._detail_frame.setFixedWidth(380)
        self._detail_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {BG_SECONDARY};
                border-left: 1px solid {BORDER_DEFAULT};
            }}
        """)
        self._detail_layout = QVBoxLayout(self._detail_frame)
        self._detail_layout.setContentsMargins(16, 16, 16, 16)
        self._detail_layout.setSpacing(8)
        placeholder = QLabel(texts.XEMPUS_EMPLOYER_DETAIL_TITLE)
        placeholder.setStyleSheet(f"color: {PRIMARY_500}; font-size: {FONT_SIZE_BODY};")
        placeholder.setAlignment(Qt.AlignCenter)
        self._detail_layout.addWidget(placeholder)
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
        self._worker = EmployerLoadWorker(self._api)
        self._worker.finished.connect(self._on_loaded)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_loaded(self, employers: list):
        self._loading.hide()
        self._model.set_data(employers)
        self._count_label.setText(texts.XEMPUS_EMPLOYER_COUNT.format(count=len(employers)))
        if self._table.model().rowCount() > 0:
            self._table.resizeColumnsToContents()
            h = self._table.horizontalHeader()
            for col in range(self._model.columnCount()):
                if h.sectionSize(col) > 250:
                    h.resizeSection(col, 250)

    def _on_error(self, msg: str):
        self._loading.hide()
        logger.error(f"Employer load error: {msg}")

    def _on_search(self, text: str):
        self._proxy.setFilterFixedString(text)

    def _on_row_selected(self, current: QModelIndex, previous: QModelIndex):
        if not current.isValid():
            return
        source_idx = self._proxy.mapToSource(current)
        employer = self._model.get_employer(source_idx.row())
        if not employer:
            return
        self._load_detail(employer.id)

    def _load_detail(self, employer_id: str):
        if self._detail_worker and self._detail_worker.isRunning():
            return
        self._detail_worker = EmployerDetailWorker(self._api, employer_id)
        self._detail_worker.finished.connect(self._show_detail)
        self._detail_worker.error.connect(lambda msg: logger.error(f"Detail: {msg}"))
        self._detail_worker.start()

    def _show_detail(self, detail: Optional[Dict]):
        while self._detail_layout.count():
            item = self._detail_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                while item.layout().count():
                    sub = item.layout().takeAt(0)
                    if sub.widget():
                        sub.widget().deleteLater()

        if not detail:
            return

        employer: XempusEmployer = detail['employer']
        tariffs: list = detail.get('tariffs', [])
        subsidies: list = detail.get('subsidies', [])

        title = QLabel(employer.name)
        title.setStyleSheet(f"font-weight: 700; font-size: 12pt; color: {PRIMARY_900};")
        title.setWordWrap(True)
        self._detail_layout.addWidget(title)

        fields = [
            (texts.XEMPUS_EMPLOYER_DETAIL_ID, employer.id),
            (texts.XEMPUS_EMPLOYER_DETAIL_ADDRESS,
             ', '.join(p for p in [employer.street, f"{employer.plz} {employer.city}".strip()] if p)),
            (texts.XEMPUS_EMPLOYER_COL_EMPLOYEES, str(employer.employee_count)),
        ]
        for label_text, value in fields:
            if not value:
                continue
            row = QHBoxLayout()
            lbl = QLabel(f"{label_text}:")
            lbl.setFixedWidth(100)
            lbl.setStyleSheet(f"color: {PRIMARY_500}; font-size: {FONT_SIZE_CAPTION};")
            val = QLabel(str(value))
            val.setStyleSheet(f"color: {PRIMARY_900}; font-size: {FONT_SIZE_BODY};")
            val.setWordWrap(True)
            row.addWidget(lbl)
            row.addWidget(val, 1)
            self._detail_layout.addLayout(row)

        if tariffs:
            sep = QFrame()
            sep.setFixedHeight(1)
            sep.setStyleSheet(f"background-color: {BORDER_DEFAULT};")
            self._detail_layout.addWidget(sep)

            tariff_title = QLabel(texts.XEMPUS_EMPLOYER_DETAIL_TARIFFS)
            tariff_title.setStyleSheet(f"font-weight: 600; font-size: 10pt; color: {PRIMARY_900};")
            self._detail_layout.addWidget(tariff_title)

            for t in tariffs[:10]:
                info = f"{t.versicherer or ''} – {t.tarif or ''}"
                lbl = QLabel(info.strip(' –'))
                lbl.setStyleSheet(f"color: {PRIMARY_900}; font-size: {FONT_SIZE_CAPTION}; padding: 1px 0;")
                lbl.setWordWrap(True)
                self._detail_layout.addWidget(lbl)

        if subsidies:
            sep = QFrame()
            sep.setFixedHeight(1)
            sep.setStyleSheet(f"background-color: {BORDER_DEFAULT};")
            self._detail_layout.addWidget(sep)

            sub_title = QLabel(texts.XEMPUS_EMPLOYER_DETAIL_SUBSIDIES)
            sub_title.setStyleSheet(f"font-weight: 600; font-size: 10pt; color: {PRIMARY_900};")
            self._detail_layout.addWidget(sub_title)

            for s in subsidies[:10]:
                info = s.bezeichnung or '–'
                if s.fester_zuschuss is not None:
                    info += f"  ({format_eur(s.fester_zuschuss)})"
                lbl = QLabel(info)
                lbl.setStyleSheet(f"color: {PRIMARY_900}; font-size: {FONT_SIZE_CAPTION}; padding: 1px 0;")
                lbl.setWordWrap(True)
                self._detail_layout.addWidget(lbl)

        self._detail_layout.addStretch()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, '_loading'):
            self._loading.resize(self.size())


class _StatsTab(QWidget):
    """KPI-Dashboard mit DonutCharts und Arbeitgeber-Statistiken."""

    def __init__(self, xempus_api: XempusAPI, parent=None):
        super().__init__(parent)
        self._api = xempus_api
        self._worker = None
        self._setup_ui()

    def _setup_ui(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        container = QWidget()
        self._content = QVBoxLayout(container)
        self._content.setContentsMargins(16, 12, 16, 16)
        self._content.setSpacing(16)

        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(12)

        self._kpi_employers = KpiCard(texts.XEMPUS_STATS_KPI_EMPLOYERS, accent_color=PRIMARY_900)
        self._kpi_employers.set_value("–")
        kpi_row.addWidget(self._kpi_employers)

        self._kpi_employees = KpiCard(texts.XEMPUS_STATS_KPI_EMPLOYEES, accent_color='#3f51b5')
        self._kpi_employees.set_value("–")
        kpi_row.addWidget(self._kpi_employees)

        self._kpi_consultations = KpiCard(texts.XEMPUS_STATS_KPI_CONSULTATIONS, accent_color=ACCENT_500)
        self._kpi_consultations.set_value("–")
        kpi_row.addWidget(self._kpi_consultations)

        self._kpi_conversion = KpiCard(texts.XEMPUS_STATS_KPI_CONVERSION, accent_color=SUCCESS)
        self._kpi_conversion.set_value("–")
        self._donut = DonutChartWidget(percent=0, size=80, thickness=10)
        self._kpi_conversion.add_extra_widget(self._donut)
        kpi_row.addWidget(self._kpi_conversion)

        self._content.addLayout(kpi_row)

        chart_title = QLabel(texts.XEMPUS_STATS_CHART_STATUS)
        chart_title.setStyleSheet(f"font-weight: 600; font-size: 11pt; color: {PRIMARY_900};")
        self._content.addWidget(chart_title)

        self._status_bar = QHBoxLayout()
        self._content.addLayout(self._status_bar)

        per_emp_title = QLabel(texts.XEMPUS_STATS_PER_EMPLOYER)
        per_emp_title.setStyleSheet(f"font-weight: 600; font-size: 11pt; color: {PRIMARY_900}; margin-top: 8px;")
        self._content.addWidget(per_emp_title)

        self._per_employer_container = QVBoxLayout()
        self._content.addLayout(self._per_employer_container)

        self._content.addStretch()
        scroll.setWidget(container)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        self._loading = ProvisionLoadingOverlay(self)
        self._loading.hide()

    def refresh(self):
        if self._worker and self._worker.isRunning():
            return
        self._loading.show()
        self._worker = XempusStatsLoadWorker(self._api)
        self._worker.finished.connect(self._on_loaded)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_loaded(self, stats: XempusStats):
        self._loading.hide()
        self._kpi_employers.set_value(str(stats.total_employers))
        self._kpi_employees.set_value(str(stats.total_employees))
        self._kpi_consultations.set_value(str(stats.total_consultations))

        if stats.unmapped_statuses:
            for um in stats.unmapped_statuses:
                logger.warning(f"Unmapped Xempus status: '{um.get('raw_status')}' ({um.get('count')} Beratungen)")

        logger.info(f"Xempus Stats: abschluss_quote={stats.abschluss_quote}, "
                     f"ansprache_quote={stats.ansprache_quote}, erfolgs_quote={stats.erfolgs_quote}, "
                     f"status_dist={stats.status_distribution}")

        rate = stats.abschluss_quote
        self._kpi_conversion.set_value(f"{rate:.1f}%")
        self._donut.set_percent(rate)

        while self._status_bar.count():
            item = self._status_bar.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        status_colors = {
            'converted': SUCCESS, 'open': WARNING, 'applied': '#5b8def',
            'rejected': ERROR, 'not_desired': '#9e9e9e', 'other': PRIMARY_500,
        }
        for entry in stats.status_distribution:
            cat = entry.get('category', 'other')
            count = int(entry.get('count', 0))
            label_text = entry.get('display_label', cat)
            color = entry.get('color', status_colors.get(cat, PRIMARY_500))

            chip = QLabel(f"  {label_text}: {count}  ")
            chip.setStyleSheet(f"""
                background-color: {color}20;
                color: {color};
                border: 1px solid {color}40;
                border-radius: 10px;
                padding: 4px 10px;
                font-size: {FONT_SIZE_CAPTION};
                font-weight: 500;
            """)
            self._status_bar.addWidget(chip)
        self._status_bar.addStretch()

        while self._per_employer_container.count():
            item = self._per_employer_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not stats.per_employer:
            lbl = QLabel(texts.XEMPUS_STATS_PER_EMPLOYER_EMPTY)
            lbl.setStyleSheet(f"color: {PRIMARY_500}; font-size: {FONT_SIZE_CAPTION};")
            self._per_employer_container.addWidget(lbl)
        else:
            for entry in stats.per_employer[:20]:
                name = entry.get('name', '–')
                emp_count = int(entry.get('employees', 0))
                cons_count = int(entry.get('consultations', 0))
                conv_rate = float(entry.get('conversion_rate', 0))

                row = QHBoxLayout()
                row.setSpacing(8)
                name_lbl = QLabel(name)
                name_lbl.setFixedWidth(200)
                name_lbl.setStyleSheet(f"color: {PRIMARY_900}; font-size: {FONT_SIZE_BODY}; font-weight: 500;")
                row.addWidget(name_lbl)

                stats_lbl = QLabel(f"{emp_count} MA  |  {cons_count} Berat.  |  {conv_rate:.0f}%")
                stats_lbl.setStyleSheet(f"color: {PRIMARY_500}; font-size: {FONT_SIZE_CAPTION};")
                row.addWidget(stats_lbl)
                row.addStretch()
                self._per_employer_container.addLayout(row)

    def _on_error(self, msg: str):
        self._loading.hide()
        logger.error(f"Stats load error: {msg}")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, '_loading'):
            self._loading.resize(self.size())


class _ImportTab(QWidget):
    """Import-Panel mit Datei-Upload und Batch-Historie."""

    import_completed = Signal()

    def __init__(self, xempus_api: XempusAPI, parent=None):
        super().__init__(parent)
        self._api = xempus_api
        self._import_worker = None
        self._batches_worker = None
        self._diff_worker = None
        self._toast_manager = None
        self._setup_ui()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 8)
        root.setSpacing(12)

        import_frame = QFrame()
        import_frame.setStyleSheet(f"""
            QFrame {{
                background-color: white;
                border: 1px solid {BORDER_DEFAULT};
                border-radius: 8px;
                border-top: 3px solid {ACCENT_500};
            }}
        """)
        import_layout = QVBoxLayout(import_frame)
        import_layout.setContentsMargins(20, 16, 20, 16)
        import_layout.setSpacing(8)

        title = QLabel(texts.XEMPUS_IMPORT_TITLE)
        title.setStyleSheet(f"font-weight: 700; font-size: 12pt; color: {PRIMARY_900};")
        import_layout.addWidget(title)

        desc = QLabel(texts.XEMPUS_IMPORT_DESC)
        desc.setStyleSheet(f"color: {PRIMARY_500}; font-size: {FONT_SIZE_CAPTION};")
        import_layout.addWidget(desc)

        btn_row = QHBoxLayout()
        self._import_btn = QPushButton(texts.XEMPUS_IMPORT_SELECT_FILE)
        self._import_btn.setStyleSheet(get_secondary_button_style())
        self._import_btn.setCursor(Qt.PointingHandCursor)
        self._import_btn.clicked.connect(self._select_file)
        btn_row.addWidget(self._import_btn)

        self._progress_label = QLabel()
        self._progress_label.setStyleSheet(f"color: {ACCENT_500}; font-size: {FONT_SIZE_CAPTION};")
        btn_row.addWidget(self._progress_label)
        btn_row.addStretch()
        import_layout.addLayout(btn_row)

        root.addWidget(import_frame)

        history_title = QLabel(texts.XEMPUS_IMPORT_BATCH_HISTORY)
        history_title.setStyleSheet(f"font-weight: 600; font-size: 11pt; color: {PRIMARY_900};")
        root.addWidget(history_title)

        self._batch_model = XempusBatchTableModel()
        self._batch_table = QTableView()
        self._batch_table.setModel(self._batch_model)
        self._batch_table.setSelectionBehavior(QTableView.SelectRows)
        self._batch_table.setSelectionMode(QTableView.SingleSelection)
        self._batch_table.setAlternatingRowColors(True)
        self._batch_table.setSortingEnabled(True)
        self._batch_table.setStyleSheet(get_provision_table_style())
        self._batch_table.verticalHeader().setVisible(False)
        self._batch_table.horizontalHeader().setStretchLastSection(True)
        phase_colors = {
            'raw_ingest': {'bg': '#fff3e0', 'text': '#e65100'},
            'normalize': {'bg': '#e3f2fd', 'text': '#1565c0'},
            'snapshot_update': {'bg': '#e8f5e9', 'text': '#2e7d32'},
            'complete': {'bg': '#e8f5e9', 'text': '#1b5e20'},
        }
        self._batch_table.setItemDelegateForColumn(
            XempusBatchTableModel.COL_PHASE,
            PillBadgeDelegate(phase_colors, parent=self._batch_table)
        )
        self._batch_table.doubleClicked.connect(self._on_batch_double_click)
        root.addWidget(self._batch_table, 1)

        self._loading = ProvisionLoadingOverlay(self)
        self._loading.hide()

    def refresh(self):
        if self._batches_worker and self._batches_worker.isRunning():
            return
        self._batches_worker = XempusBatchesLoadWorker(self._api)
        self._batches_worker.finished.connect(self._on_batches_loaded)
        self._batches_worker.error.connect(lambda m: logger.error(f"Batches: {m}"))
        self._batches_worker.start()

    def _on_batches_loaded(self, batches: list):
        self._batch_model.set_data(batches)
        if self._batch_table.model().rowCount() > 0:
            self._batch_table.resizeColumnsToContents()

    def _select_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, texts.XEMPUS_IMPORT_SELECT_FILE,
            "", "Excel (*.xlsx)")
        if not path:
            return
        self._start_import(path)

    def _start_import(self, filepath: str):
        if self._import_worker and self._import_worker.isRunning():
            return

        import os
        filename = os.path.basename(filepath)

        self._progress_label.setText(texts.XEMPUS_IMPORT_RUNNING)
        self._import_btn.setEnabled(False)

        try:
            result = parse_xempus_complete(filepath)
            sheets = prepare_sheets_for_upload(result)
        except Exception as e:
            self._progress_label.setText(texts.XEMPUS_IMPORT_ERROR.format(error=str(e)))
            self._import_btn.setEnabled(True)
            return

        if not sheets:
            self._progress_label.setText(texts.XEMPUS_IMPORT_ERROR.format(error="Keine Daten"))
            self._import_btn.setEnabled(True)
            return

        self._import_worker = XempusImportWorker(self._api, filename, sheets)
        self._import_worker.phase_changed.connect(self._on_phase_changed)
        self._import_worker.finished.connect(self._on_import_finished)
        self._import_worker.error.connect(self._on_import_error)
        self._import_worker.start()

    def _on_phase_changed(self, phase: int, desc: str):
        self._progress_label.setText(texts.XEMPUS_IMPORT_PROGRESS.format(phase=phase, desc=desc))

    def _on_import_finished(self, result):
        self._import_btn.setEnabled(True)
        rc = result.get('record_counts', {}) if isinstance(result, dict) else {}
        employers = rc.get('employers', 0)
        employees = rc.get('employees', 0)
        consultations = rc.get('consultations', 0)

        sync = result.get('sync', {}) if isinstance(result, dict) else {}
        match = result.get('match', {}) if isinstance(result, dict) else {}
        synced = sync.get('synced', 0)
        matched = match.get('matched', 0)

        msg = texts.XEMPUS_IMPORT_SUCCESS.format(
            employers=employers, employees=employees, consultations=consultations)
        if synced or matched:
            msg += '\n' + texts.XEMPUS_SYNC_RESULT.format(synced=synced, matched=matched)
        self._progress_label.setText(msg)
        self.refresh()
        self.import_completed.emit()

    def _on_import_error(self, msg: str):
        self._import_btn.setEnabled(True)
        self._progress_label.setText(texts.XEMPUS_IMPORT_ERROR.format(error=msg))
        logger.error(f"Xempus import error: {msg}")

    def _on_batch_double_click(self, index: QModelIndex):
        batch = self._batch_model.get_batch(index.row())
        if not batch or batch.import_phase != 'complete':
            return
        self._show_diff(batch.id)

    def _show_diff(self, batch_id: int):
        if self._diff_worker and self._diff_worker.isRunning():
            return
        self._diff_worker = XempusDiffLoadWorker(self._api, batch_id)
        self._diff_worker.finished.connect(self._show_diff_dialog)
        self._diff_worker.error.connect(lambda m: logger.error(f"Diff: {m}"))
        self._diff_worker.start()

    def _show_diff_dialog(self, diff: Optional[XempusDiff]):
        if not diff:
            return
        dlg = DiffDialog(diff, self)
        dlg.exec()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, '_loading'):
            self._loading.resize(self.size())


class _StatusMappingTab(QWidget):
    """Status-Mapping-Verwaltung."""

    def __init__(self, xempus_api: XempusAPI, parent=None):
        super().__init__(parent)
        self._api = xempus_api
        self._worker = None
        self._setup_ui()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 8)
        root.setSpacing(8)

        toolbar = QHBoxLayout()
        title = QLabel(texts.XEMPUS_STATUS_MAP_TITLE)
        title.setStyleSheet(f"font-weight: 600; font-size: 11pt; color: {PRIMARY_900};")
        toolbar.addWidget(title)
        toolbar.addStretch()

        desc = QLabel(texts.XEMPUS_STATUS_MAP_DESC)
        desc.setStyleSheet(f"color: {PRIMARY_500}; font-size: {FONT_SIZE_CAPTION};")
        toolbar.addWidget(desc)
        root.addLayout(toolbar)

        self._sm_model = StatusMappingModel()
        self._sm_table = QTableView()
        self._sm_table.setModel(self._sm_model)
        self._sm_table.setSelectionBehavior(QTableView.SelectRows)
        self._sm_table.setSelectionMode(QTableView.SingleSelection)
        self._sm_table.setAlternatingRowColors(True)
        self._sm_table.setStyleSheet(get_provision_table_style())
        self._sm_table.verticalHeader().setVisible(False)
        self._sm_table.horizontalHeader().setStretchLastSection(True)
        root.addWidget(self._sm_table, 1)

        self._loading = ProvisionLoadingOverlay(self)
        self._loading.hide()

    def refresh(self):
        if self._worker and self._worker.isRunning():
            return
        self._loading.show()
        self._worker = StatusMappingLoadWorker(self._api)
        self._worker.finished.connect(self._on_loaded)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_loaded(self, mappings: list):
        self._loading.hide()
        self._sm_model.set_data(mappings)
        if self._sm_table.model().rowCount() > 0:
            self._sm_table.resizeColumnsToContents()

    def _on_error(self, msg: str):
        self._loading.hide()
        logger.error(f"Status mapping load error: {msg}")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, '_loading'):
            self._loading.resize(self.size())


# =============================================================================
# Diff Dialog
# =============================================================================


# =============================================================================
# Main Panel
# =============================================================================


class XempusInsightPanel(QWidget):
    """Xempus Insight Engine: Tabbed-Panel mit Arbeitgebern, Stats, Import, Status-Mapping."""

    navigate_to_panel = Signal(int)

    def __init__(self, provision_api: ProvisionAPI):
        super().__init__()
        self._provision_api = provision_api
        self._xempus_api = XempusAPI(provision_api.client)
        self._tabs_initialized = set()
        self._toast_manager = None
        self._setup_ui()
        QTimer.singleShot(100, self._init_first_tab)

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 16)
        root.setSpacing(12)

        header = SectionHeader(texts.XEMPUS_NAV_TITLE)
        root.addWidget(header)

        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: 1px solid {BORDER_DEFAULT};
                border-radius: 4px;
                background-color: {BG_PRIMARY};
            }}
            QTabBar::tab {{
                padding: 8px 16px;
                font-family: {FONT_BODY};
                font-size: {FONT_SIZE_BODY};
                color: {PRIMARY_500};
                border: none;
                border-bottom: 2px solid transparent;
            }}
            QTabBar::tab:selected {{
                color: {PRIMARY_900};
                border-bottom: 2px solid {ACCENT_500};
                font-weight: 600;
            }}
            QTabBar::tab:hover {{
                color: {PRIMARY_900};
                background-color: {BG_SECONDARY};
            }}
        """)

        self._employers_tab = _EmployersTab(self._xempus_api)
        self._tabs.addTab(self._employers_tab, texts.XEMPUS_TAB_EMPLOYERS)

        self._stats_tab = _StatsTab(self._xempus_api)
        self._tabs.addTab(self._stats_tab, texts.XEMPUS_TAB_STATS)

        self._import_tab = _ImportTab(self._xempus_api)
        self._import_tab.import_completed.connect(self._on_import_completed)
        self._tabs.addTab(self._import_tab, texts.XEMPUS_TAB_IMPORT)

        self._status_map_tab = _StatusMappingTab(self._xempus_api)
        self._tabs.addTab(self._status_map_tab, texts.XEMPUS_TAB_STATUS_MAP)

        self._tabs.currentChanged.connect(self._on_tab_changed)
        root.addWidget(self._tabs, 1)

    def _init_first_tab(self):
        self._ensure_tab_loaded(0)

    def _on_tab_changed(self, index: int):
        self._ensure_tab_loaded(index)

    def _ensure_tab_loaded(self, index: int):
        if index in self._tabs_initialized:
            return
        self._tabs_initialized.add(index)
        tab = self._tabs.widget(index)
        if hasattr(tab, 'refresh'):
            tab.refresh()

    def _on_import_completed(self):
        self._tabs_initialized.discard(0)
        self._tabs_initialized.discard(1)
        if self._tabs.currentIndex() == 0:
            self._employers_tab.refresh()
        elif self._tabs.currentIndex() == 1:
            self._stats_tab.refresh()

    def refresh(self):
        """Alle geladenen Tabs neu laden."""
        for idx in list(self._tabs_initialized):
            tab = self._tabs.widget(idx)
            if hasattr(tab, 'refresh'):
                tab.refresh()
