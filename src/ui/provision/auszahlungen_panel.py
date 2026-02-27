"""
Auszahlungen & Reports-Panel: Monatsabrechnungen, Pruefberichte, Exporte.

Ersetzt: billing_panel.py
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableView,
    QHeaderView, QSplitter, QFrame, QScrollArea, QComboBox,
    QPushButton, QFileDialog, QMenu, QMessageBox,
)
from PySide6.QtCore import (
    Qt, Signal, QTimer, QPoint, QModelIndex,
)
from PySide6.QtGui import QColor
from typing import List, Optional
from datetime import datetime
import calendar
import csv
import os

from api.provision import ProvisionAPI
from domain.provision.entities import BeraterAbrechnung
from ui.styles.tokens import (
    PRIMARY_100, PRIMARY_500, PRIMARY_900, ACCENT_500,
    BG_PRIMARY, BG_SECONDARY, BORDER_DEFAULT,
    SUCCESS, ERROR, WARNING,
    FONT_BODY, FONT_SIZE_BODY, FONT_SIZE_CAPTION,
    PILL_COLORS, ROLE_BADGE_COLORS,
    get_provision_table_style,
)
from ui.provision.widgets import (
    SectionHeader, PillBadgeDelegate, StatementCard,
    PaginationBar, ThreeDotMenuDelegate, ProvisionLoadingOverlay,
    format_eur, get_secondary_button_style, get_combo_style,
)
from ui.provision.workers import AuszahlungenLoadWorker, AuszahlungenPositionenWorker
from ui.provision.models import AuszahlungenModel, STATUS_LABELS, STATUS_PILL_MAP
from i18n import de as texts
import logging

logger = logging.getLogger(__name__)


class AuszahlungenPanel(QWidget):
    """Auszahlungen & Reports mit Statement-Detail und CSV-Export.

    Implementiert IPayoutsView fuer den PayoutsPresenter.
    """

    navigate_to_panel = Signal(int)

    def __init__(self, api: ProvisionAPI = None):
        super().__init__()
        self._api = api
        self._presenter = None
        self._worker = None
        self._toast_manager = None
        self._setup_ui()
        if api:
            QTimer.singleShot(100, self._load_data)

    @property
    def _backend(self):
        return self._presenter or self._api

    def set_presenter(self, presenter) -> None:
        """Verbindet dieses Panel mit dem PayoutsPresenter."""
        self._presenter = presenter
        presenter.set_view(self)
        self._load_data()

    # ── IPayoutsView ──

    def show_abrechnungen(self, abrechnungen: list) -> None:
        """View-Interface: Abrechnungen anzeigen."""
        self._model.set_data(abrechnungen)

    def show_loading(self, loading: bool) -> None:
        """View-Interface: Ladezustand."""
        overlay = getattr(self, '_loading_overlay', None)
        if overlay:
            overlay.setVisible(loading)

    def show_error(self, message: str) -> None:
        """View-Interface: Fehler anzeigen."""
        logger.error(f"Auszahlungen-Fehler: {message}")

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Header
        header_row = QHBoxLayout()
        header = SectionHeader(texts.PROVISION_PAY_TITLE, texts.PROVISION_PAY_DESC)
        header_row.addWidget(header)
        header_row.addStretch()

        # Monat
        header_row.addWidget(QLabel(texts.PROVISION_DASH_MONAT))
        self._monat_combo = QComboBox()
        self._monat_combo.setFixedWidth(150)
        self._monat_combo.setStyleSheet(get_combo_style())
        now = datetime.now()
        for i in range(12):
            m = now.month - i
            y = now.year
            if m <= 0:
                m += 12
                y -= 1
            val = f"{y}-{m:02d}"
            self._monat_combo.addItem(f"{m:02d}/{y}", val)
        self._monat_combo.currentIndexChanged.connect(self._load_data)
        header_row.addWidget(self._monat_combo)
        layout.addLayout(header_row)

        # Toolbar
        toolbar = QHBoxLayout()

        gen_btn = QPushButton(texts.PROVISION_PAY_GENERATE)
        gen_btn.setStyleSheet(f"""
            QPushButton {{ background-color: {ACCENT_500}; color: white; border: none;
                border-radius: 6px; padding: 8px 16px; font-weight: 500; }}
            QPushButton:hover {{ background-color: #e88a2d; }}
        """)
        gen_btn.clicked.connect(self._generate)
        toolbar.addWidget(gen_btn)

        csv_btn = QPushButton(texts.PROVISION_PAY_EXPORT_CSV)
        csv_btn.setStyleSheet(get_secondary_button_style())
        csv_btn.clicked.connect(self._export_csv)
        toolbar.addWidget(csv_btn)

        xlsx_btn = QPushButton(texts.PROVISION_PAY_EXPORT_EXCEL)
        xlsx_btn.setStyleSheet(get_secondary_button_style())
        xlsx_btn.clicked.connect(self._export_xlsx)
        toolbar.addWidget(xlsx_btn)

        toolbar.addStretch()
        layout.addLayout(toolbar)

        # Splitter: Tabelle + Detail
        self._splitter = QSplitter(Qt.Horizontal)

        # Tabelle
        table_w = QWidget()
        table_l = QVBoxLayout(table_w)
        table_l.setContentsMargins(0, 0, 0, 0)

        self._model = AuszahlungenModel()
        self._table = QTableView()
        self._table.setModel(self._model)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QTableView.SelectRows)
        self._table.setSelectionMode(QTableView.SingleSelection)
        self._table.verticalHeader().setVisible(False)
        self._table.verticalHeader().setDefaultSectionSize(52)
        self._table.horizontalHeader().setStretchLastSection(False)
        self._table.setStyleSheet(get_provision_table_style())
        self._table.setMinimumHeight(350)
        self._table.selectionModel().selectionChanged.connect(self._on_selection)

        # Delegates
        role_del = PillBadgeDelegate(ROLE_BADGE_COLORS, label_map={
            'consulter': texts.PROVISION_EMP_ROLE_CONSULTER,
            'teamleiter': texts.PROVISION_EMP_ROLE_TEAMLEITER,
            'backoffice': texts.PROVISION_EMP_ROLE_BACKOFFICE,
        })
        self._table.setItemDelegateForColumn(self._model.COL_ROLE, role_del)
        self._role_del = role_del

        status_del = PillBadgeDelegate(PILL_COLORS, label_map={
            'entwurf': texts.PROVISION_STATUS_ENTWURF,
            'geprueft': texts.PROVISION_STATUS_GEPRUEFT,
            'freigegeben': texts.PROVISION_STATUS_FREIGEGEBEN,
            'ausgezahlt': texts.PROVISION_STATUS_AUSGEZAHLT,
        })
        self._table.setItemDelegateForColumn(self._model.COL_STATUS, status_del)
        self._status_del = status_del

        menu_del = ThreeDotMenuDelegate(self._build_menu)
        self._table.setItemDelegateForColumn(self._model.COL_MENU, menu_del)
        self._menu_del = menu_del

        table_l.addWidget(self._table)

        self._pagination = PaginationBar(page_size=25)
        self._pagination.page_changed.connect(self._on_page_changed)
        table_l.addWidget(self._pagination)

        self._splitter.addWidget(table_w)

        # Detail: StatementCard
        self._detail = self._create_detail()
        self._detail.setVisible(False)
        self._splitter.addWidget(self._detail)
        self._splitter.setStretchFactor(0, 3)
        self._splitter.setStretchFactor(1, 1)

        layout.addWidget(self._splitter)

        self._status = QLabel("")
        self._status.setStyleSheet(f"color: {ERROR}; font-size: {FONT_SIZE_CAPTION};")
        layout.addWidget(self._status)
        self._loading_overlay = ProvisionLoadingOverlay(self)

    def _create_detail(self) -> QFrame:
        frame = QFrame()
        frame.setMinimumWidth(300)
        frame.setMaximumWidth(400)
        frame.setStyleSheet(f"background: white; border: 1.5px solid #b0c4d8; border-radius: 8px;")

        outer = QVBoxLayout(frame)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(12)

        close_row = QHBoxLayout()
        close_row.addStretch()
        close_btn = QPushButton("\u2715")
        close_btn.setFixedSize(28, 28)
        close_btn.setStyleSheet(f"QPushButton {{ border: none; color: {PRIMARY_500}; font-size: 14pt; background: transparent; }}")
        close_btn.clicked.connect(lambda: self._detail.setVisible(False))
        close_row.addWidget(close_btn)
        outer.addLayout(close_row)

        lbl = QLabel(texts.PROVISION_PAY_DETAIL_OVERVIEW)
        lbl.setStyleSheet(f"font-weight: 600; font-size: 11pt; color: {PRIMARY_900};")
        outer.addWidget(lbl)

        self._statement = StatementCard()
        outer.addWidget(self._statement)

        self._det_name = QLabel("")
        self._det_name.setStyleSheet(f"color: {PRIMARY_900}; font-size: 13pt; font-weight: 600;")
        outer.insertWidget(1, self._det_name)

        # Positionsliste
        pos_lbl = QLabel(texts.PROVISION_PAY_DETAIL_POSITIONS)
        pos_lbl.setStyleSheet(f"font-weight: 600; font-size: 11pt; color: {PRIMARY_900}; margin-top: 8px;")
        outer.addWidget(pos_lbl)

        self._pos_scroll = QScrollArea()
        self._pos_scroll.setWidgetResizable(True)
        self._pos_scroll.setMaximumHeight(200)
        self._pos_scroll.setStyleSheet("QScrollArea { border: none; }")
        self._pos_container = QWidget()
        self._pos_layout = QVBoxLayout(self._pos_container)
        self._pos_layout.setContentsMargins(0, 0, 0, 0)
        self._pos_layout.setSpacing(4)
        self._pos_scroll.setWidget(self._pos_container)
        outer.addWidget(self._pos_scroll)

        outer.addStretch()
        return frame

    def _build_menu(self, index: QModelIndex) -> Optional[QMenu]:
        item = self._model.get_item(index.row())
        if not item:
            return None
        menu = QMenu(self)
        menu.addAction(texts.PROVISION_MENU_DETAILS, lambda: self._show_detail(item))
        status_menu = menu.addMenu(texts.PROVISION_MENU_STATUS)
        for s_key, s_label in STATUS_LABELS.items():
            if s_key != item.status:
                status_menu.addAction(s_label, lambda sid=item.id, sk=s_key: self._change_status(sid, sk))
        return menu

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._loading_overlay.setGeometry(self.rect())

    def refresh(self):
        self._load_data()

    def _load_data(self):
        monat = self._monat_combo.currentData() or datetime.now().strftime('%Y-%m')
        self._status.setText("")
        self._loading_overlay.setGeometry(self.rect())
        self._loading_overlay.setVisible(True)

        if self._presenter:
            self._presenter.load_abrechnungen(monat)
            return

        if self._worker and self._worker.isRunning():
            return
        self._worker = AuszahlungenLoadWorker(self._backend, monat)
        self._worker.finished.connect(self._on_loaded)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_loaded(self, data: List[BeraterAbrechnung]):
        self._loading_overlay.setVisible(False)
        self._all_data = data
        self._pagination.set_total(len(data))
        self._paginate()
        self._resize_columns()
        self._status.setText("")

    def _on_page_changed(self, page: int):
        self._paginate()

    def _paginate(self):
        data = getattr(self, '_all_data', [])
        page = self._pagination.current_page
        ps = self._pagination._page_size
        start = page * ps
        end = start + ps
        self._model.set_data(data[start:end])

    def _on_error(self, msg: str):
        self._loading_overlay.setVisible(False)
        self._status.setText(texts.PROVISION_DASH_ERROR)
        logger.error(f"Auszahlungen-Ladefehler: {msg}")

    def _resize_columns(self):
        h = self._table.horizontalHeader()
        for i in range(self._model.columnCount()):
            if i == self._model.COL_MENU:
                h.setSectionResizeMode(i, QHeaderView.Fixed)
                self._table.setColumnWidth(i, 48)
            elif i == self._model.COL_STATUS:
                h.setSectionResizeMode(i, QHeaderView.Fixed)
                self._table.setColumnWidth(i, 140)
            elif i == self._model.COL_ROLE:
                h.setSectionResizeMode(i, QHeaderView.Fixed)
                self._table.setColumnWidth(i, 130)
            else:
                h.setSectionResizeMode(i, QHeaderView.Stretch)

    def _on_selection(self, selected, deselected):
        indexes = self._table.selectionModel().selectedRows()
        if indexes:
            item = self._model.get_item(indexes[0].row())
            if item:
                self._show_detail(item)

    def _show_detail(self, item: BeraterAbrechnung):
        self._det_name.setText(item.berater_name)
        self._statement.clear_rows()
        self._statement.add_line(texts.PROVISION_PAY_DETAIL_BRUTTO, format_eur(item.brutto_provision))
        self._statement.add_line(texts.PROVISION_PAY_DETAIL_TL, format_eur(item.tl_abzug), color=ERROR if item.tl_abzug < 0 else "")
        self._statement.add_line(texts.PROVISION_PAY_DETAIL_RUECK, format_eur(item.rueckbelastungen), color=ERROR if item.rueckbelastungen < 0 else "")
        self._statement.add_separator()
        self._statement.add_line(texts.PROVISION_PAY_DETAIL_NETTO, format_eur(item.auszahlung), bold=True)

        self._load_positions(item)
        self._detail.setVisible(True)

    def _load_positions(self, item: BeraterAbrechnung):
        while self._pos_layout.count():
            w = self._pos_layout.takeAt(0).widget()
            if w:
                w.deleteLater()

        monat = item.abrechnungsmonat
        try:
            year, month = int(monat[:4]), int(monat[5:7])
            _, last_day = calendar.monthrange(year, month)
            von = f"{monat}-01"
            bis = f"{monat}-{last_day:02d}"
        except (ValueError, IndexError):
            von, bis = None, None

        if not von or not bis:
            return

        self._current_positions_berater_id = item.berater_id

        if hasattr(self, '_pos_worker') and self._pos_worker and self._pos_worker.isRunning():
            return
        self._pos_worker = AuszahlungenPositionenWorker(self._backend, item.berater_id, von, bis)
        self._pos_worker.finished.connect(self._on_positions_loaded)
        self._pos_worker.error.connect(lambda msg: logger.warning(f"Positionen-Laden fehlgeschlagen: {msg}"))
        self._pos_worker.start()

    def _on_positions_loaded(self, berater_id: int, comms: list):
        if getattr(self, '_current_positions_berater_id', None) != berater_id:
            return

        while self._pos_layout.count():
            w = self._pos_layout.takeAt(0).widget()
            if w:
                w.deleteLater()

        if not comms:
            lbl = QLabel(texts.PROVISION_PAY_NO_POSITIONS)
            lbl.setStyleSheet(f"color: {PRIMARY_500}; font-style: italic;")
            self._pos_layout.addWidget(lbl)
            return

        for c in comms:
            row = QFrame()
            row.setStyleSheet(
                f"QFrame {{ background: {BG_SECONDARY}; border-radius: 4px; padding: 4px 8px; }}"
            )
            hl = QHBoxLayout(row)
            hl.setContentsMargins(0, 0, 0, 0)
            hl.setSpacing(4)

            desc = c.versicherer or c.vu_name or ""
            if c.vsnr:
                desc += f"  {c.vsnr}"
            left = QLabel(desc)
            left.setStyleSheet(f"font-size: {FONT_SIZE_CAPTION}; color: {PRIMARY_900};")
            hl.addWidget(left, 1)

            amount = QLabel(format_eur(c.betrag))
            color = ERROR if c.betrag < 0 else PRIMARY_900
            amount.setStyleSheet(f"font-size: {FONT_SIZE_CAPTION}; font-weight: 600; color: {color};")
            amount.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            hl.addWidget(amount)

            self._pos_layout.addWidget(row)

    def _generate(self):
        monat = self._monat_combo.currentData() or datetime.now().strftime('%Y-%m')
        result = QMessageBox.question(
            self,
            texts.PROVISION_PAY_GENERATE,
            texts.PROVISION_PAY_CONFIRM.format(monat=monat),
        )
        if result == QMessageBox.Yes:
            resp = self._backend.generate_abrechnung(monat)
            if resp:
                if self._toast_manager:
                    self._toast_manager.show_success(texts.PROVISION_TOAST_GENERATE_DONE.format(monat=monat))
                self._load_data()

    def _change_status(self, abrechnung_id: int, status: str):
        if self._backend.update_abrechnung_status(abrechnung_id, status):
            if self._toast_manager:
                label = STATUS_LABELS.get(status, status)
                self._toast_manager.show_success(texts.PROVISION_TOAST_STATUS_CHANGED.format(status=label))
            self._load_data()

    def _export_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, texts.PROVISION_PAY_EXPORT_CSV_TITLE, "", "CSV (*.csv)")
        if not path:
            return
        data = []
        for row in range(self._model.rowCount()):
            row_data = []
            for col in range(self._model.columnCount() - 1):
                val = self._model.data(self._model.index(row, col))
                row_data.append(val or "")
            data.append(row_data)
        try:
            with open(path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f, delimiter=';')
                writer.writerow([self._model.COLUMNS[i] for i in range(self._model.columnCount() - 1)])
                writer.writerows(data)
            if self._toast_manager:
                self._toast_manager.show_success(texts.PROVISION_TOAST_EXPORT_DONE.format(path=os.path.basename(path)))
        except Exception as e:
            logger.error(f"CSV-Export-Fehler: {e}")
            if self._toast_manager:
                self._toast_manager.show_error(str(e))

    def _export_xlsx(self):
        try:
            import openpyxl
            from openpyxl.styles import Font, PatternFill, Alignment, numbers
        except ImportError:
            if self._toast_manager:
                self._toast_manager.show_error(texts.PROVISION_PAY_OPENPYXL_MISSING)
            return

        path, _ = QFileDialog.getSaveFileName(self, texts.PROVISION_PAY_EXPORT_XLSX_TITLE, "", "Excel (*.xlsx)")
        if not path:
            return

        try:
            wb = openpyxl.Workbook()
            ws = wb.active
            monat = self._monat_combo.currentData() or datetime.now().strftime('%Y-%m')
            ws.title = texts.PROVISION_PAY_EXCEL_SHEET.format(monat=monat)

            headers = [self._model.COLUMNS[i] for i in range(self._model.columnCount() - 1)]
            header_font = Font(bold=True, color="FFFFFF")
            header_fill = PatternFill(start_color="1e3a5f", end_color="1e3a5f", fill_type="solid")

            for col_idx, header in enumerate(headers, 1):
                cell = ws.cell(row=1, column=col_idx, value=header)
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = Alignment(horizontal="center")

            eur_cols = {
                self._model.COL_BRUTTO, self._model.COL_TL,
                self._model.COL_NETTO, self._model.COL_RUECK,
                self._model.COL_AUSZAHLUNG,
            }

            for row_idx in range(self._model.rowCount()):
                item = self._model.get_item(row_idx)
                if not item:
                    continue
                values = [
                    item.berater_name,
                    item.berater_role,
                    item.brutto_provision,
                    item.tl_abzug,
                    item.netto_provision,
                    item.rueckbelastungen,
                    item.auszahlung,
                    item.anzahl_provisionen,
                    STATUS_LABELS.get(item.status, item.status),
                    item.revision,
                ]
                for col_idx, val in enumerate(values):
                    cell = ws.cell(row=row_idx + 2, column=col_idx + 1, value=val)
                    if col_idx in eur_cols:
                        cell.number_format = '#,##0.00 €'
                        cell.alignment = Alignment(horizontal="right")

            for col_idx in range(1, len(headers) + 1):
                ws.column_dimensions[openpyxl.utils.get_column_letter(col_idx)].width = 16

            wb.save(path)
            if self._toast_manager:
                self._toast_manager.show_success(texts.PROVISION_TOAST_EXPORT_DONE.format(path=os.path.basename(path)))
        except Exception as e:
            logger.error(f"Excel-Export-Fehler: {e}")
            if self._toast_manager:
                self._toast_manager.show_error(str(e))
