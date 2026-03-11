"""
Workforce Stats View - Statistik-Dashboard mit Matplotlib-Charts.

Zeigt Mitarbeiterstatistiken pro Arbeitgeber an. Standard-Modus: KPI-Cards,
Donut-Charts (Geschlecht, Beschaeftigungsart), Bar-Charts (Abteilungen, Trends).
Langzeit-Modus: Ein-/Austritte pro Jahr, durchschnittliche Beschaeftigungsdauer.
"""

import logging
import os
from datetime import datetime

import matplotlib
matplotlib.use('QtAgg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QFrame, QProgressBar, QScrollArea, QFileDialog,
    QGridLayout,
)
from PySide6.QtCore import Qt, QThreadPool

from workforce.api_client import WorkforceApiClient
from workforce.workers import StatsWorker
from ui.styles.tokens import (
    PRIMARY_500, PRIMARY_900, ACCENT_500, ACCENT_100,
    FONT_HEADLINE, FONT_BODY,
    FONT_SIZE_BODY, FONT_SIZE_CAPTION, FONT_SIZE_H2,
    BG_PRIMARY, BG_SECONDARY, BORDER_DEFAULT, RADIUS_MD, RADIUS_SM,
    SUCCESS, ERROR, TEXT_PRIMARY, TEXT_SECONDARY,
    FONT_WEIGHT_BOLD, FONT_WEIGHT_MEDIUM,
    get_button_primary_style, get_button_secondary_style,
    CHART_PALETTE, CHART_BG_COLOR, CHART_TEXT_COLOR, CHART_GRID_COLOR,
)
from i18n import de as texts

logger = logging.getLogger(__name__)

CHART_BG = CHART_BG_COLOR
CHART_TEXT = CHART_TEXT_COLOR
CHART_GRID = CHART_GRID_COLOR
CHART_FONT = "Segoe UI"


class _ChartCanvas(FigureCanvasQTAgg):
    """Wiederverwendbares Matplotlib-Canvas mit ACENCIA-Styling."""

    def __init__(self, width=5, height=3.2, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi, facecolor=CHART_BG)
        self.fig.subplots_adjust(left=0.08, right=0.96, top=0.90, bottom=0.15)
        super().__init__(self.fig)
        self.setStyleSheet("background: transparent; border: none;")


