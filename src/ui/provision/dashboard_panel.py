"""
Dashboard-Panel (Uebersicht) fuer Provisionsmanagement v2.0.

Entscheidungs-Cockpit mit 4 KPI-Karten (2x2 Grid),
Berater-Ranking mit Pill-Badges und optionaler rechter Sidebar.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QComboBox, QTableView, QHeaderView, QSplitter, QFrame,
    QSizePolicy, QScrollArea, QDialog, QDateEdit,
)
from PySide6.QtCore import Qt, Signal, QDate, QModelIndex
from PySide6.QtGui import QColor
from typing import List, Dict, Optional, Tuple
from datetime import datetime, date
import calendar

from api.provision import ProvisionAPI
from domain.provision.entities import DashboardSummary
from ui.styles.tokens import (
    PRIMARY_0, PRIMARY_100, PRIMARY_500, PRIMARY_900,
    ACCENT_500, BG_PRIMARY, BG_SECONDARY, BG_TERTIARY,
    BORDER_DEFAULT, SUCCESS, ERROR, WARNING,
    FONT_BODY, FONT_SIZE_BODY, FONT_SIZE_CAPTION,
    PILL_COLORS, ROLE_BADGE_COLORS,
    get_provision_table_style, build_rich_tooltip,
)
from ui.provision.widgets import (
    KpiCard, DonutChartWidget, PillBadgeDelegate, SectionHeader,
    ActivityFeedWidget, format_eur, get_combo_style,
)
from ui.provision.workers import DashboardLoadWorker, BeraterDetailWorker
from ui.provision.models import BeraterRankingModel
from i18n import de as texts
import logging

logger = logging.getLogger(__name__)


class DashboardPanel(QWidget):
    """Entscheidungs-Cockpit: 4 KPI-Karten + Berater-Ranking.

    Implementiert IDashboardView fuer den DashboardPresenter.
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
            self._load_data()

    def set_presenter(self, presenter) -> None:
        """Verbindet dieses Panel mit dem DashboardPresenter."""
        self._presenter = presenter
        presenter.set_view(self)
        von, bis = self._get_date_range()
        self._presenter.load_dashboard(von=von, bis=bis)

    # ── IDashboardView ──

    def show_summary(self, summary: DashboardSummary) -> None:
        """View-Interface: Dashboard-KPIs anzeigen."""
        if not summary:
            self._status_label.setText(texts.PROVISION_DASH_ERROR)
            return
        self._render_summary(summary)

    def show_clearance_counts(self, counts: Dict) -> None:
        """View-Interface: Klaerfall-Counts anzeigen."""
        self._render_clearance(counts)
        self._status_label.setText("")

    def show_loading(self, loading: bool) -> None:
        """View-Interface: Ladezustand anzeigen."""
        if loading:
            self._status_label.setText(texts.PROVISION_DASH_LOADING)

    def show_error(self, message: str) -> None:
        """View-Interface: Fehler anzeigen."""
        self._status_label.setText(texts.PROVISION_DASH_ERROR)
        logger.error(f"Dashboard-Fehler: {message}")

    def show_berater_detail(self, berater_id: int, berater_name: str,
                            row_data: dict, detail) -> None:
        """View-Interface: Berater-Detail-Dialog oeffnen."""
        self._show_berater_detail_dialog(berater_id, berater_name, row_data, detail)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(24)

        # ── Header ──
        header = QHBoxLayout()
        title = QLabel(texts.PROVISION_DASH_TITLE)
        title.setStyleSheet(
            f"font-size: 18pt; font-weight: 700; color: {PRIMARY_900}; font-family: {FONT_BODY};"
        )
        header.addWidget(title)
        header.addStretch()

        header.addWidget(QLabel(texts.PROVISION_DASH_MONAT))

        self._mode_combo = QComboBox()
        self._mode_combo.setFixedWidth(170)
        self._mode_combo.setStyleSheet(get_combo_style())
        self._mode_combo.addItem(texts.PROVISION_FILTER_MODE_MONTH, "month")
        self._mode_combo.addItem(texts.PROVISION_FILTER_LAST_3, "last_3")
        self._mode_combo.addItem(texts.PROVISION_FILTER_LAST_6, "last_6")
        self._mode_combo.addItem(texts.PROVISION_FILTER_LAST_12, "last_12")
        self._mode_combo.addItem(texts.PROVISION_FILTER_MODE_RANGE, "range")
        self._mode_combo.addItem(texts.PROVISION_FILTER_ALL_TIME, "all")
        self._mode_combo.currentIndexChanged.connect(self._on_date_mode_changed)
        header.addWidget(self._mode_combo)

        self._monat_combo = QComboBox()
        self._monat_combo.setFixedWidth(130)
        self._monat_combo.setStyleSheet(get_combo_style())
        today = date.today()
        for i in range(24):
            y = today.year
            m = today.month - i
            while m < 1:
                m += 12
                y -= 1
            self._monat_combo.addItem(f"{m:02d}/{y}", f"{y}-{m:02d}")
        self._monat_combo.currentIndexChanged.connect(self._load_data)
        header.addWidget(self._monat_combo)

        self._von_label = QLabel(texts.PROVISION_FILTER_FROM)
        self._von_label.setStyleSheet(f"color: {PRIMARY_500};")
        self._von_label.setVisible(False)
        header.addWidget(self._von_label)
        self._date_from = QDateEdit()
        self._date_from.setCalendarPopup(True)
        self._date_from.setDisplayFormat("dd.MM.yyyy")
        self._date_from.setDate(QDate(today.year, today.month, 1).addMonths(-3))
        self._date_from.setVisible(False)
        self._date_from.dateChanged.connect(self._load_data)
        header.addWidget(self._date_from)

        self._bis_label = QLabel(texts.PROVISION_FILTER_TO)
        self._bis_label.setStyleSheet(f"color: {PRIMARY_500};")
        self._bis_label.setVisible(False)
        header.addWidget(self._bis_label)
        self._date_to = QDateEdit()
        self._date_to.setCalendarPopup(True)
        self._date_to.setDisplayFormat("dd.MM.yyyy")
        self._date_to.setDate(QDate.currentDate())
        self._date_to.setVisible(False)
        self._date_to.dateChanged.connect(self._load_data)
        header.addWidget(self._date_to)

        layout.addLayout(header)

        # ── KPI-Karten (2x2 Grid) ──
        kpi_grid = QGridLayout()
        kpi_grid.setSpacing(16)

        # Karte 1: Gesamtprovision
        self._card_total = KpiCard(texts.PROVISION_DASH_TOTAL, PRIMARY_900)
        self._card_total.set_value("0,00 \u20ac")
        self._card_total.set_subline(texts.PROVISION_DASH_TOTAL_SUB)
        self._card_total.setToolTip(build_rich_tooltip(
            texts.PROVISION_DASH_TOTAL_TIP_DEF,
            berechnung=texts.PROVISION_DASH_TOTAL_TIP_CALC,
            quelle=texts.PROVISION_DASH_TOTAL_TIP_SRC,
            hinweis=texts.PROVISION_DASH_TOTAL_TIP_NOTE,
        ))
        self._lbl_trend = self._card_total.add_extra_label("")
        self._lbl_ytd = self._card_total.add_extra_label("")
        self._lbl_top_vu_header = self._card_total.add_extra_label(texts.PROVISION_DASH_TOP_VU, PRIMARY_500)
        self._lbl_top_vu_1 = self._card_total.add_extra_label("")
        self._lbl_top_vu_2 = self._card_total.add_extra_label("")
        self._lbl_top_vu_3 = self._card_total.add_extra_label("")
        kpi_grid.addWidget(self._card_total, 0, 0)

        # Karte 2: Zuordnungsquote
        self._card_match = KpiCard(texts.PROVISION_DASH_MATCH_RATE, SUCCESS)
        self._card_match.setToolTip(build_rich_tooltip(
            texts.PROVISION_DASH_MATCH_RATE_TIP_DEF,
            berechnung=texts.PROVISION_DASH_MATCH_RATE_TIP_CALC,
            quelle=texts.PROVISION_DASH_MATCH_RATE_TIP_SRC,
            hinweis=texts.PROVISION_DASH_MATCH_RATE_TIP_NOTE,
        ))
        self._donut = DonutChartWidget(0, size=100, thickness=12, color_fill=SUCCESS)
        self._card_match.add_extra_widget(self._donut)
        self._lbl_match_detail = self._card_match.add_extra_label("")
        self._card_match.set_value("")
        kpi_grid.addWidget(self._card_match, 0, 1)

        # Karte 3: Klaerfaelle
        self._card_clearance = KpiCard(texts.PROVISION_DASH_CLEARANCE, WARNING)
        self._card_clearance.set_subline(texts.PROVISION_DASH_CLEARANCE_SUB)
        self._lbl_clear_count = None
        self._lbl_clear_no_contract = self._card_clearance.add_extra_label("")
        self._lbl_clear_no_berater = self._card_clearance.add_extra_label("")
        self._lbl_clear_no_model = self._card_clearance.add_extra_label("")
        self._card_clearance.add_action_button(
            texts.PROVISION_DASH_CLEARANCE_BTN,
            lambda: self.navigate_to_panel.emit(4),
        )
        kpi_grid.addWidget(self._card_clearance, 1, 0)

        # Karte 4: Auszahlungen
        self._card_payouts = KpiCard(texts.PROVISION_DASH_PAYOUTS, SUCCESS)
        self._card_payouts.set_subline(texts.PROVISION_DASH_PAYOUTS_SUB)
        self._lbl_pay_ready = self._card_payouts.add_extra_label("")
        self._lbl_pay_review = self._card_payouts.add_extra_label("")
        self._lbl_pay_done = self._card_payouts.add_extra_label("")
        self._card_payouts.add_action_button(
            texts.PROVISION_DASH_PAYOUTS_BTN,
            lambda: self.navigate_to_panel.emit(6),
        )
        kpi_grid.addWidget(self._card_payouts, 1, 1)

        layout.addLayout(kpi_grid)

        # ── Berater-Ranking ──
        ranking_header = SectionHeader(
            texts.PROVISION_DASH_BERATER_RANKING,
            texts.PROVISION_DASH_BERATER_RANKING_DESC,
        )
        layout.addWidget(ranking_header)

        self._ranking_model = BeraterRankingModel()
        self._ranking_table = QTableView()
        self._ranking_table.setModel(self._ranking_model)
        self._ranking_table.setAlternatingRowColors(True)
        self._ranking_table.setSelectionBehavior(QTableView.SelectRows)
        self._ranking_table.verticalHeader().setVisible(False)
        self._ranking_table.horizontalHeader().setStretchLastSection(True)
        self._ranking_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._ranking_table.setStyleSheet(get_provision_table_style())
        self._ranking_table.verticalHeader().setDefaultSectionSize(52)

        role_delegate = PillBadgeDelegate(
            ROLE_BADGE_COLORS,
            label_map={
                "consulter": texts.PROVISION_EMP_ROLE_CONSULTER,
                "teamleiter": texts.PROVISION_EMP_ROLE_TEAMLEITER,
                "backoffice": texts.PROVISION_EMP_ROLE_BACKOFFICE,
            },
        )
        self._ranking_table.setItemDelegateForColumn(1, role_delegate)
        self._role_delegate = role_delegate
        self._ranking_table.doubleClicked.connect(self._on_ranking_double_click)

        layout.addWidget(self._ranking_table)

        # ── Status ──
        self._status_label = QLabel(texts.PROVISION_DASH_LOADING)
        self._status_label.setStyleSheet(f"color: {PRIMARY_500}; font-size: {FONT_SIZE_CAPTION};")
        layout.addWidget(self._status_label)

    def refresh(self):
        self._load_data()

    def _get_date_range(self) -> Tuple[Optional[str], Optional[str]]:
        """Gibt (von, bis) als Datums-Strings zurueck -- je nach Modus."""
        mode = self._mode_combo.currentData()
        if mode == "month":
            val = self._monat_combo.currentData()
            if val:
                y, m = val.split('-')
                y, m = int(y), int(m)
                last_day = calendar.monthrange(y, m)[1]
                return f"{y}-{m:02d}-01", f"{y}-{m:02d}-{last_day:02d}"
            now = datetime.now()
            last_day = calendar.monthrange(now.year, now.month)[1]
            return f"{now.year}-{now.month:02d}-01", f"{now.year}-{now.month:02d}-{last_day:02d}"
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
        self._monat_combo.setVisible(mode == "month")
        self._von_label.setVisible(mode == "range")
        self._date_from.setVisible(mode == "range")
        self._bis_label.setVisible(mode == "range")
        self._date_to.setVisible(mode == "range")
        self._load_data()

    def _load_data(self, *args):
        von, bis = self._get_date_range()
        logger.debug(f"Dashboard _load_data: von={von}, bis={bis}")
        self._status_label.setText(texts.PROVISION_DASH_LOADING)

        if self._presenter:
            self._presenter.load_dashboard(von=von, bis=bis)
            return

        if self._worker:
            if self._worker.isRunning():
                return
            try:
                self._worker.finished.disconnect()
                self._worker.error.disconnect()
            except RuntimeError:
                pass
        self._worker = DashboardLoadWorker(self._api, von=von, bis=bis)
        self._worker.finished.connect(self._on_data_loaded)
        self._worker.error.connect(self._on_data_error)
        self._worker.start()

    def _on_data_loaded(self, summary: Optional[DashboardSummary], clearance: dict):
        if not summary:
            self._status_label.setText(texts.PROVISION_DASH_ERROR)
            return
        self._render_summary(summary)
        self._render_clearance(clearance)
        self._status_label.setText("")

    def _render_summary(self, summary: DashboardSummary):
        # Karte 1: Gesamtprovision
        self._card_total.set_value(format_eur(summary.eingang_monat))
        self._lbl_ytd.setText(texts.PROVISION_DASH_YTD.format(amount=format_eur(summary.eingang_ytd)))

        if hasattr(summary, 'eingang_vormonat') and summary.eingang_vormonat:
            prev = float(summary.eingang_vormonat)
            cur = float(summary.eingang_monat)
            if prev > 0:
                pct = ((cur - prev) / prev) * 100
                sign = "+" if pct >= 0 else ""
                color = SUCCESS if pct >= 0 else ERROR
                self._lbl_trend.setText(texts.PROVISION_DASH_VS_PREV.format(sign=sign, pct=f"{pct:.1f}"))
                self._lbl_trend.setStyleSheet(f"color: {color}; font-size: {FONT_SIZE_CAPTION}; font-family: {FONT_BODY};")

        top_vu = getattr(summary, 'top_vu', None) or []
        labels = [self._lbl_top_vu_1, self._lbl_top_vu_2, self._lbl_top_vu_3]
        for i, lbl in enumerate(labels):
            if i < len(top_vu):
                vu = top_vu[i]
                lbl.setText(f"{i+1}. {vu.get('name', '?')}  {format_eur(vu.get('sum', 0))}")
            else:
                lbl.setText("")

        # Karte 2: Zuordnungsquote
        total_count = summary.total_positions or 0
        matched_count = summary.matched_positions or 0
        if total_count > 0:
            pct = (matched_count / total_count) * 100
        else:
            pct = 0
        self._donut.set_percent(pct)
        self._card_match.set_value(f"{pct:.0f}%")
        self._lbl_match_detail.setText(
            texts.PROVISION_DASH_MATCH_RATE_SUB.format(matched=matched_count, total=total_count)
        )

        # Karte 4: Auszahlungen
        pay_ready = getattr(summary, 'payouts_ready', 0)
        pay_review = getattr(summary, 'payouts_review', 0)
        pay_done = getattr(summary, 'payouts_done', 0)
        self._lbl_pay_ready.setText(texts.PROVISION_DASH_PAYOUTS_READY.format(count=pay_ready))
        self._lbl_pay_review.setText(texts.PROVISION_DASH_PAYOUTS_REVIEW.format(count=pay_review))
        self._lbl_pay_done.setText(texts.PROVISION_DASH_PAYOUTS_DONE.format(count=pay_done))

        # Berater-Ranking
        self._ranking_model.set_data(summary.per_berater)

    def _render_clearance(self, clearance: dict):
        no_contract = clearance.get('no_contract', 0)
        no_berater = clearance.get('no_berater', 0)
        no_model = clearance.get('no_model', 0)
        total_clearance = clearance.get('total', no_contract + no_berater + no_model)
        self._card_clearance.set_value(
            texts.PROVISION_DASH_CLEARANCE_OPEN.format(count=total_clearance))
        self._lbl_clear_no_contract.setText(
            texts.PROVISION_DASH_CLEARANCE_NO_CONTRACT.format(count=no_contract)
            if no_contract else "")
        self._lbl_clear_no_berater.setText(
            texts.PROVISION_DASH_CLEARANCE_NO_BERATER.format(count=no_berater)
            if no_berater else "")
        self._lbl_clear_no_model.setText(
            texts.PROVISION_DASH_CLEARANCE_NO_MODEL.format(count=no_model)
            if no_model else "")

    def _on_data_error(self, msg: str):
        self._status_label.setText(texts.PROVISION_DASH_ERROR)
        logger.error(f"Dashboard-Ladefehler: {msg}")

    def _on_ranking_double_click(self, index: QModelIndex):
        if not index.isValid() or index.row() >= len(self._ranking_model._data):
            return
        row = self._ranking_model._data[index.row()]
        berater_id = row.get('berater_id') or row.get('id')
        berater_name = row.get('name', '')
        if not berater_id:
            return

        von, bis = self._get_date_range()

        if self._presenter:
            self._presenter.load_berater_detail(
                berater_id, berater_name, dict(row), von=von, bis=bis)
            return

        if hasattr(self, '_detail_worker') and self._detail_worker and self._detail_worker.isRunning():
            return
        self._detail_worker = BeraterDetailWorker(
            self._api, berater_id, berater_name, dict(row), von=von, bis=bis
        )
        self._detail_worker.finished.connect(self._show_berater_detail_dialog)
        self._detail_worker.error.connect(lambda msg: logger.error(f"Berater-Detail-Fehler: {msg}"))
        self._detail_worker.start()

    def _show_berater_detail_dialog(self, berater_id: int, berater_name: str, row: dict, detail):
        if not detail:
            return

        dlg = QDialog(self)
        dlg.setWindowTitle(f"{berater_name} \u2013 {texts.PROVISION_DASH_BERATER_DETAIL}")
        dlg.setMinimumSize(500, 400)
        layout = QVBoxLayout(dlg)

        name_lbl = QLabel(berater_name)
        name_lbl.setStyleSheet(f"font-size: 14pt; font-weight: 700; color: {PRIMARY_900};")
        layout.addWidget(name_lbl)

        role_lbl = QLabel({
            'consulter': texts.PROVISION_EMP_ROLE_CONSULTER,
            'teamleiter': texts.PROVISION_EMP_ROLE_TEAMLEITER,
            'backoffice': texts.PROVISION_EMP_ROLE_BACKOFFICE,
        }.get(row.get('role', ''), row.get('role', '')))
        role_lbl.setStyleSheet(f"color: {PRIMARY_500}; font-size: {FONT_SIZE_BODY};")
        layout.addWidget(role_lbl)

        sd = detail if isinstance(detail, dict) else {}
        grid = QGridLayout()
        grid.setSpacing(8)

        kpis = [
            (texts.PROVISION_DASH_COL_BRUTTO, format_eur(sd.get('brutto', 0))),
            (texts.PROVISION_DASH_COL_TL_ABZUG, format_eur(sd.get('tl_abzug', 0))),
            (texts.PROVISION_DASH_COL_NETTO, format_eur(sd.get('netto', 0))),
            (texts.PROVISION_DASH_COL_AG, format_eur(sd.get('ag_anteil', 0))),
            (texts.PROVISION_DASH_COL_RUECK, format_eur(sd.get('rueckbelastung', 0))),
            (texts.PROVISION_DASH_BERATER_CONTRACTS, str(sd.get('positions_count', 0))),
        ]
        for i, (label, value) in enumerate(kpis):
            row_idx = i // 2
            col_idx = (i % 2) * 2
            l = QLabel(label + ":")
            l.setStyleSheet(f"color: {PRIMARY_500}; font-size: {FONT_SIZE_CAPTION};")
            v = QLabel(value)
            v.setStyleSheet(f"color: {PRIMARY_900}; font-size: {FONT_SIZE_BODY}; font-weight: 600;")
            grid.addWidget(l, row_idx, col_idx)
            grid.addWidget(v, row_idx, col_idx + 1)

        layout.addLayout(grid)

        commissions = sd.get('commissions', [])
        if commissions:
            recent_lbl = QLabel(texts.PROVISION_DASH_BERATER_RECENT)
            recent_lbl.setStyleSheet(f"font-weight: 600; font-size: 11pt; color: {PRIMARY_900}; margin-top: 12px;")
            layout.addWidget(recent_lbl)
            for p in commissions[:10]:
                prov_text = f"{p.get('versicherer', '?')} \u2013 {p.get('vsnr', '?')} \u2013 {format_eur(float(p.get('betrag', 0)))}"
                prov_lbl = QLabel(prov_text)
                prov_lbl.setStyleSheet(f"color: {PRIMARY_900}; font-size: {FONT_SIZE_CAPTION};")
                layout.addWidget(prov_lbl)

        layout.addStretch()
        dlg.exec()