class StatsView(QWidget):
    """Statistik-Dashboard fuer das Workforce-Modul."""

    def __init__(self, wf_api: WorkforceApiClient, thread_pool: QThreadPool):
        super().__init__()
        self._wf_api = wf_api
        self._thread_pool = thread_pool
        self._toast_manager = None
        self._employers: list[dict] = []
        self._current_stats: dict = {}
        self._loading = False
        self._setup_ui()
        self._load_employers()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)

        header = QHBoxLayout()
        title = QLabel(texts.WF_STATS_TITLE)
        title.setStyleSheet(f"""
            font-family: {FONT_HEADLINE}; font-size: {FONT_SIZE_H2};
            color: {PRIMARY_900}; font-weight: 600;
        """)
        header.addWidget(title)
        header.addStretch()

        self._export_btn = QPushButton(texts.WF_STATS_EXPORT_TXT)
        self._export_btn.setStyleSheet(get_button_secondary_style())
        self._export_btn.setCursor(Qt.PointingHandCursor)
        self._export_btn.setEnabled(False)
        self._export_btn.clicked.connect(self._export_stats)
        header.addWidget(self._export_btn)
        root.addLayout(header)

        controls = QHBoxLayout()
        controls.setSpacing(12)

        emp_label = QLabel(texts.WF_STATS_EMPLOYER)
        emp_label.setStyleSheet(f"color: {PRIMARY_900}; font-family: {FONT_BODY};")
        controls.addWidget(emp_label)

        self._employer_combo = QComboBox()
        self._employer_combo.setMinimumWidth(250)
        self._employer_combo.currentIndexChanged.connect(self._on_employer_changed)
        controls.addWidget(self._employer_combo)

        controls.addSpacing(24)

        mode_label = QLabel(texts.WF_STATS_MODE)
        mode_label.setStyleSheet(f"color: {PRIMARY_900}; font-family: {FONT_BODY};")
        controls.addWidget(mode_label)

        self._mode_combo = QComboBox()
        self._mode_combo.addItem(texts.WF_STATS_STANDARD, "standard")
        self._mode_combo.addItem(texts.WF_STATS_LONGTERM, "longterm")
        self._mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        controls.addWidget(self._mode_combo)

        controls.addStretch()

        self._calc_btn = QPushButton(texts.WF_STATS_CALCULATE)
        self._calc_btn.setStyleSheet(get_button_primary_style())
        self._calc_btn.setCursor(Qt.PointingHandCursor)
        self._calc_btn.clicked.connect(self._calculate_stats)
        controls.addWidget(self._calc_btn)
        root.addLayout(controls)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setFixedHeight(4)
        self._progress.setVisible(False)
        root.addWidget(self._progress)

        self._progress_label = QLabel()
        self._progress_label.setStyleSheet(
            f"color: {PRIMARY_500}; font-size: {FONT_SIZE_CAPTION}; font-family: {FONT_BODY};"
        )
        self._progress_label.setVisible(False)
        root.addWidget(self._progress_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self._results_widget = QWidget()
        self._results_widget.setStyleSheet("background: transparent;")
        self._results_layout = QVBoxLayout(self._results_widget)
        self._results_layout.setContentsMargins(0, 0, 8, 0)
        self._results_layout.setSpacing(16)
        scroll.setWidget(self._results_widget)
        root.addWidget(scroll, 1)

        placeholder = QLabel(texts.WF_STATS_PLACEHOLDER)
        placeholder.setAlignment(Qt.AlignCenter)
        placeholder.setStyleSheet(
            f"color: {PRIMARY_500}; font-size: {FONT_SIZE_BODY}; font-family: {FONT_BODY}; padding: 48px;"
        )
        self._results_layout.addWidget(placeholder)

    # ── Data loading ────────────────────────────────────────────

    def _load_employers(self):
        try:
            self._employers = self._wf_api.get_employers()
            self._employer_combo.clear()
            for emp in self._employers:
                self._employer_combo.addItem(emp.get('name', '?'), emp.get('id'))
        except Exception as e:
            logger.error(f"Fehler beim Laden der Arbeitgeber: {e}")
            if self._toast_manager:
                self._toast_manager.show_error(texts.WF_STATS_EMPLOYER_LOAD_ERROR)

    def _on_employer_changed(self, _index: int):
        self._clear_results()

    def _on_mode_changed(self, _index: int):
        self._clear_results()

    def _clear_results(self):
        self._current_stats = {}
        self._export_btn.setEnabled(False)
        while self._results_layout.count():
            item = self._results_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _calculate_stats(self):
        if self._loading:
            return
        employer_id = self._employer_combo.currentData()
        if not employer_id:
            return
        stats_type = self._mode_combo.currentData()

        self._loading = True
        self._calc_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._progress_label.setVisible(True)
        self._progress_label.setText(texts.WF_STATS_LOADING)
        self._clear_results()

        worker = StatsWorker(self._wf_api, employer_id, stats_type)
        worker.signals.finished.connect(self._on_stats_done)
        worker.signals.error.connect(self._on_stats_error)
        worker.signals.progress.connect(self._on_progress)
        self._thread_pool.start(worker)

    def _on_progress(self, msg: str):
        self._progress_label.setText(msg)

    def _on_stats_done(self, result: dict):
        self._loading = False
        self._calc_btn.setEnabled(True)
        self._progress.setVisible(False)
        self._progress_label.setVisible(False)
        self._current_stats = result
        self._export_btn.setEnabled(True)

        stats_type = result.get('stats_type', 'standard')
        stats = result.get('stats', {})

        if not stats:
            lbl = QLabel(texts.WF_STATS_NO_DATA)
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet(f"color: {PRIMARY_500}; padding: 32px;")
            self._results_layout.addWidget(lbl)
            return

        if stats_type == 'standard':
            self._render_standard(stats)
        else:
            self._render_longterm(stats)

    def _on_stats_error(self, error: str):
        self._loading = False
        self._calc_btn.setEnabled(True)
        self._progress.setVisible(False)
        self._progress_label.setVisible(False)
        logger.error(f"Statistik-Fehler: {error}")
        if self._toast_manager:
            self._toast_manager.show_error(f"{texts.WF_STATS_ERROR}: {error}")

    # ── KPI Cards ───────────────────────────────────────────────

    def _make_card(self, label: str, value: str, accent: str = "") -> QFrame:
        card = QFrame()
        border_top = f"border-top: 3px solid {accent};" if accent else ""
        card.setStyleSheet(f"""
            QFrame#kpiCard {{
                background-color: {BG_PRIMARY};
                border: 1px solid {BORDER_DEFAULT};
                border-radius: {RADIUS_MD};
                {border_top}
            }}
        """)
        card.setObjectName("kpiCard")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(2)
        val_lbl = QLabel(str(value))
        val_lbl.setStyleSheet(f"""
            font-size: 18pt; font-weight: 700; color: {PRIMARY_900};
            font-family: {FONT_HEADLINE}; background: transparent; border: none;
        """)
        val_lbl.setAlignment(Qt.AlignCenter)
        lay.addWidget(val_lbl)
        cap_lbl = QLabel(label)
        cap_lbl.setStyleSheet(f"""
            font-size: {FONT_SIZE_CAPTION}; color: {TEXT_SECONDARY};
            font-family: {FONT_BODY}; background: transparent; border: none;
        """)
        cap_lbl.setAlignment(Qt.AlignCenter)
        cap_lbl.setWordWrap(True)
        lay.addWidget(cap_lbl)
        return card

    def _make_chart_frame(self, title_text: str, canvas: _ChartCanvas) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame#chartFrame {{
                background-color: {BG_PRIMARY};
                border: 1px solid {BORDER_DEFAULT};
                border-radius: {RADIUS_MD};
            }}
        """)
        frame.setObjectName("chartFrame")
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(16, 12, 16, 8)
        lay.setSpacing(4)
        lbl = QLabel(title_text)
        lbl.setStyleSheet(f"""
            font-family: {FONT_HEADLINE}; font-size: {FONT_SIZE_BODY};
            color: {PRIMARY_900}; font-weight: {FONT_WEIGHT_BOLD};
            background: transparent; border: none;
        """)
        lay.addWidget(lbl)
        lay.addWidget(canvas)
        return frame

    # ── Chart builders ──────────────────────────────────────────

    def _build_donut_chart(self, labels: list, data: list, width=3.4, height=2.8) -> _ChartCanvas:
        canvas = _ChartCanvas(width=width, height=height)
        ax = canvas.fig.add_subplot(111)

        colors = CHART_PALETTE[:len(labels)]
        wedges, _, autotexts = ax.pie(
            data, labels=None, autopct='%1.0f%%', startangle=90,
            colors=colors, pctdistance=0.78,
            wedgeprops=dict(width=0.42, edgecolor=CHART_BG, linewidth=2),
        )
        for t in autotexts:
            t.set_fontsize(8)
            t.set_color(CHART_BG)
            t.set_fontweight('bold')
            t.set_fontfamily(CHART_FONT)

        ax.legend(
            wedges, [f"{l}  ({d})" for l, d in zip(labels, data)],
            loc='center left', bbox_to_anchor=(1.0, 0.5),
            fontsize=8, frameon=False,
            prop={'family': CHART_FONT},
        )
        canvas.fig.subplots_adjust(left=0.02, right=0.58, top=0.95, bottom=0.05)
        return canvas

    def _build_hbar_chart(self, labels: list, data: list, color: str = ACCENT_500) -> _ChartCanvas:
        canvas = _ChartCanvas(width=7, height=max(2.2, 0.5 * len(labels) + 0.8))
        ax = canvas.fig.add_subplot(111)

        y_pos = range(len(labels))
        bars = ax.barh(y_pos, data, color=color, height=0.55, edgecolor='none')
        ax.set_yticks(y_pos)
        ax.set_yticklabels(labels, fontsize=8.5, fontfamily=CHART_FONT, color=CHART_TEXT)
        ax.invert_yaxis()
        ax.set_xlim(0, max(data) * 1.15 if data else 1)
        ax.tick_params(axis='x', labelsize=8, colors=CHART_TEXT)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_visible(False)
        ax.spines['bottom'].set_color(CHART_GRID)
        ax.xaxis.grid(True, color=CHART_GRID, linewidth=0.5)
        ax.set_axisbelow(True)
        ax.tick_params(axis='y', length=0)

        for bar, val in zip(bars, data):
            ax.text(
                bar.get_width() + max(data) * 0.02, bar.get_y() + bar.get_height() / 2,
                str(val), va='center', fontsize=8, fontweight='bold',
                color=CHART_TEXT, fontfamily=CHART_FONT,
            )

        canvas.fig.subplots_adjust(left=0.28, right=0.95, top=0.92, bottom=0.12)
        return canvas

    def _build_trend_chart(self, labels: list, joins: list, leaves: list) -> _ChartCanvas:
        canvas = _ChartCanvas(width=7, height=3.0)
        ax = canvas.fig.add_subplot(111)

        x = range(len(labels))
        bar_w = 0.35
        ax.bar([i - bar_w / 2 for i in x], joins, bar_w,
               label=texts.WF_STATS_JOINS, color=SUCCESS, edgecolor='none')
        ax.bar([i + bar_w / 2 for i in x], leaves, bar_w,
               label=texts.WF_STATS_LEAVES, color=ERROR, edgecolor='none')

        short_labels = [l[5:] if '-' in l else l for l in labels]
        ax.set_xticks(list(x))
        ax.set_xticklabels(short_labels, fontsize=7.5, fontfamily=CHART_FONT, color=CHART_TEXT, rotation=30, ha='right')
        ax.tick_params(axis='y', labelsize=8, colors=CHART_TEXT)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_color(CHART_GRID)
        ax.spines['bottom'].set_color(CHART_GRID)
        ax.yaxis.grid(True, color=CHART_GRID, linewidth=0.5)
        ax.set_axisbelow(True)
        ax.legend(
            fontsize=8, frameon=False, loc='upper left',
            prop={'family': CHART_FONT},
        )
        ax.set_ylabel('')
        from matplotlib.ticker import MaxNLocator
        ax.yaxis.set_major_locator(MaxNLocator(integer=True))

        canvas.fig.subplots_adjust(left=0.06, right=0.97, top=0.92, bottom=0.22)
        return canvas

    def _build_yearly_chart(self, labels: list, entries: list, exits: list) -> _ChartCanvas:
        canvas = _ChartCanvas(width=7, height=3.2)
        ax = canvas.fig.add_subplot(111)

        x = range(len(labels))
        bar_w = 0.35
        ax.bar([i - bar_w / 2 for i in x], entries, bar_w,
               label=texts.WF_STATS_ENTRIES, color=SUCCESS, edgecolor='none')
        ax.bar([i + bar_w / 2 for i in x], exits, bar_w,
               label=texts.WF_STATS_EXITS, color=ERROR, edgecolor='none')

        ax.set_xticks(list(x))
        ax.set_xticklabels(labels, fontsize=8, fontfamily=CHART_FONT, color=CHART_TEXT)
        ax.tick_params(axis='y', labelsize=8, colors=CHART_TEXT)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_color(CHART_GRID)
        ax.spines['bottom'].set_color(CHART_GRID)
        ax.yaxis.grid(True, color=CHART_GRID, linewidth=0.5)
        ax.set_axisbelow(True)
        ax.legend(
            fontsize=8, frameon=False, loc='upper left',
            prop={'family': CHART_FONT},
        )
        from matplotlib.ticker import MaxNLocator
        ax.yaxis.set_major_locator(MaxNLocator(integer=True))

        canvas.fig.subplots_adjust(left=0.06, right=0.97, top=0.92, bottom=0.15)
        return canvas

    # ── Render Standard ─────────────────────────────────────────

    def _render_standard(self, stats: dict):
        sc = stats.get('status_counts', {})
        avgs = stats.get('averages', {})
        turnover = stats.get('turnover', {})

        cards_row = QHBoxLayout()
        cards_row.setSpacing(10)
        cards_row.addWidget(self._make_card(
            texts.WF_STATS_TOTAL, str(sc.get('total', 0)), PRIMARY_900))
        cards_row.addWidget(self._make_card(
            texts.WF_STATS_ACTIVE, str(sc.get('active', 0)), SUCCESS))
        cards_row.addWidget(self._make_card(
            texts.WF_STATS_INACTIVE, str(sc.get('inactive', 0)), PRIMARY_500))
        cards_row.addWidget(self._make_card(
            texts.WF_STATS_AVG_TENURE,
            f"{avgs.get('tenure_years', 0)} {texts.WF_STATS_YEARS}"))
        cards_row.addWidget(self._make_card(
            texts.WF_STATS_AVG_HOURS, str(stats.get('average_weekly_hours', 0))))
        cards_row.addWidget(self._make_card(
            texts.WF_STATS_TURNOVER,
            f"{turnover.get('rate_percent', 0)} %", ACCENT_500))
        cards_w = QWidget()
        cards_w.setLayout(cards_row)
        self._results_layout.addWidget(cards_w)

        donuts_row = QHBoxLayout()
        donuts_row.setSpacing(12)

        gd = stats.get('gender_distribution', {})
        if gd.get('labels') and gd.get('data'):
            chart = self._build_donut_chart(gd['labels'], gd['data'])
            donuts_row.addWidget(self._make_chart_frame(texts.WF_STATS_GENDER, chart))

        etd = stats.get('employment_type_distribution', {})
        if etd.get('labels') and etd.get('data'):
            chart = self._build_donut_chart(etd['labels'], etd['data'])
            donuts_row.addWidget(self._make_chart_frame(texts.WF_STATS_EMPLOYMENT_TYPES, chart))

        if donuts_row.count() > 0:
            donuts_w = QWidget()
            donuts_w.setLayout(donuts_row)
            self._results_layout.addWidget(donuts_w)

        dd = stats.get('department_distribution', {})
        if dd.get('labels') and dd.get('data'):
            chart = self._build_hbar_chart(dd['labels'], dd['data'])
            self._results_layout.addWidget(
                self._make_chart_frame(texts.WF_STATS_DEPARTMENTS, chart))

        jlt = stats.get('join_leave_trends', {})
        if jlt.get('labels'):
            chart = self._build_trend_chart(
                jlt['labels'], jlt['joins'], jlt['leaves'])
            self._results_layout.addWidget(
                self._make_chart_frame(texts.WF_STATS_TRENDS, chart))

        self._results_layout.addStretch()

    # ── Render Longterm ─────────────────────────────────────────

    def _render_longterm(self, stats: dict):
        ad = stats.get('average_duration', {})

        cards_row = QHBoxLayout()
        cards_row.setSpacing(12)
        cards_row.addWidget(self._make_card(
            texts.WF_STATS_AVG_DURATION,
            f"{ad.get('years', 0)} {texts.WF_STATS_YEARS}", ACCENT_500))
        cards_row.addWidget(self._make_card(
            texts.WF_STATS_EMPLOYEES_INCLUDED,
            str(ad.get('total_employees_included', 0))))
        cards_row.addStretch()
        cards_w = QWidget()
        cards_w.setLayout(cards_row)
        self._results_layout.addWidget(cards_w)

        ee = stats.get('entries_exits', {})
        if ee.get('labels'):
            chart = self._build_yearly_chart(
                ee['labels'], ee['entries'], ee['exits'])
            self._results_layout.addWidget(
                self._make_chart_frame(texts.WF_STATS_ENTRIES_EXITS, chart))

        self._results_layout.addStretch()

    # ── Export ──────────────────────────────────────────────────

    def _export_stats(self):
        if not self._current_stats:
            return
        stats = self._current_stats.get('stats', {})
        stats_type = self._current_stats.get('stats_type', 'standard')
        employer_name = self._employer_combo.currentText()
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        default_name = f"workforce_stats_{stats_type}_{timestamp}.txt"

        path, _ = QFileDialog.getSaveFileName(
            self, texts.WF_STATS_EXPORT_TITLE, default_name, "Text (*.txt)"
        )
        if not path:
            return

        try:
            lines = [
                f"{texts.WF_STATS_TITLE} - {employer_name}",
                f"{texts.WF_STATS_MODE}: {texts.WF_STATS_STANDARD if stats_type == 'standard' else texts.WF_STATS_LONGTERM}",
                f"{texts.WF_STATS_EXPORT_DATE}: {datetime.now().strftime('%d.%m.%Y %H:%M')}",
                "=" * 60, "",
            ]

            if stats_type == 'standard':
                sc = stats.get('status_counts', {})
                lines.append(f"{texts.WF_STATS_TOTAL}: {sc.get('total', 0)}")
                lines.append(f"{texts.WF_STATS_ACTIVE}: {sc.get('active', 0)}")
                lines.append(f"{texts.WF_STATS_INACTIVE}: {sc.get('inactive', 0)}")
                avgs = stats.get('averages', {})
                lines.append(f"{texts.WF_STATS_AVG_TENURE}: {avgs.get('tenure_years', 0)} {texts.WF_STATS_YEARS}")
                lines.append(f"{texts.WF_STATS_AVG_HOURS}: {stats.get('average_weekly_hours', 0)}")
                to = stats.get('turnover', {})
                lines.append(f"{texts.WF_STATS_TURNOVER}: {to.get('rate_percent', 0)} %")
                lines.append("")

                gd = stats.get('gender_distribution', {})
                if gd.get('labels'):
                    lines.append(f"--- {texts.WF_STATS_GENDER} ---")
                    for lbl, val in zip(gd['labels'], gd['data']):
                        lines.append(f"  {lbl}: {val}")
                    lines.append("")

                dd = stats.get('department_distribution', {})
                if dd.get('labels'):
                    lines.append(f"--- {texts.WF_STATS_DEPARTMENTS} ---")
                    for lbl, val in zip(dd['labels'], dd['data']):
                        lines.append(f"  {lbl}: {val}")
                    lines.append("")

                jlt = stats.get('join_leave_trends', {})
                if jlt.get('labels'):
                    lines.append(f"--- {texts.WF_STATS_TRENDS} ---")
                    for i, lbl in enumerate(jlt['labels']):
                        lines.append(f"  {lbl}: +{jlt['joins'][i]} / -{jlt['leaves'][i]}")
            else:
                ad = stats.get('average_duration', {})
                lines.append(f"{texts.WF_STATS_AVG_DURATION}: {ad.get('years', 0)} {texts.WF_STATS_YEARS}")
                lines.append(f"{texts.WF_STATS_EMPLOYEES_INCLUDED}: {ad.get('total_employees_included', 0)}")
                lines.append("")
                ee = stats.get('entries_exits', {})
                if ee.get('labels'):
                    lines.append(f"--- {texts.WF_STATS_ENTRIES_EXITS} ---")
                    for i, lbl in enumerate(ee['labels']):
                        lines.append(f"  {lbl}: +{ee['entries'][i]} / -{ee['exits'][i]}")

            with open(path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines))

            if self._toast_manager:
                self._toast_manager.show_success(texts.WF_STATS_EXPORTED)
        except Exception as e:
            logger.error(f"Export-Fehler: {e}")
            if self._toast_manager:
                self._toast_manager.show_error(f"{texts.WF_STATS_EXPORT_ERROR}: {e}")

    def refresh(self):
        prev_employer_id = self._employer_combo.currentData()
        self._employer_combo.blockSignals(True)
        self._load_employers()

        if prev_employer_id is not None:
            for i in range(self._employer_combo.count()):
                if self._employer_combo.itemData(i) == prev_employer_id:
                    self._employer_combo.setCurrentIndex(i)
                    break
        self._employer_combo.blockSignals(False)
